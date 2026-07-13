"""S2.1.1 (#35) — ``geometry.py`` records + ``GeometrySource`` seam + ``GeometryError``.

Home of the record-validity invariants (G-21) and the seam/error contract for the geometry axis
(``s2_1_plan.md`` DT-1/DT-2); #36 extends this file with the real PyMuPDF+Tesseract backend
(G-1/G-8/G-17), which is why the file is named for the backend it will grow into.

The records are the *untrusted-until-matched* box layer S2.1's matcher aligns to witness text: a
:class:`WordBox` is one OCR token + its page-point bbox, a :class:`PageGeometry` is one page's
boxes + dimensions. Validity is enforced at construction (G-21) — an invalid record is
unconstructible, never a silently-wrong coordinate that corrupts S5 re-bind downstream. The seam
(:class:`GeometrySource`) is the injectable Protocol backends satisfy; :class:`GeometryError`
(exit 13) is the axis's fail-loud carrier, distinct from ``ocr``'s degrade-to-sentinel
:class:`BackendError` (DT-1).

Red-first (§9, ``feedback_red_first_tests``): each G-21 guard is proven to red on its named
violation by the mutation pass over ``geometry.__post_init__`` after green; the import-absent
collection failure is only the first, coarse red.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import fitz  # PyMuPDF — a declared engine dependency; used below for monkeypatch targets (#36)
import pytest

from engine.errors import BackendError, EngineError
from engine.structure import (
    GeometryError,
    PageGeometry,
    WordBox,
)
from engine.structure.geometry_pymupdf import PyMuPDFTesseractBackend

# The injectable seam double (``_FakeGeometrySource``) lives in ``tests/conftest.py`` behind the
# ``geom`` fixture namespace — shared there because the matcher/segmentation tiers (#37+) bind to
# the same seam (the BR-009/D6 injected-backend posture, the ``acq`` exposure pattern).


def _box(text: str = "parola", bbox=(1.0, 2.0, 3.0, 4.0)) -> WordBox:
    return WordBox(text=text, bbox=bbox)


# --- WordBox validity (G-21) --------------------------------------------------------------------- #


def test_wordbox_valid_construction_normalizes_bbox_to_a_tuple():
    wb = WordBox(text="parola", bbox=[1.0, 2.0, 3.0, 4.0])
    assert wb.text == "parola"
    assert wb.bbox == (1.0, 2.0, 3.0, 4.0)
    assert isinstance(wb.bbox, tuple)  # a retained mutable list would undermine the frozen guarantee


@pytest.mark.parametrize("pos", [0, 1, 2, 3])
@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_wordbox_rejects_non_finite_coordinate_at_any_position(pos, bad):
    # EVERY coordinate must be finite-checked, not just x1/y1 — else a mutant that narrows the guard
    # to a subset of positions survives. nan at x0/y0 is the sharpest case: it compares False, so it
    # would slip past the degenerate x1<=x0 comparison the finiteness guard is deliberately ordered
    # before (the ordering the guard's own reasoning rests on).
    bbox = [1.0, 2.0, 5.0, 6.0]
    bbox[pos] = bad
    with pytest.raises(ValueError, match="finite"):
        WordBox(text="x", bbox=tuple(bbox))


@pytest.mark.parametrize("bbox", [(3.0, 0.0, 3.0, 4.0), (3.0, 0.0, 1.0, 4.0)])
def test_wordbox_rejects_degenerate_x(bbox):
    with pytest.raises(ValueError, match="degenerate|non-degenerate"):
        WordBox(text="x", bbox=bbox)


@pytest.mark.parametrize("bbox", [(0.0, 4.0, 3.0, 4.0), (0.0, 4.0, 3.0, 1.0)])
def test_wordbox_rejects_degenerate_y(bbox):
    with pytest.raises(ValueError, match="degenerate|non-degenerate"):
        WordBox(text="x", bbox=bbox)


@pytest.mark.parametrize("text", ["", "   "])  # a "\t\n" row shared the "   " .strip() path (#56)
def test_wordbox_rejects_empty_or_whitespace_text(text):
    # A box with no token is not a word — the backend drops Tesseract's empty-text artifacts before
    # construction (DT-2 normalization), so an empty-text WordBox is a contract violation, not data.
    with pytest.raises(ValueError, match="text"):
        WordBox(text=text, bbox=(1.0, 2.0, 3.0, 4.0))


@pytest.mark.parametrize("bbox", [(1.0, 2.0, 3.0), (1.0, 2.0, 3.0, 4.0, 5.0)])
def test_wordbox_rejects_wrong_length_bbox(bbox):
    with pytest.raises(ValueError, match="four"):
        WordBox(text="x", bbox=bbox)


def test_wordbox_rejects_unordered_bbox_input():
    # A set has no coordinate order: {4,1,3,2} would tuple-ize in iteration order and construct a
    # plausible-but-reordered box — exactly the "silently-wrong coordinate" G-21 exists to make
    # unconstructible. Only an ordered sequence (tuple/list) carries (x0, y0, x1, y1).
    with pytest.raises(ValueError, match="ordered"):
        WordBox(text="x", bbox={4.0, 1.0, 3.0, 2.0})


def test_wordbox_is_frozen():
    wb = _box()
    with pytest.raises((AttributeError, TypeError)):
        wb.text = "mutated"  # type: ignore[misc]


# --- PageGeometry validity (G-21) ---------------------------------------------------------------- #


def test_pagegeometry_valid_construction_normalizes_words_to_a_tuple():
    words = [_box("uno"), _box("due")]
    pg = PageGeometry(page=52, width=612.0, height=792.0, words=words)
    assert pg.page == 52
    assert isinstance(pg.words, tuple)
    assert len(pg.words) == 2


def test_pagegeometry_allows_zero_words_a_blank_page_is_successfully_empty():
    # DT-2: "empty != failed" — a genuinely blank page yields zero words SUCCESSFULLY. Rejecting it
    # would force the backend to raise on a real blank page, which would be inventing failure.
    pg = PageGeometry(page=1, width=612.0, height=792.0, words=())
    assert pg.words == ()


def test_pagegeometry_rejects_non_wordbox_words_elements():
    # DT-2 pins the record shape as `words: tuple[WordBox, ...]` — a row that is not a WordBox
    # never went through WordBox's own G-21 gates, so admitting it would smuggle unvalidated
    # geometry past the whole construction-time contract.
    with pytest.raises(ValueError, match="WordBox"):
        PageGeometry(page=1, width=612.0, height=792.0, words=("not a box",))


@pytest.mark.parametrize("page", [0, -1, math.nan, math.inf, -math.inf, 1.5, True])
def test_pagegeometry_rejects_non_positive_or_non_integer_page(page):
    # `page` is the 1-based scan number — an exact int. `page <= 0` alone would admit nan (compares
    # False — the trap WordBox's bbox ordering avoids), inf (genuinely > 0), and a fractional page;
    # `isinstance` would still admit bool (an int subclass — True is not scan number 1). The
    # exact-type guard closes all four. (Distinct from width/height, which are finite positive
    # *floats* — dimensions, not counts.)
    with pytest.raises(ValueError, match="page"):
        PageGeometry(page=page, width=612.0, height=792.0, words=())


@pytest.mark.parametrize("width", [0.0, -1.0, math.nan, math.inf])
def test_pagegeometry_rejects_non_positive_or_non_finite_width(width):
    with pytest.raises(ValueError, match="width"):
        PageGeometry(page=1, width=width, height=792.0, words=())


@pytest.mark.parametrize("height", [0.0, -1.0, math.nan, math.inf])
def test_pagegeometry_rejects_non_positive_or_non_finite_height(height):
    with pytest.raises(ValueError, match="height"):
        PageGeometry(page=1, width=612.0, height=height, words=())


def test_pagegeometry_is_frozen():
    pg = PageGeometry(page=1, width=612.0, height=792.0, words=())
    with pytest.raises((AttributeError, TypeError)):
        pg.page = 2  # type: ignore[misc]


# --- GeometrySource seam (DT-2) ------------------------------------------------------------------ #
# (Two presence-only seam smokes were folded out (#56): a @runtime_checkable isinstance on the
# conftest double, and an engine_id sentinel echo that exercised no src code. The shape/behaviour
# guarantees live in the read_pages test below and the real backend's engine_id tests.)


def test_read_pages_yields_pagegeometry_over_the_inclusive_1_based_range(geom):
    pages = [PageGeometry(page=n, width=612.0, height=792.0, words=[_box()]) for n in (5, 6, 7)]
    src = geom.Source(pages=pages)
    got = list(src.read_pages(5, 7))  # 1-based INCLUSIVE (matches copy3's ⟨PAGE:N⟩ / page_000N.png)
    assert [p.page for p in got] == [5, 6, 7]
    assert all(isinstance(p, PageGeometry) for p in got)


def test_fake_source_raises_on_an_unseeded_in_range_page(geom):
    # A real backend yields EVERY page in range (a blank page = zero words, DT-2); silently
    # skipping one would model an impossible backend. The double raises KeyError on an unseeded
    # page (the _FakeFetcher posture), so a #37 fixture gap is a loud error, not a quiet hole.
    pages = [PageGeometry(page=5, width=612.0, height=792.0, words=())]
    with pytest.raises(KeyError):
        list(geom.Source(pages=pages).read_pages(5, 6))


def test_fake_source_rejects_duplicate_seeded_pages(geom):
    # {p.page: p} would silently last-win on a duplicate page number — a #37 fixture bug that
    # deserves an error at seeding time, not a quietly-halved page set.
    p = PageGeometry(page=5, width=612.0, height=792.0, words=())
    with pytest.raises(ValueError, match="duplicate"):
        geom.Source(pages=[p, p])


# --- GeometryError: exit 13, fail-loud, NOT a BackendError reuse (DT-1) --------------------------- #


def test_geometry_error_is_an_engine_error_at_exit_code_13():
    assert issubclass(GeometryError, EngineError)
    assert GeometryError.exit_code == 13


def test_geometry_error_is_not_a_backenderror_the_two_failure_contracts_differ():
    # DT-1: BackendError (exit 5) degrades per-page to an [OCR_ERROR] sentinel; GeometryError is
    # fail-loud with NO per-page degrade. Reusing exit 5 would put two contradictory contracts under
    # one code — so GeometryError must be its own type at its own code.
    assert not issubclass(GeometryError, BackendError)
    assert GeometryError.exit_code != BackendError.exit_code


# ================================================================================================ #
# S2.1.2 (#36) — the real PyMuPDF+Tesseract backend (DT-2/DT-4/DT-11; G-1, G-8, G-17).
#
# The tests below OCR the synthetic image-only PDF fixtures (``synth`` fixture) with a real
# Tesseract pass — hard-asserted in CI (DT-11 tier 1: no skipif, no skip-masking; the CI workflow
# installs tesseract-ocr + eng data). English drawn text is a fixture asset; the backend is told
# which language to OCR with via a *parameter* (``language=``), never a baked literal (G-2 lives in
# ``test_structure_neutrality``). Tests that exercise only the fail-loud / drop / containment guards
# monkeypatch the OCR call, so they need no tesseract.
# ================================================================================================ #


def _word(text, bbox):
    """A raw PyMuPDF ``get_text('words', ...)`` tuple: (x0, y0, x1, y1, word, block, line, word_no)."""
    return (*bbox, text, 0, 0, 0)


def _stub_ocr(monkeypatch, words):
    """Make the backend's OCR path return ``words`` without a real Tesseract pass: neutralize
    ``get_textpage_ocr`` (returns a sentinel textpage) and have ``get_text('words', …)`` yield the
    canned tuples. Lets the fail-loud / drop / containment guards be unit-tested with no tesseract."""
    monkeypatch.setattr(fitz.Page, "get_textpage_ocr", lambda self, **kw: object())
    monkeypatch.setattr(fitz.Page, "get_text", lambda self, *a, **kw: list(words))


# --- G-1: language + dpi are REQUIRED constructor params, no defaults ---------------------------- #


def test_backend_requires_dpi_no_default():
    # RED (G-1): give `dpi` a default → this stops raising. `language`/`dpi` are a scan-profile
    # opinion; a default in core is exactly the leak the neutrality budget forbids. Kw-only + no
    # default ⇒ omitting `dpi` is a bind-time TypeError, raised BEFORE the body opens any PDF (so the
    # path can be a bare string).
    with pytest.raises(TypeError):
        PyMuPDFTesseractBackend("/some/scan.pdf", language="eng")


def test_backend_requires_language_no_default():
    # RED (G-1): give `language` a default → this stops raising. Symmetric to the dpi row; the two
    # reds fail independently so a default on either param is caught.
    with pytest.raises(TypeError):
        PyMuPDFTesseractBackend("/some/scan.pdf", dpi=300)


# (A both-params-missing test was folded out (#56): any state failing it also fails one of the two
# independent single-param reds above — it bound only Python's missing-kwarg TypeError.)


# --- engine_id: encodes live versions + params (the string #37's matcher writes verbatim) -------- #


def test_engine_id_encodes_versions_and_the_configured_params():
    # #36 fixes the reproducibility string's shape (pymupdf-{ver}+tesseract-{ver}:dpi=..:lang=..);
    # #37's G-3 proves the matcher writes it verbatim. `lang=`/`dpi=` are interpolated from the
    # params — no language literal in core (G-2). Reads the real tesseract version (subprocess).
    be = PyMuPDFTesseractBackend("/some/scan.pdf", language="eng", dpi=300)
    eid = be.engine_id
    assert eid.startswith("pymupdf-")
    assert "+tesseract-" in eid
    assert eid.endswith(":dpi=300:lang=eng")
    assert fitz.pymupdf_version in eid


# --- G-8: page-point coordinate space — containment + ground-truth binding ----------------------- #


def test_read_pages_recovers_known_words_as_page_point_boxes_inside_the_rect(synth):
    # Real OCR happy path (DT-11 tier 1: "the real OCR path executes"). The known drawn words are
    # recovered, and every box comes back in PDF page-point space (DT-4), so every box ⊆ the page
    # rect — a box in raw *pixmap* space would exceed width/height by ~dpi/72 and red this.
    spec = synth.single_column()
    be = PyMuPDFTesseractBackend(synth.pdf([spec]), language="eng", dpi=300)
    (pg,) = list(be.read_pages(1, 1))
    recovered = {wb.text for wb in pg.words}
    assert set(spec.words) <= recovered, f"OCR lost known words: {set(spec.words) - recovered}"
    for wb in pg.words:
        x0, y0, x1, y1 = wb.bbox
        assert -1.0 <= x0 and -1.0 <= y0 and x1 <= pg.width + 1.0 and y1 <= pg.height + 1.0, (
            f"box {wb.bbox} escapes page rect ({pg.width}x{pg.height}) — pixmap coords leaked?"
        )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"language": "", "dpi": 300},       # empty language
        {"language": "   ", "dpi": 300},    # whitespace-only language
        {"language": "eng", "dpi": 0},      # non-positive dpi
        {"language": "eng", "dpi": -300},   # negative dpi
        {"language": "eng", "dpi": 1.5},    # non-integer dpi
        {"language": "eng", "dpi": True},   # bool is an int subclass — True is not a resolution (type trap)
    ],
)
def test_backend_rejects_invalid_language_or_dpi_values(kwargs):
    # The constructor's value guards (separate from G-1's required-ness): an empty language or a
    # non-positive / non-integer / bool dpi is a misconfiguration that would otherwise fail confusingly
    # deep in the OCR call. `type(dpi) is int` (not isinstance) is what rejects True — the same bool
    # trap PageGeometry.page guards against.
    with pytest.raises(ValueError):
        PyMuPDFTesseractBackend("/some/scan.pdf", **kwargs)


def test_backend_params_expose_the_dt9_reproducibility_contract():
    # DT-9's sidecar persists `backend_params: {dpi, language, pymupdf, tesseract}` beside engine_id;
    # exposing it structurally keeps #37's sidecar writer off the private `_dpi`/`_language` and off
    # parsing the engine_id display string (audit forward-friction). Consistency: the params the
    # string bundles are the params the dict names.
    be = PyMuPDFTesseractBackend("/some/scan.pdf", language="eng", dpi=300)
    params = be.backend_params
    assert params["dpi"] == 300 and params["language"] == "eng"
    assert params["pymupdf"] == fitz.pymupdf_version
    assert isinstance(params["tesseract"], str) and params["tesseract"]
    assert be.engine_id == f"pymupdf-{params['pymupdf']}+tesseract-{params['tesseract']}:dpi=300:lang=eng"


def test_engine_id_and_backend_params_interpolate_per_instance_values():
    # RED (audit F3/F13 / hunt M5-M6): with only the (300, "eng") pair ever asserted, a
    # constant-interpolation mutant (":dpi=300" hardcoded in the f-string) or a class-level cache
    # poisoning differing-param instances survived. Two live instances with distinct params must
    # each report their own values — and the first instance's cache must survive the second's.
    a = PyMuPDFTesseractBackend("/some/scan.pdf", language="eng", dpi=300)
    b = PyMuPDFTesseractBackend("/some/scan.pdf", language="deu", dpi=150)
    assert a.engine_id.endswith(":dpi=300:lang=eng")
    assert b.engine_id.endswith(":dpi=150:lang=deu")
    assert a.engine_id.endswith(":dpi=300:lang=eng"), "instance a's cached engine_id poisoned by b"
    assert b.backend_params["dpi"] == 150 and b.backend_params["language"] == "deu"


_GROUND_TRUTH_TOL_PT = 15.0  # font side-bearing/descender + build wobble (observed <3 pt) — and far
#                              below the ~280 pt page-space-vs-pixmap-space gap this test rules on.


@pytest.mark.parametrize("dpi", [150, 300])
def test_ocr_boxes_land_at_page_point_ground_truth_not_pixmap_space(synth, dpi):
    # RED (G-8 page-space / BR-022 seed; P-3's ground-truth-at-each-dpi form, superseding the
    # original ≤0.5 pt cross-dpi *difference* form — ledger record in s2_1_plan.md P-3/DT-4, which
    # owns the ruling's date and stamp). Prove coords are in PDF page-point space DIRECTLY: a word drawn
    # at a known page-point origin (X, baseline_Y) comes back with its box at ~(X, Y) — NOT at the
    # pixmap-space position (X·dpi/72, …). Run independently at dpi 150 and 300: each resolution
    # landing on the SAME page-point ground truth *is* dpi-independence, without binding to the
    # sub-pixel cross-dpi stability real Tesseract lacks (its box edges quantize ~0.5–0.65 pt
    # between 150 and 300 — measured in-session 2026-07-04; no durable run-report artifact exists
    # yet, to be formalized as a reproducible drift probe / #37 run report). The signal-to-noise is
    # ~30:1 at dpi 150 and ~100:1 at 300 (offset <3 pt vs 97.5/285 pt pixmap leaks), so the
    # tolerance is not knife-edge and is immune to the CI Tesseract build differing from the local
    # one. A mutant emitting pixmap coords lands ~dpi/72× off ground truth → reds hard.
    spec = synth.single_column()
    be = PyMuPDFTesseractBackend(synth.pdf([spec]), language="eng", dpi=dpi)
    (pg,) = list(be.read_pages(1, 1))
    boxes = {wb.text: wb.bbox for wb in pg.words}
    for line in spec.lines:
        tokens = line.text.split()
        assert len(tokens) == 1, "this test assumes single-token lines so origin == the word's origin"
        word = tokens[0]
        assert word in boxes, f"OCR lost known word {word!r} at dpi {dpi}"
        x0, y0, x1, y1 = boxes[word]
        draw_x, baseline_y = line.origin
        # x0 aligns with the draw origin; y1 (box bottom) aligns with the text baseline (these words
        # carry no descenders). Both must be near ground truth AND nowhere near the pixmap position.
        assert abs(x0 - draw_x) <= _GROUND_TRUTH_TOL_PT, (
            f"{word!r} x0={x0:.1f} is not within {_GROUND_TRUTH_TOL_PT} pt of drawn x={draw_x} at dpi {dpi} "
            f"(pixmap-space would be ~{draw_x * dpi / 72.0:.0f})"
        )
        assert abs(y1 - baseline_y) <= _GROUND_TRUTH_TOL_PT, (
            f"{word!r} y1={y1:.1f} is not within {_GROUND_TRUTH_TOL_PT} pt of baseline y={baseline_y} at dpi {dpi}"
        )
        # Box EXTENT sanity (audit F19): x1/y0 previously floated free, so a bug corrupting only the
        # far corner (e.g. x1 in a different space than x0) passed the origin assertions. Bounds are
        # generous glyph-metric envelopes, not tuned values: ink width per char within [0.3, 1.2] em
        # at this fontsize; box height at least a 0.4-em cap-height floor (observed ~0.5/0.75 em).
        assert 0.3 * line.fontsize <= (x1 - x0) / len(word) <= 1.2 * line.fontsize, (
            f"{word!r} width {x1 - x0:.1f} is outside the glyph-metric envelope at dpi {dpi}"
        )
        assert y1 - y0 >= 0.4 * line.fontsize, (
            f"{word!r} box height {y1 - y0:.1f} is below the cap-height floor at dpi {dpi}"
        )
        # Implied by the ground-truth band above (the pixmap position sits ≥82 pt outside it), kept
        # as an explicit statement of the space being ruled out — not an independent discriminator.
        assert abs(x0 - draw_x * dpi / 72.0) > _GROUND_TRUTH_TOL_PT, (
            f"{word!r} x0={x0:.1f} sits at the pixmap-space position (~{draw_x * dpi / 72.0:.0f}) at dpi {dpi} "
            f"— coords are not in page-point space"
        )


def test_cropped_page_reports_cropbox_dimensions_and_contains_its_boxes(synth):
    # Binds DT-4's «unverified»: with CropBox ≠ MediaBox, coords are relative to `page.rect` (the
    # cropbox-derived visible rect), so the emitted PageGeometry dimensions are the CROPBOX's, not
    # the mediabox's, and boxes ⊆ them. Asserting the dimensions is what discriminates: a mutant
    # reading `page.mediabox` would report 612×792 and still contain the (left-drawn) boxes — the
    # containment-only assertion could not tell the two apart, so it is the dimension equality that
    # actually pins the coordinate space (audit finding: containment alone under-binds this).
    crop = (60.0, 100.0, 560.0, 460.0)  # cropbox 500 wide × 360 tall, tighter than the 612×792 mediabox
    spec = synth.cropped(synth.single_column(), crop)
    be = PyMuPDFTesseractBackend(synth.pdf([spec]), language="eng", dpi=300)
    (pg,) = list(be.read_pages(1, 1))
    assert (pg.width, pg.height) == (crop[2] - crop[0], crop[3] - crop[1]), (
        f"cropped page reported {pg.width}x{pg.height}, not the cropbox 500x360 — mediabox leaked?"
    )
    assert pg.words
    for wb in pg.words:
        x0, y0, x1, y1 = wb.bbox
        assert x1 <= pg.width + 1.0 and y1 <= pg.height + 1.0, f"box {wb.bbox} escapes cropped rect {pg.width}x{pg.height}"


def test_cropped_page_boxes_land_at_crop_relative_ground_truth(synth):
    # RED (audit D5): the dimension assertion above kills a mediabox-RECT mutant, but box POSITIONS
    # on a cropped page were unbound — a crop-origin-offset bug (emitting uncropped-space coords)
    # passed containment. page.rect on a cropped page is origin-normalized (probed: (0,0,500,360)),
    # so a word drawn at (90, 140) on the uncropped page must land at (90−60, 140−100) = (30, 40)
    # in emitted coords — and NOT at its uncropped position (a 60 pt gap, 4× the tolerance). This
    # binds the coordinate-origin half of the DT-4 «unverified» the dimension test could not.
    crop = (60.0, 100.0, 560.0, 460.0)
    spec = synth.cropped(synth.single_column(), crop)
    be = PyMuPDFTesseractBackend(synth.pdf([spec]), language="eng", dpi=300)
    (pg,) = list(be.read_pages(1, 1))
    boxes = {wb.text: wb.bbox for wb in pg.words}
    for line in spec.lines:
        word = line.text
        assert word in boxes, f"OCR lost {word!r} on the cropped page"
        x0, _y0, _x1, y1 = boxes[word]
        truth_x = line.origin[0] - crop[0]
        truth_y = line.origin[1] - crop[1]
        assert abs(x0 - truth_x) <= _GROUND_TRUTH_TOL_PT, (
            f"{word!r} x0={x0:.1f} not at crop-relative ground truth {truth_x} — crop origin unapplied?"
        )
        assert abs(y1 - truth_y) <= _GROUND_TRUTH_TOL_PT, (
            f"{word!r} y1={y1:.1f} not at crop-relative baseline {truth_y}"
        )
        assert abs(x0 - line.origin[0]) > _GROUND_TRUTH_TOL_PT, (
            f"{word!r} x0={x0:.1f} sits at the UNCROPPED position {line.origin[0]} — mediabox-space coords leaked"
        )


# Five in-page filler boxes for the bounded-OOB fixtures: enough candidates that ONE off-page box
# sits at/below the 20% fraction bound (1/6 ≈ 0.167, 1/5 = 0.2) while TWO exceed it (2/7 ≈ 0.286).
_FILLER = [_word(f"fill{i}", (10.0 + 50.0 * i, 100.0, 50.0 + 50.0 * i, 130.0)) for i in range(5)]


def _oob_boxes_by_edge(rect):
    w, h = rect.width, rect.height
    return {
        "left": (-60.0, 10.0, -5.0, 40.0),
        "top": (10.0, -60.0, 60.0, -5.0),
        "right": (w + 5.0, 10.0, w + 60.0, 40.0),
        "bottom": (10.0, h + 5.0, 60.0, h + 60.0),
    }


@pytest.mark.parametrize("edge", ["left", "top", "right", "bottom"])
def test_isolated_off_page_box_is_dropped_and_counted_not_raised(synth, monkeypatch, edge):
    # RED (G-8 amended — ruled by Ben 2026-07-05, bounded drop-and-count): before the amendment this
    # page RAISED on its single off-page box; now an ISOLATED off-page box (1 of 6 candidates,
    # fraction ≤ the 20% bound) is a Tesseract hallucination — dropped, counted in `oob_boxes`,
    # never emitted, never conflated with the DT-2 `dropped_boxes` artifact counter. All FOUR edges
    # are exercised so each clause of the four-way detection bound is independently killed by a
    # mutant (an x-only fixture would leave the y-clauses untested); a dropped clause here shows as
    # oob_boxes == 0 AND the runaway word emitted.
    pdf = synth.pdf([synth.single_column()])
    be = PyMuPDFTesseractBackend(pdf, language="eng", dpi=300)
    rect = fitz.open(pdf)[0].rect
    _stub_ocr(monkeypatch, [*_FILLER, _word("runaway", _oob_boxes_by_edge(rect)[edge])])
    (pg,) = list(be.read_pages(1, 1))
    assert [w.text for w in pg.words] == [f"fill{i}" for i in range(5)], (
        "the off-page box must be dropped, the in-page boxes kept"
    )
    assert be.oob_boxes[1] == 1, "the dropped off-page box must be counted in oob_boxes"
    assert be.dropped_boxes[1] == 0, "an off-page box is not a DT-2 artifact — counters stay separate"


def test_off_page_fraction_above_bound_raises_and_banks_the_counter(synth, monkeypatch):
    # RED (G-8 amended): 2 off-page of 7 candidates (≈28.6%) exceeds the 20% bound — that is no
    # longer an isolated-hallucination profile (PLL whole-book probe worst page: 4.5%) but the
    # systemic class the bound exists to keep loud (a pixmap-space leak displaces ~every box). The
    # raise must carry the fraction diagnosis, and `oob_boxes` must be banked BEFORE the raise so
    # the failure is inspectable post-mortem (the slice-1 runner banks backend counters into its
    # box cache when GeometryError fires mid-book).
    pdf = synth.pdf([synth.single_column()])
    be = PyMuPDFTesseractBackend(pdf, language="eng", dpi=300)
    rect = fitz.open(pdf)[0].rect
    w = rect.width
    _stub_ocr(monkeypatch, [
        *_FILLER,
        _word("runaway1", (w + 5.0, 10.0, w + 60.0, 40.0)),
        _word("runaway2", (w + 5.0, 50.0, w + 60.0, 80.0)),
    ])
    with pytest.raises(GeometryError, match="off-page fraction"):
        list(be.read_pages(1, 1))
    assert be.oob_boxes[1] == 2, "the counter must be banked before the systemic raise"


def test_off_page_fraction_exactly_at_bound_is_tolerated(synth, monkeypatch):
    # RED (G-8 amended, boundary): 1 off-page of exactly 5 candidates = 20% — AT the bound, not
    # over it — must be tolerated (the bound is `>`, not `>=`; a `>=` mutant reds here). Exact in
    # floats because the comparison is `oob > _OOB_PAGE_FRACTION_MAX * candidates` and 0.2 * 5
    # rounds to exactly 1.0 (the code never computes 1/5).
    pdf = synth.pdf([synth.single_column()])
    be = PyMuPDFTesseractBackend(pdf, language="eng", dpi=300)
    rect = fitz.open(pdf)[0].rect
    w = rect.width
    _stub_ocr(monkeypatch, [*_FILLER[:4], _word("runaway", (w + 5.0, 10.0, w + 60.0, 40.0))])
    (pg,) = list(be.read_pages(1, 1))
    assert [w.text for w in pg.words] == [f"fill{i}" for i in range(4)]
    assert be.oob_boxes[1] == 1


def test_page_of_entirely_off_page_boxes_raises(synth, monkeypatch):
    # G-8's original tripwire survives the amendment: the pixmap-space-leak class (coords ~dpi/72×
    # too large) displaces ~100% of a page's boxes, and 3/3 off-page is far over any sane bound —
    # fail loud, never emit. Green before the amendment too (any oob raised); its independent teeth
    # come from the hunt (bound-check-removed and bound-enlarged mutants red only here).
    pdf = synth.pdf([synth.single_column()])
    be = PyMuPDFTesseractBackend(pdf, language="eng", dpi=300)
    rect = fitz.open(pdf)[0].rect
    w = rect.width
    _stub_ocr(monkeypatch, [
        _word(f"pix{i}", (w + 5.0, 10.0 + 40.0 * i, w + 60.0, 40.0 + 40.0 * i)) for i in range(3)
    ])
    with pytest.raises(GeometryError, match="off-page fraction"):
        list(be.read_pages(1, 1))
    assert be.oob_boxes[1] == 3


def test_oob_fraction_denominator_is_candidates_not_raw_boxes(synth, monkeypatch):
    # RED (G-8 amended, denominator): the fraction is over boxes that REACHED the off-page check
    # (post DT-2 empty/degenerate drop), not raw OCR output. 1 off-page of 4 candidates = 25% →
    # raises; a raw-count mutant sees 1 of 7 (the three DT-2 artifacts inflate the denominator)
    # ≈ 14% → tolerates → this test reds. Noise pages are exactly where empty-text artifacts and
    # hallucinated boxes co-occur, so the wrong denominator would systematically under-diagnose.
    # The empty-text OFF-PAGE box binds the precedence (delta audit 2026-07-05): a finite box that
    # is both debris and off-page counts as debris — dropped_boxes 3, not oob_boxes 2 — so a
    # mutant hoisting the OOB clauses above the DT-2 drop reds on the counter split.
    pdf = synth.pdf([synth.single_column()])
    be = PyMuPDFTesseractBackend(pdf, language="eng", dpi=300)
    rect = fitz.open(pdf)[0].rect
    w = rect.width
    _stub_ocr(monkeypatch, [
        *_FILLER[:3],
        _word("", (10.0, 200.0, 60.0, 230.0)),      # empty-text artifact (DT-2 drop)
        _word("  ", (10.0, 240.0, 60.0, 270.0)),    # whitespace-text artifact (DT-2 drop)
        _word("", (w + 5.0, 200.0, w + 60.0, 230.0)),  # empty-text AND off-page → debris wins
        _word("runaway", (w + 5.0, 10.0, w + 60.0, 40.0)),
    ])
    with pytest.raises(GeometryError, match="off-page fraction"):
        list(be.read_pages(1, 1))
    assert be.oob_boxes[1] == 1 and be.dropped_boxes[1] == 3


def test_off_page_fraction_just_above_bound_raises(synth, monkeypatch):
    # RED (delta audit 2026-07-05): the at-bound (20%) and above-bound fixtures alone pin the
    # constant only to [0.20, 0.286) — a drift mutant to 0.24 survived them. 2 off-page of 9
    # candidates ≈ 22.2% narrows the pin to [0.20, 0.222): over the real bound (2 > 0.2·9 = 1.8 →
    # raise) but under the drifted one (2 > 0.24·9 = 2.16 → tolerate → this test reds).
    pdf = synth.pdf([synth.single_column()])
    be = PyMuPDFTesseractBackend(pdf, language="eng", dpi=300)
    rect = fitz.open(pdf)[0].rect
    w = rect.width
    filler7 = [_word(f"f{i}", (10.0 + 40.0 * i, 300.0, 40.0 + 40.0 * i, 330.0)) for i in range(7)]
    _stub_ocr(monkeypatch, [
        *filler7,
        _word("runaway1", (w + 5.0, 10.0, w + 60.0, 40.0)),
        _word("runaway2", (w + 5.0, 50.0, w + 60.0, 80.0)),
    ])
    with pytest.raises(GeometryError, match="off-page fraction"):
        list(be.read_pages(1, 1))
    assert be.oob_boxes[1] == 2


def test_rect_tolerance_absorbs_subpoint_rounding_but_not_real_overshoot(synth, monkeypatch):
    # RED (audit F15 / hunt M9): the four-edge tests plant boxes 5-60 pt out, so widening
    # _RECT_TOLERANCE_PT from 1.0 to 50.0 survived the suite while admitting 50 pt of off-page
    # corruption. Two-sided bind: a box 0.5 pt over the edge (the sub-point OCR rounding the
    # tolerance exists to absorb) is ACCEPTED; a box 5 pt over is off-page and — as this page's
    # only candidate, fraction 1/1 — raises through the systemic bound (2026-07-05 amendment).
    # Together they pin the tolerance to [0.5, 5) — the intent of "edge rounding", not a loophole.
    pdf = synth.pdf([synth.single_column()])
    rect = fitz.open(pdf)[0].rect
    be = PyMuPDFTesseractBackend(pdf, language="eng", dpi=300)
    _stub_ocr(monkeypatch, [_word("overhang", (rect.x1 - 40.0, 10.0, rect.x1 + 0.5, 40.0))])
    (pg,) = list(be.read_pages(1, 1))
    assert [w.text for w in pg.words] == ["overhang"], "a 0.5 pt edge-rounding overshoot must be accepted"
    be2 = PyMuPDFTesseractBackend(pdf, language="eng", dpi=300)
    _stub_ocr(monkeypatch, [_word("runaway", (rect.x1 - 40.0, 10.0, rect.x1 + 5.0, 40.0))])
    with pytest.raises(GeometryError, match="outside"):
        list(be2.read_pages(1, 1))


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
@pytest.mark.parametrize("pos", [0, 1, 2, 3])
def test_non_finite_box_coordinate_raises_geometry_error_not_valueerror(synth, monkeypatch, pos, bad):
    # RED (delta audit 2026-07-05): a non-finite coordinate must raise UNCONDITIONALLY — the guard
    # runs before every other branch. Under bounded drop-and-count the ±inf cases went live: an
    # x1=-inf box satisfies the degenerate drop's `x1 <= x0` (silently counted as DT-2 debris) and
    # an x1=+inf box trips the OOB clause (silently dropped as an isolated hallucination) — both
    # swallow corruption unless the finite guard is checked first and covers inf, not just NaN (an
    # `isnan`-narrowed guard survives the NaN-only parametrize). NaN still slips both branches
    # (compares False everywhere) and would reach WordBox as a bare ValueError escaping the axis.
    # Every position × {nan, +inf, -inf} so a guard narrowed by position or by predicate reds.
    pdf = synth.pdf([synth.single_column()])
    be = PyMuPDFTesseractBackend(pdf, language="eng", dpi=300)
    bbox = [10.0, 20.0, 50.0, 60.0]
    bbox[pos] = bad
    _stub_ocr(monkeypatch, [_word("badbox", tuple(bbox))])
    with pytest.raises(GeometryError, match="non-finite"):
        list(be.read_pages(1, 1))
    assert be.dropped_boxes == {} and be.oob_boxes == {}, (
        "a non-finite box must fail loud, never be absorbed into a drop counter"
    )


# --- G-17: fail-loud — rotation, OCR failure, missing tessdata ----------------------------------- #


@pytest.mark.parametrize("degrees", [90, 180, 270])
def test_rotated_page_raises_geometry_error(synth, degrees):
    # RED (G-17): S2.1 does not support rotation. A rotated page must FAIL, never emit coordinates in
    # a silently-transformed space. The check precedes OCR, so no tesseract is needed; a mutant that
    # proceeds would OCR the rotated fixture and yield boxes. All three non-zero rotations are
    # exercised (audit F8): a 90°-only fixture let a `!= 0` → `== 90` narrowing survive — a
    # 180°-rotated page under that mutant emits boxes inside the unswapped rect, so the OOB check
    # cannot backstop it.
    spec = synth.rotated(synth.single_column(), degrees)
    be = PyMuPDFTesseractBackend(synth.pdf([spec]), language="eng", dpi=300)
    with pytest.raises(GeometryError, match="rotat"):
        list(be.read_pages(1, 1))


def test_ocr_invocation_carries_the_configured_language_dpi_and_tessdata(synth, monkeypatch):
    # RED (audit D2 / hunt M7-M8 — M8 proven SURVIVED by execution): hardcoding language="eng"
    # inside the OCR call passed all 124 then-collected tests of the geometry + neutrality files
    # (every real-OCR test uses eng, and the ground-truth test
    # is dpi-independent BY DESIGN, so a hardcoded dpi survives too). G-1 proves the params are
    # *required*; this spy proves they are *used* — the binding that makes engine_id/backend_params
    # honest provenance (DT-9) instead of a record of intent. Values chosen to appear nowhere else.
    seen: dict[str, object] = {}

    def spy(self, **kw):
        seen.update(kw)
        return object()

    monkeypatch.setattr(fitz.Page, "get_textpage_ocr", spy)
    monkeypatch.setattr(fitz.Page, "get_text", lambda self, *a, **kw: [])
    pdf = synth.pdf([synth.single_column()])
    be = PyMuPDFTesseractBackend(pdf, language="deu", dpi=217, tessdata="/tess/override")
    list(be.read_pages(1, 1))
    assert seen["language"] == "deu"
    assert seen["dpi"] == 217
    assert seen["tessdata"] == "/tess/override"
    assert seen["full"] is True  # full-page OCR, the S2.0-probed invocation
    assert seen["flags"] == 0    # the fifth probed kwarg — unasserted, it could drift silently


def test_ocr_failure_raises_geometry_error(synth, monkeypatch):
    # RED (G-17): a mutant that swallows the OCR exception would return silently-empty pages. Any
    # operational OCR failure must surface as GeometryError (fail-loud, no per-page degrade — DT-2).
    pdf = synth.pdf([synth.single_column()])
    be = PyMuPDFTesseractBackend(pdf, language="eng", dpi=300)

    def boom(self, **kw):
        raise RuntimeError("tesseract exploded")

    monkeypatch.setattr(fitz.Page, "get_textpage_ocr", boom)
    with pytest.raises(GeometryError, match="OCR"):
        list(be.read_pages(1, 1))


def test_missing_tessdata_raises_geometry_error(synth):
    # RED (G-17): pointing at a nonexistent tessdata dir makes the real OCR init fail; the backend
    # must surface that as GeometryError, not a bare mupdf error escaping the axis. (This exercises
    # the explicit-override path; the auto-discovery failure paths are the two tests below.)
    pdf = synth.pdf([synth.single_column()])
    be = PyMuPDFTesseractBackend(pdf, language="eng", dpi=300, tessdata="/nonexistent/tessdata")
    with pytest.raises(GeometryError):
        list(be.read_pages(1, 1))


def test_tessdata_autodiscovery_failure_raises_geometry_error_not_runtimeerror(synth, monkeypatch):
    # RED (G-17, audit D1 — reproduced live): pymupdf's `get_tessdata()` RAISES RuntimeError when
    # tesseract/tessdata is absent (all four failure sites in the pinned versions raise; none
    # returns falsy), and `_resolve_tessdata` ran outside any wrap — so on a tessdata-less machine
    # a bare RuntimeError escaped the axis, breaking the "any geometry fault → GeometryError"
    # contract on exactly the fail-loud path the CI comment advertises.
    pdf = synth.pdf([synth.single_column()])
    be = PyMuPDFTesseractBackend(pdf, language="eng", dpi=300)

    def no_tessdata():
        raise RuntimeError("No tessdata specified and Tesseract is not installed")

    monkeypatch.setattr(fitz, "get_tessdata", no_tessdata)
    with pytest.raises(GeometryError, match="tessdata"):
        list(be.read_pages(1, 1))


def test_tessdata_autodiscovery_falsy_result_raises_geometry_error(synth, monkeypatch):
    # RED (hunt M11): the falsy branch is unreachable under the pinned pymupdf (which raises
    # instead) — kept as a belt against a future falsy-returning version, and bound here so a
    # mutant turning the raise into `return ""` cannot survive as dead code.
    pdf = synth.pdf([synth.single_column()])
    be = PyMuPDFTesseractBackend(pdf, language="eng", dpi=300)
    monkeypatch.setattr(fitz, "get_tessdata", lambda: None)
    with pytest.raises(GeometryError, match="tessdata"):
        list(be.read_pages(1, 1))


# --- DT-2 normalization: drop-and-count empty/degenerate boxes; range + blank-page semantics ----- #


def test_backend_drops_and_counts_empty_and_degenerate_boxes(synth, monkeypatch):
    # DT-2 layer 2: Tesseract can emit empty-text / degenerate artifacts; the backend drops them
    # BEFORE WordBox construction (so a real artifact never crashes the record) and counts them in a
    # per-page `dropped_boxes` stat (surfaced to the sidecar in #37). Dropped-and-counted, never
    # silently absent, never a construction crash.
    pdf = synth.pdf([synth.single_column()])
    be = PyMuPDFTesseractBackend(pdf, language="eng", dpi=300)
    _stub_ocr(
        monkeypatch,
        [
            _word("keep", (10.0, 10.0, 50.0, 30.0)),
            _word("   ", (10.0, 40.0, 50.0, 60.0)),      # whitespace text → dropped
            _word("degenerate", (10.0, 80.0, 10.0, 100.0)),  # x1 == x0 → dropped
            _word("flatline", (10.0, 120.0, 50.0, 120.0)),   # y1 == y0 → dropped (audit F5: the
            _word("inverted", (10.0, 160.0, 50.0, 140.0)),   # y1 < y0 → dropped   y-clause had no
        ],                                                   # test — deleting it sent a real
    )                                                        # artifact into WordBox as a bare
    (pg,) = list(be.read_pages(1, 1))                        # ValueError escaping the axis)
    assert [w.text for w in pg.words] == ["keep"]
    assert be.dropped_boxes[1] == 4


def test_blank_page_yields_zero_words_successfully(synth, monkeypatch):
    # DT-2: empty ≠ failed. A page Tesseract reads as zero words is a SUCCESSFUL zero-word read, not
    # an error — the backend yields an empty PageGeometry, it does not raise.
    pdf = synth.pdf([synth.near_blank()])
    be = PyMuPDFTesseractBackend(pdf, language="eng", dpi=300)
    _stub_ocr(monkeypatch, [])
    (pg,) = list(be.read_pages(1, 1))
    assert pg.words == ()
    assert be.dropped_boxes[1] == 0
    assert be.oob_boxes[1] == 0, (
        "oob_boxes must key every read page unconditionally — a key-only-when-nonzero mutant "
        "leaves downstream readers with missing keys (delta audit 2026-07-05)"
    )


def test_multi_page_range_reads_the_requested_pages_with_their_own_numbers_and_rects(synth, monkeypatch):
    # RED (audit F9 / hunt M13-M14): every other backend test reads read_pages(1, 1) on a 1-page
    # PDF, so a doc[0]-always mutant and a page=1-always mutant survived. Three pages with DISTINCT
    # dimensions discriminate which page was actually opened (via its rect) without real OCR; page
    # numbers and dropped_boxes keys must be the 1-based scan numbers of the REQUESTED subrange.
    specs = [
        synth.PageSpec(width=500.0, height=700.0),
        synth.PageSpec(width=550.0, height=750.0),
        synth.PageSpec(width=600.0, height=800.0),
    ]
    pdf = synth.pdf(specs)
    _stub_ocr(monkeypatch, [])
    be = PyMuPDFTesseractBackend(pdf, language="eng", dpi=300)
    got = list(be.read_pages(2, 3))
    assert [(p.page, p.width, p.height) for p in got] == [(2, 550.0, 750.0), (3, 600.0, 800.0)]
    assert set(be.dropped_boxes) == {2, 3}
    assert set(be.oob_boxes) == {2, 3}, (
        "oob_boxes must be keyed by the requested pages' 1-based scan numbers — a hardcoded-key "
        "mutant misattributes every page's count to page 1 (delta audit 2026-07-05)"
    )


def test_unopenable_pdf_raises_geometry_error(tmp_path):
    # RED (hunt M10): fitz.open's own exception on a missing/corrupt file must not escape the axis
    # — the open is wrapped at the seam like every other geometry fault.
    be = PyMuPDFTesseractBackend(tmp_path / "nope.pdf", language="eng", dpi=300)
    # full phrase, not "open": the message embeds tmp_path, which embeds this test's name, which
    # contains "open" — the pytest match-leak trap (a bare "open" could never fail).
    with pytest.raises(GeometryError, match="could not open scan PDF"):
        list(be.read_pages(1, 1))


def test_missing_tesseract_binary_fails_provenance_loud(monkeypatch):
    # RED (audit F12 / hunt M12): a backend that cannot name its OCR engine must not stamp
    # provenance — a mutant returning "unknown" instead of raising records a silently-false
    # engine_id/backend_params on every sidecar downstream (DT-9).
    import engine.structure.geometry_pymupdf as mod

    def no_binary(*a, **kw):
        raise FileNotFoundError("tesseract not on PATH")

    monkeypatch.setattr(mod.subprocess, "run", no_binary)
    be = PyMuPDFTesseractBackend("/some/scan.pdf", language="eng", dpi=300)
    with pytest.raises(GeometryError, match="tesseract"):
        be.engine_id


@pytest.mark.parametrize(
    "first,last",
    [
        (1, 5),   # beyond the PDF (only 1 page exists)
        (0, 1),   # below 1: page 0 would negative-index doc[-1] — the LAST page served as page zero
        (2, 1),   # inverted: would otherwise be a silently EMPTY iterator, the exact hole forbidden
        (0, 0),   # both violations at once
    ],
)
def test_out_of_range_or_inverted_page_request_raises_geometry_error(synth, first, last):
    # The Protocol range is 1-based inclusive over real pages; asking outside it is a fail-loud
    # backend error, never a silently short/empty result. Each of the three bound clauses gets its
    # own red (audit D3 / hunt M1-M2 — the inverted-range clause deletion was proven SURVIVED by
    # execution when only the beyond-the-PDF case existed).
    pdf = synth.pdf([synth.single_column()])
    be = PyMuPDFTesseractBackend(pdf, language="eng", dpi=300)
    # match pins the RANGE error specifically: on a tessdata-less machine a bare raises() could be
    # satisfied by _resolve_tessdata's own GeometryError, silently masking a range-clause mutant.
    with pytest.raises(GeometryError, match="out of bounds"):
        list(be.read_pages(first, last))


# (A presence-only isinstance-GeometrySource smoke on the real backend was folded out (#56):
# read_pages arity/behaviour and engine_id are hard-bound by the tests throughout this file.)


# --- DT-11 tier 1: the fixtures are genuinely image-only (no native text layer) ------------------ #


def test_fixture_pages_have_no_native_text_layer(synth):
    # The whole tier's premise: OCR greens can't be native-text-extraction false positives, because
    # get_text() == "" on every fixture page by construction (drawn text → pixmap → re-embedded image).
    specs = [synth.single_column(), synth.two_column(), synth.near_blank(), synth.dark()]
    data = synth.render_bytes(specs)
    doc = fitz.open("pdf", data)
    assert doc.page_count == 4
    for i in range(doc.page_count):
        assert doc[i].get_text().strip() == "", f"fixture page {i} has a native text layer — not image-only"


# --- DT-11 inventory driven through REAL OCR (audit F11: only single_column was ever OCR'd) ------ #


def test_two_column_page_words_recover_through_real_ocr(synth):
    # The two-column layout (the slice-2 #39 detector's page) through an actual Tesseract pass:
    # all eight drawn words recovered, every box inside the page rect.
    spec = synth.two_column()
    be = PyMuPDFTesseractBackend(synth.pdf([spec]), language="eng", dpi=300)
    (pg,) = list(be.read_pages(1, 1))
    recovered = {wb.text for wb in pg.words}
    assert set(spec.words) <= recovered, f"OCR lost known words: {set(spec.words) - recovered}"
    for wb in pg.words:
        assert wb.bbox[2] <= pg.width + 1.0 and wb.bbox[3] <= pg.height + 1.0


def test_near_blank_page_recovers_its_lone_token_through_real_ocr(synth):
    # The low-yield end of the DT-6 continuum through a REAL pass: the folio-style "12" is read.
    # (The stubbed zero-words test above pins empty≠failed semantics; this pins that the real path
    # actually reads a nearly-empty page rather than erroring or inventing content.)
    spec = synth.near_blank()
    be = PyMuPDFTesseractBackend(synth.pdf([spec]), language="eng", dpi=300)
    (pg,) = list(be.read_pages(1, 1))
    assert "12" in {wb.text for wb in pg.words}


def test_truly_blank_page_yields_zero_words_through_real_ocr(synth):
    # empty ≠ failed against the REAL path (probed 3× in-session 2026-07-04, zero words each time):
    # a genuinely blank white page OCRs to zero words SUCCESSFULLY — no raise, no invented boxes.
    blank = synth.PageSpec(width=612.0, height=792.0)
    be = PyMuPDFTesseractBackend(synth.pdf([blank]), language="eng", dpi=300)
    (pg,) = list(be.read_pages(1, 1))
    assert pg.words == ()
    assert be.dropped_boxes[1] == 0


def test_dark_page_survives_real_ocr_and_any_output_obeys_containment(synth):
    # The hallucination-prone end (DT-6, the endpaper case): whatever Tesseract makes of a
    # near-black page, the backend must SUCCEED (fail-loud is for faults, not low yield) and
    # anything emitted obeys the containment contract; artifacts are dropped-and-counted, never a
    # crash. (Probed: tesseract 5.5.2 emits zero words here; the assertions hold either way.)
    spec = synth.dark()
    be = PyMuPDFTesseractBackend(synth.pdf([spec]), language="eng", dpi=300)
    (pg,) = list(be.read_pages(1, 1))
    assert isinstance(pg, PageGeometry)
    assert 1 in be.dropped_boxes  # the page was processed and its drop stat keyed
    for wb in pg.words:
        assert wb.bbox[2] <= pg.width + 1.0 and wb.bbox[3] <= pg.height + 1.0


# --- test-infra guard: the conftest fixture loader (audit F16) ------------------------------------ #


def test_fixture_loader_does_not_serve_a_half_executed_module(tmp_path):
    # RED (audit F16): the loader cached the module object BEFORE exec_module ran, so a failing
    # exec (e.g. a fitz ABI break) errored truthfully once, then every later `synth` use got the
    # cached hollow module — an AttributeError far from the cause. Both calls must re-raise.
    import importlib.util

    cpath = Path(__file__).resolve().parents[1] / "conftest.py"
    spec = importlib.util.spec_from_file_location("conftest_under_test", cpath)
    ct = importlib.util.module_from_spec(spec)
    sys.modules["conftest_under_test"] = ct
    # The loader registers under this shared name; the REAL conftest may have registered it earlier
    # in the session, so restore whatever was there rather than popping it.
    orig = sys.modules.get("tests_fixtures_geometry_pdf")
    try:
        spec.loader.exec_module(ct)
        bad = tmp_path / "boom.py"
        bad.write_text("raise RuntimeError('fixture module exec fails')\n", encoding="utf-8")
        ct._GEOMETRY_PDF_PATH = bad
        with pytest.raises(RuntimeError, match="exec fails"):
            ct._load_geometry_pdf()
        with pytest.raises(RuntimeError, match="exec fails"):
            ct._load_geometry_pdf()  # the failure must not have been cached as success
    finally:
        sys.modules.pop("conftest_under_test", None)
        if orig is not None:
            sys.modules["tests_fixtures_geometry_pdf"] = orig
        else:
            sys.modules.pop("tests_fixtures_geometry_pdf", None)
