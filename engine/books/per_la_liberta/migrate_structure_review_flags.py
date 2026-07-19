"""One-time, source-locked migration of the PLL seeder's 22 stdout warnings into #93 flags.

The legacy seeder remains the producer. This script reconstructs its candidate over the exact
frozen streams, verifies that every bound target has the same decision/extent semantics in the live
map, and persists immutable messages plus seed digests. It never writes the structure map or
authoring evidence.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from engine.structure.authoring_context import load_authoring_context
from engine.structure.evidence import decision_digest, decision_payload, extent_digest, extent_payload
from engine.structure.projection import ContainerNode, MINTED_BY_HUMAN
from engine.structure.review_flags import (
    STRUCTURE_REVIEW_FLAGS_SCHEMA_VERSION,
    STRUCTURE_REVIEW_FLAGS_STALE_CLASS,
    flag_id,
    validate_structure_review_flags,
)
from engine.structure.structural_contents import load_structural_contents_report
from engine.structure.structure_map import structure_map_from_json
from engine.util.jsonio import atomic_write_json, read_json

from seed_structure_map import build_draft

BOOK_DIR = Path(__file__).resolve().parent
OUTPUT = BOOK_DIR / "work" / "structure_review_flags.json"
OBSERVATIONS = BOOK_DIR / "work" / "structure_observations.json"
PRODUCER_ID = "pll-seed-structure-map-flags-v1"
PRODUCER_VERSION = 1
_ATOM = re.compile(r"\bcanonical_[0-9]+\b")
_QUOTED_CHAPTER = re.compile(r"^(Parte (?:Prima|Seconda)) '([^']+)':")


def _canonical_digest(value: object) -> str:
    rendered = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(rendered).hexdigest()


def _indexes(projection):
    parents: dict[str, str] = {}
    owners: dict[str, str] = {}
    labels: dict[str, list[str]] = {}
    for node in projection.nodes:
        if isinstance(node, ContainerNode):
            for child in node.children:
                parents[child] = node.node_id
            for atom_id in (*node.heading_atoms, *node.signature_atoms):
                owners[atom_id] = node.node_id
            if node.minted_by == MINTED_BY_HUMAN:
                for label in {node.designation, node.title} - {""}:
                    labels.setdefault(label, []).append(node.node_id)
        else:
            for atom_id in node.body_atoms:
                owners[atom_id] = node.node_id
    return parents, owners, labels


def _human_owner(atom_id: str, projection, parents: dict[str, str], owners: dict[str, str]):
    node_id = owners.get(atom_id)
    seen: set[str] = set()
    while node_id is not None and node_id not in seen:
        seen.add(node_id)
        node = projection.by_id[node_id]
        if isinstance(node, ContainerNode) and node.minted_by == MINTED_BY_HUMAN:
            return node_id
        node_id = parents.get(node_id)
    return None


def _target(message: str, cited: list[str], projection, parents, owners, labels):
    chapter = _QUOTED_CHAPTER.match(message)
    if chapter is not None:
        part_label, chapter_label = chapter.groups()
        for candidate in labels.get(chapter_label, []):
            current = parents.get(candidate)
            while current is not None:
                ancestor = projection.by_id[current]
                if ancestor.designation == part_label or ancestor.title == part_label:
                    return candidate
                current = parents.get(current)
        return None
    if message.startswith("Prefazione:"):
        matches = labels.get("Prefazione", [])
        return matches[0] if len(matches) == 1 else None
    if message.startswith("Parte Prima: only"):
        matches = labels.get("Parte Prima", [])
        return matches[0] if len(matches) == 1 else None
    if message.startswith("Parte Seconda: duplicate"):
        matches = labels.get("Parte Seconda", [])
        return matches[0] if len(matches) == 1 else None
    if cited:
        return _human_owner(cited[0], projection, parents, owners)
    return None


def _kind(message: str) -> str:
    if "fuzzy heading match" in message:
        return "fuzzy-heading"
    if "NO heading located" in message:
        return "missing-heading"
    if "only heading-like match sits AFTER" in message:
        return "out-of-order-heading"
    if "end matter" in message:
        return "unsegmented-content"
    if "duplicate heading-like" in message or "heading-like atom" in message:
        return "duplicate-heading"
    return "source-anomaly"


def build_flag_document() -> dict:
    context = load_authoring_context(BOOK_DIR)
    candidate_doc, messages = build_draft(dict(context.streams))
    candidate = structure_map_from_json(candidate_doc).projection
    parents, owners, labels = _indexes(candidate)
    observations = load_structural_contents_report(OBSERVATIONS, expected_book=context.book)
    by_expectation = {
        expectation["expectation_id"]: [
            sighting["sighting_id"]
            for sighting in observations["sightings"]
            if sighting["expectation_id"] == expectation["expectation_id"]
        ]
        for expectation in observations["expectations"]
    }
    contents_sightings = [
        sighting["sighting_id"]
        for sighting in observations["sightings"]
        if sighting["locus"] == "contents-like"
    ]
    flags: list[dict] = []
    for ordinal, message in enumerate(messages, 1):
        cited = list(dict.fromkeys(_ATOM.findall(message)))
        target = _target(message, cited, candidate, parents, owners, labels)
        node = candidate.by_id.get(target) if target is not None else None
        if target is not None:
            live = context.smap.projection.by_id.get(target)
            if live is None or decision_payload(live) != decision_payload(node) or extent_payload(
                live, context.smap.projection
            ) != extent_payload(node, candidate):
                raise ValueError(
                    f"legacy flag {ordinal} target {target!r} no longer matches candidate semantics"
                )
        corroborating: list[str] = []
        if ordinal in (2, 3):
            corroborating = by_expectation.get("part-2", [])
        elif ordinal == 4:
            corroborating = by_expectation.get("part-1", [])
        elif ordinal == 22:
            corroborating = contents_sightings
        flags.append(
            {
                "flag_id": flag_id(PRODUCER_ID, ordinal, message),
                "kind": _kind(message),
                "message": message,
                "target_node_id": target,
                "cited_atom_ids": cited,
                "seed_decision_digest": decision_digest(node) if node is not None else None,
                "seed_extent_digest": extent_digest(node, candidate) if node is not None else None,
                "resolution_posture": (
                    "correction-required"
                    if ordinal in (11, 22)
                    else "review-required"
                ),
                "corroborating_observation_ids": corroborating,
            }
        )
    semantics = [
        {
            "node_id": node.node_id,
            "decision": decision_payload(node),
            "extent": extent_payload(node, candidate),
        }
        for node in candidate.nodes
    ]
    freeze_bytes = context.freeze_path.read_bytes()
    document = {
        "schema_version": STRUCTURE_REVIEW_FLAGS_SCHEMA_VERSION,
        "stale_class": STRUCTURE_REVIEW_FLAGS_STALE_CLASS,
        "book": context.book,
        "producer": {"id": PRODUCER_ID, "version": PRODUCER_VERSION},
        "seed_identity": {
            "candidate_semantics_sha256": _canonical_digest(semantics),
            "freeze_sha256": hashlib.sha256(freeze_bytes).hexdigest(),
        },
        "flags": flags,
    }
    validate_structure_review_flags(document)
    return document


def main() -> int:
    document = build_flag_document()
    if OUTPUT.exists():
        if read_json(OUTPUT) != document:
            raise ValueError(f"{OUTPUT} differs; refusing to overwrite a migrated flag artifact")
        print(f"unchanged {OUTPUT} ({len(document['flags'])} flags)")
        return 0
    atomic_write_json(OUTPUT, document)
    print(f"wrote {OUTPUT} ({len(document['flags'])} flags)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
