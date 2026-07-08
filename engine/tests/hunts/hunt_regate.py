"""Mutant table for S2.2 (#30): the geom_regate re-gate ruling + the S2.2 property tier's teeth.

Run with the mutation-hunt runner:

    python3 ~/.claude/skills/mutation-hunt/hunt.py \
        --table tests/hunts/hunt_regate.py --artifact <scratch>/hunt30.json

Covers geom_regate.regate_verdict exhaustively (the primary AND-bar, the mean-not-median rule, the
tie-break/no-geometry band boundaries, the breadth guard, the rate/bool validation, and the pinned
policy constants), plus one property-tier cross-check that P2's real-page order coherence binds
reading_order's column split (the rest of the property tier binds functions covered by other hunt
tables — P1's off-page control and P4's matched positive-control are in-test, not production mutants).
TEST_CMD uses the engine venv python; the runner pins pyc hygiene.
"""
from pathlib import Path

REPO = str(Path(__file__).resolve().parents[2])
TEST_CMD = [str(Path(REPO) / ".venv" / "bin" / "python"), "-m", "pytest", "{scope}",
            "-q", "--no-header", "-x", "-p", "no:cacheprovider"]
TIMEOUT = 300

G = "src/engine/structure/geom_regate.py"
SEG = "src/engine/structure/segmentation.py"
TG = "tests/unit/test_geom_regate.py"
TP = "tests/unit/test_geom_properties.py"


def m(label, old, new, test_id, *, file=G, test_file=TG):
    return {"label": label, "file": file, "old": old, "new": new, "scope": f"{test_file}::{test_id}"}


MUTANTS = [
    # --- the primary bar: mean AND pass@0.85, both inclusive ------------------------------------
    m("primary-bar-and-to-or",
      "    passed_primary = mean >= PRIMARY_BAR and pass_at >= PRIMARY_BAR",
      "    passed_primary = mean >= PRIMARY_BAR or pass_at >= PRIMARY_BAR",
      "test_mean_clears_but_pass_rate_fails_demotes_the_and_control"),
    m("primary-bar-mean-comparator-strict",
      "    passed_primary = mean >= PRIMARY_BAR and pass_at >= PRIMARY_BAR",
      "    passed_primary = mean > PRIMARY_BAR and pass_at >= PRIMARY_BAR",
      "test_demotion_bands_are_value_pinned_at_the_boundaries"),
    m("primary-bar-pass-comparator-strict",
      "    passed_primary = mean >= PRIMARY_BAR and pass_at >= PRIMARY_BAR",
      "    passed_primary = mean >= PRIMARY_BAR and pass_at > PRIMARY_BAR",
      "test_pass_rate_exactly_at_the_bar_still_confirms_primary"),
    m("primary-bar-value-drift",
      "PRIMARY_BAR = 0.85",
      "PRIMARY_BAR = 0.80",
      "test_below_bar_pass_rate_never_reaches_primary_even_at_high_mean"),
    # --- the mean, not a median ----------------------------------------------------------------
    m("rule-on-median-not-mean",
      '    mean = order_qa.get("mean")',
      '    mean = order_qa.get("median", order_qa.get("mean"))',
      "test_pass_rate_clears_but_mean_fails_demotes_the_median_control"),
    # --- the tie-break / no-geometry band boundary ---------------------------------------------
    m("tie-break-floor-comparator-strict",
      "    elif mean >= TIE_BREAK_FLOOR:",
      "    elif mean > TIE_BREAK_FLOOR:",
      "test_demotion_bands_are_value_pinned_at_the_boundaries"),
    m("tie-break-floor-value-drift",
      "TIE_BREAK_FLOOR = 0.50",
      "TIE_BREAK_FLOOR = 0.0",
      "test_demotion_bands_are_value_pinned_at_the_boundaries"),
    # --- the breadth guard ---------------------------------------------------------------------
    m("breadth-guard-dropped",
      "    if not isinstance(n, int) or n < MIN_BREADTH:",
      "    if not isinstance(n, int):",
      "test_insufficient_breadth_fails_loud"),
    m("min-breadth-value-drift",
      "MIN_BREADTH = 30",
      "MIN_BREADTH = 3",
      "test_insufficient_breadth_fails_loud"),
    # --- the rate/bool validation --------------------------------------------------------------
    m("rate-validation-dropped",
      "    if not _is_rate(mean) or not _is_rate(pass_at):",
      "    if False:",
      "test_malformed_statistic_fails_loud"),
    m("is-rate-allows-bool",
      "    return isinstance(v, (int, float)) and not isinstance(v, bool) and 0.0 <= v <= 1.0",
      "    return isinstance(v, (int, float)) and 0.0 <= v <= 1.0",
      "test_malformed_statistic_fails_loud"),
    m("is-rate-drops-upper-bound",
      "    return isinstance(v, (int, float)) and not isinstance(v, bool) and 0.0 <= v <= 1.0",
      "    return isinstance(v, (int, float)) and not isinstance(v, bool) and 0.0 <= v",
      "test_malformed_statistic_fails_loud"),
    m("is-rate-drops-lower-bound",
      "    return isinstance(v, (int, float)) and not isinstance(v, bool) and 0.0 <= v <= 1.0",
      "    return isinstance(v, (int, float)) and not isinstance(v, bool) and v <= 1.0",
      "test_malformed_statistic_fails_loud"),
    # --- the ruled mode strings ----------------------------------------------------------------
    m("tie-break-mode-mislabeled-primary",
      "        mode = MODE_TIE_BREAK",
      "        mode = MODE_PRIMARY",
      "test_as_built_pll_feed_demotes_to_tie_break"),
    # --- P2 property tier: real-page order coherence binds the column split --------------------
    m("reading-order-ignores-split",
      "        left = sorted((box for box in boxes if _box_x_center(box) < split_x), key=_key)",
      "        left = sorted((box for box in boxes if _box_x_center(box) < 0.0), key=_key)",
      "test_p2_naive_full_width_order_is_strictly_worse",
      file=SEG, test_file=TP),
]
