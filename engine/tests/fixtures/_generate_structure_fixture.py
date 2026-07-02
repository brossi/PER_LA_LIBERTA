"""Dev-time generator for the CONFORMING structure-map fixture (S4.4/B-5). NOT a test (leading
underscore) and NOT run at test time.

Evolved from the S0.3 trivial fixture per s4_plan §1.5 M-S4.4 ("evolve trivial → conforming"): the
committed ``structure/conforming_structure_map.json`` is now a complete, Tier-1-valid,
Tier-2-clean structure map that the real ``load_structure_map(path, atom_store)`` loads without a
finding. It is a *fixture*, never a golden — the structure substrate has no live referent
(ENGINE_STRUCTURE_PLAN §9; ``feedback_no_cheating_results``).

Everything is derived from the LIVE producers, which is the binding this fixture exists to hold
(``feedback_validate_bindings``):

- the atom streams come from the real ``capture_witness`` + ``build_canonical`` over two synthetic
  witness sources (one carrying a furniture line, so the map's ``furniture_atoms`` exercises the
  witness-id namespace, §3.B.1);
- node ids come from the real ``mint_node_id`` seam (human counter / machine ULID-like);
- the manifest comes from the real ``build_manifest`` (split canonical hashes via the lineage
  producers) over those streams + a synthetic-but-shape-true ``ResourceLineage``;
- ``schema_version`` derives from the live constant, so a bump without a refresh here fails the
  byte-exact binding test (inv 10's second assertion).

The fixture deliberately carries one of everything the §3.J schema admits: heterogeneous siblings
(a container and a leaf under the root), a heading atom, a ``decision`` value (the inv 25
present-but-inert positive), a ``rebind_anchors.region`` (never ``.geom`` — §2.4/inv 24), an active
and a retired alias, and a reserved-unused vocabulary entry (the ``VOCAB_UNUSED`` exemption).

The synthetic RESOURCE lineage is hand-built (NOT ``ResourceLineage.build(cfg)``): a committed
fixture must not hash live asset bytes, or every dictionary edit would invalidate it. Shape
fidelity to the live class is still real — the fragment is emitted by the live ``to_json()``.

Tests import this module (``importlib`` by path, the ``test_structure_tiers`` pattern) for
``build_fixture()`` / ``render()`` / ``conforming_streams()`` / ``conforming_atom_store()``.

Refresh (after a deliberate schema/producer change):

    uv run python tests/fixtures/_generate_structure_fixture.py
"""

from __future__ import annotations

from pathlib import Path

import engine.structure as structure
from engine.structure.lineage import ResourceLineage, _canonical, _sha256_bytes

FIXTURES_DIR = Path(__file__).resolve().parent
OUT = FIXTURES_DIR / "structure" / "conforming_structure_map.json"

# Two synthetic witness sources: same three body blocks; w1 additionally carries a numeric
# furniture line ("7", a page number) that capture classifies as excluded furniture.
W1_SOURCE = (
    "7\n"
    "\n"
    "Alpha block one.\n"
    "\n"
    "Beta block two, first line.\n"
    "Beta continues here.\n"
    "\n"
    "Gamma closing block.\n"
)
W2_SOURCE = (
    "Alpha block one.\n"
    "\n"
    "Beta block two, first line.\n"
    "Beta continues here.\n"
    "\n"
    "Gamma closing block.\n"
)

CANONICAL_STREAM_ID = "canonical"


def _classify_numeric_furniture(line: str) -> str | None:
    """The fixture's capture classifier: a digits-only line is page-number furniture, else body."""
    return "page-number" if line.strip().isdigit() else None


def conforming_streams() -> dict[str, structure.AtomStream]:
    """The three live-producer streams the fixture map references: two witnesses + the canonical."""
    w1_atoms = structure.capture_witness(W1_SOURCE, "w1", classify_line=_classify_numeric_furniture)
    w2_atoms = structure.capture_witness(W2_SOURCE, "w2")
    canonical_atoms = structure.build_canonical({"w1": w1_atoms, "w2": w2_atoms}, ("w1", "w2"))
    return {
        "w1": structure.AtomStream.witness("w1", w1_atoms, structure.gap_records(w1_atoms, W1_SOURCE), W1_SOURCE),
        "w2": structure.AtomStream.witness("w2", w2_atoms, structure.gap_records(w2_atoms, W2_SOURCE), W2_SOURCE),
        CANONICAL_STREAM_ID: structure.AtomStream.canonical(canonical_atoms, stream_id=CANONICAL_STREAM_ID),
    }


def conforming_atom_store() -> structure.StreamAtomReader:
    """The §4-header thin reader over the fixture streams — what tests pass to load_structure_map."""
    return structure.StreamAtomReader(conforming_streams(), CANONICAL_STREAM_ID)


def _fixture_resource_lineage() -> ResourceLineage:
    """A synthetic-but-shape-true lineage: live class, live canonical/digest producers, fixed bytes."""
    resource_descriptor = _canonical(
        {
            "oracle_min": 2,
            "frequency": _sha256_bytes(b"fixture frequency dictionary\n"),
            "members": [
                {
                    "name": "fixture-dict",
                    "kind": "monolingual",
                    "dir": "fixture/dictionary",
                    "hash": _sha256_bytes(b"fixture member bytes\n"),
                }
            ],
        }
    )
    normalizer_descriptor = _canonical({"accent_fold": {}, "case_fold": "casefold"})
    return ResourceLineage(
        resource_version=_sha256_bytes(resource_descriptor.encode("utf-8")),
        resource_descriptor=resource_descriptor,
        resource_stale_class=structure.RESOURCE_STALE_CLASS,
        normalizer_version=_sha256_bytes(normalizer_descriptor.encode("utf-8")),
        normalizer_descriptor=normalizer_descriptor,
        normalizer_stale_class=structure.NORMALIZER_STALE_CLASS,
    )


def build_fixture() -> dict:
    """The conforming map document, every derivable value derived from the live producers."""
    streams = conforming_streams()
    root_id = structure.mint_node_id("human", 0)      # "n-0"
    section_id = structure.mint_node_id("human", 1)   # "n-1"
    leaf_a = structure.mint_node_id("machine", 10)
    leaf_b = structure.mint_node_id("machine", 11)
    canonical_ids = [a.atom_id for a in streams[CANONICAL_STREAM_ID].atoms]
    furniture_id = next(
        a.atom_id
        for a in streams["w1"].atoms
        if a.processing_scope == structure.PROCESSING_SCOPE_EXCLUDED
    )
    return {
        "schema_version": structure.STRUCTURE_MAP_SCHEMA_VERSION,
        "root_id": root_id,
        "map_revision": 2,
        "block_vocabulary": [
            {"name": "volume", "kind": "container", "status": "active"},
            {"name": "section", "kind": "container", "status": "active"},
            {"name": "block", "kind": "leaf", "status": "active"},
            {"name": "annex", "kind": "either", "status": "reserved"},
        ],
        "handle_policies": {
            "volume": "position-path",
            "section": "position-path",
            "block": "position-path",
        },
        "furniture_atoms": [{"atom_id": furniture_id, "capture_role": "page-number"}],
        "aliases": [
            {
                "handle_type": "html_slug",
                "value": "intro",
                "scope": "global",
                "locale_or_witness": "default",
                "target_node_id": section_id,
                "valid_from": 0,
                "valid_to": None,
                "status": "active",
            },
            {
                "handle_type": "html_slug",
                "value": "old-intro",
                "scope": "global",
                "locale_or_witness": "default",
                "target_node_id": section_id,
                "valid_from": 0,
                "valid_to": 1,
                "status": "retired",
            },
        ],
        "manifest": structure.build_manifest(
            streams=streams,
            canonical_stream_id=CANONICAL_STREAM_ID,
            resource_lineage=_fixture_resource_lineage(),
            profile_version="fixture-profile-1",
            recognizer_version="fixture-recognizer-1",
        ),
        "nodes": [
            {
                "node_id": root_id,
                "node_class": "volume",
                "minted_by": "human",
                "children": [section_id, leaf_b],
                "designation": "Codex",
                "title": "Synthetic Codex",
            },
            {
                "node_id": section_id,
                "node_class": "section",
                "minted_by": "human",
                "children": [leaf_a],
                "heading_atoms": [canonical_ids[0]],
                "designation": "Section One",
                "rebind_anchors": {"region": {"page": 3, "bbox_region": [10.0, 20.0, 400.0, 60.0]}},
                "decision": "human-approved",
            },
            {
                "node_id": leaf_a,
                "node_class": "block",
                "minted_by": "machine",
                "body_atoms": [canonical_ids[1]],
            },
            {
                "node_id": leaf_b,
                "node_class": "block",
                "minted_by": "machine",
                "body_atoms": [canonical_ids[2]],
            },
        ],
    }


def render() -> str:
    """The exact committed byte form — the live writer's renderer, shared with the byte-exact
    binding test, so formatting drift (not just content drift) reds."""
    return structure.render_structure_map(build_fixture())


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(), encoding="utf-8")
    print(
        f"Wrote conforming structure fixture (schema_version="
        f"{structure.STRUCTURE_MAP_SCHEMA_VERSION}) → {OUT.relative_to(FIXTURES_DIR.parents[1])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
