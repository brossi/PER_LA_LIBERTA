"""S1.2→S1.4 — the raw round-trip floor on REAL PLL bytes (ENGINE_STRUCTURE_PLAN §3.0/§9; D22).

S1.2's model floor (``test_roundtrip``) runs on synthetic in-memory text. This file is the first
slice of the **real-input floor (S1.4)**: it runs the same floor against the *committed* copy3
witness (``books/per_la_liberta/inputs/copy3_raw.txt``) and its page map. It is a *slice* of S1.4,
not the whole: the atoms here are built by hand from the page map, not produced by the S1.3a capture
stream through the public read path — that full path is still S1.4 (W2).

Two things real bytes verify that synthetic cannot:

1. **The byte-exact floor on the real witness** (round-trip + reference-integrity tiers). A frozen
   page (span + sha256 + verbatim head/tail, all committed literals derived from the fixture via an
   independent hash) binds three things at once — the witness bytes, ``hash_raw``'s algorithm, and
   the page map's offsets — so a drift in *any* reds the test (``feedback_validate_bindings``). The
   drift negative mutates the witness in-memory and asserts the floor raises.

2. **Capture completeness + span topology** (the reason S1.2 alone is "too weak" — PLAN risk table /
   DoD A-1). The probe behind this file found that copy3's page map covers 99.6% of the witness and
   the 0.4% remainder is *exactly* the ``⟨PAGE:N⟩`` delimiter furniture — no dropped book text. The
   topology check makes that a standing assertion: content spans are in-bounds, monotonic, and
   non-overlapping; the regex-found page-marker sequence equals the map's pages; and every uncovered
   char is marker-or-whitespace (zero silent loss). ``⟨PAGE:N⟩`` is a copy3/source-noise convention
   and lives only in this PLL-bound test, never in ``structure/`` core (the S0.2 neutrality guard).

Tiers (each proven red, PLAN §9): round-trip (the frozen page reconstructs byte-exact); negative
(witness drift raises; each topology branch raises on a tampered map — positive and negatives share
the ``assert_page_map_tiles_witness`` chokepoint, so they cannot silently diverge). The completeness
validator lives in the
test, not ``src/`` — the engine-side validator is S1.4/S1.5, not anticipated here.

Frozen literals refresh: re-derive from the fixture if the committed witness/page map is regenerated
(``scratchpad`` derivation probe; see the commit that added this file).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from engine.errors import RoundTripError
from engine.structure import (
    Atom,
    Geom,
    hash_raw,
    reconstruct_raw,
    verify_atom_roundtrip,
)

INPUTS = Path(__file__).resolve().parents[2] / "books" / "per_la_liberta" / "inputs"
WITNESS = INPUTS / "copy3_raw.txt"
PAGE_MAP = INPUTS / "copy3_pro_page_map.json"

# Frozen anchor: copy3 page 61 (dense interior prose, carries à/è/ù). Derived from the committed
# fixture with stdlib hashlib (an oracle independent of hash_raw). A change to the witness bytes,
# to hash_raw, or to the page map's offsets for page 61 reds at least one assertion below.
FROZEN_PAGE = 61
FROZEN_SPAN = (163971, 167523)
FROZEN_LEN = 3552
FROZEN_SHA = "sha256:7cae612de0cfda4ba7761350b6bafe57fdcfd25e74857a1d4f61e6ccc203f3c3"
FROZEN_HEAD = "anni dopo, chiudere l'eroica esistenza,\ncombattendo sulle "
FROZEN_TAIL = " sul suo capo, per debito di giusti-\n55\n"

PAGE_MARKER = re.compile(r"⟨PAGE:(\d+)⟩")


def _witness() -> str:
    # Hard, not skipped: copy3_raw.txt is a committed, required fixture (matches the discipline
    # test_sidecar_contracts states for its own frozen inputs). A skipif here would turn the whole
    # real-input floor silently green if the file moved.
    assert WITNESS.is_file(), f"frozen PLL witness missing: {WITNESS}"
    text = WITNESS.read_text(encoding="utf-8")
    assert text, "witness is empty — the round-trip would pass vacuously"
    return text


def _page_map() -> list[dict]:
    assert PAGE_MAP.is_file(), f"frozen PLL page map missing: {PAGE_MAP}"
    pm = json.loads(PAGE_MAP.read_text(encoding="utf-8"))
    assert pm, "page map is empty — the topology check would pass vacuously"
    return pm


def _atom(slice_: str, span: tuple[int, int], sha: str, page: int) -> Atom:
    return Atom(
        atom_id=f"pll_copy3_p{page}",
        text=slice_,
        raw_span=span,
        raw_source_hash=sha,
        page_range=(page, page),
        norm_layer="raw",
        geom=Geom.absent(),
        capture_provenance_class="authorial",
    )


# --- round-trip + reference-integrity tiers (the floor on real bytes) ---------------------- #

def test_frozen_page_round_trips_byte_exact_against_the_committed_witness():
    txt = _witness()
    page = next(p for p in _page_map() if p["page"] == FROZEN_PAGE)
    # binding 1: the page map's offsets for page 61 are the frozen span
    assert (page["char_start"], page["char_end"]) == FROZEN_SPAN
    slice_ = txt[FROZEN_SPAN[0]:FROZEN_SPAN[1]]
    # binding 2: hash_raw (SUT) over the committed bytes reproduces the independently-derived sha
    assert hash_raw(slice_) == FROZEN_SHA
    # the floor: an atom carrying the FROZEN hash (not a recomputed one) recovers the raw byte-exact
    recovered = verify_atom_roundtrip(_atom(slice_, FROZEN_SPAN, FROZEN_SHA, FROZEN_PAGE), txt)
    assert recovered == slice_
    assert len(recovered) == FROZEN_LEN
    # binding 3: verbatim content, so a compensating witness+map drift can't slip through
    assert recovered.startswith(FROZEN_HEAD)
    assert recovered.endswith(FROZEN_TAIL)
    # byte-exact over the real accented Italian (where a codepoint/byte confusion would surface)
    assert recovered.encode("utf-8") == slice_.encode("utf-8")
    assert any(ord(c) > 127 for c in recovered)


def test_drift_in_the_committed_witness_fails_the_floor():
    # The negative the byte-exact floor exists for: a one-char change inside the page-61 span no
    # longer hashes to the frozen value → reconstruct_raw raises. Tamper is in-memory; the committed
    # fixture is untouched.
    txt = _witness()
    s, _e = FROZEN_SPAN
    i = s + 10
    mutated = txt[:i] + ("X" if txt[i] != "X" else "Y") + txt[i + 1:]
    atom = _atom(txt[FROZEN_SPAN[0]:FROZEN_SPAN[1]], FROZEN_SPAN, FROZEN_SHA, FROZEN_PAGE)
    with pytest.raises(RoundTripError, match="drifted or the span is wrong"):
        reconstruct_raw(atom, mutated)


# --- capture completeness + span topology (the S1.4 core; why S1.2 alone is too weak) ------ #

def assert_page_map_tiles_witness(page_map: list[dict], text: str) -> None:
    """The capture-completeness + span-topology floor as one chokepoint the real-data positive and
    the tampered negatives both exercise (so they cannot diverge). Raises ``ValueError`` on any
    violation: an out-of-bounds / overlapping / mis-ordered content span; a page-marker sequence that
    disagrees with the map; or any uncovered char that is not page-marker furniture or whitespace
    (a silent content loss). This is the invariant S1.4/S1.5 will own in engine code; it lives in the
    test for now (a test-local chokepoint both the positive and the negatives exercise)."""
    n = len(text)
    spans = [(p["char_start"], p["char_end"]) for p in page_map]
    # (a) in-bounds + monotonic, non-overlapping, in offset order
    prev = 0
    for idx, (s, e) in enumerate(spans):
        if not 0 <= s <= e <= n:
            raise ValueError(f"span {(s, e)} out of bounds for witness length {n} (index {idx})")
        if s < prev:
            raise ValueError(f"span {(s, e)} overlaps/precedes prior end {prev} (index {idx})")
        prev = max(prev, e)
    # (b) the independent page-marker sequence (regex over the witness) equals the map's pages
    marker_pages = [int(m.group(1)) for m in PAGE_MARKER.finditer(text)]
    map_pages = [p["page"] for p in page_map]
    if marker_pages != map_pages:
        raise ValueError(
            f"page-marker sequence ({len(marker_pages)}) != map pages ({len(map_pages)})"
        )
    # (c) completeness: every char outside a content span is page-marker furniture or whitespace
    gaps, cur = [], 0
    for s, e in spans:
        if s > cur:
            gaps.append((cur, s))
        cur = max(cur, e)
    if cur < n:
        gaps.append((cur, n))
    residue = PAGE_MARKER.sub("", "".join(text[a:b] for a, b in gaps)).strip()
    if residue:
        raise ValueError(f"{len(residue)} uncovered non-furniture chars (silent loss): {residue[:60]!r}")


def test_real_page_map_tiles_the_witness_with_zero_silent_loss():
    # The positive: the committed copy3 page map perfectly tiles its witness — content spans plus
    # ⟨PAGE:N⟩ furniture account for every char. Raises (fails) on any violation.
    assert_page_map_tiles_witness(_page_map(), _witness())


def test_negative_overlapping_span_fails_topology():
    txt = _witness()
    pm = _page_map()
    p6 = next(p for p in pm if p["page"] == 6)
    p5 = next(p for p in pm if p["page"] == 5)
    p6["char_start"] = p5["char_start"]  # page 6 now starts before page 5 ends
    with pytest.raises(ValueError, match="overlaps"):
        assert_page_map_tiles_witness(pm, txt)


def test_negative_dropped_page_fails_marker_binding():
    txt = _witness()
    pm = [p for p in _page_map() if p["page"] != 60]  # drop an interior page from the map
    with pytest.raises(ValueError, match="!= map pages"):
        assert_page_map_tiles_witness(pm, txt)


def test_negative_uncovered_real_content_is_silent_loss():
    # Shrink page 61's content span so real words fall outside any span: the marker sequence still
    # matches (b passes), but the completeness residue is non-empty — the exact failure mode S1.4
    # exists to catch.
    txt = _witness()
    pm = _page_map()
    p61 = next(p for p in pm if p["page"] == FROZEN_PAGE)
    p61["char_end"] = p61["char_start"] + 5  # drop most of page 61's content
    with pytest.raises(ValueError, match="silent loss"):
        assert_page_map_tiles_witness(pm, txt)
