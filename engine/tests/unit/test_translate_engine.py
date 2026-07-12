"""Offline contracts for the restartable single-model translation step."""

from __future__ import annotations

import hashlib
import json

import pytest

from engine.config.loader import load_book
from engine.errors import BackendError, MissingInputError
from engine.lang.registry import get_language_plugin
from engine.paths import BookWorkspace
from engine.steps import translate


class FakeCompletion:
    model = "fake-literary-v1"

    def __init__(self, *, fail_title: str | None = None, truncated: bool = False):
        self.calls: list[str] = []
        self.fail_title = fail_title
        self.truncated = truncated

    def complete(self, *, system: str, user: str, thinking_budget: int | None):
        self.calls.append(user)
        if self.fail_title and self.fail_title in user:
            raise RuntimeError("provider failure")
        source = user.split("\n\n", 1)[1]
        if self.truncated:
            return translate.CompletionResult("tiny", "max_tokens")
        return translate.CompletionResult("English " + source, "end_turn")


def _seed(tmp_path):
    cfg = load_book("synthetic")
    lang = get_language_plugin(cfg.language_id)
    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()
    clean = """# Libro di Prova

## Prefazione

<!-- pages:1-1 -->

Testo introduttivo abbastanza lungo per una traduzione completa e verificabile.

## Parte Prima

### Capitolo Primo

Primo corpo abbastanza lungo per una traduzione completa e verificabile.

### Capitolo Secondo

Secondo corpo abbastanza lungo per una traduzione completa e verificabile.
"""
    reconciled = [
        {"id": "prefazione", "title": "Prefazione", "part": 0, "text": "x"},
        {"id": "p1_ch01", "title": "Capitolo Primo", "part": 1, "text": "x"},
        {"id": "p1_ch02", "title": "Capitolo Secondo", "part": 1, "text": "x"},
    ]
    (ws.output / translate.CLEAN_FILE).write_text(clean, encoding="utf-8")
    (ws.data / translate.RECONCILED_FILE).write_text(json.dumps(reconciled), encoding="utf-8")
    (ws.data / translate.CHAPTER_PAGES_FILE).write_text(
        json.dumps({"prefazione": [1], "p1_ch01": [2, 4], "p1_ch02": [5]}), encoding="utf-8"
    )
    clean_hash = hashlib.sha256(clean.encode()).hexdigest()
    (ws.data / translate.VALIDATION_FILE).write_text(
        json.dumps({"overall": "pass", "input_sha256": clean_hash}), encoding="utf-8"
    )
    return cfg, lang, ws


def test_parse_translation_units_binds_stable_ids_and_exact_noncontiguous_pages(tmp_path):
    cfg, _lang, ws = _seed(tmp_path)
    units = translate.parse_translation_units(
        (ws.output / translate.CLEAN_FILE).read_text(),
        json.loads((ws.data / translate.RECONCILED_FILE).read_text()),
        json.loads((ws.data / translate.CHAPTER_PAGES_FILE).read_text()),
    )
    assert [unit.id for unit in units] == ["prefazione", "p1_ch01", "p1_ch02"]
    assert units[1].pages == (2, 4)
    assert "<!-- pages:" not in units[0].text

    bad = json.loads((ws.data / translate.RECONCILED_FILE).read_text())
    bad[1]["title"] = "Renamed"
    with pytest.raises(MissingInputError, match="title mismatch"):
        translate.parse_translation_units(
            (ws.output / translate.CLEAN_FILE).read_text(), bad, {}
        )


def test_translate_run_is_complete_ordered_restartable_and_source_bound(tmp_path):
    cfg, lang, ws = _seed(tmp_path)
    fake = FakeCompletion()
    summary = translate.run(
        workspace=ws, cfg=cfg, lang=lang, workers=2, completion=fake, no_thinking=True,
    )
    assert summary["sections"] == 3 and len(fake.calls) == 3
    english = (ws.output / translate.TRANSLATION_FILE).read_text()
    assert english.index("## Preface") < english.index("### Chapter One") < english.index("### Chapter Two")
    sidecar = json.loads((ws.output / translate.SOURCE_PAGES_FILE).read_text())
    assert sidecar["p1_ch01"]["pages"] == [2, 4]

    no_calls = FakeCompletion()
    summary = translate.run(
        workspace=ws, cfg=cfg, lang=lang, completion=no_calls, no_thinking=True,
    )
    assert summary["translated"] == 0 and no_calls.calls == []


def test_failure_or_truncation_checkpoints_but_blocks_canonical_publication(tmp_path):
    cfg, lang, ws = _seed(tmp_path)
    (ws.output / translate.TRANSLATION_FILE).write_text("stale edition", encoding="utf-8")
    fake = FakeCompletion(fail_title="Capitolo Secondo")
    with pytest.raises(BackendError, match="translation incomplete"):
        translate.run(workspace=ws, cfg=cfg, lang=lang, completion=fake)
    assert not (ws.output / translate.TRANSLATION_FILE).exists()
    progress = json.loads((ws.state / translate.PROGRESS_FILE).read_text())
    assert progress["p1_ch01"]["status"] == "done"
    assert progress["p1_ch02"]["status"] == "error"

    cfg2, lang2, ws2 = _seed(tmp_path / "truncated")
    with pytest.raises(BackendError, match="translation incomplete"):
        translate.run(
            workspace=ws2, cfg=cfg2, lang=lang2, completion=FakeCompletion(truncated=True)
        )
    assert not (ws2.output / translate.TRANSLATION_FILE).exists()


def test_translate_rejects_stale_validation_and_prompt_is_neutral(tmp_path):
    cfg, lang, ws = _seed(tmp_path)
    (ws.output / translate.CLEAN_FILE).write_text(
        (ws.output / translate.CLEAN_FILE).read_text() + "changed", encoding="utf-8"
    )
    with pytest.raises(MissingInputError, match="stale validation"):
        translate.run(workspace=ws, cfg=cfg, lang=lang, completion=FakeCompletion())

    rendered = translate.render_system_prompt(cfg)
    for leaked in ("Per la libertà", "Crespi", "1913", "Italian"):
        assert leaked not in rendered
    assert "Libro di Prova" in rendered and "Sintetico" in rendered
