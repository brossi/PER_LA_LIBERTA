"""Golden reproduction — the engine ``reconcile`` step, run on the frozen OCR copies, must
reproduce what the live ``reconcile.py`` produced (frozen by ``_generate_reconcile_fixture.py``).

Per ENGINE_M3_PLAN.md D1/F1 the reference is **generated from live code**, never the hand-edited
``data/reconciled_chapters.json``. The three JSON artifacts are compared as *parsed data*
(formatting-agnostic — the data is the contract, not the indentation); ``reconciled_raw.txt`` is
compared as exact text (D4).

Determinism: reconcile's near-duplicate gate uses ``rapidfuzz.fuzz``; the engine depends on the
same rapidfuzz version that generated the fixtures (``pyproject.toml`` + the lockfile), so
``fuzz.ratio`` is stable. No spaCy is involved (reconcile has no NER pass).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.config.loader import load_book
from engine.lang.registry import get_language_plugin
from engine.paths import BookWorkspace
from engine.steps import reconcile

GOLDEN_DIR = Path(__file__).resolve().parent
ENGINE_ROOT = GOLDEN_DIR.parents[1]
INPUTS = ENGINE_ROOT / "books" / "per_la_liberta" / "inputs"
DATA = GOLDEN_DIR / "data"

pytestmark = pytest.mark.golden

_INPUT_FILES = [
    "copy1_raw.txt", "copy2_raw.txt", "copy3_raw.txt",
    "copy3_flash_page_map.json", "copy3_pro_page_map.json",
]


def _seed_workspace(tmp_path: Path) -> BookWorkspace:
    """Place the frozen OCR copies + page maps where reconcile reads them (the ws.data area a
    download/ocr run would have populated)."""
    ws = BookWorkspace.for_book("per_la_liberta", tmp_path).ensure()
    for name in _INPUT_FILES:
        (ws.data / name).write_text(
            (INPUTS / name).read_text(encoding="utf-8"), encoding="utf-8"
        )
    return ws


def test_reconcile_reproduces_frozen_outputs(tmp_path):
    cfg = load_book("per_la_liberta")
    lang = get_language_plugin(cfg.language_id)
    ws = _seed_workspace(tmp_path)

    summary = reconcile.run(
        workspace=ws, cfg=cfg, lang=lang, admission_checker=lambda **_: None
    )

    # reconciled_chapters.json — compare per-chapter so a divergence names the chapter.
    got_ch = json.loads((ws.data / reconcile.RECONCILED_FILE).read_text(encoding="utf-8"))
    want_ch = json.loads((DATA / "reconciled_chapters_expected.json").read_text(encoding="utf-8"))
    assert [c["id"] for c in got_ch] == [c["id"] for c in want_ch], "chapter ids/order diverged"
    got_by = {c["id"]: c for c in got_ch}
    for want in want_ch:
        assert got_by[want["id"]] == want, f"chapter {want['id']!r} diverged from the golden"
    assert got_ch == want_ch

    # flagged_segments.json + chapter_pages.json — full parsed-data equality.
    for name, const in (("flagged_segments", reconcile.FLAGGED_FILE),
                        ("chapter_pages", reconcile.CHAPTER_PAGES_FILE)):
        got = json.loads((ws.data / const).read_text(encoding="utf-8"))
        want = json.loads((DATA / f"{name}_expected.json").read_text(encoding="utf-8"))
        assert got == want, f"{name}.json diverged from the golden"

    # reconciled_raw.txt — exact text (D4).
    got_raw = (ws.data / reconcile.RECONCILED_RAW_FILE).read_text(encoding="utf-8")
    want_raw = (DATA / "reconciled_raw_expected.txt").read_text(encoding="utf-8")
    assert got_raw == want_raw, "reconciled_raw.txt diverged from the golden"

    # Summary sanity — the live run reported 58 chapters in 3-way mode.
    assert summary["mode"] == "3-way"
    assert summary["chapters"] == 58
