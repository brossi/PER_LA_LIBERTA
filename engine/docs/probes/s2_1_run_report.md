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
- Thresholds as proposed at DT-8: `page_accept_rate=0.80`, `atom_match_floor=0.60`
  (ratification: §Ratification below).

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

## Ratification items (DoD-gating for #37 close)

1. **DT-8 thresholds 0.80/0.60** — proposal → ratify. Evidence: the page histogram is cleanly
   bimodal (253 pages ≥ 0.80, stragglers are noise pages plus an 11-page review worklist);
   loosening to 0.75 would absorb ~8 worklist pages into "matched" — the wrong direction given
   the route-to-human posture. Atom floor 0.60: only 50 atoms land in `below_atom_floor`.
   **Recommend ratify as proposed.**
2. **Wire extension `stage="locate"/signal="empty-window"`** — observed on exactly the 7
   physically text-empty pages. **Recommend ratify** (extends DT-10's enum, honest distinct
   cause vs a match-rate failure).
3. **DT-13 (a) vs (b)** — 1,165 copy2-only canonical atoms carry no geometry from this sidecar.
   **Recommend (b)**: ratify the exclusion as a named coverage floor (24.3% of canonical atoms)
   and keep the copy2 lane as a later deliverable — lane (a) requires a Harvard-scan OCR pass,
   its own calibration argument (copy2 has no ground-truth page map), and its own leaf-offset
   handling: a full deliverable, not a close-out item. Revisit condition: the first consumer
   that needs geometry on a copy2-only atom (e.g. S3.1 word geometry or a citation surface).
4. **P-1 "tighten to 97%?" note** — clause A measures 99.70%, so 97% would pass today;
   recommend **keeping 95%** until a second book gives cross-book variance (floor-setting on
   N=1 is anchoring, not calibration).

## Reproduction

```
uv run python books/per_la_liberta/run_s2_1_slice1.py            # full run (box cache ~13.5 min cold)
uv run python books/per_la_liberta/probes/s2_1_band_drift_probe.py drift   # calibration analysis, ruled band
```
