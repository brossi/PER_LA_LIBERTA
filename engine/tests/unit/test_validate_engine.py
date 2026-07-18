"""validate is config-driven, not PLL-hardcoded.

Two layers:
  1. Per-check unit tests (fast, no spaCy): each deterministic check responds to the *config*
     it is given — a different structure/threshold/pattern changes its verdict. This is the
     binding proof: the checks read ``cfg``/``lang`` fields, not baked-in PLL constants.
  2. A synthetic-book end-to-end (``integration``, real spaCy): the whole step runs on a book
     that is *not* PLL (3 content units, not 58) and returns ``pass`` — proving nothing in the
     orchestration assumes PLL's structure.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.config.loader import load_book
from engine.config.models import CoverageSpec, PartStructure, Structure
from engine.lang.registry import get_language_plugin
from engine.paths import BookWorkspace
from engine.steps import validate

ENGINE_ROOT = Path(__file__).resolve().parents[2]
SYNTHETIC_INPUTS = ENGINE_ROOT / "books" / "synthetic" / "inputs"


def _structure(**kw) -> Structure:
    base = dict(
        h2_min=2,
        h3_count=2,
        parts=(PartStructure("Parte Prima", 2),),
        content_units=3,
        retention_min=0.60,
        foreign_char_max=0.005,
        word_quality_high_severity_max=0,
        running_heads=(),  # reconcile-facing; validate ignores it
    )
    base.update(kw)
    return Structure(**base)


# --- per-check config binding ---------------------------------------------------------- #

def test_chapter_count_reads_declared_structure():
    text = "## Prefazione\n## Parte Prima\n### Capitolo Primo\n### Capitolo Secondo\n"
    ok = validate.check_chapter_count(text, _structure())
    assert ok["passed"]
    assert ok["h2_count"] == 2 and ok["h3_count"] == 2

    # A book expecting a different count fails — and the message quotes *its* expectation,
    # not PLL's 57 (proves the threshold is read from cfg, not hardcoded).
    wrong = validate.check_chapter_count(text, _structure(h3_count=57))
    assert not wrong["passed"]
    assert "57" in wrong["issues"][0] and "Parte Prima" in wrong["issues"][0]


def test_char_coverage_reads_coverage_set_and_threshold():
    text = "Frühaufsteher"  # contains 'ü'
    with_u = validate._coverage_set(
        CoverageSpec(ascii_letters=True, digits=False, letters="ü", punctuation="")
    )
    ok = validate.check_char_coverage(text, with_u, foreign_char_max=0.005)
    assert ok["passed"] and ok["foreign_char_ratio"] == 0.0
    # Drop 'ü' from the allowlist → it's foreign over a zero tolerance. The whole in-script set
    # is config (CoverageSpec); nothing about which chars count is hardcoded in the check.
    without_u = validate._coverage_set(
        CoverageSpec(ascii_letters=True, digits=False, letters="", punctuation="")
    )
    bad = validate.check_char_coverage(text, without_u, foreign_char_max=0.0)
    assert not bad["passed"] and bad["foreign_char_ratio"] > 0


def test_coverage_set_honours_toggles():
    # The ascii_letters / digits toggles are real: a non-Latin script can exclude a–z / 0–9.
    spec = CoverageSpec(ascii_letters=False, digits=False, letters="абв", punctuation=".")
    allowed = validate._coverage_set(spec)
    assert "а" in allowed and "." in allowed
    assert "a" not in allowed and "5" not in allowed


def test_no_ascii_remnants_reads_page_marker_pattern():
    text = "testo 165 3E: altro testo"
    flagged = validate.check_no_ascii_remnants(text, page_marker_pattern=r"\d+\s+[35][EI]:?")
    assert not flagged["passed"]
    # A book whose scans don't carry that artifact uses a pattern that matches nothing here.
    clean = validate.check_no_ascii_remnants(text, page_marker_pattern=r"ZZ_NEVER_MATCHES")
    assert clean["passed"]


def test_no_ascii_remnants_flags_uppercase_digit_noise_runs():
    # The check's SECOND arm, independent of the page-marker arm and never reached by the page-marker
    # tests above: an uppercase+digit run (≥5, contains a digit) is OCR noise, while a pure all-caps
    # word with no digit is legitimate. With a page-marker pattern that matches nothing, only this
    # arm can fire — so deleting it would otherwise ship green.
    noisy = validate.check_no_ascii_remnants("testo ABC12DEF altro", page_marker_pattern=r"ZZ_NEVER")
    assert not noisy["passed"]
    allcaps = validate.check_no_ascii_remnants("testo ANGELES POPOLO", page_marker_pattern=r"ZZ_NEVER")
    assert allcaps["passed"]


def test_word_count_preservation_reads_retention_floor(tmp_path):
    recon = tmp_path / "reconciled.json"
    recon.write_text(json.dumps([{"text": "uno due tre quattro cinque sei sette otto"}]),
                     encoding="utf-8")
    cleaned = "uno due"  # 2 of 8 words → 25% retention
    strict = validate.check_word_count_preservation(cleaned, recon, retention_min=0.60)
    assert not strict["passed"] and strict["retention_pct"] == 25.0
    lax = validate.check_word_count_preservation(cleaned, recon, retention_min=0.10)
    assert lax["passed"]


def test_word_count_preservation_fails_closed_on_zero_reconciled_words(tmp_path):
    # The zero-word guard (validate.py:368-370) must fail CLOSED: a reconciled witness with no words
    # means a broken pipeline, and this is the quality gate. Asserting `passed is False` (not just
    # "doesn't ZeroDivisionError") catches a regression that flips the guard to passed=True — the
    # gate failing OPEN, letting an empty book validate green.
    recon = tmp_path / "reconciled.json"
    recon.write_text(json.dumps([{"text": ""}]), encoding="utf-8")
    result = validate.check_word_count_preservation("anything", recon, retention_min=0.60)
    assert result["passed"] is False


def test_no_empty_chapters_flags_short_and_passes_full():
    short = "### Capitolo Primo\n\nbreve.\n"
    assert not validate.check_no_empty_chapters(short, ["Parte Prima"])["passed"]
    full = "### Capitolo Primo\n\n" + ("parola " * 20) + "\n"
    assert validate.check_no_empty_chapters(full, ["Parte Prima"])["passed"]


def test_quote_balance_detects_imbalance():
    assert validate.check_quote_balance("«chiuso»")["passed"]
    assert not validate.check_quote_balance("«aperto senza chiusura")["passed"]
    # the smart-double-quote arm, independent of the guillemet arm — the PLL corpus has no curly
    # quotes, so the golden can never reach it and only this unit test protects it:
    assert validate.check_quote_balance("“chiuso”")["passed"]
    assert not validate.check_quote_balance("“aperto senza chiusura")["passed"]


class _NoEntities:
    """A spaCy-doc stand-in with no named entities — isolates word_quality's classifier from
    the model so the high-severity *logic*, not NER, is what this test exercises."""
    ents = ()


def _no_ner(_text):
    return _NoEntities()


def test_word_quality_high_severity_fails_and_reads_its_ceiling():
    # The golden only sees PLL's all-clean text (0 high-severity), so the failure branch and
    # the severity classifier (validate.py:293) are otherwise untested. Feed three *reachable*
    # high-severity patterns: a mid-word capital, a lowercase 4+ consonant cluster, and an
    # English-marker word. ("mid-word noise" is unreachable — WORD_RE captures only letters —
    # so it is deliberately not asserted here; see the gap notes.)
    text = "### Capitolo\n\nparola paRola bcdfgh the regolare\n"
    kw = dict(
        word_set=frozenset({"parola", "regolare"}),
        nlp=_no_ner,
        english_markers={"the"},
        skip_words=set(),
        consonant_alphabet="bcdfghjklmnpqrstvwxyz",
        word_letter_class="a-zA-ZÀ-ÿ",
    )

    strict = validate.check_word_quality(text, high_severity_max=0, **kw)
    assert strict["passed"] is False
    assert strict["high_severity"] == 3  # paRola, bcdfgh, the
    assert any("high-severity" in i for i in strict["issues"])

    # Same flags, a higher ceiling → passes: the gate is read from config, not hardcoded to 0.
    lax = validate.check_word_quality(text, high_severity_max=5, **kw)
    assert lax["passed"] is True
    assert lax["high_severity"] == 3


def test_mid_word_noise_is_unreachable_faithful_to_live():
    # Pins the documented dead branch (validate.py _MID_NOISE note): the word regex captures
    # letters only, so a token with embedded noise splits at the noise and "mid-word noise"
    # never fires — matching the live validate.py. If a future word-regex change makes it
    # reachable, this flips and forces a deliberate decision (and a golden refresh).
    text = "### Capitolo\n\nun com2rare guasto qui\n"
    result = validate.check_word_quality(
        text,
        word_set=frozenset({"un", "guasto", "qui", "com", "rare"}),
        nlp=_no_ner,
        english_markers=set(),
        skip_words=set(),
        consonant_alphabet="bcdfghjklmnpqrstvwxyz",
        word_letter_class="a-zA-ZÀ-ÿ",
        high_severity_max=0,
    )
    all_reasons = [r for flags in result["by_chapter"].values() for f in flags for r in f["reasons"]]
    assert "mid-word noise" not in all_reasons


def test_word_quality_capitalised_cluster_is_not_high_severity():
    # The classifier's one conditional rule: a consonant cluster counts as high-severity only
    # in a *lowercase* word (a capitalised one is likely a proper noun). "Brrtsk" clusters but
    # is capitalised → flagged, but not high-severity → the check still passes at max=0.
    text = "### Capitolo\n\nIl signor Brrtsk arrivò.\n"
    result = validate.check_word_quality(
        text,
        word_set=frozenset({"il", "signor", "arrivò"}),
        nlp=_no_ner,
        english_markers=set(),
        skip_words=set(),
        consonant_alphabet="bcdfghjklmnpqrstvwxyz",
        word_letter_class="a-zA-ZÀ-ÿ",
        high_severity_max=0,
    )
    assert result["high_severity"] == 0
    assert result["passed"] is True
    assert result["total_flagged"] >= 1  # Brrtsk is still flagged (low-severity)


# --- synthetic-book end-to-end --------------------------------------------------------- #

def test_run_without_clean_text_returns_error(tmp_path):
    # A fresh workspace (cleanup hasn't produced output/clean.md yet) must degrade
    # to an error report, not crash — and write nothing. Returns before any spaCy load.
    cfg = load_book("synthetic")
    lang = get_language_plugin(cfg.language_id)
    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()

    report = validate.run(workspace=ws, cfg=cfg, lang=lang)

    assert report["overall"] == "error"
    assert not (ws.data / validate.REPORT_FILE).exists()


@pytest.mark.integration
def test_validate_runs_on_synthetic_book(tmp_path):
    cfg = load_book("synthetic")
    lang = get_language_plugin(cfg.language_id)

    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()
    (ws.output / validate.CLEAN_FILE).write_text(
        (SYNTHETIC_INPUTS / "clean.md").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (ws.data / validate.RECONCILED_FILE).write_text(
        (SYNTHETIC_INPUTS / "reconciled_chapters.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    report = validate.run(workspace=ws, cfg=cfg, lang=lang)

    assert report["overall"] == "pass"
    checks = {c["name"]: c for c in report["checks"]}
    # The structural checks reflect the synthetic book's structure (2 chapters), not PLL's 57.
    assert checks["chapter_count"]["h3_count"] == 2
    assert checks["chapter_count"]["passed"]
    assert set(checks) == {
        "chapter_count", "no_empty_chapters", "quote_balance", "char_coverage",
        "no_ascii_remnants", "word_quality", "word_count_preservation",
    }
