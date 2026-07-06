"""S2.1.6 #40 — per-book auto-propose of the column-decision policy (DT-7 amendment, RULED
2026-07-06).

``propose_column_policy`` reads a book's ``col2_score`` distribution and PROPOSES a
``decision_threshold`` + ``hysteresis_margin`` — a valley-between-two-clusters detection that a human
ratifies and freezes into ``manifest.segmentation.column_detector``. It is **calibration tooling,
not the runtime**: ``ColumnDetector`` still takes the frozen values as required params (G-1
unchanged); this never writes config and never runs at classify time. The governance the DT-7
amendment pins:

- **Human ratifies, tooling proposes** — the return is a *proposal*, never applied.
- **Abstain to manual calibration when not cleanly bimodal** — a single-column book (no valley), a
  spurious tiny cluster, or clusters too close all abstain rather than emit a guessed threshold
  (calibrate-to-abstain, applied to calibration itself).

Red-first: each abstain branch + the valley placement was seen failing before its green. The
distributions here are deterministic fixtures.
"""
from __future__ import annotations

import pytest

from engine.structure.column_calibration import ColumnPolicyProposal, propose_column_policy
from engine.structure.segmentation import ColumnDetector


def _bimodal(low_n=60, high_n=210, low=0.0, high=0.9):
    """A clean two-cluster distribution: ``low_n`` single-column pages near ``low`` and ``high_n``
    two-column pages near ``high``, an empty valley between — the PLL shape."""
    return [low] * low_n + [high] * high_n


# --- bimodal → a proposal in the valley --------------------------------------------------------- #


def test_bimodal_distribution_yields_a_proposal():
    prop = propose_column_policy(_bimodal())
    assert isinstance(prop, ColumnPolicyProposal)
    assert prop.bimodal is True
    assert prop.decision_threshold is not None and prop.hysteresis_margin is not None


def test_proposed_threshold_sits_in_the_empty_valley():
    # low cluster at 0.0, high at 0.9 → the threshold must land strictly between them, in the gap.
    prop = propose_column_policy(_bimodal(low=0.0, high=0.9))
    assert 0.0 < prop.decision_threshold < 0.9
    lo, hi = prop.valley
    assert lo <= prop.decision_threshold <= hi  # inside the detected empty band


def test_proposal_is_a_valid_detector_policy():
    # The whole point: the proposed values construct a real ColumnDetector (in-domain params).
    prop = propose_column_policy(_bimodal())
    detector = ColumnDetector(
        decision_threshold=prop.decision_threshold, hysteresis_margin=prop.hysteresis_margin
    )
    assert detector.params["decision_threshold"] == prop.decision_threshold


def test_pll_like_distribution_is_bimodal_with_a_mid_valley():
    # 59 single-col at 0.0, 211 two-col at 0.9, 8 transition pages scattered in [0.4, 0.8) — the
    # measured PLL shape (docs/probes/s2_1_column_report.md). Bimodal; the valley is the empty
    # [0.05, 0.40) band, so the threshold lands below the transition scatter.
    scores = [0.0] * 59 + [0.9] * 211 + [0.42, 0.55, 0.58, 0.63, 0.71, 0.74, 0.78, 0.79]
    prop = propose_column_policy(scores)
    assert prop.bimodal is True
    assert 0.05 <= prop.decision_threshold <= 0.80
    assert prop.low_cluster_mass == 59 and prop.high_cluster_mass >= 211


# --- abstain branches (calibrate-to-abstain) ---------------------------------------------------- #


def test_unimodal_low_distribution_abstains():
    # A purely single-column book: every page scores ~0, all in one histogram bin. The unimodal
    # early-out fires (one populated region) — distinct from the empty-valley abstain, so the reason
    # names it specifically.
    prop = propose_column_policy([0.0] * 200 + [0.01, 0.02, 0.03])
    assert prop.bimodal is False
    assert prop.decision_threshold is None and prop.hysteresis_margin is None
    assert "unimodal" in prop.reason


def test_unimodal_high_distribution_abstains():
    prop = propose_column_policy([0.95] * 200 + [0.9, 0.92])
    assert prop.bimodal is False and prop.decision_threshold is None


def test_a_spurious_tiny_second_cluster_abstains():
    # 270 pages at 0.0 and only 3 at 0.9: the "second cluster" is below the min mass fraction — a
    # trimodal/noise artifact, not a real two-column population. Abstain, don't propose off 3 pages.
    prop = propose_column_policy([0.0] * 270 + [0.9, 0.9, 0.9])
    assert prop.bimodal is False
    assert "cluster" in prop.reason


def test_clusters_too_close_to_separate_abstains():
    # Two modes one bin apart (0.40 and 0.50) with no real empty valley between → not cleanly
    # bimodal; abstain rather than split a hair.
    prop = propose_column_policy([0.40] * 100 + [0.50] * 100)
    assert prop.bimodal is False


def test_empty_distribution_abstains():
    prop = propose_column_policy([])
    assert prop.bimodal is False and prop.decision_threshold is None


def test_out_of_range_score_is_rejected():
    with pytest.raises(ValueError, match="col2_score"):
        propose_column_policy([0.0, 0.5, 1.5])


def test_proposal_carries_run_report_evidence():
    prop = propose_column_policy(_bimodal(low_n=60, high_n=210))
    assert prop.n_scores == 270
    assert prop.reason  # a human-readable basis, always present (proposal or abstention)
