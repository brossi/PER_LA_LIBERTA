"""S4.6b — the authoring-loop toolkit (s4_6_tooling_plan §4, ratified 2026-07-02; issue #34).

The invariants under test, each proven red by the mutation hunt (red-first, §9):

- the composite gate routes each layer's failure as ITS typed error, in substrate-first order
  (freeze drift beats a stale sidecar — a drifted substrate must never be misattributed to
  evidence), and deliberately does NOT do S8.1's stored-manifest-vs-live comparison (§3.E.9);
- ``status`` is a non-raising worklist view assembled from THE findings producer's node-attributed
  core (never message-parsing, never a second staleness computation), kinds as columns, anomalies
  as their own lines, every closed kind representable;
- ``stamp`` writes exactly one node's entry (read-modify-write — every other entry preserved),
  refuses unknown nodes and machine leaves, re-stamps byte-idempotently, and offers NO bulk path;
- the explainer names exactly WHICH children/atoms moved from the entry's stored DT-4 payload
  witnesses — no baseline document — and states the non-diff states (missing/orphaned/misbound)
  plainly;
- ``validate`` collects instead of raising (the editor loop) and ``--watch`` re-validates on a
  save; the CLI exits with the failing layer's ``EngineError`` code (12 for evidence findings).

The book fixture is built from the LIVE producers via the conforming-fixture generator (two human
containers ``n-0``/``n-1``, two machine leaves), persisted through the real store/freeze/map
writers into a tmp book dir — the same shape the PLL loop will run against.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from engine.errors import StaleArtifactError
from engine.paths import BookWorkspace
from engine.structure import (
    AuthoringEvidence,
    EvidenceGateError,
    assert_authoring_integrity,
    authoring_status,
    build_freeze_record,
    explain_evidence_drift,
    save_stream,
    stamp_evidence,
    validate_authoring,
    write_authoring_evidence,
    write_freeze_record,
    write_structure_map,
)
from engine.structure.authoring import (
    STREAM_FREEZE_FILENAME,
    main,
    render_status,
    watch_validate,
)
from engine.structure.errors import StructureValidationError
from engine.structure.evidence import _attributed_findings, evidence_findings
from engine.structure.structure_map import load_structure_map

FIXTURES_ROOT = Path(__file__).resolve().parents[1] / "fixtures"
GENERATOR = FIXTURES_ROOT / "_generate_structure_fixture.py"


def _generator():
    spec = importlib.util.spec_from_file_location("_generate_structure_fixture", GENERATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GEN = _generator()
BOOK = "tbook"


def _seed_book(tmp_path, *, book: str = BOOK) -> Path:
    """A complete tmp book: persisted streams, committed freeze pin, and the conforming draft map
    — everything through the live producers/writers, nothing hand-rolled."""
    books_dir = tmp_path / "books"
    book_dir = books_dir / book
    workspace = BookWorkspace.for_book(book, books_dir).ensure()
    streams = GEN.conforming_streams()
    for stream in streams.values():
        save_stream(workspace, stream)
    write_freeze_record(book_dir / STREAM_FREEZE_FILENAME, build_freeze_record(streams, book=book))
    write_structure_map(workspace, GEN.build_fixture())
    return book_dir


def _map_path(book_dir: Path) -> Path:
    return book_dir / "work" / "structure_map.json"


def _evidence_path(book_dir: Path) -> Path:
    return book_dir / "work" / "authoring_evidence.json"


def _edit_map(book_dir: Path, mutate) -> None:
    """Hand-edit the persisted map the way the authoring human does (a direct file edit, not the
    CAS writer — plan DT-7: initial authoring happens at rev 0/as-committed via the editor)."""
    path = _map_path(book_dir)
    doc = json.loads(path.read_text(encoding="utf-8"))
    mutate(doc)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _node(doc: dict, node_id: str) -> dict:
    return next(n for n in doc["nodes"] if n["node_id"] == node_id)


def _stamp_all(book_dir: Path) -> None:
    smap = load_structure_map(_map_path(book_dir), _reader_for(book_dir))
    for node in smap.projection.nodes:
        if node.minted_by == "human":
            stamp_evidence(book_dir, node.node_id, evidence=f"verified {node.node_id}")


def _reader_for(book_dir: Path):
    from engine.structure import workspace_reader

    return workspace_reader(BookWorkspace.for_book(book_dir.name, book_dir.parent))


# --- the composite gate: routing, order, and the S8.1 non-goal (plan §4 rows 1-6) ---------------- #


def test_gate_on_a_fresh_draft_fails_all_missing_with_exit_code_12(tmp_path):
    # The fresh-draft state IS the worklist: no sidecar yet → every human container `missing`.
    book_dir = _seed_book(tmp_path)
    with pytest.raises(EvidenceGateError) as err:
        assert_authoring_integrity(book_dir)
    assert err.value.exit_code == 12
    assert list(err.value.kinds) == ["missing", "missing"]  # n-0 and n-1, map reading order
    assert "n-0" in str(err.value) and "n-1" in str(err.value)


def test_gate_goes_green_once_every_container_is_stamped(tmp_path):
    book_dir = _seed_book(tmp_path)
    _stamp_all(book_dir)
    smap = assert_authoring_integrity(book_dir)
    assert smap.map_revision == 2  # the loaded conforming map rides back out of the gate


def test_gate_routes_a_freeze_drift_as_stale_artifact_naming_the_stream(tmp_path):
    book_dir = _seed_book(tmp_path)
    _stamp_all(book_dir)
    pin_path = book_dir / STREAM_FREEZE_FILENAME
    pin = json.loads(pin_path.read_text(encoding="utf-8"))
    pin["streams"][0]["envelope_hash"] = "sha256:" + "0" * 64
    pin_path.write_text(json.dumps(pin, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(StaleArtifactError, match="drifted"):
        assert_authoring_integrity(book_dir)


def test_gate_routes_an_invalid_map_as_structure_validation_error(tmp_path):
    book_dir = _seed_book(tmp_path)
    _stamp_all(book_dir)
    _edit_map(book_dir, lambda doc: _node(doc, "n-1")["children"].append("n-ghost"))
    with pytest.raises(StructureValidationError):
        assert_authoring_integrity(book_dir)


def test_gate_routes_stale_evidence_as_the_gate_error(tmp_path):
    book_dir = _seed_book(tmp_path)
    _stamp_all(book_dir)
    # a child reorder is the minimal VALID decision drift (a class swap would orphan its vocab
    # entry and red Tier-2's VOCAB_UNUSED before evidence is ever consulted)
    _edit_map(book_dir, lambda doc: _node(doc, "n-0")["children"].reverse())
    with pytest.raises(EvidenceGateError) as err:
        assert_authoring_integrity(book_dir)
    assert "stale-decision" in err.value.kinds


def test_gate_order_is_substrate_first_a_freeze_drift_beats_stale_evidence(tmp_path):
    # Plan §4 row 4: with BOTH a drifted pin and stale evidence, the gate must name the substrate
    # — reporting evidence against a drifted base would misattribute the failure.
    book_dir = _seed_book(tmp_path)
    _stamp_all(book_dir)
    _edit_map(book_dir, lambda doc: _node(doc, "n-1").__setitem__("node_class", "volume"))
    pin_path = book_dir / STREAM_FREEZE_FILENAME
    pin = json.loads(pin_path.read_text(encoding="utf-8"))
    pin["streams"][0]["envelope_hash"] = "sha256:" + "0" * 64
    pin_path.write_text(json.dumps(pin, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(StaleArtifactError):
        assert_authoring_integrity(book_dir)


def test_gate_order_freeze_drift_beats_an_invalid_map(tmp_path):
    # Same substrate-first discipline against the MAP layer: pin drift + dangling child together
    # must report the pin (a map verdict over a drifted substrate would be meaningless).
    book_dir = _seed_book(tmp_path)
    _edit_map(book_dir, lambda doc: _node(doc, "n-1")["children"].append("n-ghost"))
    pin_path = book_dir / STREAM_FREEZE_FILENAME
    pin = json.loads(pin_path.read_text(encoding="utf-8"))
    pin["streams"][0]["envelope_hash"] = "sha256:" + "0" * 64
    pin_path.write_text(json.dumps(pin, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(StaleArtifactError):
        assert_authoring_integrity(book_dir)


def test_gate_binds_the_pin_to_the_book_dir_name(tmp_path):
    # Plan §4 row 5: a copy-pasted pin from another book is the wrong artifact, however
    # well-formed — `record["book"]` must equal the book dir's name.
    import shutil

    book_dir = _seed_book(tmp_path)
    _stamp_all(book_dir)
    other = book_dir.parent / "otherbook"
    shutil.copytree(book_dir, other)
    with pytest.raises(StaleArtifactError, match="wrong pin"):
        assert_authoring_integrity(other)


def test_gate_does_not_do_s8_1s_stored_manifest_comparison(tmp_path):
    # Plan §4 row 6 — a deliberate PASS pinned as a test: the map's stored manifest hashes are
    # S8.1's stored-vs-live comparison (s4_plan §3.E.9), NOT this gate's. The gate's freshness
    # claim rides the freeze pin, which pins the same envelope hashes the manifest stamps. A
    # junk manifest hash must therefore ride through a green gate.
    book_dir = _seed_book(tmp_path)
    _stamp_all(book_dir)
    _edit_map(
        book_dir,
        lambda doc: doc["manifest"]["atom_streams"][0].__setitem__("hash", "sha256:" + "f" * 64),
    )
    assert assert_authoring_integrity(book_dir) is not None


def test_a_tampered_witness_fails_the_composite_path_at_load(tmp_path):
    # Plan §4 row 11 at the composite level: a hand-tampered payload witness cannot reach the
    # gate — the sidecar loader's self-verification reds first, naming the node.
    book_dir = _seed_book(tmp_path)
    _stamp_all(book_dir)
    path = _evidence_path(book_dir)
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["entries"][0]["decision_payload"]["node_class"] = "tampered"
    path.write_text(json.dumps(doc, ensure_ascii=False) + "\n", encoding="utf-8")
    with pytest.raises(StaleArtifactError, match="untrustworthy"):
        assert_authoring_integrity(book_dir)


# --- status: the non-raising worklist view (plan §4 rows 7/8/18) --------------------------------- #


def test_status_on_a_fresh_draft_is_the_all_missing_worklist(tmp_path):
    book_dir = _seed_book(tmp_path)
    status = authoring_status(book_dir)
    assert status.book == BOOK
    assert [row.node_id for row in status.rows] == ["n-0", "n-1"]  # map reading order
    assert all(row.kinds == ("missing",) for row in status.rows)
    assert status.counts["missing"] == 2 and status.counts["fresh"] == 0
    assert status.anomalies == ()


def test_status_rows_come_from_the_attributed_core_not_message_parsing(tmp_path):
    # The single-producer discipline (s4_plan §1.4.1a): evidence_findings must be exactly the
    # (kind, message) projection of the attributed core the worklist reads — two enumerations
    # would eventually disagree.
    book_dir = _seed_book(tmp_path)
    smap = load_structure_map(_map_path(book_dir), _reader_for(book_dir))
    evidence = AuthoringEvidence(book=BOOK, entries=())
    attributed = _attributed_findings(evidence, smap.projection)
    assert evidence_findings(evidence, smap.projection) == tuple(
        (kind, message) for _, kind, message in attributed
    )


def test_status_render_carries_every_closed_kind_somewhere(tmp_path):
    # Plan §4 row 8: kinds as columns (missing / stale-decision / stale-extent per row) and the
    # entry-side anomalies (orphaned / misbound) as their own lines — drop any kind from the
    # renderer and this reds.
    book_dir = _seed_book(tmp_path)
    _stamp_all(book_dir)
    # ONE valid edit that stales both halves: moving n-0's leaf child under n-1 stales n-0's
    # decision (children changed) and n-1's decision+extent (new child; beneath grows). Orphan +
    # misbound ride in via a hand-extended sidecar (coherent witnesses through the model — the
    # only way foreign entries can exist under DT-4).
    def move(doc):
        leaf_b = _node(doc, "n-0")["children"][1]
        _node(doc, "n-0")["children"].remove(leaf_b)
        _node(doc, "n-1")["children"].append(leaf_b)

    _edit_map(book_dir, move)
    smap = load_structure_map(_map_path(book_dir), _reader_for(book_dir))
    from engine.structure import load_authoring_evidence

    loaded = load_authoring_evidence(_evidence_path(book_dir), expected_book=BOOK)
    leaf = next(n for n in smap.projection.nodes if n.minted_by == "machine")
    from engine.structure.evidence import EvidenceEntry, decision_payload, extent_payload
    from engine.structure.structure_map import _hash_canonical

    misbound = EvidenceEntry(
        node_id=leaf.node_id,
        decision_digest=_hash_canonical(decision_payload(leaf)),
        extent_digest=_hash_canonical(extent_payload(leaf, smap.projection)),
        evidence="stamped onto a machine leaf",
        authored_at_revision=2,
        decision_payload=decision_payload(leaf),
        extent_payload=extent_payload(leaf, smap.projection),
    )
    ghost_payload = {"node_class": "section", "children": []}
    ghost_extent = {"own": {"heading": [], "signature": []}, "beneath": []}
    orphan = EvidenceEntry(
        node_id="n-ghost",
        decision_digest=_hash_canonical(ghost_payload),
        extent_digest=_hash_canonical(ghost_extent),
        evidence="binds nothing",
        authored_at_revision=2,
        decision_payload=ghost_payload,
        extent_payload=ghost_extent,
    )
    write_authoring_evidence(
        _evidence_path(book_dir),
        AuthoringEvidence(book=BOOK, entries=(*loaded.entries, misbound, orphan)),
        force=True,
    )
    rendered = render_status(authoring_status(book_dir))
    for kind in ("missing", "stale-decision", "stale-extent", "orphaned", "misbound"):
        assert kind in rendered, f"kind {kind!r} missing from the status render"
    # ...and the three per-row kinds specifically as table COLUMNS (the header row) — the counts
    # footer also names every kind, so a dropped column would otherwise hide behind it (the
    # mutation hunt's A4 lesson)
    header = rendered.splitlines()[1]
    for kind in ("missing", "stale-decision", "stale-extent"):
        assert kind in header, f"kind {kind!r} missing from the worklist columns"


def test_status_never_raises_on_gate_failing_input_and_cli_exits_zero(tmp_path, capsys):
    book_dir = _seed_book(tmp_path)
    assert (
        main(["--book", BOOK, "--books-dir", str(book_dir.parent), "status"]) == 0
    )  # a view, not a gate
    out = capsys.readouterr().out
    assert "missing" in out and "n-0" in out


# --- stamp: one node, read-modify-write, no bulk (plan §4 rows 12/13/14/23) ----------------------- #


def test_stamp_preserves_every_other_entry(tmp_path):
    book_dir = _seed_book(tmp_path)
    stamp_evidence(book_dir, "n-0", evidence="root verified against the scans")
    first = _evidence_path(book_dir).read_text(encoding="utf-8")
    stamp_evidence(book_dir, "n-1", evidence="section verified against the scans")
    from engine.structure import load_authoring_evidence

    merged = load_authoring_evidence(_evidence_path(book_dir), expected_book=BOOK)
    assert set(merged.by_node) == {"n-0", "n-1"}
    assert merged.by_node["n-0"].evidence == "root verified against the scans"
    # authored_at_revision comes from the LIVE map (the fixture sits at rev 2), never a default
    assert merged.by_node["n-0"].authored_at_revision == 2
    assert json.loads(first)["entries"][0] == json.loads(
        _evidence_path(book_dir).read_text(encoding="utf-8")
    )["entries"][0]  # byte-level: n-0's entry survived n-1's stamp untouched


def test_restamp_with_identical_prose_is_byte_idempotent(tmp_path):
    book_dir = _seed_book(tmp_path)
    stamp_evidence(book_dir, "n-0", evidence="root verified")
    before = _evidence_path(book_dir).read_text(encoding="utf-8")
    stamp_evidence(book_dir, "n-0", evidence="root verified")
    assert _evidence_path(book_dir).read_text(encoding="utf-8") == before


def test_stamp_refuses_an_unknown_node_and_a_machine_leaf(tmp_path):
    book_dir = _seed_book(tmp_path)
    with pytest.raises(ValueError, match="names no node"):
        stamp_evidence(book_dir, "n-nowhere", evidence="nothing to verify")
    smap = load_structure_map(_map_path(book_dir), _reader_for(book_dir))
    leaf_id = next(n.node_id for n in smap.projection.nodes if n.minted_by == "machine")
    with pytest.raises(ValueError, match="not a human-minted container"):
        stamp_evidence(book_dir, leaf_id, evidence="leaves are machine-minted")


def test_there_is_no_bulk_stamp_path(tmp_path):
    # Plan §4 row 14 / DT-6: stamping without per-node verification is the exact anti-pattern the
    # evidence gate exists to prevent — the CLI must not even parse a bulk flag.
    book_dir = _seed_book(tmp_path)
    with pytest.raises(SystemExit) as excinfo:
        main(
            [
                "--book",
                BOOK,
                "--books-dir",
                str(book_dir.parent),
                "stamp",
                "--all",
                "--evidence",
                "bulk",
            ]
        )
    assert excinfo.value.code == 2  # argparse: unrecognized arguments


# --- the explainer: exact diffs from the stored witnesses (plan §4 rows 9/10) --------------------- #


def test_explainer_names_the_exact_children_and_atoms_that_moved(tmp_path):
    book_dir = _seed_book(tmp_path)
    _stamp_all(book_dir)
    # A VALID drift: move leaf n-1's sibling leaf under n-1. Root's decision stales (children
    # changed) while its extent holds (same union — the honest-cascade boundary); n-1 stales on
    # both (new child; beneath gains the leaf's body atom).
    smap = load_structure_map(_map_path(book_dir), _reader_for(book_dir))
    leaf_b = _node(json.loads(_map_path(book_dir).read_text(encoding="utf-8")), "n-0")["children"][1]
    moved_atom = next(
        n.body_atoms[0] for n in smap.projection.nodes if n.node_id == leaf_b
    )

    def move(doc):
        _node(doc, "n-0")["children"].remove(leaf_b)
        _node(doc, "n-1")["children"].append(leaf_b)

    _edit_map(book_dir, move)
    report_sec = explain_evidence_drift(book_dir, "n-1")
    assert "decision: STALE" in report_sec
    assert f"children added:   ['{leaf_b}']" in report_sec
    assert "extent: STALE" in report_sec
    # the exact atom, under the exact DIRECTION label — an entered/left swap must red here
    entered_line = next(line for line in report_sec.splitlines() if "beneath entered" in line)
    assert moved_atom in entered_line
    report_root = explain_evidence_drift(book_dir, "n-0")
    assert "decision: STALE" in report_root
    assert f"children removed: ['{leaf_b}']" in report_root
    assert "extent: fresh" in report_root  # unchanged union — the ancestor stays extent-fresh


def test_explainer_names_a_pure_reorder(tmp_path):
    book_dir = _seed_book(tmp_path)
    _stamp_all(book_dir)
    _edit_map(book_dir, lambda doc: _node(doc, "n-0")["children"].reverse())
    report = explain_evidence_drift(book_dir, "n-0")
    assert "children reordered" in report
    assert "extent: fresh" in report


def test_explainer_states_the_non_diff_states_plainly(tmp_path):
    book_dir = _seed_book(tmp_path)
    assert "missing" in explain_evidence_drift(book_dir, "n-1")  # unstamped: nothing to diff
    _stamp_all(book_dir)
    assert "both digests hold" in explain_evidence_drift(book_dir, "n-1")  # fresh
    with pytest.raises(ValueError, match="names no node"):
        explain_evidence_drift(book_dir, "n-nowhere")


# --- validate + watch: the editor loop (plan §4 row 21, DT-8) ------------------------------------- #


def test_validate_collects_instead_of_raising(tmp_path):
    book_dir = _seed_book(tmp_path)
    findings = validate_authoring(book_dir)
    assert len(findings) == 2 and all(f.startswith("[missing]") for f in findings)
    _stamp_all(book_dir)
    assert validate_authoring(book_dir) == ()
    # a broken substrate is a finding line, not a traceback
    (book_dir / STREAM_FREEZE_FILENAME).write_text("not json {", encoding="utf-8")
    findings = validate_authoring(book_dir)
    assert len(findings) == 1 and "StaleArtifactError" in findings[0]


def test_watch_revalidates_on_a_save(tmp_path):
    # Plan §4 row 21: the mtime poll re-runs validation when the map changes. The injectable
    # sleep edits the map on its first tick and interrupts on the second — no threads needed.
    book_dir = _seed_book(tmp_path)
    _stamp_all(book_dir)
    emitted: list[str] = []
    ticks = {"n": 0}

    def scripted_sleep(_interval):
        ticks["n"] += 1
        if ticks["n"] == 1:
            _edit_map(book_dir, lambda doc: _node(doc, "n-0")["children"].reverse())
        else:
            raise KeyboardInterrupt

    watch_validate(book_dir, emit=emitted.append, sleep=scripted_sleep)
    text = "\n".join(emitted)
    assert "clean" in text  # the initial pass, pre-edit
    assert "stale-decision" in text  # the post-save re-validation caught the edit


def test_cli_default_books_dir_resolves_to_the_real_engine_books():
    # Binding check (feedback_validate_bindings): the default is derived from __file__ depth —
    # the package conversion moved the file a level deeper and silently re-aimed it at
    # src/books until this pinned the resolved target.
    from engine.structure.authoring import _build_parser

    default = _build_parser().get_default("books_dir")
    assert default == Path(__file__).resolve().parents[2] / "books"
    assert default.is_dir(), f"default --books-dir {default} does not exist"


# --- CLI exit codes (plan DT-2) -------------------------------------------------------------------- #


def test_cli_exit_codes_ride_the_engine_error_taxonomy(tmp_path, capsys):
    book_dir = _seed_book(tmp_path)
    books = str(book_dir.parent)
    assert main(["--book", BOOK, "--books-dir", books, "gate"]) == 12  # evidence findings
    assert main(["--book", BOOK, "--books-dir", books, "validate"]) == 1  # findings, non-raising
    for node in ("n-0", "n-1"):
        assert (
            main(
                [
                    "--book",
                    BOOK,
                    "--books-dir",
                    books,
                    "stamp",
                    "--node",
                    node,
                    "--evidence",
                    f"verified {node}",
                ]
            )
            == 0
        )
    assert main(["--book", BOOK, "--books-dir", books, "gate"]) == 0
    assert main(["--book", BOOK, "--books-dir", books, "validate"]) == 0
    assert main(["--book", BOOK, "--books-dir", books, "explain", "--node", "n-0"]) == 0
    assert (
        main(["--book", BOOK, "--books-dir", books, "explain", "--node", "n-none"]) == 2
    )  # caller error
    capsys.readouterr()  # drain


def test_cli_entry_module_is_import_inert():
    # `python -m engine.structure.authoring` must run the CLI, but a plain import of the
    # __main__ submodule (package import-walks: pkgutil discovery, doc generators, coverage
    # import modes) must NOT execute argparse — an unguarded module-level main() call turns
    # every walk into SystemExit(2) plus usage noise on stderr. Pop the module first so the
    # import genuinely re-executes (a cached entry would pass this test vacuously).
    import importlib
    import sys

    sys.modules.pop("engine.structure.authoring.__main__", None)
    mod = importlib.import_module("engine.structure.authoring.__main__")
    assert callable(mod.main)  # the entry point is exposed, just not executed
