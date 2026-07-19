"""S4.7 item 2 Priority 3 — INV-3, INV-4, and INV-5 carried reds."""

from __future__ import annotations

import pytest

from engine.structure.boundary_anchor import (
    BOUNDARY_ANCHOR_FOOTPRINT_W,
    BoundaryConfirmation,
    BoundaryDecisionHook,
    ConfirmingBoundaryDecision,
)
from engine.structure.geom_regate import MODE_PRIMARY, MODE_TIE_BREAK
from engine.structure.rebind import RebindContext, rebind
from engine.structure.structure_map import (
    StreamAtomReader,
    structure_map_from_json,
    validate_structure_map,
)
from harness.boundary import (
    AnalyticBlock,
    classify_boundary,
    mandatory_boundary_cases,
    validate_analytic_tiling,
)
from harness.invariants_3_5 import (
    FAIL_LOUD_REASONS,
    GeometryInteractionRow,
    MoveCase,
    MoveObservation,
    assert_move_observations,
    geometry_interaction_matrix,
    priority3_move_cases,
    tie_break_only_bundle,
)
from harness.oracle import SlotRef, _edit_reference, planted_tuples
from harness.materialize import (
    AtomSeed,
    DriftConfig,
    FixtureSpec,
    NodeSeed,
    SLOT_BODY,
    materialize_fixture,
)

TRACKER = "S5.1-R/#48 (S4.7 item 3)"


def _result(bundle):
    return rebind(
        RebindContext(
            bundle.old_map,
            bundle.old_streams,
            bundle.fresh_streams,
            old_evidence=bundle.old_evidence,
            geometry_mode=bundle.geometry_mode,
            policy=bundle.policy,
        )
    )


def _map_valid(result, bundle) -> bool:
    try:
        projection = structure_map_from_json(result.migrated_doc).projection
        validate_structure_map(
            structure_map_from_json(result.migrated_doc),
            StreamAtomReader(bundle.fresh_streams, bundle.fresh_canonical.stream_id),
        )
    except Exception:
        return False
    return projection is not None


def _move_observations(case):
    result = _result(case.bundle)
    by_id = {node.node_id: node for node in result.report.nodes}
    observations = []
    for ref in case.affected:
        slot = next(
            slot for slot in by_id[ref.node_id].slots if slot.slot_name == ref.slot_name
        )
        observations.append(
            MoveObservation(
                ref,
                by_id[ref.node_id].bound and slot.bound,
                by_id[ref.node_id].reason
                if not by_id[ref.node_id].bound
                else slot.reason,
                slot.fresh_atom_ids,
                _map_valid(result, case.bundle)
                if by_id[ref.node_id].bound and slot.bound
                else False,
            )
        )
    return tuple(observations)


def test_inv3_within_and_cross_container_moves_never_bind_away_from_truth():
    assert {case.name for case in priority3_move_cases()} == {
        "within-container",
        "cross-container",
    }
    for case in priority3_move_cases():
        assert case.bundle.relation.moved
        assert_move_observations(case, _move_observations(case))


def test_inv3_duplicate_observation_for_one_moved_slot_is_rejected():
    case = priority3_move_cases()[0]
    observation = _move_observations(case)[0]
    with pytest.raises(AssertionError, match="duplicate observation"):
        assert_move_observations(case, (observation, observation))


def test_inv3_planted_greedy_wrong_span_is_rejected():
    case = priority3_move_cases()[0]
    slot = case.affected[0]
    planted = planted_tuples(case.bundle, slot)[0]
    wrong = tuple(reversed(planted))
    with pytest.raises(AssertionError, match="bound away from planted destination"):
        assert_move_observations(
            case,
            (MoveObservation(slot, True, None, wrong, True),),
        )


def test_inv3_destination_atom_bind_with_invalid_map_is_rejected():
    case = priority3_move_cases()[0]
    slot = case.affected[0]
    planted = planted_tuples(case.bundle, slot)[0]
    with pytest.raises(AssertionError, match="globally invalid structure map"):
        assert_move_observations(
            case,
            (MoveObservation(slot, True, None, planted, False),),
        )


def test_noncontiguous_slot_remains_a_valid_map_but_is_ineligible_for_rebind():
    spec = FixtureSpec(
        root_id="root",
        nodes=(
            NodeSeed("root", "volume", "container", children=("l0", "l1")),
            NodeSeed("l0", "block", "leaf", body=("a0", "a2")),
            NodeSeed("l1", "block", "leaf", body=("a1",)),
        ),
        atoms=(
            AtomSeed("a0", "alpha beta", "l0", SLOT_BODY),
            # Tokenless interposition makes the downstream token span look deceptively clean if
            # the explicit noncontiguous-slot precondition is removed.  The guard must still
            # abstain rather than claim l1's punctuation as part of l0.
            AtomSeed("a1", "—", "l1", SLOT_BODY),
            AtomSeed("a2", "…", "l0", SLOT_BODY),
        ),
        require_tokenless_cases=False,
    )
    bundle = materialize_fixture(spec, DriftConfig("noncontiguous-slot", 3601, ()))
    # Materialization has already run the ordinary structure-map validator: the map is valid.
    l0 = next(node for node in _result(bundle).report.nodes if node.node_id == "l0")
    assert not l0.bound and l0.reason == "ambiguous"


@pytest.mark.parametrize("case", mandatory_boundary_cases(), ids=lambda case: case.name)
def test_inv4_analytic_half_open_boundary_classes(case):
    _, _, _, optimal_paths = _edit_reference(case.old_tokens, case.fresh_tokens)
    assert optimal_paths == 1
    assert (
        classify_boundary(case.old_token_count, case.blocks, case.boundary)
        == case.expected
    )


def test_inv4_analytic_tiling_rejects_adjacent_non_equal_blocks():
    with pytest.raises(ValueError, match="adjacent non-equal"):
        validate_analytic_tiling(
            2,
            (
                AnalyticBlock("replace", 0, 1, 0, 1),
                AnalyticBlock("delete", 1, 2, 1, 1),
            ),
        )


def test_inv4_analytic_tiling_allows_multiple_edits_only_when_equal_separates_them():
    blocks = (
        AnalyticBlock("equal", 0, 1, 0, 1),
        AnalyticBlock("replace", 1, 2, 1, 2),
        AnalyticBlock("equal", 2, 3, 2, 3),
        AnalyticBlock("delete", 3, 4, 3, 3),
        AnalyticBlock("equal", 4, 5, 3, 4),
    )
    validate_analytic_tiling(5, blocks)
    assert classify_boundary(5, blocks, 1) == "edge-candidate"
    assert classify_boundary(5, blocks, 4) == "edge-candidate"


def test_inv4_delete_edges_collapse_to_one_fresh_gap_but_remain_edge_candidates():
    blocks = (
        AnalyticBlock("equal", 0, 1, 0, 1),
        AnalyticBlock("delete", 1, 3, 1, 1),
        AnalyticBlock("equal", 3, 4, 1, 2),
    )
    assert classify_boundary(4, blocks, 1) == "edge-candidate"
    assert classify_boundary(4, blocks, 3) == "edge-candidate"


def test_inv4_nonclean_insert_boundary_without_confirmation_fails_both_sides_loud():
    violations = {}
    for row in geometry_interaction_matrix():
        if row.drift != "boundary-edit":
            continue
        report = _result(row.bundle).report
        affected = {
            node.node_id: (node.bound, node.reason)
            for node in report.nodes
            if node.node_id in {"l0", "l1"}
        }
        if set(affected) != {"l0", "l1"} or any(
            bound or reason not in FAIL_LOUD_REASONS
            for bound, reason in affected.values()
        ):
            violations[row.mode] = affected
    assert violations == {}


def test_inv4_clean_token_projection_inside_merged_atom_never_rounds_to_a_slot():
    from harness.oracle import priority2_shared_corpus

    case = next(
        case
        for case in priority2_shared_corpus().cases
        if case.name == "merge-cross-slot-seam"
    )
    report = _result(case.bundle).report
    assert {
        node.node_id: (node.bound, node.reason)
        for node in report.nodes
        if node.node_id in {"l0", "l1"}
    } == {
        "l0": (False, "global-conflict"),
        "l1": (False, "global-conflict"),
    }


def test_inv4_every_nonclean_class_without_confirmation_abstains():
    hook: BoundaryDecisionHook = ConfirmingBoundaryDecision()
    unconfirmed = BoundaryConfirmation(False, False, 12, None)
    assert not unconfirmed.confirmed
    violations = {
        boundary_class
        for boundary_class in (
            "edge-candidate",
            "no-candidate",
            "two-candidate",
        )
        if hook.admits(
            boundary_class,
            unconfirmed,
            within_window=boundary_class == "no-candidate",
            atom_representable=True,
        )
    }
    assert violations == set()


def test_inv4_independently_confirmed_boundary_uses_the_confirmation_path():
    hook: BoundaryDecisionHook = ConfirmingBoundaryDecision()
    confirmation = BoundaryConfirmation(True, True, 12, 12)
    assert confirmation.confirmed
    assert hook.admits(
        "edge-candidate",
        confirmation,
        within_window=True,
        atom_representable=True,
    )


def test_inv4_production_edge_candidate_binds_only_through_anchor_confirmation():
    from harness.oracle import priority2_shared_corpus

    case = next(
        case
        for case in priority2_shared_corpus().cases
        if case.name == "move-container-edge"
    )
    l0 = next(node for node in _result(case.bundle).report.nodes if node.node_id == "l0")
    slot = l0.slots[0]
    assert slot.bound and slot.reason is None
    assert slot.boundary_classes == ("clean-candidate", "edge-candidate")
    assert slot.located_by == ("anchor-projected", "anchor-projected")


def test_inv5_interaction_matrix_is_exactly_three_drifts_by_two_modes():
    matrix = geometry_interaction_matrix()
    assert len(matrix) == 6
    assert {(row.drift, row.mode) for row in matrix} == {
        (drift, mode)
        for drift in {"repeated-content", "boundary-edit", "move"}
        for mode in {MODE_PRIMARY, MODE_TIE_BREAK}
    }
    for row in matrix:
        assert row.bundle.geometry_mode == row.mode
        assert row.bundle.old_map.doc["manifest"]["canonical_geometry_hash"]
        if row.drift == "repeated-content":
            assert 100 > 2 * BOUNDARY_ANCHOR_FOOTPRINT_W
            assert row.companion is not None
            assert {
                atom.page_range[0] for atom in row.companion.old_canonical.atoms
            } == {
                1,
                2,
            }


def _repeated_rows() -> tuple[GeometryInteractionRow, ...]:
    return tuple(
        row for row in geometry_interaction_matrix() if row.drift == "repeated-content"
    )


def test_inv5_same_page_repeated_content_is_ambiguous_in_both_geometry_modes():
    violations = {}
    for row in _repeated_rows():
        bound = [
            node.node_id
            for node in _result(row.bundle).report.nodes
            if node.node_id.startswith("leaf-") and node.bound
        ]
        if bound:
            violations[row.mode] = bound
    assert violations == {}


def test_inv5_distinct_page_repeated_content_may_bind_only_to_each_planted_copy():
    for row in _repeated_rows():
        assert row.companion is not None
        result = _result(row.companion)
        for node in result.report.nodes:
            if not node.node_id.startswith("leaf-"):
                continue
            assert node.bound and node.reason is None
            slot = node.slots[0]
            expected = planted_tuples(
                row.companion, SlotRef(node.node_id, slot.slot_name)
            )
            assert slot.fresh_atom_ids in expected


def test_inv5_tie_break_uses_page_only_to_reduce_an_above_tau_tie():
    result = _result(tie_break_only_bundle())
    l0 = next(node for node in result.report.nodes if node.node_id == "l0")
    slot = l0.slots[0]
    assert slot.bound and slot.reason is None
    assert slot.candidates_ge_tau == 2
    assert slot.fresh_atom_ids == ("fresh-00000dad-000-000-x0",)


def test_inv5_boundary_and_move_rows_do_not_use_geometry_as_content_rescue():
    for row in geometry_interaction_matrix():
        if row.drift == "boundary-edit":
            report = _result(row.bundle).report
            assert any(
                not node.bound for node in report.nodes if node.node_id in {"l0", "l1"}
            )
        elif row.drift == "move":
            case = MoveCase(
                f"geometry-{row.mode}",
                row.bundle,
                (SlotRef("l0", "body"),),
            )
            assert_move_observations(case, _move_observations(case))
