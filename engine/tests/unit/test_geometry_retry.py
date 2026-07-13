from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from engine.paths import BookWorkspace
from engine.structure.geometry import PageGeometry, WordBox
from engine.structure.geometry_retry import (
    STATUS_NOT_APPLICABLE,
    STATUS_SELECTED,
    STATUS_UNRESOLVED,
    observe_geometry_retry,
)
from engine.util.jsonio import read_json
from engine.structure.layout_assessment_shadow import PageDensityEvidence, PageRasterEvidence

sidecar = pytest.importorskip("book_layout_sidecar")


def _geometry(*, words: tuple[WordBox, ...] = ()) -> PageGeometry:
    return PageGeometry(page=1, width=500.0, height=700.0, words=words)


def _raster(tmp_path: Path, *, ink_fraction: float) -> tuple[Path, PageRasterEvidence]:
    path = tmp_path / "page_0001.png"
    image = Image.new("L", (500, 700), 245)
    draw = ImageDraw.Draw(image)
    draw.text((50, 50), "fixture", fill=20)
    image.save(path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return path, PageRasterEvidence(
        page=1,
        artifact_ref="scan:fixture/book.pdf#page=1:raster=copy1:dpi=300",
        sha256=digest,
        source_selector="page=1",
        producer="fixture-raster",
        dpi=300,
        width_px=500,
        height_px=700,
        ink_fraction=ink_fraction,
    )


def _density(*, ink_fraction: float) -> PageDensityEvidence:
    return PageDensityEvidence(
        page=1,
        box_count=0,
        token_yield=0.0,
        mean_token_length=0.0,
        label="abstain",
        confidence=0.0,
        hint="density_policy_absent",
        producer="fixture-density",
        policy_applied=False,
    )


def _execution(image_path: Path, *, texts: tuple[str, ...]):
    from book_layout_sidecar.adapters.tesseract_ocr import (
        OcrExecutionEvidence,
        OcrExecutionResult,
    )
    from book_layout_sidecar.core.ocr import BoundingBox, OcrBox, OcrPage

    boxes = tuple(
        OcrBox(
            page=1,
            text=text,
            bbox=BoundingBox(20.0, 20.0 + i * 12.0, 100.0, 30.0 + i * 12.0),
            confidence=0.95,
            source_format="fixture",
            source_ref=str(image_path),
            source_selector=f"word={i}",
        )
        for i, text in enumerate(texts)
    )
    producer = "fixture-tesseract"
    page = OcrPage(
        page=1,
        width=500.0,
        height=700.0,
        boxes=boxes,
        source_format="fixture",
        source_ref=str(image_path),
        source_selector="page=1",
        producer=producer,
    )
    evidence = OcrExecutionEvidence(
        record_version=1,
        status="success",
        page=1,
        image_ref=str(image_path),
        command=("fixture-tesseract", str(image_path)),
        lang="ita",
        psm=3,
        timeout_seconds=30.0,
        elapsed_seconds=0.01,
        producer=producer,
        returncode=0,
    )
    return OcrExecutionResult(evidence=evidence, page=page)


def _observe(tmp_path: Path, monkeypatch, *, ink_fraction: float, retry_texts: tuple[str, ...]):
    ws = BookWorkspace.for_book("fixture", tmp_path).ensure()
    raster_path, raster = _raster(tmp_path, ink_fraction=ink_fraction)
    calls: list[Path] = []

    def execute(image_path: Path, **kwargs):
        calls.append(image_path)
        texts = retry_texts if "adaptive_bw" in image_path.name else ()
        return _execution(image_path, texts=texts)

    monkeypatch.setattr(
        "book_layout_sidecar.adapters.tesseract_ocr.execute_tesseract_tsv", execute
    )
    result = observe_geometry_retry(
        workspace=ws,
        witness_id="copy1",
        source_ref="scan:fixture/book.pdf",
        source_sha256="a" * 64,
        raster_path=raster_path,
        raster_evidence=raster,
        density_evidence=_density(ink_fraction=ink_fraction),
        page_geometry=_geometry(),
        geometry_engine_id="fixture-pdf-geometry",
        tesseract_language="ita",
    )
    return result, calls


def test_non_null_geometry_never_loads_or_runs_retry(tmp_path):
    ws = BookWorkspace.for_book("fixture", tmp_path).ensure()
    result = observe_geometry_retry(
        workspace=ws,
        witness_id="copy1",
        source_ref="scan:fixture/book.pdf",
        source_sha256="a" * 64,
        raster_path=tmp_path / "missing.png",
        raster_evidence=object(),
        density_evidence=object(),
        page_geometry=_geometry(
            words=tuple(
                WordBox(text=f"word{i}", bbox=(10.0, 10.0 + i * 20, 60.0, 20.0 + i * 20))
                for i in range(3)
            )
        ),
        geometry_engine_id="fixture-pdf-geometry",
        tesseract_language="ita",
    )

    assert result.status == STATUS_NOT_APPLICABLE
    assert result.path is None
    assert result.selected_geometry_engine_id == "fixture-pdf-geometry"


def test_active_ocr_null_page_selects_only_trusted_adaptive_text(tmp_path, monkeypatch):
    result, calls = _observe(
        tmp_path,
        monkeypatch,
        ink_fraction=0.08,
        retry_texts=tuple(f"parola{i}" for i in range(30)),
    )

    assert result.status == STATUS_SELECTED
    assert result.selected_path == "adaptive_bw"
    assert result.retry_box_count == 30
    assert result.retry_text_verdict == "trusted_text"
    assert result.selected_geometry_engine_id == "fixture-tesseract"
    assert len(result.selected_geometry.words) == 30
    assert len(calls) == 2


def test_decisive_blank_skips_adaptive_retry(tmp_path, monkeypatch):
    result, calls = _observe(
        tmp_path,
        monkeypatch,
        ink_fraction=0.001,
        retry_texts=tuple(f"parola{i}" for i in range(30)),
    )

    assert result.status == STATUS_NOT_APPLICABLE
    assert result.selected_path == "geometry_baseline"
    assert result.gate_reason == "ocr_null_with_decisive_near_blank_evidence"
    assert len(calls) == 1


def test_more_retry_boxes_without_trusted_text_remain_unresolved(tmp_path, monkeypatch):
    result, calls = _observe(
        tmp_path,
        monkeypatch,
        ink_fraction=0.08,
        retry_texts=tuple("x" for _ in range(13)),
    )

    assert result.status == STATUS_UNRESOLVED
    assert result.selected_path == "geometry_baseline"
    assert result.retry_box_count == 13
    assert result.retry_text_verdict != "trusted_text"
    assert len(calls) == 2


def test_identical_retry_reuses_hash_valid_checkpoint(tmp_path, monkeypatch):
    first, calls = _observe(
        tmp_path,
        monkeypatch,
        ink_fraction=0.08,
        retry_texts=tuple(f"parola{i}" for i in range(30)),
    )
    assert len(calls) == 2

    def unexpected_execution(*args, **kwargs):
        raise AssertionError("current retry checkpoint should avoid OCR execution")

    monkeypatch.setattr(
        "book_layout_sidecar.adapters.tesseract_ocr.execute_tesseract_tsv",
        unexpected_execution,
    )
    ws = BookWorkspace.for_book("fixture", tmp_path).ensure()
    raster_path, raster = _raster(tmp_path, ink_fraction=0.08)
    second = observe_geometry_retry(
        workspace=ws,
        witness_id="copy1",
        source_ref="scan:fixture/book.pdf",
        source_sha256="a" * 64,
        raster_path=raster_path,
        raster_evidence=raster,
        density_evidence=_density(ink_fraction=0.08),
        page_geometry=_geometry(),
        geometry_engine_id="fixture-pdf-geometry",
        tesseract_language="ita",
    )

    assert second.cached is True
    assert second.selected_path == first.selected_path == "adaptive_bw"
    assert second.selected_geometry == first.selected_geometry


def test_changed_transform_invalidates_retry_checkpoint(tmp_path, monkeypatch):
    _observe(
        tmp_path,
        monkeypatch,
        ink_fraction=0.08,
        retry_texts=tuple(f"parola{i}" for i in range(30)),
    )
    monkeypatch.setattr("engine.structure.geometry_retry.RETRY_TRANSFORM", "background_normalize")
    ws = BookWorkspace.for_book("fixture", tmp_path).ensure()
    raster_path, raster = _raster(tmp_path, ink_fraction=0.08)
    calls: list[Path] = []

    def execute(image_path: Path, **kwargs):
        calls.append(image_path)
        return _execution(image_path, texts=())

    monkeypatch.setattr(
        "book_layout_sidecar.adapters.tesseract_ocr.execute_tesseract_tsv", execute
    )
    result = observe_geometry_retry(
        workspace=ws,
        witness_id="copy1",
        source_ref="scan:fixture/book.pdf",
        source_sha256="a" * 64,
        raster_path=raster_path,
        raster_evidence=raster,
        density_evidence=_density(ink_fraction=0.08),
        page_geometry=_geometry(),
        geometry_engine_id="fixture-pdf-geometry",
        tesseract_language="ita",
    )

    assert result.cached is False
    assert len(calls) == 2


def test_tampered_retry_ocr_evidence_invalidates_checkpoint(tmp_path, monkeypatch):
    first, _ = _observe(
        tmp_path,
        monkeypatch,
        ink_fraction=0.08,
        retry_texts=tuple(f"parola{i}" for i in range(30)),
    )
    record = read_json(first.path)
    record["retry_page"]["boxes"][0]["text"] = "tampered"
    first.path.write_text(json.dumps(record), encoding="utf-8")
    calls: list[Path] = []

    def execute(image_path: Path, **kwargs):
        calls.append(image_path)
        texts = tuple(f"parola{i}" for i in range(30)) if "adaptive_bw" in image_path.name else ()
        return _execution(image_path, texts=texts)

    monkeypatch.setattr(
        "book_layout_sidecar.adapters.tesseract_ocr.execute_tesseract_tsv", execute
    )
    ws = BookWorkspace.for_book("fixture", tmp_path).ensure()
    raster_path, raster = _raster(tmp_path, ink_fraction=0.08)
    result = observe_geometry_retry(
        workspace=ws,
        witness_id="copy1",
        source_ref="scan:fixture/book.pdf",
        source_sha256="a" * 64,
        raster_path=raster_path,
        raster_evidence=raster,
        density_evidence=_density(ink_fraction=0.08),
        page_geometry=_geometry(),
        geometry_engine_id="fixture-pdf-geometry",
        tesseract_language="ita",
    )

    assert result.cached is False
    assert len(calls) == 2
