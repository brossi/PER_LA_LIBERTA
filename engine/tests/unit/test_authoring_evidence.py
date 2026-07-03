"""S4.6a — the authoring-evidence sidecar (engine half): the split staleness digests, the total
load boundary, the S4.6 authored-map gate, and the engine writer (s4_plan §1.4.1a/b/c, Audit 15;
post-audit remediation, user-ratified 2026-07-02).

The invariants under test, each proven red by the mutation hunt (red-first, §9):

- the staleness key is SPLIT (§1.4.1b): ``decision_digest`` witnesses the human's topology decision
  (``node_class`` + ordered ``children`` node ids — nothing else), ``extent_digest`` witnesses the
  substrate binding (the transitive subtree atom coverage as a sorted set) — each through THE
  producer (``_hash_canonical``), each with its own change/ignore matrix and its own finding kind;
- the split's headline semantics hold: a boundary move stales exactly the affected subtrees (the
  parent whose union is unchanged stays fresh); content addition cascades extent-staleness to every
  ancestor; a decision digest never moves on a substrate-only change and vice versa;
- the gate raises :class:`EvidenceGateError` (exit 12) whose typed ``findings`` come from the ONE
  non-raising producer (``evidence_findings``), kinds drawn from the closed
  ``EVIDENCE_FINDING_KINDS`` set, reported in map reading order with titles and repr'd digests;
- ``load_authoring_evidence`` is a total contract (valid sidecar or ``MissingInputError`` /
  ``StaleArtifactError`` — including unreadable files and parse-depth blowups), each load negative
  differing from the loadable document in exactly ONE axis (the S4.6-pre masking lesson);
- the sidecar names its ``book`` and its ``stale_class``; the writer is deny-by-default (the
  ``write_freeze_record`` posture) and the entry builder stamps BOTH digests via the producers.
"""

from __future__ import annotations

import dataclasses
import json

import pytest

import engine.errors as engine_errors
from engine.errors import EngineError, MissingInputError, StaleArtifactError
from engine.structure import (
    AUTHORING_EVIDENCE_FILENAME,
    AUTHORING_EVIDENCE_SCHEMA_VERSION,
    AUTHORING_EVIDENCE_STALE_CLASS,
    EVIDENCE_FINDING_KINDS,
    AuthoringEvidence,
    ContainerNode,
    EvidenceEntry,
    EvidenceGateError,
    LeafNode,
    ProjectionMap,
    assert_evidence_gate,
    authoring_evidence_path,
    build_evidence_entry,
    decision_digest,
    evidence_findings,
    evidence_schema_version_const,
    extent_digest,
    load_authoring_evidence,
    render_authoring_evidence,
    write_authoring_evidence,
)
from engine.structure.errors import StructureValidationError
from engine.structure.projection import MINTED_BY_HUMAN, MINTED_BY_MACHINE
from engine.structure.structure_map import _hash_canonical

BOOK = "testbook"


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
    """One entry per human-minted container, BOTH digests stamped from the live pair."""
    return AuthoringEvidence(
        book=BOOK,
        entries=tuple(
            EvidenceEntry(
                node_id=node.node_id,
                decision_digest=decision_digest(node),
                extent_digest=extent_digest(node, projection),
                evidence=f"scan-grounded rationale for {node.node_id}",
                authored_at_revision=1,
            )
            for node in projection.nodes
            if isinstance(node, ContainerNode) and node.minted_by == MINTED_BY_HUMAN
        ),
    )


def _replace_node(projection: ProjectionMap, node_id: str, **changes) -> ProjectionMap:
    return _projection(
        *(dataclasses.replace(n, **changes) if n.node_id == node_id else n for n in projection.nodes)
    )


# --- the decision digest: node_class + ordered children, nothing else -------------------------- #


def test_decision_digest_is_hash_canonical_over_class_and_children():
    # Binds the payload byte-for-byte through THE producer (_hash_canonical): node_class + ordered
    # child node ids; a leaf contributes the empty list. Any payload change must consciously edit
    # this (and the golden pin below).
    _, sec, leaf_a, _ = _nodes()
    assert decision_digest(sec) == _hash_canonical(
        {"node_class": "section", "children": ["n-leaf-a"]}
    )
    assert decision_digest(leaf_a) == _hash_canonical({"node_class": "block", "children": []})


@pytest.mark.parametrize(
    "changes",
    [
        {"node_class": "part"},
        {"children": ("n-leaf-a", "n-extra")},
        {"children": ()},  # emptied
    ],
    ids=["node_class", "children-grown", "children-emptied"],
)
def test_decision_digest_changes_on_each_decision_axis(changes):
    _, sec, _, _ = _nodes()
    assert decision_digest(dataclasses.replace(sec, **changes)) != decision_digest(sec)


def test_decision_digest_changes_when_children_reorder():
    # children is ORDERED (reading order, §3.B.6) — a reorder is a topology decision change.
    root, *_ = _nodes()
    reordered = dataclasses.replace(root, children=("n-leaf-b", "n-sec"))
    assert decision_digest(reordered) != decision_digest(root)


@pytest.mark.parametrize(
    "changes",
    [
        {"heading_atoms": ("canonical_00009",)},  # substrate binding — the split's whole point
        {"signature_atoms": ()},
        {"title": "Renamed"},
        {"designation": "II"},
        {"handle_policy": "designation-string"},
        {"minted_by": MINTED_BY_MACHINE},
    ],
    ids=["heading_atoms", "signature_atoms", "title", "designation", "handle_policy", "minted_by"],
)
def test_decision_digest_ignores_substrate_and_display_axes(changes):
    # The decision payload is CLOSED to atom ids (that is the R1 split): an S5 re-bind that renames
    # every atom must leave every decision digest byte-identical — it is never machine-refreshed.
    _, sec, _, _ = _nodes()
    assert decision_digest(dataclasses.replace(sec, **changes)) == decision_digest(sec)


def test_decision_digest_ignores_leaf_body_atoms():
    *_, leaf_a, _ = _nodes()
    rebound = dataclasses.replace(leaf_a, body_atoms=("canonical_00099",))
    assert decision_digest(rebound) == decision_digest(leaf_a)


# --- the extent digest: transitive subtree atom coverage as a sorted set ------------------------ #


def test_extent_digest_is_hash_canonical_over_the_sorted_transitive_coverage():
    # sec's extent = own heading + signature + descendant leaf_a's body, slot-flattened, sorted;
    # root's extent = the whole tree's coverage; a leaf's = its own body. Byte-for-byte pin.
    root, sec, leaf_a, leaf_b = _nodes()
    projection = _projection(root, sec, leaf_a, leaf_b)
    assert extent_digest(sec, projection) == _hash_canonical(
        {"extent": ["canonical_00001", "canonical_00002", "canonical_00003", "canonical_00005"]}
    )
    assert extent_digest(root, projection) == _hash_canonical(
        {"extent": [f"canonical_0000{i}" for i in range(6)]}
    )
    assert extent_digest(leaf_a, projection) == _hash_canonical(
        {"extent": ["canonical_00002", "canonical_00003"]}
    )


@pytest.mark.parametrize(
    "node_id, changes",
    [
        ("n-sec", {"heading_atoms": ("canonical_00009",)}),
        ("n-sec", {"signature_atoms": ()}),
        ("n-leaf-a", {"body_atoms": ("canonical_00002",)}),  # descendant change reaches the ancestor
    ],
    ids=["own-heading", "own-signature", "descendant-body"],
)
def test_extent_digest_changes_on_own_and_descendant_coverage(node_id, changes):
    projection = _projection(*_nodes())
    sec = projection.by_id["n-sec"]
    mutated = _replace_node(projection, node_id, **changes)
    assert extent_digest(mutated.by_id["n-sec"], mutated) != extent_digest(sec, projection)


@pytest.mark.parametrize(
    "changes",
    [
        {"node_class": "part"},
        {"title": "Renamed"},
        {"minted_by": MINTED_BY_MACHINE},
    ],
    ids=["node_class", "title", "minted_by"],
)
def test_extent_digest_ignores_class_and_display(changes):
    projection = _projection(*_nodes())
    sec = projection.by_id["n-sec"]
    mutated = _replace_node(projection, "n-sec", **changes)
    assert extent_digest(mutated.by_id["n-sec"], mutated) == extent_digest(sec, projection)


def test_extent_digest_ignores_children_reorder_with_the_same_coverage():
    # A reorder changes the DECISION digest, never the extent: the coverage SET is identical.
    projection = _projection(*_nodes())
    root = projection.by_id["n-root"]
    mutated = _replace_node(projection, "n-root", children=("n-leaf-b", "n-sec"))
    assert extent_digest(mutated.by_id["n-root"], mutated) == extent_digest(root, projection)
    assert decision_digest(mutated.by_id["n-root"]) != decision_digest(root)


def test_extent_is_a_set_not_a_slot_map():
    # Conscious R1 property: re-slotting an atom (heading → signature) moves no coverage, so
    # NEITHER digest stales — the boundary rationale and the spanned content are both unchanged.
    projection = _projection(*_nodes())
    sec = projection.by_id["n-sec"]
    reslotted = _replace_node(
        projection, "n-sec", heading_atoms=(), signature_atoms=("canonical_00005", "canonical_00001")
    )
    assert extent_digest(reslotted.by_id["n-sec"], reslotted) == extent_digest(sec, projection)
    assert decision_digest(reslotted.by_id["n-sec"]) == decision_digest(sec)


def test_boundary_move_stales_exactly_the_affected_subtrees():
    # THE split's headline scenario: move an atom across a chapter boundary → both chapters'
    # extents stale, but the parent whose union is unchanged stays byte-identical (under the old
    # single digest the root always staled through its owned/child interplay or never saw it).
    ch1 = ContainerNode(
        node_id="n-ch1", node_class="chapter", minted_by=MINTED_BY_HUMAN, children=("n-leaf-a",)
    )
    ch2 = ContainerNode(
        node_id="n-ch2", node_class="chapter", minted_by=MINTED_BY_HUMAN, children=("n-leaf-b",)
    )
    root = ContainerNode(
        node_id="n-root", node_class="volume", minted_by=MINTED_BY_HUMAN, children=("n-ch1", "n-ch2")
    )
    _, _, leaf_a, leaf_b = _nodes()
    before = _projection(root, ch1, ch2, leaf_a, leaf_b)
    moved = _projection(
        root,
        ch1,
        ch2,
        dataclasses.replace(leaf_a, body_atoms=("canonical_00002",)),
        dataclasses.replace(leaf_b, body_atoms=("canonical_00003", "canonical_00004")),
    )
    assert extent_digest(moved.by_id["n-ch1"], moved) != extent_digest(ch1, before)
    assert extent_digest(moved.by_id["n-ch2"], moved) != extent_digest(ch2, before)
    assert extent_digest(moved.by_id["n-root"], moved) == extent_digest(root, before)
    for node_id in ("n-root", "n-ch1", "n-ch2"):
        assert decision_digest(moved.by_id[node_id]) == decision_digest(before.by_id[node_id])


def test_content_addition_cascades_extent_staleness_to_every_ancestor():
    # Accepted-as-honest (R1): new coverage under a leaf changes every enclosing extent — the
    # ancestors genuinely span more content than their evidence was authored against.
    projection = _projection(*_nodes())
    grown = _replace_node(
        projection, "n-leaf-a", body_atoms=("canonical_00002", "canonical_00003", "canonical_00099")
    )
    for node_id in ("n-sec", "n-root"):
        assert extent_digest(grown.by_id[node_id], grown) != extent_digest(
            projection.by_id[node_id], projection
        )


def test_extent_digest_fails_loud_on_a_dangling_child_ref():
    # Precondition documented (validated map); a dangling ref must fail loud, never KeyError-leak.
    sec = ContainerNode(
        node_id="n-sec", node_class="section", minted_by=MINTED_BY_HUMAN, children=("n-ghost",)
    )
    projection = ProjectionMap(root_id="n-sec", nodes=(sec,))
    with pytest.raises(ValueError, match="n-ghost"):
        extent_digest(sec, projection)


def test_extent_digest_fails_loud_on_a_multi_parent_diamond_not_just_true_cycles():
    # Delta re-audit F4: a DAG revisit (MULTI_PARENT territory) is not a cycle, but it is still an
    # unvalidated map — the walk refuses it with an honest diagnosis instead of double-counting.
    a = ContainerNode(node_id="n-a", node_class="section", minted_by=MINTED_BY_HUMAN, children=("n-s",))
    b = ContainerNode(node_id="n-b", node_class="section", minted_by=MINTED_BY_HUMAN, children=("n-s",))
    root = ContainerNode(
        node_id="n-r", node_class="volume", minted_by=MINTED_BY_HUMAN, children=("n-a", "n-b")
    )
    shared = LeafNode(
        node_id="n-s", node_class="block", minted_by=MINTED_BY_MACHINE, body_atoms=("canonical_00000",)
    )
    projection = ProjectionMap(root_id="n-r", nodes=(root, a, b, shared))
    with pytest.raises(ValueError, match="revisited.*multi-parent|multi-parent.*revisited"):
        extent_digest(root, projection)


def test_extent_digest_fails_loud_on_a_cycle_instead_of_hanging():
    # ProjectionMap construction admits a cycle (cycles are Tier-2's CYCLE code); the walk must
    # terminate with a diagnosis, not recurse forever.
    a = ContainerNode(node_id="n-a", node_class="section", minted_by=MINTED_BY_HUMAN, children=("n-b",))
    b = ContainerNode(node_id="n-b", node_class="section", minted_by=MINTED_BY_HUMAN, children=("n-a",))
    projection = ProjectionMap(root_id="n-a", nodes=(a, b))
    with pytest.raises(ValueError, match="cycle"):
        extent_digest(a, projection)


def test_digest_golden_pins():
    # Golden-master pin over BOTH producers' full composition (payload shape + canonical JSON +
    # sha256). The failure consequence is spelled out so a drift is never "fixed" by re-pinning
    # casually: these digests are persisted in authored sidecars (~61 entries for PLL), and a
    # payload change silently stales every one of them.
    consequence = (
        "digest payload/serialization drifted — every persisted sidecar entry (~61 authored "
        "containers for PLL) would read as stale; if this change is conscious, re-stamp the "
        "sidecars deliberately and update this pin in the same commit"
    )
    _, sec, _, _ = _nodes()
    projection = _projection(*_nodes())
    assert decision_digest(sec) == (
        "sha256:06a1af21c5da4e6d143e64527fa69e38e5e9d6a45deffbc94498380f99f2609b"
    ), consequence
    assert extent_digest(sec, projection) == (
        "sha256:2fe8d4674633a9a74425cd71d5d0606ab332157dbd4005200ce5aebd4414d4c8"
    ), consequence


# --- the gate: stale iff the bound node's OWN digest half changed (the named done-when) --------- #


@pytest.mark.parametrize(
    "changes, kinds",
    [
        # class change: n-sec's decision only — no extent moved anywhere, no cascade.
        ({"node_class": "part"}, ["stale-decision"]),
        # coverage change: n-sec's extent AND n-root's (root's transitive union genuinely
        # changed — the honest cascade), root first in reading order; decisions stay quiet.
        ({"heading_atoms": ("canonical_00009",)}, ["stale-extent", "stale-extent"]),
    ],
    ids=["decision-axis", "extent-axis"],
)
def test_digest_staleness_red_test(changes, kinds):
    # THE named done-when (§1.4.1c), post-split: each axis reds under its OWN kind, and the
    # orthogonal half stays quiet (asserted via the findings producer, not just the raise).
    projection = _projection(*_nodes())
    evidence = _fresh_evidence(projection)
    assert_evidence_gate(evidence, projection)  # fresh pair: green
    mutated = _replace_node(projection, "n-sec", **changes)
    with pytest.raises(EvidenceGateError, match="n-sec.*STALE|STALE.*n-sec"):
        assert_evidence_gate(evidence, mutated)
    assert [k for k, _ in evidence_findings(evidence, mutated)] == kinds


def test_children_reorder_is_a_decision_staleness_only():
    projection = _projection(*_nodes())
    evidence = _fresh_evidence(projection)
    mutated = _replace_node(projection, "n-root", children=("n-leaf-b", "n-sec"))
    assert [k for k, _ in evidence_findings(evidence, mutated)] == ["stale-decision"]


def test_descendant_rebinding_is_an_extent_staleness_cascade():
    # A leaf's coverage change stales the extent of EVERY enclosing container (n-sec and n-root),
    # decisions untouched — the honest-cascade half of the R1 semantics at gate level.
    projection = _projection(*_nodes())
    evidence = _fresh_evidence(projection)
    mutated = _replace_node(projection, "n-leaf-a", body_atoms=("canonical_00002",))
    findings = evidence_findings(evidence, mutated)
    assert [k for k, _ in findings] == ["stale-extent", "stale-extent"]
    assert "n-root" in findings[0][1] and "n-sec" in findings[1][1]


def test_both_digests_stale_reports_both_kinds_for_one_entry():
    projection = _projection(*_nodes())
    evidence = _fresh_evidence(projection)
    mutated = _replace_node(
        projection, "n-sec", node_class="part", heading_atoms=("canonical_00009",)
    )
    findings = evidence_findings(evidence, mutated)
    # the n-sec entry carries BOTH kinds independently (one hash could not say which half moved);
    # n-root co-fires stale-extent through the honest coverage cascade.
    assert [k for k, m in findings if "n-sec" in m] == ["stale-decision", "stale-extent"]
    assert [k for k, m in findings if "n-root" in m] == ["stale-extent"]


def test_map_revision_is_bookkeeping_never_the_staleness_trigger():
    # §1.4.1b: staleness keys on the digests and ONLY the digests. Entries stamped at wildly
    # different revisions stay fresh while digests match...
    projection = _projection(*_nodes())
    evidence = AuthoringEvidence(
        book=BOOK,
        entries=tuple(
            dataclasses.replace(e, authored_at_revision=999 + i)
            for i, e in enumerate(_fresh_evidence(projection).entries)
        ),
    )
    assert_evidence_gate(evidence, projection)  # green: revision drift is not staleness
    # ...and a digest drift reds regardless of any revision agreement.
    mutated = _replace_node(projection, "n-root", node_class="tome")
    with pytest.raises(EvidenceGateError, match="n-root"):
        assert_evidence_gate(evidence, mutated)


def test_gate_missing_evidence_for_a_human_container_reds_by_name():
    projection = _projection(*_nodes())
    fresh = _fresh_evidence(projection)
    evidence = AuthoringEvidence(
        book=BOOK, entries=tuple(e for e in fresh.entries if e.node_id != "n-sec")
    )
    with pytest.raises(EvidenceGateError, match=r"\[missing\].*n-sec.*no evidence"):
        assert_evidence_gate(evidence, projection)


def test_gate_orphan_and_misbound_entries_red_by_name():
    projection = _projection(*_nodes())
    fresh = _fresh_evidence(projection).entries
    orphan = EvidenceEntry(
        node_id="n-ghost",
        decision_digest="sha256:0",
        extent_digest="sha256:0",
        evidence="binds nothing",
        authored_at_revision=1,
    )
    _, _, leaf_a, _ = _nodes()
    misbound = EvidenceEntry(
        node_id="n-leaf-a",
        decision_digest=decision_digest(leaf_a),  # even FRESH digests cannot license a leaf entry
        extent_digest=extent_digest(leaf_a, projection),
        evidence="on a machine leaf",
        authored_at_revision=1,
    )
    # Each finding must carry its OWN kind: an orphan misreported as "misbound" (or vice versa)
    # is a dropped check hiding behind its neighbour, so the match pins the kind token.
    with pytest.raises(EvidenceGateError, match=r"\[orphaned\].*n-ghost"):
        assert_evidence_gate(AuthoringEvidence(book=BOOK, entries=(*fresh, orphan)), projection)
    with pytest.raises(EvidenceGateError, match=r"\[misbound\].*n-leaf-a"):
        assert_evidence_gate(AuthoringEvidence(book=BOOK, entries=(*fresh, misbound)), projection)


def test_gate_collects_every_finding_in_one_raise():
    projection = _projection(*_nodes())
    fresh = {e.node_id: e for e in _fresh_evidence(projection).entries}
    evidence = AuthoringEvidence(
        book=BOOK,
        entries=(
            # n-root entry MISSING; n-sec entry decision-stale; plus an orphan.
            dataclasses.replace(fresh["n-sec"], decision_digest="sha256:drifted"),
            EvidenceEntry(
                node_id="n-ghost",
                decision_digest="sha256:0",
                extent_digest="sha256:0",
                evidence="orphan",
                authored_at_revision=1,
            ),
        ),
    )
    with pytest.raises(EvidenceGateError) as err:
        assert_evidence_gate(evidence, projection)
    assert sorted(err.value.kinds) == ["missing", "orphaned", "stale-decision"]
    message = str(err.value)
    assert "n-root" in message and "n-sec" in message and "n-ghost" in message


def test_gate_green_on_a_fresh_complete_pair_returns_none():
    projection = _projection(*_nodes())
    assert assert_evidence_gate(_fresh_evidence(projection), projection) is None
    assert evidence_findings(_fresh_evidence(projection), projection) == ()


def test_the_raise_carries_exactly_the_producers_findings():
    # evidence_findings is THE single producer: the gate's raised payload is it, verbatim — a
    # second (drifting) enumeration inside the gate would break this identity.
    projection = _projection(*_nodes())
    evidence = AuthoringEvidence(book=BOOK, entries=())
    with pytest.raises(EvidenceGateError) as err:
        assert_evidence_gate(evidence, projection)
    assert err.value.findings == evidence_findings(evidence, projection)


def test_missing_findings_come_in_map_reading_order_not_id_order():
    # Reading order is how a human works a worklist: the map's node order, not lexicographic ids.
    z_first = ContainerNode(
        node_id="n-z", node_class="volume", minted_by=MINTED_BY_HUMAN, children=("n-a",)
    )
    a_second = ContainerNode(node_id="n-a", node_class="section", minted_by=MINTED_BY_HUMAN)
    projection = ProjectionMap(root_id="n-z", nodes=(z_first, a_second))
    findings = evidence_findings(AuthoringEvidence(book=BOOK, entries=()), projection)
    assert [k for k, _ in findings] == ["missing", "missing"]
    assert "n-z" in findings[0][1] and "n-a" in findings[1][1]


def test_gate_message_names_the_title_and_reprs_the_digests():
    projection = _projection(*_nodes())
    evidence = _fresh_evidence(projection)
    mutated = _replace_node(projection, "n-sec", node_class="part")
    with pytest.raises(EvidenceGateError) as err:
        assert_evidence_gate(evidence, mutated)
    message = str(err.value)
    assert "'A Section'" in message  # the human-facing title rides along with the opaque id
    assert "'sha256:" in message  # digests are repr'd, not raw-interpolated


def test_gate_message_cannot_be_forged_by_digest_content():
    # The injection fix: a pinned digest containing a newline + fake finding line must appear
    # escaped (repr), never verbatim — otherwise a crafted sidecar forges gate output.
    projection = _projection(*_nodes())
    fresh = {e.node_id: e for e in _fresh_evidence(projection).entries}
    forged = "sha256:x\n  [missing] human-minted container 'n-fake' has no evidence entry"
    evidence = AuthoringEvidence(
        book=BOOK,
        entries=tuple(
            dataclasses.replace(e, decision_digest=forged) if e.node_id == "n-sec" else e
            for e in fresh.values()
        ),
    )
    with pytest.raises(EvidenceGateError) as err:
        assert_evidence_gate(evidence, projection)
    assert forged not in str(err.value)  # raw newline payload never lands in the message
    assert "\\n" in str(err.value)  # it shows up escaped instead


# --- EvidenceGateError: the typed carrier --------------------------------------------------------- #


def test_evidence_gate_error_is_an_engine_error_at_the_next_free_exit_code():
    assert issubclass(EvidenceGateError, EngineError)
    assert EvidenceGateError.exit_code == 12
    taken = {
        getattr(engine_errors, name).exit_code
        for name in dir(engine_errors)
        if isinstance(getattr(engine_errors, name), type)
        and issubclass(getattr(engine_errors, name), EngineError)
    }
    assert 12 not in taken  # engine.errors taxonomy does not collide
    assert StructureValidationError.exit_code != EvidenceGateError.exit_code


def test_evidence_gate_error_rejects_an_empty_payload():
    with pytest.raises(ValueError, match="at least one"):
        EvidenceGateError(())


def test_evidence_gate_error_rejects_an_unknown_kind():
    # The kind set is CLOSED (deliberately not EC — §4.0 stays the structure-map vocabulary).
    with pytest.raises(ValueError, match="unknown evidence-finding kind"):
        EvidenceGateError([("typo-kind", "message")])


def test_evidence_finding_kinds_is_the_closed_five_kind_set():
    assert EVIDENCE_FINDING_KINDS == ("missing", "orphaned", "misbound", "stale-decision", "stale-extent")
    err = EvidenceGateError([(k, f"about {k}") for k in EVIDENCE_FINDING_KINDS])
    assert err.kinds == EVIDENCE_FINDING_KINDS
    assert all(f"[{k}]" in str(err) for k in EVIDENCE_FINDING_KINDS)


# --- model hygiene ------------------------------------------------------------------------------ #


def test_duplicate_entries_for_one_node_are_rejected_at_construction():
    # The gate's correspondence is ONE entry per container; a keyed table cannot hold two.
    entry = EvidenceEntry(
        node_id="n-root",
        decision_digest="sha256:a",
        extent_digest="sha256:b",
        evidence="first",
        authored_at_revision=0,
    )
    twin = dataclasses.replace(entry, evidence="second")
    with pytest.raises(ValueError, match="duplicate"):
        AuthoringEvidence(book=BOOK, entries=(entry, twin))


@pytest.mark.parametrize(
    "changes",
    [
        {"node_id": ""},
        {"node_id": "   "},
        {"node_id": 5},
        {"decision_digest": ""},
        {"decision_digest": "\u200b"},
        {"extent_digest": "   "},
        {"extent_digest": ["sha256:a"]},
        {"evidence": "   "},  # whitespace-only prose is no evidence
        {"evidence": "\u200b\u2060\ufeff"},  # zero-width-only prose is no evidence either
        {"evidence": "x\ud800y"},  # lone surrogate: loads from JSON escapes, can never re-render
        {"evidence": 5},
        {"authored_at_revision": True},
        {"authored_at_revision": 2.0},
        {"authored_at_revision": -1},
    ],
    ids=[
        "node_id-empty",
        "node_id-whitespace",
        "node_id-nonstr",
        "decision-empty",
        "decision-zero-width",
        "extent-whitespace",
        "extent-nonstr",
        "evidence-blank",
        "evidence-zero-width",
        "evidence-lone-surrogate",
        "evidence-nonstr",
        "revision-bool",
        "revision-float",
        "revision-negative",
    ],
)
def test_entry_model_rejects_degenerate_fields(changes):
    valid = dict(
        node_id="n-1",
        decision_digest="sha256:a",
        extent_digest="sha256:b",
        evidence="why",
        authored_at_revision=0,
    )
    with pytest.raises((ValueError, TypeError)):
        EvidenceEntry(**{**valid, **changes})


@pytest.mark.parametrize(
    "book", ["", "   ", "\u200b", 5], ids=["empty", "whitespace", "zero-width", "nonstr"]
)
def test_evidence_model_rejects_a_degenerate_book(book):
    with pytest.raises((ValueError, TypeError)):
        AuthoringEvidence(book=book, entries=())


# --- load boundary: total contract, one axis per negative --------------------------------------- #

_VALID_ENTRY = {
    "node_id": "n-root",
    "decision_digest": "sha256:abc",
    "extent_digest": "sha256:def",
    "evidence": "why this container exists",
    "authored_at_revision": 0,
}


def _valid_doc() -> dict:
    return {
        "schema_version": AUTHORING_EVIDENCE_SCHEMA_VERSION,
        "stale_class": AUTHORING_EVIDENCE_STALE_CLASS,
        "book": BOOK,
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
    assert evidence.book == BOOK
    assert len(evidence.entries) == 1
    entry = evidence.entries[0]
    assert entry.node_id == "n-root"
    assert entry.decision_digest == "sha256:abc"
    assert entry.extent_digest == "sha256:def"
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


def test_unreadable_file_is_stale_not_a_crash(tmp_path):
    # is_file() passes, read fails (permissions): the OSError family must land inside the total
    # contract, not escape as a PermissionError traceback.
    path = _write(tmp_path, _valid_doc())
    path.chmod(0o000)
    try:
        with pytest.raises(StaleArtifactError, match="unreadable"):
            load_authoring_evidence(path)
    finally:
        path.chmod(0o644)


def test_parse_depth_blowup_is_stale_not_a_recursion_crash(tmp_path):
    # A pathologically nested document blows json's recursive parser; RecursionError must be
    # wrapped at the boundary like any other unparseable content.
    with pytest.raises(StaleArtifactError, match="not valid JSON|nested"):
        load_authoring_evidence(_write(tmp_path, "[" * 100_000))


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
        lambda d: _drop(d, "stale_class"),
        lambda d: {**d, "stale_class": "atom-store"},
        lambda d: _drop(d, "book"),
        lambda d: {**d, "book": ""},
        lambda d: {**d, "book": "   "},  # Tier-1-legal, model-rejected: wrap proven
        lambda d: _drop(d, "entries"),
        lambda d: {**d, "entries": {}},  # not an array
        lambda d: {**d, "stray": 1},  # additionalProperties: false, top level
        lambda d: _drop_entry_key(d, "node_id"),
        lambda d: _drop_entry_key(d, "decision_digest"),
        lambda d: _drop_entry_key(d, "extent_digest"),
        lambda d: _drop_entry_key(d, "evidence"),
        lambda d: _drop_entry_key(d, "authored_at_revision"),
        lambda d: _set_entry(d, "node_id", ""),
        lambda d: _set_entry(d, "node_id", "   "),  # Tier-1-legal, model-rejected: wrap proven
        lambda d: _set_entry(d, "evidence", "   "),
        lambda d: _set_entry(d, "evidence", "\u200b"),  # zero-width: minLength cannot see it
        lambda d: _set_entry(d, "authored_at_revision", 2.0),  # Tier-1 "integer" admits it
        lambda d: _set_entry(d, "authored_at_revision", -1),
        lambda d: _set_entry(d, "stray", 1),  # additionalProperties: false, entry level
        lambda d: {**d, "entries": [dict(_VALID_ENTRY), dict(_VALID_ENTRY)]},  # duplicate node_id
        lambda d: json.dumps(d).replace('"sha256:abc"', "NaN"),  # non-finite token
        # JSON-escaped lone surrogate: json.loads admits it, UTF-8 re-render never can — the
        # model rejects it and the loader wraps that (delta re-audit F3)
        lambda d: json.dumps(d).replace('"why this container exists"', '"x\\ud800y"'),
    ],
    ids=[
        "not-json",
        "top-level-array",
        "stale-version",
        "bool-version",
        "missing-version",
        "missing-stale-class",
        "wrong-stale-class",
        "missing-book",
        "empty-book",
        "whitespace-book",
        "missing-entries",
        "entries-not-array",
        "stray-top-key",
        "entry-missing-node_id",
        "entry-missing-decision_digest",
        "entry-missing-extent_digest",
        "entry-missing-evidence",
        "entry-missing-revision",
        "entry-empty-node_id",
        "entry-whitespace-node_id",
        "entry-blank-evidence",
        "entry-zero-width-evidence",
        "entry-float-revision",
        "entry-negative-revision",
        "entry-stray-key",
        "duplicate-node_id",
        "nan-token",
        "surrogate-evidence",
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


def test_wrong_stale_class_reads_as_a_routing_failure_not_a_shape_failure(tmp_path):
    # Same M3 discipline for the layer discriminator: a foreign artifact under this filename must
    # say "not an authoring-evidence sidecar", not fail as a generic shape mismatch.
    doc = _valid_doc()
    doc["stale_class"] = "atom-store"
    with pytest.raises(StaleArtifactError, match="not an authoring-evidence sidecar"):
        load_authoring_evidence(_write(tmp_path, doc))


def test_expected_book_binds_the_sidecar_to_its_workspace(tmp_path):
    # R2: a structurally valid sidecar from ANOTHER book is the wrong artifact, not a loadable one.
    path = _write(tmp_path, _valid_doc())
    assert load_authoring_evidence(path, expected_book=BOOK).book == BOOK
    with pytest.raises(StaleArtifactError, match="otherbook.*testbook|testbook.*otherbook"):
        load_authoring_evidence(path, expected_book="otherbook")


def test_schema_const_binds_to_the_python_constant(tmp_path):
    # The inv 10 two-assertion idiom: the schema literal equals the live constant AND a
    # version-derived conforming document actually loads — so neither can drift alone.
    assert evidence_schema_version_const() == AUTHORING_EVIDENCE_SCHEMA_VERSION
    assert load_authoring_evidence(_write(tmp_path, _valid_doc())).entries


# --- the engine writer (R3): render / deny-by-default write / entry builder --------------------- #


def test_render_write_load_roundtrip(tmp_path):
    projection = _projection(*_nodes())
    evidence = _fresh_evidence(projection)
    path = tmp_path / AUTHORING_EVIDENCE_FILENAME
    assert write_authoring_evidence(path, evidence) == path
    loaded = load_authoring_evidence(path, expected_book=BOOK)
    assert loaded == evidence
    assert_evidence_gate(loaded, projection)  # the persisted form passes the gate it exists for
    # the writer persists exactly the renderer's canonical form (newline-terminated) — a writer
    # serializing independently of render_authoring_evidence would break byte-idempotence
    on_disk = path.read_text(encoding="utf-8")
    assert on_disk == render_authoring_evidence(evidence)
    assert on_disk.endswith("\n")


def test_write_is_deny_by_default_against_a_differing_sidecar(tmp_path):
    # The write_freeze_record posture: hand-authored prose is irreproducible (P4) — identical
    # bytes are an idempotent no-op, a differing record is refused without force.
    projection = _projection(*_nodes())
    evidence = _fresh_evidence(projection)
    path = tmp_path / AUTHORING_EVIDENCE_FILENAME
    write_authoring_evidence(path, evidence)
    write_authoring_evidence(path, evidence)  # idempotent no-op
    differing = AuthoringEvidence(
        book=BOOK,
        entries=tuple(
            dataclasses.replace(e, evidence="rewritten rationale") for e in evidence.entries
        ),
    )
    with pytest.raises(StaleArtifactError, match="refusing"):
        write_authoring_evidence(path, differing)
    assert load_authoring_evidence(path) == evidence  # the authored prose survived the refusal
    write_authoring_evidence(path, differing, force=True)
    assert load_authoring_evidence(path) == differing


def test_build_evidence_entry_stamps_both_digests_via_the_producers():
    projection = _projection(*_nodes())
    sec = projection.by_id["n-sec"]
    entry = build_evidence_entry(sec, projection, evidence="the scan shows a part break", authored_at_revision=3)
    assert entry.node_id == "n-sec"
    assert entry.decision_digest == decision_digest(sec)
    assert entry.extent_digest == extent_digest(sec, projection)
    assert entry.authored_at_revision == 3


def test_build_evidence_entry_refuses_a_node_the_gate_would_flag():
    # Authoring-time mirror of the misbound finding: stamping evidence onto a machine leaf is a
    # caller error at the builder, not a latent gate failure later.
    projection = _projection(*_nodes())
    with pytest.raises(ValueError, match="not a human-minted container"):
        build_evidence_entry(
            projection.by_id["n-leaf-a"], projection, evidence="nope", authored_at_revision=0
        )


# --- artifact location --------------------------------------------------------------------------- #


def test_authoring_evidence_path_is_the_work_root_companion(tmp_path):
    from engine.paths import BookWorkspace

    workspace = BookWorkspace.for_book("testbook", tmp_path).ensure()
    path = authoring_evidence_path(workspace)
    assert path.name == AUTHORING_EVIDENCE_FILENAME
    assert path.parent == workspace.root
