"""S4.7 item 2 Priority 2 — INV-1 + INV-2 on one seeded corpus.

The strict xfails are the normative carried reds for S5.1-R/#48.  Run a named test with
``--runxfail`` to reproduce its demonstrated raw red; an accidental pass is a suite failure until
item 3 deliberately removes the marker with the replacement mechanism.
"""

from __future__ import annotations

import ast
import inspect
import runpy
from collections import Counter
from pathlib import Path

import pytest

from engine.structure.boundary_anchor import (
    BOUNDARY_ANCHOR_FOOTPRINT_W,
    BoundaryAnchor,
    BoundaryAnchorFamily,
    BoundaryConfidenceGate,
    BoundaryConfirmation,
    derive_boundary_anchor,
)
from engine.structure.geom_match import normalize_tokens
from engine.structure.rebind import RebindContext, RebindPolicy, rebind
from harness.oracle import (
    ANCHOR_POOR_SENTINEL,
    ANCHOR_RICH_SENTINEL,
    ORACLE_TAU_BY_MODE,
    PRIORITY2_RANDOM_SEEDS,
    AllowedBind,
    ObservedBind,
    ObservedCase,
    SlotRef,
    _boundary_mappings,
    _edit_reference,
    allowed_bind_set,
    anchor_density_fixture,
    assert_bound_subset_and_disjoint,
    assert_insert_coverage_not_silent,
    case_oracle,
    diagnose_case,
    planted_tuples,
    priority2_shared_corpus,
    required_inv2_binds,
)

_MANIFEST_API = runpy.run_path(
    str(Path(__file__).resolve().parents[2] / "tools/s4_7_hunt_manifest.py")
)
priority_case_names = _MANIFEST_API["priority_case_names"]
priority_diagnostics = _MANIFEST_API["priority_diagnostics"]

TRACKER = "S5.1-R/#48 (S4.7 item 3)"


def _result(case):
    bundle = case.bundle
    context = RebindContext(
        bundle.old_map,
        bundle.old_streams,
        bundle.fresh_streams,
        old_evidence=bundle.old_evidence,
        geometry_mode=bundle.geometry_mode,
        policy=bundle.policy,
    )
    return rebind(context)


def _observed_case(case) -> ObservedCase:
    report = _result(case).report
    binds = tuple(
        ObservedBind(SlotRef(node.node_id, slot.slot_name), slot.fresh_atom_ids)
        for node in report.nodes
        for slot in node.slots
        if slot.bound
    )
    unresolved = frozenset(
        SlotRef(node.node_id, slot.slot_name)
        for node in report.nodes
        for slot in node.slots
        if not slot.bound
    )
    return ObservedCase(binds, unresolved)


def _observed(case) -> tuple[ObservedBind, ...]:
    return _observed_case(case).binds


def _case(name: str):
    return next(case for case in priority2_shared_corpus().cases if case.name == name)


def test_inv1_and_inv2_consume_one_exact_fixed_seed_corpus():
    corpus = priority2_shared_corpus()
    assert corpus.random_seeds == PRIORITY2_RANDOM_SEEDS == tuple(range(2700, 2716))
    assert len(corpus.case_names) == len(set(corpus.case_names)) == 29
    assert {
        "duplicate",
        "split-token-boundary",
        "merge-cross-slot-seam",
        "inv2-atom-merge",
        "inv2-interior-char-sub",
        "anchor-poor-within-container",
        "anchor-poor-cross-container",
    } <= set(corpus.case_names)

    # Both consumers resolve against these same bundle objects, not friendly/hostile split corpora.
    inv2 = required_inv2_binds(corpus)
    assert set(inv2) == {
        "split-token-boundary",
        "inv2-atom-merge",
        "inv2-interior-char-sub",
    }
    for case in corpus.cases:
        allowed_bind_set(case.bundle)


def test_shared_random_supplement_reports_realized_non_noop_operation_coverage():
    random_cases = [
        case
        for case in priority2_shared_corpus().cases
        if case.name.startswith("shared-random-seed-")
    ]
    realized = Counter()
    generated = Counter()
    for case in random_cases:
        for op, count in case.bundle.stats.realized_counts.items():
            realized[op] += count
        for op, count in case.bundle.stats.generated_counts.items():
            generated[op] += count
    assert len(random_cases) == len(PRIORITY2_RANDOM_SEEDS)
    operations = {"char_sub", "drop", "insert", "duplicate", "split", "merge", "move"}
    assert all(generated[op] == len(PRIORITY2_RANDOM_SEEDS) for op in operations)
    assert all(realized[op] > 0 for op in operations)


def test_oracle_module_has_no_rebind_import_or_report_readback():
    path = Path(inspect.getsourcefile(allowed_bind_set))
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }
    assert "engine.structure.rebind" not in imports
    assert not any(
        isinstance(node, ast.Attribute) and node.attr in {"report", "bound_node_ids"}
        for node in ast.walk(tree)
    )


def test_independent_oracle_threshold_copy_is_bound_to_shipped_policy_defaults():
    policy = RebindPolicy()
    assert dict(ORACLE_TAU_BY_MODE) == {
        "geometry-primary": policy.tau_primary,
        "geometry-tie-break": policy.tau_tie_break,
        "no-geometry": policy.tau_no_geometry,
    }


def test_oracle_keeps_concrete_atom_tuples_not_numeric_intervals():
    case = _case("split-token-boundary")
    truth = case_oracle(case.bundle)[SlotRef("l0", "body")]
    (allowed,) = truth.allowed
    assert allowed.fresh_atom_ids == (
        "fresh-00000068-000-001-a0",
        "fresh-00000068-000-002-p0",
        "fresh-00000068-001-000-a1-left",
        "fresh-00000068-001-001-a1-right",
        "fresh-00000068-000-004-p1",
    )
    assert truth.alignment[0].planted_feasible
    assert not truth.alignment[0].has_boundary_alternative


def test_bounded_reference_grid_exposes_boundary_alternatives_without_selecting_one():
    old, fresh = ("alpha", "omega"), ("alpha", "inserted", "omega")
    forward, backward, distance, paths = _edit_reference(old, fresh)
    assert distance == 1 and paths == 1
    assert _boundary_mappings(1, forward, backward, distance) == (1, 2)
    with pytest.raises(ValueError, match="reference alignment bound exceeded"):
        _edit_reference(("x",) * 513, ())


def test_oracle_rejects_the_shipped_duplicate_wrong_copy_shape():
    case = _case("duplicate")
    wrong = ObservedBind(
        SlotRef("l1", "body"),
        (
            "fresh-00000067-001-000-b0-copy",
            "fresh-00000067-000-006-b1",
        ),
    )
    with pytest.raises(AssertionError, match="false bind"):
        assert_bound_subset_and_disjoint((wrong,), allowed_bind_set(case.bundle))


def test_oracle_global_conjunct_rejects_two_pairwise_allowed_claims_of_one_atom():
    shared = "fresh-shared"
    left = AllowedBind(SlotRef("left", "body"), (shared,))
    right = AllowedBind(SlotRef("right", "body"), (shared,))
    with pytest.raises(AssertionError, match="claimed by multiple slots"):
        assert_bound_subset_and_disjoint(
            (
                ObservedBind(left.slot, left.fresh_atom_ids),
                ObservedBind(right.slot, right.fresh_atom_ids),
            ),
            frozenset({left, right}),
        )


def test_oracle_rejects_duplicate_outcome_records_for_one_slot():
    allowed = AllowedBind(SlotRef("only", "body"), ("fresh-only",))
    observed = ObservedBind(allowed.slot, allowed.fresh_atom_ids)
    with pytest.raises(AssertionError, match="more than one bind for the same slot"):
        assert_bound_subset_and_disjoint((observed, observed), frozenset({allowed}))


def test_shared_seam_insert_cannot_be_silently_dropped_when_both_owners_bind():
    case = _case("split-boundary")
    inserted = next(iter(case.bundle.relation.inserted))
    binds = []
    for slot in (SlotRef("l0", "body"), SlotRef("l1", "body")):
        without_insert = next(
            candidate
            for candidate in planted_tuples(case.bundle, slot)
            if inserted not in candidate
        )
        binds.append(ObservedBind(slot, without_insert))
    with pytest.raises(AssertionError, match="silently dropped"):
        assert_insert_coverage_not_silent(
            case.bundle, ObservedCase(tuple(binds), frozenset())
        )


def test_per_case_breakdown_is_complete_diagnostic_not_a_rate_gate():
    for case in priority2_shared_corpus().cases:
        slots = case_oracle(case.bundle)
        diagnostic = diagnose_case(
            case.name,
            slots,
            _observed(case),
            allowed_bind_set(case.bundle),
        )
        assert (
            diagnostic.bound_correct + diagnostic.abstained + diagnostic.wrong
            == len(slots)
        )
        assert not hasattr(diagnostic, "rate")


def test_manifest_breakdown_resolves_the_live_corpus_and_emits_no_rate():
    corpus = priority2_shared_corpus()
    assert priority_case_names() == corpus.case_names
    rows = priority_diagnostics()
    assert [row["case"] for row in rows] == list(corpus.case_names)
    assert all("rate" not in row for row in rows)
    assert all(
        row["bound_correct"] + row["abstained"] + row["wrong"] > 0 for row in rows
    )


def test_anchor_interface_is_content_only_bounded_and_has_separate_confidence_hook():
    assert BOUNDARY_ANCHOR_FOOTPRINT_W == 24
    assert set(BoundaryAnchor.__dataclass_fields__) == {"prefix", "exact", "suffix"}
    derive = inspect.signature(BoundaryAnchorFamily.derive)
    assert tuple(derive.parameters) == ("self", "tokens", "boundary", "side")
    assert inspect.signature(BoundaryConfidenceGate.confirm).parameters.keys() == {
        "self",
        "anchor",
        "old_tokens",
        "fresh_tokens",
        "projected_fresh_boundary",
    }
    with pytest.raises(ValueError, match="exceeds fixed W"):
        BoundaryAnchor(
            prefix=("p",) * BOUNDARY_ANCHOR_FOOTPRINT_W,
            exact=("e",),
            suffix=(),
        )


def test_anchor_interface_wrapper_enforces_determinism_and_content_contiguity():
    class StableFamily:
        def derive(self, tokens, boundary, *, side):
            return BoundaryAnchor(
                prefix=(tokens[boundary - 1],),
                exact=(tokens[boundary],),
                suffix=(tokens[boundary + 1],),
            )

    tokens = ("left", "inside", "right")
    assert derive_boundary_anchor(
        StableFamily(), tokens, 1, side="start"
    ) == BoundaryAnchor(("left",), ("inside",), ("right",))

    class AlternatingFamily:
        calls = 0

        def derive(self, tokens, boundary, *, side):
            self.calls += 1
            exact = tokens[boundary] if self.calls == 1 else tokens[boundary + 1]
            return BoundaryAnchor((), (exact,), ())

    with pytest.raises(ValueError, match="not deterministic"):
        derive_boundary_anchor(AlternatingFamily(), tokens, 1, side="start")

    class ForeignContentFamily:
        def derive(self, tokens, boundary, *, side):
            return BoundaryAnchor((), ("structural-path-42",), ())

    with pytest.raises(ValueError, match="not contiguous supplied content"):
        derive_boundary_anchor(ForeignContentFamily(), tokens, 1, side="start")


def test_unique_anchor_that_maps_far_is_not_confirmed():
    confirmation = BoundaryConfirmation(
        unique_in_old=True,
        unique_in_fresh=True,
        projected_fresh_boundary=10,
        located_fresh_boundary=91,
    )
    assert not confirmation.confirmed


def test_anchor_density_sentinels_are_mechanical_against_named_w():
    rich = anchor_density_fixture(ANCHOR_RICH_SENTINEL)
    poor = anchor_density_fixture(ANCHOR_POOR_SENTINEL)
    poor_cross = anchor_density_fixture(ANCHOR_POOR_SENTINEL, cross_container=True)
    repeat_width = 4 * BOUNDARY_ANCHOR_FOOTPRINT_W + 2
    assert repeat_width > 2 * BOUNDARY_ANCHOR_FOOTPRINT_W

    rich_tokens = [
        token
        for atom in rich.old_canonical.atoms
        for token in normalize_tokens(atom.text)
    ]
    poor_tokens = [
        token
        for atom in poor.old_canonical.atoms
        for token in normalize_tokens(atom.text)
    ]
    assert max(Counter(rich_tokens).values()) == 1
    repeated = [token for token, count in Counter(poor_tokens).items() if count == 2]
    assert len(repeated) == repeat_width
    # The repeated boundary is >W from both passage edges; every bounded content-only anchor at the
    # corresponding boundary is byte-identical in the two copies.
    assert repeat_width // 2 > BOUNDARY_ANCHOR_FOOTPRINT_W
    assert {"container-0", "container-1"} <= {
        node.node_id for node in poor_cross.spec.nodes
    }


def test_inv1_anchor_poor_sentinels_abstain_within_and_cross_container():
    violations = {}
    for case_name in (
        "anchor-poor-within-container",
        "anchor-poor-cross-container",
    ):
        case = _case(case_name)
        observed = _observed_case(case)
        try:
            assert_bound_subset_and_disjoint(
                observed.binds, allowed_bind_set(case.bundle)
            )
        except AssertionError as exc:
            violations[case_name] = str(exc)
    assert violations == {}


def test_anchor_poor_oracle_itself_admits_no_content_only_bind():
    for case_name in (
        "anchor-poor-within-container",
        "anchor-poor-cross-container",
    ):
        allowed = allowed_bind_set(_case(case_name).bundle)
        assert {bind.slot.node_id for bind in allowed} == {"separator-0"}


def test_inv1_shipped_rebind_bound_set_is_subset_of_shared_corpus_oracle():
    for case in priority2_shared_corpus().cases:
        observed = _observed_case(case)
        try:
            assert_bound_subset_and_disjoint(
                observed.binds, allowed_bind_set(case.bundle)
            )
            assert_insert_coverage_not_silent(case.bundle, observed)
        except AssertionError as exc:
            raise AssertionError(
                f"case={case.name!r} seed={case.bundle.config.seed} "
                f"config={case.bundle.config!r}: {exc}"
            ) from exc


def test_inv1_cross_slot_merge_fails_both_affected_nodes_as_global_conflict():
    report = _result(_case("merge-cross-slot-seam")).report
    affected = {
        node.node_id: (node.bound, node.reason)
        for node in report.nodes
        if node.node_id in {"l0", "l1"}
    }
    assert affected == {
        "l0": (False, "global-conflict"),
        "l1": (False, "global-conflict"),
    }


def _assert_required_inv2_case(case_name: str) -> None:
    case = _case(case_name)
    expected = set(required_inv2_binds(priority2_shared_corpus())[case_name])
    observed = {AllowedBind(bind.slot, bind.fresh_atom_ids) for bind in _observed(case)}
    assert expected <= observed, (
        f"{case_name}: missing required bind(s) {expected - observed}"
    )


def test_inv2_interior_char_substitution_with_unchanged_boundaries_binds():
    _assert_required_inv2_case("inv2-interior-char-sub")


def test_inv2_atom_split_with_unchanged_tokens_binds_exact_descendant_tuple():
    _assert_required_inv2_case("split-token-boundary")


def test_inv2_atom_merge_with_unambiguous_ownership_binds():
    _assert_required_inv2_case("inv2-atom-merge")
