from __future__ import annotations

import json
from types import SimpleNamespace

from engine import review_api
from engine.errors import StaleArtifactError


def test_record_page_verdict_bridge_emits_machine_readable_result(monkeypatch, capsys):
    monkeypatch.setattr(review_api, "load_book", lambda *args, **kwargs: SimpleNamespace())
    monkeypatch.setattr(
        review_api.BookWorkspace,
        "for_book",
        lambda *args, **kwargs: SimpleNamespace(root="fixture-work"),
    )
    captured = {}

    def record(**kwargs):
        captured.update(kwargs)
        return {"status": "review_required", "review_pages": 2}

    monkeypatch.setattr(review_api, "record_page_verdict", record)

    status = review_api.main([
        "record-page-verdict",
        "--book", "fixture",
        "--page", "4",
        "--disposition", "blank",
        "--evidence-sha256", "a" * 64,
        "--reviewer", "Fixture Reviewer",
    ])

    assert status == 0
    assert captured["page"] == 4
    assert captured["reviewer"] == "Fixture Reviewer"
    assert json.loads(capsys.readouterr().out) == {
        "review_pages": 2,
        "status": "review_required",
    }


def test_record_page_verdict_bridge_preserves_engine_exit_code(monkeypatch, capsys):
    monkeypatch.setattr(review_api, "load_book", lambda *args, **kwargs: SimpleNamespace())

    def stale(**kwargs):
        raise StaleArtifactError("evidence changed")

    monkeypatch.setattr(review_api, "record_page_verdict", stale)

    status = review_api.main([
        "record-page-verdict",
        "--book", "fixture",
        "--page", "4",
        "--disposition", "blank",
        "--evidence-sha256", "a" * 64,
        "--reviewer", "Fixture Reviewer",
    ])

    assert status == StaleArtifactError.exit_code
    assert "evidence changed" in capsys.readouterr().err
