"""S1.3a — raw addressed capture (ENGINE_STRUCTURE_PLAN §2-A/§3.0/§11.1; D25, the F4 fix).

Concern A's first behavior: re-segment a raw witness into immutable, addressed L1 atoms, **plus**
one canonical reconciled projection that back-links the per-witness atoms it was built from. This is
deliberately *not* read-only from ``reconcile``: that step segments copy1/2/3 in memory and then
**discards** the per-witness streams, persisting only the merged ``reconciled_chapters.json`` + word
flags. So the per-witness streams are *re-built here* by re-running segmentation on the raw copies —
that algorithm is this module's deliverable (the F4 note in ENGINE_STRUCTURE_TASKS), and it is what
keeps every witness independently addressable for the L3 spans of S7.1b.

Three neutral primitives, no language/book opinion (the S0.2 neutrality guard scans this file):

- :func:`capture_witness` — line-aware segmentation of one witness into raw atoms that **tile** the
  source. A maximal run of consecutive non-blank *body* lines becomes one paragraph atom whose
  ``text`` is the **verbatim** raw slice ``source[start:end]`` (no ``rejoin_lines``/``collapse_spaces``
  — those are lossy, D30 — so the S1.2 round-trip floor holds by construction). *Furniture* lines
  (page markers, running heads) are split into their own atoms carrying a caller-supplied
  ``capture_provenance_class`` + ``processing_scope="excluded"`` — captured-with-role, never dropped.
  Which lines are furniture, and how a span maps to a page, are **injected** (``classify_line`` /
  ``page_of``): the page-marker grammar and the no-page-map case are source-noise conventions that
  live in the per-book binding, not here.
- :func:`build_canonical` — align two structural witnesses block-by-block and emit a canonical atom
  per aligned group, each carrying ``derived_from`` back-links to the per-witness atoms it covers
  (§11.1). It adopts the *primary* witness's text/address; word-level cross-witness reconciliation is
  ``reconcile``'s existing job, orthogonal to this structural projection.
- :func:`assert_capture_tiles` — the capture-completeness + span-topology floor (§9): atoms are
  in-bounds, ordered, non-overlapping, and every byte outside an atom is whitespace (no *silent
  loss*). Furniture is atoms here, so the gaps are pure inter-atom whitespace — the validator needs
  no furniture grammar and stays neutral. This is the invariant S1.4 promotes to the production gate.

Plus one binding *factory*, :func:`marker_page_binding` — the mechanism half of the common per-book
shape "page furniture is a single-line marker + a char-offset page map" (PLL's copy3). The grammar
and the map stay caller-supplied data, so the factory carries no book opinion; consumers are the
real-input capture tests, the S4.6-pre stream freeze, and (later) S7.1b's copy3↔canonical work.
"""

from __future__ import annotations

import re
from bisect import bisect_right
from collections.abc import Callable, Mapping, Sequence
from difflib import SequenceMatcher

from engine.errors import CaptureError
from engine.structure.atoms import (
    PROCESSING_SCOPE_EXCLUDED,
    PROCESSING_SCOPE_INCLUDED,
    Atom,
    AtomDerivation,
    Geom,
)
from engine.structure.roundtrip import hash_raw
from engine.structure.roundtrip_gate import gap_records

# The page range an atom carries when its witness has no page addressing at all (no page map, no
# form feeds — PLL's copy1/copy2). A first-class "unmapped" sentinel, distinct from any real page,
# so page-less capture stays representable without widening S1.1's frozen ``tuple[int, int]`` field.
PAGE_UNMAPPED: tuple[int, int] = (-1, -1)

# A ``classify_line`` returns the furniture ``capture_provenance_class`` for a furniture line, or
# ``None`` for a body line. A ``page_of`` maps a ``[start, end)`` codepoint span to its page range.
ClassifyLine = Callable[[str], str | None]
PageOf = Callable[[int, int], tuple[int, int]]

_WHITESPACE_RUN = re.compile(r"\s+")


def _all_body(_line: str) -> str | None:
    """The trivial classifier: every line is body, no furniture (a witness with no markers)."""
    return None


def _unmapped(_start: int, _end: int) -> tuple[int, int]:
    """The trivial page map: no page addressing — every atom is :data:`PAGE_UNMAPPED`."""
    return PAGE_UNMAPPED


def _alignment_key(text: str) -> str:
    """The neutral block-comparison key for alignment: case-folded, whitespace-collapsed.

    Used only to *compare* blocks across witnesses (it never touches stored ``text``), so it folds
    away the OCR-noise axes — case and run-length — without an accent or language rule. A per-book
    binding may inject a stronger key, but the default carries no language opinion.
    """
    return _WHITESPACE_RUN.sub(" ", text.casefold()).strip()


def capture_witness(
    source: str,
    witness: str,
    *,
    classify_line: ClassifyLine = _all_body,
    page_of: PageOf = _unmapped,
    body_class: str = "body",
) -> list[Atom]:
    """Segment one raw witness into a complete, tiling stream of addressed L1 atoms.

    Walks ``source`` line by line. A blank line is an inter-atom boundary (its bytes become gap
    whitespace). A *body* line (``classify_line`` returns ``None``) extends the current paragraph
    run; a *furniture* line (``classify_line`` returns a class) flushes the run and becomes its own
    excluded atom. Every atom's ``text`` is the verbatim slice it addresses and its
    ``raw_source_hash`` is :func:`~engine.structure.roundtrip.hash_raw` of that slice, so each atom
    passes the S1.2 raw round-trip floor against this ``source``. ``atom_id`` is ``{witness}_{NNNNN}``
    in source order; the returned stream tiles ``source`` (verify with :func:`assert_capture_tiles`).
    """
    atoms: list[Atom] = []
    seq = 0
    body_start: int | None = None
    body_end = 0

    def flush_body() -> None:
        nonlocal body_start, seq
        if body_start is None:
            return
        atoms.append(
            _raw_atom(source, body_start, body_end, witness, seq, body_class,
                      PROCESSING_SCOPE_INCLUDED, page_of)
        )
        seq += 1
        body_start = None

    pos = 0
    n = len(source)
    while pos < n:
        nl = source.find("\n", pos)
        content_end = n if nl == -1 else nl
        line = source[pos:content_end]
        if not line.strip():
            flush_body()
        else:
            cls = classify_line(line)
            if cls is None:
                if body_start is None:
                    body_start = pos
                body_end = content_end
            else:
                flush_body()
                atoms.append(
                    _raw_atom(source, pos, content_end, witness, seq, cls,
                              PROCESSING_SCOPE_EXCLUDED, page_of)
                )
                seq += 1
        pos = n if nl == -1 else nl + 1
    flush_body()
    return atoms


def marker_page_binding(
    source: str,
    *,
    marker: re.Pattern[str],
    page_map: Sequence[Mapping[str, int]],
    furniture_class: str = "page-furniture",
) -> tuple[ClassifyLine, PageOf]:
    """Capture binding for a witness whose page furniture is single-line markers over a char-offset map.

    Mechanism only — the marker grammar and the page map are per-book source-noise supplied by the
    caller (the S0.2 neutrality boundary stays intact; PLL's ``⟨PAGE:N⟩`` literal lives in the book
    binding, never here). Returns a ``classify_line`` that tags full-line ``marker`` matches as
    ``furniture_class``, and a ``page_of`` that gives a marker span its own announced page (the
    marker's first group must capture the page number) and resolves every other span through
    ``page_map`` (entries ``{"page", "char_start", "char_end"}``, ordered by ``char_start``),
    falling back to :data:`PAGE_UNMAPPED`'s components for offsets no map entry covers.
    """
    starts = [entry["char_start"] for entry in page_map]

    def _page_at(offset: int) -> int | None:
        i = bisect_right(starts, offset) - 1
        if 0 <= i < len(page_map) and page_map[i]["char_start"] <= offset < page_map[i]["char_end"]:
            return page_map[i]["page"]
        return None

    def classify_line(line: str) -> str | None:
        return furniture_class if marker.fullmatch(line.strip()) else None

    def page_of(start: int, end: int) -> tuple[int, int]:
        m = marker.fullmatch(source[start:end].strip())
        if m:
            page = int(m.group(1))
            return (page, page)
        a, b = _page_at(start), _page_at(max(start, end - 1))
        return (a if a is not None else PAGE_UNMAPPED[0], b if b is not None else PAGE_UNMAPPED[1])

    return classify_line, page_of


def _raw_atom(
    source: str,
    start: int,
    end: int,
    witness: str,
    seq: int,
    capture_provenance_class: str,
    processing_scope: str,
    page_of: PageOf,
) -> Atom:
    """Build one raw, byte-exact atom addressing ``source[start:end]`` (``text == raw``, no geometry
    yet — geometry is S2, ``Geom.absent()`` here)."""
    slice_ = source[start:end]
    return Atom(
        atom_id=f"{witness}_{seq:05d}",
        text=slice_,
        raw_span=(start, end),
        raw_source_hash=hash_raw(slice_),
        page_range=page_of(start, end),
        norm_layer="raw",
        geom=Geom.absent(),
        capture_provenance_class=capture_provenance_class,
        witness=witness,
        processing_scope=processing_scope,
    )


def align_streams(
    primary: Sequence[Atom],
    secondary: Sequence[Atom],
    *,
    key: Callable[[str], str] = _alignment_key,
) -> list[tuple[Atom | None, Atom | None]]:
    """Align two atom streams block-by-block via :class:`difflib.SequenceMatcher` over ``key(text)``.

    Returns aligned pairs in source order: ``(p, s)`` for a matched block, ``(p, None)`` for a block
    only in ``primary``, ``(None, s)`` for one only in ``secondary``. Mirrors the opcode handling of
    the live ``reconcile.align_paragraphs`` but at atom granularity and with no language in the key.
    """
    kp = [key(a.text) for a in primary]
    ks = [key(a.text) for a in secondary]
    aligned: list[tuple[Atom | None, Atom | None]] = []
    # autojunk=True is explicit + load-bearing, never the silent default: on real >=200-element
    # streams difflib junks any key appearing in >1% of the sequence (high-frequency OCR-noise
    # keys), which shifts the alignment — a material swing in the canonical count on real witnesses.
    # Mirrors reconcile.align_paragraphs' identical call; revisiting the policy (True / False /
    # per-book junk predicate) is a carried S1.3a concern, pinned True here.
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, kp, ks, autojunk=True).get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                aligned.append((primary[i1 + k], secondary[j1 + k]))
        elif tag == "replace":
            len1, len2 = i2 - i1, j2 - j1
            for k in range(max(len1, len2)):
                aligned.append((
                    primary[i1 + k] if k < len1 else None,
                    secondary[j1 + k] if k < len2 else None,
                ))
        elif tag == "insert":
            for k in range(j1, j2):
                aligned.append((None, secondary[k]))
        elif tag == "delete":
            for k in range(i1, i2):
                aligned.append((primary[k], None))
    return aligned


def build_canonical(
    streams: Mapping[str, Sequence[Atom]],
    witness_order: Sequence[str],
    *,
    key: Callable[[str], str] = _alignment_key,
) -> list[Atom]:
    """Build the canonical reconciled projection from two structural witnesses (§11.1).

    Aligns the **included** (non-furniture) atoms of ``witness_order[0]`` (primary) and
    ``witness_order[1]`` (secondary) via :func:`align_streams`, and emits one canonical atom per
    aligned group. Each canonical atom **adopts the primary witness's text and address** (the
    secondary's where the block is primary-absent) and records a ``derived_from`` back-link for every
    contributing witness — so the S1.3a property holds: *every canonical atom has ≥1 witness
    derivation*. ``witness`` is ``None`` (canonical is no single witness); its ``raw_span`` /
    ``raw_source_hash`` address the source of ``derived_from[0]``'s witness, so it round-trips against
    that witness's source. Word-level cross-witness reconciliation (and any third, word-level witness)
    is ``reconcile``'s separate job — not done here.
    """
    if len(witness_order) != 2:
        raise CaptureError(
            f"build_canonical aligns exactly two structural witnesses; got {len(witness_order)} "
            f"({list(witness_order)!r}). N-way structural alignment is unbuilt — a word-level third "
            f"witness (PLL's copy3) is reconciled separately, never passed here (S1.3a.1)."
        )
    primary_w, secondary_w = witness_order[0], witness_order[1]
    primary = [a for a in streams[primary_w] if a.processing_scope == PROCESSING_SCOPE_INCLUDED]
    secondary = [a for a in streams[secondary_w] if a.processing_scope == PROCESSING_SCOPE_INCLUDED]

    canonical: list[Atom] = []
    for seq, (p, s) in enumerate(align_streams(primary, secondary, key=key)):
        derivations: list[AtomDerivation] = []
        if p is not None:
            derivations.append(AtomDerivation(witness=primary_w, atom_id=p.atom_id))
        if s is not None:
            derivations.append(AtomDerivation(witness=secondary_w, atom_id=s.atom_id))
        adopted = p if p is not None else s
        canonical.append(
            Atom(
                atom_id=f"canonical_{seq:05d}",
                text=adopted.text,
                raw_span=adopted.raw_span,
                raw_source_hash=adopted.raw_source_hash,
                page_range=adopted.page_range,
                norm_layer=adopted.norm_layer,
                geom=adopted.geom,
                capture_provenance_class=adopted.capture_provenance_class,
                witness=None,
                derived_from=tuple(derivations),
                processing_scope=adopted.processing_scope,
            )
        )
    return canonical


def assert_capture_tiles(atoms: Sequence[Atom], source: str) -> None:
    """The capture-completeness + span-topology floor (§9): raise :class:`CaptureError` unless the
    atoms tile ``source`` with no silent loss.

    Delegates to :func:`engine.structure.roundtrip_gate.gap_records` — the single owner of the tiling
    invariant S1.4 promotes to the production gate — discarding the returned gap records. Checks, in
    source order: every ``raw_span`` is in-bounds (``0 <= start <= end <= len``), spans do not overlap
    or run backwards, and every byte *between* atoms (and before the first / after the last) is
    whitespace — a non-whitespace gap is captured into no atom, the silent-loss failure mode
    "everything is brought in" forbids. Because furniture is captured as atoms (not left in gaps),
    this needs no furniture grammar; it stays the neutral invariant.
    """
    gap_records(atoms, source)
