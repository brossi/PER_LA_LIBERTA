"""S1.4 — the production round-trip GATE on REAL PLL bytes (ENGINE_STRUCTURE_PLAN §3.0/§9; D22).

``test_roundtrip_gate`` is the synthetic floor; this runs the **same gate** over the committed PLL
witnesses (``books/per_la_liberta/inputs/copy{1,2,3}_raw.txt``) — the real-input promotion the row
calls for. The crux S1.4 adds over the S1.2 per-atom floor and the S1.3a tiling floor:

1. **Whole-artifact byte-exactness.** Each whole witness (~520K–790K codepoints) is reconstructed
   byte-for-byte from its S1.3a atom stream + the explicit gap records — coverage the per-atom hashes
   never pin (they re-slice the source, so they cannot see an ``atom.text`` drifted off its span;
   ``test_roundtrip_gate.py::test_text_drift_passes_per_atom_but_fails_whole_artifact`` proves that).
2. **The wholesale-exclusion seam** (deferred from S1.3b): on copy3's real page-marker furniture the
   processed atoms clear the floor with room to spare, yet a capture that mis-tags every atom excluded
   raises — the failure no tiling/round-trip/completeness tier otherwise sees.

The copy3 ``⟨PAGE:N⟩`` furniture grammar is a per-book source-noise convention supplied **here**, never
in ``structure/`` core (the S0.2 neutrality guard scans the core, not this PLL-bound test). The gate is
page-agnostic, so ``page_of`` is left default — only the furniture ``classify_line`` matters.

Tiers (each proven red): round-trip (whole witness reconstructs byte-exact) + negative (real implicit
gap — the one negative that is data-dependent: it plants nothing, it drops a gap the real witness
actually has). The planted-mutation negatives (overlap, dropped atom, text drift, all-excluded) live
only in ``test_roundtrip_gate.py``: the guard clauses they exercise are byte-independent, so the real
copies added no mutant-killing power at real I/O cost (#56).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from engine.errors import CaptureError, RoundTripError
from engine.structure import (
    PROCESSING_SCOPE_EXCLUDED,
    PROCESSING_SCOPE_INCLUDED,
    assert_production_roundtrip,
    build_canonical,
    capture_witness,
    gap_records,
    reconstruct_source,
)

INPUTS = Path(__file__).resolve().parents[2] / "books" / "per_la_liberta" / "inputs"
COPY1 = INPUTS / "copy1_raw.txt"
COPY2 = INPUTS / "copy2_raw.txt"
COPY3 = INPUTS / "copy3_raw.txt"

PAGE_MARKER = re.compile(r"⟨PAGE:(\d+)⟩")


def _read(path: Path) -> str:
    # Hard, not skipped (matches test_raw_capture_real_input / test_roundtrip_real_input): committed
    # required fixtures; a skipif would turn the whole real-input floor silently green if one moved.
    assert path.is_file(), f"frozen PLL witness missing: {path}"
    text = path.read_text(encoding="utf-8")
    assert text, f"witness {path.name} is empty — the round-trip would pass vacuously"
    return text


def _copy3_furniture(line: str) -> str | None:
    """The PLL copy3 per-book binding: tag ``⟨PAGE:N⟩`` lines as excluded page-furniture (source-noise
    grammar, lives in the test, never in core)."""
    return "page-furniture" if PAGE_MARKER.fullmatch(line.strip()) else None


# --- round-trip tier: each whole witness reconstructs byte-exact ----------------------------- #

def test_copy1_copy2_reconstruct_whole_artifact_byte_exact():
    for path, witness in ((COPY1, "copy1"), (COPY2, "copy2")):
        text = _read(path)
        atoms = capture_witness(text, witness)   # all-body, unmapped
        gaps = assert_production_roundtrip(atoms, text)
        assert all(not g.text.strip() for g in gaps)            # every declared gap is whitespace
        assert reconstruct_source(atoms, gaps) == text          # whole artifact, byte-exact
        # codepoint↔byte exactness over the real accented Italian (where a UTF-8 confusion surfaces)
        assert reconstruct_source(atoms, gaps).encode("utf-8") == text.encode("utf-8")


def test_copy3_real_furniture_round_trips_and_clears_exclusion_floor():
    text = _read(COPY3)
    atoms = capture_witness(text, "copy3", classify_line=_copy3_furniture)
    excluded = [a for a in atoms if a.processing_scope == PROCESSING_SCOPE_EXCLUDED]
    included = [a for a in atoms if a.processing_scope == PROCESSING_SCOPE_INCLUDED]
    # real witness with real excluded furniture present (not a degenerate all-body fraction of 1.0) ...
    assert excluded and included, "expected both body and page-furniture atoms in copy3"
    # ... yet the body dominates, so the wholesale-exclusion floor passes with margin, and the whole
    # witness — body atoms + excluded ⟨PAGE:N⟩ furniture atoms + whitespace gaps — reconstructs exact
    gaps = assert_production_roundtrip(atoms, text)
    assert reconstruct_source(atoms, gaps) == text
    # bind the headroom the floor's docstring claims (~0.99), not just the bare >= 0.5 pass
    included_nonws = sum(1 for a in included for c in a.text if not c.isspace())
    total_nonws = sum(1 for c in text if not c.isspace())
    assert included_nonws / total_nonws > 0.9


# --- negative tier: the one data-dependent negative (drops a gap the real witness has) ------- #

def test_real_implicit_gap_fails_reconstruction():
    text = _read(COPY1)
    atoms = capture_witness(text, "copy1")
    gaps = gap_records(atoms, text)
    assert gaps, "copy1 has inter-atom whitespace gaps to drop"
    with pytest.raises(RoundTripError, match="undeclared gap"):
        reconstruct_source(atoms, gaps[1:])  # drop a declared gap → a hole opens, no longer tiling


def test_canonical_stream_is_out_of_whole_artifact_scope_until_s1_5():
    # Greppable boundary marker (mirrors S1.3a.4's tripwire). The canonical/reconciled stream is OUT
    # of the whole-artifact gate's scope: its atoms adopt their derived_from[0] witness's address, so
    # different atoms point into different witness sources and no single `source` tiles them. Feeding
    # it to the gate raises (loud — though the message reads "silent loss", the wrong cause). Canonical
    # atoms are verified per-atom against each derived_from witness by the S1.2 floor, never here. When
    # S1.5 wires "canonical-projection load" into the store read path, this marks the boundary it must
    # NOT route through assert_production_roundtrip.
    t1, t2 = _read(COPY1), _read(COPY2)
    canon = build_canonical(
        {"copy1": capture_witness(t1, "copy1"), "copy2": capture_witness(t2, "copy2")},
        ["copy1", "copy2"],
    )
    assert canon, "canonical projection is empty"
    with pytest.raises(CaptureError):
        assert_production_roundtrip(canon, t1)  # copy1 source cannot tile copy2-addressed atoms
