"""First-class layout-shadow step: CLI-independent restart and failure contracts."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from types import SimpleNamespace

import fitz
import pytest

from engine.config.loader import load_book
from engine.errors import BackendError, InvalidInvocationError, MissingInputError, StaleArtifactError
from engine.lang.registry import get_language_plugin
from engine.paths import BookWorkspace
from engine.steps import layout_shadow
from engine.structure.geometry import PageGeometry, WordBox
from engine.util.jsonio import atomic_write_json, read_json


def _setup(tmp_path):
    cfg = load_book("synthetic")
    lang = get_language_plugin(cfg.language_id)
    ws = BookWorkspace.for_book("synthetic", tmp_path)
    book_dir = ws.root.parent
    ws.scans.mkdir(parents=True)
    pdf_path = ws.scans / cfg.manifest.scan.pdf
    document = fitz.open()
    for _ in range(cfg.manifest.scan.last_scan_page_default):
        document.new_page()
    document.save(pdf_path)
    document.close()
    digest = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    (book_dir / "resources.sha256").write_text(
        f"{digest}  scans/{cfg.manifest.scan.pdf}\n", encoding="utf-8"
    )
    return cfg, lang, ws


class _Backend:
    reads: list[int] = []
    renders: list[int] = []
    fail_page: int | None = None

    def __init__(self, pdf_path, *, language, dpi):
        self._pdf_path = pdf_path
        self._dpi = dpi
        self.engine_id = f"fake:{language}:{dpi}"
        self.backend_params = {"language": language, "dpi": dpi, "backend": "fake"}
        self.dropped_boxes = {}
        self.oob_boxes = {}

    def read_pages(self, first_page, last_page):
        assert first_page == last_page
        self.reads.append(first_page)
        if first_page == self.fail_page:
            raise RuntimeError("geometry backend down")
        yield PageGeometry(
            page=first_page,
            width=500.0,
            height=700.0,
            words=(WordBox(text="testo", bbox=(10.0, 20.0, 60.0, 35.0)),),
        )

    def render_page(self, page):
        self.renders.append(page)
        with fitz.open(self._pdf_path) as document:
            return document[page - 1].get_pixmap(
                dpi=self._dpi, colorspace=fitz.csGRAY, alpha=False
            )


def _observer(**kwargs):
    path = kwargs["workspace"].resolve(
        "data", "layout_assessment", kwargs["witness_id"],
        f"page_{kwargs['page_geometry'].page:04d}.json",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(path, {"status": "available", "page": kwargs["page_geometry"].page})
    return SimpleNamespace(
        status=layout_shadow.STATUS_AVAILABLE,
        bundle=SimpleNamespace(results=()),
        path=path,
    )


def _run(cfg, lang, ws, **overrides):
    values = {
        "workspace": ws,
        "cfg": cfg,
        "lang": lang,
        "tesseract_language": "ita",
        "dpi": 300,
        "witness_id": "copy1",
        "backend_factory": _Backend,
        "observer": _observer,
        "dependency_checker": lambda: None,
    }
    values.update(overrides)
    return layout_shadow.run(**values)


def test_layout_shadow_runs_all_pages_and_publishes_report(tmp_path):
    cfg, lang, ws = _setup(tmp_path)
    _Backend.reads = []
    _Backend.renders = []

    summary = _run(cfg, lang, ws)

    assert summary["pages"] == 4
    assert summary["word_boxes"] == 4
    assert summary["available_pages"] == 4
    assert _Backend.reads == [1, 2, 3, 4]
    assert _Backend.renders == [1, 2, 3, 4]
    report = read_json(ws.data / "layout_assessment/copy1/run_report.json")
    assert report["status"] == "complete"
    assert report["source"]["sha256"]
    assert report["geometry"]["page_count"] == 4
    assert report["assessment"]["density_evidence"] == {
        "raster_schema_version": 1,
        "raster_producer": "engine-pymupdf-raster-v1",
        "policy": None,
        "classified_pages": 0,
        "raw_only_pages": 4,
    }
    first_page = report["geometry"]["page_artifacts"][0]
    assert first_page["ink_fraction"] == 0.0
    assert first_page["density_label"] == "abstain"
    assert first_page["density_policy_applied"] is False
    assert (ws.root / first_page["raster_path"]).is_file()
    progress = read_json(ws.state / layout_shadow.PROGRESS_FILE)
    assert progress["status"] == "complete"
    assert progress["completed_pages"] == progress["total_pages"] == 4


def test_layout_shadow_resume_reuses_provenance_valid_geometry(tmp_path):
    cfg, lang, ws = _setup(tmp_path)
    _Backend.reads = []
    _Backend.renders = []
    _run(cfg, lang, ws)
    _run(cfg, lang, ws)
    assert _Backend.reads == [1, 2, 3, 4]
    assert _Backend.renders == [1, 2, 3, 4]


def test_layout_shadow_tampered_raster_invalidates_only_that_raster(tmp_path):
    cfg, lang, ws = _setup(tmp_path)
    _Backend.reads = []
    _Backend.renders = []
    _run(cfg, lang, ws)
    raster_path, _ = layout_shadow._raster_paths(ws, "copy1", 2)
    raster_path.write_bytes(b"tampered")

    _run(cfg, lang, ws)

    assert _Backend.reads == [1, 2, 3, 4]
    assert _Backend.renders == [1, 2, 3, 4, 2]


def test_layout_shadow_tampered_density_metadata_invalidates_raster(tmp_path):
    cfg, lang, ws = _setup(tmp_path)
    _Backend.reads = []
    _Backend.renders = []
    _run(cfg, lang, ws)
    _, record_path = layout_shadow._raster_paths(ws, "copy1", 3)
    record = read_json(record_path)
    record["ink_fraction"] = 0.5
    atomic_write_json(record_path, record)

    _run(cfg, lang, ws)

    assert _Backend.reads == [1, 2, 3, 4]
    assert _Backend.renders == [1, 2, 3, 4, 3]


def test_layout_shadow_applies_only_manifest_density_policy(tmp_path):
    cfg, lang, ws = _setup(tmp_path)
    calibrated = load_book("per_la_liberta").manifest.segmentation
    cfg = replace(cfg, manifest=replace(cfg.manifest, segmentation=calibrated))
    _Backend.reads = []
    _Backend.renders = []

    _run(cfg, lang, ws)

    report = read_json(ws.data / "layout_assessment/copy1/run_report.json")
    density_summary = report["assessment"]["density_evidence"]
    assert density_summary["policy"] == {
        "classifier_version": "density-bands-v1",
        "params": {
            "yield_content_min": 0.7,
            "box_content_min": 40,
            "ink_blank_max": 0.15,
            "ink_dark_min": 0.6,
            "confidence_margin": 0.05,
            "cover_edge_leaves": 7,
            "ink_saturation_min": 0.9,
        },
    }
    assert density_summary["classified_pages"] == 4
    assert density_summary["raw_only_pages"] == 0
    assert all(
        page["density_policy_applied"] is True
        for page in report["geometry"]["page_artifacts"]
    )


def test_layout_shadow_parameter_change_invalidates_geometry(tmp_path):
    cfg, lang, ws = _setup(tmp_path)
    _Backend.reads = []
    _run(cfg, lang, ws, dpi=300)
    _run(cfg, lang, ws, dpi=301)
    assert _Backend.reads == [1, 2, 3, 4, 1, 2, 3, 4]


def test_layout_shadow_backend_failure_is_typed_and_retains_report(tmp_path):
    cfg, lang, ws = _setup(tmp_path)
    _Backend.reads = []
    _Backend.fail_page = 2
    try:
        with pytest.raises(BackendError, match="layout shadow failed on page 2"):
            _run(cfg, lang, ws)
    finally:
        _Backend.fail_page = None

    report = read_json(ws.data / "layout_assessment/copy1/run_report.json")
    assert report["status"] == "geometry_failed"
    assert report["failure"] == {"page": 2, "type": "RuntimeError"}
    assert report["geometry"]["page_count"] == 1
    progress = read_json(ws.state / layout_shadow.PROGRESS_FILE)
    assert progress["status"] == "failed"
    assert progress["completed_pages"] == 1


def test_layout_shadow_missing_optional_dependency_is_typed_and_write_free(tmp_path, monkeypatch):
    cfg, lang, ws = _setup(tmp_path)
    monkeypatch.setattr(layout_shadow.importlib.util, "find_spec", lambda _name: None)

    with pytest.raises(MissingInputError, match="--extra assessment"):
        layout_shadow.run(
            workspace=ws,
            cfg=cfg,
            lang=lang,
            tesseract_language="ita",
            dpi=300,
        )
    assert not ws.root.exists()


@pytest.mark.parametrize(
    ("options", "message"),
    [
        ({"tesseract_language": None, "dpi": 300}, "--tesseract-language"),
        ({"tesseract_language": "ita", "dpi": 0}, "positive --dpi"),
        (
            {"tesseract_language": "ita", "dpi": 300, "witness_id": "../escape"},
            "--witness-id",
        ),
    ],
)
def test_layout_shadow_invalid_options_fail_before_writes(tmp_path, options, message):
    cfg, lang, ws = _setup(tmp_path)
    with pytest.raises(InvalidInvocationError, match=message):
        layout_shadow.run(workspace=ws, cfg=cfg, lang=lang, **options)
    assert not ws.root.exists()


def test_layout_shadow_rejects_scan_pin_drift(tmp_path):
    cfg, lang, ws = _setup(tmp_path)
    (ws.root.parent / "resources.sha256").write_text(
        f"{'0' * 64}  scans/{cfg.manifest.scan.pdf}\n", encoding="utf-8"
    )
    with pytest.raises(StaleArtifactError, match="scan SHA-256 differs"):
        _run(cfg, lang, ws)
