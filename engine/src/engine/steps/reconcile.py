"""reconcile step — align two OCR copies at paragraph level, adjudicate words against a third.

Faithful port of the top-level ``reconcile.py``. The reconciliation mechanics (SequenceMatcher
alignment, rapidfuzz near-duplicate detection, chunk-anchor Copy-3 location, majority voting) are
Latin-script-neutral and ported verbatim. The two seams carrying a language/book opinion come
from config:

  - ``score_word``'s accepted-accent set         → ``cfg.language.word_score_accents``
  - raw-OCR chapter segmentation + boilerplate    → ``lang.split_raw_chapters`` / ``lang.strip_boilerplate``

I/O follows the live ``DATA_DIR`` seam, now workspace-contained: the OCR copies + Copy-3 page maps
are read from ``ws.data``; ``reconciled_chapters.json``, ``flagged_segments.json``,
``chapter_pages.json`` and ``reconciled_raw.txt`` are written there via the containment-checked
``ws.resolve``.

The live ``reconcile()`` also supports a ``--chapter`` subset/resume mode and writes
``reconciled_chapters.json`` incrementally for crash-safety; this port runs the full book and
writes once at the end — the final artifacts are identical (the subset path is deferred per
ENGINE_M3_PLAN.md).
"""

from __future__ import annotations

import json
import re
import unicodedata
from difflib import SequenceMatcher
from functools import lru_cache
from statistics import median

from ..config.models import RawSegmentation, ResolvedConfig
from ..contracts.markers import PAGE_MARKER_RE
from ..errors import MissingInputError
from ..lang.base import LanguagePlugin
from ..paths import BookWorkspace
from ..util.jsonio import atomic_write_json, atomic_write_text
from ..util.text import collapse_spaces, normalize_for_comparison, rejoin_lines

# Pipeline artifact names — the live data/ filenames, now workspace-relative.
COPY1_FILE = "copy1_raw.txt"
COPY2_FILE = "copy2_raw.txt"
COPY3_PRO_FILE = "copy3_raw.txt"
COPY3_FLASH_FILE = "copy3_flash.txt"
COPY3_FLASH_PAGE_MAP = "copy3_flash_page_map.json"
COPY3_PRO_PAGE_MAP = "copy3_pro_page_map.json"
RECONCILED_FILE = "reconciled_chapters.json"
FLAGGED_FILE = "flagged_segments.json"
CHAPTER_PAGES_FILE = "chapter_pages.json"
RECONCILED_RAW_FILE = "reconciled_raw.txt"

# The OCR ``⟨PAGE:N⟩`` page marker grammar (``PAGE_MARKER_RE``) is single-sourced in
# ``contracts.markers`` so the ``ocr`` emitter and this parser cannot drift (plan F6).

# Bracket/paren noise inside a word — the one language-neutral score_word penalty pattern.
_BRACKET_NOISE = re.compile(r"[(){}[\]|\\^~`]")
_MIN_DECLARED_SECTION_CHARS = 50


def split_declared_raw_sections(
    text: str,
    spec: RawSegmentation,
    *,
    running_heads: tuple[str, ...] = (),
) -> list[dict]:
    """Split an ordered flat collection from manifest-declared full-line boundaries.

    The manifest owns every book/edition-specific pattern. The engine owns only the state machine:
    trim front/back matter, open exactly the next declared section, treat repeats of the current or
    prior heading as furniture, and fail loud on missing or out-of-order future boundaries.
    """
    if spec.kind != "flat_sections":
        raise MissingInputError(f"unsupported raw segmentation kind: {spec.kind!r}")
    ids = tuple(section.id for section in spec.sections)
    if not ids or len(set(ids)) != len(ids):
        raise MissingInputError("raw flat-section ids must be non-empty and unique")

    try:
        start_re = re.compile(r"\s*(?:" + spec.body_start_after_pattern + r")\s*$")
        end_res = tuple(
            re.compile(r"\s*(?:" + pattern + r")\s*$")
            for pattern in spec.body_end_patterns
        )
        section_res = tuple(
            re.compile(r"\s*(?:" + section.heading_pattern + r")\s*$")
            for section in spec.sections
        )
        running_head_res = tuple(
            re.compile(r"\s*(?:" + pattern + r")\s*$") for pattern in running_heads
        )
    except re.error as exc:
        raise MissingInputError(f"invalid raw segmentation regex: {exc}") from exc

    lines = text.splitlines()
    start = next((index for index, line in enumerate(lines) if start_re.fullmatch(line)), None)
    if start is None:
        raise MissingInputError(
            "raw flat-section body-start anchor was not found; refusing to split possible TOC text"
        )

    stop = len(lines)
    if end_res:
        stop = next(
            (
                index
                for index, line in enumerate(lines[start + 1 :], start=start + 1)
                if any(pattern.fullmatch(line) for pattern in end_res)
            ),
            len(lines),
        )

    bodies: list[list[str]] = [[] for _ in spec.sections]
    current = -1
    for line in lines[start + 1 : stop]:
        matches = tuple(
            index for index, pattern in enumerate(section_res) if pattern.fullmatch(line)
        )
        if len(matches) > 1:
            raise MissingInputError(
                f"raw line matches multiple declared section headings: {line!r}"
            )
        if matches:
            matched = matches[0]
            expected = current + 1
            if matched == expected:
                current = matched
            elif matched <= current:
                # Repeated current/prior title heads are page furniture, never new sections.
                pass
            else:
                missing = [section.id for section in spec.sections[expected:matched]]
                raise MissingInputError(
                    f"raw section heading {spec.sections[matched].id!r} appeared before expected "
                    f"section(s) {missing}; refusing to reorder or merge content"
                )
            continue
        if any(pattern.fullmatch(line) for pattern in running_head_res):
            continue
        if current >= 0:
            bodies[current].append(line)

    if current != len(spec.sections) - 1:
        missing = [section.id for section in spec.sections[current + 1 :]]
        raise MissingInputError(f"raw witness is missing declared section boundary(s): {missing}")

    result: list[dict] = []
    for section, body_lines in zip(spec.sections, bodies, strict=True):
        body = "\n".join(body_lines).strip()
        if len(body) < _MIN_DECLARED_SECTION_CHARS:
            raise MissingInputError(
                f"raw section {section.id!r} is empty or too short ({len(body)} chars)"
            )
        result.append(
            {"id": section.id, "title": section.title, "part": 0, "text": body}
        )
    return result


@lru_cache(maxsize=None)
def _score_patterns(accents: str) -> tuple[re.Pattern, re.Pattern, re.Pattern]:
    """Compile score_word's three accent-dependent patterns once per accent set."""
    return (
        re.compile(f"[{accents}]"),                    # reward a real accent
        re.compile(f"[^a-zA-Z{accents}'\\-]"),         # penalise a non-letter inside the word
        re.compile(f"^[a-zA-Z{accents}]+[.,;:!?]*$"),  # reward an all-letters "clean" word
    )


def score_word(word: str, accents: str) -> int:
    """Score a word for likely OCR correctness; higher = more likely correct.

    The accepted-accent set (``accents``, from ``cfg.language.word_score_accents``) is the one
    language seam — every other rule is Latin-script-neutral. Faithful to live ``score_word``.
    """
    reward_accent, penalise_nonletter, clean_word = _score_patterns(accents)
    score = 0

    if "*" in word:
        score -= 10
    if _BRACKET_NOISE.search(word):
        score -= 8  # brackets/parens inside a word = OCR noise

    if reward_accent.search(word):
        score += 5

    inner = word.strip(".,;:!?\"'")
    if penalise_nonletter.search(inner):
        score -= 5

    if len(word) > 1 and re.search(r"[A-Z]", word[1:]):
        score -= 4  # mid-word capital (voM, incoQseiamente)

    if "ii" in word.lower():
        score -= 3  # doubled-i often a misread 'u'

    if clean_word.match(word):
        score += 2

    return score


def split_paragraphs(text: str) -> list[str]:
    """Split chapter text into paragraphs (blank-line separated, lines rejoined)."""
    rejoined = rejoin_lines(text)
    return [p.strip() for p in rejoined.split("\n\n") if p.strip()]


def _is_near_duplicate(
    norm_text: str, included_norms: list[str], threshold: float = 75,
) -> bool:
    """Is ``norm_text`` a near-duplicate of an already-included paragraph?

    rapidfuzz handles OCR-variant matching better than difflib; a concatenated-window check
    catches a paragraph whose content one witness merged across several others keep separate.
    """
    from rapidfuzz import fuzz

    if not norm_text or len(norm_text) < 20:
        return True  # too short to be meaningful — skip

    for inc in included_norms:
        if fuzz.ratio(norm_text, inc) > threshold:
            return True
        if len(norm_text) <= len(inc) and fuzz.partial_ratio(norm_text, inc) >= 90:
            return True

    if len(norm_text) >= 200 and len(included_norms) >= 3:
        window_size = max(3, len(norm_text) // 150)
        window_size = min(window_size, len(included_norms))
        for i in range(len(included_norms) - window_size + 1):
            window = "".join(included_norms[i : i + window_size])
            if len(window) < len(norm_text) // 2:
                continue
            if fuzz.partial_ratio(norm_text, window) >= 90:
                return True

    return False


def _split_merged_chapters(ch_map1: dict, ch_map2: dict, all_ids: list[str]) -> None:
    """Split Copy2 chapters that absorbed an adjacent chapter Copy2 is missing.

    When Copy2 lacks a chapter Copy1 has, that content was merged into the preceding Copy2
    chapter; split it back using Copy1's boundaries as a guide.
    """
    c1_ids = set(ch_map1.keys())
    c2_ids = set(ch_map2.keys())
    missing_from_c2 = c1_ids - c2_ids
    if not missing_from_c2:
        return

    for ch_id in sorted(missing_from_c2):
        c1_missing = ch_map1.get(ch_id)
        if not c1_missing:
            continue

        ch_num = int(ch_id.split("ch")[1])
        part = ch_id.split("_")[0]
        prev_id = f"{part}_ch{ch_num - 1:02d}"
        c2_host = ch_map2.get(prev_id)
        c1_prev = ch_map1.get(prev_id)
        if not c2_host or not c1_prev:
            continue

        if len(c2_host["text"]) < len(c1_prev["text"]) * 1.4:
            continue

        c1_prev_len = len(c1_prev["text"])
        c1_total = c1_prev_len + len(c1_missing["text"])
        split_fraction = c1_prev_len / c1_total
        approx_split = int(len(c2_host["text"]) * split_fraction)

        text = c2_host["text"]
        best_break = approx_split
        for offset in range(0, min(2000, len(text) - approx_split)):
            for pos in [approx_split + offset, approx_split - offset]:
                if 0 < pos < len(text) - 1 and text[pos:pos + 2] == "\n\n":
                    best_break = pos
                    break
            else:
                continue
            break

        host_text = text[:best_break].rstrip()
        split_text = text[best_break:].lstrip()
        if not split_text:
            continue

        c2_host["text"] = host_text
        ch_map2[ch_id] = {
            "id": ch_id,
            "title": c1_missing["title"],
            "part": c1_missing["part"],
            "text": split_text,
        }
        print(f"    Split {prev_id} in Copy2: {prev_id}={len(host_text):,} + "
              f"{ch_id}={len(split_text):,} chars")


def align_paragraphs(
    paras1: list[str], paras2: list[str]
) -> list[tuple[str | None, str | None]]:
    """Align paragraphs from two copies using SequenceMatcher opcodes."""
    norm1 = [normalize_for_comparison(p) for p in paras1]
    norm2 = [normalize_for_comparison(p) for p in paras2]

    aligned: list[tuple[str | None, str | None]] = []
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, norm1, norm2).get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                aligned.append((paras1[i1 + k], paras2[j1 + k]))
        elif tag == "replace":
            len1 = i2 - i1
            len2 = j2 - j1
            for k in range(max(len1, len2)):
                p1 = paras1[i1 + k] if k < len1 else None
                p2 = paras2[j1 + k] if k < len2 else None
                aligned.append((p1, p2))
        elif tag == "insert":
            for k in range(j1, j2):
                aligned.append((None, paras2[k]))
        elif tag == "delete":
            for k in range(i1, i2):
                aligned.append((paras1[k], None))
    return aligned


def _build_norm_map(text: str) -> tuple[str, list[int]]:
    """Normalize text for searching while tracking original character positions.

    Mirrors ``normalize_for_comparison`` (lowercase, strip accents, a-z only) but returns a map
    from each normalized char index back to its position in the original text.
    """
    lowered = text.lower()
    nfkd = unicodedata.normalize("NFKD", lowered)

    nfkd_to_orig: list[int] = []
    orig_idx = 0
    for orig_char in lowered:
        decomposed = unicodedata.normalize("NFKD", orig_char)
        for _ in decomposed:
            nfkd_to_orig.append(orig_idx)
        orig_idx += 1

    norm_chars: list[str] = []
    norm_to_orig: list[int] = []
    for i, c in enumerate(nfkd):
        if not unicodedata.combining(c) and "a" <= c <= "z":
            norm_chars.append(c)
            norm_to_orig.append(nfkd_to_orig[i])

    return "".join(norm_chars), norm_to_orig


def _find_copy3_region(
    para_norm: str, ch3_norm: str, search_start: int = 0,
) -> tuple[int, int] | None:
    """Locate the region of Copy 3's normalized text matching a paragraph (chunk-anchor search)."""
    if len(para_norm) < 20:
        return None

    n_chunks = max(1, min(5, len(para_norm) // 8))
    chunk_size = len(para_norm) // n_chunks
    chunks = []
    for i in range(n_chunks):
        start = i * chunk_size
        end = start + chunk_size if i < n_chunks - 1 else len(para_norm)
        chunks.append((start, para_norm[start:end]))

    margin = min(200, search_start)
    scan_from = search_start - margin

    estimated_starts = []
    for chunk_offset, chunk_text in chunks:
        pos = ch3_norm.find(chunk_text, scan_from)
        if pos >= 0:
            estimated_starts.append(pos - chunk_offset)

    min_required = 1 if n_chunks == 1 else 2
    if len(estimated_starts) < min_required:
        return None

    med_start = int(median(estimated_starts))
    if med_start < search_start - margin:
        return None

    pad = max(20, len(para_norm) // 10)
    norm_start = max(0, med_start)
    norm_end = min(len(ch3_norm), med_start + len(para_norm) + pad)
    return norm_start, norm_end


def _find_copy3_text(
    para_text: str,
    ch3_norm: str,
    ch3_orig: str,
    norm_to_orig: list[int],
    search_start: int = 0,
) -> tuple[str | None, int]:
    """Find Copy 3 text corresponding to a paragraph. Returns (extracted_text|None, new_cursor)."""
    para_norm = normalize_for_comparison(para_text)

    region = _find_copy3_region(para_norm, ch3_norm, search_start)
    if region is None:
        return None, search_start
    norm_start, norm_end = region

    orig_start = norm_to_orig[norm_start] if norm_start < len(norm_to_orig) else len(ch3_orig)
    orig_end = norm_to_orig[min(norm_end, len(norm_to_orig) - 1)] if norm_end > 0 else 0

    while orig_start > 0 and ch3_orig[orig_start - 1] not in " \n\t":
        orig_start -= 1
    while orig_end < len(ch3_orig) and ch3_orig[orig_end] not in " \n\t":
        orig_end += 1

    extracted = ch3_orig[orig_start:orig_end].strip()
    if not extracted:
        return None, search_start

    extracted_norm = normalize_for_comparison(extracted)
    ratio = SequenceMatcher(None, para_norm, extracted_norm).ratio()
    if ratio < 0.50:
        return None, search_start

    return extracted, norm_end


def reconcile_words(
    text1: str,
    text2: str,
    chapter_id: str,
    para_idx: int,
    accents: str,
    *,
    first_witness_spine: bool = False,
) -> tuple[str, list[dict]]:
    """Reconcile two versions of a paragraph at word level. Returns (best_text, flagged).

    With ``first_witness_spine``, the first witness owns extent: the second may correct aligned
    tokens but may not inject unmatched text. This is the conservative mode for two OCRs of one
    physical scan whose paragraph boundaries differ.
    """
    words1 = text1.split()
    words2 = text2.split()

    result: list[str] = []
    flagged: list[dict] = []

    for tag, i1, i2, j1, j2 in SequenceMatcher(None, words1, words2).get_opcodes():
        if tag == "equal":
            result.extend(words1[i1:i2])
        elif tag == "replace":
            len1 = i2 - i1
            len2 = j2 - j1
            for k in range(max(len1, len2)):
                w1 = words1[i1 + k] if k < len1 else None
                w2 = words2[j1 + k] if k < len2 else None

                if w1 is None:
                    if not first_witness_spine:
                        result.append(w2)
                elif w2 is None:
                    result.append(w1)
                else:
                    s1 = score_word(w1, accents)
                    s2 = score_word(w2, accents)
                    result.append(w1 if s1 >= s2 else w2)

                    if (
                        abs(s1 - s2) <= 2
                        and normalize_for_comparison(w1) != normalize_for_comparison(w2)
                    ):
                        flagged.append({
                            "chapter": chapter_id,
                            "paragraph": para_idx,
                            "word_copy1": w1,
                            "word_copy2": w2,
                            "score1": s1,
                            "score2": s2,
                            "chosen": w1 if s1 >= s2 else w2,
                            "resolution_method": "score_heuristic",
                        })
        elif tag == "insert":
            if not first_witness_spine:
                result.extend(words2[j1:j2])
        elif tag == "delete":
            result.extend(words1[i1:i2])

    return " ".join(result), flagged


def reconcile_words_3way(
    text1: str, text2: str, text3: str, chapter_id: str, para_idx: int, accents: str
) -> tuple[str, list[dict]]:
    """Reconcile three versions at word level: 2-of-3 majority auto-accepts; all-differ scores
    and flags for triage. Returns (best_text, flagged)."""
    words1 = text1.split()
    words2 = text2.split()
    words3 = text3.split()

    align_1_2: dict[int, int] = {}
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, words1, words2).get_opcodes():
        if tag in ("equal", "replace"):
            for k in range(min(i2 - i1, j2 - j1)):
                align_1_2[i1 + k] = j1 + k

    align_1_3: dict[int, int] = {}
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, words1, words3).get_opcodes():
        if tag in ("equal", "replace"):
            for k in range(min(i2 - i1, j2 - j1)):
                align_1_3[i1 + k] = j1 + k

    result: list[str] = []
    flagged: list[dict] = []

    for i, w1 in enumerate(words1):
        j = align_1_2.get(i)
        k = align_1_3.get(i)
        w2 = words2[j] if j is not None else None
        w3 = words3[k] if k is not None else None

        n1 = normalize_for_comparison(w1)
        n2 = normalize_for_comparison(w2) if w2 else None
        n3 = normalize_for_comparison(w3) if w3 else None

        if n2 is not None and n3 is not None:
            if n1 == n2 and n1 == n3:
                result.append(w1)
                continue
            elif n1 == n2:
                result.append(w1)
                continue
            elif n1 == n3:
                result.append(w1)
                continue
            elif n2 == n3:
                result.append(w2)  # prefer w2 (the different physical copy)
                continue
            else:
                s1 = score_word(w1, accents)
                s2 = score_word(w2, accents)
                s3 = score_word(w3, accents)
                best_score = max(s1, s2, s3)
                if s1 == best_score:
                    chosen = w1
                elif s2 == best_score:
                    chosen = w2
                else:
                    chosen = w3
                result.append(chosen)

                ctx_start = max(0, i - 5)
                ctx_end = min(len(words1), i + 6)
                flagged.append({
                    "chapter": chapter_id,
                    "paragraph": para_idx,
                    "word_copy1": w1,
                    "word_copy2": w2,
                    "word_copy3": w3,
                    "score1": s1,
                    "score2": s2,
                    "score3": s3,
                    "chosen": chosen,
                    "resolution_method": "all_differ",
                    "context": " ".join(words1[ctx_start:ctx_end]),
                })
                continue

        if w2 is not None and n1 != n2:
            s1 = score_word(w1, accents)
            s2 = score_word(w2, accents)
            chosen = w1 if s1 >= s2 else w2
            result.append(chosen)
            if abs(s1 - s2) <= 2:
                flagged.append({
                    "chapter": chapter_id,
                    "paragraph": para_idx,
                    "word_copy1": w1,
                    "word_copy2": w2,
                    "word_copy3": w3,
                    "score1": s1,
                    "score2": s2,
                    "score3": score_word(w3, accents) if w3 else None,
                    "chosen": chosen,
                    "resolution_method": "score_heuristic",
                    "context": "",
                })
        elif w3 is not None and n1 != n3:
            s1 = score_word(w1, accents)
            s3 = score_word(w3, accents)
            result.append(w1 if s1 >= s3 else w3)
        else:
            result.append(w1)

    return " ".join(result), flagged


def _strip_page_markers(text: str) -> tuple[str, dict[int, int]]:
    """Remove ``⟨PAGE:N⟩`` markers and build a clean-char-offset → page-number map."""
    page_breaks: dict[int, int] = {}
    clean_parts: list[str] = []
    clean_pos = 0

    for line in text.split("\n"):
        m = PAGE_MARKER_RE.match(line.strip())
        if m:
            page_breaks[clean_pos] = int(m.group(1))
        else:
            clean_parts.append(line)
            clean_pos += len(line) + 1  # +1 for newline

    return "\n".join(clean_parts), page_breaks


# --- orchestration --------------------------------------------------------------------- #

def run(
    *,
    workspace: BookWorkspace,
    cfg: ResolvedConfig,
    lang: LanguagePlugin,
) -> dict:
    """Reconcile the OCR copies in ``workspace`` and write the four artifacts.

    Reads the manifest-declared voting witnesses: ``copy1_raw.txt`` is required, ``copy2_raw.txt``
    participates only when the manifest declares a ``copy2`` source, and a Gemini witness
    (``copy3_raw.txt``, else ``copy3_flash.txt``) participates when present. At least two voting
    witnesses are required. Other downloaded roles (for example ``comparison``) are evidence but
    never enter reconciliation. Writes
    ``reconciled_chapters.json``, ``flagged_segments.json``, ``chapter_pages.json`` and
    ``reconciled_raw.txt`` into ``ws.data``. Returns a summary dict.
    """
    ws = workspace
    accents = cfg.language.word_score_accents

    declared_roles = {source.role for source in cfg.manifest.sources}
    missing = []
    if "copy1" not in declared_roles or not (ws.data / COPY1_FILE).is_file():
        missing.append(COPY1_FILE)
    copy2_declared = "copy2" in declared_roles
    if copy2_declared and not (ws.data / COPY2_FILE).is_file():
        missing.append(COPY2_FILE)
    if missing:
        raise MissingInputError(
            f"reconcile needs its manifest-declared OCR copies in {ws.data}; "
            f"missing: {', '.join(missing)} "
            f"(run `--step download` first)"
        )

    copy1_text = (ws.data / COPY1_FILE).read_text(encoding="utf-8")
    copy2_text = (
        (ws.data / COPY2_FILE).read_text(encoding="utf-8") if copy2_declared else ""
    )

    copy3_path = ws.data / COPY3_PRO_FILE
    if not copy3_path.exists():
        copy3_path = ws.data / COPY3_FLASH_FILE
    has_copy3 = copy3_path.exists()
    copy3_text = ""
    copy3_page_breaks: dict[int, int] = {}
    if has_copy3:
        copy3_text, copy3_page_breaks = _strip_page_markers(
            copy3_path.read_text(encoding="utf-8")
        )
        print(f"  Copy 3 loaded ({len(copy3_text):,} chars, "
              f"{len(copy3_page_breaks)} page markers)")

    if not copy2_declared and not has_copy3:
        raise MissingInputError(
            "reconcile needs at least two voting witnesses; the manifest declares Copy 1 but no "
            "Copy 2, and no Copy 3 OCR output was found"
        )
    if copy2_declared and has_copy3:
        print("  3-way mode: Copy 1 + Copy 2 + Copy 3")
    elif copy2_declared:
        print("  2-way mode: Copy 1 + Copy 2")
    else:
        print("  2-way mode: Copy 1 + Copy 3")

    # Book-level page-furniture (the title running head) the segmenter must drop — from the
    # manifest, not the cross-title language plugin (BR-004).
    running_heads = cfg.structure.running_heads

    raw_segmentation = cfg.structure.raw_segmentation

    def split_witness(raw_text: str) -> tuple[str, list[dict]]:
        if raw_segmentation is not None:
            prepared = collapse_spaces(raw_text)
            return prepared, split_declared_raw_sections(
                prepared, raw_segmentation, running_heads=running_heads
            )
        prepared = collapse_spaces(lang.strip_boilerplate(raw_text))
        return prepared, lang.split_raw_chapters(
            prepared, running_heads=running_heads
        )

    stripped1, chapters1 = split_witness(copy1_text)
    stripped2, chapters2 = split_witness(copy2_text) if copy2_declared else ("", [])
    ch_map1 = {ch["id"]: ch for ch in chapters1}
    ch_map2 = {ch["id"]: ch for ch in chapters2}

    ch_map3: dict[str, dict] = {}
    chapters3: list[dict] = []
    stripped3 = ""
    if has_copy3:
        stripped3, chapters3 = split_witness(copy3_text)  # same scan as Copy 1
        ch_map3 = {ch["id"]: ch for ch in chapters3}
        print(f"  Copy 3 chapters: {len(chapters3)}")

    if raw_segmentation is None and copy2_declared:
        _split_merged_chapters(ch_map1, ch_map2, sorted(ch_map1.keys()))
    if raw_segmentation is None:
        all_ids = sorted(set(ch_map1.keys()) | set(ch_map2.keys()) | set(ch_map3.keys()))
    else:
        # Flat-section order is a declared book invariant; alphabetic ID sorting would reorder it.
        all_ids = [section.id for section in raw_segmentation.sections]

    reconciled_chapters: list[dict] = []
    all_flagged: list[dict] = []
    stats = {
        "shared": 0, "copy1_only": 0, "copy2_only": 0, "copy3_only": 0,
        "total_flagged": 0, "all_differ": 0,
    }

    for ch_id in all_ids:
        ch1 = ch_map1.get(ch_id)
        ch2 = ch_map2.get(ch_id)
        ch3 = ch_map3.get(ch_id)

        available = [c for c in (ch1, ch2, ch3) if c is not None]
        if not available:
            continue
        ref = available[0]
        print(f"    {ch_id}:", end="", flush=True)

        if ch1 and ch2 and ch3:
            stats["shared"] += 1
            paras1 = split_paragraphs(ch1["text"])
            paras2 = split_paragraphs(ch2["text"])
            aligned = align_paragraphs(paras1, paras2)

            ch3_orig = rejoin_lines(ch3["text"])
            ch3_norm, norm_to_orig = _build_norm_map(ch3_orig)
            c3_search_pos = 0
            c3_matches = 0

            reconciled_paras: list[str] = []
            reconciled_norms: list[str] = []

            for para_idx, (p1, p2) in enumerate(aligned):
                ref_text = p1 or p2
                p3 = None
                if ref_text and len(normalize_for_comparison(ref_text)) >= 20:
                    p3, c3_search_pos = _find_copy3_text(
                        ref_text, ch3_norm, ch3_orig, norm_to_orig, c3_search_pos,
                    )
                    if p3:
                        c3_matches += 1

                if p1 is not None and p2 is not None:
                    if p3 is not None:
                        merged, flagged = reconcile_words_3way(p1, p2, p3, ch_id, para_idx, accents)
                    else:
                        merged, flagged = reconcile_words(p1, p2, ch_id, para_idx, accents)
                    reconciled_paras.append(merged)
                    reconciled_norms.append(normalize_for_comparison(merged))
                    all_flagged.extend(flagged)
                    stats["all_differ"] += sum(
                        1 for f in flagged if f.get("resolution_method") == "all_differ"
                    )
                elif p1 is not None or p2 is not None:
                    text = p1 if p1 is not None else p2
                    norm = normalize_for_comparison(text)
                    if not _is_near_duplicate(norm, reconciled_norms):
                        reconciled_paras.append(text)
                        reconciled_norms.append(norm)

            print(f" {len(aligned)} aligned → {len(reconciled_paras)} kept, "
                  f"{c3_matches} c3 matches", flush=True)
            reconciled_chapters.append({
                "id": ch_id, "title": ch1["title"], "part": ch1["part"],
                "text": "\n\n".join(reconciled_paras),
            })

        elif ch1 and ch3 and not copy2_declared:
            # Copy 3 is another OCR of Copy 1's physical scan, but its paragraph boundaries come
            # from rendered pages rather than IA's djvu text. Pairing the two paragraph lists by
            # SequenceMatcher can align unrelated blocks and then concatenate both sides at word
            # level, inflating the book. Copy 1 therefore owns paragraph order/extent; Copy 3 votes
            # only where a forward, normalized substring match anchors it to that paragraph.
            stats["shared"] += 1
            paras1 = split_paragraphs(ch1["text"])
            ch3_orig = rejoin_lines(ch3["text"])
            ch3_norm, norm_to_orig = _build_norm_map(ch3_orig)
            c3_search_pos = 0
            c3_matches = 0
            reconciled_paras = []

            for para_idx, p1 in enumerate(paras1):
                p3 = None
                if len(normalize_for_comparison(p1)) >= 20:
                    p3, c3_search_pos = _find_copy3_text(
                        p1, ch3_norm, ch3_orig, norm_to_orig, c3_search_pos,
                    )
                if p3 is None:
                    reconciled_paras.append(p1)
                    continue

                c3_matches += 1
                merged, flagged = reconcile_words(
                    p1, p3, ch_id, para_idx, accents, first_witness_spine=True,
                )
                for item in flagged:
                    item["word_copy3"] = item.pop("word_copy2")
                    item["score3"] = item.pop("score2")
                reconciled_paras.append(merged)
                all_flagged.extend(flagged)

            print(f" {len(paras1)} Copy 1 paras, {c3_matches} anchored Copy 3 matches", flush=True)
            reconciled_chapters.append({
                "id": ch_id, "title": ch1["title"], "part": ch1["part"],
                "text": "\n\n".join(reconciled_paras),
            })

        elif ch1 and ch2:
            stats["shared"] += 1
            paras1 = split_paragraphs(ch1["text"])
            paras2 = split_paragraphs(ch2["text"])
            aligned = align_paragraphs(paras1, paras2)

            reconciled_paras = []
            reconciled_norms = []
            for para_idx, (p1, p2) in enumerate(aligned):
                if p1 is None and p2 is not None:
                    norm = normalize_for_comparison(p2)
                    if not _is_near_duplicate(norm, reconciled_norms):
                        reconciled_paras.append(p2)
                        reconciled_norms.append(norm)
                elif p2 is None and p1 is not None:
                    norm = normalize_for_comparison(p1)
                    if not _is_near_duplicate(norm, reconciled_norms):
                        reconciled_paras.append(p1)
                        reconciled_norms.append(norm)
                elif p1 is not None and p2 is not None:
                    merged, flagged = reconcile_words(p1, p2, ch_id, para_idx, accents)
                    reconciled_paras.append(merged)
                    reconciled_norms.append(normalize_for_comparison(merged))
                    all_flagged.extend(flagged)

            print(f" {len(aligned)} aligned → {len(reconciled_paras)} kept", flush=True)
            reconciled_chapters.append({
                "id": ch_id, "title": ch1["title"], "part": ch1["part"],
                "text": "\n\n".join(reconciled_paras),
            })

        else:
            key = "copy1_only" if ch1 else ("copy2_only" if ch2 else "copy3_only")
            stats[key] += 1
            paras = split_paragraphs(ref["text"])
            print(f" single-source, {len(paras)} paras", flush=True)
            reconciled_chapters.append({
                "id": ch_id, "title": ref["title"], "part": ref["part"],
                "text": "\n\n".join(paras),
            })

    stats["total_flagged"] = len(all_flagged)

    # Page provenance from Copy 3 page markers (prefer the flash map, fall back to pro).
    chapter_pages: dict[str, list[int]] = {}
    if has_copy3 and copy3_page_breaks:
        page_map_path = ws.data / COPY3_FLASH_PAGE_MAP
        if not page_map_path.exists():
            page_map_path = ws.data / COPY3_PRO_PAGE_MAP
        if page_map_path.exists():
            page_map = json.loads(page_map_path.read_text(encoding="utf-8"))
            search_pos = 0
            for ch in chapters3:
                if not ch["text"]:
                    continue
                snippet = ch["text"][:80]
                ch_text_start = stripped3.find(snippet, search_pos)
                if ch_text_start < 0:
                    ch_text_start = stripped3.find(snippet)
                if ch_text_start >= 0:
                    ch_text_end = ch_text_start + len(ch["text"])
                    search_pos = ch_text_end
                    pages = set()
                    for entry in page_map:
                        if entry["char_end"] - entry["char_start"] < 500:
                            continue  # skip cover/blank/title/catalog pages
                        if entry["char_start"] <= ch_text_end and entry["char_end"] >= ch_text_start:
                            pages.add(entry["page"])
                    if pages:
                        chapter_pages[ch["id"]] = sorted(pages)
            atomic_write_json(ws.resolve("data", CHAPTER_PAGES_FILE), chapter_pages)

    # Human-readable dump (D4: golden-asserted) — verbatim live format.
    output_lines: list[str] = []
    for ch in reconciled_chapters:
        output_lines.append(f"=== {ch['id']} | {ch['title']} ===")
        output_lines.append(ch["text"])
        output_lines.append("")
    atomic_write_text(ws.resolve("data", RECONCILED_RAW_FILE), "\n".join(output_lines))

    atomic_write_json(ws.resolve("data", RECONCILED_FILE), reconciled_chapters)
    atomic_write_json(ws.resolve("data", FLAGGED_FILE), all_flagged)

    mode = "3-way" if copy2_declared and has_copy3 else "2-way"
    print(f"  Reconciled {len(reconciled_chapters)} chapters ({mode}); "
          f"flagged {stats['total_flagged']} word disagreements")

    return {
        "mode": mode,
        "chapters": len(reconciled_chapters),
        "flagged": stats["total_flagged"],
        "all_differ": stats["all_differ"],
        "chapter_pages": len(chapter_pages),
    }
