"""First-class restartable geometry + observation-only layout assessment step."""

from __future__ import annotations

import hashlib
import importlib.util
import re
from collections import Counter
from pathlib import Path

import fitz

from engine.config.models import ResolvedConfig
from engine.errors import (
    BackendError,
    EngineError,
    InvalidInvocationError,
    MissingInputError,
    StaleArtifactError,
)
from engine.lang.base import LanguagePlugin
from engine.paths import BookWorkspace
from engine.structure.geometry import PageGeometry, WordBox
from engine.structure.geometry_pymupdf import PyMuPDFTesseractBackend
from engine.structure.layout_assessment_shadow import (
    MODE_SHADOW,
    STATUS_AVAILABLE,
    observe_page_geometry,
)
from engine.util.jsonio import atomic_write_json, read_json

GEOMETRY_SCHEMA_VERSION = 1
GEOMETRY_STALE_CLASS = "layout-shadow-page-geometry"
REPORT_SCHEMA_VERSION = 1
REPORT_STALE_CLASS = "layout-assessment-shadow-run"
PROGRESS_FILE = "layout_shadow_progress.json"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _pinned_digest(book_dir: Path, relative_path: str) -> str:
    pins_path = book_dir / "resources.sha256"
    if not pins_path.is_file():
        raise MissingInputError(f"resource pin file not found: {pins_path}")
    matches = []
    for line in pins_path.read_text(encoding="utf-8").splitlines():
        digest, separator, name = line.partition("  ")
        if separator and name == relative_path:
            matches.append(digest)
    if len(matches) != 1 or len(matches[0]) != 64:
        raise StaleArtifactError(
            f"expected one valid SHA-256 pin for {relative_path!r}, got {matches}"
        )
    return matches[0]


def _checkpoint_path(workspace: BookWorkspace, witness_id: str, page: int) -> Path:
    return workspace.resolve(
        "data", "geometry", "shadow", witness_id, f"page_{page:04d}.json"
    )


def _checkpoint_envelope(
    *,
    source_ref: str,
    source_sha256: str,
    engine_id: str,
    backend_params: dict[str, object],
    page_geometry: PageGeometry,
    dropped_boxes: int,
    oob_boxes: int,
) -> dict:
    return {
        "schema_version": GEOMETRY_SCHEMA_VERSION,
        "stale_class": GEOMETRY_STALE_CLASS,
        "source_ref": source_ref,
        "source_sha256": source_sha256,
        "geometry_engine_id": engine_id,
        "backend_params": backend_params,
        "page": page_geometry.page,
        "dropped_boxes": dropped_boxes,
        "oob_boxes": oob_boxes,
        "geometry": {
            "width": page_geometry.width,
            "height": page_geometry.height,
            "words": [
                {"text": word.text, "bbox": list(word.bbox)}
                for word in page_geometry.words
            ],
        },
    }


def _load_checkpoint(path: Path, expected: dict[str, object]) -> tuple[PageGeometry, int, int] | None:
    if not path.is_file():
        return None
    try:
        record = read_json(path)
        if not isinstance(record, dict):
            return None
        for key, value in expected.items():
            if record.get(key) != value:
                return None
        if (
            record.get("schema_version") != GEOMETRY_SCHEMA_VERSION
            or record.get("stale_class") != GEOMETRY_STALE_CLASS
            or type(record.get("dropped_boxes")) is not int
            or type(record.get("oob_boxes")) is not int
            or not isinstance(record.get("geometry"), dict)
        ):
            return None
        geometry = record["geometry"]
        words = tuple(
            WordBox(text=item["text"], bbox=tuple(item["bbox"]))
            for item in geometry["words"]
        )
        page_geometry = PageGeometry(
            page=record["page"],
            width=geometry["width"],
            height=geometry["height"],
            words=words,
        )
        return page_geometry, record["dropped_boxes"], record["oob_boxes"]
    except (OSError, UnicodeError, ValueError, TypeError, KeyError, RecursionError):
        return None


def _write_report(
    *,
    book_id: str,
    workspace: BookWorkspace,
    witness_id: str,
    status: str,
    source: dict,
    engine_id: str,
    backend_params: dict[str, object],
    page_records: list[dict],
    available_pages: list[int],
    unavailable_pages: list[int],
    result_counts: Counter,
    failed_page: int | None = None,
    failure_type: str | None = None,
) -> Path:
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "stale_class": REPORT_STALE_CLASS,
        "status": status,
        "book_id": book_id,
        "witness_id": witness_id,
        "source": source,
        "geometry": {
            "engine_id": engine_id,
            "backend_params": backend_params,
            "page_count": len(page_records),
            "word_count": sum(item["word_count"] for item in page_records),
            "dropped_box_count": sum(item["dropped_boxes"] for item in page_records),
            "oob_box_count": sum(item["oob_boxes"] for item in page_records),
            "page_artifacts": page_records,
        },
        "assessment": {
            "mode": MODE_SHADOW,
            "column_policy": None,
            "density_evidence": None,
            "available_pages": sorted(available_pages),
            "unavailable_pages": sorted(unavailable_pages),
            "result_counts": [
                {
                    "module_id": key[0],
                    "capability": key[1],
                    "execution_status": key[2],
                    "assessment": key[3],
                    "count": count,
                }
                for key, count in sorted(result_counts.items())
            ],
        },
        "failure": (
            {"page": failed_page, "type": failure_type}
            if failed_page is not None
            else None
        ),
    }
    path = workspace.resolve("data", "layout_assessment", witness_id, "run_report.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(path, report)
    return path


def _write_progress(
    workspace: BookWorkspace,
    *,
    status: str,
    witness_id: str,
    source_sha256: str,
    engine_id: str,
    backend_params: dict[str, object],
    completed_pages: int,
    total_pages: int,
) -> None:
    atomic_write_json(workspace.resolve("state", PROGRESS_FILE), {
        "schema_version": 1,
        "status": status,
        "witness_id": witness_id,
        "source_sha256": source_sha256,
        "geometry_engine_id": engine_id,
        "backend_params": backend_params,
        "completed_pages": completed_pages,
        "total_pages": total_pages,
    })


def _validate_options(*, tesseract_language: str | None, dpi: int | None, witness_id: str) -> None:
    if not isinstance(tesseract_language, str) or not tesseract_language.strip():
        raise InvalidInvocationError(
            "layout_shadow requires --tesseract-language (for example: ita)"
        )
    if type(dpi) is not int or dpi <= 0:
        raise InvalidInvocationError("layout_shadow requires a positive --dpi")
    if not isinstance(witness_id, str) or re.fullmatch(r"[A-Za-z0-9_.-]+", witness_id) is None:
        raise InvalidInvocationError(
            "layout_shadow --witness-id must contain only letters, digits, '.', '_', or '-'"
        )


def _require_sidecar_dependency() -> None:
    if importlib.util.find_spec("book_layout_sidecar") is None:
        raise MissingInputError(
            "layout_shadow requires the optional book-layout-sidecar dependency; "
            "install it with `uv sync --extra assessment`"
        )


def run(
    *,
    workspace: BookWorkspace,
    cfg: ResolvedConfig,
    lang: LanguagePlugin,
    tesseract_language: str | None = None,
    dpi: int | None = None,
    witness_id: str = "copy1",
    refresh_geometry: bool = False,
    refresh_shadow: bool = False,
    backend_factory=PyMuPDFTesseractBackend,
    observer=observe_page_geometry,
    dependency_checker=_require_sidecar_dependency,
) -> dict:
    """Observe every scan page without changing OCR text or downstream policy."""
    _validate_options(
        tesseract_language=tesseract_language,
        dpi=dpi,
        witness_id=witness_id,
    )
    dependency_checker()
    workspace.ensure()
    book_dir = workspace.root.parent
    pdf_path = workspace.scans / cfg.manifest.scan.pdf
    if not pdf_path.is_file():
        raise MissingInputError(f"source scan PDF not found: {pdf_path}")
    source_relative = f"scans/{cfg.manifest.scan.pdf}"
    source_ref = f"scan:{cfg.book_id}/{cfg.manifest.scan.pdf}"
    actual_sha256 = _sha256_file(pdf_path)
    pinned_sha256 = _pinned_digest(book_dir, source_relative)
    if actual_sha256 != pinned_sha256:
        raise StaleArtifactError(
            f"scan SHA-256 differs from resources.sha256: {actual_sha256} != {pinned_sha256}"
        )

    try:
        with fitz.open(pdf_path) as document:
            page_count = document.page_count
            rotated = [page.number + 1 for page in document if page.rotation != 0]
    except Exception as exc:
        raise BackendError(f"could not inspect source scan PDF {pdf_path}: {exc}") from exc
    if page_count != cfg.manifest.scan.last_scan_page_default:
        raise StaleArtifactError(
            f"scan page count {page_count} != manifest {cfg.manifest.scan.last_scan_page_default}"
        )
    if rotated:
        raise BackendError(f"rotated scan pages are unsupported: {rotated}")

    backend = backend_factory(
        pdf_path, language=tesseract_language, dpi=dpi
    )
    engine_id = backend.engine_id
    backend_params = backend.backend_params
    source = {
        "ref": source_ref,
        "sha256": actual_sha256,
        "bytes": pdf_path.stat().st_size,
        "pages": page_count,
    }
    page_records: list[dict] = []
    available_pages: list[int] = []
    unavailable_pages: list[int] = []
    result_counts: Counter = Counter()
    _write_progress(
        workspace,
        status="running",
        witness_id=witness_id,
        source_sha256=actual_sha256,
        engine_id=engine_id,
        backend_params=backend_params,
        completed_pages=0,
        total_pages=page_count,
    )

    for page_number in range(1, page_count + 1):
        checkpoint = _checkpoint_path(workspace, witness_id, page_number)
        expected = {
            "source_ref": source_ref,
            "source_sha256": actual_sha256,
            "geometry_engine_id": engine_id,
            "backend_params": backend_params,
            "page": page_number,
        }
        cached = None if refresh_geometry else _load_checkpoint(checkpoint, expected)
        try:
            if cached is None:
                page_geometry = next(backend.read_pages(page_number, page_number))
                dropped = backend.dropped_boxes.get(page_number, 0)
                oob = backend.oob_boxes.get(page_number, 0)
                checkpoint.parent.mkdir(parents=True, exist_ok=True)
                atomic_write_json(
                    checkpoint,
                    _checkpoint_envelope(
                        source_ref=source_ref,
                        source_sha256=actual_sha256,
                        engine_id=engine_id,
                        backend_params=backend_params,
                        page_geometry=page_geometry,
                        dropped_boxes=dropped,
                        oob_boxes=oob,
                    ),
                )
            else:
                page_geometry, dropped, oob = cached

            observation = observer(
                workspace=workspace,
                mode=MODE_SHADOW,
                witness_id=witness_id,
                source_ref=source_ref,
                source_sha256=actual_sha256,
                page_geometry=page_geometry,
                geometry_engine_id=engine_id,
                column_policy=None,
                refresh=refresh_shadow,
            )
            if observation.status == STATUS_AVAILABLE:
                available_pages.append(page_number)
                for item in observation.bundle.results:
                    result_counts[
                        (
                            item.module_id,
                            item.capability,
                            item.execution_status,
                            item.assessment,
                        )
                    ] += 1
            else:
                unavailable_pages.append(page_number)

            page_records.append(
                {
                    "page": page_number,
                    "word_count": len(page_geometry.words),
                    "dropped_boxes": dropped,
                    "oob_boxes": oob,
                    "geometry_path": str(checkpoint.relative_to(workspace.root)),
                    "geometry_sha256": _sha256_file(checkpoint),
                    "assessment_path": (
                        str(observation.path.relative_to(workspace.root))
                        if observation.path is not None
                        else None
                    ),
                    "assessment_sha256": (
                        _sha256_file(observation.path)
                        if observation.path is not None
                        else None
                    ),
                }
            )
            _write_progress(
                workspace,
                status="running",
                witness_id=witness_id,
                source_sha256=actual_sha256,
                engine_id=engine_id,
                backend_params=backend_params,
                completed_pages=len(page_records),
                total_pages=page_count,
            )
            print(
                f"page {page_number:04d}/{page_count}: {len(page_geometry.words)} boxes, "
                f"assessment={observation.status}",
                flush=True,
            )
        except Exception as exc:
            _write_report(
                book_id=cfg.book_id,
                workspace=workspace,
                witness_id=witness_id,
                status="geometry_failed",
                source=source,
                engine_id=engine_id,
                backend_params=backend_params,
                page_records=page_records,
                available_pages=available_pages,
                unavailable_pages=unavailable_pages,
                result_counts=result_counts,
                failed_page=page_number,
                failure_type=type(exc).__name__,
            )
            _write_progress(
                workspace,
                status="failed",
                witness_id=witness_id,
                source_sha256=actual_sha256,
                engine_id=engine_id,
                backend_params=backend_params,
                completed_pages=len(page_records),
                total_pages=page_count,
            )
            if isinstance(exc, EngineError):
                raise
            raise BackendError(
                f"layout shadow failed on page {page_number}: {type(exc).__name__}: {exc}"
            ) from exc

    report_path = _write_report(
        book_id=cfg.book_id,
        workspace=workspace,
        witness_id=witness_id,
        status=("complete_with_unavailable" if unavailable_pages else "complete"),
        source=source,
        engine_id=engine_id,
        backend_params=backend_params,
        page_records=page_records,
        available_pages=available_pages,
        unavailable_pages=unavailable_pages,
        result_counts=result_counts,
    )
    _write_progress(
        workspace,
        status="complete",
        witness_id=witness_id,
        source_sha256=actual_sha256,
        engine_id=engine_id,
        backend_params=backend_params,
        completed_pages=page_count,
        total_pages=page_count,
    )
    print(f"  layout shadow report: {report_path}")
    return {
        "witness_id": witness_id,
        "pages": page_count,
        "word_boxes": sum(item["word_count"] for item in page_records),
        "available_pages": len(available_pages),
        "unavailable_pages": len(unavailable_pages),
        "report": str(report_path),
    }
