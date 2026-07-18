"""S1.4 — the production round-trip GATE (ENGINE_STRUCTURE_PLAN §3.0/§9; D22).

The S1.2 model floor (:mod:`engine.structure.roundtrip`) binds *each atom's* bytes to its span hash;
S1.3a's :func:`~engine.structure.capture.assert_capture_tiles` proves the atoms leave no
non-whitespace byte uncovered. Neither pins the **whole artifact**, and the row that promotes them to
a gate (S1.4) needs both gaps:

- A per-atom hash **re-slices the source** (``source[start:end]``) and checks that against the stored
  ``raw_source_hash`` — so it never reads ``atom.text`` and cannot see a ``text`` that has drifted off
  the span it claims. Only reconstructing from the stored ``text`` exposes that drift.
- ``assert_capture_tiles`` *walks* the inter-atom gaps to prove they are whitespace, then **discards**
  them. The completeness claim ("every source byte is inside an atom or a declared inter-atom gap")
  is only auditable if those gaps are first-class records.

This module is that promotion, over a plain ``Sequence[Atom]``:

- :class:`GapRecord` — one declared inter-atom/leading/trailing gap (span + verbatim whitespace text;
  the whitespace-only invariant is enforced **at construction**, so a record read back from a store
  fails loud if it carries content).
- :func:`gap_records` — the canonical completeness + span-topology walk; raises ``CaptureError`` on an
  out-of-bounds span, an overlap/misorder, or a non-whitespace gap (silent loss), and **returns** the
  ordered gaps. :func:`~engine.structure.capture.assert_capture_tiles` delegates here, so the
  invariant has one owner.
- :func:`reconstruct_source` — rebuild the whole source byte-for-byte from atom + gap text; fail loud
  (``RoundTripError``) on an out-of-order atom stream, an undeclared (implicit) interior gap, or an
  overlap.
- :func:`assert_no_wholesale_exclusion` — own "you excluded everything" (the seam deferred from
  S1.3b): a capture that mis-tags all body as furniture passes tiling + per-atom round-trip +
  ``check_completeness`` *vacuously*; this guard catches it.
- :func:`assert_production_roundtrip` — the single gate entry tying the three together.

**Scope — a single-witness stream that tiles one source.** Every function here reconstructs *one*
``source`` from *one* witness's atoms. The **canonical** (reconciled) stream is **out of scope**: its
atoms adopt their ``derived_from[0]`` witness's address, so different atoms point into different
witness sources and there is no single ``source`` to tile — feeding it here raises (loud, but the
message reads "silent loss", which is the wrong cause). Canonical atoms are verified per-atom against
each ``derived_from`` witness by the S1.2 floor, never through this whole-artifact gate.

**S1.5 composition (the closure).** The *primitives* (:func:`gap_records`, :func:`reconstruct_source`)
compose unchanged over atoms read from the store's public read path. The *bundled* entry
:func:`assert_production_roundtrip` derives the gap bytes by slicing ``source``; to honor S1.4's "never
re-reading raw source", the store must surface those bytes itself — either by **persisting the gap
records** (the leading choice; gap whitespace is *not* recoverable from span widths, so the store
cannot rebuild a witness from atoms alone) or by persisting the witness ``source`` — an S1.5 schema
decision (tracker S1.4-closure note). Until then this composes against the in-memory S1.3a capture.

Pure core: no language, ordinal, or book-structure opinion — only atom/source arithmetic (the S0.2
neutrality guard scans this module). Page-marker grammar and the page-map tiling check are per-book
source-noise conventions and stay in the PLL-bound tests, never here.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from engine.errors import CaptureError, RoundTripError
from engine.structure.atoms import PROCESSING_SCOPE_EXCLUDED, Atom

#: Default floor for :func:`assert_no_wholesale_exclusion`: the processed (non-excluded) atoms must
#: carry at least this fraction of the source's non-whitespace content. ``0.5`` is a conservative,
#: source-agnostic "processed content is the majority" boundary — **not** a PLL-tuned constant (a
#: PLL-tuned value would sit near PLL's measured ~0.99, not at a generic majority line). It assumes the
#: common case where excluded matter (page markers, running heads, scan furniture) is a minority of a
#: source's bytes. A source whose binding legitimately excludes the *majority* of bytes — a variorum
#: with a vast critical apparatus, an interlinear, a concordance — must pass ``min_included_fraction``
#: explicitly; the floor then fails **loud** (never silent), naming the override in its message.
DEFAULT_MIN_INCLUDED_FRACTION = 0.5


@dataclass(frozen=True, slots=True)
class GapRecord:
    """One declared inter-atom region: source bytes covered by no atom (leading, between, trailing).

    ``text`` is the verbatim source slice the span addresses and **must be whitespace-only** — a
    non-whitespace gap is content captured into no atom (silent loss). That invariant is enforced
    **here, at construction**, not merely by the :func:`gap_records` producer: a gap record is a
    durable shape an atom store will persist and read back (S1.5), so a record that carries content
    must fail loud the moment it is built, never splice that content into a faked round-trip via
    :func:`reconstruct_source`. Recording gaps makes the no-loss claim **auditable**: the atoms plus
    the gaps tile the source, and :func:`reconstruct_source` proves it byte-exact.
    """

    raw_span: tuple[int, int]
    text: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "raw_span", tuple(self.raw_span))
        if len(self.raw_span) != 2:
            raise ValueError("raw_span must be [start, end] codepoint offsets")
        start, end = self.raw_span
        if end - start != len(self.text):
            raise ValueError(
                f"GapRecord text length {len(self.text)} disagrees with span width {end - start} "
                f"({self.raw_span}) — a gap record must address exactly the bytes it carries"
            )
        if self.text.strip():
            raise ValueError(
                f"GapRecord text {self.text[:40]!r} is not whitespace-only — an inter-atom gap is "
                f"declared whitespace; content captured into no atom is silent loss, never a gap"
            )


def gap_records(atoms: Sequence[Atom], source: str) -> list[GapRecord]:
    """The capture-completeness + span-topology walk (§9): return the declared inter-atom gaps, or
    fail loud.

    Walks ``atoms`` in source order. Raises :class:`~engine.errors.CaptureError` if any ``raw_span``
    is out of bounds (``0 <= start <= end <= len``), if spans overlap or run backwards, or if any byte
    *between* atoms (or before the first / after the last) is non-whitespace — a non-whitespace gap is
    content captured into no atom (silent loss). Otherwise returns one :class:`GapRecord` per non-empty
    whitespace gap, in order, so atoms ∪ gaps tile ``source``. This is the single owner of the tiling
    invariant; :func:`~engine.structure.capture.assert_capture_tiles` delegates here.
    """
    n = len(source)
    gaps: list[GapRecord] = []
    prev = 0
    for atom in atoms:
        start, end = atom.raw_span
        if not 0 <= start <= end <= n:
            raise CaptureError(
                f"atom {atom.atom_id!r} span {atom.raw_span} is out of bounds for a source of "
                f"length {n}"
            )
        if start < prev:
            raise CaptureError(
                f"atom {atom.atom_id!r} span {atom.raw_span} overlaps or precedes the prior atom's "
                f"end {prev} — spans must be ordered and non-overlapping"
            )
        gap_text = source[prev:start]
        stripped = gap_text.strip()
        if stripped:
            raise CaptureError(
                f"{len(stripped)} uncovered non-whitespace char(s) before atom {atom.atom_id!r} "
                f"(silent loss — captured into no atom): {stripped[:60]!r}"
            )
        if gap_text:
            gaps.append(GapRecord((prev, start), gap_text))
        prev = end
    tail = source[prev:n]
    tail_stripped = tail.strip()
    if tail_stripped:
        raise CaptureError(
            f"{len(tail_stripped)} uncovered non-whitespace char(s) after the last atom "
            f"(silent loss — captured into no atom): {tail_stripped[:60]!r}"
        )
    if tail:
        gaps.append(GapRecord((prev, n), tail))
    return gaps


def reconstruct_source(atoms: Sequence[Atom], gaps: Sequence[GapRecord]) -> str:
    """Rebuild the whole source byte-for-byte from the **stored** atom + gap text.

    ``atoms`` must arrive in source order (non-decreasing ``raw_span`` start), the contract
    :func:`gap_records` enforces; an out-of-order stream fails loud rather than being silently
    reordered — otherwise this would *accept* a misordered capture ``gap_records`` rejects, a false
    green for a standalone (e.g. store-read) caller. Interleaves the declared gaps by offset and
    concatenates every piece's ``text``, requiring them to tile contiguously from offset 0 with no
    **interior** hole and no overlap. An undeclared (implicit) interior gap — a hole between two
    pieces — or an overlap fails loud (:class:`~engine.errors.RoundTripError`): the coverage failure
    mode the per-atom hash floor cannot see (it re-slices the source; this uses the stored text). A
    *trailing* shortfall (pieces that stop before the source ends) leaves no following piece to reveal
    the hole, so it is caught one level up by :func:`assert_production_roundtrip`'s ``== source``
    assertion — which is also what catches an ``atom.text`` drifted off its span (a drift the per-atom
    hash, re-slicing the source, passes). Whole-artifact completeness is therefore the gate's
    ``== source`` boundary, not this primitive's.
    """
    atom_starts = [a.raw_span[0] for a in atoms]
    if any(b < a for a, b in zip(atom_starts, atom_starts[1:])):
        raise RoundTripError(
            "atoms must be passed in source order (non-decreasing raw_span start); reconstruct_source "
            "interleaves declared gaps but does not reorder a misordered capture — pair it with "
            "gap_records, which enforces ordering"
        )
    pieces = sorted(
        [(a.raw_span[0], a.raw_span[1], a.text) for a in atoms]
        + [(g.raw_span[0], g.raw_span[1], g.text) for g in gaps]
    )
    out: list[str] = []
    cur = 0
    for start, end, text in pieces:
        if start < cur:
            raise RoundTripError(
                f"piece at {(start, end)} overlaps the reconstructed prefix ending at {cur} — atoms "
                f"and declared gaps must not overlap"
            )
        if start > cur:
            raise RoundTripError(
                f"undeclared gap [{cur}, {start}) — atoms and declared gaps do not tile contiguously "
                f"(implicit gap / silent loss)"
            )
        out.append(text)
        cur = end
    return "".join(out)


def assert_no_wholesale_exclusion(
    atoms: Sequence[Atom],
    source: str,
    *,
    min_included_fraction: float = DEFAULT_MIN_INCLUDED_FRACTION,
) -> None:
    """Own "you excluded everything" — the seam deferred from S1.3b.

    A capture that mis-tags all body as furniture passes :func:`gap_records`, the per-atom round-trip,
    **and** :func:`~engine.structure.typed.check_completeness` (vacuously complete,
    ``processed_count=0``): no other tier sees it. This guard does. The processed (non-excluded) atoms
    must carry at least ``min_included_fraction`` of the source's non-whitespace content; furniture is
    by nature a minority of a real page's bytes, so a processed fraction below the floor means capture
    excluded (nearly) all body. An all-whitespace source is exempt — there is no content to attribute,
    and capture-emptiness is the tiling floor's concern, not this guard's. Raises
    :class:`~engine.errors.CaptureError`.
    """
    total_nonws = sum(1 for c in source if not c.isspace())
    if total_nonws == 0:
        return
    included_nonws = sum(
        1
        for atom in atoms
        if atom.processing_scope != PROCESSING_SCOPE_EXCLUDED
        for c in atom.text
        if not c.isspace()
    )
    fraction = included_nonws / total_nonws
    if fraction < min_included_fraction:
        raise CaptureError(
            f"wholesale exclusion: processed (non-excluded) atoms carry only {included_nonws}/"
            f"{total_nonws} = {fraction:.2%} of the source's non-whitespace content, below the "
            f"{min_included_fraction:.0%} floor — capture excluded (nearly) all body as furniture"
        )


def assert_production_roundtrip(
    atoms: Sequence[Atom],
    source: str,
    *,
    min_included_fraction: float = DEFAULT_MIN_INCLUDED_FRACTION,
) -> list[GapRecord]:
    """The S1.4 gate entry: completeness + topology, whole-artifact byte-exactness, and the
    wholesale-exclusion guard, in one call returning the declared gap records.

    ``atoms`` must be a **single-witness** stream tiling this one ``source`` (see the module
    docstring's scope note): the canonical/reconciled stream is verified per-atom by the S1.2 floor,
    not here. The S1.5 closure runs this over atoms read from the store's public read path; because
    the gap bytes are derived from ``source`` here, that ``source`` must itself come from the store
    (persisted gaps or persisted source), never re-read from the raw witness file — an S1.5 schema
    decision (tracker S1.4-closure note). Raises :class:`~engine.errors.CaptureError` /
    :class:`~engine.errors.RoundTripError` on any violation.
    """
    gaps = gap_records(atoms, source)
    recovered = reconstruct_source(atoms, gaps)
    if recovered != source:
        raise RoundTripError(
            f"whole-artifact round-trip failed: reconstructed {len(recovered)} char(s) != source "
            f"{len(source)} char(s) — the stored atom/gap text does not reproduce the source "
            f"byte-exact (an atom.text drifted off its span, which the per-atom hash cannot see)"
        )
    assert_no_wholesale_exclusion(atoms, source, min_included_fraction=min_included_fraction)
    return gaps
