# The band-drift finding (S2.1.3 #37 → P-2 supersession)

**What this records:** why the first PLL slice-1 calibration run scored 53.6% exact against a
95% floor, what the number actually meant, and why the fix was widening the locate band
(P-2: 3× → **16×** max page bag, ruled by Ben 2026-07-05) rather than touching the matcher.
Referable evidence for any future book that misbehaves the same way.

Everything below was measured on the 2026-07-05 run (box cache
`books/per_la_liberta/work/data/geometry/_boxes_dpi300.json`, engine
`pymupdf-1.27.2.3+tesseract-5.5.2:dpi=300:lang=ita`; blocked-run stats persisted in
`s2_1_run_stats.json`). Rerunnable via `books/per_la_liberta/probes/s2_1_band_drift_probe.py`.

## The symptom

Blind page-locate on copy3 (the ground-truth witness) under the then-ruled 3× band:
279/521 single-page atoms exact = **53.6%** — but the distribution, not the headline, is the
finding. Delta = assigned − true page, bucketed by true page:

| True pages | 1–159 | 160–179 | 180–199 | 200–219 | 220–239 | 240–259 | 260–278 |
|---|---|---|---|---|---|---|---|
| exact | 74–88% | 64% | 12% | 0% | 0% | 0% | 0% |
| mean delta | ~+0.15 | +0.36 | +1.35 | +2.83 | +3.53 | +4.61 | +6.93 |

Monotonically growing, always **late**, collapsing to 0% past page 200. Meanwhile the failing
atoms' tokens overlapped their *true* page's OCR bag at ~95% (e.g. 576/606) vs ~30% at the
assigned page — the DP could see the right answer and was fenced off from it.

## The mechanism (measured, not theorized)

`locate_pages` restricts each boundary to a band around an estimated center. Centers come from
the cumulative-**bag-mass** ratio map, pinned at the scan's two ends. That map's measured error
against copy3 truth (estimated − true page):

| True pages | 1–19 | 40–59 | 80–99 | 100–119 | 140–159 | 180–199 | 220–239 | 260–278 |
|---|---|---|---|---|---|---|---|---|
| mean error | −5.2 | −3.0 | −1.1 | ~0 | +2.4 | +4.1 | +6.7 | +8.1 |

An S-curve: ~13-page swing, zero mid-book, **largest at the two ends**. Cause: pages that carry
bag mass but no *stream* tokens — front covers/scan targets and back-matter noise — stretch the
linear map outward; the text truly occupies a narrower page interval than the scan. PLL's bag
mass is nearly uniform (441–521 tokens/page in every 20-page block), so the distortion is
stream-side, not bag-side.

The ruled 3× band = 3 × 1,254 (max bag) ≈ **±3 pages** of slack. Wherever the S-curve exceeds
that, the DP is *forbidden* from choosing the true boundary — it clamps to the band edge, which
is exactly the growing-late-tail signature above. The DP itself is a global optimizer (backward
suffix DP + forward earliest-argmax walk): processing order contributes nothing, and a
two-front / meet-in-the-middle strategy cannot help — the prior's error is **largest at the
ends and zero in the middle**, the inverse of the shape meet-in-the-middle addresses. (Asked
and answered with the table above, 2026-07-05.)

## The proof and the ceiling

Rerunning the identical blind calibration with a wide band (20K tokens ≈ ±16 pages):

- deltas: `{-1: 2, 0: 421, +1: 98}` — **80.8% exact, 99.6% within ±1, nothing off by ≥2**
- flat across the book (every 40-page bucket 76–86% — the tail collapse is gone)
- misses are ~all **≤5-token atoms** (99 of 100): headings/dates/dividers whose bags genuinely
  cannot distinguish adjacent pages. Atoms with >5 tokens: **327/328 = 99.7% exact**.

That is the *evidence ceiling*: the DP is exact within its band, so once the band covers the
prior's error, accuracy is capped by tiny-atom ambiguity — no search strategy moves it.

## The remedy family (in increasing power, all converging on the same accuracy)

1. **Widen the band** *(ruled — P-2 superseded to 16× max bag, 2026-07-05)*: 16× ≈ ±16 pages on
   PLL covers the +10-page worst drift with ~60% margin. Cost: locate 9s → 88s, once per book.
   Chosen for slice 1 as the smallest change that reaches the ceiling.
2. **Re-pin the map's anchors** to the first/last *text-bearing* pages instead of the scan
   ends — collapses most of the S-curve, but finding those pages robustly is itself a
   mini-locate (chicken-and-egg).
3. **Coarse-pass re-centering**: a cheap first locate supplies boundaries as centers for a
   tight-band refinement — locally-correct anchors everywhere. The escape hatch if a future
   book's density distortion (e.g. a large mid-book plate section, which bends the S-curve
   where end-anchoring helps least) outruns any fixed multiplier. Not built; build it against
   this document's measurements.

## Guardrails now in place

- `test_locate_default_band_survives_end_matter_token_deserts` — unit-scale replica of the PLL
  failure (16 desert pages, center error 16 vs 3×-half 15); reds on a 16→3 regression.
- `test_locate_default_band_is_the_ruled_width_of_the_largest_bag` — optimum at exactly
  center + half under 16×; any multiplier < 16 (and a min-bag width) reds.
- `test_locate_band_multiplier_is_the_ruled_p2_value` — pins the constant with the supersession
  history.
- Hunt rows: `p2-band-regressed-to-superseded-3`, `p2-band-one-under-ruled`,
  `p2-band-multiplier-drifted` (`tests/hunts/hunt_geom_match.py`).

## What the 53.6% did *not* mean

Not matcher quality, not OCR quality, not a wrong objective: one mis-sized ruled constant
(P-2), caught by the P-1 calibration gate doing precisely its job before any sidecar was
published. The gate's own floor semantics (95% exact over *all* atoms, unreachable while 37% of
the atom count is ≤5-token fragments) is a separate ruling — see the P-1 row in
`s2_1_plan.md`.
