"""Mutant table for S5.1 (#47): the store-and-rebind mechanism's §4 red-first invariants.

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
"""
from pathlib import Path

REPO = str(Path(__file__).resolve().parents[2])
TEST_CMD = [str(Path(REPO) / ".venv" / "bin" / "python"), "-m", "pytest", "{scope}",
            "-q", "--no-header", "-x", "-p", "no:cacheprovider"]
TIMEOUT = 300

R = "src/engine/structure/rebind.py"
SM = "src/engine/structure/structure_map.py"
PROJ = "src/engine/structure/projection.py"
ART = "src/engine/structure/artifacts.py"
TR = "tests/unit/test_rebind.py"
TSM = "tests/unit/test_structure_map.py"
TBG = "tests/unit/test_structure_born_gate.py"


def m(label, old, new, test_id, *, file=R, test_file=TR):
    return {"label": label, "file": file, "old": old, "new": new, "scope": f"{test_file}::{test_id}"}


MUTANTS = [
    # --- fingerprint producer + similarity (§2.2) ---------------------------------------------------
    m("empty-slot-returns-empty-shingle-fingerprint",
      "    if not toks:\n        return None",
      "    if not toks:\n        return SlotFingerprint(algo_id=FINGERPRINT_ALGO_ID, "
      "normalizer_id=FINGERPRINT_NORMALIZER_ID, k=1, token_count=0, shingles=())",
      "test_fingerprint_slot_empty_is_none_never_empty_set"),
    m("short-slot-no-k-fallback",
      "    k_eff = min(k, len(toks)) if k >= 1 else 1",
      "    k_eff = k",
      "test_fingerprint_slot_short_slot_falls_back_to_available_k"),
    m("empty-window-scores-one-not-zero",
      "    if fresh is None:\n        return 0.0",
      "    if fresh is None:\n        return 1.0",
      "test_slot_similarity_empty_window_scores_zero"),
    m("jaccard-collapses-to-all-or-nothing-substring",
      "    return len(a & b) / len(union)",
      "    return 1.0 if (a & b) else 0.0",
      "test_r2_superstring_does_not_auto_bind_at_full_score"),
    # --- mode resolution (§1.2) ---------------------------------------------------------------------
    m("unknown-mode-defaults-instead-of-failing-loud",
      "    if geometry_mode in GEOMETRY_MODES:",
      "    if True:",
      "test_resolve_mode_unknown_fails_loud"),
    m("none-mode-reported-as-manifest-not-fallback",
      '        return (MODE_TIE_BREAK, FALLBACK_REPORTED_MODE, "fallback")',
      '        return (MODE_TIE_BREAK, MODE_TIE_BREAK, "manifest")',
      "test_resolve_mode_none_is_conditional_primary_fallback"),
    # --- policy default-ordering (§4, D-4) ----------------------------------------------------------
    m("policy-ordering-guard-dropped",
      "        if not (self.tau_no_geometry >= self.tau_tie_break >= self.tau_primary):",
      "        if False:",
      "test_policy_inverted_ordering_is_rejected_at_construction"),
    m("policy-default-primary-margin-inverted",
      "    tau_primary: float = DEFAULT_FINGERPRINT_THRESHOLD - _DEFAULT_MODE_MARGIN",
      "    tau_primary: float = DEFAULT_FINGERPRINT_THRESHOLD + _DEFAULT_MODE_MARGIN",
      "test_policy_default_ordering_holds_on_the_named_default"),
    # --- baseline binding (§1.4) --------------------------------------------------------------------
    m("baseline-content-hash-gate-dropped",
      '        if live_content != manifest.get("canonical_content_hash"):',
      "        if False:",
      "test_rebind_context_refuses_a_content_hash_mismatch"),
    # --- per-node reasons: missing-anchor / below-threshold / ambiguous / no-rescue -----------------
    m("fingerprint-less-slot-binds-instead-of-missing-anchor",
      '                slot_name=slot.slot_name, bound=False, reason="missing-anchor", score=None,',
      "                slot_name=slot.slot_name, bound=True, reason=None, score=None,",
      "test_missing_anchor_node_never_binds_on_geometry_alone"),
    m("below-threshold-binds-any-score",
      "                if score >= self.tau:",
      "                if score >= 0.0:",
      "test_below_threshold_when_fresh_content_diverges"),
    m("no-rescue-geometry-lifts-subtau-over-tau",
      "                if score >= self.tau:",
      "                if score >= self.tau or self._on_region_page(slot, a, b):",
      "test_no_rescue_geometry_does_not_lift_a_subtau_fingerprint"),
    m("ambiguous-picks-first-candidate",
      "        if len(chosen) == 1:",
      "        if len(chosen) >= 1:",
      "test_ambiguous_repeated_content_fails_loud"),
    # --- mode gating: the primary hard pin (§1.2) ---------------------------------------------------
    m("primary-pin-ignores-mode",
      "        if self.dp_mode == MODE_PRIMARY and slot.region is not None:",
      "        if False and slot.region is not None:",
      "test_primary_mode_hard_pin_excludes_a_wrong_page_and_yields_zero_candidate"),
    # --- global consistency (§1.3) ------------------------------------------------------------------
    m("global-validate-gate-disabled",
      "    if all_bound and not _map_validates(migrated_projection, context):",
      "    if False and not _map_validates(migrated_projection, context):",
      "test_empty_container_makes_the_rebound_map_fail_global_validation"),
    # bound-SUBSET disjointness must run on EVERY re-bind, not only all-bound (the audit-found partial
    # silent double-bind): neutering the contested-atom witness lets two bound nodes share a fresh atom.
    m("bound-subset-disjointness-disabled",
      "    return {nid for owners in claims.values() if len(owners) > 1 for nid in owners}",
      "    return set()",
      "test_partial_rebind_never_silently_double_claims_a_fresh_atom"),
    # --- re-stamp protocol (§1.6) -------------------------------------------------------------------
    m("restamp-ignores-the-bottom-up-subtree-gate",
      "        if not _subtree_ids(entry.node_id, migrated_projection).issubset(bound_node_ids):",
      "        if False:",
      "test_ancestor_not_restamped_while_a_descendant_is_unresolved"),
    m("stale-decision-never-detected",
      "        and entry.decision_digest != decision_digest(node)",
      "        and False",
      "test_stale_decision_is_a_finding_not_a_restamp"),
    m("stale-decision-node-kept-bound",
      "        bound_node_ids -= stale_decisions",
      "        bound_node_ids -= set()",
      "test_stale_decision_is_a_finding_not_a_restamp"),
    # --- Phase-A/B surface the mechanism rides ------------------------------------------------------
    m("typed-anchor-dropped-on-load",
      "        rebind_anchors=_rebind_anchors_from_json(data.get(\"rebind_anchors\")),",
      "        rebind_anchors=None,",
      "test_v2_map_exposes_typed_rebind_anchors_to_readers",
      file=SM, test_file=TSM),
    m("region-page-floor-allows-zero",
      "        if isinstance(self.page, bool) or not isinstance(self.page, int) or self.page < 1:",
      "        if isinstance(self.page, bool) or not isinstance(self.page, int) or self.page < 0:",
      "test_region_model_rejects_a_page_below_one",
      file=PROJ),
    m("v2-schema-not-born",
      "STRUCTURE_MAP_SCHEMA_STATUS: dict[int, str] = {1: SCHEMA_STATUS_BORN, 2: SCHEMA_STATUS_BORN}",
      "STRUCTURE_MAP_SCHEMA_STATUS: dict[int, str] = {1: SCHEMA_STATUS_BORN, 2: SCHEMA_STATUS_PROVISIONAL}",
      "test_v2_fingerprint_fixture_validates_and_v2_is_born",
      file=ART, test_file=TBG),
]
