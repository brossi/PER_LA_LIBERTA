# S2.1 slice-1 run report — PLL copy1 geometry (issue #37)

**Status: GREEN.** First full pass of the witness↔geometry pipeline on real data
(2026-07-05): OCR → blind calibration (two-clause P-1 gate) → copy1 page-locate + token-bow-v1
match → P-5 tripwire → `copy1_geom.json` published. Numbers below are from
`s2_1_run_stats.json` (`status: "ok"`), the committed evidence behind this report; the sidecar
itself is a regenerable workspace artifact
(`books/per_la_liberta/work/data/geometry/copy1_geom.json`, gitignored per DT-11's local-only
split).

- Engine: `pymupdf-1.27.2.3+tesseract-5.5.2:dpi=300:lang=ita`; scan = the 278-page LOC PDF.
- Wall: OCR 13.5 min cold (checkpointed cache; later phases re-run from it in ~3 min),
  calibration 89 s, copy1 match 88.6 s.
- Thresholds: `page_accept_rate=0.80`, `atom_match_floor=0.60` — both since ratified (the floor
  as a constant, the cut as a standing per-run procedure; see §Ratifications).

## Calibration (P-1, two-clause — SUPERSEDED form ruled 2026-07-05)

Blind page-locate on copy3 vs its ground-truth page map, under the P-2-superseded 16× band:

| Clause | Population | Measured | Floor | Verdict |
|---|---|---|---|---|
| A (exact) | single-page-truth atoms, > 5 tokens | 327/328 = **99.70%** | ≥ 95% | pass |
| B (within ±1) | ALL single-page-truth atoms | 521/521 = **100%** | ≥ 98% | pass |

Delta histogram `{-1: 2, 0: 421, +1: 98}` — nothing anywhere is off by two or more pages.
Reported, not gated: the ≤5-token slice (94/193 exact — headings/dates/dividers whose bags
cannot discriminate adjacent pages; always within ±1). Excluded-and-counted: 0 unmapped, 0
multi-page-truth, 0 out-of-range. The gate's floors and cutoff are CLI-tunable
(`--calibration-exact-floor` / `--calibration-window-floor` / `--small-max-tokens`), ruled
values as defaults. History: the first run blocked at 53.6% under the 3× band — that finding,
its mechanism, and the P-2 supersession live in `s2_1_band_drift.md`.

## Page results (278 scan pages)

**253 matched, 25 routed.** Match-rate histogram (token-mass-weighted, decade bins): 183 pages
in 0.9+, 70 in 0.8, 10 in 0.7, 12 lower.

The routed 25 decompose cleanly:

- **7 `locate/empty-window`** — pages 1, 4, 272, 273, 274, 277, 278: covers, the scan-target
  page, and back matter. copy1's stream has no text for them; an empty window is the honest
  outcome. (This `stage="locate"/signal="empty-window"` wire pair is an S2.1.3 extension beyond
  DT-10's original enum — ratification below.)
- **6 noise-adjacent** — pages 2, 3 (front matter, rates 0.17/0.09) and 269, 270, 275, 276
  (back matter, 0.00–0.50).
- **12 interior review pages** — 6, 75, 117, 125, 139, 168, 192, 206, 220, 231, 253, 265;
  rates 0.33–0.7996 (the "0.80" prints are display rounding of values just under the `>=` 0.80
  accept). These are the DT-10 human-review worklist: real text pages where the IA-Tesseract
  witness text and the #36 OCR bags disagree beyond threshold.

## Atom results (copy1: 3,411 records on matched pages; 210 pending on routed pages)

| Outcome | Atoms | Interpretation |
|---|---|---|
| matched | 2,401 | `Geom.matched` with provenance + union bbox |
| zero_match | 847 | ~all OCR-debris atoms (see below) |
| ambiguous (P-4 floor) | 113 | matched < 3 tokens, no page-unique token |
| below_atom_floor | 50 | matched fraction < 0.60 |

The headline 70% match rate is an *atom-count* view; the **token-mass** view is the honest one:
atoms with > 10 tokens (the prose) are 2,089/2,097 matched — **99.8% by mass** (233 absent of
118,589). The 847 zero-match atoms are dominated by copy1's own OCR debris — running-header /
page-number garble rows (`'3E'`, `'Z3S'`, `'•6-68-8-'`); 641 of 847 are single-token, 43
tokenless — witness-stream junk that *should* carry no geometry. 6,878 boxes (~5%) are
hyphenation fragments (`perso-`), part of why page rates plateau near 0.9 rather than 1.0.

Coverage counters: `canonical_no_primary_derivation` = **1,165** (copy2-only canonical atoms —
exactly DT-13's 2026-07-03 measurement, 24.3% of the canonical stream; ruling below);
`canonical_multi_primary_derivation` = **0** (the G-20 class is absent in the real data);
`pages_locate_failed` = 7; `atoms_unmatched_on_accepted_pages` = 1,010. Straddler windows: 53.

## Tripwire (P-5) and the P-7 amendment on real data

- Leg A (auto-absent token mass on accepted pages): **1.36%** vs 2% hard bound — quiet.
- Leg B (≥4-token atoms absent): **0.96%** vs 5% — quiet.
- One warn-tier flag: the ≤3-token band's absent mass is 1.11% (> 1% warn), which is the debris
  class above — structurally absent geometry for junk atoms, not lost prose.
- P-7 bounded drop-and-count: exactly the probe-predicted 20 off-page boxes dropped and counted
  (pages 4:4, 5:2, 273:1, 274:10, 276:3); no page approached the 20% systemic bound.

## Ratifications (all ruled by Ben 2026-07-05, at this run report — #37's DoD gate)

1. **DT-8 thresholds.** `atom_match_floor = 0.60` ratified as a **constant** (only 50 atoms
   below it; it guards individual atoms, not budgets). `page_accept_rate` ratified as a
   **standing procedure**: the cut is a per-run review-budget decision, named by a human from
   the run's own deterministic `threshold_sweep` (fixed ladder + advisory gap candidates +
   decision-zone page list — persisted in `s2_1_run_stats.json`, printed at run end). Gap
   detection is advisory only; the applied cut lands in `run_params`, its rationale here.
   **Run 1's cut: 0.80** — the pre-registered proposal, left standing after review of the
   12-page worklist (scans + per-page diagnostics). The decision that mattered at this cut:
   the three near-bar pages (p192/p253/p265, 0.7975–0.7988) stay in review rather than being
   accepted on closeness; their verdicts become retuning evidence at the next book.
2. **Wire extension `stage="locate"/signal="empty-window"` — RATIFIED.** Observed on exactly
   the 7 physically text-empty pages; recorded at DT-10's enum in the plan.
3. **DT-13 — outcome (b) RATIFIED.** The 24.3% copy2-only absent-geometry floor (1,165 atoms,
   reproduced exactly by this run) is a named, accepted loss; the copy2 lane stays a later
   deliverable. Revisit trigger: the first consumer needing geometry on a copy2-only atom.
4. **P-1 "tighten to 97%?" note — RESOLVED: keep 95%.** Clause A measures 99.70%, so 97% would
   pass today, but floor-setting on one book is anchoring, not calibration; revisit at N=2.

### The worklist as reviewed

The threshold decision was made against the actual pages (worklist artifact, 2026-07-05): of
the 12 interior routed pages, two are structurally empty leaves mis-dressed as text (p6 = the
title page's verso, whose 658 boxes are Tesseract reading *bleed-through* and library pencil
marks — its 0.75 "rate" spans a 4-token window; p125 = the «PARTE SECONDA» divider, 2 boxes),
two are genuine prose below 0.75 (p117 at 0.733, p139 at 0.683 — the blotchiest impression in
the book; deficits spread across short function words), and eight form the 0.755–0.799 shelf
(distributed short-word disagreement plus identifiable causes: a proper name rendered two ways,
hyphen fragments, apostrophe-word divergence). p6 is also the cautionary case for low cuts: at
0.75 its meaningless 4-token rate would have been *accepted* and the ghost-text leaf stamped a
matched page.

## S2.1.6 (#40) — segmentation front-end feed: order_qa + worklist + auto-propose

The slice-1 runner now also runs the S2.1 segmentation front-end book-wide (density gate #38 →
column detector + cross-page prior #39) and emits three #40 artifacts. All from the same run
(`s2_1_run_stats.json` sections `order_qa`, `worklist`, `column_policy_auto_propose`).

### order_qa — the S2.2 (#30) measurement feed (DT-12)

Per matched page, `ordered_coverage(witness window, detector reading order)` — the exact metric
the S2.2 re-gate rules on — is written onto the sidecar page record (schema v2:
`n_cols`/`n_cols_source`/`order_qa`) and summarised here:

- 253 matched pages measured; **mean 0.842**, median 0.878, **pass@0.85 = 0.779**.
- Column decisions: 209 pages two-column, 41 single-column, 3 matched-but-column-untrusted;
  `n_cols_source` = {evidence: 248, prior: 2} — the cross-page prior decided 2 pages, matching
  the #39 column report's "prior decides rarely."

**This is below the S2.2 re-gate bar** (mean ≥ 0.85 **and** per-page pass-rate ≥ 85%), consistent
with S2.0's measured 0.851 mean / 73% pass over all pages and its **conditional**-primary verdict.
#40's mandate is to *emit* this feed; the S5-mode ruling is #30's (S2.2), now armed with the
as-built per-page numbers. Nothing here demotes geometry — it hands #30 the evidence to.

> **Resolved at S2.2 (#30, 2026-07-08):** the re-gate read this feed and ruled **DEMOTE →
> `geometry-tie-break`** (both bars fail; mean 0.842 ∈ [0.50, 0.85)). Landed in
> `manifest.segmentation.geometry_mode`; ruling + tail analysis in `docs/probes/s2_2_regate.md`.

### Worklist (DT-10) + volume bound (P-6/G-13)

25 candidates, `{locate: 7, match: 18}` — **zero density or columns routes** (every content page
was confidently classified; the density gate abstained on none). Per-stage fractions: locate
7/278 = 2.5%, match 18/278 = 6.5%, both well under the ratified `review_fraction_max = 0.15`
(now in `manifest.segmentation`, book-tunable). One candidate per routed page, stable id
`copy1:p{page:04d}:{stage}`, each carrying the run `input_fingerprint`; the tracked verdict file
+ inputs regenerate the worklist deterministically. Verdict CLI:
`python -m engine.structure.geom_review --book per_la_liberta {status|apply|record}`.

### DT-7 auto-propose (a proposal, not a ruling)

From this book's own `col2_score` distribution the tooling proposes
**`decision_threshold = 0.400`, `hysteresis_margin = 0.350`**. The **ratified/frozen** manifest
value is `0.50 / 0.15`; the two now diverge on only **2 of 278 pages**, and the weak transition
pages (0.46–0.70) defer under both.

The anchor is the **dense-cluster edges**, not the empty-valley centre. PLL's scores are a
single-column cluster at ≈0, a *sparse transition band* (partial columns, weak gutters) at
0.46–0.70, and a dense two-column cluster from ~0.75 — the transition pages sit **low in the gap**,
not at its centre. A naive valley-centre anchor lands at 0.25 (below the transition band) and would
confidently stamp those weak-evidence pages two-column — the exact thing the hysteresis margin
exists to prevent. Anchoring the threshold high in the inter-cluster span (between the top of the
single-column cluster and the bottom of the dense two-column cluster) keeps the whole transition
band inside the margin, deferred to the cross-page prior / human — matching the ratified policy's
behaviour. It remains a proposal a human ratifies and freezes; the live run always uses the manifest
(never the live re-derivation, DT-9/G-22), and it abstains outright when a book is not cleanly
bimodal (single-column book, spurious tiny cluster, clusters too close).

## S2.1.6a (#46) — read-only review sheet + the match-evidence denominator

The runner now also renders the eyes-half of DT-10: one review overlay per worklist candidate,
keyed by `(page, stage)` (`work/output/geometry_review/overlays/page_NNNN_{stage}.png` — so a page
routed at two gates gets two distinct overlays, the columns one carrying the split + ruler), and a
read-only HTML evidence sheet
(`work/output/geometry_review/review_sheet.html`) — both disposable/gitignored, regenerable from the
worklist + overlays. Verdicts still enter **only** through the #40 `record` CLI (the sheet writes
nothing). The 2026-07-07 run: **25 overlays + a well-formed 62 KB sheet**, one entry block per
candidate.

Building the sheet's **denominator rule** (no match rate rendered without its token denominator)
exposed a #40 data gap: match candidates shipped a bare rate (`{"match_rate": 0.167}`) — no
denominator, no unmatched tokens, the two things that made the run-1 worklist legible in minutes.
Closed at the source: `match_stream` now surfaces `MatchOutcome.page_match_evidence` per match-routed
page — the rate's `matched`/`total` token denominator and the `unmatched_tokens` chips — in-memory,
feeding the worklist candidate `tentative` (never persisted to the lean sidecar, DT-9). On the real
run the enriched entries make the trap visible: a candidate reading **`3/4`** — a healthy-looking
0.75 rate over a 4-token window, exactly the p6 ghost-text failure the denominator exists to catch —
with its disagreeing tokens as OCR-garble chips (`i1(jl^s`, `ì3`, …).

The `order_qa` feed, worklist counts, sidecar, and auto-propose are byte-identical to the #40 run
(the enrichment rides existing evidence; only the worklist `tentative` payload and the new overlays/
sheet are added). `render_review_sheet` is a pure function of (worklist, book, overlays, sweep) —
byte-identical across renders. Red-first, mutation hunt **36/36**.

## Reproduction

```
uv run python books/per_la_liberta/run_s2_1_slice1.py            # full run (box cache ~13.5 min cold)
uv run python books/per_la_liberta/probes/s2_1_band_drift_probe.py drift   # calibration analysis, ruled band
```
