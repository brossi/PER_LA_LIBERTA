#!/usr/bin/env python3
"""Capture the S4.7 production scale/RSS/density profile as a source-locked artifact."""

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
    ABSOLUTE_END_TO_END_MAX_SECONDS,
    ABSOLUTE_LIFETIME_RSS_MAX_BYTES,
    PROGRESS_LOG_ENV,
    PROGRESS_ACTIVE_STATE_ENV,
    PROGRESS_FORMAT_ENV,
    PROGRESS_POLL_INTERVAL_ENV,
    PROGRESS_POLL_INTERVAL_SECONDS,
    PROGRESS_RUN_ID_ENV,
    PROGRESS_RUN_STARTED_NS_ENV,
    PRODUCTION_ATOM_LADDER,
    PRODUCTION_REPETITIONS,
    SCALE_PHASES,
    SCALE_SHAPES,
    SMALL_ATOM_LADDER,
    capture_production_profile,
    configured_progress_poll_interval_seconds,
    production_profile_gate_evaluation,
)

SOURCE_FILES = (
    "pyproject.toml",
    "docs/probes/s4_7_priority6_prereg.md",
    "src/engine/structure/atom_store.py",
    "src/engine/structure/boundary_anchor.py",
    "src/engine/structure/handles.py",
    "src/engine/structure/projection.py",
    "src/engine/structure/reanchor.py",
    "src/engine/structure/rebind.py",
    "src/engine/structure/rebind_telemetry.py",
    "src/engine/structure/structure_map.py",
    "tests/harness/materialize.py",
    "tests/harness/oracle.py",
    "tests/harness/relation.py",
    "tests/harness/scale.py",
    "tests/harness/scale_production.py",
    "tests/scale/test_s4_7_production_scale.py",
    "tests/unit/test_s4_7_scale_production.py",
    "tools/s4_7_scale.py",
    "uv.lock",
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
        else f"<rc={completed.returncode}>"
    )


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
            json.dump(payload, handle, indent=2)
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


class ScaleCheckpoint:
    def __init__(
        self, path: Path, *, profile: str, artifact: Path, metadata: dict[str, object]
    ) -> None:
        self.path = path.resolve()
        self.payload: dict[str, object] = {
            "schema": "s4.7-production-scale-checkpoint@v1",
            "status": "IN_PROGRESS",
            "started_at": _utc_now(),
            "updated_at": _utc_now(),
            "profile": profile,
            "artifact": str(artifact.resolve()),
            "progress_poll_interval_seconds": configured_progress_poll_interval_seconds(),
            "completed_event_count": 0,
            "events": [],
            **metadata,
        }
        self._write()

    def _write(self) -> None:
        self.payload["updated_at"] = _utc_now()
        _atomic_write(self.path, self.payload)

    def record(self, event: dict[str, object]) -> None:
        events = self.payload["events"]
        if not isinstance(events, list):
            raise AssertionError("checkpoint event collection was corrupted")
        events.append(event)
        self.payload["completed_event_count"] = len(events)
        self.payload["last_event"] = event
        self._write()

    def fail(self, exc: BaseException) -> None:
        self.payload["status"] = (
            "INTERRUPTED" if isinstance(exc, KeyboardInterrupt) else "ERROR"
        )
        self.payload["error"] = f"{type(exc).__name__}: {exc}"
        self.payload["traceback"] = traceback.format_exc()
        self._write()

    def complete(self, *, artifact: Path, gate_evaluation: dict[str, object]) -> None:
        self.payload["status"] = (
            "COMPLETE"
            if gate_evaluation["status"] != "FAIL"
            else "COMPLETE_GATE_FAILED"
        )
        self.payload["gate_evaluation"] = gate_evaluation
        self.payload["artifact_sha256"] = _sha256(artifact.resolve())
        self._write()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", required=True, type=Path)
    parser.add_argument("--profile", choices=("small", "full"), default="full")
    parser.add_argument("--repetitions", type=int)
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--progress-log", type=Path)
    parser.add_argument("--active-state", type=Path)
    parser.add_argument(
        "--progress-poll-interval-seconds",
        type=float,
        default=PROGRESS_POLL_INTERVAL_SECONDS,
        help="Parent heartbeat cadence; registered routine campaigns default to 15 seconds.",
    )
    parser.add_argument(
        "--progress-format",
        choices=("human", "json", "both"),
        default="both",
    )
    args = parser.parse_args(argv)
    os.environ[PROGRESS_POLL_INTERVAL_ENV] = str(
        args.progress_poll_interval_seconds
    )
    progress_poll_interval = configured_progress_poll_interval_seconds()
    ladder = PRODUCTION_ATOM_LADDER if args.profile == "full" else SMALL_ATOM_LADDER
    expected_repetitions = PRODUCTION_REPETITIONS if args.profile == "full" else 1
    repetitions = args.repetitions or expected_repetitions
    if args.profile == "full" and repetitions != PRODUCTION_REPETITIONS:
        raise ValueError(
            f"full profile is registered at {PRODUCTION_REPETITIONS} repetitions, got {repetitions}"
        )
    artifact = args.artifact.resolve()
    progress_log: Path | None = None
    if args.progress_log is not None:
        progress_log = args.progress_log.resolve()
        progress_log.parent.mkdir(parents=True, exist_ok=True)
        progress_log.write_text("", encoding="utf-8")
        os.environ[PROGRESS_LOG_ENV] = str(progress_log)
    checkpoint_path = (
        args.checkpoint.resolve()
        if args.checkpoint is not None
        else artifact.with_name(f"{artifact.stem}.checkpoint.json")
    )
    active_state_path = (
        args.active_state.resolve()
        if args.active_state is not None
        else checkpoint_path.with_name(f"{checkpoint_path.stem}.active.json")
    )
    run_id = str(uuid.uuid4())
    run_started_monotonic_ns = time.monotonic_ns()
    os.environ[PROGRESS_ACTIVE_STATE_ENV] = str(active_state_path)
    os.environ[PROGRESS_FORMAT_ENV] = args.progress_format
    os.environ[PROGRESS_RUN_ID_ENV] = run_id
    os.environ[PROGRESS_RUN_STARTED_NS_ENV] = str(run_started_monotonic_ns)
    git_info = {
        "head": _git("rev-parse", "HEAD"),
        "branch": _git("branch", "--show-current"),
        "status": _git("status", "--short"),
    }
    environment = {
        "python": platform.python_version(),
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
    }
    source_identity = {
        relative: _sha256(ENGINE_ROOT / relative) for relative in SOURCE_FILES
    }
    checkpoint = ScaleCheckpoint(
        checkpoint_path,
        profile=args.profile,
        artifact=artifact,
        metadata={
            "command": [sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]],
            "git": git_info,
            "environment": environment,
            "source_identity": source_identity,
            "telemetry": {
                "run_id": run_id,
                "active_state": str(active_state_path),
                "progress_log": str(progress_log) if progress_log else None,
                "progress_format": args.progress_format,
            },
        },
    )
    _update_active_state(
        active_state_path,
        telemetry_schema="s4.7-scale-progress@v2",
        status="IN_PROGRESS",
        run_id=run_id,
        started_at=_utc_now(),
        profile=args.profile,
        measurement_total=(
            len(SCALE_SHAPES)
            * len(ladder)
            * len(SCALE_PHASES)
            * repetitions
        ),
        checkpoint=str(checkpoint.path),
        artifact=str(artifact),
    )
    try:
        captured = capture_production_profile(
            ladder,
            repetitions=repetitions,
            enforce_growth=False,
            full_density_surface=args.profile == "full",
            enforce_density=False,
            emit_progress=True,
            event_callback=checkpoint.record,
        )
    except KeyboardInterrupt as exc:
        checkpoint.fail(exc)
        _update_active_state(
            active_state_path,
            status="INTERRUPTED",
            run_id=run_id,
            error=f"{type(exc).__name__}: {exc}",
            updated_at=_utc_now(),
        )
        print(
            f"S4.7 production scale interrupted; checkpoint retained: {checkpoint.path}",
            file=sys.stderr,
        )
        return 130
    except BaseException as exc:
        checkpoint.fail(exc)
        _update_active_state(
            active_state_path,
            status="ERROR",
            run_id=run_id,
            error=f"{type(exc).__name__}: {exc}",
            traceback=traceback.format_exc(),
            updated_at=_utc_now(),
        )
        raise
    gate_evaluation = (
        production_profile_gate_evaluation(captured)
        if args.profile == "full"
        else {"status": "NOT_APPLICABLE", "failures": [], "absolute_end_to_end": None}
    )
    payload: dict[str, object] = {
        "schema": "s4.7-production-scale@v1",
        "created_at": _utc_now(),
        "profile": args.profile,
        "command": [sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]],
        "git": git_info,
        "environment": environment,
        "source_identity": source_identity,
        "telemetry": {
            "run_id": run_id,
            "progress_poll_interval_seconds": progress_poll_interval,
            "progress_format": args.progress_format,
            "progress_log": str(progress_log) if progress_log else None,
            "progress_log_sha256": (
                _sha256(progress_log) if progress_log is not None else None
            ),
            "active_state": str(active_state_path),
        },
        "growth_limits": {
            "max_slope": 1.5,
            "max_adjacent_ratio": 50.0,
        },
        "absolute_end_to_end_ceiling": {
            "status": "RULED",
            "owner": "Ben",
            "ruled_at": "2026-07-18",
            "preregistration": "docs/probes/s4_7_priority6_prereg.md",
            "statistic": "median-of-5",
            "max_seconds": ABSOLUTE_END_TO_END_MAX_SECONDS,
            "max_lifetime_rss_bytes": ABSOLUTE_LIFETIME_RSS_MAX_BYTES,
            "note": "Immutable post-ruling; lifetime RSS includes materialization.",
        },
        "gate_evaluation": gate_evaluation,
        **captured,
    }
    _atomic_write(artifact, payload)
    checkpoint.complete(artifact=artifact, gate_evaluation=gate_evaluation)
    _update_active_state(
        active_state_path,
        status=(
            "COMPLETE"
            if gate_evaluation["status"] != "FAIL"
            else "COMPLETE_GATE_FAILED"
        ),
        run_id=run_id,
        artifact=str(artifact),
        artifact_sha256=_sha256(artifact),
        gate_evaluation=gate_evaluation,
        updated_at=_utc_now(),
    )
    print(f"S4.7 production scale artifact written: {artifact}")
    print(f"S4.7 production scale checkpoint finalized: {checkpoint.path}")
    if gate_evaluation["status"] == "FAIL":
        print(
            "S4.7 production scale gate failed after artifact capture: "
            + "; ".join(gate_evaluation["failures"]),
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
