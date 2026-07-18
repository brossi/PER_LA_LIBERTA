"""Persisted pipeline lifecycle plus artifact-derived progress snapshots.

The lifecycle file answers "what is running now?" while artifact inspection answers "how far did
the long step get?" and reconstructs useful status after a restart or for runs made before lifecycle
tracking existed. Monitoring is read-only; steps remain the owners of their artifacts.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config.models import ResolvedConfig
from .paths import BookWorkspace
from .util.jsonio import atomic_write_json

PROGRESS_FILE = "pipeline_progress.json"
TRIAGE_PROGRESS_FILE = "triage_progress.json"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _load(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return {} if default is None else default


@dataclass(slots=True)
class PipelineTracker:
    workspace: BookWorkspace

    @property
    def path(self) -> Path:
        return self.workspace.state / PROGRESS_FILE

    def _state(self) -> dict:
        state = _load(self.path)
        return state if isinstance(state, dict) else {}

    def start_step(self, step: str) -> None:
        self.workspace.ensure()
        state = self._state()
        now = _now()
        steps = state.setdefault("steps", {})
        steps[step] = {"status": "running", "started_at": now}
        state.update({
            "schema_version": 1,
            "book_id": self.workspace.book_id,
            "run_status": "running",
            "active_step": step,
            "updated_at": now,
        })
        atomic_write_json(self.path, state)

    def complete_step(self, step: str, summary: dict | None) -> None:
        state = self._state()
        now = _now()
        record = state.setdefault("steps", {}).setdefault(step, {})
        record.update({"status": "complete", "completed_at": now, "summary": summary or {}})
        state.update({
            "run_status": "idle",
            "active_step": None,
            "updated_at": now,
        })
        atomic_write_json(self.path, state)

    def fail_step(self, step: str, error: str) -> None:
        state = self._state()
        now = _now()
        record = state.setdefault("steps", {}).setdefault(step, {})
        record.update({"status": "failed", "failed_at": now, "error": error})
        state.update({
            "run_status": "failed",
            "active_step": None,
            "updated_at": now,
        })
        atomic_write_json(self.path, state)


def _entry(step: str, status: str, progress: str = "", detail: str = "") -> dict:
    return {"step": step, "status": status, "progress": progress, "detail": detail}


def _count_json(path: Path) -> int:
    return sum(1 for candidate in path.glob("*.json") if candidate.is_file()) if path.is_dir() else 0


def pipeline_snapshot(workspace: BookWorkspace, cfg: ResolvedConfig) -> dict:
    """Return a restart-safe snapshot of the useful book pipeline through translation."""
    ws = workspace
    lifecycle = _load(ws.state / PROGRESS_FILE)
    active = lifecycle.get("active_step") if isinstance(lifecycle, dict) else None
    lifecycle_steps = lifecycle.get("steps", {}) if isinstance(lifecycle, dict) else {}
    entries: list[dict] = []

    layout_root = ws.data / "layout_assessment"
    layout_candidates = []
    if layout_root.is_dir():
        for witness_dir in sorted(path for path in layout_root.iterdir() if path.is_dir()):
            report = _load(witness_dir / "run_report.json")
            observed = sum(1 for path in witness_dir.glob("page_*.json") if path.is_file())
            complete = report.get("status") in {"complete", "complete_with_unavailable"}
            layout_candidates.append((complete, observed, witness_dir.name, report))

    total_layout_pages = cfg.manifest.scan.last_scan_page_default
    layout_progress = _load(ws.state / "layout_shadow_progress.json")
    if active == "layout_shadow" and layout_progress.get("status") == "running":
        observed = int(layout_progress.get("completed_pages", 0))
        total = int(layout_progress.get("total_pages", total_layout_pages))
        entries.append(_entry(
            "layout_shadow",
            "running",
            f"{min(observed, total)}/{total} pages",
            str(layout_progress.get("witness_id", "")),
        ))
    elif layout_candidates:
        complete, observed, witness_id, layout = max(
            layout_candidates, key=lambda item: (item[0], item[1], item[2])
        )
        geometry = layout.get("geometry", {}) if isinstance(layout, dict) else {}
        observed = int(geometry.get("page_count", observed)) if complete else observed
        unavailable = (
            len(layout.get("assessment", {}).get("unavailable_pages", [])) if complete else 0
        )
        detail = (
            f"{geometry.get('word_count', 0):,} boxes; {geometry.get('oob_box_count', 0)} OOB"
            + (f"; {unavailable} unavailable" if unavailable else "")
            if complete
            else witness_id
        )
        entries.append(_entry(
            "layout_shadow",
            "complete" if complete else ("running" if active == "layout_shadow" else "pending"),
            f"{min(observed, total_layout_pages)}/{total_layout_pages} pages",
            detail,
        ))
    else:
        entries.append(_entry(
            "layout_shadow",
            "running" if active == "layout_shadow" else "pending",
            f"0/{total_layout_pages} pages",
            "optional shadow preflight",
        ))

    declared = list(cfg.manifest.sources)
    downloaded = sum((ws.data / f"{source.role}_raw.txt").is_file() for source in declared)
    entries.append(_entry(
        "download", "complete" if downloaded == len(declared) else "pending",
        f"{downloaded}/{len(declared)} sources",
    ))

    ocr_candidates = []
    for role in cfg.manifest.ocr.models:
        count = _count_json(ws.state / f"ocr_{role}_pages")
        if count or (ws.data / f"copy3_{role}.txt").is_file():
            ocr_candidates.append((role, count, (ws.data / f"copy3_{role}.txt").is_file()))
    if ocr_candidates:
        role, count, published = max(ocr_candidates, key=lambda item: (item[2], item[1]))
        total = cfg.manifest.scan.last_scan_page_default
        status = "complete" if published and count >= total else "running" if active == "ocr" else "pending"
        entries.append(_entry("ocr", status, f"{min(count, total)}/{total} pages", role))
    else:
        entries.append(_entry("ocr", "running" if active == "ocr" else "pending", "0 pages"))

    ledger = _load(ws.data / "page_evidence" / "copy1" / "ledger.json")
    ledger_counts = ledger.get("counts", {}) if isinstance(ledger, dict) else {}
    ledger_reasons = ledger.get("reason_counts", {}) if isinstance(ledger, dict) else {}
    ledger_pages = ledger.get("pages", []) if isinstance(ledger, dict) else []
    ledger_status = ledger.get("status") if isinstance(ledger, dict) else None
    entries.append(_entry(
        "ingest_gate",
        "complete" if ledger_status == "admitted" else (
            "running" if active == "ingest_gate" else "failed" if ledger_status else "pending"
        ),
        f"{len(ledger_pages)}/{cfg.manifest.scan.last_scan_page_default} pages",
        (
            f"{ledger_counts.get('review_required', 0)} require review"
            + (
                "; " + ", ".join(
                    f"{reason}={count}"
                    for reason, count in sorted(
                        ledger_reasons.items(), key=lambda item: (-item[1], item[0])
                    )[:3]
                )
                if ledger_reasons else ""
            )
            if ledger_status
            else "page-evidence admission"
        ),
    ))

    reconciled = _load(ws.data / "reconciled_chapters.json", [])
    flags = _load(ws.data / "flagged_segments.json", [])
    entries.append(_entry(
        "reconcile", "complete" if isinstance(reconciled, list) and reconciled else (
            "running" if active == "reconcile" else "pending"
        ),
        f"{len(reconciled) if isinstance(reconciled, list) else 0} sections",
        f"{len(flags) if isinstance(flags, list) else 0} disagreements",
    ))

    triage = _load(ws.state / TRIAGE_PROGRESS_FILE)
    if triage:
        total = int(triage.get("total_items", 0))
        done = int(triage.get("completed_items", 0))
        status = "complete" if triage.get("status") == "complete" else (
            "running" if active == "triage" or triage.get("status") == "running" else "failed"
        )
        detail = f"batch {triage.get('completed_batches', 0)}/{triage.get('total_batches', 0)}"
        entries.append(_entry("triage", status, f"{done}/{total} items", detail))
    else:
        resolved = _load(ws.data / "triage_resolved.json", [])
        done = len(resolved) if isinstance(resolved, list) else 0
        entries.append(_entry(
            "triage", "complete" if done else ("running" if active == "triage" else "pending"),
            f"{done}/{len(flags) if isinstance(flags, list) else 0} items",
            "legacy run (no batch checkpoints)" if done else "",
        ))

    clean_path = ws.output / "clean.md"
    llm_cached = _count_json(ws.state / "llm_cleaned")
    # LLM cleanup caches are text files, not JSON.
    if (ws.state / "llm_cleaned").is_dir():
        llm_cached = sum(1 for path in (ws.state / "llm_cleaned").glob("*.txt") if path.is_file())
    review_flags = _load(ws.data / "review_flags.json")
    review_count = sum(len(items) for items in review_flags.values()) if isinstance(review_flags, dict) else 0
    entries.append(_entry(
        "cleanup", "complete" if clean_path.is_file() else ("running" if active == "cleanup" else "pending"),
        f"{llm_cached} cached sections" if llm_cached else "",
        f"{review_count} review flags" if clean_path.is_file() else "",
    ))

    validation = _load(ws.data / "validation_report.json")
    validation_status = str(validation.get("overall", "")).lower()
    entries.append(_entry(
        "validate",
        "complete" if validation_status == "pass" else "failed" if validation_status in {"fail", "error"} else (
            "running" if active == "validate" else "pending"
        ),
        validation_status.upper() if validation_status else "",
    ))

    translation = _load(ws.state / "translation_progress.json")
    translated_total = len(reconciled) if isinstance(reconciled, list) else 0
    translated_done = sum(
        item.get("status") == "done" for item in translation.values()
    ) if isinstance(translation, dict) else 0
    translation_complete = (ws.output / "english_translation.md").is_file() and (
        translated_total == 0 or translated_done == translated_total
    )
    translation_errors = sum(
        item.get("status") in {"error", "truncated"} for item in translation.values()
    ) if isinstance(translation, dict) else 0
    entries.append(_entry(
        "translate",
        "complete" if translation_complete else "failed" if translation_errors and active != "translate" else (
            "running" if active == "translate" else "pending"
        ),
        f"{translated_done}/{translated_total} sections",
        f"{translation_errors} failed" if translation_errors else "",
    ))

    evaluation = _load(ws.data / "gutenberg_evaluation.json")
    if evaluation.get("status") == "diagnostic_complete":
        wer = evaluation.get("overall", {}).get("word_error_rate")
        entries.append(_entry(
            "evaluation", "complete", "post-seal",
            f"token WER {wer:.2%}" if isinstance(wer, (int, float)) else "",
        ))

    for entry in entries:
        lifecycle_record = lifecycle_steps.get(entry["step"], {})
        if active == entry["step"]:
            entry["status"] = "running"
        elif lifecycle_record.get("status") == "failed":
            entry["status"] = "failed"
            entry["detail"] = lifecycle_record.get("error", entry["detail"])

    if active:
        overall = "running"
    elif any(entry["status"] == "failed" for entry in entries):
        overall = "failed"
    elif next((entry for entry in entries if entry["step"] == "translate"), {}).get("status") == "complete":
        overall = "complete"
    else:
        overall = "idle"
    return {
        "schema_version": 1,
        "book_id": cfg.book_id,
        "overall": overall,
        "active_step": active,
        "updated_at": lifecycle.get("updated_at") if isinstance(lifecycle, dict) else None,
        "steps": entries,
    }


def render_snapshot(snapshot: dict) -> str:
    symbols = {"complete": "✓", "running": "▶", "failed": "✗", "pending": "○"}
    lines = [
        f"Book: {snapshot['book_id']}",
        f"Pipeline: {snapshot['overall']}"
        + (f" (active: {snapshot['active_step']})" if snapshot.get("active_step") else ""),
        "",
    ]
    width = max(len(entry["step"]) for entry in snapshot["steps"])
    for entry in snapshot["steps"]:
        tail = " · ".join(value for value in (entry["progress"], entry["detail"]) if value)
        lines.append(
            f"{symbols.get(entry['status'], '?')} {entry['step']:<{width}}  {entry['status']:<8}"
            + (f"  {tail}" if tail else "")
        )
    return "\n".join(lines)
