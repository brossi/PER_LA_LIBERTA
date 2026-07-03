# S2.1 — GeometrySource seam + backend (NORMAL path) + segmentation front-end (plan)

**Status: DRAFT v1 — three audit rounds complete (2026-07-03): round 1 (@@@@@@/&&&&&&, 21
threads), round 2 (@@@@@!/&&&&&!, 10 open threads), round 3 (@@@@!!/&&&!!!, 3 directives
executed). Round-3 actions: the tracker's both-decline sentence amended to the page-scoped form
(R10); generated review artifacts homed in existing ignored work areas (R7); **DT-13 added** — the
copy2-only eligibility gate, whose (a)/(b) ruling now gates the S2.1 DoD. Awaiting ratification
before any code; accepted amendments (incl. G-18…G-25) fold into the DT/G bodies then.** Parent issue #29 (children #35–#40, minted with
this draft); tracker row `S2.1` in `ENGINE_STRUCTURE_TASKS.md` (~L423) is the authoritative spec — on
any disagreement the tracker wins, then `ENGINE_STRUCTURE_PLAN.md` (§3.0, §11.1, D30), then this
plan. Evidence anchor: `spike/document-structure` @ `08aea65`; every file:line cite below was
verified on disk at that commit.

Inputs this plan consolidates:

- `docs/probes/s2_0_geometry_alignment.md` — the S2.0 probe result + §"S2.1 design inputs"
  (revised post-audit) — and `docs/probes/s2_0_adversarial_audit.md` (Findings B/E/2/5 carried).
- `books/per_la_liberta/probes/s2_0_geometry_probe.py` — the prototype the detector/matcher
  generalize (its `tokens`/`bow_coverage`/`ordered_coverage`/`detect_columns`/`reading_order`).
- The ingestion human-in-the-loop ruling (user, 2026-06-29): classifiers calibrate to **abstain**;
  low-confidence pages route to a human worklist **before** the gate; `geom.present=false` only
  after BOTH auto-detection and human review decline.

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
3. **Witness-text↔geometry matcher** — explicit, fail-loud, writes `{geometry_engine,
   matched_witness_id, match_method, match_confidence}` into S1.1's frozen `Geom` slot; unmatched
   boxes are unusable for primary re-bind; a canonical atom carries its **primary witness's** box
   only where matched.
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
              │
   (4) per-atom match in the page window ── page below threshold ──► worklist
              │ matched
   Geom.matched(union bbox + provenance) ──► geometry sidecar (DT-9)
              │ zero-match atom / declined page
   Geom.absent  (only after auto + human both decline)
```

On the witness branch the matcher is the deliverable that fills `atom.geom`; the detector runs on
every page anyway as the QA cross-check and the **S2.2 measurement feed** (per-page ordered
coverage of detector-ordered boxes vs the witness window — the probe's metric, now emitted by the
build). On the no-witness branch there is no witness to match: the front-end's segmentation
(trusted boxes + reading order + worklist) IS the output, proven on a synthetic fixture (DT-11) —
PLL never exercises this branch, and the engine must not presume it away.

## §2 Surfaces it binds into (verified this session)

- **`src/engine/structure/atoms.py:41`** — `Geom` frozen-slots dataclass: `present` +
  six required-when-present fields (`page`, `bbox`, `geometry_engine`, `matched_witness_id`,
  `match_method`, `match_confidence`); `absent()`/`matched()` factories; absence carries no
  coordinates (invented geometry raises in `__post_init__`). NOTE: the tracker row quoted only
  three provenance fields — the slot has **four** (`matched_witness_id` exists); the matcher
  writes all four (tracker row corrected 2026-07-03 per audit R21). `Atom.geom: Geom` at `:147`.

@@@@@@
**Audit 17 — the four-field provenance correction needs a binding test or tracker edit.** The plan
correctly notices the tracker row under-quotes the frozen `Geom` provenance fields, but it should
not stay only as a note. Add a G-row or acceptance item that a matched geom carries all four
provenance fields, including `matched_witness_id`, and log the tracker wording correction so the
done-when does not keep reintroducing the three-field contract.
@@@@@@

&&&&&&
**R17 — accepted, both halves.** (1) Binding test: folded into **G-3, widened** — the
matcher-written geom must carry all four provenance fields, with `matched_witness_id` equal to the
*configured* anchor witness, sentinel-tested (fake backend + sentinel witness id; a mutant that
hardcodes `"copy1"` or writes the wrong field reds). Note the split of labor: a *missing* field is
already unconstructible — `Geom.__post_init__` raises on any `None` in a present geom
(`atoms.py:69–74`, S1.1's proof, not re-proven) — so the new red targets the failure construction
cannot catch: the matcher writing a *wrong value*. (2) Tracker wording: fixed this turn, see R21.
The §2 NOTE above is amended to record the fix rather than keep asserting a stale mismatch.
&&&&&&

@@@@@!
**Reply R17 - satisfied, with one implementation guard.** The split between S1.1 constructor
completeness and S2.1 matcher-value correctness is sound. Keep the widened G-3 test explicitly
sentinel-driven for both `geometry_engine` and `matched_witness_id`; otherwise a test that only
asserts construction succeeds will not catch a hardcoded witness.
@@@@@!

&&&&&!
**R17 follow-up — assertion shape pinned.** The G-3 test constructs the fake backend with
`engine_id="engine-sentinel-77"` and configures the anchor witness as `"witness-sentinel-3"`, then
asserts **equality** on both `geom.geometry_engine` and `geom.matched_witness_id` against those
exact strings — never merely that construction succeeded. The two mutants (hardcode either field)
must red independently.
&&&&&!

@@@@!!
**Reply R17 follow-up - satisfied.** Independent sentinels plus independent hardcode mutants close
the assertion-shape gap. No further objection.
@@@@!!

@@@@@@
**Audit 21 — tracker minimalism should not preserve a wrong provenance contract.** Leaving the
S2.1 row's three-field `{geometry_engine, match_method, match_confidence}` prose untouched is not
just a harmless minimal edit: it conflicts with the frozen S1.1 `Geom.matched()` contract, which
requires `matched_witness_id`. This sprint should include the tiny tracker wording fix to list all
four fields, plus the matched-geom test, because implementation will otherwise be judged against
two different specs.
@@@@@@

&&&&&&
**R21 — accepted; the tracker edit is applied this turn, not deferred.** The S2.1 row now reads
`{geometry_engine, matched_witness_id, match_method, match_confidence}`
(`ENGINE_STRUCTURE_TASKS.md`, S2.1 spec cell). The two-specs risk was concrete, not stylistic:
`Geom.__post_init__` hard-rejects a present geom missing `matched_witness_id` (`atoms.py:69–74`),
so code written to the tracker's three-field prose would not even construct — the frozen S1.1
contract always was the four-field one, and the tracker prose was the drifted copy. The
matched-geom test is R17's widened G-3.
&&&&&&

@@@@@!
**Reply R21 - satisfied.** Tracker drift is closed now that the S2.1 row names all four frozen
provenance fields and G-3 owns the executable binding. No further objection.
@@@@@!

- **Frozen streams** — `books/per_la_liberta/work/data/atoms/{copy1,copy2,copy3,canonical}.json`
  (written by `freeze_streams.py`): copy1 3621 / copy2 3356 / copy3 799 / canonical 4786 atoms
  (S1.3a oracle-backed pins). Canonical derives from copy1+copy2 only (copy3's word-level link is
  S7.1b), so **"primary witness's box" ⇒ copy1 must be the matched witness** (DT-3). copy1/copy2
  are `PAGE_UNMAPPED`; only copy3 has real page ranges (its `⟨PAGE:N⟩` map, 278 pages).
- **Probe prototype** — `books/per_la_liberta/probes/s2_0_geometry_probe.py`: OCR invocation
  `pg.get_textpage_ocr(flags=0, language=OCR_LANG, dpi=DPI, full=True)` (`:195`); the tokenizer
  (`_EDGE`-strip + lower), BoW/ordered coverage, `detect_columns` (contiguous central valley +
  populated-halves guard), `reading_order`.
- **Neutrality guard** — `tests/unit/test_structure_neutrality.py`: substring, case-insensitive
  scan of `FORBIDDEN` over `structure/` py+schema files, with planted-literal non-vacuity tests.
  Gains the OCR-language literal **in quoted form** (`"ita"` / `'ita'`) — bare `ita` would
  false-positive on English words (`italic`, `vital`) (DT-1).
- **Toolchain** — `engine/pyproject.toml:20` `pymupdf>=1.27.2.2` (already a dep; no pytesseract
  needed). Local tesseract at `/opt/homebrew/bin/tesseract` with `ita` + `ita_old`; tessdata must
  be discoverable (probe docstring). **CI (`.github/workflows/engine.yml`, ubuntu-latest) has no
  tesseract today** and the 82 MB PDF is gitignored — DT-11 owns the split. Tracked-in-CI real
  assets: `data/copy{1,3}_raw.txt`, `data/copy3_page_map.json` (git ls-files verified).
- **S3.1 stub plan** — `docs/s3_1_plan.md` carries Q-S3.1-1/-2; S3.1 consumes word geometry
  through this seam (DT-12).

## §3 Decisions to ratify (DT-1 … DT-13)

### DT-1 — Module homes + neutrality budget

New core modules, all under `src/engine/structure/` (neutral; S0.2 guard extended):

- `geometry.py` — `WordBox` / `PageGeometry` records + the `GeometrySource` Protocol + a
  `GeometryError` (errors-taxonomy citizen, next free exit code).
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

@@@@@@
**Audit 1 — `GeometryError` needs a concrete taxonomy slot before code starts.** "Next free exit
code" is too loose now that structure-owned errors already occupy 11/12 beside the global
`EngineError` taxonomy. Decide whether OCR/backend operational failures reuse `BackendError`
(exit 5) or whether `GeometryError` is a new `EngineError` subclass with a pinned unique exit code
and a uniqueness test. Otherwise different S2.1 modules can surface the same failure as either a
clean typed geometry failure or a generic traceback/backend failure.
@@@@@@

&&&&&&
**R1 — accepted; pinned now, verified against the live taxonomy.** Ruling: `GeometryError(EngineError)`
with **`exit_code = 13`** — the next free code (grep-verified this session: `errors.py` owns 3–10,
`StructureValidationError` 11 at `structure/errors.py:170`, `EvidenceGateError` 12 at
`structure/evidence.py:656`) — living beside its raiser in `geometry.py`, the carrier-beside-vocabulary
posture `errors.py`'s docstring names for 11/12. **Not** a `BackendError` reuse: that class is
ocr-step-owned and its documented contract is the *opposite* posture — per-page failures degrade to
an `[OCR_ERROR]` sentinel (`errors.py:56–61`) — while `GeometryError` is fail-loud with no per-page
degrade (DT-2). Reusing exit 5 would put two contradictory failure contracts under one code.
Boundary inside S2.1: `GeometryError` covers backend/OCR operational failure and geometry integrity
(box outside rect, calibration-gate block, volume-bound breach); the sidecar/worklist **load**
boundaries do NOT use it — they join the existing shared loader taxonomy (absent →
`MissingInputError`, present-but-unloadable/stale → `StaleArtifactError`; `errors.py:18–24`), which
is G-18 (R16). Owned ripples: extend the exit-code uniqueness sweep
(`test_authoring_evidence.py:625`, currently spanning three files) to the fourth file, and update
`errors.py`'s "two structure-owned subclasses" docstring to three.
&&&&&&

@@@@@!
**Reply R1 - satisfied, pending the uniqueness sweep extension.** Exit 13 is the right shape and
the `BackendError` split is correct. The only thing to keep load-bearing is the test update: the
global exit-code uniqueness sweep must include `geometry.py`, or this can regress silently when
another carrier is added beside its raiser.
@@@@@!

&&&&&!
**R1 follow-up — the sweep extension gets its own red so it cannot regress silently.** During #35's
red phase: with `GeometryError.exit_code` temporarily set to 11 (colliding with
`StructureValidationError`), the extended sweep must red — proving it actually sees the fourth
file, not just that 13 happens to be unique today. Then green at 13.
&&&&&!

@@@@!!
**Reply R1 follow-up - satisfied.** The collision mutant proves the sweep includes the new carrier,
not just that `13` is currently free. No further objection.
@@@@!!

`FORBIDDEN` gains `'"ita"'` and `"'ita'"` (quoted forms; the existing planted-literal
parametrization inherits them automatically). pymupdf imports in core are fine — it is already a
required dependency; the neutrality rule governs language/book literals, not libraries.

### DT-2 — `GeometrySource` contract

A backend is a Protocol with one obligation: given a page index range, yield
`PageGeometry{page: int, width: float, height: float, words: tuple[WordBox, ...]}` where
`WordBox{text: str, bbox: (x0, y0, x1, y1)}`, plus an `engine_id: str` property — a
reproducibility string built from live versions and params (shape:
`pymupdf-{ver}+tesseract-{tessver}:dpi={dpi}:lang={lang}`). The matcher writes `engine_id`
**verbatim** into `geometry_engine` — never a hardcoded string (red-first G-3). Fail-loud: missing
tessdata / OCR failure / a box outside the page rect raise `GeometryError`; a backend never
returns silently-empty pages for operational failures (empty ≠ failed: a genuinely blank page
yields zero words *successfully*).

@@@@@@
**Audit 2 — `WordBox` validity is under-specified.** The contract should reject or normalize
`NaN`/`inf`, non-positive boxes (`x1 <= x0` or `y1 <= y0`), empty OCR text, and ambiguous page-index
semantics at the seam, not later in the matcher. It should also state whether backend output order
is raw OCR order or explicitly unspecified, because downstream code must not accidentally treat a
backend's native order as the canonical reading order outside the detector branch.
@@@@@@

&&&&&&
**R2 — accepted; pinned at the seam, two layers, no silent loss.** (1) Record contract:
`WordBox`/`PageGeometry` `__post_init__` rejects non-finite coords, degenerate boxes (`x1 <= x0` or
`y1 <= y0`), empty/whitespace `text`, and non-positive page/width/height — invalid records are
unconstructible (G-21, R16). (2) Backend normalization: Tesseract can emit empty-text/degenerate
artifacts; the backend drops them *before* record construction and counts them in a per-page
`dropped_boxes` stat surfaced in the sidecar page record + run report — dropped-and-counted, never
silently absent. (3) Page semantics pinned at the seam: `PageGeometry.page` is DT-4's 1-based scan
number; the Protocol's range parameters are 1-based inclusive, matching `⟨PAGE:N⟩` /
`page_000N.png`. (4) Order: **contractually unspecified** at the seam — and that is load-bearing by
design, not an omission: page-locate consumes per-page token *bags* (order-free) and the per-atom
match is BoW-within-window, so slice 1 never depends on backend emission order; the only ordered-box
producer is the slice-2 detector, and `order_qa` measures exactly that. A consumer wanting order
must go through `segmentation.reading_order` — treating backend order as reading order has no API
to do it accidentally.
&&&&&&

@@@@@!
**Reply R2 - satisfied.** The record/backend split is clean: invalid constructed records fail loud,
backend artifacts are dropped only with counts, and reading order is explicitly not a seam
guarantee. No further objection.
@@@@@!

### DT-3 — Anchor witness = copy1; page-locate by monotone alignment; copy3-blind calibration

The done-when says a canonical atom carries its **primary witness's** box; canonical derivations
are copy1+copy2 only, and copy1 is the primary structural witness — so **copy1 is the matched
witness** (`matched_witness_id="copy1"`). Problem: copy1 is `PAGE_UNMAPPED` (no page map). Rather
than a page prior, the build derives it: **monotone global alignment** of the (paginated, ordered)
box token stream against copy1's (ordered) token stream — both are in reading order, so page
assignment is a monotone segmentation of the witness stream; per-witness-atom page windows fall
out. Byproduct: **real page ranges for copy1's atoms** — the open S1.3a page-attribution question
gets its answer as derived sidecar data (never a mutation of the frozen stream, D25/DT-9).

@@@@@@
**Audit 3 — copy1-only matching needs an explicit no-fallback rule.** Choosing copy1 as the primary
witness is defensible, but the plan should state what happens when copy1 page-locates or matches
poorly while copy2 would match. If copy2 is deliberately not a fallback, the run report must count
"copy1 failed / secondary not attempted" separately so geometry coverage loss is visible. If copy2
is allowed as fallback, the sidecar and `matched_witness_id` rules need to support per-atom witness
selection rather than a single `{witness}_geom.json` namespace.
@@@@@@

&&&&&&
**R3 — ruling: no copy2 fallback in S2.1; the visibility requirement accepted in full.** The
no-fallback rule is the done-when's own semantics, not just parsimony: the tracker requires the
canonical atom to carry its *primary witness's* box, and a copy2 box on a canonical atom — however
honestly labeled `matched_witness_id="copy2"` — is a different contract that would need a D-level
redefinition first. What lands instead: the run report + sidecar count the loss **separately and by
cause** — pages where copy1 page-locate failed, accepted pages' copy1-unmatched atoms, and canonical
atoms with **no copy1 derivation at all** (copy2-only atoms, structurally unmatchable under this
ruling; the report quantifies how many of the 4786 that is) — each line tagged
`secondary-not-attempted`, so the untried copy2 option stays visible as evidence for a future
ruling rather than silent coverage loss. The `{witness}_geom.json` namespace already admits a
future `copy2_geom.json` without redesign; attach-precedence would be the new decision that ruling
brings with it.
&&&&&&

@@@@@!
**Reply R3 - satisfied, but make the coverage categories part of the run-report schema.** The
no-fallback ruling is coherent. The important enforcement detail is that `copy1 page-locate failed`,
`copy1 atom unmatched`, `copy2-only canonical`, and `secondary-not-attempted` are named fields or
counters in the report, not prose labels that can disappear from the implementation.
@@@@@!

&&&&&!
**R3 follow-up — counters become sidecar schema fields, and a new measured fact raises an open
question for your ratification.** (1) Schema: the counters live in the **sidecar** (the loaded,
schema'd artifact), under a top-level `coverage` object — `pages_locate_failed`,
`atoms_unmatched_on_accepted_pages`, `canonical_no_primary_derivation`,
`canonical_multi_primary_derivation` (R12) — the run report cites them; prose labels cannot drift
out of the implementation because G-18's loader test reads them. (2) The fact, measured this
session on the live canonical stream: **1165 of 4786 canonical atoms (24.3%) have no copy1
derivation at all** (copy2-only; multi-copy1 count is 0). Under the no-fallback ruling those are
born-unmatchable — a quarter of the canonical stream carries guaranteed-absent geometry before any
OCR runs, which is materially more than the "counted edge" flavor of R3 suggested. **Open
question:** does the done-when's "primary witness's box" admit the per-atom reading — a copy2-only
atom's primary (indeed only) witness *is* copy2 — recovering those 1165 via a second
`copy2_geom.json` with honest `matched_witness_id="copy2"` (no per-atom mixing inside one
sidecar)? Honest cost note: copy2's boxes come from the **Harvard scan** — a different physical
copy — so that path needs the second PDF, its own page-locate, and its own calibration argument
(copy2 has no ground-truth page map either). Recommendation: ship slice 1 copy1-only as planned
(the machinery is witness-generic regardless), and rule on the per-atom-primary reading as a
fast-follow once the run report shows real copy1 coverage. The ruling is yours — it reinterprets
the done-when, so I will not take it silently.
&&&&&!

@@@@!!
**Reply R3 follow-up - not satisfied as a fast-follow-only decision.** The 24.3% copy2-only
measurement changes the acceptance shape: copy1-only can still be the first productive slice, but
the final S2.1 plan should not call copy2-only atoms ordinary unmatched residue unless you
explicitly ratify that loss. The plan needs a decision gate with two admissible outcomes: either
define "primary witness" per canonical atom and add a separate `copy2_geom.json` lane with its own
scan hash, page-locate, calibration, and `matched_witness_id="copy2"`; or preserve the global-copy1
reading and state that S2.1 geometry coverage intentionally excludes copy2-only canonical atoms.
Until that ruling lands, use a distinct sidecar reason such as `no_primary_derivation` rather than
`zero_match`/`below_atom_floor`, because those 1165 atoms did not fail matching - they were never
eligible under the copy1-only contract.
@@@@!!

&&&!!!
**R3 round 3 — accepted as a directive; encoded now as DT-13, not deferred to fold.** A new
decision section (after DT-12) carries the gate with exactly your two admissible outcomes: **(a)**
per-atom primary witness + a `copy2_geom.json` lane (own Harvard `source_scan` hash, own
page-locate and calibration argument — copy2 has no ground-truth page map either —
`matched_witness_id="copy2"`, no per-atom mixing inside one sidecar), or **(b)** global-copy1 with
the 24.3% exclusion explicitly ratified and recorded in the as-built note. **S2.1's DoD now
requires DT-13 ruled (a) or (b) before the row goes DONE**; slice-1 stays outcome-neutral (matcher,
page-locate, sidecar are witness-generic under both). Vocabulary accepted, with one placement
correction from the sidecar's own key structure: `no_primary_derivation` is an **eligibility**
state, and it cannot live in the copy1 sidecar's `atoms` map — those keys are copy1 witness atom
ids, which copy2-only canonical atoms do not have. It surfaces where it is derivable and always
current: at `attach_geometry` (canonical mode reports `ineligible(no_primary_derivation)` straight
from `derived_from`) and in the persisted `coverage.canonical_no_primary_derivation` counter. New
red pinning the separation (G-25, folds with R16's set): a mutant that reports an ineligible atom
as `zero_match` — or counts it in any match-failure bucket — reds.
&&&!!!

**Calibration gate (inside slice 1, before trusting copy1 assignments):** run page-locate on
**copy3 blind** (ignore its page map), compare derived pages to the map — the only ground truth we
own. Accept when ≥95% of copy3 body atoms page-locate exactly; publish the distribution in the run
report. (Proposal; the number is Ben's to ratify. copy1's fresh-Tesseract-vs-IA-Tesseract
agreement is expected ≥ copy3's Gemini-vs-Tesseract 0.939 — same engine family, same scan — but
that expectation is *checked* by the run report, not assumed.)

@@@@@@
**Audit 4 — monotone alignment is named but not specified enough to build or falsify.** "Monotone
global alignment" needs a concrete objective: token normalization input, gap/mismatch scoring,
page-break penalty, treatment of repeated headers/furniture, and how ties choose page windows.
The copy3-blind 95% gate also needs a failure route: does S2.1.3 block, fall back to S2.1-alt,
demote geometry for S5, or route pages to review? A monotonicity-only invariant can pass with a
bad but ordered segmentation.
@@@@@@

&&&&&&
**R4 — accepted; the algorithm is now pinned.** **Objective:** given the DT-8-normalized witness
token stream `w[0..N)` and per-page box token bags `B_1..B_K` (pages in scan order), choose
monotone boundaries `0 = c_0 ≤ c_1 ≤ … ≤ c_K = N` maximizing
`Σ_p |multiset_intersect(w[c_{p-1}:c_p), B_p)|` — a banded DP (band from the cumulative-length
ratio), deterministic tie-break to the earliest boundary achieving the max. No separate
gap/mismatch scoring: unmatched tokens (garble, hallucinated boxes) simply score zero.
**Furniture:** the witness stream *contains* furniture atoms (`processing_scope="excluded"`,
`atoms.py:30–35`), so page-locate runs over the full stream — printed folios are page-anchoring
signal, and a furniture atom that matches its printed box gets real geometry, which is fine.
**Monotonicity-only passing a bad segmentation:** agreed — which is why G-7 was written as a pair:
the monotone property (CI, shape) AND the copy3-blind exactness gate (ground truth, quality). Shape
alone was never the acceptance. **Failure route, pinned:** calibration < floor → S2.1.3
**hard-blocks** — no `copy1_geom.json` is published; the run report ships the failure distribution
and the ruling comes to you with the named options: (i) ratify a page±1 tolerance tier with the
floor re-derived, (ii) route the failing page-regions to the DT-10 worklist, (iii) reopen S2.1-alt
(the tracker retains it as the specified conditional). Never a silently lowered bar.
&&&&&&

@@@@@!
**Reply R4 - mostly satisfied; pin the DP complexity and tie-break tests.** The objective is now
buildable. Add an explicit complexity expectation for the banded DP and a deterministic tie-break
fixture with repeated tokens/furniture. Without those, a correct-looking implementation can become
quadratic on the full witness or choose unstable page boundaries across Python/library changes.
@@@@@!

&&&&&!
**R4 follow-up — complexity and determinism pinned, with measured inputs.** Scale, measured this
session: copy1 = **129,767** whitespace tokens across 3,621 atoms, K = 278 pages (~467
tokens/page). **Complexity contract:** the banded DP is `O(N + K·B)` — boundary candidates per
page limited to a band `B` positioned by cumulative-token ratio (proposal: B = 3× the max page bag
size, ≈1.4K tokens), with *incremental* integer multiset scoring (moving a boundary by one token
updates the intersection count in O(1)). That is ~4×10⁵ boundary evaluations for the full book vs
N² ≈ 1.7×10¹⁰ for the quadratic shape — the run report records page-locate wall time so a
complexity regression is visible, and the mutation pass reviews the incremental-update invariant
(no perf assert in CI; timing tests flake). **Determinism:** scores are integers (multiset
intersection counts) — no floats anywhere in the DP — and argmax uses the earliest-boundary
tie-break, so boundaries are a pure function of the two token streams, stable across
Python/platform/library versions. **Committed fixture** (joins G-7's home): a synthetic stream
with a repeated-token run plus a furniture token straddling a boundary, built so two boundary
positions tie on score — asserts the exact (earliest) boundary indices; a mutant flipping the
tie-break to latest reds.
&&&&&!

@@@@!!
**Reply R4 follow-up - satisfied.** The complexity bound, integer scoring, earliest-boundary
tie-break, wall-time reporting, and repeated-token/furniture fixture close the buildability and
determinism gaps. No further objection.
@@@@!!

@@@@@@
**Audit 18 — derived copy1 page attribution needs an ownership boundary.** DT-3 says page-locate
answers the open S1.3a copy1 page-attribution question as sidecar data, but the plan should say
who treats that answer as authoritative and how it is ratified. If it is merely S2.1 geometry
evidence, keep it out of frozen streams and downstream page-range semantics; if it closes an S1.3a
follow-up, add a tracker/doc update pointing to the sidecar-derived pages and their calibration
floor.
@@@@@@

&&&&&&
**R18 — accepted; the ownership boundary already exists in code as a tripwire, and the plan now
cites it instead of drifting past it.** S1.3a.4's
`test_real_canonical_is_uniformly_page_unmapped_until_s7_1b` pins every canonical atom
`PAGE_UNMAPPED (-1,-1)` until **S7.1b**, whose tracker row names canonical page-attribution as its
deliverable (via the copy3↔canonical word-level link). The pin: S2.1's derived pages are **geometry
evidence only** — they live in `Geom.page` (a fact about where the matched *box* sits) and in the
sidecar; `Atom.page_range` (the capture address) stays `PAGE_UNMAPPED`, and the tripwire keeps
enforcing that. Different fields, different meanings — so `attach_geometry` writing `Geom.page=52`
onto a `PAGE_UNMAPPED` atom is the intended state, not a contradiction. Ratifying *adoption*
(page_range semantics) remains S7.1b's; on S2.1 close, the tracker's S1.3a `PAGE_PENDING` deferral
note gains one pointer line: sidecar-derived copy1 pages exist at calibration floor X, adoption
decision unchanged at S7.1b.
&&&&&&

@@@@@!
**Reply R18 - satisfied.** The field split between `Geom.page` and `Atom.page_range` resolves the
ownership boundary. The S1.3a deferral note should point to the sidecar as evidence only, not as an
adopted page-range source. No further objection.
@@@@@!

### DT-4 — Coordinate space + page numbering (BR-022 seed)

`bbox` is in **PDF page-point space** (PyMuPDF `page.rect` units, origin top-left, y-down) — the
one space that is dpi-independent and stable across re-renders. «to verify at build»: that
`get_textpage_ocr` returns page-space (not pixmap-space) coords at dpi≠72 — bound by a test
asserting every box ⊆ `page.rect` at two different dpi values on the synthetic fixture. `page` is
the **1-based scan page number**, consistent with copy3's `⟨PAGE:N⟩` markers and
`docs/assets/page_images/page_000N.png` (pymupdf index + 1); the copy3-blind calibration (DT-3)
doubles as the numbering cross-check (278 markers == 278 pages, S1.3a). This DT is the BR-022
answer-of-record: downstream regions inherit this space or declare a transform.

@@@@@@
**Audit 5 — the proposed coordinate proof is too weak.** "Every box is inside `page.rect` at two
dpi values" does not prove the coordinates are dpi-independent page points; pixmap-space boxes can
still be scaled into the rect and pass containment. Add a test that OCRs the same synthetic page at
two dpi values and compares the same word's bbox numerically in page space within tolerance. Also
pin behavior for rotated/cropped pages or explicitly declare them out of scope for S2.1.
@@@@@@

&&&&&&
**R5 — accepted, with one correction to the threat model.** Raw pixmap-space coords at dpi=300 are
~4.17× page points — containment against a 612×792 rect *would* red on them, so the two-dpi
containment test was not toothless. What it genuinely cannot catch is a library that scales into
page units with dpi-dependent quantization drift (rounded on the pixel grid, then divided). The
numeric test closes that and is strictly stronger, so it replaces the containment-only wording:
OCR the same synthetic page at dpi 150 and 300 and assert the same word's bbox equal in page space
within tolerance (proposal: ≤0.5 pt per coordinate), plus containment. Folded into G-8.
**Rotation/crop: explicitly unsupported in S2.1 — enforced, not assumed.** The backend raises
`GeometryError` on `page.rotation != 0` (both PLL scans are unrotated; a rotated page must fail
loud, never emit wrong coordinates silently). CropBox≠MediaBox: coords are relative to `page.rect`
«unverified that `page.rect` is the cropbox-derived visible rect — bound at build by the same
containment test on a cropped synthetic page».
&&&&&&

@@@@@!
**Reply R5 - satisfied, with crop/rotation covered.** The strengthened same-word numeric
comparison is the right proof, and rejecting rotation in S2.1 is acceptable as long as it is a
tested fail-loud condition. No further objection.
@@@@@!

&&&&&!
**R5 follow-up — rotation rejection becomes a named red, not prose.** The synthetic fixture gains a
rotated-page variant (rotation set on one page of the generated PDF); the backend must raise
`GeometryError` on it — a mutant that proceeds and emits boxes reds. Joins G-17's home
(`test_geometry_backend.py`), listed in the folded matrix rather than left as a DT-4 sentence.
&&&&&!

@@@@!!
**Reply R5 follow-up - satisfied.** A named rotated-page red in G-17 is the right enforcement
point. No further objection.
@@@@!!

### DT-5 — Two-branch reading-order sourcing (where the branch lives)

Book config declares `order_source: witness | geometry`. PLL = `witness` (copy1 column-ordered
0.98): the witness stream supplies order; page windows come from page-locate; the per-atom match
is order-free within the window (BoW), so a column-detector miss cannot corrupt geometry — the
detector still runs on every page as the QA cross-check, emitting per-page
`ordered_coverage(witness_window, detector_ordered_boxes)` into the run report (**this is the
S2.2 measurement feed**, DT-12). `geometry` branch: the detector's order is authoritative, the
worklist is its essential backstop, and the OCR tokens are the text (boxes are theirs by
construction — no matcher needed; the front-end's confidence/worklist output is the deliverable).
Proven on the synthetic fixture; PLL never exercises this branch.

@@@@@@
**Audit 6 — the no-witness branch lacks an L1 integration contract.** Saying "OCR tokens ARE the
text" skips the step that turns detector-ordered boxes into atoms with `raw_span`, `raw_source_hash`,
`page_range`, and `Geom` provenance. If the no-witness branch is only a front-end proof, say it
does not emit atom streams in S2.1. If it does emit atoms, it needs a capture/round-trip contract
compatible with S1.x, not just ordered coverage on a synthetic page.
@@@@@@

&&&&&&
**R6 — accepted; the plan now says it outright: in S2.1 the no-witness branch emits NO atom
streams.** It is a segmentation-front-end proof — trusted boxes + reading order + worklist routing
on the synthetic fixture, measured by G-16's ordered-coverage pin — nothing more. Turning
detector-ordered boxes into L1 atoms (raw_span/raw_source_hash against *what* raw source — the OCR
text itself would be the witness — plus capture tiling and round-trip) is a real capture-contract
design that must go through S1.3a's machinery, and it has no consumer today: PLL never exercises
the branch. That becomes a named §6 non-goal ("image-only-book ingestion: atom capture from OCR
text is a future lane through S1.3a, not an S2.1 deliverable"), so the omission is a recorded
decision, not a gap someone later mistakes for support.
&&&&&&

@@@@@!
**Reply R6 - satisfied.** Declaring the no-witness branch as a segmentation-front-end proof, not an
atom-stream emitter, removes the hidden S1.x contract. No further objection.
@@@@@!

### DT-6 — Density pre-check: band classifier, calibrated to abstain

Audit Finding B stands: single fixed ink threshold is dead (non-monotone continuum; dark endpaper
0.97 > densest prose; 22 real chapter-end pages < the old 0.038 "floor"). The classifier maps
per-page features → `{content, near_blank, non_text_dark, abstain}`:

- Features: ink fraction (binarized pixmap), box count, token yield (alpha-token count / box
  count — p6's hallucination signature is 658 boxes / 7 tokens), mean token length.
- **Two-sided**: `near_blank` (low ink, low token yield) and `non_text_dark` (high ink, low token
  yield) are distinct classes; both mean "boxes untrusted".
- **`abstain` is a first-class output** — the ambiguous middle routes to the worklist, never
  forced into a class. Confidence = margin to the band edges, NOT raw ink fraction (Finding B's
  trap: ink-confidence is maximal on the hallucination-prone dark pages).
- Calibration set: the S2.0 stratified 37 + the audit's boundary pages (chapter ends, endpapers,
  front/back matter), labeled once in the run report. Bands set generously toward abstain — a
  human glance is cheap next to a trusted hallucination.

@@@@@@
**Audit 7 — calibration cannot live only in a run report.** The classifier thresholds and labeled
calibration pages are part of the executable artifact: future reruns need to know whether the
classifier changed or merely the input changed. Persist the feature thresholds, calibration-page
ids, and classifier version either in book config or a governed calibration artifact, and make the
sidecar/run report record the exact version used.
@@@@@@

&&&&&&
**R7 — accepted; calibration becomes a governed artifact and the core stays numberless.** Pin:
`segmentation.py` takes band thresholds as **required constructor parameters with no defaults**
(the G-1 posture again — a baked default band is a scan-profile opinion in core) and exports a
classifier version string (`SEGMENTATION_VERSION = "density-bands-v1"`). PLL's calibrated values
live in book config under `books/per_la_liberta/`; the labeled calibration set (page ids + assigned
bands — the S2.0 stratified 37 + the audit's boundary pages) is a **tracked** input artifact,
`books/per_la_liberta/work/review/density_calibration.json`, which the run report cites rather than
contains. The sidecar records `classifier_version` + the exact band values used, and both join the
R13 input fingerprint — so a rerun distinguishes "classifier changed" from "input changed"
mechanically, and a verdict given under old bands goes stale rather than silently re-applying
(G-22).
&&&&&&

@@@@@!
**Reply R7 - mostly satisfied; do not put generated calibration under `work/` if it must be
tracked.** The governed-artifact approach is right, but `books/per_la_liberta/work/...` is usually
runtime/generated territory and may be gitignored. If `density_calibration.json` is a ratified
input, place it under a tracked config/probes path or explicitly document that this `work/review`
file is committed and governed.
@@@@@!

&&&&&!
**R7 follow-up — verified, you are right, and the objection generalizes further than DT-6.**
Checked this session: `engine/.gitignore:15–20` ignores `books/*/work/{data,output,state}/*` with
the comment "work/ is the isolated, disposable output tree… Regenerable, so never committed", and
`git ls-files` confirms only `.gitkeep`s are tracked under `work/`. `work/review/` happens to be
un-ignored today, but committing governed human labels there would violate the documented
convention — and the same violation was latent in **DT-10**: worklist *verdicts* are human labor,
and homing them in a disposable tree is the corrections.json-tombstone failure class from the live
pipeline. Revised ruling to ratify: **generated-in-work/, human-durable-tracked-in-review/**. A
new tracked `books/<id>/review/` (sibling of `work/`, like `inputs/`) homes the human-authored
artifacts — `density_calibration.json` (labels) and `geometry_verdicts.json` (verdicts +
fingerprints + history) — which pipeline steps *read only*, matching `paths.py`'s contract:
`BookWorkspace.resolve` guards **writes** into `work/` (`paths.py:97–113`) and read-only tracked
siblings are the established pattern (`inputs/`, `paths.py:83–86`). Engine-*generated* review
artifacts stay disposable in `work/review/`: the worklist candidate records and the overlay PNGs.
Band *values* land in `manifest.json` (the tracked book config that already exists). The geometry
sidecar deliberately **stays** in gitignored `work/data/geometry/` — once R13's idempotent replay
lands it is a deterministic function of (PDF × streams × params × tracked verdicts), so the durable
record is the tracked verdict file and the disposable-tree convention holds. The verdict CLI writes
the tracked file on the human's behalf — the authoring-tool family (`seed_structure_map.py`,
S4.6b gate CLI), outside the step write-containment contract; its exact plumbing is a #40 build
detail, the principle above is what needs your ratification. DT-10's paths update at fold.
&&&&&!

@@@@!!
**Reply R7 follow-up - mostly satisfied; generated review paths still need a concrete containment
and ignore rule.** The tracked `books/<id>/review/` sibling for human-authored calibration labels
and verdicts is the right correction, and keeping the replayable sidecar under gitignored
`work/data/geometry/` is defensible. The remaining gap is that `work/review/` is not part of
`BookWorkspace`'s current `_AREAS` and is not ignored by the current `.gitignore`; generated
worklist candidates and overlay PNGs placed there can still become accidental source artifacts.
Either add `review` as a generated work area with matching ignore/.gitkeep coverage, or put those
candidates under an existing ignored area such as `work/state/geometry_review/` and overlays under
`work/output/geometry_review/`.
@@@@!!

&&&!!!
**R7 round 3 — accepted; option (b), no new area.** The generated review artifacts go under the
existing ignored areas with the semantics they actually carry: worklist candidates are step state →
`work/state/geometry_review/worklist_candidates.json`; overlay renders are human-viewable output →
`work/output/geometry_review/overlays/page_NNNN.png`. Nothing added to `_AREAS`, no `.gitignore`
edit, containment already enforced by `BookWorkspace.resolve` — the accidental-source-artifact hole
is closed by placement alone. `work/review/` is dropped from the plan entirely; the tracked
`books/<id>/review/` sibling keeps only the two human-authored files (calibration labels,
verdicts). DT-9/DT-10 path prose updates accordingly at fold.
&&&!!!

### DT-7 — Column / reading-order detector (generalize the probe; cross-page prior; no symmetry)

Promote `detect_columns`/`reading_order` into `segmentation.py` with the audit's rulings baked in:
projection-profile contiguous central valley (≥3 bins) + populated-halves guard (the probe's
sparse-page fix); **mirror-symmetry rule stays DROPPED** (redundant; wrong on asymmetric layouts);
**cross-page prior retained** — layout is locally constant, so a page inherits its neighbor's
class when its own valley evidence is inside a hysteresis margin, and overrides it only on strong
disagreement (margin values proposed in-code, ratified by the run report distribution). Detector
confidence = valley depth × column-balance; below threshold → worklist. Reading order (columns
top-to-bottom, left column first, line-binned by median box height) comes free from the split.

@@@@@@
**Audit 8 — cross-page prior needs reset and abstain rules.** A retained prior can hide exactly the
transition pages S2.0 called out: front/back matter, chapter openings, dark/near-blank pages, and
sparse chapter ends. Define where the prior is allowed to apply, when density/worklist status
resets it, and add a red fixture for a single-column page between two two-column pages. Without
that, "locally constant" becomes a way to propagate a confident wrong layout.
@@@@@@

&&&&&&
**R8 — accepted; the prior gets a scope contract.** (1) It applies only between consecutive
`content`-band pages — the density gate runs first, and any non-content or worklist-routed page
**resets** the chain (a prior must never tunnel through an endpaper or a routed page). (2)
Own-page evidence outside the hysteresis margin always wins — the prior breaks ties *inside* the
margin only, never overrides a confident valley. (3) In-margin with *disagreeing* neighbors (the
transition pages you name: chapter opens, sparse ends) → **abstain to the worklist**, inherit
nothing. (4) Every page records `n_cols_source: "evidence" | "prior"` in its sidecar page record,
so the S2.2 re-gate can measure how often the prior decided and whether prior-decided pages are
where `order_qa` fails. (5) The named red fixture lands as G-23: a strong-evidence single-column
page between two two-column pages — a mutant that lets the prior override strong own-page evidence
reds.
&&&&&&

@@@@@!
**Reply R8 - satisfied.** The prior now has the needed reset, override, abstain, and provenance
rules. No further objection.
@@@@@!

### DT-8 — Matcher: normalizer, window match, confidence formula, thresholds

- **Normalizer** (promoted from the probe, one place, shared by page-locate + matcher): NFC →
  whitespace split → strip edge punctuation → casefold. **No accent stripping, no stopword
  removal** in core (language opinions; the probe's `content_tokens` stays probe-side as a
  metric variant).
- **Per-atom match** (`match_method="token-bow-v1"`): within the atom's page window, greedy
  multiset token matching between atom tokens and box tokens;
  `match_confidence = matched_tokens / atom_tokens` (pinned formula, value-pin tested);
  `bbox` = union over **matched boxes only** (a distractor box never widens the union, G-6);
  `page` = the window's page. Page-locate is recorded page-level in the sidecar as
  `locate_method="monotone-align-v1"`.

@@@@@@
**Audit 9 — BoW atom matching is vulnerable on short/common-token atoms.** A greedy multiset match
inside a page window can confidently bind a short atom to the wrong repeated phrase, especially
when function words are retained and order is ignored. Add a minimum distinctive-token floor,
tie/ambiguity handling, or a monotone/locality constraint, plus a red fixture with repeated common
tokens where the wrong boxes would otherwise meet the 0.60 threshold and produce a plausible but
false bbox.
@@@@@@

&&&&&&
**R9 — accepted as a real failure mode; mitigation pinned, with the never-invent posture doing the
heavy lifting.** V1 mechanism: (1) **multiset box-token consumption** — atoms match in witness
order within the page and a box token consumed by one atom is unavailable to the next, so a
repeated phrase cannot double-bind (G-24's mutant: remove consumption → duplicate-bind fixture
reds); (2) **distinctive-token floor** — an atom binds only if it matched ≥ `min_tokens` tokens
(proposal: 3) OR ≥1 token unique within the page bag; an atom failing the floor is written
`unmatched(reason="ambiguous")` — **absent, not a plausible wrong bbox**. The cost asymmetry
justifies the bias: a missing box degrades coverage visibly; a wrong box corrupts S5 re-bind
silently. (3) The run report quantifies the ambiguous-atom residue; if material, the named
escalation is order-aware locality (neighbor-bounded windows using detector order) — an
S2.2-evidence decision, not built speculatively now. The G-24 red fixture is exactly the one you
specify: repeated common tokens that would clear 0.60 — under consumption + floor they must not
bind.
&&&&&&

@@@@@!
**Reply R9 - mostly satisfied; define the consumption order.** Box-token consumption is the right
defense, but it needs a deterministic order over atoms and boxes inside a page. Tie that to witness
atom order plus stable box ordering from the page-locate/detector input, or repeated-token fixtures
can still produce nondeterministic bboxes.
@@@@@!

&&&&&!
**R9 follow-up — deterministic order pinned by canonicalization, not by trusting emission.** At
matcher entry the page's boxes are sorted by the stable geometric key `(y0, x0, x1, y1, text)` — a
total order independent of backend emission (which R2 left contractually unspecified, so the
matcher must not lean on it); atoms iterate in witness-stream order; token→box assignment is
first-available in canonical box order, consumed by scanning the sorted list (no dict/Counter
iteration order anywhere in the path). Result: the bbox is a pure function of (witness stream,
page box *set*). New determinism red joining G-24's home: run the matcher twice on the same fake
page with emission order shuffled between runs → byte-identical output required; a mutant that
skips the canonical sort reds.
&&&&&!

@@@@!!
**Reply R9 follow-up - satisfied.** Canonical box sorting plus the emission-shuffle red closes the
nondeterminism risk without relying on backend order. No further objection.
@@@@!!

- **Thresholds (proposals; setting method = full-book distribution in the slice-1 run report,
  ratified there, re-gated at S2.2):** page accepted when its atom-weighted match rate ≥ 0.80
  (prior: S2.0 content-BoW median 0.929 / mean 0.925); accepted-page atoms write `Geom.matched`
  when their own matched fraction ≥ 0.60, else `Geom.absent` + a report line; a page below 0.80
  routes to the **worklist** (its atoms stay PENDING — no absent-write until a verdict, G-12).
  Known robustness item, documented not solved here: line-break hyphen fragments (`perso-` / `ne`)
  — both streams are Tesseract-family on the same scan, so fragments should agree; the run report
  quantifies the residue.

@@@@@@
**Audit 10 — atom-level absent writes contradict the human-decline rule.** The header and tracker
say `geom.present=false` only after both automation and human review decline, but DT-8 lets an
accepted page write `Geom.absent` for any atom below 0.60 with no human verdict. If that exception
is intentional, name it as an explicit exception and justify why atom-level auto-decline is safe.
Otherwise low-confidence atoms on an accepted page need their own pending/review state, not an
immediate absent write.
@@@@@@

&&&&&&
**R10 — partial pushback on the premise; the fix accepted.** The tension is not between this plan
and the tracker — it sits *inside the tracker row itself*, verbatim: the done-when mandates
"unmatched → `geom.present=false`, not invented" (atom-level, no human in the sentence), while the
row prose says "`geom.present=false` only after BOTH auto-detection and human review decline" —
and that sentence lives in the front-end/worklist paragraph, i.e. page context. The coherent
reading is scope-split, and the plan now states it as the explicit exception you ask for: the
both-decline rule governs **page-level** geometry (a page's geometry is never written off without
a human verdict — routed pages stay pending, G-12); on an **accepted** page, a sub-floor or
zero-match atom writes absent **automatically**. Justification: (a) the done-when mandates exactly
that; (b) per-atom human review breaks the DT-10 volume bound by orders of magnitude; (c) the
blast radius is page-bounded — a page with many unmatched atoms fails the 0.80 page gate and
routes to the human anyway, so a systematic matcher failure cannot hide behind atom-level
auto-absents. Guard on the residue: auto-absent atoms get R19's reason records plus a proposed
tripwire — auto-absent fraction on accepted pages > 5% of book atoms (proposal, yours to ratify)
→ hard-fail, same principle as the review volume bound. §0/§1's "both decline" wording is amended
to the page-scoped form.
&&&&&&

@@@@@!
**Reply R10 - satisfied, subject to wording cleanup.** The page-level versus atom-level split is
coherent and the 5% auto-absent tripwire is the right safety valve. Make sure §0/§1 and DT-8 use
that exact scope split, because leaving the older absolute "both auto and human decline" sentence
beside the exception will recreate this ambiguity.
@@@@@!

&&&&&!
**R10 follow-up — the surviving absolute sentences are enumerated, and one open item is the
tracker's own copy.** Grep-verified: the absolute form survives at three places in this document —
the header inputs (L18), the §1 diagram's absent-leg (L66), and DT-10's "satisfying …" clause — all
three get the page-scoped form at fold: *"a page's geometry is declined only after both
auto-detection and a human verdict; within an accepted page, unmatched atoms auto-absent with
recorded reason (DT-8 exception, R19 record)."* **Open item for you:** the tracker row itself still
ends with the absolute sentence, and the row is the authoritative spec. Proposed amendment (yours
to apply or defer to the S2.1-close as-built note): "page-level `geom.present=false` only after
BOTH auto-detection and human review decline; atom-level absence on an accepted page is
automatic-with-recorded-reason (s2_1_plan R10/R19)." I have not touched the row — unlike R21's
factual under-quote, this one changes normative spec wording, which is yours.
&&&&&!

@@@@!!
**Reply R10 follow-up - not satisfied if the tracker remains open through implementation.** The
document cleanup is enough for the plan artifact, but the tracker row is the authoritative sprint
contract. Leaving its absolute sentence in place recreates the two-spec problem R21 just removed,
except this time around absence semantics. I would apply the proposed tracker amendment before
implementation starts, or at minimum add an explicit tracker note that S2.1 implementation follows
the page-scoped R10/R19 wording until the row is amended.
@@@@!!

&&&!!!
**R10 round 3 — applied, this commit.** The tracker row's closing sentence now reads: "Page-level
`geom.present=false` only after BOTH auto-detection and human review decline; atom-level absence on
an accepted page is automatic-with-recorded-reason (s2_1_plan R10/R19)." The done-when cell's
"unmatched → `geom.present=false`, not invented" stands unchanged — under the scope split it *is*
the atom-level mandate, no longer in tension with the row prose. Both surfaces of the two-spec
problem are closed before implementation starts.
&&&!!!

@@@@@@
**Audit 19 — if zero-match auto-absent remains, preserve its reason.** The coworker summary treats
"zero-match atom on an accepted page" as a legitimate second route to `Geom.absent`; that can work
only if the sidecar records it distinctly from `decline_geometry`. Otherwise S5 cannot tell
"human reviewed and declined page geometry" from "automatic atom-level miss inside an accepted
page." Add an explicit per-atom absence reason/status or route zero-match atoms to review.
@@@@@@

&&&&&&
**R19 — accepted; and the frozen model forces where the reason lives.** `Geom` has no reason field
and `absent()` is nullary (`atoms.py:84–87`) — the S1.1 slot is frozen, so the reason **cannot**
ride on the atom; it lives in the sidecar, which is what S5 loads anyway. Pin: sidecar per-atom
records carry `status ∈ {matched, unmatched}`, with `reason ∈ {zero_match, below_atom_floor,
ambiguous}` and the measured `match_confidence` on unmatched records (no bbox); a routed page's
atoms stay absent from the map entirely (pending); a declined page carries the human verdict on its
page record. So the four states S5 must distinguish are all mechanically queryable: **matched**
(bbox), **auto-unmatched** (reason), **pending** (absent-from-map + page `routed`),
**human-declined** (page `declined`). DT-9's schema sketch gains the unmatched-record shape on
fold.
&&&&&&

@@@@@!
**Reply R19 - satisfied.** Keeping absence reasons in the sidecar rather than `Geom` respects the
frozen S1.1 model and gives S5 enough state to distinguish matched, auto-unmatched, pending, and
human-declined. No further objection.
@@@@@!

### DT-9 — Persistence: geometry sidecar, no stream supersession

Geometry is L1 fact (PLAN §3.3 aside at L185), but the frozen streams are what Ben is actively
authoring against — S2.1 does **not** re-emit them. It writes a versioned **sidecar**
`books/<id>/work/data/geometry/{witness}_geom.json`:

```json
{
  "schema_version": 1,
  "witness_id": "copy1",
  "stream_source_hash": "sha256:…",          // stale fail-loud on mismatch, D14/D21 pattern
  "engine_id": "pymupdf-…+tesseract-…:dpi=300:lang=ita",
  "locate_method": "monotone-align-v1",
  "pages":  { "52": {"status": "matched", "match_rate": 0.94, "n_cols": 2, "order_qa": 0.91},
              "6":  {"status": "routed",  "stage": "density", "signal": "band-margin", "value": 0.012} },
  "atoms":  { "<atom_id>": {"page": 52, "bbox": [x0,y0,x1,y1],
                            "match_method": "token-bow-v1", "match_confidence": 0.91} }
}
```

Page `status ∈ {matched, routed, declined}`; a `routed` page's atoms are simply **absent from
`atoms`** (pending ≠ `Geom.absent`). `attach_geometry(atoms, sidecar)` overlays `Geom.matched`
onto matching atom ids at read time (new frozen instances; streams untouched); hash mismatch →
fail-loud stale error. Folding geometry into a superseding stream emission is deferred to when S5
needs it inline — a sidecar migrates trivially; churning Ben's authoring substrate now doesn't.

@@@@@@
**Audit 11 — sidecar binding is missing the source image/PDF identity.** `stream_source_hash`
guards the witness text, but the boxes are generated from a scan PDF plus OCR parameters. A stale
or swapped PDF can still match the same witness hash and produce different coordinates. Persist the
source PDF/artifact hash, page count, OCR dpi/language, and ideally a structured backend-param
object in addition to the human-readable `engine_id`; fail loud when any of those do not match.
@@@@@@

&&&&&&
**R11 — accepted in full; the witness hash alone under-binds.** The boxes are a function of
(PDF, engine, params), so the sidecar gains: `source_pdf: {sha256, n_pages, bytes}` and a
structured `backend_params: {dpi, language, pymupdf, tesseract}` beside the human-readable
`engine_id` (which stays, for grep/report use — it is now derived display, the structured object
is the contract). Enforcement points: **generation** fails loud if the live PDF's hash or page
count disagrees with an existing sidecar being regenerated (regen-guard posture); any **seam
re-invocation** (S3.1, R15) must compare the recorded `source_pdf.sha256` against the live PDF and
fail loud on mismatch — a one-shot hash of the local file, not a burden. `attach_geometry` itself
binds stream↔sidecar (its job); PDF identity is generation/replay-side, recorded so every consumer
*can* check. All of these fields join the R13 input fingerprint. New red: G-19.
&&&&&&

@@@@@!
**Reply R11 - satisfied, with one naming precision.** The structured replay contract closes the
under-binding. Use `source_pdf` only if S2.1 is truly PDF-only; otherwise name it `source_scan` or
`geometry_source_artifact` so the seam can later support image bundles without a schema rename.
@@@@@!

&&&&&!
**R11 follow-up — ruling: `source_scan` with a `kind` discriminator.**
`source_scan: {kind: "pdf", sha256, n_pages, bytes}` — your generic-name point taken; a future
image-bundle backend adds `kind: "image-dir"` (with `n_pages` as image count and `sha256` over a
canonical manifest of the bundle) without a rename or schema-version bump. The `engine_id` display
string is unchanged.
&&&&&!

@@@@!!
**Reply R11 follow-up - satisfied.** `source_scan.kind` preserves the PDF contract without naming
the schema into a corner. No further objection.
@@@@!!

@@@@@@
**Audit 12 — atom-id namespace is ambiguous.** The path is `{witness}_geom.json`, but
`attach_geometry(atoms, sidecar)` sounds generic and the done-when talks about canonical atoms
carrying the primary witness's box. State whether `atoms` keys are copy1 witness atom ids or
canonical atom ids. If witness-keyed, attaching to canonical atoms must walk `derived_from` and
handle multi-source canonical atoms explicitly; if canonical-keyed, `witness_id` is provenance
only and the sidecar is not really per-witness.
@@@@@@

&&&&&&
**R12 — accepted; pinned, and the model already carries the needed link (verified this session).**
`Atom.derived_from: tuple[AtomDerivation, ...]` with `AtomDerivation{witness, atom_id}`
(`atoms.py:116–122, :150`). Ruling: sidecar `atoms` keys are **copy1 per-witness atom ids** — the
matcher works witness-side, which keeps the sidecar honest to its `{witness}_geom.json` name.
`attach_geometry` gets a two-mode contract, both tested: (a) per-witness copy1 stream — direct id
lookup; (b) canonical stream — resolve each atom's `derived_from` entries filtered to
`witness == "copy1"` and attach that witness atom's geom. Mode (b) *is* the implementation of
"canonical atom carries its primary witness's box", and S2.2's property test ("primary-witness box
on canonical atoms where matched") consumes it — canonical attachment is a required deliverable,
not speculation. Edges: a canonical atom with no copy1 derivation → geom stays absent, counted
under R3's `secondary-not-attempted` line; a canonical atom back-linking to *multiple* copy1 atoms
→ absent + counted in v1, with the run report establishing whether the case even exists before any
union-merge machinery is built; dangling back-links are already `CaptureError`'s jurisdiction at
the store tier and are not re-checked here. New red: G-20 (mutant doing direct canonical-id lookup
→ disjoint-namespace fixture reds).
&&&&&&

@@@@@!
**Reply R12 - mostly satisfied; multi-copy1 derivations need an explicit red or report field.**
Witness-keyed storage plus canonical `derived_from` attachment is the right model. For canonical
atoms with multiple copy1 derivations, either add a fixture proving v1 marks them unmatched or add
a report counter; otherwise the "absent + counted" edge may be skipped because it is thought not to
exist.
@@@@@!

&&&&&!
**R12 follow-up — both, not either; and "thought not to exist" is now a measured fact instead of a
guess.** (a) The fixture: a synthetic canonical atom with two copy1 derivations → v1 marks it
`unmatched(reason="multi_primary_derivation")`; a mutant that unions the two or silently picks the
first reds (joins G-20's home). (b) The counter: `coverage.canonical_multi_primary_derivation` in
the sidecar (R3's schema), so the count is proven on every run. Measured this session on the live
canonical stream: **zero** multi-copy1 atoms across all 4,786 — so the fixture is synthetic-only
today and exists to guard future re-freezes, and the counter turns the zero into an assertion
rather than an assumption. (Same scan produced the 1165 no-copy1 count now sitting in the R3
follow-up as the open per-atom-primary question.)
&&&&&!

@@@@!!
**Reply R12 follow-up - satisfied, with R3 as the remaining parent decision.** The synthetic
multi-primary fixture plus a live-run counter is the right treatment for a currently-zero edge.
The only unresolved issue is not multi-copy1 handling; it is R3's measured copy2-only population
and whether those atoms get their own primary-witness lane.
@@@@!!

### DT-10 — Human-review worklist: specified, not a slogan (audit Finding E)

Home: `books/<id>/work/review/geometry_worklist.json` (+ on-demand overlay renders
`work/review/overlays/page_NNNN.png`, gitignored — page image + tentative boxes/split drawn on).
One record per routed page:

```json
{ "page": 6, "stage": "density | columns | match",
  "signal": "band-margin | valley-confidence | match-rate", "value": 0.012, "threshold": 0.02,
  "tentative": {"n_cols": 1, "split_x": null, "box_count": 658, "token_count": 7},
  "verdict": null }
```

**Verdict schema** (human fills; a small CLI applies — reuse of the S4.6b gate-CLI pattern, not a
new HTML sheet): `{"action": "confirm" | "redraw_split" | "reclassify" | "decline_geometry",
"params": {…}, "by": "...", "at": "ISO"}`. `confirm`/`redraw_split`/`reclassify` → the page
re-enters the pipeline with the human's parameters and its result is marked human-reviewed;
`decline_geometry` → the page's atoms get `Geom.absent` — the ONLY route to absent besides a
zero-match atom on an accepted page, satisfying "absent only after both auto and human decline".
Unknown action → fail loud (G-14).

@@@@@@
**Audit 13 — worklist verdicts need replay and staleness semantics.** The record lacks a stable
record id, input sidecar/run id, source PDF hash, classifier version, and status transition history.
Without those, a verdict can be applied to a different OCR run or applied twice with different
effects. The CLI should be idempotent: same worklist + same verdicts + same inputs yields the same
sidecar, while any input/calibration drift marks old verdicts stale and routes them back through
review.
@@@@@@

&&&&&&
**R13 — accepted in full; the record and CLI get replay semantics.** Each worklist record gains:
`id` (stable: `"{witness}:p{page:04d}:{stage}"`), `input_fingerprint` = sha256 over
(`stream_source_hash`, `source_pdf.sha256`, `engine_id`, `classifier_version`, band/threshold
values — the same fields R7/R11 persist), and a `history` list of applied verdicts (`by`/`at`
already in the verdict schema). CLI contract, red-tested as G-22: **idempotent** — same worklist +
same verdicts + same inputs → byte-identical sidecar, and re-applying an already-applied verdict is
a no-op; **stale-guarded** — a verdict whose record fingerprint ≠ the current input fingerprint is
refused and the page re-routed as a fresh record, the old verdict retained in `history` as evidence,
never silently re-applied to different inputs. This is the D14/D21 stale posture applied at the
human boundary.
&&&&&&

@@@@@!
**Reply R13 - satisfied.** Stable ids, input fingerprints, history, idempotent replay, and stale
verdict refusal cover the worklist lifecycle. No further objection.
@@@@@!

**Volume bound:** `review_fraction_max` per stage, default **0.15**, book-config-tunable.
Exceeding it **hard-fails the run** with the named principle: the automation premise failed —
re-design the classifier, never lower the bar to drain the queue. (Prior: witness-branch PLL
routes only density-abstain + low-match pages; S2.0's numbers predict well under 0.15. The
no-witness branch bound applies to the synthetic fixture proof and future books.)

### DT-11 — CI/test binding: synthetic image-only PDF + tesseract in CI; PLL real runs local

The PDF is gitignored and CI has no tesseract — but skipping OCR tests would be skip-masking. The
split:

- **CI-provable (hard-asserted, runs everywhere):** a **generated synthetic image-only PDF**
  fixture — pymupdf draws known text (plain ASCII, `lang="eng"`), renders each page to a pixmap,
  and re-embeds the *images* in a fresh PDF (no text layer by construction; asserted:
  `get_text() == ""`). Pages: two-column, single-column, near-blank, dark. The whole path —
  backend OCR, density, columns, order, matcher on a fake witness assembled from the known text —
  runs real. `engine.yml` gains `apt-get install -y tesseract-ocr tesseract-ocr-eng` (eng data
  installed explicitly — whether the base package bundles it is not assumed).
  English here is a **test fixture asset** (like D18's differ-fixture), not a core literal — the
  fixture generator lives under `tests/fixtures/`, language passed as a parameter.
- **Local-only (probe pattern, honest about absence):** the full-book PLL run —
  `books/per_la_liberta/` runner producing `copy1_geom.json` + a written run report
  (`docs/probes/s2_1_run_report.md`) with the calibration/threshold distributions (DT-3/6/8).
  Real-input tests that need only tracked assets (copy3 raw + page map) still run in CI.
- **Unit tier:** matcher/page-locate/segmentation tested against fake `GeometrySource`
  implementations (deterministic boxes, no OCR at all).

@@@@@@
**Audit 14 — the CI fixture risks proving only the easy OCR path.** An English ASCII synthetic PDF
is useful for the backend smoke, but it will not exercise the Italian/accent/NFC normalization path,
hyphen fragments, or repeated-token ambiguity that drive the real matcher risk. Add OCR-free fake
backend unit fixtures for accented tokens, edge punctuation, line-break hyphens, and duplicate
phrases so those semantics are CI-bound even though the PLL PDF remains local-only.
@@@@@@

&&&&&&
**R14 — accepted; the hard-semantics cases move to OCR-free fake-backend fixtures, CI-bound.**
The fixture inventory (lands in DT-11 on fold): NFC composed vs decomposed accents through the
DT-8 normalizer (`è` as one codepoint vs `e` + U+0300 must match); edge punctuation (guillemets,
commas — fixture *data*, not core literals; the neutrality guard scans `src/engine/structure/`,
not tests); casefold; line-break hyphen fragments (`perso-`/`ne` as adjacent boxes vs the
witness's joined `persone` — pinning the honest v1 behavior: fragments do NOT match the joined
form, they count as unmatched residue and degrade `match_confidence` truthfully, and must never
*wrongly* bind); and the repeated-common-token page (G-24). All exercise `geom_match` semantics
deterministically with zero OCR. The synthetic PDF keeps only what genuinely needs a real OCR
pass: the G-1/G-8/G-17 backend contracts and the G-16 order path.
&&&&&&

@@@@@!
**Reply R14 - satisfied.** The split between backend smoke and deterministic matcher semantics is
clean, and the fake-backend fixture inventory covers the missing Unicode/hyphen/repetition cases.
No further objection.
@@@@@!

@@@@@@
**Audit 20 — keep the CI OCR smoke from becoming the matcher-quality proof.** The synthetic
image-only PDF is the right anti-skip fixture for the backend, but its generated text can make OCR
too clean and layout too controlled. The plan should separate "real OCR path executes in CI" from
"matcher semantics are covered" and require the fake-backend fixtures to own the hard cases. The
run report then remains the only claim about PLL-quality matcher performance.
@@@@@@

&&&&&&
**R20 — accepted; stated as a three-tier claim ladder, each tier claiming only what it runs.**
(1) Synthetic-PDF tier: "the real OCR path executes and honors backend contracts" —
existence/fail-loud/coordinate-space, nothing about match quality. (2) Fake-backend tier:
"matcher/segmentation semantics hold on the adversarial cases" (R14's inventory) — CI-bound,
deterministic. (3) The PLL run report: the **only** artifact permitted to make quality claims
about real-book matching (distributions, threshold ratification, residues). Enforcement of the
drift you name, added to §7: no G-row may cite the synthetic PDF as evidence for a
matcher-semantics invariant — a semantics row that only reds via the synthetic PDF is
mis-homed and gets moved to a fake-backend fixture.
&&&&&&

@@@@@!
**Reply R20 - satisfied.** The three-tier claim ladder prevents the synthetic PDF from being
over-read as quality evidence. No further objection.
@@@@@!

### DT-12 — S2.2 measurement hooks + S3.1 word-box seam

- **S2.2 (#30)** re-gates S5's geometry mode on the **as-built** detector: mean ordered coverage
  AND per-page pass-rate over n≥30. S2.1 therefore emits, in the run report and sidecar
  (`order_qa` per page), exactly that per-page metric — S2.2 becomes a measurement + ruling, not
  new machinery.
- **S3.1 (D30 Zipf-DP)** needs **word-level** boxes; `atom.geom` stores only the union. No new
  persistence: S3.1 re-invokes the `GeometrySource` seam (the sidecar's `engine_id` + params make
  the re-run reproducible modulo tesseract version, which is recorded). If S3.1's cost profile
  demands word-box persistence, that is its decision to bring — the seam is the contract.

@@@@@@
**Audit 15 — S3.1 reproducibility is weaker than stated if word boxes are not persisted.** An
`engine_id` string plus params is not enough to re-run the same word-box layer after a Tesseract,
tessdata, PyMuPDF, source-PDF, or calibration change. If S3.1 is expected to re-invoke the seam,
the sidecar/run report must expose a structured replay contract and source artifact hash; otherwise
S3.1 should either consume persisted word boxes or explicitly accept that its geometry input may
differ from the S2.1 union boxes.
@@@@@@

&&&&&&
**R15 — accepted; DT-12's claim was over-strong as written and is now honest.** An `engine_id`
string alone cannot re-produce boxes across a tesseract/tessdata/PyMuPDF/PDF change. What S3.1
actually gets: (1) the **structured replay contract** from R11 (`source_pdf.sha256` +
`backend_params` with live versions) — re-invocation *verifies* fingerprint match and fails loud
on drift, so S3.1 either reproduces on provably-identical inputs or knows it did not; (2) a
**drift check even on apparent match**: each persisted atom union bbox must ≈ the union of the
fresh matched word boxes within tolerance — a consistency gate before S3.1 trusts word-level
geometry against S2.1-era unions; (3) on any mismatch, S3.1's documented options are
regenerate-under-its-own-engine-id (its geometry, its evidence, recorded as such) or bring
word-box persistence — which remains its decision to make, now with the honest price tag stated
instead of an implied free replay.
&&&&&&

@@@@@!
**Reply R15 - satisfied.** The replay contract plus union-bbox consistency gate is honest about
what S3.1 can reproduce and where a rerun becomes new evidence. No further objection.
@@@@@!

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

New red (**G-25**, folds with R16's set): eligibility/match-failure separation — a mutant that
reports an ineligible canonical atom as `zero_match`, or counts it in any match-failure bucket,
reds against a fixture stream containing a copy2-only atom. Home: `test_geom_match.py`.

## §4 Invariants and red-first matrix

Every row is seen RED against the named violation before the green lands (planted violation or
mutation; `PYTHONDONTWRITEBYTECODE=1` + `__pycache__` purge during hunts). `Geom`'s own
present/absent completeness invariants are S1.1's, already proven — new code constructs only via
the factories and is not re-proven here.

| # | Invariant | RED (named violation) | Home |
|---|-----------|----------------------|------|
| G-1 | backend requires `language`/`dpi` explicitly — no defaults | give either param a default → the no-arg `TypeError` test fails to raise | `test_geometry_backend.py` |
| G-2 | no quoted OCR-language literal in structure core | plant `LANG = "ita"` in a throwaway core file → extended FORBIDDEN scan reds (planted-literal tests inherit the new terms) | `test_structure_neutrality.py` |
| G-3 | `geometry_engine` = backend's `engine_id` verbatim | mutant hardcodes the string → fake-backend fixture with sentinel id reds | `test_geom_match.py` |
| G-4 | zero-match atom → `Geom.absent`, never an invented box | mutant writes the page bbox for a 0-match atom → reds | `test_geom_match.py` |
| G-5 | `match_confidence == matched/total` (pinned) | mutant returns constant 1.0 → value-pin fixture (known 3-of-5 match = 0.6) reds | `test_geom_match.py` |
| G-6 | union bbox spans matched boxes only | mutant unions ALL page boxes → distractor-box fixture reds on bbox equality | `test_geom_match.py` |
| G-7 | page-locate assignments monotone non-decreasing | shuffle mutant → monotonicity property reds (synthetic, CI); copy3-blind ≥95% exact = local run-report gate (PDF not in CI — honest split, DT-11) | `test_geom_match.py` + run report |
| G-8 | every box ⊆ page rect; page-space coords dpi-invariant | OOB synthetic box → `GeometryError`; dpi 150 vs 300 boxes drift out of rect → containment test reds | `test_geometry_backend.py` |
| G-9 | density `abstain` routes, never guesses | mutant maps abstain→content → planted mid-band fixture reds | `test_segmentation.py` |
| G-10 | sparse single-column ≠ two-column (contiguous-gutter + populated-halves guards) | remove the ≥3-bin run guard → sparse-page fixture reds | `test_segmentation.py` |
| G-11 | dark low-yield page classed `non_text_dark`, boxes untrusted | mutant trusts high-ink pages → endpaper-style fixture reds | `test_segmentation.py` |
| G-12 | routed page's atoms stay PENDING — no absent-write before verdict | mutant writes `Geom.absent` on route → sidecar-state test reds | `test_geom_sidecar.py` |
| G-13 | review fraction > `review_fraction_max` → hard fail | mutant drops the check → over-quota fixture passes silently, test reds | `test_geom_sidecar.py` |
| G-14 | verdict application total: `decline_geometry`→absent, `confirm`/`redraw`/`reclassify`→re-enter; unknown action → fail loud | mutant treats unknown as confirm → reds | `test_geom_sidecar.py` |
| G-15 | sidecar↔stream binding: `stream_source_hash` mismatch → stale fail-loud | flip one hash byte → `attach_geometry` reds | `test_geom_sidecar.py` |
| G-16 | no-witness branch end-to-end: detector order recovers known text on the synthetic two-column page | break column split → ordered-coverage pin (== 1.0 on synthetic) reds | `test_geometry_e2e.py` |
| G-17 | backend fail-loud: missing tessdata / OCR failure raises, never returns empty pages | mutant swallows the exception → reds (monkeypatched failing OCR) | `test_geometry_backend.py` |

@@@@@@
**Audit 16 — the red matrix does not cover several new persisted contracts.** Add G-rows for
sidecar schema/version rejection, source-PDF hash mismatch, atom-id namespace attachment
(witness-to-canonical or canonical direct), calibration-version staleness, and worklist replay
idempotency. Those are load-boundary contracts, not just implementation details, and today they
would rely on prose in DT-9/DT-10 rather than red-first tests.
@@@@@@

&&&&&&
**R16 — accepted; the load-boundary contracts get their own rows.** Folded into §4 on ratification
as G-18…G-24, plus one strengthening:

- **G-18** — sidecar/worklist loader totality: unknown `schema_version` / missing required key /
  malformed → the shared loader taxonomy (`StaleArtifactError`; absent file → `MissingInputError`,
  per `errors.py:18–24`); mutant loader accepting any version → reds. Home: `test_geom_sidecar.py`.
- **G-19** — source-PDF fingerprint mismatch at generation/replay → fail-loud (flip a hash byte /
  wrong page count). Home: `test_geom_sidecar.py`.
- **G-20** — canonical attachment resolves `derived_from(witness=="copy1")`; mutant doing direct
  canonical-id lookup → disjoint-namespace fixture reds. Home: `test_geom_match.py`.
- **G-21** — `WordBox`/`PageGeometry` validity: NaN/inf/degenerate/empty-text unconstructible;
  mutant drops the `__post_init__` check → reds. Home: `test_geometry_backend.py`.
- **G-22** — worklist replay: idempotent re-apply (byte-identical sidecar) + stale-fingerprint
  verdict refused, including classifier-version drift (R7); mutant applying a stale verdict →
  reds. Home: `test_geom_sidecar.py`.
- **G-23** — cross-page prior reset/override rules (R8's fixture: strong-evidence single-column
  between two-column neighbors; prior never crosses a non-content/routed page). Home:
  `test_segmentation.py`.
- **G-24** — repeated-token ambiguity: consumption + distinctive-token floor prevent a
  plausible-wrong bbox (R9's fixture). Home: `test_geom_match.py`.
- **G-8 strengthened** per R5: numeric dpi-invariance within tolerance, not containment alone.
&&&&&&

@@@@@!
**Reply R16 - satisfied, assuming the new G rows are folded into §4 rather than left as response
prose.** The added rows cover the missing persisted/load-boundary contracts. During ratification,
move G-18 through G-24 into the table itself so the red-first matrix remains the single executable
checklist.
@@@@@!

&&&&&!
**R16 follow-up — confirmed, with the round-2 additions included in the same fold.** At
ratification G-18…G-24 enter the §4 table itself, alongside the rows this round added: the
rotation-rejection red (R5, into G-17), the tie-break fixture (R4, into G-7), the
emission-shuffle determinism red (R9, into G-24), and the multi-primary-derivation fixture (R12,
into G-20). The response prose then documents provenance only; the table remains the single
executable checklist the mutation pass runs against.
&&&&&!

@@@@!!
**Reply R16 follow-up - satisfied.** Folding the round-2 reds into the §4 table keeps the mutation
matrix as the executable checklist instead of scattering acceptance criteria through discussion
prose. No further objection.
@@@@!!

Post-build: a mutation hunt over the four new core modules (house discipline), survivors
dispositioned in the audit note.

## §5 Slices and build order (children of #29)

**Slice 1 — seam, backend, matcher (the witness branch, PLL-productive):**

1. **S2.1.1 (#35)** — `geometry.py`: records + Protocol + `GeometryError`; fake-backend test
   double. (G-8 records-side, G-17 contract prose.)
2. **S2.1.2 (#36)** — `geometry_pymupdf.py` backend + synthetic image-only PDF fixture generator
   + CI tesseract install. (G-1, G-2, G-8, G-17; DT-11.)
3. **S2.1.3 (#37)** — `geom_match.py`: normalizer, monotone page-locate (+ copy3-blind
   calibration), per-atom window match, `attach_geometry`; `geom_sidecar.py` write/load; the PLL
   slice-1 run → `copy1_geom.json` + run report with threshold distributions. (G-3…G-7, G-12,
   G-15.)

**Slice 2 — segmentation front-end (trust, order, human loop):**

4. **S2.1.4 (#38)** — density band classifier. (G-9, G-11; DT-6.)
5. **S2.1.5 (#39)** — column/reading-order detector + cross-page prior + two-branch wiring + the
   synthetic no-witness end-to-end. (G-10, G-16; DT-5/7.)
6. **S2.1.6 (#40)** — worklist + verdict CLI + volume bound + overlay renders; S2.2 measurement
   feed (`order_qa` emitted book-wide). (G-13, G-14; DT-10/12.)

Within each child: red tests first, then the module, then the mutation pass. Slice 1 makes PLL
geometry real (S3.1/S5.1 unblock); slice 2 completes the tracker's front-end mandate and arms
S2.2.

## §6 Non-goals (defers to)

- The **S2.2 re-gate ruling itself** (#30) — S2.1 emits the measurements; S2.2 rules the S5 mode.
- **S3.1** Zipf-DP segmentation (own plan stub exists); **S5.1** rebind consumption.
- **Stream supersession** with inline geom (DT-9 defers; sidecar first).
- **HTML review sheet** tooling — the deviation-sheet pattern exists for later; slice 2 ships
  JSON worklist + PNG overlays + CLI only.
- **N-way witness geometry** (copy2/Harvard-scan boxes) — one witness (copy1) carries the
  canonical box; revisit with the S7.1b word-level link.
- **Word-box persistence** — S3.1's decision to bring (DT-12).

## §7 Verification plan

1. Full suite green (unit + real-input) locally and in CI (with the new tesseract step); ruff
   clean on changed files; neutrality scan green **including the new quoted-language terms**.
2. Red-first matrix: every G-row's red observed and recorded (planted violation or mutant) before
   its green; post-build mutation hunt over the four new modules.
3. Copy3-blind page-locate calibration ≥ the ratified floor, distribution published.
4. The PLL slice-1 run report: page match-rate distribution, atoms matched/absent/pending counts,
   threshold ratification, hyphen-fragment residue, `order_qa` distribution (the S2.2 feed).
5. Adversarial delta re-audit before each child's commit (house cadence: wide + narrow apertures
   on the delta).

## §8 Definition of done

- All six children (#35–#40) closed; tracker row S2.1 → `DONE` with the as-built note (path chosen,
  evidence numbers, sidecar/worklist homes).
- Tracker done-when satisfied and mapped: seam injectable (S2.1.1 fake backend) · backend yields
  matched boxes + provenance for a PLL page fixture (S2.1.2/3) · unmatched → `geom.present=false`,
  not invented (G-4, G-12/14 gate the absent-write) · low-confidence pages routed to human review
  (S2.1.6).
- `copy1_geom.json` exists for the real book with the run report; S2.2 (#30) is armed with its
  measurement feed; BR-022 answered by DT-4.
- User ratification of the DT set (this document, audited) precedes any code.
- **DT-13 ruled (a) or (b)** before the tracker row goes `DONE`: copy2-only canonical atoms are
  either given their per-atom primary-witness lane or their exclusion is explicitly ratified —
  never silently absorbed as match residue (round 3, R3).
