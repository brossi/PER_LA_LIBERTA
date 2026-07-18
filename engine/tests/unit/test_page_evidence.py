from __future__ import annotations

import hashlib

import pytest

from engine.config.loader import load_book
from engine.errors import ReconciliationAdmissionError, StaleArtifactError
from engine.lang.registry import get_language_plugin
from engine.paths import BookWorkspace
from engine.steps import ingest_gate, reconcile
from engine.structure.page_evidence import (
    PIPELINE_FINGERPRINT_SCHEME,
    REVIEW_FINGERPRINT_SCHEME,
    VERDICTS_SCHEMA_VERSION,
    VERDICTS_STALE_CLASS,
    assert_reconciliation_admission,
    build_page_evidence,
    record_page_verdict,
    verdicts_path,
)
from engine.structure import page_evidence_presence_shadow as presence_shadow
from engine.util.jsonio import atomic_write_json, read_json


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _assessment(page: int) -> dict:
    return {
        "status": "available",
        "provider": {
            "provider_id": "book_layout_sidecar",
            "provider_version": "0.1.4",
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
        atomic_write_json(
            geometry,
            {
                "page": page,
                "geometry": {"width": 100.0, "height": 160.0, "words": []},
            },
        )
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
                "evidence_fingerprint_scheme": REVIEW_FINGERPRINT_SCHEME,
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


def test_v1_pipeline_fingerprint_verdict_is_migrated_in_memory(tmp_path):
    cfg, ws = _setup(tmp_path)
    first = build_page_evidence(workspace=ws, cfg=cfg, max_review_pages=2)
    page = read_json(first["review"])["pages"][0]
    path = verdicts_path(ws, witness_id="copy1")
    path.parent.mkdir(parents=True)
    atomic_write_json(path, {
        "schema_version": 1,
        "stale_class": VERDICTS_STALE_CLASS,
        "book_id": cfg.book_id,
        "witness_id": "copy1",
        "verdicts": [{
            "page": page["page"],
            "disposition": "blank",
            "evidence_sha256": page["pipeline_evidence_sha256"],
            "reviewer": "fixture-reviewer",
            "decided_at": "2026-07-12T00:00:00Z",
        }],
    })

    result = build_page_evidence(workspace=ws, cfg=cfg, max_review_pages=2)
    ledger_page = read_json(result["ledger"])["pages"][2]

    assert result["review_pages"] == 1
    assert ledger_page["reasons"] == ["human_verdict"]
    assert ledger_page["human_verdict"]["evidence_fingerprint_scheme"] == (
        PIPELINE_FINGERPRINT_SCHEME
    )


def test_v1_review_fingerprint_is_not_reinterpreted_as_pipeline_fingerprint(tmp_path):
    cfg, ws = _setup(tmp_path)
    first = build_page_evidence(workspace=ws, cfg=cfg, max_review_pages=2)
    page = read_json(first["review"])["pages"][0]
    path = verdicts_path(ws, witness_id="copy1")
    path.parent.mkdir(parents=True)
    atomic_write_json(path, {
        "schema_version": 1,
        "stale_class": VERDICTS_STALE_CLASS,
        "book_id": cfg.book_id,
        "witness_id": "copy1",
        "verdicts": [{
            "page": page["page"],
            "disposition": "blank",
            "evidence_sha256": page["evidence_sha256"],
            "reviewer": "fixture-reviewer",
            "decided_at": "2026-07-12T00:00:00Z",
        }],
    })

    result = build_page_evidence(workspace=ws, cfg=cfg, max_review_pages=2)
    review_page = read_json(result["review"])["pages"][0]

    assert result["review_pages"] == 2
    assert review_page["reasons"][0] == "stale_human_verdict"


def test_recording_new_verdict_persists_v1_migration_as_v2(tmp_path):
    cfg, ws = _setup(tmp_path)
    first = build_page_evidence(workspace=ws, cfg=cfg, max_review_pages=2)
    pages = read_json(first["review"])["pages"]
    path = verdicts_path(ws, witness_id="copy1")
    path.parent.mkdir(parents=True)
    atomic_write_json(path, {
        "schema_version": 1,
        "stale_class": VERDICTS_STALE_CLASS,
        "book_id": cfg.book_id,
        "witness_id": "copy1",
        "verdicts": [{
            "page": pages[0]["page"],
            "disposition": "blank",
            "evidence_sha256": pages[0]["pipeline_evidence_sha256"],
            "reviewer": "fixture-reviewer",
            "decided_at": "2026-07-12T00:00:00Z",
        }],
    })
    migrated = build_page_evidence(workspace=ws, cfg=cfg, max_review_pages=2)
    pending = read_json(migrated["review"])["pages"][0]

    record_page_verdict(
        workspace=ws,
        cfg=cfg,
        witness_id="copy1",
        model="flash",
        page=pending["page"],
        disposition="content",
        evidence_sha256=pending["evidence_sha256"],
        reviewer="fixture-reviewer",
        decided_at="2026-07-12T01:00:00Z",
        max_review_pages=2,
    )

    document = read_json(path)
    assert document["schema_version"] == VERDICTS_SCHEMA_VERSION
    assert [item["evidence_fingerprint_scheme"] for item in document["verdicts"]] == [
        PIPELINE_FINGERPRINT_SCHEME,
        REVIEW_FINGERPRINT_SCHEME,
    ]


def test_v2_verdict_requires_an_explicit_fingerprint_scheme(tmp_path):
    cfg, ws = _setup(tmp_path)
    first = build_page_evidence(workspace=ws, cfg=cfg, max_review_pages=2)
    page = read_json(first["review"])["pages"][0]
    path = verdicts_path(ws, witness_id="copy1")
    path.parent.mkdir(parents=True)
    atomic_write_json(path, {
        "schema_version": VERDICTS_SCHEMA_VERSION,
        "stale_class": VERDICTS_STALE_CLASS,
        "book_id": cfg.book_id,
        "witness_id": "copy1",
        "verdicts": [{
            "page": page["page"],
            "disposition": "blank",
            "evidence_sha256": page["evidence_sha256"],
            "reviewer": "fixture-reviewer",
            "decided_at": "2026-07-12T00:00:00Z",
        }],
    })

    with pytest.raises(StaleArtifactError, match="human verdict document is malformed"):
        build_page_evidence(workspace=ws, cfg=cfg, max_review_pages=2)


@pytest.mark.parametrize(
    ("provenance", "expected"),
    (
        (None, False),
        ({}, False),
        ({"kind": "primary_provider"}, False),
        ({"kind": "provider_refusal_fallback_candidate"}, False),
        ({"kind": ["provider_refusal_fallback"]}, False),
        ({"kind": "provider_refusal_fallback"}, True),
        ({"kind": "explicit_recitation_fallback"}, True),
    ),
)
def test_page_evidence_uses_explicit_ocr_fallback_provenance(
    tmp_path, provenance, expected
):
    cfg, ws = _setup(tmp_path)
    ocr_path = ws.state / "ocr_flash_pages/page_0001.json"
    ocr = read_json(ocr_path)
    if provenance is not None:
        ocr["provenance"] = provenance
    atomic_write_json(ocr_path, ocr)

    result = build_page_evidence(workspace=ws, cfg=cfg, max_review_pages=2)
    ledger = read_json(result["ledger"])

    assert ledger["pages"][0]["signals"]["ocr_fallback"] is expected


def test_ingest_gate_presence_shadow_failure_cannot_change_admission(tmp_path):
    cfg, ws = _setup(tmp_path)
    lang = get_language_plugin(cfg.language_id)

    def unavailable_observer(**kwargs):
        raise RuntimeError("shadow provider unavailable")

    result = ingest_gate.run(
        workspace=ws,
        cfg=cfg,
        lang=lang,
        max_review_pages=2,
        presence_observer=unavailable_observer,
    )

    assert result["status"] == "review_required"
    assert result["review_pages"] == 2
    assert result["presence_shadow"]["status"] == "unavailable"
    assert result["presence_shadow"]["ledger"]["sha256"] == _sha(
        ws.data / "page_evidence/copy1/ledger.json"
    )
    assert result["presence_shadow"]["failure"] == {
        "code": "engine_error",
        "type": "RuntimeError",
        "message": "shadow provider unavailable",
    }


def test_ingest_gate_replaces_prior_success_when_ledger_build_fails(tmp_path, monkeypatch):
    cfg, ws = _setup(tmp_path)
    lang = get_language_plugin(cfg.language_id)
    first = ingest_gate.run(
        workspace=ws,
        cfg=cfg,
        lang=lang,
        max_review_pages=2,
    )
    assert first["presence_shadow"]["status"] == "complete"

    def fail_build(**kwargs):
        raise RuntimeError("ledger build failed")

    monkeypatch.setattr(ingest_gate, "build_page_evidence", fail_build)
    with pytest.raises(RuntimeError, match="ledger build failed"):
        ingest_gate.run(
            workspace=ws,
            cfg=cfg,
            lang=lang,
            max_review_pages=2,
        )

    report = read_json(
        ws.data / "layout_assessment/copy1/page_evidence_presence_report.json"
    )
    assert report["status"] == "unavailable"
    assert report["ledger"] is None
    assert report["failure"]["type"] == "RuntimeError"


def test_ingest_gate_observes_new_ledger_before_raising_review_bound(tmp_path):
    cfg, ws = _setup(tmp_path)
    lang = get_language_plugin(cfg.language_id)
    first = ingest_gate.run(
        workspace=ws,
        cfg=cfg,
        lang=lang,
        max_review_pages=2,
    )
    old_report_sha = first["presence_shadow"]["ledger"]["sha256"]

    with pytest.raises(ReconciliationAdmissionError, match="exceeds bound 1"):
        ingest_gate.run(
            workspace=ws,
            cfg=cfg,
            lang=lang,
            max_review_pages=1,
        )

    ledger = ws.data / "page_evidence/copy1/ledger.json"
    report = read_json(
        ws.data / "layout_assessment/copy1/page_evidence_presence_report.json"
    )
    assert report["status"] == "complete"
    assert report["ledger"]["sha256"] == _sha(ledger)
    assert report["ledger"]["sha256"] != old_report_sha


def test_presence_report_storage_failure_cannot_change_admission(tmp_path, monkeypatch):
    cfg, ws = _setup(tmp_path)
    lang = get_language_plugin(cfg.language_id)

    def fail_write(*args, **kwargs):
        raise OSError("presence report is read-only")

    monkeypatch.setattr(presence_shadow, "atomic_write_json", fail_write)
    result = ingest_gate.run(
        workspace=ws,
        cfg=cfg,
        lang=lang,
        max_review_pages=2,
    )

    assert result["status"] == "review_required"
    assert result["presence_shadow"]["status"] == "unavailable"
    assert result["presence_shadow"]["persistence_failure"] == {
        "type": "OSError",
        "message": "presence report is read-only",
    }
    assert not presence_shadow.report_path(ws, witness_id="copy1").exists()


def test_malformed_presence_observer_result_cannot_change_admission(tmp_path):
    cfg, ws = _setup(tmp_path)
    lang = get_language_plugin(cfg.language_id)

    result = ingest_gate.run(
        workspace=ws,
        cfg=cfg,
        lang=lang,
        max_review_pages=2,
        presence_observer=lambda **kwargs: None,
    )

    assert result["status"] == "review_required"
    assert result["presence_shadow"]["status"] == "unavailable"
    assert result["presence_shadow"]["failure"] == {
        "code": "engine_error",
        "type": "TypeError",
        "message": "presence observer returned an invalid summary",
    }


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
    assert read_json(path)["verdicts"][0]["evidence_fingerprint_scheme"] == (
        REVIEW_FINGERPRINT_SCHEME
    )

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
                "evidence_fingerprint_scheme": REVIEW_FINGERPRINT_SCHEME,
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


def test_admission_rejects_ledger_without_current_fingerprint_contract(tmp_path):
    cfg, ws = _setup(tmp_path)
    first = build_page_evidence(workspace=ws, cfg=cfg, max_review_pages=2)
    review = read_json(first["review"])
    path = verdicts_path(ws, witness_id="copy1")
    path.parent.mkdir(parents=True)
    atomic_write_json(path, {
        "schema_version": VERDICTS_SCHEMA_VERSION,
        "stale_class": VERDICTS_STALE_CLASS,
        "book_id": cfg.book_id,
        "witness_id": "copy1",
        "evidence_fingerprint_scheme": REVIEW_FINGERPRINT_SCHEME,
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
    admitted = build_page_evidence(workspace=ws, cfg=cfg, max_review_pages=2)
    ledger_path = ws.resolve("data", "page_evidence", "copy1", "ledger.json")
    ledger = read_json(ledger_path)
    del ledger["evidence_fingerprint_scheme"]
    atomic_write_json(ledger_path, ledger)
    pointer_path = ws.state / "page_evidence_admission.json"
    pointer = read_json(pointer_path)
    pointer["ledger_sha256"] = _sha(ledger_path)
    atomic_write_json(pointer_path, pointer)

    assert admitted["status"] == "admitted"
    with pytest.raises(ReconciliationAdmissionError, match="partial or unresolved"):
        assert_reconciliation_admission(workspace=ws, cfg=cfg)


def test_changed_review_raster_returns_previous_human_verdict_to_review(tmp_path):
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
                "evidence_fingerprint_scheme": REVIEW_FINGERPRINT_SCHEME,
                "reviewer": "fixture-reviewer",
                "decided_at": "2026-07-12T00:00:00Z",
            }
            for page in review["pages"]
        ],
    })
    build_page_evidence(workspace=ws, cfg=cfg, max_review_pages=2)

    raster = ws.data / "raster/page_0003.png"
    raster.write_bytes(b"changed-review-raster")
    report_path = ws.data / "layout_assessment/copy1/run_report.json"
    report = read_json(report_path)
    report["geometry"]["page_artifacts"][2]["raster_sha256"] = _sha(raster)
    atomic_write_json(report_path, report)

    result = build_page_evidence(workspace=ws, cfg=cfg, max_review_pages=2)
    new_review = read_json(result["review"])
    assert result["review_pages"] == 1
    assert new_review["pages"][0]["page"] == 3
    assert new_review["pages"][0]["reasons"][0] == "stale_human_verdict"


def test_provider_only_assessment_change_preserves_human_review_specimen(tmp_path):
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
                "evidence_fingerprint_scheme": REVIEW_FINGERPRINT_SCHEME,
                "reviewer": "fixture-reviewer",
                "decided_at": "2026-07-12T00:00:00Z",
            }
            for page in review["pages"]
        ],
    })
    admitted = build_page_evidence(workspace=ws, cfg=cfg, max_review_pages=2)
    before = read_json(admitted["ledger"])["pages"][2]

    assessment_path = ws.data / "assessment/page_0003.json"
    assessment = read_json(assessment_path)
    assessment["provider_diagnostic"] = "changed without changing the review specimen"
    atomic_write_json(assessment_path, assessment)
    report_path = ws.data / "layout_assessment/copy1/run_report.json"
    report = read_json(report_path)
    report["geometry"]["page_artifacts"][2]["assessment_sha256"] = _sha(assessment_path)
    atomic_write_json(report_path, report)

    rebuilt = build_page_evidence(workspace=ws, cfg=cfg, max_review_pages=2)
    after = read_json(rebuilt["ledger"])["pages"][2]
    assert rebuilt["status"] == "admitted"
    assert after["reasons"] == ["human_verdict"]
    assert after["evidence_sha256"] == before["evidence_sha256"]
    assert after["pipeline_evidence_sha256"] != before["pipeline_evidence_sha256"]


def test_reconciliation_rejects_absent_ledger(tmp_path):
    cfg = load_book("synthetic")
    lang = get_language_plugin(cfg.language_id)
    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()

    with pytest.raises(ReconciliationAdmissionError, match="run --step ingest_gate"):
        reconcile.run(workspace=ws, cfg=cfg, lang=lang)
