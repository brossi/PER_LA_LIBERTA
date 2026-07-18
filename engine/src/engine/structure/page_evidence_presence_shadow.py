"""Observation-only consumer for sidecar geometry/OCR presence assessments.

The page-evidence ledger is the first engine artifact that contains both finalized effective
geometry and canonical OCR-text presence.  This boundary consumes that ledger only after it has
been written.  Its artifacts are deliberately outside the admission ledger and cannot change page
dispositions, review routing, or reconciliation admission.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

from engine.paths import BookWorkspace
from engine.util.jsonio import atomic_write_json, read_json

SHADOW_SCHEMA_VERSION = 1
SHADOW_STALE_CLASS = "page-evidence-presence-shadow"
SHADOW_MODE = "shadow"

STATUS_AVAILABLE = "available"
STATUS_UNAVAILABLE = "unavailable"

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
        "request_sha256",
        "bundle_sha256",
        "request",
        "bundle",
        "failure",
    }
)


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


def observe_page_evidence_presence(
    *,
    workspace: BookWorkspace,
    ledger_path: Path,
    witness_id: str,
    provider_factory: Callable[[], Any] | None = None,
    refresh: bool = False,
) -> dict[str, Any]:
    """Assess every ledger page while retaining a strict observational boundary."""

    ledger_sha256 = _sha256_file(ledger_path)
    ledger = read_json(ledger_path)
    book_id = _required_text(ledger.get("book_id"), name="ledger book_id")
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
    api = _load_sidecar_api()
    features = api["load_engine_page_evidence_presence_features"](
        ledger_path,
        ledger_artifact_ref=artifact_ref,
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

    for feature in features:
        request = _build_request(
            api=api,
            book_id=book_id,
            source_ref=source_ref,
            source_sha256=source_sha256,
            ledger_ref=artifact_ref,
            ledger_sha256=ledger_sha256,
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
                ledger_binding=ledger_binding,
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
                continue

            _write_page(
                path=path,
                book_id=book_id,
                witness_id=witness_id,
                page=feature.page,
                status=STATUS_AVAILABLE,
                provider=provider_identity.to_dict(),
                ledger=ledger_binding,
                request=request.to_dict(),
                request_sha256=_text_sha256(api["assessment_request_json"](request)),
                bundle=bundle.to_dict(),
                bundle_sha256=_text_sha256(api["assessment_bundle_json"](bundle)),
                failure=None,
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
        "pages": page_count,
        "cached_pages": cached_pages,
        "counts": dict(sorted(counts.items())),
        "contradiction_pages": contradiction_pages,
        "unavailable_pages": unavailable_pages,
    }
    destination = report_path(workspace, witness_id=witness_id)
    destination.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(destination, report)
    return {**report, "report": str(destination)}


def _load_sidecar_api() -> dict[str, Any]:
    from book_layout_sidecar.adapters.engine_page_evidence import (
        load_engine_page_evidence_presence_features,
    )
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
        "validate_assessment_response": validate_assessment_response,
        "CAPABILITY": CAPABILITY_EFFECTIVE_GEOMETRY_OCR_TEXT_PRESENCE_IS_CONSISTENT,
        "INPUT_KIND_PAGE_EVIDENCE_LEDGER": INPUT_KIND_PAGE_EVIDENCE_LEDGER,
        "load_engine_page_evidence_presence_features": (
            load_engine_page_evidence_presence_features
        ),
    }


def _build_request(
    *,
    api: dict[str, Any],
    book_id: str,
    source_ref: str,
    source_sha256: str,
    ledger_ref: str,
    ledger_sha256: str,
    feature: Any,
) -> Any:
    artifact = api["AssessmentInputArtifact"](
        kind=api["INPUT_KIND_PAGE_EVIDENCE_LEDGER"],
        ref=ledger_ref,
        sha256=ledger_sha256,
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
        artifact_refs_by_evidence={"geometry_ocr_text_presence": (ledger_ref,)},
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
    ledger_binding: dict[str, str],
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
            or envelope["ledger"] != ledger_binding
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
    if len(matches) != 1:
        raise ValueError("presence assessment bundle must contain exactly one requested result")
    return matches[0]


def _required_text(value: Any, *, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be non-empty text")
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
