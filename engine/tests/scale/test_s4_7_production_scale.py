"""Nightly/opt-in S4.7 full 10^3/10^4/10^5 production scale gate."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from harness.scale_production import (
    DENSITY_REQUESTED_UNIQUE_FRACTIONS,
    DENSITY_SLOT_LADDER,
    PROGRESS_POLL_INTERVAL_SECONDS,
    PRODUCTION_ATOM_LADDER,
    PRODUCTION_REPETITIONS,
    SCALE_PHASES,
    SCALE_SHAPES,
    capture_production_profile,
    finalize_scale_progress,
    production_profile_gate_evaluation,
)

pytestmark = pytest.mark.scale


def _atomic_json_write(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def test_full_production_scale_growth_rss_and_density_gate():
    artifact_value = os.environ.get("S4_7_SCALE_ARTIFACT")
    artifact = Path(artifact_value) if artifact_value else None
    checkpoint = (
        artifact.with_name(f"{artifact.stem}.checkpoint.json")
        if artifact is not None
        else None
    )
    events: list[dict[str, object]] = []

    def record(event: dict[str, object]) -> None:
        events.append(event)
        if checkpoint is not None:
            _atomic_json_write(
                checkpoint,
                {
                    "schema": "s4.7-production-scale-pytest-checkpoint@v1",
                    "status": "IN_PROGRESS",
                    "progress_poll_interval_seconds": PROGRESS_POLL_INTERVAL_SECONDS,
                    "completed_event_count": len(events),
                    "last_event": event,
                    "events": events,
                },
            )

    captured = capture_production_profile(
        PRODUCTION_ATOM_LADDER,
        repetitions=PRODUCTION_REPETITIONS,
        enforce_growth=False,
        enforce_density=False,
        emit_progress=True,
        event_callback=record,
    )
    evaluation = production_profile_gate_evaluation(captured)
    assert captured["atom_ladder"] == list(PRODUCTION_ATOM_LADDER)
    assert captured["repetitions"] == PRODUCTION_REPETITIONS
    assert all(point["wrong"] == 0 for point in captured["density_sweep"])
    assert {point["slots"] for point in captured["density_sweep"]} == set(
        DENSITY_SLOT_LADDER
    )
    assert set(captured["density_timing_growth"]) == {
        f"{fraction:.2f}" for fraction in DENSITY_REQUESTED_UNIQUE_FRACTIONS
    }
    if artifact is not None:
        _atomic_json_write(
            artifact,
            {"gate_evaluation": evaluation, **captured},
        )
        if checkpoint is not None:
            _atomic_json_write(
                checkpoint,
                {
                    "schema": "s4.7-production-scale-pytest-checkpoint@v1",
                    "status": (
                        "COMPLETE"
                        if evaluation["status"] == "PASS"
                        else "COMPLETE_GATE_FAILED"
                    ),
                    "progress_poll_interval_seconds": PROGRESS_POLL_INTERVAL_SECONDS,
                    "completed_event_count": len(events),
                    "gate_evaluation": evaluation,
                    "events": events,
                },
            )
    try:
        assert evaluation["status"] == "PASS", evaluation["failures"]
    finally:
        finalize_scale_progress(
            status=(
                "COMPLETE"
                if evaluation["status"] == "PASS"
                else "COMPLETE_GATE_FAILED"
            ),
            measurement_total=(
                len(PRODUCTION_ATOM_LADDER)
                * len(SCALE_SHAPES)
                * len(SCALE_PHASES)
                * PRODUCTION_REPETITIONS
            ),
            failures=evaluation["failures"],
        )
