# S2.0 — bbox + text↔box-alignment probe (GATE)

**Task** `S2.0` · **Issue** #18 · **Milestone** S2 · **Scope** `GATE` · **Branch** `spike/document-structure`
· **Spec** ENGINE_STRUCTURE_PLAN §3.0, D30, §1 portability note
· **Probe** `books/per_la_liberta/probes/s2_0_geometry_probe.py` (reproducible; numbers below are its output)
· **Revised 2026-06-29** after the 5-lens adversarial audit (`s2_0_adversarial_audit.md`).

## Verdict

Geometry is **viable** as a re-bind / reading-order anchor for PLL — **S2.1-alt is not triggered** — but
the strength is **conditional**, not settled.

- **(a) S2.1 path → NORMAL (build S2.1).** Build the `GeometrySource` seam + PyMuPDF/Tesseract(ita)
  backend. Both PDFs are image scans, so the box layer is *generated* by a fresh OCR pass — a different
  engine from every witness; each box is a cross-engine match, as S1.1's `Geom` match-provenance
  requires. The audit added concrete front-end requirements (§"S2.1 design inputs").
- **(b) S5 geometry mode → conditional-primary, re-gate after S2.1 (NOT settled-PRIMARY).** On the
  two-column body pages geometry is *for*, reading-order recovery is **primary-grade** (col-aware ordered
  mean 0.92, 87% of pages clear the 0.85 bar — §Finding 4). But the *overall* per-page pass-rate is 73%,
  dragged by single-column / hard edge pages, and the order metric is only certified on n=37. So the
  honest mode is **conditional-primary**: geometry primary where the matcher is confident, re-gated once
  S2.1 builds the real detector + the two-branch order sourcing (below), measured by **mean + per-page
  pass-rate on an ordered breadth sample** (not a page median). Absence stays first-class; coords never
  invented.

> **Why the earlier "settled PRIMARY" was an overclaim (audit Finding A).** The pre-registered *naive*
> ordered metric is 0.49 — in the report's own "<0.50 → no-geometry" band. PRIMARY was recovered only by
> switching to the col-aware metric, which is a *prototype of the very S2.1 detector the gate certifies*,
> and was reported as a page *median* (0.93) that hid a mean of 0.82 and a ~30% per-page fail rate. The
> column reorder is a legitimate correction (full-width order is simply wrong for a two-column book, and
> the order-independent BoW confirms the tokens are right) — but it certifies "the order *information* is
> present," not "a buildable matcher *extracts* it at the bar." Hence conditional-primary.

## Method

- **Box layer:** fresh OCR via PyMuPDF `get_textpage_ocr(language="ita", dpi=300, full=True)` on the LOC
  scan (278 pages). Native `get_text` is empty on both PDFs (Finding 1), so this fresh pass is the only
  box source.
- **Alignment target:** `copy3_raw.txt` (Gemini OCR of the same scan) — the only witness with a per-page
  char map. The audit independently confirmed copy1 (IA-Tesseract, a *structural* witness) reads its
  columns in the same per-column order (ordered coverage 0.98), so copy3 is representative, not a soft
  target.
- **Metrics per page:** BoW (order-independent ceiling), content-token BoW (function words dropped — what
  re-bind actually anchors), naive ordered (full-width OCR order), col-aware ordered (order recovered from
  the box coordinates). All reported as **median, mean, and per-page pass@0.85** on the breadth sweep.
- **Sample:** 20 stratified pages (labels corrected — Finding 5) + a book-wide sweep (every 7th page,
  ≥20 witness tokens, n=37) that now computes **ordered coverage**, not BoW only.
- **Thresholds (pre-registered):** ordered coverage ≥0.85 → primary; 0.50–0.85 → tie-break; <0.50 →
  no-geometry. Applied per the audit's stricter reading: **mean + pass-rate**, not median.

## Findings

**1. No native word-box layer — both PDFs are image scans.** `get_text("words")` returns 0 boxes on
every content page of both the LOC and Harvard/Google scans (the Harvard PDF has text only on Google's
boilerplate cover). A usable box layer must be *generated*; Tesseract 5.5.2 + `ita` produces one at
~2 s/page.

**2. The generated boxes are well-formed, but "in-bounds" is a smoke test, not anchorability.** Boxes are
inside the page they were OCR'd from *by construction* (mean in-bounds ≈1.0), so that figure only confirms
OCR ran — it is **not** evidence boxes are trustworthy anchors. The real signal is witness coverage
(below). Near-blank pages expose the gap: the p6 verso yields **658 boxes for 7 witness tokens**
(box/witness ratio 94×) — all "in-bounds," all hallucinated. Box-count-vs-witness ratio is reported as a
hallucination flag.

**3. Cross-engine token anchorability is high and robust.** Breadth sweep (n=37): **BoW median 0.939 /
mean 0.925 / 92% of pages ≥0.85**; **content-token BoW median 0.929 / mean 0.910** (the ~1.5-pt drop is
function words, which anchor nothing — re-bind should be credited the **content-token ~0.92**, not BoW
0.94). The fresh-OCR boxes carry ~92% of the *distinctive* witness tokens.

**4. The body is two-column; column-aware order recovery is primary-grade there, conditional overall.**
Naive full-width OCR interleaves the two columns, collapsing ordered coverage to a median of **0.49**
(mean 0.51, 3% pass). Recovering column order from the box coordinates lifts it to:
- **two-column pages only (n=30): mean 0.92, median 0.94, 87% pass@0.85** — clears the strict bar.
- **all pages (n=37): mean 0.851, 73% pass** — at the bar, dragged by single-column edge pages, the hard
  TOC, and detector false-negatives.

The reorder recovers the **correct** order, not just a high-overlap permutation (on dense pages col-aware
reaches the BoW ceiling — LCS==BoW implies in-sequence; the audit verified head=top-left, tail=bottom-
right). Caveat the audit surfaced: the metric rewards agreement with the *witness's* order, which equals
ground truth only where the witness segmented columns correctly (it does on dense pages; on a few sparse
chapter-ends the Gemini witness itself interleaves, penalizing a correctly column-ordered reorder).

**5. Two-column detection is a probe heuristic with residual edge errors — the "37/37" claim was an
artifact, now corrected.** The original detector (`min(single central bin)`) returned the two-column
signal on *every* page (one stray empty bin = a "gutter"), so "37/37 uniformly two-column" carried no
discriminating information. The revised detector (contiguous central low-density run, near page-center,
splitting the page into two populated halves) detects **30/37** two-column on the sweep and correctly
calls the front matter / prefazione / TOC single-column. It still has residual errors (a few sparse
back-matter pages over-called; a few thin two-column pages under-called) — reported, not hidden. A robust
single-vs-N-column detector is S2.1 work. The *fact* that the running body is two-column is independently
solid (visual confirmation; no single-wide-column body page exists in the book).

## Reproduce

```bash
cd engine
TESSDATA_PREFIX=/opt/homebrew/share/tessdata \
  uv run python books/per_la_liberta/probes/s2_0_geometry_probe.py out.json
# env overrides: PLL_LOC_PDF (default repo-root LOC scan), PLL_OCR_DPI (default 300)
```

## Implications for downstream

- **S2.1 — proceed**, building the segmentation front-end below. Match `match_confidence` per atom;
  unmatched boxes stay unusable for primary re-bind; `geom.present=false` rather than anchor to noise.
- **S2.1-alt — not triggered** (probe positive); retained as the conditional fallback.
- **S2.2** — the geometry property tests become binding against the S2.1 backend.
- **S5** — `geometry` mode = **conditional-primary**, re-gated after S2.1 on mean + per-page pass-rate.

## S2.1 design inputs (from review, 2026-06-29; revised after the adversarial audit)

Design notes for the S2.1 matcher's segmentation front-end — **inputs to S2.1, not built**. Three stages
(density pre-check → column / reading-order detection → box↔witness match), each emitting a per-page
confidence; pages below threshold route to human review (below).

**0. Reading order is sourced two ways — geometry is not always the order oracle.**
- **When a column-correct text witness exists** (PLL has copy1/2/3): the **witness text is the
  reading-order oracle** (copy1 verified column-ordered at 0.98), and the boxes *position-match* that
  already-ordered token stream. The geometric column detector is then a **cross-check / QA signal**, not
  the order source — which is why "conditional-primary" is conservative: geometry's order burden here is
  light. This is the robust path.
- **When no prior witness exists** (image-only source — the general book-agnostic case the engine must
  not presume away): the **geometric column detector is the primary order source**, backstopped by the
  human-in-the-loop tools for low-confidence pages. The detector work is therefore not obviated — it is
  the no-witness branch. S2.1 must build both branches.

**1. Density pre-check — needs a two-sided / band classifier, NOT a single fixed threshold.** The earlier
claim that a fixed ink-fraction threshold (binarize at gray 130, count the fraction of darker pixels;
blank <0.005, content "floor" ~0.038) cleanly separates blank from content is **retracted — it is
empirically false on the full book** (audit Finding B): ink-fraction is a *continuum* from ~0.015 to
~0.12 (no valley at the claimed 0.038 floor) and **non-monotone in text content** — 22 genuine
two-column chapter-end pages fall *below* the 0.038 floor, while a text-free dark endpaper (p272)
reads 0.97 ink, *higher* than the densest prose. A working stage needs (i) a **two-sided** classifier
(or an explicit non-text-but-dark cover/endpaper class), (ii) calibration against chapter-end and
front/back-matter pages, and (iii) **not** a "density confidence" derived naively from ink-fraction
(it is maximal on the dark hallucination-prone pages). The *goal* — flag near-blank pages so their
hallucinated boxes (Finding 2) are not trusted — stands; the *mechanism* was wrong.

**2. Column / reading-order detection — projection-profile valley (RXYC), no symmetry rule.** Detect the
gutter as a contiguous central low-density run between two populated columns (the revised probe detector;
properly, the Recursive X-Y Cut valley, which also yields reading order). The earlier "mirror-symmetry
corroborator" is **dropped**: the core logic (the valley, not symmetry, discriminates single- from
two-column) is correct, but symmetry adds no *independent* signal (any symmetry feature that separates
1-vs-2 columns is equivalent to the valley's presence) and a "reject if not mirror-balanced" rule would
wrongly penalize legitimate asymmetric multi-column layouts (body + sidenote/footnote column). A
cross-page prior (layout is locally constant; inherit the previous page's class unless the profile
strongly disagrees) remains sound; the single-column exceptions are front/back matter and some
chapter-opening pages.

**3. Human-in-the-loop confidence gate — must be specified, not a slogan (audit Finding E).** As written
it named no confidence metric, threshold, human-output schema, or volume bound — unimplementable. S2.1
must specify, per stage: the confidence signal (density-class margin; gutter valley depth / column-balance
ratio; box↔witness match rate), a threshold-setting method, the **human verdict schema** (e.g. confirm /
redraw column split / mark `geom.present` / reclassify page), the criterion by which a reviewed page then
passes, and a **volume bound** (what fraction of pages routing to review is acceptable before the
automation premise fails). It is the safety net for both order-sourcing branches and the primary one for
the no-witness branch. See `project-ingestion-human-in-loop`.

## Caveats / follow-ups

- The probe's column detector is a heuristic with residual edge errors (§Finding 5); a robust detector is
  S2.1. Its false-negatives drag the all-pages ordered mean (0.851); the two-column-only mean (0.92) is
  the cleaner read.
- A genuine **bad-OCR-region** stratum and a **set-off embedded-letter** stratum were **not located** in
  the book (the index is clean small-type, not degraded; no epistolary salutations were found except one
  on the unsampled p118) — the gate's stratification is honest about this rather than mislabeling pages
  (Finding 5 corrected the labels).
- Numbers are at dpi=300, default Tesseract. The earlier "higher dpi only raises anchorability" claim was
  an unbacked extrapolation and is withdrawn (Tesseract accuracy is not monotone in dpi past ~300).
