"""Engine-owned, hash-bound geometry OCR retry over a persisted page raster."""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from engine.paths import BookWorkspace
from engine.structure.geometry import PageGeometry, WordBox
from engine.structure.layout_assessment_shadow import PageDensityEvidence, PageRasterEvidence
from engine.structure.segmentation import page_density_features
from engine.util.jsonio import atomic_write_json, read_json

RETRY_SCHEMA_VERSION = 1
RETRY_STALE_CLASS = "scan-conditioned-geometry-retry"
RETRY_TRANSFORM = "adaptive_bw"
RETRY_PSM = 3
SELECTION_RULE = "trusted-text-likeness-v1"

STATUS_NOT_APPLICABLE = "not_applicable"
STATUS_SELECTED = "selected"
STATUS_UNRESOLVED = "unresolved"
STATUS_UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class GeometryRetryObservation:
    page: int
    status: str
    selected_path: str
    path: Path | None
    selected_geometry: PageGeometry
    selected_geometry_engine_id: str
    gate_reason: str | None = None
    baseline_box_count: int | None = None
    retry_box_count: int | None = None
    retry_text_verdict: str | None = None
    probe_executed: bool = False
    cached: bool = False


def retry_path(workspace: BookWorkspace, *, witness_id: str, page: int) -> Path:
    return workspace.resolve(
        "data", "geometry", "retry", witness_id, f"page_{page:04d}.json"
    )


def observe_geometry_retry(
    *,
    workspace: BookWorkspace,
    witness_id: str,
    source_ref: str,
    source_sha256: str,
    raster_path: Path,
    raster_evidence: PageRasterEvidence,
    density_evidence: PageDensityEvidence,
    page_geometry: PageGeometry,
    geometry_engine_id: str,
    tesseract_language: str,
    refresh: bool = False,
) -> GeometryRetryObservation:
    """Run the bounded retry only for geometry-null/near-null pages.

    The direct raster OCR is a separately named baseline because it is not interchangeable with
    PyMuPDF's PDF OCR surface. A result is selected only when sidecar text-likeness calls it trusted;
    box count is recorded but never acts as the selection rule.
    """
    if len(page_geometry.words) > 2:
        return GeometryRetryObservation(
            page=page_geometry.page,
            status=STATUS_NOT_APPLICABLE,
            selected_path="geometry_baseline",
            path=None,
            selected_geometry=page_geometry,
            selected_geometry_engine_id=geometry_engine_id,
        )
    if raster_evidence.page != page_geometry.page or density_evidence.page != page_geometry.page:
        raise ValueError("geometry retry evidence pages must match")
    if not raster_path.is_file():
        raise ValueError(f"geometry retry raster is missing: {raster_path}")

    from book_layout_sidecar import __version__ as sidecar_version

    path = retry_path(workspace, witness_id=witness_id, page=page_geometry.page)
    expected = {
        "schema_version": RETRY_SCHEMA_VERSION,
        "stale_class": RETRY_STALE_CLASS,
        "source_ref": source_ref,
        "source_sha256": source_sha256,
        "page": page_geometry.page,
        "raster_ref": raster_evidence.artifact_ref,
        "raster_sha256": raster_evidence.sha256,
        "geometry_sha256": _geometry_sha256(page_geometry),
        "geometry_engine_id": geometry_engine_id,
        "sidecar_version": sidecar_version,
        "ocr_backend": _tesseract_producer(tesseract_language, psm=RETRY_PSM),
        "transform": RETRY_TRANSFORM,
        "tesseract_language": tesseract_language,
        "psm": RETRY_PSM,
        "selection_rule": SELECTION_RULE,
    }
    transformed_path = workspace.resolve(
        "data", "raster", "retry", witness_id,
        f"page_{page_geometry.page:04d}_{RETRY_TRANSFORM}.png",
    )
    if not refresh:
        cached = _load_current(
            path,
            expected=expected,
            page_geometry=page_geometry,
            transformed_path=transformed_path,
        )
        if cached is not None:
            return cached

    from book_layout_sidecar.adapters.image_transforms import (
        save_transformed_image,
        transform_image,
    )
    from book_layout_sidecar.adapters.tesseract_ocr import execute_tesseract_tsv
    from book_layout_sidecar.core.density import DensityFeature
    from book_layout_sidecar.core.near_blank import score_near_blank_hallucinated_boxes
    from book_layout_sidecar.core.ocr import ocr_page_sha256
    from book_layout_sidecar.core.ocr_stats import compute_ocr_page_stats
    from book_layout_sidecar.core.ocr_trust import compute_ocr_text_likeness
    from book_layout_sidecar.core.perturbation import should_run_perturbation_probe
    from PIL import Image

    baseline_execution = execute_tesseract_tsv(
        raster_path,
        page=page_geometry.page,
        lang=tesseract_language,
        psm=RETRY_PSM,
    )
    if baseline_execution.page is None:
        return _persist(
            path,
            expected,
            status=STATUS_UNAVAILABLE,
            selected_path="geometry_baseline",
            selected_geometry=page_geometry,
            gate=None,
            baseline_execution=baseline_execution.evidence.to_dict(),
            baseline_page=None,
            baseline_likeness=None,
            retry_execution=None,
            retry_page=None,
            retry_likeness=None,
        )

    baseline_page = baseline_execution.page
    baseline_stats = compute_ocr_page_stats(baseline_page)
    baseline_features = page_density_features(
        ink_fraction=raster_evidence.ink_fraction,
        boxes=baseline_page.boxes,
    )
    density = DensityFeature(
        page=page_geometry.page,
        hint=density_evidence.hint,
        ink_fraction=raster_evidence.ink_fraction,
        box_count=baseline_features.box_count,
        token_yield=baseline_features.token_yield,
        mean_token_length=baseline_features.mean_token_length,
        label=density_evidence.label,
        confidence=density_evidence.confidence,
        source_ref=raster_evidence.artifact_ref,
        source_selector=raster_evidence.source_selector,
        producer=density_evidence.producer,
    )
    baseline_score = score_near_blank_hallucinated_boxes(
        baseline_stats,
        ink_fraction=density.ink_fraction,
        density_label=density.label,
    )
    gate = should_run_perturbation_probe(
        baseline_score,
        stats=baseline_stats,
        density=density,
    )
    baseline_likeness = compute_ocr_text_likeness(baseline_page)
    if baseline_likeness.verdict == "trusted_text":
        selected = _page_geometry_from_ocr(baseline_page, page_geometry)
        return _persist(
            path,
            expected,
            status=STATUS_SELECTED,
            selected_path="raster_baseline",
            selected_geometry=selected,
            gate=gate.to_dict(),
            baseline_execution=baseline_execution.evidence.to_dict(),
            baseline_page=_ocr_page_dict(baseline_page),
            baseline_likeness=baseline_likeness.to_dict(),
            retry_execution=None,
            retry_page=None,
            retry_likeness=None,
            baseline_ocr_sha256=ocr_page_sha256(baseline_page),
        )

    if not gate.should_probe:
        return _persist(
            path,
            expected,
            status=STATUS_NOT_APPLICABLE,
            selected_path="geometry_baseline",
            selected_geometry=page_geometry,
            gate=gate.to_dict(),
            baseline_execution=baseline_execution.evidence.to_dict(),
            baseline_page=_ocr_page_dict(baseline_page),
            baseline_likeness=baseline_likeness.to_dict(),
            retry_execution=None,
            retry_page=None,
            retry_likeness=None,
            baseline_ocr_sha256=ocr_page_sha256(baseline_page),
        )

    with Image.open(raster_path) as opened:
        transformed = transform_image(opened.convert("L"), RETRY_TRANSFORM)
        try:
            save_transformed_image(transformed.image, transformed_path)
        finally:
            transformed.image.close()
    transformed_sha256 = _sha256_file(transformed_path)
    retry_execution = execute_tesseract_tsv(
        transformed_path,
        page=page_geometry.page,
        lang=tesseract_language,
        psm=RETRY_PSM,
    )
    if retry_execution.page is None:
        return _persist(
            path,
            expected,
            status=STATUS_UNAVAILABLE,
            selected_path="geometry_baseline",
            selected_geometry=page_geometry,
            gate=gate.to_dict(),
            baseline_execution=baseline_execution.evidence.to_dict(),
            baseline_page=_ocr_page_dict(baseline_page),
            baseline_likeness=baseline_likeness.to_dict(),
            retry_execution=retry_execution.evidence.to_dict(),
            retry_page=None,
            retry_likeness=None,
            baseline_ocr_sha256=ocr_page_sha256(baseline_page),
            transformed_sha256=transformed_sha256,
        )

    retry_page = retry_execution.page
    retry_likeness = compute_ocr_text_likeness(retry_page)
    if retry_likeness.verdict == "trusted_text":
        status = STATUS_SELECTED
        selected_path = RETRY_TRANSFORM
        selected_geometry = _page_geometry_from_ocr(retry_page, page_geometry)
    else:
        status = STATUS_UNRESOLVED
        selected_path = "geometry_baseline"
        selected_geometry = page_geometry
    return _persist(
        path,
        expected,
        status=status,
        selected_path=selected_path,
        selected_geometry=selected_geometry,
        gate=gate.to_dict(),
        baseline_execution=baseline_execution.evidence.to_dict(),
        baseline_page=_ocr_page_dict(baseline_page),
        baseline_likeness=baseline_likeness.to_dict(),
        retry_execution=retry_execution.evidence.to_dict(),
        retry_page=_ocr_page_dict(retry_page),
        retry_likeness=retry_likeness.to_dict(),
        baseline_ocr_sha256=ocr_page_sha256(baseline_page),
        retry_ocr_sha256=ocr_page_sha256(retry_page),
        transformed_sha256=transformed_sha256,
    )


def _persist(
    path: Path,
    expected: dict[str, Any],
    *,
    status: str,
    selected_path: str,
    selected_geometry: PageGeometry,
    gate: dict[str, Any] | None,
    baseline_execution: dict[str, Any],
    baseline_page: dict[str, Any] | None,
    baseline_likeness: dict[str, Any] | None,
    retry_execution: dict[str, Any] | None,
    retry_page: dict[str, Any] | None,
    retry_likeness: dict[str, Any] | None,
    baseline_ocr_sha256: str | None = None,
    retry_ocr_sha256: str | None = None,
    transformed_sha256: str | None = None,
) -> GeometryRetryObservation:
    if selected_path == "geometry_baseline":
        selected_geometry_engine_id = expected["geometry_engine_id"]
    elif selected_path == "raster_baseline":
        selected_geometry_engine_id = baseline_execution["producer"]
    else:
        if retry_execution is None:
            raise ValueError("retry-selected geometry requires retry execution provenance")
        selected_geometry_engine_id = retry_execution["producer"]
    record = {
        **expected,
        "status": status,
        "selected_path": selected_path,
        "gate": gate,
        "baseline_execution": baseline_execution,
        "baseline_page": baseline_page,
        "baseline_likeness": baseline_likeness,
        "baseline_ocr_sha256": baseline_ocr_sha256,
        "retry_execution": retry_execution,
        "retry_page": retry_page,
        "retry_likeness": retry_likeness,
        "retry_ocr_sha256": retry_ocr_sha256,
        "transformed_raster_sha256": transformed_sha256,
        "selected_geometry": _geometry_dict(selected_geometry),
        "selected_geometry_engine_id": selected_geometry_engine_id,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(path, record)
    return _observation(path, record, cached=False)


def _load_current(
    path: Path,
    *,
    expected: dict[str, Any],
    page_geometry: PageGeometry,
    transformed_path: Path,
) -> GeometryRetryObservation | None:
    if not path.is_file():
        return None
    try:
        record = read_json(path)
        if not isinstance(record, dict) or any(record.get(k) != v for k, v in expected.items()):
            return None
        transformed_sha256 = record.get("transformed_raster_sha256")
        if transformed_sha256 is not None and (
            not transformed_path.is_file()
            or _sha256_file(transformed_path) != transformed_sha256
        ):
            return None
        if not _stored_ocr_hash_is_current(record, "baseline"):
            return None
        if not _stored_ocr_hash_is_current(record, "retry"):
            return None
        observation = _observation(path, record, cached=True)
        if observation.page != page_geometry.page:
            return None
        return observation
    except (OSError, UnicodeError, ValueError, TypeError, KeyError, RecursionError):
        return None


def _observation(path: Path, record: dict[str, Any], *, cached: bool) -> GeometryRetryObservation:
    geometry = _geometry_from_dict(record["page"], record["selected_geometry"])
    baseline_page = record.get("baseline_page") or {}
    retry_page = record.get("retry_page") or {}
    retry_likeness = record.get("retry_likeness") or {}
    retry_execution = record.get("retry_execution")
    gate = record.get("gate") or {}
    return GeometryRetryObservation(
        page=record["page"],
        status=record["status"],
        selected_path=record["selected_path"],
        path=path,
        selected_geometry=geometry,
        selected_geometry_engine_id=record["selected_geometry_engine_id"],
        gate_reason=gate.get("reason"),
        baseline_box_count=(len(baseline_page.get("boxes", [])) if baseline_page else None),
        retry_box_count=(len(retry_page.get("boxes", [])) if retry_page else None),
        retry_text_verdict=retry_likeness.get("verdict"),
        probe_executed=isinstance(retry_execution, dict),
        cached=cached,
    )


def _page_geometry_from_ocr(ocr_page, reference: PageGeometry) -> PageGeometry:
    sx = reference.width / ocr_page.width
    sy = reference.height / ocr_page.height
    words = tuple(
        WordBox(
            text=box.text,
            bbox=(
                box.bbox.x0 * sx,
                box.bbox.y0 * sy,
                box.bbox.x1 * sx,
                box.bbox.y1 * sy,
            ),
        )
        for box in ocr_page.boxes
    )
    return PageGeometry(
        page=reference.page,
        width=reference.width,
        height=reference.height,
        words=words,
    )


def _ocr_page_dict(page) -> dict[str, Any]:
    """Serialize sidecar OCR evidence without depending on an adapter wire format."""
    return {
        "page": page.page,
        "width": page.width,
        "height": page.height,
        "source_format": page.source_format,
        "source_ref": page.source_ref,
        "source_selector": page.source_selector,
        "producer": page.producer,
        "boxes": [
            {
                "page": box.page,
                "text": box.text,
                "bbox": {
                    "x0": box.bbox.x0,
                    "y0": box.bbox.y0,
                    "x1": box.bbox.x1,
                    "y1": box.bbox.y1,
                },
                "confidence": box.confidence,
                "source_format": box.source_format,
                "source_ref": box.source_ref,
                "source_selector": box.source_selector,
            }
            for box in page.boxes
        ],
    }


def _stored_ocr_hash_is_current(record: dict[str, Any], prefix: str) -> bool:
    page = record.get(f"{prefix}_page")
    digest = record.get(f"{prefix}_ocr_sha256")
    if page is None:
        return digest is None
    if not isinstance(page, dict) or not isinstance(digest, str):
        return False
    try:
        payload = {
            "page": page["page"],
            "width": page["width"],
            "height": page["height"],
            "source_format": page["source_format"],
            "producer": page.get("producer"),
            "boxes": [
                {
                    "text": box["text"],
                    "bbox": [
                        box["bbox"]["x0"],
                        box["bbox"]["y0"],
                        box["bbox"]["x1"],
                        box["bbox"]["y1"],
                    ],
                    "confidence": box.get("confidence"),
                }
                for box in page["boxes"]
            ],
        }
        encoded = json.dumps(
            payload,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (KeyError, TypeError, ValueError):
        return False
    return hashlib.sha256(encoded).hexdigest() == digest


def _tesseract_producer(lang: str, *, psm: int) -> str:
    resolved = shutil.which("tesseract")
    candidate = Path(resolved) if resolved is not None else Path("tesseract")
    if candidate.is_file():
        identity = f"{candidate.name}@sha256={_sha256_file(candidate)}"
    else:
        identity = "tesseract@unresolved"
    return f"{identity}:lang={lang}:psm={psm}:format=tsv"
def _geometry_dict(geometry: PageGeometry) -> dict[str, Any]:
    return {
        "width": geometry.width,
        "height": geometry.height,
        "words": [{"text": word.text, "bbox": list(word.bbox)} for word in geometry.words],
    }


def _geometry_from_dict(page: int, raw: dict[str, Any]) -> PageGeometry:
    return PageGeometry(
        page=page,
        width=raw["width"],
        height=raw["height"],
        words=tuple(
            WordBox(text=item["text"], bbox=tuple(item["bbox"]))
            for item in raw["words"]
        ),
    )


def _geometry_sha256(geometry: PageGeometry) -> str:
    payload = json.dumps(
        _geometry_dict(geometry),
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
