#!/usr/bin/env python3
"""Capture one source-locked five-phase S4.7 production-scale telemetry cycle."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parent.parent
TESTS_ROOT = ENGINE_ROOT / "tests"
if str(TESTS_ROOT) not in sys.path:
    sys.path.insert(0, str(TESTS_ROOT))

from harness.scale_production import (  # noqa: E402
    OPTIMIZATION_PROGRESS_POLL_INTERVAL_SECONDS,
    PROGRESS_ACTIVE_STATE_ENV,
    PROGRESS_FORMAT_ENV,
    PROGRESS_LOG_ENV,
    PROGRESS_POLL_INTERVAL_ENV,
    PROGRESS_RUN_ID_ENV,
    PROGRESS_RUN_STARTED_NS_ENV,
    SCALE_PHASES,
    SCALE_SHAPES,
    CachedScaleSubstrate,
    ProductionScaleRecipe,
    ScaleProgressDescriptor,
    configured_progress_poll_interval_seconds,
    measure_recipe,
    measure_rss_phase,
    validate_cached_scale_substrate,
)

SCHEMA = "s4.7-production-scale-cycle@v1"
CHECKPOINT_SCHEMA = "s4.7-production-scale-cycle-checkpoint@v1"
SOURCE_FILES = (
    "src/engine/structure/atom_store.py",
    "src/engine/structure/boundary_anchor.py",
    "src/engine/structure/handles.py",
    "src/engine/structure/projection.py",
    "src/engine/structure/reanchor.py",
    "src/engine/structure/rebind.py",
    "src/engine/structure/rebind_telemetry.py",
    "src/engine/structure/structure_map.py",
    "tests/harness/materialize.py",
    "tests/harness/relation.py",
    "tests/harness/scale.py",
    "tests/harness/scale_production.py",
    "tools/s4_7_scale_cycle.py",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ENGINE_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return completed.stdout.strip() if completed.returncode == 0 else f"<rc={completed.returncode}>"


def _atomic_write(path: Path, payload: dict[str, object]) -> None:
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


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _update_active_state(path: Path, **updates: object) -> None:
    current: dict[str, object] = {}
    if path.exists():
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            current = loaded
    current.update(updates)
    _atomic_write(path, current)


def _span_totals(sample: dict[str, object]) -> dict[str, dict[str, float]]:
    telemetry = sample["telemetry"]
    if not isinstance(telemetry, dict):
        raise TypeError("sample telemetry must be a mapping")
    child_trace = telemetry["child_trace"]
    if not isinstance(child_trace, dict):
        raise TypeError("child telemetry trace must be a mapping")
    totals: dict[str, dict[str, float]] = {}
    for span in child_trace["spans"]:
        name = str(span["name"])
        row = totals.setdefault(name, {"wall_seconds": 0.0, "cpu_seconds": 0.0})
        row["wall_seconds"] += float(span["wall_seconds"])
        row["cpu_seconds"] += float(span["cpu_seconds"])
    return dict(sorted(totals.items()))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", required=True, type=Path)
    parser.add_argument("--shape", choices=SCALE_SHAPES, default="wide")
    parser.add_argument("--atom-count", type=int, default=100_000)
    parser.add_argument("--progress-log", type=Path)
    parser.add_argument("--active-state", type=Path)
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument(
        "--progress-poll-interval-seconds",
        type=float,
        default=OPTIMIZATION_PROGRESS_POLL_INTERVAL_SECONDS,
        help="Parent heartbeat cadence; optimization runs default to 5 seconds.",
    )
    parser.add_argument(
        "--progress-format",
        choices=("human", "json", "both"),
        default="both",
    )
    args = parser.parse_args(argv)
    if args.atom_count < 1:
        raise ValueError("cycle atom count must be positive")
    os.environ[PROGRESS_POLL_INTERVAL_ENV] = str(
        args.progress_poll_interval_seconds
    )
    progress_poll_interval = configured_progress_poll_interval_seconds()

    artifact = args.artifact.resolve()
    progress_log = (
        args.progress_log.resolve()
        if args.progress_log is not None
        else artifact.with_suffix(".progress.ndjson")
    )
    active_state = (
        args.active_state.resolve()
        if args.active_state is not None
        else artifact.with_suffix(".active.json")
    )
    checkpoint_path = (
        args.checkpoint.resolve()
        if args.checkpoint is not None
        else artifact.with_suffix(".checkpoint.json")
    )
    progress_log.parent.mkdir(parents=True, exist_ok=True)
    with progress_log.open("w", encoding="utf-8") as handle:
        handle.flush()
        os.fsync(handle.fileno())

    run_id = str(uuid.uuid4())
    os.environ[PROGRESS_LOG_ENV] = str(progress_log)
    os.environ[PROGRESS_ACTIVE_STATE_ENV] = str(active_state)
    os.environ[PROGRESS_FORMAT_ENV] = args.progress_format
    os.environ[PROGRESS_RUN_ID_ENV] = run_id
    os.environ[PROGRESS_RUN_STARTED_NS_ENV] = str(time.monotonic_ns())

    source_identity = {
        relative: _sha256(ENGINE_ROOT / relative) for relative in SOURCE_FILES
    }
    recipe = ProductionScaleRecipe(args.shape, args.atom_count)
    events: list[dict[str, object]] = []
    metadata: dict[str, object] = {
        "schema": CHECKPOINT_SCHEMA,
        "status": "IN_PROGRESS",
        "created_at": _utc_now(),
        "updated_at": _utc_now(),
        "run_id": run_id,
        "artifact": str(artifact),
        "progress_log": str(progress_log),
        "active_state": str(active_state),
        "recipe": {
            "shape": args.shape,
            "atom_count": args.atom_count,
            "tokens_per_atom": recipe.tokens_per_atom,
        },
        "named_measurement_total": len(SCALE_PHASES),
        "progress_poll_interval_seconds": progress_poll_interval,
        "events": events,
    }

    def checkpoint(event: dict[str, object] | None = None, **updates: object) -> None:
        if event is not None:
            events.append(event)
            metadata["last_event"] = event
        metadata.update(updates)
        metadata["completed_event_count"] = len(events)
        metadata["updated_at"] = _utc_now()
        _atomic_write(checkpoint_path, metadata)

    checkpoint()
    _update_active_state(
        active_state,
        status="IN_PROGRESS",
        run_id=run_id,
        shape=args.shape,
        atom_count=args.atom_count,
        measurement_index=0,
        measurement_total=len(SCALE_PHASES),
        step_coordinate="prep",
        checkpoint=str(checkpoint_path),
        artifact=str(artifact),
    )

    try:
        with tempfile.TemporaryDirectory(
            prefix=f"s4_7_cycle_{args.shape}_a{args.atom_count}_"
        ) as substrate_temp:
            substrate_root = Path(substrate_temp) / "source-locked"
            prep_descriptor = ScaleProgressDescriptor(
                args.shape,
                args.atom_count,
                "materialize",
                0,
                1,
                0,
                len(SCALE_PHASES),
            )
            materialization = measure_rss_phase(
                recipe,
                "materialize",
                progress=prep_descriptor,
                cache_output=substrate_root,
            )
            checkpoint(
                {
                    "event": "substrate-materialization-complete",
                    "progress": prep_descriptor.to_json(),
                    "sample": materialization.to_json(),
                }
            )
            substrate = CachedScaleSubstrate(recipe, substrate_root)
            validate_cached_scale_substrate(substrate)
            measurements = measure_recipe(
                recipe,
                repetitions=1,
                measurement_total=len(SCALE_PHASES),
                emit_progress=True,
                event_callback=checkpoint,
                cached_substrate=substrate,
            )
    except KeyboardInterrupt as exc:
        checkpoint(status="INTERRUPTED", error=f"{type(exc).__name__}: {exc}")
        _update_active_state(
            active_state,
            status="INTERRUPTED",
            error=f"{type(exc).__name__}: {exc}",
            updated_at=_utc_now(),
        )
        return 130
    except BaseException as exc:
        trace = traceback.format_exc()
        checkpoint(
            status="ERROR",
            error=f"{type(exc).__name__}: {exc}",
            traceback=trace,
        )
        _update_active_state(
            active_state,
            status="ERROR",
            error=f"{type(exc).__name__}: {exc}",
            traceback=trace,
            updated_at=_utc_now(),
        )
        raise

    phase_rows = {
        phase: measurement.to_json() for phase, measurement in measurements.items()
    }
    payload: dict[str, object] = {
        "schema": SCHEMA,
        "created_at": _utc_now(),
        "run_id": run_id,
        "command": [sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]],
        "git": {
            "head": _git("rev-parse", "HEAD"),
            "branch": _git("branch", "--show-current"),
            "status": _git("status", "--short"),
        },
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
        },
        "source_identity": source_identity,
        "recipe": {
            "shape": args.shape,
            "atom_count": args.atom_count,
            "tokens_per_atom": recipe.tokens_per_atom,
            "ledger": recipe.ledger.to_json(),
        },
        "scope": {
            "repetitions": 1,
            "named_measurement_total": len(SCALE_PHASES),
            "phases": list(SCALE_PHASES),
            "materialization_reported_as": "prep",
            "end_to_end_is_cold_and_materialization_inclusive": True,
            "registered_gate_verdict": "NOT_APPLICABLE_SINGLE_REPETITION",
        },
        "telemetry": {
            "progress_format": args.progress_format,
            "progress_poll_interval_seconds": progress_poll_interval,
            "progress_log": str(progress_log),
            "progress_log_sha256": _sha256(progress_log),
            "active_state": str(active_state),
            "checkpoint": str(checkpoint_path),
        },
        "substrate_materialization": materialization.to_json(),
        "phases": phase_rows,
        "span_totals": {
            phase: _span_totals(row["samples"][0])
            for phase, row in phase_rows.items()
        },
    }
    _atomic_write(artifact, payload)
    artifact_hash = _sha256(artifact)
    checkpoint(
        status="COMPLETE",
        artifact_sha256=artifact_hash,
        progress_log_sha256=_sha256(progress_log),
    )
    _update_active_state(
        active_state,
        status="COMPLETE",
        artifact=str(artifact),
        artifact_sha256=artifact_hash,
        checkpoint=str(checkpoint_path),
        updated_at=_utc_now(),
    )
    print(f"S4.7 five-phase scale cycle written: {artifact}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
