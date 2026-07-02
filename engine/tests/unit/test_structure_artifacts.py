"""``engine.structure`` S0.1 skeleton — schema-version constants + fixed artifact locations.

Asserts the package imports, the three persisted layers each expose an independent integer
schema version, and the artifact accessors resolve to their pinned work-tree locations *inside*
the workspace (ENGINE_STRUCTURE_PLAN §11.1–§11.3): atoms under the ``data`` area, the structure
map and relations at the work root. The containment guard on ``resolve_root`` itself (the
work-root resolver these accessors ride on) is exercised in ``test_workspace.py``, where it lives.

Invariants (each proven red on violation below — red-first, ENGINE_STRUCTURE_PLAN §9). That the
package imports as a real namespace needs no separate test: every test here imports it, so a
broken package fails the whole module at collection.
  - each persisted layer exposes a positive, non-bool int schema version — 0 fails ``>= 1``,
    ``True`` fails the bool exclusion (``test_each_layer_…``).
  - the three versions are independently addressable on the public surface — drop a constant from
    the package re-export and ``test_the_three_versions_…`` + ``test_all_public_exports_…`` go red.
  - accessors resolve to their §11 locations (atoms→``data/atoms``, map/relations→work root) and
    the three are distinct — a wrong location fails the ``==`` (the four location tests).
  - every ``__all__`` name imports as ``structure.X`` — a broken re-export AttributeErrors in
    ``test_all_public_exports_…`` rather than passing green (feedback_validate_bindings).
"""

from __future__ import annotations

import pytest

import engine.structure as structure
from engine.paths import BookWorkspace

VERSION_NAMES = (
    "ATOM_STORE_SCHEMA_VERSION",
    "STRUCTURE_MAP_SCHEMA_VERSION",
    "RELATION_STORE_SCHEMA_VERSION",
)


@pytest.mark.parametrize("name", VERSION_NAMES)
def test_each_layer_has_an_independent_positive_int_version(name):
    version = getattr(structure, name)
    # bool is an int subclass — exclude it so a stray True/False can't pass as a version.
    assert isinstance(version, int) and not isinstance(version, bool)
    assert version >= 1


def test_the_three_versions_are_independently_addressable():
    # M3: each layer's schema version is its own module-level name, so bumping one never moves
    # another. Their *values* coincide at v1 — a value-distinctness assertion would be hollow — so
    # the real invariant is that all three are present, distinct names on the package's public
    # surface, independently referenceable. That is what lets S1.5/S4.4/S7.1c bump one in isolation.
    # Red-proof: drop any of these names from __init__'s re-export and both this and
    # test_all_public_exports_… go red. No value-distinctness assertion — values coincide at v1,
    # so that would test nothing; independence is that each is a separately-rebindable name.
    assert set(VERSION_NAMES) <= set(structure.__all__)          # each is part of the exported API
    assert all(hasattr(structure, n) for n in VERSION_NAMES)     # each resolves to its own binding


def test_atoms_dir_is_under_the_data_area(tmp_path):
    ws = BookWorkspace.for_book("demo", tmp_path)
    p = structure.atoms_dir(ws)
    assert p == ws.data / "atoms"
    assert p.is_relative_to(ws.root)


def test_structure_map_is_at_the_work_root(tmp_path):
    ws = BookWorkspace.for_book("demo", tmp_path)
    p = structure.structure_map_path(ws)
    assert p == ws.root / "structure_map.json"
    assert p.is_relative_to(ws.root)
    # at the root, NOT nested under an area — the §11.2 placement
    assert p.parent == ws.root


def test_relations_is_at_the_work_root(tmp_path):
    ws = BookWorkspace.for_book("demo", tmp_path)
    p = structure.relations_path(ws)
    assert p == ws.root / "relations.json"
    assert p.is_relative_to(ws.root)
    assert p.parent == ws.root


def test_the_three_artifact_locations_are_distinct(tmp_path):
    ws = BookWorkspace.for_book("demo", tmp_path)
    locations = {
        structure.atoms_dir(ws),
        structure.structure_map_path(ws),
        structure.relations_path(ws),
    }
    assert len(locations) == 3


def test_all_public_exports_resolve_on_the_package():
    # Every name in __all__ actually imports as ``structure.X``. A re-export listed in __all__ but
    # dropped from the import block would AttributeError here, not pass green — the four string
    # constants (ATOMS_AREA, ATOMS_SUBDIR, STRUCTURE_MAP_FILENAME, RELATIONS_FILENAME) are
    # otherwise reached only transitively through the accessors (feedback_validate_bindings).
    for name in structure.__all__:
        assert hasattr(structure, name), f"{name!r} is in __all__ but not importable from engine.structure"


# The specific public names each structure concern contributes. The bounded gate
# (test_public_export_surface_is_bounded) pins __all__ to an exact allowlist and the test above proves
# every __all__ name imports — but both stay green if a real export is dropped from __all__ *and* the
# allowlist together. These per-concern lists pin that the specific names survive that consistent
# removal, so it still reds. Consolidated here from the former per-module test_public_exports_resolve /
# test_handle_surface_is_exported / test_structure_validation_error_is_exported copies (audit 4.8).
PUBLIC_SURFACE_BY_CONCERN = {
    "atoms": ("Atom", "Geom", "AtomDerivation", "duplicate_atom_ids"),
    "capture": ("capture_witness", "build_canonical", "align_streams", "assert_capture_tiles",
                "PAGE_UNMAPPED", "PROCESSING_SCOPE_INCLUDED", "PROCESSING_SCOPE_EXCLUDED"),
    "roundtrip": ("hash_raw", "reconstruct_raw", "ReversibleTransform", "apply_forward",
                  "apply_inverse", "is_reversible", "verify_atom_roundtrip"),
    "typed": ("TypedAtom", "typed_projection", "ReviewItem", "CompletenessReport", "check_completeness"),
    "classify": ("BlockClassifier", "BlockClassification", "DegenerateBlockClassifier",
                 "UNKNOWN", "DEGENERATE_CLASSIFIER_NAME"),
    "handles": ("render_handle", "resolve", "Alias"),
    "projection": ("Node", "ContainerNode", "LeafNode", "FurnitureAtom", "ProjectionMap",
                   "validate_projection", "StructureValidationError", "mint_node_id"),
    "structure_map": ("StructureMap", "StreamAtomReader", "validate_structure_map",
                      "load_structure_map", "write_structure_map", "render_structure_map",
                      "build_manifest", "schema_version_const", "assert_schema_born"),
}


@pytest.mark.parametrize("concern", sorted(PUBLIC_SURFACE_BY_CONCERN))
def test_public_names_per_concern_resolve(concern):
    for name in PUBLIC_SURFACE_BY_CONCERN[concern]:
        assert name in structure.__all__, f"{name!r} ({concern}) missing from structure.__all__"
        assert hasattr(structure, name), f"{name!r} ({concern}) not importable from engine.structure"


# --- S4.0 / B-1: structure-map + relation-store stale classes; schema_status map (inv 12a) ------ #

# Every stale class the structure core exports. M3's whole point is that a lineage stale-check names
# *which* layer changed, so these must be pairwise-distinct wire strings.
STALE_CLASS_NAMES = (
    "ATOM_STORE_STALE_CLASS",
    "STRUCTURE_MAP_STALE_CLASS",
    "RELATION_STORE_STALE_CLASS",
    "RESOURCE_STALE_CLASS",
    "NORMALIZER_STALE_CLASS",
)

# The relation surface S4 is *allowed* to expose: two inert layer-identity constants + the path
# accessors. NONE is a relation-store loader/reader — that behaviour is deferred to S7.1c. This is
# the inertness binding (inv 12a), not prose: a new relation-y public name breaks the equality.
ALLOWED_RELATION_EXPORTS = {
    "RELATION_STORE_SCHEMA_VERSION",
    "RELATION_STORE_STALE_CLASS",
    "RELATIONS_FILENAME",
    "relations_path",
}


@pytest.mark.parametrize("name", ("STRUCTURE_MAP_STALE_CLASS", "RELATION_STORE_STALE_CLASS"))
def test_s4_stale_class_is_a_nonempty_exported_string(name):
    # inv 12a: both new stale classes exist, are non-empty wire strings, and are on the public
    # surface. A dropped re-export AttributeErrors here rather than passing green (validate_bindings).
    assert name in structure.__all__, f"{name!r} not exported from engine.structure"
    value = getattr(structure, name)
    assert isinstance(value, str) and value.strip(), f"{name!r} is not a non-empty string"


def test_all_stale_classes_are_pairwise_distinct():
    # inv 12a: a schema change to one layer must be able to name *that* layer — so every exported
    # stale class is a distinct wire string. Red-proof: alias STRUCTURE_MAP_STALE_CLASS to the
    # atom-store value and this length-equality drops.
    values = [getattr(structure, n) for n in STALE_CLASS_NAMES]
    assert all(isinstance(v, str) and v.strip() for v in values)
    assert len(set(values)) == len(values), f"stale classes collide: {values}"


def test_no_relation_named_export_beyond_the_inert_set():
    # inv 12a (inertness), TARGETED check: the relation surface named with "relation" is exactly the
    # two inert constants + path accessors — no relation-named loader. This is a readable, specific
    # signal, but it is a name substring, so it cannot catch a relation/C-layer loader exported under
    # a name lacking "relation" (load_graph, GraphStore, edges_path). The TOTAL backstop for that is
    # test_public_export_surface_is_bounded below (R2-02): any new export, however named, trips it.
    relationy = {n for n in structure.__all__ if "relation" in n.lower()}
    assert relationy == ALLOWED_RELATION_EXPORTS, (
        "a relation-store loader/reader leaked into engine.structure's S4 surface (inertness, inv 12a):\n"
        f"  unexpected: {relationy - ALLOWED_RELATION_EXPORTS}\n"
        f"  missing:    {ALLOWED_RELATION_EXPORTS - relationy}"
    )


# --- R2-02 bounded-surface guard: the public export set is fixed, amendment-gated ---------------- #

# The exact public surface of engine.structure. The §1.5 amendment rule: any export added during S4
# (production OR test-only helper promoted to the package) must be added here in the same commit —
# so a leak of ANY kind (a relation/C-layer loader under any name, a smuggled book-shaped helper, an
# accidental re-export) trips test_public_export_surface_is_bounded, not just relation-named ones.
# Grouped as engine/structure/__init__.py groups them, newest milestones first.
EXPECTED_PUBLIC_SURFACE = frozenset(
    {
        # persisted-layer schema versions
        "ATOM_STORE_SCHEMA_VERSION",
        "STRUCTURE_MAP_SCHEMA_VERSION",
        "RELATION_STORE_SCHEMA_VERSION",
        "ATOM_STORE_STALE_CLASS",
        # S4.0 — structure-map + relation-store stale classes; schema birth-status map; EC code set
        "STRUCTURE_MAP_STALE_CLASS",
        "RELATION_STORE_STALE_CLASS",
        "SCHEMA_STATUS_PROVISIONAL",
        "SCHEMA_STATUS_BORN",
        "STRUCTURE_MAP_SCHEMA_STATUS",
        "EC",
        # S4.1 — L2 projection model (nodes + flat map + per-module validator + carrier error)
        "Node",
        "ContainerNode",
        "LeafNode",
        "FurnitureAtom",
        "ProjectionMap",
        "validate_projection",
        "StructureValidationError",
        # S4.2 — node_id identity + minting split (mint_node_id seam)
        "mint_node_id",
        # S4.3 — handle policy + rendered handles + alias records
        "Alias",
        "render_handle",
        "resolve",
        # S4.4 — structure_map.json schema + loader + manifest + born-gate + regen-guarded writer
        "StructureMap",
        "StreamAtomReader",
        "validate_structure_map",
        "load_structure_map",
        "write_structure_map",
        "render_structure_map",
        "build_manifest",
        "schema_version_const",
        "assert_schema_born",
        # S3.0 — resource + normalization-policy lineage
        "RESOURCE_LINEAGE_SCHEMA_VERSION",
        "RESOURCE_STALE_CLASS",
        "NORMALIZER_STALE_CLASS",
        # S0.1 — fixed artifact locations
        "ATOMS_AREA",
        "ATOMS_SUBDIR",
        "STRUCTURE_MAP_FILENAME",
        "RELATIONS_FILENAME",
        "atoms_dir",
        "structure_map_path",
        "relations_path",
        # S1.1 — L1 atom model
        "Atom",
        "Geom",
        "AtomDerivation",
        "duplicate_atom_ids",
        "PROCESSING_SCOPE_INCLUDED",
        "PROCESSING_SCOPE_EXCLUDED",
        # S0.4 — block-classifier seam
        "BlockClassifier",
        "BlockClassification",
        "DegenerateBlockClassifier",
        "UNKNOWN",
        "DEGENERATE_CLASSIFIER_NAME",
        # S1.2 — raw/normalized round-trip floor
        "hash_raw",
        "reconstruct_raw",
        "ReversibleTransform",
        "apply_forward",
        "apply_inverse",
        "is_reversible",
        "verify_atom_roundtrip",
        # S1.3a — raw addressed capture
        "capture_witness",
        "build_canonical",
        "align_streams",
        "assert_capture_tiles",
        "PAGE_UNMAPPED",
        # S1.4 — production round-trip gate
        "GapRecord",
        "gap_records",
        "reconstruct_source",
        "assert_no_wholesale_exclusion",
        "assert_production_roundtrip",
        "DEFAULT_MIN_INCLUDED_FRACTION",
        # S1.3b — typed projection
        "TypedAtom",
        "typed_projection",
        "ReviewItem",
        "CompletenessReport",
        "check_completeness",
        # S1.5 — persisted atom store
        "AtomStream",
        "WITNESS",
        "CANONICAL",
        "save_stream",
        "load_stream",
        "stream_path",
        "stream_ids",
        "assert_stream_roundtrip",
        "assert_atom_hashes",
        "assert_reference_integrity",
    }
)


def test_public_export_surface_is_bounded():
    # R2-02: engine.structure's public surface is exactly the amendment-gated allowlist. A new export
    # of ANY name (the complete backstop the "relation"-substring inertness check cannot provide) —
    # or a dropped one — trips this. Red-proof: add any name to __all__ without updating the set here.
    actual = set(structure.__all__)
    assert actual == EXPECTED_PUBLIC_SURFACE, (
        "engine.structure public surface drifted from the bounded allowlist (R2-02 / §1.5 amendment rule):\n"
        f"  unexpected exports: {sorted(actual - EXPECTED_PUBLIC_SURFACE)}\n"
        f"  missing exports:    {sorted(EXPECTED_PUBLIC_SURFACE - actual)}"
    )
    # __all__ carries no duplicate entries (a set-equality above would silently tolerate a dup).
    assert len(structure.__all__) == len(actual), "duplicate name(s) in engine.structure.__all__"


# --- S4.0 / B-1: structure-map schema birth-status map (§1.2.2) --------------------------------- #


def test_schema_status_map_marks_current_structure_map_version_born():
    # B-1 shipped the schema_status map pinned *provisional*; S4.5/B-6 flipped version 1 to *born*
    # after the D18 differ-fixture validated (inv 23 — the two unconditional asserts live in
    # test_structure_born_gate.py). Here we pin the map's export, shape, and post-flip state; a
    # version BUMP re-enters provisional (§1.2.2) and must update this pin alongside its own gate.
    assert "STRUCTURE_MAP_SCHEMA_STATUS" in structure.__all__
    status_map = structure.STRUCTURE_MAP_SCHEMA_STATUS
    assert isinstance(status_map, dict)
    assert status_map[structure.STRUCTURE_MAP_SCHEMA_VERSION] == structure.SCHEMA_STATUS_BORN
    # provisional and born are distinct wire strings — an alias would make the born flip (inv 23) a
    # no-op that reads green.
    assert structure.SCHEMA_STATUS_PROVISIONAL != structure.SCHEMA_STATUS_BORN
