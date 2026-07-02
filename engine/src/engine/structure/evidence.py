"""S4.6a — the authoring-evidence sidecar (engine half): schema binding, total-contract loader,
the canonical node-structure digest, and the S4.6 authored-map gate (s4_plan §1.4.1a/b/c,
Audit 15, M9/X20; issue #32).

Why this exists: the prose evidence behind each hand-authored container must live in a named,
versioned artifact (``<work>/authoring_evidence.json``, the committed companion to
``structure_map.json``) so it cannot drift into ad hoc notes (P2). The engine owns the schema, the
version constant, and the staleness rule; the *content* is Ben's (S4.6, HITL).

The staleness rule (§1.4.1b) is the load-bearing design point:

- Evidence is stale **iff** its bound node's **canonical structure digest** changes — an explicit
  field list: ``node_class`` + ordered ``children`` + owned atom ids (per owning slot), hashed
  through THE producer (:func:`~engine.structure.structure_map._hash_canonical`, D-S4-I). Display
  and handle metadata (``title``/``designation``/``handle_policy``/``minted_by``) never enter it:
  re-titling a container does not invalidate the rationale for its *boundaries*.
- ``map_revision`` (stamped per entry as ``authored_at_revision``) is informational bookkeeping,
  **never** a staleness trigger — a revision tick that changed *other* nodes must not stale this
  one's evidence.
- The sidecar hash does **not** enter structure-map lineage; its M3 identity is its own
  ``AUTHORING_EVIDENCE_SCHEMA_VERSION`` + ``AUTHORING_EVIDENCE_STALE_CLASS``.

The sidecar is **optional at generic load** (``load_structure_map`` never reads it) and **required
at the S4.6 authored-map gate** (§1.4.1a): :func:`assert_evidence_gate` holds the one-to-one
correspondence — every human-minted container has exactly one non-stale entry, every entry binds
exactly a human-minted container — collecting every finding into one raise (the
``assert_freeze_matches`` idiom). Gate failures are :class:`~engine.errors.StaleArtifactError`
(the persisted sidecar no longer holds against the live map — one human action: re-author or
refresh the evidence consciously), deliberately NOT new ``EC`` codes: the §4.0 vocabulary is the
closed *structure-map* set, and evidence is its own governed layer routed by stale class.

Neutral core (inv 15): no language/book/typeface literal — the S0.2 scan globs this module and
the schema JSON beside it.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType

import jsonschema

from engine.errors import MissingInputError, StaleArtifactError
from engine.structure.artifacts import AUTHORING_EVIDENCE_SCHEMA_VERSION
from engine.structure.projection import (
    MINTED_BY_HUMAN,
    ContainerNode,
    Node,
    ProjectionMap,
    _owning_slots,
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


@dataclass(frozen=True, slots=True)
class EvidenceEntry:
    """One authored-evidence record: the prose rationale for one hand-authored container, pinned
    to the node's structure digest at authoring time (§1.4.1b).

    ``authored_at_revision`` is the ``map_revision`` current when the entry was written —
    bookkeeping the staleness check never reads. Degenerate fields fail at construction (the
    ``Atom``/``Alias`` idiom): whitespace-only ``evidence`` is no evidence, and the revision must
    be a genuine non-negative int (Tier-1 ``"integer"`` admits ``2.0``; ``bool`` subclasses int).
    """

    node_id: str
    node_digest: str
    evidence: str
    authored_at_revision: int

    def __post_init__(self) -> None:
        if not self.node_id:
            raise ValueError("EvidenceEntry.node_id must name the bound node (non-empty)")
        if not self.node_digest:
            raise ValueError("EvidenceEntry.node_digest must carry the authoring-time digest (non-empty)")
        if not self.evidence.strip():
            raise ValueError("EvidenceEntry.evidence must carry the prose rationale (non-blank)")
        _strict_int(self.authored_at_revision, "EvidenceEntry.authored_at_revision")
        if self.authored_at_revision < 0:
            raise ValueError(
                f"EvidenceEntry.authored_at_revision must be >= 0 (a map_revision), got "
                f"{self.authored_at_revision}"
            )


@dataclass(frozen=True, slots=True)
class AuthoringEvidence:
    """A loaded sidecar: the entry tuple plus its ``node_id``-keyed read table.

    The gate's correspondence is *one* entry per container, so a duplicate ``node_id`` cannot key
    the table — it raises at construction (the ``ProjectionMap`` precedent; the loader wraps it as
    :class:`~engine.errors.StaleArtifactError` at the load boundary). An empty sidecar is valid:
    coverage is the gate's demand (§1.4.1a), never the model's.
    """

    entries: tuple[EvidenceEntry, ...]
    #: Derived read-only ``node_id`` → entry table (built in ``__post_init__``, excluded from
    #: eq/repr — a projection of ``entries``, not independent state).
    by_node: Mapping[str, EvidenceEntry] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
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


# --- the canonical node-structure digest (§1.4.1b) -------------------------------------------- #


def node_structure_digest(node: Node) -> str:
    """THE canonical node-structure digest — the sidecar's ONLY staleness key (§1.4.1b).

    An explicit field list, hashed through the single S4 producer (D-S4-I): ``node_class``,
    ordered ``children`` (reading order is structure, so a reorder changes the digest; a leaf
    contributes the empty list), and the owned atom ids per owning slot (via
    :func:`~engine.structure.projection._owning_slots`, the one enumeration of atom ownership —
    slot names included, so moving an atom between heading and signature is a structure change).
    Nothing else enters: display/handle/minting metadata may change freely without staleing
    evidence. Authoring tooling stamps entries with this same function — never a hand-computed
    hash.
    """
    payload = {
        "node_class": node.node_class,
        "children": list(node.children) if isinstance(node, ContainerNode) else [],
        "owned_atoms": {slot: list(ids) for slot, ids in _owning_slots(node)},
    }
    return _hash_canonical(payload)


# --- load boundary (total contract) ------------------------------------------------------------ #


def load_authoring_evidence(path: Path) -> AuthoringEvidence:
    """Read + validate a persisted sidecar: parse JSON → version → Tier-1 → typed build.

    The failure contract is **total** (the ``load_structure_map`` precedent): a missing file is
    :class:`~engine.errors.MissingInputError` (absent, not stale — the sidecar is optional at
    generic load, §1.4.1a); non-UTF-8 / non-JSON / non-finite-float / stale-version /
    Tier-1-malformed content — and any model-level ``ValueError``/``TypeError`` out of the typed
    build (a zero-fraction float revision, blank prose, a duplicate ``node_id``) — is
    :class:`~engine.errors.StaleArtifactError`. Nothing else escapes.
    """
    path = Path(path)
    if not path.is_file():
        raise MissingInputError(f"authoring-evidence sidecar not found at {path}")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_non_finite)
    except UnicodeDecodeError as exc:
        raise StaleArtifactError(f"authoring evidence at {path} is not valid UTF-8: {exc}") from exc
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
    try:
        jsonschema.validate(doc, load_evidence_schema())
    except jsonschema.ValidationError as exc:
        location = "/".join(str(p) for p in exc.absolute_path) or "<root>"
        raise StaleArtifactError(
            f"authoring evidence at {path} failed Tier-1 shape validation at {location}: {exc.message}"
        ) from exc
    try:
        _strict_int(doc["schema_version"], "schema_version")
        return AuthoringEvidence(
            entries=tuple(
                EvidenceEntry(
                    node_id=e["node_id"],
                    node_digest=e["node_digest"],
                    evidence=e["evidence"],
                    authored_at_revision=e["authored_at_revision"],
                )
                for e in doc["entries"]
            )
        )
    except (ValueError, TypeError) as exc:
        raise StaleArtifactError(f"malformed authoring evidence at {path}: {exc}") from exc


# --- the S4.6 authored-map gate (§1.4.1a, Audit 15) --------------------------------------------- #


def assert_evidence_gate(evidence: AuthoringEvidence, projection: ProjectionMap) -> None:
    """Hold a loaded sidecar against the live projection — fail loud listing **every** finding.

    The correspondence is one-to-one both ways: every ``minted_by:human`` container must have
    exactly one **non-stale** entry, and every entry must bind exactly a human-minted container —
    so missing evidence, an orphaned entry (binds no node), a misbound entry (binds a machine
    leaf), and a stale entry (the recomputed :func:`node_structure_digest` differs from the pinned
    one) each red **by name**, collected into one :class:`~engine.errors.StaleArtifactError`.
    ``authored_at_revision`` is never consulted (§1.4.1b). Returns ``None`` when the pair holds.

    Callers hold a :class:`~engine.structure.structure_map.StructureMap`; pass its ``projection``.
    """
    problems: list[str] = []
    human_containers = {
        node.node_id
        for node in projection.nodes
        if isinstance(node, ContainerNode) and node.minted_by == MINTED_BY_HUMAN
    }
    for node_id in sorted(human_containers - evidence.by_node.keys()):
        problems.append(f"human-minted container {node_id!r} has no evidence entry")
    for entry in evidence.entries:
        node = projection.by_id.get(entry.node_id)
        if node is None:
            problems.append(f"evidence entry {entry.node_id!r} binds no node in the map (orphaned)")
            continue
        if entry.node_id not in human_containers:
            problems.append(
                f"evidence entry {entry.node_id!r} binds a node that is not a human-minted "
                f"container — evidence documents hand-authored containers only"
            )
            continue
        live = node_structure_digest(node)
        if entry.node_digest != live:
            problems.append(
                f"evidence for {entry.node_id!r} is STALE: pinned digest {entry.node_digest} != "
                f"live {live} — the bound node's structure changed; re-verify and re-stamp"
            )
    if problems:
        raise StaleArtifactError(
            "authoring-evidence gate failed — the sidecar does not hold against the live map:\n  "
            + "\n  ".join(problems)
        )
