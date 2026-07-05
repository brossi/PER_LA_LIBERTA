"""Mutant table for the PyMuPDF+Tesseract geometry backend (issue #36; S2.1.2).

Run with the mutation-hunt runner:

    python3 ~/.claude/skills/mutation-hunt/hunt.py \
        --table tests/hunts/hunt_geometry_backend.py --artifact <scratch>/hunt36.json

Authored during the #36 remediation pass (2026-07-04 audit): the audit's coverage lens
predicted 14 survivors against the pre-remediation tests, two of which were proven
SURVIVED by execution (ocr-language-hardcoded passed 124 tests; range-inverted-clause
passed 81). Every one of those is in this table and must now be KILLED by the tests
added in remediation. TEST_CMD uses the engine venv's python directly (the geometry
tests import engine + fitz); the wrapper-vs-instrument rule does not apply here since
tools/test.py is not under mutation, but the runner pins the same hygiene itself.
"""
from pathlib import Path

REPO = str(Path(__file__).resolve().parents[2])
TEST_CMD = [str(Path(REPO) / ".venv" / "bin" / "python"), "-m", "pytest", "{scope}",
            "-q", "--no-header", "-x", "-p", "no:cacheprovider"]
TIMEOUT = 300

B = "src/engine/structure/geometry_pymupdf.py"
C = "tests/conftest.py"
T = "tests/unit/test_geometry_backend.py"


def m(label, old, new, test_id, file=B):
    return {"label": label, "file": file, "old": old, "new": new,
            "scope": f"{T}::{test_id}"}


_CTOR = "    def __init__(self, pdf_path, *, language: str, dpi: int, tessdata: str | None = None) -> None:"
_OCR_KWARGS = "                    flags=0, language=self._language, dpi=self._dpi, full=True, tessdata=tessdata"
_APPEND = "            words.append(WordBox(text=text, bbox=(x0, y0, x1, y1)))"
_RANGE = "        if first_page < 1 or last_page < first_page or last_page > n:"
_DROP = "            if not text.strip() or x1 <= x0 or y1 <= y0:"
_EID = '                f":dpi={self._dpi}:lang={self._language}"'

MUTANTS = [
    # --- G-1: required params (spot-proven KILLED pre-remediation) ---
    m("g1-dpi-default",
      _CTOR,
      _CTOR.replace("dpi: int,", "dpi: int = 300,"),
      "test_backend_requires_dpi_no_default"),
    m("g1-language-default",
      _CTOR,
      _CTOR.replace("language: str,", 'language: str = "und",'),
      "test_backend_requires_language_no_default"),
    m("dpi-value-guard-dropped",
      "        if not (type(dpi) is int and dpi > 0):",
      "        if False:",
      "test_backend_rejects_invalid_language_or_dpi_values"),
    m("language-value-guard-dropped",
      "        if not (isinstance(language, str) and language.strip()):",
      "        if False:",
      "test_backend_rejects_invalid_language_or_dpi_values"),
    # --- parameter -> invocation binding (audit D2/F2; M8 was SURVIVED by execution) ---
    m("ocr-language-hardcoded",
      _OCR_KWARGS,
      _OCR_KWARGS.replace("language=self._language", 'language="eng"'),
      "test_ocr_invocation_carries_the_configured_language_dpi_and_tessdata"),
    m("ocr-dpi-hardcoded",
      _OCR_KWARGS,
      _OCR_KWARGS.replace("dpi=self._dpi", "dpi=300"),
      "test_ocr_invocation_carries_the_configured_language_dpi_and_tessdata"),
    m("ocr-tessdata-dropped",
      _OCR_KWARGS,
      _OCR_KWARGS.replace("tessdata=tessdata", "tessdata=None"),
      "test_ocr_invocation_carries_the_configured_language_dpi_and_tessdata"),
    m("ocr-not-full-page",
      _OCR_KWARGS,
      _OCR_KWARGS.replace("full=True", "full=False"),
      "test_ocr_invocation_carries_the_configured_language_dpi_and_tessdata"),
    m("ocr-flags-drifted",
      _OCR_KWARGS,
      _OCR_KWARGS.replace("flags=0", "flags=11"),
      "test_ocr_invocation_carries_the_configured_language_dpi_and_tessdata"),
    # --- engine_id / backend_params interpolation (audit F3/F13) ---
    m("engine-id-dpi-constant",
      _EID,
      _EID.replace("{self._dpi}", "300"),
      "test_engine_id_and_backend_params_interpolate_per_instance_values"),
    m("engine-id-lang-constant",
      _EID,
      _EID.replace("{self._language}", "eng"),
      "test_engine_id_and_backend_params_interpolate_per_instance_values"),
    m("backend-params-dpi-constant",
      '            "dpi": self._dpi,',
      '            "dpi": 300,',
      "test_engine_id_and_backend_params_interpolate_per_instance_values"),
    m("tesseract-version-failure-swallowed",
      '        raise GeometryError(f"could not read the tesseract version (is tesseract installed?): {exc}") from exc',
      '        return "unknown"',
      "test_missing_tesseract_binary_fails_provenance_loud"),
    # --- fail-loud error paths (audit D1/F6/F7) ---
    m("open-not-wrapped",
      "            try:\n"
      "                self._doc = fitz.open(self._pdf_path)\n"
      "            except Exception as exc:  # missing / unreadable / not a PDF\n"
      '                raise GeometryError(f"could not open scan PDF {self._pdf_path}: {exc}") from exc',
      "            self._doc = fitz.open(self._pdf_path)",
      "test_unopenable_pdf_raises_geometry_error"),
    m("tessdata-discovery-not-wrapped",
      "        try:\n"
      "            found = fitz.get_tessdata()\n"
      "        except Exception as exc:",
      "        try:\n"
      "            found = fitz.get_tessdata()\n"
      "        except () as exc:",
      "test_tessdata_autodiscovery_failure_raises_geometry_error_not_runtimeerror"),
    m("tessdata-falsy-accepted",
      "        if not found:  # belt for a future falsy-returning pymupdf",
      "        if False:  # belt for a future falsy-returning pymupdf",
      "test_tessdata_autodiscovery_falsy_result_raises_geometry_error"),
    m("ocr-exception-swallowed",
      "            except Exception as exc:  # missing tessdata, OCR init/runtime failure — fail loud, no degrade\n"
      '                raise GeometryError(f"OCR failed on page {num}: {exc}") from exc',
      "            except Exception as exc:  # missing tessdata, OCR init/runtime failure — fail loud, no degrade\n"
      "                raw_words = []",
      "test_ocr_failure_raises_geometry_error"),
    # --- page-range bounds, one clause each (audit D3/F4; M2 was SURVIVED by execution) ---
    m("range-lower-clause-weakened",
      _RANGE,
      _RANGE.replace("first_page < 1", "first_page < -10"),
      "test_out_of_range_or_inverted_page_request_raises_geometry_error[0-1]"),
    m("range-inverted-clause-dropped",
      _RANGE,
      _RANGE.replace("last_page < first_page or ", ""),
      "test_out_of_range_or_inverted_page_request_raises_geometry_error[2-1]"),
    m("range-upper-clause-dropped",
      _RANGE,
      _RANGE.replace(" or last_page > n", ""),
      "test_out_of_range_or_inverted_page_request_raises_geometry_error[1-5]"),
    # --- page identity off page 1 (audit F9) ---
    m("page-index-hardcoded",
      "            page = doc[num - 1]",
      "            page = doc[0]",
      "test_multi_page_range_reads_the_requested_pages_with_their_own_numbers_and_rects"),
    m("page-number-hardcoded",
      "        return PageGeometry(page=num, width=rect.width, height=rect.height, words=tuple(words))",
      "        return PageGeometry(page=1, width=rect.width, height=rect.height, words=tuple(words))",
      "test_multi_page_range_reads_the_requested_pages_with_their_own_numbers_and_rects"),
    m("dropped-keying-hardcoded",
      "        self.dropped_boxes[num] = dropped",
      "        self.dropped_boxes[1] = dropped",
      "test_multi_page_range_reads_the_requested_pages_with_their_own_numbers_and_rects"),
    # --- rotation (audit F8; guard-drop spot-proven) ---
    m("rotation-guard-dropped",
      "            if page.rotation != 0:",
      "            if False:",
      "test_rotated_page_raises_geometry_error"),
    m("rotation-guard-narrowed-to-90",
      "            if page.rotation != 0:",
      "            if page.rotation == 90:",
      "test_rotated_page_raises_geometry_error[180]"),
    # --- coordinate space: rect source, containment, tolerance (G-8) ---
    m("rect-mediabox",
      "            rect = page.rect",
      "            rect = page.mediabox",
      "test_cropped_page_reports_cropbox_dimensions_and_contains_its_boxes"),
    m("oob-guard-dropped",
      "            if (\n                x0 < rect.x0 - _RECT_TOLERANCE_PT",
      "            if False and (\n                x0 < rect.x0 - _RECT_TOLERANCE_PT",
      "test_box_outside_the_page_rect_raises_geometry_error"),
    m("oob-right-clause-dropped",
      "                or x1 > rect.x1 + _RECT_TOLERANCE_PT\n"
      "                or y1 > rect.y1 + _RECT_TOLERANCE_PT",
      "                or y1 > rect.y1 + _RECT_TOLERANCE_PT",
      "test_box_outside_the_page_rect_raises_geometry_error[right]"),
    m("rect-tolerance-widened",
      "_RECT_TOLERANCE_PT = 1.0",
      "_RECT_TOLERANCE_PT = 50.0",
      "test_rect_tolerance_absorbs_subpoint_rounding_but_not_real_overshoot"),
    m("rect-tolerance-zeroed",
      "_RECT_TOLERANCE_PT = 1.0",
      "_RECT_TOLERANCE_PT = 0.0",
      "test_rect_tolerance_absorbs_subpoint_rounding_but_not_real_overshoot"),
    # --- DT-2 normalization: each drop clause + the count (audit F5) ---
    m("empty-text-clause-dropped",
      _DROP,
      "            if x1 <= x0 or y1 <= y0:",
      "test_backend_drops_and_counts_empty_and_degenerate_boxes"),
    m("degenerate-x-clause-dropped",
      _DROP,
      "            if not text.strip() or y1 <= y0:",
      "test_backend_drops_and_counts_empty_and_degenerate_boxes"),
    m("degenerate-y-clause-dropped",
      _DROP,
      "            if not text.strip() or x1 <= x0:",
      "test_backend_drops_and_counts_empty_and_degenerate_boxes"),
    m("drop-count-not-incremented",
      "                dropped += 1",
      "                dropped += 0",
      "test_backend_drops_and_counts_empty_and_degenerate_boxes"),
    m("nan-guard-dropped",
      "            if not all(math.isfinite(c) for c in (x0, y0, x1, y1)):",
      "            if False:",
      "test_non_finite_box_coordinate_raises_geometry_error_not_valueerror"),
    # --- conftest loader (audit F16) ---
    m("loader-caches-before-exec",
      "        sys.modules[name] = mod\n"
      "        try:\n"
      "            spec.loader.exec_module(mod)",
      "        sys.modules[name] = mod\n"
      "        _geometry_pdf_mod = mod\n"
      "        try:\n"
      "            spec.loader.exec_module(mod)",
      "test_fixture_loader_does_not_serve_a_half_executed_module",
      file=C),
    # --- coordinate-space controls (the bug classes G-8 rules on) ---
    m("pixmap-coords-emitted",
      _APPEND,
      "            words.append(WordBox(text=text, bbox=(x0 * self._dpi / 72.0, y0, x1 * self._dpi / 72.0, y1)))",
      "test_ocr_boxes_land_at_page_point_ground_truth_not_pixmap_space"),
    m("crop-origin-offset-emitted",
      _APPEND,
      "            words.append(WordBox(text=text, bbox=(x0 + 60.0, y0 + 100.0, x1 + 60.0, y1 + 100.0)))",
      "test_cropped_page_boxes_land_at_crop_relative_ground_truth"),
    m("native-text-layer-read",
      '                raw_words = page.get_text("words", textpage=textpage)',
      '                raw_words = page.get_text("words")',
      "test_read_pages_recovers_known_words_as_page_point_boxes_inside_the_rect"),
]
