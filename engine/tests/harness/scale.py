"""Minimal S4.7 item-2 INV-6/INV-7 performance harness.

This is measurement support, not a benchmark framework.  It pins the preregistered red ladders,
constructs deterministic public-operation fixtures, separates serialize/load/index/operation
phases, and records raw ``perf_counter`` / ``tracemalloc`` observations.  Budget assertions live
in the unit contract and consume a saved artifact; setup or phase failures therefore cannot be
mistaken for an expected performance red.
"""

from __future__ import annotations

import gc
import hashlib
import json
import math
import statistics
import sys
import tracemalloc
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Mapping, TypeVar

import jsonschema

from engine.structure.atom_store import from_json as stream_from_json
from engine.structure.atom_store import to_json as stream_to_json
from engine.structure.atoms import Atom, Geom
from engine.structure.capture import PAGE_UNMAPPED
from engine.structure.evidence import (
    _MAX_RUN_EXPANSION,
    AuthoringEvidence,
    EvidenceEntry,
    _hash_canonical,
    decision_payload,
    evidence_findings,
    load_evidence_schema,
    render_authoring_evidence,
)
from engine.structure.lineage import ResourceLineage
from engine.structure.projection import MINTED_BY_HUMAN, MINTED_BY_MACHINE
from engine.structure.rebind import RebindContext, RebindResult, rebind
from engine.structure.roundtrip import hash_raw
from engine.structure.structure_map import (
    STRUCTURE_MAP_SCHEMA_VERSION,
    StreamAtomReader,
    StructureMap,
    build_manifest,
    load_schema,
    render_structure_map,
    structure_map_from_json,
    validate_structure_map,
)
from engine.structure.atom_store import AtomStream, assert_reference_integrity
from engine.structure.artifacts import NORMALIZER_STALE_CLASS, RESOURCE_STALE_CLASS

from harness.materialize import (
    SLOT_BODY,
    AtomSeed,
    DriftConfig,
    FixtureSpec,
    NodeSeed,
    RebindFixtureBundle,
    materialize_fixture,
)

REPETITIONS = 5
INV6_RED_TOKENS = (300, 600, 1200, 2400, 4800)
INV6_MAX_SLOPE = 1.5
INV6_MAX_ADJACENT_RATIO = 50.0
INV7_DEPTH = 3_000
INV7_MAX_SECONDS = 2.0
INV7_MAX_PEAK_BYTES = 512 * 1024 * 1024
PRIORITY4_BASELINE = (
    Path(__file__).resolve().parents[2]
    / "docs/probes/s4_7_priority4_perf_baseline.json"
)
PRIORITY5_BASELINE = (
    Path(__file__).resolve().parents[2]
    / "docs/probes/s4_7_priority5_perf_baseline.json"
)

_T = TypeVar("_T")


@dataclass(frozen=True, slots=True)
class SizeLedger:
    family: str
    L: int
    K: int
    A: int
    T: int
    D: int

    def __post_init__(self) -> None:
        values = (self.L, self.K, self.A, self.T, self.D)
        if not self.family or any(
            isinstance(value, bool) or not isinstance(value, int) or value < 1
            for value in values
        ):
            raise ValueError(
                "size ledger requires a family and positive integer L/K/A/T/D"
            )

    def to_json(self) -> dict[str, str | int]:
        return {
            "family": self.family,
            "L": self.L,
            "K": self.K,
            "A": self.A,
            "T": self.T,
            "D": self.D,
        }


@dataclass(frozen=True, slots=True)
class PhaseMeasurement:
    elapsed_seconds: tuple[float, ...]
    peak_bytes: tuple[int, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "elapsed_seconds", tuple(self.elapsed_seconds))
        object.__setattr__(self, "peak_bytes", tuple(self.peak_bytes))
        if (
            len(self.elapsed_seconds) != REPETITIONS
            or len(self.peak_bytes) != REPETITIONS
        ):
            raise ValueError(
                f"each phase requires exactly k={REPETITIONS} time and memory samples"
            )
        if any(
            not math.isfinite(value) or value <= 0 for value in self.elapsed_seconds
        ):
            raise ValueError("elapsed samples must be finite and positive")
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in self.peak_bytes
        ):
            raise ValueError("peak-memory samples must be non-negative integers")

    @property
    def median_seconds(self) -> float:
        return float(statistics.median(self.elapsed_seconds))

    @property
    def median_peak_bytes(self) -> float:
        return float(statistics.median(self.peak_bytes))

    def to_json(self) -> dict[str, object]:
        return {
            "elapsed_seconds": list(self.elapsed_seconds),
            "peak_bytes": list(self.peak_bytes),
            "median_seconds": self.median_seconds,
            "median_peak_bytes": self.median_peak_bytes,
        }


@dataclass(frozen=True, slots=True)
class RebindScaleFixture:
    ledger: SizeLedger
    bundle: RebindFixtureBundle


@dataclass(frozen=True, slots=True)
class SerializedRebindFixture:
    old_map: str
    old_streams: Mapping[str, str]
    fresh_streams: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class LoadedRebindFixture:
    old_map: StructureMap
    old_streams: Mapping[str, AtomStream]
    fresh_streams: Mapping[str, AtomStream]


@dataclass(frozen=True, slots=True)
class IndexedRebindFixture:
    loaded: LoadedRebindFixture
    old_reader: StreamAtomReader
    fresh_reader: StreamAtomReader


@dataclass(frozen=True, slots=True)
class DeepEvidenceFixture:
    ledger: SizeLedger
    structure_map: StructureMap
    evidence: AuthoringEvidence
    structure_json: str
    evidence_json: str
    decoded_witness_ids: int

    @property
    def input_bytes(self) -> int:
        return len(self.structure_json.encode()) + len(self.evidence_json.encode())


def _partition_sizes(total: int, parts: int) -> tuple[int, ...]:
    base, remainder = divmod(total, parts)
    sizes = tuple(base + (index < remainder) for index in range(parts))
    if len(sizes) != parts or sum(sizes) != total or min(sizes) < 1:
        raise AssertionError(
            "scale partition must be complete and leave every slot non-empty"
        )
    return sizes


def build_rebind_scale_fixture(target_tokens: int) -> RebindScaleFixture:
    """Build the preregistered PLL-ratio family with contiguous slot ownership."""
    if target_tokens not in INV6_RED_TOKENS:
        raise ValueError(
            f"target_tokens must be one of {INV6_RED_TOKENS}, got {target_tokens}"
        )
    atom_count = max(1, round(target_tokens / 36))
    leaf_count = max(1, round(atom_count / 40))
    atom_tokens = _partition_sizes(target_tokens, atom_count)
    leaf_atoms = _partition_sizes(atom_count, leaf_count)

    atoms: list[AtomSeed] = []
    nodes: list[NodeSeed] = [
        NodeSeed(
            "scale-root",
            "volume",
            "container",
            children=tuple(f"scale-leaf-{index:03d}" for index in range(leaf_count)),
        )
    ]
    atom_index = 0
    for leaf_index, owned_count in enumerate(leaf_atoms):
        node_id = f"scale-leaf-{leaf_index:03d}"
        keys: list[str] = []
        for _ in range(owned_count):
            key = f"scale-atom-{atom_index:04d}"
            token_count = atom_tokens[atom_index]
            text = " ".join(
                f"token{atom_index:04d}x{token_index:03d}"
                for token_index in range(token_count)
            )
            atoms.append(AtomSeed(key, text, node_id, SLOT_BODY))
            keys.append(key)
            atom_index += 1
        nodes.append(NodeSeed(node_id, "block", "leaf", body=tuple(keys)))

    bundle = materialize_fixture(
        FixtureSpec(
            "scale-root",
            tuple(nodes),
            tuple(atoms),
            require_tokenless_cases=False,
        ),
        DriftConfig(f"inv6-scale-{target_tokens}", 47_000 + target_tokens, ()),
    )
    ledger = SizeLedger(
        family="wide-rebind-pll-ratio",
        L=leaf_count,
        K=leaf_count,
        A=atom_count,
        T=sum(len(atom.text.split()) for atom in atoms),
        D=2,
    )
    if ledger.T != target_tokens or len(bundle.old_canonical.atoms) != ledger.A:
        raise AssertionError(
            "materialized scale fixture disagrees with its size ledger"
        )
    return RebindScaleFixture(ledger, bundle)


def serialize_rebind_fixture(fixture: RebindScaleFixture) -> SerializedRebindFixture:
    return SerializedRebindFixture(
        old_map=render_structure_map(fixture.bundle.old_map.doc),
        old_streams={
            stream_id: json.dumps(stream_to_json(stream), sort_keys=True)
            for stream_id, stream in fixture.bundle.old_streams.items()
        },
        fresh_streams={
            stream_id: json.dumps(stream_to_json(stream), sort_keys=True)
            for stream_id, stream in fixture.bundle.fresh_streams.items()
        },
    )


def load_rebind_fixture(serialized: SerializedRebindFixture) -> LoadedRebindFixture:
    map_doc = json.loads(serialized.old_map)
    jsonschema.validate(map_doc, load_schema())
    return LoadedRebindFixture(
        old_map=structure_map_from_json(map_doc),
        old_streams={
            stream_id: stream_from_json(json.loads(payload))
            for stream_id, payload in serialized.old_streams.items()
        },
        fresh_streams={
            stream_id: stream_from_json(json.loads(payload))
            for stream_id, payload in serialized.fresh_streams.items()
        },
    )


def _assert_stream_integrity(streams: Mapping[str, AtomStream]) -> None:
    canonical = streams["canonical"]
    witnesses = {key: value for key, value in streams.items() if key != "canonical"}
    assert_reference_integrity(canonical, witnesses)


def index_rebind_fixture(loaded: LoadedRebindFixture) -> IndexedRebindFixture:
    _assert_stream_integrity(loaded.old_streams)
    _assert_stream_integrity(loaded.fresh_streams)
    old_reader = StreamAtomReader(loaded.old_streams, "canonical")
    fresh_reader = StreamAtomReader(loaded.fresh_streams, "canonical")
    validate_structure_map(loaded.old_map, old_reader)
    return IndexedRebindFixture(loaded, old_reader, fresh_reader)


def run_indexed_rebind(indexed: IndexedRebindFixture) -> RebindResult:
    loaded = indexed.loaded
    return rebind(
        RebindContext(
            loaded.old_map,
            loaded.old_streams,
            loaded.fresh_streams,
            geometry_mode="no-geometry",
        )
    )


def run_rebind_end_to_end(fixture: RebindScaleFixture) -> RebindResult:
    return run_indexed_rebind(
        index_rebind_fixture(load_rebind_fixture(serialize_rebind_fixture(fixture)))
    )


def preflight_rebind_fixture(fixture: RebindScaleFixture) -> dict[str, object]:
    serialized = serialize_rebind_fixture(fixture)
    if (
        not serialized.old_map
        or not serialized.old_streams
        or not serialized.fresh_streams
    ):
        raise AssertionError("serialize phase produced an empty artifact")
    loaded = load_rebind_fixture(serialized)
    indexed = index_rebind_fixture(loaded)
    if len(indexed.old_reader.included_atom_ids()) != fixture.ledger.A:
        raise AssertionError("index phase did not expose every registered old atom")
    result = run_indexed_rebind(indexed)
    if len(result.report.nodes) != fixture.ledger.L + 1:
        raise AssertionError("rebind phase did not report every fixture node")
    end_to_end = run_rebind_end_to_end(fixture)
    if len(end_to_end.report.nodes) != fixture.ledger.L + 1:
        raise AssertionError("end-to-end phase did not complete")
    return {
        "serialize": True,
        "load": True,
        "index": True,
        "rebind": True,
        "end_to_end": True,
        "reported_nodes": len(result.report.nodes),
    }


def _measure_time(
    operation: Callable[[], _T], validate: Callable[[_T], None]
) -> tuple[float, ...]:
    samples: list[float] = []
    for _ in range(REPETITIONS):
        start = perf_counter()
        result = operation()
        elapsed = perf_counter() - start
        validate(result)
        samples.append(elapsed)
    return tuple(samples)


def _measure_memory(
    operation: Callable[[], _T], validate: Callable[[_T], None]
) -> tuple[int, ...]:
    samples: list[int] = []
    for _ in range(REPETITIONS):
        gc.collect()
        tracemalloc.start()
        try:
            result = operation()
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        validate(result)
        samples.append(peak)
    return tuple(samples)


def measure_phase(
    operation: Callable[[], _T], validate: Callable[[_T], None]
) -> PhaseMeasurement:
    """Measure time and Python-allocation peak independently, validating every completion."""
    return PhaseMeasurement(
        elapsed_seconds=_measure_time(operation, validate),
        peak_bytes=_measure_memory(operation, validate),
    )


def rebind_phase_operations(
    fixture: RebindScaleFixture,
) -> dict[str, tuple[Callable[[], Any], Callable[[Any], None]]]:
    serialized = serialize_rebind_fixture(fixture)
    loaded = load_rebind_fixture(serialized)
    indexed = index_rebind_fixture(loaded)

    def validate_serialized(value: SerializedRebindFixture) -> None:
        if not value.old_map or not value.old_streams or not value.fresh_streams:
            raise AssertionError("serialize phase incomplete")

    def validate_loaded(value: LoadedRebindFixture) -> None:
        if len(value.old_map.projection.nodes) != fixture.ledger.L + 1:
            raise AssertionError("load phase lost nodes")

    def validate_indexed(value: IndexedRebindFixture) -> None:
        if len(value.old_reader.included_atom_ids()) != fixture.ledger.A:
            raise AssertionError("index phase lost atoms")

    def validate_result(value: RebindResult) -> None:
        if len(value.report.nodes) != fixture.ledger.L + 1:
            raise AssertionError("rebind phase lost node outcomes")

    return {
        "serialize": (lambda: serialize_rebind_fixture(fixture), validate_serialized),
        "load": (lambda: load_rebind_fixture(serialized), validate_loaded),
        "index": (lambda: index_rebind_fixture(loaded), validate_indexed),
        "rebind": (lambda: run_indexed_rebind(indexed), validate_result),
        "end_to_end": (lambda: run_rebind_end_to_end(fixture), validate_result),
    }


def ols_log_log_slope(xs: tuple[float, ...], ys: tuple[float, ...]) -> float:
    if len(xs) != len(ys) or len(xs) < 3:
        raise ValueError(
            "growth slope requires equal x/y sequences with at least three points"
        )
    if any(value <= 0 or not math.isfinite(value) for value in (*xs, *ys)):
        raise ValueError("growth coordinates must be finite and positive")
    logs_x = tuple(math.log(value) for value in xs)
    logs_y = tuple(math.log(value) for value in ys)
    mean_x = statistics.fmean(logs_x)
    mean_y = statistics.fmean(logs_y)
    denominator = sum((value - mean_x) ** 2 for value in logs_x)
    if denominator == 0:
        raise ValueError("growth x coordinates must not be constant")
    return (
        sum(
            (x_value - mean_x) * (y_value - mean_y)
            for x_value, y_value in zip(logs_x, logs_y)
        )
        / denominator
    )


def adjacent_ratios(values: tuple[float, ...]) -> tuple[float, ...]:
    if len(values) < 2 or any(
        value <= 0 or not math.isfinite(value) for value in values
    ):
        raise ValueError("adjacent ratios require at least two finite positive values")
    return tuple(right / left for left, right in zip(values, values[1:]))


def growth_summary(xs: tuple[float, ...], ys: tuple[float, ...]) -> dict[str, object]:
    return {
        "slope": ols_log_log_slope(xs, ys),
        "adjacent_ratios": list(adjacent_ratios(ys)),
        "max_slope": INV6_MAX_SLOPE,
        "max_adjacent_ratio": INV6_MAX_ADJACENT_RATIO,
    }


def assert_growth_within_limits(summary: Mapping[str, object], *, metric: str) -> None:
    slope = float(summary["slope"])
    ratios = tuple(float(value) for value in summary["adjacent_ratios"])
    if slope > INV6_MAX_SLOPE:
        raise AssertionError(
            f"INV-6 {metric} log-log slope {slope:.6f} exceeds preregistered {INV6_MAX_SLOPE}"
        )
    oversized = tuple(value for value in ratios if value > INV6_MAX_ADJACENT_RATIO)
    if oversized:
        raise AssertionError(
            f"INV-6 {metric} adjacent ratio(s) {oversized} exceed preregistered "
            f"{INV6_MAX_ADJACENT_RATIO}"
        )


def _deep_atom(index: int) -> Atom:
    text = f"deep-token-{index:07d}"
    return Atom(
        atom_id=f"deep-atom-{index:07d}",
        text=text,
        raw_span=(0, len(text)),
        raw_source_hash=hash_raw(text),
        page_range=PAGE_UNMAPPED,
        norm_layer="raw",
        geom=Geom.absent(),
        capture_provenance_class="body",
    )


def _deep_structure_document(depth: int, canonical: AtomStream) -> dict[str, object]:
    nodes: list[dict[str, object]] = []
    for index in range(depth):
        container_id = f"deep-container-{index:07d}"
        leaf_id = f"deep-leaf-{index:07d}"
        children = [leaf_id]
        if index + 1 < depth:
            children.append(f"deep-container-{index + 1:07d}")
        nodes.extend(
            (
                {
                    "node_id": container_id,
                    "node_class": "container",
                    "minted_by": MINTED_BY_HUMAN,
                    "children": children,
                },
                {
                    "node_id": leaf_id,
                    "node_class": "block",
                    "minted_by": MINTED_BY_MACHINE,
                    "body_atoms": [f"deep-atom-{index:07d}"],
                },
            )
        )
    return {
        "schema_version": STRUCTURE_MAP_SCHEMA_VERSION,
        "root_id": "deep-container-0000000",
        "map_revision": 1,
        "block_vocabulary": [
            {"name": "block", "kind": "leaf", "status": "active"},
            {"name": "container", "kind": "container", "status": "active"},
        ],
        "handle_policies": {"block": "position-path", "container": "position-path"},
        "furniture_atoms": [],
        "aliases": [],
        "manifest": build_manifest(
            streams={canonical.stream_id: canonical},
            canonical_stream_id=canonical.stream_id,
            resource_lineage=ResourceLineage(
                resource_version="s4.7-deep-v1",
                resource_descriptor='{"fixture":"s4.7-deep-evidence"}',
                resource_stale_class=RESOURCE_STALE_CLASS,
                normalizer_version="s4.7-deep-normalizer-v1",
                normalizer_descriptor='{"identity":true}',
                normalizer_stale_class=NORMALIZER_STALE_CLASS,
            ),
            profile_version="s4.7-deep-profile-v1",
            recognizer_version="s4.7-deep-recognizer-v1",
        ),
        "nodes": nodes,
    }


def build_deep_evidence_fixture(depth: int = INV7_DEPTH) -> DeepEvidenceFixture:
    if depth != INV7_DEPTH:
        raise ValueError(f"INV-7 depth is preregistered at {INV7_DEPTH}, got {depth}")
    canonical = AtomStream.canonical(tuple(_deep_atom(index) for index in range(depth)))
    document = _deep_structure_document(depth, canonical)
    jsonschema.validate(document, load_schema())
    structure_map = structure_map_from_json(document)
    reader = StreamAtomReader({canonical.stream_id: canonical}, canonical.stream_id)
    validate_structure_map(structure_map, reader)
    structure_json = render_structure_map(document)
    reparsed_structure = json.loads(structure_json)
    jsonschema.validate(reparsed_structure, load_schema())

    atom_ids = tuple(atom.atom_id for atom in canonical.atoms)
    entries: list[EvidenceEntry] = []
    for index in range(depth):
        node = structure_map.projection.by_id[f"deep-container-{index:07d}"]
        d_payload = decision_payload(node)
        e_payload = {
            "own": {"heading": (), "signature": ()},
            "beneath": atom_ids[index:],
        }
        entries.append(
            EvidenceEntry(
                node_id=node.node_id,
                decision_digest=_hash_canonical(d_payload),
                extent_digest=_hash_canonical(e_payload),
                evidence=f"synthetic deep-chain rationale {index:07d}",
                authored_at_revision=1,
                decision_payload=d_payload,
                extent_payload=e_payload,
            )
        )
    evidence = AuthoringEvidence("s4.7-deep-evidence", tuple(entries))
    evidence_json = render_authoring_evidence(evidence)
    reparsed_evidence = json.loads(evidence_json)
    jsonschema.validate(reparsed_evidence, load_evidence_schema())
    decoded_witness_ids = depth * (depth + 1) // 2
    if decoded_witness_ids <= _MAX_RUN_EXPANSION:
        raise AssertionError(
            "deep fixture must prove why the persisted decode path is bypassed"
        )
    if depth <= sys.getrecursionlimit():
        raise AssertionError(
            "deep fixture must exceed the ordinary Python recursion limit"
        )
    ledger = SizeLedger(
        "deep-evidence-isolated-core", depth, depth, depth, depth, depth
    )
    return DeepEvidenceFixture(
        ledger,
        structure_map,
        evidence,
        structure_json,
        evidence_json,
        decoded_witness_ids,
    )


def preflight_deep_evidence_fixture(fixture: DeepEvidenceFixture) -> dict[str, object]:
    if len(fixture.structure_map.projection.nodes) != 2 * fixture.ledger.D:
        raise AssertionError("deep fixture node construction incomplete")
    if len(fixture.evidence.entries) != fixture.ledger.D:
        raise AssertionError("deep fixture evidence construction incomplete")
    if not fixture.structure_json.endswith("\n") or not fixture.evidence_json.endswith(
        "\n"
    ):
        raise AssertionError("deep fixture serialization incomplete")
    return {
        "construction": True,
        "schema_validation": True,
        "serialization": True,
        "iterative_beyond_recursion_limit": fixture.ledger.D > sys.getrecursionlimit(),
        "persisted_decode_feasible": False,
        "decode_budget": _MAX_RUN_EXPANSION,
        "decoded_witness_ids": fixture.decoded_witness_ids,
        "input_bytes": fixture.input_bytes,
        "node_count": len(fixture.structure_map.projection.nodes),
    }


def measure_evidence_findings(fixture: DeepEvidenceFixture) -> PhaseMeasurement:
    def operation() -> tuple[tuple[str, str], ...]:
        return evidence_findings(fixture.evidence, fixture.structure_map.projection)

    def validate(value: tuple[tuple[str, str], ...]) -> None:
        if value != ():
            raise AssertionError(
                f"deep evidence fixture must be fresh, got {value[:1]}"
            )

    return measure_phase(operation, validate)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_priority4_baseline(
    path: Path = PRIORITY4_BASELINE, *, verify_source_identity: bool
) -> dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") not in {
        "s4.7-item2-priority4-perf-baseline@v1",
        "s4.7-perf-baseline@v2",
    }:
        raise ValueError("unexpected S4.7 Priority 4 baseline schema")
    if data.get("repetitions") != REPETITIONS:
        raise ValueError("baseline repetition count disagrees with preregistration")
    points = data.get("inv6", {}).get("points", [])
    if [point.get("ledger", {}).get("T") for point in points] != list(INV6_RED_TOKENS):
        raise ValueError("baseline INV-6 ladder disagrees with preregistration")
    if not all(all(point.get("preflight", {}).values()) for point in points):
        raise ValueError("baseline contains an incomplete INV-6 phase preflight")
    inv7_preflight = data.get("inv7", {}).get("preflight", {})
    required = {
        "construction",
        "schema_validation",
        "serialization",
        "iterative_beyond_recursion_limit",
    }
    if not all(inv7_preflight.get(key) is True for key in required):
        raise ValueError("baseline contains an incomplete INV-7 preflight")
    if verify_source_identity:
        root = Path(__file__).resolve().parents[2]
        for relative, expected in data.get("source_identity", {}).items():
            if sha256_file(root / relative) != expected:
                raise ValueError(f"baseline source identity is stale for {relative}")
    return data
