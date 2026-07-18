"""S1.4 closure — the production round-trip GATE through the S1.5 atom store's public read path
(ENGINE_STRUCTURE_PLAN §3.0/§9; D22). Closes issue #21.

S1.4's core (`roundtrip_gate.py`) and real-input floor (`test_roundtrip_gate_real_input.py`) reconstruct
each witness from **hand-built** atoms. The GATE's done-when, however, is byte-exactness **through the
store's public read path consumers use** — ``load_stream`` (filter-by-witness / canonical load) and
``stream_ids`` (witness iteration) — *never a private helper, never re-reading the raw witness file*.
This file is that closure:

- **round-trip tier** — each witness, captured → ``save_stream`` → ``load_stream`` → reconstructed
  byte-for-byte from the **loaded** atoms + gaps, checked against the independently-read fixture (the
  oracle the test brings — not the store's own ``source_hash``, so the compare is non-tautological);
  iterated via ``stream_ids``; canonical routed through reference-integrity, not the whole-artifact gate.
- **back-door-read negative** — the crux of "never re-reading raw source": corrupt the **store** on disk
  while the raw witness fixture stays pristine. ``load_stream`` must **fail loud** — proving the read
  path validates the *store's* bytes, not the still-correct raw file a back-door would have read (which
  would have falsely passed). Plus overlap / implicit-gap negatives through the same read path.

The copy3 ``⟨PAGE:N⟩`` furniture grammar is the per-book binding, supplied here, never in ``structure/``
core (the S0.2 neutrality guard scans the core, not this PLL-bound test).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from engine.errors import RoundTripError
from engine.paths import BookWorkspace
from engine.structure import (
    CANONICAL,
    WITNESS,
    AtomStream,
    assert_no_wholesale_exclusion,
    assert_reference_integrity,
    build_canonical,
    capture_witness,
    gap_records,
    load_stream,
    reconstruct_source,
    save_stream,
    stream_ids,
    stream_path,
)
from engine.util.jsonio import atomic_write_json, read_json

INPUTS = Path(__file__).resolve().parents[2] / "books" / "per_la_liberta" / "inputs"
COPY1, COPY2, COPY3 = INPUTS / "copy1_raw.txt", INPUTS / "copy2_raw.txt", INPUTS / "copy3_raw.txt"
PAGE_MARKER = re.compile(r"⟨PAGE:(\d+)⟩")


def _read(path: Path) -> str:
    assert path.is_file(), f"frozen PLL witness missing: {path}"
    text = path.read_text(encoding="utf-8")
    assert text, f"witness {path.name} is empty — the round-trip would pass vacuously"
    return text


def _copy3_furniture(line: str) -> str | None:
    return "page-furniture" if PAGE_MARKER.fullmatch(line.strip()) else None


def _ws(tmp_path) -> BookWorkspace:
    return BookWorkspace.for_book("per_la_liberta", tmp_path).ensure()


def _save_witnesses(ws) -> dict[str, str]:
    """Capture + persist copy1/2/3 into the store; return the true fixture sources by witness id."""
    sources: dict[str, str] = {}
    for path, witness, kw in (
        (COPY1, "copy1", {}),
        (COPY2, "copy2", {}),
        (COPY3, "copy3", {"classify_line": _copy3_furniture}),
    ):
        text = _read(path)
        atoms = capture_witness(text, witness, **kw)
        save_stream(ws, AtomStream.witness(witness, atoms, gap_records(atoms, text), text))
        sources[witness] = text
    return sources


# --- round-trip tier: byte-exact through the public read path -------------------------------- #


def test_each_witness_reconstructs_byte_exact_through_the_store(tmp_path):
    ws = _ws(tmp_path)
    sources = _save_witnesses(ws)
    for witness, true_source in sources.items():
        loaded = load_stream(ws, witness)                 # public read path (also self-checks on load)
        assert loaded.kind == WITNESS
        # reconstructed from the LOADED stream only, compared to the INDEPENDENT fixture (non-vacuous):
        assert reconstruct_source(loaded.atoms, loaded.gaps) == true_source
        assert reconstruct_source(loaded.atoms, loaded.gaps).encode("utf-8") == true_source.encode("utf-8")
        # full-gate wholesale-exclusion holds over the loaded stream (load_stream does not bundle it):
        assert_no_wholesale_exclusion(loaded.atoms, true_source)


def test_witness_iteration_via_stream_ids(tmp_path):
    ws = _ws(tmp_path)
    sources = _save_witnesses(ws)
    canon = build_canonical(
        {"copy1": capture_witness(sources["copy1"], "copy1"),
         "copy2": capture_witness(sources["copy2"], "copy2")},
        ["copy1", "copy2"],
    )
    save_stream(ws, AtomStream.canonical(canon))
    # the enumeration read path discovers every stream without pre-known ids ...
    assert stream_ids(ws) == ["canonical", "copy1", "copy2", "copy3"]
    # ... and filter-by-kind separates witnesses (reconstructable) from canonical (not whole-artifact):
    witnesses = [w for w in stream_ids(ws) if load_stream(ws, w).kind == WITNESS]
    assert witnesses == ["copy1", "copy2", "copy3"]
    for w in witnesses:
        s = load_stream(ws, w)
        assert reconstruct_source(s.atoms, s.gaps) == sources[w]


def test_canonical_loads_and_resolves_through_the_store(tmp_path):
    ws = _ws(tmp_path)
    sources = _save_witnesses(ws)
    w1, w2 = capture_witness(sources["copy1"], "copy1"), capture_witness(sources["copy2"], "copy2")
    save_stream(ws, AtomStream.canonical(build_canonical({"copy1": w1, "copy2": w2}, ["copy1", "copy2"])))
    loaded_canon = load_stream(ws, "canonical")
    assert loaded_canon.kind == CANONICAL
    # canonical is routed through reference-integrity (+ per-atom address check load_stream ran),
    # NOT the whole-artifact gate (it tiles no single source) — the carried S1.4-audit scope decision.
    witnesses = {w: load_stream(ws, w) for w in ("copy1", "copy2")}
    assert_reference_integrity(loaded_canon, witnesses)


def test_stream_ids_empty_before_any_save(tmp_path):
    assert stream_ids(_ws(tmp_path)) == []                # no data/atoms/ yet → empty, not a crash


# --- back-door-read negative: the read path validates the STORE, not the pristine raw file ------ #


def test_back_door_read_negative_store_drift_fails_while_raw_pristine(tmp_path):
    ws = _ws(tmp_path)
    raw_before = COPY1.read_bytes()
    save_stream(ws, AtomStream.witness("copy1", capture_witness(_read(COPY1), "copy1"),
                                       gap_records(capture_witness(_read(COPY1), "copy1"), _read(COPY1)),
                                       _read(COPY1)))
    path = stream_path(ws, "copy1")
    env = read_json(path)
    env["atoms"][20]["text"] = env["atoms"][20]["text"] + "X"   # drift the STORE; raw file untouched
    atomic_write_json(path, env)
    with pytest.raises(RoundTripError):
        load_stream(ws, "copy1")                          # fails loud — it read the store, not raw
    # the raw witness is byte-identical: a back-door re-reading it would have FALSELY passed.
    assert COPY1.read_bytes() == raw_before


def test_store_overlap_fails_through_the_read_path(tmp_path):
    ws = _ws(tmp_path)
    _save_witnesses(ws)
    path = stream_path(ws, "copy1")
    env = read_json(path)
    # extend atom 5's span to swallow into atom 7 → overlapping coverage in the persisted stream
    env["atoms"][5]["raw_span"][1] = env["atoms"][7]["raw_span"][0] + 1
    atomic_write_json(path, env)
    with pytest.raises(RoundTripError, match="overlaps"):
        load_stream(ws, "copy1")


def test_store_implicit_gap_fails_through_the_read_path(tmp_path):
    ws = _ws(tmp_path)
    _save_witnesses(ws)
    path = stream_path(ws, "copy1")
    env = read_json(path)
    assert env["gaps"], "copy1 has inter-atom gaps to drop"
    env["gaps"] = env["gaps"][1:]                         # drop a declared gap → a hole opens
    atomic_write_json(path, env)
    with pytest.raises(RoundTripError, match="undeclared gap"):
        load_stream(ws, "copy1")
