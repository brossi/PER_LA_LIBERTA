"""S2.1.6 — per-book auto-propose of the column-decision policy (``s2_1_plan.md`` DT-7 amendment,
RULED by Ben 2026-07-06; issue #40).

The column detector's policy (``decision_threshold``, ``hysteresis_margin``) is per-book config,
defaultless in the runtime core (:class:`~engine.structure.segmentation.ColumnDetector` takes both
as required params — the G-1 numberless-core posture). This module is the **proposal** side: given a
book's ``col2_score`` distribution (valley-depth × column-balance over its pages, from
``segmentation.detect_columns``), it detects the empty valley between the single-column cluster
(scores ≈ 0) and the two-column cluster (scores ≈ 1) and proposes a threshold in that valley plus a
margin sized from the valley width.

It is **calibration tooling, not the runtime** (DT-7 amendment governance):

- **Human ratifies, tooling proposes** — the return is a :class:`ColumnPolicyProposal`, never
  written to config. The runtime classifier always reads the frozen, human-ratified value.
- **Abstain when not cleanly bimodal** — a single-column book (no valley), a spurious tiny second
  cluster, or two clusters too close to separate all yield ``bimodal=False`` with a reason, routing
  the whole book to manual calibration rather than emitting a guessed threshold. Calibrate-to-abstain
  applied to calibration itself.

``col2_score`` is a normalized ``[0, 1]`` product, so the clusters are structural (a clean
two-column page ≈ 1.0, a single-column page 0.0 by construction) — which is what makes a
data-driven valley robust. The bin/mass parameters below are algorithm parameters (how a valley is
detected), not a scan-profile opinion: no book's threshold is baked here, it is derived from the
book's own scores.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

#: How finely the ``[0, 1]`` score range is binned to find the valley.
_DEFAULT_N_BINS = 20
#: A cluster must hold at least this fraction of pages to count as a real mode (else the "second
#: cluster" is noise — a handful of transitional pages — and the tooling abstains).
_DEFAULT_MIN_CLUSTER_FRACTION = 0.05
#: The empty valley must span at least this many bins to count as a real separation (two modes one
#: bin apart are not "cleanly bimodal").
_DEFAULT_MIN_VALLEY_BINS = 2


@dataclass(frozen=True, slots=True)
class ColumnPolicyProposal:
    """A proposed (or abstained) column-decision policy for one book.

    On a clean bimodal distribution: ``bimodal=True``, ``decision_threshold`` at the valley centre,
    ``hysteresis_margin`` = half the valley width (so the hysteresis band spans the empty valley),
    ``valley`` = the detected ``(lo, hi)`` empty band. On an abstention: ``bimodal=False`` and both
    values ``None``. ``reason`` always carries the human-readable basis (for the run report), and the
    mass counters expose the two clusters. **A proposal, never applied** — a human ratifies it into
    config.
    """

    bimodal: bool
    reason: str
    n_scores: int
    decision_threshold: float | None = None
    hysteresis_margin: float | None = None
    valley: tuple[float, float] | None = None
    low_cluster_mass: int = 0
    high_cluster_mass: int = 0


def _abstain(reason: str, n: int, **evidence) -> ColumnPolicyProposal:
    return ColumnPolicyProposal(bimodal=False, reason=reason, n_scores=n, **evidence)


def propose_column_policy(
    col2_scores: Sequence[float],
    *,
    n_bins: int = _DEFAULT_N_BINS,
    min_cluster_fraction: float = _DEFAULT_MIN_CLUSTER_FRACTION,
    min_valley_bins: int = _DEFAULT_MIN_VALLEY_BINS,
) -> ColumnPolicyProposal:
    """Propose a column-decision policy from a book's ``col2_score`` distribution, or abstain.

    Method (a #40 build choice, per the DT-7 amendment): histogram the scores, find the widest
    **interior** run of empty bins (the valley) between the lowest and highest populated bins, place
    the threshold at its centre and the margin at half its width. Abstain when there is no interior
    empty valley ≥ ``min_valley_bins`` (unimodal, or clusters too close) or when either side of the
    valley holds fewer than ``min_cluster_fraction`` of the pages (a spurious mode). Pure and
    deterministic.
    """
    scores = list(col2_scores)
    for s in scores:
        if not (isinstance(s, (int, float)) and not isinstance(s, bool) and math.isfinite(s) and 0.0 <= s <= 1.0):
            raise ValueError(f"col2_score must be a finite number in [0, 1], got {s!r}")
    n = len(scores)
    if n == 0:
        return _abstain("no col2_scores to calibrate against — provide the book's distribution", n)
    if not (isinstance(n_bins, int) and n_bins >= 4):
        raise ValueError(f"n_bins must be an integer >= 4, got {n_bins!r}")

    counts = [0] * n_bins
    for s in scores:
        counts[min(n_bins - 1, int(s * n_bins))] += 1
    populated = [i for i, c in enumerate(counts) if c > 0]
    if len(populated) < 2 or populated[0] == populated[-1]:
        return _abstain(
            "the col2_score distribution is unimodal (one populated region) — no valley to place a "
            "threshold in; calibrate columns by hand",
            n,
        )

    lo_bin, hi_bin = populated[0], populated[-1]
    best_start, best_len = None, 0
    run_start, run = None, 0
    for i in range(lo_bin + 1, hi_bin):  # interior bins only — a valley separates the two clusters
        if counts[i] == 0:
            if run == 0:
                run_start = i
            run += 1
            if run > best_len:
                best_len, best_start = run, run_start
        else:
            run = 0
    if best_start is None or best_len < min_valley_bins:
        return _abstain(
            f"no interior empty valley of >= {min_valley_bins} bins between the score clusters — the "
            f"distribution is not cleanly bimodal; calibrate columns by hand",
            n,
        )

    valley_lo = best_start / n_bins
    valley_hi = (best_start + best_len) / n_bins
    low_mass = sum(1 for s in scores if s < valley_lo)
    high_mass = sum(1 for s in scores if s >= valley_hi)
    floor = min_cluster_fraction * n
    if low_mass < floor or high_mass < floor:
        return _abstain(
            f"a score cluster is below the {min_cluster_fraction:.0%} mass floor "
            f"(low={low_mass}, high={high_mass}, of {n}) — the apparent valley is a noise artifact, "
            f"not a real two-column population; calibrate columns by hand",
            n,
            valley=(valley_lo, valley_hi),
            low_cluster_mass=low_mass,
            high_cluster_mass=high_mass,
        )

    threshold = (valley_lo + valley_hi) / 2.0
    margin = (valley_hi - valley_lo) / 2.0
    return ColumnPolicyProposal(
        bimodal=True,
        reason=(
            f"bimodal: {low_mass} single-column pages below {valley_lo:.2f}, {high_mass} two-column "
            f"pages at/above {valley_hi:.2f}, empty valley [{valley_lo:.2f}, {valley_hi:.2f}] — "
            f"proposing threshold {threshold:.3f} (valley centre), margin {margin:.3f} (half width). "
            f"A PROPOSAL: ratify + freeze into manifest.segmentation.column_detector"
        ),
        n_scores=n,
        decision_threshold=threshold,
        hysteresis_margin=margin,
        valley=(valley_lo, valley_hi),
        low_cluster_mass=low_mass,
        high_cluster_mass=high_mass,
    )
