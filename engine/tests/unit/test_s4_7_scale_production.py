"""Always-on controls for the S4.7 production scale and RSS harness."""

from __future__ import annotations

import inspect
import json
import tomllib
from pathlib import Path

import pytest

import engine.structure.rebind as rebind_module
from engine.structure.reanchor import BoundaryAnchorBatchLocator
from engine.structure.rebind import (
    WORK_PROGRESS_PUBLISH_INTERVAL_SECONDS,
    RebindContext,
    _AnchoredAssignment,
    _enumerate_slots,
)
from engine.structure.rebind_telemetry import (
    REBIN_TELEMETRY_SCHEMA,
    RebindTelemetry,
)
from harness.scale import adjacent_ratios, ols_log_log_slope
from harness.scale_production import (
    ABSOLUTE_END_TO_END_ATOM_COUNT,
    ABSOLUTE_END_TO_END_MAX_SECONDS,
    ABSOLUTE_LIFETIME_RSS_MAX_BYTES,
    DENSITY_REQUESTED_UNIQUE_FRACTIONS,
    DENSITY_REPETITIONS,
    DENSITY_SLOT_LADDER,
    OPTIMIZATION_PROGRESS_POLL_INTERVAL_SECONDS,
    PRODUCTION_ATOM_LADDER,
    PROGRESS_ACTIVE_STATE_ENV,
    PROGRESS_FORMAT_ENV,
    PROGRESS_LOG_ENV,
    PROGRESS_POLL_INTERVAL_ENV,
    PROGRESS_POLL_INTERVAL_SECONDS,
    PROGRESS_TELEMETRY_SCHEMA,
    RSS_PROBE_BYTES,
    RSS_SAMPLE_INTERVAL_SECONDS,
    RSS_START_METHOD,
    SCALE_SUBSTRATE_SCHEMA,
    SMALL_ATOM_LADDER,
    CachedScaleSubstrate,
    DensityPoint,
    ProductionScaleRecipe,
    RssPhaseSample,
    ScaleProgressDescriptor,
    _conservative_lifetime_peak_bytes,
    _emit_scale_progress,
    _phase_uses_cached_substrate,
    _substrate_source_identity,
    assert_absolute_end_to_end_budget,
    assert_density_sweep,
    assert_density_timing_growth,
    assert_production_growth,
    build_production_drift_fixture,
    build_production_scale_fixture,
    capture_production_profile,
    clone_cached_scale_substrate,
    configured_progress_poll_interval_seconds,
    create_cached_scale_substrate,
    finalize_scale_progress,
    index_production_fixture,
    load_production_fixture,
    measure_density_sweep,
    measure_rss_phase,
    persist_production_fixture,
    production_profile_gate_evaluation,
    run_production_rebind,
    validate_rss_sampler,
    validate_cached_scale_substrate,
)
from tools.s4_7_rebind_telemetry import SOURCE_FILES as TELEMETRY_SOURCE_FILES
from tools.s4_7_scale import SOURCE_FILES
from tools.s4_7_scale_cycle import (
    SCHEMA as SCALE_CYCLE_SCHEMA,
    SOURCE_FILES as SCALE_CYCLE_SOURCE_FILES,
)


def test_production_ladders_and_both_shape_ledgers_are_pinned():
    assert SMALL_ATOM_LADDER == (10, 100, 1_000)
    assert PRODUCTION_ATOM_LADDER == (1_000, 10_000, 100_000)
    assert ABSOLUTE_END_TO_END_ATOM_COUNT == 100_000
    assert ABSOLUTE_END_TO_END_MAX_SECONDS == 300.0
    assert ABSOLUTE_LIFETIME_RSS_MAX_BYTES == 6_442_450_944
    assert PROGRESS_POLL_INTERVAL_SECONDS == 15.0
    assert OPTIMIZATION_PROGRESS_POLL_INTERVAL_SECONDS == 5.0
    assert WORK_PROGRESS_PUBLISH_INTERVAL_SECONDS == 1.0
    assert RSS_SAMPLE_INTERVAL_SECONDS == 0.005
    assert RSS_START_METHOD == "spawn"
    assert SCALE_SUBSTRATE_SCHEMA == "s4.7-scale-substrate@v1"
    assert "tests/harness/relation.py" in _substrate_source_identity()
    assert "src/engine/structure/handles.py" in _substrate_source_identity()
    assert "src/engine/structure/projection.py" in _substrate_source_identity()
    assert "src/engine/structure/rebind_telemetry.py" in _substrate_source_identity()
    assert "src/engine/structure/handles.py" in SOURCE_FILES
    assert "src/engine/structure/projection.py" in SOURCE_FILES
    assert "src/engine/structure/rebind_telemetry.py" in TELEMETRY_SOURCE_FILES
    assert "tests/harness/scale_production.py" in TELEMETRY_SOURCE_FILES
    assert RSS_PROBE_BYTES == 64 * 1024 * 1024
    assert DENSITY_SLOT_LADDER == (24, 240, 2_400)
    assert DENSITY_REPETITIONS == 3
    assert (
        inspect.signature(capture_production_profile)
        .parameters["full_density_surface"]
        .default
        is True
    )
    wide = ProductionScaleRecipe("wide", 1_000).ledger
    deep = ProductionScaleRecipe("deep", 1_000).ledger
    assert wide.to_json() == {
        "family": "wide-rebind-production",
        "L": 25,
        "K": 25,
        "A": 1_000,
        "T": 36_000,
        "D": 4,
    }
    assert deep.to_json() == {
        "family": "deep-rebind-production",
        "L": 25,
        "K": 25,
        "A": 1_000,
        "T": 36_000,
        "D": 25,
    }


def test_progress_poll_interval_has_routine_default_and_validated_run_override(
    monkeypatch,
):
    monkeypatch.delenv(PROGRESS_POLL_INTERVAL_ENV, raising=False)
    assert configured_progress_poll_interval_seconds() == 15.0
    monkeypatch.setenv(PROGRESS_POLL_INTERVAL_ENV, "5")
    assert configured_progress_poll_interval_seconds() == 5.0
    monkeypatch.setenv(PROGRESS_POLL_INTERVAL_ENV, "1")
    assert configured_progress_poll_interval_seconds() == 1.0
    for invalid in ("0", "-1", "nan", "inf", "not-a-number"):
        monkeypatch.setenv(PROGRESS_POLL_INTERVAL_ENV, invalid)
        with pytest.raises(ValueError, match="positive finite number"):
            configured_progress_poll_interval_seconds()


def test_production_round_trip_uses_separate_real_workspaces(tmp_path, monkeypatch):
    import engine.structure.rebind as rebind_module

    def forbidden_duplication_analysis(*_args, **_kwargs):
        raise AssertionError("identical token streams must not build gram counters")

    monkeypatch.setattr(
        rebind_module,
        "_detect_introduced_token_duplication",
        forbidden_duplication_analysis,
    )
    recipe = ProductionScaleRecipe("wide", 10, tokens_per_atom=6)
    bundle = build_production_scale_fixture(recipe)
    persisted = persist_production_fixture(bundle, tmp_path)
    assert persisted.old_workspace.root != persisted.fresh_workspace.root
    assert (persisted.old_workspace.data / "atoms" / "canonical.json").is_file()
    assert (persisted.fresh_workspace.data / "atoms" / "canonical.json").is_file()
    assert (persisted.old_workspace.root / "structure_map.json").is_file()
    loaded = load_production_fixture(persisted)
    old_ids = {atom.atom_id for atom in loaded.old_streams["canonical"].atoms}
    fresh_ids = {atom.atom_id for atom in loaded.fresh_streams["canonical"].atoms}
    assert old_ids.isdisjoint(fresh_ids)
    telemetry = RebindTelemetry()
    indexed = index_production_fixture(loaded, telemetry=telemetry)
    result = run_production_rebind(indexed, telemetry=telemetry)
    assert result.report.unresolved == ()
    trace = telemetry.to_json()
    assert trace["schema"] == REBIN_TELEMETRY_SCHEMA
    names = {span["name"] for span in trace["spans"]}
    assert {
        "index.readers",
        "rebind.align-tokens",
        "rebind.locate-old-anchors",
        "rebind.detect-token-duplication",
        "rebind.resolve-slots",
        "rebind.resolve-slots.old-span-discovery",
        "rebind.resolve-slots.boundary-projection",
        "rebind.resolve-slots.atom-boundary-conversion",
        "rebind.resolve-slots.fingerprint-construction",
        "rebind.resolve-slots.fingerprint-metrics",
        "rebind.resolve-slots.outcome-assembly",
        "rebind.migrate-projection",
    } <= names
    assert all(span["wall_seconds"] >= 0 for span in trace["spans"])
    assert all(span["cpu_seconds"] >= 0 for span in trace["spans"])
    resolve_span = next(
        span for span in trace["spans"] if span["name"] == "rebind.resolve-slots"
    )
    assert resolve_span["attributes"]["fingerprint_evaluated_slots"] == recipe.ledger.K
    assert (
        resolve_span["attributes"]["fresh_fingerprint_computations"]
        == recipe.ledger.K
    )
    assert resolve_span["attributes"]["atom_boundary_lookup_calls"] == (
        2 * recipe.ledger.K
    )
    assert resolve_span["attributes"]["atom_boundary_inspected_ranges"] <= (
        resolve_span["attributes"]["atom_boundary_lookup_calls"]
        * (recipe.ledger.A.bit_length() + 1)
    )
    atom_boundary_span = next(
        span
        for span in trace["spans"]
        if span["name"] == "rebind.resolve-slots.atom-boundary-conversion"
    )
    assert atom_boundary_span["parent"] == "rebind.resolve-slots"
    assert atom_boundary_span["attributes"] == {
        "aggregation": "disjoint-call-total",
        "occurrences": 2 * recipe.ledger.K,
        "lookup_calls": 2 * recipe.ledger.K,
        "inspected_ranges": resolve_span["attributes"][
            "atom_boundary_inspected_ranges"
        ],
        "lookup_outcomes": {"resolved": 2 * recipe.ledger.K},
    }
    alignment_span = next(
        span for span in trace["spans"] if span["name"] == "rebind.align-tokens"
    )
    assert alignment_span["attributes"]["identity_fast_path"] is True
    duplication_span = next(
        span
        for span in trace["spans"]
        if span["name"] == "rebind.detect-token-duplication"
    )
    assert duplication_span["attributes"] == {
        "tokens_identical": True,
        "analysis_skipped": True,
        "gram_widths_analyzed": 0,
        "unresolved_duplication": False,
    }


def test_rebind_telemetry_publishes_nested_stage_progress_and_restores_parent():
    events: list[tuple[str, int | None, int | None]] = []
    telemetry = RebindTelemetry(
        stage_callback=lambda stage, completed, total: events.append(
            (stage, completed, total)
        )
    )
    with telemetry.span("outer", item_count=3):
        with telemetry.span("inner") as span:
            telemetry.progress(2, 3)
            span.update(answer=42)
    assert events == [
        ("outer", None, None),
        ("inner", None, None),
        ("inner", 2, 3),
        ("outer", None, None),
        ("idle", None, None),
    ]
    records = telemetry.to_json()["spans"]
    inner = next(record for record in records if record["name"] == "inner")
    assert inner["parent"] == "outer"
    assert inner["attributes"] == {"answer": 42}


def test_rebind_telemetry_records_disjoint_aggregate_without_live_stage_noise():
    events: list[tuple[str, int | None, int | None]] = []
    telemetry = RebindTelemetry(
        stage_callback=lambda stage, completed, total: events.append(
            (stage, completed, total)
        )
    )
    with telemetry.span("parent"):
        telemetry.record_aggregate_span(
            "parent.component",
            first_started_wall_ns=telemetry._origin_wall_ns,
            wall_ns=1_500_000_000,
            cpu_ns=750_000_000,
            occurrences=3,
            inspected=17,
        )

    record = next(
        item
        for item in telemetry.to_json()["spans"]
        if item["name"] == "parent.component"
    )
    assert record == {
        "name": "parent.component",
        "parent": "parent",
        "start_offset_seconds": 0.0,
        "wall_seconds": 1.5,
        "cpu_seconds": 0.75,
        "attributes": {
            "aggregation": "disjoint-call-total",
            "occurrences": 3,
            "inspected": 17,
        },
    }
    assert events == [("parent", None, None), ("idle", None, None)]


def test_rebind_telemetry_retains_error_type_before_reraising():
    telemetry = RebindTelemetry()
    with pytest.raises(RuntimeError, match="planted"):
        with telemetry.span("failing-stage"):
            raise RuntimeError("planted")
    assert telemetry.to_json()["spans"][0]["attributes"]["error_type"] == "RuntimeError"


def test_drift_telemetry_sentinel_is_token_changed_resegmented_and_correct(tmp_path):
    recipe = ProductionScaleRecipe("wide", 100, tokens_per_atom=6)
    bundle = build_production_drift_fixture(recipe)
    assert len(bundle.old_canonical.atoms) == len(bundle.fresh_canonical.atoms) == 100
    persisted = persist_production_fixture(bundle, tmp_path)
    indexed = index_production_fixture(load_production_fixture(persisted))
    telemetry = RebindTelemetry()
    result = run_production_rebind(indexed, telemetry=telemetry)
    assert result.report.unresolved == ()
    fresh_locator = next(
        span
        for span in telemetry.to_json()["spans"]
        if span["name"] == "rebind.locate-fresh-anchors"
    )
    assert fresh_locator["attributes"]["tokens_identical"] is False
    assert fresh_locator["attributes"]["reused_old_locator"] is False
    alignment = next(
        span
        for span in telemetry.to_json()["spans"]
        if span["name"] == "rebind.align-tokens"
    )
    assert alignment["attributes"]["identity_fast_path"] is False
    duplication = next(
        span
        for span in telemetry.to_json()["spans"]
        if span["name"] == "rebind.detect-token-duplication"
    )
    assert duplication["attributes"]["tokens_identical"] is False
    assert duplication["attributes"]["analysis_skipped"] is False
    assert duplication["attributes"]["gram_widths_analyzed"] == 3
    assert duplication["attributes"]["old_unique_1gram"] > 0


def test_source_locked_cached_substrate_is_clone_equivalent_and_tamper_loud(
    tmp_path,
):
    recipe = ProductionScaleRecipe("wide", 10, tokens_per_atom=6)
    bundle = build_production_scale_fixture(recipe)
    substrate = create_cached_scale_substrate(recipe, bundle, tmp_path / "cache")
    assert isinstance(substrate, CachedScaleSubstrate)
    manifest = json.loads(
        (substrate.root / "substrate.json").read_text(encoding="utf-8")
    )
    assert manifest["schema"] == SCALE_SUBSTRATE_SCHEMA
    assert manifest["cold_round_trip_equivalent"] is True

    source_persisted = validate_cached_scale_substrate(substrate)
    clone_persisted = clone_cached_scale_substrate(substrate, tmp_path / "clone")
    assert clone_persisted.old_workspace.root != source_persisted.old_workspace.root
    assert clone_persisted.fresh_workspace.root != source_persisted.fresh_workspace.root
    source = load_production_fixture(source_persisted)
    clone = load_production_fixture(clone_persisted)
    assert clone.old_map.doc == source.old_map.doc == bundle.old_map.doc
    assert clone.old_streams == source.old_streams == bundle.old_streams
    assert clone.fresh_streams == source.fresh_streams == bundle.fresh_streams

    original_manifest = dict(manifest)
    manifest["source_identity"] = {}
    (substrate.root / "substrate.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    with pytest.raises(AssertionError, match="source lock"):
        validate_cached_scale_substrate(substrate)

    manifest = dict(original_manifest)
    manifest["cold_round_trip_equivalent"] = False
    (substrate.root / "substrate.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    with pytest.raises(AssertionError, match="equivalence proof"):
        validate_cached_scale_substrate(substrate)

    (substrate.root / "substrate.json").write_text(
        json.dumps(original_manifest), encoding="utf-8"
    )
    canonical_path = next((substrate.root / "books").rglob("canonical.json"))
    canonical_path.write_text(
        canonical_path.read_text(encoding="utf-8") + "\n", encoding="utf-8"
    )
    with pytest.raises(AssertionError, match="persisted-file lock"):
        validate_cached_scale_substrate(substrate)


def test_end_to_end_never_uses_cached_substrate_including_absolute_gate():
    assert not _phase_uses_cached_substrate("end_to_end")
    assert all(
        _phase_uses_cached_substrate(phase)
        for phase in ("serialize", "load", "index", "rebind")
    )


def test_production_assignment_batches_anchor_windows_once_and_consumes_the_index(
    monkeypatch,
):
    recipe = ProductionScaleRecipe("wide", 100, tokens_per_atom=6)
    bundle = build_production_scale_fixture(recipe)
    context = RebindContext(
        bundle.old_map,
        bundle.old_streams,
        bundle.fresh_streams,
        geometry_mode="no-geometry",
    )
    slots = _enumerate_slots(context.old_map, context.old_canonical)
    assignment = _AnchoredAssignment(slots, context)
    assert assignment.fresh_anchor_locations is assignment.old_anchor_locations
    assert assignment.old_anchor_locations.windows_scanned <= (
        len(assignment.old.tokens) * 3
    )

    calls = 0
    original = BoundaryAnchorBatchLocator.locate

    def tracked(self, anchor, *, side):
        nonlocal calls
        calls += 1
        return original(self, anchor, side=side)

    monkeypatch.setattr(BoundaryAnchorBatchLocator, "locate", tracked)
    assignment.resolve_all()
    assert calls == 4 * len(slots)


def test_slot_progress_is_time_throttled_and_always_publishes_final_completion(
    monkeypatch,
):
    recipe = ProductionScaleRecipe("wide", 400, tokens_per_atom=6)
    bundle = build_production_scale_fixture(recipe)
    publications: list[tuple[str, int | None, int | None]] = []
    telemetry = RebindTelemetry(
        stage_callback=lambda stage, completed, total: publications.append(
            (stage, completed, total)
        )
    )
    context = RebindContext(
        bundle.old_map,
        bundle.old_streams,
        bundle.fresh_streams,
        geometry_mode="no-geometry",
        telemetry=telemetry,
    )
    slots = _enumerate_slots(context.old_map, context.old_canonical)
    assert len(slots) == 10
    assignment = _AnchoredAssignment(slots, context)
    publications.clear()
    ticks = iter((0.0, 0.4, 0.8, 1.2, 1.6, 2.0, 2.4, 2.8, 3.2, 3.6))
    monkeypatch.setattr(rebind_module.time, "monotonic", lambda: next(ticks))

    assignment.resolve_all()

    assert [
        (completed, total)
        for _stage, completed, total in publications
        if completed is not None
    ] == [(3, 10), (6, 10), (9, 10), (10, 10)]


def test_telemetry_disabled_slot_resolution_avoids_progress_clock(monkeypatch):
    recipe = ProductionScaleRecipe("wide", 100, tokens_per_atom=6)
    bundle = build_production_scale_fixture(recipe)
    context = RebindContext(
        bundle.old_map,
        bundle.old_streams,
        bundle.fresh_streams,
        geometry_mode="no-geometry",
    )
    slots = _enumerate_slots(context.old_map, context.old_canonical)
    assignment = _AnchoredAssignment(slots, context)
    monkeypatch.setattr(
        rebind_module.time,
        "monotonic",
        lambda: (_ for _ in ()).throw(AssertionError("progress clock consulted")),
    )

    assert len(assignment.resolve_all()) == len(slots)


def test_rss_sampler_captures_a_short_lived_native_visible_allocation():
    probe = validate_rss_sampler()
    assert probe.lifetime_peak_bytes == max(
        probe.raw_ru_maxrss_bytes, probe.span_peak_bytes
    )
    assert probe.lifetime_peak_bytes >= probe.span_peak_bytes
    assert probe.span_peak_bytes >= probe.setup_baseline_bytes
    assert probe.incremental_peak_bytes >= int(RSS_PROBE_BYTES * 0.80)
    assert probe.sample_count >= 2


def test_run_scoped_poll_override_drives_heartbeats_and_sample_provenance(
    monkeypatch, tmp_path
):
    progress_log = tmp_path / "fast-heartbeats.ndjson"
    monkeypatch.setenv(PROGRESS_POLL_INTERVAL_ENV, "0.01")
    monkeypatch.setenv(PROGRESS_LOG_ENV, str(progress_log))
    monkeypatch.setenv(PROGRESS_FORMAT_ENV, "json")
    descriptor = ScaleProgressDescriptor("wide", 1, "materialize", 0, 1, 0, 1)

    sample = measure_rss_phase(None, "allocation_probe", progress=descriptor)

    records = [
        json.loads(line.removeprefix("S4.7_SCALE_PROGRESS "))
        for line in progress_log.read_text(encoding="utf-8").splitlines()
    ]
    assert sum(record["event"] == "heartbeat" for record in records) >= 2
    assert sample.telemetry["progress_poll_interval_seconds"] == 0.01


def test_spawned_phase_reports_all_three_nested_rss_values():
    sample = measure_rss_phase(
        ProductionScaleRecipe("deep", 10, tokens_per_atom=6), "rebind"
    )
    assert sample.ledger.family == "deep-rebind-production"
    assert sample.elapsed_seconds > 0
    assert sample.setup_elapsed_seconds >= 0
    assert sample.monitor_elapsed_seconds >= sample.elapsed_seconds
    assert sample.lifetime_peak_bytes == max(
        sample.raw_ru_maxrss_bytes, sample.span_peak_bytes
    )
    assert sample.lifetime_peak_bytes >= sample.span_peak_bytes
    assert sample.span_peak_bytes >= sample.setup_baseline_bytes
    assert sample.incremental_peak_bytes == (
        sample.span_peak_bytes - sample.setup_baseline_bytes
    )
    assert sample.telemetry["schema"] == "s4.7-runtime-telemetry@v1"
    assert sample.telemetry["child_trace"]["schema"] == REBIN_TELEMETRY_SCHEMA
    assert sample.telemetry["child_trace"]["spans"]
    assert sample.telemetry["stage_rss"]


def test_spawned_drift_sentinel_is_labeled_and_runs_the_fresh_locator():
    sample = measure_rss_phase(
        ProductionScaleRecipe("wide", 40, tokens_per_atom=6),
        "rebind",
        fixture_variant="drift",
    )
    assert sample.telemetry["fixture_variant"] == "drift"
    spans = sample.telemetry["child_trace"]["spans"]
    fresh_locator = next(
        span for span in spans if span["name"] == "rebind.locate-fresh-anchors"
    )
    assert fresh_locator["attributes"]["tokens_identical"] is False
    assert fresh_locator["attributes"]["reused_old_locator"] is False


def test_always_on_small_end_to_end_ratio_is_subquadratic_in_both_shapes():
    xs = tuple(float(value) for value in SMALL_ATOM_LADDER)
    for shape in ("wide", "deep"):
        samples = tuple(
            measure_rss_phase(ProductionScaleRecipe(shape, atoms), "end_to_end")
            for atoms in SMALL_ATOM_LADDER
        )
        for field in ("elapsed_seconds", "lifetime_peak_bytes", "span_peak_bytes"):
            values = tuple(float(getattr(sample, field)) for sample in samples)
            assert ols_log_log_slope(xs, values) <= 1.5
            assert max(adjacent_ratios(values)) <= 50.0


def test_actual_v3_anchor_density_sweep_has_zero_wrong_binds_and_directional_abstention():
    points = measure_density_sweep()
    assert tuple(point.requested_unique_fraction for point in points) == (
        DENSITY_REQUESTED_UNIQUE_FRACTIONS
    )
    assert all(point.wrong == 0 for point in points)
    densities = tuple(point.measured_anchor_density for point in points)
    abstentions = tuple(point.abstained for point in points)
    assert all(left > right for left, right in zip(densities, densities[1:]))
    assert all(left <= right for left, right in zip(abstentions, abstentions[1:]))
    assert any(
        point.measured_anchor_density != point.requested_unique_fraction
        for point in points
    )
    assert all(len(point.samples) == point.repetitions for point in points)
    assert all(
        sample["telemetry"]["schema"] == REBIN_TELEMETRY_SCHEMA
        for point in points
        for sample in point.samples
    )


def test_density_and_growth_guards_reject_planted_bad_results():
    points = tuple(
        DensityPoint(
            fraction,
            1.0 - index / 10,
            10,
            80,
            1,
            0.01,
            9,
            index,
            0,
        )
        for index, fraction in enumerate(DENSITY_REQUESTED_UNIQUE_FRACTIONS)
    )
    planted = list(points)
    planted[2] = DensityPoint(
        planted[2].requested_unique_fraction,
        planted[2].measured_anchor_density,
        10,
        80,
        1,
        0.01,
        8,
        planted[2].abstained,
        1,
    )
    with pytest.raises(AssertionError, match="wrong-content"):
        assert_density_sweep(tuple(planted))
    with pytest.raises(AssertionError, match="slope"):
        assert_production_growth(
            {
                "end_to_end": {
                    "median_seconds": {
                        "slope": 1.6,
                        "adjacent_ratios": [10.0, 10.0],
                    }
                }
            }
        )
    with pytest.raises(AssertionError, match="not subquadratic"):
        assert_density_timing_growth(
            {"slope": 1.6, "adjacent_ratios": [10.0, 10.0]},
            treatment="planted",
        )


def test_absolute_end_to_end_budget_rejects_either_overrun():
    def captured(seconds: float, lifetime_bytes: int) -> dict[str, object]:
        point = {
            "ledger": {"A": 100_000},
            "phases": {
                "end_to_end": {
                    "median_seconds": seconds,
                    "median_lifetime_peak_bytes": lifetime_bytes,
                }
            },
        }
        return {
            "atom_ladder": list(PRODUCTION_ATOM_LADDER),
            "repetitions": 5,
            "shapes": {
                "wide": {"points": [point]},
                "deep": {"points": [point]},
            },
        }

    assert_absolute_end_to_end_budget(
        captured(ABSOLUTE_END_TO_END_MAX_SECONDS, ABSOLUTE_LIFETIME_RSS_MAX_BYTES)
    )
    with pytest.raises(AssertionError, match="absolute end-to-end"):
        assert_absolute_end_to_end_budget(
            captured(
                ABSOLUTE_END_TO_END_MAX_SECONDS + 0.001,
                ABSOLUTE_LIFETIME_RSS_MAX_BYTES,
            )
        )
    with pytest.raises(AssertionError, match="absolute end-to-end"):
        assert_absolute_end_to_end_budget(
            captured(
                ABSOLUTE_END_TO_END_MAX_SECONDS,
                ABSOLUTE_LIFETIME_RSS_MAX_BYTES + 1,
            )
        )


def test_rss_value_object_rejects_broken_nesting_or_incremental_arithmetic():
    ledger = ProductionScaleRecipe("wide", 10).ledger
    with pytest.raises(ValueError, match="lifetime >= span"):
        RssPhaseSample(
            ledger, "rebind", 1.0, 0.5, 1.5, 99, 99, 100, 80, 20, 0.005, 2
        )
    with pytest.raises(ValueError, match="span minus setup"):
        RssPhaseSample(
            ledger, "rebind", 1.0, 0.5, 1.5, 120, 120, 100, 80, 19, 0.005, 2
        )


def test_conservative_lifetime_rss_reconciles_os_counter_disagreement():
    ledger = ProductionScaleRecipe("wide", 10).ledger
    assert _conservative_lifetime_peak_bytes(99, 100) == 100
    assert _conservative_lifetime_peak_bytes(101, 100) == 101
    sample = RssPhaseSample(
        ledger,
        "rebind",
        1.0,
        0.5,
        1.5,
        99,
        100,
        100,
        80,
        20,
        0.005,
        2,
    )
    assert sample.raw_ru_maxrss_bytes == 99
    assert sample.lifetime_peak_bytes == 100
    with pytest.raises(ValueError, match=r"max\(raw ru_maxrss"):
        RssPhaseSample(
            ledger,
            "rebind",
            1.0,
            0.5,
            1.5,
            99,
            101,
            100,
            80,
            20,
            0.005,
            2,
        )


def test_scale_progress_heartbeat_is_structured_and_context_complete(
    capsys, monkeypatch, tmp_path
):
    progress_log = tmp_path / "progress.log"
    active_state = tmp_path / "active.json"
    monkeypatch.setenv(PROGRESS_LOG_ENV, str(progress_log))
    monkeypatch.setenv(PROGRESS_ACTIVE_STATE_ENV, str(active_state))
    monkeypatch.setenv(PROGRESS_FORMAT_ENV, "json")
    descriptor = ScaleProgressDescriptor("wide", 100_000, "load", 2, 5, 77, 150)
    _emit_scale_progress(
        "heartbeat",
        descriptor,
        child_pid=123,
        state="setup",
        monitor_elapsed_seconds=15.0,
        current_rss_bytes=456,
        span_peak_bytes=0,
    )
    emitted = capsys.readouterr().err.strip()
    assert progress_log.read_text(encoding="utf-8").strip() == emitted
    prefix, encoded = emitted.split(" ", 1)
    assert prefix == "S4.7_SCALE_PROGRESS"
    payload = json.loads(encoded)
    assert json.loads(active_state.read_text(encoding="utf-8")) == payload
    assert {
        "atom_count": 100_000,
        "child_pid": 123,
        "current_rss_bytes": 456,
        "event": "heartbeat",
        "measurement_index": 77,
        "measurement_total": 150,
        "monitor_elapsed_seconds": 15.0,
        "phase": "load",
        "phase_index": 2,
        "phase_total": 5,
        "point_step_index": 7,
        "point_step_total": 25,
        "repetition": 2,
        "repetitions": 5,
        "shape": "wide",
        "span_peak_bytes": 0,
        "state": "setup",
        "status": "IN_PROGRESS",
        "step_coordinate": "2.2",
        "telemetry_schema": PROGRESS_TELEMETRY_SCHEMA,
    }.items() <= payload.items()
    assert payload["event_sequence"] >= 1
    assert payload["run_elapsed_seconds"] >= 0
    assert payload["run_id"]
    assert payload["emitted_at"]
    assert payload["emitter_pid"] > 0


def test_terminal_scale_progress_overwrites_live_state_after_gate_failure(
    capsys, monkeypatch, tmp_path
):
    active_state = tmp_path / "active.json"
    monkeypatch.setenv(PROGRESS_ACTIVE_STATE_ENV, str(active_state))
    monkeypatch.setenv(PROGRESS_FORMAT_ENV, "json")
    finalize_scale_progress(
        status="COMPLETE_GATE_FAILED",
        measurement_total=150,
        failures=("growth/wide: planted",),
    )

    prefix, encoded = capsys.readouterr().err.strip().split(" ", 1)
    assert prefix == "S4.7_SCALE_PROGRESS"
    payload = json.loads(encoded)
    assert json.loads(active_state.read_text(encoding="utf-8")) == payload
    assert payload["event"] == "scale-campaign-finalized"
    assert payload["status"] == "COMPLETE_GATE_FAILED"
    assert payload["measurement_total"] == 150
    assert payload["gate_failures"] == ["growth/wide: planted"]


def test_scale_progress_coordinates_identify_phase_repetition_and_preparation():
    assert ScaleProgressDescriptor(
        "wide", 1_000, "serialize", 1, 5, 1, 150
    ).to_json()["step_coordinate"] == "1.1"
    second_phase_last_repetition = ScaleProgressDescriptor(
        "wide", 1_000, "load", 5, 5, 10, 150
    ).to_json()
    assert second_phase_last_repetition["step_coordinate"] == "2.5"
    assert second_phase_last_repetition["point_step_index"] == 10
    last = ScaleProgressDescriptor(
        "deep", 100_000, "end_to_end", 5, 5, 150, 150
    ).to_json()
    assert last["step_coordinate"] == "5.5"
    assert last["point_step_index"] == last["point_step_total"] == 25
    preparation = ScaleProgressDescriptor(
        "wide", 1_000, "materialize", 0, 5, 0, 150
    ).to_json()
    assert preparation["step_coordinate"] == "prep"
    assert preparation["point_step_index"] == 0


def test_default_human_progress_line_includes_both_run_counters(
    capsys, monkeypatch
):
    monkeypatch.delenv(PROGRESS_FORMAT_ENV, raising=False)
    descriptor = ScaleProgressDescriptor(
        "deep", 100_000, "end_to_end", 5, 5, 150, 150
    )
    _emit_scale_progress("heartbeat", descriptor, state="measured-span")
    human, structured = capsys.readouterr().err.strip().splitlines()
    assert "[150/150]" in human
    assert "step 5.5 (25/25)" in human
    assert structured.startswith("S4.7_SCALE_PROGRESS ")


def test_gate_evaluation_preserves_every_density_growth_failure():
    rows = [
        DensityPoint(
            fraction,
            1.0 - index / 10,
            slots,
            slots * 8,
            1,
            0.01,
            1,
            0,
            0,
        ).to_json()
        for slots in DENSITY_SLOT_LADDER
        for index, fraction in enumerate(DENSITY_REQUESTED_UNIQUE_FRACTIONS)
    ]
    captured = {
        "shapes": {shape: {"growth": {}} for shape in ("wide", "deep")},
        "density_sweep": rows,
        "density_timing_growth": {
            f"{fraction:.2f}": {
                "slope": 1.0,
                "adjacent_ratios": [
                    51.0 if fraction in (0.71, 0.60) else 2.0,
                    2.0,
                ],
            }
            for fraction in DENSITY_REQUESTED_UNIQUE_FRACTIONS
        },
    }
    evaluation = production_profile_gate_evaluation(
        captured, require_absolute=False
    )
    assert any(
        failure.startswith("density/0.71:")
        for failure in evaluation["failures"]
    )
    assert any(
        failure.startswith("density/0.60:")
        for failure in evaluation["failures"]
    )


def test_scale_marker_is_registered_and_default_deselected():
    root = Path(__file__).resolve().parents[2]
    config = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    pytest_config = config["tool"]["pytest"]["ini_options"]
    assert "not scale" in pytest_config["addopts"]
    assert any(marker.startswith("scale:") for marker in pytest_config["markers"])
    workflow = (root / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in workflow and "schedule:" in workflow
    assert "uv run pytest -q --capture=tee-sys -m scale" in workflow
    assert "s4_7_scale*.json" in workflow
    scale_test = (root / "tests/scale/test_s4_7_production_scale.py").read_text(
        encoding="utf-8"
    )
    tool = (root / "tools/s4_7_scale.py").read_text(encoding="utf-8")
    assert "emit_progress=True" in scale_test
    assert "event_callback=record" in scale_test
    assert 'parser.add_argument("--checkpoint", type=Path)' in tool
    assert 'parser.add_argument("--progress-log", type=Path)' in tool
    assert 'parser.add_argument("--active-state", type=Path)' in tool
    assert '"--progress-format"' in tool
    assert "os.environ[PROGRESS_LOG_ENV]" in tool
    assert "os.environ[PROGRESS_ACTIVE_STATE_ENV]" in tool
    assert "os.environ[PROGRESS_FORMAT_ENV]" in tool
    assert "emit_progress=True" in tool
    assert "event_callback=checkpoint.record" in tool


def test_single_cycle_runner_is_source_locked_to_one_pass_over_five_phases():
    root = Path(__file__).resolve().parents[2]
    tool = (root / "tools/s4_7_scale_cycle.py").read_text(encoding="utf-8")
    assert SCALE_CYCLE_SCHEMA == "s4.7-production-scale-cycle@v1"
    assert "src/engine/structure/rebind_telemetry.py" in SCALE_CYCLE_SOURCE_FILES
    assert "tests/harness/scale_production.py" in SCALE_CYCLE_SOURCE_FILES
    assert "tools/s4_7_scale_cycle.py" in SCALE_CYCLE_SOURCE_FILES
    assert "repetitions=1" in tool
    assert "default=OPTIMIZATION_PROGRESS_POLL_INTERVAL_SECONDS" in tool
    assert "progress_poll_interval_seconds" in tool
    assert "measurement_total=len(SCALE_PHASES)" in tool
    assert (
        '"registered_gate_verdict": "NOT_APPLICABLE_SINGLE_REPETITION"'
        in tool
    )
    assert '"end_to_end_is_cold_and_materialization_inclusive": True' in tool
