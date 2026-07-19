"""S4.6d evidence-bound structure-review packet and guarded item identity (#93)."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Mapping

import jsonschema

from engine.errors import InvalidInvocationError, MissingInputError, StaleArtifactError
from engine.structure.artifacts import AUTHORING_EVIDENCE_SCHEMA_VERSION
from engine.structure.authoring import (
    authoring_status_for_context,
    stamp_evidence_for_context,
)
from engine.structure.authoring_context import AuthoringContext, load_authoring_context
from engine.structure.authoring_inspection import (
    StructureInspection,
    normalize_review_label,
)
from engine.structure.review_flags import load_structure_review_flags, live_flag
from engine.structure.structural_contents import load_structural_contents_report

STRUCTURE_REVIEW_SCHEMA_VERSION = 1
STRUCTURE_REVIEW_STALE_CLASS = "structure-review-packet"
STRUCTURE_REVIEW_PACKET_POLICY = "structure-review-packet-v1"
STRUCTURE_REVIEW_RENDERER = "structure-review-json-v1"
STRUCTURE_REVIEW_ITEM_POLICY = "structure-review-item-v1"
OBSERVATION_ASSOCIATION_POLICY = "structure-observation-association-v1"
VISUAL_SOURCE_POLICY = "structure-review-visual-sources-v1"

OBSERVATIONS_FILENAME = "structure_observations.json"
REVIEW_FLAGS_FILENAME = "structure_review_flags.json"
VISUAL_SOURCES_FILENAME = "structure_review_sources.json"
_SAFE_SOURCE_ID = re.compile(r"[A-Za-z0-9_.-]+")

SCHEMA_PATH = (
    Path(__file__).resolve().parent / "schema" / "structure_review_packet.schema.json"
)


def load_structure_review_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _packet_validator() -> jsonschema.Draft202012Validator:
    schema = load_structure_review_schema()
    jsonschema.Draft202012Validator.check_schema(schema)
    return jsonschema.Draft202012Validator(schema)


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _file_identity(path: Path) -> tuple[str, int]:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise MissingInputError(
            f"review packet input is unreadable at {path}: {exc}"
        ) from exc
    return hashlib.sha256(data).hexdigest(), len(data)


def _relative_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise StaleArtifactError(
            f"review packet artifact {path} escapes registered root {root}"
        ) from exc


def _contained_asset(asset_root: Path, relative: str) -> Path:
    if not isinstance(relative, str):
        raise StaleArtifactError("visual source path must be text")
    pure = PurePosixPath(relative)
    if (
        pure.is_absolute()
        or not pure.parts
        or any(part in ("", ".", "..") for part in pure.parts)
    ):
        raise StaleArtifactError(
            f"visual source path {relative!r} is not a contained relative path"
        )
    root = Path(asset_root).resolve()
    path = root.joinpath(*pure.parts).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise StaleArtifactError(
            f"visual source path {relative!r} escapes asset root {root}"
        ) from exc
    if not path.is_file():
        raise MissingInputError(f"registered visual source not found at {path}")
    return path


def _load_visual_sources(
    book_dir: Path, asset_root: Path
) -> tuple[dict, tuple[dict, ...], dict[str, dict[str, list[list[int]]]]]:
    path = book_dir / VISUAL_SOURCES_FILENAME
    if not path.is_file():
        return (
            {
                "state": "unavailable",
                "reason": f"no registered {VISUAL_SOURCES_FILENAME}",
                "sources": [],
            },
            (),
            {},
        )
    try:
        data = path.read_bytes()
        doc = json.loads(
            data, parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token))
        )
    except (OSError, UnicodeError, ValueError, RecursionError) as exc:
        raise StaleArtifactError(
            f"visual source registration at {path} is unreadable"
        ) from exc
    required = {"schema_version", "book", "policy", "sources"}
    if not isinstance(doc, dict) or set(doc) != required:
        raise StaleArtifactError(
            f"visual source registration keys must be exactly {sorted(required)}"
        )
    if doc["schema_version"] != 1 or type(doc["schema_version"]) is not int:
        raise StaleArtifactError(
            "visual source registration schema_version must be integer 1"
        )
    if doc["book"] != book_dir.name:
        raise StaleArtifactError(
            f"visual source registration names book {doc['book']!r}, not {book_dir.name!r}"
        )
    if doc["policy"] != VISUAL_SOURCE_POLICY:
        raise StaleArtifactError(
            f"visual source registration policy {doc['policy']!r} is not {VISUAL_SOURCE_POLICY!r}"
        )
    if not isinstance(doc["sources"], list) or not doc["sources"]:
        raise StaleArtifactError(
            "visual source registration must contain at least one source"
        )
    fields = {
        "source_id",
        "witness_id",
        "kind",
        "media_type",
        "path",
        "sha256",
        "bytes",
        "page_numbering",
    }
    sources: list[dict] = []
    page_maps: dict[str, dict[str, list[list[int]]]] = {}
    seen: set[str] = set()
    for index, source in enumerate(doc["sources"]):
        if not isinstance(source, dict) or set(source) not in (
            fields,
            fields | {"node_pages"},
        ):
            raise StaleArtifactError(
                f"visual source {index} keys must be {sorted(fields)} plus optional node_pages"
            )
        source_id = source["source_id"]
        if (
            not isinstance(source_id, str)
            or _SAFE_SOURCE_ID.fullmatch(source_id) is None
            or source_id in seen
        ):
            raise StaleArtifactError(
                f"visual source {index} has invalid/duplicate source_id"
            )
        seen.add(source_id)
        for field in fields - {"source_id", "bytes"}:
            if not isinstance(source[field], str) or not source[field].strip():
                raise StaleArtifactError(
                    f"visual source {source_id!r} field {field!r} must be non-blank text"
                )
        if len(source["sha256"]) != 64 or any(
            character not in "0123456789abcdef" for character in source["sha256"]
        ):
            raise StaleArtifactError(
                f"visual source {source_id!r} sha256 must be lowercase SHA-256"
            )
        if source["kind"] not in {"pdf", "image", "raster-set"}:
            raise StaleArtifactError(f"visual source {source_id!r} has unknown kind")
        if type(source["bytes"]) is not int or source["bytes"] < 0:
            raise StaleArtifactError(
                f"visual source {source_id!r} bytes must be non-negative int"
            )
        local = _contained_asset(asset_root, source["path"])
        digest, size = _file_identity(local)
        if digest != source["sha256"] or size != source["bytes"]:
            raise StaleArtifactError(
                f"visual source {source_id!r} bytes do not match its registered lock"
            )
        node_pages = source.get("node_pages", {})
        if not isinstance(node_pages, dict):
            raise StaleArtifactError(
                f"visual source {source_id!r} node_pages must be an object"
            )
        normalized_pages: dict[str, list[list[int]]] = {}
        for node_id, ranges in node_pages.items():
            if (
                not isinstance(node_id, str)
                or not node_id
                or not isinstance(ranges, list)
                or not ranges
            ):
                raise StaleArtifactError(
                    f"visual source {source_id!r} has malformed node_pages"
                )
            normalized: list[list[int]] = []
            previous_end = 0
            for page_range in ranges:
                if (
                    not isinstance(page_range, list)
                    or len(page_range) != 2
                    or any(type(page) is not int or page < 1 for page in page_range)
                    or page_range[1] < page_range[0]
                ):
                    raise StaleArtifactError(
                        f"visual source {source_id!r} node {node_id!r} has malformed page range"
                    )
                if page_range[0] <= previous_end:
                    raise StaleArtifactError(
                        f"visual source {source_id!r} node {node_id!r} page ranges overlap or are unordered"
                    )
                normalized.append(list(page_range))
                previous_end = page_range[1]
            normalized_pages[node_id] = normalized
        base = {field: source[field] for field in fields}
        sources.append(base)
        page_maps[source_id] = normalized_pages
    config_digest = hashlib.sha256(data).hexdigest()
    adjunct = {
        "state": "available",
        "schema_version": 1,
        "policy": VISUAL_SOURCE_POLICY,
        "sha256": config_digest,
        "bytes": len(data),
        "path": _relative_path(path, book_dir),
        "sources": sources,
    }
    return adjunct, tuple(sources), page_maps


def _validate_visual_page_nodes(
    page_maps: Mapping[str, Mapping[str, list[list[int]]]],
    human_node_ids: tuple[str, ...],
) -> None:
    valid = set(human_node_ids)
    for source_id, node_pages in page_maps.items():
        unknown = sorted(set(node_pages) - valid)
        if unknown:
            raise StaleArtifactError(
                f"visual source {source_id!r} maps unknown/non-human nodes: {unknown}"
            )


def _observation_regions(book_dir: Path, book: str) -> tuple[dict, dict | None]:
    path = book_dir / "work" / OBSERVATIONS_FILENAME
    if not path.is_file():
        return {
            "state": "unavailable",
            "reason": f"no current work/{OBSERVATIONS_FILENAME}",
        }, None
    report = load_structural_contents_report(path, expected_book=book)
    digest, size = _file_identity(path)
    return (
        {
            "state": "available",
            "schema_version": report["schema_version"],
            "policy": report["observer_policy"],
            "sha256": digest,
            "bytes": size,
            "path": _relative_path(path, book_dir),
        },
        report,
    )


def _flag_regions(
    context: AuthoringContext, observations: dict | None
) -> tuple[dict, dict[str, list[dict]], list[dict]]:
    path = context.book_dir / "work" / REVIEW_FLAGS_FILENAME
    if not path.is_file():
        return (
            {
                "state": "unavailable",
                "reason": f"no migrated work/{REVIEW_FLAGS_FILENAME}",
            },
            {},
            [],
        )
    document = load_structure_review_flags(path, expected_book=context.book)
    freeze_digest, _ = _file_identity(context.freeze_path)
    if document["seed_identity"]["freeze_sha256"] != freeze_digest:
        raise StaleArtifactError(
            "structure-review flags bind a different stream freeze; migrate them consciously"
        )
    observation_ids = {
        sighting["sighting_id"]
        for sighting in (observations or {}).get("sightings", [])
    }
    by_node: dict[str, list[dict]] = {}
    unassociated: list[dict] = []
    for record in document["flags"]:
        decorated = live_flag(
            record,
            context.smap.projection,
            current_observation_ids=observation_ids,
        )
        target = decorated["target_node_id"]
        if target in context.smap.projection.by_id:
            by_node.setdefault(target, []).append(decorated)
        else:
            unassociated.append(decorated)
    digest, size = _file_identity(path)
    return (
        {
            "state": "available",
            "schema_version": document["schema_version"],
            "policy": document["producer"]["id"],
            "sha256": digest,
            "bytes": size,
            "path": _relative_path(path, context.book_dir),
        },
        by_node,
        unassociated,
    )


def _associate_observations(
    inspection: StructureInspection, report: dict | None
) -> tuple[list[dict], dict[str, list[dict]]]:
    if report is None:
        return [], {}
    projection = inspection.context.smap.projection
    by_node: dict[str, list[dict]] = {}
    associations: list[dict] = []
    for expectation in report["expectations"]:
        wanted = normalize_review_label(expectation["literal"])
        candidates = [
            node_id
            for node_id in inspection.human_containers
            if wanted
            in {
                normalize_review_label(projection.by_id[node_id].designation),
                normalize_review_label(projection.by_id[node_id].title),
            }
        ]
        state = (
            "associated"
            if len(candidates) == 1
            else "unmatched"
            if not candidates
            else "ambiguous"
        )
        association = {
            "expectation_id": expectation["expectation_id"],
            "state": state,
            "candidate_node_ids": candidates,
        }
        associations.append(association)
        if state == "associated":
            source_ids = {
                sighting["source_id"]
                for sighting in report["sightings"]
                if sighting["expectation_id"] == expectation["expectation_id"]
            }
            by_node.setdefault(candidates[0], []).append(
                {
                    "association_policy": OBSERVATION_ASSOCIATION_POLICY,
                    "expectation": dict(expectation),
                    "sources": [
                        dict(source)
                        for source in report["sources"]
                        if source["source_id"] in source_ids
                    ],
                    "sightings": [
                        dict(sighting)
                        for sighting in report["sightings"]
                        if sighting["expectation_id"] == expectation["expectation_id"]
                    ],
                    "summaries": [
                        dict(summary)
                        for summary in report["summaries"]
                        if summary["expectation_id"] == expectation["expectation_id"]
                    ],
                }
            )
    return associations, by_node


def _identity(context: AuthoringContext) -> dict:
    map_digest, map_size = _file_identity(context.structure_map_path)
    freeze_digest, freeze_size = _file_identity(context.freeze_path)
    identity = {
        "structure_map": {
            "schema_version": context.smap.doc["schema_version"],
            "sha256": map_digest,
            "bytes": map_size,
            "map_revision": context.smap.map_revision,
            "root_id": context.smap.projection.root_id,
            "path": _relative_path(context.structure_map_path, context.book_dir),
        },
        "stream_freeze": {
            "schema_version": context.freeze_record["stream_freeze_schema_version"],
            "sha256": freeze_digest,
            "bytes": freeze_size,
            "path": _relative_path(context.freeze_path, context.book_dir),
            "streams": [dict(stream) for stream in context.freeze_record["streams"]],
        },
    }
    if context.evidence_path.is_file():
        evidence_digest, evidence_size = _file_identity(context.evidence_path)
        identity["authoring_evidence"] = {
            "state": "available",
            "schema_version": AUTHORING_EVIDENCE_SCHEMA_VERSION,
            "sha256": evidence_digest,
            "bytes": evidence_size,
            "path": _relative_path(context.evidence_path, context.book_dir),
        }
    else:
        identity["authoring_evidence"] = {
            "state": "unavailable",
            "reason": "authoring evidence has not been created; all human containers are missing",
        }
    return identity


def _status_state(kinds: list[str]) -> str:
    if not kinds:
        return "fresh"
    if kinds == ["missing"]:
        return "missing"
    return "stale"


def _item_fingerprint(item: Mapping) -> str:
    payload = dict(item)
    payload.pop("review_fingerprint", None)
    return _digest(payload)


def _exact_keys(value: object, expected: set[str], where: str) -> Mapping:
    if not isinstance(value, Mapping) or set(value) != expected:
        actual = sorted(value) if isinstance(value, Mapping) else type(value).__name__
        raise StaleArtifactError(
            f"{where} keys {actual!r} do not equal registered {sorted(expected)!r}"
        )
    return value


def _validate_atom_view(value: object, where: str) -> None:
    atom = _exact_keys(
        value,
        {
            "atom_id",
            "text",
            "text_length",
            "text_truncated",
            "raw_span",
            "raw_source_hash",
            "page_range",
            "norm_layer",
            "capture_provenance_class",
            "witness",
            "derived_from",
            "processing_scope",
            "geom",
        },
        where,
    )
    geom = atom["geom"]
    if not isinstance(geom, Mapping) or type(geom.get("present")) is not bool:
        raise StaleArtifactError(f"{where}.geom must carry a genuine present boolean")
    geom_keys = (
        {
            "present",
            "page",
            "bbox",
            "geometry_engine",
            "matched_witness_id",
            "match_method",
            "match_confidence",
        }
        if geom["present"]
        else {"present"}
    )
    _exact_keys(geom, geom_keys, f"{where}.geom")
    if type(atom["text_length"]) is not int or type(atom["text_truncated"]) is not bool:
        raise StaleArtifactError(
            f"{where} text length/truncation fields have false scalar types"
        )
    for index, derivation in enumerate(atom["derived_from"]):
        _exact_keys(
            derivation, {"witness", "atom_id"}, f"{where}.derived_from[{index}]"
        )


def _validate_inspection(value: object, node_id: str) -> None:
    inspection = _exact_keys(
        value,
        {
            "node_id",
            "node_class",
            "minted_by",
            "designation",
            "title",
            "stored_handle_policy",
            "effective_handle_policy",
            "handles",
            "aliases",
            "parent",
            "children",
            "previous_container",
            "following_container",
            "hierarchy",
            "own_slots",
            "own_atoms",
            "extent",
            "decision_payload",
            "extent_payload",
            "evidence_entry",
        },
        f"item {node_id!r}.inspection",
    )
    _exact_keys(
        inspection["handles"],
        {"html_slug", "parse_md", "short"},
        f"item {node_id!r}.inspection.handles",
    )
    for index, alias in enumerate(inspection["aliases"]):
        _exact_keys(
            alias,
            {
                "handle_type",
                "value",
                "scope",
                "locale_or_witness",
                "valid_from",
                "valid_to",
                "status",
            },
            f"item {node_id!r}.inspection.aliases[{index}]",
        )
    for index, member in enumerate(inspection["hierarchy"]):
        _exact_keys(
            member,
            {"node_id", "node_class", "label"},
            f"item {node_id!r}.inspection.hierarchy[{index}]",
        )
    if not isinstance(inspection["own_slots"], Mapping) or not isinstance(
        inspection["own_atoms"], Mapping
    ):
        raise StaleArtifactError(
            f"item {node_id!r} own slot/atom regions must be objects"
        )
    if set(inspection["own_slots"]) != set(inspection["own_atoms"]):
        raise StaleArtifactError(
            f"item {node_id!r} own slot and own atom keys disagree"
        )
    for slot, atoms in inspection["own_atoms"].items():
        if [atom.get("atom_id") for atom in atoms] != inspection["own_slots"][slot]:
            raise StaleArtifactError(
                f"item {node_id!r} own atom ids disagree in slot {slot!r}"
            )
        for index, atom in enumerate(atoms):
            _validate_atom_view(atom, f"item {node_id!r}.own_atoms.{slot}[{index}]")
    extent = _exact_keys(
        inspection["extent"],
        {"atom_count", "first_atom_id", "last_atom_id", "truncated", "atoms"},
        f"item {node_id!r}.inspection.extent",
    )
    for index, atom in enumerate(extent["atoms"]):
        _validate_atom_view(atom, f"item {node_id!r}.extent.atoms[{index}]")
    _exact_keys(
        inspection["decision_payload"],
        {"node_class", "children"},
        f"item {node_id!r}.inspection.decision_payload",
    )
    extent_payload = _exact_keys(
        inspection["extent_payload"],
        {"own", "beneath"},
        f"item {node_id!r}.inspection.extent_payload",
    )
    if set(extent_payload["own"]) != set(inspection["own_slots"]):
        raise StaleArtifactError(
            f"item {node_id!r} extent/inspection slot names disagree"
        )
    entry = inspection["evidence_entry"]
    if entry is not None:
        evidence_entry = _exact_keys(
            entry,
            {
                "node_id",
                "decision_digest",
                "extent_digest",
                "evidence",
                "authored_at_revision",
                "decision_payload",
                "extent_payload",
            },
            f"item {node_id!r}.inspection.evidence_entry",
        )
        _exact_keys(
            evidence_entry["decision_payload"],
            {"node_class", "children"},
            f"item {node_id!r}.evidence_entry.decision_payload",
        )
        _exact_keys(
            evidence_entry["extent_payload"],
            {"own", "beneath"},
            f"item {node_id!r}.evidence_entry.extent_payload",
        )


def _build_packet_for_context(
    context: AuthoringContext, *, asset_root: Path, validate_live: bool
) -> dict:
    """Assemble one packet from one already checked authoring filesystem snapshot."""

    book_dir = context.book_dir
    canonical_stream_id = context.canonical_stream_id
    inspection = StructureInspection.build(context)
    status = authoring_status_for_context(context)
    observations_adjunct, observations = _observation_regions(book_dir, context.book)
    associations, observations_by_node = _associate_observations(
        inspection, observations
    )
    visual_adjunct, visual_sources, visual_page_maps = _load_visual_sources(
        book_dir, asset_root
    )
    _validate_visual_page_nodes(visual_page_maps, inspection.human_containers)
    flag_adjunct, flags_by_node, unassociated_flags = _flag_regions(
        context, observations
    )
    row_by_node = {row.node_id: row for row in status.rows}
    items: list[dict] = []
    for ordinal, node_id in enumerate(inspection.human_containers, 1):
        kinds = list(row_by_node[node_id].kinds)
        item = {
            "node_id": node_id,
            "ordinal": ordinal,
            "status": {"state": _status_state(kinds), "kinds": kinds},
            "inspection": inspection.inspect_node(node_id),
            "observations": observations_by_node.get(node_id, []),
            "flags": (
                {
                    "state": "available",
                    "reason": None,
                    "items": flags_by_node.get(node_id, []),
                }
                if flag_adjunct["state"] == "available"
                else {
                    "state": flag_adjunct["state"],
                    "reason": flag_adjunct["reason"],
                    "items": [],
                }
            ),
            "visuals": [
                {
                    **dict(source),
                    "page_ranges": visual_page_maps.get(source["source_id"], {}).get(
                        node_id, []
                    ),
                }
                for source in visual_sources
            ],
            "review_fingerprint_policy": STRUCTURE_REVIEW_ITEM_POLICY,
        }
        item["review_fingerprint"] = _item_fingerprint(item)
        items.append(item)
    packet = {
        "schema_version": STRUCTURE_REVIEW_SCHEMA_VERSION,
        "stale_class": STRUCTURE_REVIEW_STALE_CLASS,
        "packet_policy": STRUCTURE_REVIEW_PACKET_POLICY,
        "renderer": STRUCTURE_REVIEW_RENDERER,
        "book": context.book,
        "canonical_stream_id": canonical_stream_id,
        "identity": _identity(context),
        "adjuncts": {
            "structural_observations": observations_adjunct,
            "review_flags": flag_adjunct,
            "visual_sources": visual_adjunct,
        },
        "class_counts": inspection.class_counts(),
        "status_counts": dict(status.counts),
        "anomalies": [
            {"kind": kind, "message": message} for kind, message in status.anomalies
        ],
        "observation_associations": associations,
        "unassociated_flags": unassociated_flags,
        "items": items,
    }
    packet["packet_sha256"] = _digest(packet)
    validate_structure_review_packet(
        packet,
        asset_root=asset_root,
        book_dir=book_dir if validate_live else None,
    )
    return packet


def build_structure_review_packet(
    book_dir: Path,
    *,
    canonical_stream_id: str = "canonical",
    asset_root: Path | None = None,
) -> dict:
    """Build the current deterministic review packet from the shared authoring context."""

    book_dir = Path(book_dir).resolve()
    root = Path(asset_root) if asset_root is not None else book_dir.parents[2]
    context = load_authoring_context(book_dir, canonical_stream_id=canonical_stream_id)
    return _build_packet_for_context(context, asset_root=root, validate_live=True)


def render_structure_review_packet(packet: Mapping) -> str:
    """Canonical human-diffable JSON rendering (deterministic, one trailing newline)."""

    return (
        json.dumps(
            packet, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False
        )
        + "\n"
    )


def _validate_live_identity(packet: Mapping, book_dir: Path) -> None:
    identity = packet["identity"]
    for field, base in (("structure_map", book_dir), ("stream_freeze", book_dir)):
        record = identity[field]
        path = _contained_asset(base, record["path"])
        digest, size = _file_identity(path)
        if digest != record["sha256"] or size != record["bytes"]:
            raise StaleArtifactError(
                f"review packet {field} identity no longer matches live bytes"
            )
    evidence = identity["authoring_evidence"]
    evidence_path = book_dir / "work" / "authoring_evidence.json"
    if evidence["state"] == "available":
        path = _contained_asset(book_dir, evidence["path"])
        digest, size = _file_identity(path)
        if digest != evidence["sha256"] or size != evidence["bytes"]:
            raise StaleArtifactError(
                "review packet authoring-evidence identity is stale"
            )
    elif evidence_path.exists():
        raise StaleArtifactError(
            "review packet predates the now-present authoring evidence"
        )
    adjunct_paths = {
        "structural_observations": book_dir / "work" / OBSERVATIONS_FILENAME,
        "review_flags": book_dir / "work" / REVIEW_FLAGS_FILENAME,
        "visual_sources": book_dir / VISUAL_SOURCES_FILENAME,
    }
    for name, live_path in adjunct_paths.items():
        record = packet["adjuncts"][name]
        if record["state"] == "available":
            path = _contained_asset(book_dir, record["path"])
            digest, size = _file_identity(path)
            if digest != record["sha256"] or size != record["bytes"]:
                raise StaleArtifactError(f"review packet adjunct {name!r} is stale")
        elif live_path.exists():
            raise StaleArtifactError(
                f"review packet says adjunct {name!r} is absent but it is now present"
            )


def _validate_live_semantics(packet: Mapping, book_dir: Path, asset_root: Path) -> None:
    """Reproduce every engine-owned item region from current validated inputs."""

    context = load_authoring_context(
        book_dir, canonical_stream_id=packet["canonical_stream_id"]
    )
    inspection = StructureInspection.build(context)
    status = authoring_status_for_context(context)
    status_by_node = {row.node_id: list(row.kinds) for row in status.rows}
    _, observations = _observation_regions(book_dir, context.book)
    associations, observations_by_node = _associate_observations(
        inspection, observations
    )
    flag_adjunct, flags_by_node, unassociated_flags = _flag_regions(
        context, observations
    )
    _, visual_sources, visual_page_maps = _load_visual_sources(book_dir, asset_root)
    _validate_visual_page_nodes(visual_page_maps, inspection.human_containers)
    if packet["class_counts"] != inspection.class_counts():
        raise StaleArtifactError("structure-review class counts do not reproduce")
    if packet["status_counts"] != dict(status.counts):
        raise StaleArtifactError("structure-review status counts do not reproduce")
    if packet["anomalies"] != [
        {"kind": kind, "message": message} for kind, message in status.anomalies
    ]:
        raise StaleArtifactError("structure-review anomalies do not reproduce")
    if packet["observation_associations"] != associations:
        raise StaleArtifactError(
            "structure-review observation associations do not reproduce"
        )
    if packet["unassociated_flags"] != unassociated_flags:
        raise StaleArtifactError("structure-review unassociated flags do not reproduce")
    expected_ids = list(inspection.human_containers)
    if [item["node_id"] for item in packet["items"]] != expected_ids:
        raise StaleArtifactError(
            "structure-review item order does not match live map reading order"
        )
    flags_available = packet["adjuncts"]["review_flags"]["state"] == "available"
    for item in packet["items"]:
        node_id = item["node_id"]
        if item["inspection"] != inspection.inspect_node(node_id):
            raise StaleArtifactError(
                f"structure-review inspection for {node_id!r} is stale"
            )
        kinds = status_by_node[node_id]
        if item["status"] != {"state": _status_state(kinds), "kinds": kinds}:
            raise StaleArtifactError(
                f"structure-review status for {node_id!r} is stale"
            )
        if item["observations"] != observations_by_node.get(node_id, []):
            raise StaleArtifactError(
                f"structure-review observations for {node_id!r} are stale"
            )
        expected_flags = (
            {
                "state": "available",
                "reason": None,
                "items": flags_by_node.get(node_id, []),
            }
            if flags_available
            else {
                "state": flag_adjunct["state"],
                "reason": flag_adjunct["reason"],
                "items": [],
            }
        )
        if item["flags"] != expected_flags:
            raise StaleArtifactError(
                f"structure-review flags for {node_id!r} are stale"
            )
        expected_visuals = [
            {
                **dict(source),
                "page_ranges": visual_page_maps.get(source["source_id"], {}).get(
                    node_id, []
                ),
            }
            for source in visual_sources
        ]
        if item["visuals"] != expected_visuals:
            raise StaleArtifactError(
                f"structure-review visuals for {node_id!r} are stale"
            )


def validate_structure_review_packet(
    packet: Mapping, *, asset_root: Path, book_dir: Path | None = None
) -> None:
    """Hold schema, deterministic hashes, cross-fields, live identities, and visual locks."""

    errors = sorted(
        _packet_validator().iter_errors(packet),
        key=lambda error: tuple(str(part) for part in error.path),
    )
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        raise StaleArtifactError(
            f"structure-review packet schema failure at {location}: {error.message}"
        )
    if type(packet["schema_version"]) is not int:
        raise StaleArtifactError(
            "structure-review packet schema_version must be a genuine int"
        )
    without_hash = dict(packet)
    supplied_packet_hash = without_hash.pop("packet_sha256")
    if not hmac.compare_digest(supplied_packet_hash, _digest(without_hash)):
        raise StaleArtifactError("structure-review packet_sha256 does not reproduce")
    node_ids: set[str] = set()
    for ordinal, item in enumerate(packet["items"], 1):
        if type(item["ordinal"]) is not int or item["ordinal"] != ordinal:
            raise StaleArtifactError(
                "structure-review item ordinals must be genuine sequential ints"
            )
        if item["node_id"] in node_ids:
            raise StaleArtifactError(
                f"duplicate structure-review item {item['node_id']!r}"
            )
        node_ids.add(item["node_id"])
        if item["inspection"].get("node_id") != item["node_id"]:
            raise StaleArtifactError(
                f"structure-review item {item['node_id']!r} disagrees with its inspection"
            )
        _validate_inspection(item["inspection"], item["node_id"])
        if not hmac.compare_digest(item["review_fingerprint"], _item_fingerprint(item)):
            raise StaleArtifactError(
                f"structure-review item {item['node_id']!r} fingerprint does not reproduce"
            )
    if packet["status_counts"]["containers"] != len(packet["items"]):
        raise StaleArtifactError(
            "structure-review container count disagrees with items"
        )
    registered_visuals = packet["adjuncts"]["visual_sources"]["sources"]
    visual_by_id = {source["source_id"]: source for source in registered_visuals}
    if len(visual_by_id) != len(registered_visuals):
        raise StaleArtifactError("structure-review visual sources have duplicate ids")
    for source in registered_visuals:
        path = _contained_asset(asset_root, source["path"])
        digest, size = _file_identity(path)
        if digest != source["sha256"] or size != source["bytes"]:
            raise StaleArtifactError(
                f"visual source {source['source_id']!r} no longer matches"
            )
    for item in packet["items"]:
        incoherent = False
        for source in item["visuals"]:
            base = dict(source)
            base.pop("page_ranges", None)
            if visual_by_id.get(source["source_id"]) != base:
                incoherent = True
                break
        if incoherent:
            raise StaleArtifactError(
                f"item {item['node_id']!r} contains an unregistered/incoherent visual descriptor"
            )
    if book_dir is not None:
        live_book_dir = Path(book_dir)
        _validate_live_identity(packet, live_book_dir)
        _validate_live_semantics(packet, live_book_dir, Path(asset_root))


def load_structure_review_packet(
    path: Path, *, asset_root: Path, book_dir: Path
) -> dict:
    """Load a persisted packet or fail totally as stale/missing."""

    path = Path(path)
    if not path.is_file():
        raise MissingInputError(f"structure-review packet not found at {path}")
    try:
        text = path.read_text(encoding="utf-8")
        packet = json.loads(
            text, parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token))
        )
    except (OSError, UnicodeError, ValueError, RecursionError) as exc:
        raise StaleArtifactError(
            f"structure-review packet at {path} is unreadable"
        ) from exc
    if not isinstance(packet, dict):
        raise StaleArtifactError("structure-review packet top level must be an object")
    validate_structure_review_packet(packet, asset_root=asset_root, book_dir=book_dir)
    return packet


def record_structure_evidence(
    book_dir: Path,
    *,
    node_id: str,
    review_fingerprint: str,
    evidence: str,
    canonical_stream_id: str = "canonical",
    asset_root: Path | None = None,
) -> dict:
    """Guard and record exactly one structure evidence stamp, then return its refreshed item."""

    if not isinstance(node_id, str) or not node_id:
        raise InvalidInvocationError(
            "structure evidence write requires a non-empty node_id"
        )
    if (
        not isinstance(review_fingerprint, str)
        or len(review_fingerprint) != 64
        or any(character not in "0123456789abcdef" for character in review_fingerprint)
    ):
        raise InvalidInvocationError(
            "structure evidence write requires a lowercase SHA-256 review fingerprint"
        )
    if not isinstance(evidence, str) or not evidence.strip():
        raise InvalidInvocationError(
            "structure evidence write requires non-blank evidence prose"
        )
    book_dir = Path(book_dir).resolve()
    root = Path(asset_root) if asset_root is not None else book_dir.parents[2]
    context = load_authoring_context(book_dir, canonical_stream_id=canonical_stream_id)
    current = _build_packet_for_context(context, asset_root=root, validate_live=False)
    matches = [item for item in current["items"] if item["node_id"] == node_id]
    if len(matches) != 1:
        raise StaleArtifactError(
            f"structure-review node {node_id!r} is not one current human-container item"
        )
    live_fingerprint = matches[0]["review_fingerprint"]
    if not hmac.compare_digest(review_fingerprint, live_fingerprint):
        raise StaleArtifactError(
            f"structure-review item {node_id!r} changed: submitted {review_fingerprint} != "
            f"current {live_fingerprint}"
        )
    stamp_evidence_for_context(context, node_id, evidence=evidence)
    refreshed = build_structure_review_packet(
        book_dir, canonical_stream_id=canonical_stream_id, asset_root=root
    )
    refreshed_items = [
        item for item in refreshed["items"] if item["node_id"] == node_id
    ]
    if len(refreshed_items) != 1 or refreshed_items[0]["status"]["kinds"]:
        raise StaleArtifactError(
            f"structure evidence stamp for {node_id!r} did not reload as fresh"
        )
    return {
        "status": "fresh",
        "book": refreshed["book"],
        "node_id": node_id,
        "packet_sha256": refreshed["packet_sha256"],
        "item": refreshed_items[0],
    }
