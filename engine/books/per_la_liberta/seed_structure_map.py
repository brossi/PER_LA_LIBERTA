"""S4.6b — seed the PLL candidate structure map (s4_6_tooling_plan T-1/DT-3; issue #34).

Drafts ``<work>/structure_map.json`` (map_revision 0) from the frozen atom streams + the known
skeleton, for Ben to review and correct in the S4.6 HITL loop. The draft is a **candidate**, not a
recognition result (D28/D29): heading candidates are matched exact-first against the skeleton's
expected chapter titles, garbled headings fall back to a flagged fuzzy match, and anything the
matcher cannot place it **abstains on** — the chapter is simply not seeded, and the flag says so.
Every anomaly (duplicate headings from running heads / the end-matter index, garbled ordinals,
out-of-order sightings, unplaced chapters) is emitted in the stdout report and, for fuzzy matches,
marked on the node's ``title`` for in-editor visibility.

Where the skeleton comes from: the expected chapter titles ride in the frozen
``inputs/reconciled_chapters.json`` (24 P1 + 33 P2 + prefazione), and the part names/counts are
cross-checked against the book manifest's declared ``structure.parts``. Heading candidates come
from the canonical atom stream itself.

Every container is ``minted_by: human`` (MINTED_BY_SPLIT requires it — the human ratifies each in
S4.6) with ``decision: plugin-suggested`` **written, never read** (inv 25 stays unbreached: the S4
gate keys on evidence only, so the draft fails the evidence gate all-``missing`` until Ben has
worked every container — that failing worklist IS the S4.6 TODO list). Coverage is total by
construction: every canonical atom lands in exactly one node slot (front matter and the end-matter
index included — the index is NOT segmented off, it rides inside the last chapter's span with a
flag, because drawing that boundary is a judgment call, not a match).

The manifest is stamped honestly: the real ``ResourceLineage.build`` over the resolved book config
(live dictionary hashes), ``profile_version`` marked pre-S9 (no structure profile exists yet —
S9.1 owns those), ``recognizer_version`` ``none-pre-s9`` (no recognizer ran; this seeder is not
one).

Re-seed protection (DT-3): the first write is free; a re-run against an existing map hits the
regen-guarded writer's ``MAP_OVERWRITE_BLOCKED`` with **no escape** — re-seeding after hand edits
requires a human to delete the draft first. Deliberate.

Usage (from ``engine/``):  uv run python books/per_la_liberta/seed_structure_map.py
"""

from __future__ import annotations

import difflib
import json
import re
from pathlib import Path

from engine.config.loader import load_book
from engine.paths import BookWorkspace
from engine.structure import (
    STRUCTURE_MAP_SCHEMA_VERSION,
    AtomStream,
    StreamAtomReader,
    assert_freeze_matches,
    build_manifest,
    load_freeze_record,
    load_structure_map,
    load_workspace_streams,
    mint_node_id,
    write_structure_map,
)
from engine.structure.lineage import ResourceLineage

BOOK_DIR = Path(__file__).resolve().parent
BOOKS_DIR = BOOK_DIR.parent
INPUTS = BOOK_DIR / "inputs"
FREEZE_PATH = BOOK_DIR / "stream_freeze.json"
BOOK_ID = "per_la_liberta"
CANONICAL_ID = "canonical"

#: Fuzzy floor for a garbled-heading match ('Capitolo Qyarto' ≈ 'Capitolo Quarto'). Exact matches
#: are always preferred over ANY fuzzy candidate — fuzzy ratios between neighbouring ordinals
#: ('Undicesimo'/'Dodicesimo') run high enough that fuzzy-first would mis-assign boundaries.
FUZZY_THRESHOLD = 0.72
#: A heading is a short line; a body paragraph that merely *starts* with 'Capitolo…' is not one.
MAX_HEADING_NORM_LEN = 34

_NORM_RE = re.compile(r"[^a-zàèéìíòóùú]")


def _norm(text: str) -> str:
    """Lowercase, letters only — collapses the 1913 printing's double spaces, the OCR's stray
    punctuation, and the index's trailing page numbers ('Prefazione 1' → 'prefazione')."""
    return _NORM_RE.sub("", text.lower())


def _heading_candidates(atoms) -> list[tuple[int, str, str, str]]:
    """Every atom that *looks like* a structural heading: ``(index, atom_id, norm, raw)``.

    Deliberately over-inclusive (running heads, the end-matter index, garbles all land here) —
    the assigner consumes what it can place and FLAGS the rest; nothing is silently resolved.
    """
    out = []
    for i, atom in enumerate(atoms):
        norm = _norm(atom.text)
        if not norm or len(norm) > MAX_HEADING_NORM_LEN:
            continue
        is_chapter = norm.startswith("capitolo")
        is_preface = norm.startswith("prefazione") and len(norm) <= len("prefazione") + 2
        is_part = norm.startswith("parte") and (
            difflib.SequenceMatcher(None, norm, "parteprima").ratio() >= FUZZY_THRESHOLD
            or difflib.SequenceMatcher(None, norm, "parteseconda").ratio() >= FUZZY_THRESHOLD
        )
        if is_chapter or is_preface or is_part:
            out.append((i, atom.atom_id, norm, atom.text.strip()))
    return out


def _pick_anchor(
    candidates: list, want: str, *, after: int, flags: list[str], label: str
) -> tuple[int, str] | None:
    """The first exact-normalized match for a unique structural anchor (prefazione / part
    headings); later duplicates (running heads, the index) are flagged, an absent anchor abstains
    with a flag."""
    matches = [c for c in candidates if c[2] == want and c[0] > after]
    if not matches:
        flags.append(f"{label}: no heading atom located — seeded without one; REVIEW by hand")
        return None
    first = matches[0]
    for dup in matches[1:]:
        flags.append(
            f"{label}: duplicate heading-like atom {dup[1]} ({dup[3]!r}) not used as a boundary "
            f"(running head or index entry?) — REVIEW"
        )
    return first[0], first[1]


def _assign_chapters(
    expected_titles: list[str],
    candidates: list,
    *,
    start: int,
    end: int,
    flags: list[str],
    part_label: str,
) -> list[dict]:
    """Walk the skeleton's expected titles in order, binding each to a candidate heading atom —
    exact match anywhere ahead in the window first (this is what steps OVER an out-of-order
    running-head sighting), best fuzzy above threshold second (flagged), abstention third (the
    chapter is not seeded; flagged). Boundaries are ascending by construction (each search starts
    after the previous match).

    Fuzzy guard: a fuzzy match may NEVER consume a candidate whose norm exactly matches a
    *different* expected chapter's heading — Italian ordinals sit close enough
    ('Ventesimo Secondo' vs 'Trentesimo Secondo' ≈ 0.94) that without this, one truly-absent
    heading would steal a later chapter's atom, advance the cursor past it, and cascade every
    following chapter into abstention (observed live on P2 ch22 before the guard)."""
    assigned: list[dict] = []
    consumed: set[int] = set()
    expected_norms = {_norm(t) for t in expected_titles}
    prev = start
    for title in expected_titles:
        want = _norm(title)
        window = [c for c in candidates if prev < c[0] < end and c[0] not in consumed]
        chosen = next((c for c in window if c[2] == want), None)
        fuzzy_note = None
        if chosen is None:
            fuzzable = [c for c in window if c[2] not in expected_norms - {want}]
            scored = sorted(
                ((difflib.SequenceMatcher(None, want, c[2]).ratio(), c) for c in fuzzable),
                key=lambda pair: (-pair[0], pair[1][0]),
            )
            if scored and scored[0][0] >= FUZZY_THRESHOLD:
                ratio, chosen = scored[0]
                fuzzy_note = f"fuzzy heading match {chosen[3]!r} (ratio {ratio:.2f})"
                flags.append(f"{part_label} {title!r}: {fuzzy_note} at {chosen[1]} — REVIEW")
        if chosen is None:
            flags.append(
                f"{part_label} {title!r}: NO heading located — chapter NOT seeded; place it by "
                f"hand (abstain, DT-3)"
            )
            continue
        consumed.add(chosen[0])
        assigned.append(
            {"title": title, "index": chosen[0], "atom_id": chosen[1], "fuzzy": fuzzy_note}
        )
        prev = chosen[0]
    for unused in (c for c in candidates if start < c[0] < end and c[0] not in consumed):
        flags.append(
            f"{part_label}: heading-like atom {unused[1]} ({unused[3]!r}) not used as a boundary "
            f"— REVIEW (duplicate copy segment, running head, or index entry)"
        )
    return assigned


def build_draft(streams: dict[str, AtomStream], cfg=None) -> tuple[dict, list[str]]:
    """Assemble the candidate map document + the anomaly flags — pure (no disk writes), so the
    lockstep test can hold it against the frozen streams without touching the workspace."""
    cfg = cfg or load_book(BOOK_ID)
    flags: list[str] = []
    atoms = streams[CANONICAL_ID].atoms
    atom_ids = [a.atom_id for a in atoms]
    candidates = _heading_candidates(atoms)

    skeleton = json.loads((INPUTS / "reconciled_chapters.json").read_text(encoding="utf-8"))
    part_titles = {
        1: [e["title"] for e in skeleton if e["part"] == 1],
        2: [e["title"] for e in skeleton if e["part"] == 2],
    }
    declared = {i + 1: p.chapters for i, p in enumerate(cfg.structure.parts)}
    for part_number, titles in part_titles.items():
        if len(titles) != declared[part_number]:
            flags.append(
                f"skeleton/manifest disagree on part {part_number}: {len(titles)} reconciled "
                f"chapters vs {declared[part_number]} declared — REVIEW"
            )

    preface = _pick_anchor(candidates, "prefazione", after=-1, flags=flags, label="Prefazione")
    preface_at = preface[0] if preface else -1
    part2 = _pick_anchor(
        candidates, "parteseconda", after=preface_at, flags=flags, label="Parte Seconda"
    )
    part2_at = part2[0] if part2 else len(atoms)
    part1 = _pick_anchor(candidates, "parteprima", after=preface_at, flags=flags, label="Parte Prima")
    if part1 and part1[0] > part2_at:
        flags.append(
            f"Parte Prima: only heading-like match sits AFTER Parte Seconda (the end-matter "
            f"index?) at {part1[1]} — not used; part seeded without a heading atom; REVIEW"
        )
        part1 = None
    chapter_pool = [c for c in candidates if c[2].startswith("capitolo")]
    p1_chapters = _assign_chapters(
        part_titles[1], chapter_pool, start=preface_at, end=part2_at, flags=flags,
        part_label="Parte Prima",
    )
    p2_chapters = _assign_chapters(
        part_titles[2], chapter_pool, start=part2_at, end=len(atoms), flags=flags,
        part_label="Parte Seconda",
    )
    if p2_chapters:
        flags.append(
            f"end matter (the printed index) is NOT segmented off — it rides inside the last "
            f"chapter's span after {p2_chapters[-1]['atom_id']}; split it by hand (abstain, DT-3)"
        )

    # --- events → spans: every atom between one heading and the next belongs to the earlier ---- #
    human = iter(range(10_000)).__next__
    machine = iter(range(10_000)).__next__
    nodes: list[dict] = []

    def _leaf(span_ids: list[str]) -> str | None:
        if not span_ids:
            return None
        node_id = mint_node_id("machine", machine())
        nodes.append(
            {
                "node_id": node_id,
                "node_class": "prose",
                "minted_by": "machine",
                "body_atoms": span_ids,
            }
        )
        return node_id

    def _container(node_class: str, designation: str, title: str, heading: list[str]) -> dict:
        node = {
            "node_id": mint_node_id("human", human()),
            "node_class": node_class,
            "minted_by": "human",
            "children": [],
            "designation": designation,
            "title": title,
            "decision": "plugin-suggested",
        }
        if heading:
            node["heading_atoms"] = heading
        nodes.append(node)
        return node

    events: list[dict] = []  # ordered structural anchors, each owning the gap to the next
    if preface:
        events.append({"kind": "preface", "index": preface[0], "atom_id": preface[1]})
    if part1:
        events.append({"kind": "part", "part": 1, "index": part1[0], "atom_id": part1[1]})
    for ch in p1_chapters:
        events.append({"kind": "chapter", "part": 1, "index": ch["index"], **ch})
    if part2:
        events.append({"kind": "part", "part": 2, "index": part2[0], "atom_id": part2[1]})
    for ch in p2_chapters:
        events.append({"kind": "chapter", "part": 2, "index": ch["index"], **ch})
    events.sort(key=lambda e: e["index"])
    for event, following in zip(events, [*events[1:], {"index": len(atoms)}]):
        event["gap"] = atom_ids[event["index"] + 1 : following["index"]]

    root = _container("volume", cfg.manifest.title, cfg.manifest.title, [])
    front_span = atom_ids[0 : events[0]["index"]] if events else list(atom_ids)
    if front_span:
        front = _container("front-matter", "Front matter", "Front matter", [])
        front["children"] = [leaf for leaf in (_leaf(front_span),) if leaf]
        root["children"].append(front["node_id"])
    part_nodes: dict[int, dict] = {}

    def _part(number: int) -> dict:
        # lazy, so the flat node table lands in reading order even when a part's heading atom was
        # never located (Parte Prima) — the container materializes at its first chapter instead
        if number not in part_nodes:
            name = cfg.structure.parts[number - 1].name
            part_nodes[number] = _container("part", name, name, [])
        return part_nodes[number]

    preface_node = None
    for event in events:
        if event["kind"] == "preface":
            preface_node = _container(
                "preface", "Prefazione", "Prefazione", [event["atom_id"]]
            )
            leaf = _leaf(event["gap"])
            if leaf:
                preface_node["children"].append(leaf)
        elif event["kind"] == "part":
            part = _part(event["part"])
            part["heading_atoms"] = [event["atom_id"]]
            leaf = _leaf(event["gap"])
            if leaf:
                part["children"].append(leaf)
        else:
            part = _part(event["part"])
            title = event["title"] + (" [REVIEW: fuzzy heading]" if event["fuzzy"] else "")
            chapter = _container("chapter", event["title"], title, [event["atom_id"]])
            leaf = _leaf(event["gap"])
            if leaf:
                chapter["children"].append(leaf)
            part["children"].append(chapter["node_id"])
    if preface_node:
        root["children"].append(preface_node["node_id"])
    for number in sorted(part_nodes):
        root["children"].append(part_nodes[number]["node_id"])

    used_classes = {n["node_class"] for n in nodes}
    vocabulary = [
        {"name": name, "kind": kind, "status": "active"}
        for name, kind in (
            ("volume", "container"),
            ("front-matter", "container"),
            ("preface", "container"),
            ("part", "container"),
            ("chapter", "container"),
            ("prose", "leaf"),
        )
        if name in used_classes
    ]
    doc = {
        "schema_version": STRUCTURE_MAP_SCHEMA_VERSION,
        "root_id": root["node_id"],
        "map_revision": 0,
        "block_vocabulary": vocabulary,
        "handle_policies": {entry["name"]: "position-path" for entry in vocabulary},
        "furniture_atoms": [],
        "aliases": [],
        "manifest": build_manifest(
            streams=streams,
            canonical_stream_id=CANONICAL_ID,
            resource_lineage=ResourceLineage.build(cfg),
            # No structure profile exists yet (S9.1 owns those) and no recognizer ran (this
            # seeder is a candidate generator, not a recognizer — D28): both stamped honestly.
            profile_version=f"pre-s9-manifest:{cfg.manifest.schema_version}",
            recognizer_version="none-pre-s9",
        ),
        "nodes": nodes,
    }
    return doc, flags


def main() -> int:
    record = load_freeze_record(FREEZE_PATH)
    workspace = BookWorkspace.for_book(BOOK_ID, BOOKS_DIR)
    streams = load_workspace_streams(workspace, canonical_stream_id=CANONICAL_ID)
    assert_freeze_matches(record, streams)  # never seed against a drifted substrate
    doc, flags = build_draft(streams)
    path = write_structure_map(workspace, doc)  # first write only — re-seed needs a human delete
    smap = load_structure_map(path, StreamAtomReader(streams, CANONICAL_ID))
    containers = sum(1 for n in smap.projection.nodes if n.minted_by == "human")
    chapters = sum(1 for n in smap.projection.nodes if n.node_class == "chapter")
    print(f"seeded {path}")
    print(
        f"  {len(smap.projection.nodes)} nodes: {containers} containers "
        f"({chapters} chapters) — map_revision 0, all decision=plugin-suggested"
    )
    print(f"  validates clean over the frozen streams ({len(streams[CANONICAL_ID].atoms)} atoms covered)")
    if flags:
        print(f"\n{len(flags)} review flag(s) — work these in the S4.6 loop:")
        for flag in flags:
            print(f"  - {flag}")
    print(
        "\nnext: uv run python -m engine.structure.authoring --book per_la_liberta status "
        "(the all-missing worklist), then verify + stamp container by container"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
