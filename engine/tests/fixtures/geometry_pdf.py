"""Synthetic image-only PDF fixture generator (S2.1.2 #36, ``s2_1_plan.md`` DT-11 tier 1).

The CI "does the real OCR path execute and honor backend contracts?" tier needs a PDF with **no
native text layer** — the only way to recover its words is a real PyMuPDF+Tesseract pass. This
module builds one deterministically: it draws known text on a scratch page, rasterizes that page
to a pixmap, and re-embeds the *image* in a fresh PDF. The result has no text layer by construction
— ``page.get_text() == ""`` for every page (asserted by the tests) — so a green OCR test cannot be
a native-text-extraction false positive.

The drawn words are **plain-ASCII English** (DT-11) because they are a *test fixture asset* (the
D18 differ-fixture posture), not a core literal: the language the backend OCRs with is passed to
the backend as a required parameter (``language=``), and this generator lives under ``tests/`` where
the S0.2 neutrality guard does not scan. Plain ASCII specifically — no accented glyph — so a page
OCR'd with ``lang="eng"`` (as #39's column detector will) carries no character Tesseract could
misread for that reason. The words are short, high-contrast, and large so Tesseract reads them
reliably at the test DPIs.

Page variants mirror DT-11's inventory — ``single_column`` / ``two_column`` / ``near_blank`` /
``dark`` — plus per-page ``rotation`` and ``cropbox`` overrides (G-17's rotated-page red and G-8's
cropped-page containment bind). The rotation/crop are applied to the *final image page*, so a
reopened fixture reports them exactly as a real rotated/cropped scan would.

``render_dpi`` fixes the resolution of the image embedded in the PDF; it is independent of the
backend's OCR ``dpi``. The ground-truth test (G-8) holds ``render_dpi`` fixed and varies the
backend's OCR dpi: each resolution must land boxes at the same drawn page-point origins —
agreement with ground truth, not sub-point cross-dpi agreement, which real Tesseract does not
provide (box edges quantize ~0.5–0.65 pt between 150 and 300 dpi).
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import fitz  # PyMuPDF — declared engine dependency


@dataclass(frozen=True)
class Line:
    """One run of known text and where its baseline starts, in page-point space."""

    text: str
    origin: tuple[float, float]
    fontsize: float = 26.0


@dataclass(frozen=True)
class PageSpec:
    """One synthetic page: its point dimensions, the text drawn on it, and optional scan quirks.

    ``background`` fills the whole page before text (the dark-page variant); ``text_color`` lets a
    dark page carry light-on-dark marks. ``rotation`` (0/90/180/270) and ``cropbox`` (a page-point
    rect ``(x0, y0, x1, y1)`` inside the mediabox) are applied to the final image page, so a
    reopened fixture reports them like a real scan.
    """

    width: float
    height: float
    lines: tuple[Line, ...] = ()
    background: tuple[float, float, float] | None = None
    text_color: tuple[float, float, float] = (0.0, 0.0, 0.0)
    rotation: int = 0
    cropbox: tuple[float, float, float, float] | None = None

    @property
    def words(self) -> tuple[str, ...]:
        """The known tokens drawn on this page (whitespace-split), the OCR ground truth."""
        return tuple(tok for ln in self.lines for tok in ln.text.split())


# --- Named page variants (DT-11 inventory) ------------------------------------------------------ #

_LETTER = (612.0, 792.0)


def single_column_page() -> PageSpec:
    """One column of a few large, clearly separated words — the reliable-OCR page the
    coordinate-space ground-truth reds (G-8) run on. Plain-ASCII English (DT-11)."""
    w, h = _LETTER
    return PageSpec(
        width=w,
        height=h,
        lines=(
            Line("Boston", (90.0, 140.0), 34.0),
            Line("Harbor", (90.0, 230.0), 34.0),
            Line("Window", (90.0, 320.0), 34.0),
        ),
    )


def two_column_page() -> PageSpec:
    """Two populated columns with a central gutter — the layout the slice-2 column detector
    (#39) trains on; here it exists as an image-only page whose native text layer is empty.
    Plain-ASCII English (DT-11): the detector will OCR this with ``lang="eng"``, so no accented
    glyph may hide in it."""
    w, h = _LETTER
    left = tuple(Line(t, (80.0, 150.0 + 70.0 * i), 22.0) for i, t in enumerate(("autumn", "harvest", "morning", "meadow")))
    right = tuple(Line(t, (360.0, 150.0 + 70.0 * i), 22.0) for i, t in enumerate(("London", "market", "letter", "window")))
    return PageSpec(width=w, height=h, lines=left + right)


def near_blank_page() -> PageSpec:
    """A mostly empty page (a lone folio-style number) — the low-ink / low-token-yield end of
    the density continuum (DT-6). Image-only like the rest."""
    w, h = _LETTER
    return PageSpec(width=w, height=h, lines=(Line("12", (300.0, 740.0), 14.0),))


def dark_page() -> PageSpec:
    """A high-ink page (a near-black fill) with negligible real text — the ``non_text_dark`` end
    of the continuum (DT-6; the hallucination-prone endpaper). Image-only."""
    w, h = _LETTER
    return PageSpec(
        width=w,
        height=h,
        background=(0.06, 0.06, 0.06),
        text_color=(0.10, 0.10, 0.10),
        lines=(Line("...", (300.0, 400.0), 12.0),),
    )


def rotated(spec: PageSpec, degrees: int = 90) -> PageSpec:
    """The same page marked rotated — G-17's fail-loud red (``page.rotation != 0``)."""
    return replace(spec, rotation=degrees)


def cropped(spec: PageSpec, cropbox: tuple[float, float, float, float]) -> PageSpec:
    """The same page with a cropbox tighter than its mediabox — G-8's cropped-page containment
    bind (DT-4: coords are relative to ``page.rect``, the cropbox-derived visible rect)."""
    return replace(spec, cropbox=cropbox)


# --- Rendering: known text -> pixmap -> image-only PDF ------------------------------------------- #


def _draw(spec: PageSpec, render_dpi: int) -> fitz.Pixmap:
    """Draw one spec's text on a scratch page and rasterize it to a pixmap at ``render_dpi``."""
    scratch = fitz.open()
    page = scratch.new_page(width=spec.width, height=spec.height)
    if spec.background is not None:
        page.draw_rect(page.rect, color=spec.background, fill=spec.background)
    for ln in spec.lines:
        page.insert_text(ln.origin, ln.text, fontsize=ln.fontsize, color=spec.text_color)
    pix = page.get_pixmap(dpi=render_dpi)
    scratch.close()
    return pix


def render_image_only_pdf(specs: list[PageSpec] | tuple[PageSpec, ...], *, render_dpi: int = 200) -> bytes:
    """Build a PDF whose every page is a re-embedded raster image of a drawn ``PageSpec``.

    No page carries a text layer (``get_text() == ""``), so the words are recoverable only by a
    real OCR pass. Per-page ``rotation`` / ``cropbox`` are applied to the final image page.
    """
    if not specs:
        raise ValueError("render_image_only_pdf needs at least one PageSpec")
    out = fitz.open()
    for spec in specs:
        pix = _draw(spec, render_dpi)
        page = out.new_page(width=spec.width, height=spec.height)
        page.insert_image(page.rect, pixmap=pix)
        if spec.cropbox is not None:
            page.set_cropbox(fitz.Rect(*spec.cropbox))
        if spec.rotation:
            page.set_rotation(spec.rotation)
    data = out.tobytes()
    out.close()
    return data


def write_image_only_pdf(path, specs, *, render_dpi: int = 200):
    """Write :func:`render_image_only_pdf` to ``path`` and return it (the backend opens a path)."""
    from pathlib import Path

    path = Path(path)
    path.write_bytes(render_image_only_pdf(list(specs), render_dpi=render_dpi))
    return path
