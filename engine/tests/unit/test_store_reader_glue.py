"""S4.6a — the store-backed reader glue: workspace → ``load_stream``× → ``StreamAtomReader``,
with ``assert_reference_integrity`` composed on load (runway.md §3 item 2; issue #32).

``StreamAtomReader`` takes in-memory streams; before this glue nothing loaded a workspace's
*persisted* streams into a reader — the seam both the S4.6 authoring gate and S5's re-bind consume.
The invariants under test, each proven red by the mutation hunt (red-first, §9):

- ``load_workspace_streams`` returns EVERY persisted stream, round-trip-checked by ``load_stream``;
- **reference integrity is asserted on load** — a persisted canonical stream with a dangling
  ``derived_from`` back-link reds at the glue (``CaptureError``), never rides silently into a reader;
- one canonical anchor per workspace: the named canonical stream must be canonical-kind, and no
  *other* stream may be canonical-kind — either fault is a stale substrate, not a loadable one;
- an absent substrate (no streams / no canonical id) is ``MissingInputError``, absent-not-stale;
- ``workspace_reader`` wires the loaded streams into a live ``StreamAtomReader`` (canonical
  included universe; witness ids resolvable) and honors a non-default ``canonical_stream_id``.
"""

from __future__ import annotations

import dataclasses

import pytest

from engine.errors import CaptureError, MissingInputError, StaleArtifactError
from engine.paths import BookWorkspace
from engine.structure import (
    CANONICAL,
    WITNESS,
    AtomStream,
    build_canonical,
    capture_witness,
    gap_records,
    load_workspace_streams,
    save_stream,
    workspace_reader,
)
from engine.structure.atom_store import to_json as stream_envelope_json
from engine.structure.atoms import AtomDerivation

W1 = "Alpha block one.\n\nBeta block two.\n\nGamma block three.\n"
W2 = "Alpha block one.\n\nBeta blok two.\n\nGamma block three.\n"


def _streams(canonical_stream_id: str = "canonical") -> dict[str, AtomStream]:
    a1 = capture_witness(W1, "w1")
    a2 = capture_witness(W2, "w2")
    canon = build_canonical({"w1": a1, "w2": a2}, ["w1", "w2"])
    return {
        "w1": AtomStream.witness("w1", a1, gap_records(a1, W1), W1),
        "w2": AtomStream.witness("w2", a2, gap_records(a2, W2), W2),
        canonical_stream_id: AtomStream.canonical(canon, stream_id=canonical_stream_id),
    }


def _workspace(tmp_path) -> BookWorkspace:
    return BookWorkspace.for_book("testbook", tmp_path).ensure()


def _persist(workspace: BookWorkspace, streams: dict[str, AtomStream]) -> None:
    for stream in streams.values():
        save_stream(workspace, stream)


# --- the happy path: persisted substrate → streams → reader ------------------------------------ #


def test_glue_returns_every_persisted_stream_roundtripped(tmp_path):
    workspace = _workspace(tmp_path)
    streams = _streams()
    _persist(workspace, streams)
    loaded = load_workspace_streams(workspace)
    assert sorted(loaded) == ["canonical", "w1", "w2"]
    for stream_id, stream in streams.items():
        # envelope-equality: the persisted round trip changed nothing the store serializes
        assert stream_envelope_json(loaded[stream_id]) == stream_envelope_json(stream)
    assert loaded["canonical"].kind == CANONICAL
    assert loaded["w1"].kind == WITNESS


def test_workspace_reader_is_a_live_stream_atom_reader(tmp_path):
    workspace = _workspace(tmp_path)
    streams = _streams()
    _persist(workspace, streams)
    reader = workspace_reader(workspace)
    canonical = streams["canonical"]
    assert reader.included_atom_ids() == tuple(a.atom_id for a in canonical.atoms)
    # witness-side resolution: the reader's contains/scope_of span the union, not just canonical
    witness_atom = streams["w1"].atoms[0]
    assert reader.contains(witness_atom.atom_id)
    assert reader.scope_of(witness_atom.atom_id) == witness_atom.processing_scope
    assert not reader.contains("no_such_atom")


def test_glue_honors_a_non_default_canonical_stream_id(tmp_path):
    workspace = _workspace(tmp_path)
    _persist(workspace, _streams(canonical_stream_id="canon2"))
    loaded = load_workspace_streams(workspace, canonical_stream_id="canon2")
    assert loaded["canon2"].kind == CANONICAL
    reader = workspace_reader(workspace, canonical_stream_id="canon2")
    assert reader.included_atom_ids()
    # and the DEFAULT id is now genuinely absent, not silently substituted
    with pytest.raises(MissingInputError):
        load_workspace_streams(workspace)


# --- reference integrity composes on load ------------------------------------------------------- #


def test_reference_integrity_is_asserted_on_load(tmp_path):
    # A persisted canonical atom whose derived_from names a ghost witness passes load_stream's
    # per-stream tiers (text/hash untouched) — ONLY the glue's composed cross-stream tier catches
    # it. Dropping that compose call is exactly the mutation this test kills.
    workspace = _workspace(tmp_path)
    streams = _streams()
    atoms = list(streams["canonical"].atoms)
    atoms[0] = dataclasses.replace(
        atoms[0], derived_from=(AtomDerivation(witness="ghost", atom_id="ghost_00000"),)
    )
    streams["canonical"] = AtomStream.canonical(atoms)
    _persist(workspace, streams)
    with pytest.raises(CaptureError, match="ghost"):
        load_workspace_streams(workspace)


# --- absent substrate: missing-input, not stale -------------------------------------------------- #


def test_empty_workspace_is_missing_input(tmp_path):
    # Message pinned so the check stays killable: without it the canonical-membership check would
    # raise the same type for the empty case, and a dropped empty-check would hide behind it.
    with pytest.raises(MissingInputError, match="no persisted atom streams"):
        load_workspace_streams(_workspace(tmp_path))


def test_missing_canonical_stream_is_missing_input(tmp_path):
    workspace = _workspace(tmp_path)
    streams = _streams()
    del streams["canonical"]
    _persist(workspace, streams)
    # Same masking discipline: load_stream's own missing-file error is also MissingInputError,
    # so the glue's membership check is pinned by its distinct wording.
    with pytest.raises(MissingInputError, match="not among the persisted streams"):
        load_workspace_streams(workspace)


# --- one canonical anchor per workspace ----------------------------------------------------------- #


def test_witness_kind_under_the_canonical_id_is_stale(tmp_path):
    # One axis only: the named canonical stream is witness-kind and NO canonical-kind stream
    # exists anywhere else — a second one would trip the rogue-canonical check, whose message
    # also names "canonical", masking a dropped kind check (the mutation hunt caught exactly
    # that with the first fixture). The match pins the kind check's own wording.
    workspace = _workspace(tmp_path)
    streams = _streams()
    del streams["canonical"]
    a1 = capture_witness(W1, "canonical")
    streams["canonical"] = AtomStream.witness("canonical", a1, gap_records(a1, W1), W1)
    _persist(workspace, streams)
    with pytest.raises(StaleArtifactError, match="must be the canonical projection"):
        load_workspace_streams(workspace)


def test_a_second_canonical_kind_stream_is_stale(tmp_path):
    workspace = _workspace(tmp_path)
    streams = _streams()
    streams["canon2"] = AtomStream.canonical(streams["canonical"].atoms, stream_id="canon2")
    _persist(workspace, streams)
    with pytest.raises(StaleArtifactError, match="canon2"):
        load_workspace_streams(workspace)
