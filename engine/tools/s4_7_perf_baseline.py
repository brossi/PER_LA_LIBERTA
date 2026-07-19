#!/usr/bin/env python3
"""Capture the preregistered S4.7 item-2 INV-6/INV-7 performance baseline."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parent.parent
TESTS_ROOT = ENGINE_ROOT / "tests"
if str(TESTS_ROOT) not in sys.path:
    sys.path.insert(0, str(TESTS_ROOT))

from harness.scale import (  # noqa: E402
    INV6_MAX_ADJACENT_RATIO,
    INV6_MAX_SLOPE,
    INV6_RED_TOKENS,
    INV7_MAX_PEAK_BYTES,
    INV7_MAX_SECONDS,
    REPETITIONS,
    build_deep_evidence_fixture,
    build_rebind_scale_fixture,
    growth_summary,
    measure_evidence_findings,
    measure_phase,
    preflight_deep_evidence_fixture,
    preflight_rebind_fixture,
    rebind_phase_operations,
)

SOURCE_FILES = (
    "src/engine/structure/evidence.py",
    "src/engine/structure/artifacts.py",
    "src/engine/structure/boundary_anchor.py",
    "src/engine/structure/rebind.py",
    "src/engine/structure/reanchor.py",
    "src/engine/structure/schema/structure_map.schema.json",
    "src/engine/structure/structure_map.py",
    "tests/harness/materialize.py",
    "tests/harness/scale.py",
    "tools/s4_7_perf_baseline.py",
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
    return (
        completed.stdout.strip()
        if completed.returncode == 0
        else f"<git rc={completed.returncode}>"
    )


def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
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
            json.dump(payload, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", required=True, type=Path)
    args = parser.parse_args(argv)

    points: list[dict[str, object]] = []
    for target_tokens in INV6_RED_TOKENS:
        print(f"INV-6: build/preflight T={target_tokens}", flush=True)
        fixture = build_rebind_scale_fixture(target_tokens)
        preflight = preflight_rebind_fixture(fixture)
        phases: dict[str, object] = {}
        for phase, (operation, validate) in rebind_phase_operations(fixture).items():
            print(f"INV-6: measure T={target_tokens} phase={phase}", flush=True)
            phases[phase] = measure_phase(operation, validate).to_json()
        points.append(
            {
                "ledger": fixture.ledger.to_json(),
                "seed": fixture.bundle.config.seed,
                "preflight": preflight,
                "phases": phases,
            }
        )

    xs = tuple(float(point["ledger"]["T"]) for point in points)
    growth_by_phase: dict[str, object] = {}
    for phase in ("serialize", "load", "index", "rebind", "end_to_end"):
        wall = tuple(
            float(point["phases"][phase]["median_seconds"]) for point in points
        )
        memory = tuple(
            float(point["phases"][phase]["median_peak_bytes"]) for point in points
        )
        growth_by_phase[phase] = {
            "wall_clock": growth_summary(xs, wall),
            "tracemalloc_peak": growth_summary(xs, memory),
        }

    print("INV-7: build/preflight D=3000", flush=True)
    deep = build_deep_evidence_fixture()
    deep_preflight = preflight_deep_evidence_fixture(deep)
    print("INV-7: measure evidence_findings", flush=True)
    evidence_measurement = measure_evidence_findings(deep)

    source_identity = {
        relative: _sha256(ENGINE_ROOT / relative) for relative in SOURCE_FILES
    }
    payload: dict[str, object] = {
        "schema": "s4.7-perf-baseline@v2",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "command": [sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]],
        "repo": str(ENGINE_ROOT),
        "git": {
            "head": _git("rev-parse", "HEAD"),
            "branch": _git("branch", "--show-current"),
            "status": _git("status", "--short"),
        },
        "environment": {
            "python": platform.python_version(),
            "python_executable": sys.executable,
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "uv_lock_sha256": _sha256(ENGINE_ROOT / "uv.lock"),
        },
        "repetitions": REPETITIONS,
        "source_identity": source_identity,
        "inv6": {
            "axis": "T",
            "ladder": list(INV6_RED_TOKENS),
            "limits": {
                "max_slope": INV6_MAX_SLOPE,
                "max_adjacent_ratio": INV6_MAX_ADJACENT_RATIO,
            },
            "points": points,
            "growth_by_phase": growth_by_phase,
        },
        "inv7": {
            "ledger": deep.ledger.to_json(),
            "limits": {
                "max_seconds": INV7_MAX_SECONDS,
                "max_peak_bytes": INV7_MAX_PEAK_BYTES,
            },
            "preflight": deep_preflight,
            "evidence_findings": evidence_measurement.to_json(),
            "within_wall_clock_ceiling": evidence_measurement.median_seconds
            <= INV7_MAX_SECONDS,
            "within_tracemalloc_ceiling": (
                evidence_measurement.median_peak_bytes <= INV7_MAX_PEAK_BYTES
            ),
        },
    }
    artifact = args.artifact.resolve()
    _atomic_write_json(artifact, payload)
    print(f"S4.7 performance baseline written: {artifact}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
