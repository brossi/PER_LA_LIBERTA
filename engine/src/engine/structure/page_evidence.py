"""Total page-disposition ledger and reconciliation admission boundary."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from engine.config.models import ResolvedConfig
from engine.contracts.markers import SENTINEL_BLANK, SENTINEL_OCR_ERROR_PREFIX
from engine.errors import (
    InvalidInvocationError,
    MissingInputError,
    ReconciliationAdmissionError,
    StaleArtifactError,
)
from engine.paths import BookWorkspace
from engine.util.jsonio import atomic_write_json, read_json

LEDGER_SCHEMA_VERSION = 1
LEDGER_STALE_CLASS = "page-evidence-ledger"
REVIEW_SCHEMA_VERSION = 1
REVIEW_STALE_CLASS = "page-evidence-review"
VERDICTS_SCHEMA_VERSION = 1
VERDICTS_STALE_CLASS = "page-evidence-human-verdicts"
ADMISSION_SCHEMA_VERSION = 1
ADMISSION_STALE_CLASS = "reconciliation-page-evidence-admission"
DEFAULT_REVIEW_BOUND = 25

DISPOSITIONS = {"content", "blank", "non_text", "review_required"}
HUMAN_DISPOSITIONS = DISPOSITIONS - {"review_required"}


def ledger_path(workspace: BookWorkspace, *, witness_id: str) -> Path:
    return workspace.resolve("data", "page_evidence", witness_id, "ledger.json")


def review_path(workspace: BookWorkspace, *, witness_id: str) -> Path:
    return workspace.resolve("data", "page_evidence", witness_id, "review.json")


def verdicts_path(workspace: BookWorkspace, *, witness_id: str) -> Path:
    """Tracked human decisions, outside the regenerable ``work/`` tree."""
    return workspace.root.parent / "review" / "page_evidence" / witness_id / "verdicts.json"


def admission_path(workspace: BookWorkspace) -> Path:
    return workspace.resolve("state", "page_evidence_admission.json")


def build_page_evidence(
    *,
    workspace: BookWorkspace,
    cfg: ResolvedConfig,
    witness_id: str = "copy1",
    model: str = "flash",
    max_review_pages: int = DEFAULT_REVIEW_BOUND,
) -> dict[str, Any]:
    """Build the deterministic total ledger and its bounded review packet."""
    if type(max_review_pages) is not int or max_review_pages < 0:
        raise InvalidInvocationError("ingest_gate requires a non-negative --max-review-pages")
    if not witness_id or not model:
        raise InvalidInvocationError("ingest_gate witness and OCR model must be non-empty")

    report_path = workspace.resolve(
        "data", "layout_assessment", witness_id, "run_report.json"
    )
    report = _required_json(report_path, kind="layout-shadow run report")
    total = cfg.manifest.scan.last_scan_page_default
    if (
        report.get("schema_version") != 3
        or report.get("status") not in {"complete", "complete_with_unavailable"}
        or report.get("book_id") != cfg.book_id
        or report.get("witness_id") != witness_id
        or report.get("source", {}).get("pages") != total
    ):
        raise StaleArtifactError(f"layout-shadow report is not current for {cfg.book_id}")

    source_path = workspace.scans / cfg.manifest.scan.pdf
    if not source_path.is_file():
        raise MissingInputError(f"source scan PDF not found: {source_path}")
    source_sha256 = _sha256_file(source_path)
    if report["source"].get("sha256") != source_sha256:
        raise StaleArtifactError("layout-shadow report source hash does not match the scan")

    page_artifacts = report.get("geometry", {}).get("page_artifacts")
    if not isinstance(page_artifacts, list) or [item.get("page") for item in page_artifacts] != list(
        range(1, total + 1)
    ):
        raise StaleArtifactError("layout-shadow page artifacts are not total and ordered")

    verdict_path = verdicts_path(workspace, witness_id=witness_id)
    verdict_document, verdicts = _load_verdicts(
        verdict_path, book_id=cfg.book_id, witness_id=witness_id, total=total
    )
    verdict_sha256 = _sha256_file(verdict_path) if verdict_document is not None else None

    pages: list[dict[str, Any]] = []
    review_pages: list[dict[str, Any]] = []
    providers: set[tuple[str, str]] = set()
    for artifact in page_artifacts:
        page = artifact["page"]
        assessment_path = _artifact_path(workspace, artifact, "assessment_path")
        assessment = _required_json(assessment_path, kind=f"page {page} assessment")
        _require_hash(assessment_path, artifact.get("assessment_sha256"), page=page)
        if assessment.get("status") != "available" or not isinstance(
            assessment.get("bundle", {}).get("results"), list
        ):
            assessment_available = False
        else:
            assessment_available = True
            provider = assessment.get("provider", {})
            providers.add((provider.get("provider_id"), provider.get("provider_version")))

        evidence_files = {
            "raster": _evidence_file(workspace, artifact, "raster_path", "raster_sha256", page),
            "geometry": _evidence_file(
                workspace, artifact, "geometry_path", "geometry_sha256", page
            ),
            "assessment": _evidence_file(
                workspace, artifact, "assessment_path", "assessment_sha256", page
            ),
        }
        retry_ref = artifact.get("retry_path")
        if retry_ref is not None:
            evidence_files["geometry_retry"] = _evidence_file(
                workspace, artifact, "retry_path", "retry_sha256", page
            )
            retry_record = _required_json(
                _workspace_relative(workspace, retry_ref),
                kind=f"page {page} geometry retry",
            )
            transformed_sha256 = retry_record.get("transformed_raster_sha256")
            if transformed_sha256 is not None:
                transformed_path = workspace.resolve(
                    "data", "raster", "retry", witness_id,
                    f"page_{page:04d}_{retry_record['transform']}.png",
                )
                _require_hash(transformed_path, transformed_sha256, page=page)
                evidence_files["retry_raster"] = {
                    "path": str(transformed_path.relative_to(workspace.root)),
                    "sha256": transformed_sha256,
                }

        ocr_path = workspace.resolve("state", f"ocr_{model}_pages", f"page_{page:04d}.json")
        ocr = _required_json(ocr_path, kind=f"page {page} OCR checkpoint")
        if ocr.get("page") != page or not isinstance(ocr.get("text"), str):
            raise StaleArtifactError(f"page {page} OCR checkpoint is malformed")
        evidence_files["ocr_checkpoint"] = {
            "path": str(ocr_path.relative_to(workspace.root)),
            "sha256": _sha256_file(ocr_path),
        }

        raw_evidence = {
            "page": page,
            "source_sha256": source_sha256,
            "files": evidence_files,
            "ocr_text_sha256": _sha256_text(ocr["text"]),
        }
        evidence_sha256 = _dict_sha256(raw_evidence)
        disposition, reasons, human = _derive_disposition(
            artifact=artifact,
            assessment=assessment,
            assessment_available=assessment_available,
            ocr=ocr,
            verdict=verdicts.get(page),
            evidence_sha256=evidence_sha256,
        )
        page_record = {
            "page": page,
            "disposition": disposition,
            "reasons": reasons,
            "evidence_sha256": evidence_sha256,
            "evidence": raw_evidence,
            "signals": {
                "ocr_has_text": _ocr_has_text(ocr["text"]),
                "ocr_fallback": isinstance(ocr.get("provenance"), dict),
                "baseline_geometry_boxes": artifact.get("word_count"),
                "effective_geometry_boxes": artifact.get("effective_word_count"),
                "retry_status": artifact.get("retry_status"),
                "retry_selected_path": artifact.get("retry_selected_path"),
                "retry_text_verdict": artifact.get("retry_text_verdict"),
                "ink_fraction": artifact.get("ink_fraction"),
                "density_label": artifact.get("density_label"),
                "density_policy_applied": artifact.get("density_policy_applied"),
            },
            "human_verdict": human,
        }
        pages.append(page_record)
        if disposition == "review_required":
            review_pages.append({
                "page": page,
                "evidence_sha256": evidence_sha256,
                "reasons": reasons,
                "raster": evidence_files["raster"],
                "assessment": evidence_files["assessment"],
                "geometry_retry": evidence_files.get("geometry_retry"),
                "ocr_checkpoint": evidence_files["ocr_checkpoint"],
                "ocr_excerpt": ocr["text"][:800],
                "signals": page_record["signals"],
            })

    if len(providers) != 1:
        raise StaleArtifactError(f"page assessments do not share one provider identity: {providers}")
    provider_id, provider_version = next(iter(providers))
    try:
        from book_layout_sidecar import __version__ as current_provider_version
    except ImportError as exc:
        raise MissingInputError(
            "ingest_gate requires the assessment dependency; install --extra assessment"
        ) from exc
    if provider_id != "book_layout_sidecar" or provider_version != current_provider_version:
        raise StaleArtifactError(
            f"page assessments use {provider_id}@{provider_version}, current provider is "
            f"book_layout_sidecar@{current_provider_version}; rerun layout_shadow"
        )
    counts = Counter(page["disposition"] for page in pages)
    reason_counts = Counter(reason for page in pages for reason in page["reasons"])
    verdict_ref = str(verdict_path.relative_to(workspace.root.parent))
    ledger = {
        "schema_version": LEDGER_SCHEMA_VERSION,
        "stale_class": LEDGER_STALE_CLASS,
        "book_id": cfg.book_id,
        "witness_id": witness_id,
        "ocr_model": model,
        "source": {
            "path": str(source_path.relative_to(workspace.root.parent)),
            "sha256": source_sha256,
            "pages": total,
        },
        "provider": {"provider_id": provider_id, "provider_version": provider_version},
        "layout_report": {
            "path": str(report_path.relative_to(workspace.root)),
            "sha256": _sha256_file(report_path),
        },
        "verdicts": {"scope": "book", "path": verdict_ref, "sha256": verdict_sha256},
        "review_bound": max_review_pages,
        "status": "admitted" if not review_pages else "review_required",
        "counts": {key: counts.get(key, 0) for key in sorted(DISPOSITIONS)},
        "reason_counts": dict(sorted(reason_counts.items())),
        "pages": pages,
    }
    ledger_file = ledger_path(workspace, witness_id=witness_id)
    review_file = review_path(workspace, witness_id=witness_id)
    ledger_file.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(ledger_file, ledger)
    atomic_write_json(review_file, {
        "schema_version": REVIEW_SCHEMA_VERSION,
        "stale_class": REVIEW_STALE_CLASS,
        "book_id": cfg.book_id,
        "witness_id": witness_id,
        "verdicts_path": verdict_ref,
        "review_bound": max_review_pages,
        "review_count": len(review_pages),
        "pages": review_pages,
    })
    atomic_write_json(admission_path(workspace), {
        "schema_version": ADMISSION_SCHEMA_VERSION,
        "stale_class": ADMISSION_STALE_CLASS,
        "book_id": cfg.book_id,
        "status": ledger["status"],
        "ledger_path": str(ledger_file.relative_to(workspace.root)),
        "ledger_sha256": _sha256_file(ledger_file),
        "review_path": str(review_file.relative_to(workspace.root)),
        "review_sha256": _sha256_file(review_file),
    })
    if len(review_pages) > max_review_pages:
        raise ReconciliationAdmissionError(
            f"page-evidence review volume {len(review_pages)} exceeds bound "
            f"{max_review_pages}; see {review_file}"
        )
    return {
        "status": ledger["status"],
        "pages": total,
        "counts": ledger["counts"],
        "review_pages": len(review_pages),
        "ledger": str(ledger_file),
        "review": str(review_file),
    }


def assert_reconciliation_admission(
    *, workspace: BookWorkspace, cfg: ResolvedConfig
) -> dict[str, Any]:
    """Fail loud unless a total admitted ledger still matches every bound input."""
    pointer_path = admission_path(workspace)
    if not pointer_path.is_file():
        raise ReconciliationAdmissionError(
            "reconciliation requires an admitted page-evidence ledger; run --step ingest_gate"
        )
    pointer = _required_json(pointer_path, kind="page-evidence admission record")
    if (
        pointer.get("schema_version") != ADMISSION_SCHEMA_VERSION
        or pointer.get("stale_class") != ADMISSION_STALE_CLASS
        or pointer.get("book_id") != cfg.book_id
        or pointer.get("status") != "admitted"
    ):
        raise ReconciliationAdmissionError(
            "page-evidence ledger is not admitted; resolve its review packet and rerun ingest_gate"
        )
    ledger_file = _workspace_relative(workspace, pointer.get("ledger_path"))
    if not ledger_file.is_file() or _sha256_file(ledger_file) != pointer.get("ledger_sha256"):
        raise ReconciliationAdmissionError("page-evidence ledger changed after admission")
    ledger = _required_json(ledger_file, kind="page-evidence ledger")
    total = cfg.manifest.scan.last_scan_page_default
    if (
        ledger.get("schema_version") != LEDGER_SCHEMA_VERSION
        or ledger.get("stale_class") != LEDGER_STALE_CLASS
        or ledger.get("book_id") != cfg.book_id
        or ledger.get("status") != "admitted"
        or [page.get("page") for page in ledger.get("pages", [])] != list(range(1, total + 1))
        or any(page.get("disposition") not in HUMAN_DISPOSITIONS for page in ledger.get("pages", []))
    ):
        raise ReconciliationAdmissionError("page-evidence ledger is partial or unresolved")
    source_path = workspace.scans / cfg.manifest.scan.pdf
    if not source_path.is_file() or _sha256_file(source_path) != ledger.get("source", {}).get("sha256"):
        raise ReconciliationAdmissionError("source scan changed after page-evidence admission")
    report_meta = ledger.get("layout_report", {})
    report_file = _workspace_relative(workspace, report_meta.get("path"))
    if not report_file.is_file() or _sha256_file(report_file) != report_meta.get("sha256"):
        raise ReconciliationAdmissionError("layout report changed after page-evidence admission")
    for page in ledger["pages"]:
        for evidence in page["evidence"]["files"].values():
            path = _workspace_relative(workspace, evidence["path"])
            if not path.is_file() or _sha256_file(path) != evidence["sha256"]:
                raise ReconciliationAdmissionError(
                    f"page {page['page']} evidence changed after admission: {evidence['path']}"
                )
    verdict_meta = ledger["verdicts"]
    if verdict_meta.get("scope") != "book":
        raise ReconciliationAdmissionError("page-evidence verdict location is not durable")
    verdict_file = _book_relative(workspace, verdict_meta["path"])
    current_verdict_sha = _sha256_file(verdict_file) if verdict_file.is_file() else None
    if current_verdict_sha != verdict_meta.get("sha256"):
        raise ReconciliationAdmissionError("human verdicts changed after page-evidence admission")
    return ledger


def _derive_disposition(
    *,
    artifact: dict[str, Any],
    assessment: dict[str, Any],
    assessment_available: bool,
    ocr: dict[str, Any],
    verdict: dict[str, Any] | None,
    evidence_sha256: str,
) -> tuple[str, list[str], dict[str, Any] | None]:
    if verdict is not None:
        if verdict["evidence_sha256"] == evidence_sha256:
            return verdict["disposition"], ["human_verdict"], verdict
        stale_reason = ["stale_human_verdict"]
    else:
        stale_reason = []
    if not assessment_available:
        return "review_required", [*stale_reason, "assessment_unavailable"], None

    text = ocr["text"]
    has_text = _ocr_has_text(text)
    effective_boxes = artifact.get("effective_word_count")
    retry_status = artifact.get("retry_status")
    results = assessment["bundle"]["results"]
    text_like = _result_assessment(results, module="ocr_text_likeness")
    near_blank = _result_assessment(results, module="near_blank_hallucinated_boxes")

    if has_text:
        if retry_status in {"unresolved", "unavailable"}:
            return "review_required", [*stale_reason, "ocr_content_with_unresolved_geometry"], None
        if type(effective_boxes) is not int or effective_boxes <= 2:
            return "review_required", [*stale_reason, "ocr_content_without_trusted_geometry"], None
        if text_like == "unsupported" or near_blank == "unsupported":
            return "review_required", [*stale_reason, "ocr_content_contradicted_by_layout"], None
        return "content", ["ocr_content_with_geometry_support"], None

    if text.startswith(SENTINEL_OCR_ERROR_PREFIX):
        return "review_required", [*stale_reason, "ocr_checkpoint_error"], None
    if retry_status == "selected" or (type(effective_boxes) is int and effective_boxes > 2):
        return "review_required", [*stale_reason, "blank_ocr_with_content_geometry"], None
    if retry_status in {"unresolved", "unavailable"}:
        return "review_required", [*stale_reason, "blank_ocr_with_unresolved_geometry"], None
    if artifact.get("retry_gate_reason") == "ocr_null_with_decisive_near_blank_evidence":
        return "blank", ["ocr_blank_with_decisive_near_blank_evidence"], None
    if artifact.get("density_policy_applied") and artifact.get("density_label") in {
        "cover", "non_text_dark"
    }:
        return "non_text", ["ocr_blank_with_calibrated_non_text_density"], None
    return "review_required", [*stale_reason, "blank_ocr_without_decisive_visual_evidence"], None


def _result_assessment(results: list[dict[str, Any]], *, module: str) -> str | None:
    matches = [
        item.get("assessment")
        for item in results
        if item.get("module_id") == module and item.get("execution_status") == "completed"
    ]
    return matches[0] if len(matches) == 1 else None


def _ocr_has_text(text: str) -> bool:
    stripped = text.strip()
    return bool(stripped and stripped != SENTINEL_BLANK and not stripped.startswith(SENTINEL_OCR_ERROR_PREFIX))


def _load_verdicts(
    path: Path, *, book_id: str, witness_id: str, total: int
) -> tuple[dict[str, Any] | None, dict[int, dict[str, Any]]]:
    if not path.is_file():
        return None, {}
    document = _required_json(path, kind="human verdicts")
    if (
        document.get("schema_version") != VERDICTS_SCHEMA_VERSION
        or document.get("stale_class") != VERDICTS_STALE_CLASS
        or document.get("book_id") != book_id
        or document.get("witness_id") != witness_id
        or not isinstance(document.get("verdicts"), list)
    ):
        raise StaleArtifactError(f"human verdict document is malformed: {path}")
    verdicts: dict[int, dict[str, Any]] = {}
    for verdict in document["verdicts"]:
        page = verdict.get("page")
        if (
            type(page) is not int
            or not 1 <= page <= total
            or page in verdicts
            or verdict.get("disposition") not in HUMAN_DISPOSITIONS
            or not isinstance(verdict.get("evidence_sha256"), str)
            or not isinstance(verdict.get("reviewer"), str)
            or not verdict["reviewer"].strip()
            or not isinstance(verdict.get("decided_at"), str)
            or not verdict["decided_at"].strip()
        ):
            raise StaleArtifactError(f"invalid human verdict in {path}: {verdict!r}")
        verdicts[page] = verdict
    return document, verdicts


def record_page_verdict(
    *,
    workspace: BookWorkspace,
    cfg: ResolvedConfig,
    witness_id: str,
    model: str,
    page: int,
    disposition: str,
    evidence_sha256: str,
    reviewer: str,
    note: str | None = None,
    decided_at: str | None = None,
    max_review_pages: int = DEFAULT_REVIEW_BOUND,
) -> dict[str, Any]:
    """Record one current-evidence human verdict and rebuild admission artifacts."""
    if disposition not in HUMAN_DISPOSITIONS:
        raise InvalidInvocationError(
            f"page verdict disposition must be one of {sorted(HUMAN_DISPOSITIONS)}"
        )
    if type(page) is not int or page < 1:
        raise InvalidInvocationError("page verdict requires a positive page number")
    if not isinstance(evidence_sha256, str) or len(evidence_sha256) != 64:
        raise InvalidInvocationError("page verdict requires a SHA-256 evidence fingerprint")
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise InvalidInvocationError("page verdict requires a non-empty reviewer identity")
    if note is not None and not isinstance(note, str):
        raise InvalidInvocationError("page verdict note must be text")

    # Refresh before accepting the browser's fingerprint. This closes the window where a stale
    # generated review packet still exists after source evidence changes.
    build_page_evidence(
        workspace=workspace,
        cfg=cfg,
        witness_id=witness_id,
        model=model,
        max_review_pages=max_review_pages,
    )
    packet = _required_json(
        review_path(workspace, witness_id=witness_id), kind="page-evidence review packet"
    )
    candidates = [item for item in packet.get("pages", []) if item.get("page") == page]
    if len(candidates) != 1:
        raise StaleArtifactError(f"page {page} is not in the current review packet")
    current_evidence = candidates[0].get("evidence_sha256")
    if current_evidence != evidence_sha256:
        raise StaleArtifactError(
            f"page {page} review evidence changed: {evidence_sha256} != {current_evidence}"
        )

    path = verdicts_path(workspace, witness_id=witness_id)
    _, existing = _load_verdicts(
        path,
        book_id=cfg.book_id,
        witness_id=witness_id,
        total=cfg.manifest.scan.last_scan_page_default,
    )
    verdict: dict[str, Any] = {
        "page": page,
        "disposition": disposition,
        "evidence_sha256": evidence_sha256,
        "reviewer": reviewer.strip(),
        "decided_at": decided_at or datetime.now(UTC).isoformat(),
    }
    if note is not None and note.strip():
        verdict["note"] = note.strip()
    existing[page] = verdict
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(path, {
        "schema_version": VERDICTS_SCHEMA_VERSION,
        "stale_class": VERDICTS_STALE_CLASS,
        "book_id": cfg.book_id,
        "witness_id": witness_id,
        "verdicts": [existing[key] for key in sorted(existing)],
    })
    summary = build_page_evidence(
        workspace=workspace,
        cfg=cfg,
        witness_id=witness_id,
        model=model,
        max_review_pages=max_review_pages,
    )
    return {**summary, "verdict": verdict, "verdicts_path": str(path)}


def _evidence_file(
    workspace: BookWorkspace,
    artifact: dict[str, Any],
    path_key: str,
    hash_key: str,
    page: int,
) -> dict[str, str]:
    path = _artifact_path(workspace, artifact, path_key)
    _require_hash(path, artifact.get(hash_key), page=page)
    return {"path": str(path.relative_to(workspace.root)), "sha256": artifact[hash_key]}


def _artifact_path(workspace: BookWorkspace, artifact: dict[str, Any], key: str) -> Path:
    return _workspace_relative(workspace, artifact.get(key))


def _workspace_relative(workspace: BookWorkspace, relative: Any) -> Path:
    if not isinstance(relative, str) or not relative:
        raise StaleArtifactError(f"invalid workspace artifact path: {relative!r}")
    path = (workspace.root / relative).resolve()
    if not path.is_relative_to(workspace.root):
        raise StaleArtifactError(f"artifact path escapes workspace: {relative!r}")
    return path


def _book_relative(workspace: BookWorkspace, relative: Any) -> Path:
    if not isinstance(relative, str) or not relative:
        raise StaleArtifactError(f"invalid book artifact path: {relative!r}")
    book_root = workspace.root.parent.resolve()
    path = (book_root / relative).resolve()
    if not path.is_relative_to(book_root):
        raise StaleArtifactError(f"artifact path escapes book directory: {relative!r}")
    return path


def _require_hash(path: Path, expected: Any, *, page: int) -> None:
    if not path.is_file():
        raise MissingInputError(f"page {page} evidence is missing: {path}")
    if not isinstance(expected, str) or _sha256_file(path) != expected:
        raise StaleArtifactError(f"page {page} evidence hash is stale: {path}")


def _required_json(path: Path, *, kind: str) -> dict[str, Any]:
    if not path.is_file():
        raise MissingInputError(f"{kind} is missing: {path}")
    try:
        value = read_json(path)
    except (OSError, UnicodeError, ValueError, TypeError, RecursionError) as exc:
        raise StaleArtifactError(f"{kind} is unreadable: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise StaleArtifactError(f"{kind} must be a JSON object: {path}")
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _dict_sha256(value: dict[str, Any]) -> str:
    payload = json.dumps(value, allow_nan=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
