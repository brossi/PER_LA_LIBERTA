"""Mutant table for the S2.1.5 (#39) column / reading-order detector + cross-page prior.

Run with the mutation-hunt runner:

    python3 ~/.claude/skills/mutation-hunt/hunt.py \
        --table tests/hunts/hunt_columns.py --artifact <scratch>/hunt39.json

Covers DT-7 (the projection-profile gutter detection: G-10's >= 3-bin + populated-halves + center
guards, the min-box floor, the valley-depth x column-balance score), the ColumnDetector decision
threshold + hysteresis margin (incl. both boundary comparators), reading_order's column split
(the G-16 mechanism, one mutant scoped to the real-OCR e2e to prove its teeth), ordered_coverage,
the cross-page prior R8 clauses (G-23 own-evidence-wins, chain resets on non-content/routed pages,
disagreeing-neighbors abstain, the single-neighbor inherit path), the DT-5 from_config wiring, and
the new record guards. TEST_CMD uses the engine venv python; the runner pins pyc hygiene.

Known EQUIVALENT mutants (deliberately not listed — unkillable by construction, not survivors):
the ``else``-branch ``prior = None`` reset (line ~708) and the "inherited page does not update
``prior``" choice are non-observable: an in-margin page can only abstain-via-disagreement when it
HAS a confident next neighbor, which then re-anchors the prior for the following page, and an
inherited value always equals an existing confident neighbor's value — so propagating it (or not),
and resetting on an abstain (or not), produce byte-identical output on every reachable sequence.
"""
from pathlib import Path

REPO = str(Path(__file__).resolve().parents[2])
TEST_CMD = [str(Path(REPO) / ".venv" / "bin" / "python"), "-m", "pytest", "{scope}",
            "-q", "--no-header", "-x", "-p", "no:cacheprovider"]
TIMEOUT = 300

S = "src/engine/structure/segmentation.py"
T = "tests/unit/test_segmentation.py"
E = "tests/unit/test_geometry_e2e.py"


def m(label, old, new, test_id, *, file=S, test_file=T):
    return {"label": label, "file": file, "old": old, "new": new, "scope": f"{test_file}::{test_id}"}


MUTANTS = [
    # --- detect_columns: the four single-column rejections + the score factors -------------------
    m("minbox-floor-removed",
      "    if len(boxes) < _COLUMN_MIN_BOXES:",
      "    if len(boxes) < 0:",
      "test_too_few_boxes_is_single_column"),
    m("g10-min-gutter-bins-relaxed",
      "            if run >= _MIN_GUTTER_BINS:",
      "            if run >= 1:",
      "test_sparse_single_column_is_not_two_column_g10"),
    m("center-guard-removed",
      "        if not (center_lo * width <= split <= center_hi * width):  # gutter must sit near page center",
      "        if not (0.0 <= split <= width):  # gutter must sit near page center",
      "test_gutter_must_sit_near_center_not_at_the_margin"),
    m("populated-halves-guard-removed",
      "        if not (halves_lo <= left_fraction <= halves_hi):  # both columns genuinely populated (G-10)",
      "        if not (0.0 <= left_fraction <= 1.0):  # both columns genuinely populated (G-10)",
      "test_lopsided_beyond_the_populated_halves_band_is_single_column"),
    m("valley-depth-dropped",
      "        valley_depth = 1.0 - gutter_mean / peak",
      "        valley_depth = 1.0",
      "test_valley_depth_lowers_score_for_a_partially_filled_gutter"),
    m("column-balance-dropped",
      "        column_balance = min(left_fraction, right_fraction) / max(left_fraction, right_fraction)",
      "        column_balance = 1.0",
      "test_unbalanced_halves_lower_the_score_via_column_balance"),
    m("all-runs-shadowing-regression",
      "    for start, length in runs:",
      "    for start, length in runs[:1]:",
      "test_centered_gutter_element_does_not_shadow_a_valid_gutter"),
    m("width-guard-relaxed",
      "    if not (math.isfinite(width) and width > 0.0):",
      "    if not (math.isfinite(width) and width > -1.0):",
      "test_detect_columns_rejects_nonpositive_width"),
    # --- ColumnDetector: decision threshold + hysteresis (incl. boundary comparators) ------------
    m("threshold-comparator-strict",
      "        n_cols = 2 if score >= self._decision_threshold else 1",
      "        n_cols = 2 if score > self._decision_threshold else 1",
      "test_decision_threshold_boundary_is_inclusive_for_two_columns"),
    m("confidence-not-absolute",
      "        confidence = abs(score - self._decision_threshold)",
      "        confidence = score - self._decision_threshold",
      "test_confident_single_column_verdict"),
    m("hysteresis-comparator-strict",
      "        confident = confidence >= self._hysteresis_margin",
      "        confident = confidence > self._hysteresis_margin",
      "test_hysteresis_margin_boundary_is_inclusive"),
    m("hysteresis-always-confident",
      "        confident = confidence >= self._hysteresis_margin",
      "        confident = True",
      "test_score_inside_the_hysteresis_margin_is_not_confident"),
    m("ctor-threshold-guard-relaxed",
      "        if not (math.isfinite(decision_threshold) and 0.0 < decision_threshold < 1.0):",
      "        if not (math.isfinite(decision_threshold) and 0.0 <= decision_threshold <= 1.0):",
      "test_column_detector_rejects_incoherent_params"),
    m("ctor-hysteresis-guard-relaxed",
      "        if not (math.isfinite(hysteresis_margin) and 0.0 < hysteresis_margin <= 1.0):",
      "        if not (math.isfinite(hysteresis_margin) and 0.0 <= hysteresis_margin <= 1.0):",
      "test_column_detector_rejects_incoherent_params"),
    # --- reading_order: the column split (left column first) + single/two-column branch ----------
    m("reading-order-right-column-first",
      "        ordered = [*left, *right]",
      "        ordered = [*right, *left]",
      "test_reading_order_two_columns_reads_left_column_then_right"),
    m("reading-order-single-two-branch-flip",
      "    if split_x is None:",
      "    if split_x is not None:",
      "test_reading_order_single_column_sorts_by_line_then_x"),
    # G-16: break the column split at the OCR e2e -> columns interleave -> ordered_coverage < 1.0.
    m("g16-split-broken-at-e2e",
      "        left = sorted((box for box in boxes if _box_x_center(box) < split_x), key=_key)",
      "        left = sorted((box for box in boxes if _box_x_center(box) < 0.0), key=_key)",
      "test_no_witness_branch_recovers_reading_order_end_to_end", test_file=E),
    # --- ordered_coverage --------------------------------------------------------------------------
    m("ordered-coverage-empty-not-guarded",
      "    if not expected:",
      "    if False:",
      "test_ordered_coverage_empty_expected_is_zero_not_vacuous_one"),
    m("ordered-coverage-ignores-order",
      "    matched = sum(block.size for block in matcher.get_matching_blocks())",
      "    matched = len(expected)",
      "test_ordered_coverage_out_of_order_is_partial"),
    # --- cross-page prior (R8) ---------------------------------------------------------------------
    m("g23-confident-guard-dropped",
      "        elif confident:",
      "        elif False:",
      "test_strong_single_column_between_two_two_columns_keeps_its_own_evidence_g23"),
    m("prior-neighbor-agreement-dropped",
      "            if neighbors and all(c == neighbors[0] for c in neighbors):",
      "            if neighbors:",
      "test_in_margin_page_between_disagreeing_neighbors_abstains"),
    m("prior-empty-neighbors-guard-dropped",
      "            if neighbors and all(c == neighbors[0] for c in neighbors):",
      "            if all(c == neighbors[0] for c in neighbors):",
      "test_isolated_in_margin_page_abstains"),
    m("confident-page-does-not-set-prior",
      "            prior = lean",
      "            prior = None",
      "test_in_margin_page_with_a_single_agreeing_neighbor_inherits"),
    m("next-neighbor-ignores-confident",
      "    return lean if (kind == _CONTENT and confident) else None",
      "    return lean if (kind == _CONTENT) else None",
      "test_in_margin_page_with_a_single_agreeing_neighbor_inherits"),
    m("routed-density-branch-skipped",
      "        if page.density.routed:",
      "        if False:",
      "test_routed_density_page_resets_the_prior_chain_and_routes"),
    m("untrusted-branch-inverted",
      "        elif not page.density.boxes_trusted:",
      "        elif page.density.boxes_trusted:",
      "test_untrusted_page_carries_no_column_verdict"),
    # clause 1 chain-reset: non-unique `prior = None`, so anchor on the preceding append line.
    m("routed-page-does-not-reset-chain",
      '            verdicts.append(PageColumnVerdict(None, None, routed=True, signal="density-routed"))\n'
      "            prior = None",
      '            verdicts.append(PageColumnVerdict(None, None, routed=True, signal="density-routed"))\n'
      "            prior = prior",
      "test_routed_density_page_resets_the_prior_chain_and_routes"),
    m("untrusted-page-does-not-reset-chain",
      '            verdicts.append(PageColumnVerdict(None, None, routed=False, signal="boxes-untrusted"))\n'
      "            prior = None",
      '            verdicts.append(PageColumnVerdict(None, None, routed=False, signal="boxes-untrusted"))\n'
      "            prior = prior",
      "test_untrusted_page_resets_the_prior_chain"),
    # --- DT-5 wiring: from_config field mapping (in the config-loader suite) ----------------------
    m("from-config-field-swapped",
      "            ink_blank_max=bands.ink_blank_max,",
      "            ink_blank_max=bands.ink_dark_min,",
      "test_density_classifier_constructs_from_config",
      test_file="tests/unit/test_config_loader.py"),
    # --- new record guards -------------------------------------------------------------------------
    m("column-evidence-score-guard-dropped",
      "        if not (math.isfinite(self.col2_score) and 0.0 <= self.col2_score <= 1.0):",
      "        if not (math.isfinite(self.col2_score) and 0.0 <= self.col2_score <= 2.0):",
      "test_column_evidence_rejects_out_of_range_score"),
    m("column-verdict-ncols-guard-dropped",
      "        if self.n_cols not in (1, 2):",
      "        if self.n_cols not in (1, 2, 3):",
      "test_column_verdict_rejects_bad_n_cols"),
    m("page-column-verdict-source-guard-dropped",
      '        if self.n_cols_source not in (None, "evidence", "prior"):',
      '        if self.n_cols_source not in (None, "evidence", "prior", "banana"):',
      "test_page_column_verdict_rejects_bad_source_and_count"),
]
