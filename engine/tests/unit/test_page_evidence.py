from __future__ import annotations

import hashlib

import pytest

from engine.config.loader import load_book
from engine.errors import ReconciliationAdmissionError, StaleArtifactError
from engine.lang.registry import get_language_plugin
from engine.paths import BookWorkspace
from engine.steps import reconcile
from engine.structure.page_evidence import (
    VERDICTS_SCHEMA_VERSION,
    VERDICTS_STALE_CLASS,
    assert_reconciliation_admission,
    build_page_evidence,
    record_page_verdict,
    verdicts_path,
)
from engine.util.jsonio import atomic_write_json, read_json


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _assessment(page: int) -> dict:
    return {
        "status": "available",
        "provider": {
            "provider_id": "book_layout_sidecar",
            "provider_version": "0.1.2",
        },
        "bundle": {
            "results": [
                {
                    "module_id": "ocr_text_likeness",
                    "execution_status": "completed",
                    "assessment": "supported",
                },
                {
                    "module_id": "near_blank_hallucinated_boxes",
                    "execution_status": "completed",
                    "assessment": "supported",
                },
            ]
        },
        "page": page,
    }


def _setup(tmp_path):
    cfg = load_book("synthetic")
    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()
    ws.scans.mkdir(parents=True)
    source = ws.scans / cfg.manifest.scan.pdf
    source.write_bytes(b"four-page-scan")
    pages = []
    texts = {1: "ordinary body text", 2: "[BLANK]", 3: "[BLANK]", 4: "body text"}
    for page in range(1, 5):
        raster = ws.resolve("data", "raster", f"page_{page:04d}.png")
        geometry = ws.resolve("data", "geometry", f"page_{page:04d}.json")
        assessment = ws.resolve("data", "assessment", f"page_{page:04d}.json")
        ocr = ws.resolve("state", "ocr_flash_pages", f"page_{page:04d}.json")
        for path in (raster, geometry, assessment, ocr):
            path.parent.mkdir(parents=True, exist_ok=True)
        raster.write_bytes(f"raster-{page}".encode())
        atomic_write_json(geometry, {"page": page})
        atomic_write_json(assessment, _assessment(page))
        atomic_write_json(ocr, {"page": page, "text": texts[page]})
        effective = 10 if page in {1, 3} else 0
        pages.append({
            "page": page,
            "word_count": effective,
            "effective_word_count": effective,
            "raster_path": str(raster.relative_to(ws.root)),
            "raster_sha256": _sha(raster),
            "geometry_path": str(geometry.relative_to(ws.root)),
            "geometry_sha256": _sha(geometry),
            "assessment_path": str(assessment.relative_to(ws.root)),
            "assessment_sha256": _sha(assessment),
            "retry_path": None,
            "retry_sha256": None,
            "retry_status": "unresolved" if page == 4 else "not_applicable",
            "retry_selected_path": "geometry_baseline",
            "retry_gate_reason": (
                "ocr_null_with_decisive_near_blank_evidence" if page == 2 else None
            ),
            "retry_text_verdict": "needs_review" if page == 4 else None,
            "ink_fraction": 0.001 if page == 2 else 0.08,
            "density_label": "abstain",
            "density_policy_applied": False,
        })
    report_path = ws.resolve("data", "layout_assessment", "copy1", "run_report.json")
    report_path.parent.mkdir(parents=True)
    atomic_write_json(report_path, {
        "schema_version": 3,
        "status": "complete",
        "book_id": cfg.book_id,
        "witness_id": "copy1",
        "source": {
            "sha256": _sha(source),
            "pages": 4,
        },
        "geometry": {"page_artifacts": pages},
    })
    return cfg, ws


def test_total_ledger_routes_contradictions_and_applies_bound_verdicts(tmp_path):
    cfg, ws = _setup(tmp_path)

    first = build_page_evidence(workspace=ws, cfg=cfg, max_review_pages=2)

    assert first["status"] == "review_required"
    assert first["counts"] == {
        "blank": 1,
        "content": 1,
        "non_text": 0,
        "review_required": 2,
    }
    review = read_json(first["review"])
    assert [page["page"] for page in review["pages"]] == [3, 4]
    with pytest.raises(ReconciliationAdmissionError, match="not admitted"):
        assert_reconciliation_admission(workspace=ws, cfg=cfg)

    path = verdicts_path(ws, witness_id="copy1")
    path.parent.mkdir(parents=True)
    atomic_write_json(path, {
        "schema_version": VERDICTS_SCHEMA_VERSION,
        "stale_class": VERDICTS_STALE_CLASS,
        "book_id": cfg.book_id,
        "witness_id": "copy1",
        "verdicts": [
            {
                "page": page["page"],
                "disposition": "blank" if page["page"] == 3 else "content",
                "evidence_sha256": page["evidence_sha256"],
                "reviewer": "fixture-reviewer",
                "decided_at": "2026-07-12T00:00:00Z",
            }
            for page in review["pages"]
        ],
    })
    second = build_page_evidence(workspace=ws, cfg=cfg, max_review_pages=2)

    assert second["status"] == "admitted"
    assert second["review_pages"] == 0
    ledger = assert_reconciliation_admission(workspace=ws, cfg=cfg)
    assert [page["disposition"] for page in ledger["pages"]] == [
        "content", "blank", "blank", "content"
    ]


def test_review_volume_exceeding_named_bound_fails_after_writing_packet(tmp_path):
    cfg, ws = _setup(tmp_path)

    with pytest.raises(ReconciliationAdmissionError, match="exceeds bound 1"):
        build_page_evidence(workspace=ws, cfg=cfg, max_review_pages=1)

    review = read_json(ws.data / "page_evidence/copy1/review.json")
    assert review["review_count"] == 2


def test_record_page_verdict_writes_tracked_decision_and_rejects_stale_submission(tmp_path):
    cfg, ws = _setup(tmp_path)
    first = build_page_evidence(workspace=ws, cfg=cfg, max_review_pages=2)
    item = read_json(first["review"])["pages"][0]

    with pytest.raises(StaleArtifactError, match="review evidence changed"):
        record_page_verdict(
            workspace=ws,
            cfg=cfg,
            witness_id="copy1",
            model="flash",
            page=item["page"],
            disposition="blank",
            evidence_sha256="0" * 64,
            reviewer="fixture-reviewer",
            max_review_pages=2,
        )
    assert not verdicts_path(ws, witness_id="copy1").exists()

    result = record_page_verdict(
        workspace=ws,
        cfg=cfg,
        witness_id="copy1",
        model="flash",
        page=item["page"],
        disposition="blank",
        evidence_sha256=item["evidence_sha256"],
        reviewer="fixture-reviewer",
        note="visual inspection",
        decided_at="2026-07-12T00:00:00Z",
        max_review_pages=2,
    )

    path = verdicts_path(ws, witness_id="copy1")
    assert path == ws.root.parent / "review/page_evidence/copy1/verdicts.json"
    assert result["review_pages"] == 1
    assert read_json(path)["verdicts"][0]["note"] == "visual inspection"

    corrected = record_page_verdict(
        workspace=ws,
        cfg=cfg,
        witness_id="copy1",
        model="flash",
        page=item["page"],
        disposition="content",
        evidence_sha256=item["evidence_sha256"],
        reviewer="fixture-reviewer",
        note="corrected after a second look",
        decided_at="2026-07-12T01:00:00Z",
        max_review_pages=2,
    )

    corrected_verdict = read_json(path)["verdicts"][0]
    assert corrected["review_pages"] == 1
    assert corrected_verdict["disposition"] == "content"
    assert corrected_verdict["note"] == "corrected after a second look"
    assert corrected_verdict["decided_at"] == "2026-07-12T01:00:00Z"


def test_record_page_verdict_rejects_automatically_admitted_page(tmp_path):
    cfg, ws = _setup(tmp_path)
    first = build_page_evidence(workspace=ws, cfg=cfg, max_review_pages=2)
    ledger = read_json(first["ledger"])
    admitted = next(page for page in ledger["pages"] if page["page"] == 1)

    with pytest.raises(StaleArtifactError, match="neither pending review nor an existing reviewed"):
        record_page_verdict(
            workspace=ws,
            cfg=cfg,
            witness_id="copy1",
            model="flash",
            page=1,
            disposition="blank",
            evidence_sha256=admitted["evidence_sha256"],
            reviewer="fixture-reviewer",
            max_review_pages=2,
        )
    assert not verdicts_path(ws, witness_id="copy1").exists()


def test_admission_detects_post_ledger_evidence_drift(tmp_path):
    cfg, ws = _setup(tmp_path)
    first = build_page_evidence(workspace=ws, cfg=cfg, max_review_pages=2)
    review = read_json(first["review"])
    verdict_path = verdicts_path(ws, witness_id="copy1")
    verdict_path.parent.mkdir(parents=True)
    atomic_write_json(verdict_path, {
        "schema_version": VERDICTS_SCHEMA_VERSION,
        "stale_class": VERDICTS_STALE_CLASS,
        "book_id": cfg.book_id,
        "witness_id": "copy1",
        "verdicts": [
            {
                "page": page["page"],
                "disposition": "blank",
                "evidence_sha256": page["evidence_sha256"],
                "reviewer": "fixture-reviewer",
                "decided_at": "2026-07-12T00:00:00Z",
            }
            for page in review["pages"]
        ],
    })
    build_page_evidence(workspace=ws, cfg=cfg, max_review_pages=2)
    checkpoint = ws.state / "ocr_flash_pages/page_0001.json"
    checkpoint.write_bytes(checkpoint.read_bytes() + b" ")

    with pytest.raises(ReconciliationAdmissionError, match="page 1 evidence changed"):
        assert_reconciliation_admission(workspace=ws, cfg=cfg)


def test_changed_evidence_returns_previous_human_verdict_to_review(tmp_path):
    cfg, ws = _setup(tmp_path)
    first = build_page_evidence(workspace=ws, cfg=cfg, max_review_pages=2)
    review = read_json(first["review"])
    verdict_path = verdicts_path(ws, witness_id="copy1")
    verdict_path.parent.mkdir(parents=True)
    atomic_write_json(verdict_path, {
        "schema_version": VERDICTS_SCHEMA_VERSION,
        "stale_class": VERDICTS_STALE_CLASS,
        "book_id": cfg.book_id,
        "witness_id": "copy1",
        "verdicts": [
            {
                "page": page["page"],
                "disposition": "blank",
                "evidence_sha256": page["evidence_sha256"],
                "reviewer": "fixture-reviewer",
                "decided_at": "2026-07-12T00:00:00Z",
            }
            for page in review["pages"]
        ],
    })
    build_page_evidence(workspace=ws, cfg=cfg, max_review_pages=2)

    geometry = ws.data / "geometry/page_0003.json"
    atomic_write_json(geometry, {"page": 3, "changed": True})
    report_path = ws.data / "layout_assessment/copy1/run_report.json"
    report = read_json(report_path)
    report["geometry"]["page_artifacts"][2]["geometry_sha256"] = _sha(geometry)
    atomic_write_json(report_path, report)

    result = build_page_evidence(workspace=ws, cfg=cfg, max_review_pages=2)
    new_review = read_json(result["review"])
    assert result["review_pages"] == 1
    assert new_review["pages"][0]["page"] == 3
    assert new_review["pages"][0]["reasons"][0] == "stale_human_verdict"


def test_reconciliation_rejects_absent_ledger(tmp_path):
    cfg = load_book("synthetic")
    lang = get_language_plugin(cfg.language_id)
    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()

    with pytest.raises(ReconciliationAdmissionError, match="run --step ingest_gate"):
        reconcile.run(workspace=ws, cfg=cfg, lang=lang)
