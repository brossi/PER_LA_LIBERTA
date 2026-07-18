"""Golden reproduction — the engine ``validate`` step, run on the frozen PLL inputs, must
reproduce the report the live ``validate.py`` produced (frozen by
``_generate_validate_fixture.py``), modulo the one documented label generalisation
(``italian_char_coverage`` → ``char_coverage``).

This loads the real spaCy model (word_quality's NER pass) — asserted *hard*, never skipped:
a missing model is a real configuration error (``uv sync --extra it``), and a skip here would
hide a broken word-quality port until it shipped. The report is also asserted to land inside
the workspace, never the live tree.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.config.loader import load_book
from engine.lang.registry import get_language_plugin
from engine.paths import BookWorkspace
from engine.steps import validate

GOLDEN_DIR = Path(__file__).resolve().parent
ENGINE_ROOT = GOLDEN_DIR.parents[1]
INPUTS = ENGINE_ROOT / "books" / "per_la_liberta" / "inputs"
EXPECTED = GOLDEN_DIR / "data" / "validation_report_expected.json"

pytestmark = pytest.mark.golden


def _seed_workspace(tmp_path: Path) -> BookWorkspace:
    """Place the frozen cleaned text + reconciled witness where the step reads them — the
    workspace areas an upstream cleanup/reconcile run would have populated."""
    ws = BookWorkspace.for_book("per_la_liberta", tmp_path).ensure()
    (ws.output / validate.CLEAN_FILE).write_text(
        (INPUTS / "clean.md").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (ws.data / validate.RECONCILED_FILE).write_text(
        (INPUTS / "reconciled_chapters.json").read_text(encoding="utf-8"), encoding="utf-8"
    )
    return ws


def test_validate_reproduces_frozen_report(tmp_path):
    cfg = load_book("per_la_liberta")
    lang = get_language_plugin(cfg.language_id)
    ws = _seed_workspace(tmp_path)

    report = validate.run(workspace=ws, cfg=cfg, lang=lang)

    # The report is written into the workspace and equals the returned dict.
    written = ws.data / validate.REPORT_FILE
    assert written.is_file()
    assert json.loads(written.read_text(encoding="utf-8")) == report

    expected = json.loads(EXPECTED.read_text(encoding="utf-8"))
    assert report["overall"] == expected["overall"]

    got = {c["name"]: c for c in report["checks"]}
    assert [c["name"] for c in report["checks"]] == [c["name"] for c in expected["checks"]], (
        "check order or naming drifted from the live report"
    )
    # Compare per-check so a divergence names the offending check, not a giant blob...
    for want in expected["checks"]:
        assert got[want["name"]] == want, f"check {want['name']!r} diverged from the golden"
    # ...then assert the whole report (catches top-level schema drift, e.g. the issues channel).
    assert report == expected
