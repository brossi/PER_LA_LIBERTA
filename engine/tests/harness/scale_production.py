"""Production S4.7 scale, native-RSS, and correctness-at-density harness.

Unlike :mod:`harness.scale` (the immutable item-2 red scaffold), this module exercises the
as-built #48 mechanism through real atom-store workspaces and a spawn-only child process.  Each
RSS result reports the three ratified nested quantities: conservative lifetime ``ru_maxrss``,
absolute sampled peak during the named phase, and incremental peak above the explicit
post-materialization/setup baseline.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
import multiprocessing as mp
import os
import queue
import resource
import shutil
import statistics
import sys
import tempfile
import time
import traceback
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Mapping, Protocol, Sequence

import psutil

from engine.paths import BookWorkspace
from engine.structure.atom_store import load_workspace_streams, save_stream
from engine.structure.geom_regate import MODE_NO_GEOMETRY
from engine.structure.reanchor import (
    BoundaryAnchorBatchLocator,
    materialize_token_stream,
)
from engine.structure.rebind import RebindContext, RebindPolicy, RebindResult, rebind
from engine.structure.rebind_telemetry import (
    NULL_REBIND_TELEMETRY,
    REBIN_TELEMETRY_STAGES,
    RebindTelemetry,
)
from engine.structure.structure_map import (
    StreamAtomReader,
    StructureMap,
    load_structure_map,
    structure_map_path,
    validate_structure_map,
    write_structure_map,
)

from harness.materialize import (
    SLOT_BODY,
    AtomSeed,
    DriftConfig,
    DriftOperation,
    FixtureSpec,
    NodeSeed,
    RebindFixtureBundle,
    materialize_fixture,
)
from harness.oracle import (
    AllowedBind,
    ObservedBind,
    SlotRef,
    assert_bound_subset_and_disjoint,
    diagnose_case,
)
from harness.scale import (
    INV6_MAX_ADJACENT_RATIO,
    INV6_MAX_SLOPE,
    SizeLedger,
    adjacent_ratios,
    ols_log_log_slope,
)

ScaleShape = Literal["wide", "deep"]
ScalePhase = Literal["serialize", "load", "index", "rebind", "end_to_end"]
ScaleSamplePhase = ScalePhase | Literal["allocation_probe", "materialize"]
ProductionFixtureVariant = Literal["identical", "drift"]

SCALE_SHAPES: tuple[ScaleShape, ...] = ("wide", "deep")
SCALE_PHASES: tuple[ScalePhase, ...] = (
    "serialize",
    "load",
    "index",
    "rebind",
    "end_to_end",
)
SMALL_ATOM_LADDER = (10, 100, 1_000)
PRODUCTION_ATOM_LADDER = (1_000, 10_000, 100_000)
PRODUCTION_REPETITIONS = 5
TOKENS_PER_ATOM = 36

ABSOLUTE_END_TO_END_ATOM_COUNT = 100_000
ABSOLUTE_END_TO_END_MAX_SECONDS = 300.0
ABSOLUTE_LIFETIME_RSS_MAX_BYTES = 6 * 1024**3

RSS_SAMPLE_INTERVAL_SECONDS = 0.005
RSS_START_METHOD = "spawn"
RSS_PROBE_BYTES = 64 * 1024 * 1024
RSS_PROBE_HOLD_SECONDS = 0.050
PROGRESS_POLL_INTERVAL_SECONDS = 15.0
OPTIMIZATION_PROGRESS_POLL_INTERVAL_SECONDS = 5.0
PROGRESS_PREFIX = "S4.7_SCALE_PROGRESS"
PROGRESS_HUMAN_PREFIX = "S4.7 SCALE"
PROGRESS_LOG_ENV = "S4_7_PROGRESS_LOG"
PROGRESS_ACTIVE_STATE_ENV = "S4_7_ACTIVE_STATE"
PROGRESS_FORMAT_ENV = "S4_7_PROGRESS_FORMAT"
PROGRESS_RUN_ID_ENV = "S4_7_RUN_ID"
PROGRESS_RUN_STARTED_NS_ENV = "S4_7_RUN_STARTED_MONOTONIC_NS"
PROGRESS_POLL_INTERVAL_ENV = "S4_7_PROGRESS_POLL_INTERVAL_SECONDS"
PROGRESS_TELEMETRY_SCHEMA = "s4.7-scale-progress@v2"
RUNTIME_TELEMETRY_SCHEMA = "s4.7-runtime-telemetry@v1"
SCALE_SUBSTRATE_SCHEMA = "s4.7-scale-substrate@v1"

DENSITY_REQUESTED_UNIQUE_FRACTIONS = (0.71, 0.60, 0.48, 0.36, 0.24, 0.12)
DENSITY_SLOT_COUNT = 240
DENSITY_SLOT_LADDER = (24, 240, 2_400)
DENSITY_REPETITIONS = 3
DENSITY_TOKENS_PER_SLOT = 8

_PROGRESS_SEQUENCE = itertools.count(1)


def configured_progress_poll_interval_seconds() -> float:
    """Return the run-scoped heartbeat cadence, preserving the 15-second routine default."""
    configured = os.environ.get(PROGRESS_POLL_INTERVAL_ENV)
    if configured is None:
        return PROGRESS_POLL_INTERVAL_SECONDS
    try:
        interval = float(configured)
    except ValueError as exc:
        raise ValueError(
            f"{PROGRESS_POLL_INTERVAL_ENV} must be a positive finite number"
        ) from exc
    if not math.isfinite(interval) or interval <= 0:
        raise ValueError(
            f"{PROGRESS_POLL_INTERVAL_ENV} must be a positive finite number"
        )
    return interval

_HARNESS_TELEMETRY_STAGES = (
    "idle",
    "setup.prepare",
    "setup.materialize-fixture",
    "setup.clone-substrate",
    "setup.persist-prerequisites",
    "setup.load-prerequisites",
    "setup.index-prerequisites",
    "named.allocation-probe",
    "named.materialize",
    "named.serialize",
    "named.load",
    "named.index",
    "named.rebind",
    "named.end-to-end",
    "persist.prepare-workspaces",
    "persist.old-streams",
    "persist.fresh-streams",
    "persist.structure-map",
    "load.old-streams",
    "load.fresh-streams",
    "load.structure-map",
    "index.readers",
    "index.validate-map",
    "index.compare-cardinality",
    "finalize.cache-substrate",
    *REBIN_TELEMETRY_STAGES,
)
_TELEMETRY_STAGE_TO_ID = {
    stage: index for index, stage in enumerate(_HARNESS_TELEMETRY_STAGES)
}


@dataclass(frozen=True, slots=True)
class ProductionScaleRecipe:
    shape: ScaleShape
    atom_count: int
    tokens_per_atom: int = TOKENS_PER_ATOM

    def __post_init__(self) -> None:
        if self.shape not in SCALE_SHAPES:
            raise ValueError(f"unknown scale shape {self.shape!r}")
        if isinstance(self.atom_count, bool) or self.atom_count < 1:
            raise ValueError("atom_count must be a positive int")
        if isinstance(self.tokens_per_atom, bool) or self.tokens_per_atom < 3:
            raise ValueError("tokens_per_atom must be an int >= 3")

    @property
    def ledger(self) -> SizeLedger:
        leaves = max(1, round(self.atom_count / 40))
        return SizeLedger(
            family=f"{self.shape}-rebind-production",
            L=leaves,
            K=leaves,
            A=self.atom_count,
            T=self.atom_count * self.tokens_per_atom,
            D=4 if self.shape == "wide" else leaves,
        )


@dataclass(frozen=True, slots=True)
class ScaleProgressDescriptor:
    shape: ScaleShape
    atom_count: int
    phase: ScalePhase | Literal["materialize"]
    repetition: int
    repetitions: int
    measurement_index: int
    measurement_total: int
    fixture_variant: ProductionFixtureVariant | None = None

    def to_json(self) -> dict[str, object]:
        data = asdict(self)
        if self.phase == "materialize":
            data.update(
                {
                    "phase_index": 0,
                    "phase_total": len(SCALE_PHASES),
                    "step_coordinate": "prep",
                    "point_step_index": 0,
                    "point_step_total": len(SCALE_PHASES) * self.repetitions,
                }
            )
            return data
        phase_index = SCALE_PHASES.index(self.phase) + 1
        data.update(
            {
                "phase_index": phase_index,
                "phase_total": len(SCALE_PHASES),
                "step_coordinate": f"{phase_index}.{self.repetition}",
                "point_step_index": (
                    (phase_index - 1) * self.repetitions + self.repetition
                ),
                "point_step_total": len(SCALE_PHASES) * self.repetitions,
            }
        )
        return data


ProgressEventCallback = Callable[[dict[str, object]], None]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_active_state_write(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        delete=False,
    )
    temporary = Path(handle.name)
    try:
        with handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _human_progress_line(payload: Mapping[str, object]) -> str:
    event = str(payload.get("event", "event"))
    measurement = ""
    if payload.get("measurement_index") is not None:
        measurement = (
            f"[{payload['measurement_index']}/{payload.get('measurement_total', '?')}] "
        )
    point = ""
    if payload.get("shape") is not None:
        variant = (
            f"/{payload['fixture_variant']}"
            if payload.get("fixture_variant") is not None
            else ""
        )
        point = f"{payload['shape']}{variant} A={int(payload.get('atom_count', 0)):,} "
    step = ""
    if payload.get("step_coordinate") is not None:
        step = (
            f"step {payload['step_coordinate']} "
            f"({payload.get('point_step_index', '?')}/"
            f"{payload.get('point_step_total', '?')}) "
        )
    stage = str(payload.get("internal_stage") or payload.get("state") or "")
    stage_text = f"| {stage} " if stage else ""
    work_text = ""
    if payload.get("work_total") not in (None, 0):
        work_text = f"{payload.get('work_completed', 0)}/{payload['work_total']} "
    elapsed = payload.get("named_span_elapsed_seconds")
    elapsed_text = f"| span {float(elapsed):.1f}s " if elapsed is not None else ""
    cpu = payload.get("child_cpu_percent_of_one_core")
    cpu_text = f"| CPU {float(cpu):.0f}% " if cpu is not None else ""
    rss = payload.get("current_rss_bytes")
    peak = payload.get("span_peak_bytes")
    rss_text = ""
    if rss is not None and peak is not None:
        rss_text = f"| RSS {int(rss) / 1024**3:.2f}/{int(peak) / 1024**3:.2f} GiB"
    return (
        f"{PROGRESS_HUMAN_PREFIX} {measurement}{point}{step}{event} "
        f"{stage_text}{work_text}{elapsed_text}{cpu_text}{rss_text}"
    ).rstrip()


def _emit_scale_progress(
    event: str,
    descriptor: ScaleProgressDescriptor | None = None,
    **values: object,
) -> None:
    run_started_ns = int(
        os.environ.get(PROGRESS_RUN_STARTED_NS_ENV, str(time.monotonic_ns()))
    )
    payload: dict[str, object] = {
        "telemetry_schema": PROGRESS_TELEMETRY_SCHEMA,
        "run_id": os.environ.get(PROGRESS_RUN_ID_ENV, "unscoped"),
        "event_sequence": next(_PROGRESS_SEQUENCE),
        "emitted_at": _utc_now(),
        "run_elapsed_seconds": (time.monotonic_ns() - run_started_ns) / 1_000_000_000,
        "emitter_pid": os.getpid(),
        "status": "IN_PROGRESS",
        "event": event,
    }
    if descriptor is not None:
        payload.update(descriptor.to_json())
    payload.update(values)
    line = (
        f"{PROGRESS_PREFIX} "
        f"{json.dumps(payload, sort_keys=True, separators=(',', ':'))}"
    )
    progress_format = os.environ.get(PROGRESS_FORMAT_ENV, "both")
    if progress_format not in {"human", "json", "both"}:
        raise ValueError(f"unknown progress format {progress_format!r}")
    if progress_format in {"human", "both"}:
        print(_human_progress_line(payload), file=sys.stderr, flush=True)
    if progress_format in {"json", "both"}:
        print(line, file=sys.stderr, flush=True)
    progress_log = os.environ.get(PROGRESS_LOG_ENV)
    if progress_log:
        with Path(progress_log).open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    active_state = os.environ.get(PROGRESS_ACTIVE_STATE_ENV)
    if active_state:
        _atomic_active_state_write(Path(active_state), payload)


def finalize_scale_progress(
    *,
    status: str,
    measurement_total: int,
    failures: Sequence[str] = (),
) -> None:
    """Publish the terminal campaign state even when the registered gate assertion raises."""
    if status not in {"COMPLETE", "COMPLETE_GATE_FAILED", "ERROR", "INTERRUPTED"}:
        raise ValueError(f"unknown terminal scale status {status!r}")
    _emit_scale_progress(
        "scale-campaign-finalized",
        status=status,
        measurement_total=measurement_total,
        gate_failures=list(failures),
    )


@dataclass(frozen=True, slots=True)
class PersistedScaleFixture:
    old_workspace: BookWorkspace
    fresh_workspace: BookWorkspace


@dataclass(frozen=True, slots=True)
class CachedScaleSubstrate:
    recipe: ProductionScaleRecipe
    root: Path


class ProductionFixtureSource(Protocol):
    old_map: StructureMap
    old_streams: Mapping[str, object]
    fresh_streams: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class LoadedProductionFixture:
    old_map: StructureMap
    old_streams: Mapping[str, object]
    fresh_streams: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class IndexedProductionFixture:
    loaded: LoadedProductionFixture
    old_reader: StreamAtomReader
    fresh_reader: StreamAtomReader


@dataclass(frozen=True, slots=True)
class RssPhaseSample:
    ledger: SizeLedger
    phase: ScaleSamplePhase
    elapsed_seconds: float
    setup_elapsed_seconds: float
    monitor_elapsed_seconds: float
    raw_ru_maxrss_bytes: int
    lifetime_peak_bytes: int
    span_peak_bytes: int
    setup_baseline_bytes: int
    incremental_peak_bytes: int
    sample_interval_seconds: float
    sample_count: int
    telemetry: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.elapsed_seconds <= 0:
            raise ValueError("RSS phase elapsed_seconds must be positive")
        if self.setup_elapsed_seconds < 0:
            raise ValueError("RSS setup_elapsed_seconds must be nonnegative")
        if self.monitor_elapsed_seconds < self.elapsed_seconds:
            raise ValueError("RSS monitor time cannot be shorter than the named span")
        if self.sample_interval_seconds != RSS_SAMPLE_INTERVAL_SECONDS:
            raise ValueError(
                "RSS sample interval disagrees with the registered sampler"
            )
        if self.sample_count < 1:
            raise ValueError("RSS phase must contain at least one in-span sample")
        if self.raw_ru_maxrss_bytes < 0:
            raise ValueError("raw ru_maxrss must be nonnegative")
        if not (
            self.lifetime_peak_bytes
            >= self.span_peak_bytes
            >= self.setup_baseline_bytes
            >= 0
        ):
            raise ValueError("RSS values violate lifetime >= span >= setup >= 0")
        if self.lifetime_peak_bytes != max(
            self.raw_ru_maxrss_bytes, self.span_peak_bytes
        ):
            raise ValueError(
                "conservative lifetime RSS must be max(raw ru_maxrss, sampled span)"
            )
        if self.incremental_peak_bytes != (
            self.span_peak_bytes - self.setup_baseline_bytes
        ):
            raise ValueError("RSS incremental peak is not span minus setup baseline")

    def to_json(self) -> dict[str, object]:
        data = asdict(self)
        data["ledger"] = self.ledger.to_json()
        data["telemetry"] = dict(self.telemetry)
        return data


@dataclass(frozen=True, slots=True)
class RssPhaseMeasurement:
    ledger: SizeLedger
    phase: ScalePhase
    samples: tuple[RssPhaseSample, ...]

    def __post_init__(self) -> None:
        if not self.samples:
            raise ValueError("RSS measurement requires at least one sample")
        if any(
            sample.ledger != self.ledger or sample.phase != self.phase
            for sample in self.samples
        ):
            raise ValueError("RSS samples disagree with the measurement descriptor")

    @property
    def median_seconds(self) -> float:
        return statistics.median(sample.elapsed_seconds for sample in self.samples)

    def median(self, field: str) -> float:
        return statistics.median(
            float(getattr(sample, field)) for sample in self.samples
        )

    def to_json(self) -> dict[str, object]:
        return {
            "ledger": self.ledger.to_json(),
            "phase": self.phase,
            "samples": [sample.to_json() for sample in self.samples],
            "median_seconds": self.median_seconds,
            "median_setup_seconds": self.median("setup_elapsed_seconds"),
            "median_monitor_seconds": self.median("monitor_elapsed_seconds"),
            "median_raw_ru_maxrss_bytes": self.median("raw_ru_maxrss_bytes"),
            "median_lifetime_peak_bytes": self.median("lifetime_peak_bytes"),
            "median_span_peak_bytes": self.median("span_peak_bytes"),
            "median_setup_baseline_bytes": self.median("setup_baseline_bytes"),
            "median_incremental_peak_bytes": self.median("incremental_peak_bytes"),
        }


@dataclass(frozen=True, slots=True)
class DensityPoint:
    requested_unique_fraction: float
    measured_anchor_density: float
    slots: int
    tokens: int
    repetitions: int
    median_seconds: float
    bound_correct: int
    abstained: int
    wrong: int
    samples: tuple[Mapping[str, object], ...] = ()

    def to_json(self) -> dict[str, object]:
        data = asdict(self)
        data["samples"] = [dict(sample) for sample in self.samples]
        return data


def _partition_sizes(total: int, parts: int) -> tuple[int, ...]:
    base, remainder = divmod(total, parts)
    values = tuple(base + (index < remainder) for index in range(parts))
    if len(values) != parts or sum(values) != total or min(values) < 1:
        raise AssertionError("production scale partition is not total and non-empty")
    return values


def _scale_text(atom_index: int, tokens_per_atom: int) -> str:
    return " ".join(
        f"scale{atom_index:07d}token{token_index:02d}"
        for token_index in range(tokens_per_atom)
    )


def _scale_nodes(
    recipe: ProductionScaleRecipe, leaf_atoms: tuple[int, ...]
) -> list[NodeSeed]:
    leaf_ids = tuple(f"scale-leaf-{index:05d}" for index in range(len(leaf_atoms)))
    if recipe.shape == "wide":
        nodes = [
            NodeSeed("scale-root", "volume", "container", children=("scale-tier-1",)),
            NodeSeed("scale-tier-1", "part", "container", children=("scale-tier-2",)),
            NodeSeed("scale-tier-2", "section", "container", children=leaf_ids),
        ]
    else:
        nodes = []
        for index, leaf_id in enumerate(leaf_ids):
            children = [leaf_id]
            if index + 1 < len(leaf_ids):
                children.append(f"scale-container-{index + 1:05d}")
            nodes.append(
                NodeSeed(
                    f"scale-container-{index:05d}",
                    "section",
                    "container",
                    children=tuple(children),
                )
            )
    atom_cursor = 0
    for leaf_index, owned_count in enumerate(leaf_atoms):
        keys = tuple(
            f"scale-atom-{atom_index:06d}"
            for atom_index in range(atom_cursor, atom_cursor + owned_count)
        )
        nodes.append(NodeSeed(leaf_ids[leaf_index], "block", "leaf", body=keys))
        atom_cursor += owned_count
    return nodes


def _production_fixture_spec(recipe: ProductionScaleRecipe) -> FixtureSpec:
    ledger = recipe.ledger
    leaf_atoms = _partition_sizes(ledger.A, ledger.L)
    nodes = _scale_nodes(recipe, leaf_atoms)
    owner_by_atom: list[str] = []
    for leaf_index, owned_count in enumerate(leaf_atoms):
        owner_by_atom.extend([f"scale-leaf-{leaf_index:05d}"] * owned_count)
    atoms = tuple(
        AtomSeed(
            f"scale-atom-{index:06d}",
            _scale_text(index, recipe.tokens_per_atom),
            owner_by_atom[index],
            SLOT_BODY,
        )
        for index in range(ledger.A)
    )
    root_id = "scale-root" if recipe.shape == "wide" else "scale-container-00000"
    return FixtureSpec(root_id, tuple(nodes), atoms, require_tokenless_cases=False)


def build_production_scale_fixture(
    recipe: ProductionScaleRecipe,
) -> RebindFixtureBundle:
    """Build the registered A-axis family; old/fresh ids differ with identical content."""
    ledger = recipe.ledger
    bundle = materialize_fixture(
        _production_fixture_spec(recipe),
        DriftConfig(
            f"production-{recipe.shape}-a{recipe.atom_count}",
            58_000 + recipe.atom_count + (0 if recipe.shape == "wide" else 1),
            (),
        ),
    )
    if len(bundle.old_canonical.atoms) != ledger.A:
        raise AssertionError("production scale materialization lost atoms")
    return bundle


def build_production_drift_fixture(
    recipe: ProductionScaleRecipe,
) -> RebindFixtureBundle:
    """Build the diagnostic drift sentinel used to keep identity-path timing honest.

    Every 400 atoms, one atom receives an in-token OCR-class substitution, a different atom is split
    at a token boundary, and two further atoms are merged.  Split/merge keeps aggregate cardinality
    stable for the production index preflight while exercising genuine re-segmentation.  The OCR
    edit independently guarantees unequal token streams.
    """
    if recipe.atom_count < 40:
        raise ValueError("production drift sentinel requires at least 40 atoms")
    operations: list[DriftOperation] = []
    for cohort_start in range(0, recipe.atom_count - 39, 400):
        char_index = cohort_start + 20
        char_key = f"scale-atom-{char_index:06d}"
        original = _scale_text(char_index, recipe.tokens_per_atom)
        replacement = original.replace("c", "e", 1)
        operations.append(
            DriftOperation(
                "char_sub",
                (char_key,),
                (f"{char_key}-ocr",),
                (replacement,),
            )
        )

        split_index = cohort_start + 10
        split_key = f"scale-atom-{split_index:06d}"
        tokens = _scale_text(split_index, recipe.tokens_per_atom).split(" ")
        split_at = len(tokens) // 2
        operations.append(
            DriftOperation(
                "split",
                (split_key,),
                (f"{split_key}-left", f"{split_key}-right"),
                (
                    " ".join(tokens[:split_at]) + " ",
                    " ".join(tokens[split_at:]),
                ),
            )
        )
        merge_left = cohort_start + 30
        merge_right = merge_left + 1
        operations.append(
            DriftOperation(
                "merge",
                (
                    f"scale-atom-{merge_left:06d}",
                    f"scale-atom-{merge_right:06d}",
                ),
                (f"scale-atoms-{merge_left:06d}-{merge_right:06d}-merged",),
            )
        )
    bundle = materialize_fixture(
        _production_fixture_spec(recipe),
        DriftConfig(
            f"production-drift-{recipe.shape}-a{recipe.atom_count}",
            68_000 + recipe.atom_count + (0 if recipe.shape == "wide" else 1),
            tuple(operations),
            permitted_compositions=frozenset(
                {
                    ("char_sub", "merge"),
                    ("char_sub", "split"),
                    ("merge", "split"),
                }
            ),
        ),
    )
    if (
        materialize_token_stream(bundle.old_canonical).tokens
        == materialize_token_stream(bundle.fresh_canonical).tokens
    ):
        raise AssertionError("production drift sentinel did not alter the token stream")
    return bundle


def persist_production_fixture(
    bundle: ProductionFixtureSource,
    root: Path,
    *,
    telemetry: RebindTelemetry | None = None,
) -> PersistedScaleFixture:
    """Persist the two canonical generations in separate sanctioned workspaces."""
    recorder = telemetry or NULL_REBIND_TELEMETRY
    with recorder.span("persist.prepare-workspaces"):
        old_workspace = BookWorkspace.for_book("old-generation", root).ensure()
        fresh_workspace = BookWorkspace.for_book("fresh-generation", root).ensure()
    if old_workspace.root == fresh_workspace.root:
        raise AssertionError(
            "old and fresh scale generations must use distinct workspaces"
        )
    with recorder.span("persist.old-streams") as span:
        for stream in bundle.old_streams.values():
            save_stream(old_workspace, stream)
        span.update(stream_count=len(bundle.old_streams))
    with recorder.span("persist.fresh-streams") as span:
        for stream in bundle.fresh_streams.values():
            save_stream(fresh_workspace, stream)
        span.update(stream_count=len(bundle.fresh_streams))
    with recorder.span("persist.structure-map"):
        write_structure_map(old_workspace, bundle.old_map.doc, telemetry=recorder)
    return PersistedScaleFixture(old_workspace, fresh_workspace)


_SUBSTRATE_SOURCE_FILES = (
    Path(__file__),
    Path(__file__).with_name("materialize.py"),
    Path(__file__).with_name("relation.py"),
    Path(__file__).resolve().parents[2] / "src/engine/structure/boundary_anchor.py",
    Path(__file__).resolve().parents[2] / "src/engine/structure/handles.py",
    Path(__file__).resolve().parents[2] / "src/engine/structure/projection.py",
    Path(__file__).resolve().parents[2] / "src/engine/structure/rebind_telemetry.py",
    Path(__file__).resolve().parents[2]
    / "src/engine/structure/schema/structure_map.schema.json",
)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _substrate_source_identity() -> dict[str, str]:
    root = Path(__file__).resolve().parents[2]
    return {
        str(path.relative_to(root)): _sha256_file(path)
        for path in _SUBSTRATE_SOURCE_FILES
    }


def _persisted_file_identity(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): _sha256_file(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "substrate.json"
    }


def create_cached_scale_substrate(
    recipe: ProductionScaleRecipe,
    bundle: RebindFixtureBundle,
    root: Path,
) -> CachedScaleSubstrate:
    """Persist, round-trip-check, version, and source-lock one reusable fixture substrate."""
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    books_root = root / "books"
    persisted = persist_production_fixture(bundle, books_root)
    loaded = load_production_fixture(persisted)
    if (
        loaded.old_map.doc != bundle.old_map.doc
        or loaded.old_streams != bundle.old_streams
        or loaded.fresh_streams != bundle.fresh_streams
    ):
        raise AssertionError("cached substrate differs from its cold fixture source")
    manifest = {
        "schema": SCALE_SUBSTRATE_SCHEMA,
        "recipe": asdict(recipe),
        "source_identity": _substrate_source_identity(),
        "persisted_file_identity": _persisted_file_identity(root),
        "cold_round_trip_equivalent": True,
    }
    temporary = root / ".substrate.json.tmp"
    temporary.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(root / "substrate.json")
    return CachedScaleSubstrate(recipe, root)


def validate_cached_scale_substrate(
    substrate: CachedScaleSubstrate,
) -> PersistedScaleFixture:
    manifest_path = substrate.root / "substrate.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != SCALE_SUBSTRATE_SCHEMA:
        raise AssertionError("cached substrate schema/version mismatch")
    if manifest.get("recipe") != asdict(substrate.recipe):
        raise AssertionError("cached substrate recipe mismatch")
    if manifest.get("source_identity") != _substrate_source_identity():
        raise AssertionError("cached substrate source lock mismatch")
    if manifest.get("persisted_file_identity") != _persisted_file_identity(
        substrate.root
    ):
        raise AssertionError("cached substrate persisted-file lock mismatch")
    if manifest.get("cold_round_trip_equivalent") is not True:
        raise AssertionError(
            "cached substrate lacks a cold round-trip equivalence proof"
        )
    books_root = substrate.root / "books"
    return PersistedScaleFixture(
        BookWorkspace.for_book("old-generation", books_root),
        BookWorkspace.for_book("fresh-generation", books_root),
    )


def clone_cached_scale_substrate(
    substrate: CachedScaleSubstrate, destination: Path
) -> PersistedScaleFixture:
    validate_cached_scale_substrate(substrate)
    destination = Path(destination).resolve()
    books_root = destination / "books"
    shutil.copytree(substrate.root / "books", books_root)
    return PersistedScaleFixture(
        BookWorkspace.for_book("old-generation", books_root),
        BookWorkspace.for_book("fresh-generation", books_root),
    )


def load_production_fixture(
    persisted: PersistedScaleFixture,
    *,
    telemetry: RebindTelemetry | None = None,
) -> LoadedProductionFixture:
    recorder = telemetry or NULL_REBIND_TELEMETRY
    with recorder.span("load.old-streams") as span:
        old_streams = load_workspace_streams(persisted.old_workspace)
        span.update(stream_count=len(old_streams))
    with recorder.span("load.fresh-streams") as span:
        fresh_streams = load_workspace_streams(persisted.fresh_workspace)
        span.update(stream_count=len(fresh_streams))
    with recorder.span("load.structure-map"):
        old_reader = StreamAtomReader(old_streams, "canonical")
        old_map = load_structure_map(
            structure_map_path(persisted.old_workspace),
            old_reader,
            telemetry=recorder,
        )
    return LoadedProductionFixture(old_map, old_streams, fresh_streams)


def index_production_fixture(
    loaded: LoadedProductionFixture,
    *,
    telemetry: RebindTelemetry | None = None,
) -> IndexedProductionFixture:
    recorder = telemetry or NULL_REBIND_TELEMETRY
    with recorder.span("index.readers"):
        old_reader = StreamAtomReader(loaded.old_streams, "canonical")
        fresh_reader = StreamAtomReader(loaded.fresh_streams, "canonical")
    with recorder.span("index.validate-map"):
        validate_structure_map(loaded.old_map, old_reader)
    with recorder.span("index.compare-cardinality") as span:
        old_count = len(old_reader.included_atom_ids())
        fresh_count = len(fresh_reader.included_atom_ids())
        span.update(old_included_atoms=old_count, fresh_included_atoms=fresh_count)
    if old_count != fresh_count:
        raise AssertionError(
            "production scale generations disagree on included atom cardinality"
        )
    return IndexedProductionFixture(loaded, old_reader, fresh_reader)


def run_production_rebind(
    indexed: IndexedProductionFixture,
    *,
    telemetry: RebindTelemetry | None = None,
) -> RebindResult:
    return rebind(
        RebindContext(
            indexed.loaded.old_map,
            indexed.loaded.old_streams,
            indexed.loaded.fresh_streams,
            geometry_mode=MODE_NO_GEOMETRY,
            telemetry=telemetry,
        )
    )


def _validate_result(result: RebindResult, ledger: SizeLedger) -> None:
    container_count = 3 if ledger.family.startswith("wide") else ledger.L
    if len(result.report.nodes) != ledger.L + container_count:
        raise AssertionError("production rebind did not report every structure node")
    if result.report.unresolved:
        raise AssertionError(
            f"anchor-rich production scale fixture unexpectedly abstained: "
            f"{result.report.unresolved[:1]}"
        )


def _run_named_phase(
    phase: ScalePhase,
    recipe: ProductionScaleRecipe,
    bundle: RebindFixtureBundle,
    root: Path,
    telemetry: RebindTelemetry,
) -> object:
    if phase == "serialize":
        return persist_production_fixture(bundle, root, telemetry=telemetry)
    if phase == "end_to_end":
        persisted = persist_production_fixture(bundle, root, telemetry=telemetry)
        loaded = load_production_fixture(persisted, telemetry=telemetry)
        indexed = index_production_fixture(loaded, telemetry=telemetry)
        result = run_production_rebind(indexed, telemetry=telemetry)
        _validate_result(result, recipe.ledger)
        return result

    with telemetry.span("setup.persist-prerequisites"):
        persisted = persist_production_fixture(bundle, root, telemetry=telemetry)
    if phase == "load":
        return load_production_fixture(persisted, telemetry=telemetry)
    with telemetry.span("setup.load-prerequisites"):
        loaded = load_production_fixture(persisted, telemetry=telemetry)
    if phase == "index":
        return index_production_fixture(loaded, telemetry=telemetry)
    with telemetry.span("setup.index-prerequisites"):
        indexed = index_production_fixture(loaded, telemetry=telemetry)
    result = run_production_rebind(indexed, telemetry=telemetry)
    _validate_result(result, recipe.ledger)
    return result


def _prepare_phase(
    phase: ScalePhase,
    recipe: ProductionScaleRecipe,
    bundle: RebindFixtureBundle,
    root: Path,
    telemetry: RebindTelemetry,
):
    """Prepare only inputs that precede the named phase; returned callable is the measured span."""
    if phase in {"serialize", "end_to_end"}:
        return lambda: _run_named_phase(phase, recipe, bundle, root, telemetry)
    with telemetry.span("setup.persist-prerequisites"):
        persisted = persist_production_fixture(bundle, root, telemetry=telemetry)
    if phase == "load":
        return lambda: load_production_fixture(persisted, telemetry=telemetry)
    with telemetry.span("setup.load-prerequisites"):
        loaded = load_production_fixture(persisted, telemetry=telemetry)
    if phase == "index":
        return lambda: index_production_fixture(loaded, telemetry=telemetry)
    with telemetry.span("setup.index-prerequisites"):
        indexed = index_production_fixture(loaded, telemetry=telemetry)
    return lambda: run_production_rebind(indexed, telemetry=telemetry)


def _phase_uses_cached_substrate(phase: ScalePhase) -> bool:
    """Keep every end-to-end point cold; all prerequisite-only phases may use the cache."""
    return phase != "end_to_end"


def _prepare_cached_phase(
    phase: ScalePhase,
    substrate: CachedScaleSubstrate,
    root: Path,
    telemetry: RebindTelemetry,
):
    if not _phase_uses_cached_substrate(phase):
        raise AssertionError("end-to-end measurements must never use cached substrates")
    with telemetry.span("setup.clone-substrate"):
        persisted = clone_cached_scale_substrate(substrate, root / "prerequisite")
    if phase == "load":
        return lambda: load_production_fixture(persisted, telemetry=telemetry)
    with telemetry.span("setup.load-prerequisites"):
        loaded = load_production_fixture(persisted, telemetry=telemetry)
    if phase == "serialize":
        return lambda: persist_production_fixture(
            loaded, root / "named-output", telemetry=telemetry
        )
    if phase == "index":
        return lambda: index_production_fixture(loaded, telemetry=telemetry)
    with telemetry.span("setup.index-prerequisites"):
        indexed = index_production_fixture(loaded, telemetry=telemetry)
    return lambda: run_production_rebind(indexed, telemetry=telemetry)


def _ru_maxrss_bytes() -> int:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if sys.platform == "darwin" else value * 1024)


def _conservative_lifetime_peak_bytes(raw_ru_maxrss: int, span_peak: int) -> int:
    return max(raw_ru_maxrss, span_peak)


def _rss_child(
    recipe: ProductionScaleRecipe | None,
    phase: ScaleSamplePhase,
    fixture_variant: ProductionFixtureVariant,
    cached_substrate: CachedScaleSubstrate | None,
    cache_output: Path | None,
    events,
    ready,
    results,
    shared_stage_id,
    shared_stage_started_ns,
    shared_work_completed,
    shared_work_total,
) -> None:
    current_stage_id = _TELEMETRY_STAGE_TO_ID["idle"]

    def publish_stage(
        stage: str,
        completed: int | None,
        total: int | None,
    ) -> None:
        nonlocal current_stage_id
        next_stage_id = _TELEMETRY_STAGE_TO_ID.get(stage, 0)
        if next_stage_id != current_stage_id:
            shared_stage_started_ns.value = time.monotonic_ns()
            current_stage_id = next_stage_id
            shared_stage_id.value = next_stage_id
        shared_work_completed.value = -1 if completed is None else completed
        shared_work_total.value = -1 if total is None else total

    telemetry = RebindTelemetry(stage_callback=publish_stage)
    try:
        process = psutil.Process()
        with telemetry.span("setup.prepare"):
            if phase == "allocation_probe":
                ledger = SizeLedger("rss-allocation-probe", 1, 1, 1, 1, 1)

                def operation():
                    planted = bytearray(RSS_PROBE_BYTES)
                    planted[::4096] = b"x" * len(planted[::4096])
                    time.sleep(RSS_PROBE_HOLD_SECONDS)
                    return len(planted)

            elif phase == "materialize":
                if recipe is None:
                    raise AssertionError("materialization phase requires a recipe")
                ledger = recipe.ledger

                def operation():
                    return build_production_scale_fixture(recipe)

            else:
                if recipe is None:
                    raise AssertionError("scale phase child requires a recipe")
                ledger = recipe.ledger
                scratch = tempfile.TemporaryDirectory(prefix="s4_7_scale_child_")
                if cached_substrate is not None and _phase_uses_cached_substrate(phase):
                    if fixture_variant != "identical":
                        raise AssertionError(
                            "drift diagnostics must not use the identical fixture cache"
                        )
                    operation = _prepare_cached_phase(
                        phase, cached_substrate, Path(scratch.name), telemetry
                    )
                else:
                    with telemetry.span("setup.materialize-fixture"):
                        bundle = (
                            build_production_scale_fixture(recipe)
                            if fixture_variant == "identical"
                            else build_production_drift_fixture(recipe)
                        )
                    operation = _prepare_phase(
                        phase, recipe, bundle, Path(scratch.name), telemetry
                    )

        baseline = process.memory_info().rss
        events.put(("span-ready", baseline))
        if not ready.wait(timeout=30):
            raise TimeoutError("RSS sampler did not acknowledge the setup boundary")
        started = time.perf_counter()
        named_stage = {
            "allocation_probe": "named.allocation-probe",
            "end_to_end": "named.end-to-end",
        }.get(phase, f"named.{phase}")
        with telemetry.span(named_stage):
            value = operation()
        elapsed = time.perf_counter() - started
        if phase == "allocation_probe":
            if value != RSS_PROBE_BYTES:
                raise AssertionError("allocation probe did not complete")
        elif phase == "serialize":
            if not isinstance(value, PersistedScaleFixture):
                raise AssertionError("serialize phase returned the wrong type")
        elif phase == "load":
            if not isinstance(value, LoadedProductionFixture):
                raise AssertionError("load phase returned the wrong type")
        elif phase == "index":
            if not isinstance(value, IndexedProductionFixture):
                raise AssertionError("index phase returned the wrong type")
        elif phase == "materialize":
            if not isinstance(value, RebindFixtureBundle):
                raise AssertionError("materialize phase returned the wrong type")
        else:
            if not isinstance(value, RebindResult):
                raise AssertionError("rebind phase returned the wrong type")
            _validate_result(value, ledger)
        named_raw_ru_maxrss = _ru_maxrss_bytes()
        events.put(("span-done", None))
        if phase == "materialize" and cache_output is not None:
            with telemetry.span("finalize.cache-substrate"):
                create_cached_scale_substrate(recipe, value, cache_output)
        results.put(
            {
                "ok": True,
                "ledger": ledger.to_json(),
                "elapsed_seconds": elapsed,
                "setup_baseline_bytes": baseline,
                "raw_ru_maxrss_bytes": named_raw_ru_maxrss,
                "fixture_variant": fixture_variant,
                "telemetry": telemetry.to_json(),
            }
        )
    except BaseException as exc:  # child boundary: serialize the failure for the parent
        results.put(
            {
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc(),
                "telemetry": telemetry.to_json(),
            }
        )


def measure_rss_phase(
    recipe: ProductionScaleRecipe | None,
    phase: ScaleSamplePhase,
    *,
    progress: ScaleProgressDescriptor | None = None,
    cached_substrate: CachedScaleSubstrate | None = None,
    cache_output: Path | None = None,
    fixture_variant: ProductionFixtureVariant = "identical",
) -> RssPhaseSample:
    """Spawn one phase child, sample RSS at 5 ms, and report configured heartbeats."""
    if fixture_variant not in {"identical", "drift"}:
        raise ValueError(f"unknown production fixture variant {fixture_variant!r}")
    if fixture_variant == "drift" and cached_substrate is not None:
        raise ValueError("drift diagnostics cannot use an identical cached substrate")
    progress_poll_interval = configured_progress_poll_interval_seconds()
    context = mp.get_context(RSS_START_METHOD)
    events = context.Queue()
    results = context.Queue()
    ready = context.Event()
    shared_stage_id = context.Value("i", _TELEMETRY_STAGE_TO_ID["idle"], lock=False)
    shared_stage_started_ns = context.Value("q", 0, lock=False)
    shared_work_completed = context.Value("q", -1, lock=False)
    shared_work_total = context.Value("q", -1, lock=False)
    process = context.Process(
        target=_rss_child,
        args=(
            recipe,
            phase,
            fixture_variant,
            cached_substrate,
            cache_output,
            events,
            ready,
            results,
            shared_stage_id,
            shared_stage_started_ns,
            shared_work_completed,
            shared_work_total,
        ),
    )
    process.start()
    observed = psutil.Process(process.pid)
    monitor_started = time.monotonic()
    next_progress = monitor_started + progress_poll_interval
    span_started: float | None = None
    state = "setup"
    active = False
    baseline = 0
    span_peak = 0
    current_rss = 0
    sample_count = 0
    span_done = False
    stage_rss: dict[str, dict[str, float | int]] = {}
    previous_cpu_total = 0.0
    previous_cpu_observed_at = monitor_started
    if progress is not None:
        _emit_scale_progress(
            "measurement-start",
            progress,
            child_pid=process.pid,
            state=state,
        )
    try:
        while process.is_alive() or not span_done:
            try:
                event, value = events.get(timeout=RSS_SAMPLE_INTERVAL_SECONDS)
                if event == "span-ready":
                    baseline = int(value)
                    current_rss = baseline
                    active = True
                    state = "measured-span"
                    span_started = time.monotonic()
                    span_peak = max(span_peak, baseline)
                    ready.set()
                    if progress is not None:
                        _emit_scale_progress(
                            "named-span-start",
                            progress,
                            child_pid=process.pid,
                            state=state,
                            setup_elapsed_seconds=round(
                                span_started - monitor_started, 3
                            ),
                            current_rss_bytes=current_rss,
                            span_peak_bytes=span_peak,
                        )
                elif event == "span-done":
                    span_done = True
                    active = False
                    state = "finalizing"
                    if progress is not None:
                        _emit_scale_progress(
                            "named-span-done",
                            progress,
                            child_pid=process.pid,
                            state=state,
                            monitor_elapsed_seconds=round(
                                time.monotonic() - monitor_started, 3
                            ),
                            current_rss_bytes=current_rss,
                            span_peak_bytes=span_peak,
                        )
            except queue.Empty:
                pass
            try:
                memory_info = observed.memory_info()
                current_rss = memory_info.rss
                stage_index = int(shared_stage_id.value)
                internal_stage = (
                    _HARNESS_TELEMETRY_STAGES[stage_index]
                    if 0 <= stage_index < len(_HARNESS_TELEMETRY_STAGES)
                    else "idle"
                )
                stage_row = stage_rss.setdefault(
                    internal_stage,
                    {
                        "rss_peak_bytes": 0,
                        "sample_count": 0,
                        "first_monitor_elapsed_seconds": time.monotonic()
                        - monitor_started,
                        "last_monitor_elapsed_seconds": 0.0,
                    },
                )
                stage_row["rss_peak_bytes"] = max(
                    int(stage_row["rss_peak_bytes"]), current_rss
                )
                stage_row["sample_count"] = int(stage_row["sample_count"]) + 1
                stage_row["last_monitor_elapsed_seconds"] = (
                    time.monotonic() - monitor_started
                )
                if active:
                    span_peak = max(span_peak, current_rss)
                    sample_count += 1
            except psutil.NoSuchProcess:
                if process.is_alive():
                    continue
            now = time.monotonic()
            if progress is not None and now >= next_progress:
                runtime: dict[str, object] = {}
                try:
                    cpu_times = observed.cpu_times()
                    cpu_total = float(cpu_times.user + cpu_times.system)
                    cpu_wall = max(1e-9, now - previous_cpu_observed_at)
                    runtime = {
                        "child_cpu_user_seconds": float(cpu_times.user),
                        "child_cpu_system_seconds": float(cpu_times.system),
                        "child_cpu_percent_of_one_core": max(
                            0.0,
                            100.0 * (cpu_total - previous_cpu_total) / cpu_wall,
                        ),
                        "child_num_threads": observed.num_threads(),
                        "child_status": observed.status(),
                    }
                    previous_cpu_total = cpu_total
                    previous_cpu_observed_at = now
                    heartbeat_memory = observed.memory_info()
                    for field_name in ("pfaults", "pageins"):
                        field_value = getattr(heartbeat_memory, field_name, None)
                        if field_value is not None:
                            runtime[f"child_{field_name}"] = int(field_value)
                except psutil.Error:
                    pass
                virtual_memory = psutil.virtual_memory()
                swap_memory = psutil.swap_memory()
                runtime.update(
                    {
                        "system_available_memory_bytes": int(virtual_memory.available),
                        "system_memory_percent": float(virtual_memory.percent),
                        "system_swap_used_bytes": int(swap_memory.used),
                    }
                )
                try:
                    runtime["system_load_1m"] = float(os.getloadavg()[0])
                except (AttributeError, OSError):
                    pass
                stage_index = int(shared_stage_id.value)
                internal_stage = (
                    _HARNESS_TELEMETRY_STAGES[stage_index]
                    if 0 <= stage_index < len(_HARNESS_TELEMETRY_STAGES)
                    else "idle"
                )
                stage_started_ns = int(shared_stage_started_ns.value)
                work_completed = int(shared_work_completed.value)
                work_total = int(shared_work_total.value)
                _emit_scale_progress(
                    "heartbeat",
                    progress,
                    child_pid=process.pid,
                    state=state,
                    monitor_elapsed_seconds=round(now - monitor_started, 3),
                    named_span_elapsed_seconds=(
                        round(now - span_started, 3)
                        if span_started is not None and not span_done
                        else None
                    ),
                    current_rss_bytes=current_rss,
                    span_peak_bytes=span_peak,
                    internal_stage=internal_stage,
                    internal_stage_elapsed_seconds=(
                        (time.monotonic_ns() - stage_started_ns) / 1_000_000_000
                        if stage_started_ns > 0
                        else None
                    ),
                    work_completed=(work_completed if work_completed >= 0 else None),
                    work_total=(work_total if work_total >= 0 else None),
                    **runtime,
                )
                while next_progress <= now:
                    next_progress += progress_poll_interval
            if not process.is_alive():
                break
    except BaseException:
        if process.is_alive():
            process.terminate()
            process.join(timeout=30)
        raise
    process.join(timeout=30)
    if process.is_alive():
        process.terminate()
        process.join()
        raise TimeoutError("RSS child did not terminate")
    try:
        payload = results.get(timeout=5)
    except queue.Empty as exc:
        raise RuntimeError(
            f"RSS child exited {process.exitcode} without a result"
        ) from exc
    if not payload.get("ok"):
        if progress is not None:
            stage_index = int(shared_stage_id.value)
            _emit_scale_progress(
                "measurement-error",
                progress,
                child_pid=process.pid,
                state="error",
                internal_stage=(
                    _HARNESS_TELEMETRY_STAGES[stage_index]
                    if 0 <= stage_index < len(_HARNESS_TELEMETRY_STAGES)
                    else "idle"
                ),
                error=payload.get("error"),
                child_traceback=payload.get("traceback"),
                telemetry=payload.get("telemetry"),
            )
        raise RuntimeError(f"RSS child failed: {payload.get('error')}")
    raw_ru_maxrss = int(payload["raw_ru_maxrss_bytes"])
    baseline = int(payload["setup_baseline_bytes"])
    span_peak = max(span_peak, baseline)
    lifetime = _conservative_lifetime_peak_bytes(raw_ru_maxrss, span_peak)
    ledger = SizeLedger(**payload["ledger"])
    monitor_elapsed = time.monotonic() - monitor_started
    setup_elapsed = span_started - monitor_started if span_started is not None else 0.0
    sample = RssPhaseSample(
        ledger=ledger,
        phase=phase,
        elapsed_seconds=float(payload["elapsed_seconds"]),
        setup_elapsed_seconds=setup_elapsed,
        monitor_elapsed_seconds=monitor_elapsed,
        raw_ru_maxrss_bytes=raw_ru_maxrss,
        lifetime_peak_bytes=lifetime,
        span_peak_bytes=span_peak,
        setup_baseline_bytes=baseline,
        incremental_peak_bytes=max(0, span_peak - baseline),
        sample_interval_seconds=RSS_SAMPLE_INTERVAL_SECONDS,
        sample_count=sample_count,
        telemetry={
            "schema": RUNTIME_TELEMETRY_SCHEMA,
            "progress_poll_interval_seconds": progress_poll_interval,
            "fixture_variant": payload.get("fixture_variant", fixture_variant),
            "child_trace": payload.get("telemetry", {}),
            "stage_rss": [
                {"name": stage, **values} for stage, values in sorted(stage_rss.items())
            ],
        },
    )
    if progress is not None:
        _emit_scale_progress(
            "measurement-complete",
            progress,
            child_pid=process.pid,
            state="complete",
            monitor_elapsed_seconds=round(sample.monitor_elapsed_seconds, 3),
            setup_elapsed_seconds=round(sample.setup_elapsed_seconds, 3),
            named_span_elapsed_seconds=sample.elapsed_seconds,
            raw_ru_maxrss_bytes=sample.raw_ru_maxrss_bytes,
            lifetime_peak_bytes=sample.lifetime_peak_bytes,
            span_peak_bytes=sample.span_peak_bytes,
            sample_count=sample.sample_count,
            telemetry_span_totals={
                str(name): sum(
                    float(span["wall_seconds"])
                    for span in payload.get("telemetry", {}).get("spans", [])
                    if span.get("name") == name
                )
                for name in {
                    span.get("name")
                    for span in payload.get("telemetry", {}).get("spans", [])
                }
                if name is not None
            },
        )
    return sample


def validate_rss_sampler() -> RssPhaseSample:
    sample = measure_rss_phase(None, "allocation_probe")
    if sample.sample_count < 2:
        raise AssertionError("RSS probe did not receive at least two in-span samples")
    if sample.incremental_peak_bytes < int(RSS_PROBE_BYTES * 0.80):
        raise AssertionError(
            "RSS sampler missed the planted short-lived allocation: "
            f"observed {sample.incremental_peak_bytes}, planted {RSS_PROBE_BYTES}"
        )
    return sample


def measure_recipe(
    recipe: ProductionScaleRecipe,
    *,
    repetitions: int = PRODUCTION_REPETITIONS,
    measurement_offset: int = 0,
    measurement_total: int | None = None,
    emit_progress: bool = False,
    event_callback: ProgressEventCallback | None = None,
    cached_substrate: CachedScaleSubstrate | None = None,
) -> dict[ScalePhase, RssPhaseMeasurement]:
    if repetitions < 1:
        raise ValueError("repetitions must be positive")
    total = measurement_total or len(SCALE_PHASES) * repetitions
    output: dict[ScalePhase, RssPhaseMeasurement] = {}
    for phase_index, phase in enumerate(SCALE_PHASES):
        samples: list[RssPhaseSample] = []
        for repetition_index in range(repetitions):
            descriptor = ScaleProgressDescriptor(
                shape=recipe.shape,
                atom_count=recipe.atom_count,
                phase=phase,
                repetition=repetition_index + 1,
                repetitions=repetitions,
                measurement_index=(
                    measurement_offset
                    + phase_index * repetitions
                    + repetition_index
                    + 1
                ),
                measurement_total=total,
            )
            sample = measure_rss_phase(
                recipe,
                phase,
                progress=descriptor if emit_progress else None,
                cached_substrate=cached_substrate,
            )
            samples.append(sample)
            if event_callback is not None:
                event_callback(
                    {
                        "event": "phase-sample-complete",
                        "progress": descriptor.to_json(),
                        "sample": sample.to_json(),
                    }
                )
        output[phase] = RssPhaseMeasurement(
            recipe.ledger,
            phase,
            tuple(samples),
        )
    return output


def measure_scale_ladder(
    shape: ScaleShape,
    atom_ladder: tuple[int, ...],
    *,
    repetitions: int = PRODUCTION_REPETITIONS,
    measurement_offset: int = 0,
    measurement_total: int | None = None,
    emit_progress: bool = False,
    event_callback: ProgressEventCallback | None = None,
) -> tuple[dict[ScalePhase, RssPhaseMeasurement], ...]:
    if len(atom_ladder) < 3 or atom_ladder[-1] / atom_ladder[0] < 100:
        raise ValueError(
            "scale ladder must contain at least three points spanning 100x"
        )
    per_point = len(SCALE_PHASES) * repetitions
    return tuple(
        measure_recipe(
            ProductionScaleRecipe(shape, atoms),
            repetitions=repetitions,
            measurement_offset=measurement_offset + index * per_point,
            measurement_total=measurement_total,
            emit_progress=emit_progress,
            event_callback=event_callback,
        )
        for index, atoms in enumerate(atom_ladder)
    )


def capture_production_profile(
    atom_ladder: tuple[int, ...],
    *,
    repetitions: int = PRODUCTION_REPETITIONS,
    enforce_growth: bool = True,
    full_density_surface: bool = True,
    enforce_density: bool = True,
    emit_progress: bool = False,
    event_callback: ProgressEventCallback | None = None,
) -> dict[str, object]:
    sampler_probe = validate_rss_sampler()
    if full_density_surface:
        density, density_growth = measure_density_surface(
            enforce=enforce_density,
            emit_progress=emit_progress,
            event_callback=event_callback,
        )
    else:
        density = measure_density_sweep(
            enforce=enforce_density,
            emit_progress=emit_progress,
            event_callback=event_callback,
        )
        density_growth = {}
    measurement_total = (
        len(SCALE_SHAPES) * len(atom_ladder) * len(SCALE_PHASES) * repetitions
    )
    if emit_progress:
        _emit_scale_progress(
            "scale-campaign-start",
            measurement_total=measurement_total,
            atom_ladder=list(atom_ladder),
            repetitions=repetitions,
        )
    shapes: dict[str, object] = {}
    substrate_materialization: dict[str, list[dict[str, object]]] = {}
    per_shape = len(atom_ladder) * len(SCALE_PHASES) * repetitions
    per_point = len(SCALE_PHASES) * repetitions
    substrate_total = len(SCALE_SHAPES) * len(atom_ladder)
    for shape_index, shape in enumerate(SCALE_SHAPES):
        measured_points: list[dict[ScalePhase, RssPhaseMeasurement]] = []
        materialization_points: list[dict[str, object]] = []
        for point_index, atoms in enumerate(atom_ladder):
            recipe = ProductionScaleRecipe(shape, atoms)
            with tempfile.TemporaryDirectory(
                prefix=f"s4_7_substrate_{shape}_a{atoms}_"
            ) as substrate_temp:
                substrate_root = Path(substrate_temp) / "source-locked"
                substrate_descriptor = ScaleProgressDescriptor(
                    shape=shape,
                    atom_count=atoms,
                    phase="materialize",
                    repetition=0,
                    repetitions=repetitions,
                    measurement_index=(
                        shape_index * len(atom_ladder) + point_index + 1
                    ),
                    measurement_total=substrate_total,
                )
                materialization_sample = measure_rss_phase(
                    recipe,
                    "materialize",
                    progress=substrate_descriptor if emit_progress else None,
                    cache_output=substrate_root,
                )
                cached = CachedScaleSubstrate(recipe, substrate_root)
                validate_cached_scale_substrate(cached)
                if event_callback is not None:
                    event_callback(
                        {
                            "event": "substrate-materialization-complete",
                            "progress": substrate_descriptor.to_json(),
                            "sample": materialization_sample.to_json(),
                        }
                    )
                materialization_points.append(materialization_sample.to_json())
                measured_points.append(
                    measure_recipe(
                        recipe,
                        repetitions=repetitions,
                        measurement_offset=(
                            shape_index * per_shape + point_index * per_point
                        ),
                        measurement_total=measurement_total,
                        emit_progress=emit_progress,
                        event_callback=event_callback,
                        cached_substrate=cached,
                    )
                )
        measurements = tuple(measured_points)
        substrate_materialization[shape] = materialization_points
        growth = production_growth_summary(measurements)
        if enforce_growth:
            assert_production_growth(growth)
        shapes[shape] = {
            "points": [
                {
                    "ledger": point["end_to_end"].ledger.to_json(),
                    "phases": {phase: point[phase].to_json() for phase in SCALE_PHASES},
                }
                for point in measurements
            ],
            "growth": growth,
        }
    captured = {
        "atom_ladder": list(atom_ladder),
        "repetitions": repetitions,
        "rss_sampler_probe": sampler_probe.to_json(),
        "density_sweep": [point.to_json() for point in density],
        "density_timing_growth": density_growth,
        "density_pairing": {
            "slot_ladder": list(DENSITY_SLOT_LADDER),
            "tokens_per_slot": DENSITY_TOKENS_PER_SLOT,
            "same_atom_boundaries": True,
            "same_edit_locations": "empty (remint-only generation change)",
            "intended_treatment": "v3 boundary-anchor uniqueness density",
            "residual_confounds": [
                "one clustered repetition run",
                "anchor ambiguity",
                "shingle-frequency skew",
                "backend tie behavior",
                "512-token gap-cap activation",
            ],
        },
        "substrate_cache": {
            "schema": SCALE_SUBSTRATE_SCHEMA,
            "ordinary_phase_policy": "source-locked clone per child",
            "end_to_end_policy": "cold materialization in every child",
            "source_files": sorted(_substrate_source_identity()),
            "materialization": substrate_materialization,
        },
        "shapes": shapes,
    }
    if emit_progress:
        _emit_scale_progress(
            "scale-campaign-complete", measurement_total=measurement_total
        )
    return captured


def production_growth_summary(
    points: tuple[Mapping[ScalePhase, RssPhaseMeasurement], ...],
) -> dict[str, dict[str, dict[str, object]]]:
    if len(points) < 3:
        raise ValueError("production growth requires at least three size points")
    xs = tuple(float(point["end_to_end"].ledger.A) for point in points)
    output: dict[str, dict[str, dict[str, object]]] = {}
    for phase in SCALE_PHASES:
        output[phase] = {}
        for metric in (
            "median_seconds",
            "median_lifetime_peak_bytes",
            "median_span_peak_bytes",
        ):
            if metric == "median_seconds":
                values = tuple(point[phase].median_seconds for point in points)
            else:
                field = metric.removeprefix("median_")
                values = tuple(point[phase].median(field) for point in points)
            output[phase][metric] = {
                "slope": ols_log_log_slope(xs, values),
                "adjacent_ratios": list(adjacent_ratios(values)),
                "max_slope": INV6_MAX_SLOPE,
                "max_adjacent_ratio": INV6_MAX_ADJACENT_RATIO,
            }
    return output


def assert_production_growth(
    growth: Mapping[str, Mapping[str, Mapping[str, object]]],
) -> None:
    for phase, metrics in growth.items():
        for metric, summary in metrics.items():
            slope = float(summary["slope"])
            ratios = tuple(float(value) for value in summary["adjacent_ratios"])
            if slope > INV6_MAX_SLOPE:
                raise AssertionError(f"{phase}/{metric} slope {slope:.6f} exceeds 1.5")
            if any(value > INV6_MAX_ADJACENT_RATIO for value in ratios):
                raise AssertionError(
                    f"{phase}/{metric} adjacent ratios {ratios} exceed 50"
                )


def absolute_end_to_end_summary(captured: Mapping[str, object]) -> dict[str, object]:
    """Evaluate the pre-registered top-rung budget without raising.

    The five-run median is the registered statistic. Raw repetitions remain under each phase in
    ``captured`` so the summary cannot erase run-to-run variation.
    """
    if tuple(captured.get("atom_ladder", ())) != PRODUCTION_ATOM_LADDER:
        raise ValueError("absolute gate requires the registered production atom ladder")
    if captured.get("repetitions") != PRODUCTION_REPETITIONS:
        raise ValueError("absolute gate requires the registered five repetitions")
    shapes = captured.get("shapes")
    if not isinstance(shapes, Mapping) or set(shapes) != set(SCALE_SHAPES):
        raise ValueError("absolute gate requires exactly the wide and deep shapes")
    observations: dict[str, object] = {}
    for shape in SCALE_SHAPES:
        shape_data = shapes[shape]
        if not isinstance(shape_data, Mapping):
            raise ValueError(f"malformed {shape} scale result")
        points = shape_data.get("points")
        if not isinstance(points, list):
            raise ValueError(f"malformed {shape} scale points")
        top_points = [
            point
            for point in points
            if isinstance(point, Mapping)
            and isinstance(point.get("ledger"), Mapping)
            and point["ledger"].get("A") == ABSOLUTE_END_TO_END_ATOM_COUNT
        ]
        if len(top_points) != 1:
            raise ValueError(
                f"{shape} must contain exactly one {ABSOLUTE_END_TO_END_ATOM_COUNT}-atom point"
            )
        phases = top_points[0].get("phases")
        if not isinstance(phases, Mapping) or not isinstance(
            phases.get("end_to_end"), Mapping
        ):
            raise ValueError(f"{shape} top point lacks end_to_end measurements")
        end_to_end = phases["end_to_end"]
        seconds = float(end_to_end["median_seconds"])
        lifetime_bytes = float(end_to_end["median_lifetime_peak_bytes"])
        observations[shape] = {
            "median_seconds": seconds,
            "median_lifetime_peak_bytes": lifetime_bytes,
            "within_wall_clock_ceiling": seconds <= ABSOLUTE_END_TO_END_MAX_SECONDS,
            "within_lifetime_rss_ceiling": lifetime_bytes
            <= ABSOLUTE_LIFETIME_RSS_MAX_BYTES,
        }
    passed = all(
        bool(row["within_wall_clock_ceiling"])
        and bool(row["within_lifetime_rss_ceiling"])
        for row in observations.values()
    )
    return {
        "status": "PASS" if passed else "FAIL",
        "atom_count": ABSOLUTE_END_TO_END_ATOM_COUNT,
        "statistic": "median-of-5",
        "max_seconds": ABSOLUTE_END_TO_END_MAX_SECONDS,
        "max_lifetime_rss_bytes": ABSOLUTE_LIFETIME_RSS_MAX_BYTES,
        "observations": observations,
    }


def assert_absolute_end_to_end_budget(captured: Mapping[str, object]) -> None:
    summary = absolute_end_to_end_summary(captured)
    failures = [
        f"{shape}: {row}"
        for shape, row in summary["observations"].items()
        if not row["within_wall_clock_ceiling"]
        or not row["within_lifetime_rss_ceiling"]
    ]
    if failures:
        raise AssertionError(
            "absolute end-to-end production budget exceeded: " + "; ".join(failures)
        )


def production_profile_gate_evaluation(
    captured: Mapping[str, object], *, require_absolute: bool = True
) -> dict[str, object]:
    """Return a non-raising gate verdict suitable for a failure-preserving artifact."""
    failures: list[str] = []
    shapes = captured.get("shapes")
    if not isinstance(shapes, Mapping):
        failures.append("growth: captured profile has no shape mapping")
    else:
        for shape in SCALE_SHAPES:
            try:
                shape_data = shapes[shape]
                if not isinstance(shape_data, Mapping):
                    raise ValueError("malformed shape result")
                growth = shape_data["growth"]
                if not isinstance(growth, Mapping):
                    raise ValueError("malformed growth summary")
                assert_production_growth(growth)
            except (AssertionError, KeyError, TypeError, ValueError) as exc:
                failures.append(f"growth/{shape}: {exc}")

    density_rows = captured.get("density_sweep")
    if not isinstance(density_rows, list):
        failures.append("density: captured profile has no density rows")
    else:
        try:
            points = tuple(DensityPoint(**row) for row in density_rows)
            if {point.slots for point in points} != set(DENSITY_SLOT_LADDER):
                raise AssertionError("density surface lost a registered N-axis point")
            for slot_count in DENSITY_SLOT_LADDER:
                assert_density_sweep(
                    tuple(point for point in points if point.slots == slot_count)
                )
            density_growth = captured.get("density_timing_growth")
            if not isinstance(density_growth, Mapping) or set(density_growth) != {
                f"{fraction:.2f}" for fraction in DENSITY_REQUESTED_UNIQUE_FRACTIONS
            }:
                raise AssertionError(
                    "density timing growth lost a registered treatment"
                )
            for treatment, summary in density_growth.items():
                if not isinstance(summary, Mapping):
                    raise ValueError("malformed density timing summary")
                try:
                    assert_density_timing_growth(summary, treatment=str(treatment))
                except AssertionError as exc:
                    failures.append(f"density/{treatment}: {exc}")
        except (AssertionError, TypeError, ValueError) as exc:
            failures.append(f"density: {exc}")

    absolute: dict[str, object] | None = None
    if require_absolute:
        try:
            absolute = absolute_end_to_end_summary(captured)
            if absolute["status"] != "PASS":
                failures.append(
                    "absolute: top-rung wall-clock or lifetime-RSS ceiling exceeded"
                )
        except (AssertionError, KeyError, TypeError, ValueError) as exc:
            failures.append(f"absolute: {exc}")
    return {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "absolute_end_to_end": absolute,
    }


def assert_production_profile_gates(captured: Mapping[str, object]) -> None:
    evaluation = production_profile_gate_evaluation(captured)
    if evaluation["status"] != "PASS":
        raise AssertionError(
            "production scale gate failed: " + "; ".join(evaluation["failures"])
        )


def build_density_fixture(
    unique_fraction: float, *, slot_count: int = DENSITY_SLOT_COUNT
) -> RebindFixtureBundle:
    if unique_fraction not in DENSITY_REQUESTED_UNIQUE_FRACTIONS:
        raise ValueError("density fixture must use one of the registered sweep points")
    if slot_count not in DENSITY_SLOT_LADDER:
        raise ValueError("density fixture must use one of the registered N-axis points")
    unique_slots = round(slot_count * unique_fraction)
    nodes = [
        NodeSeed(
            "density-root",
            "volume",
            "container",
            children=tuple(f"density-leaf-{index:04d}" for index in range(slot_count)),
        )
    ]
    atoms: list[AtomSeed] = []
    for index in range(slot_count):
        node_id = f"density-leaf-{index:04d}"
        key = f"density-atom-{index:04d}"
        if index < unique_slots:
            text = " ".join(
                f"unique{index:03d}token{token_index:02d}"
                for token_index in range(DENSITY_TOKENS_PER_SLOT)
            )
        else:
            text = "repeat alpha beta gamma delta epsilon zeta eta"
        nodes.append(NodeSeed(node_id, "block", "leaf", body=(key,)))
        atoms.append(AtomSeed(key, text, node_id, SLOT_BODY))
    return materialize_fixture(
        FixtureSpec(
            "density-root", tuple(nodes), tuple(atoms), require_tokenless_cases=False
        ),
        DriftConfig(
            f"density-n{slot_count}-{unique_fraction:.2f}",
            62_000 + slot_count * 10 + unique_slots,
            (),
        ),
    )


def _actual_v3_anchor_density(bundle: RebindFixtureBundle) -> float:
    old = materialize_token_stream(bundle.old_canonical)
    fresh = materialize_token_stream(bundle.fresh_canonical)
    threshold = RebindPolicy().threshold(MODE_NO_GEOMETRY)
    queries = tuple(
        query
        for node in bundle.old_map.projection.nodes
        if node.rebind_anchors is not None
        for slot_name in ("body", "heading", "signature")
        if (pair := node.rebind_anchors.boundaries(slot_name)) is not None
        for query in ((pair.start, "start"), (pair.end, "end"))
    )
    old_locator = BoundaryAnchorBatchLocator(old.tokens, queries, threshold=threshold)
    fresh_locator = (
        old_locator
        if old.tokens == fresh.tokens
        else BoundaryAnchorBatchLocator(fresh.tokens, queries, threshold=threshold)
    )
    unique = total = 0
    for node in bundle.old_map.projection.nodes:
        anchors = node.rebind_anchors
        if anchors is None:
            continue
        for slot_name in ("body", "heading", "signature"):
            pair = anchors.boundaries(slot_name)
            if pair is None:
                continue
            for side, anchor in (("start", pair.start), ("end", pair.end)):
                total += 1
                old_location = old_locator.locate(anchor, side=side)
                fresh_location = fresh_locator.locate(anchor, side=side)
                unique += (
                    len(old_location.boundaries) == len(fresh_location.boundaries) == 1
                )
    if not total:
        raise AssertionError("density fixture produced no v3 boundary anchors")
    return unique / total


def measure_density_point(
    unique_fraction: float,
    *,
    slot_count: int = DENSITY_SLOT_COUNT,
    repetitions: int = 1,
) -> DensityPoint:
    if repetitions < 1:
        raise ValueError("density repetitions must be positive")
    bundle = build_density_fixture(unique_fraction, slot_count=slot_count)
    # This paired sweep has remint-only drift, so its independent truth is the fixture's direct
    # provenance relation rather than the bounded edit-grid oracle (the sweep intentionally
    # exceeds that oracle's 512-token unit-test ceiling).
    old_by_key = {
        seed.key: atom.atom_id
        for seed, atom in zip(
            bundle.spec.atoms, bundle.old_canonical.atoms, strict=True
        )
    }
    fresh_by_old: dict[str, list[str]] = {}
    fresh_positions = {
        atom_id: index for index, atom_id in enumerate(bundle.relation.fresh_order)
    }
    for old_id, fresh_id in bundle.relation.pairs:
        fresh_by_old.setdefault(old_id, []).append(fresh_id)
    slots: list[SlotRef] = []
    allowed_rows: list[AllowedBind] = []
    for node in bundle.spec.nodes:
        if not node.body:
            continue
        slot = SlotRef(node.node_id, SLOT_BODY)
        slots.append(slot)
        fresh_ids = tuple(
            fresh_id
            for key in node.body
            for fresh_id in sorted(
                fresh_by_old[old_by_key[key]], key=fresh_positions.__getitem__
            )
        )
        allowed_rows.append(AllowedBind(slot, fresh_ids))
    allowed = frozenset(allowed_rows)
    diagnostics = []
    elapsed: list[float] = []
    samples: list[Mapping[str, object]] = []
    for repetition_index in range(repetitions):
        telemetry = RebindTelemetry()
        started = time.perf_counter()
        result = rebind(
            RebindContext(
                bundle.old_map,
                bundle.old_streams,
                bundle.fresh_streams,
                geometry_mode=MODE_NO_GEOMETRY,
                telemetry=telemetry,
            )
        )
        elapsed_seconds = time.perf_counter() - started
        elapsed.append(elapsed_seconds)
        observed = tuple(
            ObservedBind(SlotRef(node.node_id, slot.slot_name), slot.fresh_atom_ids)
            for node in result.report.nodes
            for slot in node.slots
            if slot.bound
        )
        assert_bound_subset_and_disjoint(observed, allowed)
        diagnostic = diagnose_case(
            f"density-n{slot_count}-{unique_fraction:.2f}",
            slots,
            observed,
            allowed,
        )
        diagnostics.append(diagnostic)
        samples.append(
            {
                "repetition": repetition_index + 1,
                "elapsed_seconds": elapsed_seconds,
                "bound_correct": diagnostic.bound_correct,
                "abstained": diagnostic.abstained,
                "wrong": diagnostic.wrong,
                "telemetry": telemetry.to_json(),
            }
        )
    if len(set(diagnostics)) != 1:
        raise AssertionError("density outcome changed across identical repetitions")
    diagnostic = diagnostics[0]
    return DensityPoint(
        requested_unique_fraction=unique_fraction,
        measured_anchor_density=_actual_v3_anchor_density(bundle),
        slots=len(slots),
        tokens=len(slots) * DENSITY_TOKENS_PER_SLOT,
        repetitions=repetitions,
        median_seconds=statistics.median(elapsed),
        bound_correct=diagnostic.bound_correct,
        abstained=diagnostic.abstained,
        wrong=diagnostic.wrong,
        samples=tuple(samples),
    )


def measure_density_sweep(
    *,
    slot_count: int = DENSITY_SLOT_COUNT,
    repetitions: int = 1,
    enforce: bool = True,
    point_offset: int = 0,
    point_total: int | None = None,
    emit_progress: bool = False,
    event_callback: ProgressEventCallback | None = None,
) -> tuple[DensityPoint, ...]:
    total = point_total or len(DENSITY_REQUESTED_UNIQUE_FRACTIONS)
    rows: list[DensityPoint] = []
    for fraction_index, fraction in enumerate(DENSITY_REQUESTED_UNIQUE_FRACTIONS):
        point_index = point_offset + fraction_index + 1
        if emit_progress:
            _emit_scale_progress(
                "density-point-start",
                density_point_index=point_index,
                density_point_total=total,
                slot_count=slot_count,
                requested_unique_fraction=fraction,
                repetitions=repetitions,
            )
        point = measure_density_point(
            fraction, slot_count=slot_count, repetitions=repetitions
        )
        rows.append(point)
        if emit_progress:
            _emit_scale_progress(
                "density-point-complete",
                density_point_index=point_index,
                density_point_total=total,
                **point.to_json(),
            )
        if event_callback is not None:
            event_callback(
                {
                    "event": "density-point-complete",
                    "density_point_index": point_index,
                    "density_point_total": total,
                    "point": point.to_json(),
                }
            )
    points = tuple(rows)
    if enforce:
        assert_density_sweep(points)
    return points


def assert_density_sweep(points: tuple[DensityPoint, ...]) -> None:
    if len(points) != len(DENSITY_REQUESTED_UNIQUE_FRACTIONS):
        raise AssertionError("density sweep lost a registered treatment point")
    if len({point.slots for point in points}) != 1:
        raise AssertionError("one density sweep must hold N fixed")
    densities = tuple(point.measured_anchor_density for point in points)
    abstentions = tuple(point.abstained for point in points)
    if any(point.wrong for point in points):
        raise AssertionError("wrong-content bind appeared on the density sweep")
    if any(right >= left for left, right in zip(densities, densities[1:])):
        raise AssertionError(
            f"measured v3 anchor density is not strictly descending: {densities}"
        )
    if any(right < left for left, right in zip(abstentions, abstentions[1:])):
        raise AssertionError(
            f"fail-loud count fell as anchor density thinned: {abstentions}"
        )


def measure_density_surface(
    *,
    enforce: bool = True,
    emit_progress: bool = False,
    event_callback: ProgressEventCallback | None = None,
) -> tuple[tuple[DensityPoint, ...], dict[str, object]]:
    point_total = len(DENSITY_SLOT_LADDER) * len(DENSITY_REQUESTED_UNIQUE_FRACTIONS)
    if emit_progress:
        _emit_scale_progress(
            "density-campaign-start",
            density_point_total=point_total,
            slot_ladder=list(DENSITY_SLOT_LADDER),
            repetitions=DENSITY_REPETITIONS,
        )
    rows = tuple(
        point
        for slot_index, slot_count in enumerate(DENSITY_SLOT_LADDER)
        for point in measure_density_sweep(
            slot_count=slot_count,
            repetitions=DENSITY_REPETITIONS,
            enforce=enforce,
            point_offset=slot_index * len(DENSITY_REQUESTED_UNIQUE_FRACTIONS),
            point_total=point_total,
            emit_progress=emit_progress,
            event_callback=event_callback,
        )
    )
    growth: dict[str, object] = {}
    xs = tuple(float(value) for value in DENSITY_SLOT_LADDER)
    for fraction in DENSITY_REQUESTED_UNIQUE_FRACTIONS:
        treatment = tuple(
            point for point in rows if point.requested_unique_fraction == fraction
        )
        values = tuple(point.median_seconds for point in treatment)
        summary = {
            "slope": ols_log_log_slope(xs, values),
            "adjacent_ratios": list(adjacent_ratios(values)),
            "max_slope": INV6_MAX_SLOPE,
            "max_adjacent_ratio": INV6_MAX_ADJACENT_RATIO,
        }
        if enforce:
            assert_density_timing_growth(summary, treatment=f"{fraction:.2f}")
        growth[f"{fraction:.2f}"] = summary
    if emit_progress:
        _emit_scale_progress(
            "density-campaign-complete", density_point_total=point_total
        )
    return rows, growth


def assert_density_timing_growth(
    summary: Mapping[str, object], *, treatment: str
) -> None:
    if float(summary["slope"]) > INV6_MAX_SLOPE or any(
        float(value) > INV6_MAX_ADJACENT_RATIO for value in summary["adjacent_ratios"]
    ):
        raise AssertionError(
            f"density treatment {treatment} timing is not subquadratic: {summary}"
        )
