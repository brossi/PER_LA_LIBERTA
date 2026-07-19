"""S4.6d structure-review read contract and stale-safe single-node write (#93)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from engine.errors import StaleArtifactError
from engine.paths import BookWorkspace
from engine.structure import (
    build_freeze_record,
    save_stream,
    stamp_evidence,
    write_freeze_record,
    write_structure_map,
)
from engine.structure.authoring import STREAM_FREEZE_FILENAME, main as authoring_main
from engine.structure.authoring_context import load_authoring_context
from engine.structure.evidence import decision_digest, extent_digest
from engine.structure.review_flags import (
    flag_id,
    live_flag,
    validate_structure_review_flags,
)
from engine.structure.structural_contents import (
    SourceSpec,
    StructuralExpectation,
    load_source_bytes,
    observe_structural_contents,
    write_structural_contents_report,
)
from engine.structure.structure_review import (
    VISUAL_SOURCE_POLICY,
    _digest,
    _item_fingerprint,
    build_structure_review_packet,
    load_structure_review_packet,
    record_structure_evidence,
    render_structure_review_packet,
    validate_structure_review_packet,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
GENERATOR = FIXTURES / "_generate_structure_fixture.py"


def _generator():
    spec = importlib.util.spec_from_file_location(
        "_structure_review_fixture", GENERATOR
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GEN = _generator()


def _seed_book(tmp_path: Path, *, book: str = "review_fixture") -> Path:
    books_dir = tmp_path / "books"
    book_dir = books_dir / book
    workspace = BookWorkspace.for_book(book, books_dir).ensure()
    streams = GEN.conforming_streams()
    for stream in streams.values():
        save_stream(workspace, stream)
    write_freeze_record(
        book_dir / STREAM_FREEZE_FILENAME,
        build_freeze_record(streams, book=book),
    )
    write_structure_map(workspace, GEN.build_fixture())
    return book_dir


def _item(packet: dict, node_id: str) -> dict:
    return next(item for item in packet["items"] if item["node_id"] == node_id)


def _stamp_all(book_dir: Path) -> None:
    for node_id in ("n-0", "n-1"):
        stamp_evidence(book_dir, node_id, evidence=f"verified {node_id}")


def _write_observations(book_dir: Path) -> None:
    data = b"Section One\n"
    spec = SourceSpec(
        source_id="fixture-text",
        format="plain-text",
        source_ref="fixture.txt",
        sha256=__import__("hashlib").sha256(data).hexdigest(),
        n_bytes=len(data),
    )
    report = observe_structural_contents(
        book=book_dir.name,
        sources=(load_source_bytes(spec, data),),
        expectations=(
            StructuralExpectation(
                expectation_id="section-one", literal="Section One", role="section"
            ),
        ),
    )
    write_structural_contents_report(
        book_dir / "work" / "structure_observations.json", report
    )


def _write_visual_registration(book_dir: Path, asset_root: Path) -> Path:
    asset = asset_root / "fixture.pdf"
    asset.write_bytes(b"%PDF fixture review bytes")
    import hashlib

    registration = {
        "schema_version": 1,
        "book": book_dir.name,
        "policy": VISUAL_SOURCE_POLICY,
        "sources": [
            {
                "source_id": "fixture-pdf",
                "witness_id": "fixture-witness",
                "kind": "pdf",
                "media_type": "application/pdf",
                "path": "fixture.pdf",
                "sha256": hashlib.sha256(asset.read_bytes()).hexdigest(),
                "bytes": asset.stat().st_size,
                "page_numbering": "pdf-page-1-based",
                "node_pages": {"n-0": [[1, 4], [8, 9]]},
            }
        ],
    }
    (book_dir / "structure_review_sources.json").write_text(
        json.dumps(registration, indent=2) + "\n", encoding="utf-8"
    )
    return asset


def test_generic_packet_reuses_inspection_and_authoring_status(tmp_path):
    book_dir = _seed_book(tmp_path)
    packet = build_structure_review_packet(book_dir, asset_root=tmp_path)

    assert [item["node_id"] for item in packet["items"]] == ["n-0", "n-1"]
    assert [item["ordinal"] for item in packet["items"]] == [1, 2]
    assert packet["status_counts"]["missing"] == 2
    assert [_item(packet, node)["status"]["kinds"] for node in ("n-0", "n-1")] == [
        ["missing"],
        ["missing"],
    ]
    section = _item(packet, "n-1")["inspection"]
    assert section["parent"] == "n-0"
    assert section["hierarchy"][-1]["label"] == "Section One"
    assert section["own_slots"]["heading"] == ["canonical_00000"]
    assert section["extent"]["atom_count"] == 2
    assert packet["class_counts"] == {"block": 2, "section": 1, "volume": 1}

    # The CLI is merely another renderer over the shared model.
    assert (
        authoring_main(
            [
                "--book",
                book_dir.name,
                "--books-dir",
                str(book_dir.parent),
                "inspect",
                "--atom",
                "canonical_00000",
            ]
        )
        == 0
    )


def test_equal_inputs_are_byte_identical_and_strict_loader_rejects_unknowns(tmp_path):
    book_dir = _seed_book(tmp_path)
    first = build_structure_review_packet(book_dir, asset_root=tmp_path)
    second = build_structure_review_packet(book_dir, asset_root=tmp_path)
    assert render_structure_review_packet(first) == render_structure_review_packet(
        second
    )

    path = tmp_path / "packet.json"
    path.write_text(render_structure_review_packet(first), encoding="utf-8")
    assert (
        load_structure_review_packet(path, asset_root=tmp_path, book_dir=book_dir)
        == first
    )

    mutated = json.loads(render_structure_review_packet(first))
    mutated["items"][0]["inspection"]["unregistered"] = True
    mutated["items"][0]["review_fingerprint"] = _item_fingerprint(mutated["items"][0])
    without_hash = dict(mutated)
    without_hash.pop("packet_sha256")
    mutated["packet_sha256"] = _digest(without_hash)
    with pytest.raises(StaleArtifactError, match="inspection.*keys"):
        validate_structure_review_packet(
            mutated, asset_root=tmp_path, book_dir=book_dir
        )


def test_exact_observation_association_and_ambiguity_remain_visible(tmp_path):
    book_dir = _seed_book(tmp_path)
    _write_observations(book_dir)
    packet = build_structure_review_packet(book_dir, asset_root=tmp_path)
    assert packet["observation_associations"] == [
        {
            "expectation_id": "section-one",
            "state": "associated",
            "candidate_node_ids": ["n-1"],
        }
    ]
    observations = _item(packet, "n-1")["observations"]
    assert observations[0]["sightings"][0]["unverified"] is True
    assert observations[0]["sightings"][0]["matched_text"] == "Section One"

    map_path = book_dir / "work" / "structure_map.json"
    doc = json.loads(map_path.read_text(encoding="utf-8"))
    doc["nodes"][0]["title"] = "Section One"
    map_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    ambiguous = build_structure_review_packet(book_dir, asset_root=tmp_path)
    assert ambiguous["observation_associations"][0] == {
        "expectation_id": "section-one",
        "state": "ambiguous",
        "candidate_node_ids": ["n-0", "n-1"],
    }
    assert not _item(ambiguous, "n-0")["observations"]
    assert not _item(ambiguous, "n-1")["observations"]


def test_visual_descriptors_are_contained_and_hash_bound(tmp_path):
    book_dir = _seed_book(tmp_path)
    asset = _write_visual_registration(book_dir, tmp_path)
    packet = build_structure_review_packet(book_dir, asset_root=tmp_path)
    assert packet["adjuncts"]["visual_sources"]["state"] == "available"
    assert _item(packet, "n-0")["visuals"][0]["source_id"] == "fixture-pdf"
    assert _item(packet, "n-0")["visuals"][0]["page_ranges"] == [[1, 4], [8, 9]]
    assert _item(packet, "n-1")["visuals"][0]["page_ranges"] == []

    asset.write_bytes(b"changed")
    with pytest.raises(StaleArtifactError, match="registered lock"):
        build_structure_review_packet(book_dir, asset_root=tmp_path)

    registration_path = book_dir / "structure_review_sources.json"
    registration = json.loads(registration_path.read_text(encoding="utf-8"))
    registration["sources"][0]["path"] = "../escape.pdf"
    registration_path.write_text(json.dumps(registration), encoding="utf-8")
    with pytest.raises(StaleArtifactError, match="contained relative path"):
        build_structure_review_packet(book_dir, asset_root=tmp_path)


def test_visual_page_map_rejects_unknown_structure_nodes(tmp_path):
    book_dir = _seed_book(tmp_path)
    _write_visual_registration(book_dir, tmp_path)
    registration_path = book_dir / "structure_review_sources.json"
    registration = json.loads(registration_path.read_text(encoding="utf-8"))
    registration["sources"][0]["node_pages"]["typo-node"] = [[1, 1]]
    registration_path.write_text(json.dumps(registration), encoding="utf-8")

    with pytest.raises(StaleArtifactError, match="unknown/non-human"):
        build_structure_review_packet(book_dir, asset_root=tmp_path)


def test_relevant_visual_mapping_changes_only_its_item_fingerprint(tmp_path):
    book_dir = _seed_book(tmp_path)
    _write_visual_registration(book_dir, tmp_path)
    before = build_structure_review_packet(book_dir, asset_root=tmp_path)

    registration_path = book_dir / "structure_review_sources.json"
    registration = json.loads(registration_path.read_text(encoding="utf-8"))
    registration["sources"][0]["node_pages"]["n-0"] = [[2, 4], [8, 9]]
    registration_path.write_text(json.dumps(registration), encoding="utf-8")
    after = build_structure_review_packet(book_dir, asset_root=tmp_path)

    assert (
        _item(after, "n-0")["review_fingerprint"]
        != _item(before, "n-0")["review_fingerprint"]
    )
    assert (
        _item(after, "n-1")["review_fingerprint"]
        == _item(before, "n-1")["review_fingerprint"]
    )


def test_visual_registration_rejects_false_types_and_overlapping_ranges(tmp_path):
    book_dir = _seed_book(tmp_path)
    _write_visual_registration(book_dir, tmp_path)
    registration_path = book_dir / "structure_review_sources.json"
    registration = json.loads(registration_path.read_text(encoding="utf-8"))
    registration["sources"][0]["node_pages"]["n-0"] = [[1, 4], [4, 8]]
    registration_path.write_text(json.dumps(registration), encoding="utf-8")
    with pytest.raises(StaleArtifactError, match="overlap or are unordered"):
        build_structure_review_packet(book_dir, asset_root=tmp_path)

    registration["sources"][0]["node_pages"]["n-0"] = [[1, 4]]
    registration["sources"][0]["path"] = 7
    registration_path.write_text(json.dumps(registration), encoding="utf-8")
    with pytest.raises(StaleArtifactError, match="field 'path'.*text"):
        build_structure_review_packet(book_dir, asset_root=tmp_path)


def test_unrelated_stamp_changes_packet_not_unchanged_item(tmp_path):
    book_dir = _seed_book(tmp_path)
    before = build_structure_review_packet(book_dir, asset_root=tmp_path)
    n0_before = _item(before, "n-0")["review_fingerprint"]
    n1_before = _item(before, "n-1")["review_fingerprint"]

    stamp_evidence(book_dir, "n-0", evidence="root checked against source")
    after = build_structure_review_packet(book_dir, asset_root=tmp_path)
    assert after["packet_sha256"] != before["packet_sha256"]
    assert _item(after, "n-0")["review_fingerprint"] != n0_before
    assert _item(after, "n-1")["review_fingerprint"] == n1_before


def test_packet_preserves_fresh_decision_and_extent_finding_semantics(tmp_path):
    book_dir = _seed_book(tmp_path)
    _stamp_all(book_dir)
    fresh = build_structure_review_packet(book_dir, asset_root=tmp_path)
    assert [_item(fresh, node_id)["status"] for node_id in ("n-0", "n-1")] == [
        {"state": "fresh", "kinds": []},
        {"state": "fresh", "kinds": []},
    ]

    map_path = book_dir / "work" / "structure_map.json"
    document = json.loads(map_path.read_text(encoding="utf-8"))
    next(node for node in document["nodes"] if node["node_id"] == "n-0")[
        "children"
    ].reverse()
    map_path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    decision_stale = build_structure_review_packet(book_dir, asset_root=tmp_path)
    assert _item(decision_stale, "n-0")["status"] == {
        "state": "stale",
        "kinds": ["stale-decision"],
    }

    extent_root = tmp_path / "extent-case"
    book_dir = _seed_book(extent_root)
    _stamp_all(book_dir)
    map_path = book_dir / "work" / "structure_map.json"
    document = json.loads(map_path.read_text(encoding="utf-8"))
    section = next(node for node in document["nodes"] if node["node_id"] == "n-1")
    section["signature_atoms"] = [
        *section.get("signature_atoms", []),
        *section["heading_atoms"],
    ]
    section["heading_atoms"] = []
    map_path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    extent_stale = build_structure_review_packet(book_dir, asset_root=extent_root)
    assert _item(extent_stale, "n-1")["status"] == {
        "state": "stale",
        "kinds": ["stale-extent"],
    }
    assert _item(extent_stale, "n-0")["status"] == {
        "state": "fresh",
        "kinds": [],
    }


def test_guarded_write_refuses_stale_without_write_and_changes_one_entry(tmp_path):
    book_dir = _seed_book(tmp_path)
    packet = build_structure_review_packet(book_dir, asset_root=tmp_path)
    original = _item(packet, "n-0")["review_fingerprint"]

    # A relevant stamp changes n-0's displayed evidence state and makes the old browser item stale.
    stamp_evidence(book_dir, "n-0", evidence="first rationale")
    evidence_path = book_dir / "work" / "authoring_evidence.json"
    before = evidence_path.read_bytes()
    with pytest.raises(StaleArtifactError, match="changed"):
        record_structure_evidence(
            book_dir,
            node_id="n-0",
            review_fingerprint=original,
            evidence="must not overwrite",
            asset_root=tmp_path,
        )
    assert evidence_path.read_bytes() == before

    current = build_structure_review_packet(book_dir, asset_root=tmp_path)
    result = record_structure_evidence(
        book_dir,
        node_id="n-1",
        review_fingerprint=_item(current, "n-1")["review_fingerprint"],
        evidence="section boundary checked against the source",
        asset_root=tmp_path,
    )
    assert result["status"] == "fresh"
    doc = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert [entry["node_id"] for entry in doc["entries"]] == ["n-0", "n-1"]
    assert (
        next(entry for entry in doc["entries"] if entry["node_id"] == "n-0")["evidence"]
        == "first rationale"
    )


def test_guarded_write_stamps_from_the_context_used_for_fingerprint(
    monkeypatch, tmp_path
):
    import engine.structure.structure_review as review

    book_dir = _seed_book(tmp_path)
    packet = build_structure_review_packet(book_dir, asset_root=tmp_path)
    expected = _item(packet, "n-0")["review_fingerprint"]
    real_build = review._build_packet_for_context
    real_stamp = review.stamp_evidence_for_context
    built_contexts = []
    contexts = []

    def capture_build(context, **kwargs):
        built_contexts.append(context)
        return real_build(context, **kwargs)

    def capture(context, node_id, *, evidence):
        contexts.append(context)
        return real_stamp(context, node_id, evidence=evidence)

    monkeypatch.setattr(review, "_build_packet_for_context", capture_build)
    monkeypatch.setattr(review, "stamp_evidence_for_context", capture)
    review.record_structure_evidence(
        book_dir,
        node_id="n-0",
        review_fingerprint=expected,
        evidence="verified from one guarded snapshot",
        asset_root=tmp_path,
    )
    assert len(contexts) == 1
    assert built_contexts[0] is contexts[0]
    assert contexts[0].book_dir.resolve() == book_dir.resolve()


def test_flag_lifecycle_is_deterministic_and_human_edits_supersede(tmp_path):
    book_dir = _seed_book(tmp_path)
    context = load_authoring_context(book_dir)
    node = context.smap.projection.by_id["n-0"]
    producer = "fixture-seed-flags-v1"
    message = "candidate boundary needs review"
    import hashlib

    document = {
        "schema_version": 1,
        "stale_class": "structure-review-flags",
        "book": book_dir.name,
        "producer": {"id": producer, "version": 1},
        "seed_identity": {
            "candidate_semantics_sha256": "a" * 64,
            "freeze_sha256": hashlib.sha256(
                context.freeze_path.read_bytes()
            ).hexdigest(),
        },
        "flags": [
            {
                "flag_id": flag_id(producer, 1, message),
                "kind": "source-anomaly",
                "message": message,
                "target_node_id": "n-0",
                "cited_atom_ids": [],
                "seed_decision_digest": decision_digest(node),
                "seed_extent_digest": extent_digest(node, context.smap.projection),
                "resolution_posture": "review-required",
                "corroborating_observation_ids": [],
            }
        ],
    }
    validate_structure_review_flags(document)
    flag_path = book_dir / "work" / "structure_review_flags.json"
    flag_path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    packet = build_structure_review_packet(book_dir, asset_root=tmp_path)
    assert _item(packet, "n-0")["flags"]["items"][0]["state"] == "applicable"

    map_path = book_dir / "work" / "structure_map.json"
    doc = json.loads(map_path.read_text(encoding="utf-8"))
    doc["nodes"][0]["children"].reverse()
    map_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    edited = build_structure_review_packet(book_dir, asset_root=tmp_path)
    assert _item(edited, "n-0")["flags"]["items"][0]["state"] == "superseded"


def test_flag_lifecycle_keeps_unresolved_and_corroborated_distinct(tmp_path):
    book_dir = _seed_book(tmp_path)
    context = load_authoring_context(book_dir)
    node = context.smap.projection.by_id["n-0"]
    bound = {
        "flag_id": "flag-bound",
        "kind": "source-anomaly",
        "message": "source corroborates this candidate warning",
        "target_node_id": "n-0",
        "cited_atom_ids": [],
        "seed_decision_digest": decision_digest(node),
        "seed_extent_digest": extent_digest(node, context.smap.projection),
        "resolution_posture": "review-required",
        "corroborating_observation_ids": ["obs-current"],
    }
    corroborated = live_flag(
        bound,
        context.smap.projection,
        current_observation_ids={"obs-current"},
    )
    assert corroborated["state"] == "corroborated"
    assert corroborated["base_state"] == "applicable"

    unbound = {
        **bound,
        "flag_id": "flag-unbound",
        "target_node_id": None,
        "seed_decision_digest": None,
        "seed_extent_digest": None,
        "corroborating_observation_ids": [],
    }
    unresolved = live_flag(
        unbound,
        context.smap.projection,
        current_observation_ids=set(),
    )
    assert unresolved["state"] == unresolved["base_state"] == "unresolved"
