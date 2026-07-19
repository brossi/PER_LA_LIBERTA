"""Mutant table for S5.1 (#47) and S4.7/#48 rebind invariants.

Each mutant is a single-line perturbation of production code that must red exactly one named test —
the mechanical form of `feedback_red_first_tests` (a test never seen red is a claim, not a check).
Run with the mutation-hunt runner (it pins pyc hygiene — `feedback_mutation_pyc_staleness`):

    python3 ~/.claude/skills/mutation-hunt/hunt.py \
        --table tests/hunts/hunt_rebind.py --artifact <scratch>/hunt_rebind.json

Covers every §4 invariant: the fingerprint producer + similarity (empty→None, short-slot fallback,
empty-window→0, fuzzy-not-substring), mode resolution (unknown fails loud, None→fallback), the policy
default-ordering, the assignment's per-node reasons (missing-anchor / below-threshold / ambiguous /
no-rescue / zero-candidate via the mode pin), the baseline gate, the global-consistency gate, the
bottom-up re-stamp gate, the stale-decision producer, and the Phase-A/B surface the mechanism rides
(v2 born gate, the Region page floor, the typed-anchor load path).

S4.7 item 2 extends the same table with the independent INV-1 oracle's pairwise/global guards,
the representation-agnostic positional-confirmation hook, and the fixed anchor-footprint contract.
"""

from pathlib import Path

REPO = str(Path(__file__).resolve().parents[2])
TEST_CMD = [
    str(Path(REPO) / ".venv" / "bin" / "python"),
    "-m",
    "pytest",
    "{scope}",
    "-q",
    "--no-header",
    "-x",
    "-p",
    "no:cacheprovider",
]
TIMEOUT = 300

R = "src/engine/structure/rebind.py"
SM = "src/engine/structure/structure_map.py"
PROJ = "src/engine/structure/projection.py"
ART = "src/engine/structure/artifacts.py"
TR = "tests/unit/test_rebind.py"
TSM = "tests/unit/test_structure_map.py"
TBG = "tests/unit/test_structure_born_gate.py"
ORACLE = "tests/harness/oracle.py"
ANCHOR = "src/engine/structure/boundary_anchor.py"
TS47 = "tests/unit/test_s4_7_inv1_inv2.py"
BOUNDARY = "tests/harness/boundary.py"
INV35 = "tests/harness/invariants_3_5.py"
TS35 = "tests/unit/test_s4_7_inv3_inv5.py"
SCALE = "tests/harness/scale.py"
TS67 = "tests/unit/test_s4_7_inv6_inv7.py"
REANCHOR = "src/engine/structure/reanchor.py"
TSRA = "tests/unit/test_s4_7_reanchor.py"
SCHEMA = "src/engine/structure/schema/structure_map.schema.json"
SPROD = "tests/harness/scale_production.py"
TSPROD = "tests/unit/test_s4_7_scale_production.py"
RELATION = "tests/harness/relation.py"
TRELATION = "tests/unit/test_harness_relation_laws.py"
MATERIALIZE = "tests/harness/materialize.py"
TMATERIALIZE = "tests/unit/test_harness_materialize.py"
PYPROJECT = "pyproject.toml"
CI_WORKFLOW = ".github/workflows/ci.yml"
HANDLES = "src/engine/structure/handles.py"
THANDLES = "tests/unit/test_structure_handles.py"
REBIN_TELEMETRY = "src/engine/structure/rebind_telemetry.py"
MUTATION_TOOL = "tools/s4_7_hunt_manifest.py"
TMUTATION = "tests/unit/test_s4_7_mutation_progress.py"
EVIDENCE = "src/engine/structure/evidence.py"
TEVIDENCE = "tests/unit/test_authoring_evidence.py"


def m(label, old, new, test_id, *, file=R, test_file=TR):
    return {
        "label": label,
        "file": file,
        "old": old,
        "new": new,
        "scope": f"{test_file}::{test_id}",
    }


MUTANTS = [
    # --- fingerprint producer + similarity (§2.2) ---------------------------------------------------
    m(
        "empty-slot-returns-empty-shingle-fingerprint",
        "    if not toks:\n        return None",
        "    if not toks:\n        return SlotFingerprint(algo_id=FINGERPRINT_ALGO_ID, "
        "normalizer_id=FINGERPRINT_NORMALIZER_ID, k=1, token_count=0, shingles=())",
        "test_fingerprint_slot_empty_is_none_never_empty_set",
    ),
    m(
        "short-slot-no-k-fallback",
        "    k_eff = min(k, len(toks)) if k >= 1 else 1",
        "    k_eff = k",
        "test_fingerprint_slot_short_slot_falls_back_to_available_k",
    ),
    m(
        "empty-window-scores-one-not-zero",
        "        score=intersection_size / union_size if union_size else 0.0,\n",
        "        score=(\n"
        "            1.0\n"
        "            if fresh is None\n"
        "            else intersection_size / union_size if union_size else 0.0\n"
        "        ),\n",
        "test_slot_similarity_empty_window_scores_zero",
    ),
    m(
        "jaccard-collapses-to-all-or-nothing-substring",
        "        score=intersection_size / union_size if union_size else 0.0,",
        "        score=1.0 if intersection_size else 0.0,",
        "test_slot_similarity_identity_disjoint_and_fuzzy",
    ),
    # --- mode resolution (§1.2) ---------------------------------------------------------------------
    m(
        "unknown-mode-defaults-instead-of-failing-loud",
        "    if geometry_mode in GEOMETRY_MODES:",
        "    if True:",
        "test_resolve_mode_unknown_fails_loud",
    ),
    m(
        "none-mode-reported-as-manifest-not-fallback",
        '        return (MODE_TIE_BREAK, FALLBACK_REPORTED_MODE, "fallback")',
        '        return (MODE_TIE_BREAK, MODE_TIE_BREAK, "manifest")',
        "test_resolve_mode_none_is_conditional_primary_fallback",
    ),
    # --- policy default-ordering (§4, D-4) ----------------------------------------------------------
    m(
        "policy-ordering-guard-dropped",
        "        if not (self.tau_no_geometry >= self.tau_tie_break >= self.tau_primary):",
        "        if False:",
        "test_policy_inverted_ordering_is_rejected_at_construction",
    ),
    m(
        "policy-default-primary-margin-inverted",
        "    tau_primary: float = DEFAULT_FINGERPRINT_THRESHOLD - _DEFAULT_MODE_MARGIN",
        "    tau_primary: float = DEFAULT_FINGERPRINT_THRESHOLD + _DEFAULT_MODE_MARGIN",
        "test_policy_default_ordering_holds_on_the_named_default",
    ),
    # --- baseline binding (§1.4) --------------------------------------------------------------------
    m(
        "baseline-content-hash-gate-dropped",
        '        if live_content != manifest.get("canonical_content_hash"):',
        "        if False:",
        "test_rebind_context_refuses_a_content_hash_mismatch",
    ),
    # --- per-node reasons: missing-anchor / below-threshold / ambiguous / no-rescue -----------------
    m(
        "fingerprint-less-slot-binds-instead-of-missing-anchor",
        "        if slot.fingerprint is None or slot.boundary_anchors is None:\n",
        "        if False:\n",
        "test_missing_anchor_node_never_binds_on_geometry_alone",
    ),
    m(
        "below-threshold-binds-any-score",
        "        if fingerprint_metrics.score < self.tau:\n",
        "        if False:\n",
        "test_no_rescue_geometry_does_not_lift_a_subtau_fingerprint",
    ),
    m(
        "no-rescue-geometry-lifts-subtau-over-tau",
        "        if fingerprint_metrics.score < self.tau:\n",
        "        if fingerprint_metrics.score < self.tau and slot.region is None:\n",
        "test_no_rescue_geometry_does_not_lift_a_subtau_fingerprint",
    ),
    m(
        "ambiguous-picks-first-candidate",
        "                    best_scores[query] = 1.0\n"
        "                    best_boundaries[query].add(boundary)\n",
        "                    best_scores[query] = 1.0\n"
        "                    if not best_boundaries[query]:\n"
        "                        best_boundaries[query].add(boundary)\n",
        "test_batch_anchor_locator_resolves_exact_ties_without_fuzzy_signatures",
        file=REANCHOR,
        test_file=TSRA,
    ),
    # --- mode gating: the primary hard pin (§1.2) ---------------------------------------------------
    m(
        "primary-pin-ignores-mode",
        "        if self.dp_mode == MODE_PRIMARY and slot.region is not None:",
        "        if False and slot.region is not None:",
        "test_primary_mode_pin_checks_every_atom_not_only_boundary_pages",
    ),
    # --- global consistency (§1.3) ------------------------------------------------------------------
    m(
        "global-validate-gate-disabled",
        "        map_valid = not all_bound or _map_validates(migrated_projection, context)",
        "        map_valid = True",
        "test_empty_container_makes_the_rebound_map_fail_global_validation",
    ),
    # bound-SUBSET disjointness must run on EVERY re-bind, not only all-bound (the audit-found partial
    # silent double-bind): neutering the contested-atom witness lets two bound nodes share a fresh atom.
    m(
        "bound-subset-disjointness-disabled",
        "    return {nid for owners in claims.values() if len(owners) > 1 for nid in owners}",
        "    return set()",
        "test_bound_subset_disjointness_backstop_names_both_contested_nodes",
    ),
    # --- S4.7 item-2 INV-1 oracle + DR-4 interface -------------------------------------------------
    # Baseline for the first scope is a strict carried xfail. Disabling the pairwise guard makes the
    # current shipped false bind pass, which becomes XPASS(strict) and therefore kills the mutant.
    m(
        "s4-7-inv1-oracle-pairwise-disabled",
        "    if unexpected:\n",
        "    if False and unexpected:\n",
        "test_oracle_rejects_the_shipped_duplicate_wrong_copy_shape",
        file=ORACLE,
        test_file=TS47,
    ),
    m(
        "s4-7-repeated-passage-uniqueness-guard-disabled",
        "        and old_counts[old_token] == 1\n        and fresh_counts[fresh_token] == 1\n",
        "        and True\n",
        "test_anchor_poor_oracle_itself_admits_no_content_only_bind",
        file=ORACLE,
        test_file=TS47,
    ),
    m(
        "s4-7-inv1-oracle-global-disjointness-disabled",
        "    if contested:\n",
        "    if False and contested:\n",
        "test_oracle_global_conjunct_rejects_two_pairwise_allowed_claims_of_one_atom",
        file=ORACLE,
        test_file=TS47,
    ),
    m(
        "s4-7-inv1-duplicate-slot-outcome-guard-disabled",
        "    if len(observed_slots) != len(set(observed_slots)):\n",
        "    if False:\n",
        "test_oracle_rejects_duplicate_outcome_records_for_one_slot",
        file=ORACLE,
        test_file=TS47,
    ),
    m(
        "s4-7-positional-confirmation-accepts-maps-far",
        "            and self.located_fresh_boundary == self.projected_fresh_boundary\n",
        "            and self.located_fresh_boundary is not None\n",
        "test_unique_anchor_that_maps_far_is_not_confirmed",
        file=ANCHOR,
        test_file=TS47,
    ),
    m(
        "s4-7-anchor-footprint-widened-without-lock-rerun",
        "BOUNDARY_ANCHOR_FOOTPRINT_W = 24\n",
        "BOUNDARY_ANCHOR_FOOTPRINT_W = 240\n",
        "test_anchor_interface_is_content_only_bounded_and_has_separate_confidence_hook",
        file=ANCHOR,
        test_file=TS47,
    ),
    m(
        "s4-7-anchor-determinism-contract-disabled",
        "    if first != second:\n",
        "    if False:\n",
        "test_anchor_interface_wrapper_enforces_determinism_and_content_contiguity",
        file=ANCHOR,
        test_file=TS47,
    ),
    m(
        "s4-7-anchor-content-only-contract-disabled",
        "    if not matches_boundary:\n",
        "    if False:\n",
        "test_anchor_interface_wrapper_enforces_determinism_and_content_contiguity",
        file=ANCHOR,
        test_file=TS47,
    ),
    m(
        "s4-7-seam-insert-silent-drop-guard-disabled",
        "        if legal_slots and legal_slots.isdisjoint(observed.unresolved_slots):\n",
        "        if False:\n",
        "test_shared_seam_insert_cannot_be_silently_dropped_when_both_owners_bind",
        file=ORACLE,
        test_file=TS47,
    ),
    # --- S4.7 item-2 INV-3 / INV-4 / INV-5 --------------------------------------------------------
    m(
        "s4-7-inv3-planted-destination-guard-disabled",
        "        if observation.fresh_atom_ids not in planted:\n",
        "        if False:\n",
        "test_inv3_planted_greedy_wrong_span_is_rejected",
        file=INV35,
        test_file=TS35,
    ),
    m(
        "s4-7-inv3-duplicate-observation-guard-disabled",
        "    if len(by_slot) != len(observations):\n",
        "    if False:\n",
        "test_inv3_duplicate_observation_for_one_moved_slot_is_rejected",
        file=INV35,
        test_file=TS35,
    ),
    m(
        "s4-7-inv3-global-map-validity-guard-disabled",
        "        if not observation.map_globally_valid:\n",
        "        if False:\n",
        "test_inv3_destination_atom_bind_with_invalid_map_is_rejected",
        file=INV35,
        test_file=TS35,
    ),
    m(
        "s4-7-inv4-insert-precedence-disabled",
        '    if any(block.tag == "insert" and block.old_lo == boundary for block in blocks):\n',
        "    if False:\n",
        "test_inv4_analytic_half_open_boundary_classes[insert-at-gap]",
        file=BOUNDARY,
        test_file=TS35,
    ),
    m(
        "s4-7-inv4-strict-interior-class-disabled",
        "        and block.old_lo < boundary < block.old_hi\n",
        "        and False\n",
        "test_inv4_analytic_half_open_boundary_classes[replace-interior]",
        file=BOUNDARY,
        test_file=TS35,
    ),
    m(
        "s4-7-inv4-capped-gap-interior-class-disabled",
        "        and block.old_lo < boundary < block.old_hi\n",
        "        and False\n",
        "test_inv4_analytic_half_open_boundary_classes[capped-gap]",
        file=BOUNDARY,
        test_file=TS35,
    ),
    m(
        "s4-7-inv4-edge-class-disabled",
        '    if token_tag(boundary - 1) != "equal" or token_tag(boundary) != "equal":\n',
        "    if False:\n",
        "test_inv4_analytic_half_open_boundary_classes[replace-edge]",
        file=BOUNDARY,
        test_file=TS35,
    ),
    m(
        "s4-7-inv4-adjacent-non-equal-tiling-accepted",
        '        if left.tag != "equal" and right.tag != "equal":\n',
        "        if False:\n",
        "test_inv4_analytic_tiling_rejects_adjacent_non_equal_blocks",
        file=BOUNDARY,
        test_file=TS35,
    ),
    m(
        "s4-7-inv4-clean-class-corrupted",
        '    return "clean-candidate"\n',
        '    return "edge-candidate"\n',
        "test_inv4_analytic_half_open_boundary_classes[clean]",
        file=BOUNDARY,
        test_file=TS35,
    ),
    m(
        "s4-7-inv5-tie-break-branch-disabled",
        "        return on_page if len(boundaries) > 1 and on_page else boundaries\n",
        "        return boundaries\n",
        "test_inv5_distinct_page_repeated_content_may_bind_only_to_each_planted_copy",
        file=R,
        test_file=TS35,
    ),
    m(
        "s4-7-inv5-no-geometry-illegally-hard-pins-region",
        "        if self.dp_mode == MODE_PRIMARY and slot.region is not None:\n",
        "        if self.dp_mode in (MODE_PRIMARY, MODE_NO_GEOMETRY) and slot.region is not None:\n",
        "test_no_geometry_mode_ignores_the_region_and_binds_on_fingerprint",
    ),
    # --- S4.7 item-2 INV-6 / INV-7 ---------------------------------------------------------------
    m(
        "s4-7-inv6-slope-estimator-forced-linear",
        "    logs_y = tuple(math.log(value) for value in ys)\n",
        "    logs_y = logs_x\n",
        "test_growth_estimator_distinguishes_linear_from_quadratic_and_keeps_ratios",
        file=SCALE,
        test_file=TS67,
    ),
    m(
        "s4-7-inv6-adjacent-ratios-erased",
        "    return tuple(right / left for left, right in zip(values, values[1:]))\n",
        "    return tuple(1.0 for left, right in zip(values, values[1:]))\n",
        "test_growth_estimator_distinguishes_linear_from_quadratic_and_keeps_ratios",
        file=SCALE,
        test_file=TS67,
    ),
    m(
        "s4-7-perf-time-phase-completion-validation-dropped",
        "        validate(result)\n        samples.append(elapsed)\n",
        "        if False:\n            validate(result)\n        samples.append(elapsed)\n",
        "test_perf_measurement_validates_every_run_and_observes_python_allocations",
        file=SCALE,
        test_file=TS67,
    ),
    m(
        "s4-7-perf-tracemalloc-peak-forced-zero",
        "            _, peak = tracemalloc.get_traced_memory()\n",
        "            _, peak = (0, 0)\n",
        "test_perf_measurement_validates_every_run_and_observes_python_allocations",
        file=SCALE,
        test_file=TS67,
    ),
    m(
        "s4-7-inv6-growth-budget-guard-disabled",
        'def assert_growth_within_limits(summary: Mapping[str, object], *, metric: str) -> None:\n    slope = float(summary["slope"])\n',
        'def assert_growth_within_limits(summary: Mapping[str, object], *, metric: str) -> None:\n    return\n    slope = float(summary["slope"])\n',
        "test_growth_budget_rejects_an_excessive_slope_or_adjacent_ratio",
        file=SCALE,
        test_file=TS67,
    ),
    m(
        "s4-7-inv7-depth-shrunk-after-preregistration",
        "INV7_DEPTH = 3_000\n",
        "INV7_DEPTH = 300\n",
        "test_priority4_preregistered_constants_and_upward_only_ladder_are_pinned",
        file=SCALE,
        test_file=TS67,
    ),
    m(
        "s4-7-inv7-wall-ceiling-relaxed-after-measurement",
        "INV7_MAX_SECONDS = 2.0\n",
        "INV7_MAX_SECONDS = 20.0\n",
        "test_priority4_preregistered_constants_and_upward_only_ladder_are_pinned",
        file=SCALE,
        test_file=TS67,
    ),
    m(
        "s4-7-inv7-shared-extent-pass-disabled",
        "    extent_batch = _batch_extent_digests(extent_entries, projection)\n",
        "    extent_batch = None\n",
        "test_gate_batch_path_never_calls_the_per_entry_scalar_extent_walk",
        file=EVIDENCE,
        test_file=TEVIDENCE,
    ),
    m(
        "s4-7-inv7-fresh-witness-reuse-disabled",
        '        if entry.extent_payload["own"] == own and beneath == set(stored_beneath):\n',
        '        if False and entry.extent_payload["own"] == own and beneath == set(stored_beneath):\n',
        "test_gate_batch_extent_pass_visits_each_node_and_edge_once_and_reuses_fresh_witnesses",
        file=EVIDENCE,
        test_file=TEVIDENCE,
    ),
    m(
        "s4-7-perf-baseline-source-identity-check-disabled",
        "    if verify_source_identity:\n",
        "    if False:\n",
        "test_priority4_baseline_rejects_stale_source_identity",
        file=SCALE,
        test_file=TS67,
    ),
    # --- re-stamp protocol (§1.6) -------------------------------------------------------------------
    m(
        "restamp-ignores-the-bottom-up-subtree-gate",
        "        included_node_ids=bound_node_ids,\n",
        "        included_node_ids=set(migrated_projection.by_id),\n",
        "test_ancestor_not_restamped_while_a_descendant_is_unresolved",
    ),
    m(
        "restamp-restores-per-entry-subtree-walk",
        "        if live is None:\n"
        "            continue\n"
        "        restamped.append(\n",
        "        if live is None:\n"
        "            continue\n"
        "        if not _subtree_ids(entry.node_id, migrated_projection).issubset(\n"
        "            bound_node_ids\n"
        "        ):\n"
        "            continue\n"
        "        restamped.append(\n",
        "test_restamp_valid_path_never_restores_per_entry_walks_or_duplicate_payload_construction",
    ),
    {
        "label": "restamp-restores-duplicate-scalar-extent-construction",
        "scope": (
            f"{TR}::"
            "test_restamp_valid_path_never_restores_per_entry_walks_or_duplicate_payload_construction"
        ),
        "patches": (
            {
                "file": R,
                "old": "        restamped.append(\n"
                "            EvidenceEntry(\n"
                "                node_id=entry.node_id,\n"
                "                decision_digest=entry.decision_digest,  # carried, never machine-refreshed\n",
                "new": "        node = migrated_projection.by_id[entry.node_id]\n"
                "        restamped.append(\n"
                "            EvidenceEntry(\n"
                "                node_id=entry.node_id,\n"
                "                decision_digest=entry.decision_digest,  # carried, never machine-refreshed\n",
            },
            {
                "file": R,
                "old": "                extent_digest=live.digest,  # mechanically re-stamped from this exact payload\n",
                "new": "                extent_digest=extent_digest(node, migrated_projection),\n",
            },
            {
                "file": R,
                "old": "                extent_payload=live.payload,\n",
                "new": "                extent_payload=extent_payload(node, migrated_projection),\n",
            },
        ),
    },
    m(
        "restamp-telemetry-evidence-supplied-hard-coded-false",
        "            evidence_supplied=context.old_evidence is not None,\n",
        "            evidence_supplied=False,\n",
        "test_restamp_telemetry_distinguishes_absent_unqualified_and_restamped_evidence",
    ),
    m(
        "stale-decision-never-detected",
        "        and entry.decision_digest != decision_digest(node)",
        "        and False",
        "test_stale_decision_is_a_finding_not_a_restamp",
    ),
    m(
        "stale-decision-node-kept-bound",
        "        bound_node_ids -= stale_decisions",
        "        bound_node_ids -= set()",
        "test_stale_decision_is_a_finding_not_a_restamp",
    ),
    # --- Phase-A/B surface the mechanism rides ------------------------------------------------------
    m(
        "typed-anchor-dropped-on-load",
        '        rebind_anchors=_rebind_anchors_from_json(data.get("rebind_anchors")),',
        "        rebind_anchors=None,",
        "test_v3_map_exposes_typed_rebind_anchors_to_readers",
        file=SM,
        test_file=TSM,
    ),
    m(
        "region-page-floor-allows-zero",
        "        if isinstance(self.page, bool) or not isinstance(self.page, int) or self.page < 1:",
        "        if isinstance(self.page, bool) or not isinstance(self.page, int) or self.page < 0:",
        "test_region_model_rejects_a_page_below_one",
        file=PROJ,
    ),
    m(
        "v3-schema-not-born",
        "    3: SCHEMA_STATUS_BORN,\n",
        "    3: SCHEMA_STATUS_PROVISIONAL,\n",
        "test_v3_boundary_anchor_fixture_validates_and_v3_is_born",
        file=ART,
        test_file=TBG,
    ),
    # --- S4.7/#48 production alignment, projection, and v3 provenance ----------------------------
    m(
        "alignment-anchor-k-changed-without-lock-rerun",
        "ALIGNMENT_ANCHOR_K = 3\n",
        "ALIGNMENT_ANCHOR_K = 4\n",
        "test_alignment_contract_constants_and_backend_identity_are_pinned",
        file=REANCHOR,
        test_file=TSRA,
    ),
    m(
        "alignment-gap-cap-changed-without-lock-rerun",
        "ALIGNMENT_GAP_CAP = 512\n",
        "ALIGNMENT_GAP_CAP = 513\n",
        "test_alignment_contract_constants_and_backend_identity_are_pinned",
        file=REANCHOR,
        test_file=TSRA,
    ),
    m(
        "alignment-backend-variant-swapped-to-indel",
        "from rapidfuzz.distance import Levenshtein\n",
        "from rapidfuzz.distance import Indel as Levenshtein\n",
        "test_backend_variant_pins_replace_opcode_semantics",
        file=REANCHOR,
        test_file=TSRA,
    ),
    m(
        "alignment-gap-cap-guard-disabled",
        "    if max(old_hi - old_lo, fresh_hi - fresh_lo) > ALIGNMENT_GAP_CAP:\n",
        "    if max(old_hi - old_lo, fresh_hi - fresh_lo) > ALIGNMENT_GAP_CAP * 2:\n",
        "test_gap_above_fixed_cap_becomes_one_synthetic_unaligned_block",
        file=REANCHOR,
        test_file=TSRA,
    ),
    m(
        "batch-anchor-edit-budget-forced-exact-only",
        "                max(0, math.floor((1.0 - float(threshold)) * width + 1e-12)),\n",
        "                0,\n",
        "test_batch_anchor_locator_matches_bruteforce_under_bounded_random_edits",
        file=REANCHOR,
        test_file=TSRA,
    ),
    m(
        "batch-anchor-best-score-update-inverted",
        "                    if score > best_scores[query]:\n",
        "                    if score < best_scores[query]:\n",
        "test_batch_anchor_locator_falls_back_to_fuzzy_only_for_unresolved_queries",
        file=REANCHOR,
        test_file=TSRA,
    ),
    m(
        "batch-anchor-exact-results-also-build-fuzzy-signatures",
        "            unresolved = [query for query in group if not best_boundaries[query]]\n",
        "            unresolved = list(group)\n",
        "test_batch_anchor_locator_resolves_exact_ties_without_fuzzy_signatures",
        file=REANCHOR,
        test_file=TSRA,
    ),
    {
        "label": "production-rebind-reverts-to-per-slot-whole-stream-anchor-scans",
        "scope": (
            f"{TSPROD}::"
            "test_production_assignment_batches_anchor_windows_once_and_consumes_the_index"
        ),
        "patches": (
            {
                "file": R,
                "old": "    BoundaryAnchorBatchLocator,\n    align_token_streams,\n",
                "new": (
                    "    BoundaryAnchorBatchLocator,\n    align_token_streams,\n"
                    "    locate_boundary_anchor,\n"
                ),
            },
            {
                "file": R,
                "old": "        old_location = self.old_anchor_locations.locate(anchor, side=side)\n",
                "new": (
                    "        old_location = locate_boundary_anchor(\n"
                    "            anchor, self.old.tokens, side=side, threshold=self.tau\n"
                    "        )\n"
                ),
            },
            {
                "file": R,
                "old": "        fresh_location = self.fresh_anchor_locations.locate(anchor, side=side)\n",
                "new": (
                    "        fresh_location = locate_boundary_anchor(\n"
                    "            anchor, self.fresh.tokens, side=side, threshold=self.tau\n"
                    "        )\n"
                ),
            },
        ),
    },
    m(
        "alignment-lis-chain-disabled",
        "    return tuple(_lis_pairs(pairs))\n",
        "    return tuple(pairs)\n",
        "test_unique_anchor_chain_is_monotone_when_raw_landmarks_cross",
        file=REANCHOR,
        test_file=TSRA,
    ),
    m(
        "near-duplicate-precheck-forced-true",
        "    near_duplicate = length_ratio <= NEAR_DUPLICATE_MAX_LENGTH_RATIO and (\n",
        "    near_duplicate = True or length_ratio <= NEAR_DUPLICATE_MAX_LENGTH_RATIO and (\n",
        "test_near_duplicate_precheck_rejects_extreme_length_skew_before_alignment",
        file=REANCHOR,
        test_file=TSRA,
    ),
    m(
        "anchor-location-keeps-weaker-competitors",
        "    boundaries = tuple(\n"
        "        sorted({boundary for score, boundary in scored if score == best})\n"
        "    )\n",
        "    boundaries = tuple(\n"
        "        sorted({boundary for score, boundary in scored})\n"
        "    )\n",
        "test_anchor_location_tolerates_one_token_substitution_but_rejects_repeat_ties",
        file=REANCHOR,
        test_file=TSRA,
    ),
    m(
        "merged-atom-interior-boundary-rounded",
        "            if start < boundary < end:\n"
        '                return AtomBoundaryLookup(None, inspected_ranges, "inside-atom")\n',
        "            if False:\n"
        '                return AtomBoundaryLookup(None, inspected_ranges, "inside-atom")\n',
        "test_token_boundary_inside_one_fresh_atom_is_not_representable",
        file=REANCHOR,
        test_file=TSRA,
    ),
    m(
        "noncontiguous-slot-rebind-precondition-disabled",
        "        if not slot.contiguous:\n",
        "        if False:\n",
        "test_noncontiguous_slot_remains_a_valid_map_but_is_ineligible_for_rebind",
        test_file=TS35,
    ),
    m(
        "uncalibrated-result-marked-consumable",
        "    if not result.report.consumable:\n",
        "    if False:\n",
        "test_fully_bound_uncalibrated_result_is_explicitly_not_for_consumption",
    ),
    m(
        "policy-unit-interval-validation-disabled",
        '        for name in ("tau_primary", "tau_tie_break", "tau_no_geometry"):\n',
        "        for name in ():\n",
        "test_policy_thresholds_are_finite_unit_interval_scores",
    ),
    m(
        "stored-boundary-anchors-dropped-on-load",
        "        boundary_anchors=boundaries,\n",
        "        boundary_anchors=(),\n",
        "test_v3_map_exposes_typed_rebind_anchors_to_readers",
        file=SM,
        test_file=TSM,
    ),
    m(
        "shared-insert-boundary-conflict-disabled",
        "            if any(value is None for value in resolved) or len(set(resolved)) > 1:\n",
        "            if False:\n",
        "test_inv4_nonclean_insert_boundary_without_confirmation_fails_both_sides_loud",
        test_file=TS35,
    ),
    m(
        "near-duplicate-copy-hazard-guard-disabled",
        "        if self.dp_mode == MODE_NO_GEOMETRY and self.unresolved_duplication:\n",
        "        if False:\n",
        "test_inv1_shipped_rebind_bound_set_is_subset_of_shared_corpus_oracle",
        test_file=TS47,
    ),
    m(
        "report-backend-provenance-erased",
        "        alignment_backend=ALIGNMENT_BACKEND_ID,\n",
        '        alignment_backend="unknown",\n',
        "test_happy_rebind_binds_every_node_on_an_id_permuted_stream",
    ),
    m(
        "report-policy-identity-erased",
        "        policy_identity=context.policy.identity,\n",
        "        policy_identity=None,\n",
        "test_happy_rebind_binds_every_node_on_an_id_permuted_stream",
    ),
    m(
        "v3-anchor-allocation-expanded-to-maximum",
        "    footprint: int = 6\n",
        "    footprint: int = BOUNDARY_ANCHOR_FOOTPRINT_W\n",
        "test_v3_anchor_allocation_is_deterministic_content_only_and_bounded",
        file=ANCHOR,
        test_file=TSRA,
    ),
    # --- S4.7 item-4 production scale, RSS, density, and CI ------------------------------------
    m(
        "production-scale-top-decade-dropped",
        "PRODUCTION_ATOM_LADDER = (1_000, 10_000, 100_000)\n",
        "PRODUCTION_ATOM_LADDER = (1_000, 10_000, 10_000)\n",
        "test_production_ladders_and_both_shape_ledgers_are_pinned",
        file=SPROD,
        test_file=TSPROD,
    ),
    m(
        "absolute-wall-clock-ceiling-relaxed",
        "ABSOLUTE_END_TO_END_MAX_SECONDS = 300.0\n",
        "ABSOLUTE_END_TO_END_MAX_SECONDS = 301.0\n",
        "test_production_ladders_and_both_shape_ledgers_are_pinned",
        file=SPROD,
        test_file=TSPROD,
    ),
    m(
        "absolute-lifetime-rss-ceiling-relaxed",
        "ABSOLUTE_LIFETIME_RSS_MAX_BYTES = 6 * 1024**3\n",
        "ABSOLUTE_LIFETIME_RSS_MAX_BYTES = 7 * 1024**3\n",
        "test_production_ladders_and_both_shape_ledgers_are_pinned",
        file=SPROD,
        test_file=TSPROD,
    ),
    m(
        "absolute-production-budget-guard-disabled",
        '    if failures:\n        raise AssertionError(\n            "absolute end-to-end production budget exceeded: " + "; ".join(failures)\n        )\n',
        '    if False:\n        raise AssertionError(\n            "absolute end-to-end production budget exceeded: " + "; ".join(failures)\n        )\n',
        "test_absolute_end_to_end_budget_rejects_either_overrun",
        file=SPROD,
        test_file=TSPROD,
    ),
    m(
        "density-size-axis-top-decade-dropped",
        "DENSITY_SLOT_LADDER = (24, 240, 2_400)\n",
        "DENSITY_SLOT_LADDER = (24, 240, 240)\n",
        "test_production_ladders_and_both_shape_ledgers_are_pinned",
        file=SPROD,
        test_file=TSPROD,
    ),
    m(
        "density-surface-repetitions-shrunk",
        "DENSITY_REPETITIONS = 3\n",
        "DENSITY_REPETITIONS = 1\n",
        "test_production_ladders_and_both_shape_ledgers_are_pinned",
        file=SPROD,
        test_file=TSPROD,
    ),
    m(
        "full-profile-collapses-density-surface-to-one-n",
        "    full_density_surface: bool = True,\n",
        "    full_density_surface: bool = False,\n",
        "test_production_ladders_and_both_shape_ledgers_are_pinned",
        file=SPROD,
        test_file=TSPROD,
    ),
    m(
        "rss-sampler-cadence-relaxed-tenfold",
        "RSS_SAMPLE_INTERVAL_SECONDS = 0.005\n",
        "RSS_SAMPLE_INTERVAL_SECONDS = 0.050\n",
        "test_production_ladders_and_both_shape_ledgers_are_pinned",
        file=SPROD,
        test_file=TSPROD,
    ),
    m(
        "progress-heartbeat-cadence-relaxed",
        "PROGRESS_POLL_INTERVAL_SECONDS = 15.0\n",
        "PROGRESS_POLL_INTERVAL_SECONDS = 60.0\n",
        "test_production_ladders_and_both_shape_ledgers_are_pinned",
        file=SPROD,
        test_file=TSPROD,
    ),
    m(
        "optimization-heartbeat-cadence-loses-five-second-default",
        "OPTIMIZATION_PROGRESS_POLL_INTERVAL_SECONDS = 5.0\n",
        "OPTIMIZATION_PROGRESS_POLL_INTERVAL_SECONDS = 15.0\n",
        "test_production_ladders_and_both_shape_ledgers_are_pinned",
        file=SPROD,
        test_file=TSPROD,
    ),
    m(
        "rss-child-start-method-swapped-to-fork",
        'RSS_START_METHOD = "spawn"\n',
        'RSS_START_METHOD = "fork"\n',
        "test_production_ladders_and_both_shape_ledgers_are_pinned",
        file=SPROD,
        test_file=TSPROD,
    ),
    m(
        "two-generation-workspaces-collapsed",
        '    fresh_workspace = BookWorkspace.for_book("fresh-generation", root).ensure()\n',
        '    fresh_workspace = BookWorkspace.for_book("old-generation", root).ensure()\n',
        "test_production_round_trip_uses_separate_real_workspaces",
        file=SPROD,
        test_file=TSPROD,
    ),
    m(
        "fresh-workspace-serialized-from-old-generation",
        "    for stream in bundle.fresh_streams.values():\n",
        "    for stream in bundle.old_streams.values():\n",
        "test_production_round_trip_uses_separate_real_workspaces",
        file=SPROD,
        test_file=TSPROD,
    ),
    m(
        "rss-three-value-nesting-guard-disabled",
        "        if not (\n            self.lifetime_peak_bytes\n",
        "        if False and not (\n            self.lifetime_peak_bytes\n",
        "test_rss_value_object_rejects_broken_nesting_or_incremental_arithmetic",
        file=SPROD,
        test_file=TSPROD,
    ),
    m(
        "rss-conservative-counter-reconciliation-disabled",
        "    return max(raw_ru_maxrss, span_peak)\n",
        "    return raw_ru_maxrss\n",
        "test_conservative_lifetime_rss_reconciles_os_counter_disagreement",
        file=SPROD,
        test_file=TSPROD,
    ),
    m(
        "density-wrong-content-guard-disabled",
        "    if any(point.wrong for point in points):\n",
        "    if False:\n",
        "test_density_and_growth_guards_reject_planted_bad_results",
        file=SPROD,
        test_file=TSPROD,
    ),
    m(
        "density-reports-request-instead-of-actual-v3-anchors",
        "        measured_anchor_density=_actual_v3_anchor_density(bundle),\n",
        "        measured_anchor_density=unique_fraction,\n",
        "test_actual_v3_anchor_density_sweep_has_zero_wrong_binds_and_directional_abstention",
        file=SPROD,
        test_file=TSPROD,
    ),
    m(
        "production-growth-slope-guard-disabled",
        "            if slope > INV6_MAX_SLOPE:\n",
        "            if False:\n",
        "test_density_and_growth_guards_reject_planted_bad_results",
        file=SPROD,
        test_file=TSPROD,
    ),
    m(
        "density-timing-growth-guard-disabled",
        '    if float(summary["slope"]) > INV6_MAX_SLOPE or any(\n        float(value) > INV6_MAX_ADJACENT_RATIO for value in summary["adjacent_ratios"]\n    ):\n',
        "    if False:\n",
        "test_density_and_growth_guards_reject_planted_bad_results",
        file=SPROD,
        test_file=TSPROD,
    ),
    m(
        "scale-marker-no-longer-default-deselected",
        "addopts = '-m \"not scale\"'\n",
        "addopts = '-m \"scale\"'\n",
        "test_scale_marker_is_registered_and_default_deselected",
        file=PYPROJECT,
        test_file=TSPROD,
    ),
    m(
        "nightly-workflow-drops-scale-selector",
        "        run: uv run pytest -q --capture=tee-sys -m scale\n",
        "        run: uv run pytest -q --capture=tee-sys\n",
        "test_scale_marker_is_registered_and_default_deselected",
        file=CI_WORKFLOW,
        test_file=TSPROD,
    ),
    m(
        "nightly-workflow-hides-live-progress",
        "        run: uv run pytest -q --capture=tee-sys -m scale\n",
        "        run: uv run pytest -q -m scale\n",
        "test_scale_marker_is_registered_and_default_deselected",
        file=CI_WORKFLOW,
        test_file=TSPROD,
    ),
    m(
        "scale-cli-progress-disabled",
        "            emit_progress=True,\n            event_callback=checkpoint.record,\n",
        "            emit_progress=False,\n            event_callback=checkpoint.record,\n",
        "test_scale_marker_is_registered_and_default_deselected",
        file="tools/s4_7_scale.py",
        test_file=TSPROD,
    ),
    m(
        "scale-cli-checkpoint-events-dropped",
        "            event_callback=checkpoint.record,\n",
        "            event_callback=None,\n",
        "test_scale_marker_is_registered_and_default_deselected",
        file="tools/s4_7_scale.py",
        test_file=TSPROD,
    ),
    m(
        "boundary-anchor-derivation-rescans-entire-stream",
        '    token_count = len(tokens)\n    inside = boundary if side == "start" else boundary - 1\n',
        '    token_count = len(tuple(tokens))\n    inside = boundary if side == "start" else boundary - 1\n',
        "test_boundary_anchor_derivation_touches_only_bounded_local_context",
        file=ANCHOR,
        test_file=TSRA,
    ),
    m(
        "scale-substrate-schema-version-unpinned",
        'SCALE_SUBSTRATE_SCHEMA = "s4.7-scale-substrate@v1"\n',
        'SCALE_SUBSTRATE_SCHEMA = "s4.7-scale-substrate@v0"\n',
        "test_production_ladders_and_both_shape_ledgers_are_pinned",
        file=SPROD,
        test_file=TSPROD,
    ),
    m(
        "scale-substrate-source-lock-disabled",
        '    if manifest.get("source_identity") != _substrate_source_identity():\n',
        "    if False:\n",
        "test_source_locked_cached_substrate_is_clone_equivalent_and_tamper_loud",
        file=SPROD,
        test_file=TSPROD,
    ),
    m(
        "scale-substrate-persisted-file-lock-disabled",
        '    if manifest.get("persisted_file_identity") != _persisted_file_identity(\n        substrate.root\n    ):\n',
        "    if False:\n",
        "test_source_locked_cached_substrate_is_clone_equivalent_and_tamper_loud",
        file=SPROD,
        test_file=TSPROD,
    ),
    m(
        "scale-substrate-equivalence-proof-disabled",
        '    if manifest.get("cold_round_trip_equivalent") is not True:\n',
        "    if False:\n",
        "test_source_locked_cached_substrate_is_clone_equivalent_and_tamper_loud",
        file=SPROD,
        test_file=TSPROD,
    ),
    m(
        "scale-substrate-clone-collapsed-to-shared-source",
        '    shutil.copytree(substrate.root / "books", books_root)\n',
        '    books_root = substrate.root / "books"\n',
        "test_source_locked_cached_substrate_is_clone_equivalent_and_tamper_loud",
        file=SPROD,
        test_file=TSPROD,
    ),
    m(
        "end-to-end-routed-through-cached-substrate",
        '    return phase != "end_to_end"\n',
        "    return True\n",
        "test_end_to_end_never_uses_cached_substrate_including_absolute_gate",
        file=SPROD,
        test_file=TSPROD,
    ),
    m(
        "ordinary-phases-stop-using-cached-substrate",
        '    return phase != "end_to_end"\n',
        "    return False\n",
        "test_end_to_end_never_uses_cached_substrate_including_absolute_gate",
        file=SPROD,
        test_file=TSPROD,
    ),
    m(
        "direct-progress-log-mirroring-disabled",
        "    if progress_log:\n",
        "    if False:\n",
        "test_scale_progress_heartbeat_is_structured_and_context_complete",
        file=SPROD,
        test_file=TSPROD,
    ),
    m(
        "reference-composer-position-index-replaced-by-list-scan",
        "        idx = positions.get(atom_id)\n",
        "        idx = stream.index(atom_id) if atom_id in stream else None\n",
        "test_reference_composer_indexes_remint_ids_without_linear_stream_scans",
        file=RELATION,
        test_file=TRELATION,
    ),
    m(
        "reference-composer-new-id-check-rescans-live-stream",
        "        duplicates = [atom_id for atom_id in ids if atom_id in ancestors]\n",
        "        duplicates = [\n            atom_id for atom_id in ids if atom_id in ancestors or atom_id in stream\n        ]\n",
        "test_reference_composer_indexes_remint_ids_without_linear_stream_scans",
        file=RELATION,
        test_file=TRELATION,
    ),
    m(
        "fixture-spec-canonical-position-index-replaced-by-list-scan",
        "                indices.append(atom_positions[key])\n",
        "                indices.append(atom_keys.index(key))\n",
        "test_fixture_spec_validation_indexes_canonical_positions_without_list_scans",
        file=MATERIALIZE,
        test_file=TMATERIALIZE,
    ),
    m(
        "scale-substrate-source-lock-omits-relation-interpreter",
        '    Path(__file__).with_name("relation.py"),\n',
        "    # relation.py omitted\n",
        "test_production_ladders_and_both_shape_ledgers_are_pinned",
        file=SPROD,
        test_file=TSPROD,
    ),
    m(
        "deep-fixture-iterative-reachability-traversal-disabled",
        "    while work:\n",
        "    while False:\n",
        "test_fixture_spec_validation_supports_registered_depth_without_recursion",
        file=MATERIALIZE,
        test_file=TMATERIALIZE,
    ),
    m(
        "handle-validation-rebuilds-tree-index-per-node",
        '        return nid == "0" or any(\n',
        '        return nid == "0" or render_handle(\n'
        "            pmap, nid, policy, TARGET_HTML_SLUG, SCOPE_GLOBAL\n"
        "        ) == nid or any(\n",
        "test_handle_policy_validation_builds_the_tree_index_once",
        file=HANDLES,
        test_file=THANDLES,
    ),
    m(
        "handle-validation-restores-per-node-ancestor-walks",
        "    effective_policies = _effective_policy_map(\n"
        "        pmap, context.parents, handle_policies\n"
        "    )\n",
        "    effective_policies = {\n"
        "        node.node_id: _effective_policy(\n"
        "            node, pmap, context.parents, handle_policies\n"
        "        )\n"
        "        for node in pmap.nodes\n"
        "    }\n",
        "test_handle_policy_validation_does_not_walk_ancestors_per_node",
        file=HANDLES,
        test_file=THANDLES,
    ),
    m(
        "scale-substrate-source-lock-omits-handle-index-semantics",
        '    Path(__file__).resolve().parents[2] / "src/engine/structure/handles.py",\n',
        "    # handles.py omitted\n",
        "test_production_ladders_and_both_shape_ledgers_are_pinned",
        file=SPROD,
        test_file=TSPROD,
    ),
    m(
        "scale-artifact-source-identity-omits-handle-index-semantics",
        '    "src/engine/structure/handles.py",\n',
        "    # handles.py omitted\n",
        "test_production_ladders_and_both_shape_ledgers_are_pinned",
        file="tools/s4_7_scale.py",
        test_file=TSPROD,
    ),
    m(
        "scale-step-coordinate-drops-repetition",
        '                "step_coordinate": f"{phase_index}.{self.repetition}",\n',
        '                "step_coordinate": str(phase_index),\n',
        "test_scale_progress_coordinates_identify_phase_repetition_and_preparation",
        file=SPROD,
        test_file=TSPROD,
    ),
    m(
        "rebind-internal-telemetry-recorder-discarded",
        "        self.telemetry = context.telemetry or NULL_REBIND_TELEMETRY\n",
        "        self.telemetry = NULL_REBIND_TELEMETRY\n",
        "test_production_round_trip_uses_separate_real_workspaces",
        file=R,
        test_file=TSPROD,
    ),
    m(
        "telemetry-live-stage-publication-disabled",
        "        if self._enabled and self._stage_callback is not None:\n",
        "        if False:\n",
        "test_rebind_telemetry_publishes_nested_stage_progress_and_restores_parent",
        file=REBIN_TELEMETRY,
        test_file=TSPROD,
    ),
    m(
        "slot-progress-time-throttle-disabled",
        "                if now >= next_progress_at:\n",
        "                if False:\n",
        "test_slot_progress_is_time_throttled_and_always_publishes_final_completion",
        file=R,
        test_file=TSPROD,
    ),
    m(
        "slot-progress-final-completion-omitted",
        "                if completed == total:\n",
        "                if completed > total:\n",
        "test_slot_progress_is_time_throttled_and_always_publishes_final_completion",
        file=R,
        test_file=TSPROD,
    ),
    m(
        "density-raw-repetitions-discarded",
        "        samples=tuple(samples),\n",
        "        samples=(),\n",
        "test_actual_v3_anchor_density_sweep_has_zero_wrong_binds_and_directional_abstention",
        file=SPROD,
        test_file=TSPROD,
    ),
    m(
        "failed-scale-finalization-reports-in-progress",
        "        status=status,\n        measurement_total=measurement_total,\n",
        '        status="IN_PROGRESS",\n        measurement_total=measurement_total,\n',
        "test_terminal_scale_progress_overwrites_live_state_after_gate_failure",
        file=SPROD,
        test_file=TSPROD,
    ),
    m(
        "density-gate-short-circuits-earlier-failures",
        '                    failures.append(f"density/{treatment}: {exc}")\n',
        '                    failures = [f"density/{treatment}: {exc}"]\n',
        "test_gate_evaluation_preserves_every_density_growth_failure",
        file=SPROD,
        test_file=TSPROD,
    ),
    m(
        "drift-telemetry-sentinel-routed-to-identical-fixture",
        '                            if fixture_variant == "identical"\n',
        "                            if True\n",
        "test_spawned_drift_sentinel_is_labeled_and_runs_the_fresh_locator",
        file=SPROD,
        test_file=TSPROD,
    ),
    m(
        "slot-resolution-recomputes-fresh-fingerprint",
        "        fresh_fingerprint = _runtime_fingerprint_slot(\n"
        "            fresh_tokens, k=slot.fingerprint.k\n"
        "        )\n",
        "        _runtime_fingerprint_slot(fresh_tokens, k=slot.fingerprint.k)\n"
        "        self._fresh_fingerprint_computations += 1\n"
        "        fresh_fingerprint = _runtime_fingerprint_slot(\n"
        "            fresh_tokens, k=slot.fingerprint.k\n"
        "        )\n",
        "test_slot_resolution_constructs_one_fresh_fingerprint_per_evaluated_slot",
    ),
    m(
        "atom-boundary-index-restores-linear-range-walk",
        "        left, inspected_ranges = self._first_atom_ending_after(boundary)\n",
        "        left = 0\n"
        "        inspected_ranges = 0\n"
        "        while (\n"
        "            left < len(self.atom_ids)\n"
        "            and self.atom_token_ranges[left][1] <= boundary\n"
        "        ):\n"
        "            inspected_ranges += 1\n"
        "            left += 1\n",
        "test_production_round_trip_uses_separate_real_workspaces",
        file=REANCHOR,
        test_file=TSPROD,
    ),
    m(
        "resolver-aggregate-component-records-discarded",
        "        if not self._enabled or occurrences == 0:\n",
        "        if True:\n",
        "test_rebind_telemetry_records_disjoint_aggregate_without_live_stage_noise",
        file=REBIN_TELEMETRY,
        test_file=TSPROD,
    ),
    m(
        "identical-token-alignment-builds-kgram-indexes",
        "    if old == fresh:\n",
        "    if False:\n",
        "test_identical_alignment_is_one_equal_block_without_kgram_indexing",
        file=REANCHOR,
        test_file=TSRA,
    ),
    m(
        "identical-token-duplication-builds-gram-counters",
        "            if self.tokens_identical:\n",
        "            if False:\n",
        "test_production_round_trip_uses_separate_real_workspaces",
        file=R,
        test_file=TSPROD,
    ),
    m(
        "structure-map-tier1-native-validation-disabled",
        "        _tier1_schema_validator().validate(doc)\n",
        "        _tier1_schema_validator()\n",
        "test_bumped_document_version_fails_tier1",
        file=SM,
        test_file=TSM,
    ),
    m(
        "mutation-evidence-heartbeat-default-relaxed",
        "MUTATION_HEARTBEAT_INTERVAL_SECONDS = 5.0\n",
        "MUTATION_HEARTBEAT_INTERVAL_SECONDS = 15.0\n",
        "test_mutation_manifest_heartbeat_default_is_five_seconds",
        file=MUTATION_TOOL,
        test_file=TMUTATION,
    ),
    m(
        "mutation-evidence-live-tee-disabled",
        '        print(line, end="", file=sys.stderr, flush=True)\n',
        "        pass\n",
        "test_live_runner_output_is_forwarded_and_captured_bit_for_bit",
        file=MUTATION_TOOL,
        test_file=TMUTATION,
    ),
    m(
        "mutation-evidence-interrupt-traceback-unsuppressed",
        "        except KeyboardInterrupt:\n",
        "        except ():\n",
        "test_manifest_interrupt_exits_130_without_wrapper_traceback",
        file=MUTATION_TOOL,
        test_file=TMUTATION,
    ),
]
