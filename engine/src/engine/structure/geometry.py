"""The geometry seam (concern A's word-box layer) — records, the ``GeometrySource`` Protocol, and
the fail-loud ``GeometryError`` (S2.1; ``s2_1_plan.md`` DT-1/DT-2, D30).

A book's word-box geometry is the primary re-binding signal (S5) and the base layer for space
reconstruction (S3.1). On PLL both scans are images, so there is no native box layer: it is
*generated* fresh by an OCR backend (PyMuPDF+Tesseract, #36). Because those boxes come from a
different OCR pass than the witness text, **a box is not a fact about that text until a matcher
proves it** (S2.1's matcher, #37) — this module fixes only the raw material and the seam:

- :class:`WordBox` — one OCR token + its page-point bbox. :class:`PageGeometry` — one page's boxes
  plus its dimensions. Validity is enforced at construction: a non-finite / degenerate / empty-text
  / non-positive record is *unconstructible* (never a silently-wrong coordinate that would corrupt
  re-bind downstream). An empty page is **not** invalid — a genuinely blank page yields zero words
  *successfully* (DT-2: empty ≠ failed).
- :class:`GeometrySource` — the injectable Protocol a backend satisfies (one page-range obligation
  + an ``engine_id`` reproducibility string). Order of emission is **contractually unspecified**:
  page-locate consumes per-page token bags and the matcher canonicalizes box order itself, so no
  consumer depends on backend emission order; a consumer wanting reading order goes through
  ``segmentation.reading_order`` (#39), never backend order.
- :class:`GeometryError` — the axis's immediate fail-loud carrier (exit 13). Deliberately **not** a
  reuse of ``ocr``'s :class:`~engine.errors.BackendError` (exit 5): OCR retains a per-page error
  checkpoint for retry and raises at its pre-publication completeness gate, while geometry cannot
  emit or retain coordinates it does not trust.

Pure core: no language, dpi, or book literal lives here — OCR language and dpi are the backend's
required constructor parameters (#36), supplied from book config (the S0.2 neutrality guard scans
this module).
"""

from __future__ import annotations

import math
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from engine.errors import EngineError


class GeometryError(EngineError):
    """A geometry-backend / OCR-integrity failure — fail-loud, no per-page degrade (S2.1, DT-1/DT-2).

    Covers the backend's operational faults (missing tessdata, an OCR failure, and *any* rotated
    page — ``page.rotation != 0`` raises rather than emitting coordinates in a silently-transformed
    space, G-17) and geometry-integrity violations (a systemic off-page-box fraction — isolated
    off-page boxes are dropped and counted, ruled 2026-07-05 — a calibration-gate block, a
    volume-bound breach). One human action — the geometry is
    untrustworthy, stop — so one exit code.

    Distinct from :class:`~engine.errors.BackendError` (exit 5) by design: ``ocr`` retains a
    per-page ``[OCR_ERROR]`` checkpoint and fails its publication gate after the page batch, whereas
    this axis raises immediately and must never emit coordinates it does not trust. Geometry carries
    its own code (the next free code
    after ``StructureValidationError`` 11 and ``EvidenceGateError`` 12). The sidecar/worklist *load*
    boundaries do NOT use this type — they join the shared loader taxonomy (absent →
    :class:`~engine.errors.MissingInputError`, present-but-unloadable/stale →
    :class:`~engine.errors.StaleArtifactError`).
    """

    exit_code = 13


@dataclass(frozen=True, slots=True)
class WordBox:
    """One OCR word token and its bounding box, in PDF page-point space (D30; DT-2/DT-4).

    ``text`` is a single non-empty token; ``bbox`` is exactly four floats ``(x0, y0, x1, y1)`` with
    origin top-left, y-down (PyMuPDF ``page.rect`` units — the dpi-independent space, DT-4). Validity
    is enforced at construction (G-21): coordinates must be finite (checked *before* the degenerate
    comparison, since ``nan`` compares False and would otherwise slip past it), the box must be
    non-degenerate (``x1 > x0`` and ``y1 > y0``), and the text must carry a token — an empty-text box
    is a Tesseract artifact the backend drops before construction (DT-2 normalization), never data.
    Frozen: a box is a record, not a mutable handle.
    """

    text: str
    bbox: tuple[float, float, float, float]

    def __post_init__(self) -> None:
        # Ordered sequences only: a set/generator would tuple-ize in iteration order, and a
        # reordered-but-plausible box is the exact silently-wrong coordinate this record exists to
        # make unconstructible.
        if not isinstance(self.bbox, (tuple, list)):
            raise ValueError(
                f"WordBox bbox must be an ordered sequence (tuple/list), got {type(self.bbox).__name__}"
            )
        object.__setattr__(self, "bbox", tuple(self.bbox))
        if len(self.bbox) != 4:
            raise ValueError(f"WordBox bbox must be four floats (x0, y0, x1, y1), got {len(self.bbox)}")
        if not all(math.isfinite(c) for c in self.bbox):
            raise ValueError(f"WordBox bbox coordinates must be finite, got {self.bbox!r}")
        x0, y0, x1, y1 = self.bbox
        if x1 <= x0 or y1 <= y0:
            raise ValueError(
                f"WordBox bbox must be non-degenerate (x1 > x0 and y1 > y0), got {self.bbox!r}"
            )
        if not self.text.strip():
            raise ValueError("WordBox text must carry a token — an empty/whitespace box is not a word")


@dataclass(frozen=True, slots=True)
class PageGeometry:
    """One page's word boxes plus its dimensions (DT-2).

    ``page`` is the 1-based scan number (DT-4; consistent with copy3's ``⟨PAGE:N⟩`` markers and
    ``page_000N.png``); ``width``/``height`` are the page-point dimensions; ``words`` is this page's
    boxes. Validity is enforced at construction (G-21): ``page`` positive, ``width``/``height``
    positive and finite; every ``words`` element must be a :class:`WordBox` (DT-2's record shape —
    anything else skipped ``WordBox``'s own gates). ``words`` may be **empty** — a genuinely blank
    page yields zero words *successfully* (DT-2: empty ≠ failed; rejecting it would force the
    backend to invent a failure on a real blank page). ``words`` is normalized to a tuple so the
    frozen guarantee holds.
    """

    page: int
    width: float
    height: float
    words: tuple[WordBox, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "words", tuple(self.words))
        # DT-2 pins the shape as tuple[WordBox, ...]: a non-WordBox row never passed WordBox's own
        # gates, so admitting one would smuggle unvalidated geometry past the construction contract.
        if not all(isinstance(w, WordBox) for w in self.words):
            raise ValueError("PageGeometry.words elements must all be WordBox records")
        # ``page`` is an int count (the 1-based scan number), so the gate is exact-type, not
        # numeric: a bare ``page <= 0`` would admit ``nan`` (compares False — the trap ``WordBox``'s
        # bbox ordering avoids), ``inf`` (genuinely > 0), and a fractional page; ``isinstance``
        # would still admit ``bool`` (an ``int`` subclass — ``True`` is not scan number 1).
        # ``type(...) is int`` closes all four. Deliberately unlike ``width``/``height`` below,
        # which are finite positive *floats* (dimensions), guarded by ``math.isfinite``.
        if not (type(self.page) is int and self.page > 0):
            raise ValueError(f"PageGeometry.page must be a positive integer scan number, got {self.page!r}")
        if not (math.isfinite(self.width) and self.width > 0):
            raise ValueError(f"PageGeometry.width must be a positive finite dimension, got {self.width!r}")
        if not (math.isfinite(self.height) and self.height > 0):
            raise ValueError(f"PageGeometry.height must be a positive finite dimension, got {self.height!r}")


@runtime_checkable
class GeometrySource(Protocol):
    """The injectable word-box seam (S2.1, DT-2): a backend yields per-page geometry on demand.

    One obligation — :meth:`read_pages` over a 1-based inclusive page range — plus an
    :attr:`engine_id` reproducibility string the matcher writes verbatim into a matched atom's
    ``geometry_engine`` provenance field (never a hardcoded string). Injectable so S2.1's matcher,
    the segmentation front-end, and tests bind to the seam, not the real PyMuPDF+Tesseract backend
    (the D6/BR-009 injected-backend posture).

    Fail-loud (backend obligation, enforced by the #36 backend, not this Protocol): missing tessdata,
    an OCR failure, a rotated page (``page.rotation != 0`` — refused outright, never silently
    de-rotated into a coordinate space the matcher does not expect; G-17), or a systemic
    off-page-box fraction (isolated off-page boxes are dropped and counted — bounded
    drop-and-count, ruled 2026-07-05) raise :class:`GeometryError`; a backend never returns
    silently-empty pages for operational failures — an empty page is a *successful* zero-word read,
    an operational failure is an exception. Emission order is **unspecified** (DT-2): no consumer
    may treat backend order as reading order.
    """

    @property
    def engine_id(self) -> str:
        """A reproducibility string built from live library versions + params (shape:
        ``pymupdf-{ver}+tesseract-{tessver}:dpi={dpi}:lang={lang}``), written verbatim into the
        matched geom's ``geometry_engine`` field."""
        ...

    def read_pages(self, first_page: int, last_page: int) -> Iterator[PageGeometry]:
        """Yield :class:`PageGeometry` for each page in ``[first_page, last_page]`` (1-based,
        inclusive — matching copy3's ``⟨PAGE:N⟩`` markers and ``page_000N.png``)."""
        ...
