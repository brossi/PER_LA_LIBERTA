# S2.1.5 column / reading-order detector — run report (DT-7 checkpoint)

Issue #39 (S2.1.5). Reproduce with
`cd engine && uv run python books/per_la_liberta/probes/s2_1_column_probe.py`
(needs the local `_boxes_dpi300.json` box cache + the LOC PDF for the density gate).

**Status: RATIFIED by Ben 2026-07-06** (`decision_threshold = 0.50`, `hysteresis_margin = 0.15`) —
DT-7's "proposed in-code, ratified by the run report distribution," the same governance as the DT-8
thresholds at the slice-1 report. The ratified values now live in `manifest.json`
`segmentation.column_detector`; the loader builds the `ColumnDetector` from them via `from_config`.

The values below are **hand-read** from the distribution. Per Ben's 2026-07-06 ruling (DT-7
amendment), **#40's run-report tooling will auto-*propose* them per book** from this same
`col2_score` distribution — antimode / largest-empty-band detection places the threshold in the
valley and sizes the margin from the valley width, **abstaining to manual calibration when a book
isn't cleanly bimodal**. It stays a *proposal* a human ratifies, frozen into config (never live
re-derived — the DT-9/G-22 fingerprint constraint). The threshold is near book-invariant (the
`col2_score` clusters are structural: clean two-column ≈1.0, single-column 0.0 by construction); the
hysteresis margin is the genuinely per-book knob.

## col2_score distribution (valley-depth × column-balance) — all 278 pages

```
  [0.00,0.05)    59  single-column / sparse (front & back matter, dividers, chapter opens)
  [0.05,0.40)     0  ← empty valley
  [0.40,0.50)     1
  [0.50,0.60)     3
  [0.60,0.70)     2   transition band (partial columns, footnote splits)
  [0.70,0.80)     2
  [0.80,1.00)   211  clean two-column body
  min / median / max = 0.000 / 0.908 / 1.000
```

The score is **sharply bimodal**: a single-column cluster at 0.0 and a two-column cluster ≥ 0.80,
separated by a completely empty band [0.05, 0.40). Only 8 pages fall in the whole [0.40, 0.80)
transition zone.

## Ratified policy (Ben, 2026-07-06)

- **`decision_threshold = 0.50`** — sits in the empty valley between the two clusters, so no clean
  page is near it. Two-column detection rate at 0.50: **218/278** (78%), consistent with the S2.0
  prior (30/37 = 81% two-col on the body-weighted sweep; the book is majority two-column body with
  single-column front/back matter).
- **`hysteresis_margin = 0.15`** — the band `|score − 0.50| < 0.15` = [0.35, 0.65] captures exactly
  the **5** transition pages `[47, 195, 227, 271, 274]`, the pages whose own evidence is genuinely
  weak and that the cross-page prior (or, failing agreement, the human worklist) should arbitrate —
  not the detector guess. Widening to 0.20 would pull in the 0.70–0.80 pages (confidently two-col);
  narrowing to 0.10 would drop pages 195/227 that sit near 0.55–0.60.

## Full front-end (density gate #38 → cross-page prior R8)

Density bands (#38, ratified) gate box trust; the detector + prior then run over the book:

```
  evidence 2-col : 213
  evidence 1-col :  45
  prior-inherited:   3   (in-margin pages an agreeing content neighbor resolved)
  routed / abstain:   0
  boxes-untrusted :  17   (near_blank / non_text_dark / cover pages — no column verdict)
```

The prior decided only 3 pages (all others stood on their own confident evidence), and no page
abstained — consistent with the bimodality: PLL's layout is locally constant and rarely ambiguous.
The witness branch (PLL = `order_source: witness`) means this detector output is a **QA
cross-check**, not the reading-order source; the book-wide `order_qa` feed that quantifies it
against the copy1 witness is #40 (S2.1.6), per the plan.
