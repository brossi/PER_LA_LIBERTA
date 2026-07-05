"""Mutant table for the density band pre-check classifier (issue #38; S2.1.4).

Run with the mutation-hunt runner:

    python3 ~/.claude/skills/mutation-hunt/hunt.py \
        --table tests/hunts/hunt_segmentation.py --artifact <scratch>/hunt38.json

Covers the DT-6 semantics (four bands, abstain-routing G-9, dark-untrusted G-11, the
confidence-is-margin-not-ink Finding-B trap), the numberless-core band posture (G-1), the
feature-assembly formulas (token_yield / mean_token_length / alpha-token rule), ink-fraction
extraction across colorspaces, and every record/band guard. TEST_CMD uses the engine venv's
python directly (segmentation tests import engine + fitz); the runner pins its own pyc hygiene.
"""
from pathlib import Path

REPO = str(Path(__file__).resolve().parents[2])
TEST_CMD = [str(Path(REPO) / ".venv" / "bin" / "python"), "-m", "pytest", "{scope}",
            "-q", "--no-header", "-x", "-p", "no:cacheprovider"]
TIMEOUT = 300

S = "src/engine/structure/segmentation.py"
T = "tests/unit/test_segmentation.py"


def m(label, old, new, test_id):
    return {"label": label, "file": S, "old": old, "new": new, "scope": f"{T}::{test_id}"}


MUTANTS = [
    # --- G-9: abstain routes, never guesses -----------------------------------------------------
    m("g9-margin-override-removed",
      "        if margin < self._confidence_margin:",
      "        if False:",
      "test_abstain_at_content_boundary_routes_never_guesses"),
    m("g9-ink-ambiguous-to-nearblank",
      'return DensityVerdict(DensityBand.ABSTAIN, confidence=0.0, signal="ink-ambiguous")',
      'return DensityVerdict(DensityBand.NEAR_BLANK, confidence=0.0, signal="ink-ambiguous")',
      "test_abstain_in_ink_midband_is_first_class"),
    m("g9-band-margin-abstain-to-content",
      'return DensityVerdict(DensityBand.ABSTAIN, confidence=margin, signal="band-margin")',
      'return DensityVerdict(DensityBand.CONTENT, confidence=margin, signal="band-margin")',
      "test_abstain_at_content_boundary_routes_never_guesses"),
    # --- G-11: dark low-yield page untrusted, not trusted as content ----------------------------
    m("g11-content-drops-yield-ok",
      "        if yield_ok and boxes_ok:",
      "        if boxes_ok:",
      "test_dark_low_yield_is_non_text_dark_and_untrusted"),
    m("g11-confident-return-always-content",
      "        return DensityVerdict(raw, confidence=margin, signal=raw.value)",
      "        return DensityVerdict(DensityBand.CONTENT, confidence=margin, signal=raw.value)",
      "test_dark_low_yield_is_non_text_dark_and_untrusted"),
    m("g11-dark-ink-margin-sign",
      "            margin = features.ink_fraction - self._ink_dark_min  # distance down to the ink mid-band",
      "            margin = self._ink_dark_min - features.ink_fraction  # distance down to the ink mid-band",
      "test_dark_low_yield_is_non_text_dark_and_untrusted"),
    # --- the Finding-B trap: confidence is the edge margin, never the raw ink fraction -----------
    m("confidence-is-raw-ink",
      "        return DensityVerdict(raw, confidence=margin, signal=raw.value)",
      "        return DensityVerdict(raw, confidence=features.ink_fraction, signal=raw.value)",
      "test_confidence_is_edge_margin_not_raw_ink"),
    m("content-margin-flipped",
      "            margin = features.token_yield - self._yield_content_min",
      "            margin = self._yield_content_min - features.token_yield",
      "test_content_page_is_trusted_and_confident"),
    # --- box_content_min hard gate (divider is not content) -------------------------------------
    m("content-drops-boxes-ok",
      "        if yield_ok and boxes_ok:",
      "        if yield_ok:",
      "test_low_box_count_divider_is_not_content_even_with_clean_tokens"),
    m("boxes-ok-comparator-flipped",
      "        boxes_ok = features.box_count >= self._box_content_min",
      "        boxes_ok = features.box_count <= self._box_content_min",
      "test_content_page_is_trusted_and_confident"),
    m("yield-ok-comparator-flipped",
      "        yield_ok = features.token_yield >= self._yield_content_min",
      "        yield_ok = features.token_yield <= self._yield_content_min",
      "test_content_page_is_trusted_and_confident"),
    # --- near_blank side: ink margin + untrusted --------------------------------------------------
    m("nearblank-ink-margin-sign",
      "            margin = self._ink_blank_max - features.ink_fraction  # distance up to the ink mid-band",
      "            margin = features.ink_fraction - self._ink_blank_max  # distance up to the ink mid-band",
      "test_near_blank_low_yield_is_untrusted"),
    m("dark-margin-uses-max",
      "                margin = min(margin, self._yield_content_min - features.token_yield)\n        else:",
      "                margin = max(margin, self._yield_content_min - features.token_yield)\n        else:",
      "test_confidence_is_edge_margin_not_raw_ink"),
    m("nearblank-margin-uses-max",
      "                margin = min(margin, self._yield_content_min - features.token_yield)\n        elif features.ink_fraction >= self._ink_dark_min:",
      "                margin = max(margin, self._yield_content_min - features.token_yield)\n        elif features.ink_fraction >= self._ink_dark_min:",
      "test_near_blank_close_to_content_yield_abstains"),
    # --- feature assembly: token_yield / alpha-token rule / mean_token_length --------------------
    m("alpha-count-drops-len-floor",
      "    alpha_count = sum(1 for s in stripped if len(s) >= _MIN_ALPHA_TOKEN_LEN and any(c.isalpha() for c in s))",
      "    alpha_count = sum(1 for s in stripped if any(c.isalpha() for c in s))",
      "test_token_yield_is_alpha_count_over_box_count"),
    m("alpha-count-drops-isalpha",
      "    alpha_count = sum(1 for s in stripped if len(s) >= _MIN_ALPHA_TOKEN_LEN and any(c.isalpha() for c in s))",
      "    alpha_count = sum(1 for s in stripped if len(s) >= _MIN_ALPHA_TOKEN_LEN)",
      "test_token_yield_is_alpha_count_over_box_count"),
    m("mean-denominator-nonblank",
      "    mean_token_length = sum(len(s) for s in stripped) / box_count if box_count else 0.0",
      "    mean_token_length = sum(len(s) for s in stripped) / len([s for s in stripped if s]) if box_count else 0.0",
      "test_mean_token_length_is_over_all_boxes_stripped"),
    m("is-alpha-drops-len-floor",
      "    return len(stripped) >= _MIN_ALPHA_TOKEN_LEN and any(c.isalpha() for c in stripped)",
      "    return any(c.isalpha() for c in stripped)",
      "test_is_alpha_token"),
    m("is-alpha-drops-isalpha",
      "    return len(stripped) >= _MIN_ALPHA_TOKEN_LEN and any(c.isalpha() for c in stripped)",
      "    return len(stripped) >= _MIN_ALPHA_TOKEN_LEN",
      "test_is_alpha_token"),
    m("edge-strip-noop",
      '    return _EDGE.sub("", text)',
      "    return text",
      "test_edge_strip_is_unicode_neutral"),
    # --- ink-fraction extraction: direction, threshold, colorspace/alpha normalization ----------
    m("ink-table-counts-light",
      "_INK_TABLE = bytes(1 if v < _INK_LUMA_THRESHOLD else 0 for v in range(256))",
      "_INK_TABLE = bytes(1 if v >= _INK_LUMA_THRESHOLD else 0 for v in range(256))",
      "test_ink_fraction_asymmetric_pins_direction"),
    m("ink-count-light-value",
      "    return luma.translate(_INK_TABLE).count(1) / len(luma)",
      "    return luma.translate(_INK_TABLE).count(0) / len(luma)",
      "test_ink_fraction_asymmetric_pins_direction"),
    m("ink-threshold-inclusive",
      "_INK_TABLE = bytes(1 if v < _INK_LUMA_THRESHOLD else 0 for v in range(256))",
      "_INK_TABLE = bytes(1 if v <= _INK_LUMA_THRESHOLD else 0 for v in range(256))",
      "test_ink_fraction_threshold_boundary"),
    m("ink-rgb-not-converted",
      "    if pm.colorspace is None or pm.colorspace.n != 1:",
      "    if False:",
      "test_ink_fraction_converts_rgb_to_gray"),
    m("ink-alpha-not-dropped",
      "    if pm.alpha:",
      "    if False:",
      "test_ink_fraction_drops_alpha_channel"),
    # --- record guards (G-21-analogue) ----------------------------------------------------------
    m("feat-fraction-guard-dropped",
      "            if not (math.isfinite(v) and 0.0 <= v <= 1.0):",
      "            if False:",
      "test_features_reject_out_of_range_ink_fraction[1.5]"),
    m("feat-box-guard-dropped",
      "        if not (type(self.box_count) is int and self.box_count >= 0):",
      "        if False:",
      "test_features_reject_non_count_box_count[-1]"),
    m("feat-box-guard-relaxed-to-numeric",
      "        if not (type(self.box_count) is int and self.box_count >= 0):",
      "        if not (self.box_count >= 0):",
      "test_features_reject_non_count_box_count[True]"),
    m("feat-mean-guard-dropped",
      "        if not (math.isfinite(self.mean_token_length) and self.mean_token_length >= 0.0):",
      "        if False:",
      "test_features_reject_bad_mean_token_length[-1.0]"),
    m("verdict-confidence-guard-dropped",
      "        if not (math.isfinite(self.confidence) and self.confidence >= 0.0):",
      "        if False:",
      "test_verdict_rejects_negative_or_nonfinite_confidence[-0.1]"),
    m("verdict-signal-guard-dropped",
      "        if not self.signal:",
      "        if False:",
      "test_verdict_rejects_empty_signal"),
    # --- constructor band guards (fail-loud config integrity) -----------------------------------
    m("ctor-yield-guard-dropped",
      "        if not (math.isfinite(yield_content_min) and 0.0 < yield_content_min <= 1.0):",
      "        if False:",
      "test_classifier_rejects_incoherent_bands[overrides0-yield_content_min]"),
    m("ctor-box-guard-dropped",
      "        if not (type(box_content_min) is int and box_content_min >= 0):",
      "        if False:",
      "test_classifier_rejects_incoherent_bands[overrides2-box_content_min]"),
    m("ctor-blank-guard-dropped",
      "        if not (math.isfinite(ink_blank_max) and 0.0 <= ink_blank_max < 1.0):",
      "        if False:",
      "test_classifier_rejects_incoherent_bands[overrides4-ink_blank_max]"),
    # overrides7 (ink_dark_min=1.5) isolates the dark VALUE guard: it passes the ordering guard
    # (0.10 < 1.5), so only the value guard's upper bound catches it. overrides6 (0.0) cannot isolate
    # the guard against this whole-guard drop: with the value guard mutated to `if False`, 0.0 is then
    # caught by the ORDERING guard (0.10 < 0.0 is False → raises, message names ink_dark_min), so the
    # mutant would SURVIVE overrides6. (In unmutated code 0.0 is caught by the value guard itself.)
    m("ctor-dark-guard-dropped",
      "        if not (math.isfinite(ink_dark_min) and 0.0 < ink_dark_min <= 1.0):",
      "        if False:",
      "test_classifier_rejects_incoherent_bands[overrides7-ink_dark_min]"),
    m("ctor-ordering-guard-dropped",
      "        if not (ink_blank_max < ink_dark_min):",
      "        if False:",
      "test_classifier_rejects_incoherent_bands[overrides10-ink_blank_max]"),
    m("ctor-margin-guard-dropped",
      "        if not (math.isfinite(confidence_margin) and 0.0 < confidence_margin <= 1.0):",
      "        if False:",
      "test_classifier_rejects_incoherent_bands[overrides8-confidence_margin]"),
    # --- G-1: bands are required constructor params (no default) — representative params ---------
    m("g1-yield-default",
      "        yield_content_min: float,",
      "        yield_content_min: float = 0.5,",
      "test_classifier_requires_every_band_no_default[yield_content_min]"),
    m("g1-dark-default",
      "        ink_dark_min: float,",
      "        ink_dark_min: float = 0.6,",
      "test_classifier_requires_every_band_no_default[ink_dark_min]"),
    m("g1-margin-default",
      "        confidence_margin: float,",
      "        confidence_margin: float = 0.05,",
      "test_classifier_requires_every_band_no_default[confidence_margin]"),
    # --- version pin ----------------------------------------------------------------------------
    m("version-drift",
      'SEGMENTATION_VERSION = "density-bands-v1"',
      'SEGMENTATION_VERSION = "density-bands-v2"',
      "test_version_and_params_are_pinned_for_the_sidecar_fingerprint"),
]
