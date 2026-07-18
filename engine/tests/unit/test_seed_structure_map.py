"""S4.6b — the PLL candidate-map seeder, in lockstep with the frozen substrate
(s4_6_tooling_plan T-1/DT-3 + §4 rows 15-18; issue #34).

The seeder is a book-side script (``books/per_la_liberta/seed_structure_map.py``), so this test
imports it by path (the ``test_stream_freeze`` pattern) and recaptures the streams through the
SAME recipe that test holds against the committed pin — then asserts:

- the draft loads CLEAN through the real ``load_structure_map`` over those streams (Tier-1 +
  Tier-2: full atom coverage, ownership, ordering, vocab hygiene — ``UNOWNED_INCLUDED_ATOM``
  would red here if the seeder dropped a single span, plan §4 row 16);
- known boundary pins hold (the prefazione heading atom, Part 1 Chapter 1's heading atom) — the
  assignment is deterministic over the frozen inputs, not merely shape-valid;
- the draft posture is DT-3's: every container ``minted_by: human`` + ``decision:
  plugin-suggested`` (written, never read), ``map_revision`` 0, and the fresh draft fails the
  evidence gate all-``missing`` (the S4.6 worklist state, plan §4 row 18);
- anomalies are FLAGGED, never silently resolved (plan §4 row 17): the duplicate headings
  (running heads / the end-matter index), any fuzzy garble matches, and the deliberately
  unsegmented end matter all surface in the flag report.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from engine.structure import (
    AuthoringEvidence,
    StreamAtomReader,
    assert_freeze_matches,
    evidence_findings,
    load_freeze_record,
    load_structure_map,
    render_structure_map,
)

HERE = Path(__file__).resolve()
ENGINE_ROOT = HERE.parents[2]
BOOK_DIR = ENGINE_ROOT / "books" / "per_la_liberta"
SEEDER_PATH = BOOK_DIR / "seed_structure_map.py"
FREEZE_TEST_PATH = HERE.parent / "test_stream_freeze.py"


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SEEDER = _load_module(SEEDER_PATH, "seed_structure_map")
#: The freeze test owns THE capture recipe (its tripwire holds it against the committed pin);
#: reusing it here means a capture drift breaks both coherently instead of this test silently
#: seeding from a different substrate.
FREEZE_LOCKSTEP = _load_module(FREEZE_TEST_PATH, "_freeze_lockstep_for_seeder")


@pytest.fixture(scope="module")
def streams():
    return FREEZE_LOCKSTEP._pll_streams()


@pytest.fixture(scope="module")
def draft(streams):
    return SEEDER.build_draft(streams)


def test_capture_matches_the_committed_pin(streams):
    # Anchor: the streams this test seeds from ARE the pinned substrate — otherwise every
    # assertion below would hold against something the authored map will never reference.
    assert_freeze_matches(load_freeze_record(BOOK_DIR / "stream_freeze.json"), streams)


def test_draft_validates_clean_over_the_frozen_streams(tmp_path, streams, draft):
    doc, _ = draft
    path = tmp_path / "structure_map.json"
    path.write_text(render_structure_map(doc), encoding="utf-8")
    # Tier-1 + Tier-2 with zero findings — full coverage included: every one of the canonical
    # atoms is owned exactly once (a dropped span reds as UNOWNED_INCLUDED_ATOM, §4 row 16).
    smap = load_structure_map(path, StreamAtomReader(streams, "canonical"))
    assert smap.map_revision == 0
    assert len(smap.projection.by_id) == len(doc["nodes"])


def test_known_boundary_pins_hold(draft):
    doc, _ = draft
    preface = next(n for n in doc["nodes"] if n["node_class"] == "preface")
    assert preface["heading_atoms"] == ["canonical_00089"]
    first_chapter = next(n for n in doc["nodes"] if n["node_class"] == "chapter")
    assert first_chapter["designation"] == "Capitolo Primo"
    assert first_chapter["heading_atoms"] == ["canonical_00103"]
    part2 = next(
        n for n in doc["nodes"] if n["node_class"] == "part" and n["designation"] == "Parte Seconda"
    )
    assert part2["heading_atoms"] == ["canonical_02237"]
    # Parte Prima's body heading was never printed legibly enough to survive OCR — the container
    # exists WITHOUT a heading atom (abstain, not guess), and the flags say so (asserted below).
    part1 = next(
        n for n in doc["nodes"] if n["node_class"] == "part" and n["designation"] == "Parte Prima"
    )
    assert "heading_atoms" not in part1


def test_draft_posture_is_dt3(draft):
    doc, _ = draft
    containers = [n for n in doc["nodes"] if "children" in n]
    leaves = [n for n in doc["nodes"] if "body_atoms" in n]
    assert containers and leaves
    assert all(n["minted_by"] == "human" for n in containers)
    assert all(n["decision"] == "plugin-suggested" for n in containers)
    assert all(n["minted_by"] == "machine" and "decision" not in n for n in leaves)
    assert doc["map_revision"] == 0
    assert doc["furniture_atoms"] == [] and doc["aliases"] == []
    assert doc["manifest"]["recognizer_version"] == "none-pre-s9"


def test_fresh_draft_fails_the_evidence_gate_all_missing(tmp_path, streams, draft):
    # Plan §4 row 18: the seeded draft + an empty sidecar = every container `missing` — the
    # worklist Ben works down in S4.6. The gate flipping green IS S4.6 completion.
    doc, _ = draft
    path = tmp_path / "structure_map.json"
    path.write_text(render_structure_map(doc), encoding="utf-8")
    smap = load_structure_map(path, StreamAtomReader(streams, "canonical"))
    findings = evidence_findings(
        AuthoringEvidence(book="per_la_liberta", entries=()), smap.projection
    )
    containers = [n for n in doc["nodes"] if "children" in n]
    assert [kind for kind, _ in findings] == ["missing"] * len(containers)


def test_anomalies_are_flagged_never_silently_resolved(draft):
    doc, flags = draft
    assert flags, "the PLL substrate is known-noisy — a flagless seed means anomalies were eaten"
    # duplicate headings (running heads / duplicated copy segments / the index) surface by id —
    # including plan §4 row 17's named case, the duplicate 'Capitolo Sesto' sightings
    assert any("not used as a boundary" in flag for flag in flags)
    assert any("Sesto" in flag and "not used as a boundary" in flag for flag in flags)
    # the end matter is deliberately NOT segmented off (a judgment call, not a match)
    assert any("end matter" in flag for flag in flags)
    # Parte Prima's missing body heading is stated, not papered over
    assert any("Parte Prima" in flag and "heading" in flag for flag in flags)
    # every fuzzy (garbled-ordinal) assignment is BOTH flagged and title-marked for the editor
    fuzzy_flags = [flag for flag in flags if "fuzzy heading match" in flag]
    marked_titles = [
        n["title"]
        for n in doc["nodes"]
        if n.get("title", "").endswith("[REVIEW: fuzzy heading]")
    ]
    assert len(fuzzy_flags) == len(marked_titles)


def test_chapter_seeding_is_deterministic_and_abstains_on_the_unplaceable(draft):
    doc, flags = draft
    chapters = [n for n in doc["nodes"] if n["node_class"] == "chapter"]
    unplaced = [flag for flag in flags if "NO heading located" in flag]
    # exact-first assignment over the frozen substrate is deterministic: 57 expected chapters
    # split between seeded containers and explicit abstentions, nothing dropped silently
    assert len(chapters) + len(unplaced) == 57
    # Pinned to the frozen substrate: 56 placed; ONE honest abstention — P2 ch22, whose heading
    # atom genuinely does not survive in the canonical stream. Before the fuzzy guard, this one
    # absent heading stole ch32's atom ('Trentesimo Secondo', ratio 0.94) and cascaded ch24-33
    # into abstention — the pin holds the guard in place.
    assert len(chapters) == 56
    assert len(unplaced) == 1 and "Ventesimo Secondo" in unplaced[0]
    fuzzy = [flag for flag in flags if "fuzzy heading match" in flag]
    assert len(fuzzy) == 1 and "Dccimoscttimo" in fuzzy[0]  # the one true garble, flagged
