"""Mutant table for the S2.1.6 (#40) human-review worklist + verdict CLI + volume bound + the
schema-v2 detector fields + the DT-7 auto-propose.

Run with the mutation-hunt runner:

    python3 ~/.claude/skills/mutation-hunt/hunt.py \
        --table tests/hunts/hunt_review.py --artifact <scratch>/hunt40.json

Covers G-13 (per-stage volume bound hard-fail + inclusive boundary), G-14 (verdict_outcome
totality + unknown-action fail-loud + provenance), G-22 (apply_verdicts idempotent projection +
stale-fingerprint refuse-and-retain + orphan reporting), the worklist candidate/id/fingerprint
guards, the schema-v2 page-record detector fields (domains + matched-only + count↔source
coherence) and ``with_detector_fields``, and ``propose_column_policy``'s valley/abstain branches.
TEST_CMD uses the engine venv python; the runner pins pyc hygiene.
"""
from pathlib import Path

REPO = str(Path(__file__).resolve().parents[2])
TEST_CMD = [str(Path(REPO) / ".venv" / "bin" / "python"), "-m", "pytest", "{scope}",
            "-q", "--no-header", "-x", "-p", "no:cacheprovider"]
TIMEOUT = 300

R = "src/engine/structure/geom_review.py"
S = "src/engine/structure/geom_sidecar.py"
C = "src/engine/structure/column_calibration.py"
GM = "src/engine/structure/geom_match.py"
TR = "tests/unit/test_geom_review.py"
TS = "tests/unit/test_geom_sidecar.py"
TC = "tests/unit/test_column_calibration.py"
TGM = "tests/unit/test_geom_match.py"


def m(label, old, new, test_id, *, file=R, test_file=TR):
    return {"label": label, "file": file, "old": old, "new": new, "scope": f"{test_file}::{test_id}"}


MUTANTS = [
    # --- G-13: per-stage volume bound ------------------------------------------------------------
    m("volume-bound-comparator-strict",
      "        if fraction > review_fraction_max:",
      "        if fraction >= review_fraction_max:",
      "test_volume_bound_boundary_is_inclusive"),
    m("volume-bound-check-dropped",
      "        if fraction > review_fraction_max:",
      "        if False:",
      "test_volume_bound_is_per_stage_not_aggregate"),
    m("volume-bound-aggregate-not-per-stage",
      "        fraction = fractions[stage]",
      "        fraction = sum(fractions.values()) / len(fractions)",
      "test_volume_bound_is_per_stage_not_aggregate"),
    m("review-fraction-default-drifted",
      "REVIEW_FRACTION_MAX_DEFAULT = 0.15",
      "REVIEW_FRACTION_MAX_DEFAULT = 0.20",
      "test_review_fraction_max_default_is_the_ruled_p6_value"),
    # --- worklist candidate id + fingerprint -----------------------------------------------------
    m("candidate-id-page-mismatch-unchecked",
      "        if not match or int(match[\"page\"]) != self.page or match[\"stage\"] != self.stage:",
      "        if not match or match[\"stage\"] != self.stage:",
      "test_worklist_candidate_id_must_match_its_page_and_stage"),
    m("fingerprint-ignores-engine-id",
      "        \"engine_id\": engine_id,",
      "        \"engine_id\": \"\",",
      "test_input_fingerprint_changes_when_any_binding_input_changes"),
    m("build-worklist-order-not-deterministic",
      "    ordered = sorted(routes, key=lambda r: (r.page, WORKLIST_STAGES.index(r.stage)))",
      "    ordered = list(routes)",
      "test_build_worklist_is_deterministic_in_page_then_stage_order"),
    m("build-worklist-duplicate-page-stage-unguarded",
      "        if key in seen:",
      "        if False:",
      "test_build_worklist_rejects_duplicate_page_stage_routes"),
    # --- G-14: verdict_outcome totality ----------------------------------------------------------
    m("verdict-unknown-action-silently-confirmed",
      "    raise GeometryError(\n"
      "        f\"unknown verdict action {action!r} — must be one of {VERDICT_ACTIONS}; refusing to guess \"\n"
      "        f\"which gate outcome to apply (G-14)\"\n"
      "    )",
      "    return OUTCOME_REENTERED",
      "test_verdict_outcome_unknown_action_fails_loud"),
    m("verdict-decline-misrouted-to-reenter",
      "    if action == ACTION_DECLINE_GEOMETRY:\n        return OUTCOME_DECLINED",
      "    if action == ACTION_DECLINE_GEOMETRY:\n        return OUTCOME_REENTERED",
      "test_verdict_outcome_maps_decline_to_declined"),
    m("validate-verdict-skips-provenance",
      "        if not (isinstance(value, str) and value.strip()):\n"
      "            raise GeometryError(f\"verdict missing provenance: {name!r} must be a non-empty string, got {value!r}\")",
      "        if False:\n"
      "            raise GeometryError(f\"verdict missing provenance: {name!r} must be a non-empty string, got {value!r}\")",
      "test_validate_verdict_requires_provenance"),
    # --- G-22: apply_verdicts projection / idempotency / stale -----------------------------------
    m("apply-verdicts-not-projected-from-base",
      "        base = replace(candidate, verdict=None, history=())  # project from base → idempotent",
      "        base = candidate",
      "test_apply_verdicts_removing_a_verdict_reopens_the_candidate"),
    m("apply-verdicts-stale-not-detected",
      "        if found.get(\"input_fingerprint\") != candidate.input_fingerprint:",
      "        if False:",
      "test_apply_verdicts_stale_fingerprint_is_refused_and_retained"),
    m("apply-verdicts-stale-not-retained",
      "            new_candidates.append(replace(base, verdict=None, history=(dict(found),)))",
      "            new_candidates.append(replace(base, verdict=None, history=()))",
      "test_apply_verdicts_stale_fingerprint_is_refused_and_retained"),
    m("apply-verdicts-orphan-not-reported",
      "        if vid not in ids:\n            stats[\"orphaned\"] += 1",
      "        if vid not in ids:\n            stats[\"orphaned\"] += 0",
      "test_apply_verdicts_ignores_verdicts_for_absent_candidates"),
    # --- G-14 concrete: decline → declined page --------------------------------------------------
    m("apply-declines-wrong-status",
      "        new_pages[page] = PageRecord(status=PAGE_DECLINED, verdict=verdict)",
      "        new_pages[page] = PageRecord(status=PAGE_MATCHED, match_rate=1.0)",
      "test_apply_declines_to_sidecar_declines_the_routed_page"),
    m("apply-declines-includes-reentry",
      "        if c.verdict is not None and c.verdict.get(\"action\") == ACTION_DECLINE_GEOMETRY",
      "        if c.verdict is not None",
      "test_apply_declines_leaves_non_decline_pages_routed"),
    # --- overlays --------------------------------------------------------------------------------
    m("overlay-dims-guard-relaxed",
      "    if not (math.isfinite(width) and width > 0.0 and math.isfinite(height) and height > 0.0):",
      "    if not (math.isfinite(width) and width > -1.0 and math.isfinite(height) and height > 0.0):",
      "test_render_overlay_rejects_nonpositive_dimensions"),
    # --- page_order_qa ---------------------------------------------------------------------------
    m("order-qa-ignores-split",
      "    ordered_texts = reading_order(boxes, split_x=split_x)",
      "    ordered_texts = reading_order(boxes, split_x=None)",
      "test_page_order_qa_is_one_when_detector_order_matches_the_witness",
      test_file=TR),
    # --- schema v2: detector-field domains (geom_sidecar) ----------------------------------------
    m("n-cols-domain-unchecked",
      "        if self.n_cols is not None and not (_is_int(self.n_cols) and self.n_cols in (1, 2)):",
      "        if self.n_cols is not None and not (_is_int(self.n_cols) and self.n_cols in (1, 2, 3)):",
      "test_detector_field_domains_are_enforced", file=S, test_file=TS),
    m("n-cols-source-coherence-dropped",
      "        if (self.n_cols is None) != (self.n_cols_source is None):",
      "        if False:",
      "test_detector_field_domains_are_enforced", file=S, test_file=TS),
    m("order-qa-range-unchecked",
      "        if self.order_qa is not None and not _is_rate(self.order_qa):",
      "        if self.order_qa is not None and not (self.order_qa <= 2.0):",
      "test_detector_field_domains_are_enforced", file=S, test_file=TS),
    m("detector-fields-matched-only-dropped",
      "        if self.status != PAGE_MATCHED and (",
      "        if False and (",
      "test_detector_fields_forbidden_on_non_matched_pages", file=S, test_file=TS),
    m("with-detector-fields-attaches-to-non-matched",
      "        if record is None or record.status != PAGE_MATCHED:",
      "        if record is None:",
      "test_with_detector_fields_rejects_a_non_matched_page", file=S, test_file=TS),
    m("with-detector-fields-unknown-key-unguarded",
      "        if unknown:",
      "        if False:",
      "test_with_detector_fields_rejects_unknown_field_keys", file=S, test_file=TS),
    # --- DT-7 auto-propose (column_calibration) --------------------------------------------------
    m("propose-no-valley-still-proposes",
      "    if best_start is None or best_len < min_valley_bins:",
      "    if False:",
      "test_clusters_too_close_to_separate_abstains", file=C, test_file=TC),
    m("propose-ignores-cluster-mass-floor",
      "    if low_mass < floor or high_mass < floor:",
      "    if False:",
      "test_a_spurious_tiny_second_cluster_abstains", file=C, test_file=TC),
    m("propose-unimodal-not-caught",
      "    if len(populated) < 2 or populated[0] == populated[-1]:",
      "    if False:",
      "test_unimodal_low_distribution_abstains", file=C, test_file=TC),
    m("propose-out-of-range-unchecked",
      "            raise ValueError(f\"col2_score must be a finite number in [0, 1], got {s!r}\")",
      "            pass",
      "test_out_of_range_score_is_rejected", file=C, test_file=TC),
    m("propose-anchors-on-valley-not-dense-edge",
      "    high_bottom = _run_bottom(counts, populated[-1], n_bins)  # lower edge of the dense two-column cluster",
      "    high_bottom = valley_hi",
      "test_asymmetric_gap_anchors_the_threshold_above_the_transition_band", file=C, test_file=TC),
    # --- #46: review-sheet greens (denominator / totality / command-binding / plausible verbs) ---
    m("denominator-rule-dropped",
      "    if not (_is_int(total) and total >= 0):",
      "    if False:",
      "test_review_sheet_match_entry_without_denominator_fails_loud"),
    m("denominator-rule-rejects-honest-zero",
      "    if not (_is_int(total) and total >= 0):",
      "    if not (_is_int(total) and total > 0):",
      "test_review_sheet_zero_token_match_page_renders_not_aborts"),
    m("missing-overlay-not-fatal",
      "        if (c.page, c.stage) not in available_overlays:",
      "        if False:",
      "test_review_sheet_missing_overlay_fails_loud"),
    m("overlay-path-stage-domain-unchecked",
      "    if stage not in WORKLIST_STAGES:\n"
      "        raise ValueError(f\"overlay stage must be one of {WORKLIST_STAGES}, got {stage!r}\")",
      "    if False:\n"
      "        raise ValueError(f\"overlay stage must be one of {WORKLIST_STAGES}, got {stage!r}\")",
      "test_overlay_path_rejects_an_unknown_stage"),
    m("walk-redraw-split-param-not-captured",
      "        if answer == ACTION_REDRAW_SPLIT:",
      "        if False:",
      "test_next_walk_redraw_split_captures_the_split_x_param"),
    m("command-binding-unknown-verb-emittable",
      "    if action not in VERDICT_ACTIONS:",
      "    if False:",
      "test_prefilled_command_rejects_an_unknown_action"),
    m("redraw-split-offered-everywhere",
      "    \"columns\": (ACTION_CONFIRM, ACTION_REDRAW_SPLIT, ACTION_RECLASSIFY, ACTION_DECLINE_GEOMETRY),",
      "    \"columns\": (ACTION_CONFIRM, ACTION_RECLASSIFY, ACTION_DECLINE_GEOMETRY),",
      "test_redraw_split_is_offered_only_where_there_is_a_split_to_redraw"),
    # --- #46: matcher review evidence (Part A) ---------------------------------------------------
    m("unmatched-tokens-not-collected",
      "                    page_unmatched.append(t)  # #46: no available box token → a disagreement chip",
      "                    pass",
      "test_match_routed_page_carries_review_evidence_denominator_and_unmatched_tokens",
      file=GM, test_file=TGM),
    m("match-evidence-matched-total-swapped",
      "                matched=matched_sum, total=total_sum, unmatched_tokens=tuple(page_unmatched)",
      "                matched=total_sum, total=matched_sum, unmatched_tokens=tuple(page_unmatched)",
      "test_match_routed_page_carries_review_evidence_denominator_and_unmatched_tokens",
      file=GM, test_file=TGM),
]
