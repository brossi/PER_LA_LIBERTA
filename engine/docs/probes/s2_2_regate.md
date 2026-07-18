# S2.2 — the binding S2.0 RE-GATE (GATE)

**Task** `S2.2` · **Issue** #30 · **Milestone** S2 · **Scope** `GATE` · **Branch** `spike/document-structure`
· **Spec** `ENGINE_STRUCTURE_PLAN.md` §9; tracker `S2.2` (~L527); `docs/probes/s2_0_geometry_alignment.md` §Method/§Verdict
· **Ruling landed 2026-07-08 (Ben — D-A/D-B/D-C, `docs/s2_2_plan.md`).**

## Verdict

**DEMOTE. The S5 geometry mode is `geometry-tie-break`** (not the conditional-`geometry-primary`
S2.0 held pending this re-gate).

The as-built S2.1 detector does **not** clear the pre-registered primary bar over the breadth
sample, so `geometry-primary` is unsupported book-wide; but the geometry is far from noise (mean 0.84,
148/253 pages primary-grade), so `no-geometry` would discard real signal. Tie-break is the band the
number lands in and the honest role: **geometry corroborates and cross-checks; content + the
structural path lead re-binding, with geometry primary only where the matcher is confident on the
two-column body.** This makes S2.0's *conditional*-primary binding on the measured detector.

Consistent with the rest of the design: PLL has column-correct text witnesses (copy1 verified
column-ordered at 0.98), so `order_source = witness` already, and the geometric detector is a QA
cross-check on the witness branch — exactly the role `geometry-tie-break` names (tracker S5.1 row).

## Method — a ruling over persisted numbers, not new machinery

#40 (S2.1.6) already computed the metric the gate rules on and froze its breadth distribution, by
design ("#30 becomes a ruling over persisted numbers", `run_s2_1_slice1.py`). Per matched page the
run wrote `order_qa = ordered_coverage(copy1 witness window, detector reading order at the detected
column split)` onto the sidecar (schema v2), and summarised it in `s2_1_run_stats.json → order_qa`.

The re-gate reads that block and applies the **pre-registered S2.0 thresholds** (ratified
2026-06-29; `s2_0_geometry_alignment.md` §Method) — an **engine policy, not a per-book knob**, so a
book cannot lower its own gate:

- ordered coverage **≥0.85 → `geometry-primary`; 0.50–0.85 → `geometry-tie-break`; <0.50 →
  `no-geometry`**,
- applied on **mean AND per-page pass@0.85** — **never a median** (the median hid a 0.82 mean / ~30%
  fail tail in the S2.0 report; ruling on it is the exact error the mean+pass-rate form prevents),
- over a breadth of **n≥30** matched pages.

The logic is `engine/src/engine/structure/geom_regate.py` (`regate_verdict`), red-first tested in
`tests/unit/test_geom_regate.py` (the median-, OR-, and breadth-guard mutants each red a test).

**Boundary semantics (a deliberate asymmetry).** The primary bar is mean **AND** pass-rate; the
demotion band (tie-break vs no-geometry) is on the **mean alone**. This is intentional: the pass-rate
strengthens only the boundary that risks *over-trust* — a high mean masking a fail tail would let
geometry *lead* re-binding on unreliable pages. The tie-break/no-geometry boundary carries no such
risk (tie-break is already conservative: geometry only corroborates where the matcher is confident,
content leads elsewhere), so a bimodal feed — a few good pages under a low mean — is served correctly
by tie-break, not discarded. Adding a pass-rate floor at 0.50 would also be an *un-pre-registered*
threshold (S2.0 pre-registered a pass-rate bar only for primary); the anti-cheat rule is to rule on
the pre-registered bands, not invent one. For the PLL feed the point is moot — both the mean and the
pass-rate independently land it in tie-break — so the ruling is robust to this choice.

## The numbers (as-built S2.1 detector, PLL, frozen run 2026-07-05)

| quantity | value | bar | verdict |
|---|---|---|---|
| n (matched pages measured) | **253** | ≥30 | ✓ breadth |
| mean order_qa | **0.8417** | ≥0.85 | ✗ below |
| pass@0.85 (per-page pass-rate) | **0.7787** | ≥0.85 | ✗ below |
| median (context only, **not** the bar) | 0.908 | — | — |

Both binding quantities fail the primary bar; the mean **0.8417 ∈ [0.50, 0.85)** → the tie-break
band. Corroborates S2.0's own all-pages measurement (mean 0.851 / 73% pass) on the prototype.

### The drag is a tail, not uniform weakness

The per-page `order_qa` distribution is bimodal:

| band | 0.4 | 0.5 | 0.7 | 0.8 | 0.9 |
|---|---|---|---|---|---|
| pages | 32 | 6 | 5 | 62 | 148 |

**148/253 pages are ≥0.9** (primary-grade); a hard **32-page cluster at ~0.4** pulls the mean and
the pass-rate down. Those are the single-column / chapter-end / TOC / sparse-edge pages where the
column-aware order disagrees with the witness — exactly the "single-column edge pages drag the mean"
pattern S2.0 predicted. The median (0.908) sits inside the upper mode and would **hide** the tail,
which is why the gate rules on mean + pass-rate. Column decisions over the 253: 209 two-column, 41
single-column, 3 matched-but-column-untrusted.

## What landed (D-A/D-B/D-C, ruled by Ben 2026-07-08)

- **D-A (both):** the mode is recorded in **`books/per_la_liberta/manifest.json` →
  `segmentation.geometry_mode = "geometry-tie-break"`** (the book's durable segmentation-policy home,
  parallel to how the DT-7 column policy landed; the manifest is the mode's lineage home until S5's
  rebind config exists) **and** in this probe artifact. Schema: `geometry_mode` added to
  `manifest.schema.json` as an optional enum of the three modes, bound to the module vocabulary by
  `test_geom_regate`.
- **D-B (land it):** the ruling is mechanical from the pre-registered rule + measured numbers, so it
  was landed directly; the S2.0 pre-registration (Ben, 2026-06-29) is the ratifying act.
- **D-C (tie-break):** 0.842 ∈ [0.50, 0.85); `no-geometry` would discard 148 primary-grade pages.

## Reproduce

```python
import json
from engine.structure.geom_regate import regate_verdict
oq = json.load(open("docs/probes/s2_1_run_stats.json"))["order_qa"]
print(regate_verdict(oq))   # -> geometry-tie-break, passed_primary=False, mean 0.8417, pass 0.7787, n 253
```

`tests/unit/test_geom_regate.py::test_the_persisted_run_stats_on_disk_still_rule_tie_break` binds
this to the on-disk artifact, so a re-run that moved the numbers past the bar surfaces there.

## Implications for downstream

- **S5.1 (`rebind_anchors`)** reads `segmentation.geometry_mode` and operates in **`geometry-tie-break`**
  on PLL: geometry corroborates / cross-checks; content fingerprint + structural path lead the
  re-bind; geometry is the primary order source only on the no-witness branch (which PLL is not).
  The mode is recorded in lineage so a re-bind result is interpretable after the fact.
- **The property tier (S2.2 Half A)** is `tests/unit/test_geom_properties.py` (P1 real-page
  in-bounds, P2 real-page order coherence on p219: col-aware 0.956 vs naive 0.502) plus the cited
  binding homes for P3 (canonical primary-witness box) and P4 (absent/ineligible geometry); P4's
  *operational* re-bind exclusion is re-proven at S5.5 when the re-bind exists.
- **A book can lift the mode to primary** only by improving the detector (a better column /
  reading-order model) so the as-built `order_qa` clears mean + pass-rate — not by editing the bar.
