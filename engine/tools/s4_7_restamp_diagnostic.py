#!/usr/bin/env python3
"""Capture the focused, diagnostic-only S4.7 evidence-restamp measurement."""

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

from harness.restamp_diagnostic import (  # noqa: E402
    build_restamp_diagnostic_fixture,
    measure_restamp_diagnostic,
)

SOURCE_FILES = (
    "src/engine/structure/evidence.py",
    "src/engine/structure/projection.py",
    "src/engine/structure/rebind.py",
    "tests/harness/restamp_diagnostic.py",
    "tests/harness/scale.py",
    "tools/s4_7_restamp_diagnostic.py",
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


def _comparison(before_path: Path, after: dict[str, object]) -> dict[str, object]:
    before = json.loads(before_path.read_text(encoding="utf-8"))
    if before.get("schema") != "s4.7-restamp-diagnostic@v1":
        raise ValueError("comparison artifact has an unexpected schema")
    if before.get("variant") != "before":
        raise ValueError("comparison artifact is not the before measurement")
    if before["fixture"]["expected_sha256"] != after["fixture"]["expected_sha256"]:
        raise ValueError("before/after expected restamp outputs differ")
    before_measurement = before["measurement"]
    return {
        "before_artifact": str(before_path.resolve()),
        "before_sha256": _sha256(before_path),
        "wall_speedup": before_measurement["median_wall_seconds"]
        / after["measurement"]["median_wall_seconds"],
        "cpu_speedup": before_measurement["median_cpu_seconds"]
        / after["measurement"]["median_cpu_seconds"],
        "peak_ratio_after_over_before": after["measurement"]["median_peak_bytes"]
        / before_measurement["median_peak_bytes"],
    }


def _progress(
    event: str, repetition: int, total: int, values: dict[str, float | int]
) -> None:
    suffix = " ".join(f"{key}={value}" for key, value in values.items())
    print(
        f"RESTAMP {event} repetition={repetition}/{total}"
        + (f" {suffix}" if suffix else ""),
        flush=True,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", choices=("before", "after"), required=True)
    parser.add_argument("--artifact", required=True, type=Path)
    parser.add_argument("--compare-to", type=Path)
    args = parser.parse_args(argv)
    if args.variant == "after" and args.compare_to is None:
        parser.error("--variant after requires --compare-to")
    if args.variant == "before" and args.compare_to is not None:
        parser.error("--compare-to is only valid for --variant after")

    print("RESTAMP fixture-build depth=3000 (outside measurement)", flush=True)
    fixture = build_restamp_diagnostic_fixture()
    print("RESTAMP fixture-preflight COMPLETE", flush=True)
    measured = measure_restamp_diagnostic(fixture, progress=_progress)

    payload: dict[str, object] = {
        "schema": "s4.7-restamp-diagnostic@v1",
        "variant": args.variant,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "command": [sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]],
        "operation": "engine.structure.rebind._restamp_evidence",
        "contract": {
            "diagnostic_only": True,
            "registered_gate_changed": False,
            "depth": 3_000,
            "repetitions": 5,
            "all_bound_success_path": True,
            "fixture_outside_measurement": True,
            "validation_after_every_sample": True,
            "allocation_measured_separately": True,
            "public_telemetry_changed": False,
        },
        "fixture": fixture.preflight,
        "measurement": measured.to_json(),
        "source_identity": {
            relative: _sha256(ENGINE_ROOT / relative) for relative in SOURCE_FILES
        },
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
    }
    if args.compare_to is not None:
        payload["comparison"] = _comparison(args.compare_to.resolve(), payload)

    artifact = args.artifact.resolve()
    _atomic_write_json(artifact, payload)
    print(f"RESTAMP artifact={artifact}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
