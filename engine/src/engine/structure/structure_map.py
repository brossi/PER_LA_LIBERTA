"""S4.4 — the persisted ``structure_map.json``: schema binding, two-tier loader, lineage manifest,
born-gate, and the regen-guarded writer (s4_plan D-S4-E/D-S4-G/D-S4-I, §4).

This module is where the in-memory L2 models (``projection.py``, ``handles.py``) become a
validated, versioned on-disk artifact. It is deliberately **compositional**: every semantic code it
surfaces is produced by exactly one per-module validator (I5 single-sourcing, §4.2 producer note) —
nothing here re-implements a check that already has a producer. What is native here:

- **Tier-1** — JSON-Schema shape validation against ``schema/structure_map.schema.json`` (field
  presence/types, container-xor-leaf ``oneOf`` [inv 2], no ``node_class`` enum [inv 22], the
  ``rebind_anchors`` region-only shape [inv 24], manifest structural completeness [inv 11]). A
  Tier-1 or JSON-parse failure is a malformed persisted artifact →
  :class:`~engine.errors.StaleArtifactError` (the atom-store load-boundary precedent), never an
  ``EC`` code.
- **Tier-2a preconditions (short-circuit, §4.1)** — ``DUPLICATE_NODE_ID`` fires at
  :class:`~engine.structure.projection.ProjectionMap` construction inside
  :func:`structure_map_from_json`; ``ROOT_ID_DANGLING`` fires first in
  :func:`validate_structure_map`. Each raises alone, before any collect-all check runs — the only
  reason no second root/identity code can co-fire (P3A-3/P3A-5).
- **Tier-2b (collect-all)** — :func:`validate_structure_map` runs every per-module validator
  (``validate_projection`` / ``validate_reference_integrity`` / ``validate_atom_existence`` /
  ``validate_handle_policies`` / ``validate_block_vocabulary`` / ``validate_aliases``), merges their
  findings, and raises **once** with the whole collected payload.
- **The loader contract (X15)** — :func:`load_structure_map` runs parse → Tier-1 → Tier-2, in that
  order, and is **born-agnostic**: it never reads the schema birth status, so the S4.1–S4.4
  invariant red-tests route through it on a still-``provisional`` schema (§4.2) and S4.5's
  differ-fixture can validate *before* the flip. The born check is the separate
  :func:`assert_schema_born` (§1.2.3) — the only producer of ``SCHEMA_NOT_BORN`` — which a
  DONE/GATE harness or S8.1 calls explicitly. There is **no** override for it: a provisional
  schema simply cannot pass the gate.
- **The manifest assembly** (:func:`build_manifest`, §3.E) — per-layer versions + stale classes
  (relation-store pinned ``present: false`` until S7.1c), the **two split canonical hashes**
  (content vs geometry, so a geometry re-match never masquerades as a content change, R2-10), the
  witness ``source_hash`` anchors, per-stream envelope hashes, and the
  :class:`~engine.structure.lineage.ResourceLineage` fragment verbatim. Every hash is
  ``lineage._sha256_bytes(lineage._canonical(obj).encode("utf-8"))`` over an **explicit field
  list** in canonical-stream order (D-S4-I) — an implementer may not substitute a different
  producer or ordering.
- **The regen-guarded writer** (:func:`write_structure_map`, §3.E.8/inv 21) — ``structure_map.json``
  is irreproducible committed data; overwriting a present map without the explicit licensed path
  (name the exact stored ``map_revision`` you supersede + snapshot-before-overwrite + the new
  revision exactly one higher) raises ``MAP_OVERWRITE_BLOCKED``. **No env-var escape exists.**

The ``decision`` field (§3.J) is **reserved present-but-inert**: the schema admits it, the
conforming fixture carries it, and *no code in this package reads it* (inv 25 pins that with an AST
no-reader scan). That is why :class:`StructureMap` retains the parsed document verbatim (``doc``)
and :func:`render_structure_map` re-renders from it: unmodeled reserved fields round-trip through
load→dump byte-stably without any code naming them.

Neutral core (inv 15): no language/book/typeface literal — the S0.2 scan globs this module and the
schema JSON beside it.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import jsonschema

from engine.errors import MissingInputError, StaleArtifactError
from engine.paths import BookWorkspace
from engine.structure.artifacts import (
    ATOM_STORE_SCHEMA_VERSION,
    ATOM_STORE_STALE_CLASS,
    RELATION_STORE_SCHEMA_VERSION,
    RELATION_STORE_STALE_CLASS,
    SCHEMA_STATUS_BORN,
    STRUCTURE_MAP_SCHEMA_STATUS,
    STRUCTURE_MAP_SCHEMA_VERSION,
    STRUCTURE_MAP_STALE_CLASS,
    structure_map_path,
    structure_map_snapshot_path,
)
from engine.structure.atom_store import CANONICAL, WITNESS, AtomStream
from engine.structure.atom_store import to_json as stream_envelope_json
from engine.structure.atoms import PROCESSING_SCOPE_INCLUDED
from engine.structure.errors import EC, StructureValidationError
from engine.structure.handles import (
    HANDLE_RENDERER_VERSION,
    Alias,
    NodeClassSpec,
    validate_aliases,
    validate_block_vocabulary,
    validate_handle_policies,
)
from engine.structure.lineage import ResourceLineage, _canonical, _sha256_bytes
from engine.structure.projection import (
    ContainerNode,
    LeafNode,
    Node,
    FurnitureAtom,
    ProjectionMap,
    validate_atom_existence,
    validate_projection,
    validate_reference_integrity,
)
from engine.util.jsonio import atomic_write_text, read_json

#: The packaged Tier-1 schema (D-S4-G ruling O2: ``structure/schema/``).
SCHEMA_PATH = Path(__file__).resolve().parent / "schema" / "structure_map.schema.json"


def load_schema() -> dict:
    """The parsed Tier-1 JSON-Schema, read fresh from :data:`SCHEMA_PATH` (a fresh dict per call, so
    no caller can mutate a shared cache)."""
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def schema_version_const(schema: Mapping | None = None) -> int:
    """The ``schema_version`` ``const`` the Tier-1 schema pins (D-S4-G; §3.E.5).

    Half of the two-assertion binding that keeps the schema literal and the Python constant from
    drifting (the ``manifest.schema.json`` anti-pattern, §2.3): inv 10 asserts
    ``schema_version_const() == STRUCTURE_MAP_SCHEMA_VERSION`` *and* that the version-derived
    conforming fixture validates. Fails loud (``KeyError``/``ValueError``) on a schema whose const
    is missing or not a genuine int — a malformed schema file is a bug, not a fallback case.
    """
    if schema is None:
        schema = load_schema()
    const = schema["properties"]["schema_version"]["const"]
    if not isinstance(const, int) or isinstance(const, bool):
        raise ValueError(f"schema_version const must be an int, got {const!r}")
    return const


def assert_schema_born() -> None:
    """The D18 born-gate (§1.2.3) — the ONLY producer of ``SCHEMA_NOT_BORN``.

    Reads ``STRUCTURE_MAP_SCHEMA_STATUS[schema_version_const()]`` (P3A-6): raises unless the current
    schema version is ``born``. A **missing** key is fail-safe — treated as provisional and raised
    (P3B-11). Deliberately separate from the born-agnostic :func:`load_structure_map` (X1: gating the
    loader would deadlock the S4.1–S4.4 red-tests that must route through it on a provisional
    schema). ``SCHEMA_NOT_BORN`` names S4.5 (the differ-fixture birth gate) as the repair — distinct
    from ordinary M3 version staleness. There is no override path: a provisional schema cannot pass.
    """
    version = schema_version_const()
    status = STRUCTURE_MAP_SCHEMA_STATUS.get(version)
    if status != SCHEMA_STATUS_BORN:
        raise StructureValidationError(
            [
                (
                    EC.SCHEMA_NOT_BORN,
                    f"structure-map schema version {version} is "
                    f"{status if status is not None else 'unregistered (fail-safe: provisional)'} — "
                    f"not born. The repair is the S4.5 differ-fixture birth gate (D18), not a version "
                    f"migration.",
                )
            ]
        )


# --- typed model + document builder --------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class StructureMap:
    """A loaded structure map: the typed L2 surface plus the parsed document it came from.

    ``doc`` is the Tier-1-valid parsed JSON, retained **verbatim** (treat as read-only): it is what
    :func:`render_structure_map` re-renders, so unmodeled reserved fields (§3.J's inert enum among
    them) survive load→dump byte-stably without any code reading them (inv 25). The typed fields are
    projections *of* ``doc`` for the validators and downstream consumers.
    """

    doc: Mapping
    projection: ProjectionMap
    block_vocabulary: tuple[NodeClassSpec, ...]
    handle_policies: Mapping[str, str]
    aliases: tuple[Alias, ...]
    map_revision: int


def _node_from_json(data: Mapping) -> Node:
    """One Tier-1-valid node object → its dataclass variant (container-xor-leaf is dispatched on the
    ``children`` slot, which Tier-1 guarantees is present exactly on containers)."""
    common = dict(
        node_id=data["node_id"],
        node_class=data["node_class"],
        minted_by=data["minted_by"],
        designation=data.get("designation", ""),
        title=data.get("title", ""),
        handle_policy=data.get("handle_policy", ""),
    )
    if "children" in data:
        return ContainerNode(
            children=tuple(data["children"]),
            heading_atoms=tuple(data.get("heading_atoms", ())),
            signature_atoms=tuple(data.get("signature_atoms", ())),
            **common,
        )
    return LeafNode(body_atoms=tuple(data["body_atoms"]), **common)


def _strict_int(value: object, where: str) -> int:
    """A genuine JSON integer for a contract-int field. JSON Schema's ``"integer"`` admits any
    zero-fraction number (``2.0``), and Python's ``bool`` is an ``int`` subclass — either riding
    into a revision/version field would corrupt CAS arithmetic or round-trip as a float, so both
    are rejected here (the audit's numeric-boundary finding; the ``Alias.__post_init__`` idiom)."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{where} must be a JSON integer (not bool/float), got {value!r}")
    return value


def structure_map_from_json(doc: Mapping) -> StructureMap:
    """Build the typed :class:`StructureMap` from a **Tier-1-valid** parsed document.

    Presumes shape (the loader runs Tier-1 first — a direct call with an arbitrary dict is a
    programming error and may raise bare ``KeyError``/``TypeError``); the loader wraps any
    model-level ``ValueError``/``TypeError`` (a zero-fraction float in an int field, a malformed
    alias) as :class:`~engine.errors.StaleArtifactError` — Tier-1's numeric semantics cannot
    guarantee genuine ints, so the int contract is enforced at this layer. The Tier-2a
    ``DUPLICATE_NODE_ID`` precondition fires **here**, at :class:`ProjectionMap` construction —
    short-circuiting before any collect-all check can run (§4.1).
    """
    _strict_int(doc["schema_version"], "schema_version")
    projection = ProjectionMap(
        root_id=doc["root_id"],
        nodes=tuple(_node_from_json(n) for n in doc["nodes"]),
        furniture_atoms=tuple(
            FurnitureAtom(atom_id=f["atom_id"], capture_role=f["capture_role"])
            for f in doc["furniture_atoms"]
        ),
    )
    return StructureMap(
        doc=doc,
        projection=projection,
        block_vocabulary=tuple(
            NodeClassSpec(name=v["name"], kind=v["kind"], status=v["status"])
            for v in doc["block_vocabulary"]
        ),
        handle_policies=dict(doc["handle_policies"]),
        aliases=tuple(
            Alias(
                handle_type=a["handle_type"],
                value=a["value"],
                scope=a["scope"],
                locale_or_witness=a["locale_or_witness"],
                target_node_id=a["target_node_id"],
                valid_from=a["valid_from"],
                valid_to=a["valid_to"],
                status=a["status"],
            )
            for a in doc["aliases"]
        ),
        map_revision=_strict_int(doc["map_revision"], "map_revision"),
    )


# --- two-tier validation ---------------------------------------------------------------------------- #


def _tier1_validate(doc: object) -> None:
    """Tier-1: JSON-Schema shape validation. A failure is a malformed persisted artifact →
    :class:`~engine.errors.StaleArtifactError` naming the offending location — never an ``EC`` code
    (the closed set is semantic; shape rejection is the load boundary's)."""
    try:
        jsonschema.validate(doc, load_schema())
    except jsonschema.ValidationError as exc:
        location = "/".join(str(p) for p in exc.absolute_path) or "<root>"
        raise StaleArtifactError(
            f"structure map failed Tier-1 shape validation at {location}: {exc.message}"
        ) from exc


def validate_structure_map(smap: StructureMap, atom_store) -> None:
    """The public Tier-2 semantic validator (§4.1): Tier-2a preconditions short-circuit, then every
    Tier-2b per-module validator runs and the findings are **collected into one payload**.

    ``atom_store`` is the §4-header thin reader: ``included_atom_ids()`` (the included
    canonical-stream universe, in canonical order), ``scope_of(atom_id)`` and ``contains(atom_id)``
    (over the **full** canonical+witness population — furniture entries carry witness ids, P3B-1).
    :class:`StreamAtomReader` adapts a mapping of real :class:`~engine.structure.atom_store.AtomStream`\\ s.

    Raises :class:`~engine.structure.errors.StructureValidationError`; returns ``None`` when clean.
    (The other Tier-2a precondition, ``DUPLICATE_NODE_ID``, cannot reach this function: it fires at
    :func:`structure_map_from_json` construction.)
    """
    projection = smap.projection
    if projection.by_id.get(projection.root_id) is None:
        # Tier-2a: nothing downstream can anchor on a missing root — including the empty map (zero
        # nodes), where root_id necessarily resolves against nothing (P3A-2). Short-circuit: the Z /
        # traversal / collect-all checks below never run, so no second root code co-fires (P3A-3).
        raise StructureValidationError(
            [
                (
                    EC.ROOT_ID_DANGLING,
                    f"root_id {projection.root_id!r} names no node "
                    f"({len(projection.nodes)} node(s) in the map)",
                )
            ]
        )
    findings: list[tuple[EC, str]] = []
    checks = (
        lambda: validate_projection(projection, atom_store),
        lambda: validate_reference_integrity(projection),
        lambda: validate_atom_existence(projection, atom_store),
        lambda: validate_handle_policies(projection, smap.block_vocabulary, smap.handle_policies),
        lambda: validate_block_vocabulary(smap.block_vocabulary, projection),
        lambda: validate_aliases(projection, smap.aliases, smap.map_revision),
    )
    for check in checks:
        try:
            check()
        except StructureValidationError as err:
            findings.extend(err.findings)
    if findings:
        raise StructureValidationError(findings)


def load_structure_map(path: Path, atom_store) -> StructureMap:
    """Read + validate a persisted structure map: **parse JSON → Tier-1 → Tier-2**, in that order,
    raising on the first tier that fails (X15). Returns the typed :class:`StructureMap`.

    **Born-agnostic** (§1.2.3): this loader never reads the schema birth status — the born check is
    :func:`assert_schema_born`, called separately by DONE/GATE harness paths. The failure contract
    is **total** (the ``atom_store.from_json`` precedent): a missing file is
    :class:`~engine.errors.MissingInputError`; non-UTF-8 / non-JSON / non-finite-float (``NaN`` /
    ``Infinity`` — legal to ``json.loads`` but not RFC 8259, and fatal to the ``allow_nan=False``
    re-render inv 20 depends on) / Tier-1-malformed content — and any model-level
    ``ValueError``/``TypeError`` out of the typed build, e.g. a zero-fraction float in an int field
    that Tier-1's ``"integer"`` semantics admit — is :class:`~engine.errors.StaleArtifactError`; a
    semantic violation is :class:`~engine.structure.errors.StructureValidationError` carrying the
    collected ``EC`` payload. Nothing else escapes.
    """
    path = Path(path)
    if not path.is_file():
        raise MissingInputError(f"structure map not found at {path}")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_non_finite)
    except UnicodeDecodeError as exc:
        raise StaleArtifactError(f"structure map at {path} is not valid UTF-8: {exc}") from exc
    except ValueError as exc:  # json.JSONDecodeError subclasses ValueError; also _reject_non_finite
        raise StaleArtifactError(f"structure map at {path} is not valid JSON: {exc}") from exc
    _tier1_validate(doc)
    try:
        smap = structure_map_from_json(doc)
    except StructureValidationError:
        raise  # Tier-2a (DUPLICATE_NODE_ID) — a semantic finding, not a malformed artifact
    except (ValueError, TypeError) as exc:
        raise StaleArtifactError(f"malformed structure map at {path}: {exc}") from exc
    validate_structure_map(smap, atom_store)
    return smap


def _reject_non_finite(token: str) -> float:
    """``json.loads`` hook: the ``NaN``/``Infinity``/``-Infinity`` tokens are rejected outright — a
    map carrying one would load "clean" and then crash the ``allow_nan=False`` renderer, breaking
    the dump→load→dump property on a Tier-1-"valid" document (audit finding)."""
    raise ValueError(f"non-finite float token {token!r} is not valid structure-map JSON")


# --- the §4-header atom_store adapter --------------------------------------------------------------- #


class StreamAtomReader:
    """The thin atom-store reader S4 takes (§4 header, X4/D-2): adapts a mapping of persisted/in-memory
    :class:`~engine.structure.atom_store.AtomStream`\\ s to the exact three capabilities the validators
    need. There is deliberately no aggregate ``AtomStore`` class yet — this adapter *is* the thin
    reader, and any duck-typed object with the same three methods is equally acceptable.

    - ``included_atom_ids()`` — the **canonical-stream** included universe, in canonical order (the
      coverage universe, inv 1b, and the inv 27 ordering key). Canonical-only by design (P3B-1).
    - ``contains(atom_id)`` / ``scope_of(atom_id)`` — over the **union** of every stream's atoms,
      canonical *and* witness: excluded furniture lives only in witness streams, so the canonical
      stream alone could not resolve a ``furniture_atoms`` entry (inv 17).
    """

    def __init__(self, streams: Mapping[str, AtomStream], canonical_stream_id: str = "canonical") -> None:
        canonical = streams.get(canonical_stream_id)
        if canonical is None or canonical.kind != CANONICAL:
            raise ValueError(
                f"StreamAtomReader: canonical_stream_id {canonical_stream_id!r} does not name a "
                f"canonical-kind stream (have {sorted(streams)})"
            )
        self._included = tuple(
            a.atom_id for a in canonical.atoms if a.processing_scope == PROCESSING_SCOPE_INCLUDED
        )
        # The canonical stream's scopes win unconditionally on an id collision (audit hardening: a
        # witness stream sorting before "canonical" must not shadow a canonical atom's scope into a
        # spurious OWNED_EXCLUDED_ATOM); the remaining witnesses merge deterministically by sorted id.
        self._scope: dict[str, str] = {a.atom_id: a.processing_scope for a in canonical.atoms}
        for stream_id in sorted(streams):
            if stream_id == canonical_stream_id:
                continue
            for atom in streams[stream_id].atoms:
                self._scope.setdefault(atom.atom_id, atom.processing_scope)

    def included_atom_ids(self) -> tuple[str, ...]:
        return self._included

    def contains(self, atom_id: str) -> bool:
        return atom_id in self._scope

    def scope_of(self, atom_id: str) -> str | None:
        return self._scope.get(atom_id)


# --- lineage manifest assembly (§3.E) ---------------------------------------------------------------- #


def _hash_canonical(obj: object) -> str:
    """THE hash producer (D-S4-I, M5): ``lineage._sha256_bytes(lineage._canonical(obj).encode("utf-8"))``.
    Every S4 hash routes through this one composition — substituting a different digest, serializer,
    or encoding is exactly the mutation inv 20 exists to catch."""
    return _sha256_bytes(_canonical(obj).encode("utf-8"))


def build_manifest(
    *,
    streams: Mapping[str, AtomStream],
    canonical_stream_id: str,
    resource_lineage: ResourceLineage,
    profile_version: str,
    recognizer_version: str,
) -> dict:
    """Assemble the §3.E lineage manifest from the live streams + resource lineage.

    S4 **stamps** this basis; the stored-vs-live staleness comparison is S8.1's (§3.E.9 — there is no
    separate structure-map self-hash). Hash field lists are explicit (D-S4-I):

    - ``canonical_content_hash`` — per canonical atom, in canonical-stream (stored) order:
      ``{atom_id, text, raw_span, raw_source_hash}``.
    - ``canonical_geometry_hash`` — per canonical atom, same order, the geom-region fields:
      ``{atom_id, present, page, bbox}``. Match-provenance (engine/method/confidence) is deliberately
      outside the hash: the *region* is what re-binding keys on, and a provenance-only re-stamp must
      not read as a geometry change.
    - ``atom_streams[*].hash`` — the canonical-JSON hash of each stream's persisted envelope
      (``atom_store.to_json``), streams sorted by id.

    ``handle_renderer_version`` is stamped from the live constant (§3.D.6); the relation-store layer
    is pinned ``present: false`` until S7.1c (O1). Raises ``ValueError`` if ``canonical_stream_id``
    does not name a canonical-kind stream (a caller programming error, not map data).
    """
    canonical = streams.get(canonical_stream_id)
    if canonical is None or canonical.kind != CANONICAL:
        raise ValueError(
            f"build_manifest: canonical_stream_id {canonical_stream_id!r} does not name a "
            f"canonical-kind stream (have {sorted(streams)})"
        )
    content_payload = [
        {
            "atom_id": a.atom_id,
            "text": a.text,
            "raw_span": list(a.raw_span),
            "raw_source_hash": a.raw_source_hash,
        }
        for a in canonical.atoms
    ]
    geometry_payload = [
        {
            "atom_id": a.atom_id,
            "present": a.geom.present,
            "page": a.geom.page,
            "bbox": list(a.geom.bbox) if a.geom.bbox is not None else None,
        }
        for a in canonical.atoms
    ]
    return {
        "source_artifacts": [
            {"witness": stream_id, "hash": stream.source_hash}
            for stream_id, stream in sorted(streams.items())
            if stream.kind == WITNESS
        ],
        "atom_streams": [
            {"id": stream_id, "hash": _hash_canonical(stream_envelope_json(stream))}
            for stream_id, stream in sorted(streams.items())
        ],
        "canonical_stream_id": canonical_stream_id,
        "canonical_content_hash": _hash_canonical(content_payload),
        "canonical_geometry_hash": _hash_canonical(geometry_payload),
        "layers": {
            "atom_store": {
                "schema_version": ATOM_STORE_SCHEMA_VERSION,
                "stale_class": ATOM_STORE_STALE_CLASS,
                "present": True,
            },
            "structure_map": {
                "schema_version": STRUCTURE_MAP_SCHEMA_VERSION,
                "stale_class": STRUCTURE_MAP_STALE_CLASS,
                "present": True,
            },
            "relation_store": {
                "schema_version": RELATION_STORE_SCHEMA_VERSION,
                "stale_class": RELATION_STORE_STALE_CLASS,
                "present": False,  # pinned until S7.1c (O1) — the layer identity exists, the artifact does not
            },
        },
        "resource_lineage": resource_lineage.to_json(),
        "profile_version": profile_version,
        "recognizer_version": recognizer_version,
        "handle_renderer_version": HANDLE_RENDERER_VERSION,
    }


# --- render + regen-guarded writer (§3.E.8) ----------------------------------------------------------- #


def render_structure_map(doc: Mapping) -> str:
    """The exact on-disk byte form of a structure-map document: diffable ``indent=2`` JSON (D-S4-I —
    only the *hashed sub-objects* use canonical byte-form, the human-authored file stays readable),
    key order as assembled/loaded, trailing newline. One renderer shared by the writer, the fixture
    generator, and the inv 20 dump→load→dump byte-identity proof."""
    return json.dumps(doc, indent=2, ensure_ascii=False, allow_nan=False) + "\n"


def write_structure_map(
    workspace: BookWorkspace, doc: Mapping, *, supersede_revision: int | None = None
) -> Path:
    """The production writer, **regen-guarded** (§3.E.8, inv 21): ``structure_map.json`` is
    irreproducible hand-authored data, so overwriting a present map without the explicit licensed
    path raises ``MAP_OVERWRITE_BLOCKED``. There is **no env-var escape**.

    The licensed overwrite is deliberately compare-and-swap shaped — all three §3.E.8 elements:

    1. **explicit target** — ``supersede_revision`` must equal the *stored* map's ``map_revision``
       (you must name exactly what you believe you are replacing; a stale belief is blocked);
    2. **snapshot-before-overwrite** — the superseded bytes are copied to
       ``structure_map.snapshots/structure_map.rev{N}.json`` first, and an already-present snapshot
       for that revision is refused (history is never clobbered);
    3. **a new revision entry** — the new document's ``map_revision`` must be exactly
       ``supersede_revision + 1`` (one authoring change, one revision tick, §3.D.5).

    The document is Tier-1-validated **and pre-rendered** before anything touches disk (a writer
    that can persist a shape-invalid or non-finite-float map would poison every later load; and
    rendering *after* the snapshot write left a data-triggered partial state — snapshot present,
    live map stale, retry blocked by the clobber guard — the audit's writer-wedge finding). All
    writes are atomic per file (I8). **Residual risk, disclosed:** the snapshot+live pair is not
    one transaction — a process kill between the two atomic writes leaves the snapshot without the
    superseded live map; recovery machinery is S8.1's (which owns snapshot-guarded migration), not
    built here. Fixture/test generation under ``tests/fixtures/`` writes freely — this guard is
    the *production* path.
    """
    if supersede_revision is not None and (
        isinstance(supersede_revision, bool) or not isinstance(supersede_revision, int)
    ):
        # bool is an int subclass: supersede_revision=True would silently license replacing rev 1.
        raise ValueError(
            f"supersede_revision must be an int map_revision (not bool/float), got {supersede_revision!r}"
        )
    _tier1_validate(doc)
    try:
        _strict_int(doc["map_revision"], "map_revision")  # Tier-1 "integer" admits 2.0; CAS needs an int
    except ValueError as exc:
        raise StaleArtifactError(f"structure map document is malformed: {exc}") from exc
    try:
        rendered = render_structure_map(doc)
    except ValueError as exc:
        raise StaleArtifactError(
            f"structure map document is not renderable ({exc}) — refusing to persist what no "
            f"subsequent load could read"
        ) from exc
    path = structure_map_path(workspace)
    if supersede_revision is not None and not path.exists():
        raise StructureValidationError(
            [
                (
                    EC.MAP_OVERWRITE_BLOCKED,
                    f"supersede_revision={supersede_revision} names a stored map, but no structure "
                    f"map exists at {path} — a stale overwrite belief is blocked, never a silent "
                    f"fresh write",
                )
            ]
        )
    if path.exists():
        if supersede_revision is None:
            raise StructureValidationError(
                [
                    (
                        EC.MAP_OVERWRITE_BLOCKED,
                        f"a structure map already exists at {path} — it is hand-authored, "
                        f"irreproducible data. To supersede it, pass supersede_revision=<stored "
                        f"map_revision>; the old map is snapshotted first (s4_plan §3.E.8).",
                    )
                ]
            )
        try:
            existing = read_json(path)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise StaleArtifactError(
                f"existing structure map at {path} is not valid JSON/UTF-8: {exc} — refusing to "
                f"overwrite what cannot be snapshotted meaningfully"
            ) from exc
        stored_revision = existing.get("map_revision")
        if stored_revision != supersede_revision:
            raise StructureValidationError(
                [
                    (
                        EC.MAP_OVERWRITE_BLOCKED,
                        f"supersede_revision {supersede_revision} does not match the stored "
                        f"map_revision {stored_revision} — the overwrite license must name exactly "
                        f"the revision it replaces",
                    )
                ]
            )
        if doc["map_revision"] != supersede_revision + 1:
            raise StructureValidationError(
                [
                    (
                        EC.MAP_OVERWRITE_BLOCKED,
                        f"new map_revision {doc['map_revision']} must be exactly "
                        f"{supersede_revision + 1} (stored + 1): one authoring change, one revision",
                    )
                ]
            )
        snapshot = structure_map_snapshot_path(workspace, stored_revision)
        if snapshot.exists():
            raise StructureValidationError(
                [
                    (
                        EC.MAP_OVERWRITE_BLOCKED,
                        f"snapshot {snapshot} already exists — a superseded revision's snapshot is "
                        f"immutable history and is never clobbered",
                    )
                ]
            )
        if snapshot.parent.exists() and not snapshot.parent.is_dir():
            raise StaleArtifactError(
                f"snapshot location {snapshot.parent} exists but is not a directory — the "
                f"workspace is corrupt; refusing to overwrite"
            )
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(snapshot, path.read_text(encoding="utf-8"))
    path.parent.mkdir(parents=True, exist_ok=True)  # a fresh checkout may not be .ensure()d yet
    atomic_write_text(path, rendered)
    return path
