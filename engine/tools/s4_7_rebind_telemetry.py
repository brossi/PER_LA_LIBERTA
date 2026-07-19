#!/usr/bin/env python3
"""Capture a source-locked identical-versus-drifted S4.7 rebind comparison."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parent.parent
TESTS_ROOT = ENGINE_ROOT / "tests"
if str(TESTS_ROOT) not in sys.path:
    sys.path.insert(0, str(TESTS_ROOT))

from harness.scale_production import (  # noqa: E402
    OPTIMIZATION_PROGRESS_POLL_INTERVAL_SECONDS,
    PROGRESS_FORMAT_ENV,
    PROGRESS_LOG_ENV,
    PROGRESS_POLL_INTERVAL_ENV,
    PROGRESS_PREFIX,
    PROGRESS_RUN_ID_ENV,
    PROGRESS_RUN_STARTED_NS_ENV,
    ProductionScaleRecipe,
    ScaleProgressDescriptor,
    configured_progress_poll_interval_seconds,
    measure_rss_phase,
)

SCHEMA = "s4.7-rebind-telemetry-comparison@v2"
SOURCE_FILES = (
    "src/engine/structure/reanchor.py",
    "src/engine/structure/rebind.py",
    "src/engine/structure/rebind_telemetry.py",
    "tests/harness/materialize.py",
    "tests/harness/relation.py",
    "tests/harness/scale_production.py",
    "tools/s4_7_rebind_telemetry.py",
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


def _span_medians(samples: list[dict[str, object]]) -> dict[str, dict[str, float]]:
    by_name: dict[str, dict[str, list[float]]] = {}
    for sample in samples:
        telemetry = sample["telemetry"]
        if not isinstance(telemetry, dict):
            raise TypeError("sample telemetry must be a mapping")
        child_trace = telemetry["child_trace"]
        if not isinstance(child_trace, dict):
            raise TypeError("child trace must be a mapping")
        for span in child_trace["spans"]:
            row = by_name.setdefault(span["name"], {"wall": [], "cpu": []})
            row["wall"].append(float(span["wall_seconds"]))
            row["cpu"].append(float(span["cpu_seconds"]))
    return {
        name: {
            "median_wall_seconds": statistics.median(values["wall"]),
            "median_cpu_seconds": statistics.median(values["cpu"]),
        }
        for name, values in sorted(by_name.items())
    }


def _fingerprint_count_summary(samples: list[dict[str, object]]) -> dict[str, object]:
    evaluated: list[int] = []
    computations: list[int] = []
    for sample in samples:
        telemetry = sample["telemetry"]
        if not isinstance(telemetry, dict):
            raise TypeError("sample telemetry must be a mapping")
        child_trace = telemetry["child_trace"]
        if not isinstance(child_trace, dict):
            raise TypeError("child trace must be a mapping")
        resolve_span = next(
            span
            for span in child_trace["spans"]
            if span["name"] == "rebind.resolve-slots"
        )
        attributes = resolve_span["attributes"]
        evaluated.append(int(attributes["fingerprint_evaluated_slots"]))
        computations.append(int(attributes["fresh_fingerprint_computations"]))
    return {
        "fingerprint_evaluated_slots": evaluated,
        "fresh_fingerprint_computations": computations,
        "one_computation_per_evaluated_slot": evaluated == computations,
    }


def _progress_summary(path: Path) -> dict[str, object]:
    records: list[dict[str, object]] = []
    prefix = f"{PROGRESS_PREFIX} "
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith(prefix):
            raise ValueError("progress log contains a non-structured line")
        record = json.loads(line.removeprefix(prefix))
        if not isinstance(record, dict):
            raise TypeError("progress record must be a mapping")
        records.append(record)

    def values(name: str) -> list[float]:
        return [float(record[name]) for record in records if record.get(name) is not None]

    available = values("system_available_memory_bytes")
    memory = values("system_memory_percent")
    swap = values("system_swap_used_bytes")
    load = values("system_load_1m")
    child_cpu = values("child_cpu_percent_of_one_core")
    return {
        "record_count": len(records),
        "heartbeat_count": sum(record.get("event") == "heartbeat" for record in records),
        "event_sequence_first": records[0]["event_sequence"] if records else None,
        "event_sequence_last": records[-1]["event_sequence"] if records else None,
        "host": {
            "available_memory_min_bytes": min(available) if available else None,
            "available_memory_max_bytes": max(available) if available else None,
            "memory_percent_max": max(memory) if memory else None,
            "swap_used_max_bytes": max(swap) if swap else None,
            "load_1m_max": max(load) if load else None,
            "child_cpu_percent_min": min(child_cpu) if child_cpu else None,
            "child_cpu_percent_max": max(child_cpu) if child_cpu else None,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", required=True, type=Path)
    parser.add_argument("--stage", required=True)
    parser.add_argument("--atom-count", type=int, default=10_000)
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument(
        "--shape", choices=("all", "wide", "deep"), default="all"
    )
    parser.add_argument(
        "--fixture-variant",
        choices=("all", "identical", "drift"),
        default="all",
    )
    parser.add_argument("--progress-log", type=Path)
    parser.add_argument(
        "--progress-poll-interval-seconds",
        type=float,
        default=OPTIMIZATION_PROGRESS_POLL_INTERVAL_SECONDS,
        help="Parent heartbeat cadence; optimization runs default to 5 seconds.",
    )
    parser.add_argument(
        "--progress-format",
        choices=("human", "json", "both"),
        default="human",
    )
    args = parser.parse_args(argv)
    if args.atom_count < 40:
        raise ValueError("telemetry baseline atom count must be at least 40")
    if args.repetitions < 1:
        raise ValueError("telemetry baseline repetitions must be positive")
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
    progress_log.parent.mkdir(parents=True, exist_ok=True)
    with progress_log.open("w", encoding="utf-8") as handle:
        handle.flush()
        os.fsync(handle.fileno())
    os.environ[PROGRESS_FORMAT_ENV] = args.progress_format
    os.environ[PROGRESS_LOG_ENV] = str(progress_log)
    os.environ[PROGRESS_RUN_ID_ENV] = str(uuid.uuid4())
    os.environ[PROGRESS_RUN_STARTED_NS_ENV] = str(time.monotonic_ns())
    shapes = ("wide", "deep") if args.shape == "all" else (args.shape,)
    variants = (
        ("identical", "drift")
        if args.fixture_variant == "all"
        else (args.fixture_variant,)
    )
    total = len(shapes) * len(variants) * args.repetitions
    measurement_index = 0
    cases: dict[str, dict[str, object]] = {}
    for shape in shapes:
        recipe = ProductionScaleRecipe(shape, args.atom_count)
        for variant in variants:
            samples: list[dict[str, object]] = []
            for repetition in range(1, args.repetitions + 1):
                measurement_index += 1
                descriptor = ScaleProgressDescriptor(
                    shape,
                    args.atom_count,
                    "rebind",
                    repetition,
                    args.repetitions,
                    measurement_index,
                    total,
                    variant,
                )
                sample = measure_rss_phase(
                    recipe,
                    "rebind",
                    progress=descriptor,
                    fixture_variant=variant,
                )
                samples.append(sample.to_json())
            key = f"{shape}/{variant}"
            cases[key] = {
                "shape": shape,
                "fixture_variant": variant,
                "atom_count": args.atom_count,
                "repetitions": args.repetitions,
                "median_named_span_seconds": statistics.median(
                    float(sample["elapsed_seconds"]) for sample in samples
                ),
                "median_lifetime_peak_bytes": statistics.median(
                    int(sample["lifetime_peak_bytes"]) for sample in samples
                ),
                "span_medians": _span_medians(samples),
                "fingerprint_counts": _fingerprint_count_summary(samples),
                "samples": samples,
            }

    payload: dict[str, object] = {
        "schema": SCHEMA,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "stage": args.stage,
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
        "source_identity": {
            relative: _sha256(ENGINE_ROOT / relative) for relative in SOURCE_FILES
        },
        "fixture": {
            "identical": "reminted atom ids with identical old/fresh tokens",
            "drift": (
                "one OCR-class token edit plus one split and one merge per "
                "400 old atoms; aggregate atom cardinality remains stable"
            ),
        },
        "step_semantics": "phase.repetition; this diagnostic measures phase 4 (rebind) only",
        "progress": {
            "path": str(progress_log),
            "sha256": _sha256(progress_log),
            "poll_interval_seconds": progress_poll_interval,
            "summary": _progress_summary(progress_log),
        },
        "cases": cases,
    }
    _atomic_write(artifact, payload)
    print(f"S4.7 rebind telemetry comparison written: {artifact}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
