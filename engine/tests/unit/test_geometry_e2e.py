"""S2.1.5 (#39) — no-witness geometry branch, end-to-end (``s2_1_plan.md`` DT-5 / DT-7; G-16).

The witness branch (PLL) has a column-ordered text witness that supplies reading order; the
detector there is only a QA cross-check. The **no-witness branch** (an image-only source) has no
such witness — the geometric detector IS the reading-order source. This is its end-to-end proof, on
a synthetic two-column page whose native text layer is empty (DT-11 tier 1): a real
PyMuPDF+Tesseract pass recovers the boxes, ``detect_columns`` recovers the gutter, and
``reading_order`` reproduces the page's true reading order — pinned by ``ordered_coverage == 1.0``.
There is NO atom stream here (R6 / §6 non-goal): S2.1's no-witness branch proves segmentation +
ordering only, not L1 capture.

Real OCR, hard-asserted (DT-11 tier 1: no skipif, no skip-masking — CI installs tesseract-ocr +
eng data). The drawn words are plain-ASCII English fixture assets (the D18 posture); the backend is
told the OCR language via a parameter, never a core literal.
"""
from __future__ import annotations

import pytest

from engine.structure import (
    ColumnDetector,
    detect_columns,
    ordered_coverage,
    reading_order,
)
from engine.structure.geometry_pymupdf import PyMuPDFTesseractBackend

# A dense two-column page: 13 known words per column (26 boxes, clear of the detector's 25-box
# floor — a real two-column page carries far more), each on its own well-separated line so OCR reads
# them reliably at dpi 300 and the line sort is unambiguous. Left column reads top-to-bottom, then
# the right column: this list IS the page's true reading order.
_LEFT = ("autumn", "harvest", "morning", "meadow", "orchard", "valley", "thicket",
         "garden", "cottage", "willow", "lantern", "chimney", "hearth")
_RIGHT = ("London", "market", "letter", "signal", "harbor", "anchor", "captain",
          "voyage", "compass", "beacon", "current", "island", "cargo")
_EXPECTED = tuple(w.casefold() for w in (*_LEFT, *_RIGHT))

_DECISION_THRESHOLD = 0.5   # test policy — a clean two-column page scores near 1.0, well clear
_HYSTERESIS_MARGIN = 0.15


def _two_column_pdf(synth):
    """A dense image-only two-column page built from the exposed PageSpec/Line primitives (the named
    two_column fixture has only 8 words, below the detector's floor)."""
    left = tuple(synth.Line(t, (80.0, 110.0 + 44.0 * i), 18.0) for i, t in enumerate(_LEFT))
    right = tuple(synth.Line(t, (360.0, 110.0 + 44.0 * i), 18.0) for i, t in enumerate(_RIGHT))
    spec = synth.PageSpec(width=612.0, height=792.0, lines=left + right)
    return synth.pdf([spec])


def _ocr_boxes(synth):
    backend = PyMuPDFTesseractBackend(_two_column_pdf(synth), language="eng", dpi=300)
    (page,) = list(backend.read_pages(1, 1))
    return page


def test_no_witness_branch_recovers_reading_order_end_to_end(synth):
    # G-16: the detector recovers the column split from the OCR boxes and reading_order reproduces the
    # page's true reading order (all expected words, in order) -> ordered_coverage == 1.0. RED
    # (mutant): break the column split (detect_columns misses the gutter / reading_order ignores it)
    # -> the columns interleave row-by-row and coverage drops below 1.0.
    page = _ocr_boxes(synth)
    recovered = {wb.text.casefold() for wb in page.words}
    assert set(_EXPECTED) <= recovered, f"OCR lost known words: {set(_EXPECTED) - recovered}"

    evidence = detect_columns(page.words, page.width)
    verdict = ColumnDetector(
        decision_threshold=_DECISION_THRESHOLD, hysteresis_margin=_HYSTERESIS_MARGIN
    ).classify(evidence)
    assert verdict.n_cols == 2, "the detector should see two columns on a clean two-column page"

    order = [t.casefold() for t in reading_order(page.words, split_x=evidence.split_x)]
    assert ordered_coverage(_EXPECTED, order) == pytest.approx(1.0)


def test_naive_full_width_order_loses_the_reading_order(synth):
    # The control that gives G-16 its teeth: WITHOUT the column split (single-column reading order),
    # the two columns interleave row by row and ordered_coverage falls below 1.0 — so the == 1.0 pin
    # above is doing real work, not passing on any ordering.
    page = _ocr_boxes(synth)
    naive = [t.casefold() for t in reading_order(page.words, split_x=None)]
    assert ordered_coverage(_EXPECTED, naive) < 1.0
