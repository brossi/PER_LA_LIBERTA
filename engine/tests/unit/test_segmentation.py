"""S2.1.4 (#38) — ``segmentation.py`` density band pre-check classifier (``s2_1_plan.md`` DT-6).

Home of the density-classifier invariants: the five-class ``{content, near_blank, non_text_dark,
cover, abstain}`` band map (``cover`` = position × saturation, ruled 2026-07-06), ``abstain`` as a
first-class route-to-worklist result (G-9), the untrusted split with ``non_text_dark`` boxes
untrusted (G-11), the ink-gate on content (a saturated page is never content), and — the trap guard —
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
    COLUMN_DETECTOR_VERSION,
    SEGMENTATION_VERSION,
    ColumnDetector,
    ColumnEvidence,
    ColumnVerdict,
    DensityBand,
    DensityClassifier,
    DensityVerdict,
    PageColumnInput,
    PageColumnVerdict,
    PageDensityFeatures,
    WordBox,
    detect_columns,
    edge_strip,
    ink_fraction_from_pixmap,
    is_alpha_token,
    ordered_coverage,
    page_density_features,
    reading_order,
    resolve_reading_columns,
)
from engine.structure.segmentation import _INK_LUMA_THRESHOLD


def _box(text: str) -> WordBox:
    """A real WordBox (the production box record) with a throwaway bbox — the seam reads only .text."""
    return WordBox(text=text, bbox=(0.0, 0.0, 1.0, 1.0))


# Reference bands used across the semantics tests. Non-default *test* values (the classifier itself
# has no defaults — G-1): a page is content at yield >= 0.5 with >= 10 boxes and ink < 0.60; untrusted
# below that, split near_blank <= 0.10 ink / non_text_dark >= 0.60 ink; a near-saturated (ink >= 0.90)
# leaf within 3 of either end is a cover; edges within 0.05 abstain.
def _clf(**overrides) -> DensityClassifier:
    params = dict(
        yield_content_min=0.5,
        box_content_min=10,
        ink_blank_max=0.10,
        ink_dark_min=0.60,
        confidence_margin=0.05,
        cover_edge_leaves=3,
        ink_saturation_min=0.90,
    )
    params.update(overrides)
    return DensityClassifier(**params)


# Most semantics tests are position-agnostic — they exercise the density bands, not the cover rule.
# ``_c`` classifies at a fixed INTERIOR leaf (10 of 20) so the cover branch never fires unless a test
# deliberately passes an extreme position.
def _c(clf: DensityClassifier, f: PageDensityFeatures, *, leaf: int = 10, n: int = 20) -> DensityVerdict:
    return clf.classify(f, leaf_index=leaf, n_leaves=n)


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
    ["yield_content_min", "box_content_min", "ink_blank_max", "ink_dark_min", "confidence_margin",
     "cover_edge_leaves", "ink_saturation_min"],
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
        cover_edge_leaves=3,
        ink_saturation_min=0.90,
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
        # Match the dark guard's OWN wording, not the bare param name: an out-of-range ink_dark_min
        # also trips the ordering/saturation guards, whose messages mention "ink_dark_min" too — a
        # loose match would pass against those and hide a dropped dark guard.
        (dict(ink_dark_min=0.0), "ink_dark_min must be in"),
        (dict(ink_dark_min=1.5), "ink_dark_min must be in"),
        (dict(confidence_margin=0.0), "confidence_margin"),
        (dict(confidence_margin=1.5), "confidence_margin"),
        # The two ink edges must leave a real mid-band (else the classes overlap / no ink-ambiguous
        # zone): blank_max must be strictly below dark_min.
        (dict(ink_blank_max=0.6, ink_dark_min=0.6), "ink_blank_max"),
        (dict(ink_blank_max=0.7, ink_dark_min=0.6), "ink_blank_max"),
        (dict(cover_edge_leaves=-1), "cover_edge_leaves"),
        (dict(cover_edge_leaves=2.5), "cover_edge_leaves"),
        # ink_saturation_min must sit strictly above ink_dark_min (a cover is darker than mere dark).
        (dict(ink_saturation_min=0.60, ink_dark_min=0.60), "ink_saturation_min"),
        (dict(ink_saturation_min=0.40, ink_dark_min=0.60), "ink_saturation_min"),
        (dict(ink_saturation_min=1.5), "ink_saturation_min"),
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
        "cover_edge_leaves": 3,
        "ink_saturation_min": 0.90,
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
# Classifier semantics — the five bands, abstain-routing (G-9), dark-untrusted (G-11), the
# confidence-is-margin-not-ink trap, the ink-gate on content, and positional covers.
# ------------------------------------------------------------------------------------------------ #


def test_content_page_is_trusted_and_confident():
    f = PageDensityFeatures(ink_fraction=0.20, box_count=400, token_yield=0.90, mean_token_length=5.0)
    v = _c(_clf(), f)
    assert v.band is DensityBand.CONTENT
    assert v.boxes_trusted is True
    assert v.routed is False
    # margin = min(yield above floor 0.40, ink below dark edge 0.40) — both 0.40 here.
    assert v.confidence == pytest.approx(0.40)


def test_dark_low_yield_is_non_text_dark_and_untrusted():
    # G-11: high ink + low yield → non_text_dark, boxes untrusted. RED (mutant): trust high-ink pages
    # → CONTENT. Fixture is comfortably dark (margin 0.3 >= 0.05); interior leaf so it is not a cover.
    f = PageDensityFeatures(ink_fraction=0.90, box_count=400, token_yield=0.02, mean_token_length=1.1)
    v = _c(_clf(), f)
    assert v.band is DensityBand.NON_TEXT_DARK
    assert v.boxes_trusted is False
    assert v.routed is False


def test_saturated_high_yield_interior_page_is_not_content_ink_gate():
    # The p278 Finding-B trap on real data: a solid-dark leaf (ink 0.98) Tesseract hallucinated
    # 1189 tokens on at 0.75 yield. Because the dark check precedes content (the ink gate, ruled
    # 2026-07-06), an INTERIOR saturated page is NON_TEXT_DARK, never content. RED (mutant): check
    # content before the ink gate → yield_ok & boxes_ok → CONTENT, the exact trap.
    f = PageDensityFeatures(ink_fraction=0.98, box_count=1189, token_yield=0.75, mean_token_length=2.9)
    v = _c(_clf(), f)  # interior leaf 10/20 → not a cover
    assert v.band is DensityBand.NON_TEXT_DARK
    assert v.boxes_trusted is False


def test_near_blank_low_yield_is_untrusted():
    # The two-sided companion to G-11: low ink + low yield → near_blank, boxes untrusted.
    f = PageDensityFeatures(ink_fraction=0.02, box_count=400, token_yield=0.02, mean_token_length=1.1)
    v = _c(_clf(), f)
    assert v.band is DensityBand.NEAR_BLANK
    assert v.boxes_trusted is False


def test_confidence_is_edge_margin_not_raw_ink():
    # THE Finding-B trap guard: a confident dark page reads ink 0.90, but its verdict confidence is
    # the margin to the nearest edge (0.90 - 0.60 = 0.30), NOT 0.90. RED (mutant): return ink_fraction
    # as confidence → 0.90 != 0.30 reds. Ink-confidence would be maximal on exactly the pages we
    # least trust — the whole reason confidence is a margin.
    f = PageDensityFeatures(ink_fraction=0.90, box_count=400, token_yield=0.02, mean_token_length=1.1)
    v = _c(_clf(), f)
    assert v.confidence == pytest.approx(0.30)
    assert v.confidence != pytest.approx(0.90)


def test_content_confidence_is_the_nearer_of_the_yield_and_ink_edges():
    # Content flips to abstain if yield falls to the floor OR to non_text_dark if ink rises to
    # ink_dark_min — confidence is the nearer edge. ink 0.52 (ink edge 0.08) with yield 0.90 (yield
    # edge 0.40) → confidence 0.08, the ink edge. RED (mutant): drop the ink term from the content
    # margin → confidence reports 0.40, blind to a content page creeping toward the dark edge.
    f = PageDensityFeatures(ink_fraction=0.52, box_count=400, token_yield=0.90, mean_token_length=5.0)
    v = _c(_clf(), f)
    assert v.band is DensityBand.CONTENT
    assert v.confidence == pytest.approx(0.08)


def test_content_near_the_dark_edge_abstains():
    # A content-yield page that is suspiciously dark (ink 0.58, ink edge 0.02 < 0.05) routes rather
    # than being stamped confident content — the ink term in the content margin driving an abstain.
    f = PageDensityFeatures(ink_fraction=0.58, box_count=400, token_yield=0.90, mean_token_length=5.0)
    v = _c(_clf(), f)
    assert v.band is DensityBand.ABSTAIN
    assert v.signal == "band-margin"
    assert v.confidence == pytest.approx(0.02)


def test_abstain_at_content_boundary_routes_never_guesses():
    # G-9: a page exactly on the content yield boundary (yield == floor, boxes ok) is raw-content but
    # margin 0 < confidence_margin → ABSTAIN, routed. RED (mutant): map abstain→content (remove the
    # margin override) → returns CONTENT, the guess G-9 forbids.
    f = PageDensityFeatures(ink_fraction=0.20, box_count=400, token_yield=0.50, mean_token_length=5.0)
    v = _c(_clf(), f)
    assert v.band is DensityBand.ABSTAIN
    assert v.routed is True
    assert v.boxes_trusted is False
    assert v.signal == "band-margin"


def test_abstain_in_ink_midband_is_first_class():
    # G-9 second cause: low yield with ink between the two edges — cannot tell blank from dark, so
    # abstain is the honest class, not a forced near_blank/non_text_dark. RED (mutant): map the
    # else-branch to a trusted/untrusted class → reds.
    f = PageDensityFeatures(ink_fraction=0.35, box_count=400, token_yield=0.02, mean_token_length=1.1)
    v = _c(_clf(), f)
    assert v.band is DensityBand.ABSTAIN
    assert v.signal == "ink-ambiguous"
    assert v.confidence == 0.0


def test_near_blank_within_margin_of_the_ink_midband_abstains():
    # An untrusted class also respects the edge margin: ink just below blank_max (0.10 - 0.08 = 0.02
    # margin < 0.05) → abstain, not a confident near_blank. Guards the untrusted-side margin + the
    # boxes_ok min() path.
    f = PageDensityFeatures(ink_fraction=0.08, box_count=400, token_yield=0.02, mean_token_length=1.1)
    v = _c(_clf(), f)
    assert v.band is DensityBand.ABSTAIN
    assert v.signal == "band-margin"
    assert v.confidence == pytest.approx(0.02)


def test_low_box_count_divider_is_not_content_even_with_clean_tokens():
    # The box_content_min hard gate: a two-box "«PARTE SECONDA»" divider has yield ~1.0 but too few
    # boxes to be content; low ink → confident near_blank (NOT content, NOT a spurious abstain from a
    # negative margin). RED (mutant): drop boxes_ok from the content condition → divider → CONTENT.
    f = PageDensityFeatures(ink_fraction=0.02, box_count=2, token_yield=1.0, mean_token_length=6.0)
    v = _c(_clf(), f)
    assert v.band is DensityBand.NEAR_BLANK
    assert v.boxes_trusted is False
    assert v.confidence == pytest.approx(0.10 - 0.02)  # ink margin only; yield axis can't flip it


def test_near_blank_close_to_content_yield_abstains():
    # A very-low-ink page (ink 0.01, well inside near_blank) whose token_yield is just under the
    # content floor (0.48 vs 0.50, boxes ok) is ambiguous with content on the yield axis: the margin
    # is min(ink 0.09, yield 0.02) = 0.02 < 0.05 → abstain. Guards the boxes_ok min() path — a max()
    # there would take 0.09 and wrongly stamp it a confident near_blank.
    f = PageDensityFeatures(ink_fraction=0.01, box_count=400, token_yield=0.48, mean_token_length=5.0)
    v = _c(_clf(), f)
    assert v.band is DensityBand.ABSTAIN
    assert v.signal == "band-margin"
    assert v.confidence == pytest.approx(0.02)


def test_classify_is_deterministic():
    f = PageDensityFeatures(ink_fraction=0.90, box_count=400, token_yield=0.02, mean_token_length=1.1)
    clf = _clf()
    assert clf.classify(f, leaf_index=10, n_leaves=20) == clf.classify(f, leaf_index=10, n_leaves=20)


# --- Positional COVER class (5th band; RULED by Ben 2026-07-06) --------------------------------- #


def test_cover_at_first_leaf_is_untrusted_not_routed():
    # A near-saturated leaf at the front (leaf 1, within cover_edge_leaves=3) is a COVER: boxes
    # untrusted, but confidently classed (not routed). RED (mutant): drop the cover branch → the
    # saturated leaf falls through to NON_TEXT_DARK.
    f = PageDensityFeatures(ink_fraction=0.98, box_count=1189, token_yield=0.75, mean_token_length=2.9)
    v = _clf().classify(f, leaf_index=1, n_leaves=20)
    assert v.band is DensityBand.COVER
    assert v.boxes_trusted is False
    assert v.routed is False
    assert v.signal == "cover"
    assert v.confidence == pytest.approx(0.98 - 0.90)  # ink above the saturation edge


def test_cover_at_last_leaf_uses_the_near_end_window():
    # The back cover: leaf 20 of 20 is within cover_edge_leaves of the END (20 > 20-3). RED (mutant):
    # drop the near-end clause of at_extreme → the back cover is misclassed NON_TEXT_DARK.
    f = PageDensityFeatures(ink_fraction=1.0, box_count=1189, token_yield=0.75, mean_token_length=2.9)
    v = _clf().classify(f, leaf_index=20, n_leaves=20)
    assert v.band is DensityBand.COVER


def test_interior_saturated_leaf_is_not_a_cover():
    # Position × saturation: the SAME saturated features at an interior leaf are NOT a cover — an
    # interior dark page is the NON_TEXT_DARK anomaly. RED (mutant): drop the at_extreme condition →
    # every saturated page becomes a cover regardless of position.
    f = PageDensityFeatures(ink_fraction=0.98, box_count=1189, token_yield=0.75, mean_token_length=2.9)
    v = _clf().classify(f, leaf_index=10, n_leaves=20)
    assert v.band is DensityBand.NON_TEXT_DARK


def test_extreme_but_not_saturated_leaf_is_not_a_cover():
    # A dark-but-not-saturated leaf (ink 0.70, between ink_dark_min 0.60 and ink_saturation_min 0.90)
    # at the extreme is NON_TEXT_DARK, not a cover — the saturation gate, not position alone, makes a
    # cover. RED (mutant): weaken the cover ink test to ink_dark_min → this dark endpaper → cover.
    f = PageDensityFeatures(ink_fraction=0.70, box_count=400, token_yield=0.02, mean_token_length=1.1)
    v = _clf().classify(f, leaf_index=1, n_leaves=20)
    assert v.band is DensityBand.NON_TEXT_DARK


def test_extreme_content_leaf_is_still_content():
    # Position alone never overrides: a real content page near the front (leaf 2) is CONTENT — cover
    # needs saturation too. RED (mutant): make cover fire on position alone → front-matter content →
    # cover.
    f = PageDensityFeatures(ink_fraction=0.20, box_count=400, token_yield=0.90, mean_token_length=5.0)
    v = _clf().classify(f, leaf_index=2, n_leaves=20)
    assert v.band is DensityBand.CONTENT


def test_cover_near_start_boundary_leaf_is_extreme():
    # The near-start window is inclusive: leaf_index == cover_edge_leaves (3) is still extreme. RED
    # (mutant): <= → < drops leaf 3 out of the extreme set → the saturated leaf → NON_TEXT_DARK.
    f = PageDensityFeatures(ink_fraction=0.98, box_count=1189, token_yield=0.75, mean_token_length=2.9)
    v = _clf().classify(f, leaf_index=3, n_leaves=20)  # cover_edge_leaves = 3
    assert v.band is DensityBand.COVER


def test_near_end_boundary_leaf_just_outside_is_not_cover():
    # The near-end window is leaf_index > n_leaves - cover_edge_leaves (> 17); leaf 17 is the first
    # NON-extreme leaf. RED (mutant): > → >= pulls leaf 17 into the extreme set → saturated → COVER.
    f = PageDensityFeatures(ink_fraction=0.98, box_count=1189, token_yield=0.75, mean_token_length=2.9)
    v = _clf().classify(f, leaf_index=17, n_leaves=20)
    assert v.band is DensityBand.NON_TEXT_DARK


def test_cover_ink_saturation_boundary_is_inclusive():
    # ink exactly at ink_saturation_min (0.90) is on the cover side (>=): the raw band is COVER with
    # margin 0, so it abstains (band-margin). RED (mutant): >= → > drops it off the cover side → the
    # saturated leaf reads as a confident NON_TEXT_DARK (ink 0.90 >= ink_dark_min 0.60, margin 0.30).
    f = PageDensityFeatures(ink_fraction=0.90, box_count=1189, token_yield=0.75, mean_token_length=2.9)
    v = _clf().classify(f, leaf_index=1, n_leaves=20)
    assert v.band is DensityBand.ABSTAIN
    assert v.signal == "band-margin"
    assert v.confidence == pytest.approx(0.0)


def test_non_text_dark_ink_boundary_is_inclusive():
    # ink exactly at ink_dark_min (0.60) is dark (>=): raw NON_TEXT_DARK, margin 0 → abstain
    # (band-margin). RED (mutant): >= → > drops it out of dark → a low-yield page with mid-band ink
    # abstains as ink-ambiguous instead — a different signal.
    f = PageDensityFeatures(ink_fraction=0.60, box_count=400, token_yield=0.02, mean_token_length=1.1)
    v = _c(_clf(), f)
    assert v.band is DensityBand.ABSTAIN
    assert v.signal == "band-margin"


def test_cover_within_margin_of_saturation_abstains():
    # A cover-position leaf whose ink barely clears saturation (0.92, margin 0.02 < 0.05) routes
    # rather than auto-declining — the band-margin override applies to COVER too. RED (mutant):
    # early-return the cover before the margin check → it auto-declines on a hairline saturation.
    f = PageDensityFeatures(ink_fraction=0.92, box_count=1189, token_yield=0.75, mean_token_length=2.9)
    v = _clf().classify(f, leaf_index=1, n_leaves=20)
    assert v.band is DensityBand.ABSTAIN
    assert v.signal == "band-margin"
    assert v.confidence == pytest.approx(0.02)


# (1, 2.5): a non-int n_leaves is caught ONLY by the n_leaves guard — with n_leaves=0 the leaf-index
# guard (1 <= leaf <= 0 fails) masks it, so the count guard needs its own isolating case. (True, 20)
# and (1.0, 20): a bool / float leaf_index that is numerically IN range — only the `type(...) is int`
# check (not a numeric bound) rejects them, so they isolate that clause from a numeric-relax mutant.
@pytest.mark.parametrize(
    "leaf,n", [(0, 20), (21, 20), (1, 0), (-1, 20), (1, 2.5), (True, 20), (1.0, 20), (1, True)]
)
def test_classify_rejects_invalid_position(leaf, n):
    f = PageDensityFeatures(ink_fraction=0.20, box_count=400, token_yield=0.90, mean_token_length=5.0)
    with pytest.raises(ValueError, match="leaf_index|n_leaves"):
        _clf().classify(f, leaf_index=leaf, n_leaves=n)


def test_classify_page_extracts_then_classifies():
    # The convenience entry the calibration probe / #39 wiring use: pixmap + boxes + position →
    # (features, verdict). A dark interior pixmap of noise boxes → non_text_dark.
    pm = fitz.Pixmap(fitz.csGRAY, 2, 2, bytes([0, 0, 0, 255]), False)  # 0.75 ink
    boxes = [_box(".") for _ in range(20)] + [_box("x")]  # yield ~0, "x" is 1-char → not alpha
    features, verdict = _clf().classify_page(pixmap=pm, boxes=boxes, leaf_index=10, n_leaves=20)
    assert features.ink_fraction == pytest.approx(0.75)
    assert verdict.band is DensityBand.NON_TEXT_DARK


# ================================================================================================ #
# S2.1.5 (#39) — column / reading-order detector (DT-7) + cross-page prior (R8).
#
# The projection-profile column detector generalized from the S2.0 probe with the adversarial
# audit's rulings baked in: a contiguous central valley (>= 3 bins) splitting the page into two
# genuinely-populated halves, mirror-symmetry DROPPED. ``detect_columns`` is pure geometry
# (col2_score = valley depth x column balance); ``ColumnDetector`` applies the calibrated decision
# threshold + hysteresis margin; ``resolve_reading_columns`` threads the cross-page prior under the
# density gate. Fake tier: synthetic WordBox layouts, no PDF/OCR (the real-OCR end-to-end is
# ``test_geometry_e2e.py``, G-16).
# ================================================================================================ #

_W = 1000.0  # page width used by the column fixtures; 100 projection bins -> bin b spans [10b, 10b+10)


def _boxc(b: int, *, row: int = 0, text: str = "w", width: float = _W, bins: int = 100) -> WordBox:
    """A WordBox whose x-center falls in projection bin ``b``, on line ``row`` (distinct y). The
    detector reads only box x-centers (for binning) and y/height (for line-order); text is carried
    for reading_order."""
    xc = (b + 0.5) / bins * width
    y = 20.0 + row * 30.0
    return WordBox(text=text, bbox=(xc - 3.0, y, xc + 3.0, y + 12.0))


def _two_col_boxes(*, left_bins=range(15, 41), right_bins=range(60, 86)) -> list[WordBox]:
    """Two dense clusters (one box per bin, so peak count = 1) with an empty central gutter
    (bins 41-59). Left texts ``L0..``, right ``R0..``, each on its own line top-to-bottom."""
    boxes = [_boxc(b, row=i, text=f"L{i}") for i, b in enumerate(left_bins)]
    boxes += [_boxc(b, row=i, text=f"R{i}") for i, b in enumerate(right_bins)]
    return boxes


def _sparse_single_col_boxes() -> list[WordBox]:
    """>= 25 boxes filling the central third EXCEPT a 2-bin gap (bins 49-50) — a stray sparse gap,
    NOT a >= 3-bin gutter, split ~50/50. The G-10 fixture: only the >= 3-bin run guard keeps this
    single-column (the populated-halves guard passes at 50/50)."""
    populated = list(range(33, 49)) + list(range(51, 67))  # 16 + 16 = 32 boxes; bins 49,50 empty
    return [_boxc(b, row=i) for i, b in enumerate(populated)]


def _det(**overrides) -> ColumnDetector:
    params = dict(decision_threshold=0.5, hysteresis_margin=0.15)
    params.update(overrides)
    return ColumnDetector(**params)


def _dense_two_col(*, strays: tuple[int, ...] = ()) -> list[WordBox]:
    """Two columns stacked 7-deep per bin (peak = 7, so a lone box in a gutter bin, count 1 <=
    0.15*7 = 1.05, still reads as 'empty') plus optional single-box strays in central gutter bins.
    Columns sit OUTSIDE the central band (bins 20-30 / 70-80) so they never break the gutter run;
    the strays are placed symmetrically about the split, so they move valley depth WITHOUT touching
    column balance."""
    boxes: list[WordBox] = []
    row = 0
    for b in (*range(20, 31), *range(70, 81)):
        boxes += [_boxc(b, row=row + k) for k in range(7)]
        row += 7
    for b in strays:
        boxes.append(_boxc(b, row=row))
        row += 1
    return boxes


# --- detect_columns: projection-profile evidence (pure geometry) -------------------------------- #


def test_two_column_page_scores_a_deep_balanced_gutter():
    ev = detect_columns(_two_col_boxes(), _W)
    assert isinstance(ev, ColumnEvidence)
    assert ev.col2_score == pytest.approx(1.0)         # depth 1.0 (empty gutter) x balance 1.0 (50/50)
    assert 0.40 * _W <= ev.split_x <= 0.60 * _W        # gutter near center


def test_sparse_single_column_is_not_two_column_g10():
    # G-10: a sparse page with a 2-bin central gap (no >= 3-bin contiguous gutter) is single-column,
    # col2_score 0.0. RED (mutant): remove the >= 3-bin run guard (min_gutter_bins 3 -> 1) -> the
    # 2-bin gap reads as a gutter, splits 50/50, and scores > 0.
    ev = detect_columns(_sparse_single_col_boxes(), _W)
    assert ev.col2_score == 0.0
    assert ev.split_x == pytest.approx(_W)             # no gutter -> full width


def test_too_few_boxes_is_single_column():
    # Below the min-box floor the projection profile is too sparse to assert a gutter at all.
    ev = detect_columns([_boxc(20), _boxc(80)], _W)    # 2 boxes, clearly < the floor
    assert ev.col2_score == 0.0


def test_gutter_must_sit_near_center_not_at_the_margin():
    # A real >= 3-bin empty run that lies INSIDE the central search band but off to one side (bins
    # 33-37, midpoint ~0.355w) is not a true center gutter: the center-range guard (0.40-0.60)
    # rejects it. RED (mutant): drop the center guard -> this off-center valley scores > 0. (The empty
    # run is inside 33-66 so the >= 3-bin guard passes it through to the center check — this fixture
    # isolates the center guard, unlike a margin band the >= 3-bin guard would already reject.)
    boxes = [_boxc(b, row=i) for i, b in enumerate(range(12, 33))]        # left cluster bins 12-32
    boxes += [_boxc(b, row=i) for i, b in enumerate(range(38, 67))]       # right cluster bins 38-66
    ev = detect_columns(boxes, _W)                                        # empty run bins 33-37, off-center
    assert ev.col2_score == 0.0


def test_unbalanced_halves_lower_the_score_via_column_balance():
    # A real gutter but a lopsided split (26 left vs 13 right = 0.667/0.333) still detects two columns
    # but at a lower score: depth 1.0 x balance (0.333/0.667 = 0.5) = 0.5. Pins col2_score = depth x
    # balance (a mutant dropping the balance factor returns 1.0).
    ev = detect_columns(_two_col_boxes(left_bins=range(15, 41), right_bins=range(60, 73)), _W)
    assert ev.col2_score == pytest.approx(0.5)


def test_lopsided_beyond_the_populated_halves_band_is_single_column():
    # A tiny right stub (26 left vs 4 right = 0.867/0.133) fails the populated-halves guard (0.133 <
    # 0.28): not two genuinely-populated columns. RED (mutant): drop the populated-halves guard -> the
    # stub scores as a column.
    ev = detect_columns(_two_col_boxes(left_bins=range(15, 41), right_bins=range(60, 64)), _W)
    assert ev.col2_score == 0.0


def test_valley_depth_lowers_score_for_a_partially_filled_gutter():
    # col2_score = valley_depth x balance: a gutter with sub-threshold strays is less confidently a
    # gutter than an empty one. The strays are symmetric about the split, so column balance is
    # identical between the two and ONLY valley depth changes. RED (mutant): valley_depth -> 1.0 drops
    # the depth factor -> the two score equally and `strays < empty` fails.
    empty = detect_columns(_dense_two_col(), _W).col2_score
    strays = detect_columns(_dense_two_col(strays=(45, 46, 47, 48, 49, 51, 52, 53, 54, 55)), _W).col2_score
    assert empty == pytest.approx(1.0)                 # empty gutter, 50/50 split -> depth 1 x balance 1
    assert 0.0 < strays < empty


def test_centered_gutter_element_does_not_shadow_a_valid_gutter():
    # A two-column page with a centered element sitting in the gutter zone (a centered running head /
    # folio / caption) splits the central empty band into two runs: a longer OFF-center run and a
    # shorter CENTERED one. The detector must not fix on the global-longest run, reject it on the
    # center guard, and declare a confident single column — it must find the valid centered gutter.
    # RED (pre-fix / mutant that keeps only the longest run): returns col2_score 0.0 (confident
    # single-column) even though the control (same boxes, no centered element) is a clean two-column.
    bins = [*range(20, 33), 46, 47, 48, *range(52, 65)]  # two columns + 3 centered gutter boxes
    boxes = [_boxc(b, row=i) for i, b in enumerate(bins)]
    ev = detect_columns(boxes, _W)
    assert ev.col2_score > 0.0, "a centered element must not shadow the real centered gutter"
    assert 0.40 * _W <= ev.split_x <= 0.60 * _W
    # and the control (drop the 3 centered boxes) is unambiguously two-column
    control = [_boxc(b, row=i) for i, b in enumerate([*range(20, 33), *range(52, 65)])]
    assert detect_columns(control, _W).col2_score == pytest.approx(1.0)


def test_detect_columns_rejects_nonpositive_width():
    # Defensive: a non-positive page width would divide by zero in the projection binning. Page width
    # from the backend is always positive; a clear ValueError beats a ZeroDivisionError deep inside.
    with pytest.raises(ValueError, match="width"):
        detect_columns(_two_col_boxes(), 0.0)


def test_detect_columns_reads_word_boxes_not_tuples():
    # The promoted detector reads production WordBox records (.bbox), not the probe's raw tuples.
    boxes = _two_col_boxes()
    assert all(isinstance(b, WordBox) for b in boxes)
    assert detect_columns(boxes, _W).col2_score > 0.0


# --- ColumnDetector: calibrated decision threshold + hysteresis margin --------------------------- #


def test_column_detector_requires_both_params_no_default():
    with pytest.raises(TypeError):
        ColumnDetector(decision_threshold=0.5)          # hysteresis_margin omitted
    with pytest.raises(TypeError):
        ColumnDetector(hysteresis_margin=0.15)          # decision_threshold omitted


@pytest.mark.parametrize(
    "overrides,needle",
    [
        ({"decision_threshold": 0.0}, "decision_threshold"),   # must be in (0, 1)
        ({"decision_threshold": 1.0}, "decision_threshold"),
        ({"decision_threshold": float("nan")}, "decision_threshold"),
        ({"hysteresis_margin": 0.0}, "hysteresis_margin"),     # must be in (0, 1]
        ({"hysteresis_margin": 1.5}, "hysteresis_margin"),
    ],
)
def test_column_detector_rejects_incoherent_params(overrides, needle):
    with pytest.raises(ValueError, match=needle):
        _det(**overrides)


def test_confident_two_column_verdict():
    ev = ColumnEvidence(col2_score=1.0, split_x=505.0)
    v = _det().classify(ev)
    assert isinstance(v, ColumnVerdict)
    assert v.n_cols == 2
    assert v.confident is True                          # margin |1.0 - 0.5| = 0.5 >= 0.15
    assert v.confidence == pytest.approx(0.5)
    assert v.signal == "evidence"


def test_confident_single_column_verdict():
    ev = ColumnEvidence(col2_score=0.0, split_x=_W)
    v = _det().classify(ev)
    assert v.n_cols == 1
    assert v.confident is True                          # margin |0.0 - 0.5| = 0.5 >= 0.15
    assert v.confidence == pytest.approx(0.5)


def test_score_inside_the_hysteresis_margin_is_not_confident():
    # A score just above the decision threshold (0.55, margin 0.05 < 0.15) leans two-column but is
    # NOT confident — the cross-page prior decides it. RED (mutant): drop the margin comparison ->
    # every page reads confident and the prior never engages.
    ev = ColumnEvidence(col2_score=0.55, split_x=505.0)
    v = _det().classify(ev)
    assert v.n_cols == 2                                # lean is by the threshold
    assert v.confident is False
    assert v.confidence == pytest.approx(0.05)
    assert v.signal == "weak-evidence"


def test_decision_threshold_boundary_is_inclusive_for_two_columns():
    # A score exactly at the threshold leans two-column (>=), margin 0 -> not confident.
    v = _det().classify(ColumnEvidence(col2_score=0.5, split_x=505.0))
    assert v.n_cols == 2
    assert v.confident is False
    assert v.confidence == pytest.approx(0.0)


def test_hysteresis_margin_boundary_is_inclusive():
    # confidence exactly at the hysteresis margin is confident (>=). Dyadic-exact values (0.75, 0.5,
    # 0.25 are all exact in IEEE-754, so |0.75 - 0.5| == 0.25 with no float residue) put confidence
    # EXACTLY on the margin — a value like 0.65 - 0.5 = 0.15000000000000002 would sit just above it
    # and hide the comparator. RED (mutant): >= -> > drops the exact boundary out of confident.
    v = _det(hysteresis_margin=0.25).classify(ColumnEvidence(col2_score=0.75, split_x=505.0))
    assert v.confidence == 0.25          # exact, not approx — the point is the boundary is exact
    assert v.confident is True


def test_column_detector_version_is_pinned():
    # Pin the literal, not the constant against itself — the property returns the constant, so the
    # old `_det().version == COLUMN_DETECTOR_VERSION` passed under any drift (#55). Matches the
    # density twin's posture (test_version_and_params_are_pinned_for_the_sidecar_fingerprint).
    assert COLUMN_DETECTOR_VERSION == "columns-v1"
    assert _det().version == "columns-v1"


# --- ColumnEvidence / ColumnVerdict / PageColumnVerdict record validity ------------------------- #


@pytest.mark.parametrize("bad", [1.5, -0.1, float("nan"), float("inf")])
def test_column_evidence_rejects_out_of_range_score(bad):
    with pytest.raises(ValueError, match="col2_score"):
        ColumnEvidence(col2_score=bad, split_x=505.0)


@pytest.mark.parametrize("bad", [0.0, -1.0, float("nan")])
def test_column_evidence_rejects_nonpositive_split(bad):
    with pytest.raises(ValueError, match="split_x"):
        ColumnEvidence(col2_score=0.5, split_x=bad)


@pytest.mark.parametrize("bad", [0, 3, -1])
def test_column_verdict_rejects_bad_n_cols(bad):
    with pytest.raises(ValueError, match="n_cols"):
        ColumnVerdict(n_cols=bad, confidence=0.2, confident=True, signal="evidence")


def test_column_verdict_rejects_negative_confidence():
    with pytest.raises(ValueError, match="confidence"):
        ColumnVerdict(n_cols=2, confidence=-0.1, confident=True, signal="evidence")


def test_page_column_verdict_rejects_bad_source_and_count():
    with pytest.raises(ValueError, match="n_cols_source"):
        PageColumnVerdict(n_cols=2, n_cols_source="banana", routed=False, signal="evidence")
    with pytest.raises(ValueError, match="n_cols"):
        PageColumnVerdict(n_cols=5, n_cols_source="evidence", routed=False, signal="evidence")


# --- reading_order: columns top-to-bottom, left column first ------------------------------------ #


def test_reading_order_two_columns_reads_left_column_then_right():
    boxes = _two_col_boxes()
    ev = detect_columns(boxes, _W)
    order = reading_order(boxes, split_x=ev.split_x)
    expected = [f"L{i}" for i in range(26)] + [f"R{i}" for i in range(26)]
    assert list(order) == expected


def test_reading_order_single_column_sorts_by_line_then_x():
    # Single column (split_x None): a plain top-to-bottom, left-to-right line sort.
    boxes = [_boxc(30, row=2, text="third"), _boxc(10, row=0, text="first"), _boxc(50, row=1, text="second")]
    assert list(reading_order(boxes, split_x=None)) == ["first", "second", "third"]


def test_reading_order_two_columns_beats_naive_full_width_order():
    # The unit companion to G-16: recovering the column split reproduces the true reading order
    # (coverage 1.0), while a naive full-width line sort interleaves the columns and loses it.
    boxes = _two_col_boxes()
    ev = detect_columns(boxes, _W)
    expected = [f"L{i}" for i in range(26)] + [f"R{i}" for i in range(26)]
    col_order = reading_order(boxes, split_x=ev.split_x)
    naive_order = reading_order(boxes, split_x=None)     # ignore columns -> row-interleaved
    assert ordered_coverage(expected, col_order) == pytest.approx(1.0)
    assert ordered_coverage(expected, naive_order) < 1.0


# --- ordered_coverage: LCS-based order metric (DT-5 order_qa feed; G-16 pin) --------------------- #


def test_ordered_coverage_identical_is_one():
    assert ordered_coverage(["a", "b", "c"], ["a", "b", "c"]) == pytest.approx(1.0)


def test_ordered_coverage_all_expected_in_order_with_extras_is_one():
    assert ordered_coverage(["a", "b"], ["x", "a", "y", "b", "z"]) == pytest.approx(1.0)


def test_ordered_coverage_out_of_order_is_partial():
    # Reversed: only a length-1 subsequence is common -> 1/3.
    assert ordered_coverage(["a", "b", "c"], ["c", "b", "a"]) == pytest.approx(1.0 / 3.0)


def test_ordered_coverage_partial_fraction():
    assert ordered_coverage(["a", "b", "c", "d"], ["a", "b"]) == pytest.approx(0.5)


def test_ordered_coverage_empty_expected_is_zero_not_vacuous_one():
    # No expected tokens is undefined coverage; 0.0 avoids a vacuous perfect score on an empty page.
    assert ordered_coverage([], ["a", "b"]) == 0.0


# --- resolve_reading_columns: cross-page prior under the density gate (DT-7 / R8; G-23) ---------- #
#
# ``resolve_reading_columns`` threads a book's pages through the prior: a content page whose own
# column evidence is confident keeps it (clause 2); an in-margin content page inherits an agreeing
# neighbor's class (locally-constant layout) but abstains to the worklist on disagreement (clause 3);
# any non-content or routed page RESETS the chain so the prior never tunnels an endpaper (clause 1);
# every decided page records n_cols_source "evidence"/"prior" (clause 4). The score->band coupling
# uses tiny synthetic evidence + density verdicts (no PDF).


def _content_dv() -> DensityVerdict:
    """A density verdict that trusts the boxes (band CONTENT) — the gate that lets a page carry a
    column verdict at all."""
    return DensityVerdict(DensityBand.CONTENT, confidence=0.30, signal="content")


def _dark_dv() -> DensityVerdict:
    """An untrusted (non-content) density verdict — near_blank/dark/cover all reset the prior chain."""
    return DensityVerdict(DensityBand.NON_TEXT_DARK, confidence=0.30, signal="non_text_dark")


def _routed_dv() -> DensityVerdict:
    """A density-abstained (routed) page — routes to the worklist and resets the prior chain."""
    return DensityVerdict(DensityBand.ABSTAIN, confidence=0.0, signal="ink-ambiguous")


def _pin(score: float, density: DensityVerdict | None = None) -> PageColumnInput:
    """A page input: a column evidence of the given col2_score + a density verdict (content default)."""
    return PageColumnInput(density=density or _content_dv(), evidence=ColumnEvidence(col2_score=score, split_x=505.0))


# Under _det() (threshold 0.5, margin 0.15): score 1.0 -> confident 2-col; score 0.0 -> confident
# 1-col; score 0.55 -> in-margin (margin 0.05 < 0.15), leans 2-col but not confident.
_CONF2, _CONF1, _INMARGIN = 1.0, 0.0, 0.55


def test_confident_pages_keep_their_own_evidence():
    verdicts = resolve_reading_columns([_pin(_CONF2), _pin(_CONF1)], _det())
    assert [v.n_cols for v in verdicts] == [2, 1]
    assert all(v.n_cols_source == "evidence" and not v.routed for v in verdicts)


def test_strong_single_column_between_two_two_columns_keeps_its_own_evidence_g23():
    # G-23: the middle page's own evidence is confidently single-column; the prior must NOT override
    # it to two-column just because both neighbors are two-column. RED (mutant): let the prior override
    # strong own-page evidence (drop the `confident` guard / force the prior branch) -> the middle page
    # inherits 2 columns from its neighbors.
    verdicts = resolve_reading_columns([_pin(_CONF2), _pin(_CONF1), _pin(_CONF2)], _det())
    assert verdicts[1].n_cols == 1
    assert verdicts[1].n_cols_source == "evidence"
    assert verdicts[1].routed is False


def test_in_margin_page_inherits_agreeing_neighbors():
    # An in-margin content page between two confident two-column pages inherits two columns — layout
    # is locally constant, the prior breaking a tie inside the margin (R8 clause 2; the disagree->
    # abstain half is clause 3, tested separately). Records source "prior".
    verdicts = resolve_reading_columns([_pin(_CONF2), _pin(_INMARGIN), _pin(_CONF2)], _det())
    assert verdicts[1].n_cols == 2
    assert verdicts[1].n_cols_source == "prior"
    assert verdicts[1].routed is False


def test_in_margin_page_between_disagreeing_neighbors_abstains():
    # Clause 3: an in-margin page whose confident neighbors DISAGREE (2-col before, 1-col after) cannot
    # inherit — it abstains to the worklist. RED (mutant): inherit from one side only / ignore the
    # disagreement -> it takes a column count instead of routing.
    verdicts = resolve_reading_columns([_pin(_CONF2), _pin(_INMARGIN), _pin(_CONF1)], _det())
    assert verdicts[1].routed is True
    assert verdicts[1].n_cols is None
    assert verdicts[1].n_cols_source is None
    assert verdicts[1].signal == "prior-ambiguous"


def test_untrusted_page_resets_the_prior_chain():
    # Clause 1: a non-content (untrusted) page breaks the chain — an in-margin page after it cannot
    # inherit the two-column class from before it (the prior must never tunnel an endpaper). RED
    # (mutant): don't reset the prior on a non-content page -> the in-margin page inherits across it.
    verdicts = resolve_reading_columns([_pin(_CONF2), _pin(0.0, _dark_dv()), _pin(_INMARGIN)], _det())
    assert verdicts[1].n_cols is None and verdicts[1].routed is False
    assert verdicts[1].signal == "boxes-untrusted"
    assert verdicts[2].routed is True          # no prior survived the reset -> nothing to inherit
    assert verdicts[2].n_cols is None


def test_routed_density_page_resets_the_prior_chain_and_routes():
    # Clause 1, routed variant: a density-abstained page routes AND resets the chain.
    verdicts = resolve_reading_columns([_pin(_CONF2), _pin(0.0, _routed_dv()), _pin(_INMARGIN)], _det())
    assert verdicts[1].routed is True and verdicts[1].n_cols is None
    assert verdicts[1].signal == "density-routed"
    assert verdicts[2].routed is True          # chain reset -> the in-margin page has no neighbor to inherit


def test_in_margin_page_with_a_single_agreeing_neighbor_inherits():
    # At a chain boundary only one side has a confident content neighbor; the in-margin page still
    # inherits it (locally-constant layout), it does not need both sides. Two trailing in-margin pages
    # both inherit the single leading confident 1-col page.
    verdicts = resolve_reading_columns([_pin(_CONF1), _pin(_INMARGIN), _pin(_INMARGIN)], _det())
    assert [v.n_cols for v in verdicts] == [1, 1, 1]
    assert verdicts[1].n_cols_source == "prior" and verdicts[2].n_cols_source == "prior"


def test_isolated_in_margin_page_abstains():
    # An in-margin page with NO confident content neighbor on either side has nothing to inherit ->
    # abstain (the calibrate-to-abstain posture; a lone weak page is a human's call).
    verdicts = resolve_reading_columns([_pin(_INMARGIN)], _det())
    assert verdicts[0].routed is True
    assert verdicts[0].n_cols is None


def test_untrusted_page_carries_no_column_verdict():
    # A non-content page itself gets no column count (its boxes are untrusted) but is NOT routed by
    # the column stage — the density stage already made its trust ruling.
    verdicts = resolve_reading_columns([_pin(0.0, _dark_dv())], _det())
    assert verdicts[0].n_cols is None
    assert verdicts[0].n_cols_source is None
    assert verdicts[0].routed is False
    assert verdicts[0].signal == "boxes-untrusted"


def test_resolve_reading_columns_empty_is_empty():
    assert resolve_reading_columns([], _det()) == []


def test_realistic_book_slice_threads_every_clause():
    # End-to-end over one book slice exercising all four clauses in order: a dark cover (untrusted,
    # resets), a 1-col front-matter page (evidence), a weak chapter-open BETWEEN a 1-col and a 2-col
    # page (disagreeing neighbors -> abstain), two 2-col body pages (evidence), a routed smudge
    # (routes + resets), and a trailing weak page isolated by the reset (abstain).
    pages = [
        _pin(0.0, _dark_dv()),   # 0 cover -> untrusted
        _pin(_CONF1),            # 1 front matter -> evidence 1
        _pin(_INMARGIN),         # 2 chapter open, weak; neighbors 1 (prev) and 2 (next) disagree
        _pin(_CONF2),            # 3 body -> evidence 2
        _pin(_CONF2),            # 4 body -> evidence 2
        _pin(0.0, _routed_dv()), # 5 smudge -> routed
        _pin(_INMARGIN),         # 6 weak, isolated by the reset -> abstain
    ]
    v = resolve_reading_columns(pages, _det())
    assert [x.n_cols for x in v] == [None, 1, None, 2, 2, None, None]
    assert [x.n_cols_source for x in v] == [None, "evidence", None, "evidence", "evidence", None, None]
    assert [x.routed for x in v] == [False, False, True, False, False, True, True]
    assert [x.signal for x in v] == [
        "boxes-untrusted", "evidence", "prior-ambiguous", "evidence", "evidence",
        "density-routed", "prior-ambiguous",
    ]
