"""S4.7 item-2 Component 0(b): fixture materialization and generator gates.

These tests are the gate before INV-1…INV-7 may consume generated truth.  They exercise every
perturbation class, the required risky compositions, final relation cardinalities, independent
relation-law closure, deterministic replay, old-map anchor provenance, tokenless ownership cases,
and the geometry transform contract.
"""

from __future__ import annotations

import ast
import copy
import inspect
from dataclasses import replace
from pathlib import Path

import pytest

from engine.structure.atom_store import (
    assert_reference_integrity,
    assert_stream_roundtrip,
)
from engine.structure.geom_regate import MODE_TIE_BREAK
from engine.structure.rebind import (
    RebindContext,
    fingerprint_slot,
    normalized_slot_tokens,
)
from engine.structure.structure_map import structure_map_from_json
from harness.materialize import (
    AtomSeed,
    DriftConfig,
    DriftOperation,
    DriftSuiteConfig,
    FixtureBuildError,
    FixtureSpec,
    NodeSeed,
    REQUIRED_COMPOSITION_TAGS,
    component0_case_matrix,
    component0_fixture_spec,
    materialize_fixture,
    seeded_supplemental_config,
    validate_fixture_bundle,
)
from harness.relation import check_relation_laws


def test_fixture_spec_validation_indexes_canonical_positions_without_list_scans():
    from harness.materialize import _validate_spec

    source = inspect.getsource(_validate_spec)
    assert "atom_keys.index(" not in source


def test_fixture_spec_validation_supports_registered_depth_without_recursion():
    depth = 2_500
    nodes = tuple(
        NodeSeed(
            f"container-{index}",
            "section",
            "container",
            children=(
                (f"container-{index + 1}",)
                if index + 1 < depth
                else ("leaf",)
            ),
        )
        for index in range(depth)
    ) + (NodeSeed("leaf", "block", "leaf", body=("a0",)),)
    spec = FixtureSpec(
        "container-0",
        nodes,
        (AtomSeed("a0", "alpha beta", "leaf", "body"),),
        require_tokenless_cases=False,
    )
    assert len(spec.nodes) == depth + 1


def _case(name: str) -> DriftConfig:
    return next(case for case in component0_case_matrix().cases if case.name == name)


def _atom_by_id(stream):
    return {atom.atom_id: atom for atom in stream.atoms}


def _fresh_descendants(bundle, old_id: str) -> set[str]:
    return {fresh for old, fresh in bundle.relation.pairs if old == old_id}


def _old_id(key: str) -> str:
    return f"old-{key}"


def test_shared_spec_contains_tokenless_atoms_both_interior_and_slot_final():
    spec = component0_fixture_spec()
    by_key = {atom.key: atom for atom in spec.atoms}
    l0 = next(node for node in spec.nodes if node.node_id == "l0")
    assert by_key["p0"].text == "—" and l0.body.index("p0") < len(l0.body) - 1
    assert by_key["p1"].text == "…" and l0.body[-1] == "p1"


def test_mandatory_case_matrix_covers_every_op_and_required_composition():
    suite = component0_case_matrix()
    covered_ops = {
        operation.op for case in suite.cases for operation in case.operations
    }
    covered_tags = {tag for case in suite.cases for tag in case.composition_tags}
    assert covered_ops == {
        "char_sub",
        "drop",
        "insert",
        "duplicate",
        "split",
        "merge",
        "move",
    }
    assert REQUIRED_COMPOSITION_TAGS <= covered_tags


def test_incomplete_case_matrix_is_rejected_before_materialization():
    with pytest.raises(ValueError, match="drift suite is incomplete"):
        DriftSuiteConfig(
            cases=(DriftConfig("only-one", 1, (_case("char-sub").operations[0],)),)
        )


def test_composition_tag_cannot_claim_an_operation_pair_the_case_does_not_contain():
    with pytest.raises(ValueError, match="requires ops"):
        DriftConfig(
            "lying-tag",
            2,
            (_case("char-sub").operations[0],),
            composition_tags=frozenset({"merge×repeat"}),
        )


@pytest.mark.parametrize(
    "case", component0_case_matrix().cases, ids=lambda case: case.name
)
def test_every_mandatory_case_materializes_a_lawful_distinct_generation(case):
    bundle = materialize_fixture(component0_fixture_spec(), case)
    assert check_relation_laws(bundle.relation, list(bundle.events)) == []
    assert set(bundle.relation.old_order).isdisjoint(bundle.relation.fresh_order)
    assert (
        tuple(atom.atom_id for atom in bundle.old_canonical.atoms)
        == bundle.relation.old_order
    )
    assert (
        tuple(atom.atom_id for atom in bundle.fresh_canonical.atoms)
        == bundle.relation.fresh_order
    )
    for operation in case.operations:
        assert bundle.stats.count(operation.op) >= 1


def test_split_relation_is_one_to_many_and_token_sequence_is_unchanged():
    bundle = materialize_fixture(
        component0_fixture_spec(), _case("split-token-boundary")
    )
    descendants = _fresh_descendants(bundle, _old_id("a1"))
    assert len(descendants) == 2
    fresh = _atom_by_id(bundle.fresh_canonical)
    assert [
        fresh[atom_id].text
        for atom_id in bundle.relation.fresh_order
        if atom_id in descendants
    ] == [
        "gamma ",
        "delta ",
    ]
    assert normalized_slot_tokens(["gamma delta "]) == normalized_slot_tokens(
        ["gamma ", "delta "]
    )


def test_duplicate_relation_is_one_to_many_without_reusing_an_atom_id():
    bundle = materialize_fixture(component0_fixture_spec(), _case("duplicate"))
    descendants = _fresh_descendants(bundle, _old_id("b0"))
    assert len(descendants) == 2
    assert len(bundle.relation.fresh_order) == len(set(bundle.relation.fresh_order))


def test_merge_repeat_relation_is_many_to_many_with_complete_ancestry():
    bundle = materialize_fixture(component0_fixture_spec(), _case("merge-repeat"))
    b0 = _fresh_descendants(bundle, _old_id("b0"))
    b1 = _fresh_descendants(bundle, _old_id("b1"))
    assert b0 == b1 and len(b0) == 2  # merge product plus its duplicate
    for fresh in b0:
        assert {
            old for old, candidate in bundle.relation.pairs if candidate == fresh
        } == {
            _old_id("b0"),
            _old_id("b1"),
        }


def test_drop_and_insert_keep_null_sides_explicit():
    bundle = materialize_fixture(component0_fixture_spec(), _case("drop-insert"))
    assert _old_id("c1") in bundle.relation.deleted
    assert _fresh_descendants(bundle, _old_id("c1")) == set()
    assert len(bundle.relation.inserted) == 1
    inserted = next(iter(bundle.relation.inserted))
    assert not {old for old, fresh in bundle.relation.pairs if fresh == inserted}
    assert inserted in bundle.insertion_ownership
    assert bundle.insertion_ownership[inserted] == {("l2", "body")}


def test_insert_ownership_distinguishes_interior_from_a_true_slot_seam():
    spec = component0_fixture_spec()
    interior = DriftConfig(
        "interior-insert",
        701,
        (
            DriftOperation(
                "insert", outputs=("inside",), texts=("inside l0",), position=2
            ),
        ),
    )
    interior_bundle = materialize_fixture(spec, interior)
    interior_id = next(iter(interior_bundle.relation.inserted))
    assert interior_bundle.insertion_ownership[interior_id] == {("l0", "body")}

    seam_bundle = materialize_fixture(spec, _case("split-boundary"))
    seam_id = next(iter(seam_bundle.relation.inserted))
    assert seam_bundle.insertion_ownership[seam_id] == {
        ("l0", "body"),
        ("l1", "body"),
        None,
    }


def test_move_preserves_ancestry_and_records_the_planted_final_destination():
    bundle = materialize_fixture(
        component0_fixture_spec(), _case("move-container-edge")
    )
    fresh = _atom_by_id(bundle.fresh_canonical)
    assert [fresh[atom_id].text for atom_id in bundle.relation.fresh_order[-2:]] == [
        "epsilon zeta ",
        "eta theta ",
    ]
    assert {_old_id("b0"), _old_id("b1")} <= bundle.relation.moved
    assert len(_fresh_descendants(bundle, _old_id("b0"))) == 1


def test_move_out_then_back_is_not_reported_as_realized_final_drift():
    config = DriftConfig(
        "net-zero-move",
        705,
        (
            DriftOperation("move", ("b0",), position=9),
            DriftOperation("move", ("b0",), position=5),
        ),
    )
    bundle = materialize_fixture(component0_fixture_spec(), config)
    assert [event.op for event in bundle.events].count("move") == 2
    assert bundle.relation.moved == frozenset()
    assert bundle.stats.generated_count("move") == 2
    assert bundle.stats.count("move") == 0


def test_same_seed_and_config_replays_byte_identical_truth():
    spec = component0_fixture_spec()
    config = _case("split-boundary")
    first = materialize_fixture(spec, config)
    second = materialize_fixture(spec, config)
    assert first.events == second.events
    assert first.relation == second.relation
    assert first.old_map.doc == second.old_map.doc
    assert first.fresh_canonical == second.fresh_canonical


def test_seeded_random_supplement_replays_and_realizes_every_enabled_class():
    spec = component0_fixture_spec()
    config = seeded_supplemental_config(spec, seed=424242)
    replay = seeded_supplemental_config(spec, seed=424242)
    assert config == replay
    bundle = materialize_fixture(spec, config)
    assert check_relation_laws(bundle.relation, list(bundle.events)) == []
    assert {op.op for op in config.operations} == {
        "char_sub",
        "drop",
        "insert",
        "duplicate",
        "split",
        "merge",
        "move",
    }
    assert all(
        bundle.stats.count(op) == 1
        for op in {"char_sub", "drop", "insert", "duplicate", "split", "merge", "move"}
    )


@pytest.mark.parametrize(
    "enabled",
    [
        frozenset({op})
        for op in ("char_sub", "drop", "insert", "duplicate", "split", "merge", "move")
    ],
)
def test_seeded_random_supplement_operations_are_independently_toggleable(enabled):
    config = seeded_supplemental_config(
        component0_fixture_spec(), seed=505, enabled_ops=enabled
    )
    assert {operation.op for operation in config.operations} == set(enabled)
    bundle = materialize_fixture(component0_fixture_spec(), config)
    assert bundle.stats.count(next(iter(enabled))) == 1


def test_composed_operations_must_be_explicitly_permitted():
    with pytest.raises(ValueError, match="explicitly permitted"):
        DriftConfig(
            "undeclared",
            8,
            (
                DriftOperation("drop", ("c1",)),
                DriftOperation(
                    "insert", outputs=("new",), texts=("new text",), position=9
                ),
            ),
        )


def test_materializer_rejects_active_output_label_reuse_before_truth_is_built():
    config = DriftConfig(
        "label-reuse",
        707,
        (DriftOperation("duplicate", ("b0",), ("a0",)),),
    )
    with pytest.raises(FixtureBuildError, match="output label.*already active"):
        materialize_fixture(component0_fixture_spec(), config)


def test_seed_changes_ids_without_changing_the_explicit_drift_content():
    spec = component0_fixture_spec()
    config = _case("char-sub")
    other = replace(config, seed=config.seed + 1)
    first = materialize_fixture(spec, config)
    second = materialize_fixture(spec, other)
    assert first.relation.fresh_order != second.relation.fresh_order
    assert [atom.text for atom in first.fresh_canonical.atoms] == [
        atom.text for atom in second.fresh_canonical.atoms
    ]


def test_char_sub_rejects_an_arbitrary_non_ocr_replacement():
    config = DriftConfig(
        "not-ocr",
        708,
        (
            DriftOperation(
                "char_sub", ("a0",), ("rewritten",), ("entirely different text",)
            ),
        ),
    )
    with pytest.raises(FixtureBuildError, match="OCR-class"):
        materialize_fixture(component0_fixture_spec(), config)


def test_old_map_fingerprint_contract_matches_production_but_is_derived_before_drift():
    bundle = materialize_fixture(component0_fixture_spec(), _case("char-sub"))
    raw_l0 = next(
        node for node in bundle.old_map.doc["nodes"] if node["node_id"] == "l0"
    )
    stored = raw_l0["rebind_anchors"]["content_fingerprint"]["body"]
    old_texts = ["alpha beta ", "—", "gamma delta ", "…"]
    production = fingerprint_slot(normalized_slot_tokens(old_texts))
    assert stored == {
        "algo_id": production.algo_id,
        "normalizer_id": production.normalizer_id,
        "k": production.k,
        "token_count": production.token_count,
        "shingles": list(production.shingles),
    }
    # Fresh char-sub content is different; a careless fresh-truth rebuild would change this value.
    fresh_texts = [atom.text for atom in bundle.fresh_canonical.atoms]
    fresh_fp = fingerprint_slot(normalized_slot_tokens(fresh_texts[1:5]))
    assert list(fresh_fp.shingles) != stored["shingles"]


def test_bundle_validator_rejects_a_map_not_bound_to_the_supplied_old_canonical():
    bundle = materialize_fixture(component0_fixture_spec(), _case("char-sub"))
    tampered_doc = copy.deepcopy(bundle.old_map.doc)
    tampered_doc["manifest"]["canonical_content_hash"] = "0" * 64
    tampered = replace(bundle, old_map=structure_map_from_json(tampered_doc))
    with pytest.raises(FixtureBuildError, match="canonical_content_hash"):
        validate_fixture_bundle(tampered)


def test_bundle_validator_runs_the_aggregate_structure_gate_not_only_hash_checks():
    bundle = materialize_fixture(component0_fixture_spec(), _case("char-sub"))
    tampered_doc = copy.deepcopy(bundle.old_map.doc)
    tampered_doc["handle_policies"] = {}
    tampered = replace(bundle, old_map=structure_map_from_json(tampered_doc))
    with pytest.raises(
        FixtureBuildError, match="not globally valid.*POLICY_UNRESOLVED"
    ):
        validate_fixture_bundle(tampered)


def test_bundle_validator_enforces_the_persisted_tier1_shape():
    bundle = materialize_fixture(component0_fixture_spec(), _case("char-sub"))
    tampered_doc = copy.deepcopy(bundle.old_map.doc)
    del tampered_doc["manifest"]["profile_version"]
    tampered = replace(bundle, old_map=structure_map_from_json(tampered_doc))
    with pytest.raises(FixtureBuildError, match="not Tier-1 valid.*profile_version"):
        validate_fixture_bundle(tampered)


def test_materialized_bundle_is_accepted_by_the_real_rebind_context_baseline_gate():
    bundle = materialize_fixture(component0_fixture_spec(), _case("char-sub"))
    context = RebindContext(
        bundle.old_map,
        bundle.old_streams,
        bundle.fresh_streams,
        geometry_mode=bundle.geometry_mode,
    )
    assert context.old_canonical is bundle.old_canonical
    assert context.fresh_canonical is bundle.fresh_canonical


def test_materialized_witnesses_are_roundtrip_valid_and_resolve_every_backlink():
    bundle = materialize_fixture(component0_fixture_spec(), _case("char-sub"))
    for witness in bundle.old_witnesses + bundle.fresh_witnesses:
        assert_stream_roundtrip(witness)
    assert_reference_integrity(
        bundle.old_canonical, {w.stream_id: w for w in bundle.old_witnesses}
    )
    assert_reference_integrity(
        bundle.fresh_canonical, {w.stream_id: w for w in bundle.fresh_witnesses}
    )


@pytest.mark.parametrize(
    "name",
    [
        "char-sub",
        "duplicate",
        "split-token-boundary",
        "merge-repeat",
        "move-container-edge",
        "drop-insert",
    ],
)
def test_geometry_mode_materializes_present_transformed_geometry(name):
    config = replace(_case(name), geometry_mode=MODE_TIE_BREAK)
    bundle = materialize_fixture(component0_fixture_spec(), config)
    assert all(atom.geom.present for atom in bundle.old_canonical.atoms)
    assert all(atom.geom.present for atom in bundle.fresh_canonical.atoms)


def test_char_sub_preserves_geometry_exactly():
    bundle = materialize_fixture(
        component0_fixture_spec(),
        replace(_case("char-sub"), geometry_mode=MODE_TIE_BREAK),
    )
    old = _atom_by_id(bundle.old_canonical)[_old_id("a0")]
    fresh_id = next(iter(_fresh_descendants(bundle, _old_id("a0"))))
    fresh = _atom_by_id(bundle.fresh_canonical)[fresh_id]
    assert fresh.geom == old.geom


def test_duplicate_gets_a_distinct_physical_box():
    bundle = materialize_fixture(
        component0_fixture_spec(),
        replace(_case("duplicate"), geometry_mode=MODE_TIE_BREAK),
    )
    fresh = _atom_by_id(bundle.fresh_canonical)
    boxes = {
        fresh[atom_id].geom.bbox
        for atom_id in _fresh_descendants(bundle, _old_id("b0"))
    }
    assert len(boxes) == 2


def test_duplicate_transform_emits_same_page_and_distinct_page_variants():
    spec = component0_fixture_spec()
    same = materialize_fixture(
        spec, replace(_case("duplicate"), geometry_mode=MODE_TIE_BREAK)
    )
    same_atoms = _atom_by_id(same.fresh_canonical)
    assert {
        same_atoms[atom_id].geom.page
        for atom_id in _fresh_descendants(same, _old_id("b0"))
    } == {1}

    distinct_config = DriftConfig(
        "duplicate-distinct-page",
        702,
        (DriftOperation("duplicate", ("b0",), ("b0-page2",), output_pages=(2,)),),
        geometry_mode=MODE_TIE_BREAK,
    )
    distinct = materialize_fixture(spec, distinct_config)
    distinct_atoms = _atom_by_id(distinct.fresh_canonical)
    assert {
        distinct_atoms[atom_id].geom.page
        for atom_id in _fresh_descendants(distinct, _old_id("b0"))
    } == {1, 2}


def test_multiple_duplicate_outputs_receive_distinct_ids_and_boxes():
    config = DriftConfig(
        "duplicate-two",
        703,
        (DriftOperation("duplicate", ("b0",), ("copy-1", "copy-2")),),
        geometry_mode=MODE_TIE_BREAK,
    )
    bundle = materialize_fixture(component0_fixture_spec(), config)
    atoms = _atom_by_id(bundle.fresh_canonical)
    descendants = _fresh_descendants(bundle, _old_id("b0"))
    assert len(descendants) == 3
    assert len({atoms[atom_id].geom.bbox for atom_id in descendants}) == 3


def test_split_partitions_and_merge_unions_the_source_box():
    split = materialize_fixture(
        component0_fixture_spec(),
        replace(_case("split-token-boundary"), geometry_mode=MODE_TIE_BREAK),
    )
    old_box = _atom_by_id(split.old_canonical)[_old_id("a1")].geom.bbox
    fresh = _atom_by_id(split.fresh_canonical)
    parts = sorted(
        (
            fresh[atom_id].geom.bbox
            for atom_id in _fresh_descendants(split, _old_id("a1"))
        ),
        key=lambda box: box[0],
    )
    assert min(box[0] for box in parts) == old_box[0]
    assert max(box[2] for box in parts) == old_box[2]
    assert parts[0][2] == parts[1][0]

    merged = materialize_fixture(
        component0_fixture_spec(),
        replace(_case("merge-repeat"), geometry_mode=MODE_TIE_BREAK),
    )
    old_atoms = _atom_by_id(merged.old_canonical)
    expected = (
        min(
            old_atoms[_old_id("b0")].geom.bbox[0], old_atoms[_old_id("b1")].geom.bbox[0]
        ),
        min(
            old_atoms[_old_id("b0")].geom.bbox[1], old_atoms[_old_id("b1")].geom.bbox[1]
        ),
        max(
            old_atoms[_old_id("b0")].geom.bbox[2], old_atoms[_old_id("b1")].geom.bbox[2]
        ),
        max(
            old_atoms[_old_id("b0")].geom.bbox[3], old_atoms[_old_id("b1")].geom.bbox[3]
        ),
    )
    merged_fresh = _atom_by_id(merged.fresh_canonical)
    assert {
        merged_fresh[atom_id].geom.bbox
        for atom_id in _fresh_descendants(merged, _old_id("b0"))
    } >= {expected}


def test_move_rehomes_boxes_and_insert_gets_an_interpolated_box():
    moved = materialize_fixture(
        component0_fixture_spec(),
        replace(_case("move-container-edge"), geometry_mode=MODE_TIE_BREAK),
    )
    old = _atom_by_id(moved.old_canonical)[_old_id("b0")]
    fresh_id = next(iter(_fresh_descendants(moved, _old_id("b0"))))
    assert _atom_by_id(moved.fresh_canonical)[fresh_id].geom.bbox != old.geom.bbox

    inserted = materialize_fixture(
        component0_fixture_spec(),
        replace(_case("drop-insert"), geometry_mode=MODE_TIE_BREAK),
    )
    inserted_atom = _atom_by_id(inserted.fresh_canonical)[
        next(iter(inserted.relation.inserted))
    ]
    assert (
        inserted_atom.geom.present
        and inserted_atom.geom.bbox[3] > inserted_atom.geom.bbox[1]
    )


def test_noop_move_and_byte_identical_drop_insert_are_rejected_as_fixture_errors():
    spec = component0_fixture_spec()
    noop = DriftConfig("noop", 900, (DriftOperation("move", ("b0", "b1"), position=5),))
    with pytest.raises(FixtureBuildError, match="unchanged"):
        materialize_fixture(spec, noop)

    forbidden = DriftConfig(
        "forbidden",
        901,
        (
            DriftOperation("drop", ("c1",)),
            DriftOperation(
                "insert", outputs=("copy",), texts=("lambda mu",), position=9
            ),
        ),
        permitted_compositions=frozenset({("drop", "insert")}),
    )
    with pytest.raises(FixtureBuildError, match="forbidden-composition"):
        materialize_fixture(spec, forbidden)


def test_geometry_hash_is_conditionally_enforced_by_bundle_mode():
    bundle = materialize_fixture(
        component0_fixture_spec(),
        replace(_case("char-sub"), geometry_mode=MODE_TIE_BREAK),
    )
    tampered_doc = copy.deepcopy(bundle.old_map.doc)
    tampered_doc["manifest"]["canonical_geometry_hash"] = "f" * 64
    tampered = replace(bundle, old_map=structure_map_from_json(tampered_doc))
    with pytest.raises(FixtureBuildError, match="canonical_geometry_hash"):
        validate_fixture_bundle(tampered)

    # The same mismatch is deliberately outside the no-geometry baseline contract.
    no_geom = materialize_fixture(component0_fixture_spec(), _case("char-sub"))
    no_geom_doc = copy.deepcopy(no_geom.old_map.doc)
    no_geom_doc["manifest"]["canonical_geometry_hash"] = "f" * 64
    validate_fixture_bundle(
        replace(no_geom, old_map=structure_map_from_json(no_geom_doc))
    )


def test_resegmentation_stats_count_original_participants_not_events():
    bundle = materialize_fixture(component0_fixture_spec(), _case("merge-repeat"))
    assert bundle.stats.resegmented_old_ids == {_old_id("b0"), _old_id("b1")}
    assert bundle.stats.count("merge") == 1
    assert bundle.stats.count("duplicate") == 1


def test_heavy_resegmentation_case_meets_the_preregistered_thirty_percent_floor():
    bundle = materialize_fixture(
        component0_fixture_spec(), _case("heavy-resegmentation")
    )
    assert (
        len(bundle.stats.resegmented_old_ids) / len(bundle.relation.old_order) >= 0.30
    )


def test_split_then_merge_back_is_reported_generated_but_not_realized():
    config = DriftConfig(
        "net-zero-resegmentation",
        704,
        (
            DriftOperation("split", ("a0",), ("left", "right"), ("alpha ", "beta ")),
            DriftOperation("merge", ("left", "right"), ("whole-again",)),
        ),
        permitted_compositions=frozenset({("merge", "split")}),
    )
    bundle = materialize_fixture(component0_fixture_spec(), config)
    assert [event.op for event in bundle.events].count("split") == 1
    assert [event.op for event in bundle.events].count("merge") == 1
    assert bundle.stats.resegmented_old_ids == frozenset()
    assert bundle.stats.generated_count("split") == 1
    assert bundle.stats.generated_count("merge") == 1
    assert bundle.stats.count("split") == 0
    assert bundle.stats.count("merge") == 0


def test_cross_slot_merge_preserves_both_slot_lineages_for_the_conflict_oracle():
    bundle = materialize_fixture(
        component0_fixture_spec(), _case("merge-cross-slot-seam")
    )
    descendants = _fresh_descendants(bundle, _old_id("p1"))
    assert descendants == _fresh_descendants(bundle, _old_id("b0"))
    assert len(descendants) == 1
    merged_id = next(iter(descendants))
    assert {old for old, fresh in bundle.relation.pairs if fresh == merged_id} == {
        _old_id("p1"),
        _old_id("b0"),
    }


def test_cross_page_merge_is_an_explicitly_excluded_geometry_composition():
    spec = component0_fixture_spec()
    atoms = tuple(
        replace(atom, page=2) if atom.key == "b1" else atom for atom in spec.atoms
    )
    cross_page = replace(spec, atoms=atoms)
    for config in (
        _case("merge-repeat"),
        replace(_case("merge-repeat"), geometry_mode=MODE_TIE_BREAK),
    ):
        with pytest.raises(FixtureBuildError, match="cross-page"):
            materialize_fixture(cross_page, config)


def test_cross_page_insert_is_excluded_even_when_geometry_boxes_are_absent():
    spec = component0_fixture_spec()
    atoms = tuple(
        replace(atom, page=2) if atom.key in {"b1", "s0", "c0", "c1"} else atom
        for atom in spec.atoms
    )
    cross_page = replace(spec, atoms=atoms)
    config = DriftConfig(
        "cross-page-insert",
        706,
        (DriftOperation("insert", outputs=("bad",), texts=("bad seam",), position=6),),
    )
    with pytest.raises(FixtureBuildError, match="cross pages"):
        materialize_fixture(cross_page, config)


def test_harness_has_no_production_rebind_import_or_direct_reference_fold():
    # Oracle independence is executable: Component 0 may use neutral structure models/validators,
    # but never the production rebind implementation it will judge.  The mutation engine also must
    # not call compose_events directly; only check_relation_laws invokes that independent interpreter.
    harness_dir = Path(__file__).resolve().parents[1] / "harness"
    for filename in ("materialize.py", "relation.py"):
        source = (harness_dir / filename).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        }
        assert "engine.structure.rebind" not in imported
        if filename == "materialize.py":
            assert not any(
                isinstance(node, ast.Name) and node.id in {"compose_events", "rebind"}
                for node in ast.walk(tree)
            )
