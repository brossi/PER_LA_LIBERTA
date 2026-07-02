"""S4.1 — the L2 projection model: container/leaf nodes over the addressed atom stream (s4_plan §3.B).

L2 is where a book's structure lives. The recognizer re-groups + re-types the flat L1 atom stream
(concern A) into a tree of **nodes**, each addressed by an opaque, persisted ``node_id`` (distinct
from the atom's ``atom_id``, D33) and each *owning* a disjoint slice of the atoms. A node is a
**container** (owns ordered ``children`` node-references + optional ``heading_atoms`` /
``signature_atoms``) or a **leaf** (owns ``body_atoms``); the two are distinct dataclasses, so
container-xor-leaf holds **by construction** — you cannot instantiate a node carrying both slots
(the Tier-1 ``oneOf`` schema, inv 2, is B-5's belt-and-braces).

This is the **Phase-1** slice (s4_plan §4.2): the validator here raises the ``EC.*`` codes directly
and is red-tested against in-memory dataclasses. The aggregate ``validate_structure_map(map,
atom_store)``, the JSON schema, and the born-agnostic loader are B-5, which *composes* this
per-module validator (one producer per code, invariant I5). ``node_id`` uniqueness is a **Tier-2a
precondition**: it is enforced at :class:`ProjectionMap` construction (you cannot build the keyed
table with a collision), short-circuiting before any collect-all check runs (§4.1). Everything else
here — ownership disjointness, coverage, empty-container, body ordering — is **Tier-2b**: collected
in one pass and raised together on :class:`~engine.structure.errors.StructureValidationError`.

Pure core: a node's ``node_class`` is an open per-book string (the profile/map declares the
vocabulary, §3.B.2), never an enum here; no language/ordinal/book-structure literal lives in this
module (the S0.2 neutrality guard scans it via the ``structure/*.py`` glob, inv 15).

Identity (S4.2/B-3) lives here too: the opaque ``node_id`` is minted by :func:`mint_node_id` — an
arg-free-of-content seam that never sees a designation/title/path/content, so a ``node_id`` *cannot*
be derived from them (the primary non-derivation control, §3.C.3) — and ``minted_by`` records the
conceptual minting authority (``human`` ⇒ a container, ``machine`` ⇒ a leaf), a split the validator
enforces **both** ways (``MINTED_BY_SPLIT``, inv 7). The validator also rejects a ``node_id`` that
matches an enumerated derivation cheat (``NODE_ID_DERIVED``, inv 6) — the belt-and-braces for a
hand-authored map, since the seam cannot stop a human from *typing* a derived id. ``designation`` /
``title`` are the optional handle/display inputs those cheats compare against (§3.J).

Not here (owned by neighbours): handles/aliases/``handle_policy`` + the substring-of-rendered-handle
derivation cheat (S4.3/B-4); root topology + reference-integrity traversal (``root_id`` resolution,
``NO_ROOT``/``MULTIPLE_ROOTS``/``ORPHAN_NODE``/``CYCLE``), the JSON schema, and atom *existence*
(``DANGLING_ATOM_REF`` via ``atom_store.contains()``) — all S4.4/B-5.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from engine.structure.atoms import PROCESSING_SCOPE_EXCLUDED
from engine.structure.errors import EC, StructureValidationError

#: The two conceptual minting authorities (§3.C.2): a **human** mints a container, the **extractor**
#: **machine** mints a leaf. Not the runtime writer — the authority that *decided* the node exists.
#: Process-role wire tokens, not language/book literals (they pass the inv-15 neutrality scan).
MINTED_BY_HUMAN = "human"
MINTED_BY_MACHINE = "machine"

#: Default ``node_id`` scheme (§3.C.4) — **revisitable, fixture-only**. Human containers get a plain
#: counter, machine leaves a ULID-like token. The ``"n-"`` human prefix is load-bearing: a bare
#: integer id (``"0"``) would collide with the root's ``"0"`` position-path and spuriously trip the
#: ``NODE_ID_DERIVED`` position cheat — the prefix keeps a legitimately-minted id off every derivation
#: form. Crockford base32 (no ``I``/``L``/``O``/``U``) gives the leaf id its opaque ULID shape.
_HUMAN_ID_PREFIX = "n-"
_CROCKFORD32 = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_ULID_LIKE_WIDTH = 26


def mint_node_id(minted_by: str, seq: int) -> str:
    """Mint a fresh opaque ``node_id`` — the S4.2 identity **seam** (§3.C.3/§3.C.4).

    The seam is the *primary* non-derivation control (inv 6): it takes only the minting
    **authority** and a monotonic mint **ordinal** — **never** a designation, title, position-path,
    or content — so a minted ``node_id`` *structurally cannot* encode any of them. ``seq`` is the
    mint-order counter, **not** a tree position (which would re-derive on a move, inv 5); it is
    assigned once and travels with the node.

    Scheme (revisitable, fixture-only, §3.C.4): a human authority mints a container id as a plain
    counter (``n-0``, ``n-1``, …); a machine authority mints a leaf id as a ULID-like Crockford-base32
    token. An unknown authority is a caller programming error (``ValueError``) — the human/machine
    *split* over an already-built map is the validator's job (``MINTED_BY_SPLIT``), but you cannot
    *mint* under an authority that names no scheme.
    """
    if seq < 0:
        raise ValueError(f"mint_node_id seq must be a non-negative mint ordinal, got {seq!r}")
    if minted_by == MINTED_BY_HUMAN:
        return f"{_HUMAN_ID_PREFIX}{seq}"
    if minted_by == MINTED_BY_MACHINE:
        return _ulid_like(seq)
    raise ValueError(
        f"mint_node_id: unknown minting authority {minted_by!r} — expected "
        f"{MINTED_BY_HUMAN!r} (container) or {MINTED_BY_MACHINE!r} (leaf)"
    )


def _ulid_like(seq: int) -> str:
    """A deterministic, opaque, fixed-width Crockford-base32 token for a machine-minted leaf (§3.C.4).

    Deterministic in ``seq`` (not a real timestamp+random ULID) so fixtures/tests are reproducible;
    the shape — 26 base32 chars — is what makes it read as an opaque leaf id, distinct from the human
    ``n-<counter>`` form. Fixture-only and revisitable: the production minter is the extractor.
    """
    digits = []
    n = seq
    for _ in range(_ULID_LIKE_WIDTH):
        n, rem = divmod(n, 32)
        digits.append(_CROCKFORD32[rem])
    return "".join(reversed(digits))


def _slug(text: str) -> str:
    """The canonical id-derivation slug used **only** by the ``NODE_ID_DERIVED`` cheat check.

    Lowercase, **NFKD-decompose and drop the combining marks** (accent-fold), then collapse every run
    of non-``a-z0-9`` characters to a single hyphen and strip leading/trailing hyphens. The two-step
    fold is load-bearing on a non-English book: NFKD splits an accented Latin letter into base +
    combining mark, and dropping the mark (``unicodedata.combining``) leaves the bare base letter — so
    ``"Città"`` → ``"citta"`` and ``"Über"`` → ``"uber"`` (mark **anywhere** in the word, not only
    word-final), matching the id a real slugifier would mint. Dropping the mark is essential:
    normalizing alone would turn the freed combining mark into a hyphen (``"Über"`` → ``"u-ber"``) and
    still miss an internal-accent derivation, while a plain ``[^a-z0-9]`` filter with no NFKD drops the
    accented letter whole (``"Città"`` → ``"citt"``). This mirrors the de-facto slugify convention
    (NFKD → strip-combining → ASCII → lower). Carries no language/book literal (inv 15). Honest scope:
    a **fully non-Latin** script (Cyrillic/CJK/Greek — no ASCII base after decomposition) still folds
    to empty here; catching *those* transliterated derivations is B-4's substring-of-rendered-handle
    cheat over the real ``render_handle``, not this belt-and-braces. It is *not* the B-4 renderer's
    per-policy, versioned ``html_slug`` — it only has to recognise the ``node_id ==
    slug(designation/title)`` derivation shape.
    """
    decomposed = unicodedata.normalize("NFKD", text.lower())
    deaccented = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "-", deaccented).strip("-")


def _require_identity(node_id: str, node_class: str) -> None:
    """Fail loud on a degenerate node identity at construction (the Atom/BlockClassification idiom).

    ``node_id`` keys the registry and ``node_class`` is the projection's type axis; an empty either
    is a malformed node, not a validatable map — so this is a plain ``ValueError`` (dataclass-shape
    hygiene), distinct from the map-semantic ``EC`` codes the validator collects.
    """
    if not node_id:
        raise ValueError("node_id must be a non-empty opaque id (it keys the projection's node table)")
    if not node_class:
        raise ValueError("node_class must be a non-empty label (the profile-declared projection type)")


@dataclass(frozen=True, slots=True)
class ContainerNode:
    """A container node: owns ordered ``children`` (child ``node_id`` references, in **reading
    order**, §3.B.6) and, optionally, its own ``heading_atoms`` and ``signature_atoms`` (a container's
    heading / closing atoms — the latter e.g. an embedded letter's sign-off line; ownership only,
    authorship is S6). It owns no ``body_atoms`` — that slot exists only on :class:`LeafNode`, which
    is how container-xor-leaf holds by construction. ``parent`` is **not** stored: it is derived from
    the ``children`` edges on load (§3.B.4, the single-source-of-truth storage posture).

    ``minted_by`` is the conceptual minting authority (§3.C.2): a container is **human**-minted, a
    split :func:`validate_projection` enforces (``MINTED_BY_SPLIT``). ``designation`` / ``title`` are
    optional handle/display inputs (§3.J) — inert here except that ``node_id`` may not be *derived*
    from them (``NODE_ID_DERIVED``).
    """

    node_id: str
    node_class: str
    minted_by: str
    children: tuple[str, ...] = ()
    heading_atoms: tuple[str, ...] = ()
    signature_atoms: tuple[str, ...] = ()
    designation: str = ""
    title: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "children", tuple(self.children))
        object.__setattr__(self, "heading_atoms", tuple(self.heading_atoms))
        object.__setattr__(self, "signature_atoms", tuple(self.signature_atoms))
        _require_identity(self.node_id, self.node_class)


@dataclass(frozen=True, slots=True)
class LeafNode:
    """A leaf node: owns ``body_atoms`` — the atom ids of its running text, ordered by **strictly
    ascending canonical-stream index** and permitted to be non-contiguous (it may interleave around
    excluded furniture, §3.B.6). It owns no ``children``; a leaf is a terminal in the projection tree.

    ``minted_by`` is the conceptual minting authority (§3.C.2): a leaf is **machine**-minted (the
    extractor), the mirror of the container's human split (``MINTED_BY_SPLIT``). ``designation`` /
    ``title`` are optional handle/display inputs; ``node_id`` may not be *derived* from them.
    """

    node_id: str
    node_class: str
    minted_by: str
    body_atoms: tuple[str, ...] = ()
    designation: str = ""
    title: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "body_atoms", tuple(self.body_atoms))
        _require_identity(self.node_id, self.node_class)


#: A projection node is exactly one of the two variants — the union callers dispatch on. The xor is
#: structural (two types), not a runtime flag, so a "both slots" node is unrepresentable.
Node = ContainerNode | LeafNode


@dataclass(frozen=True, slots=True)
class FurnitureAtom:
    """A header-level record for an atom captured as **furniture** (page numbers, running heads, …):
    excluded from the canonical body stream but retained with its ``capture_role`` (§3.J). Furniture
    is the fourth ownership bucket for disjointness (inv 1a) and is exempt from body coverage (inv 1b):
    an excluded atom lives here, never inside a node slot.
    """

    atom_id: str
    capture_role: str

    def __post_init__(self) -> None:
        if not self.atom_id:
            raise ValueError("FurnitureAtom.atom_id must be a non-empty atom id")
        if not self.capture_role:
            raise ValueError("FurnitureAtom.capture_role must name the furniture role (non-empty)")


@dataclass(frozen=True, slots=True)
class ProjectionMap:
    """The L2 projection: a flat table of nodes keyed by ``node_id`` (§3.B.4), the header ``root_id``,
    and the header ``furniture_atoms``. Persist-children-only — ``parent`` is derived on load — so the
    stored form has a single source of truth for the tree edges.

    ``node_id`` **uniqueness is a Tier-2a precondition enforced here, at construction** (§4.1/§3.C.1e):
    the keyed table cannot be built with a collision, so a duplicate raises
    :class:`~engine.structure.errors.StructureValidationError` (``DUPLICATE_NODE_ID``) on the *second*
    insert — short-circuiting, before the collect-all :func:`validate_projection` pass runs (which is
    why a duplicate never co-fires a downstream code). ``by_id`` is the read-only resolved table
    reference-validation runs through (no per-reference tree scan).
    """

    root_id: str
    nodes: tuple[Node, ...]
    furniture_atoms: tuple[FurnitureAtom, ...] = ()
    #: Derived read-only ``node_id`` → node table (built in ``__post_init__``, excluded from eq/hash/
    #: repr — it is a projection of ``nodes``, not independent state). NB: the ``mappingproxy`` makes a
    #: ``ProjectionMap`` non-``pickle``/``deepcopy``-safe; that is off the persistence path (B-5 stores
    #: via canonical JSON) and ``dataclasses.replace`` rebuilds it — add ``__getstate__`` only if a
    #: worker-boundary send ever needs it.
    by_id: Mapping[str, Node] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "nodes", tuple(self.nodes))
        object.__setattr__(self, "furniture_atoms", tuple(self.furniture_atoms))
        table: dict[str, Node] = {}
        for node in self.nodes:
            if node.node_id in table:
                # inv 16 / DUPLICATE_NODE_ID (Tier-2a): fail on the second insert rather than letting
                # the later node silently overwrite the earlier — an id-keyed table with a collision
                # cannot be built, so the whole map is rejected before any collect-all check runs.
                raise StructureValidationError(
                    [(EC.DUPLICATE_NODE_ID, f"node_id {node.node_id!r} appears on more than one node")]
                )
            table[node.node_id] = node
        object.__setattr__(self, "by_id", MappingProxyType(table))
        if not self.root_id:
            raise ValueError("ProjectionMap.root_id must name the root node (non-empty)")


def _owning_slots(node: Node) -> Iterator[tuple[str, tuple[str, ...]]]:
    """Yield each ``(slot_name, atom_ids)`` **atom-owning** slot of a node, atoms as-stored.

    Container ``children`` are node references, not atoms, so they are *not* an atom-ownership bucket —
    only ``heading_atoms``/``signature_atoms`` (container) and ``body_atoms`` (leaf) own atoms.
    """
    if isinstance(node, ContainerNode):
        yield "heading_atoms", node.heading_atoms
        yield "signature_atoms", node.signature_atoms
    else:
        yield "body_atoms", node.body_atoms


def validate_projection(pmap: ProjectionMap, atom_store) -> None:
    """Run the Tier-2b projection checks (Phase-1, §4.2); raise
    :class:`~engine.structure.errors.StructureValidationError` with the **collected** codes, or return
    ``None`` when the projection is clean. (The Tier-2a ``node_id`` precondition already fired at
    :class:`ProjectionMap` construction.)

    ``atom_store`` is the thin reader S4 takes (§4 header) — any object exposing:

    - ``included_atom_ids() -> Sequence[str]`` — the included canonical-stream atom ids **in
      canonical-stream order** (an atom's position *is* its canonical index). The coverage universe
      (inv 1b) and the ordering key (inv 27).
    - ``scope_of(atom_id) -> str | None`` — an atom's ``processing_scope``; used to reject an excluded
      atom smuggled into a node slot (``OWNED_EXCLUDED_ATOM``, inv 1b).

    Atom *existence* (``contains()`` → ``DANGLING_ATOM_REF``, inv 17) and root topology (inv 14) are
    B-5 and are **not** consulted here. The two identity checks (``MINTED_BY_SPLIT`` /
    ``NODE_ID_DERIVED``) are pure projection-model checks — they read only node type + ``minted_by`` /
    ``node_id`` / ``designation`` / ``title`` and the ``children`` edges, never the ``atom_store``.

    Collected codes: ``DUP_OWNERSHIP`` (inv 1a), ``UNOWNED_INCLUDED_ATOM`` / ``OWNED_EXCLUDED_ATOM``
    (inv 1b), ``EMPTY_CONTAINER`` (inv 26), ``BODY_ATOMS_UNORDERED`` (inv 27), ``MINTED_BY_SPLIT``
    (inv 7), ``NODE_ID_DERIVED`` (inv 6).
    """
    findings: list[tuple[EC, str]] = []
    _check_ownership_disjoint(pmap, findings)
    _check_coverage(pmap, atom_store, findings)
    _check_empty_containers(pmap, findings)
    _check_body_atom_order(pmap, atom_store, findings)
    _check_minted_by(pmap, findings)
    _check_node_id_not_derived(pmap, findings)
    if findings:
        raise StructureValidationError(findings)


def _check_ownership_disjoint(pmap: ProjectionMap, findings: list[tuple[EC, str]]) -> None:
    """inv 1a — no ``atom_id`` in two of the four ownership buckets (X4 folds furniture in).

    Keyed by the *bucket* — ``(node_id, slot_name)`` or ``furniture`` — so an atom shared by two
    nodes' body slots is caught (two distinct buckets), while a repeat *within* one slot is one bucket
    (that within-list repeat is inv 27's concern, not double-ownership). Iterated as-stored with an
    order-preserving dedupe so the report is deterministic (I9).
    """
    buckets: dict[str, list[str]] = {}
    for node in pmap.nodes:
        for slot_name, atoms in _owning_slots(node):
            for atom_id in dict.fromkeys(atoms):  # dedupe within a slot, preserve order
                buckets.setdefault(atom_id, []).append(f"{node.node_id}.{slot_name}")
    # Furniture is ONE of the four buckets, so a repeated atom_id *within* furniture is one bucket —
    # deduped like a within-slot repeat, not reported as cross-bucket double-ownership (inv 1a is
    # "two of the four buckets"). A furniture atom that ALSO appears in a node slot is still two
    # buckets and fires below. (A malformed within-furniture repeat is uncaught here, symmetric with
    # heading/signature intra-slot repeats — the closed EC set has no furniture-dup code.)
    for atom_id in dict.fromkeys(fa.atom_id for fa in pmap.furniture_atoms):
        buckets.setdefault(atom_id, []).append("furniture")
    for atom_id, owners in buckets.items():
        if len(owners) >= 2:
            findings.append(
                (EC.DUP_OWNERSHIP, f"atom {atom_id!r} owned by multiple buckets: {owners}")
            )


def _check_coverage(pmap: ProjectionMap, atom_store, findings: list[tuple[EC, str]]) -> None:
    """inv 1b — coverage: every *included* canonical atom owned by exactly one node
    (``UNOWNED_INCLUDED_ATOM`` for a miss), and no node slot owns an *excluded* atom
    (``OWNED_EXCLUDED_ATOM``).

    Coverage ranges over ``included_atom_ids()`` only — excluded/furniture atoms are exempt (they live
    in the header ``furniture_atoms``, never in a node). The double-owned case is inv 1a's; here we
    only witness the two coverage directions.
    """
    owned: set[str] = set()
    excluded_owned: list[tuple[str, str, str]] = []
    for node in pmap.nodes:
        for slot_name, atoms in _owning_slots(node):
            for atom_id in dict.fromkeys(atoms):  # dedupe within a slot (one finding per atom/slot)
                owned.add(atom_id)
                if atom_store.scope_of(atom_id) == PROCESSING_SCOPE_EXCLUDED:
                    excluded_owned.append((atom_id, node.node_id, slot_name))
    for atom_id in atom_store.included_atom_ids():  # ordered → deterministic report
        if atom_id not in owned:
            findings.append(
                (EC.UNOWNED_INCLUDED_ATOM, f"included canonical atom {atom_id!r} is owned by no node")
            )
    for atom_id, node_id, slot_name in excluded_owned:
        findings.append(
            (
                EC.OWNED_EXCLUDED_ATOM,
                f"excluded atom {atom_id!r} placed in {node_id}.{slot_name} (excluded atoms belong in "
                f"header furniture_atoms, never a node slot)",
            )
        )


def _check_empty_containers(pmap: ProjectionMap, findings: list[tuple[EC, str]]) -> None:
    """inv 26 — a container with zero ``children`` **and** no ``heading_atoms``/``signature_atoms``
    owns nothing and leads nowhere → ``EMPTY_CONTAINER``. A pure projection check (no atom_store):
    it is the conjunction, so a container holding only a heading (a section head not yet given a body)
    is legitimate.
    """
    for node in pmap.nodes:
        if (
            isinstance(node, ContainerNode)
            and not node.children
            and not node.heading_atoms
            and not node.signature_atoms
        ):
            findings.append(
                (EC.EMPTY_CONTAINER, f"container {node.node_id!r} has no children and no heading/signature atoms")
            )


def _check_body_atom_order(pmap: ProjectionMap, atom_store, findings: list[tuple[EC, str]]) -> None:
    """inv 27 — each leaf's ``body_atoms`` is strictly ascending by canonical-stream index, no
    intra-list duplicate → else ``BODY_ATOMS_UNORDERED``.

    Checked **as-stored** — never on a ``sorted()`` copy, which would make a descending list pass
    (P3B-3, the exact vacuity the plan calls out). An atom absent from the canonical index is a
    coverage/reference fault (inv 1b/17), not an ordering fault, so it is skipped here rather than
    masking the ordering check.
    """
    index = {atom_id: i for i, atom_id in enumerate(atom_store.included_atom_ids())}
    for node in pmap.nodes:
        if not isinstance(node, LeafNode):
            continue
        body = node.body_atoms  # as-stored — do NOT sort
        if len(set(body)) != len(body):
            findings.append(
                (EC.BODY_ATOMS_UNORDERED, f"leaf {node.node_id!r} body_atoms has a repeated atom")
            )
            continue
        previous: int | None = None
        for atom_id in body:
            i = index.get(atom_id)
            if i is None:
                continue  # not in the canonical stream — an inv 1b/17 fault, not an ordering one
            # Strict ``<`` (not ``<=``): the duplicate check above already ``continue``d on any repeat,
            # so the remaining atom_ids are distinct ⇒ distinct indices, making ``<``/``<=`` identical
            # in production. ``<`` keeps the duplicate check *independently* load-bearing (an adjacent
            # repeat has equal indices, which ``<=`` would mask as an ordering fault, hiding a dropped
            # duplicate check behind the ordering check).
            if previous is not None and i < previous:
                findings.append(
                    (
                        EC.BODY_ATOMS_UNORDERED,
                        f"leaf {node.node_id!r} body_atoms not strictly ascending by canonical-stream "
                        f"index at atom {atom_id!r}",
                    )
                )
                break
            previous = i


def _check_minted_by(pmap: ProjectionMap, findings: list[tuple[EC, str]]) -> None:
    """inv 7 — ``minted_by`` recorded + the human/machine split enforced **both** ways →
    ``MINTED_BY_SPLIT`` (§3.C.2).

    One comparison covers all three failure modes the plan enumerates: a container must be
    ``human``-minted and a leaf ``machine``-minted, so ``minted_by != expected`` fires on a blank
    ``minted_by`` (**presence**: neither token), on a container carrying ``machine`` / a leaf carrying
    ``human`` (**split**, either direction), and on any out-of-vocabulary value (§3.C.1d). The
    authority is the *conceptual* minter, not the runtime writer — a machine cannot mint a container,
    a human cannot mint a leaf.
    """
    for node in pmap.nodes:
        is_container = isinstance(node, ContainerNode)
        expected = MINTED_BY_HUMAN if is_container else MINTED_BY_MACHINE
        if node.minted_by != expected:
            kind = "container" if is_container else "leaf"
            findings.append(
                (
                    EC.MINTED_BY_SPLIT,
                    f"{kind} node {node.node_id!r} has minted_by={node.minted_by!r}; a {kind} must be "
                    f"minted_by={expected!r} (conceptual minting authority, §3.C.2)",
                )
            )


def _position_paths(pmap: ProjectionMap) -> dict[str, str]:
    """Assign each node reachable from ``root_id`` its **position-path** — the dot-joined child-index
    trail from the root (root ``"0"``, its i-th child ``"0.<i>"``, and so on).

    A pre-order walk over the ``children`` edges resolved through ``by_id``. Cheap and local (no full
    inv-14 traversal, which is B-5): it visits each id once, tolerates a dangling/duplicate ``children``
    ref (skips the missing target, guards re-entry) so it cannot loop on a malformed map, and simply
    omits any node unreachable from the root — a node with no position-path has no position cheat to
    check, and its unreachability is inv 14's report at B-5, not this helper's.
    """
    paths: dict[str, str] = {}
    stack: list[tuple[str, str]] = [(pmap.root_id, "0")]
    while stack:
        node_id, path = stack.pop()
        if node_id in paths:
            continue  # already placed — a MULTI_PARENT/CYCLE artifact (inv 14, B-5); do not re-walk
        node = pmap.by_id.get(node_id)
        if node is None:
            continue  # dangling children ref (DANGLING_REF, inv 14, B-5)
        paths[node_id] = path
        if isinstance(node, ContainerNode):
            for i, child in enumerate(node.children):
                stack.append((child, f"{path}.{i}"))
    return paths


def _check_node_id_not_derived(pmap: ProjectionMap, findings: list[tuple[EC, str]]) -> None:
    """inv 6 — reject a ``node_id`` that matches an enumerated **derivation cheat** → ``NODE_ID_DERIVED``
    (§3.C.3, closed list).

    The seam (:func:`mint_node_id`) is the primary control — it structurally cannot derive — but it
    cannot stop a *hand-authored* map from typing a derived id, so the validator re-checks the closed
    set: ``node_id`` equal to the ``designation`` (exact), to the ``designation`` under casefold, to
    ``_slug(designation)`` / ``_slug(title)``, or to the node's own position-path string. An empty
    ``designation`` / ``title`` is not a derivation source (skipped). The
    **substring-of-rendered-handle** cheat needs ``render_handle`` and so re-runs at S4.3/B-4 (§3.C.3).
    """
    paths = _position_paths(pmap)
    for node in pmap.nodes:
        nid = node.node_id
        cheats: list[str] = []
        designation = node.designation
        title = node.title
        if designation:
            if nid == designation:
                cheats.append("exact designation")
            elif nid.casefold() == designation.casefold():
                cheats.append("casefold(designation)")
            if nid == _slug(designation):
                cheats.append("slug(designation)")
        if title and nid == _slug(title):
            cheats.append("slug(title)")
        if nid == paths.get(nid):
            cheats.append("position-path")
        if cheats:
            findings.append(
                (
                    EC.NODE_ID_DERIVED,
                    f"node_id {nid!r} appears derived from {', '.join(cheats)} — a node_id is opaque and "
                    f"minted independently (§3.C.3); it must not encode a designation/title/position",
                )
            )
