"""S2.2 (#30) — the binding S2.0 RE-GATE: rule the S5 geometry mode from the as-built order_qa feed.

S2.0 (`docs/probes/s2_0_geometry_alignment.md`) selected the S5 geometry mode **conditionally**:
geometry is primary-grade on confident two-column body pages, but the overall per-page pass-rate did
not clear the bar, so the mode was **conditional-primary, to be re-gated once S2.1 built the real
detector**. That re-gate is this module. It is deliberately thin: #40 already computed the metric the
gate rules on — per matched page, `ordered_coverage(witness window, detector reading order)` — and
froze its breadth distribution (mean + per-page pass@0.85) in the run stats. So #30 is a **ruling
over persisted numbers, not new machinery**: read the `order_qa` breadth feed, apply the
**pre-registered** thresholds, and confirm `geometry-primary` or demote.

The three S5 operating modes (tracker S5.1 row): `geometry-primary` (the geometric detector leads
re-binding / reading order), `geometry-tie-break` (geometry corroborates, but content + structural
path lead), `no-geometry` (geometry is noise, discarded). The mode this returns is recorded in the
book's segmentation policy (its lineage home until S5's rebind config exists) and consumed by S5.1.

**The pre-registered thresholds (S2.0 §Method; audit Finding A) — an ENGINE policy, not a per-book
knob.** A book must not be able to lower its own gate (that is the anti-cheat reason these live in
code, not the manifest): ordered coverage **≥0.85 → primary; 0.50–0.85 → tie-break; <0.50 →
no-geometry**, applied on **mean AND per-page pass@0.85** — never a page *median* (the median hid a
0.82 mean / ~30% fail tail in the S2.0 report; ruling on it is the exact error the mean+pass-rate
form exists to prevent). A breadth of **n≥30** matched pages is required to rule at all.

Engine-neutral: this module carries no book, language, or typeface literal — only the geometry-mode
policy constants. The S0.2 neutrality scan globs `structure/`; the load-bearing proof is behavioural
(the re-gate rules on numbers passed in, never on a baked book identity).

Invariants (proven red below — `tests/unit/test_geom_regate.py`):
1. The as-built PLL feed (mean 0.842 / pass@0.85 0.779, n=253) rules **DEMOTE → geometry-tie-break**
   (regression sentinel on the real frozen numbers).
2. Primary is confirmed **iff mean ≥0.85 AND pass@0.85 ≥0.85** — an OR mutant reds on a feed meeting
   only one bar; a median mutant reds on a feed whose median clears the bar but whose mean does not.
3. On demotion the mode bands on the mean: **[0.50, 0.85) → tie-break; <0.50 → no-geometry**, value-
   pinned at both boundaries (0.50, 0.85) inclusive-low.
4. Fail-loud: n<30 (insufficient breadth to rule) and a missing/None mean or pass-rate raise, never a
   silent default verdict.

Built at S2.2 (#30).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

#: The three S5 geometry operating modes (tracker S5.1 row).
MODE_PRIMARY = "geometry-primary"
MODE_TIE_BREAK = "geometry-tie-break"
MODE_NO_GEOMETRY = "no-geometry"

#: Pre-registered S2.0 thresholds (ratified 2026-06-29; `s2_0_geometry_alignment.md` §Method).
#: The bar mean AND pass-rate must both clear to *confirm* geometry-primary.
PRIMARY_BAR = 0.85
#: The per-page order_qa pass threshold behind pass@0.85.
PASS_THRESHOLD = 0.85
#: Below this mean, geometry is no-geometry; [floor, bar) is the tie-break band.
TIE_BREAK_FLOOR = 0.50
#: Minimum breadth (matched pages measured) to rule at all (S2.0 §Method, done-when n≥30).
MIN_BREADTH = 30


@dataclass(frozen=True, slots=True)
class RegateVerdict:
    """The re-gate outcome over one order_qa breadth feed.

    ``mode`` is the ruled S5 geometry mode; ``passed_primary`` is whether the primary bar was
    confirmed (both quantities ≥ the bar). ``mean``/``pass_at``/``n`` are the numbers ruled on, so
    the verdict is self-describing.
    """

    mode: str
    passed_primary: bool
    mean: float
    pass_at: float
    n: int


def regate_verdict(order_qa: Mapping[str, object]) -> RegateVerdict:
    """Rule the S5 geometry mode from an ``order_qa`` breadth feed (the run-stats block, or any
    mapping with ``n_pages`` / ``mean`` / ``pass_at_0_85``).

    Fail-loud on an unrulable feed — insufficient breadth or a missing summary statistic — never a
    silent default: a gate that quietly passes on absent evidence is worse than a dropped italic.
    """
    n = order_qa.get("n_pages")
    mean = order_qa.get("mean")
    pass_at = order_qa.get("pass_at_0_85")
    if not isinstance(n, int) or n < MIN_BREADTH:
        raise ValueError(
            f"re-gate needs n≥{MIN_BREADTH} matched pages to rule; got n_pages={n!r} "
            "(regenerate the order_qa feed over the breadth sample)"
        )
    if not _is_rate(mean) or not _is_rate(pass_at):
        raise ValueError(
            "re-gate needs both a mean and a pass@0.85 rate in [0, 1]; got "
            f"mean={mean!r}, pass_at_0_85={pass_at!r} (a malformed order_qa feed)"
        )
    passed_primary = mean >= PRIMARY_BAR and pass_at >= PRIMARY_BAR
    if passed_primary:
        mode = MODE_PRIMARY
    elif mean >= TIE_BREAK_FLOOR:
        # The demotion band is on the mean alone — deliberately, not pass-rate too. The pass-rate
        # strengthens the PRIMARY bar because that boundary risks *over-trust* (a high mean masking a
        # fail tail would let geometry LEAD re-binding on unreliable pages). The tie-break/no-geometry
        # boundary carries no such risk: tie-break is already conservative (geometry only corroborates
        # where the matcher is confident, content leads elsewhere), so a bimodal feed — a few good
        # pages under a low mean — is served correctly by tie-break, not discarded. Adding a pass-rate
        # floor here would also be an *un-pre-registered* threshold (S2.0 pre-registered a pass-rate
        # bar only for primary); the anti-cheat rule is to rule on the pre-registered bands, not invent.
        mode = MODE_TIE_BREAK
    else:
        mode = MODE_NO_GEOMETRY
    return RegateVerdict(mode=mode, passed_primary=passed_primary, mean=mean, pass_at=pass_at, n=n)


def _is_rate(v: object) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and 0.0 <= v <= 1.0
