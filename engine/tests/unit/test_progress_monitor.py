"""Pipeline monitor contracts: lifecycle truth overrides reconstructable artifact status."""

from __future__ import annotations

import json

from engine.config.loader import load_book
from engine.paths import BookWorkspace
from engine.progress import PipelineTracker, pipeline_snapshot, render_snapshot


def _write(path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_tracker_records_running_complete_and_failed_lifecycle(tmp_path):
    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()
    tracker = PipelineTracker(ws)
    tracker.start_step("ocr")
    state = json.loads(tracker.path.read_text())
    assert state["active_step"] == "ocr"
    assert state["steps"]["ocr"]["status"] == "running"

    tracker.complete_step("ocr", {"pages": 4})
    state = json.loads(tracker.path.read_text())
    assert state["active_step"] is None
    assert state["steps"]["ocr"]["summary"] == {"pages": 4}

    tracker.start_step("validate")
    tracker.fail_step("validate", "bad text")
    state = json.loads(tracker.path.read_text())
    assert state["run_status"] == "failed"
    assert state["steps"]["validate"]["error"] == "bad text"


def test_snapshot_reconstructs_long_step_counts_and_exact_page_progress(tmp_path):
    cfg = load_book("synthetic")
    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()
    _write(ws.data / "layout_assessment/copy1/run_report.json", {
        "status": "complete",
        "geometry": {"page_count": 4, "word_count": 90, "oob_box_count": 1},
    })
    for source in cfg.manifest.sources:
        (ws.data / f"{source.role}_raw.txt").write_text("source", encoding="utf-8")
    for page in range(1, 5):
        _write(ws.state / f"ocr_flash_pages/page_{page:04d}.json", {"page": page})
    (ws.data / "copy3_flash.txt").write_text("ocr", encoding="utf-8")
    _write(ws.data / "reconciled_chapters.json", [
        {"id": "a", "part": 0}, {"id": "b", "part": 1}, {"id": "c", "part": 1},
    ])
    _write(ws.data / "flagged_segments.json", [{}, {}])
    _write(ws.state / "triage_progress.json", {
        "status": "running", "total_items": 10, "completed_items": 5,
        "total_batches": 2, "completed_batches": 1,
    })
    (ws.output / "clean.md").write_text("clean", encoding="utf-8")
    _write(ws.data / "validation_report.json", {"overall": "pass"})
    _write(ws.state / "translation_progress.json", {
        "a": {"status": "done"}, "b": {"status": "done"}, "c": {"status": "done"},
    })
    (ws.output / "english_translation.md").write_text("english", encoding="utf-8")
    _write(ws.data / "gutenberg_evaluation.json", {
        "status": "diagnostic_complete", "overall": {"word_error_rate": 0.02},
    })

    snapshot = pipeline_snapshot(ws, cfg)
    by_step = {entry["step"]: entry for entry in snapshot["steps"]}
    assert by_step["ocr"]["progress"] == "4/4 pages"
    assert by_step["triage"]["progress"] == "5/10 items"
    assert by_step["translate"]["status"] == "complete"
    assert by_step["evaluation"]["detail"] == "token WER 2.00%"
    assert "▶ triage" in render_snapshot(snapshot)


def test_lifecycle_failure_overrides_old_success_artifact(tmp_path):
    cfg = load_book("synthetic")
    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()
    _write(ws.data / "validation_report.json", {"overall": "pass"})
    tracker = PipelineTracker(ws)
    tracker.start_step("validate")
    tracker.fail_step("validate", "new validation failed")

    snapshot = pipeline_snapshot(ws, cfg)
    validate = next(entry for entry in snapshot["steps"] if entry["step"] == "validate")
    assert validate["status"] == "failed"
    assert validate["detail"] == "new validation failed"


def test_layout_shadow_reports_exact_in_progress_page_count(tmp_path):
    cfg = load_book("synthetic")
    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()
    _write(ws.data / "layout_assessment/old/run_report.json", {
        "status": "complete",
        "geometry": {"page_count": 4, "word_count": 90, "oob_box_count": 0},
    })
    _write(ws.state / "layout_shadow_progress.json", {
        "status": "running",
        "witness_id": "copy2",
        "completed_pages": 2,
        "total_pages": 4,
    })
    PipelineTracker(ws).start_step("layout_shadow")

    snapshot = pipeline_snapshot(ws, cfg)
    layout = next(entry for entry in snapshot["steps"] if entry["step"] == "layout_shadow")
    assert layout == {
        "step": "layout_shadow",
        "status": "running",
        "progress": "2/4 pages",
        "detail": "copy2",
    }


def test_layout_shadow_complete_with_unavailable_is_complete(tmp_path):
    cfg = load_book("synthetic")
    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()
    _write(ws.data / "layout_assessment/copy1/run_report.json", {
        "status": "complete_with_unavailable",
        "geometry": {"page_count": 4, "word_count": 80, "oob_box_count": 2},
        "assessment": {"unavailable_pages": [3]},
    })

    snapshot = pipeline_snapshot(ws, cfg)
    layout = next(entry for entry in snapshot["steps"] if entry["step"] == "layout_shadow")
    assert layout["status"] == "complete"
    assert layout["progress"] == "4/4 pages"
    assert layout["detail"] == "80 boxes; 2 OOB; 1 unavailable"
