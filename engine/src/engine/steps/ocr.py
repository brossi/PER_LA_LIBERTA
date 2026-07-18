"""ocr step — third OCR witness via a vision model on the source PDF scan.

Faithful port of the top-level ``ocr.py``: render each PDF page to an image, transcribe it with a
vision model, and stitch the per-page results into ``copy3`` text + a page map — the names
``reconcile`` reads. The mechanics (page-range, resume via a per-page progress dir, sequential /
thread-pool workers, ``[2, 8, 16]`` retry backoff, ``_stitch_pages``) are book/language-neutral
and ported ~verbatim. ``_stitch_pages`` is pure given the per-page texts → unit-tested directly.

The book/language opinions leave the code:

  - the source PDF is a per-book input at ``books/<id>/scans/<manifest.scan.pdf>`` (``ws.scans``, D7);
  - the model ids come from ``manifest.ocr.models`` — no baked frontier default (D3/BR-010);
  - the prompt is the book-neutral ``ocr`` template rendered with the book/language context (D2/BR-008).

Three seams are injectable (D1/BR-009), defaulting to the real backends so the property /
separability tiers run offline: ``PageRenderer`` (PyMuPDF render + page count), ``OcrBackend`` (the
vision call), and the explicit RECITATION-only ``OcrFallback``. The ``⟨PAGE:N⟩`` / ``[BLANK]`` /
``[OCR_ERROR]`` protocol constants are single-sourced
in ``contracts.markers`` so the prompt template, the stitcher, and ``reconcile`` cannot drift (F6).

Resume scaffolding (the per-page progress dir) is transient state → ``ws.state``; the final
``copy3`` text + page map are pipeline inputs → ``ws.data`` (the live ``ocr`` parks progress beside
the output in ``data/``; routing it to ``state/`` aligns with the engine's area semantics — a
two-way door).
"""

from __future__ import annotations

import hashlib
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ..config.models import ResolvedConfig
from ..contracts.markers import (
    PAGE_MARKER_TEMPLATE,
    SENTINEL_BLANK,
    SENTINEL_OCR_ERROR_PREFIX,
)
from ..errors import BackendError, InvalidInvocationError, MissingInputError
from ..lang.base import LanguagePlugin
from ..ocr_provenance import is_ocr_fallback_provenance
from ..paths import BookWorkspace
from ..prompts.templating import PromptTemplate, build_prompt_context
from ..util.jsonio import atomic_write_json, atomic_write_text, read_json

# Output filenames reconcile reads: pro → copy3_raw.txt (quality witness), flash → copy3_flash.txt.
_OUTPUT_NAMES = {"pro": "copy3_raw.txt", "flash": "copy3_flash.txt"}

# Scan-render tuning — code defaults (promotable to the manifest ocr block if a book needs them).
_DEFAULT_DPI = 200
_JPEG_QUALITY = 85

# Retry backoff between transcription attempts (seconds) + inter-page politeness delay, verbatim
# from live ocr. Module constants so tests can drop them to zero for speed.
_RETRY_BACKOFF = (2, 8, 16)
_PAGE_DELAY = 0.2
_MAX_WORKERS = 32


# --- injectable seams (D1/BR-009) ------------------------------------------------------ #

class PageRenderer(Protocol):
    """Read a source PDF: total page count + render one page to image bytes. The PyMuPDF seam,
    injectable so unit tests need neither a real PDF nor the native library."""

    def page_count(self, pdf_path: Path) -> int: ...

    def render(self, pdf_path: Path, page: int, *, dpi: int) -> bytes: ...


class OcrBackend(Protocol):
    """Transcribe one page image to text — the vision-model seam (image→text). Tests inject canned
    page text; the default calls the configured model."""

    def transcribe(self, image_bytes: bytes, prompt: str) -> str: ...


class OcrFallback(Protocol):
    """Page-local fallback eligible only for a typed provider refusal."""

    @property
    def identity(self) -> dict: ...

    def transcribe(self, image_bytes: bytes) -> "FallbackTranscription": ...


class OcrProviderRefusal(BackendError):
    """The provider deliberately returned no transcription for a named reason."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"Gemini returned no text (finish_reason={reason})")


class OcrInvalidResponse(BackendError):
    """The provider response was structurally successful but contained no usable text."""


@dataclass(frozen=True, slots=True)
class FallbackTranscription:
    text: str
    provenance: dict


class TesseractRecitationFallback:
    """Explicit local fallback for a Gemini RECITATION refusal — and no other outcome."""

    def __init__(self, *, language: str, thresholding_method: int | None = None) -> None:
        if not isinstance(language, str) or not language.strip():
            raise InvalidInvocationError("fallback Tesseract language must be non-empty")
        if thresholding_method not in {None, 0, 1, 2}:
            raise InvalidInvocationError("fallback thresholding method must be 0, 1, or 2")
        try:
            result = subprocess.run(
                ["tesseract", "--version"], capture_output=True, text=True, check=True
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise BackendError(f"could not read fallback Tesseract version: {exc}") from exc
        banner = result.stdout.splitlines()
        self._backend = banner[0] if banner else "tesseract unknown"
        self._language = language
        self._thresholding_method = thresholding_method

    @property
    def identity(self) -> dict:
        return {
            "backend": self._backend,
            "language": self._language,
            "psm": 3,
            "thresholding_method": self._thresholding_method,
        }

    def transcribe(self, image_bytes: bytes) -> FallbackTranscription:
        command = [
            "tesseract", "stdin", "stdout", "-l", self._language, "--psm", "3",
        ]
        if self._thresholding_method is not None:
            command.extend(["-c", f"thresholding_method={self._thresholding_method}"])
        try:
            result = subprocess.run(
                command, input=image_bytes, capture_output=True, check=True
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise BackendError(f"Tesseract fallback failed: {exc}") from exc
        text = result.stdout.decode("utf-8").strip()
        if not text:
            raise BackendError("Tesseract fallback returned empty text")
        return FallbackTranscription(text=text, provenance=self.identity)


class FitzPageRenderer:
    """Default ``PageRenderer`` — PyMuPDF (``fitz``) page count + JPEG render, verbatim from live
    ``_get_page_count`` / ``_render_page``."""

    def page_count(self, pdf_path: Path) -> int:
        import fitz

        doc = fitz.open(str(pdf_path))
        try:
            return len(doc)
        finally:
            doc.close()

    def render(self, pdf_path: Path, page: int, *, dpi: int) -> bytes:
        import io

        import fitz
        from PIL import Image

        doc = fitz.open(str(pdf_path))
        try:
            pix = doc[page - 1].get_pixmap(dpi=dpi)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        finally:
            doc.close()

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=_JPEG_QUALITY)
        return buf.getvalue()


class GeminiOcrBackend:
    """Default ``OcrBackend`` — Gemini vision, verbatim from live ``_ocr_page``. The concrete model
    id comes from ``manifest.ocr.models`` (no baked default); a missing API key is a ``BackendError``."""

    def __init__(self, *, model_id: str, api_key: str | None = None) -> None:
        if not api_key:
            import os

            api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise BackendError("No Gemini API key. Set GEMINI_API_KEY or pass --api-key.")

        from google import genai

        self._client = genai.Client(api_key=api_key)
        self._model_id = model_id

    def transcribe(self, image_bytes: bytes, prompt: str) -> str:
        from google.genai import types

        response = self._client.models.generate_content(
            model=self._model_id,
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                        types.Part.from_text(text=prompt),
                    ],
                )
            ],
        )
        return _gemini_response_text(response)


def _gemini_response_text(response) -> str:
    """Extract provider text or raise a diagnostic error retaining the finish reason."""
    text = response.text
    if not isinstance(text, str):
        reasons = sorted(
            {
                str(candidate.finish_reason).removeprefix("FinishReason.")
                for candidate in (response.candidates or ())
                if getattr(candidate, "finish_reason", None) is not None
            }
        )
        detail = ", ".join(reasons) if reasons else "unknown"
        if "RECITATION" in reasons:
            raise OcrProviderRefusal("RECITATION")
        raise OcrInvalidResponse(f"Gemini returned no text (finish_reason={detail})")
    text = text.strip()
    if not text:
        raise OcrInvalidResponse("Gemini returned an empty text response")
    return text


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


# --- pure mechanics ---------------------------------------------------------------------- #

def _render_ocr_prompt(cfg: ResolvedConfig) -> str:
    """Render the book-neutral ``ocr`` template with the book/language context + the blank sentinel."""
    template = PromptTemplate.load("ocr")
    context = build_prompt_context(cfg)
    return template.render(**context, blank_sentinel=SENTINEL_BLANK)


def _ocr_single_page(
    renderer: PageRenderer,
    backend: OcrBackend,
    pdf_path: Path,
    page: int,
    prompt: str,
    progress_dir: Path,
    dpi: int,
    *,
    fallback: OcrFallback | None,
    source_sha256: str,
    primary_model_id: str,
) -> int:
    """Render + transcribe one page, persisting the result for resume. Returns ``page``.

    A present progress file short-circuits (resume). A **render** failure is non-transient, so it
    gets no retry — the page becomes an ``[OCR_ERROR: render failed: …]`` checkpoint. A
    **transcription** failure is retried with ``_RETRY_BACKOFF``, then becomes an ``[OCR_ERROR: …]``
    checkpoint. The run audits those records before stitching: an error is retained for diagnosis
    and retry but blocks canonical publication.
    """
    # ``run`` has already provenance-validated the checkpoint set and passes only pages that need
    # work. Do not reintroduce the old presence-only shortcut here: it would resurrect a fallback
    # checkpoint that the caller rejected for source/image/configuration drift.
    page_file = progress_dir / f"page_{page:04d}.json"

    try:
        img_bytes = renderer.render(pdf_path, page, dpi=dpi)
    except Exception as exc:  # non-transient → no retry (a corrupt page renders the same each time)
        atomic_write_json(
            page_file,
            {
                "page": page,
                "text": f"{SENTINEL_OCR_ERROR_PREFIX}: render failed: {exc}]",
                "failure": {
                    "class": "render_error",
                    "retryable": False,
                    "detail": f"{type(exc).__name__}: {exc}",
                    "attempts": 1,
                },
            },
        )
        return page

    text: str | None = None
    failure: dict | None = None
    for attempt in range(len(_RETRY_BACKOFF)):
        try:
            text = backend.transcribe(img_bytes, prompt)
            if not isinstance(text, str) or not text.strip():
                raise OcrInvalidResponse("OCR backend returned empty or non-text output")
            break
        except OcrProviderRefusal as exc:
            failure = {
                "class": "provider_refusal",
                "retryable": False,
                "detail": exc.reason,
                "attempts": attempt + 1,
            }
            break
        except OcrInvalidResponse as exc:
            failure = {
                "class": "invalid_response",
                "retryable": False,
                "detail": str(exc),
                "attempts": attempt + 1,
            }
            break
        except Exception as exc:  # backend transient failure → retry, then sentinel
            if attempt < len(_RETRY_BACKOFF) - 1:
                if _RETRY_BACKOFF[attempt]:
                    time.sleep(_RETRY_BACKOFF[attempt])
            else:
                failure = {
                    "class": "backend_error",
                    "retryable": True,
                    "detail": f"{type(exc).__name__}: {exc}",
                    "attempts": attempt + 1,
                }

    if failure and failure["class"] == "provider_refusal" and failure["detail"] == "RECITATION":
        if fallback is not None:
            try:
                recovered = fallback.transcribe(img_bytes)
                text_sha256 = hashlib.sha256(recovered.text.encode("utf-8")).hexdigest()
                atomic_write_json(page_file, {
                    "page": page,
                    "text": recovered.text,
                    "provenance": {
                        "kind": "provider_refusal_fallback",
                        "source_sha256": source_sha256,
                        "render": {
                            "dpi": dpi,
                            "jpeg_quality": _JPEG_QUALITY,
                            "image_sha256": hashlib.sha256(img_bytes).hexdigest(),
                        },
                        "primary": {
                            "backend": type(backend).__name__,
                            "model_id": primary_model_id,
                            "outcome_class": failure["class"],
                            "detail": failure["detail"],
                            "attempts": failure["attempts"],
                        },
                        "fallback": recovered.provenance,
                        "text_sha256": text_sha256,
                    },
                })
                return page
            except Exception as exc:
                failure["fallback_error"] = f"{type(exc).__name__}: {exc}"

    if failure is not None:
        detail = failure["detail"]
        atomic_write_json(page_file, {
            "page": page,
            "text": f"{SENTINEL_OCR_ERROR_PREFIX}: {detail}]",
            "failure": failure,
        })
        return page

    atomic_write_json(page_file, {"page": page, "text": text or ""})
    return page


def _completed_page_text(
    page_file: Path,
    expected_page: int,
    *,
    source_sha256: str | None = None,
    renderer: PageRenderer | None = None,
    pdf_path: Path | None = None,
    dpi: int = _DEFAULT_DPI,
    fallback_identity: dict | None = None,
) -> str | None:
    """Return a reusable checkpoint body, or ``None`` when it must be regenerated.

    Presence alone is not completion: malformed records, records for another page, non-string
    bodies, and persisted ``[OCR_ERROR...]`` sentinels are incomplete.  ``[BLANK]`` is a valid
    completed transcription and remains resumable.
    """
    if not page_file.is_file():
        return None
    try:
        record = read_json(page_file)
    except (OSError, UnicodeError, ValueError, RecursionError):
        return None
    if not isinstance(record, dict):
        return None
    if type(record.get("page")) is not int or record["page"] != expected_page:
        return None
    text = record.get("text")
    if not isinstance(text, str) or text.startswith(SENTINEL_OCR_ERROR_PREFIX):
        return None
    provenance = record.get("provenance")
    if is_ocr_fallback_provenance(provenance):
        if source_sha256 is not None and provenance.get("source_sha256") != source_sha256:
            return None
        if fallback_identity is not None:
            stored_identity = provenance.get("fallback", provenance)
            if any(stored_identity.get(key) != value for key, value in fallback_identity.items()):
                return None
        render = provenance.get("render", provenance)
        stored_image_sha256 = render.get("image_sha256")
        if renderer is not None and pdf_path is not None and isinstance(stored_image_sha256, str):
            try:
                image = renderer.render(pdf_path, expected_page, dpi=dpi)
            except Exception:
                return None
            if hashlib.sha256(image).hexdigest() != stored_image_sha256:
                return None
    return text


def _validate_run_options(*, pages: tuple[int, int] | None, workers: int) -> None:
    """Reject unsafe caller options before the workspace can be initialized or mutated."""
    if type(workers) is not int or not 1 <= workers <= _MAX_WORKERS:
        raise InvalidInvocationError(
            f"workers must be an integer in [1, {_MAX_WORKERS}], got {workers!r}"
        )
    if pages is None:
        return
    if (
        not isinstance(pages, tuple)
        or len(pages) != 2
        or any(type(value) is not int for value in pages)
    ):
        raise InvalidInvocationError("pages must be a two-integer tuple (START, END)")
    start, end = pages
    if start < 1 or end < start:
        raise InvalidInvocationError(
            f"pages must be an inclusive 1-based range with START <= END, got {pages!r}"
        )


def _process_pages(
    renderer: PageRenderer,
    backend: OcrBackend,
    pdf_path: Path,
    todo: list[int],
    prompt: str,
    progress_dir: Path,
    dpi: int,
    workers: int,
    *,
    fallback: OcrFallback | None,
    source_sha256: str,
    primary_model_id: str,
) -> None:
    """Transcribe every ``todo`` page, sequentially or via a thread pool. (Collapses the live
    ``_ocr_pages_sequential`` / ``_ocr_pages_parallel`` pair, whose only difference was a cosmetic
    progress bar, into one behaviour-equivalent loop.)"""
    if workers <= 1:
        for page in todo:
            _ocr_single_page(
                renderer, backend, pdf_path, page, prompt, progress_dir, dpi,
                fallback=fallback, source_sha256=source_sha256,
                primary_model_id=primary_model_id,
            )
            if _PAGE_DELAY:
                time.sleep(_PAGE_DELAY)
        return

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                _ocr_single_page, renderer, backend, pdf_path, p, prompt, progress_dir, dpi,
                fallback=fallback, source_sha256=source_sha256,
                primary_model_id=primary_model_id,
            ): p
            for p in todo
        }
        for future in as_completed(futures):
            page = futures[future]
            try:
                future.result()
            except Exception as exc:  # noqa: BLE001 — surface, keep going with other pages
                print(f"    Error on page {page}: {exc}")


def _stitch_pages(
    progress_dir: Path, start: int, end: int
) -> tuple[str, list[dict]]:
    """Stitch per-page JSON files into ``copy3`` text + a page map. Pure given the progress files.

    Each page contributes a ``⟨PAGE:N⟩`` marker line; a ``[BLANK]`` or ``[OCR_ERROR…]`` page
    contributes the marker but no body. ``char_start``/``char_end`` bound the page's body within
    the stitched text. Verbatim from live ``_stitch_pages`` minus the I/O (the caller writes)."""
    parts: list[str] = []
    page_map: list[dict] = []
    pos = 0

    for page in range(start, end + 1):
        page_data = read_json(progress_dir / f"page_{page:04d}.json")
        text = page_data["text"]

        marker = PAGE_MARKER_TEMPLATE.format(page) + "\n"
        parts.append(marker)
        pos += len(marker)

        char_start = pos
        if text and text != SENTINEL_BLANK and not text.startswith(SENTINEL_OCR_ERROR_PREFIX):
            parts.append(text + "\n")
            pos += len(text) + 1

        parts.append("\n")
        pos += 1

        page_entry = {"page": page, "char_start": char_start, "char_end": pos - 1}
        if isinstance(page_data.get("provenance"), dict):
            page_entry["provenance"] = page_data["provenance"]
        page_map.append(page_entry)

    return "".join(parts), page_map


# --- orchestration ----------------------------------------------------------------------- #

def run(
    *,
    workspace: BookWorkspace,
    cfg: ResolvedConfig,
    lang: LanguagePlugin,
    model: str = "pro",
    pages: tuple[int, int] | None = None,
    workers: int = 1,
    api_key: str | None = None,
    fallback_tesseract_language: str | None = None,
    fallback_thresholding_method: int | None = None,
    renderer: PageRenderer | None = None,
    backend: OcrBackend | None = None,
    fallback: OcrFallback | None = None,
) -> dict:
    """OCR the source scan in ``workspace`` → ``copy3`` text + page map in ``ws.data``.

    ``model`` selects a role in ``manifest.ocr.models`` (``"pro"`` → ``copy3_raw.txt``, ``"flash"``
    → ``copy3_flash.txt``). ``pages`` is an inclusive 1-indexed range (default: the whole PDF).
    ``renderer``/``backend`` default to the real PyMuPDF/Gemini backends and are injectable so unit
    tests run offline. ``lang`` is unused (OCR is language-neutral) but kept for the uniform
    signature. Returns a summary dict.
    """
    _validate_run_options(pages=pages, workers=workers)
    if fallback_thresholding_method is not None and fallback_tesseract_language is None:
        raise InvalidInvocationError(
            "--fallback-thresholding-method requires --fallback-tesseract-language"
        )
    if fallback is not None and fallback_tesseract_language is not None:
        raise InvalidInvocationError(
            "pass either an injected fallback or --fallback-tesseract-language, not both"
        )

    ws = workspace

    if model not in cfg.manifest.ocr.models:
        raise InvalidInvocationError(
            f"unknown ocr model role {model!r}; manifest declares "
            f"{sorted(cfg.manifest.ocr.models)}"
        )
    if model not in _OUTPUT_NAMES:
        raise InvalidInvocationError(f"ocr model role {model!r} has no output-filename mapping")

    pdf_path = ws.scans / cfg.manifest.scan.pdf

    using_default_renderer = renderer is None
    renderer = renderer or FitzPageRenderer()
    # The real PyMuPDF renderer needs the PDF on disk; an injected renderer (tests) does not, so
    # the path is merely *resolved* there (D7). A real run with a missing scan is a clean error.
    if using_default_renderer and not pdf_path.is_file():
        raise MissingInputError(f"source scan PDF not found: {pdf_path}")
    source_sha256 = (
        _sha256_file(pdf_path)
        if pdf_path.is_file()
        else hashlib.sha256(f"injected-renderer:{pdf_path}".encode("utf-8")).hexdigest()
    )

    try:
        total_pages = renderer.page_count(pdf_path)
    except Exception as exc:  # a present-but-unreadable PDF is a whole-document backend failure
        raise BackendError(f"could not read the source scan PDF {pdf_path}: {exc}") from exc
    if type(total_pages) is not int or total_pages < 1:
        raise BackendError(
            f"source scan PDF {pdf_path} reported an invalid page count: {total_pages!r}"
        )

    start, end = 1, total_pages
    if pages:
        start, end = pages
        if end > total_pages:
            raise InvalidInvocationError(
                f"pages range {pages!r} exceeds the source scan's {total_pages} pages"
            )
    page_count = end - start + 1

    if backend is None:
        backend = GeminiOcrBackend(model_id=cfg.manifest.ocr.models[model], api_key=api_key)
    if fallback is None and fallback_tesseract_language is not None:
        fallback = TesseractRecitationFallback(
            language=fallback_tesseract_language,
            thresholding_method=fallback_thresholding_method,
        )
    fallback_identity = fallback.identity if fallback is not None else None

    prompt = _render_ocr_prompt(cfg)

    # Invalid caller options and an invalid document range have all failed before this point.
    ws.ensure()

    progress_dir = ws.resolve("state", f"ocr_{model}_pages")
    progress_dir.mkdir(parents=True, exist_ok=True)

    completed = {
        page
        for page in range(start, end + 1)
        if _completed_page_text(
            progress_dir / f"page_{page:04d}.json",
            page,
            source_sha256=source_sha256,
            renderer=renderer,
            pdf_path=pdf_path,
            fallback_identity=fallback_identity,
        ) is not None
    }
    todo = [p for p in range(start, end + 1) if p not in completed]
    if completed:
        print(f"  OCR [{model}]: resuming — {len(completed)} done, {len(todo)} remaining")
    else:
        print(f"  OCR [{model}]: {page_count} pages "
              f"({cfg.manifest.ocr.models[model]})"
              + (f", {workers} workers" if workers > 1 else ""))

    if todo:
        _process_pages(
            renderer, backend, pdf_path, todo, prompt, progress_dir, _DEFAULT_DPI, workers,
            fallback=fallback,
            source_sha256=source_sha256,
            primary_model_id=cfg.manifest.ocr.models[model],
        )

    incomplete = [
        page
        for page in range(start, end + 1)
        if _completed_page_text(
            progress_dir / f"page_{page:04d}.json",
            page,
            source_sha256=source_sha256,
            renderer=renderer,
            pdf_path=pdf_path,
            fallback_identity=fallback_identity,
        ) is None
    ]
    if incomplete:
        preview = ", ".join(str(page) for page in incomplete[:10])
        suffix = "" if len(incomplete) <= 10 else f", … ({len(incomplete)} total)"
        raise BackendError(
            f"OCR incomplete for page(s) {preview}{suffix}; retained resumable page state and "
            "did not publish canonical OCR output"
        )

    full_text, page_map = _stitch_pages(progress_dir, start, end)

    output_path = ws.resolve("data", _OUTPUT_NAMES[model])
    page_map_path = ws.resolve("data", f"copy3_{model}_page_map.json")
    atomic_write_text(output_path, full_text)
    atomic_write_json(page_map_path, page_map)
    fallback_pages = [
        {"page": entry["page"], "provenance": entry["provenance"]}
        for entry in page_map
        if isinstance(entry.get("provenance"), dict)
        and entry["provenance"].get("kind") in {
            "provider_refusal_fallback", "explicit_recitation_fallback",
        }
    ]
    fallback_report_path = None
    if fallback_pages:
        fallback_report_path = ws.resolve("state", f"ocr_{model}_fallbacks.json")
        atomic_write_json(fallback_report_path, {
            "schema_version": 2,
            "stale_class": "ocr-provider-fallbacks",
            "book_id": cfg.book_id,
            "model_role": model,
            "source_sha256": source_sha256,
            "pages": fallback_pages,
        })
    print(f"  OCR text: {output_path.name} ({len(full_text):,} chars); "
          f"page map: {page_map_path.name} ({len(page_map)} pages)")

    return {
        "model": model,
        "pages": page_count,
        "chars": len(full_text),
        "output": str(output_path),
        "page_map": str(page_map_path),
        "fallback_pages": len(fallback_pages),
        "fallback_report": str(fallback_report_path) if fallback_report_path else None,
    }
