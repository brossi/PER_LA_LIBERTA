"""ocr property/contract tier (non-deterministic step → no equivalence golden, F1).

Render + transcribe are injected; these pin the pure mechanics — ``_stitch_pages`` page-map
invariants, the ``[BLANK]``/``[OCR_ERROR]`` sentinel handling and template↔stitcher *sync* (F6),
resume, the faithful prompt render, and the ``ocr`` → ``reconcile`` marker round-trip that closes
the producer/consumer inversion.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from engine.config.loader import load_book
from engine.contracts.markers import (
    PAGE_MARKER_TEMPLATE,
    SENTINEL_BLANK,
    SENTINEL_OCR_ERROR_PREFIX,
)
from engine.errors import BackendError, InvalidInvocationError
from engine.lang.registry import get_language_plugin
from engine.paths import BookWorkspace
from engine.steps import ocr, reconcile
from engine.util.jsonio import atomic_write_json, read_json

# The exact live OCR_PROMPT (top-level ocr.py:27-38) — the port must reproduce it byte-for-byte
# for PLL, proving the templating extraction changed *where* the facts live, not the prompt sent.
_LIVE_OCR_PROMPT = (
    "Transcribe all the text on this page exactly as printed. "
    "This is a page from a 1913 Italian book titled 'Per la libertà!' by Cesare Crespi. "
    "Rules:\n"
    "- Output only the text content, no commentary\n"
    "- Preserve line breaks as they appear on the page\n"
    "- Preserve all accented characters (à, è, ì, ò, ù, é)\n"
    "- Preserve punctuation exactly\n"
    "- If the page has a page number, include it on its own line\n"
    "- If the page is blank or has only decorative elements, output [BLANK]\n"
    "- Do not translate — output the Italian text as printed"
)


def _cfg_lang(book="synthetic"):
    cfg = load_book(book)
    return cfg, get_language_plugin(cfg.language_id)


def _write_pages(progress_dir, page_texts):
    progress_dir.mkdir(parents=True, exist_ok=True)
    for n, t in page_texts.items():
        atomic_write_json(progress_dir / f"page_{n:04d}.json", {"page": n, "text": t})


def test_render_ocr_prompt_is_faithful_to_live_for_pll():
    cfg, _ = _cfg_lang("per_la_liberta")
    assert ocr._render_ocr_prompt(cfg) == _LIVE_OCR_PROMPT


def test_stitch_pages_map_invariants(tmp_path):
    pdir = tmp_path / "prog"
    pages = {1: "Prima pagina di prova.", 2: SENTINEL_BLANK, 3: "[OCR_ERROR: kaboom]"}
    _write_pages(pdir, pages)

    full_text, page_map = ocr._stitch_pages(pdir, 1, 3)

    assert [e["page"] for e in page_map] == [1, 2, 3]
    for e in page_map:
        # every page contributes its marker, ahead of its body region
        marker = PAGE_MARKER_TEMPLATE.format(e["page"])
        assert marker in full_text
        assert full_text.index(marker) < e["char_start"]
        # char_start/char_end bound exactly this page's body within the stitched text
        body = full_text[e["char_start"]:e["char_end"]]
        assert e["char_start"] <= e["char_end"]
        if e["page"] == 1:
            assert body.strip() == pages[1]
        else:
            # BLANK / OCR_ERROR pages keep their marker but contribute no body
            assert e["char_start"] == e["char_end"]
            assert body == ""

    # the sentinel bodies never leak into the stitched output
    assert SENTINEL_BLANK not in full_text
    assert "kaboom" not in full_text


def test_blank_sentinel_template_and_stitcher_use_one_constant(tmp_path):
    # F6: the prompt template instructs the model to emit SENTINEL_BLANK, and the stitcher drops a
    # page whose body IS that same constant. Asserting both sides here proves they cannot drift —
    # if the constant changed, the template no longer instructs what the stitcher matches.
    cfg, _ = _cfg_lang()
    assert SENTINEL_BLANK in ocr._render_ocr_prompt(cfg)

    pdir = tmp_path / "prog"
    _write_pages(pdir, {1: SENTINEL_BLANK})
    full_text, page_map = ocr._stitch_pages(pdir, 1, 1)
    assert page_map[0]["char_start"] == page_map[0]["char_end"]  # body dropped
    assert SENTINEL_BLANK not in full_text


def test_failing_backend_retains_error_state_but_publishes_no_canonical_output(
    tmp_path, monkeypatch, acq
):
    from engine.errors import BackendError

    monkeypatch.setattr(ocr, "_RETRY_BACKOFF", (0, 0, 0))
    monkeypatch.setattr(ocr, "_PAGE_DELAY", 0)
    cfg, lang = _cfg_lang()
    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()

    class _Failing:
        def transcribe(self, image_bytes, prompt):
            raise RuntimeError("vision-down")

    with pytest.raises(BackendError, match="OCR incomplete"):
        ocr.run(
            workspace=ws, cfg=cfg, lang=lang, model="pro", pages=(1, 2),
            renderer=acq.Renderer(2), backend=_Failing(),
        )

    # Page state remains inspectable/resumable, but an incomplete witness is never published.
    pf = read_json(ws.state / "ocr_pro_pages" / "page_0001.json")
    assert pf["text"].startswith(SENTINEL_OCR_ERROR_PREFIX)
    assert not (ws.data / "copy3_raw.txt").exists()
    assert not (ws.data / "copy3_pro_page_map.json").exists()


def test_transient_backend_failure_retries_then_recovers(tmp_path, monkeypatch, acq):
    # The retry loop's RECOVERY path (ocr.py:183-194), which the always-failing backend above never
    # reaches: a transient transcribe failure is retried and a later success transcribes the page
    # normally — it does NOT become a permanent OCR_ERROR sentinel. Guards a regression that disables
    # the retry (e.g. range(1)), which would turn every transient blip into a dropped page.
    monkeypatch.setattr(ocr, "_RETRY_BACKOFF", (0, 0, 0))
    monkeypatch.setattr(ocr, "_PAGE_DELAY", 0)
    cfg, lang = _cfg_lang()
    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()

    class _FlakyOnce:
        def __init__(self):
            self.calls = 0

        def transcribe(self, image_bytes, prompt):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("transient-blip")
            return "recovered page text"

    backend = _FlakyOnce()
    ocr.run(
        workspace=ws, cfg=cfg, lang=lang, model="pro", pages=(1, 1),
        renderer=acq.Renderer(1), backend=backend,
    )

    pf = read_json(ws.state / "ocr_pro_pages" / "page_0001.json")
    assert pf["text"] == "recovered page text"
    assert not pf["text"].startswith(SENTINEL_OCR_ERROR_PREFIX)
    assert backend.calls == 2  # one failure + one successful retry


def test_unreadable_pdf_page_count_failure_is_a_backend_error(tmp_path, acq):
    # A present-but-corrupt PDF (page_count raises) is a whole-document failure → typed BackendError
    # (exit 5), not a raw fitz traceback. Distinct from the missing-PDF MissingInputError (exit 3).
    from engine.errors import BackendError

    cfg, lang = _cfg_lang()
    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()

    class _UnreadableDoc:
        def page_count(self, pdf_path):
            raise RuntimeError("cannot open broken document")

        def render(self, pdf_path, page, *, dpi):
            raise AssertionError("render must not be reached — page_count failed first")

    with pytest.raises(BackendError) as ei:
        ocr.run(
            workspace=ws, cfg=cfg, lang=lang, model="pro",
            renderer=_UnreadableDoc(), backend=acq.Backend({}),
        )
    assert ei.value.exit_code == 5
    assert "could not read the source scan PDF" in str(ei.value)


def test_per_page_render_failure_retains_state_and_blocks_publication(tmp_path, monkeypatch):
    from engine.errors import BackendError

    # A torn leaf becomes inspectable resumable state, but blocks the canonical witness.
    monkeypatch.setattr(ocr, "_PAGE_DELAY", 0)
    cfg, lang = _cfg_lang()
    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()

    renders: list[int] = []

    class _TornLeafRenderer:
        def page_count(self, pdf_path):
            return 2

        def render(self, pdf_path, page, *, dpi):
            renders.append(page)
            if page == 1:
                raise RuntimeError("torn leaf")
            return str(page).encode()

    class _Backend:
        def transcribe(self, image_bytes, prompt):
            return f"page {int(image_bytes.decode())} text"

    with pytest.raises(BackendError, match=r"page\(s\) 1"):
        ocr.run(
            workspace=ws, cfg=cfg, lang=lang, model="pro", pages=(1, 2),
            renderer=_TornLeafRenderer(), backend=_Backend(),
        )

    pf1 = read_json(ws.state / "ocr_pro_pages" / "page_0001.json")
    assert pf1["text"].startswith(SENTINEL_OCR_ERROR_PREFIX)
    assert "render failed" in pf1["text"]
    assert renders.count(1) == 1, "a render failure is non-transient → not retried"

    assert read_json(ws.state / "ocr_pro_pages" / "page_0002.json")["text"] == "page 2 text"
    assert not (ws.data / "copy3_raw.txt").exists()


def test_error_checkpoint_is_retried_and_then_publishes(tmp_path, monkeypatch):
    monkeypatch.setattr(ocr, "_PAGE_DELAY", 0)
    cfg, lang = _cfg_lang()
    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()
    _write_pages(
        ws.state / "ocr_pro_pages",
        {1: f"{SENTINEL_OCR_ERROR_PREFIX}: previous outage]"},
    )

    class _Renderer:
        def page_count(self, pdf_path):
            return 1

        def render(self, pdf_path, page, *, dpi):
            return b"retry"

    class _Backend:
        def transcribe(self, image_bytes, prompt):
            return "recovered"

    ocr.run(
        workspace=ws,
        cfg=cfg,
        lang=lang,
        model="pro",
        pages=(1, 1),
        renderer=_Renderer(),
        backend=_Backend(),
    )

    assert read_json(ws.state / "ocr_pro_pages" / "page_0001.json")["text"] == "recovered"
    assert "recovered" in (ws.data / "copy3_raw.txt").read_text(encoding="utf-8")


@pytest.mark.parametrize("pages", [(0, 1), (2, 1), (True, 1), [1, 1]])
def test_invalid_page_range_fails_before_workspace_initialization(tmp_path, pages, acq):
    cfg, lang = _cfg_lang()
    ws = BookWorkspace.for_book("synthetic", tmp_path)

    with pytest.raises(ValueError, match="pages"):
        ocr.run(
            workspace=ws,
            cfg=cfg,
            lang=lang,
            model="pro",
            pages=pages,
            renderer=acq.Renderer(2),
            backend=acq.Backend({}),
        )

    assert not ws.root.exists()


def test_out_of_bounds_page_range_is_not_clamped_or_published(tmp_path, acq):
    cfg, lang = _cfg_lang()
    ws = BookWorkspace.for_book("synthetic", tmp_path)

    with pytest.raises(ValueError, match="exceeds"):
        ocr.run(
            workspace=ws,
            cfg=cfg,
            lang=lang,
            model="pro",
            pages=(1, 3),
            renderer=acq.Renderer(2),
            backend=acq.Backend({}),
        )

    assert not ws.root.exists()


@pytest.mark.parametrize("workers", [0, True, 33])
def test_invalid_worker_count_fails_before_workspace_initialization(tmp_path, workers, acq):
    cfg, lang = _cfg_lang()
    ws = BookWorkspace.for_book("synthetic", tmp_path)

    with pytest.raises(ValueError, match="workers"):
        ocr.run(
            workspace=ws,
            cfg=cfg,
            lang=lang,
            model="pro",
            pages=(1, 1),
            workers=workers,
            renderer=acq.Renderer(1),
            backend=acq.Backend({}),
        )

    assert not ws.root.exists()


def test_resume_skips_completed_pages(tmp_path, monkeypatch, acq):
    monkeypatch.setattr(ocr, "_PAGE_DELAY", 0)
    cfg, lang = _cfg_lang()
    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()
    page_texts = acq.split((acq.inputs / "copy3_raw.txt").read_text(encoding="utf-8"))

    # pre-seed page 1 as already OCR'd with a distinctive body
    _write_pages(ws.state / "ocr_pro_pages", {1: "PRESEEDED ONE"})

    rendered: list[int] = []

    class _CountingRenderer:
        def page_count(self, pdf_path):
            return 2

        def render(self, pdf_path, page, *, dpi):
            rendered.append(page)
            return str(page).encode()

    ocr.run(
        workspace=ws, cfg=cfg, lang=lang, model="pro", pages=(1, 2),
        renderer=_CountingRenderer(), backend=acq.Backend(page_texts),
    )

    assert rendered == [2], "page 1 should resume from cache, only page 2 re-rendered"
    text = (ws.data / "copy3_raw.txt").read_text(encoding="utf-8")
    assert "PRESEEDED ONE" in text  # the resumed page's cached body, not a re-OCR


def test_ocr_to_reconcile_marker_roundtrip(tmp_path):
    # The closing contract: a stitched OCR output is parseable by reconcile's marker stripper +
    # page-map consumer — the ⟨PAGE:N⟩ protocol round-trips between the two ported steps.
    pdir = tmp_path / "prog"
    bodies = {1: "Riga uno.\nRiga due.", 2: "Pagina due, testo."}
    _write_pages(pdir, bodies)
    full_text, page_map = ocr._stitch_pages(pdir, 1, 2)

    clean, page_breaks = reconcile._strip_page_markers(full_text)
    assert sorted(page_breaks.values()) == [1, 2]      # both page numbers recovered
    assert "⟨PAGE" not in clean                          # markers stripped
    assert "Riga uno." in clean and "Pagina due, testo." in clean

    # the page map reconcile reads is well-formed (the shape its chapter_pages logic depends on)
    assert [e["page"] for e in page_map] == [1, 2]
    assert all(e["char_start"] <= e["char_end"] for e in page_map)


def test_unknown_model_role_is_rejected(tmp_path, acq):
    cfg, lang = _cfg_lang()
    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()
    with pytest.raises(ValueError, match="unknown ocr model role"):
        ocr.run(
            workspace=ws, cfg=cfg, lang=lang, model="nonesuch",
            renderer=acq.Renderer(1), backend=acq.Backend({}),
        )


def test_default_gemini_backend_without_key_is_a_backend_error(monkeypatch):
    # The default backend's missing-key failure branch → typed BackendError (exit 5), not a bare
    # ValueError. Exercised without network (construction fails before any client call).
    from engine.errors import BackendError

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(BackendError, match="No Gemini API key"):
        ocr.GeminiOcrBackend(model_id="whatever")


def test_gemini_no_text_preserves_finish_reason_as_backend_error():
    response = SimpleNamespace(
        text=None,
        candidates=[SimpleNamespace(finish_reason="RECITATION")],
    )

    with pytest.raises(ocr.OcrProviderRefusal, match="finish_reason=RECITATION"):
        ocr._gemini_response_text(response)


class _Fallback:
    def __init__(self, text="fallback text", *, language="ita", thresholding_method=2):
        self.text = text
        self.calls = 0
        self._identity = {
            "backend": "fake-tesseract 1",
            "language": language,
            "psm": 3,
            "thresholding_method": thresholding_method,
        }

    @property
    def identity(self):
        return dict(self._identity)

    def transcribe(self, image_bytes):
        self.calls += 1
        return ocr.FallbackTranscription(text=self.text, provenance=self.identity)


def test_recitation_refusal_uses_only_configured_fallback_and_publishes_provenance(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(ocr, "_PAGE_DELAY", 0)
    cfg, lang = _cfg_lang()
    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()

    class _Renderer:
        def page_count(self, pdf_path):
            return 1

        def render(self, pdf_path, page, *, dpi):
            return b"stable rendered page"

    class _Refusal:
        calls = 0

        def transcribe(self, image_bytes, prompt):
            self.calls += 1
            raise ocr.OcrProviderRefusal("RECITATION")

    backend = _Refusal()
    fallback = _Fallback()
    result = ocr.run(
        workspace=ws, cfg=cfg, lang=lang, model="flash", pages=(1, 1),
        renderer=_Renderer(), backend=backend, fallback=fallback,
    )

    assert backend.calls == 1, "a typed refusal is non-transient and must not be retried"
    assert fallback.calls == 1
    assert result["fallback_pages"] == 1
    checkpoint = read_json(ws.state / "ocr_flash_pages/page_0001.json")
    provenance = checkpoint["provenance"]
    assert provenance["kind"] == "provider_refusal_fallback"
    assert provenance["primary"]["detail"] == "RECITATION"
    assert provenance["fallback"] == fallback.identity
    assert provenance["render"]["image_sha256"]
    assert provenance["text_sha256"]
    page_map = read_json(ws.data / "copy3_flash_page_map.json")
    assert page_map[0]["provenance"] == provenance
    report = read_json(ws.state / "ocr_flash_fallbacks.json")
    assert report["pages"] == [{"page": 1, "provenance": provenance}]


def test_backend_outage_retries_and_never_enters_recitation_fallback(
    tmp_path, monkeypatch, acq
):
    monkeypatch.setattr(ocr, "_RETRY_BACKOFF", (0, 0, 0))
    cfg, lang = _cfg_lang()
    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()

    class _Outage:
        calls = 0

        def transcribe(self, image_bytes, prompt):
            self.calls += 1
            raise RuntimeError("transport down")

    backend = _Outage()
    fallback = _Fallback()
    with pytest.raises(BackendError, match="OCR incomplete"):
        ocr.run(
            workspace=ws, cfg=cfg, lang=lang, model="flash", pages=(1, 1),
            renderer=acq.Renderer(1), backend=backend, fallback=fallback,
        )

    assert backend.calls == 3
    assert fallback.calls == 0
    failure = read_json(ws.state / "ocr_flash_pages/page_0001.json")["failure"]
    assert failure["class"] == "backend_error"
    assert failure["retryable"] is True


def test_render_failure_never_enters_recitation_fallback(tmp_path, acq):
    cfg, lang = _cfg_lang()
    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()

    class _RenderFailure:
        def page_count(self, pdf_path):
            return 1

        def render(self, pdf_path, page, *, dpi):
            raise RuntimeError("cannot render")

    fallback = _Fallback()
    with pytest.raises(BackendError, match="OCR incomplete"):
        ocr.run(
            workspace=ws, cfg=cfg, lang=lang, model="flash", pages=(1, 1),
            renderer=_RenderFailure(), backend=acq.Backend({}), fallback=fallback,
        )
    assert fallback.calls == 0
    failure = read_json(ws.state / "ocr_flash_pages/page_0001.json")["failure"]
    assert failure["class"] == "render_error"


def test_valid_fallback_checkpoint_resumes_without_primary_or_fallback_call(tmp_path):
    cfg, lang = _cfg_lang()
    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()

    class _Renderer:
        def page_count(self, pdf_path):
            return 1

        def render(self, pdf_path, page, *, dpi):
            return b"same image"

    class _Refusal:
        calls = 0

        def transcribe(self, image_bytes, prompt):
            self.calls += 1
            raise ocr.OcrProviderRefusal("RECITATION")

    renderer = _Renderer()
    backend = _Refusal()
    fallback = _Fallback()
    values = dict(
        workspace=ws, cfg=cfg, lang=lang, model="flash", pages=(1, 1),
        renderer=renderer, backend=backend, fallback=fallback,
    )
    ocr.run(**values)
    ocr.run(**values)
    assert backend.calls == 1
    assert fallback.calls == 1


def test_fallback_checkpoint_image_or_configuration_drift_is_not_reused(tmp_path):
    cfg, lang = _cfg_lang()
    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()

    class _Renderer:
        def __init__(self, image):
            self.image = image

        def page_count(self, pdf_path):
            return 1

        def render(self, pdf_path, page, *, dpi):
            return self.image

    class _Refusal:
        calls = 0

        def transcribe(self, image_bytes, prompt):
            self.calls += 1
            raise ocr.OcrProviderRefusal("RECITATION")

    backend = _Refusal()
    first = _Fallback(language="ita")
    ocr.run(
        workspace=ws, cfg=cfg, lang=lang, model="flash", pages=(1, 1),
        renderer=_Renderer(b"image one"), backend=backend, fallback=first,
    )
    second = _Fallback(language="eng")
    ocr.run(
        workspace=ws, cfg=cfg, lang=lang, model="flash", pages=(1, 1),
        renderer=_Renderer(b"image two"), backend=backend, fallback=second,
    )
    assert backend.calls == 2
    assert second.calls == 1


def test_fallback_checkpoint_source_drift_is_not_reused(tmp_path):
    cfg, lang = _cfg_lang()
    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()
    ws.scans.mkdir(parents=True, exist_ok=True)
    source = ws.scans / cfg.manifest.scan.pdf
    source.write_bytes(b"source version one")

    class _Renderer:
        def page_count(self, pdf_path):
            return 1

        def render(self, pdf_path, page, *, dpi):
            return b"same rendered image"

    class _Refusal:
        calls = 0

        def transcribe(self, image_bytes, prompt):
            self.calls += 1
            raise ocr.OcrProviderRefusal("RECITATION")

    backend = _Refusal()
    fallback = _Fallback()
    values = dict(
        workspace=ws, cfg=cfg, lang=lang, model="flash", pages=(1, 1),
        renderer=_Renderer(), backend=backend, fallback=fallback,
    )
    ocr.run(**values)
    source.write_bytes(b"source version two")
    ocr.run(**values)
    assert backend.calls == 2
    assert fallback.calls == 2


def test_invalid_provider_response_never_enters_recitation_fallback(tmp_path, acq):
    cfg, lang = _cfg_lang()
    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()

    class _Invalid:
        calls = 0

        def transcribe(self, image_bytes, prompt):
            self.calls += 1
            raise ocr.OcrInvalidResponse("empty response")

    backend = _Invalid()
    fallback = _Fallback()
    with pytest.raises(BackendError, match="OCR incomplete"):
        ocr.run(
            workspace=ws, cfg=cfg, lang=lang, model="flash", pages=(1, 1),
            renderer=acq.Renderer(1), backend=backend, fallback=fallback,
        )
    assert backend.calls == 1
    assert fallback.calls == 0
    failure = read_json(ws.state / "ocr_flash_pages/page_0001.json")["failure"]
    assert failure["class"] == "invalid_response"


def test_fallback_threshold_option_without_language_is_invalid_and_write_free(tmp_path, acq):
    cfg, lang = _cfg_lang()
    ws = BookWorkspace.for_book("synthetic", tmp_path)
    with pytest.raises(InvalidInvocationError, match="requires --fallback-tesseract-language"):
        ocr.run(
            workspace=ws, cfg=cfg, lang=lang, model="flash", pages=(1, 1),
            renderer=acq.Renderer(1), backend=acq.Backend({}),
            fallback_thresholding_method=2,
        )
    assert not ws.root.exists()


def test_missing_scan_pdf_is_a_clean_error_with_default_renderer(tmp_path):
    # The real renderer needs the PDF on disk; absent → a typed MissingInputError (exit 3), not a
    # PyMuPDF traceback. (Default renderer path; no PDF created, no network — the guard fires
    # before any fitz call.)
    from engine.errors import MissingInputError

    cfg, lang = _cfg_lang()
    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()
    with pytest.raises(MissingInputError, match="source scan PDF not found"):
        ocr.run(workspace=ws, cfg=cfg, lang=lang, model="pro", pages=(1, 1))


@pytest.mark.integration
def test_fitz_renderer_and_run_against_a_real_pdf(tmp_path, monkeypatch):
    # The lone real-fitz smoke (D7): exercises the PyMuPDF binding (page_count + render → JPEG)
    # AND the full ocr.run path with the *default* renderer on a real 2-page PDF, transcription
    # canned (no network). Validate-bindings: the import + render path runs, not shape-asserted.
    import fitz

    monkeypatch.setattr(ocr, "_PAGE_DELAY", 0)
    cfg, lang = _cfg_lang()

    # The scan PDF resolves to books/<id>/scans/<manifest.scan.pdf> — build a real one there.
    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()
    ws.scans.mkdir(parents=True, exist_ok=True)
    pdf_path = ws.scans / cfg.manifest.scan.pdf
    doc = fitz.open()
    for i in range(2):
        doc.new_page().insert_text((72, 72), f"Pagina di prova {i + 1}")
    doc.save(str(pdf_path))
    doc.close()

    # Direct binding check: real render returns JPEG bytes (SOI marker), real page_count is 2.
    renderer = ocr.FitzPageRenderer()
    assert renderer.page_count(pdf_path) == 2
    assert renderer.render(pdf_path, 1, dpi=72)[:2] == b"\xff\xd8"

    class _ConstBackend:
        def transcribe(self, image_bytes, prompt):
            assert image_bytes[:2] == b"\xff\xd8"  # received a real rendered JPEG
            return "testo OCR di prova"

    result = ocr.run(
        workspace=ws, cfg=cfg, lang=lang, model="pro", pages=(1, 2),
        backend=_ConstBackend(),  # default (real fitz) renderer
    )
    assert result["pages"] == 2
    text = (ws.data / "copy3_raw.txt").read_text(encoding="utf-8")
    assert PAGE_MARKER_TEMPLATE.format(1) in text and PAGE_MARKER_TEMPLATE.format(2) in text
    assert text.count("testo OCR di prova") == 2
