"""cleanup step — deterministic OCR-artifact removal + an optional LLM correction pass.

Faithful port of the top-level ``cleanup.py`` (the largest single file). Two surfaces:

  - **Deterministic core** (``use_llm=False``): noise-line removal, stray-symbol stripping,
    dehyphenation, punctuation normalisation, paragraph rejoining, sentence de-duplication, and
    symspell+spaCy dictionary correction. This is the milestone's one equivalence golden (D4):
    ``test_cleanup_golden`` reproduces the live ``clean_text`` output per chapter byte-for-byte.
  - **LLM-correction pass** (``use_llm=True``): per-chapter (sync) or whole-book (Batch API)
    Claude correction through an injectable ``Chat`` seam (BR-014), with a full-text cache and the
    deterministic post-LLM flag bookkeeping (``reconcile_flags``). Property-tested (no LLM golden).

**No source-noise / Italian literal in this step's code (BR-002 / M4b-D1, proven by
``test_cleanup_neutrality``).** Every accent/letter class and every OCR-noise pattern the core
parameterises on is sourced from ``cfg.language`` / ``cfg.source_noise`` and compiled once into a
``CleanupRules`` bundle — the step interpolates config *strings* into its regexes, never a baked
``À-ÿ``/``£``. Universal typographic punctuation (``«» — " "``) and universal OCR-decoration glyphs
(``■ • ¶ §``) stay in code: they carry no language/typeface opinion (any scan/language uses them),
so they are engine-general mechanics, not relocatable source-noise.

The detcore golden isolates ``clean_text`` *per chapter* (``{id: {text, flags}}``), not the wrapped
markdown: the wrapper bakes book identity (title/subtitle/author/part names) which is config here,
so the equivalence check stays on the algorithm while the wrapper is config-driven + property-tested.
"""

from __future__ import annotations

import difflib
import os
import re
import time
from dataclasses import dataclass
from typing import Protocol

from ..config.models import ResolvedConfig
from ..dictionaries.frequency import load_word_set
from ..dictionaries.symspell import load_symspell
from ..errors import BackendError, MissingInputError, RegenerationGuardError
from ..lang.base import LanguagePlugin
from ..paths import BookWorkspace, require_asset
from ..prompts.templating import PromptTemplate, build_prompt_context
from ..util.jsonio import atomic_write_json, atomic_write_text, read_json
from ..util.retry import retry_api_call
from ..util.text import build_fold_table
# Oracle reuse (F6/refinement #7): adjudicate ported these "specifically so cleanup can reuse them".
from .adjudicate import DictionaryOracle, _build_oracle, dictionary_context_for_flags

# Artifact names — generic engine names; per-book provenance lives in the book dir, not the filename.
CLEAN_FILE = "clean.md"                                   # cleanup's output (validate reads it)
RECONCILED_FILE = "reconciled_chapters.json"              # input (reconcile produces it)
CHAPTER_PAGES_FILE = "chapter_pages.json"                 # optional page provenance (reconcile)
REVIEW_FLAGS_FILE = "review_flags.json"                   # sidecar adjudicate consumes
REVIEW_FLAGS_REMAINING_FILE = "review_flags_remaining.json"  # post-LLM surviving flags

#: Env escape mirroring the live ``PER_LA_LIBERTA_ALLOW_REGEN`` (M4b-D2). Deliberate friction.
ENGINE_ALLOW_REGEN_ENV = "ENGINE_ALLOW_REGEN"

# Edge punctuation stripped before spell-checking a token — straight + smart quotes, guillemets,
# dashes. Universal typography (the exact set the live ``_correct_token`` strips); written as
# explicit code points so the byte-identical set is unambiguous, not a glyph that could mis-encode.
_TOKEN_STRIP = ".,;:!?\"'“”‘’«»—-"

# Universal OCR-decoration glyphs that never carry text (scanner artifacts, any language): the four
# non-ASCII ones (■ • ¶ §) as code points; the rest ASCII noise. Stripped anywhere in a line.
_DECORATION_RE = re.compile("[■•¶§|~`@#%=+<>{}\\[\\]\\\\]")
_CARET_RE = re.compile(r"(?<!\w)\^|\^(?!\w)")             # freestanding caret between non-word chars
_DIGITS_ONLY_RE = re.compile(r"^\d+$")                    # a bare page number


# --- config-derived rule bundle ---------------------------------------------------------- #

@dataclass(frozen=True, slots=True)
class CleanupRules:
    """Every config-derived datum the deterministic core parameterises on, compiled once.

    Built by ``build_rules(cfg)`` from ``cfg.language`` (accent/letter classes) and
    ``cfg.source_noise`` (OCR-noise tables). One frozen bundle keeps ``clean_text``'s signature
    small and keeps the step code free of any baked Italian/source-noise literal: every regex below
    interpolates a config *string* (``word_letter_class``/``accented_letters``) or compiles a config
    *pattern* (the source-noise fields).
    """

    fold_table: dict
    substitution_rules: tuple[tuple[str, str], ...]
    boundary_substitutions: dict
    ligature_substitutions: tuple[tuple[str, str], ...]
    char_substitutions: tuple[tuple[re.Pattern, str], ...]
    inline_page_marker_patterns: tuple[re.Pattern, ...]
    noise_line_patterns: tuple[re.Pattern, ...]
    page_marker_line_re: re.Pattern
    # Regexes built from the language's letter classes (config strings, not baked À-ÿ):
    hyphen_token_re: re.Pattern        # dehyphenate_text — ([wlc]{2,})-([wlc]{2,})
    punct_rules: tuple[tuple[re.Pattern, str], ...]
    flig_word_re: re.Pattern           # f-ligature flag scan — \b([wlc]{4,})\b
    real_word_short_re: re.Pattern     # is_noise :231 — ^[a-zA-Z{accented}]+$
    real_word_3_re: re.Pattern         # is_noise :244 — ^[a-zA-Z{accented}]{3,}$
    real_word_4_re: re.Pattern         # is_noise :257 — ^[wlc]{4,}$
    para_lower_re: re.Pattern          # clean_text :684 — [.!?"]\n\n([wlc])
    spacing_fix_re: re.Pattern         # clean_text :680 — ([wlc][,;:])([wlc])


def _build_punct_rules(wlc: str) -> tuple[tuple[re.Pattern, str], ...]:
    """The punctuation-normalisation rules. Order matters — garbled quote patterns before doubled
    punctuation. Two rules (mid-word comma/backtick → apostrophe) interpolate the word-letter class;
    the rest are universal typography. Verbatim from the live ``_PUNCT_RULES``."""
    return (
        (re.compile(r"(?<=[\w.,;:!?]) +'\s+'"), '"'),
        (re.compile(r"'\s+' +(?=\w)"), '"'),
        (re.compile(r"'\s+'"), '"'),
        (re.compile(r"[\^*]\s*'"), '"'),
        (re.compile(r"\*\s*\*"), '"'),
        (re.compile(r"(?:;\s*){2,};?"), ";"),
        (re.compile(r"(?:,\s*){2,},?"), ","),
        (re.compile(r"(?::\s*){2,}:?"), ":"),
        (re.compile(r"[«»]"), '"'),            # stray guillemets → double quote
        (re.compile(r"<<"), '"'),
        (re.compile(r">>"), '"'),
        (re.compile(rf"(?<=[{wlc}]),(?=[{wlc}])"), "'"),  # mid-word comma → apostrophe
        (re.compile(rf"(?<=[{wlc}])`(?=[{wlc}])"), "'"),  # mid-word backtick → apostrophe
        (re.compile(r"-{2,}"), "—"),                # double/triple hyphen → em-dash
        (re.compile(r"(?<=\w)\s+\^\s+(?=\w)"), " "),
    )


def build_rules(cfg: ResolvedConfig) -> CleanupRules:
    """Compile the per-run rule bundle from the resolved config (language + source-noise)."""
    lp = cfg.language
    sn = cfg.source_noise
    wlc = lp.word_letter_class      # permissive "any word letter" class, e.g. "a-zA-ZÀ-ÿ"
    acc = lp.accented_letters       # canonical accented-letter superset, e.g. "àèìòùéÀÈÌÒÙÉ"
    return CleanupRules(
        fold_table=build_fold_table(lp.accent_fold),
        substitution_rules=sn.substitution_rules,
        boundary_substitutions=sn.boundary_substitutions,
        ligature_substitutions=sn.ligature_substitutions,
        char_substitutions=tuple((re.compile(p), r) for p, r in sn.char_substitutions),
        inline_page_marker_patterns=tuple(re.compile(p) for p in sn.inline_page_marker_patterns),
        noise_line_patterns=tuple(re.compile(p) for p in sn.noise_line_patterns),
        page_marker_line_re=re.compile(sn.page_marker_line_pattern),
        hyphen_token_re=re.compile(rf"([{wlc}]{{2,}})-([{wlc}]{{2,}})"),
        punct_rules=_build_punct_rules(wlc),
        flig_word_re=re.compile(rf"\b([{wlc}]{{4,}})\b"),
        real_word_short_re=re.compile(rf"^[a-zA-Z{acc}]+$"),
        real_word_3_re=re.compile(rf"^[a-zA-Z{acc}]{{3,}}$"),
        real_word_4_re=re.compile(rf"^[{wlc}]{{4,}}$"),
        para_lower_re=re.compile(rf"[.!?\"]\n\n([{wlc}])"),
        spacing_fix_re=re.compile(rf"([{wlc}][,;:])([{wlc}])"),
    )


# --- pure deterministic helpers ---------------------------------------------------------- #

def _in_word_set(word: str, word_set, fold_table: dict) -> bool:
    """Dictionary membership, accent-insensitive (1913 text uses accento facoltativo; OCR adds
    spurious accents). Accept a match if the accent-folded form exists. Verbatim ``_in_word_set``
    with the fold table from ``cfg.language.accent_fold`` instead of an in-step ``_ACCENT_MAP``."""
    lower = word.lower()
    if lower in word_set:
        return True
    stripped = lower.translate(fold_table)
    return stripped != lower and stripped in word_set


def is_noise_line(line: str, rules: CleanupRules) -> bool:
    """Whether a line is purely OCR decoration/noise. Faithful port of live ``is_noise_line``;
    the three full-line noise regexes (NOISE_LINE_PATTERN + separator + ``Disp.`` furniture) fold
    into ``rules.noise_line_patterns`` and are checked as one ``any(...)`` — order-independent
    because each can only force a True, and the intervening checks never short-circuit to False."""
    stripped = line.strip()
    if not stripped:
        return False
    if _DIGITS_ONLY_RE.match(stripped):
        return True
    if len(stripped) <= 4 and not rules.real_word_short_re.match(stripped):
        return True
    if any(p.match(stripped) for p in rules.noise_line_patterns):
        return True
    letters = sum(1 for c in stripped if c.isalpha())
    if len(stripped) > 3 and letters / len(stripped) < 0.3:
        return True
    # Page-marker furniture: short lines that are all caps/digits/OCR-noise with ≤1 real word.
    if rules.page_marker_line_re.match(stripped) and len(stripped) < 30:
        words = stripped.split()
        real_words = [w for w in words if rules.real_word_3_re.match(w)]
        if len(real_words) <= 1 and any(c.isdigit() for c in stripped):
            return True
    # Short mixed alphanumeric fragments with digits but no real words.
    if len(stripped) < 30 and any(c.isdigit() for c in stripped):
        words = stripped.split()
        real_words = [w for w in words if rules.real_word_4_re.match(w)]
        if not real_words:
            return True
    # Short lines with high special-character density.
    if 3 < len(stripped) < 20:
        special = sum(1 for c in stripped if not c.isalnum() and not c.isspace())
        if special / len(stripped) > 0.4:
            return True
    return False


def dehyphenate_token(left: str, right: str, word_set, rules: CleanupRules) -> str | None:
    """Try to rejoin a hyphenated token via the multi-pass strategy, returning the joined word or
    None. Verbatim from live ``dehyphenate_token`` with the boundary table + fold from config."""
    boundary = rules.boundary_substitutions
    fold = rules.fold_table

    joined = left + right
    if _in_word_set(joined, word_set, fold):
        return joined

    for pos in range(max(0, len(left) - 2), len(left)):
        ch = left[pos].lower()
        if ch in boundary:
            for replacement in boundary[ch]:
                candidate = left[:pos] + replacement + left[pos + 1:] + right
                if _in_word_set(candidate, word_set, fold):
                    return candidate

    for pos in range(min(2, len(right))):
        ch = right[pos].lower()
        if ch in boundary:
            for replacement in boundary[ch]:
                candidate = left + right[:pos] + replacement + right[pos + 1:]
                if _in_word_set(candidate, word_set, fold):
                    return candidate

    if len(left) > 1 and left[-1].lower() == "i":
        candidate = left[:-1] + right
        if _in_word_set(candidate, word_set, fold):
            return candidate
    if len(right) > 1 and right[0].lower() == "i":
        candidate = left + right[1:]
        if _in_word_set(candidate, word_set, fold):
            return candidate
    if (len(left) > 1 and len(right) > 1
            and left[-1].lower() == right[0].lower()
            and left[-1].lower() != "i"):
        candidate = left[:-1] + right
        if _in_word_set(candidate, word_set, fold):
            return candidate
        candidate = left + right[1:]
        if _in_word_set(candidate, word_set, fold):
            return candidate

    return None


def dehyphenate_text(text: str, word_set, rules: CleanupRules) -> tuple[str, list[dict]]:
    """Fix mid-line hyphenated tokens where joining produces a valid word; flag the unresolved ones
    for the review sidecar. Verbatim from live ``dehyphenate_text`` (the per-token log dropped — it
    is debug output, not part of the artifact)."""
    flags: list[dict] = []

    def _replacer(m: re.Match) -> str:
        left, right = m.group(1), m.group(2)
        if left.isdigit() or right.isdigit():
            return m.group(0)
        result = dehyphenate_token(left, right, word_set, rules)
        if result is not None:
            return result
        has_nonalpha = any(not c.isalpha() and c != "-" for c in m.group(0))
        both_caps = left[0].isupper() and right[0].isupper()
        if has_nonalpha:
            reason = "ocr_noise"
        elif both_caps:
            reason = "ner_candidate"
        else:
            reason = "unresolved"
        flags.append({
            "token": m.group(0), "left": left, "right": right,
            "offset": m.start(), "reason": reason,
        })
        return m.group(0)

    corrected = rules.hyphen_token_re.sub(_replacer, text)
    return corrected, flags


def _case_preserving_sub(pattern: str, replacement: str, text: str) -> str:
    """Apply a regex substitution preserving the original's capitalisation. Verbatim."""
    def _replacer(match):
        original = match.group(0)
        if original[0].isupper():
            return replacement[0].upper() + replacement[1:]
        return replacement
    return re.sub(r"\b" + pattern + r"\b", _replacer, text, flags=re.IGNORECASE)


def apply_pre_filters(text: str, rules: CleanupRules) -> str:
    """Apply the high-confidence garble→word substitution rules (source-noise word-fixes)."""
    for pattern, replacement in rules.substitution_rules:
        text = _case_preserving_sub(pattern, replacement, text)
    return text


def normalize_punctuation(text: str, rules: CleanupRules) -> tuple[str, int]:
    """Normalise OCR-garbled punctuation. Returns (text, total_replacements). Verbatim mechanics."""
    total = 0
    for pattern, replacement in rules.punct_rules:
        text, n = pattern.subn(replacement, text)
        total += n
    return text, total


def join_broken_paragraphs(text: str) -> str:
    """Rejoin paragraphs falsely split at OCR page boundaries (a continuation never starts
    lowercase). Verbatim from live — the redundant ``or first_char in "àèéìòù"`` clause is dropped:
    those six accented vowels are already lowercase, so ``.islower()`` covers them (M4b-D1)."""
    paragraphs = text.split("\n\n")
    if len(paragraphs) <= 1:
        return text

    result = [paragraphs[0]]
    for i in range(1, len(paragraphs)):
        prev = result[-1].rstrip()
        curr = paragraphs[i]
        curr_stripped = curr.lstrip()

        if not curr_stripped:
            result.append(curr)
            continue

        first_char = curr_stripped[0]
        should_join = False
        if prev.endswith("-"):
            should_join = True
        elif first_char.islower():
            should_join = True

        if should_join:
            if prev.endswith("-"):
                result[-1] = prev + curr_stripped
            else:
                result[-1] = prev + " " + curr_stripped
        else:
            result.append(curr)

    return "\n\n".join(result)


def deduplicate_sentences(text: str, rules: CleanupRules, min_len: int = 40) -> str:
    """Remove duplicate sentence fragments within each paragraph (OCR page-boundary merges).
    Verbatim from live; the normalisation folds accents via the config table."""
    fold = rules.fold_table
    paragraphs = text.split("\n\n")
    result = []
    for para in paragraphs:
        if len(para) < min_len * 2:
            result.append(para)
            continue
        sentences = re.split(r'(?<=[.!?])\s+', para)
        if len(sentences) < 2:
            result.append(para)
            continue
        def norm(s: str) -> str:
            return re.sub(r'\s+', ' ', s.lower().strip().translate(fold))
        seen = []
        kept = []
        for sent in sentences:
            n = norm(sent)
            if len(n) < min_len:
                kept.append(sent)
                continue
            is_dup = False
            for prev_n in seen:
                shorter, longer = (n, prev_n) if len(n) <= len(prev_n) else (prev_n, n)
                if shorter in longer:
                    is_dup = True
                    break
                if len(shorter) > min_len:
                    ratio = difflib.SequenceMatcher(None, shorter, longer).ratio()
                    if ratio > 0.75:
                        is_dup = True
                        break
            if is_dup:
                continue
            seen.append(n)
            kept.append(sent)
        result.append(' '.join(kept))
    return "\n\n".join(result)


def _is_accent_only_change(original: str, corrected: str, fold_table: dict) -> bool:
    """True if the only difference is accent removal — defer to the LLM (it has sentence context)
    rather than strip a legitimate accento facoltativo. Verbatim, folding via the config table."""
    return original.translate(fold_table) == corrected.translate(fold_table)


def apply_dictionary_correction(text: str, *, sym, nlp, fold_table: dict) -> str:
    """symspell dictionary correction over spaCy tokens (contraction-splitting + NER protection).
    Verbatim from live ``apply_dictionary_correction``; the speller + NER pipeline are injected
    (the engine's path-keyed loaders), and the accent-only-change guard folds via the config table.
    """
    from symspellpy import Verbosity

    def _correct_token(tok_text: str, is_proper: bool) -> str:
        inner = tok_text.strip(_TOKEN_STRIP)
        if not inner or not inner[0].isalpha():
            return tok_text
        # Protect proper nouns — but not ALL-CAPS words (≥4 chars) absent from the dictionary,
        # which spaCy mis-tags as PROPN/ORG when they are garbled OCR.
        if is_proper and not (inner.isupper() and len(inner) >= 4):
            return tok_text
        # Clitic prefixes ending in apostrophe (dell', l', d') — functional, not spell-checkable.
        if inner.endswith("'") or inner.endswith("’") or inner.endswith("`"):
            return tok_text
        if len(inner) <= 2:
            return tok_text

        is_allcaps = inner.isupper() and len(inner) >= 4
        edit_dist = 2 if is_allcaps else 1

        suggestions = sym.lookup(
            inner.lower(), Verbosity.TOP, max_edit_distance=edit_dist, include_unknown=True
        )
        if not suggestions:
            return tok_text

        best = suggestions[0]
        if best.distance == 0:
            return tok_text
        if best.distance <= edit_dist:
            corrected = best.term
            if _is_accent_only_change(inner.lower(), corrected, fold_table):
                return tok_text
            if inner[0].isupper():
                corrected = corrected[0].upper() + corrected[1:]
            if inner.isupper():
                corrected = corrected.upper()
            prefix = tok_text[:tok_text.index(inner[0])] if inner[0] in tok_text else ""
            suffix = tok_text[tok_text.rindex(inner[-1]) + 1:] if inner[-1] in tok_text else ""
            return prefix + corrected + suffix

        return tok_text

    result_lines = []
    for line in text.split("\n"):
        if not line.strip():
            result_lines.append(line)
            continue

        doc = nlp(line)

        proper_indices = set()
        for ent in doc.ents:
            if ent.label_ in ("PER", "LOC", "ORG", "MISC"):
                for i in range(ent.start, ent.end):
                    tok = doc[i]
                    if tok.pos_ == "PROPN" or tok.text[0].isupper():
                        proper_indices.add(i)
        for tok in doc:
            if tok.pos_ == "PROPN" and tok.text[0].isupper():
                proper_indices.add(tok.i)

        parts = []
        for tok in doc:
            is_proper = tok.i in proper_indices
            corrected = _correct_token(tok.text, is_proper)
            parts.append(corrected)
            parts.append(tok.whitespace_)

        result_lines.append("".join(parts).rstrip())

    return "\n".join(result_lines)


def clean_text(text: str, word_set, rules: CleanupRules, *, sym, nlp) -> tuple[str, list[dict], int]:
    """Apply the deterministic OCR cleanup to one chapter's text.

    Returns ``(cleaned_text, review_flags, punct_fixes)`` — the same contract as live ``clean_text``
    (review_flags lists tokens needing LLM review; punct_fixes counts punctuation normalisations).
    This is the equivalence-golden surface (D4): byte-identical to the live ``clean_text``.
    """
    # Remove noise lines (page numbers, OCR artifacts, separator patterns).
    text = "\n".join(line for line in text.split("\n") if not is_noise_line(line, rules))

    # Strip universal OCR-decoration glyphs and freestanding carets.
    text = _DECORATION_RE.sub("", text)
    text = _CARET_RE.sub("", text)
    # Source-noise char confusions whose replacement is opinion (e.g. £→E).
    for pat, repl in rules.char_substitutions:
        text = pat.sub(repl, text)

    text = re.sub(r"\n{3,}", "\n\n", text)
    text = join_broken_paragraphs(text)
    text = deduplicate_sentences(text, rules)
    text = apply_pre_filters(text, rules)
    text, punct_fixes = normalize_punctuation(text, rules)

    # Dehyphenate before dictionary correction so symspell never sees a broken fragment.
    text, review_flags = dehyphenate_text(text, word_set, rules)
    text = apply_dictionary_correction(text, sym=sym, nlp=nlp, fold_table=rules.fold_table)

    # Remove inline OCR page-marker artifacts (replaced by a neutral space).
    for pat in rules.inline_page_marker_patterns:
        text = pat.sub(" ", text)

    # Fix OCR asterisks replacing lost characters.
    text = re.sub(r"(\w)\*\s+(\w)", r"\1\2", text)
    text = re.sub(r"(\w)\*(\w)", r"\1\2", text)
    text = re.sub(r"'\*\s*", '"', text)
    text = re.sub(r'"\s*\*\s*', '"', text)
    text = re.sub(r"\s\*\s", " ", text)

    # Spacing around punctuation + ellipsis normalisation.
    text = re.sub(r"\s+([.,;:!?])", r"\1", text)
    text = re.sub(r"\.{4,}", "...", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Flag stray carets between words (lost text) for LLM review.
    stray_re = re.compile(r"(?<=\w) ([\^]) (?=\w)")
    for m in stray_re.finditer(text):
        ctx_start = max(0, m.start() - 30)
        ctx_end = min(len(text), m.end() + 30)
        review_flags.append({
            "token": m.group(1),
            "left": text[ctx_start:m.start()].split()[-1] if text[ctx_start:m.start()].split() else "",
            "right": text[m.end():ctx_end].split()[0] if text[m.end():ctx_end].split() else "",
            "offset": m.start(),
            "reason": "stray_symbol",
            "context": text[ctx_start:ctx_end],
        })

    # Flag probable f-ligature misreads: not-in-dictionary words that become valid with a ligature
    # correction (e.g. atterrandolo → afferrandolo).
    seen_flig: set[str] = set()
    for m in rules.flig_word_re.finditer(text):
        w = m.group(1)
        lower = w.lower()
        if lower in seen_flig or _in_word_set(lower, word_set, rules.fold_table):
            continue
        seen_flig.add(lower)
        for ocr_form, correct_form in rules.ligature_substitutions:
            pos = 0
            found = False
            while not found:
                idx = lower.find(ocr_form, pos)
                if idx == -1:
                    break
                candidate = lower[:idx] + correct_form + lower[idx + len(ocr_form):]
                if _in_word_set(candidate, word_set, rules.fold_table):
                    ctx_start = max(0, m.start() - 30)
                    ctx_end = min(len(text), m.end() + 30)
                    review_flags.append({
                        "token": w, "left": ocr_form, "right": correct_form,
                        "offset": m.start(), "reason": "f_ligature",
                        "context": text[ctx_start:ctx_end], "suggestion": candidate,
                    })
                    found = True
                pos = idx + 1

    # Fix missing space after punctuation (letter+punct+letter always needs a space here).
    text = rules.spacing_fix_re.sub(r"\1 \2", text)

    # Flag paragraph-initial lowercase (broken sentence / OCR noise at a page boundary). The class
    # is the permissive word-letter class; the ``.islower()`` filter reproduces the live lowercase
    # match (M4b-D1) without an in-step accent literal.
    for m in rules.para_lower_re.finditer(text):
        if not m.group(1).islower():
            continue
        ctx_start = max(0, m.start() - 30)
        ctx_end = min(len(text), m.end() + 30)
        review_flags.append({
            "token": m.group(1),
            "left": text[ctx_start:m.start() + 1],
            "right": text[m.start(1):ctx_end],
            "offset": m.start(1),
            "reason": "lowercase_after_break",
            "context": text[ctx_start:ctx_end],
        })

    return text.strip(), review_flags, punct_fixes


# --- config-driven markdown wrapper ------------------------------------------------------ #

def render_markdown(rendered: list[tuple[dict, str]], cfg: ResolvedConfig, chapter_pages: dict) -> str:
    """Assemble the bilingual-edition markdown from cleaned chapters (in sorted order).

    Book identity comes from config (``edition`` + ``structure.parts``), not baked: ``# title`` /
    ``*subtitle*`` / ``**author**``, a ``part==0`` chapter as ``##`` and others as ``###``, part
    headers from ``structure.parts[n-1].name`` with a ``---`` rule before each part after the first,
    and ``<!-- pages:a-b -->`` provenance from ``chapter_pages``. Property-tested (refinement #1/#3).
    """
    ed = cfg.manifest.edition
    parts = cfg.structure.parts
    byline = f"**{ed.author}** ({ed.year})"      # author bold, year outside the bold span
    md = [f"# {ed.title_it}", "", f"*{ed.subtitle_it}*", "", byline, "", "---", ""]

    current_part = 0
    for ch, text in rendered:
        part = ch["part"]
        if part != current_part:
            if part >= 1:
                if current_part >= 1:
                    md.extend(["---", ""])
                md.extend([f"## {parts[part - 1].name}", ""])
            current_part = part

        header = "##" if part == 0 else "###"
        md.extend([f"{header} {ch['title']}", ""])

        pages = chapter_pages.get(ch["id"])
        if pages:
            md.extend([f"<!-- pages:{pages[0]}-{pages[-1]} -->", ""])

        md.append(text)
        md.extend(["", ""])

    return "\n".join(md)


def _sort_chapters(chapters: list[dict]) -> list[dict]:
    """Stable sort by the existing ``part`` field — works for both id namespaces (short ``p1_ch01``
    and long ``p1_capitolo_primo``), unlike the live id-parsing sort which crashes on long ids
    (refinement #2). Part 0 (prefazione) sorts first; the input's per-part order is preserved."""
    return sorted(chapters, key=lambda ch: ch["part"])


# --- LLM correction: chat seam + prompt + post-processing (BR-014) ------------------------ #

_LLM_CORRECT_MODEL = "claude-sonnet-4-6"
_LLM_CORRECT_MAX_TOKENS = 128000

_PREAMBLE_RE = re.compile(
    r"^("
    r"(?:Here is|Here's|Below is)[\s\S]*?:\s*\n+"
    r"|(?:Ecco|Eil|E il|Ed ecco)[\s\S]*?:\s*\n+"
    r"|I'll[\s\S]*?[.:]\s*\n+"
    r"|I will[\s\S]*?[.:]\s*\n+"
    r"|(?:The )?corrected[\s\S]*?:\s*\n+"
    r"|Il testo corretto[\s\S]*?:\s*\n+"
    r")",
    re.IGNORECASE,
)


class Chat(Protocol):
    """One OCR-correction completion: returns the corrected chapter text. Injectable so the sync
    LLM path runs offline in tests (BR-014); the default is the real Anthropic client."""

    def correct(self, *, system: str, user: str) -> str: ...


class AnthropicChat:
    """Default ``Chat`` — Anthropic ``messages.create`` wrapped in ``retry_api_call``. The model is
    a code default (the live id); a missing key is a ``BackendError`` (exit 5)."""

    def __init__(
        self, *, model: str = _LLM_CORRECT_MODEL, api_key: str | None = None,
        max_tokens: int = _LLM_CORRECT_MAX_TOKENS,
    ) -> None:
        if not api_key:
            api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise BackendError("No Anthropic API key. Set ANTHROPIC_API_KEY or pass --api-key.")

        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key, timeout=600.0)
        self._model = model
        self._max_tokens = max_tokens

    def correct(self, *, system: str, user: str) -> str:
        def _call():
            return self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )

        response = retry_api_call(_call)
        return response.content[0].text


def render_correct_prompt(cfg: ResolvedConfig) -> str:
    """Render the book-neutral cleanup-correction system prompt with the book/language context."""
    template = PromptTemplate.load("cleanup_correct")
    return template.render(**build_prompt_context(cfg))


def build_user_content(text: str, chapter_title: str, dict_context: str = "") -> str:
    """Build the user message for LLM OCR correction. Verbatim from live ``_build_user_content``,
    with the dictionary-reference section appended when flag context is supplied."""
    content = (
        f"Correct OCR errors in the following chapter ({chapter_title}). "
        f"Return only the corrected text:\n\n{text}"
    )
    if dict_context:
        content += (
            "\n\n--- REFERENCE ---\n"
            "The following tokens were flagged as potentially broken or garbled. "
            "Use the period-dictionary evidence below to inform your corrections. "
            "Tokens marked 'not found' may be proper nouns (keep as-is) or noise (remove).\n\n"
            + dict_context
        )
    return content


def strip_preamble(text: str) -> str:
    """Strip LLM meta-commentary that sometimes precedes the corrected text. Verbatim."""
    return _PREAMBLE_RE.sub("", text, count=1)


# Note: the live ``apply_corrections`` / ``extract_corrections_from_diff`` (the corrections.json
# manual-override mechanism) are deliberately NOT ported — ``run`` omits the deprecated/stale
# corrections.json path entirely (the full-text LLM cache supersedes it). They would be re-ported
# alongside a real per-book overrides input, not kept as unwired dead code (M4b audit, YAGNI).


# --- Batch API (default-only; pure request-building is property-tested) ------------------- #

def build_batch_requests(
    chapters: list[dict], pre_texts: dict[str, str], pre_flags: dict[str, list[dict]],
    skip_ids: set[str], system: str, oracle: DictionaryOracle,
) -> list[dict]:
    """Build the Anthropic Message-Batch request list (skipping already-cached chapters). Pure —
    the property tier covers it. Port of live ``_build_batch_requests`` with the system prompt +
    oracle injected (instead of module constants)."""
    requests = []
    for ch in chapters:
        ch_id = ch["id"]
        if ch_id in skip_ids:
            continue
        text = pre_texts.get(ch_id, "")
        if not text:
            continue
        flags = pre_flags.get(ch_id, [])
        dict_ctx = dictionary_context_for_flags(flags, oracle) if flags else ""
        requests.append({
            "custom_id": ch_id,
            "params": {
                "model": _LLM_CORRECT_MODEL,
                "max_tokens": _LLM_CORRECT_MAX_TOKENS,
                "system": system,
                "messages": [{"role": "user", "content": build_user_content(text, ch["title"], dict_ctx)}],
            },
        })
    return requests


def _submit_batch(ws: BookWorkspace, requests: list[dict], api_key: str) -> str | None:
    """Submit (or resume) a Message Batch. Default-only (anthropic-direct); returns its id."""
    import anthropic

    batch_state_path = ws.resolve("state", "llm_batch.json")
    if batch_state_path.exists():
        state = read_json(batch_state_path)
        if state.get("status") == "submitted":
            print(f"  Found in-progress batch {state['batch_id']}, resuming polling...")
            return state["batch_id"]

    if not requests:
        print("  All chapters already cached — nothing to submit.")
        return None

    print(f"  Submitting batch: {len(requests)} chapters")
    client = anthropic.Anthropic(api_key=api_key, timeout=120.0)
    batch = client.messages.batches.create(requests=requests)
    atomic_write_json(batch_state_path, {
        "batch_id": batch.id,
        "chapter_ids": [r["custom_id"] for r in requests],
        "status": "submitted",
    })
    print(f"  Batch submitted: {batch.id}")
    return batch.id


def _poll_and_collect_batch(ws: BookWorkspace, api_key: str, batch_id: str, poll_interval: int = 30) -> dict:
    """Poll a batch to completion, write results to the LLM cache. Default-only (anthropic-direct)."""
    import anthropic

    batch_state_path = ws.resolve("state", "llm_batch.json")
    cache_dir = ws.state / "llm_cleaned"
    cache_dir.mkdir(parents=True, exist_ok=True)
    client = anthropic.Anthropic(api_key=api_key, timeout=120.0)

    print(f"  Polling batch {batch_id} (every {poll_interval}s)...")
    while True:
        status = client.messages.batches.retrieve(batch_id)
        if status.processing_status == "ended":
            break
        time.sleep(poll_interval)

    succeeded = 0
    failed_ids = []
    for result in client.messages.batches.results(batch_id):
        ch_id = result.custom_id
        if result.result.type == "succeeded":
            text = strip_preamble(result.result.message.content[0].text)
            atomic_write_text(ws.resolve("state", "llm_cleaned", f"{ch_id}.txt"), text)
            succeeded += 1
        else:
            failed_ids.append(ch_id)
            print(f"  Warning: {ch_id} {result.result.type}")

    atomic_write_json(batch_state_path, {
        "batch_id": batch_id, "status": "completed",
        "succeeded": succeeded, "failed": len(failed_ids), "failed_ids": failed_ids,
    })
    return {"succeeded": succeeded, "failed": len(failed_ids), "failed_ids": failed_ids}


# --- post-LLM flag bookkeeping (deterministic; M4b-D5) ----------------------------------- #

def reconcile_flags(ws: BookWorkspace) -> dict:
    """Diff ``review_flags.json`` (pre-LLM) against the corrected ``clean.md`` and write only the
    surviving flags to ``review_flags_remaining.json`` (atomic). ``review_flags.json`` is preserved
    intact. Deterministic, runs after the LLM pass (M4b-D5). Returns a summary dict.
    """
    flags_path = ws.data / REVIEW_FLAGS_FILE
    output_path = ws.output / CLEAN_FILE
    if not flags_path.is_file() or not output_path.is_file():
        print("  reconcile_flags: missing review_flags.json or clean.md, skipping")
        return {"original": 0, "remaining": 0, "resolved": 0}

    flags = read_json(flags_path)
    output_text = output_path.read_text(encoding="utf-8")

    remaining: dict[str, list[dict]] = {}
    total_original = 0
    total_remaining = 0
    for ch_id, ch_flags in flags.items():
        for f in ch_flags:
            total_original += 1
            context = f.get("context", "").strip()
            token = f.get("token", "")
            search = context if context else token
            if search and search in output_text:
                remaining.setdefault(ch_id, []).append(f)
                total_remaining += 1

    atomic_write_json(ws.resolve("data", REVIEW_FLAGS_REMAINING_FILE), remaining)
    resolved = total_original - total_remaining
    print(f"  Flag reconciliation: {total_original} original → {total_remaining} remaining ({resolved} resolved)")
    return {"original": total_original, "remaining": total_remaining, "resolved": resolved}


# --- regen-guard (BR-012 / M4b-D2) ------------------------------------------------------- #

def _check_regen_guard(out_path, allow_regen: bool) -> None:
    """Refuse to clobber an existing ``clean.md`` without an explicit override. The engine sandbox
    protects the live tree, but not a hand-tuned artifact *inside* ``work/`` — a re-run would
    overwrite it. Override via ``allow_regen=True`` or ``ENGINE_ALLOW_REGEN=1`` (M4b-D2)."""
    if allow_regen or os.environ.get(ENGINE_ALLOW_REGEN_ENV) == "1":
        return
    if out_path.exists():
        raise RegenerationGuardError(
            f"{out_path} already exists; cleanup would overwrite it (it may carry hand-applied "
            f"fixes). Pass allow_regen=True or set {ENGINE_ALLOW_REGEN_ENV}=1 to proceed."
        )


# --- orchestration ----------------------------------------------------------------------- #

def run(
    *,
    workspace: BookWorkspace,
    cfg: ResolvedConfig,
    lang: LanguagePlugin,
    use_llm: bool = False,
    chapter: str | None = None,
    batch: bool = False,
    chat: Chat | None = None,
    oracle: DictionaryOracle | None = None,
    api_key: str | None = None,
    allow_regen: bool = False,
) -> dict:
    """Clean the reconciled chapters into ``clean.md`` (+ the review-flags sidecar).

    Deterministic by default; ``use_llm=True`` adds the LLM correction pass (sync per-chapter, or
    ``batch=True`` for the whole-book Batch API), through the injectable ``chat`` seam. ``chapter``
    scopes a fresh LLM pass to one chapter (others use cache). Refuses to clobber an existing
    ``clean.md`` without ``allow_regen`` / ``ENGINE_ALLOW_REGEN=1`` (regen-guard). Returns a summary.
    """
    ws = workspace
    ws.ensure()

    out_path = ws.output / CLEAN_FILE
    _check_regen_guard(out_path, allow_regen)

    reconciled_path = ws.data / RECONCILED_FILE
    if not reconciled_path.is_file():
        raise MissingInputError(
            f"{RECONCILED_FILE} not found at {reconciled_path} — run reconcile first"
        )
    chapters = _sort_chapters(read_json(reconciled_path))

    chapter_pages = {}
    pages_path = ws.data / CHAPTER_PAGES_FILE
    if pages_path.is_file():
        chapter_pages = read_json(pages_path)

    lp = cfg.language
    word_set = load_word_set(require_asset(lp.frequency_dictionary, kind="file"))
    sym = load_symspell(require_asset(lp.frequency_dictionary, kind="file"))
    nlp = lang.load_spacy(lp.spacy_model, disable=["parser", "lemmatizer"])
    rules = build_rules(cfg)

    if use_llm:
        if chat is None:
            chat = AnthropicChat(api_key=api_key)
        if oracle is None:
            oracle = _build_oracle(cfg)

    cache_dir = ws.state / "llm_cleaned"
    cache_dir.mkdir(parents=True, exist_ok=True)

    # --- Batch API path: pre-clean every chapter, submit + poll, then fall through to cache ---
    if use_llm and batch:
        system = render_correct_prompt(cfg)
        pre_texts: dict[str, str] = {}
        pre_flags: dict[str, list[dict]] = {}
        for ch in chapters:
            text, flags, _ = clean_text(ch["text"], word_set, rules, sym=sym, nlp=nlp)
            pre_texts[ch["id"]] = text
            if flags:
                pre_flags[ch["id"]] = flags
        skip_ids = {p.stem for p in cache_dir.glob("*.txt")}
        requests = build_batch_requests(chapters, pre_texts, pre_flags, skip_ids, system, oracle)
        batch_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not batch_key:
            raise BackendError("--batch requires an Anthropic API key (ANTHROPIC_API_KEY).")
        batch_id = _submit_batch(ws, requests, batch_key)
        if batch_id:
            stats = _poll_and_collect_batch(ws, batch_key, batch_id)
            print(f"  Batch complete: {stats['succeeded']} succeeded, {stats['failed']} failed")

    rendered: list[tuple[dict, str]] = []
    all_flags: dict[str, list[dict]] = {}
    total_punct = 0
    system_prompt = render_correct_prompt(cfg) if (use_llm and not batch) else ""

    for ch in chapters:
        text, flags, punct = clean_text(ch["text"], word_set, rules, sym=sym, nlp=nlp)
        total_punct += punct
        ch_id = ch["id"]
        cache_path = cache_dir / f"{ch_id}.txt"

        will_run_llm = use_llm and not batch and (
            ch_id == chapter if chapter is not None else not cache_path.exists()
        )

        if will_run_llm:
            try:
                dict_ctx = dictionary_context_for_flags(flags, oracle) if flags else ""
                text = strip_preamble(chat.correct(
                    system=system_prompt, user=build_user_content(text, ch["title"], dict_ctx)
                ))
                atomic_write_text(cache_path, text)
            except Exception as exc:  # noqa: BLE001 — a chapter LLM failure degrades to clean_text
                print(f"  LLM error on {ch_id}, using deterministic text: {exc}")
        elif cache_path.exists():
            # Cache wins over clean_text output (the live cache-precedence rule).
            text = cache_path.read_text(encoding="utf-8")

        if flags:
            all_flags[ch_id] = flags
        rendered.append((ch, text))

    atomic_write_text(out_path, render_markdown(rendered, cfg, chapter_pages))

    flags_path = ws.resolve("data", REVIEW_FLAGS_FILE)
    if all_flags:
        atomic_write_json(flags_path, all_flags)
    elif flags_path.exists():
        flags_path.unlink()

    review_flagged = sum(len(v) for v in all_flags.values())
    print(f"  Cleaned {len(chapters)} chapters → {out_path} "
          f"({review_flagged} review flags, {total_punct} punctuation fixes)")

    return {
        "chapters": len(chapters),
        "review_flags": review_flagged,
        "punct_fixes": total_punct,
        "used_llm": use_llm,
    }
