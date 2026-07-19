"""Focused diagnostic fixture and measurement for production evidence restamping.

The S4.7 registered rebind fixture intentionally carries no authoring evidence, so it cannot
measure :func:`engine.structure.rebind._restamp_evidence`.  This diagnostic reuses the validated
depth-3,000 INV-7 topology, remints every atom id, and exercises the all-bound successful restamp
path directly.  Fixture construction, validation, and the independent expected output are built
before either timing or allocation measurement begins.
"""

from __future__ import annotations

import dataclasses
import gc
import hashlib
import statistics
import tracemalloc
from dataclasses import dataclass
from time import perf_counter, process_time
from typing import Callable

from engine.structure.atom_store import AtomStream
from engine.structure.evidence import (
    AuthoringEvidence,
    EvidenceEntry,
    _hash_canonical,
    extent_payload,
    render_authoring_evidence,
)
from engine.structure.projection import (
    LeafNode,
    ProjectionMap,
    validate_atom_existence,
    validate_projection,
    validate_reference_integrity,
)
from engine.structure.rebind import _restamp_evidence
from engine.structure.structure_map import StreamAtomReader
from harness.scale import (
    INV7_DEPTH,
    REPETITIONS,
    _deep_atom,
    build_deep_evidence_fixture,
)


@dataclass(frozen=True, slots=True)
class RestampDiagnosticFixture:
    evidence: AuthoringEvidence
    migrated_projection: ProjectionMap
    bound_node_ids: frozenset[str]
    expected: tuple[EvidenceEntry, ...]
    expected_sha256: str
    preflight: dict[str, object]


@dataclass(frozen=True, slots=True)
class RestampDiagnosticMeasurement:
    wall_seconds: tuple[float, ...]
    cpu_seconds: tuple[float, ...]
    peak_bytes: tuple[int, ...]

    @property
    def median_wall_seconds(self) -> float:
        return float(statistics.median(self.wall_seconds))

    @property
    def median_cpu_seconds(self) -> float:
        return float(statistics.median(self.cpu_seconds))

    @property
    def median_peak_bytes(self) -> float:
        return float(statistics.median(self.peak_bytes))

    def to_json(self) -> dict[str, object]:
        return {
            "wall_seconds": list(self.wall_seconds),
            "cpu_seconds": list(self.cpu_seconds),
            "peak_bytes": list(self.peak_bytes),
            "median_wall_seconds": self.median_wall_seconds,
            "median_cpu_seconds": self.median_cpu_seconds,
            "median_peak_bytes": self.median_peak_bytes,
        }


def _fresh_atom_id(index: int) -> str:
    return f"restamp-atom-{index:07d}"


def _expected_restamp(
    evidence: AuthoringEvidence, projection: ProjectionMap
) -> tuple[EvidenceEntry, ...]:
    """Independent scalar semantic reference, built outside every measured span."""
    expected: list[EvidenceEntry] = []
    for entry in evidence.entries:
        node = projection.by_id[entry.node_id]
        payload = extent_payload(node, projection)
        expected.append(
            EvidenceEntry(
                node_id=entry.node_id,
                decision_digest=entry.decision_digest,
                extent_digest=_hash_canonical(payload),
                evidence=entry.evidence,
                authored_at_revision=entry.authored_at_revision,
                decision_payload=dict(entry.decision_payload),
                extent_payload=payload,
            )
        )
    return tuple(expected)


def build_restamp_diagnostic_fixture() -> RestampDiagnosticFixture:
    """Build and fully validate the fixed depth-3,000 all-bound diagnostic fixture."""
    source = build_deep_evidence_fixture()
    old_to_fresh = {
        f"deep-atom-{index:07d}": _fresh_atom_id(index) for index in range(INV7_DEPTH)
    }
    canonical = AtomStream.canonical(
        tuple(
            dataclasses.replace(_deep_atom(index), atom_id=_fresh_atom_id(index))
            for index in range(INV7_DEPTH)
        )
    )
    migrated = ProjectionMap(
        root_id=source.structure_map.projection.root_id,
        nodes=tuple(
            dataclasses.replace(
                node,
                body_atoms=tuple(old_to_fresh[atom_id] for atom_id in node.body_atoms),
            )
            if isinstance(node, LeafNode)
            else node
            for node in source.structure_map.projection.nodes
        ),
    )
    reader = StreamAtomReader({canonical.stream_id: canonical}, canonical.stream_id)
    validate_reference_integrity(migrated)
    validate_projection(migrated, reader)
    validate_atom_existence(migrated, reader)

    bound_node_ids = frozenset(node.node_id for node in migrated.nodes)
    expected = _expected_restamp(source.evidence, migrated)
    expected_sidecar = render_authoring_evidence(
        AuthoringEvidence(book=source.evidence.book, entries=expected)
    )
    expected_sha256 = hashlib.sha256(expected_sidecar.encode("utf-8")).hexdigest()
    if len(expected) != INV7_DEPTH or len(bound_node_ids) != 2 * INV7_DEPTH:
        raise AssertionError("restamp diagnostic construction is incomplete")
    if any(
        old.extent_digest == fresh.extent_digest
        for old, fresh in zip(source.evidence.entries, expected)
    ):
        raise AssertionError("restamp diagnostic must remint every stored extent")

    return RestampDiagnosticFixture(
        evidence=source.evidence,
        migrated_projection=migrated,
        bound_node_ids=bound_node_ids,
        expected=expected,
        expected_sha256=expected_sha256,
        preflight={
            "construction": True,
            "source_fixture_validation": True,
            "migrated_reference_validation": True,
            "migrated_projection_validation": True,
            "migrated_atom_existence_validation": True,
            "all_bound": True,
            "depth": INV7_DEPTH,
            "projection_nodes": len(migrated.nodes),
            "evidence_entries": len(source.evidence.entries),
            "bound_node_ids": len(bound_node_ids),
            "reminted_atoms": len(canonical.atoms),
            "expected_entries": len(expected),
            "expected_sha256": expected_sha256,
        },
    )


def _operation(fixture: RestampDiagnosticFixture) -> tuple[EvidenceEntry, ...]:
    """The real production operation under measurement — deliberately no surrogate."""
    return _restamp_evidence(
        fixture.evidence, fixture.migrated_projection, set(fixture.bound_node_ids)
    )


def _validate_output(
    value: tuple[EvidenceEntry, ...], fixture: RestampDiagnosticFixture
) -> None:
    if value != fixture.expected:
        raise AssertionError(
            "production restamp output differs from the scalar semantic reference"
        )


def measure_restamp_diagnostic(
    fixture: RestampDiagnosticFixture,
    *,
    progress: Callable[[str, int, int, dict[str, float | int]], None] | None = None,
) -> RestampDiagnosticMeasurement:
    """Measure five wall/CPU samples and five separate allocation samples.

    Output equivalence is checked after every production call but outside its measured span.
    ``tracemalloc`` is active only for the allocation series, never for wall/CPU timing.
    """
    wall_samples: list[float] = []
    cpu_samples: list[float] = []
    peak_samples: list[int] = []
    publish = progress or (lambda *_args: None)

    for repetition in range(1, REPETITIONS + 1):
        publish("time-start", repetition, REPETITIONS, {})
        cpu_start = process_time()
        wall_start = perf_counter()
        result = _operation(fixture)
        wall_elapsed = perf_counter() - wall_start
        cpu_elapsed = process_time() - cpu_start
        _validate_output(result, fixture)
        wall_samples.append(wall_elapsed)
        cpu_samples.append(cpu_elapsed)
        publish(
            "time-finish",
            repetition,
            REPETITIONS,
            {"wall_seconds": wall_elapsed, "cpu_seconds": cpu_elapsed},
        )
        del result

    for repetition in range(1, REPETITIONS + 1):
        gc.collect()
        publish("allocation-start", repetition, REPETITIONS, {})
        tracemalloc.start()
        try:
            result = _operation(fixture)
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        _validate_output(result, fixture)
        peak_samples.append(peak)
        publish(
            "allocation-finish",
            repetition,
            REPETITIONS,
            {"peak_bytes": peak},
        )
        del result

    return RestampDiagnosticMeasurement(
        tuple(wall_samples), tuple(cpu_samples), tuple(peak_samples)
    )
