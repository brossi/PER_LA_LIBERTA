"""Observation-only consumer for sidecar geometry/OCR presence assessments.

The page-evidence ledger is the first engine artifact that contains both finalized effective
geometry and canonical OCR-text presence.  This boundary consumes that ledger only after it has
been written.  Its artifacts are deliberately outside the admission ledger and cannot change page
dispositions, review routing, or reconciliation admission.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

from engine.paths import BookWorkspace
from engine.util.jsonio import atomic_write_json, read_json

SHADOW_SCHEMA_VERSION = 2
SHADOW_STALE_CLASS = "page-evidence-presence-shadow"
SHADOW_MODE = "shadow"

STATUS_AVAILABLE = "available"
STATUS_UNAVAILABLE = "unavailable"

FAILURE_OBSERVATION_STARTED = "observation_started"
FAILURE_ENGINE_ERROR = "engine_error"

_PAGE_KEYS = frozenset(
    {
        "schema_version",
        "stale_class",
        "mode",
        "book_id",
        "witness_id",
        "page",
        "status",
        "provider",
        "ledger",
        "projection",
        "request_sha256",
        "bundle_sha256",
        "request",
        "bundle",
        "failure",
    }
)

_REPORT_KEYS = frozenset(
    {
        "schema_version",
        "stale_class",
        "mode",
        "book_id",
        "witness_id",
        "status",
        "provider",
        "ledger",
        "projection",
        "pages",
        "cached_pages",
        "counts",
        "contradiction_pages",
        "unavailable_pages",
        "observations",
        "observations_sha256",
        "failure",
    }
)

_PRESENCE_SIGNAL_KEYS = (
    "baseline_geometry_boxes",
    "effective_geometry_boxes",
    "ocr_has_text",
    "ocr_fallback",
    "retry_status",
    "retry_selected_path",
)
_RETRY_STATUSES = frozenset({"not_applicable", "selected", "unresolved", "unavailable"})
_RETRY_SELECTED_PATHS = frozenset({"geometry_baseline", "raster_baseline", "adaptive_bw"})
_RECOVERY_SELECTED_PATHS = frozenset({"raster_baseline", "adaptive_bw"})


def page_observation_path(
    workspace: BookWorkspace, *, witness_id: str, page: int
) -> Path:
    return workspace.resolve(
        "data",
        "layout_assessment",
        witness_id,
        "page_evidence_presence",
        f"page_{page:04d}.json",
    )


def report_path(workspace: BookWorkspace, *, witness_id: str) -> Path:
    return workspace.resolve(
        "data",
        "layout_assessment",
        witness_id,
        "page_evidence_presence_report.json",
    )


def projection_path(workspace: BookWorkspace, *, witness_id: str) -> Path:
    return workspace.resolve(
        "data",
        "layout_assessment",
        witness_id,
        "page_evidence_presence_projection.json",
    )


def observe_page_evidence_presence(
    *,
    workspace: BookWorkspace,
    ledger_path: Path,
    book_id: str,
    witness_id: str,
    provider_factory: Callable[[], Any] | None = None,
    refresh: bool = False,
) -> dict[str, Any]:
    """Assess every ledger page while retaining a strict observational boundary."""

    begin_presence_observation(
        workspace=workspace,
        book_id=book_id,
        witness_id=witness_id,
    )
    try:
        return _observe_page_evidence_presence(
            workspace=workspace,
            ledger_path=ledger_path,
            book_id=book_id,
            witness_id=witness_id,
            provider_factory=provider_factory,
            refresh=refresh,
        )
    except Exception as exc:
        record_presence_unavailable(
            workspace=workspace,
            book_id=book_id,
            witness_id=witness_id,
            ledger_path=ledger_path,
            failure=exc,
        )
        raise


def _observe_page_evidence_presence(
    *,
    workspace: BookWorkspace,
    ledger_path: Path,
    book_id: str,
    witness_id: str,
    provider_factory: Callable[[], Any] | None,
    refresh: bool,
) -> dict[str, Any]:
    """Run one observation after the durable unavailable sentinel has been installed."""

    ledger_bytes = ledger_path.read_bytes()
    ledger_sha256 = hashlib.sha256(ledger_bytes).hexdigest()
    ledger = json.loads(ledger_bytes)
    if ledger.get("book_id") != book_id:
        raise ValueError("page-evidence ledger book differs from the requested book")
    if ledger.get("witness_id") != witness_id:
        raise ValueError("page-evidence ledger witness differs from the requested witness")
    source = ledger.get("source")
    if not isinstance(source, dict):
        raise ValueError("page-evidence ledger source must be an object")
    source_sha256 = _required_text(source.get("sha256"), name="ledger source sha256")
    source_path = _required_text(source.get("path"), name="ledger source path")
    source_ref = f"scan:{book_id}/{Path(source_path).name}"
    page_count = source.get("pages")
    if type(page_count) is not int or page_count < 1:
        raise ValueError("page-evidence ledger source pages must be a positive integer")

    artifact_ref = f"page-evidence:{book_id}/{witness_id}"
    ledger_binding = {
        "ref": artifact_ref,
        "path": str(ledger_path.relative_to(workspace.root)),
        "sha256": ledger_sha256,
    }
    _write_unavailable_report(
        workspace=workspace,
        book_id=book_id,
        witness_id=witness_id,
        ledger=ledger_binding,
        projection=None,
        failure={
            "code": FAILURE_OBSERVATION_STARTED,
            "type": None,
            "message": "page-evidence presence observation has not completed",
        },
    )
    projection_document = _presence_projection(ledger)
    projection_file = projection_path(workspace, witness_id=witness_id)
    projection_file.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(projection_file, projection_document)
    projection_bytes = projection_file.read_bytes()
    projection_ref = f"page-evidence-presence:{book_id}/{witness_id}"
    projection_binding = {
        "ref": projection_ref,
        "path": str(projection_file.relative_to(workspace.root)),
        "sha256": hashlib.sha256(projection_bytes).hexdigest(),
    }
    api = _load_sidecar_api()
    features = _presence_features(
        projection_document,
        projection_ref=projection_ref,
        constructor=api["compute_effective_geometry_ocr_text_presence"],
    )
    if [feature.page for feature in features] != list(range(1, page_count + 1)):
        raise ValueError("page-evidence presence adapter did not return the total ordered range")

    provider = (
        provider_factory() if provider_factory is not None else api["CoreAssessmentProvider"]()
    )
    provider_identity = provider.identity
    counts: Counter[str] = Counter()
    contradiction_pages: list[int] = []
    unavailable_pages: list[int] = []
    cached_pages = 0
    observations: list[dict[str, Any]] = []

    for feature in features:
        request = _build_request(
            api=api,
            book_id=book_id,
            source_ref=source_ref,
            source_sha256=source_sha256,
            projection_ref=projection_ref,
            projection_sha256=projection_binding["sha256"],
            feature=feature,
        )
        path = page_observation_path(
            workspace, witness_id=witness_id, page=feature.page
        )
        bundle = None
        if not refresh:
            bundle = _load_current_bundle(
                path=path,
                request=request,
                expected_provider=provider_identity,
                projection_binding=projection_binding,
                api=api,
                book_id=book_id,
                witness_id=witness_id,
                page=feature.page,
            )
        if bundle is not None:
            cached_pages += 1
            result = _presence_result(bundle, capability=api["CAPABILITY"])
        else:
            try:
                bundle = provider.assess(request)
                api["validate_assessment_response"](
                    request, bundle, expected_provider=provider_identity
                )
                result = _presence_result(bundle, capability=api["CAPABILITY"])
            except Exception as exc:
                unavailable_pages.append(feature.page)
                counts["unavailable"] += 1
                _write_page(
                    path=path,
                    book_id=book_id,
                    witness_id=witness_id,
                    page=feature.page,
                    status=STATUS_UNAVAILABLE,
                    provider=provider_identity.to_dict(),
                    ledger=ledger_binding,
                    projection=projection_binding,
                    request=request.to_dict(),
                    request_sha256=_text_sha256(api["assessment_request_json"](request)),
                    bundle=None,
                    bundle_sha256=None,
                    failure={
                        "code": "provider_error",
                        "type": type(exc).__name__,
                        "message": str(exc) or type(exc).__name__,
                    },
                )
                observations.append(
                    _observation_manifest_entry(
                        workspace=workspace,
                        path=path,
                        page=feature.page,
                        status=STATUS_UNAVAILABLE,
                    )
                )
                continue

        _write_page(
            path=path,
            book_id=book_id,
            witness_id=witness_id,
            page=feature.page,
            status=STATUS_AVAILABLE,
            provider=provider_identity.to_dict(),
            ledger=ledger_binding,
            projection=projection_binding,
            request=request.to_dict(),
            request_sha256=_text_sha256(api["assessment_request_json"](request)),
            bundle=bundle.to_dict(),
            bundle_sha256=_text_sha256(api["assessment_bundle_json"](bundle)),
            failure=None,
        )
        observations.append(
            _observation_manifest_entry(
                workspace=workspace,
                path=path,
                page=feature.page,
                status=STATUS_AVAILABLE,
            )
        )

        key = (
            result.assessment
            if result.execution_status == "completed"
            else result.execution_status
        )
        counts[key] += 1
        if result.execution_status == "completed" and result.assessment == "unsupported":
            contradiction_pages.append(feature.page)

    report = {
        "schema_version": SHADOW_SCHEMA_VERSION,
        "stale_class": SHADOW_STALE_CLASS,
        "mode": SHADOW_MODE,
        "book_id": book_id,
        "witness_id": witness_id,
        "status": "complete_with_unavailable" if unavailable_pages else "complete",
        "provider": provider_identity.to_dict(),
        "ledger": ledger_binding,
        "projection": projection_binding,
        "pages": page_count,
        "cached_pages": cached_pages,
        "counts": dict(sorted(counts.items())),
        "contradiction_pages": contradiction_pages,
        "unavailable_pages": unavailable_pages,
        "observations": observations,
        "observations_sha256": _dict_sha256(observations),
        "failure": None,
    }
    destination = report_path(workspace, witness_id=witness_id)
    destination.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(destination, report)
    validate_presence_report(workspace=workspace, witness_id=witness_id)
    return {**report, "report": str(destination)}


def validate_presence_report(
    *, workspace: BookWorkspace, witness_id: str
) -> dict[str, Any]:
    """Fail unless the report, projection, and every page observation remain coherent."""

    report = read_json(report_path(workspace, witness_id=witness_id))
    if (
        not isinstance(report, dict)
        or set(report) != _REPORT_KEYS
        or report.get("schema_version") != SHADOW_SCHEMA_VERSION
        or report.get("stale_class") != SHADOW_STALE_CLASS
        or report.get("mode") != SHADOW_MODE
        or report.get("witness_id") != witness_id
    ):
        raise ValueError("page-evidence presence report envelope is malformed")
    book_id = _required_text(report.get("book_id"), name="presence report book_id")
    if report.get("status") == STATUS_UNAVAILABLE:
        if (
            report.get("provider") is not None
            or report.get("projection") is not None
            or report.get("pages") is not None
            or report.get("cached_pages") != 0
            or report.get("counts") != {}
            or report.get("contradiction_pages") != []
            or report.get("unavailable_pages") != []
            or report.get("observations") != []
            or report.get("observations_sha256") != _dict_sha256([])
            or not isinstance(report.get("failure"), dict)
        ):
            raise ValueError("unavailable page-evidence presence report is malformed")
        ledger = report.get("ledger")
        if ledger is not None:
            ledger_file = workspace.resolve("data", "page_evidence", witness_id, "ledger.json")
            if ledger != _artifact_binding(
                workspace=workspace,
                path=ledger_file,
                ref=f"page-evidence:{book_id}/{witness_id}",
            ):
                raise ValueError("unavailable page-evidence presence ledger binding is stale")
        return report
    if report.get("status") not in {"complete", "complete_with_unavailable"}:
        raise ValueError("page-evidence presence report status is unknown")

    page_count = report.get("pages")
    if type(page_count) is not int or page_count < 1:
        raise ValueError("page-evidence presence report pages must be positive")
    cached_pages = report.get("cached_pages")
    if type(cached_pages) is not int or not 0 <= cached_pages <= page_count:
        raise ValueError("page-evidence presence report cached_pages is invalid")

    ledger_file = workspace.resolve("data", "page_evidence", witness_id, "ledger.json")
    expected_ledger = _artifact_binding(
        workspace=workspace,
        path=ledger_file,
        ref=f"page-evidence:{book_id}/{witness_id}",
    )
    if report.get("ledger") != expected_ledger:
        raise ValueError("page-evidence presence report ledger binding is stale")
    ledger = json.loads(ledger_file.read_bytes())
    if ledger.get("book_id") != book_id or ledger.get("witness_id") != witness_id:
        raise ValueError("page-evidence presence report ledger identity differs")

    projection_file = projection_path(workspace, witness_id=witness_id)
    expected_projection = _artifact_binding(
        workspace=workspace,
        path=projection_file,
        ref=f"page-evidence-presence:{book_id}/{witness_id}",
    )
    if report.get("projection") != expected_projection:
        raise ValueError("page-evidence presence report projection binding is stale")
    projection = json.loads(projection_file.read_bytes())
    if projection != _presence_projection(ledger):
        raise ValueError("page-evidence presence projection differs from its ledger signals")

    observations = report.get("observations")
    if (
        not isinstance(observations, list)
        or not all(isinstance(item, dict) for item in observations)
        or [item.get("page") for item in observations] != list(range(1, page_count + 1))
        or report.get("observations_sha256") != _dict_sha256(observations)
    ):
        raise ValueError("page-evidence presence observation manifest is malformed")

    api = _load_sidecar_api()
    features = _presence_features(
        projection,
        projection_ref=expected_projection["ref"],
        constructor=api["compute_effective_geometry_ocr_text_presence"],
    )
    if [feature.page for feature in features] != list(range(1, page_count + 1)):
        raise ValueError("page-evidence presence projection does not cover the report pages")
    ledger_source = ledger.get("source")
    if not isinstance(ledger_source, dict):
        raise ValueError("page-evidence presence ledger source is malformed")
    source_path = _required_text(ledger_source.get("path"), name="ledger source path")
    source_sha256 = _required_text(
        ledger_source.get("sha256"), name="ledger source sha256"
    )
    source_ref = f"scan:{book_id}/{Path(source_path).name}"
    provider = report.get("provider")
    counts: Counter[str] = Counter()
    contradictions: list[int] = []
    unavailable: list[int] = []
    for item in observations:
        if (
            set(item) != {"page", "path", "sha256", "status"}
            or item.get("status") not in {STATUS_AVAILABLE, STATUS_UNAVAILABLE}
        ):
            raise ValueError("page-evidence presence observation entry is malformed")
        page = item["page"]
        path = _workspace_artifact(workspace, item["path"])
        if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError(f"page-evidence presence observation page {page} changed")
        envelope = read_json(path)
        if (
            not isinstance(envelope, dict)
            or set(envelope) != _PAGE_KEYS
            or envelope.get("schema_version") != SHADOW_SCHEMA_VERSION
            or envelope.get("stale_class") != SHADOW_STALE_CLASS
            or envelope.get("mode") != SHADOW_MODE
            or envelope.get("book_id") != book_id
            or envelope.get("witness_id") != witness_id
            or envelope.get("page") != page
            or envelope.get("status") != item["status"]
            or envelope.get("provider") != provider
            or envelope.get("ledger") != expected_ledger
            or envelope.get("projection") != expected_projection
        ):
            raise ValueError(f"page-evidence presence observation page {page} is malformed")
        request = api["assessment_request_from_dict"](envelope["request"])
        request_json = api["assessment_request_json"](request)
        if envelope["request_sha256"] != _text_sha256(request_json):
            raise ValueError(f"page-evidence presence request page {page} changed")
        expected_request = _build_request(
            api=api,
            book_id=book_id,
            source_ref=source_ref,
            source_sha256=source_sha256,
            projection_ref=expected_projection["ref"],
            projection_sha256=expected_projection["sha256"],
            feature=features[page - 1],
        )
        if request_json != api["assessment_request_json"](expected_request):
            raise ValueError(
                f"page-evidence presence request page {page} differs from projection"
            )
        artifacts = request.input_artifacts
        if len(artifacts) != 1 or artifacts[0].to_dict() != {
            "kind": api["INPUT_KIND_PAGE_EVIDENCE_LEDGER"],
            "ref": expected_projection["ref"],
            "sha256": expected_projection["sha256"],
            "version": "page-evidence-v1",
        }:
            raise ValueError(f"page-evidence presence request page {page} is not projection-bound")
        if item["status"] == STATUS_UNAVAILABLE:
            if (
                envelope.get("bundle") is not None
                or envelope.get("bundle_sha256") is not None
                or not isinstance(envelope.get("failure"), dict)
            ):
                raise ValueError(f"unavailable presence observation page {page} is malformed")
            unavailable.append(page)
            counts["unavailable"] += 1
            continue
        bundle = api["assessment_bundle_from_dict"](envelope["bundle"])
        if (
            envelope.get("failure") is not None
            or envelope.get("bundle_sha256")
            != _text_sha256(api["assessment_bundle_json"](bundle))
            or bundle.provider.to_dict() != provider
        ):
            raise ValueError(f"page-evidence presence bundle page {page} changed")
        api["validate_assessment_response"](
            request,
            bundle,
            expected_provider=bundle.provider,
        )
        result = _presence_result(bundle, capability=api["CAPABILITY"])
        key = (
            result.assessment
            if result.execution_status == "completed"
            else result.execution_status
        )
        counts[key] += 1
        if result.execution_status == "completed" and result.assessment == "unsupported":
            contradictions.append(page)
    if (
        report.get("counts") != dict(sorted(counts.items()))
        or report.get("contradiction_pages") != contradictions
        or report.get("unavailable_pages") != unavailable
        or report.get("failure") is not None
    ):
        raise ValueError("page-evidence presence report aggregates disagree with observations")
    return report


def begin_presence_observation(
    *, workspace: BookWorkspace, book_id: str, witness_id: str
) -> dict[str, Any]:
    """Atomically replace any prior success before a new ingest attempt starts."""

    return _write_unavailable_report(
        workspace=workspace,
        book_id=book_id,
        witness_id=witness_id,
        ledger=None,
        projection=None,
        failure={
            "code": FAILURE_OBSERVATION_STARTED,
            "type": None,
            "message": "page-evidence presence observation has not completed",
        },
    )


def record_presence_unavailable(
    *,
    workspace: BookWorkspace,
    book_id: str,
    witness_id: str,
    ledger_path: Path | None,
    failure: Exception,
) -> dict[str, Any]:
    """Persist a terminal shadow failure without changing engine admission state."""

    ledger = None
    try:
        if ledger_path is not None and ledger_path.is_file():
            ledger_bytes = ledger_path.read_bytes()
            ledger = {
                "ref": f"page-evidence:{book_id}/{witness_id}",
                "path": str(ledger_path.relative_to(workspace.root)),
                "sha256": hashlib.sha256(ledger_bytes).hexdigest(),
            }
    except (OSError, ValueError):
        # Failure reporting is a shadow concern too. If its binding cannot be recovered, retain
        # the original engine/provider failure and publish an explicitly unbound report.
        ledger = None
    return _write_unavailable_report(
        workspace=workspace,
        book_id=book_id,
        witness_id=witness_id,
        ledger=ledger,
        projection=None,
        failure={
            "code": FAILURE_ENGINE_ERROR,
            "type": type(failure).__name__,
            "message": str(failure) or type(failure).__name__,
        },
    )


def _write_unavailable_report(
    *,
    workspace: BookWorkspace,
    book_id: str,
    witness_id: str,
    ledger: dict[str, str] | None,
    projection: dict[str, str] | None,
    failure: dict[str, Any],
) -> dict[str, Any]:
    report = {
        "schema_version": SHADOW_SCHEMA_VERSION,
        "stale_class": SHADOW_STALE_CLASS,
        "mode": SHADOW_MODE,
        "book_id": book_id,
        "witness_id": witness_id,
        "status": STATUS_UNAVAILABLE,
        "provider": None,
        "ledger": ledger,
        "projection": projection,
        "pages": None,
        "cached_pages": 0,
        "counts": {},
        "contradiction_pages": [],
        "unavailable_pages": [],
        "observations": [],
        "observations_sha256": _dict_sha256([]),
        "failure": failure,
    }
    destination = report_path(workspace, witness_id=witness_id)
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(destination, report)
    except Exception as exc:
        # A shadow-report storage failure must not become an admission dependency. Remove any
        # prior success when possible, then return the unavailable state in memory.
        try:
            destination.unlink(missing_ok=True)
        except OSError:
            pass
        return {
            **report,
            "report": str(destination),
            "persistence_failure": {
                "type": type(exc).__name__,
                "message": str(exc) or type(exc).__name__,
            },
        }
    return {**report, "report": str(destination)}


def _presence_projection(ledger: dict[str, Any]) -> dict[str, Any]:
    """Retain only the factual fields consumed by the presence adapter."""

    if ledger.get("schema_version") != 1 or ledger.get("stale_class") != "page-evidence-ledger":
        raise ValueError("page-evidence ledger schema is not supported for presence projection")
    pages = ledger.get("pages")
    if not isinstance(pages, list):
        raise ValueError("page-evidence ledger pages must be an array")
    source = ledger.get("source")
    if not isinstance(source, dict):
        raise ValueError("page-evidence ledger source must be an object")
    projected_pages: list[dict[str, Any]] = []
    for index, page in enumerate(pages):
        if not isinstance(page, dict) or not isinstance(page.get("signals"), dict):
            raise ValueError(f"page-evidence ledger pages[{index}] is malformed")
        signals = page["signals"]
        projected_pages.append(
            {
                "page": page.get("page"),
                "signals": {key: signals.get(key) for key in _PRESENCE_SIGNAL_KEYS},
            }
        )
    return {
        "schema_version": 1,
        "stale_class": "page-evidence-ledger",
        "book_id": ledger.get("book_id"),
        "witness_id": ledger.get("witness_id"),
        "ocr_model": ledger.get("ocr_model"),
        "source": {
            "path": source.get("path"),
            "sha256": source.get("sha256"),
            "pages": source.get("pages"),
        },
        "pages": projected_pages,
    }


def _presence_features(
    projection: dict[str, Any], *, projection_ref: str, constructor: Callable[..., Any]
) -> tuple[Any, ...]:
    """Translate the engine-owned projection into supported sidecar core records."""

    ocr_model = _required_text(projection.get("ocr_model"), name="projection ocr_model")
    source = projection.get("source")
    pages = projection.get("pages")
    if not isinstance(source, dict) or not isinstance(pages, list):
        raise ValueError("page-evidence presence projection is malformed")
    page_count = source.get("pages")
    if type(page_count) is not int or page_count < 1 or len(pages) != page_count:
        raise ValueError("page-evidence presence projection page count is invalid")
    features: list[Any] = []
    for index, page_record in enumerate(pages):
        expected_page = index + 1
        if not isinstance(page_record, dict) or page_record.get("page") != expected_page:
            raise ValueError("page-evidence presence projection must be total and ordered")
        signals = page_record.get("signals")
        if not isinstance(signals, dict) or set(signals) != set(_PRESENCE_SIGNAL_KEYS):
            raise ValueError(f"page-evidence presence projection page {expected_page} is malformed")
        baseline = _optional_count(
            signals["baseline_geometry_boxes"],
            name=f"page {expected_page} baseline_geometry_boxes",
        )
        effective = _optional_count(
            signals["effective_geometry_boxes"],
            name=f"page {expected_page} effective_geometry_boxes",
        )
        ocr_text_present = signals["ocr_has_text"]
        ocr_fallback = signals["ocr_fallback"]
        retry_status = signals["retry_status"]
        selected_path = signals["retry_selected_path"]
        if type(ocr_text_present) is not bool or type(ocr_fallback) is not bool:
            raise ValueError(f"page-evidence presence projection page {expected_page} OCR flags invalid")
        if (
            not isinstance(retry_status, str)
            or retry_status not in _RETRY_STATUSES
            or not isinstance(selected_path, str)
            or selected_path not in _RETRY_SELECTED_PATHS
        ):
            raise ValueError(f"page-evidence presence projection page {expected_page} retry invalid")
        if retry_status == "selected" and selected_path not in _RECOVERY_SELECTED_PATHS:
            raise ValueError(f"page-evidence presence projection page {expected_page} retry invalid")
        if retry_status != "selected" and selected_path != "geometry_baseline":
            raise ValueError(f"page-evidence presence projection page {expected_page} retry invalid")
        if selected_path == "geometry_baseline" and baseline != effective:
            raise ValueError(
                f"page-evidence presence projection page {expected_page} baseline changed"
            )
        selector = f"$.pages[{index}]"
        features.append(
            constructor(
                page=expected_page,
                effective_geometry_box_count=effective,
                ocr_text_present=ocr_text_present,
                retry_selected_path=selected_path,
                ocr_fallback=ocr_fallback,
                geometry_selection_producer="engine-effective-geometry-selection-v1",
                ocr_selection_producer=(
                    "engine-canonical-ocr-text-selection-v1:"
                    f"model_alias={ocr_model}"
                ),
                geometry_source_ref=projection_ref,
                geometry_source_selector=(
                    f"{selector}.signals.effective_geometry_boxes"
                ),
                ocr_text_source_ref=projection_ref,
                ocr_text_source_selector=f"{selector}.signals.ocr_has_text",
            )
        )
    return tuple(features)


def _optional_count(value: Any, *, name: str) -> int | None:
    if value is None:
        return None
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a non-negative integer or null")
    return value


def _observation_manifest_entry(
    *, workspace: BookWorkspace, path: Path, page: int, status: str
) -> dict[str, Any]:
    return {
        "page": page,
        "path": str(path.relative_to(workspace.root)),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "status": status,
    }


def _artifact_binding(
    *, workspace: BookWorkspace, path: Path, ref: str
) -> dict[str, str]:
    return {
        "ref": ref,
        "path": str(path.relative_to(workspace.root)),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def _workspace_artifact(workspace: BookWorkspace, value: Any) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError("presence observation artifact path must be non-empty text")
    root = workspace.root.resolve()
    path = (root / value).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError("presence observation artifact escapes the workspace") from exc
    if not path.is_file():
        raise ValueError(f"presence observation artifact is missing: {value}")
    return path


def _load_sidecar_api() -> dict[str, Any]:
    from book_layout_sidecar.core import (
        AssessmentEvidence,
        AssessmentInputArtifact,
        AssessmentSubject,
        CoreAssessmentProvider,
        assessment_bundle_from_dict,
        assessment_bundle_json,
        assessment_request_from_dict,
        assessment_request_json,
        build_assessment_request,
        compute_effective_geometry_ocr_text_presence,
        validate_assessment_response,
    )
    from book_layout_sidecar.core.assessment import (
        CAPABILITY_EFFECTIVE_GEOMETRY_OCR_TEXT_PRESENCE_IS_CONSISTENT,
    )
    from book_layout_sidecar.core.modules import INPUT_KIND_PAGE_EVIDENCE_LEDGER

    return {
        "AssessmentEvidence": AssessmentEvidence,
        "AssessmentInputArtifact": AssessmentInputArtifact,
        "AssessmentSubject": AssessmentSubject,
        "CoreAssessmentProvider": CoreAssessmentProvider,
        "assessment_bundle_from_dict": assessment_bundle_from_dict,
        "assessment_bundle_json": assessment_bundle_json,
        "assessment_request_from_dict": assessment_request_from_dict,
        "assessment_request_json": assessment_request_json,
        "build_assessment_request": build_assessment_request,
        "compute_effective_geometry_ocr_text_presence": (
            compute_effective_geometry_ocr_text_presence
        ),
        "validate_assessment_response": validate_assessment_response,
        "CAPABILITY": CAPABILITY_EFFECTIVE_GEOMETRY_OCR_TEXT_PRESENCE_IS_CONSISTENT,
        "INPUT_KIND_PAGE_EVIDENCE_LEDGER": INPUT_KIND_PAGE_EVIDENCE_LEDGER,
    }


def _build_request(
    *,
    api: dict[str, Any],
    book_id: str,
    source_ref: str,
    source_sha256: str,
    projection_ref: str,
    projection_sha256: str,
    feature: Any,
) -> Any:
    artifact = api["AssessmentInputArtifact"](
        kind=api["INPUT_KIND_PAGE_EVIDENCE_LEDGER"],
        ref=projection_ref,
        sha256=projection_sha256,
        version="page-evidence-v1",
    )
    evidence = api["AssessmentEvidence"](
        subject=api["AssessmentSubject"](
            book_id=book_id,
            source_ref=source_ref,
            source_sha256=source_sha256,
            page=feature.page,
        ),
        input_artifacts=(artifact,),
        geometry_ocr_text_presence=feature,
        artifact_refs_by_evidence={"geometry_ocr_text_presence": (projection_ref,)},
    )
    return api["build_assessment_request"](
        evidence=evidence,
        capabilities=(api["CAPABILITY"],),
    )


def _load_current_bundle(
    *,
    path: Path,
    request: Any,
    expected_provider: Any,
    projection_binding: dict[str, str],
    api: dict[str, Any],
    book_id: str,
    witness_id: str,
    page: int,
) -> Any | None:
    if not path.is_file():
        return None
    try:
        envelope = read_json(path)
        if not isinstance(envelope, dict) or set(envelope) != _PAGE_KEYS:
            return None
        if (
            envelope["schema_version"] != SHADOW_SCHEMA_VERSION
            or envelope["stale_class"] != SHADOW_STALE_CLASS
            or envelope["mode"] != SHADOW_MODE
            or envelope["book_id"] != book_id
            or envelope["witness_id"] != witness_id
            or envelope["page"] != page
            or envelope["status"] != STATUS_AVAILABLE
            or envelope["provider"] != expected_provider.to_dict()
            or envelope["projection"] != projection_binding
            or envelope["failure"] is not None
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
        _presence_result(stored_bundle, capability=api["CAPABILITY"])
        return stored_bundle
    except (OSError, UnicodeError, ValueError, TypeError, KeyError, RecursionError):
        return None


def _write_page(path: Path, **values: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(
        path,
        {
            "schema_version": SHADOW_SCHEMA_VERSION,
            "stale_class": SHADOW_STALE_CLASS,
            "mode": SHADOW_MODE,
            **values,
        },
    )


def _presence_result(bundle: Any, *, capability: str) -> Any:
    matches = [item for item in bundle.results if item.capability == capability]
    if len(bundle.results) != 1 or len(matches) != 1:
        raise ValueError("presence assessment bundle must contain exactly one requested result")
    return matches[0]


def _required_text(value: Any, *, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be non-empty text")
    return value


def _text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _dict_sha256(value: Any) -> str:
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return _text_sha256(rendered)
