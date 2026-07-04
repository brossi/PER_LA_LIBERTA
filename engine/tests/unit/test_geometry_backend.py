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

import pytest

from engine.errors import BackendError, EngineError
from engine.structure import (
    GeometryError,
    GeometrySource,
    PageGeometry,
    WordBox,
)

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


@pytest.mark.parametrize("text", ["", "   ", "\t\n"])
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


def test_fake_backend_satisfies_the_runtime_checkable_geometrysource_protocol(geom):
    # NB: @runtime_checkable isinstance is PRESENCE-only — it verifies engine_id/read_pages exist,
    # not their shape (a wrong-arity read_pages or a method-not-property engine_id would still pass).
    # DT-2 frames this as a seam smoke test; the shape/behaviour guarantee lives in the two tests
    # below (read_pages arity + inclusive range; engine_id str property).
    src = geom.Source(pages=[])
    assert isinstance(src, GeometrySource)


def test_read_pages_yields_pagegeometry_over_the_inclusive_1_based_range(geom):
    pages = [PageGeometry(page=n, width=612.0, height=792.0, words=[_box()]) for n in (5, 6, 7)]
    src = geom.Source(pages=pages)
    got = list(src.read_pages(5, 7))  # 1-based INCLUSIVE (matches copy3's ⟨PAGE:N⟩ / page_000N.png)
    assert [p.page for p in got] == [5, 6, 7]
    assert all(isinstance(p, PageGeometry) for p in got)


def test_engine_id_is_a_string_property_the_matcher_writes_verbatim(geom):
    src = geom.Source(pages=[], engine_id="engine-sentinel-77")
    assert src.engine_id == "engine-sentinel-77"


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
