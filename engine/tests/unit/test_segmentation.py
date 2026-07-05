"""S2.1.4 (#38) — ``segmentation.py`` density band pre-check classifier (``s2_1_plan.md`` DT-6).

Home of the density-classifier invariants: the four-class ``{content, near_blank, non_text_dark,
abstain}`` band map, ``abstain`` as a first-class route-to-worklist result (G-9), the two-sided
untrusted split with ``non_text_dark`` boxes untrusted (G-11), and — the Finding-B trap guard —
confidence as the **margin to the nearest band edge**, never the raw ink fraction that is maximal on
exactly the hallucination-prone dark pages.

Fake-backend tier (DT-11): the classifier and feature-assembly semantics run on synthetic feature
vectors and fake boxes — no PDF, no OCR. Ink-fraction extraction is exercised on small in-memory
``fitz.Pixmap`` objects (the only pixmap-touching leg), which need no PDF either.

Red-first (``feedback_red_first_tests``): every invariant below was seen red on its named violation
(planted-violation control for the guards/semantics, TDD-absent-behavior for the records) before its
green — the mutation pass over ``segmentation.py`` mechanizes the same reds.
"""

from __future__ import annotations

import math

import fitz  # PyMuPDF — a declared engine dependency; builds the in-memory pixmaps for ink tests.
import pytest

from engine.structure import (
    SEGMENTATION_VERSION,
    DensityBand,
    DensityClassifier,
    DensityVerdict,
    PageDensityFeatures,
    WordBox,
    edge_strip,
    ink_fraction_from_pixmap,
    is_alpha_token,
    page_density_features,
)
from engine.structure.segmentation import _INK_LUMA_THRESHOLD


def _box(text: str) -> WordBox:
    """A real WordBox (the production box record) with a throwaway bbox — the seam reads only .text."""
    return WordBox(text=text, bbox=(0.0, 0.0, 1.0, 1.0))


# Reference bands used across the semantics tests. Non-default *test* values (the classifier itself
# has no defaults — G-1): a page is content at yield >= 0.5 with >= 10 boxes; untrusted below that,
# split near_blank <= 0.10 ink / non_text_dark >= 0.60 ink; edges within 0.05 abstain.
def _clf(**overrides) -> DensityClassifier:
    params = dict(
        yield_content_min=0.5,
        box_content_min=10,
        ink_blank_max=0.10,
        ink_dark_min=0.60,
        confidence_margin=0.05,
    )
    params.update(overrides)
    return DensityClassifier(**params)


# ------------------------------------------------------------------------------------------------ #
# PageDensityFeatures / DensityVerdict record validity (G-21-analogue: an invalid feature vector is
# an extractor bug, made unconstructible rather than silently classified).
# ------------------------------------------------------------------------------------------------ #


@pytest.mark.parametrize("bad", [1.5, -0.1, math.nan, math.inf])
def test_features_reject_out_of_range_ink_fraction(bad):
    # RED: drop the [0,1] finite gate on ink_fraction → these construct.
    with pytest.raises(ValueError, match="ink_fraction"):
        PageDensityFeatures(ink_fraction=bad, box_count=1, token_yield=0.5, mean_token_length=3.0)


@pytest.mark.parametrize("bad", [1.5, -0.1, math.nan])
def test_features_reject_out_of_range_token_yield(bad):
    with pytest.raises(ValueError, match="token_yield"):
        PageDensityFeatures(ink_fraction=0.3, box_count=1, token_yield=bad, mean_token_length=3.0)


@pytest.mark.parametrize("bad", [-1, True, 2.5, math.nan])
def test_features_reject_non_count_box_count(bad):
    # RED: relax to `box_count >= 0` (numeric) → True (bool subclass), 2.5, nan all slip through.
    with pytest.raises(ValueError, match="box_count"):
        PageDensityFeatures(ink_fraction=0.3, box_count=bad, token_yield=0.5, mean_token_length=3.0)


@pytest.mark.parametrize("bad", [-1.0, math.nan, math.inf])
def test_features_reject_bad_mean_token_length(bad):
    with pytest.raises(ValueError, match="mean_token_length"):
        PageDensityFeatures(ink_fraction=0.3, box_count=1, token_yield=0.5, mean_token_length=bad)


def test_features_accept_a_genuinely_blank_page():
    # A blank page (zero boxes, zero yield/mean) is valid, not an error — DT-2 empty != failed.
    f = PageDensityFeatures(ink_fraction=0.0, box_count=0, token_yield=0.0, mean_token_length=0.0)
    assert f.box_count == 0


@pytest.mark.parametrize("bad", [-0.1, math.nan, math.inf])
def test_verdict_rejects_negative_or_nonfinite_confidence(bad):
    with pytest.raises(ValueError, match="confidence"):
        DensityVerdict(band=DensityBand.CONTENT, confidence=bad, signal="content")


def test_verdict_rejects_empty_signal():
    with pytest.raises(ValueError, match="signal"):
        DensityVerdict(band=DensityBand.ABSTAIN, confidence=0.0, signal="")


# ------------------------------------------------------------------------------------------------ #
# DensityClassifier constructor — bands are REQUIRED, no defaults (G-1 numberless-core posture), and
# incoherent bands are refused (fail-loud config integrity).
# ------------------------------------------------------------------------------------------------ #


@pytest.mark.parametrize(
    "omit",
    ["yield_content_min", "box_content_min", "ink_blank_max", "ink_dark_min", "confidence_margin"],
)
def test_classifier_requires_every_band_no_default(omit):
    # RED (G-1): give the omitted param a default → constructing without it stops raising. A default
    # band value is a scan-profile opinion baked into neutral core (DT-6). Each param independently.
    kwargs = dict(
        yield_content_min=0.5,
        box_content_min=10,
        ink_blank_max=0.10,
        ink_dark_min=0.60,
        confidence_margin=0.05,
    )
    del kwargs[omit]
    with pytest.raises(TypeError):
        DensityClassifier(**kwargs)


@pytest.mark.parametrize(
    "overrides,needle",
    [
        (dict(yield_content_min=0.0), "yield_content_min"),
        (dict(yield_content_min=1.5), "yield_content_min"),
        (dict(box_content_min=-1), "box_content_min"),
        (dict(box_content_min=2.5), "box_content_min"),
        (dict(ink_blank_max=-0.1), "ink_blank_max"),
        (dict(ink_blank_max=1.0), "ink_blank_max"),
        (dict(ink_dark_min=0.0), "ink_dark_min"),
        (dict(ink_dark_min=1.5), "ink_dark_min"),
        (dict(confidence_margin=0.0), "confidence_margin"),
        (dict(confidence_margin=1.5), "confidence_margin"),
        # The two ink edges must leave a real mid-band (else the classes overlap / no ink-ambiguous
        # zone): blank_max must be strictly below dark_min.
        (dict(ink_blank_max=0.6, ink_dark_min=0.6), "ink_blank_max"),
        (dict(ink_blank_max=0.7, ink_dark_min=0.6), "ink_blank_max"),
    ],
)
def test_classifier_rejects_incoherent_bands(overrides, needle):
    with pytest.raises(ValueError, match=needle):
        _clf(**overrides)


def test_version_and_params_are_pinned_for_the_sidecar_fingerprint():
    # SEGMENTATION_VERSION and params feed the sidecar classifier_version/classifier_params and the
    # DT-10 input fingerprint — pin both so a silent drift is caught.
    assert SEGMENTATION_VERSION == "density-bands-v1"
    clf = _clf()
    assert clf.version == "density-bands-v1"
    assert clf.params == {
        "yield_content_min": 0.5,
        "box_content_min": 10,
        "ink_blank_max": 0.10,
        "ink_dark_min": 0.60,
        "confidence_margin": 0.05,
    }


# ------------------------------------------------------------------------------------------------ #
# Feature assembly — token_yield = alpha-token count / box count; mean_token_length over all boxes.
# ------------------------------------------------------------------------------------------------ #


@pytest.mark.parametrize(
    "text,expected",
    [
        ("libertà", True),   # real word
        ("Popolo", True),    # real word, caps
        ("e", False),        # 1-char function word — below the 2-char floor
        ("35", False),       # digit-only folio — no letter
        ("«", False),        # punctuation only — strips to empty
        (".,", False),       # punctuation only
        ("«Voi»", True),     # edge punctuation stripped, "Voi" survives
        ("a1", True),        # 2 chars incl. a letter
    ],
)
def test_is_alpha_token(text, expected):
    assert is_alpha_token(text) is expected


def test_edge_strip_is_unicode_neutral():
    assert edge_strip("«libertà!»") == "libertà"
    assert edge_strip("...parola,,,") == "parola"
    assert edge_strip("35") == "35"  # digits are word chars, kept


def test_token_yield_is_alpha_count_over_box_count():
    # 4 alpha tokens (parola, libertà, Popolo, «Voi»→Voi) of 8 boxes → 0.5. Independent hand count,
    # not computed by the code under test (tautology guard).
    boxes = [_box(t) for t in ["parola", "libertà", "Popolo", "«Voi»", "e", "35", "«", ".,"]]
    f = page_density_features(ink_fraction=0.3, boxes=boxes)
    assert f.box_count == 8
    assert f.token_yield == pytest.approx(4 / 8)


def test_mean_token_length_is_over_all_boxes_stripped():
    # Stripped lengths: parola=6, e=1, «=0, 35=2 → sum 9 over 4 boxes = 2.25. A leaf of tiny
    # fragments reads short — the hallucination tell.
    boxes = [_box(t) for t in ["parola", "e", "«", "35"]]
    f = page_density_features(ink_fraction=0.3, boxes=boxes)
    assert f.mean_token_length == pytest.approx(9 / 4)


def test_ghost_leaf_signature_low_yield():
    # p6's signature: many boxes, almost no real tokens. 20 single-char noise boxes + 1 word → yield
    # 1/21 ≈ 0.048, the "boxes untrusted" tell.
    boxes = [_box(".") for _ in range(20)] + [_box("parola")]
    f = page_density_features(ink_fraction=0.5, boxes=boxes)
    assert f.token_yield == pytest.approx(1 / 21)


def test_zero_boxes_gives_zero_yield_and_mean_no_divide_error():
    f = page_density_features(ink_fraction=0.0, boxes=[])
    assert f.box_count == 0
    assert f.token_yield == 0.0
    assert f.mean_token_length == 0.0


# ------------------------------------------------------------------------------------------------ #
# Ink-fraction extraction — dark(< threshold) pixels / total, across colorspaces.
# ------------------------------------------------------------------------------------------------ #


def test_ink_fraction_counts_dark_pixels_grayscale():
    # 4 gray pixels: two black (0 < 128 = ink), two white (255) → 0.5. RED: count light pixels → 0.5
    # would flip on an asymmetric fixture, so use an asymmetric one below too.
    pm = fitz.Pixmap(fitz.csGRAY, 2, 2, bytes([0, 0, 255, 255]), False)
    assert ink_fraction_from_pixmap(pm) == pytest.approx(0.5)


def test_ink_fraction_asymmetric_pins_direction():
    # 3 dark + 1 light → 0.75, not 0.25 — a light-counting mutant reds here.
    pm = fitz.Pixmap(fitz.csGRAY, 2, 2, bytes([0, 10, 100, 255]), False)
    assert ink_fraction_from_pixmap(pm) == pytest.approx(0.75)


def test_ink_fraction_threshold_boundary():
    # Exactly the threshold value is NOT ink (strict <): one pixel at the cutoff, one below.
    pm = fitz.Pixmap(fitz.csGRAY, 2, 1, bytes([_INK_LUMA_THRESHOLD, _INK_LUMA_THRESHOLD - 1]), False)
    assert ink_fraction_from_pixmap(pm) == pytest.approx(0.5)


def test_ink_fraction_converts_rgb_to_gray():
    # RGB path: black (0,0,0) + dark-red (128,0,0) both convert to a dark luma → ink 1.0. A colored
    # pixel is what distinguishes real conversion from a per-byte count: skipping the conversion reads
    # the raw RGB bytes ([0,0,0,128,0,0] → 5 dark of 6 = 0.833), so this asymmetric-colour fixture reds
    # the conversion-skipped mutant, where the earlier black/white fixture coincided at 0.5.
    pm = fitz.Pixmap(fitz.csRGB, 2, 1, bytes([0, 0, 0, 128, 0, 0]), False)
    assert ink_fraction_from_pixmap(pm) == pytest.approx(1.0)


def test_ink_fraction_drops_alpha_channel():
    # Gray+alpha: luma bytes [0, 255], alpha [200, 200] must be dropped, not counted → 0.5.
    pm = fitz.Pixmap(fitz.csGRAY, 2, 1, bytes([0, 200, 255, 200]), True)
    assert ink_fraction_from_pixmap(pm) == pytest.approx(0.5)


def test_ink_fraction_empty_pixmap_is_zero():
    # The `not luma` guard: a zero-sample pixmap-like returns 0.0, no divide error.
    from types import SimpleNamespace

    empty = SimpleNamespace(colorspace=SimpleNamespace(n=1), alpha=0, samples=b"")
    assert ink_fraction_from_pixmap(empty) == 0.0


# ------------------------------------------------------------------------------------------------ #
# Classifier semantics — the four bands, abstain-routing (G-9), dark-untrusted (G-11), and the
# confidence-is-margin-not-ink trap.
# ------------------------------------------------------------------------------------------------ #


def test_content_page_is_trusted_and_confident():
    f = PageDensityFeatures(ink_fraction=0.20, box_count=400, token_yield=0.90, mean_token_length=5.0)
    v = _clf().classify(f)
    assert v.band is DensityBand.CONTENT
    assert v.boxes_trusted is True
    assert v.routed is False
    assert v.confidence == pytest.approx(0.90 - 0.50)  # margin above the yield floor


def test_dark_low_yield_is_non_text_dark_and_untrusted():
    # G-11: high ink + low yield → non_text_dark, boxes untrusted. RED (mutant): trust high-ink pages
    # → CONTENT. Fixture is comfortably dark (margin 0.3 >= 0.05).
    f = PageDensityFeatures(ink_fraction=0.90, box_count=400, token_yield=0.02, mean_token_length=1.1)
    v = _clf().classify(f)
    assert v.band is DensityBand.NON_TEXT_DARK
    assert v.boxes_trusted is False
    assert v.routed is False


def test_near_blank_low_yield_is_untrusted():
    # The two-sided companion to G-11: low ink + low yield → near_blank, boxes untrusted.
    f = PageDensityFeatures(ink_fraction=0.02, box_count=400, token_yield=0.02, mean_token_length=1.1)
    v = _clf().classify(f)
    assert v.band is DensityBand.NEAR_BLANK
    assert v.boxes_trusted is False


def test_confidence_is_edge_margin_not_raw_ink():
    # THE Finding-B trap guard: a confident dark page reads ink 0.90, but its verdict confidence is
    # the margin to the nearest edge (0.90 - 0.60 = 0.30), NOT 0.90. RED (mutant): return ink_fraction
    # as confidence → 0.90 != 0.30 reds. Ink-confidence would be maximal on exactly the pages we
    # least trust — the whole reason confidence is a margin.
    f = PageDensityFeatures(ink_fraction=0.90, box_count=400, token_yield=0.02, mean_token_length=1.1)
    v = _clf().classify(f)
    assert v.confidence == pytest.approx(0.30)
    assert v.confidence != pytest.approx(0.90)


def test_abstain_at_content_boundary_routes_never_guesses():
    # G-9: a page exactly on the content yield boundary (yield == floor, boxes ok) is raw-content but
    # margin 0 < confidence_margin → ABSTAIN, routed. RED (mutant): map abstain→content (remove the
    # margin override) → returns CONTENT, the guess G-9 forbids.
    f = PageDensityFeatures(ink_fraction=0.20, box_count=400, token_yield=0.50, mean_token_length=5.0)
    v = _clf().classify(f)
    assert v.band is DensityBand.ABSTAIN
    assert v.routed is True
    assert v.boxes_trusted is False
    assert v.signal == "band-margin"


def test_abstain_in_ink_midband_is_first_class():
    # G-9 second cause: low yield with ink between the two edges — cannot tell blank from dark, so
    # abstain is the honest class, not a forced near_blank/non_text_dark. RED (mutant): map the
    # else-branch to a trusted/untrusted class → reds.
    f = PageDensityFeatures(ink_fraction=0.35, box_count=400, token_yield=0.02, mean_token_length=1.1)
    v = _clf().classify(f)
    assert v.band is DensityBand.ABSTAIN
    assert v.signal == "ink-ambiguous"
    assert v.confidence == 0.0


def test_near_blank_within_margin_of_the_ink_midband_abstains():
    # An untrusted class also respects the edge margin: ink just below blank_max (0.10 - 0.08 = 0.02
    # margin < 0.05) → abstain, not a confident near_blank. Guards the untrusted-side margin + the
    # boxes_ok min() path.
    f = PageDensityFeatures(ink_fraction=0.08, box_count=400, token_yield=0.02, mean_token_length=1.1)
    v = _clf().classify(f)
    assert v.band is DensityBand.ABSTAIN
    assert v.signal == "band-margin"
    assert v.confidence == pytest.approx(0.02)


def test_low_box_count_divider_is_not_content_even_with_clean_tokens():
    # The box_content_min hard gate: a two-box "«PARTE SECONDA»" divider has yield ~1.0 but too few
    # boxes to be content; low ink → confident near_blank (NOT content, NOT a spurious abstain from a
    # negative margin). RED (mutant): drop boxes_ok from the content condition → divider → CONTENT.
    f = PageDensityFeatures(ink_fraction=0.02, box_count=2, token_yield=1.0, mean_token_length=6.0)
    v = _clf().classify(f)
    assert v.band is DensityBand.NEAR_BLANK
    assert v.boxes_trusted is False
    assert v.confidence == pytest.approx(0.10 - 0.02)  # ink margin only; yield axis can't flip it


def test_near_blank_close_to_content_yield_abstains():
    # A very-low-ink page (ink 0.01, well inside near_blank) whose token_yield is just under the
    # content floor (0.48 vs 0.50, boxes ok) is ambiguous with content on the yield axis: the margin
    # is min(ink 0.09, yield 0.02) = 0.02 < 0.05 → abstain. Guards the boxes_ok min() path — a max()
    # there would take 0.09 and wrongly stamp it a confident near_blank.
    f = PageDensityFeatures(ink_fraction=0.01, box_count=400, token_yield=0.48, mean_token_length=5.0)
    v = _clf().classify(f)
    assert v.band is DensityBand.ABSTAIN
    assert v.signal == "band-margin"
    assert v.confidence == pytest.approx(0.02)


def test_classify_is_deterministic():
    f = PageDensityFeatures(ink_fraction=0.90, box_count=400, token_yield=0.02, mean_token_length=1.1)
    clf = _clf()
    assert clf.classify(f) == clf.classify(f)


def test_classify_page_extracts_then_classifies():
    # The convenience entry the calibration probe / #39 wiring use: pixmap + boxes → (features,
    # verdict). A dark pixmap of noise boxes → non_text_dark.
    pm = fitz.Pixmap(fitz.csGRAY, 2, 2, bytes([0, 0, 0, 255]), False)  # 0.75 ink
    boxes = [_box(".") for _ in range(20)] + [_box("x")]  # yield ~0, "x" is 1-char → not alpha
    features, verdict = _clf().classify_page(pixmap=pm, boxes=boxes)
    assert features.ink_fraction == pytest.approx(0.75)
    assert verdict.band is DensityBand.NON_TEXT_DARK
