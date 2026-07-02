"""S4.6a — the authoring-evidence sidecar (engine half): the canonical node-structure digest,
the total load boundary, and the S4.6 authored-map gate (s4_plan §1.4.1a/b/c, Audit 15).

The invariants under test, each proven red by the mutation hunt (red-first, §9):

- the digest is THE single producer (``_hash_canonical`` over the §1.4.1b explicit field list:
  ``node_class`` + ordered ``children`` + owned atom ids) — nothing else enters it;
- evidence is stale **iff** its bound node's digest changes (the named done-when red test), and
  ``map_revision``/``authored_at_revision`` is bookkeeping that can NEVER trigger staleness;
- the gate holds the §1.4.1a one-to-one correspondence: every human-minted container has exactly
  one non-stale entry, and every entry binds exactly a human-minted container — missing, orphaned,
  misbound, and stale entries all red **by name**, collected into one raise;
- ``load_authoring_evidence`` is a total contract (valid sidecar or ``MissingInputError`` /
  ``StaleArtifactError``), with each load negative differing from the loadable document in
  exactly ONE axis (the S4.6-pre masking lesson — two-axis negatives let a dropped check hide);
- the schema ``const`` is bound to ``AUTHORING_EVIDENCE_SCHEMA_VERSION`` both ways (the inv 10
  two-assertion idiom: const equality AND a version-derived conforming document loads).
"""

from __future__ import annotations

import dataclasses
import json

import pytest

from engine.errors import MissingInputError, StaleArtifactError
from engine.structure import (
    AUTHORING_EVIDENCE_FILENAME,
    AUTHORING_EVIDENCE_SCHEMA_VERSION,
    AuthoringEvidence,
    ContainerNode,
    EvidenceEntry,
    LeafNode,
    ProjectionMap,
    assert_evidence_gate,
    authoring_evidence_path,
    evidence_schema_version_const,
    load_authoring_evidence,
    node_structure_digest,
)
from engine.structure.projection import MINTED_BY_HUMAN, MINTED_BY_MACHINE
from engine.structure.structure_map import _hash_canonical


# --- fixture: a small valid projection (two human containers, two machine leaves) -------------- #


def _nodes():
    root = ContainerNode(
        node_id="n-root",
        node_class="volume",
        minted_by=MINTED_BY_HUMAN,
        children=("n-sec", "n-leaf-b"),
        heading_atoms=("canonical_00000",),
    )
    sec = ContainerNode(
        node_id="n-sec",
        node_class="section",
        minted_by=MINTED_BY_HUMAN,
        children=("n-leaf-a",),
        heading_atoms=("canonical_00001",),
        signature_atoms=("canonical_00005",),
        title="A Section",
    )
    leaf_a = LeafNode(
        node_id="n-leaf-a",
        node_class="block",
        minted_by=MINTED_BY_MACHINE,
        body_atoms=("canonical_00002", "canonical_00003"),
    )
    leaf_b = LeafNode(
        node_id="n-leaf-b",
        node_class="block",
        minted_by=MINTED_BY_MACHINE,
        body_atoms=("canonical_00004",),
    )
    return root, sec, leaf_a, leaf_b


def _projection(*nodes) -> ProjectionMap:
    return ProjectionMap(root_id="n-root", nodes=tuple(nodes))


def _fresh_evidence(projection: ProjectionMap) -> AuthoringEvidence:
    """One entry per human-minted container, digests stamped from the live nodes."""
    return AuthoringEvidence(
        entries=tuple(
            EvidenceEntry(
                node_id=node.node_id,
                node_digest=node_structure_digest(node),
                evidence=f"scan-grounded rationale for {node.node_id}",
                authored_at_revision=1,
            )
            for node in projection.nodes
            if isinstance(node, ContainerNode) and node.minted_by == MINTED_BY_HUMAN
        )
    )


def _replace_node(projection: ProjectionMap, node_id: str, **changes) -> ProjectionMap:
    return _projection(
        *(dataclasses.replace(n, **changes) if n.node_id == node_id else n for n in projection.nodes)
    )


# --- the digest: single producer over the §1.4.1b explicit field list -------------------------- #


def test_digest_is_hash_canonical_over_the_named_field_list():
    # Binds the payload shape byte-for-byte: node_class + ordered children + owned atom ids per
    # slot, through THE producer (_hash_canonical). Any payload change must consciously edit this.
    root, sec, leaf_a, _ = _nodes()
    assert node_structure_digest(sec) == _hash_canonical(
        {
            "node_class": "section",
            "children": ["n-leaf-a"],
            "owned_atoms": {
                "heading_atoms": ["canonical_00001"],
                "signature_atoms": ["canonical_00005"],
            },
        }
    )
    assert node_structure_digest(leaf_a) == _hash_canonical(
        {
            "node_class": "block",
            "children": [],
            "owned_atoms": {"body_atoms": ["canonical_00002", "canonical_00003"]},
        }
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"node_class": "part"},
        {"children": ("n-leaf-a", "n-extra")},
        {"children": ()},  # emptied
        {"heading_atoms": ("canonical_00009",)},
        {"signature_atoms": ()},
    ],
    ids=["node_class", "children-grown", "children-emptied", "heading_atoms", "signature_atoms"],
)
def test_digest_changes_on_each_container_structural_axis(changes):
    _, sec, _, _ = _nodes()
    assert node_structure_digest(dataclasses.replace(sec, **changes)) != node_structure_digest(sec)


def test_digest_changes_when_children_reorder():
    # children is ORDERED (reading order, §3.B.6) — a reorder is a structure change, not a no-op.
    root, *_ = _nodes()
    reordered = dataclasses.replace(root, children=("n-leaf-b", "n-sec"))
    assert node_structure_digest(reordered) != node_structure_digest(root)


def test_digest_changes_on_leaf_body_atoms():
    *_, leaf_a, _ = _nodes()
    rebound = dataclasses.replace(leaf_a, body_atoms=("canonical_00002",))
    assert node_structure_digest(rebound) != node_structure_digest(leaf_a)


@pytest.mark.parametrize(
    "changes",
    [
        {"title": "Renamed"},
        {"designation": "II"},
        {"handle_policy": "designation-string"},
        {"minted_by": MINTED_BY_MACHINE},
    ],
    ids=["title", "designation", "handle_policy", "minted_by"],
)
def test_digest_ignores_every_non_structural_field(changes):
    # The §1.4.1b field list is closed: display/handle/minting metadata never enters the digest,
    # so re-titling a container does not stale its evidence.
    _, sec, _, _ = _nodes()
    assert node_structure_digest(dataclasses.replace(sec, **changes)) == node_structure_digest(sec)


# --- the gate: stale iff the bound node's digest changed (the named done-when) ----------------- #


@pytest.mark.parametrize(
    "changes",
    [
        {"node_class": "part"},
        {"children": ()},
        {"heading_atoms": ("canonical_00009",)},
    ],
    ids=["node_class", "children", "owned_atoms"],
)
def test_digest_staleness_red_test(changes):
    # THE named done-when (§1.4.1c): edit a bound node's node_class / children / owned atoms →
    # its evidence entry goes stale, named in the raise.
    projection = _projection(*_nodes())
    evidence = _fresh_evidence(projection)
    assert_evidence_gate(evidence, projection)  # fresh pair: green
    mutated = _replace_node(projection, "n-sec", **changes)
    with pytest.raises(StaleArtifactError, match="n-sec.*STALE|STALE.*n-sec"):
        assert_evidence_gate(evidence, mutated)


def test_map_revision_is_bookkeeping_never_the_staleness_trigger():
    # §1.4.1b: staleness keys on the digest and ONLY the digest. Entries stamped at wildly
    # different revisions stay fresh while digests match...
    projection = _projection(*_nodes())
    evidence = AuthoringEvidence(
        entries=tuple(
            dataclasses.replace(e, authored_at_revision=999 + i)
            for i, e in enumerate(_fresh_evidence(projection).entries)
        )
    )
    assert_evidence_gate(evidence, projection)  # green: revision drift is not staleness
    # ...and a digest drift reds regardless of any revision agreement.
    mutated = _replace_node(projection, "n-root", node_class="tome")
    with pytest.raises(StaleArtifactError, match="n-root"):
        assert_evidence_gate(evidence, mutated)


def test_gate_missing_evidence_for_a_human_container_reds_by_name():
    projection = _projection(*_nodes())
    evidence = AuthoringEvidence(
        entries=tuple(e for e in _fresh_evidence(projection).entries if e.node_id != "n-sec")
    )
    with pytest.raises(StaleArtifactError, match="n-sec.*no evidence"):
        assert_evidence_gate(evidence, projection)


def test_gate_orphan_and_misbound_entries_red_by_name():
    projection = _projection(*_nodes())
    fresh = _fresh_evidence(projection).entries
    orphan = EvidenceEntry(
        node_id="n-ghost", node_digest="sha256:0", evidence="binds nothing", authored_at_revision=1
    )
    _, _, leaf_a, _ = _nodes()
    misbound = EvidenceEntry(
        node_id="n-leaf-a",
        node_digest=node_structure_digest(leaf_a),  # even a FRESH digest cannot license a leaf entry
        evidence="on a machine leaf",
        authored_at_revision=1,
    )
    # Each finding must carry its OWN diagnosis: an orphan misreported as "misbound" (or vice
    # versa) is a dropped check hiding behind its neighbour, so the match pins the finding kind.
    with pytest.raises(StaleArtifactError, match="n-ghost.*orphaned"):
        assert_evidence_gate(AuthoringEvidence(entries=(*fresh, orphan)), projection)
    with pytest.raises(StaleArtifactError, match="n-leaf-a.*not a human-minted container"):
        assert_evidence_gate(AuthoringEvidence(entries=(*fresh, misbound)), projection)


def test_gate_collects_every_finding_in_one_raise():
    projection = _projection(*_nodes())
    fresh = {e.node_id: e for e in _fresh_evidence(projection).entries}
    evidence = AuthoringEvidence(
        entries=(
            # n-root entry MISSING; n-sec entry stale (digest of a mutated twin); plus an orphan.
            dataclasses.replace(fresh["n-sec"], node_digest="sha256:drifted"),
            EvidenceEntry(
                node_id="n-ghost", node_digest="sha256:0", evidence="orphan", authored_at_revision=1
            ),
        )
    )
    with pytest.raises(StaleArtifactError) as err:
        assert_evidence_gate(evidence, projection)
    message = str(err.value)
    assert "n-root" in message and "n-sec" in message and "n-ghost" in message


def test_gate_green_on_a_fresh_complete_pair_returns_none():
    projection = _projection(*_nodes())
    assert assert_evidence_gate(_fresh_evidence(projection), projection) is None


# --- model hygiene ------------------------------------------------------------------------------ #


def test_duplicate_entries_for_one_node_are_rejected_at_construction():
    # The gate's correspondence is ONE entry per container; a keyed table cannot hold two.
    entry = EvidenceEntry(
        node_id="n-root", node_digest="sha256:a", evidence="first", authored_at_revision=0
    )
    twin = dataclasses.replace(entry, evidence="second")
    with pytest.raises(ValueError, match="duplicate"):
        AuthoringEvidence(entries=(entry, twin))


@pytest.mark.parametrize(
    "changes",
    [
        {"node_id": ""},
        {"node_digest": ""},
        {"evidence": "   "},  # whitespace-only prose is no evidence
        {"authored_at_revision": True},
        {"authored_at_revision": 2.0},
        {"authored_at_revision": -1},
    ],
    ids=["node_id", "node_digest", "evidence-blank", "revision-bool", "revision-float", "revision-negative"],
)
def test_entry_model_rejects_degenerate_fields(changes):
    valid = dict(node_id="n-1", node_digest="sha256:a", evidence="why", authored_at_revision=0)
    with pytest.raises(ValueError):
        EvidenceEntry(**{**valid, **changes})


# --- load boundary: total contract, one axis per negative --------------------------------------- #

_VALID_ENTRY = {
    "node_id": "n-root",
    "node_digest": "sha256:abc",
    "evidence": "why this container exists",
    "authored_at_revision": 0,
}


def _valid_doc() -> dict:
    return {
        "schema_version": AUTHORING_EVIDENCE_SCHEMA_VERSION,
        "entries": [dict(_VALID_ENTRY)],
    }


def _write(tmp_path, doc) -> "object":
    path = tmp_path / AUTHORING_EVIDENCE_FILENAME
    path.write_text(
        doc if isinstance(doc, str) else json.dumps(doc, ensure_ascii=False), encoding="utf-8"
    )
    return path


def test_loadable_document_loads_typed(tmp_path):
    evidence = load_authoring_evidence(_write(tmp_path, _valid_doc()))
    assert len(evidence.entries) == 1
    entry = evidence.entries[0]
    assert entry.node_id == "n-root"
    assert entry.node_digest == "sha256:abc"
    assert entry.authored_at_revision == 0
    assert evidence.by_node["n-root"] is entry


def test_empty_entries_is_a_valid_starting_sidecar(tmp_path):
    # Optional-at-load (§1.4.1a): a zero-entry sidecar is coherent mid-authoring; the GATE is
    # what later demands coverage.
    doc = _valid_doc()
    doc["entries"] = []
    assert load_authoring_evidence(_write(tmp_path, doc)).entries == ()


def test_missing_file_is_missing_input(tmp_path):
    with pytest.raises(MissingInputError):
        load_authoring_evidence(tmp_path / AUTHORING_EVIDENCE_FILENAME)


def _drop(doc: dict, key: str) -> dict:
    del doc[key]
    return doc


def _drop_entry_key(doc: dict, key: str) -> dict:
    del doc["entries"][0][key]
    return doc


def _set_entry(doc: dict, key: str, value) -> dict:
    doc["entries"][0][key] = value
    return doc


@pytest.mark.parametrize(
    "mangle",
    [
        lambda d: "not json {",
        lambda d: [d],  # top level not an object
        lambda d: {**d, "schema_version": AUTHORING_EVIDENCE_SCHEMA_VERSION + 1},
        lambda d: {**d, "schema_version": True},
        lambda d: _drop(d, "schema_version"),
        lambda d: _drop(d, "entries"),
        lambda d: {**d, "entries": {}},  # not an array
        lambda d: {**d, "stray": 1},  # additionalProperties: false, top level
        lambda d: _drop_entry_key(d, "node_id"),
        lambda d: _drop_entry_key(d, "node_digest"),
        lambda d: _drop_entry_key(d, "evidence"),
        lambda d: _drop_entry_key(d, "authored_at_revision"),
        lambda d: _set_entry(d, "node_id", ""),
        lambda d: _set_entry(d, "evidence", "   "),  # Tier-1-legal, model-rejected: wrap proven
        lambda d: _set_entry(d, "authored_at_revision", 2.0),  # Tier-1 "integer" admits it; strict int must not
        lambda d: _set_entry(d, "authored_at_revision", -1),
        lambda d: _set_entry(d, "stray", 1),  # additionalProperties: false, entry level
        lambda d: {**d, "entries": [dict(_VALID_ENTRY), dict(_VALID_ENTRY)]},  # duplicate node_id
        lambda d: json.dumps(d).replace('"sha256:abc"', "NaN"),  # non-finite token
    ],
    ids=[
        "not-json",
        "top-level-array",
        "stale-version",
        "bool-version",
        "missing-version",
        "missing-entries",
        "entries-not-array",
        "stray-top-key",
        "entry-missing-node_id",
        "entry-missing-node_digest",
        "entry-missing-evidence",
        "entry-missing-revision",
        "entry-empty-node_id",
        "entry-blank-evidence",
        "entry-float-revision",
        "entry-negative-revision",
        "entry-stray-key",
        "duplicate-node_id",
        "nan-token",
    ],
)
def test_load_contract_is_total(tmp_path, mangle):
    # Every negative differs from the loadable document in exactly one axis (the S4.6-pre
    # masking lesson): a dropped check cannot hide behind a second broken axis.
    with pytest.raises(StaleArtifactError):
        load_authoring_evidence(_write(tmp_path, mangle(_valid_doc())))


def test_stale_version_reads_as_stale_not_as_a_shape_failure(tmp_path):
    # The version pre-check is deliberately redundant with the schema const — it exists for the
    # M3 routing message. Asserting the STALE wording keeps it killable: dropping the pre-check
    # would still raise (Tier-1 const), but as a shape failure, and this match reds.
    doc = _valid_doc()
    doc["schema_version"] = AUTHORING_EVIDENCE_SCHEMA_VERSION + 1
    with pytest.raises(StaleArtifactError, match="stale sidecar"):
        load_authoring_evidence(_write(tmp_path, doc))


def test_schema_const_binds_to_the_python_constant(tmp_path):
    # The inv 10 two-assertion idiom: the schema literal equals the live constant AND a
    # version-derived conforming document actually loads — so neither can drift alone.
    assert evidence_schema_version_const() == AUTHORING_EVIDENCE_SCHEMA_VERSION
    assert load_authoring_evidence(_write(tmp_path, _valid_doc())).entries


# --- artifact location --------------------------------------------------------------------------- #


def test_authoring_evidence_path_is_the_work_root_companion(tmp_path):
    from engine.paths import BookWorkspace

    workspace = BookWorkspace.for_book("testbook", tmp_path).ensure()
    path = authoring_evidence_path(workspace)
    assert path.name == AUTHORING_EVIDENCE_FILENAME
    assert path.parent == workspace.root
