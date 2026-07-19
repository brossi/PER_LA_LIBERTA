"""S4.7 item 2 Priority 4 — INV-6/INV-7 saved-baseline carried reds."""

from __future__ import annotations

import hashlib
import json

import pytest

from harness.scale import (
    INV6_MAX_ADJACENT_RATIO,
    INV6_MAX_SLOPE,
    INV6_RED_TOKENS,
    INV7_DEPTH,
    INV7_MAX_PEAK_BYTES,
    INV7_MAX_SECONDS,
    PRIORITY4_BASELINE,
    PRIORITY5_BASELINE,
    REPETITIONS,
    adjacent_ratios,
    assert_growth_within_limits,
    build_rebind_scale_fixture,
    load_priority4_baseline,
    measure_phase,
    ols_log_log_slope,
)

TRACKER = "S5.1-R/#48 (S4.7 item 3)"
INV7_TRACKER = "S4.7-E — deep-evidence composite traversal wall-clock follow-up"

# Structural corruption or a stale/missing ladder is a collection error, never an expected
# performance failure. Source identity is checked in its own green test so mutation scopes can
# exercise the harness without turning an intentional source patch into an import error.
BASELINE = load_priority4_baseline(
    PRIORITY5_BASELINE, verify_source_identity=False
)


def _growth(phase: str, metric: str):
    return BASELINE["inv6"]["growth_by_phase"][phase][metric]


def test_priority4_preregistered_constants_and_upward_only_ladder_are_pinned():
    assert REPETITIONS == 5
    assert INV6_RED_TOKENS == (300, 600, 1200, 2400, 4800)
    assert INV6_MAX_SLOPE == 1.5
    assert INV6_MAX_ADJACENT_RATIO == 50.0
    assert INV7_DEPTH == 3_000
    assert INV7_MAX_SECONDS == 2.0
    assert INV7_MAX_PEAK_BYTES == 512 * 1024 * 1024


def test_inv6_fixture_uses_exact_ledger_and_contiguous_nonempty_slots():
    fixture = build_rebind_scale_fixture(2_400)
    assert fixture.ledger.to_json() == {
        "family": "wide-rebind-pll-ratio",
        "L": 2,
        "K": 2,
        "A": 67,
        "T": 2_400,
        "D": 2,
    }
    old_ids = tuple(atom.atom_id for atom in fixture.bundle.old_canonical.atoms)
    leaves = fixture.bundle.old_map.projection.nodes[1:]
    positions = {atom_id: index for index, atom_id in enumerate(old_ids)}
    for leaf in leaves:
        indices = [positions[atom_id] for atom_id in leaf.body_atoms]
        assert indices
        assert indices == list(range(indices[0], indices[-1] + 1))


def test_perf_measurement_validates_every_run_and_observes_python_allocations():
    validations = []

    def operation():
        return bytearray(32_768)

    def validate(value):
        assert len(value) == 32_768
        validations.append(len(value))

    measured = measure_phase(operation, validate)
    assert len(validations) == 2 * REPETITIONS
    assert len(measured.elapsed_seconds) == REPETITIONS
    assert len(measured.peak_bytes) == REPETITIONS
    assert measured.median_peak_bytes >= 32_768


def test_perf_measurement_never_swallows_a_phase_validation_failure():
    def reject(_value):
        raise AssertionError("planted phase-incomplete")

    with pytest.raises(AssertionError, match="phase-incomplete"):
        measure_phase(lambda: object(), reject)


def test_growth_estimator_distinguishes_linear_from_quadratic_and_keeps_ratios():
    xs = (1.0, 10.0, 100.0)
    assert ols_log_log_slope(xs, xs) == pytest.approx(1.0)
    assert ols_log_log_slope(xs, tuple(value**2 for value in xs)) == pytest.approx(2.0)
    assert adjacent_ratios((1.0, 10.0, 1_000.0)) == (10.0, 100.0)


def test_growth_budget_rejects_an_excessive_slope_or_adjacent_ratio():
    with pytest.raises(AssertionError, match="slope"):
        assert_growth_within_limits(
            {"slope": 1.6, "adjacent_ratios": [2.0]}, metric="planted slope"
        )
    with pytest.raises(AssertionError, match="adjacent ratio"):
        assert_growth_within_limits(
            {"slope": 1.0, "adjacent_ratios": [51.0]}, metric="planted ratio"
        )


def test_priority5_baseline_identity_phase_completion_and_raw_samples_are_green():
    baseline = load_priority4_baseline(
        PRIORITY5_BASELINE, verify_source_identity=True
    )
    assert [point["ledger"]["T"] for point in baseline["inv6"]["points"]] == list(
        INV6_RED_TOKENS
    )
    for point in baseline["inv6"]["points"]:
        assert point["preflight"] == {
            "serialize": True,
            "load": True,
            "index": True,
            "rebind": True,
            "end_to_end": True,
            "reported_nodes": point["ledger"]["L"] + 1,
        }
        for phase in ("serialize", "load", "index", "rebind", "end_to_end"):
            measured = point["phases"][phase]
            assert len(measured["elapsed_seconds"]) == REPETITIONS
            assert len(measured["peak_bytes"]) == REPETITIONS
            assert measured["median_seconds"] > 0
            assert measured["median_peak_bytes"] >= 0
    inv7 = baseline["inv7"]
    assert inv7["ledger"] == {
        "family": "deep-evidence-isolated-core",
        "L": 3_000,
        "K": 3_000,
        "A": 3_000,
        "T": 3_000,
        "D": 3_000,
    }
    assert inv7["preflight"]["decoded_witness_ids"] == 4_501_500
    assert inv7["preflight"]["persisted_decode_feasible"] is False
    assert inv7["preflight"]["decode_budget"] == 1_000_000


def test_priority4_baseline_file_hash_is_stable_for_the_evidence_wrapper():
    assert PRIORITY4_BASELINE.is_file()
    assert hashlib.sha256(PRIORITY4_BASELINE.read_bytes()).hexdigest() == (
        "6eb8ed5c12b2272adb538cb62c7ce3ba082a7559b0093188cd4d6927b45408f7"
    )


def test_priority4_baseline_rejects_stale_source_identity(tmp_path):
    planted = json.loads(json.dumps(BASELINE))
    relative = next(iter(planted["source_identity"]))
    planted["source_identity"][relative] = "0" * 64
    path = tmp_path / "stale-baseline.json"
    path.write_text(json.dumps(planted), encoding="utf-8")
    with pytest.raises(ValueError, match="source identity is stale"):
        load_priority4_baseline(path, verify_source_identity=True)


def test_inv6_all_python_allocation_growth_conjuncts_are_within_the_registered_bar():
    for phase in ("serialize", "load", "index", "rebind", "end_to_end"):
        assert_growth_within_limits(
            _growth(phase, "tracemalloc_peak"), metric=f"{phase} memory"
        )


def test_inv6_non_rebind_wall_clock_phases_are_within_the_registered_bar():
    for phase in ("serialize", "load", "index"):
        assert_growth_within_limits(
            _growth(phase, "wall_clock"), metric=f"{phase} wall clock"
        )


def test_inv6_anchored_rebind_wall_growth_is_within_the_preregistered_bar():
    assert_growth_within_limits(
        _growth("rebind", "wall_clock"), metric="rebind wall clock"
    )


def test_inv6_anchored_end_to_end_wall_growth_is_within_the_preregistered_bar():
    assert_growth_within_limits(
        _growth("end_to_end", "wall_clock"), metric="end-to-end wall clock"
    )


def test_inv7_deep_evidence_python_allocation_peak_is_within_the_registered_ceiling():
    measured = BASELINE["inv7"]["evidence_findings"]
    assert measured["median_peak_bytes"] <= INV7_MAX_PEAK_BYTES
    assert BASELINE["inv7"]["within_tracemalloc_ceiling"] is True


@pytest.mark.xfail(strict=True, reason=INV7_TRACKER)
def test_inv7_deep_evidence_wall_clock_exceeds_the_preregistered_ceiling():
    observed = BASELINE["inv7"]["evidence_findings"]["median_seconds"]
    assert observed <= INV7_MAX_SECONDS, (
        f"INV-7 evidence_findings median {observed:.6f}s exceeds preregistered "
        f"{INV7_MAX_SECONDS:.1f}s"
    )
