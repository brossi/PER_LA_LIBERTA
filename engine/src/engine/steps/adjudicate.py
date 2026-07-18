"""adjudicate step — classify unresolved hyphenated tokens against a period dictionary.

Faithful port of the top-level ``adjudicate.py``. Each flagged hyphen token (from cleanup's
``review_flags.json``) is classified by looking up its parts in a period-appropriate
monolingual dictionary:

  - **noise**     — OCR garbage (too few alphabetic characters) → flag for removal
  - **ner**       — proper noun (capitalised, parts absent from the dictionary) → keep hyphen
  - **compound**  — both parts are real words → keep hyphen
  - **corrected** — a broken word with a plausible dictionary-validated fix → suggest it
  - **unknown**   — needs LLM adjudication with dictionary context

**Two seams carry the language/book opinion, both injected:**

  - the dictionary membership check ("is W a real period word?") is a ``DictionaryOracle``.
    M3 binds it to the **monolingual** period dictionary (Zingarelli 1922, the example book's); M6 will
    re-express it on the ≥2-of-N period-dictionary oracle (branch register **BR-001**) without
    touching the classifier, which depends only on the oracle's ``(found, matches)`` contract.
  - the OCR boundary substitutions used by the correction passes come from
    ``cfg.source_noise.boundary_substitutions`` (the source scan's ``i→r``/``i→e`` confusions).

**No equivalence golden (F2/D3).** ``adjudicate``'s paired input (``review_flags.json``) is
unrecoverable for the committed output, so the classification *branches* are pinned by unit
tests (``test_adjudicate_engine``) rather than a reproduced artifact. The two LLM-context
helpers (``DictionaryOracle.lookup`` / ``dictionary_context_for_flags``) are ported here — they
are cleanup's prompt-context API — but their *call site* belongs to cleanup (M4b); they hang off
the same oracle so M4b receives them ready-made.

**Result contract (opinionated, diverges from live).** ``run`` always writes a *self-describing
envelope* — ``{"input_present", "tokens", "stats", "results"}`` — never the live script's bare
``{chapter_id: [...]}``. A missing ``review_flags.json`` is written as an **explicit** null result
(``input_present: false``, empty ``results``), deliberately distinct from a populated run *and*
from a silent empty ``{}`` (which could equally signal an upstream failure that ate the flags).
The classified entries inside ``results`` are byte-faithful to live. Recorded as a one-way-door
step-contract decision (branch register **BR-005**).
"""

from __future__ import annotations

import re
from pathlib import Path

from ..config.models import ResolvedConfig
from ..lang.base import LanguagePlugin
from ..paths import BookWorkspace, require_asset
from ..util.jsonio import atomic_write_json, read_json
from ..util.text import build_fold_table

REVIEW_FLAGS_FILE = "review_flags.json"
RESULTS_FILE = "adjudication_results.json"


def _is_noise(token: str) -> bool:
    """OCR noise = too few alphabetic characters. Verbatim from live ``_is_noise``."""
    alpha = sum(1 for c in token if c.isalpha())
    return alpha < 3 or (len(token) > 3 and alpha / len(token) < 0.5)


def _search_chunk(word: str, chunk_text: str, word_letter_class: str) -> list[str]:
    """Lines where ``word`` appears as a standalone token (word-boundary match, ≤5 lines).

    Verbatim from live ``_search_chunk`` — boundary anchors stop ``fl`` matching inside ``ffle``.
    ``word_letter_class`` is the language's "any word letter" regex fragment (config, not an inline
    À-ÿ literal — sourced like cleanup/validate), so the boundary anchors are script-correct.
    """
    if not word or not chunk_text or len(word) < 3:
        return []
    pattern = re.compile(
        rf"(?<![{word_letter_class}])" + re.escape(word) + rf"(?![{word_letter_class}])",
        re.IGNORECASE,
    )
    matches = []
    for line in chunk_text.split("\n"):
        if pattern.search(line):
            matches.append(line.strip())
            if len(matches) >= 5:
                break
    return matches


class DictionaryOracle:
    """Membership oracle over one letter-chunked monolingual period dictionary.

    ``__call__(word) -> (found, matches)`` is the single seam ``adjudicate``'s classifier
    depends on, and the one point M6's ≥2-of-N oracle (BR-001) will replace. ``name`` labels the
    dictionary in LLM prompt context. The chunk cache is per-oracle (one instance per run).
    """

    def __init__(
        self, name: str, dict_dir: Path, word_letter_class: str, fold_table: dict
    ) -> None:
        self.name = name
        self._dir = Path(dict_dir)
        self._word_letter_class = word_letter_class
        # Accent fold for chunk selection + the accent-insensitive retry. Sourced from
        # ``cfg.language.accent_fold`` (the shared fixed table), not a duplicate in-step literal.
        self._fold_table = fold_table
        self._chunks: dict[str, str] = {}

    def _load_chunk(self, letter: str) -> str:
        if letter not in self._chunks:
            path = self._dir / f"{letter.lower()}.txt"
            self._chunks[letter] = path.read_text(encoding="utf-8") if path.exists() else ""
        return self._chunks[letter]

    def __call__(self, word: str) -> tuple[bool, list[str]]:
        """Is ``word`` a standalone entry in the dictionary? Verbatim ``_word_in_zingarelli``.

        Words < 3 chars are rejected (OCR-noise fragments yield false matches).
        """
        if not word or len(word) < 3:
            return False, []

        base = word[0].lower().translate(self._fold_table)
        chunk = self._load_chunk(base)
        matches = _search_chunk(word, chunk, self._word_letter_class)

        if not matches:  # accent-insensitive retry
            stripped = word.translate(self._fold_table)
            if stripped != word:
                matches = _search_chunk(stripped, chunk, self._word_letter_class)

        return bool(matches), matches

    def lookup(self, word: str, context_lines: int = 3) -> str | None:
        """Up to ``context_lines`` matching dictionary lines for ``word`` (cleanup's LLM-context
        API). Port of live ``zingarelli_lookup``; the consumer (cleanup) lands in M4b."""
        found, matches = self(word)
        if not found:
            stripped = word.translate(self._fold_table)
            if stripped != word:
                _, matches = self(stripped)
        if matches:
            return "\n".join(matches[:context_lines])
        return None


def dictionary_context_for_flags(flags: list[dict], oracle: DictionaryOracle) -> str:
    """Formatted dictionary evidence for flagged tokens, for an LLM prompt. Port of live
    ``zingarelli_context_for_flags`` with the dictionary name taken from the oracle."""
    if not flags:
        return ""

    sections = []
    for item in flags:
        token = item["token"]
        parts = []
        for part in (item["left"], item["right"]):
            context = oracle.lookup(part)
            if context:
                parts.append(f"  '{part}': {context.split(chr(10))[0][:120]}")
            else:
                parts.append(f"  '{part}': not found in {oracle.name}")
        sections.append(f"Token: {token}\n" + "\n".join(parts))

    return (
        f"=== {oracle.name} Dictionary Reference ===\n"
        + "\n\n".join(sections)
        + "\n=== End Dictionary Reference ===\n"
    )


def _try_corrections(
    left: str, right: str, oracle: DictionaryOracle, boundary_subs: dict
) -> str | None:
    """Find the intended word with the same passes as dehyphenation, validated against the
    oracle. Verbatim from live ``_try_corrections`` with the boundary table injected."""
    # Pass 1: simple join.
    joined = left + right
    if oracle(joined)[0]:
        return joined

    # Pass 2: boundary substitution at the end of ``left``.
    for pos in range(max(0, len(left) - 2), len(left)):
        ch = left[pos].lower()
        if ch in boundary_subs:
            for repl in boundary_subs[ch]:
                candidate = left[:pos] + repl + left[pos + 1:] + right
                if oracle(candidate)[0]:
                    return candidate

    # Pass 3: boundary substitution at the start of ``right``.
    for pos in range(min(2, len(right))):
        ch = right[pos].lower()
        if ch in boundary_subs:
            for repl in boundary_subs[ch]:
                candidate = left + right[:pos] + repl + right[pos + 1:]
                if oracle(candidate)[0]:
                    return candidate

    # Pass 4a: drop a boundary 'i' (OCR doubling of 'r').
    if len(left) > 1 and left[-1].lower() == "i":
        candidate = left[:-1] + right
        if oracle(candidate)[0]:
            return candidate

    # Pass 4b: drop a duplicated boundary character.
    if len(left) > 1 and len(right) > 1 and left[-1].lower() == right[0].lower():
        candidate = left[:-1] + right
        if oracle(candidate)[0]:
            return candidate

    return None


def _confident(word: str, matches: list[str]) -> bool:
    """Short words (≤5 chars) need ≥2 hits to trust; longer words trust a single match.
    Verbatim from live ``adjudicate._confident``."""
    return len(matches) >= (2 if len(word) <= 5 else 1)


_STATS_KEYS = ("compound", "ner", "noise", "corrected", "unknown")


def classify_flags(
    flags: dict, *, oracle: DictionaryOracle, boundary_subs: dict
) -> tuple[dict, dict]:
    """Classify each flagged token. Returns ``(results, stats)``.

    ``results`` maps chapter_id → list of entries (each is the original flag item plus a
    ``resolution`` and ``detail``, and a ``suggestion`` for corrections). Faithful port of live
    ``adjudicate()`` minus its prints; the classifier touches the dictionary only through
    ``oracle`` and the boundary table only through ``boundary_subs``.
    """
    results: dict[str, list[dict]] = {}
    stats = {k: 0 for k in _STATS_KEYS}

    for chapter_id, items in flags.items():
        chapter_results = []

        for item in items:
            token = item["token"]
            left = item["left"]
            right = item["right"]
            original_reason = item["reason"]

            entry = {**item}

            # 1. noise
            if _is_noise(token):
                entry["resolution"] = "noise"
                entry["detail"] = "OCR garbage — too few alphabetic characters"
                stats["noise"] += 1
                chapter_results.append(entry)
                continue

            # 2. NER — flagged as a name candidate; keep the hyphen if the parts aren't words,
            #    or if both parts are capitalised even when one is also a dictionary word.
            if original_reason == "ner_candidate":
                left_found, _ = oracle(left)
                right_found, _ = oracle(right)
                if not left_found and not right_found:
                    entry["resolution"] = "ner"
                    entry["detail"] = f"Proper noun — neither part in {oracle.name}"
                    stats["ner"] += 1
                    chapter_results.append(entry)
                    continue
                if left[0].isupper() and right[0].isupper():
                    entry["resolution"] = "ner"
                    note = []
                    if left_found:
                        note.append(f"'{left}' is also a dictionary word")
                    if right_found:
                        note.append(f"'{right}' is also a dictionary word")
                    entry["detail"] = f"Proper noun (both caps). {'; '.join(note)}"
                    stats["ner"] += 1
                    chapter_results.append(entry)
                    continue

            # 3. compound — both parts real words (≥4 chars each, confident hit counts).
            left_found, left_matches = oracle(left)
            right_found, right_matches = oracle(right)
            is_compound = (
                left_found and right_found
                and len(left) >= 4 and len(right) >= 4
                and _confident(left, left_matches)
                and _confident(right, right_matches)
            )
            if is_compound:
                entry["resolution"] = "compound"
                entry["detail"] = (
                    f"Both parts in {oracle.name} "
                    f"({len(left_matches)}+{len(right_matches)} hits)"
                )
                stats["compound"] += 1
                chapter_results.append(entry)
                continue

            # 4. corrected — a dictionary-validated repair.
            correction = _try_corrections(left, right, oracle, boundary_subs)
            if correction:
                _, matches = oracle(correction)
                entry["resolution"] = "corrected"
                entry["suggestion"] = correction
                entry["detail"] = (
                    f"{oracle.name} match: {matches[0][:80] if matches else correction}"
                )
                stats["corrected"] += 1
                chapter_results.append(entry)
                continue

            # 5. unknown — partial or no match; needs LLM adjudication.
            if left_found and not right_found:
                entry["detail"] = f"Left part '{left}' in {oracle.name}; right '{right}' not found"
            elif right_found and not left_found:
                entry["detail"] = f"Right part '{right}' in {oracle.name}; left '{left}' not found"
            else:
                entry["detail"] = f"Neither part in {oracle.name}"
            entry["resolution"] = "unknown"
            stats["unknown"] += 1
            chapter_results.append(entry)

        if chapter_results:
            results[chapter_id] = chapter_results

    return results, stats


def _build_oracle(cfg: ResolvedConfig) -> DictionaryOracle:
    """Bind the membership oracle to the language's **monolingual** period dictionary.

    adjudicate needs an "is this a real Italian word?" membership test; the monolingual period
    dictionary (Zingarelli 1922, the example book's) is that, whereas the bilingual IT→EN dictionaries are a
    different shape. The ≥2-of-N combination across all period dictionaries is M6's job (BR-001).
    """
    mono = [d for d in cfg.language.period_dictionaries if d.kind == "monolingual"]
    if not mono:
        raise ValueError(
            f"adjudicate needs a monolingual period dictionary; language "
            f"{cfg.language.language_id!r} declares none"
        )
    pd = mono[0]
    return DictionaryOracle(
        pd.name,
        require_asset(pd.dir, kind="dir"),
        cfg.language.word_letter_class,
        build_fold_table(cfg.language.accent_fold),
    )


def _write_envelope(ws: BookWorkspace, *, input_present: bool, results: dict, stats: dict) -> dict:
    """Write (and return) the self-describing result envelope. The envelope is the step's only
    output shape — ``input_present`` makes the no-input case an explicit declaration, never a
    silent empty/absent artifact (see module docstring / BR-005)."""
    envelope = {
        "input_present": input_present,
        "tokens": sum(stats.values()),
        "stats": stats,
        "results": results,
    }
    atomic_write_json(ws.resolve("data", RESULTS_FILE), envelope)
    return envelope


def run(
    *,
    workspace: BookWorkspace,
    cfg: ResolvedConfig,
    lang: LanguagePlugin,
    oracle: DictionaryOracle | None = None,
) -> dict:
    """Adjudicate ``review_flags.json`` in ``workspace`` → ``adjudication_results.json``.

    ``oracle`` defaults to the monolingual period dictionary (``_build_oracle``); it is injectable
    so fast tests can drive the classifier without loading the real chunked dictionary. Always
    writes (and returns) the result envelope; a missing input yields an explicit no-input envelope.
    """
    ws = workspace
    flags_path = ws.data / REVIEW_FLAGS_FILE
    if not flags_path.is_file():
        print(f"  No review flags found ({flags_path.name}); writing explicit no-input result")
        return _write_envelope(
            ws, input_present=False, results={}, stats={k: 0 for k in _STATS_KEYS}
        )

    flags = read_json(flags_path)
    if oracle is None:
        oracle = _build_oracle(cfg)
    boundary_subs = cfg.source_noise.boundary_substitutions

    results, stats = classify_flags(flags, oracle=oracle, boundary_subs=boundary_subs)

    total = sum(stats.values())
    print(f"  Adjudicated {total} tokens across {len(results)} chapters:")
    for classification, count in stats.items():
        if count:
            print(f"    {classification:12s}: {count}")

    return _write_envelope(ws, input_present=True, results=results, stats=stats)
