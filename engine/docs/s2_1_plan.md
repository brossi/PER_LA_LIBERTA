# S2.1 — GeometrySource seam + backend (NORMAL path) + segmentation front-end (plan)

**Status: RATIFIED 2026-07-03 (Ben) — DT-1…DT-13 ratified as written**, after: the four-round
adversarial audit (21 → 10 → 3 → 2 threads, all closed "no further objection"; verbatim trail in
`s2_1_plan-discussion.md`), a two-lens post-redraft fold audit (121/121 discussion commitments
verified present + faithful; drift findings fixed), and per-item rulings on every escalated
number and name (§8 ledger: B1, B2, P-1…P-6). This document is the build surface; the discussion
file is the audit trail. **Build is unblocked — slice 1, #35 first.** One decision deliberately
remains open: **DT-13's (a)/(b) ruling** — it gates the tracker row's `DONE`, not the build;
slice 1 is outcome-neutral and the designed decision point is the slice-1 run report's measured
copy1 coverage. Parent issue #29 (children #35–#40); tracker row
`S2.1` in `ENGINE_STRUCTURE_TASKS.md` (~L423) is the authoritative spec — on any disagreement the
tracker wins, then `ENGINE_STRUCTURE_PLAN.md` (§3.0, §11.1, D30), then this plan. Evidence anchor:
`spike/document-structure` — file:line cites verified on disk during the audit (commits `08aea65`
through `ccf9c05`); stream measurements taken 2026-07-03 on the live frozen streams.

Inputs this plan consolidates:

- `docs/probes/s2_0_geometry_alignment.md` — the S2.0 probe result + §"S2.1 design inputs"
  (revised post-audit) — and `docs/probes/s2_0_adversarial_audit.md` (Findings B/E carried;
  the numbered findings 2/5 are the alignment doc's §Findings).
- `books/per_la_liberta/probes/s2_0_geometry_probe.py` — the prototype the detector/matcher
  generalize (its `tokens`/`bow_coverage`/`ordered_coverage`/`detect_columns`/`reading_order`).
- The ingestion human-in-the-loop ruling (user, 2026-06-29): classifiers calibrate to **abstain**;
  low-confidence pages route to a human worklist **before** the gate. Absence semantics carry the
  R10 scope split: a page's geometry is declined only after both auto-detection and a human
  verdict; within an accepted page, unmatched atoms auto-absent with recorded reason (DT-8
  exception, DT-9 record).
- `s2_1_plan-discussion.md` — the four-round audit this draft folds (thread ids R1–R21 cited
  below where a ruling's provenance matters).

## §0 Scope and provenance

S2.0 (GATE, DONE, #18) chose the **NORMAL path**: both PLL PDFs are image scans (0 native boxes);
the box layer is generated fresh by PyMuPDF+Tesseract (`ita`, 300 dpi). Evidence carried forward:
token anchorability vs copy3/Gemini BoW median 0.939 / mean 0.925 (n=37); content-token median
0.929; body two-column (probe detector 30/37); naive full-width order 0.49; column-order recovered
mean 0.92 / 87% pass@0.85 on two-column pages (n=30) but mean 0.851 / 73% over all pages; copy1
confirmed column-ordered 0.98. Verdict: S5 geometry = **conditional-primary, re-gated at S2.2
(#30)** on the as-built detector, on mean + per-page pass-rate.

S2.1 builds, in one wave (two slices, §5):

1. **`GeometrySource` seam** — an injectable Protocol; backends yield per-page word boxes.
2. **PyMuPDF+Tesseract backend** — the NORMAL path; OCR language/dpi come from book config.
3. **Witness-text↔geometry matcher** — explicit, fail-loud, writes all four provenance fields
   `{geometry_engine, matched_witness_id, match_method, match_confidence}` into S1.1's frozen
   `Geom` slot; unmatched boxes are unusable for primary re-bind; a canonical atom carries its
   **primary witness's** box only where matched.
4. **Segmentation front-end** — (0) two-branch reading-order sourcing, (1) density band pre-check,
   (2) column/reading-order detection, (3) a **specified** human-review worklist.

Consumers waiting on the as-built output (runway Lane 1): **BR-022** (region coordinate space —
DT-4 pins it), **S3.1** (D30 word geometry — DT-12), **S5.1**'s mode re-gate (defined against this
detector, ruled at **S2.2**).

## §1 The geometry path (end-to-end)

```
scan PDF ──► GeometrySource backend ──► per-page WordBoxes
                                            │
                              (1) density band pre-check ── abstain ──► worklist
                                            │ content
                              (2) column / reading-order detect ── low conf ──► worklist
                                            │
              ┌── order-source branch (book config) ──┐
   witness branch (PLL)                     no-witness branch (image-only)
   witness text = order oracle              detector = primary order source
   detector = cross-check / QA feed         human loop = essential backstop
              │                                        │
   (3) page-locate: monotone align          OCR tokens ARE the text; boxes
       box stream ↔ witness stream          are theirs by construction
              │                             (segmentation proof only — NO atom
   (4) per-atom match in the page window     streams in S2.1, §6)
              │ matched      │ page below threshold ──► worklist
   Geom.matched(union bbox + provenance) ──► geometry sidecar (DT-9)
              │
   Geom.absent  (page-level: only after auto + human both decline;
                 atom-level on an accepted page: automatic, reason recorded — DT-8)
```

On the witness branch the matcher is the deliverable that fills `atom.geom`; the detector runs on
every page anyway as the QA cross-check and the **S2.2 measurement feed** (per-page ordered
coverage of detector-ordered boxes vs the witness window — the probe's metric, now emitted by the
build). On the no-witness branch there is no witness to match: the front-end's segmentation
(trusted boxes + reading order + worklist) IS the output, proven on a synthetic fixture (DT-11) —
PLL never exercises this branch, and the engine must not presume it away.

## §2 Surfaces it binds into (verified during the audit)

- **`src/engine/structure/atoms.py:41`** — `Geom` frozen-slots dataclass: `present` +
  six required-when-present fields (`page`, `bbox`, `geometry_engine`, `matched_witness_id`,
  `match_method`, `match_confidence`); `absent()`/`matched()` factories; `absent()` is nullary
  (`:84–87` — no reason field, so absence reasons live in the sidecar, DT-9); absence carries no
  coordinates and half-built/invented geometry raises in `__post_init__` (`:69–74`). The tracker
  row originally quoted only three provenance fields; corrected 2026-07-03 to all four (audit
  R21) — the frozen contract always was four-field. `Atom.geom: Geom` at `:147`.
- **`Atom.derived_from: tuple[AtomDerivation, ...]`** with `AtomDerivation{witness, atom_id}`
  (`atoms.py:116–122, :150`) — the link canonical attachment walks (DT-9). `processing_scope`
  `included`/`excluded` (`:30–37`); measured (2026-07-03): copy1 carries **zero** `excluded`
  atoms — its page furniture (folio/decoration OCR garble, chapter heads) is `included`-scope
  text — while copy3's 278 `excluded` atoms are its synthetic `⟨PAGE:N⟩` markers. DT-3's
  page-locate runs over the full stream either way.
- **Frozen streams** — `books/per_la_liberta/work/data/atoms/{copy1,copy2,copy3,canonical}.json`
  (written by `freeze_streams.py`): copy1 3621 / copy2 3356 / copy3 799 / canonical 4786 atoms
  (S1.3a oracle-backed pins). Canonical derives from copy1+copy2 only (copy3's word-level link is
  S7.1b), so **"primary witness's box" ⇒ copy1 is the matched witness** (DT-3).
  copy1/copy2 are `PAGE_UNMAPPED`; only copy3 has real page ranges (its `⟨PAGE:N⟩` map, 278
  pages). Measured 2026-07-03 on the live streams: **1165/4786 canonical atoms (24.3%) have no
  copy1 derivation** (copy2-only — DT-13's population); **multi-copy1 count = 0** (DT-9's
  synthetic-only edge); copy1 = **129,767** whitespace tokens (~467/page — DT-3's scale input).
  Atom-size profile (sizes the P-1/P-4/P-5 rulings): copy1 tokens/atom mean 35.8 / median 25 /
  max 283, with a large short tail — ≤3 tokens = 1,170 atoms (32.3% by count, **1.3% by token
  mass**), spread uniformly across the book, mostly folio/decoration OCR garble (`'35 32 5E:'`,
  `'3E'`) plus chapter heads (82 of the 1,170 are `«`/`—` dialogue openers). copy3 body = 521
  atoms and bimodal: ~63% page-sized prose chunks (mean 241 tokens, ~2/page) + 193 atoms ≤5
  tokens (stamps, chapter heads, bare folio numbers, decoration garble); **no copy3 body atom
  spans a page boundary** (atoms were cut at the markers), so DT-3's calibration "exact" is
  unambiguous for every atom.
- **Probe prototype** — `books/per_la_liberta/probes/s2_0_geometry_probe.py`: OCR invocation
  `pg.get_textpage_ocr(flags=0, language=OCR_LANG, dpi=DPI, full=True)` (`:195`); the tokenizer
  (`_EDGE`-strip + lower), BoW/ordered coverage, `detect_columns` (contiguous central valley +
  populated-halves guard), `reading_order`.
- **Neutrality guard** — `tests/unit/test_structure_neutrality.py`: substring, case-insensitive
  scan of `FORBIDDEN` over `structure/` py+schema files, with planted-literal non-vacuity tests.
  Gains the OCR-language literal **in quoted form** (`"ita"` / `'ita'`) — bare `ita` would
  false-positive on English words (`italic`, `vital`) (DT-1).
- **Errors taxonomy** — `errors.py` owns exit codes 3–10 (`BackendError` = 5, with a per-page
  degrade-to-sentinel contract, `:56–61`; shared loader taxonomy `MissingInputError` /
  `StaleArtifactError`, `:18–24`); `StructureValidationError` 11 (`structure/errors.py:170`);
  `EvidenceGateError` 12 (`structure/evidence.py:656`); uniqueness sweep at
  `test_authoring_evidence.py:625`. **13 is free** (grep-verified) — DT-1 claims it.
- **Toolchain** — `engine/pyproject.toml:20` `pymupdf>=1.27.2.2` (already a dep; no pytesseract
  needed). Local tesseract at `/opt/homebrew/bin/tesseract` with `ita` + `ita_old`; tessdata must
  be discoverable (probe docstring). **CI (`.github/workflows/engine.yml`, ubuntu-latest) has no
  tesseract today** and the 82 MB PDF is gitignored — DT-11 owns the split. Tracked-in-CI real
  assets: `books/per_la_liberta/inputs/copy{1,2,3}_raw.txt` + `copy3_pro_page_map.json`
  (git ls-files verified; these are the files the engine's real-input tests read).
- **Workspace containment** — `paths.py`: `BookWorkspace.resolve` guards **writes** into `work/`
  (`:97–113`); tracked read-only siblings are the established pattern (`inputs/`, `:83–86`);
  `engine/.gitignore:15–20` ignores `books/*/work/{data,output,state}/*` ("regenerable, so never
  committed"). DT-6/DT-10's artifact homes follow this split.
- **S1.3a tripwire** — `test_real_canonical_is_uniformly_page_unmapped_until_s7_1b` pins every
  canonical atom `PAGE_UNMAPPED (-1,-1)` until S7.1b. DT-3's derived pages live in `Geom.page`,
  never `Atom.page_range` — the tripwire keeps enforcing that.
- **S3.1 stub plan** — `docs/s3_1_plan.md` carries Q-S3.1-1/-2; S3.1 consumes word geometry
  through this seam (DT-12).

## §3 Decisions to ratify (DT-1 … DT-13)

### DT-1 — Module homes + neutrality budget + `GeometryError` (exit 13)

New core modules, all under `src/engine/structure/` (neutral; S0.2 guard extended):

- `geometry.py` — `WordBox` / `PageGeometry` records + the `GeometrySource` Protocol +
  `GeometryError(EngineError)` with **`exit_code = 13`** (the next free code; 3–12 occupied, §2).
  The class lives beside its raiser — the carrier-beside-vocabulary posture `errors.py`'s
  docstring names for 11/12. **Not** a `BackendError` reuse: that class is ocr-step-owned and its
  documented contract is the *opposite* posture — per-page failures degrade to an `[OCR_ERROR]`
  sentinel (`errors.py:58–63`) — while `GeometryError` is fail-loud with no per-page degrade
  (DT-2). Reusing exit 5 would put two contradictory failure contracts under one code.
- `geometry_pymupdf.py` — the PyMuPDF+Tesseract backend. `language` and `dpi` are **required
  constructor parameters with no defaults** — a default language is a language opinion in core.
  `"ita"` lives only in PLL book config under `books/per_la_liberta/`.
- `segmentation.py` — density band classifier + column/reading-order detector + per-page
  confidence records. Operates on boxes/pixmaps only; no witness, no language.
- `geom_match.py` — normalizer + monotone page-locate + per-atom window matcher +
  `attach_geometry(atoms, sidecar)` overlay loader.
- `geom_sidecar.py` — sidecar schema/write/load (DT-9) + worklist records (DT-10). (If this file
  wants to split during build, worklist records may move to their own module — name stability of
  the four above is the commitment, not the count.)

**`GeometryError` boundary inside S2.1:** it covers backend/OCR operational failure and geometry
integrity (box outside rect, calibration-gate block, volume-bound breach). The sidecar/worklist
**load** boundaries do NOT use it — they join the existing shared loader taxonomy (absent →
`MissingInputError`, present-but-unloadable/stale → `StaleArtifactError`, `errors.py:20–26`),
red-tested as G-18.

**Owned ripples:** extend the exit-code uniqueness sweep (`test_authoring_evidence.py:625`,
currently spanning three files) to `geometry.py` — and prove the extension during #35's red phase:
with `GeometryError.exit_code` temporarily set to 11 (colliding with `StructureValidationError`),
the extended sweep must red, proving it actually sees the fourth file, not just that 13 happens to
be unique today; then green at 13. Update `errors.py`'s "two structure-owned subclasses" docstring
to three.

`FORBIDDEN` gains `'"ita"'` and `"'ita'"` (quoted forms; the existing planted-literal
parametrization inherits them automatically — G-2). pymupdf imports in core are fine — it is
already a required dependency; the neutrality rule governs language/book literals, not libraries.

### DT-2 — `GeometrySource` contract

A backend is a Protocol with one obligation: given a page index range, yield
`PageGeometry{page: int, width: float, height: float, words: tuple[WordBox, ...]}` where
`WordBox{text: str, bbox: (x0, y0, x1, y1)}`, plus an `engine_id: str` property — a
reproducibility string built from live versions and params (shape:
`pymupdf-{ver}+tesseract-{tessver}:dpi={dpi}:lang={lang}`). The matcher writes `engine_id`
**verbatim** into `geometry_engine` — never a hardcoded string (G-3). Fail-loud: missing
tessdata / OCR failure / a box outside the page rect raise `GeometryError`; a backend never
returns silently-empty pages for operational failures (empty ≠ failed: a genuinely blank page
yields zero words *successfully*).

**Record validity (two layers, no silent loss — R2):**

1. **Record contract:** `WordBox`/`PageGeometry` `__post_init__` rejects non-finite coords,
   degenerate boxes (`x1 <= x0` or `y1 <= y0`), empty/whitespace `text`, and non-positive
   page/width/height — invalid records are unconstructible (G-21).
2. **Backend normalization:** Tesseract can emit empty-text/degenerate artifacts; the backend
   drops them *before* record construction and counts them in a per-page `dropped_boxes` stat
   surfaced in the sidecar page record + run report — dropped-and-counted, never silently absent.

**Page semantics pinned at the seam:** `PageGeometry.page` is DT-4's 1-based scan number; the
Protocol's range parameters are 1-based inclusive, matching `⟨PAGE:N⟩` / `page_000N.png`.

**Order: contractually unspecified at the seam** — load-bearing by design, not an omission:
page-locate consumes per-page token *bags* (order-free) and the per-atom match is
BoW-within-window, so slice 1 never depends on backend emission order; the only ordered-box
producer is the slice-2 detector, and `order_qa` measures exactly that. A consumer wanting order
must go through `segmentation.reading_order` — treating backend order as reading order has no API
to do it accidentally. The matcher additionally canonicalizes box order at entry (DT-8), so its
output is invariant to emission order (G-24's determinism red).

### DT-3 — Anchor witness = copy1; page-locate by monotone alignment; copy3-blind calibration

The done-when says a canonical atom carries its **primary witness's** box; canonical derivations
are copy1+copy2 only, and copy1 is the primary structural witness — so **copy1 is the matched
witness** (`matched_witness_id="copy1"`). Problem: copy1 is `PAGE_UNMAPPED` (no page map). Rather
than a page prior, the build derives it by monotone global alignment of the (paginated) box token
stream against copy1's (ordered) token stream — both are in reading order, so page assignment is
a monotone segmentation of the witness stream, and per-witness-atom page windows fall out (the
windows DT-8's matcher works inside). Byproduct: **real page ranges for copy1's atoms**
— the open S1.3a page-attribution question gets its answer as derived sidecar data (never a
mutation of the frozen stream, D25/DT-9).

**Page-locate algorithm (pinned, R4):**

- **Objective:** given the DT-8-normalized witness token stream `w[0..N)` and per-page box token
  bags `B_1..B_K` (pages in scan order), choose monotone boundaries
  `0 = c_0 ≤ c_1 ≤ … ≤ c_K = N` maximizing `Σ_p |multiset_intersect(w[c_{p-1}:c_p), B_p)|` —
  a banded DP (band positioned by the cumulative-token ratio), deterministic tie-break to the
  **earliest** boundary achieving the max. No separate gap/mismatch scoring: unmatched tokens
  (garble, hallucinated boxes) simply score zero.
- **Complexity contract:** `O(N + K·B)` — boundary candidates per page limited to a band `B`
  (ruled 2026-07-03, P-2: 3× the max page bag size, ≈1.4K tokens), with *incremental* integer
  multiset scoring
  (moving a boundary by one token updates the intersection count in O(1)). Scale, measured: copy1
  N = 129,767 tokens, K = 278 pages — ~4×10⁵ boundary evaluations vs N² ≈ 1.7×10¹⁰ for the
  quadratic shape. The run report records page-locate wall time so a complexity regression is
  visible; the mutation pass reviews the incremental-update invariant (no perf assert in CI;
  timing tests flake).
- **Determinism:** scores are integers (multiset intersection counts) — no floats anywhere in the
  DP — and argmax uses the earliest-boundary tie-break, so boundaries are a pure function of the
  two token streams, stable across Python/platform/library versions. Committed fixture (G-7): a
  synthetic stream with a repeated-token run plus a furniture token straddling a boundary, built
  so two boundary positions tie on score — asserts the exact (earliest) boundary indices; a
  mutant flipping the tie-break to latest reds.
- **Furniture:** page-locate runs over the **full** stream, never filtered by `processing_scope`
  (`atoms.py:30–37`). Measured (2026-07-03): copy1 carries its page furniture as
  `included`-scope text (folio/decoration garble — ~1/3 of its atoms by count, 1.3% by token
  mass) and copy3's `excluded` atoms are the synthetic `⟨PAGE:N⟩` markers, which match no box
  and score zero — harmless. Printed folios/decoration are page-anchoring signal, and a
  furniture-text atom that matches its printed box gets real geometry, which is fine.

**No copy2 fallback (ruling, R3):** the tracker requires the canonical atom to carry its *primary
witness's* box; a copy2 box on a canonical atom is a different contract needing a D-level
redefinition first (that question is now DT-13's gate). What lands instead: the loss is counted
**separately and by cause** in the sidecar's `coverage` object (DT-9) — `pages_locate_failed`,
`atoms_unmatched_on_accepted_pages`, `canonical_no_primary_derivation`,
`canonical_multi_primary_derivation` — the run report cites them, each line tagged
`secondary-not-attempted`, so the untried copy2 option stays visible as evidence for DT-13's
ruling rather than silent coverage loss. The `{witness}_geom.json` namespace already admits a
future `copy2_geom.json` without redesign.

**Calibration gate (inside slice 1, before trusting copy1 assignments):** run page-locate on
**copy3 blind** (ignore its page map), compare derived pages to the map — the only ground truth we
own. Accept when ≥95% of copy3 body atoms page-locate exactly; publish the distribution in the run
report. (**Ruled 2026-07-03, P-1: 95% stands for the slice-1 gate, re-evaluated at the run
report** — tighten to 97% if the ≤5-token calibration-atom exactness distribution supports it;
the copy3 body population is bimodal (§2) and the tiny-atom mislocation rate is the one unknown
the run resolves. copy1's fresh-Tesseract-vs-IA-Tesseract agreement is expected ≥ copy3's
Gemini-vs-Tesseract 0.939 — same engine family, same scan — but that expectation is *checked* by
the run report, not assumed.) Shape alone is never the
acceptance: G-7 pairs the monotone property (CI) with this exactness gate (ground truth).

**Failure route (pinned):** calibration < floor → S2.1.3 **hard-blocks** — no `copy1_geom.json`
is published; the run report ships the failure distribution and the ruling comes to Ben with the
named options: (i) ratify a page±1 tolerance tier with the floor re-derived, (ii) route the
failing page-regions to the DT-10 worklist, (iii) reopen S2.1-alt (the tracker retains it as the
specified conditional). Never a silently lowered bar.

**Ownership boundary (R18):** S2.1's derived pages are **geometry evidence only** — they live in
`Geom.page` (a fact about where the matched *box* sits) and in the sidecar; `Atom.page_range`
(the capture address) stays `PAGE_UNMAPPED`, enforced by the S1.3a.4 tripwire (§2). Different
fields, different meanings — `attach_geometry` writing `Geom.page=52` onto a `PAGE_UNMAPPED` atom
is the intended state. Ratifying *adoption* (page_range semantics) remains S7.1b's; on S2.1
close, the tracker's S1.3a `PAGE_PENDING` deferral note gains one pointer line: sidecar-derived
copy1 pages exist at calibration floor X, adoption decision unchanged at S7.1b.

### DT-4 — Coordinate space + page numbering (BR-022 seed)

`bbox` is in **PDF page-point space** (PyMuPDF `page.rect` units, origin top-left, y-down) — the
one space that is dpi-independent and stable across re-renders. Proof is numeric, not
containment-only (R5): OCR the same synthetic page at dpi 150 and 300 and assert the same word's
bbox equal in page space within tolerance (ruled 2026-07-03, P-3: ≤0.5 pt per coordinate), plus
containment
(every box ⊆ `page.rect`) — containment alone would already red on raw pixmap coords (~4.17× at
300 dpi) but cannot catch dpi-dependent quantization drift; the numeric test closes that (G-8).

**Rotation/crop: explicitly unsupported in S2.1 — enforced, not assumed.** The backend raises
`GeometryError` on `page.rotation != 0` (both PLL scans are unrotated; a rotated page must fail
loud, never emit wrong coordinates silently) — the synthetic fixture gains a rotated-page variant
and the rejection is a named red (G-17). CropBox≠MediaBox: coords are relative to `page.rect`
«unverified that `page.rect` is the cropbox-derived visible rect — bound at build by the same
containment test on a cropped synthetic page» (G-8's home).

`page` is the **1-based scan page number**, consistent with copy3's `⟨PAGE:N⟩` markers and
`docs/assets/page_images/page_000N.png` (pymupdf index + 1); the copy3-blind calibration (DT-3)
doubles as the numbering cross-check (278 markers == 278 pages, S1.3a). This DT is the BR-022
answer-of-record: downstream regions inherit this space or declare a transform.

### DT-5 — Two-branch reading-order sourcing (where the branch lives)

Book config declares `order_source: witness | geometry`. PLL = `witness` (copy1 column-ordered
0.98): the witness stream supplies order; page windows come from page-locate; the per-atom match
is order-free within the window (BoW), so a column-detector miss cannot corrupt geometry — the
detector still runs on every page as the QA cross-check, emitting per-page
`ordered_coverage(witness_window, detector_ordered_boxes)` into the run report (**this is the
S2.2 measurement feed**, DT-12). `geometry` branch: the detector's order is authoritative, the
worklist is its essential backstop, and the OCR tokens are the text (boxes are theirs by
construction — no matcher needed; the front-end's confidence/worklist output is the deliverable).

**In S2.1 the no-witness branch emits NO atom streams (R6).** It is a segmentation-front-end
proof — trusted boxes + reading order + worklist routing on the synthetic fixture, measured by
G-16's ordered-coverage pin — nothing more. Turning detector-ordered boxes into L1 atoms
(raw_span/raw_source_hash against *what* raw source, capture tiling, round-trip) is a real
capture-contract design that must go through S1.3a's machinery and has no consumer today: PLL
never exercises the branch. Named §6 non-goal, so the omission is a recorded decision, not a gap
someone later mistakes for support.

### DT-6 — Density pre-check: band classifier, calibrated to abstain

Audit Finding B stands: a single fixed ink threshold is dead (non-monotone continuum; dark
endpaper 0.97 > densest prose; 22 real chapter-end pages < the old 0.038 "floor"). The classifier
maps per-page features → `{content, near_blank, non_text_dark, abstain}`:

- Features: ink fraction (binarized pixmap), box count, token yield (alpha-token count / box
  count — p6's hallucination signature is 658 boxes / 7 tokens), mean token length.
- **Two-sided**: `near_blank` (low ink, low token yield) and `non_text_dark` (high ink, low token
  yield) are distinct classes; both mean "boxes untrusted".
- **`abstain` is a first-class output** — the ambiguous middle routes to the worklist, never
  forced into a class. Confidence = margin to the band edges, NOT raw ink fraction (Finding B's
  trap: ink-confidence is maximal on the hallucination-prone dark pages).
- Calibration set: the S2.0 stratified 37 + the audit's boundary pages (chapter ends, endpapers,
  front/back matter), labeled in the **tracked** `books/<id>/review/density_calibration.json`
  (R7; the run report cites it, band values live in `manifest.json`). Bands set generously toward
  abstain — a human glance is cheap next to a trusted hallucination.

**Calibration is a governed artifact and the core stays numberless (R7):** `segmentation.py`
takes band thresholds as **required constructor parameters with no defaults** (the G-1 posture —
a baked default band is a scan-profile opinion in core) and exports a classifier version string
(`SEGMENTATION_VERSION = "density-bands-v1"`). PLL's calibrated band values live in
`manifest.json` (the tracked book config); the labeled calibration set (page ids + assigned
bands) is the tracked `books/<id>/review/density_calibration.json`, which pipeline steps read
only. The sidecar records `classifier_version` + the exact band values used, and both join the
DT-10 input fingerprint — so a rerun distinguishes "classifier changed" from "input changed"
mechanically, and a verdict given under old bands goes stale rather than silently re-applying
(G-22).

### DT-7 — Column / reading-order detector (generalize the probe; cross-page prior; no symmetry)

Promote `detect_columns`/`reading_order` into `segmentation.py` with the audit's rulings baked in:
projection-profile contiguous central valley (≥3 bins) + populated-halves guard (the probe's
sparse-page fix); **mirror-symmetry rule stays DROPPED** (redundant; wrong on asymmetric
layouts); **cross-page prior retained** — layout is locally constant, so a page inherits its
neighbor's class when its own valley evidence is inside a hysteresis margin (margin values
proposed in-code, ratified by the run report distribution). Detector confidence = valley depth ×
column-balance; below threshold → worklist. Reading order (columns top-to-bottom, left column
first, line-binned by median box height) comes free from the split.

**Prior scope contract (R8):**

1. The prior applies only between consecutive `content`-band pages — the density gate runs first,
   and any non-content or worklist-routed page **resets** the chain (a prior must never tunnel
   through an endpaper or a routed page).
2. Own-page evidence outside the hysteresis margin always wins — the prior breaks ties *inside*
   the margin only, never overrides a confident valley.
3. In-margin with *disagreeing* neighbors (the transition pages: chapter opens, sparse ends) →
   **abstain to the worklist**, inherit nothing.
4. Every page records `n_cols_source: "evidence" | "prior"` in its sidecar page record, so the
   S2.2 re-gate can measure how often the prior decided and whether prior-decided pages are where
   `order_qa` fails.
5. Red fixture (G-23): a strong-evidence single-column page between two two-column pages — a
   mutant that lets the prior override strong own-page evidence reds.

### DT-8 — Matcher: normalizer, window match, confidence formula, thresholds, absence semantics

- **Normalizer** (promoted from the probe, one place, shared by page-locate + matcher): NFC →
  whitespace split → strip edge punctuation → casefold. **No accent stripping, no stopword
  removal** in core (language opinions; the probe's `content_tokens` stays probe-side as a
  metric variant).
- **Per-atom match** (`match_method="token-bow-v1"`): within the atom's page window, greedy
  multiset token matching between atom tokens and box tokens;
  `match_confidence = matched_tokens / atom_tokens` (pinned formula, value-pin tested, G-5);
  `bbox` = union over **matched boxes only** (a distractor box never widens the union, G-6);
  `page` = the window's page. Page-locate is recorded page-level in the sidecar as
  `locate_method="monotone-align-v1"`.

**Ambiguity defense (R9) — the never-invent posture does the heavy lifting:**

1. **Multiset box-token consumption** — atoms match in witness order within the page and a box
   token consumed by one atom is unavailable to the next, so a repeated phrase cannot double-bind
   (G-24's mutant: remove consumption → duplicate-bind fixture reds).
2. **Distinctive-token floor** — an atom binds only if it matched ≥ `min_tokens` tokens
   (ruled 2026-07-03, P-4: 3) OR ≥1 token unique within the page bag; an atom failing the floor
   is written
   `unmatched(reason="ambiguous")` — **absent, not a plausible wrong bbox**. The cost asymmetry
   justifies the bias: a missing box degrades coverage visibly; a wrong box corrupts S5 re-bind
   silently.
3. **Deterministic order by canonicalization, not emission trust** — at matcher entry the page's
   boxes are sorted by the stable geometric key `(y0, x0, x1, y1, text)` — a total order
   independent of backend emission (which DT-2 leaves contractually unspecified); atoms iterate
   in witness-stream order; token→box assignment is first-available in canonical box order (no
   dict/Counter iteration order anywhere in the path). Result: the bbox is a pure function of
   (witness stream, page box *set*). Determinism red (G-24): run the matcher twice on the same
   fake page with emission order shuffled between runs → byte-identical output required; a mutant
   that skips the canonical sort reds.
4. The run report quantifies the ambiguous-atom residue; if material, the named escalation is
   order-aware locality (neighbor-bounded windows using detector order) — an S2.2-evidence
   decision, not built speculatively now.

**Thresholds (proposals; setting method = full-book distribution in the slice-1 run report,
ratified there, re-gated at S2.2):** page accepted when its atom-weighted match rate ≥ 0.80
(prior: S2.0 content-BoW median 0.929 / mean 0.925); accepted-page atoms write `Geom.matched`
when their own matched fraction ≥ 0.60, else `Geom.absent` + a sidecar reason record; a page
below 0.80 routes to the **worklist** (its atoms stay PENDING — no absent-write until a verdict,
G-12). Known robustness item, documented not solved here: line-break hyphen fragments (`perso-` /
`ne`) — both streams are Tesseract-family on the same scan, so fragments should agree; the run
report quantifies the residue; DT-11's fixture pins the honest v1 behavior (fragments never
*wrongly* bind).

**Absence semantics — the explicit scope split (R10; tracker row amended to match, 2026-07-03):**
the both-decline rule governs **page-level** geometry — a page's geometry is never written off
without a human verdict; routed pages stay pending (G-12). On an **accepted** page, a sub-floor
or zero-match atom writes absent **automatically**, with the reason recorded in the sidecar
(DT-9). Justification: (a) the tracker done-when mandates exactly that ("unmatched →
`geom.present=false`, not invented" — the atom-level rule); (b) per-atom human review breaks the
DT-10 volume bound by orders of magnitude; (c) the blast radius is page-bounded — a page with
many unmatched atoms fails the 0.80 page gate and routes to the human anyway, so a systematic
matcher failure cannot hide behind atom-level auto-absents.

**Auto-absent tripwire (ruled 2026-07-03, P-5 — a second-opinion-sized two-leg form replaces the
earlier flat "5% of book atoms" proposal, which the measured short-atom tail (§2) could trip on
honest residue):** both legs computed over **accepted pages only** from the sidecar's per-atom
records + witness token counts (DT-8-normalizer counts), hard-fail on either:

- **Leg A — token mass:** auto-absent token mass / accepted-page token mass > **0.02**. Sized
  against the measured honest ceiling: the entire ≤3-token furniture tail is 1.3% of token mass,
  so leg A cannot fire on it even at total wipeout — any firing implies real prose mass absent.
- **Leg B — scoped count:** among atoms with ≥4 witness tokens on accepted pages, auto-absent
  rate > **0.05** (≈123 of the 2,451 such atoms ≈ one prose absence every ~2.3 pages —
  systematic, never honest residue). Leg B catches the wide-but-thin failure leg A underweights;
  leg A catches the mass-concentrated one leg B underweights.
- **Warn tier (run report, non-blocking, never thresholded away):** the auto-absent table by
  reason × token band (≤3 / 4–10 / >10) + the accepted-page `match_confidence` histogram;
  informational flag on any band > 1%.

Both constants are value-pin-tested with named-principle failure messages (the G-13 posture);
red row G-26. Retune protocol, pre-committed: tighten at S2.2 if honest residue lands under the
priors; **raise only with a newly named, quantified honest-absence class ratified in the run
report — never to un-fire a trip.** Named blind spots, recorded honestly: (a) a failure confined
to short atoms (headings, dialogue openers) moves leg A ≤1.3 points and is invisible to leg B —
only the warn-tier band table surfaces it; (b) a joint mode threading P-6 (~10% routed) and leg A
(~1.5% mass) evades both guards individually — mitigation is the run report publishing routing
rate beside absent mass; (c) the tripwire sees only *absence* — a confidently-wrong bbox is
G-6/G-24's territory, not a tripwire's.

### DT-9 — Persistence: geometry sidecar, no stream supersession

Geometry is L1 fact (PLAN §3.3 aside at L185), but the frozen streams are what Ben is actively
authoring against — S2.1 does **not** re-emit them. It writes a versioned **sidecar**
`books/<id>/work/data/geometry/{witness}_geom.json` (gitignored `work/data/`, disposable by
convention — regenerable via DT-10's idempotent verdict replay, so the durable record is the
tracked verdict file):

```json
{
  "schema_version": 1,
  "witness_id": "copy1",
  "stream_source_hash": "sha256:…",
  "source_scan": {"kind": "pdf", "sha256": "…", "n_pages": 278, "bytes": 86123456},
  "backend_params": {"dpi": 300, "language": "ita", "pymupdf": "1.27.2.2", "tesseract": "5.5.0"},
  "engine_id": "pymupdf-…+tesseract-…:dpi=300:lang=ita",
  "locate_method": "monotone-align-v1",
  "classifier_version": "density-bands-v1",
  "classifier_params": {"…": "the exact band values used (DT-6)"},
  "pages":  { "52": {"status": "matched", "match_rate": 0.94, "n_cols": 2,
                     "n_cols_source": "evidence", "order_qa": 0.91, "dropped_boxes": 0},
              "6":  {"status": "routed",  "stage": "density", "signal": "band-margin", "value": 0.012},
              "230": {"status": "declined", "verdict": {"action": "decline_geometry", "by": "…", "at": "…"}} },
  "atoms":  { "<copy1_atom_id>":  {"status": "matched", "page": 52, "bbox": [1,2,3,4],
                                   "match_method": "token-bow-v1", "match_confidence": 0.91},
              "<copy1_atom_id2>": {"status": "unmatched", "reason": "below_atom_floor",
                                   "match_confidence": 0.41} },
  "coverage": {"pages_locate_failed": 0, "atoms_unmatched_on_accepted_pages": 12,
               "canonical_no_primary_derivation": 1165, "canonical_multi_primary_derivation": 0}
}
```

**Binding (R11):** `stream_source_hash` alone under-binds — boxes are a function of (scan,
engine, params). `source_scan: {kind, sha256, n_pages, bytes}` uses a `kind` discriminator so a
future image-bundle backend adds `kind: "image-dir"` (`n_pages` = image count, `sha256` over a
canonical bundle manifest) without a rename or schema-version bump. `backend_params` is the
structured contract; `engine_id` stays as derived display (grep/report use). Enforcement points:
**generation** fails loud if the live scan's hash or page count disagrees with an existing
sidecar being regenerated (regen-guard posture); any **seam re-invocation** (S3.1, DT-12)
compares the recorded `source_scan.sha256` against the live scan and fails loud on mismatch
(G-19). `attach_geometry` itself binds stream↔sidecar via `stream_source_hash` — mismatch →
stale fail-loud (G-15). All of these fields join the DT-10 input fingerprint.

**Page records:** `status ∈ {matched, routed, declined}`; a `routed` page's atoms are simply
**absent from `atoms`** (pending ≠ `Geom.absent`); a `declined` page carries the human verdict on
its page record.

**Atom records (R19):** keys are **copy1 per-witness atom ids** — the matcher works witness-side,
keeping the sidecar honest to its `{witness}_geom.json` name. `Geom` has no reason field and
`absent()` is nullary (`atoms.py:84–87`) — the S1.1 slot is frozen, so absence reasons **cannot**
ride on the atom; they live here, which is what S5 loads anyway. Unmatched records carry
`status="unmatched"`, `reason ∈ {zero_match, below_atom_floor, ambiguous}`, and the measured
`match_confidence` (no bbox). The four states S5 must distinguish are all mechanically queryable:
**matched** (bbox), **auto-unmatched** (reason), **pending** (absent-from-map + page `routed`),
**human-declined** (page `declined`).

**`attach_geometry(atoms, sidecar)` — two modes, both tested (R12):** (a) per-witness copy1
stream — direct id lookup; (b) canonical stream — resolve each atom's `derived_from` entries
filtered to `witness == "copy1"` and attach that witness atom's geom. Mode (b) *is* the
implementation of "canonical atom carries its primary witness's box"; S2.2's property test
consumes it — canonical attachment is a required deliverable, not speculation. Attachment
produces new frozen instances at read time; streams untouched. Edges:

- canonical atom with **no copy1 derivation** → `ineligible(no_primary_derivation)`, derived at
  attach from `derived_from` (not persisted per-atom — the copy1-keyed `atoms` map cannot name
  it) + the `coverage.canonical_no_primary_derivation` counter; **never a match-failure reason**
  (DT-13, G-25);
- canonical atom back-linking to **multiple** copy1 atoms → reported
  `unmatched(reason="multi_primary_derivation")` **at attach, canonical mode** — like
  `ineligible`, an attach-time outcome, not a persisted per-atom record (the copy1-keyed `atoms`
  map cannot name a canonical atom, and the persisted per-atom reason enum stays the three
  values above); the durable trace is `coverage.canonical_multi_primary_derivation`. Measured
  zero on the live stream (§2), so the fixture is synthetic-only today and exists to guard
  future re-freezes — a mutant that unions the two or silently picks the first reds (G-20);
- dangling back-links are already `CaptureError`'s jurisdiction at the store tier, not re-checked
  here.

Folding geometry into a superseding stream emission is deferred to when S5 needs it inline — a
sidecar migrates trivially; churning Ben's authoring substrate now doesn't.

### DT-10 — Human-review worklist: specified, not a slogan (audit Finding E)

Home (paths per R7): generated candidates
`books/<id>/work/state/geometry_review/worklist_candidates.json` + on-demand overlay renders
`books/<id>/work/output/geometry_review/overlays/page_NNNN.png` (both in existing ignored work
areas — page image + tentative boxes/split drawn on; nothing added to `_AREAS`, no `.gitignore`
edit, containment already enforced by `BookWorkspace.resolve`); human verdicts land in the
**tracked** `books/<id>/review/geometry_verdicts.json` (sibling of `work/`, like `inputs/`),
which pipeline steps read only. The split is generated-in-`work/`, human-durable-tracked-in-
`review/` — human labor must never live in a disposable tree (the corrections.json-tombstone
failure class from the live pipeline). The verdict CLI writes the tracked file on the human's
behalf — the authoring-tool family (`seed_structure_map.py`, S4.6b gate CLI), outside the step
write-containment contract; its exact plumbing is a #40 build detail.

One record per routed page (replay semantics per R13):

```json
{ "id": "copy1:p0006:density",
  "page": 6, "stage": "density | columns | match",
  "signal": "band-margin | valley-confidence | match-rate", "value": 0.012, "threshold": 0.02,
  "input_fingerprint": "sha256:…",
  "tentative": {"n_cols": 1, "split_x": null, "box_count": 658, "token_count": 7},
  "verdict": null,
  "history": [] }
```

- `id` is stable: `"{witness}:p{page:04d}:{stage}"`.
- `input_fingerprint` = sha256 over (`stream_source_hash`, `source_scan.sha256`, `engine_id`,
  `classifier_version`, band/threshold values) — the same fields DT-6/DT-9 persist.
- `history` accumulates applied verdicts (`by`/`at` from the verdict schema).

**Verdict schema** (human fills; a small CLI applies — reuse of the S4.6b gate-CLI pattern, not a
new HTML sheet): `{"action": "confirm" | "redraw_split" | "reclassify" | "decline_geometry",
"params": {…}, "by": "...", "at": "ISO"}`. `confirm`/`redraw_split`/`reclassify` → the page
re-enters the pipeline with the human's parameters and its result is marked human-reviewed;
`decline_geometry` → the page's atoms get `Geom.absent` — the only **page-level** route to
absent (within an accepted page, sub-floor/zero-match atoms auto-absent with recorded reason —
DT-8's exception, DT-9's record). Unknown action → fail loud (G-14).

**CLI contract, red-tested as G-22:** **idempotent** — same worklist + same verdicts + same
inputs → byte-identical sidecar, and re-applying an already-applied verdict is a no-op;
**stale-guarded** — a verdict whose record fingerprint ≠ the current input fingerprint is refused
and the page re-routed as a fresh record, the old verdict retained in `history` as evidence,
never silently re-applied to different inputs. This is the D14/D21 stale posture applied at the
human boundary. It is also what keeps the sidecar disposable: the tracked verdicts + inputs
deterministically regenerate it.

**Volume bound:** `review_fraction_max` per stage, default **0.15** (ruled 2026-07-03, P-6),
book-config-tunable.
Exceeding it **hard-fails the run** with the named principle: the automation premise failed —
re-design the classifier, never lower the bar to drain the queue (G-13). (Prior: witness-branch
PLL routes only density-abstain + low-match pages; S2.0's numbers predict well under 0.15. The
no-witness branch bound applies to the synthetic fixture proof and future books.)

### DT-11 — CI/test binding: three-tier claim ladder; tesseract in CI; PLL real runs local

The PDF is gitignored and CI has no tesseract — but skipping OCR tests would be skip-masking. The
split is a **claim ladder**: each tier claims only what it runs (R20).

1. **Synthetic-PDF tier (CI, hard-asserted): "the real OCR path executes and honors backend
   contracts"** — existence/fail-loud/coordinate-space, nothing about match quality. A
   **generated synthetic image-only PDF** fixture — pymupdf draws known text (plain ASCII,
   `lang="eng"`), renders each page to a pixmap, and re-embeds the *images* in a fresh PDF (no
   text layer by construction; asserted: `get_text() == ""`). Pages: two-column, single-column,
   near-blank, dark, **plus a rotated-page variant** (G-17's rotation red, R5). The whole path —
   backend OCR, density, columns, order, matcher on a fake witness assembled from the known
   text — runs real. `engine.yml` gains `apt-get install -y tesseract-ocr tesseract-ocr-eng`
   (eng data installed explicitly — whether the base package bundles it is not assumed). English
   here is a **test fixture asset** (like D18's differ-fixture), not a core literal — the fixture
   generator lives under `tests/fixtures/`, language passed as a parameter.
2. **Fake-backend tier (CI, deterministic, zero OCR): "matcher/segmentation semantics hold on
   the adversarial cases."** The fixture inventory (R14): NFC composed vs decomposed accents
   through the DT-8 normalizer (`è` as one codepoint vs `e` + U+0300 must match); edge
   punctuation (guillemets, commas — fixture *data*, not core literals; the neutrality guard
   scans `src/engine/structure/`, not tests); casefold; line-break hyphen fragments
   (`perso-`/`ne` as adjacent boxes vs the witness's joined `persone` — pinning the honest v1
   behavior: fragments do NOT match the joined form, they count as unmatched residue and degrade
   `match_confidence` truthfully, and must never *wrongly* bind); the repeated-common-token page
   + emission-shuffle determinism (G-24); the tie-break fixture (G-7).
3. **The PLL run report (local-only, probe pattern): the ONLY artifact permitted to make quality
   claims about real-book matching** — distributions, threshold ratification, residues. The
   full-book run: `books/per_la_liberta/` runner producing `copy1_geom.json` + a written run
   report (`docs/probes/s2_1_run_report.md`) with the calibration/threshold distributions
   (DT-3/6/8). Real-input tests that need only tracked assets (`inputs/copy3_raw.txt` +
   `copy3_pro_page_map.json`) still run in CI.

Enforcement of tier drift (§7): no G-row may cite the synthetic PDF as evidence for a
matcher-semantics invariant — a semantics row that only reds via the synthetic PDF is mis-homed
and gets moved to a fake-backend fixture.

### DT-12 — S2.2 measurement hooks + S3.1 word-box seam

- **S2.2 (#30)** re-gates S5's geometry mode on the **as-built** detector: mean ordered coverage
  AND per-page pass-rate over n≥30. S2.1 therefore emits, in the run report and sidecar
  (`order_qa` per page), exactly that per-page metric — S2.2 becomes a measurement + ruling, not
  new machinery.
- **S3.1 (D30 Zipf-DP)** needs **word-level** boxes; `atom.geom` stores only the union. No new
  persistence in S2.1 — S3.1 re-invokes the `GeometrySource` seam under an honest replay
  contract (R15): (1) the **structured replay contract** from DT-9 (`source_scan.sha256` +
  `backend_params` with live versions) — re-invocation *verifies* fingerprint match and fails
  loud on drift (G-19), so S3.1 either reproduces on provably-identical inputs or knows it did
  not; (2) a **drift check even on apparent match**: each persisted atom union bbox must ≈ the
  union of the fresh matched word boxes within tolerance — a consistency gate before S3.1 trusts
  word-level geometry against S2.1-era unions; (3) on any mismatch, S3.1's documented options are
  regenerate-under-its-own-engine-id (its geometry, its evidence, recorded as such) or bring
  word-box persistence — which remains its decision to make, with the price tag stated instead
  of an implied free replay.

### DT-13 — Copy2-only canonical atoms: eligibility gate (added round 3, per R3)

Measured on the live streams (2026-07-03): **1165/4786 canonical atoms (24.3%) have no copy1
derivation** (copy2-only; multi-copy1 = 0). Under DT-3's copy1-only ruling these atoms are not
match *failures* — they are **ineligible**: no copy1 witness atom exists for the sidecar to key.
Two admissible outcomes; **one must be ratified before S2.1 closes** (DoD-gating):

- **(a) Per-atom primary witness.** "Primary witness's box" reads per canonical atom: copy1 where
  a copy1 derivation exists, else copy2. Adds a `copy2_geom.json` lane — Harvard-scan
  `source_scan` hash, its own page-locate and calibration argument (copy2 has no ground-truth
  page map either), `matched_witness_id="copy2"`; attach resolves copy1 first, copy2 only for
  copy2-only atoms; no per-atom mixing inside one sidecar.
- **(b) Global copy1, exclusion ratified.** S2.1 geometry coverage explicitly excludes copy2-only
  canonical atoms as a named, accepted loss (a ≥24.3% absent-geometry floor on the canonical
  stream), recorded in the tracker's as-built note; the copy2 lane stays available as a later
  deliverable.

Until ruled, and under either outcome: copy2-only atoms never receive a match-failure reason. They
surface as `ineligible` / `no_primary_derivation` — derived at `attach_geometry` from
`derived_from` (not persisted per-atom in the copy1 sidecar, whose copy1-keyed `atoms` map cannot
name them) — and in `coverage.canonical_no_primary_derivation`. Slice-1 build order is
outcome-neutral: matcher, page-locate, and sidecar are witness-generic under both outcomes.

The eligibility/match-failure separation is red-pinned (G-25): a mutant that reports an ineligible
canonical atom as `zero_match`, or counts it in any match-failure bucket, reds against a fixture
stream containing a copy2-only atom.

## §4 Invariants and red-first matrix

Every row is seen RED against the named violation before the green lands (planted violation or
mutation; `PYTHONDONTWRITEBYTECODE=1` + `__pycache__` purge during hunts). `Geom`'s own
present/absent completeness invariants are S1.1's, already proven — new code constructs only via
the factories and is not re-proven here. Field-*presence* is likewise S1.1's
(`Geom.__post_init__` rejects a present geom with any `None`); the rows below target what the
constructor cannot catch: wrong *values*, wrong *routing*, wrong *state*.

| # | Invariant | RED (named violation) | Home |
|---|-----------|----------------------|------|
| G-1 | backend requires `language`/`dpi` explicitly — no defaults | give either param a default → the no-arg `TypeError` test fails to raise | `test_geometry_backend.py` |
| G-2 | no quoted OCR-language literal in structure core | plant `LANG = "ita"` in a throwaway core file → extended FORBIDDEN scan reds (planted-literal tests inherit the new terms) | `test_structure_neutrality.py` |
| G-3 | matched geom carries all four provenance fields with *configured* values: `geometry_engine` == backend `engine_id` verbatim; `matched_witness_id` == configured anchor witness | fake backend `engine_id="engine-sentinel-77"` + anchor `"witness-sentinel-3"`, **equality** asserted on both fields; two independent hardcode mutants (either field) must red independently | `test_geom_match.py` |
| G-4 | zero-match atom → `Geom.absent`, never an invented box | mutant writes the page bbox for a 0-match atom → reds | `test_geom_match.py` |
| G-5 | `match_confidence == matched/total` (pinned) | mutant returns constant 1.0 → value-pin fixture (known 3-of-5 match = 0.6) reds | `test_geom_match.py` |
| G-6 | union bbox spans matched boxes only | mutant unions ALL page boxes → distractor-box fixture reds on bbox equality | `test_geom_match.py` |
| G-7 | page-locate monotone non-decreasing + deterministic earliest-boundary tie-break | shuffle mutant → monotonicity property reds (synthetic, CI); tie-break fixture (repeated-token run + boundary-straddling furniture, two boundaries tied on score) asserts exact earliest indices — latest-flip mutant reds; copy3-blind ≥95% exact = local run-report gate (PDF not in CI — honest split, DT-11) | `test_geom_match.py` + run report |
| G-8 | every box ⊆ page rect; page-point coords numerically dpi-invariant | OOB synthetic box → `GeometryError`; same word at dpi 150 vs 300 must be equal in page space within ≤0.5 pt/coordinate → quantization-drift mutant reds; cropped-page containment binds the `page.rect` «unverified» (DT-4) | `test_geometry_backend.py` |
| G-9 | density `abstain` routes, never guesses | mutant maps abstain→content → planted mid-band fixture reds | `test_segmentation.py` |
| G-10 | sparse single-column ≠ two-column (contiguous-gutter + populated-halves guards) | remove the ≥3-bin run guard → sparse-page fixture reds | `test_segmentation.py` |
| G-11 | dark low-yield page classed `non_text_dark`, boxes untrusted | mutant trusts high-ink pages → endpaper-style fixture reds | `test_segmentation.py` |
| G-12 | routed page's atoms stay PENDING — no absent-write before verdict | mutant writes `Geom.absent` on route → sidecar-state test reds | `test_geom_sidecar.py` |
| G-13 | review fraction > `review_fraction_max` → hard fail | mutant drops the check → over-quota fixture passes silently, test reds | `test_geom_sidecar.py` |
| G-14 | verdict application total: `decline_geometry`→absent, `confirm`/`redraw`/`reclassify`→re-enter; unknown action → fail loud | mutant treats unknown as confirm → reds | `test_geom_sidecar.py` |
| G-15 | sidecar↔stream binding: `stream_source_hash` mismatch → stale fail-loud | flip one hash byte → `attach_geometry` reds | `test_geom_sidecar.py` |
| G-16 | no-witness branch end-to-end: detector order recovers known text on the synthetic two-column page | break column split → ordered-coverage pin (== 1.0 on synthetic) reds | `test_geometry_e2e.py` |
| G-17 | backend fail-loud: missing tessdata / OCR failure raises; rotated page (`page.rotation != 0`) raises `GeometryError`, never emits coordinates | mutant swallows the exception → reds (monkeypatched failing OCR); mutant proceeds on the rotated-page fixture variant and emits boxes → reds | `test_geometry_backend.py` |
| G-18 | sidecar/worklist loader totality: unknown `schema_version` / missing required key / malformed → `StaleArtifactError`; absent file → `MissingInputError` (shared taxonomy, `errors.py:20–26`) | mutant loader accepting any version → reds | `test_geom_sidecar.py` |
| G-19 | `source_scan` fingerprint mismatch at generation/replay → fail-loud | flip a hash byte / wrong page count → reds | `test_geom_sidecar.py` |
| G-20 | canonical attachment resolves `derived_from(witness=="copy1")`; multi-primary derivation → `unmatched(multi_primary_derivation)`, never a silent union/pick | mutant doing direct canonical-id lookup → disjoint-namespace fixture reds; mutant unioning or picking-first on the two-derivation synthetic fixture → reds | `test_geom_match.py` |
| G-21 | `WordBox`/`PageGeometry` validity: non-finite / degenerate / empty-text / non-positive page unconstructible | mutant drops the `__post_init__` check → reds | `test_geometry_backend.py` |
| G-22 | worklist replay: idempotent re-apply (byte-identical sidecar; re-apply = no-op) + stale-fingerprint verdict refused and re-routed, incl. classifier-version/band drift | mutant applying a stale verdict → reds | `test_geom_sidecar.py` |
| G-23 | cross-page prior scope: own-evidence-outside-margin wins; prior never crosses a non-content/routed page; in-margin disagreeing neighbors → abstain | mutant lets the prior override strong own-page evidence → strong-evidence single-column-between-two-column fixture reds | `test_segmentation.py` |
| G-24 | repeated-token ambiguity + determinism: consumption + distinctive-token floor prevent a plausible-wrong bbox; output invariant to backend emission order | remove consumption → duplicate-bind fixture reds; skip the canonical box sort → emission-shuffled double-run not byte-identical, reds | `test_geom_match.py` |
| G-25 | eligibility ≠ match failure: copy2-only canonical atom surfaces as `ineligible(no_primary_derivation)`, never `zero_match` or any match-failure bucket | mutant reporting an ineligible atom as `zero_match` / counting it in a failure bucket → copy2-only fixture reds | `test_geom_match.py` |
| G-26 | auto-absent tripwire (DT-8, P-5): leg A (>2% token mass) and leg B (>5% of ≥4-token atoms) each hard-fail; the ≤3-token honest class alone can never fire either | mutant drops either leg, mis-scopes the ≥4-token population, or counts routed-page atoms → sized fixtures red; control fixture: total short-tail wipeout must NOT trip (guards the never-fire-on-honest charter) | `test_geom_sidecar.py` |

Not in the table (module-external ripple, DT-1): the exit-code uniqueness sweep extension gets its
own red during #35 — `GeometryError.exit_code` temporarily set to 11 must red the extended sweep.

Post-build: a mutation hunt over the five new core modules — `geom_sidecar.py` explicitly
included; it owns the most load-boundary rows (house discipline) — survivors dispositioned in
the audit note.

## §5 Slices and build order (children of #29)

**Slice 1 — seam, backend, matcher (the witness branch, PLL-productive):**

1. **S2.1.1 (#35)** — `geometry.py`: records + Protocol + `GeometryError` (exit 13 + sweep
   extension with its collision red); fake-backend test double. (G-21 records-side; G-8/G-17
   contract prose.)
2. **S2.1.2 (#36)** — `geometry_pymupdf.py` backend + synthetic image-only PDF fixture generator
   (incl. rotated-page variant) + CI tesseract install. (G-1, G-2, G-8, G-17; DT-11.)
3. **S2.1.3 (#37)** — `geom_match.py`: normalizer, monotone page-locate (+ copy3-blind
   calibration), per-atom window match, `attach_geometry` (both modes); `geom_sidecar.py`
   write/load; the PLL slice-1 run → `copy1_geom.json` + run report with threshold
   distributions. (G-3…G-7, G-12, G-15, G-18, G-19, G-20, G-24, G-25, G-26.)

**Slice 2 — segmentation front-end (trust, order, human loop):**

4. **S2.1.4 (#38)** — density band classifier. (G-9, G-11; DT-6.)
5. **S2.1.5 (#39)** — column/reading-order detector + cross-page prior + two-branch wiring + the
   synthetic no-witness end-to-end. (G-10, G-16, G-23; DT-5/7.)
6. **S2.1.6 (#40)** — worklist + verdict CLI + volume bound + overlay renders; S2.2 measurement
   feed (`order_qa` emitted book-wide). (G-13, G-14, G-22; DT-10/12.)

Within each child: red tests first, then the module, then the mutation pass. Slice 1 makes PLL
geometry real (S3.1/S5.1 unblock); slice 2 completes the tracker's front-end mandate and arms
S2.2.

## §6 Non-goals (defers to)

- The **S2.2 re-gate ruling itself** (#30) — S2.1 emits the measurements; S2.2 rules the S5 mode.
- **S3.1** Zipf-DP segmentation (own plan stub exists); **S5.1** rebind consumption.
- **Stream supersession** with inline geom (DT-9 defers; sidecar first).
- **HTML review sheet** tooling — the deviation-sheet pattern exists for later; slice 2 ships
  JSON worklist + PNG overlays + CLI only.
- **Image-only-book ingestion** — atom capture from OCR text (raw_span/raw_source_hash/capture
  round-trip against the OCR text as witness) is a future lane through S1.3a's machinery, not an
  S2.1 deliverable; the no-witness branch here proves segmentation only (DT-5).
- **The copy2 geometry lane** (`copy2_geom.json`, Harvard-scan boxes) — built only if DT-13 rules
  (a); under (b) it stays a later deliverable. N-way witness geometry beyond that waits for the
  S7.1b word-level link.
- **Word-box persistence** — S3.1's decision to bring (DT-12).

## §7 Verification plan

1. Full suite green (unit + real-input) locally and in CI (with the new tesseract step); ruff
   clean on changed files; neutrality scan green **including the new quoted-language terms**.
2. Red-first matrix: every G-row's red observed and recorded (planted violation or mutant) before
   its green; post-build mutation hunt over the five new modules (incl. `geom_sidecar.py`).
3. **Claim-ladder rule (DT-11):** no G-row may cite the synthetic PDF as evidence for a
   matcher-semantics invariant — a semantics row that only reds via the synthetic PDF is
   mis-homed and gets moved to a fake-backend fixture.
4. Copy3-blind page-locate calibration ≥ the ratified floor, distribution published; below floor
   → S2.1.3 hard-blocks (DT-3's failure route, ruled by Ben — never a silently lowered bar).
5. The PLL slice-1 run report: page match-rate distribution, atoms
   matched/absent/pending/ineligible counts, `coverage` counters, threshold ratification,
   hyphen-fragment residue, ambiguous-atom residue, page-locate wall time, `order_qa`
   distribution (the S2.2 feed); the P-5 warn-tier table (reason × token band + confidence
   histogram) with routing rate published beside absent token mass (the joint-threading watch);
   the ≤5-token calibration-atom exactness distribution (P-1's tighten-to-97% input).
6. Adversarial delta re-audit before each child's commit (house cadence: wide + narrow apertures
   on the delta).

## §8 Definition of done

- All six children (#35–#40) closed; tracker row S2.1 → `DONE` with the as-built note (path
  chosen, evidence numbers, sidecar/worklist homes).
- Tracker done-when satisfied and mapped: seam injectable (S2.1.1 fake backend) · backend yields
  matched boxes + provenance for a PLL page fixture (S2.1.2/3) · unmatched → `geom.present=false`,
  not invented (G-4; G-12/G-14 gate the absent-write; page/atom scope split per DT-8) ·
  low-confidence pages routed to human review (S2.1.6).
- `copy1_geom.json` exists for the real book with the run report; S2.2 (#30) is armed with its
  measurement feed; BR-022 answered by DT-4.
- User ratification of the DT set (this document, audited) precedes any code — **satisfied
  2026-07-03** (post-audit, post-P-rulings; status header).
- **DT-13 ruled (a) or (b)** before the tracker row goes `DONE`: copy2-only canonical atoms are
  either given their per-atom primary-witness lane or their exclusion is explicitly ratified —
  never silently absorbed as match residue (round 3, R3).

**Numeric proposals — ruled independently** (Ben, 2026-07-03: no bundled signature; each number
carries its own ruling). Ledger below; the DT prose stays the definition of record, this table
records the verdicts. A number stays a proposal until ruled, and the child that consumes it
cannot land with an unruled value — the constants are required parameters/test values, so there
is no default to fall back to.

| # | Proposal | DT | Consumed by | Ruling |
|---|----------|----|-------------|--------|
| P-1 | copy3-blind page-locate calibration floor: ≥95% exact | DT-3 | #37 (calibration gate) | **RULED 2026-07-03: 95% for slice 1; re-evaluate at the run report (tighten to 97% if the ≤5-token exactness distribution supports it)** |
| P-2 | DP band B = 3× max page bag (≈1.4K tokens) | DT-3 | #37 (page-locate) | **RULED 2026-07-03: accepted** |
| P-3 | dpi-invariance tolerance ≤0.5 pt/coordinate | DT-4 | #36 (G-8 test) | **RULED 2026-07-03: accepted** |
| P-4 | distinctive-token floor: `min_tokens=3` OR ≥1 page-unique token | DT-8 | #37 (matcher) | **RULED 2026-07-03: accepted as proposed** |
| P-5 | auto-absent tripwire: >5% of book atoms on accepted pages → hard-fail | DT-8 | #37 (slice-1 run gate) | **RULED 2026-07-03: replaced by the two-leg form — leg A >2% token mass + leg B >5% of ≥4-token atoms, accepted pages only, + warn tier (DT-8; red row G-26)** |
| P-6 | `review_fraction_max` = 0.15 per stage | DT-10 | #40 (volume bound) | **RULED 2026-07-03: accepted** |

Separately (unchanged): the **match thresholds 0.80/0.60** (DT-8) and the **hysteresis margins**
(DT-7) are ratified *at the slice-1 run report* against the full-book distributions — proposing
them final now would be measurement-blind.
