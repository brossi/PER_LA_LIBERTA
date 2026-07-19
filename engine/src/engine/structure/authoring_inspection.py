"""Reusable, read-only S4.6 structure inspection model (#44/#93).

The terminal ``authoring inspect`` command and the structure-review packet consume this one
indexed model. It has no persistence or mutation capability.
"""

from __future__ import annotations

import unicodedata
from collections import Counter
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from engine.structure.authoring_context import AuthoringContext
from engine.structure.evidence import decision_payload, extent_payload
from engine.structure.handles import (
    SCOPE_GLOBAL,
    TARGET_FORMATS,
    effective_handle_policy,
    render_handle,
)
from engine.structure.projection import MINTED_BY_HUMAN, ContainerNode, Node

ATOM_TEXT_LIMIT = 500
EXTENT_EDGE_ATOMS = 12


def normalize_review_label(value: str) -> str:
    """The neutral exact-label normalizer registered for review search/association."""

    folded = unicodedata.normalize("NFKC", value).casefold()
    words: list[str] = []
    current: list[str] = []
    for character in folded:
        if character.isalnum():
            current.append(character)
        elif current:
            words.append("".join(current))
            current = []
    if current:
        words.append("".join(current))
    return " ".join(words)


def _node_slots(node: Node) -> dict[str, list[str]]:
    if isinstance(node, ContainerNode):
        return {
            "heading": list(node.heading_atoms),
            "signature": list(node.signature_atoms),
        }
    return {"body": list(node.body_atoms)}


def _entry_json(entry) -> dict | None:
    if entry is None:
        return None
    return {
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
            "own": {
                slot: list(atom_ids)
                for slot, atom_ids in entry.extent_payload["own"].items()
            },
            "beneath": list(entry.extent_payload["beneath"]),
        },
    }


@dataclass(frozen=True, slots=True)
class StructureInspection:
    """A one-pass index over a fully validated authoring context."""

    context: AuthoringContext
    parents: Mapping[str, str]
    owners: Mapping[str, tuple[str, str]]
    canonical_atoms: Mapping[str, object]
    canonical_order: Mapping[str, int]
    human_containers: tuple[str, ...]

    @classmethod
    def build(cls, context: AuthoringContext) -> "StructureInspection":
        projection = context.smap.projection
        parents: dict[str, str] = {}
        owners: dict[str, tuple[str, str]] = {}
        for node in projection.nodes:
            if isinstance(node, ContainerNode):
                for child in node.children:
                    parents[child] = node.node_id
            for slot, atom_ids in _node_slots(node).items():
                for atom_id in atom_ids:
                    owners[atom_id] = (node.node_id, slot)
        canonical = context.streams[context.canonical_stream_id]
        atoms = {atom.atom_id: atom for atom in canonical.atoms}
        order = {atom.atom_id: index for index, atom in enumerate(canonical.atoms)}
        humans = tuple(
            node.node_id
            for node in projection.nodes
            if isinstance(node, ContainerNode) and node.minted_by == MINTED_BY_HUMAN
        )
        return cls(
            context=context,
            parents=MappingProxyType(parents),
            owners=MappingProxyType(owners),
            canonical_atoms=MappingProxyType(atoms),
            canonical_order=MappingProxyType(order),
            human_containers=humans,
        )

    def class_counts(self) -> dict[str, int]:
        return dict(
            sorted(Counter(node.node_class for node in self.context.smap.projection.nodes).items())
        )

    def node_for_atom(self, atom_id: str) -> tuple[str, str]:
        try:
            return self.owners[atom_id]
        except KeyError as exc:
            raise ValueError(f"inspect: atom {atom_id!r} is not owned by a structure node") from exc

    def search_headings(self, query: str) -> tuple[str, ...]:
        wanted = normalize_review_label(query)
        if not wanted:
            raise ValueError("inspect: heading query must contain an alphanumeric character")
        return tuple(
            node.node_id
            for node in self.context.smap.projection.nodes
            if wanted
            in normalize_review_label(
                " ".join(value for value in (node.designation, node.title) if value)
            )
        )

    def _hierarchy(self, node_id: str) -> list[dict]:
        projection = self.context.smap.projection
        chain: list[str] = []
        seen: set[str] = set()
        current: str | None = node_id
        while current is not None and current not in seen:
            seen.add(current)
            chain.append(current)
            current = self.parents.get(current)
        chain.reverse()
        return [
            {
                "node_id": member,
                "node_class": projection.by_id[member].node_class,
                "label": projection.by_id[member].designation
                or projection.by_id[member].title,
            }
            for member in chain
        ]

    def _atom_json(self, atom_id: str) -> dict:
        atom = self.canonical_atoms.get(atom_id)
        if atom is None:
            raise ValueError(
                f"inspect: structure atom {atom_id!r} is absent from canonical stream "
                f"{self.context.canonical_stream_id!r}"
            )
        text = atom.text
        clipped = len(text) > ATOM_TEXT_LIMIT
        geom = {"present": atom.geom.present}
        if atom.geom.present:
            geom.update(
                {
                    "page": atom.geom.page,
                    "bbox": list(atom.geom.bbox),
                    "geometry_engine": atom.geom.geometry_engine,
                    "matched_witness_id": atom.geom.matched_witness_id,
                    "match_method": atom.geom.match_method,
                    "match_confidence": atom.geom.match_confidence,
                }
            )
        return {
            "atom_id": atom.atom_id,
            "text": text[:ATOM_TEXT_LIMIT],
            "text_length": len(text),
            "text_truncated": clipped,
            "raw_span": list(atom.raw_span),
            "raw_source_hash": atom.raw_source_hash,
            "page_range": list(atom.page_range),
            "norm_layer": atom.norm_layer,
            "capture_provenance_class": atom.capture_provenance_class,
            "witness": atom.witness,
            "derived_from": [
                {"witness": derivation.witness, "atom_id": derivation.atom_id}
                for derivation in atom.derived_from
            ],
            "processing_scope": atom.processing_scope,
            "geom": geom,
        }

    def inspect_node(self, node_id: str) -> dict:
        projection = self.context.smap.projection
        node = projection.by_id.get(node_id)
        if node is None:
            raise ValueError(f"inspect: node {node_id!r} is not in the structure map")
        policy = effective_handle_policy(projection, node_id, self.context.smap.handle_policies)
        aliases = [
            {
                "handle_type": alias.handle_type,
                "value": alias.value,
                "scope": alias.scope,
                "locale_or_witness": alias.locale_or_witness,
                "valid_from": alias.valid_from,
                "valid_to": alias.valid_to,
                "status": alias.status,
            }
            for alias in self.context.smap.aliases
            if alias.target_node_id == node_id
        ]
        extent = extent_payload(node, projection)
        extent_ids = set(extent["beneath"])
        for own_ids in extent["own"].values():
            extent_ids.update(own_ids)
        ordered_extent = sorted(
            extent_ids,
            key=lambda atom_id: (
                self.canonical_order.get(atom_id, len(self.canonical_order)),
                atom_id,
            ),
        )
        if len(ordered_extent) <= EXTENT_EDGE_ATOMS * 2:
            displayed = ordered_extent
        else:
            displayed = [
                *ordered_extent[:EXTENT_EDGE_ATOMS],
                *ordered_extent[-EXTENT_EDGE_ATOMS:],
            ]
        previous_id = following_id = None
        if node_id in self.human_containers:
            position = self.human_containers.index(node_id)
            previous_id = self.human_containers[position - 1] if position else None
            following_id = (
                self.human_containers[position + 1]
                if position + 1 < len(self.human_containers)
                else None
            )
        decision = decision_payload(node)
        return {
            "node_id": node.node_id,
            "node_class": node.node_class,
            "minted_by": node.minted_by,
            "designation": node.designation,
            "title": node.title,
            "stored_handle_policy": node.handle_policy or None,
            "effective_handle_policy": policy,
            "handles": {
                target: render_handle(projection, node_id, policy, target, SCOPE_GLOBAL)
                for target in sorted(TARGET_FORMATS)
            },
            "aliases": aliases,
            "parent": self.parents.get(node_id),
            "children": list(node.children) if isinstance(node, ContainerNode) else [],
            "previous_container": previous_id,
            "following_container": following_id,
            "hierarchy": self._hierarchy(node_id),
            "own_slots": _node_slots(node),
            "own_atoms": {
                slot: [self._atom_json(atom_id) for atom_id in atom_ids]
                for slot, atom_ids in _node_slots(node).items()
            },
            "extent": {
                "atom_count": len(ordered_extent),
                "first_atom_id": ordered_extent[0] if ordered_extent else None,
                "last_atom_id": ordered_extent[-1] if ordered_extent else None,
                "truncated": len(displayed) < len(ordered_extent),
                "atoms": [self._atom_json(atom_id) for atom_id in displayed],
            },
            "decision_payload": {
                "node_class": decision["node_class"],
                "children": list(decision["children"]),
            },
            "extent_payload": {
                "own": {slot: list(ids) for slot, ids in extent["own"].items()},
                "beneath": list(extent["beneath"]),
            },
            "evidence_entry": _entry_json(self.context.evidence.by_node.get(node_id)),
        }

