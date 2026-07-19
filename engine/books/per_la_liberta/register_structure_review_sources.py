"""Register PLL's deterministic structure-node ranges for the review workbench.

The visual source locks are hand-selected witness facts.  The per-node ranges are derived facts:
the reviewed structure map supplies the current hierarchy while ``chapter_start_pages.json`` and
the frozen reconciliation skeleton supply copy 1's scan starts.  Re-running this script therefore
refreshes only ``node_pages``; it never guesses that copy 2 shares copy 1's pagination.

Usage (from ``engine/``)::

    uv run python books/per_la_liberta/register_structure_review_sources.py
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from engine.util.jsonio import atomic_write_json, read_json

BOOK_DIR = Path(__file__).resolve().parent
REGISTRATION = BOOK_DIR / "structure_review_sources.json"
STRUCTURE_MAP = BOOK_DIR / "work" / "structure_map.json"
SKELETON = BOOK_DIR / "inputs" / "reconciled_chapters.json"
PAGE_STARTS = BOOK_DIR / "inputs" / "chapter_start_pages.json"
MAPPED_SOURCE_ID = "copy1-pdf"


def _chapter_starts() -> dict[tuple[int, str], int]:
    skeleton = read_json(SKELETON)
    starts_doc = read_json(PAGE_STARTS)
    chapters = [row for row in skeleton if row["part"] in {1, 2}]
    starts = [
        row for row in starts_doc["chapters"] if row["id"].startswith(("p1_", "p2_"))
    ]
    if len(chapters) != len(starts):
        raise RuntimeError(
            "reconciliation skeleton and scan-page sidecar have different chapters"
        )
    result: dict[tuple[int, str], int] = {}
    for chapter, start in zip(chapters, starts, strict=True):
        expected_prefix = f"p{chapter['part']}_"
        if not start["id"].startswith(expected_prefix):
            raise RuntimeError(
                "scan-page sidecar chapter order disagrees with the skeleton"
            )
        key = (chapter["part"], chapter["title"])
        if key in result:
            raise RuntimeError(f"duplicate structural chapter label {key!r}")
        result[key] = start["start_scan"]
    return result


def _node_pages() -> dict[str, list[list[int]]]:
    document = read_json(STRUCTURE_MAP)
    pages_doc = read_json(PAGE_STARTS)
    nodes = {node["node_id"]: node for node in document["nodes"]}
    parents = {
        child: node["node_id"]
        for node in document["nodes"]
        for child in node.get("children", [])
        if child in nodes
    }
    part_numbers = {
        node["node_id"]: number
        for number, node in enumerate(
            [
                nodes[node_id]
                for node_id in nodes[document["root_id"]].get("children", [])
                if nodes[node_id]["node_class"] == "part"
            ],
            1,
        )
    }
    starts = _chapter_starts()
    chapter_rows: dict[int, list[tuple[str, int]]] = defaultdict(list)
    for node in document["nodes"]:
        if node["node_class"] != "chapter":
            continue
        part = part_numbers.get(parents.get(node["node_id"], ""))
        key = (part, node["designation"])
        if part is None or key not in starts:
            raise RuntimeError(
                f"current chapter {node['node_id']!r} has no scan-page identity"
            )
        chapter_rows[part].append((node["node_id"], starts[key]))

    last_scan = pages_doc["_last_scan_page"]
    first_preface = next(
        row["start_scan"] for row in pages_doc["chapters"] if row["id"] == "prefazione"
    )
    first_chapter = min(start for rows in chapter_rows.values() for _, start in rows)
    node_pages: dict[str, list[list[int]]] = {
        document["root_id"]: [[1, last_scan]],
    }
    for node in document["nodes"]:
        if node["node_class"] == "front-matter":
            node_pages[node["node_id"]] = [[1, first_preface - 1]]
        elif node["node_class"] == "preface":
            node_pages[node["node_id"]] = [[first_preface, first_chapter - 1]]

    ordered_parts = sorted(chapter_rows)
    for part_index, part in enumerate(ordered_parts):
        rows = chapter_rows[part]
        if any(right[1] <= left[1] for left, right in zip(rows, rows[1:])):
            raise RuntimeError(
                f"current part {part} chapters are not in increasing scan order"
            )
        part_end = (
            chapter_rows[ordered_parts[part_index + 1]][0][1] - 1
            if part_index + 1 < len(ordered_parts)
            else last_scan
        )
        node_pages[
            next(node_id for node_id, number in part_numbers.items() if number == part)
        ] = [[rows[0][1], part_end]]
        for row_index, (node_id, start) in enumerate(rows):
            end = rows[row_index + 1][1] - 1 if row_index + 1 < len(rows) else part_end
            node_pages[node_id] = [[start, end]]

    human_ids = {
        node["node_id"]
        for node in document["nodes"]
        if node.get("minted_by") == "human"
    }
    if set(node_pages) != human_ids:
        missing = sorted(human_ids - set(node_pages))
        raise RuntimeError(
            f"scan-page registration does not cover human nodes: {missing}"
        )
    return node_pages


def main() -> None:
    document = read_json(REGISTRATION)
    matches = [
        source
        for source in document["sources"]
        if source["source_id"] == MAPPED_SOURCE_ID
    ]
    if len(matches) != 1:
        raise RuntimeError(f"expected one registered source {MAPPED_SOURCE_ID!r}")
    for source in document["sources"]:
        if source["source_id"] == MAPPED_SOURCE_ID:
            source["node_pages"] = _node_pages()
        else:
            # Different witnesses require independently registered pagination.
            source.pop("node_pages", None)
    atomic_write_json(REGISTRATION, document)
    print(
        f"registered {len(matches[0]['node_pages'])} node ranges for {MAPPED_SOURCE_ID}"
    )


if __name__ == "__main__":
    main()
