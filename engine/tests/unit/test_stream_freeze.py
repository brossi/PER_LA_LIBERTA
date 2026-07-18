"""S4.6-pre — the stream freeze: a committed hash pin over the PLL atom streams (issue #31).

Canonical atom ids are **positional** (``canonical_NNNNN`` in capture order): a capture-algorithm
change silently renumbers the stream, and the S4.6 hand-authored map references those ids *before*
S5's re-bind machinery exists. The book workspace is disposable (gitignored), so the durable pin is
the committed record ``books/<id>/stream_freeze.json``: one envelope hash per stream — the SAME
producer value ``build_manifest`` stamps into ``manifest.atom_streams[*].hash`` — plus each
witness's ``source_hash`` anchor and the atom count.

Tiers (each proven red, PLAN §9):

- **synthetic battery** over ``structure.freeze`` — record shape, the single-producer hash pin,
  render/load round-trip, the total load contract, the deny-by-default writer guard, and every
  drift axis of ``assert_freeze_matches`` failing loud **naming the stream**
- **manifest coherence** — freeze envelope hashes == ``build_manifest``'s ``atom_streams`` hashes
  over the same streams (one producer, never a re-implementation)
- **the PLL tripwire** — recapture the committed inputs through the live producers and hold them
  against the committed freeze record. This is the invariant the task exists for: a capture change
  reds HERE, instead of silently orphaning an authored map. Hard-asserted, never skipped (a skipif
  would turn the freeze silently green on a fresh clone).

The ``⟨PAGE:N⟩`` grammar + page-map literals below are the PLL copy3 per-book binding — duplicated
(by design) in ``books/per_la_liberta/freeze_streams.py``; this tripwire machine-checks the two
sites agree, because a drifted script would have written hashes this recapture cannot reproduce.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from engine.errors import MissingInputError, StaleArtifactError
from engine.structure import (
    AtomStream,
    assert_freeze_matches,
    build_canonical,
    build_freeze_record,
    build_manifest,
    capture_witness,
    gap_records,
    load_freeze_record,
    marker_page_binding,
    render_freeze_record,
    write_freeze_record,
)
from engine.structure.artifacts import (
    NORMALIZER_STALE_CLASS,
    RESOURCE_STALE_CLASS,
    STREAM_FREEZE_SCHEMA_VERSION,
)
from engine.structure.atom_store import to_json as stream_envelope_json
from engine.structure.lineage import ResourceLineage, _canonical, _sha256_bytes
from engine.structure.structure_map import _hash_canonical

BOOK = Path(__file__).resolve().parents[2] / "books" / "per_la_liberta"
INPUTS = BOOK / "inputs"
FREEZE = BOOK / "stream_freeze.json"

PAGE_MARKER = re.compile(r"⟨PAGE:(\d+)⟩")


# --- synthetic substrate ------------------------------------------------------------------ #

W1 = "Alpha block one.\n\nBeta block two.\n\nGamma block three.\n"
W2 = "Alpha block one.\n\nBeta blok two.\n\nGamma block three.\n"


def _streams(t1: str = W1, t2: str = W2) -> dict[str, AtomStream]:
    a1 = capture_witness(t1, "w1")
    a2 = capture_witness(t2, "w2")
    canon = build_canonical({"w1": a1, "w2": a2}, ["w1", "w2"])
    return {
        "w1": AtomStream.witness("w1", a1, gap_records(a1, t1), t1),
        "w2": AtomStream.witness("w2", a2, gap_records(a2, t2), t2),
        "canonical": AtomStream.canonical(canon),
    }


def _lineage() -> ResourceLineage:
    resource = _canonical({"oracle_min": 2, "frequency": None, "members": []})
    normalizer = _canonical({"case_fold": False, "accent_fold": False})
    return ResourceLineage(
        resource_version=_sha256_bytes(resource.encode("utf-8")),
        resource_descriptor=resource,
        resource_stale_class=RESOURCE_STALE_CLASS,
        normalizer_version=_sha256_bytes(normalizer.encode("utf-8")),
        normalizer_descriptor=normalizer,
        normalizer_stale_class=NORMALIZER_STALE_CLASS,
    )


# --- record shape + the single-producer hash pin ------------------------------------------ #


def test_record_shape_streams_sorted_witness_anchored():
    streams = _streams()
    record = build_freeze_record(streams, book="testbook")
    assert record["stream_freeze_schema_version"] == STREAM_FREEZE_SCHEMA_VERSION
    assert record["book"] == "testbook"
    ids = [entry["id"] for entry in record["streams"]]
    assert ids == sorted(ids) == ["canonical", "w1", "w2"]
    by_id = {entry["id"]: entry for entry in record["streams"]}
    assert by_id["w1"]["kind"] == "witness"
    assert by_id["canonical"]["kind"] == "canonical"
    assert by_id["w1"]["atom_count"] == 3
    assert by_id["w1"]["source_hash"] == streams["w1"].source_hash
    # a canonical stream tiles no single source — it carries no anchor, and the record must not
    # invent one (the AtomStream model guard's shape, mirrored in the pin)
    assert "source_hash" not in by_id["canonical"]


def test_envelope_hash_is_the_manifest_producer_not_a_reimplementation():
    # I5/D-S4-I: the pin's hash IS _hash_canonical over the persisted envelope (atom_store.to_json)
    # — recomputed here through those exact producers, so a freeze-side re-serialization reds.
    streams = _streams()
    record = build_freeze_record(streams, book="b")
    for entry in record["streams"]:
        assert entry["envelope_hash"] == _hash_canonical(stream_envelope_json(streams[entry["id"]]))


def test_freeze_hashes_equal_build_manifest_stream_hashes():
    # The design point: the committed pin and the authored map's manifest carry the SAME values,
    # so freeze <-> manifest agreement is directly comparable at the S4.6 gate and under S8.1.
    streams = _streams()
    record = build_freeze_record(streams, book="b")
    manifest = build_manifest(
        streams=streams,
        canonical_stream_id="canonical",
        resource_lineage=_lineage(),
        profile_version="profile-test-1",
        recognizer_version="recognizer-test-1",
    )
    assert {e["id"]: e["envelope_hash"] for e in record["streams"]} == {
        e["id"]: e["hash"] for e in manifest["atom_streams"]
    }


def test_build_freeze_record_rejects_empty_and_mislabeled_streams():
    with pytest.raises(ValueError, match="no streams"):
        build_freeze_record({}, book="b")
    streams = _streams()
    # a mapping key that contradicts the stream's own id would pin a lie — refused at build
    with pytest.raises(ValueError, match="wrong-key"):
        build_freeze_record({"wrong-key": streams["w1"]}, book="b")


# --- render / load: byte-stable artifact, total load contract ----------------------------- #


def test_render_load_round_trip_and_byte_idempotence(tmp_path):
    record = build_freeze_record(_streams(), book="b")
    path = tmp_path / "stream_freeze.json"
    path.write_text(render_freeze_record(record), encoding="utf-8")
    assert load_freeze_record(path) == record
    # content-derived only (no timestamp): re-rendering the same streams is byte-identical, so a
    # no-drift regeneration is an empty git diff
    assert render_freeze_record(build_freeze_record(_streams(), book="b")) == render_freeze_record(record)


# One VALID entry, so each malformed case below differs from loadable in exactly its own axis —
# a case that is broken two ways (e.g. bad version AND empty streams) would let a dropped check
# hide behind the other one (the mutation hunt caught exactly that masking on the version axis).
_VALID_ENTRY = '{"id": "w1", "kind": "witness", "atom_count": 1, "envelope_hash": "h", "source_hash": "s"}'


@pytest.mark.parametrize(
    "doc",
    [
        "not json {",
        "[]",
        '{"book": "b", "streams": [' + _VALID_ENTRY + "]}",
        '{"stream_freeze_schema_version": 999, "book": "b", "streams": [' + _VALID_ENTRY + "]}",
        '{"stream_freeze_schema_version": 1, "streams": [' + _VALID_ENTRY + "]}",
        '{"stream_freeze_schema_version": 1, "book": "b"}',
        '{"stream_freeze_schema_version": 1, "book": "b", "streams": []}',
        '{"stream_freeze_schema_version": 1, "book": "b", "streams": [{"id": "w1"}]}',
        '{"stream_freeze_schema_version": 1, "book": "b", "streams": [{"id": "w1", "kind": "mystery", "atom_count": 1, "envelope_hash": "h"}]}',
        '{"stream_freeze_schema_version": 1, "book": "b", "streams": [{"id": "w1", "kind": "witness", "atom_count": 1, "envelope_hash": "h"}]}',
    ],
)
def test_load_freeze_record_is_a_total_contract(tmp_path, doc):
    path = tmp_path / "freeze.json"
    path.write_text(doc, encoding="utf-8")
    with pytest.raises(StaleArtifactError):
        load_freeze_record(path)


def test_load_freeze_record_missing_file_is_missing_input(tmp_path):
    # Post-audit alignment with the shared load-boundary taxonomy (errors.py): an ABSENT artifact
    # is MissingInputError everywhere; StaleArtifactError is reserved for present-but-unloadable.
    with pytest.raises(MissingInputError):
        load_freeze_record(tmp_path / "absent.json")


def test_load_freeze_record_unreadable_file_is_stale(tmp_path):
    path = tmp_path / "freeze.json"
    path.write_text("{}", encoding="utf-8")
    path.chmod(0o000)
    try:
        with pytest.raises(StaleArtifactError, match="unreadable"):
            load_freeze_record(path)
    finally:
        path.chmod(0o644)


def test_load_freeze_record_non_utf8_and_depth_blowup_are_stale(tmp_path):
    # Delta re-audit F1: these two escaped raw (UnicodeDecodeError / RecursionError) while the
    # docstring claimed the total contract — the loader now matches its evidence/structure-map
    # siblings.
    bad = tmp_path / "freeze.json"
    bad.write_bytes(b"\xff\xfe{")
    with pytest.raises(StaleArtifactError, match="not valid UTF-8"):
        load_freeze_record(bad)
    deep = tmp_path / "deep.json"
    deep.write_text("[" * 100_000, encoding="utf-8")
    with pytest.raises(StaleArtifactError, match="not valid JSON"):
        load_freeze_record(deep)


# --- assert_freeze_matches: every drift axis fails loud, naming the stream ---------------- #


def test_matches_green_on_identical_streams():
    streams = _streams()
    record = build_freeze_record(streams, book="b")
    assert_freeze_matches(record, streams)  # no raise


def test_content_drift_names_the_stream():
    # the motivating failure: same stream set, same counts, one witness's text re-captured
    # differently -> its envelope hash (and the canonical projection's) must red by name
    record = build_freeze_record(_streams(), book="b")
    drifted = _streams(t2=W2.replace("blok", "block"))
    with pytest.raises(StaleArtifactError, match="w2"):
        assert_freeze_matches(record, drifted)


def test_renumbering_drift_reds():
    # an extra leading block shifts every downstream atom id — the exact silent-renumbering
    # hazard the freeze exists to make loud
    record = build_freeze_record(_streams(), book="b")
    renumbered = _streams(t1="Zero block inserted.\n\n" + W1)
    with pytest.raises(StaleArtifactError):
        assert_freeze_matches(record, renumbered)


def test_missing_and_extra_live_streams_red_by_name():
    streams = _streams()
    record = build_freeze_record(streams, book="b")
    with pytest.raises(StaleArtifactError, match="w2"):
        assert_freeze_matches(record, {k: v for k, v in streams.items() if k != "w2"})
    extra = dict(streams)
    atoms = capture_witness("Lone block.\n", "w9")
    extra["w9"] = AtomStream.witness("w9", atoms, gap_records(atoms, "Lone block.\n"), "Lone block.\n")
    with pytest.raises(StaleArtifactError, match="w9"):
        assert_freeze_matches(record, extra)


@pytest.mark.parametrize("field,value", [("kind", "canonical"), ("atom_count", 99), ("source_hash", "sha256:0")])
def test_record_field_tamper_reds_independently(field, value):
    # each frozen field is checked in its own right — a hand-edited record cannot pass on the
    # strength of the other fields (atom_count tamper leaves the hash agreeing, and still reds)
    streams = _streams()
    record = build_freeze_record(streams, book="b")
    entry = next(e for e in record["streams"] if e["id"] == "w1")
    entry[field] = value
    with pytest.raises(StaleArtifactError, match=field):
        assert_freeze_matches(record, streams)


# --- the writer guard: deny-by-default on a differing committed pin ----------------------- #


def test_writer_fresh_then_idempotent(tmp_path):
    record = build_freeze_record(_streams(), book="b")
    path = tmp_path / "stream_freeze.json"
    write_freeze_record(path, record)
    first = path.read_text(encoding="utf-8")
    write_freeze_record(path, record)  # identical bytes: idempotent, no guard, no churn
    assert path.read_text(encoding="utf-8") == first == render_freeze_record(record)


def test_writer_refuses_silent_overwrite_and_leaves_the_pin_intact(tmp_path):
    path = tmp_path / "stream_freeze.json"
    original = build_freeze_record(_streams(), book="b")
    write_freeze_record(path, original)
    drifted = build_freeze_record(_streams(t1="Zero block inserted.\n\n" + W1), book="b")
    with pytest.raises(StaleArtifactError, match="force"):
        write_freeze_record(path, drifted)
    assert load_freeze_record(path) == original  # the committed pin survives the refusal
    write_freeze_record(path, drifted, force=True)  # explicit human intent overwrites
    assert load_freeze_record(path) == drifted


# --- the PLL tripwire: committed record == live recapture --------------------------------- #


def _read(name: str) -> str:
    path = INPUTS / name
    assert path.is_file(), f"frozen PLL input missing: {path}"
    text = path.read_text(encoding="utf-8")
    assert text, f"{name} is empty — the freeze would pin a vacuous stream"
    return text


def _pll_streams() -> dict[str, AtomStream]:
    """The exact capture ``books/per_la_liberta/freeze_streams.py`` performs (kept in lockstep by
    this tripwire: a drifted script writes hashes this recapture cannot reproduce)."""
    t1, t2, t3 = _read("copy1_raw.txt"), _read("copy2_raw.txt"), _read("copy3_raw.txt")
    page_map = json.loads((INPUTS / "copy3_pro_page_map.json").read_text(encoding="utf-8"))
    assert page_map, "copy3 page map is empty"
    classify_line, page_of = marker_page_binding(t3, marker=PAGE_MARKER, page_map=page_map)
    a1 = capture_witness(t1, "copy1")
    a2 = capture_witness(t2, "copy2")
    a3 = capture_witness(t3, "copy3", classify_line=classify_line, page_of=page_of)
    canon = build_canonical({"copy1": a1, "copy2": a2}, ["copy1", "copy2"])
    return {
        "copy1": AtomStream.witness("copy1", a1, gap_records(a1, t1), t1),
        "copy2": AtomStream.witness("copy2", a2, gap_records(a2, t2), t2),
        "copy3": AtomStream.witness("copy3", a3, gap_records(a3, t3), t3),
        "canonical": AtomStream.canonical(canon),
    }


def test_pll_freeze_record_is_committed_and_matches_the_live_recapture():
    # Hard, never skipped: the committed pin must exist (a fresh clone regenerates the workspace
    # but NOT the ids the authored map references — those are pinned here) ...
    assert FREEZE.is_file(), (
        f"S4.6-pre freeze record missing: {FREEZE} — generate it with "
        "`uv run python books/per_la_liberta/freeze_streams.py`"
    )
    record = load_freeze_record(FREEZE)
    assert record["book"] == "per_la_liberta"
    assert [e["id"] for e in record["streams"]] == ["canonical", "copy1", "copy2", "copy3"]
    # ... and the live producers over the committed inputs must still reproduce it exactly. A
    # capture/segmentation change reds HERE — refresh the freeze consciously (--force) and re-verify
    # any authored structure map against the new ids; never let the substrate drift silently.
    assert_freeze_matches(record, _pll_streams())
