"""S4.6a — the authoring-evidence sidecar (engine half): schema binding, total-contract loader,
the split staleness digests, the S4.6 authored-map gate, and the deny-by-default writer
(s4_plan §1.4.1a/b/c, Audit 15, M9/X20; issue #32; post-audit remediation, user-ratified
2026-07-02).

Why this exists: the prose evidence behind each hand-authored container must live in a named,
versioned artifact (``<work>/authoring_evidence.json``, the committed companion to
``structure_map.json``) so it cannot drift into ad hoc notes (P2). The engine owns the schema, the
version constant, the digests, and the staleness rule; the *content* is the human author's
(S4.6, HITL).

The staleness rule (§1.4.1b, post-split) is the load-bearing design point. One hash cannot witness
two change domains, so each entry pins **two digests**, each through THE producer
(:func:`~engine.structure.structure_map._hash_canonical`, D-S4-I):

- :func:`decision_digest` — the human's **topology decision**: ``node_class`` + ordered ``children``
  node ids, *nothing else*. Re-bind-stable by D33 store-and-rebind (an S5 re-bind renames atoms,
  never node ids), and therefore **never machine-refreshed**: a stale decision digest always means
  a human changed the map's shape and must re-verify the rationale.
- :func:`extent_digest` — the **substrate binding**, slot-aware since the F5/Option B closure
  (user-ratified 2026-07-02): the node's **own** per-slot binding (``heading``/``signature`` for a
  container, ``body`` for a leaf — each a sorted set) plus the flat sorted union of everything
  **beneath** it. Any re-slot touching the node's own binding (heading→signature, or a heading
  atom moved into its own child leaf — the F5 case the earlier flat-set payload missed) stales
  exactly that node; a boundary move stales exactly the affected subtrees (an ancestor whose
  union is unchanged stays fresh); content addition cascades extent-staleness to every ancestor
  (accepted as honest). At S5, extents are mechanically re-stampable where a re-bind is unique
  and above threshold — the re-stamp protocol is S5.1's.

Display and handle metadata (``title``/``designation``/``handle_policy``/``minted_by``) enter
neither digest: re-titling a container does not invalidate the rationale for its *boundaries*.
``map_revision`` (stamped per entry as ``authored_at_revision``) is informational bookkeeping,
**never** a staleness trigger. The sidecar hash does **not** enter structure-map lineage; its M3
identity is its own ``AUTHORING_EVIDENCE_SCHEMA_VERSION`` + ``AUTHORING_EVIDENCE_STALE_CLASS``
(both persisted in the document, like every governed layer).

Beside each digest the entry persists its **payload witness** (DT-4 of the S4.6b tooling plan,
user-ratified 2026-07-02): the exact payload the digest was computed over — the decision payload
verbatim, the extent payload with each sorted atom-id list run-length encoded on the wire
(:func:`_encode_atom_runs`). The witness is *explanation data, never attestation*: the digests
remain the only staleness authority, the gate never reads a witness, and the loader
**self-verifies** every witness by recomputing its digest — a payload that does not reproduce its
digest is an internally incoherent sidecar and fails the load contract
(:class:`~engine.errors.StaleArtifactError` naming the node), never a quiet degraded mode. This is
what lets the S4.6b digest-diff explainer name WHICH children/atoms moved without any baseline
document, snapshot, or git archaeology.

The sidecar is **optional at generic load** (``load_structure_map`` never reads it) and **required
at the S4.6 authored-map gate** (§1.4.1a): :func:`assert_evidence_gate` holds the one-to-one
correspondence — every human-minted container has exactly one entry fresh on *both* digests, every
entry binds exactly a human-minted container. Findings come from the ONE non-raising producer
(:func:`evidence_findings`) and are raised as :class:`EvidenceGateError` (exit 12), whose typed
``(kind, message)`` payload draws on the closed :data:`EVIDENCE_FINDING_KINDS` set — deliberately
NOT new ``EC`` codes: the §4.0 vocabulary is the closed *structure-map* set, and evidence is its
own governed layer routed by stale class. The gate is a *correspondence* check between a sidecar
and a live map; a sidecar that cannot be loaded at all stays
:class:`~engine.errors.StaleArtifactError` at the load boundary (the taxonomy line).

Both gate functions assume an already-**validated** projection (one loaded through
``load_structure_map`` or passed through ``validate_projection``): they resolve ``children`` edges
and do not re-run Tier-2. On an unvalidated map, :func:`extent_digest` fails loud on a dangling
child reference and on any node revisit (a cycle, a multi-parent diamond, or a duplicate child
edge) rather than crashing, double-counting, or hanging.

Neutral core (inv 15): no language/book/typeface literal — the S0.2 scan globs this module and
the schema JSON beside it.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType

import jsonschema

from engine.errors import EngineError, MissingInputError, StaleArtifactError
from engine.structure.artifacts import (
    AUTHORING_EVIDENCE_SCHEMA_VERSION,
    AUTHORING_EVIDENCE_STALE_CLASS,
)
from engine.structure.projection import (
    MINTED_BY_HUMAN,
    ContainerNode,
    Node,
    ProjectionMap,
)
from engine.structure.structure_map import _hash_canonical, _reject_non_finite, _strict_int

#: The packaged Tier-1 schema (the D-S4-G ``structure/schema/`` posture).
SCHEMA_PATH = Path(__file__).resolve().parent / "schema" / "authoring_evidence.schema.json"


def load_evidence_schema() -> dict:
    """The parsed Tier-1 JSON-Schema, read fresh from :data:`SCHEMA_PATH` (a fresh dict per call,
    so no caller can mutate a shared cache)."""
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def evidence_schema_version_const(schema: Mapping | None = None) -> int:
    """The ``schema_version`` ``const`` the sidecar schema pins — half of the inv 10-style
    two-assertion binding to ``AUTHORING_EVIDENCE_SCHEMA_VERSION`` (the other half being the
    version-derived conforming fixture). Fails loud (``KeyError``/``ValueError``) on a schema whose
    const is missing or not a genuine int — a malformed schema file is a bug, not a fallback case.
    """
    if schema is None:
        schema = load_evidence_schema()
    const = schema["properties"]["schema_version"]["const"]
    if not isinstance(const, int) or isinstance(const, bool):
        raise ValueError(f"schema_version const must be an int, got {const!r}")
    return const


# --- typed model ----------------------------------------------------------------------------- #

#: Zero-width / invisible code points that survive ``str.strip()``: a field made only of these
#: would read as authored while carrying nothing, so blankness checks strip them alongside
#: whitespace.
_INVISIBLES = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff"))


def _require_text(value: object, where: str) -> str:
    """A genuine, visibly non-blank string — the type floor + blankness check every string field of
    the model shares. ``isinstance`` first: a non-str must fail as a *type* error rather than ride
    through truthiness into a digest comparison or keyed table where its canonical form could
    collide with a str's."""
    if not isinstance(value, str):
        raise TypeError(f"{where} must be a str, got {type(value).__name__}")
    if not value.translate(_INVISIBLES).strip():
        raise ValueError(f"{where} must be visibly non-blank (whitespace/zero-width-only is empty)")
    if any("\ud800" <= ch <= "\udfff" for ch in value):
        # A JSON-escaped lone surrogate ("\ud800") survives json.loads but cannot encode back to
        # UTF-8 — it would load cleanly and then crash the writer, breaking byte-idempotence.
        raise ValueError(f"{where} must be valid Unicode text (lone surrogate cannot round-trip)")
    return value


# --- the payload-witness wire codec (DT-4, s4_6_tooling_plan) ----------------------------------- #

#: Decode budget for expanded atom ids — **cumulative**, and shared across an entire document at
#: the load boundary. Without it a crafted pair (``["a_0", "a_999999999999"]``) would make the
#: loader materialize the whole range; without the *cumulative* accounting, N sub-ceiling runs
#: across slots and entries would sum without bound (the delta re-audit's demolisher forced a
#: multi-million-id, 697 MB allocation from a 578-byte sidecar that way — the digest coherence
#: check runs only *after* decode materializes the ids, so the budget must run first). The
#: ceiling sits far above the 10^5 addressability tier (D35) while keeping the failure a clean
#: load error instead of an OOM.
_MAX_RUN_EXPANSION = 1_000_000


def _split_decimal_tail(atom_id: str) -> tuple[str, str]:
    """``(prefix, digits)`` where ``digits`` is the maximal ASCII-decimal tail (possibly empty).

    ASCII-only deliberately: ``str.isdigit`` admits Unicode digits whose ``int()`` round-trip
    changes the character, which would break ``decode(encode(x)) == x``.
    """
    i = len(atom_id)
    while i > 0 and "0" <= atom_id[i - 1] <= "9":
        i -= 1
    return atom_id[:i], atom_id[i:]


def _decode_atom_runs(tokens: object, *, budget: list[int] | None = None) -> list[str]:
    """Inverse of :func:`_encode_atom_runs`: expand each ``[first, last]`` pair back to its ids.

    A malformed token (wrong shape, mismatched prefixes/widths, descending range) is ``ValueError``
    — the loader wraps it into the total contract. ``budget`` is a single-element mutable counter
    of ids this decode may still emit, **debited before any expansion**, so a crafted range is a
    clean failure, never an allocation. The loader shares ONE budget across the whole document
    (per-run or per-call ceilings alone sum without bound across slots/entries — the delta
    re-audit's allocation-bomb finding); a bare call gets a fresh per-call budget.
    """
    if not isinstance(tokens, (list, tuple)):
        raise TypeError(f"atom-run tokens must be a list, got {type(tokens).__name__}")
    if budget is None:
        budget = [_MAX_RUN_EXPANSION]
    out: list[str] = []
    for token in tokens:
        if isinstance(token, str):
            budget[0] -= 1
            if budget[0] < 0:
                raise ValueError(
                    f"atom-run decode exceeds the {_MAX_RUN_EXPANSION}-id budget — refusing the "
                    f"allocation (crafted or degenerate witness)"
                )
            out.append(token)
            continue
        if not (
            isinstance(token, (list, tuple))
            and len(token) == 2
            and all(isinstance(t, str) for t in token)
        ):
            raise ValueError(
                f"malformed atom-run token {token!r}: expected a plain id or a [first, last] pair"
            )
        first, last = token
        first_prefix, first_digits = _split_decimal_tail(first)
        last_prefix, last_digits = _split_decimal_tail(last)
        if not first_digits or first_prefix != last_prefix or len(first_digits) != len(last_digits):
            raise ValueError(
                f"malformed atom run {token!r}: endpoints must share a prefix and equal-width "
                f"decimal tails"
            )
        start, end = int(first_digits), int(last_digits)
        if end < start:
            raise ValueError(f"malformed atom run {token!r}: descending range")
        budget[0] -= end - start + 1
        if budget[0] < 0:
            raise ValueError(
                f"atom run {token!r} expands to {end - start + 1} ids — beyond the remaining "
                f"{_MAX_RUN_EXPANSION}-id budget; refusing the allocation"
            )
        width = len(first_digits)
        out.extend(f"{first_prefix}{value:0{width}d}" for value in range(start, end + 1))
    return out


def _encode_atom_runs(ids: list[str] | tuple[str, ...]) -> list:
    """The witness wire form of a sorted atom-id list: maximal consecutive runs (shared prefix,
    equal-width ASCII-decimal tails, values ascending by one) collapse to a two-element
    ``[first, last]`` array; everything else stays a plain string. Ids that don't fit the pattern
    simply never compress — no id-scheme literal anywhere (inv 15).

    Deterministic (one canonical encoding per input, so an unchanged re-stamp re-renders
    byte-identically) and self-checked on every call: ``decode(encode(x)) == x``, so a codec fault
    can never persist a lying witness.
    """
    tokens: list = []
    i, n = 0, len(ids)
    while i < n:
        prefix, digits = _split_decimal_tail(ids[i])
        j = i
        if digits:
            width, start = len(digits), int(digits)
            while j + 1 < n:
                nxt_prefix, nxt_digits = _split_decimal_tail(ids[j + 1])
                if (
                    nxt_prefix == prefix
                    and len(nxt_digits) == width
                    and int(nxt_digits) == start + (j + 1 - i)
                ):
                    j += 1
                else:
                    break
        tokens.append([ids[i], ids[j]] if j > i else ids[i])
        i = j + 1
    # budget = exactly the input length: a correct encoding decodes to precisely len(ids), so any
    # over-expansion bug is refused here too, and a legitimately huge in-memory encode never
    # trips the document-load ceiling
    if _decode_atom_runs(tokens, budget=[len(ids)]) != list(ids):
        raise ValueError(
            "atom-run encoding failed its decode(encode(x)) == x self-check — refusing to emit a "
            "witness that does not reproduce its input"
        )
    return tokens


# --- payload-witness shape validation (DT-4) ----------------------------------------------------- #

#: The two ``own`` shapes the extent producer emits: a container binds ``heading``+``signature``,
#: a leaf binds ``body``. A witness carrying any other slot combination is not a producer payload.
_OWN_SLOT_SHAPES = ({"heading", "signature"}, {"body"})


def _require_ascending_ids(values: object, where: str) -> tuple[str, ...]:
    """A strictly ascending, duplicate-free sequence of atom-id strings — the canonical
    sorted-set form the extent producer emits. Anything else cannot be a producer payload.
    Returned as a tuple (the witnesses are stored deep-frozen)."""
    if not isinstance(values, (list, tuple)):
        raise TypeError(f"{where} must be a list of atom ids, got {type(values).__name__}")
    ids = tuple(_require_text(value, f"{where}[{i}]") for i, value in enumerate(values))
    if any(b <= a for a, b in zip(ids, ids[1:])):
        raise ValueError(
            f"{where} must be strictly ascending with no duplicates — the canonical sorted-set "
            f"form the digest producers emit"
        )
    return ids


def _normalized_decision_payload(payload: object, where: str) -> dict:
    """Validate + normalize a decision-payload witness to the exact producer shape
    (``{"node_class": str, "children": [ordered node ids]}`` — children order is meaningful,
    never sorted here)."""
    if not isinstance(payload, Mapping):
        raise TypeError(f"{where} must be an object, got {type(payload).__name__}")
    if set(payload.keys()) != {"node_class", "children"}:
        raise ValueError(
            f"{where} must carry exactly node_class + children, got {sorted(map(str, payload.keys()))}"
        )
    node_class = _require_text(payload["node_class"], f"{where}.node_class")
    children = payload["children"]
    if not isinstance(children, (list, tuple)):
        raise TypeError(f"{where}.children must be a list, got {type(children).__name__}")
    return {
        "node_class": node_class,
        "children": tuple(
            _require_text(child, f"{where}.children[{i}]") for i, child in enumerate(children)
        ),
    }


def _normalized_extent_payload(payload: object, where: str) -> dict:
    """Validate + normalize an extent-payload witness to the exact producer shape
    (``{"own": <per-slot sorted sets>, "beneath": <sorted union>}``)."""
    if not isinstance(payload, Mapping):
        raise TypeError(f"{where} must be an object, got {type(payload).__name__}")
    if set(payload.keys()) != {"own", "beneath"}:
        raise ValueError(
            f"{where} must carry exactly own + beneath, got {sorted(map(str, payload.keys()))}"
        )
    own = payload["own"]
    if not isinstance(own, Mapping):
        raise TypeError(f"{where}.own must be an object, got {type(own).__name__}")
    if set(own.keys()) not in _OWN_SLOT_SHAPES:
        raise ValueError(
            f"{where}.own must carry exactly heading+signature (container) or body (leaf), got "
            f"{sorted(map(str, own.keys()))}"
        )
    return {
        "own": {
            slot: _require_ascending_ids(own[slot], f"{where}.own.{slot}") for slot in sorted(own)
        },
        "beneath": _require_ascending_ids(payload["beneath"], f"{where}.beneath"),
    }


@dataclass(frozen=True, slots=True)
class EvidenceEntry:
    """One authored-evidence record: the prose rationale for one hand-authored container, pinned
    to BOTH of the node's staleness digests at authoring time (§1.4.1b, post-split).

    ``authored_at_revision`` is the ``map_revision`` current when the entry was written —
    bookkeeping the staleness check never reads. Degenerate fields fail at construction (the
    ``Atom``/``Alias`` idiom): every string field must be a genuine, visibly non-blank ``str``
    (zero-width-only prose is no evidence), and the revision must be a genuine non-negative int
    (Tier-1 ``"integer"`` admits ``2.0``; ``bool`` subclasses int).

    ``decision_payload``/``extent_payload`` are the DT-4 payload witnesses, held **decoded and
    deep-frozen** (``MappingProxyType`` + tuples, the ``by_node`` posture — the wire run-encoding
    is the renderer/loader's concern) and normalized to the exact producer shapes. Coherence is a
    *model* invariant, not a load nicety: a witness that does not reproduce its digest through
    THE producer cannot be constructed at all — nor mutated out from under it afterwards (the
    delta re-audit's aliasing finding) — so a loaded entry's witness is always trustworthy and
    the explainer never needs a degraded mode for it.
    """

    node_id: str
    decision_digest: str
    extent_digest: str
    evidence: str
    authored_at_revision: int
    decision_payload: Mapping
    extent_payload: Mapping

    def __post_init__(self) -> None:
        _require_text(self.node_id, "EvidenceEntry.node_id")
        _require_text(self.decision_digest, "EvidenceEntry.decision_digest")
        _require_text(self.extent_digest, "EvidenceEntry.extent_digest")
        _require_text(self.evidence, "EvidenceEntry.evidence")
        _strict_int(self.authored_at_revision, "EvidenceEntry.authored_at_revision")
        if self.authored_at_revision < 0:
            raise ValueError(
                f"EvidenceEntry.authored_at_revision must be >= 0 (a map_revision), got "
                f"{self.authored_at_revision}"
            )
        decision = _normalized_decision_payload(
            self.decision_payload, "EvidenceEntry.decision_payload"
        )
        extent = _normalized_extent_payload(self.extent_payload, "EvidenceEntry.extent_payload")
        # hash the plain normalized forms (json cannot serialize a MappingProxyType), THEN freeze
        if _hash_canonical(decision) != self.decision_digest:
            raise ValueError(
                f"EvidenceEntry {self.node_id!r}: decision_payload does not reproduce "
                f"decision_digest — the stored witness is untrustworthy; re-stamp the node"
            )
        if _hash_canonical(extent) != self.extent_digest:
            raise ValueError(
                f"EvidenceEntry {self.node_id!r}: extent_payload does not reproduce "
                f"extent_digest — the stored witness is untrustworthy; re-stamp the node"
            )
        object.__setattr__(self, "decision_payload", MappingProxyType(decision))
        object.__setattr__(
            self,
            "extent_payload",
            MappingProxyType({"own": MappingProxyType(extent["own"]), "beneath": extent["beneath"]}),
        )


@dataclass(frozen=True, slots=True)
class AuthoringEvidence:
    """A loaded sidecar: the book it documents, the entry tuple, and the ``node_id``-keyed read
    table.

    ``book`` binds the sidecar to its workspace (R2): a structurally valid sidecar from another
    book is the wrong artifact, and the loader's ``expected_book`` check makes that a loud load
    failure instead of a confusing gate result. The gate's correspondence is *one* entry per
    container, so a duplicate ``node_id`` cannot key the table — it raises at construction (the
    ``ProjectionMap`` precedent; the loader wraps it as
    :class:`~engine.errors.StaleArtifactError` at the load boundary). An empty sidecar is valid:
    coverage is the gate's demand (§1.4.1a), never the model's.
    """

    book: str
    entries: tuple[EvidenceEntry, ...]
    #: Derived read-only ``node_id`` → entry table (built in ``__post_init__``, excluded from
    #: eq/repr — a projection of ``entries``, not independent state).
    by_node: Mapping[str, EvidenceEntry] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        _require_text(self.book, "AuthoringEvidence.book")
        object.__setattr__(self, "entries", tuple(self.entries))
        table: dict[str, EvidenceEntry] = {}
        for entry in self.entries:
            if entry.node_id in table:
                raise ValueError(
                    f"duplicate evidence entry for node {entry.node_id!r} — the gate's "
                    f"correspondence is one entry per container, so a keyed table cannot hold two"
                )
            table[entry.node_id] = entry
        object.__setattr__(self, "by_node", MappingProxyType(table))


# --- the split staleness digests (§1.4.1b) ------------------------------------------------------ #


def decision_payload(node: Node) -> dict:
    """THE decision payload — what :func:`decision_digest` hashes, and (verbatim) the DT-4 witness
    an entry stores beside that digest: ``{"node_class": ..., "children": [ordered child node
    ids]}`` (a leaf contributes the empty sequence; tuples — the stored-witness interior form,
    identical canonical-JSON bytes). One producer for digest and witness, so the two can never be
    computed from different definitions."""
    return {
        "node_class": node.node_class,
        "children": tuple(node.children) if isinstance(node, ContainerNode) else (),
    }


def decision_digest(node: Node) -> str:
    """THE decision digest — the human-topology half of the split staleness key (§1.4.1b).

    Payload: :func:`decision_payload`, hashed through the single S4 producer (D-S4-I). The field
    list is CLOSED to atom ids — that is the R1 split: an S5 re-bind that renames every atom
    leaves every decision digest byte-identical, so this digest is **never machine-refreshed**;
    when it stales, a human changed the map's shape and must re-verify the rationale. Reading
    order is structure (§3.B.6), so a child reorder changes it. Display/handle/minting metadata
    never enters. Authoring tooling stamps entries via :func:`build_evidence_entry` — never a
    hand-computed hash.
    """
    return _hash_canonical(decision_payload(node))


def extent_digest(node: Node, projection: ProjectionMap) -> str:
    """THE extent digest — the substrate-binding half of the split staleness key (§1.4.1b,
    slot-aware since the F5/Option B closure, user-ratified 2026-07-02).

    Payload: ``{"own": <the node's per-slot binding, each slot a sorted set>, "beneath": <the
    flat sorted union of every descendant's coverage>}`` — a container's ``own`` carries
    ``heading``/``signature``, a leaf's carries ``body``; ``beneath`` unions descendants' own
    slots and bodies without distinguishing them — hashed through the single S4 producer
    (D-S4-I). Semantics that fall out: a re-slot (heading→signature within the node, or a heading
    atom moved into the node's own child leaf — the F5 case the earlier flat-set payload missed)
    changes the node's OWN binding and stales exactly that node, while unchanged-union ancestors
    stay fresh; a boundary move stales exactly the subtrees whose union changed; internal
    re-segmentation under an unchanged boundary stales nothing above it; content addition
    cascades to every ancestor (honest — they genuinely span more than they were authored
    against). Assumes a validated map; fails loud (``ValueError``) on a dangling child reference
    or any node revisit (cycle / multi-parent / duplicate edge) rather than crashing or hanging.
    """
    return _hash_canonical(extent_payload(node, projection))


def _own_extent_payload(node: Node) -> dict[str, tuple[str, ...]]:
    """The canonical ``own`` half of an extent payload.

    Kept separate from the descendant walk so the evidence gate's batch path and the scalar
    producer cannot drift on slot names, sorting, or node-kind dispatch.
    """
    if isinstance(node, ContainerNode):
        return {
            "heading": tuple(sorted(node.heading_atoms)),
            "signature": tuple(sorted(node.signature_atoms)),
        }
    return {"body": tuple(sorted(node.body_atoms))}


def extent_payload(node: Node, projection: ProjectionMap) -> dict:
    """THE extent payload — what :func:`extent_digest` hashes, and (run-encoded on the wire) the
    DT-4 witness an entry stores beside that digest: the node's ``own`` per-slot binding plus the
    flat sorted ``beneath`` union (tuples — the stored-witness interior form, identical
    canonical-JSON bytes). One producer for digest and witness. Same validated-map precondition
    as the digest (fails loud on dangling/revisited nodes)."""
    return {
        "own": _own_extent_payload(node),
        "beneath": tuple(sorted(_beneath_atom_ids(node, projection))),
    }


def _require_child(child_id: str, parent_id: str, projection: ProjectionMap) -> Node:
    child = projection.by_id.get(child_id)
    if child is None:
        raise ValueError(
            f"extent_digest: child {child_id!r} of {parent_id!r} resolves to no "
            f"node — dangling reference; validate the map before digesting"
        )
    return child


def _beneath_atom_ids(node: Node, projection: ProjectionMap) -> set[str]:
    """The transitive atom coverage strictly BENEATH ``node`` (descendants only — the node's own
    slots are the payload's ``own`` half), resolved through ``projection.by_id`` (an iterative
    walk — no recursion-depth ceiling on deep maps)."""
    coverage: set[str] = set()
    seen: set[str] = {node.node_id}
    stack: list[Node] = [
        _require_child(child_id, node.node_id, projection)
        for child_id in (node.children if isinstance(node, ContainerNode) else ())
    ]
    while stack:
        current = stack.pop()
        if current.node_id in seen:
            raise ValueError(
                f"extent_digest: node {current.node_id!r} revisited under {node.node_id!r} — the "
                f"projection has a cycle or a multi-parent/duplicate child edge (Tier-2's CYCLE / "
                f"MULTI_PARENT / DUPLICATE_CHILD_REF territory); validate the map before digesting"
            )
        seen.add(current.node_id)
        if isinstance(current, ContainerNode):
            coverage.update(current.heading_atoms)
            coverage.update(current.signature_atoms)
            stack.extend(
                _require_child(child_id, current.node_id, projection)
                for child_id in current.children
            )
        else:
            coverage.update(current.body_atoms)
    return coverage


@dataclass(frozen=True, slots=True)
class _ExtentDigestBatch:
    """Internal result and deterministic work counters for the gate's shared extent pass."""

    by_node: Mapping[str, str]
    node_visits: int
    edge_visits: int
    witness_reuses: int
    live_hashes: int


def _batch_extent_digests(
    entries: tuple[EvidenceEntry, ...], projection: ProjectionMap
) -> _ExtentDigestBatch | None:
    """Compute requested live extent digests in one iterative bottom-up projection pass.

    A validated projection is a tree, so after a child's digest has been decided its subtree set
    can become its parent's accumulator. That removes the old independent descendant walk for
    every evidence entry. The persisted extent witness is explanation data, but it is also an
    exact, constructor-verified copy of the payload behind ``entry.extent_digest``: when live
    ``own`` and ``beneath`` are exactly equal to that witness, reusing the entry digest is
    byte-identical to hashing the same canonical JSON again. A changed payload is always hashed
    through THE producer, preserving even the theoretical SHA-collision behavior of the scalar
    comparison and producing the same live digest in a stale finding.

    Return ``None`` if the flat table is not a tree (dangling edge, duplicate/multi-parent edge,
    or cycle). The caller then uses the scalar producer in sidecar order, retaining its existing
    fail-loud message and malformed-map behavior. Validated production maps stay on this path.
    """
    requested = {entry.node_id: entry for entry in entries}
    if not requested:
        return _ExtentDigestBatch({}, 0, 0, 0, 0)

    children_by_node: dict[str, tuple[str, ...]] = {}
    parent_by_node: dict[str, str] = {}
    edge_visits = 0
    for node in projection.nodes:
        children = node.children if isinstance(node, ContainerNode) else ()
        children_by_node[node.node_id] = children
        for child_id in children:
            edge_visits += 1
            if child_id not in projection.by_id or child_id in parent_by_node:
                return None
            parent_by_node[child_id] = node.node_id

    pending = {node_id: len(children) for node_id, children in children_by_node.items()}
    ready = [node_id for node_id, count in pending.items() if count == 0]
    subtree_atoms: dict[str, set[str]] = {}
    digests: dict[str, str] = {}
    node_visits = 0
    witness_reuses = 0
    live_hashes = 0

    while ready:
        node_id = ready.pop()
        node = projection.by_id[node_id]
        children = children_by_node[node_id]
        child_sets = [subtree_atoms.pop(child_id) for child_id in children]
        if child_sets:
            beneath = max(child_sets, key=len)
            for child_set in child_sets:
                if child_set is not beneath:
                    beneath.update(child_set)
        else:
            beneath = set()

        entry = requested.get(node_id)
        own = _own_extent_payload(node)
        if entry is not None:
            stored_beneath = entry.extent_payload["beneath"]
            if entry.extent_payload["own"] == own and beneath == set(stored_beneath):
                # EvidenceEntry.__post_init__ proved this witness hashes to the stored digest.
                digests[node_id] = entry.extent_digest
                witness_reuses += 1
            else:
                digests[node_id] = _hash_canonical(
                    {"own": own, "beneath": tuple(sorted(beneath))}
                )
                live_hashes += 1

        for atom_ids in own.values():
            beneath.update(atom_ids)
        subtree_atoms[node_id] = beneath
        node_visits += 1

        parent_id = parent_by_node.get(node_id)
        if parent_id is not None:
            pending[parent_id] -= 1
            if pending[parent_id] == 0:
                ready.append(parent_id)

    if node_visits != len(projection.nodes):
        return None
    return _ExtentDigestBatch(
        digests,
        node_visits=node_visits,
        edge_visits=edge_visits,
        witness_reuses=witness_reuses,
        live_hashes=live_hashes,
    )


# --- load boundary (total contract) ------------------------------------------------------------ #


def load_authoring_evidence(path: Path, *, expected_book: str | None = None) -> AuthoringEvidence:
    """Read + validate a persisted sidecar: parse JSON → version → stale class → Tier-1 → typed
    build → optional book binding.

    The failure contract is **total** (the ``load_structure_map`` precedent): a missing file is
    :class:`~engine.errors.MissingInputError` (absent, not stale — the sidecar is optional at
    generic load, §1.4.1a); an unreadable file / non-UTF-8 / non-JSON (including a parse-depth
    blowup) / non-finite-float / stale-version / wrong-stale-class / Tier-1-malformed content —
    and any model-level ``ValueError``/``TypeError`` out of the typed build (a zero-fraction float
    revision, blank prose, a duplicate ``node_id``) — is
    :class:`~engine.errors.StaleArtifactError`. Nothing else escapes. With ``expected_book`` set,
    a sidecar naming a different book is likewise :class:`~engine.errors.StaleArtifactError`: the
    wrong artifact for this workspace, however well-formed.
    """
    path = Path(path)
    if not path.is_file():
        raise MissingInputError(f"authoring-evidence sidecar not found at {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise StaleArtifactError(f"authoring evidence at {path} is unreadable: {exc}") from exc
    except UnicodeDecodeError as exc:
        raise StaleArtifactError(f"authoring evidence at {path} is not valid UTF-8: {exc}") from exc
    try:
        doc = json.loads(text, parse_constant=_reject_non_finite)
    except RecursionError as exc:
        raise StaleArtifactError(
            f"authoring evidence at {path} is not valid JSON: nested beyond parseable depth"
        ) from exc
    except ValueError as exc:  # json.JSONDecodeError subclasses ValueError; also _reject_non_finite
        raise StaleArtifactError(f"authoring evidence at {path} is not valid JSON: {exc}") from exc
    if not isinstance(doc, dict):
        raise StaleArtifactError(
            f"authoring evidence at {path}: top level is {type(doc).__name__}, not an object"
        )
    version = doc.get("schema_version")
    if version != AUTHORING_EVIDENCE_SCHEMA_VERSION:
        # Checked before Tier-1 so a stale sidecar reads as STALE (the M3/S8.1 routing hook),
        # not as a generic shape failure against a schema it was never written for.
        raise StaleArtifactError(
            f"authoring evidence at {path} carries schema_version {version!r}, not the registered "
            f"{AUTHORING_EVIDENCE_SCHEMA_VERSION} — stale sidecar; refresh it consciously"
        )
    stale_class = doc.get("stale_class")
    if stale_class != AUTHORING_EVIDENCE_STALE_CLASS:
        # Same M3 routing discipline for the layer discriminator (the atom-store envelope
        # precedent): a foreign artifact under this filename must say so, not fail as shape.
        raise StaleArtifactError(
            f"authoring evidence at {path} declares stale_class {stale_class!r}, not "
            f"{AUTHORING_EVIDENCE_STALE_CLASS!r} — not an authoring-evidence sidecar"
        )
    try:
        jsonschema.validate(doc, load_evidence_schema())
    except jsonschema.ValidationError as exc:
        location = "/".join(str(p) for p in exc.absolute_path) or "<root>"
        raise StaleArtifactError(
            f"authoring evidence at {path} failed Tier-1 shape validation at {location}: {exc.message}"
        ) from exc
    try:
        _strict_int(doc["schema_version"], "schema_version")
        # ONE decode budget across the whole document — per-run ceilings alone sum without bound
        # over slots and entries (a sub-KB sidecar forced a multi-million-id allocation in the
        # delta re-audit), and the digest coherence check only runs AFTER decode materializes ids.
        document_budget = [_MAX_RUN_EXPANSION]
        evidence = AuthoringEvidence(
            book=doc["book"],
            entries=tuple(
                EvidenceEntry(
                    node_id=e["node_id"],
                    decision_digest=e["decision_digest"],
                    extent_digest=e["extent_digest"],
                    evidence=e["evidence"],
                    authored_at_revision=e["authored_at_revision"],
                    decision_payload=e["decision_payload"],
                    extent_payload={
                        # Wire → decoded witness; the entry model then self-verifies each payload
                        # against its digest, so an expanded run that lies about the substrate
                        # cannot survive the load (DT-4).
                        "own": {
                            slot: _decode_atom_runs(tokens, budget=document_budget)
                            for slot, tokens in e["extent_payload"]["own"].items()
                        },
                        "beneath": _decode_atom_runs(
                            e["extent_payload"]["beneath"], budget=document_budget
                        ),
                    },
                )
                for e in doc["entries"]
            ),
        )
    except (ValueError, TypeError) as exc:
        raise StaleArtifactError(f"malformed authoring evidence at {path}: {exc}") from exc
    if expected_book is not None and evidence.book != expected_book:
        raise StaleArtifactError(
            f"authoring evidence at {path} belongs to book {evidence.book!r}, not the expected "
            f"{expected_book!r} — wrong sidecar for this workspace"
        )
    return evidence


# --- the S4.6 authored-map gate (§1.4.1a, Audit 15) --------------------------------------------- #

#: The closed evidence-finding vocabulary — literal kinds, deliberately NOT ``EC`` codes (§4.0 is
#: the closed *structure-map* set; evidence is its own governed layer). S4.6 tooling's status
#: listing consumes these via :func:`evidence_findings`.
EVIDENCE_FINDING_KINDS = ("missing", "orphaned", "misbound", "stale-decision", "stale-extent")


class EvidenceGateError(EngineError):
    """The authoring-evidence gate failed: a loaded sidecar does not hold against the live map —
    the carrier for the collected ``(kind, message)`` payload from :func:`evidence_findings`.

    Lives beside its raiser (the ``StructureValidationError``-beside-``EC`` precedent) and takes
    the next free exit code after it. Distinct from :class:`~engine.errors.StaleArtifactError` on
    the taxonomy line the remediation drew: *staleness* is a persisted artifact failing its own
    load contract (including a stale freeze pin — ``assert_freeze_matches`` keeps
    ``StaleArtifactError``); the gate is a **correspondence** between two independently loadable
    things, with typed findings a worklist can route on (:attr:`kinds`). Kinds are validated
    against the closed :data:`EVIDENCE_FINDING_KINDS` set so a typo cannot mint a pseudo-kind, and
    an empty payload is a programming error (it would read "holds, yet raised") — it fails loud.
    """

    exit_code = 12

    def __init__(self, findings: Iterable[tuple[str, str]]):
        normalized = []
        for kind, message in findings:
            if kind not in EVIDENCE_FINDING_KINDS:
                raise ValueError(
                    f"unknown evidence-finding kind {kind!r} — the closed set is "
                    f"{EVIDENCE_FINDING_KINDS}"
                )
            normalized.append((kind, str(message)))
        self.findings = tuple(normalized)
        if not self.findings:
            raise ValueError(
                "EvidenceGateError requires at least one (kind, message) finding — an empty "
                "payload would signal a gate failure with no stated reason."
            )
        super().__init__(
            "authoring-evidence gate failed — the sidecar does not hold against the live map:\n  "
            + "\n  ".join(f"[{kind}] {message}" for kind, message in self.findings)
        )

    @property
    def kinds(self) -> tuple[str, ...]:
        """The finding kinds in report order (with multiplicity) — the routing surface a worklist
        or re-stamp tool reads."""
        return tuple(kind for kind, _ in self.findings)


def _describe(node: Node) -> str:
    """``node_id`` plus the human-facing title where one exists — worklist messages should not
    force a human to resolve opaque ids by hand."""
    title = getattr(node, "title", "")
    return f"{node.node_id!r} ({title!r})" if title else f"{node.node_id!r}"


def _attributed_findings(
    evidence: AuthoringEvidence, projection: ProjectionMap
) -> tuple[tuple[str, str, str], ...]:
    """The single findings core, each finding attributed to its subject ``node_id`` —
    ``(node_id, kind, message)``. :func:`evidence_findings` is the (kind, message) projection of
    exactly this sequence; the S4.6b worklist view consumes the attribution directly, so per-node
    status is never re-derived by parsing messages or by a second staleness computation."""
    findings: list[tuple[str, str, str]] = []
    human_containers = {
        node.node_id
        for node in projection.nodes
        if isinstance(node, ContainerNode) and node.minted_by == MINTED_BY_HUMAN
    }
    extent_entries = tuple(
        entry for entry in evidence.entries if entry.node_id in human_containers
    )
    extent_batch = _batch_extent_digests(extent_entries, projection)
    for node in projection.nodes:  # map reading order, not lexicographic id order
        if node.node_id in human_containers and node.node_id not in evidence.by_node:
            findings.append(
                (
                    node.node_id,
                    "missing",
                    f"human-minted container {_describe(node)} has no evidence entry",
                )
            )
    for entry in evidence.entries:
        node = projection.by_id.get(entry.node_id)
        if node is None:
            findings.append(
                (
                    entry.node_id,
                    "orphaned",
                    f"evidence entry {entry.node_id!r} binds no node in the map",
                )
            )
            continue
        if entry.node_id not in human_containers:
            findings.append(
                (
                    entry.node_id,
                    "misbound",
                    f"evidence entry {entry.node_id!r} binds a node that is not a human-minted "
                    f"container — evidence documents hand-authored containers only",
                )
            )
            continue
        live_decision = decision_digest(node)
        if entry.decision_digest != live_decision:
            findings.append(
                (
                    entry.node_id,
                    "stale-decision",
                    f"evidence for {_describe(node)} is STALE on its decision digest: pinned "
                    f"{entry.decision_digest!r} != live {live_decision!r} — the container's class "
                    f"or child topology changed; re-verify the authoring decision and re-stamp",
                )
            )
        live_extent = (
            extent_batch.by_node[entry.node_id]
            if extent_batch is not None
            else extent_digest(node, projection)
        )
        if entry.extent_digest != live_extent:
            findings.append(
                (
                    entry.node_id,
                    "stale-extent",
                    f"evidence for {_describe(node)} is STALE on its extent digest: pinned "
                    f"{entry.extent_digest!r} != live {live_extent!r} — the subtree's atom "
                    f"coverage changed; re-verify the boundary extent and re-stamp",
                )
            )
    return tuple(findings)


def evidence_findings(
    evidence: AuthoringEvidence, projection: ProjectionMap
) -> tuple[tuple[str, str], ...]:
    """THE findings producer — non-raising; the gate raises exactly this payload, and S4.6
    tooling's status listing reads it directly.

    The correspondence is one-to-one both ways: every ``minted_by:human`` container must have
    exactly one entry fresh on **both** digests, and every entry must bind exactly a human-minted
    container. Kinds (closed set :data:`EVIDENCE_FINDING_KINDS`): ``missing`` coverage gaps are
    reported first, in **map reading order** (the order a human works a worklist), then per
    sidecar entry ``orphaned`` (binds no node), ``misbound`` (binds a non-human-container), and
    the per-digest ``stale-decision`` / ``stale-extent`` — both checked independently, so one
    entry can carry both. Digests are repr'd into messages (a crafted digest cannot forge finding
    lines). ``authored_at_revision`` is never consulted (§1.4.1b). Assumes a validated projection
    (see the module docstring). Returns ``()`` when the pair holds.
    """
    return tuple((kind, message) for _, kind, message in _attributed_findings(evidence, projection))


def assert_evidence_gate(evidence: AuthoringEvidence, projection: ProjectionMap) -> None:
    """Hold a loaded sidecar against the live projection — fail loud listing **every** finding.

    Raises :class:`EvidenceGateError` carrying :func:`evidence_findings`'s payload verbatim (one
    producer, one raise — the ``assert_freeze_matches`` collect-all idiom). Returns ``None`` when
    the pair holds. Callers hold a :class:`~engine.structure.structure_map.StructureMap`; pass its
    ``projection``.
    """
    findings = evidence_findings(evidence, projection)
    if findings:
        raise EvidenceGateError(findings)


# --- the engine writer (R3): render / deny-by-default write / entry builder --------------------- #


def build_evidence_entry(
    node: Node, projection: ProjectionMap, *, evidence: str, authored_at_revision: int
) -> EvidenceEntry:
    """Stamp a fresh entry for a hand-authored container — BOTH digests through THE producers,
    never a hand-computed hash.

    Refuses a node the gate would flag as ``misbound`` (a machine leaf, a machine-minted node):
    catching the caller error at authoring time beats a latent gate failure later.
    """
    if not (isinstance(node, ContainerNode) and node.minted_by == MINTED_BY_HUMAN):
        raise ValueError(
            f"build_evidence_entry: {node.node_id!r} is not a human-minted container — evidence "
            f"documents hand-authored containers only"
        )
    d_payload = decision_payload(node)
    e_payload = extent_payload(node, projection)
    return EvidenceEntry(
        node_id=node.node_id,
        decision_digest=_hash_canonical(d_payload),
        extent_digest=_hash_canonical(e_payload),
        evidence=evidence,
        authored_at_revision=authored_at_revision,
        decision_payload=d_payload,
        extent_payload=e_payload,
    )


def render_authoring_evidence(evidence: AuthoringEvidence) -> str:
    """The sidecar's canonical file form: stable indented JSON, newline-terminated (the
    ``render_freeze_record`` posture) — regenerating unchanged evidence is byte-idempotent, so a
    no-change write is an empty git diff."""
    doc = {
        "schema_version": AUTHORING_EVIDENCE_SCHEMA_VERSION,
        "stale_class": AUTHORING_EVIDENCE_STALE_CLASS,
        "book": evidence.book,
        "entries": [
            {
                "node_id": entry.node_id,
                "decision_digest": entry.decision_digest,
                "extent_digest": entry.extent_digest,
                "evidence": entry.evidence,
                "authored_at_revision": entry.authored_at_revision,
                "decision_payload": {
                    "node_class": entry.decision_payload["node_class"],
                    "children": list(entry.decision_payload["children"]),
                },
                "extent_payload": {
                    # Decoded → wire runs; the codec's per-call decode(encode(x)) == x self-check
                    # plus the deterministic maximal-run rule keep re-stamps byte-idempotent.
                    "own": {
                        slot: _encode_atom_runs(ids)
                        for slot, ids in sorted(entry.extent_payload["own"].items())
                    },
                    "beneath": _encode_atom_runs(entry.extent_payload["beneath"]),
                },
            }
            for entry in evidence.entries
        ],
    }
    return json.dumps(doc, indent=2, ensure_ascii=False, allow_nan=False) + "\n"


def write_authoring_evidence(
    path: Path, evidence: AuthoringEvidence, *, force: bool = False
) -> Path:
    """Write the committed sidecar — deny-by-default against overwriting *different* evidence (the
    ``write_freeze_record`` posture).

    The prose rationale is hand-authored and irreproducible (P4), so identical bytes are an
    idempotent no-op and a differing existing sidecar is refused without ``force=True`` — replacing
    authored evidence is explicit human intent, never a side effect. The document is rendered
    before any disk mutation.
    """
    rendered = render_authoring_evidence(evidence)
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if existing == rendered:
            return path
        if not force:
            raise StaleArtifactError(
                f"{path} already holds different authoring evidence — refusing the silent "
                f"overwrite. The prose rationale is hand-authored and irreproducible; pass "
                f"force=True only after verifying the replacement is intentional"
            )
    path.write_text(rendered, encoding="utf-8")
    return path
