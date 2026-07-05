"""The NORMAL-path geometry backend: PyMuPDF + Tesseract OCR (S2.1.2 #36; ``s2_1_plan.md``
DT-1/DT-2/DT-4/DT-11).

Both PLL scans are images (0 native boxes, S2.0 gate), so the word-box layer is *generated* fresh
by an OCR pass — ``page.get_textpage_ocr`` then ``page.get_text("words", …)``, the invocation the
S2.0 probe validated. This module is that pass behind the :class:`~engine.structure.geometry`
seam: one :class:`GeometrySource` implementation yielding :class:`PageGeometry` per page.

The core carries **no** language or dpi opinion (invariant I4; the S0.2 neutrality guard scans this
file): ``language`` and ``dpi`` are **required constructor parameters with no defaults** (G-1) —
PLL's Tesseract language code and its 300-dpi setting live in book config and are passed in. The
``engine_id`` reproducibility string interpolates ``lang={language}`` from the parameter, so no
language literal appears here (G-2) — including in this docstring, which the guard scans too.

Fail-loud, no per-page degrade (the deliberate opposite of ``ocr``'s degrade-to-``[OCR_ERROR]``
posture — DT-1): a rotated page (``page.rotation != 0`` — S2.1 is unrotated-only, G-17), an OCR
failure / missing tessdata (G-17), a box outside the page rect (G-8), or an out-of-range request
raises :class:`GeometryError`. Coordinates are PDF **page-point** space (DT-4) — the dpi-independent
space stable across re-renders — so a box ⊆ ``page.rect`` and a word's box lands at its drawn
page-point ground truth at any OCR dpi (G-8; the P-3 ground-truth form — box *edges* still quantize
sub-point between resolutions, which is why the bind is to ground truth, not cross-dpi equality).
Tesseract's empty-text / degenerate artifacts are dropped before record construction and
counted in :attr:`dropped_boxes` (DT-2 normalization) — dropped-and-counted, never a silent hole or
a construction crash. Emission order is unspecified by the seam (DT-2): boxes are yielded in
whatever order ``get_text("words")`` returns; no consumer may read it as reading order.
"""

from __future__ import annotations

import math
import subprocess
from collections.abc import Iterator
from pathlib import Path

import fitz  # PyMuPDF — a declared engine dependency (pyproject: pymupdf>=1.27.2.2)

from engine.structure.geometry import GeometryError, PageGeometry, WordBox

# A real OCR box sits inside the page it was read from by construction; this 1 pt slack only
# absorbs rounding at the page edge. A box beyond it is corruption (e.g. a pixmap-space coordinate
# ~dpi/72× too large, or a hallucinated off-page box), not an artifact to drop — it fails loud (G-8).
_RECT_TOLERANCE_PT = 1.0


def _tesseract_version() -> str:
    """The Tesseract version, for the ``engine_id`` provenance string.

    Read from the ``tesseract`` CLI — the same package that provides the libtesseract MuPDF's OCR
    links against on both target platforms (homebrew locally, ``apt`` in CI). NOTE (unverified):
    whether the CLI version is byte-identical to the linked library's is not confirmed; the current
    bindings expose no library-side version to check it against. It is a best-effort provenance
    token, not a matched invariant. A missing binary is fail-loud (``GeometryError``): a backend
    that can OCR but cannot name its OCR engine cannot honestly stamp provenance.
    """
    try:
        proc = subprocess.run(
            ["tesseract", "--version"], capture_output=True, text=True, check=True
        )
    except (OSError, subprocess.SubprocessError) as exc:  # not found / non-zero exit
        raise GeometryError(f"could not read the tesseract version (is tesseract installed?): {exc}") from exc
    banner = (proc.stdout or proc.stderr).strip().splitlines()
    # First line is "tesseract X.Y.Z"; take the version token, fall back to the whole banner.
    head = banner[0].split() if banner else []
    return head[1] if len(head) >= 2 else (banner[0].strip() if banner else "unknown")


class PyMuPDFTesseractBackend:
    """A :class:`~engine.structure.geometry.GeometrySource` over a scan PDF via PyMuPDF+Tesseract.

    ``language`` (a Tesseract language code, e.g. from book config) and ``dpi`` (the OCR render
    resolution) are **required, no defaults** (G-1) — a baked default would be a scan-profile
    opinion in neutral core. ``tessdata`` overrides the tessdata directory; when ``None`` the
    directory is auto-discovered (``fitz.get_tessdata()`` — honors ``TESSDATA_PREFIX``). The PDF is
    opened lazily on the first :meth:`read_pages`, so construction is pure (no I/O) and a caller can
    read :attr:`engine_id` without a real file — though reading it does shell out to the
    ``tesseract`` CLI for the version token (fail-loud without the binary).
    """

    def __init__(self, pdf_path, *, language: str, dpi: int, tessdata: str | None = None) -> None:
        if not (isinstance(language, str) and language.strip()):
            raise ValueError(f"language must be a non-empty Tesseract code, got {language!r}")
        if not (type(dpi) is int and dpi > 0):
            raise ValueError(f"dpi must be a positive integer, got {dpi!r}")
        self._pdf_path = Path(pdf_path)
        self._language = language
        self._dpi = dpi
        self._tessdata = tessdata
        self._doc: fitz.Document | None = None
        self._engine_id: str | None = None
        #: Per-page count of empty-text / degenerate OCR boxes dropped before record construction
        #: (DT-2). Keyed by 1-based scan page; populated as :meth:`read_pages` runs. #37's sidecar
        #: surfaces it as the per-page ``dropped_boxes`` stat.
        self.dropped_boxes: dict[int, int] = {}

    @property
    def engine_id(self) -> str:
        """``pymupdf-{ver}+tesseract-{ver}:dpi={dpi}:lang={lang}`` — versions + params, cached.

        The matcher (#37) writes this verbatim into a matched atom's ``geometry_engine`` provenance
        field (G-3). ``lang=``/``dpi=`` are interpolated from the parameters — no language literal in
        core (G-2)."""
        if self._engine_id is None:
            self._engine_id = (
                f"pymupdf-{fitz.pymupdf_version}+tesseract-{_tesseract_version()}"
                f":dpi={self._dpi}:lang={self._language}"
            )
        return self._engine_id

    @property
    def backend_params(self) -> dict[str, object]:
        """The structured reproducibility contract DT-9's sidecar persists as ``backend_params``
        (``s2_1_plan.md`` schema) — the same four facts :attr:`engine_id` bundles into a display
        string, exposed structurally so #37's sidecar writer and S3.1's replay check read them
        without parsing the string or reaching past the seam (WIDE-audit forward-friction)."""
        return {
            "dpi": self._dpi,
            "language": self._language,
            "pymupdf": fitz.pymupdf_version,
            "tesseract": _tesseract_version(),
        }

    def _open(self) -> fitz.Document:
        if self._doc is None:
            try:
                self._doc = fitz.open(self._pdf_path)
            except Exception as exc:  # missing / unreadable / not a PDF
                raise GeometryError(f"could not open scan PDF {self._pdf_path}: {exc}") from exc
        return self._doc

    def _resolve_tessdata(self) -> str:
        if self._tessdata is not None:
            return self._tessdata
        try:
            found = fitz.get_tessdata()
        except Exception as exc:
            # pymupdf RAISES (RuntimeError) when tesseract/tessdata is absent — every failure site
            # in the pinned versions raises rather than returning falsy, so without this wrap the
            # bare RuntimeError escaped the axis (the G-17 fail-loud path itself was the escape).
            raise GeometryError(
                f"tessdata directory not found — set TESSDATA_PREFIX or pass tessdata= to the backend ({exc})"
            ) from exc
        if not found:  # belt for a future falsy-returning pymupdf
            raise GeometryError(
                "tessdata directory not found — set TESSDATA_PREFIX or pass tessdata= to the backend"
            )
        return found

    def read_pages(self, first_page: int, last_page: int) -> Iterator[PageGeometry]:
        """Yield :class:`PageGeometry` for each page in ``[first_page, last_page]`` (1-based,
        inclusive). Fail-loud on rotation, OCR failure, an off-page box, or an out-of-range request
        (GeometryError). A blank page yields zero words *successfully* (DT-2: empty ≠ failed)."""
        doc = self._open()
        n = doc.page_count
        if first_page < 1 or last_page < first_page or last_page > n:
            raise GeometryError(
                f"page range [{first_page}, {last_page}] out of bounds for a {n}-page PDF (1-based inclusive)"
            )
        tessdata = self._resolve_tessdata()
        for num in range(first_page, last_page + 1):
            page = doc[num - 1]
            # Rotation precedes OCR: S2.1 is unrotated-only, and a rotated page must fail before it
            # can emit coordinates in a silently-transformed space (G-17).
            if page.rotation != 0:
                raise GeometryError(
                    f"page {num} is rotated ({page.rotation}°) — S2.1 supports only unrotated pages; "
                    f"refusing to emit coordinates in a transformed space"
                )
            rect = page.rect
            try:
                textpage = page.get_textpage_ocr(
                    flags=0, language=self._language, dpi=self._dpi, full=True, tessdata=tessdata
                )
                raw_words = page.get_text("words", textpage=textpage)
            except GeometryError:
                raise
            except Exception as exc:  # missing tessdata, OCR init/runtime failure — fail loud, no degrade
                raise GeometryError(f"OCR failed on page {num}: {exc}") from exc
            yield self._build_page(num, rect, raw_words)

    def _build_page(self, num: int, rect: fitz.Rect, raw_words) -> PageGeometry:
        words: list[WordBox] = []
        dropped = 0
        for entry in raw_words:
            x0, y0, x1, y1, text = entry[0], entry[1], entry[2], entry[3], entry[4]
            # DT-2 normalization: drop Tesseract's empty-text / degenerate artifacts (and count them)
            # BEFORE record construction — a real artifact must never crash WordBox nor vanish silently.
            if not text.strip() or x1 <= x0 or y1 <= y0:
                dropped += 1
                continue
            # Non-finite coord → corruption, fail loud AS GeometryError. A NaN slips both the
            # degenerate drop above and the OOB bound below (NaN compares False on every operator),
            # so without this it would reach WordBox and escape the axis as a bare ValueError — the
            # "any geometry fault → GeometryError" contract hole both audit lenses flagged. inf is
            # already caught by the OOB check; this closes NaN.
            if not all(math.isfinite(c) for c in (x0, y0, x1, y1)):
                raise GeometryError(
                    f"OCR box ({x0}, {y0}, {x1}, {y1}) on page {num} has a non-finite coordinate — "
                    f"refusing to emit corrupt geometry"
                )
            # Off-page box → corruption, not a droppable artifact: fail loud (G-8). A pixmap-space
            # coordinate leak would trip this by ~dpi/72×.
            if (
                x0 < rect.x0 - _RECT_TOLERANCE_PT
                or y0 < rect.y0 - _RECT_TOLERANCE_PT
                or x1 > rect.x1 + _RECT_TOLERANCE_PT
                or y1 > rect.y1 + _RECT_TOLERANCE_PT
            ):
                raise GeometryError(
                    f"OCR box ({x0}, {y0}, {x1}, {y1}) on page {num} lies outside the page rect "
                    f"{tuple(rect)} — refusing to emit an off-page coordinate"
                )
            words.append(WordBox(text=text, bbox=(x0, y0, x1, y1)))
        self.dropped_boxes[num] = dropped
        return PageGeometry(page=num, width=rect.width, height=rect.height, words=tuple(words))
