"""S4.6-pre — freeze + persist the PLL atom streams (issue #31; ENGINE_STRUCTURE_TASKS S4.6-pre).

Captures the committed witnesses (``inputs/copy{1,2,3}_raw.txt``) through the live producers,
persists the four streams (three witnesses + the canonical projection) into the gitignored,
disposable book workspace for authoring use, and writes the **committed** hash pin
``stream_freeze.json`` beside this script. The pin — not the workspace — is the durable substrate:
``tests/unit/test_stream_freeze.py`` recaptures the inputs on every run and holds them against it,
so a capture change that renumbers atom ids reds the suite instead of silently orphaning the
hand-authored structure map (S4.6) that references those ids.

The ``⟨PAGE:N⟩`` grammar below is the PLL copy3 per-book binding — the same literals as the
tripwire test's; the tripwire machine-checks the two sites agree (a drifted script would write
hashes the test's recapture cannot reproduce).

Usage (from ``engine/``):  uv run python books/per_la_liberta/freeze_streams.py [--force]

``--force`` is required to replace an existing pin that differs — explicit human intent, because
an authored map may already reference the pinned ids.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from engine.paths import BookWorkspace
from engine.structure import (
    AtomStream,
    build_canonical,
    build_freeze_record,
    capture_witness,
    gap_records,
    marker_page_binding,
    save_stream,
    write_freeze_record,
)

BOOK_DIR = Path(__file__).resolve().parent
BOOKS_DIR = BOOK_DIR.parent
INPUTS = BOOK_DIR / "inputs"
FREEZE_PATH = BOOK_DIR / "stream_freeze.json"

PAGE_MARKER = re.compile(r"⟨PAGE:(\d+)⟩")


def _read(name: str) -> str:
    path = INPUTS / name
    if not path.is_file():
        raise SystemExit(f"frozen PLL input missing: {path}")
    text = path.read_text(encoding="utf-8")
    if not text:
        raise SystemExit(f"{name} is empty — refusing to freeze a vacuous stream")
    return text


def main() -> None:
    parser = argparse.ArgumentParser(description="Freeze + persist the PLL atom streams (S4.6-pre)")
    parser.add_argument(
        "--force",
        action="store_true",
        help="replace an existing, differing stream_freeze.json (verify the drift is intentional "
        "and re-verify any authored structure map first)",
    )
    args = parser.parse_args()

    t1, t2, t3 = _read("copy1_raw.txt"), _read("copy2_raw.txt"), _read("copy3_raw.txt")
    page_map = json.loads((INPUTS / "copy3_pro_page_map.json").read_text(encoding="utf-8"))
    if not page_map:
        raise SystemExit("copy3 page map is empty")
    classify_line, page_of = marker_page_binding(t3, marker=PAGE_MARKER, page_map=page_map)

    a1 = capture_witness(t1, "copy1")
    a2 = capture_witness(t2, "copy2")
    a3 = capture_witness(t3, "copy3", classify_line=classify_line, page_of=page_of)
    canon = build_canonical({"copy1": a1, "copy2": a2}, ["copy1", "copy2"])

    streams = {
        "copy1": AtomStream.witness("copy1", a1, gap_records(a1, t1), t1),
        "copy2": AtomStream.witness("copy2", a2, gap_records(a2, t2), t2),
        "copy3": AtomStream.witness("copy3", a3, gap_records(a3, t3), t3),
        "canonical": AtomStream.canonical(canon),
    }

    workspace = BookWorkspace.for_book("per_la_liberta", BOOKS_DIR).ensure()
    for stream in streams.values():
        path = save_stream(workspace, stream)
        print(f"persisted {stream.stream_id:<10} {len(stream.atoms):>5} atoms -> {path}")

    record = build_freeze_record(streams, book="per_la_liberta")
    write_freeze_record(FREEZE_PATH, record, force=args.force)
    print(f"\nfreeze pin -> {FREEZE_PATH}")
    for entry in record["streams"]:
        print(f"  {entry['id']:<10} {entry['kind']:<9} atoms={entry['atom_count']:>5}  {entry['envelope_hash']}")


if __name__ == "__main__":
    main()
