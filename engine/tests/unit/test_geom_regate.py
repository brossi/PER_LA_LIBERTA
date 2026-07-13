"""S2.2 (#30) — the binding S2.0 RE-GATE greens (red-first; `geom_regate` module docstring).

The re-gate rules the S5 geometry mode over the as-built order_qa breadth feed. Each invariant names
the mutant that reds it (the mechanical red-proof is `tests/hunts/hunt_regate.py`):

1. as-built PLL feed → DEMOTE→tie-break (regression sentinel on the frozen numbers)
2. primary iff mean≥0.85 AND pass@0.85≥0.85 (OR-mutant + median-mutant controls)
3. demotion bands on the mean, value-pinned at 0.50 and 0.85
4. fail-loud on n<30 and on a missing/None statistic
"""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from engine.structure.geom_regate import (
    MODE_NO_GEOMETRY,
    MODE_PRIMARY,
    MODE_TIE_BREAK,
    RegateVerdict,
    regate_verdict,
)

# The frozen as-built feed the run persisted (docs/probes/s2_1_run_stats.json → order_qa).
AS_BUILT = {"n_pages": 253, "mean": 0.8417281984174582, "pass_at_0_85": 0.7786561264822134}


def test_as_built_pll_feed_demotes_to_tie_break():
    # Invariant 1 — the binding ruling. Both bars fail (mean 0.842 < 0.85, pass 0.779 < 0.85), and
    # the mean lands in [0.50, 0.85) → tie-break. RED (mutant): rule on median, or flip AND→OR, or
    # widen the bar — any of them would confirm primary on this feed.
    v = regate_verdict(AS_BUILT)
    assert v.mode == MODE_TIE_BREAK
    assert v.passed_primary is False
    assert (v.mean, v.pass_at, v.n) == (AS_BUILT["mean"], AS_BUILT["pass_at_0_85"], 253)


def test_the_persisted_run_stats_on_disk_still_rule_tie_break():
    # The ruling is over the ACTUAL frozen artifact, not just an inlined copy — so a re-run that
    # moved the numbers past the bar would surface here, not hide behind a stale literal.
    stats = json.loads(
        (Path(__file__).resolve().parents[2] / "docs/probes/s2_1_run_stats.json").read_text()
    )
    v = regate_verdict(stats["order_qa"])
    assert v.mode == MODE_TIE_BREAK and v.passed_primary is False
    assert v.mean < 0.85 and v.pass_at < 0.85 and v.n >= 30


def test_primary_confirmed_only_when_both_bars_clear():
    # Invariant 2 (positive) — both ≥ bar confirms primary.
    v = regate_verdict({"n_pages": 40, "mean": 0.90, "pass_at_0_85": 0.90})
    assert v.mode == MODE_PRIMARY and v.passed_primary is True


def test_mean_clears_but_pass_rate_fails_demotes_the_and_control():
    # Invariant 2 — the AND, not OR: a high mean with a failing pass-rate must NOT confirm primary.
    # RED (mutant): AND→OR confirms primary here (mean 0.90 alone).
    v = regate_verdict({"n_pages": 40, "mean": 0.90, "pass_at_0_85": 0.80})
    assert v.passed_primary is False and v.mode == MODE_TIE_BREAK


def test_pass_rate_clears_but_mean_fails_demotes_the_median_control():
    # Invariant 2 — the mean, not a median: a feed whose pass-rate clears but whose MEAN is under the
    # bar must demote. A median clause (median present but ignored) would wrongly confirm; the mean
    # is what binds. RED (mutant): rule on `median` — this feed's median (added, high) would pass.
    v = regate_verdict({"n_pages": 40, "mean": 0.84, "median": 0.99, "pass_at_0_85": 0.90})
    assert v.passed_primary is False and v.mode == MODE_TIE_BREAK


@pytest.mark.parametrize(
    "mean,expected",
    [
        (0.85, MODE_PRIMARY),        # exactly the bar → primary (>=), paired with a passing rate
        (0.8499, MODE_TIE_BREAK),    # just under → demote
        (0.50, MODE_TIE_BREAK),      # exactly the floor → tie-break (>=)
        (0.4999, MODE_NO_GEOMETRY),  # just under the floor → no-geometry (a 0.0 row added no kill, #56)
    ],
)
def test_demotion_bands_are_value_pinned_at_the_boundaries(mean, expected):
    # Invariant 3 — the band boundaries 0.85 and 0.50 are inclusive-low. Pass-rate is held at 0.90
    # so the mean is the only thing moving; for the 0.85 case that makes primary reachable.
    v = regate_verdict({"n_pages": 40, "mean": mean, "pass_at_0_85": 0.90})
    assert v.mode == expected


def test_pass_rate_exactly_at_the_bar_still_confirms_primary():
    # Pins the pass comparator as inclusive (>=): mean and pass both exactly at 0.85 → primary.
    # RED (mutant): pass_at > PRIMARY_BAR would demote this.
    v = regate_verdict({"n_pages": 40, "mean": 0.90, "pass_at_0_85": 0.85})
    assert v.mode == MODE_PRIMARY and v.passed_primary is True


def test_below_bar_pass_rate_never_reaches_primary_even_at_high_mean():
    # Guards the 0.85 boundary case above from a false read: primary needs BOTH, so a 0.85 mean with
    # a sub-bar pass-rate is still a demotion.
    v = regate_verdict({"n_pages": 40, "mean": 0.85, "pass_at_0_85": 0.84})
    assert v.mode == MODE_TIE_BREAK and v.passed_primary is False


def test_insufficient_breadth_fails_loud():
    # Invariant 4 — n<30 cannot rule. RED (mutant): drop the breadth guard → a 3-page fluke rules.
    with pytest.raises(ValueError, match="n≥30"):
        regate_verdict({"n_pages": 29, "mean": 0.99, "pass_at_0_85": 0.99})


@pytest.mark.parametrize(
    "feed",
    [
        {"n_pages": 40, "mean": None, "pass_at_0_85": 0.9},
        {"n_pages": 40, "mean": 0.9, "pass_at_0_85": None},
        {"n_pages": 40, "pass_at_0_85": 0.9},           # mean absent
        {"n_pages": 40, "mean": 1.5, "pass_at_0_85": 0.9},    # over the upper bound
        {"n_pages": 40, "mean": -0.2, "pass_at_0_85": 0.9},   # under the lower bound
        {"n_pages": 40, "mean": 0.9, "pass_at_0_85": -0.01},  # a negative pass-rate
        {"n_pages": 40, "mean": 0.9, "pass_at_0_85": True},   # bool is not a rate
    ],
)
def test_malformed_statistic_fails_loud(feed):
    # Invariant 4 — a missing/None/out-of-range statistic raises, never a silent default verdict.
    with pytest.raises(ValueError, match="mean and a pass@0.85"):
        regate_verdict(feed)


def test_missing_n_pages_fails_loud_as_breadth():
    with pytest.raises(ValueError, match="n≥30"):
        regate_verdict({"mean": 0.9, "pass_at_0_85": 0.9})


def test_verdict_is_frozen():
    # FrozenInstanceError specifically, not bare Exception — any incidental raise passed the old
    # form (#55). RED (mutant): frozen=True removed -> assignment succeeds, nothing raises.
    v = regate_verdict(AS_BUILT)
    assert isinstance(v, RegateVerdict)
    with pytest.raises(FrozenInstanceError):
        v.mode = MODE_PRIMARY  # type: ignore[misc]


def test_manifest_schema_geometry_mode_enum_is_bound_to_the_module_modes():
    # The schema enum (static JSON) and the module MODE_* vocabulary must not drift: a mode added to
    # one but not the other would let an unrulable value land in a manifest, or reject a real one.
    root = Path(__file__).resolve().parents[2]
    schema = json.loads((root / "src/engine/config/schema/manifest.schema.json").read_text())
    enum = schema["properties"]["segmentation"]["properties"]["geometry_mode"]["enum"]
    assert set(enum) == {MODE_PRIMARY, MODE_TIE_BREAK, MODE_NO_GEOMETRY}


def test_pll_manifest_carries_the_ruled_tie_break_mode():
    # The re-gate ruling actually landed in the book's segmentation policy (D-A/D-B), and it is the
    # mode this feed rules — so a manifest hand-edit away from the evidence would surface here.
    root = Path(__file__).resolve().parents[2]
    manifest = json.loads((root / "books/per_la_liberta/manifest.json").read_text())
    assert manifest["segmentation"]["geometry_mode"] == MODE_TIE_BREAK == regate_verdict(AS_BUILT).mode
