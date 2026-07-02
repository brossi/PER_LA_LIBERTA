"""S4.1 / B-2 + S4.2 / B-3 — the L2 projection model (``projection.py``): nodes, the flat table,
ownership, and node identity.

The L2 layer re-groups + re-types the L1 atom stream into a tree of **container** and **leaf**
:class:`~engine.structure.projection.Node`\\ s, each addressed by an opaque ``node_id`` and each
*owning* a disjoint slice of the atom stream (ENGINE_STRUCTURE_PLAN §3.1; s4_plan §3.B, §3.J). This
module is the **Phase-1** slice (s4_plan §4.2): the per-module validators in ``projection.py`` raise
the ``EC.*`` codes **directly** and are red-tested **against in-memory dataclasses** — the aggregate
``validate_structure_map`` and the born-agnostic loader are B-5. Container-xor-leaf is enforced **by
construction** (a node is *either* a ``ContainerNode`` *or* a ``LeafNode`` — you cannot build one
holding both ``children`` and ``body_atoms``), so no separate B-2 invariant is owed for it (the
Tier-1 ``oneOf`` red, inv 2, is B-5).

Invariants (each proven red by a targeted SUT mutation — red-first, ENGINE_STRUCTURE_PLAN §9;
mutation cycles run under ``PYTHONDONTWRITEBYTECODE=1`` / ``__pycache__`` purge, X13):
  - **inv 16 — ``node_id`` uniqueness (Tier-2a precondition, short-circuit).** Two nodes with one
    ``node_id`` fail at :class:`ProjectionMap` construction — you cannot build the keyed table with a
    collision — raising ``DUPLICATE_NODE_ID`` on the *second* insert, before any collect-all check
    runs (§3.C.1e/§4.1). Drop the in-``__post_init__`` collision check → the later node silently
    overwrites the earlier and construction passes → ``test_duplicate_node_id_*`` red.
  - **inv 1a — no double-ownership → ``DUP_OWNERSHIP``.** An ``atom_id`` in two of the four ownership
    buckets ``{heading_atoms, signature_atoms, body_atoms, header furniture_atoms}`` (X4 folds
    furniture in). Drop the dedup accounting → the shared atom passes → ``test_*double_ownership*`` red.
  - **inv 1b — coverage → ``UNOWNED_INCLUDED_ATOM`` / ``OWNED_EXCLUDED_ATOM``.** (A) an *included*
    canonical-stream atom owned by no node raises; (B, exemption) an *excluded* furniture atom owned
    by no node passes — coverage ranges over ``atom_store.included_atom_ids()`` only; (C) an
    *excluded* atom (``scope_of() == excluded``) placed in a node slot raises ``OWNED_EXCLUDED_ATOM``.
  - **inv 26 — empty-container rejection → ``EMPTY_CONTAINER``.** A container with zero ``children``
    *and* no ``heading_atoms``/``signature_atoms`` (a pure projection check, no atom_store, P3B-9).
    Drop the check → the empty container passes → ``test_empty_container_*`` red. A container holding
    only a heading is **not** empty (the check is the conjunction, not "no children").
  - **inv 27 — ``body_atoms`` strict order → ``BODY_ATOMS_UNORDERED``.** A leaf's ``body_atoms`` must
    be strictly ascending by canonical-stream index (non-contiguous OK) with no intra-list duplicate.
    Checked **as-stored** — a ``sorted()``-copy-first mutation makes a descending list pass → the
    order test red (the P3B-3 vacuity the plan calls out).
  - **inv 3 — ragged depth + heterogeneous siblings validate.** A tree mixing branch depths and
    leaf/container siblings passes; a hard-coded uniform-depth check would red the ragged fixture.
  - **inv 7 — ``minted_by`` recorded + split enforced both ways → ``MINTED_BY_SPLIT`` (B-3/§3.C.2).**
    A container must be ``human``-minted and a leaf ``machine``-minted; a blank/wrong/out-of-vocab
    ``minted_by`` fires. Drop or one-side the split check → the mirror fixture passes → red.
  - **inv 6 — ``node_id`` rejects the enumerated derivation cheats → ``NODE_ID_DERIVED`` (B-3/§3.C.3).**
    The arg-free ``mint_node_id()`` seam is the primary control (it never sees a
    designation/title/path/content); the validator is the belt-and-braces that rejects a hand-authored
    id equal to the designation (exact/casefold), ``_slug(designation)``/``_slug(title)``, or the
    node's position-path. The substring-of-rendered-handle cheat re-runs at B-4.
  - **inv 4 / inv 5 — ``node_id`` stable across re-serialize / positional move (B-3).** Must-not-bake
    property guards: the id is a *stored* opaque field, so it survives an ``asdict``/``replace`` copy
    (inv 4) and a sibling reorder (inv 5); a position-DERIVING impl is caught by inv 6's position-path
    cheat (the two fold, §4.1.x items 5/6).
  - **inv 15 — neutrality.** ``projection.py`` carries no language/book literal — auto-covered by the
    dynamic ``structure/*.py`` glob in ``test_structure_neutrality.py`` (no test lives here).

Collect-all vs short-circuit (§4.1): the Tier-2b checks (1a/1b/26/27 + 6/7) accumulate and raise
**once** with the whole code set as payload; the Tier-2a precondition (16, ``DUPLICATE_NODE_ID``)
short-circuits at construction. Both carry an ``EC`` payload on the same
:class:`~engine.structure.errors.StructureValidationError` (the exception deferred from B-1, now
homed beside the code vocabulary it carries).
"""

from __future__ import annotations

import dataclasses
import inspect

import pytest

import engine.structure as structure
from engine.errors import EngineError
from engine.structure import (
    PROCESSING_SCOPE_EXCLUDED,
    PROCESSING_SCOPE_INCLUDED,
    EC,
    ContainerNode,
    FurnitureAtom,
    LeafNode,
    Node,
    ProjectionMap,
    StructureValidationError,
    mint_node_id,
    validate_projection,
)


# --- atom_store double (the thin reader S4 takes — §4 header) ------------------------------------ #


class _Store:
    """A minimal atom_store exposing the two capabilities ``validate_projection`` reads at B-2:
    ``included_atom_ids()`` (the ordered canonical-stream universe — coverage + ordering key) and
    ``scope_of()`` (processing scope — the OWNED_EXCLUDED discriminator). ``included`` is given in
    canonical-stream order, so an atom's index in it *is* its canonical index (inv 27).

    Unknown atoms return ``None`` from ``scope_of`` — B-2 never asserts on a dangling atom
    (``DANGLING_ATOM_REF`` / ``contains()`` is inv 17, B-5), so the fixtures always register every
    atom they own.
    """

    def __init__(self, included: tuple[str, ...], excluded: tuple[str, ...] = ()) -> None:
        self._included = tuple(included)
        self._scope: dict[str, str] = {a: PROCESSING_SCOPE_INCLUDED for a in included}
        for a in excluded:
            self._scope[a] = PROCESSING_SCOPE_EXCLUDED

    def included_atom_ids(self):
        return self._included

    def scope_of(self, atom_id: str):
        return self._scope.get(atom_id)


# --- builders: a known-good base map, perturbed one axis at a time (isolation, P3B-6) ------------ #
#
# Canonical stream a0..a5 (all included). The base map: root container → [ch1 container, ch2 leaf];
# ch1 → [leaf1a, leaf1b]. Every included atom is owned exactly once, and every node's minted_by
# matches its kind (containers human, leaves machine), so a single-violation fixture built by
# perturbing ONE node fires ONLY its own code (nothing co-fires) — the isolation the specific-token
# asserts below rely on.


def _base_store() -> _Store:
    return _Store(included=("a0", "a1", "a2", "a3", "a4", "a5"))


def _base_nodes() -> tuple[Node, ...]:
    return (
        ContainerNode(node_id="root", node_class="document", minted_by="human", children=("ch1", "ch2"), heading_atoms=("a0",)),
        ContainerNode(node_id="ch1", node_class="section", minted_by="human", children=("leaf1a", "leaf1b"), heading_atoms=("a1",)),
        LeafNode(node_id="leaf1a", node_class="para", minted_by="machine", body_atoms=("a2",)),
        LeafNode(node_id="leaf1b", node_class="para", minted_by="machine", body_atoms=("a3", "a4")),
        LeafNode(node_id="ch2", node_class="para", minted_by="machine", body_atoms=("a5",)),
    )


def _base_map(nodes: tuple[Node, ...] | None = None, furniture=()) -> ProjectionMap:
    return ProjectionMap(root_id="root", nodes=nodes if nodes is not None else _base_nodes(), furniture_atoms=furniture)


def _codes(err: StructureValidationError) -> set[EC]:
    return set(err.codes)


# --- baseline: the well-formed map validates ---------------------------------------------------- #


def test_base_map_validates_clean():
    # The known-good fixture passes — the floor every single-violation test perturbs away from. A
    # false-positive here (a check firing on a clean map) would mask every isolation assertion. Now
    # also exercises the positive minted_by split (containers human, leaves machine) and the clean
    # node_id_derived path (opaque ids, no designation matching any cheat).
    validate_projection(_base_map(), _base_store())  # no raise


# --- container-xor-leaf BY CONSTRUCTION (no separate invariant; the model makes it unbuildable) -- #


def test_container_and_leaf_are_distinct_variants_of_the_node_union():
    # inv 2 is a B-5 Tier-1 oneOf; at B-2 the *model* forbids both-slots by having two types. A
    # ContainerNode has no body_atoms; a LeafNode has no children — neither can hold both.
    assert isinstance(ContainerNode(node_id="c", node_class="k", minted_by="human", children=("x",)), Node)
    assert isinstance(LeafNode(node_id="l", node_class="k", minted_by="machine", body_atoms=("a",)), Node)
    assert not hasattr(ContainerNode(node_id="c", node_class="k", minted_by="human", heading_atoms=("a",)), "body_atoms")
    assert not hasattr(LeafNode(node_id="l", node_class="k", minted_by="machine", body_atoms=("a",)), "children")


def test_nodes_store_children_not_parent():
    # §3.B.4 storage posture: persist children only, derive parent on load. Neither variant carries a
    # stored ``parent`` — a parent field would be the second source of truth the derive-on-load design
    # exists to avoid.
    assert not hasattr(ContainerNode(node_id="c", node_class="k", minted_by="human", children=("x",)), "parent")
    assert not hasattr(LeafNode(node_id="l", node_class="k", minted_by="machine", body_atoms=("a",)), "parent")


def test_nodes_and_map_are_frozen():
    # Frozen like every other model in structure/: an addressed projection is a record, re-grouping
    # produces a new one (R3/D5). A retained mutable handle cannot undermine the atom-ownership sets.
    c = ContainerNode(node_id="c", node_class="k", minted_by="human", children=("x",))
    lf = LeafNode(node_id="l", node_class="k", minted_by="machine", body_atoms=("a",))
    m = _base_map()
    with pytest.raises(dataclasses.FrozenInstanceError):
        c.node_id = "other"  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        lf.node_id = "other"  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        m.root_id = "other"  # type: ignore[misc]


def test_sequence_fields_normalize_to_tuples():
    # A list passed in is stored as a tuple (the Atom/Geom idiom) so the frozen guarantee can't be
    # undermined by mutating a retained list handle. Every sequence field on every model — including
    # signature_atoms and the map's nodes/furniture_atoms — normalizes.
    c = ContainerNode(node_id="c", node_class="k", minted_by="human", children=["x", "y"], heading_atoms=["a"], signature_atoms=["s"])
    lf = LeafNode(node_id="l", node_class="k", minted_by="machine", body_atoms=["a", "b"])
    assert isinstance(c.children, tuple) and isinstance(c.heading_atoms, tuple) and isinstance(c.signature_atoms, tuple)
    assert isinstance(lf.body_atoms, tuple)
    m = ProjectionMap(root_id="root", nodes=[c, lf], furniture_atoms=[FurnitureAtom(atom_id="f", capture_role="r")])
    assert isinstance(m.nodes, tuple) and isinstance(m.furniture_atoms, tuple)


# --- inv 16 — node_id uniqueness (Tier-2a precondition, at construction, short-circuit) ---------- #


def test_duplicate_node_id_rejected_at_construction():
    # inv 16: two nodes with one node_id fail when the keyed table is built (§3.C.1e). Raised on the
    # *second* insert as DUPLICATE_NODE_ID — a Tier-2a precondition, not a collect-all code.
    dup = (
        ContainerNode(node_id="root", node_class="document", minted_by="human", children=("x",), heading_atoms=("a0",)),
        LeafNode(node_id="x", node_class="para", minted_by="machine", body_atoms=("a1",)),
        LeafNode(node_id="x", node_class="para", minted_by="machine", body_atoms=("a2",)),  # collides
    )
    with pytest.raises(StructureValidationError) as ei:
        ProjectionMap(root_id="root", nodes=dup)
    assert EC.DUPLICATE_NODE_ID in _codes(ei.value)


def test_duplicate_node_id_short_circuits_before_collect_all():
    # P3A-5: the precondition raises at construction, so the collect-all pass never runs — a map that
    # ALSO has a Tier-2b violation (here an empty container) surfaces ONLY DUPLICATE_NODE_ID, not the
    # downstream code. This is what makes DUPLICATE_NODE_ID deliberately exempt from collect-all.
    nodes = (
        ContainerNode(node_id="root", node_class="document", minted_by="human", children=("dupe",), heading_atoms=("a0",)),
        ContainerNode(node_id="dupe", node_class="section", minted_by="human"),  # would be EMPTY_CONTAINER under collect-all
        ContainerNode(node_id="dupe", node_class="section", minted_by="human", heading_atoms=("a1",)),  # node_id collision
    )
    with pytest.raises(StructureValidationError) as ei:
        ProjectionMap(root_id="root", nodes=nodes)
    codes = _codes(ei.value)
    assert EC.DUPLICATE_NODE_ID in codes
    assert EC.EMPTY_CONTAINER not in codes  # collect-all never ran (short-circuit)


# --- inv 1a — no double-ownership (DUP_OWNERSHIP), furniture is the 4th bucket (X4) -------------- #


def test_atom_in_heading_and_body_is_double_ownership():
    # a1 is owned by both ch1.heading_atoms and leaf1a.body_atoms — two of the four buckets. leaf1a
    # keeps a2 too, so a2 stays owned and only DUP_OWNERSHIP fires (single-violation isolation — if
    # leaf1a dropped a2, a2 would orphan and UNOWNED_INCLUDED_ATOM would co-fire, breaking isolation).
    nodes = (
        ContainerNode(node_id="root", node_class="document", minted_by="human", children=("ch1", "ch2"), heading_atoms=("a0",)),
        ContainerNode(node_id="ch1", node_class="section", minted_by="human", children=("leaf1a", "leaf1b"), heading_atoms=("a1",)),
        LeafNode(node_id="leaf1a", node_class="para", minted_by="machine", body_atoms=("a1", "a2")),  # a1 again (double-owned); a2 kept
        LeafNode(node_id="leaf1b", node_class="para", minted_by="machine", body_atoms=("a3", "a4")),
        LeafNode(node_id="ch2", node_class="para", minted_by="machine", body_atoms=("a5",)),
    )
    with pytest.raises(StructureValidationError) as ei:
        validate_projection(ProjectionMap(root_id="root", nodes=nodes), _base_store())
    codes = _codes(ei.value)
    assert EC.DUP_OWNERSHIP in codes
    assert EC.UNOWNED_INCLUDED_ATOM not in codes  # isolation: a2 stays owned, so nothing co-fires


def test_atom_in_a_node_slot_and_furniture_is_double_ownership():
    # X4: furniture_atoms is the fourth ownership bucket — an atom in a node slot AND the header
    # furniture list is double-owned. This is the mutation that reds if furniture is dropped from the
    # bucket accounting. a5 is a canonical body atom; furniture normally carries excluded/witness ids,
    # but the disjointness check is by id across all four buckets regardless of scope.
    furniture = (FurnitureAtom(atom_id="a5", capture_role="running-head"),)
    with pytest.raises(StructureValidationError) as ei:
        validate_projection(_base_map(furniture=furniture), _base_store())
    assert EC.DUP_OWNERSHIP in _codes(ei.value)


def test_same_atom_in_two_leaves_is_double_ownership():
    # An included atom owned by two different leaves is double-owned too (an atom belongs to exactly
    # one node). The bucket key is (node_id, slot), so two body slots on different nodes are two
    # distinct buckets — caught.
    nodes = (
        ContainerNode(node_id="root", node_class="document", minted_by="human", children=("l1", "l2"), heading_atoms=("a0",)),
        LeafNode(node_id="l1", node_class="para", minted_by="machine", body_atoms=("a1", "a2")),
        LeafNode(node_id="l2", node_class="para", minted_by="machine", body_atoms=("a2", "a3")),  # a2 shared with l1
    )
    store = _Store(included=("a0", "a1", "a2", "a3"))
    with pytest.raises(StructureValidationError) as ei:
        validate_projection(ProjectionMap(root_id="root", nodes=nodes), store)
    assert EC.DUP_OWNERSHIP in _codes(ei.value)


def test_duplicate_furniture_atom_is_not_double_ownership():
    # Furniture is ONE of the four buckets. The same atom_id in two FurnitureAtom entries is a within-
    # bucket repeat (like a within-slot repeat), NOT "two of the four buckets" → no DUP_OWNERSHIP. This
    # pins the furniture-vs-slot dedup symmetry; drop the furniture dedup and this reds (the repeat
    # fires a spurious cross-bucket DUP_OWNERSHIP). The base map covers a0..a5, so nothing else fires.
    furniture = (
        FurnitureAtom(atom_id="a9", capture_role="page-number"),
        FurnitureAtom(atom_id="a9", capture_role="page-number"),  # same id, second entry
    )
    store = _Store(included=("a0", "a1", "a2", "a3", "a4", "a5"), excluded=("a9",))
    validate_projection(_base_map(furniture=furniture), store)  # no raise


def test_duplicate_heading_atom_is_not_double_ownership():
    # A repeated atom_id WITHIN one heading_atoms slot is one bucket (the node-slot dedup), not
    # cross-bucket DUP_OWNERSHIP. Unlike body_atoms, heading/signature carry no inv-27 ordering/dup
    # code, so the repeat is silently allowed — the spec pins no intra-heading uniqueness. Pins the
    # node-slot dedup via the non-body path: drop that dedup and a0×2 spuriously fires DUP_OWNERSHIP.
    nodes = (
        ContainerNode(node_id="root", node_class="document", minted_by="human", children=("l",), heading_atoms=("a0", "a0")),
        LeafNode(node_id="l", node_class="para", minted_by="machine", body_atoms=("a1",)),
    )
    store = _Store(included=("a0", "a1"))
    validate_projection(ProjectionMap(root_id="root", nodes=nodes), store)  # no raise


def test_excluded_atom_repeated_in_one_slot_reports_owned_excluded_once():
    # An excluded atom repeated within one body_atoms list is deduped in the coverage scan, so
    # OWNED_EXCLUDED_ATOM is reported ONCE, not once per occurrence (the payload carries multiplicity).
    # The repeat also trips BODY_ATOMS_UNORDERED (inv 27) — that is a separate code.
    nodes = (
        ContainerNode(node_id="root", node_class="document", minted_by="human", children=("l",), heading_atoms=("a0",)),
        LeafNode(node_id="l", node_class="para", minted_by="machine", body_atoms=("a1", "a9", "a9")),  # a9 excluded, twice
    )
    store = _Store(included=("a0", "a1"), excluded=("a9",))
    with pytest.raises(StructureValidationError) as ei:
        validate_projection(ProjectionMap(root_id="root", nodes=nodes), store)
    assert ei.value.codes.count(EC.OWNED_EXCLUDED_ATOM) == 1  # deduped: one finding, not two


# --- inv 1b — coverage (UNOWNED_INCLUDED_ATOM / OWNED_EXCLUDED_ATOM) ----------------------------- #


def test_unowned_included_atom_raises():
    # Mutation (A): the canonical stream has a6, owned by no node → UNOWNED_INCLUDED_ATOM. Coverage
    # is over included_atom_ids(); the base nodes own a0..a5 only.
    store = _Store(included=("a0", "a1", "a2", "a3", "a4", "a5", "a6"))  # a6 unowned
    with pytest.raises(StructureValidationError) as ei:
        validate_projection(_base_map(), store)
    assert EC.UNOWNED_INCLUDED_ATOM in _codes(ei.value)


def test_unowned_excluded_furniture_atom_passes():
    # Mutation (B, exemption): an *excluded* atom (a9) owned by no node does NOT raise — coverage
    # ranges over the included universe only. It is captured as furniture in the header, never forced
    # into a node. Proves the coverage universe is included_atom_ids(), not "every atom the store knows".
    store = _Store(included=("a0", "a1", "a2", "a3", "a4", "a5"), excluded=("a9",))
    validate_projection(_base_map(furniture=(FurnitureAtom(atom_id="a9", capture_role="page-number"),)), store)  # no raise


def test_excluded_atom_in_a_node_slot_raises_owned_excluded():
    # Mutation (C): an atom whose scope_of() is 'excluded' (a witness-level furniture atom, a9) placed
    # in a leaf's body_atoms → OWNED_EXCLUDED_ATOM. A node slot may own only included atoms.
    nodes = (
        ContainerNode(node_id="root", node_class="document", minted_by="human", children=("l",), heading_atoms=("a0",)),
        LeafNode(node_id="l", node_class="para", minted_by="machine", body_atoms=("a1", "a9")),  # a9 is excluded
    )
    store = _Store(included=("a0", "a1"), excluded=("a9",))
    with pytest.raises(StructureValidationError) as ei:
        validate_projection(ProjectionMap(root_id="root", nodes=nodes), store)
    assert EC.OWNED_EXCLUDED_ATOM in _codes(ei.value)


# --- inv 26 — empty-container rejection (EMPTY_CONTAINER; pure projection, no atom_store) -------- #


def test_empty_container_raises():
    # A container with zero children AND no heading/signature atoms owns nothing and leads nowhere —
    # EMPTY_CONTAINER. Built so nothing else is wrong (all included atoms still owned elsewhere), so
    # the payload isolates this code.
    nodes = (
        ContainerNode(node_id="root", node_class="document", minted_by="human", children=("empty", "l"), heading_atoms=("a0",)),
        ContainerNode(node_id="empty", node_class="section", minted_by="human"),  # no children, no heading/signature
        LeafNode(node_id="l", node_class="para", minted_by="machine", body_atoms=("a1", "a2", "a3", "a4", "a5")),
    )
    with pytest.raises(StructureValidationError) as ei:
        validate_projection(ProjectionMap(root_id="root", nodes=nodes), _base_store())
    assert EC.EMPTY_CONTAINER in _codes(ei.value)


def test_container_with_only_heading_is_not_empty():
    # The check is the conjunction (no children AND no heading AND no signature): a container holding
    # only a heading atom (a section head whose body has not been projected yet) is legitimate. Guards
    # against a mutation that reduces the check to "no children".
    nodes = (
        ContainerNode(node_id="root", node_class="document", minted_by="human", children=("head_only", "l"), heading_atoms=("a0",)),
        ContainerNode(node_id="head_only", node_class="section", minted_by="human", heading_atoms=("a1",)),  # heading, no children
        LeafNode(node_id="l", node_class="para", minted_by="machine", body_atoms=("a2", "a3", "a4", "a5")),
    )
    validate_projection(ProjectionMap(root_id="root", nodes=nodes), _base_store())  # no raise


# --- inv 27 — body_atoms strict ordering (BODY_ATOMS_UNORDERED), checked AS-STORED (P3B-3) ------- #


def test_body_atoms_out_of_canonical_order_raises():
    # leaf1b's body_atoms are (a4, a3) — descending canonical index. Checked as-stored, this is not
    # strictly ascending → BODY_ATOMS_UNORDERED. A sorted()-copy-first mutation would make it pass.
    nodes = (
        ContainerNode(node_id="root", node_class="document", minted_by="human", children=("ch1", "ch2"), heading_atoms=("a0",)),
        ContainerNode(node_id="ch1", node_class="section", minted_by="human", children=("leaf1a", "leaf1b"), heading_atoms=("a1",)),
        LeafNode(node_id="leaf1a", node_class="para", minted_by="machine", body_atoms=("a2",)),
        LeafNode(node_id="leaf1b", node_class="para", minted_by="machine", body_atoms=("a4", "a3")),  # descending
        LeafNode(node_id="ch2", node_class="para", minted_by="machine", body_atoms=("a5",)),
    )
    with pytest.raises(StructureValidationError) as ei:
        validate_projection(ProjectionMap(root_id="root", nodes=nodes), _base_store())
    assert EC.BODY_ATOMS_UNORDERED in _codes(ei.value)


def test_body_atoms_intra_list_duplicate_raises():
    # A repeated atom in one body_atoms list → BODY_ATOMS_UNORDERED (a strictly-ascending sequence has
    # no repeats). Distinct from DUP_OWNERSHIP, which is a *cross-bucket* repeat. An ADJACENT duplicate
    # (a1, a1) is used deliberately: its two indices are equal, so the ascending check (strict <)
    # cannot catch it — only the duplicate check can, which is what makes that check independently
    # pinnable. The store covers a0/a1 fully so nothing else co-fires.
    nodes = (
        ContainerNode(node_id="root", node_class="document", minted_by="human", children=("l",), heading_atoms=("a0",)),
        LeafNode(node_id="l", node_class="para", minted_by="machine", body_atoms=("a1", "a1")),  # a1 twice, adjacent
    )
    store = _Store(included=("a0", "a1"))
    with pytest.raises(StructureValidationError) as ei:
        validate_projection(ProjectionMap(root_id="root", nodes=nodes), store)
    codes = _codes(ei.value)
    assert EC.BODY_ATOMS_UNORDERED in codes
    assert EC.UNOWNED_INCLUDED_ATOM not in codes  # a0/a1 both owned — the dup is the only fault
    # a within-slot repeat is ONE bucket (the node-slot dedup), not cross-bucket double-ownership:
    # drop that dedup and this repeat spuriously fires DUP_OWNERSHIP — pins it here.
    assert EC.DUP_OWNERSHIP not in codes


def test_body_atoms_ascending_but_non_contiguous_passes():
    # §3.B.6: body_atoms need not be contiguous — a leaf may interleave around excluded furniture. The
    # leaf owns (a2, a4) with a3 owned by a sibling; strictly ascending, non-contiguous → valid.
    nodes = (
        ContainerNode(node_id="root", node_class="document", minted_by="human", children=("l1", "l2"), heading_atoms=("a0",)),
        LeafNode(node_id="l1", node_class="para", minted_by="machine", body_atoms=("a1", "a2", "a4")),  # gap at a3
        LeafNode(node_id="l2", node_class="para", minted_by="machine", body_atoms=("a3", "a5")),
    )
    validate_projection(ProjectionMap(root_id="root", nodes=nodes), _base_store())  # no raise


# --- inv 3 — ragged depth + heterogeneous siblings validate ------------------------------------- #


def test_ragged_depth_and_heterogeneous_siblings_validate():
    # inv 3: the model must not bake a uniform depth. root has a depth-1 branch (a direct leaf child)
    # and a depth-3 branch (container→container→leaf); ch has both a leaf child and a container child
    # (heterogeneous siblings). This is a "must-not-bake" PROPERTY guard, not a red-first check: the
    # SUT has no depth logic to mutate, so it is proven live only against a planted uniform-depth
    # mutant (the mutation harness), not the real code — a hard-coded-depth impl would red this.
    nodes = (
        ContainerNode(node_id="root", node_class="document", minted_by="human", children=("shallow", "deep"), heading_atoms=("a0",)),
        LeafNode(node_id="shallow", node_class="para", minted_by="machine", body_atoms=("a1",)),  # depth 1
        ContainerNode(node_id="deep", node_class="section", minted_by="human", children=("mid_leaf", "mid_cont"), heading_atoms=("a2",)),
        LeafNode(node_id="mid_leaf", node_class="para", minted_by="machine", body_atoms=("a3",)),  # leaf sibling
        ContainerNode(node_id="mid_cont", node_class="subsection", minted_by="human", children=("deepest",), heading_atoms=("a4",)),
        LeafNode(node_id="deepest", node_class="para", minted_by="machine", body_atoms=("a5",)),  # depth 3
    )
    validate_projection(ProjectionMap(root_id="root", nodes=nodes), _base_store())  # no raise


# --- flat node table (§3.B.4) ------------------------------------------------------------------- #


def test_projection_map_exposes_flat_table_keyed_by_node_id():
    # §3.B.4: the map is a flat table keyed by node_id; reference-validation resolves through it (no
    # tree scan). Every node is reachable by its id, and the table size equals the node count.
    m = _base_map()
    assert set(m.by_id) == {"root", "ch1", "leaf1a", "leaf1b", "ch2"}
    assert m.by_id["root"].node_class == "document"
    assert len(m.by_id) == len(m.nodes)
    # the table is a read-only view (a mappingproxy), not a mutable dict a caller can corrupt
    with pytest.raises(TypeError):
        m.by_id["x"] = m.by_id["root"]  # type: ignore[index]


# --- collect-all: independent Tier-2b violations surface together (§4.1) ------------------------- #


def test_collect_all_reports_multiple_independent_violations():
    # §4.1 Tier-2b: independent semantic faults are collected in ONE pass and raised together — not
    # short-circuited on the first. Here an unowned included atom (a6) AND an empty container both
    # fire; the payload carries both codes.
    nodes = (
        ContainerNode(node_id="root", node_class="document", minted_by="human", children=("empty", "l"), heading_atoms=("a0",)),
        ContainerNode(node_id="empty", node_class="section", minted_by="human"),  # EMPTY_CONTAINER
        LeafNode(node_id="l", node_class="para", minted_by="machine", body_atoms=("a1", "a2", "a3", "a4", "a5")),
    )
    store = _Store(included=("a0", "a1", "a2", "a3", "a4", "a5", "a6"))  # a6 unowned
    with pytest.raises(StructureValidationError) as ei:
        validate_projection(ProjectionMap(root_id="root", nodes=nodes), store)
    codes = _codes(ei.value)
    assert {EC.EMPTY_CONTAINER, EC.UNOWNED_INCLUDED_ATOM} <= codes


# --- the payload-carrying exception (deferred from B-1) ------------------------------------------ #


def test_structure_validation_error_is_an_engine_error_with_a_code_payload():
    # The exception homes with the code vocabulary it carries; it is an EngineError (CLI exit code)
    # and exposes .codes for S8.1 routing / test membership. A findings-less construction is a
    # programming error (an empty payload would read as "valid but raised").
    err = StructureValidationError([(EC.CYCLE, "demo")])
    assert isinstance(err, EngineError)
    assert err.codes == (EC.CYCLE,)
    assert err.exit_code == 11  # the reserved code (next free after StaleArtifactError=10)
    with pytest.raises(ValueError):
        StructureValidationError([])


def test_structure_validation_error_is_exported():
    # R2-02 amendment: the B-2 public surface (the exception + the model + the validator) is on the
    # package. Bindings resolve — a dropped re-export AttributeErrors, not passes green.
    for name in ("Node", "ContainerNode", "LeafNode", "FurnitureAtom", "ProjectionMap",
                 "validate_projection", "StructureValidationError", "mint_node_id"):
        assert hasattr(structure, name), f"{name!r} not exported from engine.structure"


# --- construction hygiene: degenerate node identity fails loud ---------------------------------- #


@pytest.mark.parametrize("empty", ["node_id", "node_class"])
def test_leaf_empty_identity_rejected_at_construction(empty):
    # node_id keys the registry and node_class is the projection's type axis; an empty one is a
    # malformed node (the Atom/BlockClassification fail-loud-on-degenerate-construction idiom). A
    # ValueError, not an EC code — this is dataclass-shape hygiene, distinct from map-semantic codes.
    # (minted_by is NOT construction-hygiene: a blank minted_by is a validator MINTED_BY_SPLIT, inv 7.)
    fields = {"node_id": "n", "node_class": "k", "minted_by": "machine", "body_atoms": ("a",)}
    fields[empty] = ""
    with pytest.raises(ValueError):
        LeafNode(**fields)


@pytest.mark.parametrize("empty", ["node_id", "node_class"])
def test_container_empty_identity_rejected_at_construction(empty):
    # Same guard on the container variant — a mutant dropping _require_identity from ContainerNode
    # must red too (both variants call it), not only LeafNode.
    fields = {"node_id": "c", "node_class": "k", "minted_by": "human", "children": ("x",)}
    fields[empty] = ""
    with pytest.raises(ValueError):
        ContainerNode(**fields)


@pytest.mark.parametrize("empty", ["atom_id", "capture_role"])
def test_furniture_empty_fields_rejected_at_construction(empty):
    # A furniture record must carry a real atom id and a role label; an empty either is malformed.
    fields = {"atom_id": "a9", "capture_role": "page-number"}
    fields[empty] = ""
    with pytest.raises(ValueError):
        FurnitureAtom(**fields)


def test_empty_root_id_rejected_at_construction():
    # root_id names the root node; an empty header root is a malformed map (topology resolution is
    # B-5, but a blank root_id is dataclass-shape hygiene rejected here).
    with pytest.raises(ValueError):
        ProjectionMap(root_id="", nodes=(LeafNode(node_id="l", node_class="k", minted_by="machine", body_atoms=("a",)),))


# ================================================================================================ #
# B-3 / S4.2 — node_id identity + minting split (mint_node_id seam; minted_by / designation / title)
# ================================================================================================ #

# --- the mint_node_id seam (inv 6 PRIMARY control: no content argument) -------------------------- #


def test_mint_node_id_takes_no_content_argument():
    # inv 6 primary control (§3.C.3): the seam is arg-free OF CONTENT. Its parameters are exactly the
    # minting authority + a mint ordinal — it cannot even RECEIVE a designation/title/path/content, so
    # a minted node_id structurally cannot encode one. A mutation that adds such a parameter reds this.
    params = set(inspect.signature(mint_node_id).parameters)
    assert params == {"minted_by", "seq"}
    forbidden = {"designation", "title", "path", "content", "text", "node_class", "slug", "position"}
    assert not (params & forbidden), f"mint_node_id must not accept content params: {params & forbidden}"


def test_mint_node_id_is_deterministic_in_authority_and_ordinal():
    # Same (authority, ordinal) → same id; a different ordinal → a different id (the counter advances).
    # Determinism is what lets the seam be fixture-usable without hidden global state.
    assert mint_node_id("human", 3) == mint_node_id("human", 3)
    assert mint_node_id("human", 3) != mint_node_id("human", 4)
    assert mint_node_id("machine", 3) == mint_node_id("machine", 3)
    assert mint_node_id("machine", 3) != mint_node_id("machine", 4)


def test_mint_node_id_human_and_machine_use_distinct_schemes():
    # §3.C.4: humans mint a container id as a counter, machines mint a leaf id as a ULID-like token —
    # visibly distinct forms. The human id is prefixed (never a bare integer) so it cannot collide with
    # a "0"-rooted position-path and spuriously trip the NODE_ID_DERIVED position cheat.
    human = mint_node_id("human", 0)
    machine = mint_node_id("machine", 0)
    assert human != machine
    assert not human[0].isdigit()  # prefixed — not a bare position-path-shaped integer
    assert len(machine) == 26 and machine.isalnum()  # opaque, fixed-width, ULID-shaped


def test_mint_node_id_rejects_unknown_authority_and_negative_ordinal():
    # An authority that names no scheme is a caller programming error (you cannot mint under it) — a
    # ValueError, distinct from the map-level MINTED_BY_SPLIT the validator raises. A negative ordinal
    # is likewise rejected.
    with pytest.raises(ValueError):
        mint_node_id("robot", 0)
    with pytest.raises(ValueError):
        mint_node_id("", 0)
    with pytest.raises(ValueError):
        mint_node_id("human", -1)


# --- inv 7 — minted_by recorded + split enforced BOTH ways (MINTED_BY_SPLIT) --------------------- #


def test_container_minted_by_machine_raises_split():
    # A container minted_by 'machine' contradicts the authority split (a machine cannot mint a
    # container) → MINTED_BY_SPLIT. Perturb one node off the clean base so the code isolates.
    nodes = _base_nodes()
    bad = dataclasses.replace(nodes[0], minted_by="machine")  # nodes[0] is the root container
    with pytest.raises(StructureValidationError) as ei:
        validate_projection(_base_map(nodes=(bad,) + nodes[1:]), _base_store())
    codes = _codes(ei.value)
    assert EC.MINTED_BY_SPLIT in codes
    assert codes == {EC.MINTED_BY_SPLIT}  # isolation: nothing else co-fires


def test_leaf_minted_by_human_raises_split():
    # The mirror direction: a leaf minted_by 'human' → MINTED_BY_SPLIT. Pins that the split is checked
    # in BOTH directions — a one-sided check (only container→human) would pass this leaf.
    nodes = _base_nodes()
    bad = dataclasses.replace(nodes[2], minted_by="human")  # nodes[2] is leaf1a
    with pytest.raises(StructureValidationError) as ei:
        validate_projection(_base_map(nodes=nodes[:2] + (bad,) + nodes[3:]), _base_store())
    assert EC.MINTED_BY_SPLIT in _codes(ei.value)


@pytest.mark.parametrize("bad_value", ["", "robot", "Human", "MACHINE"])
def test_blank_or_out_of_vocab_minted_by_raises_split(bad_value):
    # Presence + vocabulary: a blank minted_by ("not recorded"), an out-of-vocab value, and a
    # wrong-case near-miss all fail the exact-token split. One comparison covers all of them (the node
    # must carry its kind's exact authority token).
    nodes = _base_nodes()
    bad = dataclasses.replace(nodes[2], minted_by=bad_value)  # a leaf → expected 'machine'
    with pytest.raises(StructureValidationError) as ei:
        validate_projection(_base_map(nodes=nodes[:2] + (bad,) + nodes[3:]), _base_store())
    assert EC.MINTED_BY_SPLIT in _codes(ei.value)


def test_correct_split_validates_clean():
    # The positive: containers minted_by 'human', leaves minted_by 'machine' — the base map's own
    # split — validates with no MINTED_BY_SPLIT. (test_base_map_validates_clean also covers this; kept
    # explicit so a mutation that fires the split on a CORRECT map reds a named test.)
    m = _base_map()
    validate_projection(m, _base_store())  # no raise
    assert all(
        n.minted_by == ("human" if isinstance(n, ContainerNode) else "machine") for n in m.nodes
    )


# --- inv 6 — node_id must not be DERIVED from designation / title / position (NODE_ID_DERIVED) --- #


def _derivation_map(*, node_id: str = "leaf", designation: str = "", title: str = "") -> ProjectionMap:
    # A minimal, otherwise-clean map: root container → one leaf. Only the leaf's node_id + its
    # designation/title vary, so a NODE_ID_DERIVED finding isolates (a0/a1 both owned, split correct,
    # not an empty container). The leaf sits at child-index 0, so its position-path is "0.0".
    root = ContainerNode(node_id="root", node_class="document", minted_by="human", children=(node_id,), heading_atoms=("a0",))
    leaf = LeafNode(node_id=node_id, node_class="para", minted_by="machine", body_atoms=("a1",), designation=designation, title=title)
    return ProjectionMap(root_id="root", nodes=(root, leaf))


_DERIV_STORE = _Store(included=("a0", "a1"))


@pytest.mark.parametrize(
    ("kwargs", "transform"),
    [
        ({"node_id": "Chapter One", "designation": "Chapter One"}, "exact designation"),
        ({"node_id": "chapter one", "designation": "Chapter One"}, "casefold(designation)"),
        ({"node_id": "chapter-one", "designation": "Chapter One"}, "slug(designation)"),
        # word-FINAL accent: coincidentally slugs right even if the NFKD combining mark isn't dropped
        # (the freed mark merges into the word-boundary hyphen), so it ALONE cannot pin the fold — an
        # ASCII-only slug would instead yield "citt-di-roma" and miss it (adversarial F1).
        ({"node_id": "citta-di-roma", "designation": "Città di Roma"}, "slug(designation)"),
        # word-INTERNAL accent: REQUIRES dropping the combining mark ("Über"→"uber", not "u-ber"). This
        # is the divergent axis the word-final fixture masks (delta-audit: single-fixture blind spot —
        # the first F1 fix normalized but did not strip the mark, and only "Città" happened to pass).
        ({"node_id": "uber-alles", "designation": "Über Alles"}, "slug(designation)"),
        ({"node_id": "the-preface", "title": "The Preface"}, "slug(title)"),
        ({"node_id": "0.0"}, "position-path"),  # leaf sits at child index 0 under root "0"
    ],
    ids=["exact", "casefold", "slug-designation", "slug-designation-final-accent",
         "slug-designation-internal-accent", "slug-title", "position-path"],
)
def test_node_id_matching_an_enumerated_cheat_raises_derived(kwargs, transform):
    # inv 6 (§3.C.3): each enumerated derivation transform, one red fixture apiece. A node_id equal to
    # a cheat form of its designation/title/position is rejected; dropping THAT transform from the
    # check lets its fixture through → the mutation harness reds it. The finding must NAME the specific
    # transform — exact-equals is a strict subset of casefold-equals (equal strings casefold-equal), so
    # without the label assertion, dropping the exact branch would be masked by casefold. Asserting the
    # label makes each of the five independently mutation-catchable.
    with pytest.raises(StructureValidationError) as ei:
        validate_projection(_derivation_map(**kwargs), _DERIV_STORE)
    codes = _codes(ei.value)
    assert EC.NODE_ID_DERIVED in codes
    assert codes == {EC.NODE_ID_DERIVED}  # isolation: the otherwise-clean map fires only this
    assert transform in str(ei.value)  # the specific derivation transform is named (per-transform pin)


def test_opaque_node_id_with_designation_and_title_validates_clean():
    # The positive: a node CARRYING a designation and title but with an opaque, independently-minted
    # id (not any cheat form of them) validates. Proves the check keys on the derivation MATCH, not on
    # the mere presence of a designation/title — else every titled node would false-positive.
    m = _derivation_map(node_id="n-7", designation="Chapter One", title="The Preface")
    validate_projection(m, _DERIV_STORE)  # no raise


def test_minted_ids_survive_the_derivation_check():
    # Integration: ids straight from the seam, on nodes that DO carry designations, validate clean —
    # the seam and the belt-and-braces validator agree. mint gives root n-0, leaf a ULID-like token;
    # neither is a cheat form of the designations.
    root_id = mint_node_id("human", 0)
    leaf_id = mint_node_id("machine", 0)
    root = ContainerNode(node_id=root_id, node_class="document", minted_by="human", children=(leaf_id,), heading_atoms=("a0",), designation="Preface")
    leaf = LeafNode(node_id=leaf_id, node_class="para", minted_by="machine", body_atoms=("a1",), designation="First Paragraph")
    validate_projection(ProjectionMap(root_id=root_id, nodes=(root, leaf)), _DERIV_STORE)  # no raise


# --- inv 4 / inv 5 — node_id stable across re-serialize (asdict/replace) and positional move ----- #


def _round_trip(node):
    # reconstruct a node from its own stored fields — a serialize→deserialize simulation that re-runs
    # __post_init__, so a "re-derive node_id on construct" mutant would change the id here.
    return type(node)(**{f.name: getattr(node, f.name) for f in dataclasses.fields(node)})


def test_node_id_survives_dataclass_round_trip():
    # inv 4 (re-serialize axis, §4.1.x item 5): a node's node_id is a STORED opaque field, so a
    # round-trip through the dataclass (reconstruct + replace()) reproduces it exactly — even for a node
    # carrying a designation a "re-derive on serialize" impl could latch onto. That impl (a __post_init__
    # that recomputes node_id from designation) is the planted mutant this guards; byte-exact dump/load
    # is B-5/inv 20. BOTH variants are round-tripped so a container-only derive-mutant reds directly
    # (not merely via an inv-6 side-effect, adversarial F3).
    leaf = LeafNode(node_id="n-5", node_class="para", minted_by="machine", body_atoms=("a1",), designation="Chapter One")
    cont = ContainerNode(node_id="n-0", node_class="document", minted_by="human", children=("n-5",), designation="Preface")
    assert _round_trip(leaf).node_id == "n-5"
    assert _round_trip(cont).node_id == "n-0"
    assert dataclasses.replace(leaf).node_id == "n-5"
    assert dataclasses.replace(cont).node_id == "n-0"


def test_node_id_independent_of_owned_content():
    # §3.C.3 (the "content" axis of "one fixture mutates designation, position, AND content with the id
    # fixed"): a node_id is opaque and does not track the atoms the node owns. Two leaves sharing one id
    # but owning different body_atoms carry the SAME id — a content-deriving __post_init__ (node_id from
    # body_atoms) would make them diverge, so this binds that axis the seam's arg-free-of-content
    # signature already forbids at mint time.
    a = LeafNode(node_id="n-9", node_class="para", minted_by="machine", body_atoms=("a1",))
    b = LeafNode(node_id="n-9", node_class="para", minted_by="machine", body_atoms=("a2", "a3"))
    assert a.node_id == b.node_id == "n-9"


def test_node_id_stable_across_positional_move():
    # inv 5 (positional-move axis, §4.1.x item 6): moving a node among its siblings must NOT change its
    # node_id. Here leaf1a and leaf1b swap order (both in ch1.children and in the nodes tuple); each
    # keeps its id and by_id resolution, and the reordered map still validates. A position-DERIVING
    # impl would disagree across the two arrangements — caught by inv 6's position-path cheat below.
    nodes = _base_nodes()
    moved_ch1 = dataclasses.replace(nodes[1], children=("leaf1b", "leaf1a"))  # swap the two leaves
    moved = (nodes[0], moved_ch1, nodes[3], nodes[2], nodes[4])  # reorder nodes tuple to match
    m = _base_map(nodes=moved)
    validate_projection(m, _base_store())  # still valid — id is not position-derived
    assert m.by_id["leaf1a"].node_id == "leaf1a" and m.by_id["leaf1b"].node_id == "leaf1b"


def test_position_derived_id_is_position_dependent():
    # inv 5's mutation, made concrete via inv 6's position-path cheat: an id EQUAL to the node's
    # position-path is derived → NODE_ID_DERIVED; the SAME id at a DIFFERENT position no longer matches
    # its path → clean. This is exactly the disagreement a position-deriving impl produces across
    # arrangements, and the single position-path cheat drop reds it.
    derived = _derivation_map(node_id="0.0")  # leaf at child-index 0 → path "0.0" → matches → derived
    with pytest.raises(StructureValidationError) as ei:
        validate_projection(derived, _DERIV_STORE)
    assert EC.NODE_ID_DERIVED in _codes(ei.value)
    # same id "0.0" but the leaf sits second (path "0.1") behind a sibling → no longer its path → clean
    root = ContainerNode(node_id="root", node_class="document", minted_by="human", children=("filler", "0.0"), heading_atoms=("a0",))
    filler = LeafNode(node_id="filler", node_class="para", minted_by="machine", body_atoms=("a1",))
    moved = LeafNode(node_id="0.0", node_class="para", minted_by="machine", body_atoms=("a2",))
    store = _Store(included=("a0", "a1", "a2"))
    validate_projection(ProjectionMap(root_id="root", nodes=(root, filler, moved)), store)  # no raise


def test_collect_all_includes_the_new_identity_codes():
    # §4.1 Tier-2b: MINTED_BY_SPLIT (inv 7) and NODE_ID_DERIVED (inv 6) are collect-all codes — a map
    # violating BOTH surfaces BOTH in one payload, not short-circuited on the first (they append to the
    # findings list, like every other Tier-2b check). The leaf is minted_by 'human' (wrong direction)
    # AND named after its own position-path "0.0" — one perturbed node, two independent identity faults.
    root = ContainerNode(node_id="root", node_class="document", minted_by="human", children=("0.0",), heading_atoms=("a0",))
    leaf = LeafNode(node_id="0.0", node_class="para", minted_by="human", body_atoms=("a1",))  # human (wrong) + position-path id
    with pytest.raises(StructureValidationError) as ei:
        validate_projection(ProjectionMap(root_id="root", nodes=(root, leaf)), _DERIV_STORE)
    assert {EC.MINTED_BY_SPLIT, EC.NODE_ID_DERIVED} <= _codes(ei.value)
