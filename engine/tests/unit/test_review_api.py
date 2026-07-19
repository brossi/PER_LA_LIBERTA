from __future__ import annotations

import json
from types import SimpleNamespace

from engine import review_api
from engine.errors import InvalidInvocationError, StaleArtifactError


def test_record_page_verdict_bridge_emits_machine_readable_result(monkeypatch, capsys):
    monkeypatch.setattr(
        review_api, "load_book", lambda *args, **kwargs: SimpleNamespace()
    )
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

    status = review_api.main(
        [
            "record-page-verdict",
            "--book",
            "fixture",
            "--page",
            "4",
            "--disposition",
            "blank",
            "--evidence-sha256",
            "a" * 64,
            "--reviewer",
            "Fixture Reviewer",
        ]
    )

    assert status == 0
    assert captured["page"] == 4
    assert captured["reviewer"] == "Fixture Reviewer"
    assert json.loads(capsys.readouterr().out) == {
        "review_pages": 2,
        "status": "review_required",
    }


def test_record_page_verdict_bridge_preserves_engine_exit_code(monkeypatch, capsys):
    monkeypatch.setattr(
        review_api, "load_book", lambda *args, **kwargs: SimpleNamespace()
    )

    def stale(**kwargs):
        raise StaleArtifactError("evidence changed")

    monkeypatch.setattr(review_api, "record_page_verdict", stale)

    status = review_api.main(
        [
            "record-page-verdict",
            "--book",
            "fixture",
            "--page",
            "4",
            "--disposition",
            "blank",
            "--evidence-sha256",
            "a" * 64,
            "--reviewer",
            "Fixture Reviewer",
        ]
    )

    assert status == StaleArtifactError.exit_code
    assert "evidence changed" in capsys.readouterr().err


def test_structure_packet_bridge_emits_engine_owned_packet(
    monkeypatch, capsys, tmp_path
):
    captured = {}

    def build(book_dir, **kwargs):
        captured.update(book_dir=book_dir, **kwargs)
        return {"schema_version": 1, "items": [{"node_id": "node-fixture"}]}

    monkeypatch.setattr(review_api, "build_structure_review_packet", build)
    status = review_api.main(
        [
            "structure-packet",
            "--book",
            "fixture",
            "--books-dir",
            str(tmp_path / "books"),
            "--asset-root",
            str(tmp_path),
        ]
    )
    assert status == 0
    assert captured["book_dir"] == tmp_path / "books" / "fixture"
    assert captured["asset_root"] == tmp_path
    assert json.loads(capsys.readouterr().out)["items"][0]["node_id"] == "node-fixture"


def test_structure_write_bridge_preserves_typed_stale_conflict(
    monkeypatch, capsys, tmp_path
):
    def stale(*args, **kwargs):
        raise StaleArtifactError("structure item changed")

    monkeypatch.setattr(review_api, "record_structure_evidence", stale)
    status = review_api.main(
        [
            "record-structure-evidence",
            "--book",
            "fixture",
            "--books-dir",
            str(tmp_path / "books"),
            "--asset-root",
            str(tmp_path),
            "--node",
            "node-fixture",
            "--review-fingerprint",
            "a" * 64,
            "--evidence",
            "checked against both scans",
        ]
    )
    assert status == StaleArtifactError.exit_code
    assert "structure item changed" in capsys.readouterr().err


def test_structure_write_bridge_preserves_invalid_invocation(
    monkeypatch, capsys, tmp_path
):
    def invalid(*args, **kwargs):
        raise InvalidInvocationError("structure evidence is blank")

    monkeypatch.setattr(review_api, "record_structure_evidence", invalid)
    status = review_api.main(
        [
            "record-structure-evidence",
            "--book",
            "fixture",
            "--books-dir",
            str(tmp_path / "books"),
            "--asset-root",
            str(tmp_path),
            "--node",
            "node-fixture",
            "--review-fingerprint",
            "a" * 64,
            "--evidence",
            "checked against both scans",
        ]
    )
    assert status == InvalidInvocationError.exit_code
    assert "structure evidence is blank" in capsys.readouterr().err
