"""S1.4 — the production round-trip GATE, synthetic floor (ENGINE_STRUCTURE_PLAN §3.0/§9; D22).

The S1.2 model floor binds *each atom's* bytes to its span hash; the S1.3a tiling floor proves the
atoms leave no non-whitespace byte uncovered. Neither pins the **whole artifact**: per-atom hashes
re-slice the source and so cannot see an ``atom.text`` that has drifted from the span it claims, and
``assert_capture_tiles`` discards the gaps it walks over. S1.4 promotes both into one gate over the
atom stream — ``structure/roundtrip_gate`` — that (a) emits the inter-atom gaps as **explicit
records**, (b) reconstructs the whole source byte-for-byte from the stored atom + gap text, and (c)
owns "you excluded everything" (the seam deferred from S1.3b). This file is the synthetic floor;
``test_roundtrip_gate_real_input`` runs the same gate over the committed PLL witnesses.

Invariants (each proven red below — PLAN §9 red-first):

- ``gap_records`` returns the leading / inter-atom / trailing gaps in order, each a whitespace-only
  verbatim slice; atoms ∪ gaps tile the source. (``test_gap_records_emit_*``)
- ``gap_records`` fails loud (``CaptureError``) on an out-of-bounds span, an overlap/misorder, or a
  **non-whitespace** gap (silent loss) — the messages ``assert_capture_tiles`` delegates to.
  (``test_gap_records_rejects_*``)
- ``GapRecord`` rejects a text whose length disagrees with its span width (a self-inconsistent
  record). (``test_gap_record_rejects_width_text_mismatch``)
- ``reconstruct_source`` rebuilds the whole source byte-exact from atom + gap text, and fails loud
  on an **undeclared (implicit) gap** or an overlap — the coverage hole the per-atom floor cannot
  see. (``test_reconstruct_*``)
- ``reconstruct_source`` over a drifted ``atom.text`` (span unchanged, so the per-atom hash still
  passes) does **not** reproduce the source → ``assert_production_roundtrip`` raises. This is the
  whole-artifact value-add over the per-atom floor. (``test_text_drift_passes_per_atom_but_fails_whole_artifact``)
- ``assert_no_wholesale_exclusion`` passes when processed atoms carry the majority of the source's
  non-whitespace content, and raises when (nearly) all body is mis-tagged excluded — exempting an
  all-whitespace source. (``test_wholesale_exclusion_*``)
- ``assert_production_roundtrip`` ties the three and returns the gap records.
  (``test_production_roundtrip_*``)
"""

from __future__ import annotations

import dataclasses

import pytest

from engine.errors import CaptureError, RoundTripError
from engine.structure import (
    PROCESSING_SCOPE_EXCLUDED,
    PROCESSING_SCOPE_INCLUDED,
    Atom,
    Geom,
    GapRecord,
    assert_no_wholesale_exclusion,
    assert_production_roundtrip,
    gap_records,
    hash_raw,
    reconstruct_source,
)


def _atom(text: str, start: int, end: int, *, scope: str = PROCESSING_SCOPE_INCLUDED,
          cls: str = "body", aid: str | None = None) -> Atom:
    return Atom(
        atom_id=aid if aid is not None else f"w_{start:05d}",
        text=text,
        raw_span=(start, end),
        raw_source_hash=hash_raw(text),
        page_range=(-1, -1),
        norm_layer="raw",
        geom=Geom.absent(),
        capture_provenance_class=cls,
        witness="w",
        processing_scope=scope,
    )


# A source whose body atoms are separated (and surrounded, in the leading/trailing variant) by
# whitespace gaps — the minimal shape that exercises every gap position.
SOURCE = "A\n\nBB\n\nCCC"           # atoms (0,1)(3,5)(7,10); inter-gaps (1,3)(5,7); no edge gaps
ATOMS = [_atom("A", 0, 1), _atom("BB", 3, 5), _atom("CCC", 7, 10)]


# --- gap_records: the explicit declared gaps + the topology/silent-loss raises ------------- #

def test_gap_records_emit_ordered_inter_atom_whitespace_gaps():
    gaps = gap_records(ATOMS, SOURCE)
    assert [g.raw_span for g in gaps] == [(1, 3), (5, 7)]
    assert [g.text for g in gaps] == ["\n\n", "\n\n"]
    # the declared-gap contract: every gap is whitespace, and atoms ∪ gaps cover the whole source
    assert all(not g.text.strip() for g in gaps)
    covered = sum(e - s for s, e in [a.raw_span for a in ATOMS]) + sum(e - s for s, e in
                                                                       [g.raw_span for g in gaps])
    assert covered == len(SOURCE)


def test_gap_records_emit_leading_and_trailing_gaps():
    src = "\nXY\n"
    atoms = [_atom("XY", 1, 3)]
    gaps = gap_records(atoms, src)
    assert [g.raw_span for g in gaps] == [(0, 1), (3, 4)]  # leading + trailing, both whitespace
    assert [g.text for g in gaps] == ["\n", "\n"]


def test_gap_records_rejects_out_of_bounds_span():
    atoms = [_atom("A", 0, 1), dataclasses.replace(_atom("ZZ", 3, 5), raw_span=(3, 999))]
    with pytest.raises(CaptureError, match="out of bounds"):
        gap_records(atoms, SOURCE)


def test_gap_records_rejects_overlap():
    bad = [ATOMS[0], dataclasses.replace(ATOMS[1], raw_span=(0, 5))]  # second starts inside first
    with pytest.raises(CaptureError, match="overlaps or precedes"):
        gap_records(bad, SOURCE)


def test_gap_records_rejects_non_whitespace_gap_as_silent_loss():
    # a body atom dropped: real content "BB" now falls in no atom and no whitespace gap
    bad = [ATOMS[0], ATOMS[2]]
    with pytest.raises(CaptureError, match="silent loss"):
        gap_records(bad, SOURCE)


def test_gap_records_rejects_trailing_non_whitespace_as_silent_loss():
    # content after the last atom, captured into nothing — the tail branch (distinct from an
    # inter-atom gap: it has no following atom to anchor the message on)
    src = "A\n\nZZ"
    atoms = [_atom("A", 0, 1)]
    with pytest.raises(CaptureError, match="after the last atom"):
        gap_records(atoms, src)


def test_gap_record_rejects_width_text_mismatch():
    with pytest.raises(ValueError, match="disagrees with span width"):
        GapRecord((1, 3), "\n")  # span width 2, text width 1 — a self-inconsistent record


def test_gap_record_rejects_non_whitespace_text():
    # whitespace-only is enforced at CONSTRUCTION (not just by the gap_records producer): a gap record
    # is a durable shape S1.5 persists + reads back, so a content-bearing "gap" must fail loud the
    # moment it is built, never splice content into a faked reconstruct_source round-trip
    with pytest.raises(ValueError, match="not whitespace-only"):
        GapRecord((1, 3), "ab")  # width matches (2 == 2) but carries content


# --- reconstruct_source: whole-artifact byte-exactness + implicit-gap / overlap raises ----- #

def test_reconstruct_source_rebuilds_the_whole_artifact_byte_exact():
    gaps = gap_records(ATOMS, SOURCE)
    assert reconstruct_source(ATOMS, gaps) == SOURCE


def test_reconstruct_source_rebuilds_with_edge_gaps():
    src = "\nXY\n"
    atoms = [_atom("XY", 1, 3)]
    assert reconstruct_source(atoms, gap_records(atoms, src)) == src


def test_reconstruct_source_rejects_undeclared_implicit_gap():
    gaps = gap_records(ATOMS, SOURCE)
    with pytest.raises(RoundTripError, match="undeclared gap"):
        reconstruct_source(ATOMS, gaps[1:])  # drop the (1,3) gap → a hole opens between atoms


def test_reconstruct_source_rejects_overlap():
    # an IN-ORDER overlap (second atom's start is within the first's span, but starts are
    # non-decreasing) — so the reconstruct overlap guard fires, not the out-of-order guard
    overlapping = [_atom("AAA", 0, 3), _atom("BB", 2, 4, aid="w_overlap")]
    with pytest.raises(RoundTripError, match="overlaps"):
        reconstruct_source(overlapping, [])


def test_reconstruct_source_rejects_out_of_order_atoms():
    # reconstruct_source must NOT silently reorder a misordered stream — it would false-green a capture
    # gap_records rejects (the standalone / store-read caller risk). Even with complete matching gaps,
    # out-of-order atoms raise rather than being sorted into a passing reconstruction.
    src = "  BB AA  "
    a_bb, a_aa = _atom("BB", 2, 4), _atom("AA", 5, 7)
    gaps = [GapRecord((0, 2), "  "), GapRecord((4, 5), " "), GapRecord((7, 9), "  ")]
    assert reconstruct_source([a_bb, a_aa], gaps) == src              # in order: tiles
    with pytest.raises(RoundTripError, match="source order"):
        reconstruct_source([a_aa, a_bb], gaps)                        # out of order: fails loud


def test_reconstruct_source_trailing_shortfall_shows_only_in_the_gate_compare():
    # the documented seam: reconstruct_source can't see a TRAILING shortfall (no following piece
    # reveals the hole), so it returns a short string without raising; the gate's == source catches it
    src = "\nXY\n"
    atoms = [_atom("XY", 1, 3)]
    gaps = gap_records(atoms, src)                  # [(0,1)"\n", (3,4)"\n"]
    short = reconstruct_source(atoms, gaps[:-1])    # drop the trailing gap
    assert short == "\nXY"                          # silently short — reconstruct_source does not raise
    assert short != src                             # ... so whole-artifact completeness is the gate's job


def test_text_drift_passes_per_atom_but_fails_whole_artifact():
    # The crux: drift atom.text off its span WITHOUT touching raw_span/raw_source_hash. The per-atom
    # floor re-slices the source and so still passes (it never reads atom.text); only the
    # whole-artifact reconstruction, which uses atom.text, can see the drift.
    from engine.structure import reconstruct_raw  # the per-atom floor
    drifted = [ATOMS[0], dataclasses.replace(ATOMS[1], text="BX"), ATOMS[2]]
    assert reconstruct_raw(drifted[1], SOURCE) == "BB"   # per-atom: green (re-slices span, ignores text)
    with pytest.raises(RoundTripError, match="whole-artifact"):
        assert_production_roundtrip(drifted, SOURCE)


# --- assert_no_wholesale_exclusion: the "you excluded everything" seam (deferred from S1.3b) - #

def test_wholesale_exclusion_passes_when_body_dominates():
    assert_no_wholesale_exclusion(ATOMS, SOURCE)  # all body included → fraction 1.0


def test_wholesale_exclusion_raises_when_all_body_excluded():
    all_excluded = [dataclasses.replace(a, processing_scope=PROCESSING_SCOPE_EXCLUDED) for a in ATOMS]
    with pytest.raises(CaptureError, match="wholesale exclusion"):
        assert_no_wholesale_exclusion(all_excluded, SOURCE)


def test_wholesale_exclusion_raises_when_below_fraction():
    # only "A" (1 non-ws char) processed; "BB"+"CCC" (5) excluded → 1/6 ≈ 0.17 < 0.5 floor
    mostly_excluded = [
        ATOMS[0],
        dataclasses.replace(ATOMS[1], processing_scope=PROCESSING_SCOPE_EXCLUDED),
        dataclasses.replace(ATOMS[2], processing_scope=PROCESSING_SCOPE_EXCLUDED),
    ]
    with pytest.raises(CaptureError, match="wholesale exclusion"):
        assert_no_wholesale_exclusion(mostly_excluded, SOURCE)


def test_wholesale_exclusion_exempts_all_whitespace_source():
    # no content to attribute — capture-emptiness is the tiling floor's concern, not this guard's
    assert_no_wholesale_exclusion([], "   \n\n ")


def test_wholesale_exclusion_floor_is_tunable():
    # only "CCC" (3 of 6 non-ws) processed → fraction exactly 0.5; a stricter per-book floor reds it
    half = [
        dataclasses.replace(ATOMS[0], processing_scope=PROCESSING_SCOPE_EXCLUDED),
        dataclasses.replace(ATOMS[1], processing_scope=PROCESSING_SCOPE_EXCLUDED),
        ATOMS[2],
    ]
    assert_no_wholesale_exclusion(half, SOURCE, min_included_fraction=0.5)   # 0.5 is not < 0.5
    with pytest.raises(CaptureError, match="wholesale exclusion"):
        assert_no_wholesale_exclusion(half, SOURCE, min_included_fraction=0.6)


# --- assert_production_roundtrip: the single gate entry --------------------------------------- #

def test_production_roundtrip_delegates_to_the_gap_floor():
    # The single gate entry wraps gap_records + reconstruct: clean input returns the declared gaps;
    # dropping a body atom propagates the gap floor's silent-loss failure. (Merged from the former
    # _returns_declared_gaps_on_clean_input / _raises_on_silent_loss delegation pair — audit 4.3.)
    gaps = assert_production_roundtrip(ATOMS, SOURCE)
    assert [g.raw_span for g in gaps] == [(1, 3), (5, 7)]
    with pytest.raises(CaptureError, match="silent loss"):
        assert_production_roundtrip([ATOMS[0], ATOMS[2]], SOURCE)
