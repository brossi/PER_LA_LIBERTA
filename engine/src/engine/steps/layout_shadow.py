"""First-class restartable geometry + observation-only layout assessment step."""

from __future__ import annotations

import hashlib
import importlib.util
import json
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
from engine.structure.geometry_retry import observe_geometry_retry
from engine.structure.layout_assessment_shadow import (
    MODE_SHADOW,
    PageDensityEvidence,
    PageRasterEvidence,
    STATUS_AVAILABLE,
    observe_page_geometry,
)
from engine.structure.segmentation import (
    DensityClassifier,
    ink_fraction_from_pixmap,
    page_density_features,
)
from engine.util.jsonio import atomic_write_bytes, atomic_write_json, read_json

GEOMETRY_SCHEMA_VERSION = 1
GEOMETRY_STALE_CLASS = "layout-shadow-page-geometry"
REPORT_SCHEMA_VERSION = 3
REPORT_STALE_CLASS = "layout-assessment-shadow-run"
RASTER_SCHEMA_VERSION = 1
RASTER_STALE_CLASS = "layout-shadow-page-raster"
RASTER_PRODUCER = "engine-pymupdf-raster-v1"
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


def _raster_paths(
    workspace: BookWorkspace, witness_id: str, page: int
) -> tuple[Path, Path]:
    directory = workspace.resolve("data", "raster", "shadow", witness_id)
    stem = f"page_{page:04d}"
    return directory / f"{stem}.png", directory / f"{stem}.json"


def _raster_artifact_ref(*, source_ref: str, witness_id: str, page: int, dpi: int) -> str:
    return f"{source_ref}#page={page}:raster={witness_id}:dpi={dpi}"


def _load_raster_checkpoint(
    *,
    workspace: BookWorkspace,
    witness_id: str,
    page: int,
    source_ref: str,
    source_sha256: str,
    dpi: int,
) -> tuple[PageRasterEvidence, Path, Path] | None:
    png_path, record_path = _raster_paths(workspace, witness_id, page)
    if not png_path.is_file() or not record_path.is_file():
        return None
    try:
        record = read_json(record_path)
        expected = {
            "schema_version": RASTER_SCHEMA_VERSION,
            "stale_class": RASTER_STALE_CLASS,
            "source_ref": source_ref,
            "source_sha256": source_sha256,
            "page": page,
            "dpi": dpi,
            "producer": RASTER_PRODUCER,
            "artifact_ref": _raster_artifact_ref(
                source_ref=source_ref, witness_id=witness_id, page=page, dpi=dpi
            ),
            "source_selector": f"page={page}",
        }
        if not isinstance(record, dict) or any(record.get(key) != value for key, value in expected.items()):
            return None
        if record.get("raster_path") != str(png_path.relative_to(workspace.root)):
            return None
        actual_raster_sha256 = _sha256_file(png_path)
        if record.get("raster_sha256") != actual_raster_sha256:
            return None
        decoded = fitz.Pixmap(str(png_path))
        actual_ink_fraction = ink_fraction_from_pixmap(decoded)
        if (
            record.get("width_px") != decoded.width
            or record.get("height_px") != decoded.height
            or record.get("ink_fraction") != actual_ink_fraction
        ):
            return None
        evidence = PageRasterEvidence(
            page=page,
            artifact_ref=record["artifact_ref"],
            sha256=actual_raster_sha256,
            source_selector=record["source_selector"],
            producer=record["producer"],
            dpi=dpi,
            width_px=decoded.width,
            height_px=decoded.height,
            ink_fraction=actual_ink_fraction,
        )
        return evidence, png_path, record_path
    except (OSError, UnicodeError, ValueError, TypeError, KeyError, RecursionError):
        return None


def _capture_page_raster(
    *,
    workspace: BookWorkspace,
    backend,
    witness_id: str,
    page: int,
    source_ref: str,
    source_sha256: str,
    dpi: int,
) -> tuple[PageRasterEvidence, Path, Path]:
    pixmap = backend.render_page(page)
    png_bytes = pixmap.tobytes("png")
    raster_sha256 = hashlib.sha256(png_bytes).hexdigest()
    png_path, record_path = _raster_paths(workspace, witness_id, page)
    png_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_bytes(png_path, png_bytes)
    evidence = PageRasterEvidence(
        page=page,
        artifact_ref=_raster_artifact_ref(
            source_ref=source_ref, witness_id=witness_id, page=page, dpi=dpi
        ),
        sha256=raster_sha256,
        source_selector=f"page={page}",
        producer=RASTER_PRODUCER,
        dpi=dpi,
        width_px=pixmap.width,
        height_px=pixmap.height,
        ink_fraction=ink_fraction_from_pixmap(pixmap),
    )
    atomic_write_json(record_path, {
        "schema_version": RASTER_SCHEMA_VERSION,
        "stale_class": RASTER_STALE_CLASS,
        "source_ref": source_ref,
        "source_sha256": source_sha256,
        "page": page,
        "dpi": dpi,
        "producer": evidence.producer,
        "artifact_ref": evidence.artifact_ref,
        "source_selector": evidence.source_selector,
        "raster_path": str(png_path.relative_to(workspace.root)),
        "raster_sha256": evidence.sha256,
        "width_px": evidence.width_px,
        "height_px": evidence.height_px,
        "ink_fraction": evidence.ink_fraction,
    })
    return evidence, png_path, record_path


def _density_evidence(
    *,
    classifier: DensityClassifier | None,
    raster: PageRasterEvidence,
    geometry: PageGeometry,
    n_leaves: int,
) -> PageDensityEvidence:
    features = page_density_features(
        ink_fraction=raster.ink_fraction,
        boxes=geometry.words,
    )
    if classifier is None:
        return PageDensityEvidence(
            page=geometry.page,
            box_count=features.box_count,
            token_yield=features.token_yield,
            mean_token_length=features.mean_token_length,
            label="abstain",
            confidence=0.0,
            hint="density_policy_absent",
            producer="engine-density:density-bands-v1;policy=absent",
            policy_applied=False,
        )
    verdict = classifier.classify(
        features,
        leaf_index=geometry.page,
        n_leaves=n_leaves,
    )
    params_json = json.dumps(
        classifier.params,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return PageDensityEvidence(
        page=geometry.page,
        box_count=features.box_count,
        token_yield=features.token_yield,
        mean_token_length=features.mean_token_length,
        label=verdict.band.value,
        confidence=verdict.confidence,
        hint=verdict.signal,
        producer=(
            f"engine-density:{classifier.version};"
            f"params_sha256={hashlib.sha256(params_json.encode('utf-8')).hexdigest()}"
        ),
        policy_applied=True,
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
    density_policy: dict[str, object] | None,
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
            "effective_word_count": sum(
                item["effective_word_count"] for item in page_records
            ),
            "dropped_box_count": sum(item["dropped_boxes"] for item in page_records),
            "oob_box_count": sum(item["oob_boxes"] for item in page_records),
            "page_artifacts": page_records,
        },
        "assessment": {
            "mode": MODE_SHADOW,
            "column_policy": None,
            "density_evidence": {
                "raster_schema_version": RASTER_SCHEMA_VERSION,
                "raster_producer": RASTER_PRODUCER,
                "policy": density_policy,
                "classified_pages": sum(
                    item["density_policy_applied"] for item in page_records
                ),
                "raw_only_pages": sum(
                    not item["density_policy_applied"] for item in page_records
                ),
            },
            "geometry_retry": {
                "candidate_pages": sum(
                    item["retry_path"] is not None for item in page_records
                ),
                "attempted_pages": sum(
                    item["retry_probe_executed"] for item in page_records
                ),
                "selected_pages": sum(
                    item["retry_status"] == "selected" for item in page_records
                ),
                "unresolved_pages": sorted(
                    item["page"]
                    for item in page_records
                    if item["retry_status"] in {"unresolved", "unavailable"}
                ),
                "selection_rule": "trusted-text-likeness-v1",
                "transform": "adaptive_bw",
            },
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
    retry_observer=observe_geometry_retry,
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
    density_classifier = (
        DensityClassifier.from_config(cfg.manifest.segmentation.density_bands)
        if cfg.manifest.segmentation is not None
        else None
    )
    density_policy = (
        {
            "classifier_version": density_classifier.version,
            "params": density_classifier.params,
        }
        if density_classifier is not None
        else None
    )
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

            raster_cached = None if refresh_geometry else _load_raster_checkpoint(
                workspace=workspace,
                witness_id=witness_id,
                page=page_number,
                source_ref=source_ref,
                source_sha256=actual_sha256,
                dpi=dpi,
            )
            if raster_cached is None:
                raster, raster_path, raster_record_path = _capture_page_raster(
                    workspace=workspace,
                    backend=backend,
                    witness_id=witness_id,
                    page=page_number,
                    source_ref=source_ref,
                    source_sha256=actual_sha256,
                    dpi=dpi,
                )
            else:
                raster, raster_path, raster_record_path = raster_cached
            density = _density_evidence(
                classifier=density_classifier,
                raster=raster,
                geometry=page_geometry,
                n_leaves=page_count,
            )
            retry = retry_observer(
                workspace=workspace,
                witness_id=witness_id,
                source_ref=source_ref,
                source_sha256=actual_sha256,
                raster_path=raster_path,
                raster_evidence=raster,
                density_evidence=density,
                page_geometry=page_geometry,
                geometry_engine_id=engine_id,
                tesseract_language=tesseract_language,
                refresh=refresh_geometry,
            )
            effective_density = _density_evidence(
                classifier=density_classifier,
                raster=raster,
                geometry=retry.selected_geometry,
                n_leaves=page_count,
            )

            observation = observer(
                workspace=workspace,
                mode=MODE_SHADOW,
                witness_id=witness_id,
                source_ref=source_ref,
                source_sha256=actual_sha256,
                page_geometry=retry.selected_geometry,
                geometry_engine_id=retry.selected_geometry_engine_id,
                raster_evidence=raster,
                density_evidence=effective_density,
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
                    "effective_word_count": len(retry.selected_geometry.words),
                    "selected_geometry_engine_id": retry.selected_geometry_engine_id,
                    "dropped_boxes": dropped,
                    "oob_boxes": oob,
                    "raster_path": str(raster_path.relative_to(workspace.root)),
                    "raster_sha256": raster.sha256,
                    "raster_record_path": str(raster_record_path.relative_to(workspace.root)),
                    "raster_record_sha256": _sha256_file(raster_record_path),
                    "raster_dpi": raster.dpi,
                    "raster_width_px": raster.width_px,
                    "raster_height_px": raster.height_px,
                    "ink_fraction": raster.ink_fraction,
                    "density_label": effective_density.label,
                    "density_confidence": effective_density.confidence,
                    "density_signal": effective_density.hint,
                    "density_policy_applied": (
                        effective_density.policy_applied
                    ),
                    "retry_status": retry.status,
                    "retry_selected_path": retry.selected_path,
                    "retry_gate_reason": retry.gate_reason,
                    "retry_baseline_box_count": retry.baseline_box_count,
                    "retry_box_count": retry.retry_box_count,
                    "retry_text_verdict": retry.retry_text_verdict,
                    "retry_probe_executed": retry.probe_executed,
                    "retry_path": (
                        str(retry.path.relative_to(workspace.root))
                        if retry.path is not None
                        else None
                    ),
                    "retry_sha256": (
                        _sha256_file(retry.path) if retry.path is not None else None
                    ),
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
                density_policy=density_policy,
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
        density_policy=density_policy,
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
