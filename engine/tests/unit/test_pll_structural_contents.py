"""PLL instance lock for the generalized S4.6c/#90 source observer."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from engine.errors import MissingInputError
from engine.structure import SourceSpec, load_structural_contents_report


ENGINE = Path(__file__).parents[2]
BOOK = ENGINE / "books" / "per_la_liberta"
CONFIG = BOOK / "structural_contents_sources.json"
REPORT = BOOK / "work" / "structure_observations.json"
RUNNER = BOOK / "observe_structural_contents.py"
REPORT_SHA256 = "cf19c081c461f5aab2228cd3bfa8ad8232c7650fed6a7ccb002d31e754009bac"


def _runner_module():
    spec = importlib.util.spec_from_file_location("pll_structural_contents_runner", RUNNER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_book_runner_derives_expectations_and_source_locks_from_declarations():
    runner = _runner_module()

    expectations = runner._expectations()
    declarations = runner._load_declarations()

    assert [(item.expectation_id, item.literal, item.role) for item in expectations] == [
        ("part-1", "Parte Prima", "part"),
        ("part-2", "Parte Seconda", "part"),
    ]
    assert [item.source_id for item in declarations] == [
        "copy1-djvu",
        "copy2-djvu",
        "copy1-text",
        "copy2-text",
    ]
    assert all(len(item.sha256) == 64 and item.n_bytes > 0 for item in declarations)


def test_book_runner_fails_loud_when_a_declared_local_source_is_missing():
    runner = _runner_module()
    declaration = SourceSpec(
        source_id="missing-local",
        format="plain-text",
        source_ref="inputs/does-not-exist.txt",
        sha256=hashlib.sha256(b"").hexdigest(),
        n_bytes=0,
    )

    with pytest.raises(MissingInputError, match="not found"):
        runner._source_bytes(declaration)


def test_committed_report_is_source_locked_and_holds_the_registered_diagnostic():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    report_bytes = REPORT.read_bytes()
    report = load_structural_contents_report(REPORT, expected_book="per_la_liberta")

    assert hashlib.sha256(report_bytes).hexdigest() == REPORT_SHA256
    assert report["schema_version"] == 1
    assert report["stale_class"] == "structural-contents-observation"
    assert report["observer_policy"] == "structural-contents-sightings-v1"
    assert [
        {
            "source_id": source["source_id"],
            "format": source["format"],
            "source_ref": source["source_ref"],
            "sha256": source["sha256"],
            "bytes": source["bytes"],
        }
        for source in report["sources"]
    ] == config["sources"]

    contents_pages = {
        (item["source_id"], item["page"])
        for item in report["page_features"]
        if item["contents_like"]
    }
    assert contents_pages == {("copy1-djvu", 269), ("copy2-djvu", 271)}

    summaries = {
        (item["expectation_id"], item["source_id"]): item
        for item in report["summaries"]
    }
    for source_id in ("copy1-djvu", "copy2-djvu"):
        first = summaries[("part-1", source_id)]
        assert (first["body_like"], first["contents_like"], first["total"]) == (0, 1, 1)
        second = summaries[("part-2", source_id)]
        assert (second["body_like"], second["contents_like"], second["total"]) == (2, 1, 3)

    first_part_sightings = [
        item
        for item in report["sightings"]
        if item["expectation_id"] == "part-1" and item["source_id"].endswith("-djvu")
    ]
    assert {item["context_before"] for item in first_part_sightings} == {"INDICE"}
    assert {item["locus"] for item in first_part_sightings} == {"contents-like"}
    assert all(item["unverified"] is True for item in first_part_sightings)


def test_runner_and_observer_have_no_structure_map_or_language_surface_dependency():
    runner_text = RUNNER.read_text(encoding="utf-8")
    observer_text = (ENGINE / "src/engine/structure/structural_contents.py").read_text(
        encoding="utf-8"
    )

    assert "load_structure_map" not in runner_text
    assert "write_structure_map" not in runner_text
    assert "authoring_evidence_path" not in runner_text
    assert "engine.lang" not in runner_text
    assert "engine.lang" not in observer_text
