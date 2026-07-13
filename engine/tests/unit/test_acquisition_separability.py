"""Separability tier: acquisition runs the synthetic book and feeds M3's reconcile.

download (injected Fetcher) + ocr (injected PageRenderer + OcrBackend) produce ``copy{1,2,3}`` +
page map in ``work/data``; the existing synthetic ``reconcile`` then consumes them. The injected
backends are seeded from the frozen synthetic ``inputs/`` — those files are the *expected*
acquisition output read back as canned-response seed (BR-009/D6/BR-013): they are read, never
re-frozen. Per-page OCR responses come from splitting the frozen ``copy3`` on its ``⟨PAGE:N⟩``
markers (confirmed present in the fixture). This proves the acquisition→reconcile contract on
engine-produced witnesses, closing the producer/consumer inversion M3 left open.
"""

from __future__ import annotations

import pytest

from engine.config.loader import load_book
from engine.errors import MissingInputError
from engine.lang.registry import get_language_plugin
from engine.paths import BookWorkspace
from engine.steps import download, ocr, reconcile


def test_synthetic_acquisition_feeds_reconcile(tmp_path, monkeypatch, acq):
    monkeypatch.setattr(ocr, "_PAGE_DELAY", 0)
    cfg = load_book("synthetic")
    lang = get_language_plugin(cfg.language_id)
    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()

    # Fetcher seeded from the frozen djvu-text witnesses, keyed by the URL download computes.
    copy1 = (acq.inputs / "copy1_raw.txt").read_text(encoding="utf-8")
    copy2 = (acq.inputs / "copy2_raw.txt").read_text(encoding="utf-8")
    url_map = {
        download.source_url(s): (copy1 if s.role == "copy1" else copy2)
        for s in cfg.manifest.sources
    }
    download.run(workspace=ws, cfg=cfg, lang=lang, fetcher=acq.Fetcher(url_map))

    # OcrBackend seeded by splitting the frozen copy3 on its page markers.
    page_texts = acq.split((acq.inputs / "copy3_raw.txt").read_text(encoding="utf-8"))
    last = max(page_texts)
    ocr.run(
        workspace=ws, cfg=cfg, lang=lang, model="pro", pages=(1, last),
        renderer=acq.Renderer(last), backend=acq.Backend(page_texts),
    )

    # The produced witnesses are exactly the names reconcile reads.
    for name in ("copy1_raw.txt", "copy2_raw.txt", "copy3_raw.txt", "copy3_pro_page_map.json"):
        assert (ws.data / name).is_file(), name

    result = reconcile.run(
        workspace=ws, cfg=cfg, lang=lang, admission_checker=lambda **_: None
    )
    assert result["mode"] == "3-way"           # copy3 was produced and picked up
    assert result["chapters"] >= 2
    assert (ws.data / "reconciled_chapters.json").is_file()
    assert (ws.data / "flagged_segments.json").is_file()


def test_download_then_reconcile_without_ocr_is_two_way(tmp_path, acq):
    # Acquisition is composable: download alone (no ocr) → reconcile falls back to 2-way, proving
    # copy3 is genuinely optional and the produced copy{1,2} suffice.
    cfg = load_book("synthetic")
    lang = get_language_plugin(cfg.language_id)
    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()
    copy1 = (acq.inputs / "copy1_raw.txt").read_text(encoding="utf-8")
    copy2 = (acq.inputs / "copy2_raw.txt").read_text(encoding="utf-8")
    url_map = {
        download.source_url(s): (copy1 if s.role == "copy1" else copy2)
        for s in cfg.manifest.sources
    }
    download.run(workspace=ws, cfg=cfg, lang=lang, fetcher=acq.Fetcher(url_map))

    result = reconcile.run(
        workspace=ws, cfg=cfg, lang=lang, admission_checker=lambda **_: None
    )
    assert result["mode"] == "2-way"


def test_reconcile_without_copies_is_a_typed_missing_input_error(tmp_path):
    # The F7 fold-in: reconcile on an empty workspace (download not yet run) raises a typed
    # MissingInputError (CLI exit 3), not a bare FileNotFoundError.
    cfg = load_book("synthetic")
    lang = get_language_plugin(cfg.language_id)
    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()
    with pytest.raises(MissingInputError) as ei:
        reconcile.run(
            workspace=ws, cfg=cfg, lang=lang, admission_checker=lambda **_: None
        )
    assert ei.value.exit_code == 3
    assert "copy1_raw.txt" in str(ei.value)
