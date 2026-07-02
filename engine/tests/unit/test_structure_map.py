"""S4.4 / B-5 — ``structure_map.json``: Tier-1 schema, two-tier loader, manifest, born-gate,
regen-guarded writer, and the **Phase-2 re-route** of every Tier-2 invariant through the public
``load_structure_map`` (s4_plan §4.2 — the loader-wiring proof).

The Phase-1 red tests for the per-module validators live with their producers
(``test_structure_projection.py`` / ``test_structure_handles.py``); here every code re-fires through
``load_structure_map(path, atom_store)`` on a perturbed copy of the conforming fixture, asserting
the **specific token in the collected payload** (never a bare raise — the X5 lesson). The negative
fixture set (`§3.B.5`) lives in ``tests/fixtures/structure/invalid/*.json``; those files pin
``schema_version: 1`` by hand and are refreshed on a version bump (inv 10's binding test is the
tripwire that forces the refresh).

Invariant map (each red-first against the named mutation; mutation cycles under
``PYTHONDONTWRITEBYTECODE=1`` / ``__pycache__`` purge, X13):
  - **inv 10** — schema ``const`` ↔ ``STRUCTURE_MAP_SCHEMA_VERSION`` (two assertions: the const
    reads back equal, and the version-derived conforming fixture Tier-1-validates). Mutation: bump
    either side without the other → red.
  - **inv 2 / 22 / 24 (Tier-1)** — container-xor-leaf ``oneOf``; ``node_class`` open (no enum);
    ``rebind_anchors`` rejects ``present``/``geom``. Mutations: a both-slots node / an ``enum`` in
    the schema / a smuggled ``geom`` key → red.
  - **inv 11 / 12b** — manifest structural completeness (Tier-1 ``required``; the S4-only manifest
    mechanism — stale COMPARISON is S8.1) + every layer stamped with its live stale class.
  - **inv 13** — ``rebind_anchors`` optional; ``{page, bbox_region}`` region validates.
  - **inv 14 / 16 / 17 + 1a/1b/26/27, 6/7, 18/19, §4.5** — the Phase-2 battery below: every
    validator code re-routed through the loader.
  - **inv 20** — dump→load→dump byte-identity; split-hash independence (a text edit moves ONLY
    ``canonical_content_hash``, a geometry edit — on a synthesized ``Geom.matched`` atom, X8 —
    moves ONLY ``canonical_geometry_hash``); atom-order sensitivity (a ``sorted()``-normalizing
    mutant reds); the producer is pinned by recomputing the hash in-test from the explicit field
    list via ``lineage._sha256_bytes(lineage._canonical(...))``.
  - **inv 21** — the regen guard: unlicensed overwrite → ``MAP_OVERWRITE_BLOCKED``; the licensed
    path (exact ``supersede_revision`` + snapshot + revision+1) succeeds; wrong revision /
    revision-skip / snapshot-clobber each blocked. Mutation: drop the ``path.exists()`` guard → red.
  - **inv 23 (B-5 slice)** — ``assert_schema_born()`` raises ``SCHEMA_NOT_BORN`` on a provisional
    or UNREGISTERED version (missing key fail-safe, P3B-11) and passes on born; the loader is
    born-agnostic (X1): it loads the conforming fixture clean with the status forced provisional.
    (The two unconditional differ-fixture asserts are B-6's, in ``test_structure_born_gate.py``.)
  - **inv 25** — the ``decision`` no-reader: an AST access-pattern scan (Subscript / Attribute /
    ``.get("decision")``) over every ``structure/*.py``, plus the planted-reader non-vacuity proof,
    plus the schema-presence positive (the conforming fixture carries a ``decision``). Mutation:
    add a ``node["decision"]`` read in ``structure_map.py`` → red.
  - **§4.3** — a live ``ResourceLineage(...).to_json()`` fragment validates against the schema's
    ``resource_lineage`` def; a shape drift (extra/renamed key) is rejected.
  - **§4.4** — the complexity smoke: reference-integrity through the counting accessor is linear
    (the mandatory two-size ratio ≈ 2, not ≈ 4). A heuristic floor; S4.7 owns the 10⁵ tier.
"""

from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path

import jsonschema
import pytest

import engine.structure as structure
from engine.errors import MissingInputError, StaleArtifactError
from engine.paths import BookWorkspace
from engine.structure import (
    PAGE_UNMAPPED,
    PROCESSING_SCOPE_EXCLUDED,
    PROCESSING_SCOPE_INCLUDED,
    EC,
    Atom,
    AtomStream,
    ContainerNode,
    Geom,
    LeafNode,
    ProjectionMap,
    StructureValidationError,
    hash_raw,
)
from engine.structure import structure_map as smod
from engine.structure.artifacts import (
    ATOM_STORE_STALE_CLASS,
    RELATION_STORE_STALE_CLASS,
    SCHEMA_STATUS_BORN,
    SCHEMA_STATUS_PROVISIONAL,
    STRUCTURE_MAP_SCHEMA_STATUS,
    STRUCTURE_MAP_SCHEMA_VERSION,
    STRUCTURE_MAP_STALE_CLASS,
    structure_map_snapshot_path,
)
from engine.structure.handles import HANDLE_RENDERER_VERSION
from engine.structure.lineage import _canonical, _sha256_bytes
from engine.structure.projection import NodeTableAccess, validate_reference_integrity

FIXTURES_ROOT = Path(__file__).resolve().parents[1] / "fixtures"
FIXTURE = FIXTURES_ROOT / "structure" / "conforming_structure_map.json"
INVALID_DIR = FIXTURES_ROOT / "structure" / "invalid"
GENERATOR = FIXTURES_ROOT / "_generate_structure_fixture.py"
STRUCTURE_SRC = Path(__file__).resolve().parents[2] / "src" / "engine" / "structure"


def _load_generator():
    spec = importlib.util.spec_from_file_location("_generate_structure_fixture", GENERATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GEN = _load_generator()


def _fresh_doc() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _write_doc(tmp_path: Path, doc: dict) -> Path:
    path = tmp_path / "structure_map.json"
    path.write_text(smod.render_structure_map(doc), encoding="utf-8")
    return path


def _load(tmp_path: Path, doc: dict, store=None):
    return structure.load_structure_map(_write_doc(tmp_path, doc), store or GEN.conforming_atom_store())


def _load_codes(tmp_path: Path, doc: dict, store=None) -> tuple[EC, ...]:
    with pytest.raises(StructureValidationError) as ei:
        _load(tmp_path, doc, store)
    return ei.value.codes


class _DuckStore:
    """A minimal §4-header store for the hand-authored invalid fixtures (their tiny atom universe
    is not the conforming streams')."""

    def __init__(self, included=(), excluded=()) -> None:
        self._included = tuple(included)
        self._scope = {a: PROCESSING_SCOPE_INCLUDED for a in included}
        for a in excluded:
            self._scope[a] = PROCESSING_SCOPE_EXCLUDED

    def included_atom_ids(self):
        return self._included

    def contains(self, atom_id):
        return atom_id in self._scope

    def scope_of(self, atom_id):
        return self._scope.get(atom_id)


def _invalid(name: str) -> Path:
    return INVALID_DIR / name


# --- the positive floor: the conforming fixture loads clean through the FULL loader -------------- #


def test_conforming_fixture_loads_clean_through_the_full_loader():
    # Phase-2's floor: parse → Tier-1 → Tier-2 on the committed fixture with the real streams-backed
    # store. Every perturbation test below deviates from THIS known-good load, so a false positive
    # here would mask the whole battery.
    smap = structure.load_structure_map(FIXTURE, GEN.conforming_atom_store())
    assert len(smap.projection.nodes) == 4
    assert smap.map_revision == 2
    assert smap.projection.root_id == smap.doc["root_id"]


def test_loader_missing_file_and_non_json_fail_loud(tmp_path):
    with pytest.raises(MissingInputError):
        structure.load_structure_map(tmp_path / "absent.json", GEN.conforming_atom_store())
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(StaleArtifactError, match="not valid JSON"):
        structure.load_structure_map(bad, GEN.conforming_atom_store())


def test_loader_unreadable_and_depth_blowup_stay_inside_the_total_contract(tmp_path):
    # Post-audit fix: OSError (is_file passed, read fails) and RecursionError (pathological
    # nesting blows json's recursive parser) must land as StaleArtifactError, never escape as a
    # PermissionError/RecursionError traceback through the "nothing else escapes" contract.
    locked = tmp_path / "locked.json"
    locked.write_text("{}", encoding="utf-8")
    locked.chmod(0o000)
    try:
        with pytest.raises(StaleArtifactError, match="unreadable"):
            structure.load_structure_map(locked, GEN.conforming_atom_store())
    finally:
        locked.chmod(0o644)
    deep = tmp_path / "deep.json"
    deep.write_text("[" * 100_000, encoding="utf-8")
    with pytest.raises(StaleArtifactError, match="not valid JSON"):
        structure.load_structure_map(deep, GEN.conforming_atom_store())


# --- inv 10 — schema const ↔ constant (the two-assertion binding, §3.E.5) ------------------------- #


def test_schema_version_const_binds_to_the_live_constant():
    # Assertion (a): the schema literal reads back equal to the Python constant — in both call forms.
    assert smod.schema_version_const() == STRUCTURE_MAP_SCHEMA_VERSION
    assert smod.schema_version_const(smod.load_schema()) == STRUCTURE_MAP_SCHEMA_VERSION


def test_version_derived_fixture_validates_at_tier1():
    # Assertion (b): the fixture (whose schema_version DERIVES from the constant via the generator)
    # Tier-1-validates — so a constant bump without a schema+fixture refresh reds one of the two.
    jsonschema.validate(_fresh_doc(), smod.load_schema())


def test_bumped_document_version_fails_tier1(tmp_path):
    doc = _fresh_doc()
    doc["schema_version"] = STRUCTURE_MAP_SCHEMA_VERSION + 1
    with pytest.raises(StaleArtifactError, match="schema_version"):
        _load(tmp_path, doc)


# --- inv 2 (Tier-1 oneOf) — container-xor-leaf ---------------------------------------------------- #


def test_node_with_both_children_and_body_atoms_fails_tier1(tmp_path):
    doc = _fresh_doc()
    doc["nodes"][2]["children"] = []  # leafA now carries both slots
    with pytest.raises(StaleArtifactError, match="Tier-1"):
        _load(tmp_path, doc)


def test_node_with_neither_slot_fails_tier1(tmp_path):
    doc = _fresh_doc()
    del doc["nodes"][2]["body_atoms"]  # leafA now carries neither slot
    with pytest.raises(StaleArtifactError, match="Tier-1"):
        _load(tmp_path, doc)


# --- inv 22 (Tier-1) — node_class stays an open string -------------------------------------------- #


def test_schema_keeps_node_class_open_no_enum():
    node_class = smod.load_schema()["$defs"]["node_class"]
    assert node_class["type"] == "string"
    assert "enum" not in node_class, "node_class must stay an OPEN per-book vocabulary (inv 22)"


def test_minted_by_description_carries_the_conceptual_authority_phrase():
    # §3.C.2: the schema description carries "conceptual minting authority" verbatim — the term is
    # the design decision (authority ≠ runtime writer), so it is pinned, not paraphrasable.
    assert "conceptual minting authority" in smod.load_schema()["$defs"]["minted_by"]["description"]


def test_region_description_pins_the_shared_coordinate_space_contract():
    # s4_plan §0.3 A-3 / BR-022: the one thing locked about region BEFORE S5 planning is that it
    # shares the atom-level Geom's coordinate space (whatever S2.1 pins) — never a second
    # convention. The sentence is normative (S5's re-bind comparability rests on it), so it is
    # pinned verbatim like the minted_by authority phrase; the space itself stays an S5 decision.
    description = smod.load_schema()["$defs"]["rebind_anchors"]["description"]
    assert "same coordinate space as the atom-level Geom" in description
    assert "BR-022" in description


# --- inv 13 / 24 — rebind_anchors: optional, region-only shape ------------------------------------ #


def test_rebind_anchors_region_and_absence_both_validate(tmp_path):
    # inv 13 positives: the fixture's section node carries {region: {page, bbox_region}}; leafA
    # carries none; a null region is also first-class (O4). All three shapes load clean.
    doc = _fresh_doc()
    doc["nodes"][3]["rebind_anchors"] = {"region": None}
    _load(tmp_path, doc)  # no raise


@pytest.mark.parametrize("smuggled", ["geom", "present"])
def test_rebind_anchors_rejects_smuggled_atom_geom_keys(tmp_path, smuggled):
    # inv 24 (H4/M6): node-level anchors are never the atom-level Geom — additionalProperties:false
    # rejects a `geom` or `present` key at Tier-1 (D-S4-H keeps the two geoms distinct).
    doc = _fresh_doc()
    doc["nodes"][1]["rebind_anchors"][smuggled] = {"page": 3}
    with pytest.raises(StaleArtifactError, match="Tier-1"):
        _load(tmp_path, doc)


# --- inv 11 / 12b — manifest completeness + stale-class stamping ---------------------------------- #


@pytest.mark.parametrize(
    "drop",
    [
        ("canonical_geometry_hash",),
        ("layers", "structure_map"),
        ("resource_lineage", "resource"),
        ("handle_renderer_version",),
    ],
)
def test_manifest_missing_required_member_fails_tier1(tmp_path, drop):
    # inv 11: structural completeness is Tier-1 `required` — the ONLY S4 manifest rejection
    # (stored-vs-live staleness comparison is S8.1's, §1.2/§3.E.9).
    doc = _fresh_doc()
    target = doc["manifest"]
    for key in drop[:-1]:
        target = target[key]
    del target[drop[-1]]
    with pytest.raises(StaleArtifactError, match="Tier-1"):
        _load(tmp_path, doc)


def test_manifest_stamps_every_layer_with_its_live_stale_class():
    # inv 12b: the assembly declares STRUCTURE_MAP_STALE_CLASS (and its two siblings) from the live
    # constants; relation-store is pinned present:false until S7.1c (O1). Asserted on BOTH the
    # assembly output and the committed fixture bytes, so neither can drift alone.
    manifest = structure.build_manifest(
        streams=GEN.conforming_streams(),
        canonical_stream_id=GEN.CANONICAL_STREAM_ID,
        resource_lineage=GEN._fixture_resource_lineage(),
        profile_version="p1",
        recognizer_version="r1",
    )
    for source in (manifest, _fresh_doc()["manifest"]):
        layers = source["layers"]
        assert layers["structure_map"]["stale_class"] == STRUCTURE_MAP_STALE_CLASS
        assert layers["atom_store"]["stale_class"] == ATOM_STORE_STALE_CLASS
        assert layers["relation_store"]["stale_class"] == RELATION_STORE_STALE_CLASS
        assert layers["relation_store"]["present"] is False
        assert layers["structure_map"]["present"] is True
        assert source["handle_renderer_version"] == HANDLE_RENDERER_VERSION


# --- Tier-2a preconditions through the loader (short-circuit, §4.1) ------------------------------- #


def test_duplicate_node_id_short_circuits_through_the_loader(tmp_path):
    # The duplicated node ALSO double-owns its body atom — but the payload is exactly
    # DUPLICATE_NODE_ID: the precondition raised before any collect-all check ran (P3A-5).
    doc = _fresh_doc()
    doc["nodes"].append(dict(doc["nodes"][3]))
    assert _load_codes(tmp_path, doc) == (EC.DUPLICATE_NODE_ID,)


def test_dangling_root_id_short_circuits_through_the_loader(tmp_path):
    # Re-pointing root_id strands every node — but the payload is exactly ROOT_ID_DANGLING: the Z /
    # traversal codes are suppressed by the short-circuit (P3A-3).
    doc = _fresh_doc()
    doc["root_id"] = "ghost"
    assert _load_codes(tmp_path, doc) == (EC.ROOT_ID_DANGLING,)


# --- the §3.B.5 negative-fixture set (each file Tier-1-valid unless stated) ----------------------- #


def test_negative_fixture_empty_map_is_root_id_dangling_not_no_root():
    # P3A-2: zero nodes ⇒ root_id cannot resolve ⇒ the Tier-2a precondition — NOT NO_ROOT (reserved
    # for a resolving root_id with |Z|==0), and none of the would-be collect-all codes (the unused
    # vocabulary entry) appear: exactly the one precondition token.
    with pytest.raises(StructureValidationError) as ei:
        structure.load_structure_map(_invalid("empty_map.json"), _DuckStore())
    assert ei.value.codes == (EC.ROOT_ID_DANGLING,)


def test_negative_fixture_leaf_only_is_multiple_roots():
    with pytest.raises(StructureValidationError) as ei:
        structure.load_structure_map(_invalid("leaf_only.json"), _DuckStore(included=("i0", "i1")))
    assert EC.MULTIPLE_ROOTS in ei.value.codes


def test_negative_fixture_empty_container_fires_inv26():
    with pytest.raises(StructureValidationError) as ei:
        structure.load_structure_map(_invalid("empty_container.json"), _DuckStore())
    assert EC.EMPTY_CONTAINER in ei.value.codes


def test_negative_fixture_non_container_root_is_no_root():
    with pytest.raises(StructureValidationError) as ei:
        structure.load_structure_map(_invalid("non_container_root.json"), _DuckStore(included=("i0",)))
    assert EC.NO_ROOT in ei.value.codes


def test_negative_fixture_malformed_manifest_is_a_tier1_rejection_not_an_ec_code():
    # inv 11/M9: the S4 manifest rejection is structural completeness at the LOAD BOUNDARY — a
    # StaleArtifactError, never a semantic EC payload (the closed set has no manifest code).
    with pytest.raises(StaleArtifactError, match="Tier-1"):
        structure.load_structure_map(_invalid("malformed_manifest.json"), _DuckStore(included=("i0",)))


def test_negative_fixture_alias_collision_passes_tier1_fails_semantically():
    # The §4.2 headline shape: JSON-parses, Tier-1-validates (asserted explicitly), and fails ONLY
    # at Tier-2 — two status:active aliases sharing the uniqueness key.
    doc = json.loads(_invalid("alias_collision.json").read_text(encoding="utf-8"))
    jsonschema.validate(doc, smod.load_schema())  # Tier-1 passes: the failure is purely semantic
    with pytest.raises(StructureValidationError) as ei:
        structure.load_structure_map(_invalid("alias_collision.json"), _DuckStore(included=("i0",)))
    assert EC.ALIAS_COLLISION in ei.value.codes


# --- Phase-2 re-route: every remaining Tier-2b code fires through load_structure_map -------------- #
#
# Each case perturbs ONE axis of the conforming fixture and asserts the specific token in the
# collected payload. Where a co-fire is structural (ORPHAN⇒MULTIPLE_ROOTS, CYCLE⇒MULTI_PARENT on
# these shapes) the second token is asserted too — pinning it is what keeps the primary check
# non-vacuous (X5/P3A-4).


def _canonical_ids(doc) -> list[str]:
    return [doc["nodes"][1]["heading_atoms"][0], doc["nodes"][2]["body_atoms"][0], doc["nodes"][3]["body_atoms"][0]]


def test_phase2_dup_ownership(tmp_path):
    doc = _fresh_doc()
    c0 = _canonical_ids(doc)[0]
    doc["nodes"][2]["body_atoms"] = [c0, *doc["nodes"][2]["body_atoms"]]  # heading atom also in a body
    assert EC.DUP_OWNERSHIP in _load_codes(tmp_path, doc)


def test_phase2_unowned_included_atom(tmp_path):
    doc = _fresh_doc()
    doc["nodes"][3]["body_atoms"] = []  # c2 now owned by nobody
    assert EC.UNOWNED_INCLUDED_ATOM in _load_codes(tmp_path, doc)


def test_phase2_owned_excluded_atom(tmp_path):
    doc = _fresh_doc()
    furniture_id = doc["furniture_atoms"][0]["atom_id"]
    doc["furniture_atoms"] = []  # move it out of the furniture bucket (else DUP_OWNERSHIP co-fires)
    doc["nodes"][3]["body_atoms"].append(furniture_id)
    codes = _load_codes(tmp_path, doc)
    assert EC.OWNED_EXCLUDED_ATOM in codes


def test_phase2_dangling_atom_ref(tmp_path):
    doc = _fresh_doc()
    doc["nodes"][3]["body_atoms"].append("phantom-atom")
    assert EC.DANGLING_ATOM_REF in _load_codes(tmp_path, doc)


def test_phase2_dangling_children_ref(tmp_path):
    # A well-formed string that names no node: passes Tier-1, fails only semantically — the §4.2
    # headline's first shape.
    doc = _fresh_doc()
    doc["nodes"][0]["children"].append("ghost-node")
    assert EC.DANGLING_REF in _load_codes(tmp_path, doc)


def test_phase2_orphan_node_co_fires_multiple_roots(tmp_path):
    doc = _fresh_doc()
    doc["nodes"].append({"node_id": "stray", "node_class": "block", "minted_by": "machine", "body_atoms": []})
    codes = _load_codes(tmp_path, doc)
    assert EC.ORPHAN_NODE in codes
    assert EC.MULTIPLE_ROOTS in codes  # the pinned structural co-fire (P3A-4)


def test_phase2_multi_parent(tmp_path):
    doc = _fresh_doc()
    leaf_a = doc["nodes"][2]["node_id"]
    doc["nodes"][0]["children"].append(leaf_a)  # already a child of the section
    assert EC.MULTI_PARENT in _load_codes(tmp_path, doc)


def test_phase2_duplicate_child_ref(tmp_path):
    doc = _fresh_doc()
    doc["nodes"][1]["children"] = doc["nodes"][1]["children"] * 2
    assert EC.DUPLICATE_CHILD_REF in _load_codes(tmp_path, doc)


def test_phase2_reachable_cycle_asserts_cycle_token(tmp_path):
    doc = _fresh_doc()
    doc["nodes"][1]["children"].append(doc["root_id"])  # section points back at the root
    codes = _load_codes(tmp_path, doc)
    assert EC.CYCLE in codes
    assert EC.NO_ROOT in codes  # the root is now parented: |Z| == 0 on this shape


def test_phase2_disconnected_cycle_is_unreachable_not_cycle(tmp_path):
    doc = _fresh_doc()
    doc["nodes"].extend(
        [
            {"node_id": "x", "node_class": "section", "minted_by": "human", "children": ["y"]},
            {"node_id": "y", "node_class": "section", "minted_by": "human", "children": ["x"]},
        ]
    )
    codes = _load_codes(tmp_path, doc)
    assert EC.UNREACHABLE_NODE in codes
    assert EC.CYCLE not in codes  # traversal runs from root_id only — no component scan


def test_phase2_empty_container(tmp_path):
    doc = _fresh_doc()
    doc["nodes"][1]["children"] = []
    doc["nodes"][1]["heading_atoms"] = []
    # the stranded leafA + unowned atoms co-fire reference/coverage codes; the token under test:
    codes = _load_codes(tmp_path, doc)
    assert EC.EMPTY_CONTAINER in codes


def test_phase2_body_atoms_unordered(tmp_path):
    doc = _fresh_doc()
    c0, c1, _ = _canonical_ids(doc)
    doc["nodes"][1]["heading_atoms"] = []          # free c0 so no DUP_OWNERSHIP co-fires
    doc["nodes"][2]["body_atoms"] = [c1, c0]       # descending canonical index
    assert _load_codes(tmp_path, doc) == (EC.BODY_ATOMS_UNORDERED,)


def test_phase2_minted_by_split(tmp_path):
    doc = _fresh_doc()
    doc["nodes"][0]["minted_by"] = "machine"  # a container must be human-minted
    assert EC.MINTED_BY_SPLIT in _load_codes(tmp_path, doc)


def test_phase2_node_id_derived(tmp_path):
    doc = _fresh_doc()
    leaf_a = doc["nodes"][2]
    leaf_a["node_id"] = "0.0.0"  # its own position-path (root→section→leafA)
    doc["nodes"][1]["children"] = ["0.0.0"]
    assert EC.NODE_ID_DERIVED in _load_codes(tmp_path, doc)


def test_phase2_class_kind_mismatch(tmp_path):
    doc = _fresh_doc()
    doc["nodes"][3]["node_class"] = "section"  # a leaf wearing a container-kind class
    assert EC.CLASS_KIND_MISMATCH in _load_codes(tmp_path, doc)


def test_phase2_policy_not_in_vocab(tmp_path):
    doc = _fresh_doc()
    doc["handle_policies"]["ghost-class"] = "position-path"
    assert EC.POLICY_NOT_IN_VOCAB in _load_codes(tmp_path, doc)


def test_phase2_policy_unresolved(tmp_path):
    doc = _fresh_doc()
    del doc["handle_policies"]["block"]  # both leaves lose their only resolution path
    assert EC.POLICY_UNRESOLVED in _load_codes(tmp_path, doc)


def test_phase2_alias_collision(tmp_path):
    doc = _fresh_doc()
    doc["aliases"].append(dict(doc["aliases"][0]))  # duplicate the active alias
    assert EC.ALIAS_COLLISION in _load_codes(tmp_path, doc)


def test_phase2_alias_dangling_target(tmp_path):
    doc = _fresh_doc()
    doc["aliases"][0]["target_node_id"] = "ghost-node"
    assert EC.ALIAS_DANGLING_TARGET in _load_codes(tmp_path, doc)


def test_phase2_alias_interval_invalid_isolated(tmp_path):
    # valid_from beyond the current map_revision; valid_to stays open so TEMPORAL_INCOMPLETE cannot
    # co-fire (P3B-6 isolation).
    doc = _fresh_doc()
    doc["aliases"][0]["valid_from"] = doc["map_revision"] + 3
    assert _load_codes(tmp_path, doc) == (EC.ALIAS_INTERVAL_INVALID,)


def test_phase2_alias_temporal_incomplete_isolated(tmp_path):
    # A retired alias with no valid_to; its interval is otherwise well-formed so INTERVAL_INVALID
    # cannot co-fire (P3B-6 isolation).
    doc = _fresh_doc()
    doc["aliases"][1]["valid_to"] = None
    assert _load_codes(tmp_path, doc) == (EC.ALIAS_TEMPORAL_INCOMPLETE,)


@pytest.mark.parametrize(
    "entry,code",
    [
        ({"name": "Unknown", "kind": "leaf", "status": "reserved"}, EC.VOCAB_UNKNOWN_COLLISION),
        ({"name": "   ", "kind": "leaf", "status": "reserved"}, EC.VOCAB_EMPTY),
        ({"name": "Block", "kind": "leaf", "status": "reserved"}, EC.VOCAB_DUPLICATE),
        ({"name": "tercet", "kind": "leaf", "status": "active"}, EC.VOCAB_UNUSED),
    ],
)
def test_phase2_vocab_hygiene(tmp_path, entry, code):
    doc = _fresh_doc()
    doc["block_vocabulary"].append(entry)
    assert code in _load_codes(tmp_path, doc)


def test_phase2_collect_all_carries_multiple_independent_faults(tmp_path):
    # §4.1 Tier-2b: two violations on independent axes (a dangling child ref + an invalid alias
    # interval) surface TOGETHER in one collected payload — neither short-circuits the other.
    doc = _fresh_doc()
    doc["nodes"][0]["children"].append("ghost-node")
    doc["aliases"][0]["valid_from"] = doc["map_revision"] + 3
    codes = _load_codes(tmp_path, doc)
    assert EC.DANGLING_REF in codes
    assert EC.ALIAS_INTERVAL_INVALID in codes


# --- inv 20 — determinism + the two split canonical hashes (D-S4-I, X8) --------------------------- #


def test_dump_load_dump_is_byte_identical():
    smap = structure.load_structure_map(FIXTURE, GEN.conforming_atom_store())
    assert smod.render_structure_map(smap.doc) == FIXTURE.read_text(encoding="utf-8")


def _atom(atom_id: str, text: str, geom: Geom) -> Atom:
    return Atom(
        atom_id=atom_id,
        text=text,
        raw_span=(0, len(text)),
        raw_source_hash=hash_raw(text),
        page_range=PAGE_UNMAPPED,
        norm_layer="raw",
        geom=geom,
        capture_provenance_class="body",
    )


def _matched_geom(page: int = 1, bbox=(1.0, 2.0, 3.0, 4.0)) -> Geom:
    return Geom.matched(
        page=page,
        bbox=bbox,
        geometry_engine="fixture-engine",
        matched_witness_id="w1",
        match_method="exact",
        match_confidence=0.9,
    )


def _manifest_for(atoms) -> dict:
    return structure.build_manifest(
        streams={"canonical": AtomStream.canonical(tuple(atoms))},
        canonical_stream_id="canonical",
        resource_lineage=GEN._fixture_resource_lineage(),
        profile_version="p1",
        recognizer_version="r1",
    )


def test_canonical_hashes_stable_under_rebuild():
    a = [_atom("A", "alpha", Geom.absent()), _atom("B", "beta", _matched_geom())]
    assert _manifest_for(a) == _manifest_for(a)


def test_text_edit_moves_content_hash_only():
    base = _manifest_for([_atom("A", "alpha", Geom.absent()), _atom("B", "beta", _matched_geom())])
    edited = _manifest_for([_atom("A", "alpha CHANGED", Geom.absent()), _atom("B", "beta", _matched_geom())])
    assert edited["canonical_content_hash"] != base["canonical_content_hash"]
    assert edited["canonical_geometry_hash"] == base["canonical_geometry_hash"]


def test_geometry_edit_moves_geometry_hash_only():
    # X8: capture emits only Geom.absent() today, so the geometry red is unproducible from captured
    # streams — the fixture SYNTHESIZES a Geom.matched atom (the real factory) and edits its region.
    base = _manifest_for([_atom("A", "alpha", Geom.absent()), _atom("B", "beta", _matched_geom())])
    moved = _manifest_for(
        [_atom("A", "alpha", Geom.absent()), _atom("B", "beta", _matched_geom(page=2, bbox=(9.0, 9.0, 12.0, 12.0)))]
    )
    assert moved["canonical_geometry_hash"] != base["canonical_geometry_hash"]
    assert moved["canonical_content_hash"] == base["canonical_content_hash"]


def test_atom_order_enters_the_hash():
    # D-S4-I pins canonical-stream order as the hash ordering: swapping two atoms MUST move the
    # content hash — a mutant that sorts/normalizes the payload before hashing would erase the
    # difference and red here.
    a, b = _atom("A", "alpha", Geom.absent()), _atom("B", "beta", Geom.absent())
    assert _manifest_for([a, b])["canonical_content_hash"] != _manifest_for([b, a])["canonical_content_hash"]


def test_content_hash_producer_is_the_named_lineage_composition():
    # The anti-substitution binding (M5): recompute the hash in-test from the EXPLICIT field list
    # through lineage._sha256_bytes(lineage._canonical(...).encode("utf-8")) — a different digest,
    # serializer, encoding, or field set in build_manifest reds here.
    atoms = [_atom("A", "alpha", Geom.absent()), _atom("B", "beta", _matched_geom())]
    expected = _sha256_bytes(
        _canonical(
            [
                {"atom_id": a.atom_id, "text": a.text, "raw_span": list(a.raw_span), "raw_source_hash": a.raw_source_hash}
                for a in atoms
            ]
        ).encode("utf-8")
    )
    assert _manifest_for(atoms)["canonical_content_hash"] == expected


# --- inv 21 — the regen-guarded writer (§3.E.8) ---------------------------------------------------- #


def _workspace(tmp_path) -> BookWorkspace:
    return BookWorkspace.for_book("demo", tmp_path).ensure()


def test_fresh_write_lands_at_the_structure_map_path(tmp_path):
    ws = _workspace(tmp_path)
    path = structure.write_structure_map(ws, _fresh_doc())
    assert path == structure.structure_map_path(ws)
    assert path.read_text(encoding="utf-8") == smod.render_structure_map(_fresh_doc())


def test_unlicensed_overwrite_is_blocked(tmp_path):
    ws = _workspace(tmp_path)
    structure.write_structure_map(ws, _fresh_doc())
    with pytest.raises(StructureValidationError) as ei:
        structure.write_structure_map(ws, _fresh_doc())
    assert EC.MAP_OVERWRITE_BLOCKED in ei.value.codes


def test_licensed_supersede_snapshots_then_writes(tmp_path):
    ws = _workspace(tmp_path)
    old = _fresh_doc()
    structure.write_structure_map(ws, old)
    new = _fresh_doc()
    new["map_revision"] = old["map_revision"] + 1
    path = structure.write_structure_map(ws, new, supersede_revision=old["map_revision"])
    snapshot = structure_map_snapshot_path(ws, old["map_revision"])
    assert snapshot.read_text(encoding="utf-8") == smod.render_structure_map(old)  # history kept
    assert path.read_text(encoding="utf-8") == smod.render_structure_map(new)      # live superseded


def test_supersede_must_name_the_exact_stored_revision(tmp_path):
    ws = _workspace(tmp_path)
    structure.write_structure_map(ws, _fresh_doc())  # stored map_revision == 2
    new = _fresh_doc()
    new["map_revision"] = 4
    with pytest.raises(StructureValidationError) as ei:
        structure.write_structure_map(ws, new, supersede_revision=3)  # stale belief about the store
    assert EC.MAP_OVERWRITE_BLOCKED in ei.value.codes


def test_supersede_requires_exactly_one_revision_tick(tmp_path):
    ws = _workspace(tmp_path)
    old = _fresh_doc()
    structure.write_structure_map(ws, old)
    new = _fresh_doc()
    new["map_revision"] = old["map_revision"] + 2  # skips a revision
    with pytest.raises(StructureValidationError) as ei:
        structure.write_structure_map(ws, new, supersede_revision=old["map_revision"])
    assert EC.MAP_OVERWRITE_BLOCKED in ei.value.codes


def test_supersede_never_clobbers_an_existing_snapshot(tmp_path):
    ws = _workspace(tmp_path)
    old = _fresh_doc()
    structure.write_structure_map(ws, old)
    snapshot = structure_map_snapshot_path(ws, old["map_revision"])
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    snapshot.write_text("immutable history\n", encoding="utf-8")
    new = _fresh_doc()
    new["map_revision"] = old["map_revision"] + 1
    with pytest.raises(StructureValidationError) as ei:
        structure.write_structure_map(ws, new, supersede_revision=old["map_revision"])
    assert EC.MAP_OVERWRITE_BLOCKED in ei.value.codes
    assert snapshot.read_text(encoding="utf-8") == "immutable history\n"


def test_writer_tier1_validates_before_touching_disk(tmp_path):
    ws = _workspace(tmp_path)
    doc = _fresh_doc()
    del doc["manifest"]["canonical_content_hash"]
    with pytest.raises(StaleArtifactError, match="Tier-1"):
        structure.write_structure_map(ws, doc)
    assert not structure.structure_map_path(ws).exists()  # nothing persisted


def test_writer_has_no_env_var_escape():
    # §3.E.8: "no env-var as the primary escape" — pinned structurally: the writer's source reads no
    # environment at all (os/environ never appear), so no variable can widen the licensed path.
    source = (STRUCTURE_SRC / "structure_map.py").read_text(encoding="utf-8")
    assert "environ" not in source and "getenv" not in source


# --- inv 23 (B-5 slice) — the born-gate + the born-agnostic loader (X1) --------------------------- #


def test_assert_schema_born_raises_on_a_provisional_version(monkeypatch):
    monkeypatch.setitem(STRUCTURE_MAP_SCHEMA_STATUS, STRUCTURE_MAP_SCHEMA_VERSION, SCHEMA_STATUS_PROVISIONAL)
    with pytest.raises(StructureValidationError) as ei:
        structure.assert_schema_born()
    assert EC.SCHEMA_NOT_BORN in ei.value.codes


def test_assert_schema_born_passes_on_a_born_version(monkeypatch):
    monkeypatch.setitem(STRUCTURE_MAP_SCHEMA_STATUS, STRUCTURE_MAP_SCHEMA_VERSION, SCHEMA_STATUS_BORN)
    structure.assert_schema_born()  # no raise


def test_assert_schema_born_is_fail_safe_on_a_missing_key(monkeypatch):
    # P3B-11: an UNREGISTERED version is treated as provisional and raised — deleting the key is the
    # named mutation, and it must fail closed, never fall through to "born by default".
    monkeypatch.delitem(STRUCTURE_MAP_SCHEMA_STATUS, STRUCTURE_MAP_SCHEMA_VERSION)
    with pytest.raises(StructureValidationError) as ei:
        structure.assert_schema_born()
    assert EC.SCHEMA_NOT_BORN in ei.value.codes


def test_loader_is_born_agnostic(monkeypatch):
    # X1 — the deadlock breaker: with the schema status forced provisional, the loader still loads
    # the conforming fixture CLEAN. Every red-test above routes through this loader on a provisional
    # schema; a born-aware loader would short-circuit them all into SCHEMA_NOT_BORN.
    monkeypatch.setitem(STRUCTURE_MAP_SCHEMA_STATUS, STRUCTURE_MAP_SCHEMA_VERSION, SCHEMA_STATUS_PROVISIONAL)
    smap = structure.load_structure_map(FIXTURE, GEN.conforming_atom_store())
    assert len(smap.projection.nodes) == 4


# --- inv 25 — reserved-inert `decision`: schema-present, code-blind -------------------------------- #


def _decision_reads(tree: ast.AST) -> list[str]:
    """Every AST access-pattern that READS a `decision` field/key (X9/P3B-7): a Subscript with the
    constant key, an Attribute access, or a ``.get("decision")`` call. Docstrings/comments are not
    AST access nodes, so they are structurally exempt — no substring false positives."""
    hits: list[str] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Subscript)
            and isinstance(node.slice, ast.Constant)
            and node.slice.value == "decision"
        ):
            hits.append(f"subscript@{node.lineno}")
        elif isinstance(node, ast.Attribute) and node.attr == "decision":
            hits.append(f"attribute@{node.lineno}")
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value == "decision"
        ):
            hits.append(f"get@{node.lineno}")
    return hits


def test_no_structure_module_reads_the_decision_field():
    # inv 25: the field is reserved present-but-inert — value-semantics are S8.2. The schema .json
    # legitimately DEFINES the property (exempt: this scan walks the .py AST only).
    scanned = sorted(STRUCTURE_SRC.rglob("*.py"))
    assert scanned, f"no .py files under {STRUCTURE_SRC}; the no-reader scan would pass vacuously"
    offenders = {}
    for py in scanned:
        hits = _decision_reads(ast.parse(py.read_text(encoding="utf-8")))
        if hits:
            offenders[py.name] = hits
    assert not offenders, f"S4 code reads the reserved-inert decision field (inv 25): {offenders}"


def test_decision_scanner_catches_a_planted_reader(tmp_path):
    # Non-vacuity proof: each access shape planted in a throwaway module is flagged.
    planted = 'def f(node, o):\n    return node["decision"], o.decision, node.get("decision")\n'
    hits = _decision_reads(ast.parse(planted))
    assert {h.split("@")[0] for h in hits} == {"subscript", "attribute", "get"}


def test_decision_is_schema_present_and_round_trips():
    # The positive half: the conforming fixture CARRIES a decision value, validates, and the value
    # survives load→dump untouched (the doc-retention passthrough — carried without being read).
    doc = _fresh_doc()
    assert doc["nodes"][1]["decision"] == "human-approved"
    smap = structure.load_structure_map(FIXTURE, GEN.conforming_atom_store())
    assert json.loads(smod.render_structure_map(smap.doc))["nodes"][1]["decision"] == "human-approved"


# --- §4.3 — the ResourceLineage contract ----------------------------------------------------------- #


def _lineage_subschema() -> dict:
    schema = smod.load_schema()
    return {"$defs": schema["$defs"], **schema["$defs"]["resource_lineage"]}


def test_live_resource_lineage_fragment_validates_against_the_schema():
    # A live ResourceLineage instance's to_json() drops verbatim into the manifest slot (§3.E.3) —
    # if lineage.py's emitted shape drifts (rename/addition), this contract test reds.
    fragment = GEN._fixture_resource_lineage().to_json()
    jsonschema.validate(fragment, _lineage_subschema())


def test_lineage_fragment_shape_drift_is_rejected():
    fragment = GEN._fixture_resource_lineage().to_json()
    fragment["surprise"] = 1  # an added top-level key = a lineage shape change
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(fragment, _lineage_subschema())


# --- §4.4 — complexity smoke: reference-integrity is linear (mandatory two-size ratio) ------------- #


class _CountingAccess(NodeTableAccess):
    """The §3.E.10 instrumented accessor: counts every node-table access AND every child-list
    element access, so a per-reference full-tree scan (or an `in parent.children` membership walk
    routed through the accessor) inflates the count quadratically."""

    def __init__(self, pmap: ProjectionMap) -> None:
        super().__init__(pmap)
        self.ref_ops = 0

    def node(self, node_id):
        self.ref_ops += 1
        return super().node(node_id)

    def child_ids(self, node):
        for child in super().child_ids(node):
            self.ref_ops += 1
            yield child


def _flat_map(n: int) -> ProjectionMap:
    leaves = tuple(
        LeafNode(node_id=f"L{i}", node_class="block", minted_by="machine", body_atoms=()) for i in range(n)
    )
    root = ContainerNode(
        node_id="root", node_class="section", minted_by="human", children=tuple(leaf.node_id for leaf in leaves)
    )
    return ProjectionMap(root_id="root", nodes=(root, *leaves))


def _ref_ops(n: int) -> int:
    pmap = _flat_map(n)
    access = _CountingAccess(pmap)
    validate_reference_integrity(pmap, access=access)
    return access.ref_ops


def test_reference_integrity_ref_ops_scale_linearly():
    # The MANDATORY two-size ratio (X12): doubling the node count must ~double the counted accesses
    # (linear ⇒ ratio ≈ 2); a per-reference tree scan yields ≈ 4. A heuristic floor, honestly held —
    # a linear-but-uncounted bypass is caught only by review/S4.7 (§3.E.10).
    small, large = _ref_ops(1200), _ref_ops(2400)
    assert small > 0
    ratio = large / small
    assert 1.7 <= ratio <= 2.4, f"ref_ops ratio {ratio:.2f} is not linear-shaped (≈2 expected, ≈4 = quadratic)"


# --- audit remediation (B-7 correctness findings): the numeric load/write boundary ----------------- #
#
# The pre-commit adversarial audit found the load/write boundary leaking bare exceptions on inputs
# that pass Tier-1's JSON-Schema numeric semantics ("integer" accepts 1.0; json.loads accepts NaN).
# The loader's contract is TOTAL: a persisted map yields a StructureMap or one of
# {MissingInputError, StaleArtifactError, StructureValidationError} — never a bare traceback (the
# atom_store.from_json precedent). Each test below was seen red against the unfixed boundary.


def test_zero_fraction_float_revision_fields_are_stale_not_a_traceback(tmp_path):
    # JSON Schema "integer" admits 0.0 (zero-fraction float). The model layer rejects it — and the
    # loader must surface that as the load-boundary StaleArtifactError, not a bare ValueError.
    doc = _fresh_doc()
    doc["aliases"][0]["valid_from"] = 0.0
    with pytest.raises(StaleArtifactError, match="malformed structure map"):
        _load(tmp_path, doc)


@pytest.mark.parametrize("field", ["map_revision", "schema_version"])
def test_float_typed_header_ints_are_stale_not_silently_loaded(tmp_path, field):
    # 2.0 satisfies Tier-1 "integer" (and 1.0 satisfies const:1 by numeric equality); the typed
    # model must refuse to carry a float where the contract says int.
    doc = _fresh_doc()
    doc[field] = float(doc[field])
    with pytest.raises(StaleArtifactError, match="JSON integer"):
        _load(tmp_path, doc)


def test_nan_in_region_is_rejected_at_parse_not_a_render_crash(tmp_path):
    # json.loads accepts the non-RFC NaN token by default; a NaN that reaches smap.doc breaks
    # render_structure_map (allow_nan=False) AFTER a "clean" load. The loader rejects it at parse.
    doc = _fresh_doc()
    path = tmp_path / "structure_map.json"
    text = smod.render_structure_map(doc).replace('"page": 3', '"page": 3, "extra": NaN')
    # (write raw text: the NaN token cannot be produced through the renderer, by design)
    path.write_text(text.replace('"bbox_region": [10.0', '"bbox_region": [NaN'), encoding="utf-8")
    with pytest.raises(StaleArtifactError, match="non-finite|not valid JSON"):
        structure.load_structure_map(path, GEN.conforming_atom_store())


def test_non_utf8_map_file_is_stale_not_a_unicode_traceback(tmp_path):
    path = tmp_path / "structure_map.json"
    path.write_bytes(b'{"schema_version": 1, "x": "\xe8\xa1"}')
    with pytest.raises(StaleArtifactError, match="not valid UTF-8"):
        structure.load_structure_map(path, GEN.conforming_atom_store())


def test_writer_rejects_a_non_finite_doc_before_touching_disk(tmp_path):
    # The audit's writer-wedge: NaN passes Tier-1, then the live render crashes AFTER the snapshot
    # was written — snapshot present, live map stale, retry permanently blocked. The writer now
    # pre-renders before any disk mutation, so the bad doc fails loud with NOTHING persisted.
    ws = _workspace(tmp_path)
    old = _fresh_doc()
    structure.write_structure_map(ws, old)
    new = _fresh_doc()
    new["map_revision"] = old["map_revision"] + 1
    new["nodes"][1]["rebind_anchors"]["region"]["bbox_region"][0] = float("nan")
    with pytest.raises(StaleArtifactError, match="not renderable"):
        structure.write_structure_map(ws, new, supersede_revision=old["map_revision"])
    assert not structure_map_snapshot_path(ws, old["map_revision"]).exists()  # no partial state
    assert structure.structure_map_path(ws).read_text(encoding="utf-8") == smod.render_structure_map(old)


def test_supersede_license_on_an_empty_workspace_is_blocked(tmp_path):
    # CAS discipline: "I am replacing rev N" against an empty workspace is a stale belief — blocked,
    # never a silent fresh write.
    ws = _workspace(tmp_path)
    with pytest.raises(StructureValidationError) as ei:
        structure.write_structure_map(ws, _fresh_doc(), supersede_revision=2)
    assert EC.MAP_OVERWRITE_BLOCKED in ei.value.codes
    assert not structure.structure_map_path(ws).exists()


def test_supersede_revision_rejects_a_bool(tmp_path):
    # bool is an int subclass: supersede_revision=True would silently license replacing rev 1 —
    # rejected as an API-arg programming error (the Alias model's bool-exclusion idiom).
    ws = _workspace(tmp_path)
    structure.write_structure_map(ws, _fresh_doc())
    with pytest.raises(ValueError, match="bool"):
        structure.write_structure_map(ws, _fresh_doc(), supersede_revision=True)


def test_snapshot_dir_existing_as_a_file_is_stale_not_a_bare_oserror(tmp_path):
    ws = _workspace(tmp_path)
    old = _fresh_doc()
    structure.write_structure_map(ws, old)
    structure_map_snapshot_path(ws, old["map_revision"]).parent.write_text("not a dir", encoding="utf-8")
    new = _fresh_doc()
    new["map_revision"] = old["map_revision"] + 1
    with pytest.raises(StaleArtifactError, match="snapshot"):
        structure.write_structure_map(ws, new, supersede_revision=old["map_revision"])


def test_fresh_write_works_in_a_never_ensured_workspace(tmp_path):
    # The writer owns its destination directory (the save_stream precedent) — a fresh checkout
    # without .ensure() must not FileNotFoundError out of mkstemp.
    ws = BookWorkspace.for_book("demo", tmp_path)  # no .ensure()
    path = structure.write_structure_map(ws, _fresh_doc())
    assert path.is_file()


def test_stream_reader_scope_prefers_the_canonical_stream_on_id_collision():
    # Audit hardening: with first-writer-wins by sorted stream id, a witness stream sorting before
    # "canonical" could shadow a canonical atom's scope (spurious OWNED_EXCLUDED_ATOM). The canonical
    # stream's scopes win unconditionally.
    shared = _atom("shared_0", "alpha", Geom.absent())
    excluded_twin = Atom(
        atom_id="shared_0", text="alpha", raw_span=(0, 5), raw_source_hash=hash_raw("alpha"),
        page_range=PAGE_UNMAPPED, norm_layer="raw", geom=Geom.absent(),
        capture_provenance_class="page-number", witness="a-witness",
        processing_scope=PROCESSING_SCOPE_EXCLUDED,
    )
    reader = structure.StreamAtomReader(
        {
            "a-witness": AtomStream.witness("a-witness", (excluded_twin,), (), "alpha"),
            "canonical": AtomStream.canonical((shared,)),
        }
    )
    assert reader.scope_of("shared_0") == PROCESSING_SCOPE_INCLUDED


def test_phase2_node_id_derived_from_rendered_handle_routes_through_the_loader(tmp_path):
    # The S4.3 substring-of-rendered-handle arm (inv 6), loader-routed: an id that is a proper
    # substring of its OWN designation-string handle (but not equal to the designation or its slug,
    # so the projection.py arms stay silent).
    doc = _fresh_doc()
    leaf_a = doc["nodes"][2]
    leaf_a["node_id"] = "p-sile"
    leaf_a["designation"] = "Deep Silence"          # own html_slug: "deep-silence" ⊃ "p-sile"
    leaf_a["handle_policy"] = "designation-string"
    doc["nodes"][1]["children"] = ["p-sile"]
    assert EC.NODE_ID_DERIVED in _load_codes(tmp_path, doc)


def test_phase2_undeclared_node_class_with_override_no_longer_loads_clean(tmp_path):
    # CLASS_NOT_IN_VOCAB (post-B-7 audit disposition): before the fix this exact doc — an undeclared
    # class + a per-node policy override — loaded CLEAN through the full loader (the audit's
    # confirmed repro). Now the loader surfaces the one code that owns it.
    doc = _fresh_doc()
    doc["nodes"][3]["node_class"] = "phantom-class"
    doc["nodes"][3]["handle_policy"] = "position-path"
    assert EC.CLASS_NOT_IN_VOCAB in _load_codes(tmp_path, doc)


def test_phase2_undeclared_node_class_without_override_co_fires_policy_unresolved(tmp_path):
    # Without the override the class also fails policy resolution — both codes surface in the one
    # collected payload (Tier-2b), pinning that the new code did not absorb/shadow the old one.
    doc = _fresh_doc()
    doc["nodes"][3]["node_class"] = "phantom-class"
    codes = _load_codes(tmp_path, doc)
    assert EC.CLASS_NOT_IN_VOCAB in codes
    assert EC.POLICY_UNRESOLVED in codes
