"""S1.3a — raw addressed capture on REAL PLL bytes (ENGINE_STRUCTURE_PLAN §2-A/§3.0/§11.1; D25, F4).

The model floor (``test_raw_capture``) runs on synthetic text. This is the real-input slice: it runs
``structure.capture`` against the *committed* PLL witnesses (``books/per_la_liberta/inputs/copy{1,2,3}_raw.txt``)
and copy3's page map, with the PLL ``⟨PAGE:N⟩`` page-marker grammar supplied **here**, never in core —
the copy3 source-noise convention lives in this per-book binding (the S0.2 neutrality guard scans
``structure/``, not this test).

What real bytes verify that synthetic cannot:

1. **Capture completeness on the whole witness** — copy3 segments into body paragraphs + page-marker
   furniture that **tile the witness with zero silent loss**: every one of ~790K codepoints is inside
   an atom span or inter-atom whitespace. The furniture count is bound to an *independent* regex over
   the witness (two computations of "how many markers" must agree), so a segmenter that swallowed a
   marker into a body atom reds. This is the capture-completeness invariant S1.4 promotes to a gate.
2. **Page attribution at scale** — copy3 is the only page-addressable witness: every body atom lands
   on a real page and each ``⟨PAGE:N⟩`` furniture atom carries ``(N, N)``; copy1/copy2 (0 form-feeds,
   no map) carry :data:`~engine.structure.PAGE_UNMAPPED` throughout.
3. **The canonical projection over real divergence** — aligning the full copy1/copy2 streams (~3.6K vs
   ~3.4K paragraphs of independently-OCR'd text) yields a canonical stream where **every atom has ≥1
   witness derivation** (the S1.3a done-when), ~46% are derived from both witnesses (a **structural /
   positional** pairing — *not* content agreement: only ~6% are content-anchored `equal` matches; the
   rest are positionally-aligned but textually-divergent `replace` pairs that word-level reconciliation,
   S7.1b, resolves), ids are unique, and each atom round-trips byte-exact against its primary witness's
   source.

Tiers (each proven red, PLAN §9): completeness (``assert_capture_tiles`` over the real witness) +
negatives (a tampered overlap / silent loss on real bytes share that chokepoint). Each frozen count is
bound to an independent in-test oracle (S1.3a.3 — regex / blank-block split / opcode algebra) so a
segmenter regression reds the binding; the ints stay as legible scale anchors — **refresh them if the
witnesses/page map are regenerated.**
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from difflib import SequenceMatcher
from pathlib import Path

import pytest

from engine.errors import CaptureError
from engine.structure import (
    PAGE_UNMAPPED,
    PROCESSING_SCOPE_EXCLUDED,
    PROCESSING_SCOPE_INCLUDED,
    align_streams,
    assert_capture_tiles,
    build_canonical,
    capture_witness,
    duplicate_atom_ids,
    marker_page_binding,
    reconstruct_raw,
)

# The canonical projection's default block-comparison key — imported (not replicated) so the canonical
# count oracle below keys with the *identical* comparison build_canonical uses, staying faithful if the
# default key ever changes (S1.3a.3).
from engine.structure.capture import _alignment_key

INPUTS = Path(__file__).resolve().parents[2] / "books" / "per_la_liberta" / "inputs"
COPY1 = INPUTS / "copy1_raw.txt"
COPY2 = INPUTS / "copy2_raw.txt"
COPY3 = INPUTS / "copy3_raw.txt"
PAGE_MAP = INPUTS / "copy3_pro_page_map.json"

PAGE_MARKER = re.compile(r"⟨PAGE:(\d+)⟩")

# Frozen counts, derived from the committed fixtures (segmentation of the witness bytes). A change to
# the witnesses, the page map, or capture_witness's segmentation reds the bound assertion.
FROZEN_COPY3_FURNITURE = 278       # == independent regex marker count (the binding oracle)
FROZEN_COPY3_BODY = 521            # == blank/furniture-delimited block oracle (_count_body_blocks)
FROZEN_COPY1_ATOMS = 3621          # == blank-delimited block oracle
FROZEN_COPY2_ATOMS = 3356          # == blank-delimited block oracle
FROZEN_CANONICAL_ATOMS = 4786      # == opcode-algebra oracle (_alignment_pair_count, autojunk=True)


# --- independent oracles for the frozen counts (S1.3a.3, #16 audit Thread 3A) ------------- #
# Each frozen count is bound to a re-derivation by a *different* mechanism than capture_witness, so a
# segmentation regression reds the binding rather than the count silently tracking a magic int. The
# independence is graded honestly (mirroring S1.3a.2's value-not-explicitness candor):
#   - furniture: genuinely cross-architecture — a regex *occurrence* count vs capture's line-classified
#     *atom* count; the two diverge exactly when a marker is welded into a body block (the probe risk).
#   - body / copy1 / copy2: implementation-independent (a regex blank-block split vs capture's stateful
#     line-walk) but specification-shared — catches a walk-implementation bug, not a shared spec error.
#   - canonical: independent of build_canonical's per-pair emission loop (the opcode->pair algebra),
#     recomputing only the alignment; catches a drop/dup in emission. The frozen scale anchor catches a
#     capture-segmentation drift the same-input algebra would otherwise track silently.
# A localized capture mutation is proven to red these bindings (PLAN §9). The copy3 body oracle masks
# furniture lines with the genuinely-independent furniture regex, so it inherits that independence on
# its furniture-boundary axis.

def _count_body_blocks(text: str, *, mask_furniture: Callable[[str], bool] | None = None) -> int:
    """Count blank-line-delimited non-blank blocks via ``re.split`` — a different mechanism than
    capture's stateful line-walk. Furniture lines are masked to blank first (capture flushes the body
    run at a furniture line exactly as at a blank line), so this predicts capture's body-atom count."""
    if mask_furniture is not None:
        text = "\n".join("" if mask_furniture(line) else line for line in text.split("\n"))
    return sum(1 for block in re.split(r"\n\s*\n", text) if block.strip())


def _alignment_pair_count(kp: list[str], ks: list[str], *, autojunk: bool) -> int:
    """The number of aligned pairs the difflib opcode algebra yields over two key streams — the
    canonical-count oracle, independent of ``build_canonical``'s emission loop (it recomputes only the
    alignment). ``kp``/``ks`` must be keyed with the same comparison the projection uses."""
    n = 0
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, kp, ks, autojunk=autojunk).get_opcodes():
        if tag == "insert":
            n += j2 - j1
        elif tag == "replace":
            n += max(i2 - i1, j2 - j1)
        else:  # equal | delete
            n += i2 - i1
    return n


def _read(path: Path) -> str:
    # Hard, not skipped (matches test_roundtrip_real_input / test_sidecar_contracts): these are
    # committed required fixtures; a skipif would turn the whole real-input floor silently green.
    assert path.is_file(), f"frozen PLL witness missing: {path}"
    text = path.read_text(encoding="utf-8")
    assert text, f"witness {path.name} is empty — capture would tile vacuously"
    return text


def _pll_copy3_binding(text: str):
    """The PLL copy3 per-book binding: the ``⟨PAGE:N⟩`` grammar + copy3's page map, supplied HERE
    (this grammar is source-noise — it lives book-side, never in ``structure/`` core) to the neutral
    ``marker_page_binding`` factory (S4.6-pre moved the mechanism into core; the page-attribution
    tests below are its behavior anchors)."""
    assert PAGE_MAP.is_file(), f"frozen PLL page map missing: {PAGE_MAP}"
    page_map = json.loads(PAGE_MAP.read_text(encoding="utf-8"))
    assert page_map, "copy3 page map is empty"
    return marker_page_binding(text, marker=PAGE_MARKER, page_map=page_map)


# --- capture completeness on the real witness ------------------------------------------- #

def test_copy3_segments_and_tiles_with_zero_silent_loss():
    text = _read(COPY3)
    classify_line, page_of = _pll_copy3_binding(text)
    atoms = capture_witness(text, "copy3", classify_line=classify_line, page_of=page_of)
    # the capture-completeness floor on ~790K real codepoints: nothing captured into no atom
    assert_capture_tiles(atoms, text)
    assert duplicate_atom_ids(atoms) == []
    body = [a for a in atoms if a.processing_scope == PROCESSING_SCOPE_INCLUDED]
    furniture = [a for a in atoms if a.processing_scope == PROCESSING_SCOPE_EXCLUDED]
    is_marker = lambda ln: bool(PAGE_MARKER.fullmatch(ln.strip()))  # noqa: E731 — local oracle mask
    # body count bound to the independent block oracle (furniture-masked), not just the frozen int
    assert len(body) == _count_body_blocks(text, mask_furniture=is_marker) == FROZEN_COPY3_BODY
    assert len(furniture) == FROZEN_COPY3_FURNITURE


def test_copy3_furniture_count_binds_to_an_independent_marker_oracle():
    text = _read(COPY3)
    classify_line, page_of = _pll_copy3_binding(text)
    atoms = capture_witness(text, "copy3", classify_line=classify_line, page_of=page_of)
    furniture = [a for a in atoms if a.capture_provenance_class == "page-furniture"]
    # the binding: the number of furniture atoms equals an independent regex count of the marker —
    # a segmenter that welded a marker into a body block (the probe's exact risk) would disagree.
    assert len(furniture) == len(PAGE_MARKER.findall(text)) == FROZEN_COPY3_FURNITURE
    # every furniture atom is an excluded, verbatim marker that round-trips
    for a in furniture:
        assert PAGE_MARKER.fullmatch(a.text)
        assert a.processing_scope == PROCESSING_SCOPE_EXCLUDED
        assert reconstruct_raw(a, text) == a.text


def test_copy3_pages_attributed_body_real_furniture_self():
    text = _read(COPY3)
    classify_line, page_of = _pll_copy3_binding(text)
    atoms = capture_witness(text, "copy3", classify_line=classify_line, page_of=page_of)
    body = [a for a in atoms if a.processing_scope == PROCESSING_SCOPE_INCLUDED]
    # every body atom lands on a real page (copy3 is the page-addressable witness)
    assert all(a.page_range != PAGE_UNMAPPED for a in body)
    assert all(a.page_range[0] >= 1 and a.page_range[1] >= a.page_range[0] for a in body)
    # each ⟨PAGE:N⟩ furniture atom carries the page it announces
    for a in atoms:
        if a.capture_provenance_class == "page-furniture":
            n = int(PAGE_MARKER.fullmatch(a.text).group(1))
            assert a.page_range == (n, n)


def test_copy1_copy2_tile_and_are_page_unmapped():
    for path, witness, frozen in ((COPY1, "copy1", FROZEN_COPY1_ATOMS),
                                  (COPY2, "copy2", FROZEN_COPY2_ATOMS)):
        text = _read(path)
        atoms = capture_witness(text, witness)   # no markers, no page map → all-body, unmapped
        assert_capture_tiles(atoms, text)
        # count bound to the independent blank-block oracle, not just the frozen int
        assert len(atoms) == _count_body_blocks(text) == frozen
        assert all(a.page_range == PAGE_UNMAPPED for a in atoms)
        assert all(a.processing_scope == PROCESSING_SCOPE_INCLUDED for a in atoms)
        assert duplicate_atom_ids(atoms) == []


# --- the negatives: real bytes, sharing the assert_capture_tiles chokepoint -------------- #

def test_real_overlap_fails_capture_tiles():
    text = _read(COPY1)
    atoms = capture_witness(text, "copy1")
    import dataclasses
    bad = list(atoms)
    # widen one atom's span to swallow into the next — an overlap on real offsets
    s, _e = bad[5].raw_span
    bad[5] = dataclasses.replace(bad[5], raw_span=(s, bad[7].raw_span[0] + 1))
    with pytest.raises(CaptureError, match="overlaps or precedes"):
        assert_capture_tiles(bad, text)


def test_real_dropped_atom_is_silent_loss():
    text = _read(COPY1)
    atoms = capture_witness(text, "copy1")
    # remove a body atom: its real-text bytes are now captured into nothing → silent loss
    bad = atoms[:10] + atoms[11:]
    with pytest.raises(CaptureError, match="silent loss"):
        assert_capture_tiles(bad, text)


# --- the canonical projection over real copy1/copy2 divergence --------------------------- #

def test_real_canonical_every_atom_derived_and_round_trips():
    t1, t2 = _read(COPY1), _read(COPY2)
    a1 = capture_witness(t1, "copy1")
    a2 = capture_witness(t2, "copy2")
    canon = build_canonical({"copy1": a1, "copy2": a2}, ["copy1", "copy2"])
    assert canon, "canonical projection is empty"
    # the canonical count is bound to the opcode-algebra oracle (independent of build_canonical's
    # emission loop) and to a documented scale anchor — a drop/dup in emission, or a fixture/segmenter
    # drift, reds it. kp/ks use build_canonical's own default key (imported, not replicated).
    included = lambda s: [a for a in s if a.processing_scope == PROCESSING_SCOPE_INCLUDED]  # noqa: E731
    kp = [_alignment_key(a.text) for a in included(a1)]
    ks = [_alignment_key(a.text) for a in included(a2)]
    assert len(canon) == _alignment_pair_count(kp, ks, autojunk=True) == FROZEN_CANONICAL_ATOMS
    # the S1.3a done-when, on real divergent OCR streams: no canonical atom is orphaned
    assert all(len(a.derived_from) >= 1 for a in canon)
    assert all(a.witness is None for a in canon)
    assert duplicate_atom_ids(canon) == []
    # a meaningful fraction are derived from BOTH witnesses — a structural/positional pairing, NOT
    # content agreement (only ~6% are content-anchored `equal` matches; word-level reconciliation is
    # S7.1b's job). This guards against a degenerate copy1-only projection, nothing more.
    both = sum(1 for a in canon if len(a.derived_from) == 2)
    assert both > len(canon) // 4, (
        f"only {both}/{len(canon)} canonical atoms are derived from both witnesses (positional pairing)"
    )
    # every canonical atom round-trips byte-exact against the source of its primary derivation
    sources = {"copy1": t1, "copy2": t2}
    for a in canon:
        assert reconstruct_raw(a, sources[a.derived_from[0].witness]) == a.text


# --- the canonical-page tripwire: S7.1b's worklist marker (S1.3a.4) ---------------------- #

def test_real_canonical_is_uniformly_page_unmapped_until_s7_1b():
    """S1.3a.4 — the S7.1b worklist marker. Today the canonical projection is uniformly PAGE_UNMAPPED:
    build_canonical aligns the two **structural** witnesses (copy1/copy2), both page-less, and copy3 —
    the only page-addressable witness — is the word-level adjudicator, absent from the structural
    alignment (S1.3a.1), so no page can reach canonical. When S7.1b establishes the copy3<->canonical
    word-level linkage and back-fills canonical page-attribution, this assertion **reds** — the signal
    that the page-attribution change is intentional, not an accident (see ENGINE_STRUCTURE_TASKS S7.1b
    and the PAGE_PENDING_ANCHOR deferral note). The assertion is **not vacuous**: page provenance flows
    primary->canonical, proven by ``test_canonical_adopts_primary_page_so_the_unmapped_tripwire_is_non_vacuous``
    in the model floor — a page-mapped primary yields a page-mapped canonical."""
    a1 = capture_witness(_read(COPY1), "copy1")
    a2 = capture_witness(_read(COPY2), "copy2")
    canon = build_canonical({"copy1": a1, "copy2": a2}, ["copy1", "copy2"])
    assert canon, "canonical projection is empty"
    assert all(a.page_range == PAGE_UNMAPPED for a in canon), (
        "a canonical atom gained a real page — if this is S7.1b's page-attribution, update this marker "
        "intentionally; otherwise a page leaked from a witness into the structural projection"
    )


# --- the SequenceMatcher junk policy is explicit + load-bearing on real-scale streams ----- #

def test_align_streams_pins_explicit_autojunk_and_it_is_load_bearing():
    """`align_streams`'s **effective** junk policy is ``autojunk=True`` (mirrors
    ``reconcile.align_paragraphs``), and on real >=200-element streams that policy is
    **load-bearing**. One key is held fixed so the *junk value* is the only variable.

    Scope, stated honestly: this pins the **value**, not the **explicitness**. Flipping the call to
    ``autojunk=False`` reds it (the pair count diverges from the True oracle: 5226 != 4786); but
    *removing* the explicit arg reverts to difflib's default — also ``True`` — so this test stays
    **green** on that change. Explicit-vs-implicit is a source-level intent, not behaviorally
    observable, and is carried by the call-site comment + review. The opcode->pair *mapping* is
    covered by the synthetic opcode-shape tests; this real-input test's marginal job is the one
    behavior invisible at synthetic scale — the junk value — plus the data-property guard (B) that
    keeps the "load-bearing" comment from going stale."""
    a1 = capture_witness(_read(COPY1), "copy1")
    a2 = capture_witness(_read(COPY2), "copy2")
    key = lambda s: re.sub(r"\s+", " ", s.casefold()).strip()  # noqa: E731 — local, one-line
    kp = [key(a.text) for a in a1]
    ks = [key(a.text) for a in a2]

    chosen = align_streams(a1, a2, key=key)
    # align_streams uses the True policy (its emitted pair count matches the autojunk=True algebra) ...
    assert len(chosen) == _alignment_pair_count(kp, ks, autojunk=True)
    # ... and on these real streams the policy is load-bearing (True and False genuinely differ).
    assert _alignment_pair_count(kp, ks, autojunk=True) != _alignment_pair_count(kp, ks, autojunk=False)
