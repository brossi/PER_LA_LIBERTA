"""S1.5 — the persisted atom store on REAL PLL bytes (ENGINE_STRUCTURE_PLAN §3.5/§3.6/§11.1; D21).

``test_atom_store`` is the synthetic floor; this persists and reloads the committed PLL witnesses
(``books/per_la_liberta/inputs/copy{1,2,3}_raw.txt``) + their canonical projection through the **same**
store, so the three tiers hold on real data:

1. **serialization-invariance** at scale — each whole witness stream (thousands of atoms + real
   inter-atom gaps) survives JSON + disk byte-for-byte (``load(save(s)) == s``);
2. **reference-integrity** — every ``derived_from`` back-link of the real canonical projection resolves
   to a real atom in the real witness streams.

The planted negatives (persisted text drift, dangling back-link) live only in ``test_atom_store.py``:
those guard paths are byte-independent, so real-bytes copies added no mutant-killing power (#56).

The copy3 ``⟨PAGE:N⟩`` furniture grammar is the per-book source-noise binding, supplied here, never in
``structure/`` core (the S0.2 neutrality guard scans the core, not this PLL-bound test).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from engine.paths import BookWorkspace
from engine.structure.atom_store import (
    AtomStream,
    assert_reference_integrity,
    load_stream,
    save_stream,
)
from engine.structure.atoms import PROCESSING_SCOPE_EXCLUDED
from engine.structure.capture import build_canonical, capture_witness
from engine.structure.roundtrip_gate import gap_records

INPUTS = Path(__file__).resolve().parents[2] / "books" / "per_la_liberta" / "inputs"
COPY1 = INPUTS / "copy1_raw.txt"
COPY2 = INPUTS / "copy2_raw.txt"
COPY3 = INPUTS / "copy3_raw.txt"

PAGE_MARKER = re.compile(r"⟨PAGE:(\d+)⟩")


def _read(path: Path) -> str:
    # Hard, not skipped (matches the sibling real-input floors): a committed required fixture; a skipif
    # would turn the whole real-input store floor silently green if one moved.
    assert path.is_file(), f"frozen PLL witness missing: {path}"
    text = path.read_text(encoding="utf-8")
    assert text, f"witness {path.name} is empty — the round-trip would pass vacuously"
    return text


def _copy3_furniture(line: str) -> str | None:
    return "page-furniture" if PAGE_MARKER.fullmatch(line.strip()) else None


def _ws(tmp_path) -> BookWorkspace:
    return BookWorkspace.for_book("per_la_liberta", tmp_path).ensure()


def _witness_stream(path: Path, witness: str, **kw) -> tuple[AtomStream, str]:
    text = _read(path)
    atoms = capture_witness(text, witness, **kw)
    return AtomStream.witness(witness, atoms, gap_records(atoms, text), text), text


# --- serialization-invariance at scale ------------------------------------------------------- #


@pytest.mark.parametrize("path,witness", [(COPY1, "copy1"), (COPY2, "copy2")])
def test_real_witness_stream_round_trips_through_disk(tmp_path, path, witness):
    ws = _ws(tmp_path)
    stream, _text = _witness_stream(path, witness)
    assert len(stream.atoms) > 100, "expected a real multi-atom witness stream"
    save_stream(ws, stream)
    assert load_stream(ws, witness) == stream            # whole real stream + gaps, byte-exact


def test_real_copy3_furniture_stream_round_trips(tmp_path):
    ws = _ws(tmp_path)
    stream, _text = _witness_stream(COPY3, "copy3", classify_line=_copy3_furniture)
    assert any(a.processing_scope == PROCESSING_SCOPE_EXCLUDED for a in stream.atoms), \
        "expected real ⟨PAGE:N⟩ furniture atoms captured-excluded"
    save_stream(ws, stream)
    assert load_stream(ws, "copy3") == stream


# --- reference-integrity over the real canonical projection ---------------------------------- #


def _real_canon_and_witnesses(tmp_path):
    t1, t2 = _read(COPY1), _read(COPY2)
    w1, w2 = capture_witness(t1, "copy1"), capture_witness(t2, "copy2")
    canon = AtomStream.canonical(build_canonical({"copy1": w1, "copy2": w2}, ["copy1", "copy2"]))
    witnesses = {
        "copy1": AtomStream.witness("copy1", w1, gap_records(w1, t1), t1),
        "copy2": AtomStream.witness("copy2", w2, gap_records(w2, t2), t2),
    }
    return canon, witnesses


def test_real_canonical_reference_integrity_resolves(tmp_path):
    canon, witnesses = _real_canon_and_witnesses(tmp_path)
    assert canon.atoms and all(a.derived_from for a in canon.atoms)
    assert_reference_integrity(canon, witnesses)          # every real back-link resolves
    # and the real canonical stream itself persists + reloads
    ws = _ws(tmp_path)
    save_stream(ws, canon)
    assert load_stream(ws, "canonical") == canon


