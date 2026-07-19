"""Shared substrate-first context for S4.6 authoring reads and writes.

This module is deliberately below both the terminal authoring toolkit and the machine review
bridge.  A command that needs a current structure-authoring view must pass through this one loader;
otherwise a visual packet could accidentally acquire a weaker freshness posture than the CLI gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from engine.errors import MissingInputError, StaleArtifactError
from engine.paths import BookWorkspace
from engine.structure.artifacts import authoring_evidence_path, structure_map_path
from engine.structure.atom_store import AtomStream, load_workspace_streams
from engine.structure.evidence import AuthoringEvidence, load_authoring_evidence
from engine.structure.freeze import assert_freeze_matches, load_freeze_record
from engine.structure.structure_map import StreamAtomReader, StructureMap, load_structure_map

STREAM_FREEZE_FILENAME = "stream_freeze.json"


@dataclass(frozen=True, slots=True)
class AuthoringContext:
    """A fully checked S4.6 substrate plus the optional authoring-evidence state."""

    book: str
    book_dir: Path
    workspace: BookWorkspace
    canonical_stream_id: str
    freeze_record: Mapping
    freeze_path: Path
    streams: Mapping[str, AtomStream]
    reader: StreamAtomReader
    smap: StructureMap
    structure_map_path: Path
    evidence: AuthoringEvidence
    evidence_path: Path


def workspace_for_book(book_dir: Path) -> BookWorkspace:
    """Resolve the established ``books/<book>`` layout without creating directories."""

    book_dir = Path(book_dir)
    return BookWorkspace.for_book(book_dir.name, book_dir.parent)


def load_authoring_context(
    book_dir: Path, *, canonical_stream_id: str = "canonical"
) -> AuthoringContext:
    """Load freeze → streams → pin match → map → optional evidence, in that exact order.

    Each layer retains its native typed failure contract.  An absent sidecar is the legitimate
    all-missing authoring state and is represented by an empty, book-bound ``AuthoringEvidence``.
    """

    book_dir = Path(book_dir)
    freeze_path = book_dir / STREAM_FREEZE_FILENAME
    record = load_freeze_record(freeze_path)
    book = record["book"]
    if book != book_dir.name:
        raise StaleArtifactError(
            f"freeze pin at {freeze_path} names book {book!r}, but the book dir is "
            f"{book_dir.name!r} — wrong pin for this book"
        )
    workspace = workspace_for_book(book_dir)
    streams = load_workspace_streams(workspace, canonical_stream_id=canonical_stream_id)
    assert_freeze_matches(record, streams)
    reader = StreamAtomReader(streams, canonical_stream_id)
    map_path = structure_map_path(workspace)
    smap = load_structure_map(map_path, reader)
    evidence_path = authoring_evidence_path(workspace)
    try:
        evidence = load_authoring_evidence(evidence_path, expected_book=book)
    except MissingInputError:
        evidence = AuthoringEvidence(book=book, entries=())
    return AuthoringContext(
        book=book,
        book_dir=book_dir,
        workspace=workspace,
        canonical_stream_id=canonical_stream_id,
        freeze_record=MappingProxyType(dict(record)),
        freeze_path=freeze_path,
        streams=MappingProxyType(dict(streams)),
        reader=reader,
        smap=smap,
        structure_map_path=map_path,
        evidence=evidence,
        evidence_path=evidence_path,
    )

