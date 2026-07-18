"""validate step — structure / threshold / word-quality checks on the cleaned text.

Faithful port of the top-level ``validate.py``. Every book/scan/language constant the live
script hardcoded now comes from ``cfg`` / ``lang``:

  - chapter-structure counts + thresholds       → ``cfg.structure.*``
  - part names (structural-header skip)          → ``cfg.structure.parts[].name``
  - the in-script character set                  → ``cfg.language.coverage`` (literal-char allowlist)
  - the page-marker artifact pattern             → ``cfg.source_noise.page_marker_artifact_pattern``
  - the frequency word set / spaCy NER model     → ``cfg.language.frequency_dictionary`` / ``spacy_model``
  - English-leak markers, function-word skips,   → ``cfg.language.english_markers`` / ``skip_words`` /
    the consonant alphabet                           ``consonant_alphabet``

The one language-specific *label* in the live report — the check named
``italian_char_coverage`` — is generalised to ``char_coverage`` here; its data (ratio,
issues, pass/fail) is reproduced exactly (see ``tests/golden/test_validate_golden``).

I/O follows the live DATA_DIR/OUTPUT_DIR seam, now workspace-contained: the cleaned text is
read from ``ws.output/<CLEAN_FILE>``, the reconciled witness from ``ws.data/<RECONCILED_FILE>``,
and the report written to ``ws.data/<REPORT_FILE>`` via the containment-checked ``ws.resolve``.
"""

from __future__ import annotations

import hashlib
import re
import string
from collections.abc import Sequence
from pathlib import Path

from ..config.models import CoverageSpec, ResolvedConfig, Structure
from ..dictionaries.frequency import load_word_set
from ..lang.base import LanguagePlugin
from ..paths import BookWorkspace, require_asset
from ..util.jsonio import atomic_write_json, read_json
from ..util.text import strip_accents

# Pipeline artifact names — the engine's generic names, carrying no language opinion. The
# live pipeline calls the cleaned text ``italian_clean.md``; the engine artifact is just
# ``clean.md`` (cleanup writes it in M4b; tests seed it). Per-book provenance lives in the
# book directory, not the filename.
CLEAN_FILE = "clean.md"
RECONCILED_FILE = "reconciled_chapters.json"
REPORT_FILE = "validation_report.json"

# Markdown provenance comment the pipeline embeds (``<!-- page:N -->``); language-neutral.
_PAGE_COMMENT_RE = re.compile(r"<!--\s*page:\d+\s*-->")

# A chapter with fewer real characters than this is treated as empty/broken. Generic floor.
MIN_CHAPTER_CHARS = 50
# word_quality emits an advisory note past this many unique flags. Unlike the high-severity
# ceiling (``word_quality_high_severity_max``, a per-book *gate* in manifest.structure), this
# is display-only — it never affects pass/fail — so it stays a fixed code constant rather than
# per-book config: a wrong value here has no functional consequence, only a longer/shorter
# advisory line. Promote it only if a real book needs to tune the *informational* threshold.
WORD_QUALITY_TOTAL_WARN = 200
# spaCy max_length guard — chunk the NER pass so large texts stay under the model limit.
_NER_CHUNK = 500_000

# Mid-word patterns: Latin-script mechanics, language-neutral (ASCII-only). Verbatim ports. The
# word regex itself is built per-run from ``cfg.language.word_letter_class`` (the "any word letter"
# script fact, sourced from config like cleanup/adjudicate — no longer an inline À-ÿ literal).
#
# _MID_NOISE is a faithful port of a branch that is *unreachable* in the live validate.py too:
# the word regex captures letters + apostrophes only, so a matched ``word`` can never contain a
# noise char (digit / bracket / <> / ^ \ |) for _MID_NOISE to find — the token simply splits at the
# noise instead, and "mid-word noise" therefore never appears in reasons. Kept for 1:1 fidelity
# with the live check list. Making it fire (e.g. scanning the raw line span) would flag tokens the
# live code does not and break the golden — an improvement *over* live for a deliberate later pass,
# not a silent change here.
_MID_NOISE = re.compile(r"[a-zA-Z][(\)\[\]{}^\\|<>0-9][a-zA-Z]")
_MID_CAPS = re.compile(r"[a-z][A-Z][a-z]")


# --- individual checks (each reads only the config it needs, for unit-testability) --------- #

def check_chapter_count(text: str, structure: Structure) -> dict:
    """Verify the part/chapter header counts match the book's declared structure."""
    h2_count = len(re.findall(r"^## ", text, re.MULTILINE))
    h3_count = len(re.findall(r"^### ", text, re.MULTILINE))

    issues = []
    if h2_count < structure.h2_min:
        issues.append(
            f"Expected at least {structure.h2_min} ## headers, found {h2_count}"
        )
    if h3_count != structure.h3_count:
        breakdown = ", ".join(f"{p.chapters} {p.name}" for p in structure.parts)
        issues.append(
            f"Expected {structure.h3_count} ### chapter headers ({breakdown}), found {h3_count}"
        )

    return {
        "name": "chapter_count",
        "passed": len(issues) == 0,
        "h2_count": h2_count,
        "h3_count": h3_count,
        "issues": issues,
    }


def check_no_empty_chapters(text: str, part_names: Sequence[str]) -> dict:
    """No ``###`` chapter should be empty/near-empty (structural part headers are skipped)."""
    issues = []
    sections = re.split(r"^(#{2,3}\s.+)$", text, flags=re.MULTILINE)

    i = 1  # Skip content before the first header.
    while i < len(sections) - 1:
        header = sections[i].strip()
        content = sections[i + 1].strip() if i + 1 < len(sections) else ""

        if any(name in header for name in part_names):
            i += 2
            continue

        clean_content = _PAGE_COMMENT_RE.sub("", content).strip()
        if header.startswith("###") and len(clean_content) < MIN_CHAPTER_CHARS:
            issues.append(f"Near-empty chapter: {header} ({len(clean_content)} chars)")

        i += 2

    return {"name": "no_empty_chapters", "passed": len(issues) == 0, "issues": issues}


def check_quote_balance(text: str) -> dict:
    """Balanced guillemets and smart double quotes — typographic, language-neutral."""
    issues = []

    left_g = text.count("«")   # «
    right_g = text.count("»")  # »
    if left_g != right_g:
        issues.append(f"Guillemet imbalance: {left_g} « vs {right_g} »")

    left_dq = text.count("“")  # "
    right_dq = text.count("”")  # "
    if left_dq != right_dq:
        issues.append(f"Smart double quote imbalance: {left_dq} “ vs {right_dq} ”")

    return {"name": "quote_balance", "passed": len(issues) == 0, "issues": issues}


def _coverage_set(spec: CoverageSpec) -> frozenset[str]:
    """Build the in-script character allowlist from the language's ``CoverageSpec``. A plain
    set — no regex — so there is no syntax/escaping/range surface to get wrong; a forgotten
    character simply shows up as foreign (visible), never a silent mis-parse."""
    allowed: set[str] = set(spec.letters) | set(spec.punctuation)
    if spec.ascii_letters:
        allowed |= set(string.ascii_letters)
    if spec.digits:
        allowed |= set(string.digits)
    return frozenset(allowed)


def check_char_coverage(text: str, allowed: frozenset[str], foreign_char_max: float) -> dict:
    """Flag if more than ``foreign_char_max`` of non-whitespace chars fall outside the
    language's in-script set. ``allowed`` is the literal-character allowlist from
    ``_coverage_set`` (whitespace is excluded below, so it need not be in the set)."""
    non_ws_chars = [c for c in text if not c.isspace()]
    if not non_ws_chars:
        return {"name": "char_coverage", "passed": True, "issues": []}

    foreign_chars = [c for c in non_ws_chars if c not in allowed]
    ratio = len(foreign_chars) / len(non_ws_chars)

    issues = []
    if ratio > foreign_char_max:
        sample = set(foreign_chars[:50])
        issues.append(
            f"{ratio:.2%} non-script chars ({len(foreign_chars):,} of "
            f"{len(non_ws_chars):,}). Sample: {sorted(sample)}"
        )

    return {
        "name": "char_coverage",
        "passed": ratio <= foreign_char_max,
        "foreign_char_ratio": round(ratio * 100, 3),
        "issues": issues,
    }


def check_no_ascii_remnants(text: str, page_marker_pattern: str) -> dict:
    """Detect leftover page-marker artifacts and uppercase+digit OCR-noise runs."""
    issues = []

    page_markers = re.findall(page_marker_pattern, text)
    if page_markers:
        issues.append(
            f"{len(page_markers)} page marker artifacts remain (e.g., {page_markers[:3]})"
        )

    # Uppercase+digit runs that look like noise — but only when they contain a digit (pure
    # all-caps words like ANGELES/POPOLO are legitimate). A roman-numeral run is excluded for
    # free: the lookahead requires a digit, and roman numerals have none, so they never match.
    noise_runs = re.findall(r"\b(?=[A-Z\d]*\d)[A-Z\d]{5,}\b", text)
    if noise_runs:
        issues.append(f"{len(noise_runs)} potential OCR noise runs (e.g., {noise_runs[:3]})")

    return {"name": "no_ascii_remnants", "passed": len(issues) == 0, "issues": issues}


def check_word_quality(
    text: str,
    *,
    word_set: frozenset[str] | set[str],
    nlp,
    english_markers: set[str],
    skip_words: set[str],
    consonant_alphabet: str,
    word_letter_class: str,
    high_severity_max: int,
) -> dict:
    """Per-word OCR quality scan: dictionary lookup + pattern-based garble detection.

    Flags words absent from the frequency dictionary, mid-word noise/capitals, impossible
    consonant clusters, and English-marker words (possible LLM instruction leaks). spaCy NER
    over the full text supplies a proper-noun allowlist so place/person names aren't flagged.
    ``word_letter_class`` is the language's "any word letter" regex fragment (config, not an inline
    À-ÿ literal) — the tokeniser that splits the text into candidate words.
    """
    consonant_cluster = re.compile(f"[{consonant_alphabet}]{{4,}}", re.IGNORECASE)
    word_re = re.compile(rf"\b([{word_letter_class}]+(?:['''][{word_letter_class}]+)?)\b")

    # Proper-noun allowlist: legitimate names absent from the frequency dictionary.
    known_entities: set[str] = set()
    for chunk_start in range(0, len(text), _NER_CHUNK):
        doc = nlp(text[chunk_start:chunk_start + _NER_CHUNK])
        for ent in doc.ents:
            for token in ent.text.split():
                known_entities.add(token.lower().strip(".,;:!?\"'''«»—-"))

    chapter_sections = re.split(r"^(#{2,3}\s.+)$", text, flags=re.MULTILINE)

    all_flags: list[dict] = []
    chapter_name = "Header"

    for section in chapter_sections:
        if section.startswith("#"):
            chapter_name = section.strip("# \n")
            continue

        content = re.sub(r"<!--.*?-->", "", section)
        if not content.strip():
            continue

        for line in content.split("\n"):
            if not line.strip():
                continue

            for m in word_re.finditer(line):
                word = m.group(1)
                if "'" in word:
                    core = word.split("'")[0]
                elif "’" in word:
                    core = word.split("’")[0]
                else:
                    core = word
                lower = core.lower()

                if lower in skip_words or len(core) <= 1:
                    continue

                reasons = []

                if _MID_NOISE.search(word):  # unreachable (see _MID_NOISE note); faithful to live
                    reasons.append("mid-word noise")

                if _MID_CAPS.search(core):
                    reasons.append("mid-word capitals")

                if lower not in known_entities:
                    cluster_match = consonant_cluster.search(strip_accents(lower))
                    if cluster_match:
                        reasons.append(f"consonant cluster '{cluster_match.group()}'")

                if lower in english_markers:
                    reasons.append("English word")

                if len(core) >= 4 and not reasons and lower not in known_entities:
                    in_dict = (
                        lower in word_set
                        or strip_accents(lower) in word_set
                        or (core[0].isupper() and lower in word_set)
                    )
                    if not in_dict:
                        reasons.append("not in dictionary")

                if reasons:
                    ctx_start = max(0, m.start() - 30)
                    ctx_end = min(len(line), m.end() + 30)
                    all_flags.append({
                        "word": word,
                        "chapter": chapter_name,
                        "reasons": reasons,
                        "context": line[ctx_start:ctx_end].strip(),
                    })

    # Group by chapter, dedupe by word (first occurrence wins, preserving text order).
    by_chapter: dict[str, list[dict]] = {}
    for flag in all_flags:
        by_chapter.setdefault(flag["chapter"], []).append(flag)

    total_unique = 0
    chapter_summary = []
    for ch_name, flags in sorted(by_chapter.items()):
        seen_words: set[str] = set()
        unique_flags = []
        for f in flags:
            if f["word"].lower() not in seen_words:
                seen_words.add(f["word"].lower())
                unique_flags.append(f)
        by_chapter[ch_name] = unique_flags
        total_unique += len(unique_flags)
        chapter_summary.append(f"{ch_name}: {len(unique_flags)} flagged")

    # Consonant clusters in capitalised words are likely proper nouns — high-severity only
    # when the word is lowercase.
    high_severity = [f for f in all_flags if any(
        r in ("mid-word noise", "mid-word capitals", "English word")
        or (r.startswith("consonant cluster") and f["word"][0].islower())
        for r in f["reasons"]
    )]

    issues = []
    # The high-severity line is the *gate-failure explanation* — it fires iff the gate fails.
    # The live code coupled them implicitly (``passed = len==0`` + ``if high_severity:``, so it
    # warned iff it failed); generalising the gate to ``> high_severity_max`` preserves that
    # coupling at the configurable threshold (identical to live at the example book's max=0). The separate
    # total-flagged line below is the only purely-advisory one (it can fire on a passing check).
    if len(high_severity) > high_severity_max:
        issues.append(f"{len(high_severity)} high-severity flags (noise/garble patterns)")
    if total_unique > WORD_QUALITY_TOTAL_WARN:
        issues.append(
            f"{total_unique} total unique flagged words across {len(by_chapter)} chapters"
        )

    return {
        "name": "word_quality",
        "passed": len(high_severity) <= high_severity_max,
        "total_flagged": total_unique,
        "high_severity": len(high_severity),
        "by_chapter": {
            ch: [{"word": f["word"], "reasons": f["reasons"], "context": f["context"]}
                 for f in flags]
            for ch, flags in by_chapter.items()
        },
        "chapter_summary": chapter_summary,
        "issues": issues,
    }


def check_word_count_preservation(
    cleaned_text: str, reconciled_path: Path, retention_min: float
) -> dict:
    """Cleaned text must retain at least ``retention_min`` of the reconciled word count.

    Cleanup intentionally drops OCR noise lines, so some reduction is expected; a drop below
    the floor signals data loss beyond normal noise removal.
    """
    chapters = read_json(reconciled_path)
    reconciled_words = sum(len(ch["text"].split()) for ch in chapters)

    clean = re.sub(r"^#+\s.*$", "", cleaned_text, flags=re.MULTILINE)
    clean = _PAGE_COMMENT_RE.sub("", clean)
    clean = re.sub(r"^---$", "", clean, flags=re.MULTILINE)
    clean = re.sub(r"^\*.*\*$", "", clean, flags=re.MULTILINE)  # metadata lines
    cleaned_words = len(clean.split())

    if reconciled_words == 0:
        return {"name": "word_count_preservation", "passed": False,
                "issues": ["Reconciled text has 0 words"]}

    ratio = cleaned_words / reconciled_words
    passed = ratio >= retention_min

    issues = []
    if not passed:
        issues.append(
            f"Cleaned text is only {ratio:.0%} of reconciled ({cleaned_words:,} vs "
            f"{reconciled_words:,} words) — possible data loss"
        )

    return {
        "name": "word_count_preservation",
        "passed": passed,
        "reconciled_words": reconciled_words,
        "cleaned_words": cleaned_words,
        "retention_pct": round(ratio * 100, 1),
        "issues": issues,
    }


# --- orchestration --------------------------------------------------------------------- #

def _print_summary(report: dict) -> None:
    """Compact console summary (the per-chapter word_quality dump the live script printed was
    a debugging aid, not part of the report — the report's ``by_chapter`` carries that data)."""
    for check in report["checks"]:
        status = "✓" if check["passed"] else "✗"
        print(f"  {status} {check['name']}")
        for issue in check.get("issues", []):
            print(f"      {issue}")
    for issue in report.get("issues", []):  # report-level/fatal issues
        print(f"  ! {issue}")
    print(f"\n  Overall: {report['overall'].upper()}")


def run(
    *,
    workspace: BookWorkspace,
    cfg: ResolvedConfig,
    lang: LanguagePlugin,
) -> dict:
    """Validate the cleaned text in ``workspace`` and write ``validation_report.json``.

    Returns the report dict — uniform schema ``{overall, issues, checks}`` on every path
    (top-level ``issues`` carries report-level/fatal errors; per-check issues live in each
    check). Reads ``ws.output/clean.md`` (required) and ``ws.data/reconciled_chapters.json``
    (the word-count witness; degraded check if absent).
    """
    ws = workspace
    clean_path = ws.output / CLEAN_FILE
    if not clean_path.is_file():
        # Uniform schema: every report carries top-level overall / issues / checks. Here the
        # report-level ``issues`` channel holds the fatal preflight error and checks is empty.
        report = {"overall": "error",
                  "issues": [f"{CLEAN_FILE} not found at {clean_path}"],
                  "checks": []}
        _print_summary(report)
        return report

    text = clean_path.read_text(encoding="utf-8")
    reconciled_path = ws.data / RECONCILED_FILE

    structure = cfg.structure
    lp = cfg.language
    nlp = lang.load_spacy(lp.spacy_model, disable=["parser", "lemmatizer"])
    word_set = load_word_set(require_asset(lp.frequency_dictionary, kind="file"))

    checks = [
        check_chapter_count(text, structure),
        check_no_empty_chapters(text, [p.name for p in structure.parts]),
        check_quote_balance(text),
        check_char_coverage(text, _coverage_set(lp.coverage), structure.foreign_char_max),
        check_no_ascii_remnants(text, cfg.source_noise.page_marker_artifact_pattern),
        check_word_quality(
            text,
            word_set=word_set,
            nlp=nlp,
            english_markers=set(lp.english_markers),
            skip_words=set(lp.skip_words),
            consonant_alphabet=lp.consonant_alphabet,
            word_letter_class=lp.word_letter_class,
            high_severity_max=structure.word_quality_high_severity_max,
        ),
    ]

    if reconciled_path.is_file():
        checks.append(
            check_word_count_preservation(text, reconciled_path, structure.retention_min)
        )
    else:
        checks.append({
            "name": "word_count_preservation",
            "passed": False,
            "issues": [f"{RECONCILED_FILE} not found — cannot compare"],
        })

    overall = "pass" if all(c["passed"] for c in checks) else "fail"
    # Top-level ``issues`` is the report-level/fatal channel (per-check issues live in each
    # check); empty on a normal run. Present on every report so the schema is uniform.
    report = {
        "overall": overall,
        "input_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "issues": [],
        "checks": checks,
    }

    _print_summary(report)

    report_path = ws.resolve("data", REPORT_FILE)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(report_path, report)
    print(f"  Report: {report_path}")

    return report
