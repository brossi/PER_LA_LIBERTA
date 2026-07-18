"""Observation-only bridge to the optional ``book-layout-sidecar`` provider.

The engine owns mode selection, translation from validated engine geometry, persistence, and every
downstream effect.  The provider receives one source-bound page request and returns evidence only.
This module deliberately imports the optional package lazily, does not use its adapters or lab
surface, and has no route into geometry, worklists, or structure-map mutation.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from engine.paths import BookWorkspace
from engine.structure.geometry import PageGeometry
from engine.util.jsonio import atomic_write_json, read_json

MODE_OFF = "off"
MODE_SHADOW = "shadow"
MODES = (MODE_OFF, MODE_SHADOW)

STATUS_OFF = "off"
STATUS_AVAILABLE = "available"
STATUS_UNAVAILABLE = "unavailable"

OBSERVATION_SCHEMA_VERSION = 1
OBSERVATION_STALE_CLASS = "layout-assessment-shadow"
ADAPTER_ID = "engine-page-geometry"
ADAPTER_VERSION = 2

_WITNESS_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_OBSERVATION_KEYS = frozenset(
    {
        "schema_version",
        "stale_class",
        "adapter_id",
        "adapter_version",
        "mode",
        "witness_id",
        "page",
        "status",
        "provider",
        "request_sha256",
        "bundle_sha256",
        "request",
        "bundle",
        "failure",
    }
)


@dataclass(frozen=True, slots=True)
class ColumnAssessmentPolicy:
    """An already-ratified engine column policy; no thresholds are guessed by the adapter."""

    decision_threshold: float
    hysteresis_margin: float


@dataclass(frozen=True, slots=True)
class PageRasterEvidence:
    """Hash-bound rendered page pixels and their raw, policy-free ink measurement."""

    page: int
    artifact_ref: str
    sha256: str
    source_selector: str
    producer: str
    dpi: int
    width_px: int
    height_px: int
    ink_fraction: float

    def __post_init__(self) -> None:
        if type(self.page) is not int or self.page < 1:
            raise ValueError("raster evidence page must be a positive integer")
        if not self.artifact_ref or not self.source_selector or not self.producer:
            raise ValueError("raster evidence references and producer must be non-empty")
        if _SHA256.fullmatch(self.sha256) is None:
            raise ValueError("raster evidence sha256 must be a bare lowercase SHA-256")
        if type(self.dpi) is not int or self.dpi < 1:
            raise ValueError("raster evidence dpi must be a positive integer")
        if type(self.width_px) is not int or self.width_px < 1:
            raise ValueError("raster evidence width_px must be a positive integer")
        if type(self.height_px) is not int or self.height_px < 1:
            raise ValueError("raster evidence height_px must be a positive integer")
        if not (math.isfinite(self.ink_fraction) and 0.0 <= self.ink_fraction <= 1.0):
            raise ValueError("raster evidence ink_fraction must be in [0, 1]")


@dataclass(frozen=True, slots=True)
class PageDensityEvidence:
    """Engine-classified density evidence produced only by an explicit calibrated policy."""

    page: int
    box_count: int
    token_yield: float
    mean_token_length: float
    label: str
    confidence: float
    hint: str
    producer: str
    policy_applied: bool = False

    def __post_init__(self) -> None:
        if type(self.page) is not int or self.page < 1:
            raise ValueError("density evidence page must be a positive integer")
        if type(self.box_count) is not int or self.box_count < 0:
            raise ValueError("density evidence box_count must be a non-negative integer")
        if not (math.isfinite(self.token_yield) and 0.0 <= self.token_yield <= 1.0):
            raise ValueError("density evidence token_yield must be in [0, 1]")
        if not (math.isfinite(self.mean_token_length) and self.mean_token_length >= 0.0):
            raise ValueError("density evidence mean_token_length must be non-negative")
        if not self.label or not self.hint or not self.producer:
            raise ValueError("density evidence label, hint, and producer must be non-empty")
        if type(self.policy_applied) is not bool:
            raise ValueError("density evidence policy_applied must be boolean")
        if not (math.isfinite(self.confidence) and 0.0 <= self.confidence <= 1.0):
            raise ValueError("density evidence confidence must be in [0, 1]")


@dataclass(frozen=True, slots=True)
class LayoutAssessmentObservation:
    """Engine-owned result of one off/shadow attempt."""

    status: str
    page: int
    path: Path | None
    cached: bool = False
    bundle: Any | None = None
    failure_code: str | None = None
    failure_message: str | None = None


def observation_path(
    workspace: BookWorkspace, *, witness_id: str, page: int
) -> Path:
    _validate_witness_id(witness_id)
    if type(page) is not int or page < 1:
        raise ValueError(f"assessment page must be a positive integer, got {page!r}")
    return workspace.resolve(
        "data", "layout_assessment", witness_id, f"page_{page:04d}.json"
    )


def observe_page_geometry(
    *,
    workspace: BookWorkspace,
    mode: str,
    witness_id: str,
    source_ref: str,
    source_sha256: str,
    page_geometry: PageGeometry,
    geometry_engine_id: str,
    raster_evidence: PageRasterEvidence | None = None,
    density_evidence: PageDensityEvidence | None = None,
    column_policy: ColumnAssessmentPolicy | None = None,
    provider_factory: Callable[[], Any] | None = None,
    refresh: bool = False,
) -> LayoutAssessmentObservation:
    """Assess one validated geometry page without admitting any pipeline effect.

    ``off`` returns before loading the optional package, constructing a provider, or creating an
    artifact.  ``shadow`` persists the exact request and validated bundle.  Provider/import/
    response failures become explicit unavailable observations; engine-owned persistence failures
    still raise.
    """
    if mode not in MODES:
        raise ValueError(f"layout assessment mode must be one of {MODES}, got {mode!r}")
    if mode == MODE_OFF:
        return LayoutAssessmentObservation(status=STATUS_OFF, page=page_geometry.page, path=None)

    _validate_witness_id(witness_id)
    _validate_source(source_ref, source_sha256, geometry_engine_id)
    path = observation_path(workspace, witness_id=witness_id, page=page_geometry.page)

    try:
        api = _load_sidecar_api()
        request = _build_request(
            api=api,
            workspace=workspace,
            witness_id=witness_id,
            source_ref=source_ref,
            source_sha256=source_sha256,
            page_geometry=page_geometry,
            geometry_engine_id=geometry_engine_id,
            raster_evidence=raster_evidence,
            density_evidence=density_evidence,
            column_policy=column_policy,
        )
        provider = (
            provider_factory() if provider_factory is not None else api["CoreAssessmentProvider"]()
        )
        provider_identity = provider.identity
    except Exception as exc:
        return _persist_unavailable(
            path=path,
            witness_id=witness_id,
            page=page_geometry.page,
            request=None,
            provider=None,
            code="provider_unavailable",
            exc=exc,
        )

    if not refresh:
        cached_bundle = _load_current_bundle(
            path=path,
            request=request,
            expected_provider=provider_identity,
            api=api,
            witness_id=witness_id,
            page=page_geometry.page,
        )
        if cached_bundle is not None:
            return LayoutAssessmentObservation(
                status=STATUS_AVAILABLE,
                page=page_geometry.page,
                path=path,
                cached=True,
                bundle=cached_bundle,
            )

    try:
        bundle = provider.assess(request)
        api["validate_assessment_response"](
            request, bundle, expected_provider=provider_identity
        )
    except Exception as exc:
        return _persist_unavailable(
            path=path,
            witness_id=witness_id,
            page=page_geometry.page,
            request=request,
            provider=provider_identity,
            code="provider_error",
            exc=exc,
        )

    request_json = api["assessment_request_json"](request)
    bundle_json = api["assessment_bundle_json"](bundle)
    envelope = _envelope(
        witness_id=witness_id,
        page=page_geometry.page,
        status=STATUS_AVAILABLE,
        provider=provider_identity.to_dict(),
        request=request.to_dict(),
        request_sha256=_text_sha256(request_json),
        bundle=bundle.to_dict(),
        bundle_sha256=_text_sha256(bundle_json),
        failure=None,
    )
    _write_observation(path, envelope)
    return LayoutAssessmentObservation(
        status=STATUS_AVAILABLE,
        page=page_geometry.page,
        path=path,
        bundle=bundle,
    )


def _load_sidecar_api() -> dict[str, Any]:
    # Supported release surface only.  Keeping imports here makes MODE_OFF a true optional no-op.
    from book_layout_sidecar.core import (
        AssessmentEvidence,
        AssessmentInputArtifact,
        AssessmentSubject,
        BoundingBox,
        CoreAssessmentProvider,
        OcrBox,
        OcrPage,
        assessment_bundle_from_dict,
        assessment_bundle_json,
        assessment_request_from_dict,
        assessment_request_json,
        build_assessment_request,
        validate_assessment_response,
    )
    from book_layout_sidecar.core.assessment import (
        CAPABILITY_COLUMN_EVIDENCE_IS_STABLE,
        CAPABILITY_OCR_BOXES_ARE_TEXT_LIKE,
        CAPABILITY_PAGE_CONTAINS_OCR_RELEVANT_CONTENT,
    )
    from book_layout_sidecar.core.columns import compute_column_feature
    from book_layout_sidecar.core.density import DensityFeature
    from book_layout_sidecar.core.modules import (
        INPUT_KIND_DENSITY_FEATURES,
        INPUT_KIND_OCR_BOXES,
        INPUT_KIND_SOURCE_RASTER,
    )
    from book_layout_sidecar.core.near_blank import score_near_blank_hallucinated_boxes
    from book_layout_sidecar.core.ocr import ocr_page_sha256
    from book_layout_sidecar.core.ocr_stats import compute_ocr_page_stats
    from book_layout_sidecar.core.ocr_trust import compute_ocr_text_likeness_from_stats

    return {
        "AssessmentEvidence": AssessmentEvidence,
        "AssessmentInputArtifact": AssessmentInputArtifact,
        "AssessmentSubject": AssessmentSubject,
        "BoundingBox": BoundingBox,
        "CoreAssessmentProvider": CoreAssessmentProvider,
        "OcrBox": OcrBox,
        "OcrPage": OcrPage,
        "assessment_bundle_from_dict": assessment_bundle_from_dict,
        "assessment_bundle_json": assessment_bundle_json,
        "assessment_request_from_dict": assessment_request_from_dict,
        "assessment_request_json": assessment_request_json,
        "build_assessment_request": build_assessment_request,
        "validate_assessment_response": validate_assessment_response,
        "CAPABILITY_COLUMN_EVIDENCE_IS_STABLE": CAPABILITY_COLUMN_EVIDENCE_IS_STABLE,
        "CAPABILITY_OCR_BOXES_ARE_TEXT_LIKE": CAPABILITY_OCR_BOXES_ARE_TEXT_LIKE,
        "CAPABILITY_PAGE_CONTAINS_OCR_RELEVANT_CONTENT": (
            CAPABILITY_PAGE_CONTAINS_OCR_RELEVANT_CONTENT
        ),
        "compute_column_feature": compute_column_feature,
        "DensityFeature": DensityFeature,
        "INPUT_KIND_DENSITY_FEATURES": INPUT_KIND_DENSITY_FEATURES,
        "INPUT_KIND_OCR_BOXES": INPUT_KIND_OCR_BOXES,
        "INPUT_KIND_SOURCE_RASTER": INPUT_KIND_SOURCE_RASTER,
        "score_near_blank_hallucinated_boxes": score_near_blank_hallucinated_boxes,
        "ocr_page_sha256": ocr_page_sha256,
        "compute_ocr_page_stats": compute_ocr_page_stats,
        "compute_ocr_text_likeness_from_stats": compute_ocr_text_likeness_from_stats,
    }


def _build_request(
    *,
    api: dict[str, Any],
    workspace: BookWorkspace,
    witness_id: str,
    source_ref: str,
    source_sha256: str,
    page_geometry: PageGeometry,
    geometry_engine_id: str,
    raster_evidence: PageRasterEvidence | None,
    density_evidence: PageDensityEvidence | None,
    column_policy: ColumnAssessmentPolicy | None,
) -> Any:
    artifact_ref = f"{source_ref}#page={page_geometry.page}:ocr-boxes={witness_id}"
    selector = f"page={page_geometry.page}"
    boxes = tuple(
        api["OcrBox"](
            page=page_geometry.page,
            text=word.text,
            bbox=api["BoundingBox"](*word.bbox),
            confidence=None,
            source_format=ADAPTER_ID,
            source_ref=artifact_ref,
            source_selector=f"{selector}:word={index}",
        )
        for index, word in enumerate(page_geometry.words)
    )
    ocr_page = api["OcrPage"](
        page=page_geometry.page,
        width=page_geometry.width,
        height=page_geometry.height,
        boxes=boxes,
        source_format=ADAPTER_ID,
        source_ref=artifact_ref,
        source_selector=selector,
        producer=f"{geometry_engine_id};adapter={ADAPTER_ID}@{ADAPTER_VERSION}",
    )
    stats = api["compute_ocr_page_stats"](ocr_page)
    if raster_evidence is not None and raster_evidence.page != page_geometry.page:
        raise ValueError("raster evidence page differs from geometry page")
    if density_evidence is not None:
        if raster_evidence is None:
            raise ValueError("classified density evidence requires its source raster evidence")
        if density_evidence.page != page_geometry.page:
            raise ValueError("density evidence page differs from geometry page")
        if density_evidence.box_count != stats.box_count:
            raise ValueError("density evidence box_count differs from normalized OCR stats")

    density = None
    if density_evidence is not None:
        density = api["DensityFeature"](
            page=density_evidence.page,
            hint=density_evidence.hint,
            ink_fraction=raster_evidence.ink_fraction,
            box_count=density_evidence.box_count,
            token_yield=density_evidence.token_yield,
            mean_token_length=density_evidence.mean_token_length,
            label=density_evidence.label,
            confidence=density_evidence.confidence,
            source_ref=raster_evidence.artifact_ref,
            source_selector=raster_evidence.source_selector,
            producer=(
                f"{density_evidence.producer};"
                f"source_raster_sha256={raster_evidence.sha256}"
            ),
        )
    near_blank = api["score_near_blank_hallucinated_boxes"](
        stats,
        ink_fraction=density.ink_fraction if density is not None else None,
        density_label=density.label if density is not None else None,
    )
    text_likeness = api["compute_ocr_text_likeness_from_stats"](
        page=ocr_page, stats=stats
    )
    column_feature = None
    capabilities = [
        api["CAPABILITY_PAGE_CONTAINS_OCR_RELEVANT_CONTENT"],
        api["CAPABILITY_OCR_BOXES_ARE_TEXT_LIKE"],
    ]
    if column_policy is not None:
        column_feature = api["compute_column_feature"](
            ocr_page,
            decision_threshold=column_policy.decision_threshold,
            hysteresis_margin=column_policy.hysteresis_margin,
        )
        capabilities.append(api["CAPABILITY_COLUMN_EVIDENCE_IS_STABLE"])

    ocr_artifact = api["AssessmentInputArtifact"](
        kind=api["INPUT_KIND_OCR_BOXES"],
        ref=artifact_ref,
        sha256=api["ocr_page_sha256"](ocr_page),
        version=None,
    )
    artifacts = [ocr_artifact]
    if raster_evidence is not None:
        artifacts.append(api["AssessmentInputArtifact"](
            kind=api["INPUT_KIND_SOURCE_RASTER"],
            ref=raster_evidence.artifact_ref,
            sha256=raster_evidence.sha256,
            version=None,
        ))
    density_artifact = None
    if density is not None:
        density_ref = f"{raster_evidence.artifact_ref}:density"
        density_artifact = api["AssessmentInputArtifact"](
            kind=api["INPUT_KIND_DENSITY_FEATURES"],
            ref=density_ref,
            sha256=_dict_sha256(density.to_dict()),
            version=None,
        )
        artifacts.append(density_artifact)

    refs_by_evidence = {
        "stats": (artifact_ref,),
        "near_blank_score": (
            (artifact_ref, density_artifact.ref)
            if density_artifact is not None
            else (artifact_ref,)
        ),
        "ocr_text_likeness": (artifact_ref,),
    }
    if column_feature is not None:
        refs_by_evidence["column_feature"] = (artifact_ref,)
    if density_artifact is not None:
        refs_by_evidence["density"] = (density_artifact.ref,)
    evidence = api["AssessmentEvidence"](
        subject=api["AssessmentSubject"](
            book_id=workspace.book_id,
            source_ref=source_ref,
            source_sha256=source_sha256,
            page=page_geometry.page,
        ),
        input_artifacts=tuple(artifacts),
        stats=stats,
        near_blank_score=near_blank,
        density=density,
        ocr_text_likeness=text_likeness,
        column_feature=column_feature,
        artifact_refs_by_evidence=refs_by_evidence,
    )
    return api["build_assessment_request"](
        evidence=evidence, capabilities=tuple(capabilities)
    )


def _load_current_bundle(
    *,
    path: Path,
    request: Any,
    expected_provider: Any,
    api: dict[str, Any],
    witness_id: str,
    page: int,
) -> Any | None:
    if not path.is_file():
        return None
    try:
        envelope = read_json(path)
        if not isinstance(envelope, dict) or set(envelope) != _OBSERVATION_KEYS:
            return None
        if (
            type(envelope["schema_version"]) is not int
            or envelope["schema_version"] != OBSERVATION_SCHEMA_VERSION
            or envelope["stale_class"] != OBSERVATION_STALE_CLASS
            or envelope["adapter_id"] != ADAPTER_ID
            or envelope["adapter_version"] != ADAPTER_VERSION
            or envelope["mode"] != MODE_SHADOW
            or envelope["witness_id"] != witness_id
            or type(envelope["page"]) is not int
            or envelope["page"] != page
            or envelope["status"] != STATUS_AVAILABLE
            or envelope["failure"] is not None
            or envelope["provider"] != expected_provider.to_dict()
        ):
            return None
        stored_request = api["assessment_request_from_dict"](envelope["request"])
        stored_request_json = api["assessment_request_json"](stored_request)
        if envelope["request_sha256"] != _text_sha256(stored_request_json):
            return None
        if stored_request_json != api["assessment_request_json"](request):
            return None
        stored_bundle = api["assessment_bundle_from_dict"](envelope["bundle"])
        stored_bundle_json = api["assessment_bundle_json"](stored_bundle)
        if envelope["bundle_sha256"] != _text_sha256(stored_bundle_json):
            return None
        api["validate_assessment_response"](
            stored_request, stored_bundle, expected_provider=expected_provider
        )
        return stored_bundle
    except (OSError, UnicodeError, ValueError, TypeError, KeyError, RecursionError):
        return None


def _persist_unavailable(
    *,
    path: Path,
    witness_id: str,
    page: int,
    request: Any | None,
    provider: Any | None,
    code: str,
    exc: Exception,
) -> LayoutAssessmentObservation:
    request_dict = request.to_dict() if request is not None else None
    request_hash = None
    if request is not None:
        try:
            api = _load_sidecar_api()
            request_hash = _text_sha256(api["assessment_request_json"](request))
        except Exception:
            request_hash = None
    message = str(exc) or type(exc).__name__
    envelope = _envelope(
        witness_id=witness_id,
        page=page,
        status=STATUS_UNAVAILABLE,
        provider=provider.to_dict() if provider is not None else None,
        request=request_dict,
        request_sha256=request_hash,
        bundle=None,
        bundle_sha256=None,
        failure={"code": code, "type": type(exc).__name__, "message": message},
    )
    _write_observation(path, envelope)
    return LayoutAssessmentObservation(
        status=STATUS_UNAVAILABLE,
        page=page,
        path=path,
        failure_code=code,
        failure_message=message,
    )


def _envelope(**values: Any) -> dict[str, Any]:
    return {
        "schema_version": OBSERVATION_SCHEMA_VERSION,
        "stale_class": OBSERVATION_STALE_CLASS,
        "adapter_id": ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "mode": MODE_SHADOW,
        **values,
    }


def _write_observation(path: Path, envelope: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(path, envelope)


def _validate_witness_id(witness_id: str) -> None:
    if not isinstance(witness_id, str) or _WITNESS_ID.fullmatch(witness_id) is None:
        raise ValueError(
            f"witness_id must be a flat identifier matching {_WITNESS_ID.pattern!r}, "
            f"got {witness_id!r}"
        )


def _validate_source(source_ref: str, source_sha256: str, geometry_engine_id: str) -> None:
    if not isinstance(source_ref, str) or not source_ref.strip():
        raise ValueError("source_ref must be a non-empty logical reference")
    if not isinstance(source_sha256, str) or _SHA256.fullmatch(source_sha256) is None:
        raise ValueError("source_sha256 must be a bare lowercase SHA-256 digest")
    if not isinstance(geometry_engine_id, str) or not geometry_engine_id.strip():
        raise ValueError("geometry_engine_id must be non-empty")


def _text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _dict_sha256(value: dict[str, Any]) -> str:
    import json

    canonical = json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))
    return _text_sha256(canonical)
