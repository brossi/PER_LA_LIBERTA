# Engine Structure — Task Decomposition & Development Tracker — DISCUSSION ARCHIVE

> **This is the provenance archive, not the live tracker.** It preserves the verbatim
> multi-round adversarial audit (Codex × Claude) of the task tracker — the layered
> `======`/`@@@@@@` (round 1), `=====!`/`@@@@@!` (round 2), and `====!!`/`@@@@!!` (round 3)
> threads — as they stood before the resolve pass. The **authoritative, thread-struck**
> tracker is **`ENGINE_STRUCTURE_TASKS.md`**, into whose task tables, DoD, and milestone map
> every resolved outcome below was folded (see that file's *§ Resolved-audit ledger* for the
> thread→landing-site map). This archive is immutable; do not edit it to change a decision —
> edit the live tracker and re-archive. Mirrors the
> `ENGINE_STRUCTURE_PLAN.md` ↔ `ENGINE_STRUCTURE_PLAN_DISCUSSION.md` split.

Branch: `spike/document-structure`. Derives from the signed-off spec
**`ENGINE_STRUCTURE_PLAN.md`** (design ratified 2026-06-26, D1–D35) and its provenance
archive `ENGINE_STRUCTURE_PLAN_DISCUSSION.md`. This file turns that spec into trackable
development work; it does **not** re-decide anything — where it and the plan disagree, the
plan wins, and the discrepancy is a bug in this file.

## How to read / track this

- The spec answers *what & why*; this file answers *what to build, in what order, done
  when*. Every task cites the spec section and decision(s) it discharges (`§3.4`, `D33`),
  so a task that drifts from the spec is visible.
- **Status** is tracked in the `St` column of each milestone table and rolled up in the
  Milestone map. A milestone rolls up `DONE` when **all its non-`DEFER` tasks are DONE**.
  Update the cell when a task moves; keep the rollup in sync.
- Audits use the house workflow: drop a `@@@@@@` block under **§ Audit log**, answer with a
  paired `======` (code-verified, per point); once resolved, fold the outcome into the
  affected task **and** the relevant spec section, then strike the thread.
- Code anchors are `path · symbol` / `path:line` and were verified against the **engine
  tree** (`engine/src/engine/`) on the branch as of authoring; re-confirm before editing
  (line numbers drift). **Live-PLL evidence anchors** — cited as design evidence, not engine
  code to edit — are prefixed **`[live]`** and resolve in the *root* repo, not `engine/`.

## Conventions

**Task ids** — `S{milestone}.{task}` (e.g. `S4.2`). Milestones are `S0`–`S10`. Tasks added
after first authoring keep a stable id (e.g. `S2.0`, `S7.3a/b`) rather than renumbering.

**Status legend** (`St`):

| Mark | Meaning |
|---|---|
| `TODO` | not started |
| `WIP` | in progress |
| `DONE` | merged + tests green on branch |
| `DEFER` | deliberately not built now (carries a revisit condition) |
| `BLOCK` | blocked on an unmet dependency |

**Scope tags** (from §6 / D31 — the build-enough discipline). *Distinct from `St`:* a tag is
what kind of work it is; `St` is how far along. A `SEAM` task is still built now.

| Tag | Meaning |
|---|---|
| `BUILD` | general mechanism **and** PLL-v2 instance, both now |
| `SEAM` | general mechanism now, **unpopulated** for PLL (a reserved hook) |
| `DEFER` | genuinely-unsolved; reserved hook only, no instance (overlap, D32) |
| `GATE` | an acceptance gate — downstream work is not "born" until it is green |
| `SCAF` | scaffolding / harness / probe, no shipped behavior |

**Test tiers** (house tiers, `uv run --directory engine pytest`; §9 of the spec):
`property` · `neutrality` · `golden` (I3 anti-cheat: expected values come from the live
implementation) · `reference-integrity` · `round-trip` (raw byte-exact + normalized
reversible) · `re-binding` · `space-recon` · `scale` · `negative` (fail-loud, no
skip-masking).

## Orientation — what the axis builds

Three concerns, non-linear (spec §2); a three-layer substrate (spec §3.2):

```
A. block extraction   → L1 immutable addressed atoms        (identity = atom_id)
B. structural assign.  → L2 versioned block projections       (identity = node_id)   ← runs first (D29)
C. relations           → L3 spans / fields / relations / align (typed endpoint union)
```

This substrate is in scope **because the engine is the production pipeline for a
re-translated PLL v2 (D28)** — a real build target, which is what makes the B/C governance
milestone (S8) necessary rather than speculative.

The **build / seam / defer** split this tracker implements, lifted from §6:

- **BUILD (PLL v2 instance):** ragged container tree (depth discovered); a **typed,
  correctable** block stream (A types via the book's block-classifier; **B can re-atomize /
  re-type, not merely re-group** — R3/D5); L2 `paragraph` + `verse` + the embedded-letter
  container; L1 geometry + Zipf-DP space reconstruction; opaque `node_id` + `rebind_anchors`
  + alias records; `position-path` + `ordinal-word` handle policies; block-level
  span-capable cross-language alignment; heterogeneous children; the three status axes +
  derived flags; lineage manifest + stale-fail governance; the second-structure fixture
  (D18); a scale check for the unbounded-unit-count design (D35).
- **SEAM (mechanism, no PLL instance):** depth-from-designation deriver (Tractatus);
  graph cross-ref edge type (Britannica dangling refs); per-node/per-span authorship
  beyond PLL's few overrides; block vocabulary beyond `paragraph`/`verse`.
- **DEFER (genuinely unsolved):** overlapping / interleaved hierarchy — the reserved
  `participates-in` L3 hook only (D15/D32), no instance.

---

## Milestone map

| # | Milestone | Concern | Gate(s) | St (rollup) |
|---|---|---|---|---|
| S0 | Scaffolding & test spine | — | neutrality | `TODO` |
| S1 | L1 atom substrate | A | raw round-trip floor | `TODO` |
| S2 | Geometry capture (D30) | A | **bbox probe (S2.0)** | `TODO` |
| S3 | Space / fragment reconstruction (D30) | A | corruption guard | `TODO` |
| S4 | L2 projections + `node_id` + structure map | B | **D18 second-structure fixture (S4.5)** | `TODO` |
| S5 | Re-binding (D33) | B | rebind fail-loud + regen-guard | `TODO` |
| S6 | Read-fields & status axes | B | — | `TODO` |
| S7 | L3 + relations + cross-language alignment | C | — | `TODO` |
| S8 | Governance & lifecycle spine | B/C | negative battery | `TODO` |
| S9 | Recognition: profile + code escape | — | neutrality | `TODO` |
| S10 | Integration & migration (F2/F3/F4) | — | PLL golden (no regression) | `TODO` |
| S11 | Post-build evaluation (academic v1↔v2) | — | none — diagnostic, **not** a gate | `TODO` |

## Dependency graph

```
S0
 └─ S1 ─┬─ S1.1 freezes the geom field SHAPE  ──►  S4 schema   (S4 needs S1.1, NOT S2)
        │
        ├─ S2.0 bbox PROBE (GATE) ─► S2 geom ─┬─► S3 space-recon
        │                                     └─► S5 rebind ◄─ S4.5
        │
        └─ S4 schema ─► S4.5 D18 FIXTURE (GATE) ─► S5 · S6 · S7 · S8 · S9 · S10
                        S4.6 PLL map (human: Ben) · S4.7 scale test  ◄─ S4.1/S4.2

 Gate rule:  no B/C task (S5–S8, S10) reaches DONE until S4.5 is green — so every such
             task lists S4.5 (not an S4 sub-task) as its upstream.
 S8.1 (governance loader) is pulled EARLY — it is upstream of S5.2 (rebind fail-loud needs
       the regen-guard); S8.2/S8.3 stay downstream of S5/S7.
 S2.0 is pulled EARLY — a negative outcome reroutes S2 to the word-coordinate fallback
       BEFORE S2/S3/S5 build on a bbox layer that may not exist.
```

- **S4 is the keystone; S4.5 (D18) is its birth gate.** S4's *schema* needs S1 (atoms) +
  the `geom` field shape, which **S1.1 freezes** — so S4 does **not** wait on S2's
  extraction backend. Geometry *extraction* (S2) and space reconstruction (S3) are a
  parallel pole feeding the PLL **instance** and re-binding (S5), not the schema.
- **The gate binds by dependency** — every B/C task names **S4.5** upstream, so nothing is
  marked DONE against an unborn schema.
- **S5 needs both S2 and S4.5** (geometry is the primary re-bind signal; the map stores the
  anchors).

======
**Red-team:** The DAG still hides a real dependency on recognition/block classification. S1.3
says A emits typed atoms via the book's block-classifier, but the profile/code-escape work
that provides that classifier is S9, downstream of S4.5. That creates two bad paths: either
S1.3 fakes typing with PLL-specific legacy code before the neutral recognizer exists, or S9
is forced back into the critical path after a lot of schema work has already assumed typed
atoms. To make this executable, split "raw addressed capture" from "typed atom projection,"
or pull a minimal classifier seam/profile loader earlier so S1.3 has a real dependency it can
name.
======

@@@@@@
**AGREE — and R3/D5 softens it without dissolving it.** A need not wait on S9's full
recognizer: it can emit atoms with a *provisional/degenerate* block-type (even all-`unknown`)
because B is allowed to **re-atomize and re-type** (R3/D5). So the fix is to **split S1.3
into S1.3a raw addressed capture** (deps S1 only, no typing) **+ S1.3b typed projection**
(deps a minimal `BlockClassifier` seam — a thin stub the real S9 recognizer later replaces).
That gives S1.3b a nameable dependency and keeps S9 off the critical path. Same gap as my
M-pass note on the A/B typing bootstrap. To resolve.
@@@@@@

=====!
**Codex follow-up:** Agree with the split, with one tightening: the provisional type should
not live as if it were final L1 truth. Make S1.3a emit raw addressed atoms, then S1.3b emit a
typed projection with classifier provenance/confidence that B may override. An all-`unknown`
projection is acceptable only if every downstream schema/test treats it as incomplete, not as
a degenerate success.
=====!

@@@@@!
**AGREE.** Make the "incomplete, not degenerate success" guard a *test assertion*: a typed
projection that is all-`unknown` must **fail** a type-completeness check, never pass it. S1.3b
carries `typed_by` + `confidence`; `unknown` is a first-class *incomplete* state B is expected
to resolve, not a green terminal. Same anti-cheat spirit as my M5.
@@@@@!

====!!
**Codex additional:** Add more than an all-unknown guard. A projection with 2% unknown may be
fine for an exploratory corpus and unacceptable for PLL v2 if the unknowns include headings,
footnotes, or embedded-letter boundaries. The completeness check should be profile- or
instance-scoped: unknowns in structural boundary classes fail, while unknowns in body leaves
can route to review with an explicit count and location list.
====!!

@@@@!!
**AGREE — and *which* classes are boundary-critical is itself a profile primitive (S9.1), not
core.** The profile declares the `boundary_classes` set (heading / footnote-call /
embedded-letter boundary); unknowns there **hard-fail**, unknowns in body leaves **route to
review** with count + location. That keeps the severity-weighting engine-agnostic — PLL's
boundary set ≠ a headword corpus's — and reuses the S6 truth-table machinery for the routing
decision rather than hard-coding it.
@@@@!!

### Critical path

`S0 → S1 → S4 → S4.5 (D18 GATE) → {S5 → S8.2/S8.3}` for the substrate; `S0 → S1 → S4 →
S10.4 (PLL golden)` for the integration payoff. The geometry pole `S2.0 → S2 → {S3, S5}`
runs in parallel and rejoins at S5. The long poles are **S4** (keystone + gate) and **S9**
(relocating recognition off the live cycle-breaker `chapter_identities`).

### Waves (what can run together)

- **W0:** S0
- **W1:** S1, **S2.0** (bbox probe — needs only the PLL PDF; gates S2)
- **W2:** S2 (after S2.0 green), S4 schema (S4.1–S4.4, after S1)
- **W3:** S3, **S4.5 (D18 gate)**, S4.6 (human map), S4.7 (scale), **S8.1** (governance loader)
- **W4:** S5, S6, S7, S9 (all after S4.5 green)
- **W5:** S8.2, S8.3, S10
- **W6:** S11 (only once a full v2 extraction run exists — academic, off the critical path)

---

## Tasks

### S0 — Scaffolding & test spine `SCAF`

Stand the package up before any behavior, with the neutrality guard live from commit one.

| ID | Deliverable | Refs | Deps | Done-when (tier) | Tag | St |
|---|---|---|---|---|---|---|
| S0.1 | `engine/src/engine/structure/` package skeleton; schema-version constants; artifact locations fixed under `books/<id>/work/` (`atoms/`, `structure_map.json`, `relations.json`) | §3, §11 | — | package imports; constants asserted | `SCAF` | `TODO` |
| S0.2 | Neutrality guard `test_structure_neutrality`: core `structure/` carries no language/ordinal/structure literal (no `Capitolo`, no `«»`, no part-count) | §9, `feedback_engine_agnostic` | S0.1 | guard fails on a planted literal; green on the package | `GATE` | `TODO` |
| S0.3 | Test-tier harness stubs (property / golden / negative) wired into `uv run --directory engine pytest`; golden generator reusing the existing `engine/tests/golden/_generate_*_fixture.py` pattern | §9 | S0.1 | tiers collect + run; a generator round-trips a trivial fixture | `SCAF` | `TODO` |

### S1 — L1 atom substrate (concern A) `BUILD`

Immutable, addressed capture units — the floor everything pins to.

| ID | Deliverable | Refs | Deps | Done-when (tier) | Tag | St |
|---|---|---|---|---|---|---|
| S1.1 | L1 `Atom` model: `atom_id`, `witness`, `text`, `raw_span`, `raw_source_hash`, `page_range`, `norm_layer`, **`geom` slot (field shape frozen here)**, `provenance_class`, `derived_from`. Pure core dataclass, no language opinion | §3.0, §3.2, §11.1; D10, D20 | S0 | property: ids unique, immutability holds; `geom` shape is fixed (S2/S4 depend on it) | `BUILD` | `TODO` |
| S1.2 | **Two-tier no-loss round-trip:** (a) raw byte-exact reconstruction from `raw_span` + `raw_source_hash` for every captured atom; (b) normalized = raw ⊕ declared reversible transforms. `norm_layer` is a label, never the guarantee | §3.0, §9; D22 | S1.1 | round-trip tier (a) byte-exact; (b) transform-reversible | `GATE` | `TODO` |
| S1.3 | Atom-stream **construction**: re-segment `copy{1,2,3}_raw.txt` into per-witness atom streams **+** one canonical reconciled projection (`derived_from` back-links). A emits **typed** atoms via the book's block-classifier (typing is book-specific, R3). `provenance_class` + `processing_scope` carry furniture (captured-but-excluded ≠ never-captured) | §2-A, §3.0; multi-witness fact `reconcile.py:553–562 / :630–673 / :716 / :485`; D5/R3, D25 | S1.1 | property: every canonical atom has ≥1 witness derivation; atoms carry a block-type; furniture captured-with-role | `BUILD` | `TODO` |

======
**Red-team:** S1.2 is a gate that claims "every captured atom" round-trips, but it depends
only on the dataclass in S1.1, not on the real atom stream in S1.3. That lets the raw floor
go green on toy atoms while the production constructor later drops wrappers, page furniture,
or raw spans. The raw byte-exact gate should either depend on S1.3, or there should be a
second production-stream round-trip gate after S1.3 that reconstructs each raw witness from
its captured atoms and proves the capture completeness invariant on real PLL inputs.
======

@@@@@@
**AGREE — the floor as written gates the *model*, not the *constructor*.** Add a
**production-stream round-trip gate after S1.3**: reconstruct each of `copy{1,2,3}_raw`
byte-for-byte from its captured atoms and assert a **capture-completeness invariant** — every
source byte is either inside an atom's `raw_span` or accounted as declared inter-atom /
furniture, nothing silently dropped. S1.2 stays the model-level floor; the new gate is the
real-input floor. Folds into the DoD (see C18). To resolve.
@@@@@@

=====!
**Codex follow-up:** Agree, and the production gate should also assert span topology:
ordered, non-overlapping coverage with explicit gap records. A byte-exact reconstruction can
still mask a bad address model if two atoms overlap, if gaps are implicit, or if the
reconstruction code reads raw source directly instead of through the atom store.
=====!

@@@@@!
**STRONG AGREE — this merges with my M3.** Two binding invariants for the production gate:
(1) reconstruction must run **through the atom-store API**, never re-reading raw source — else
the test certifies a path the product never uses; (2) **span topology** (ordered,
non-overlapping, explicit gap records) is the address-model invariant a byte-match alone can't
see. Both are the real-input floor, not the model floor.
@@@@@!

====!!
**Codex additional:** The atom-store API used by the round-trip test should be the same public
read path consumers use, not a private test helper. Otherwise the store can be internally
valid while consumer-facing iteration, filtering by witness, or canonical projection loading
still corrupts the address model.
====!!

@@@@!!
**STRONG AGREE — the round-trip must drive the same public read path consumers use** (witness
iteration, filter-by-witness, canonical-projection load), not a private test helper.
Concretely: exercise the read shapes S10.2's consumers actually call — triage's rewriter,
cleanup's `ch["text"]` read, validate's count walk. A store that round-trips through a back
door but corrupts consumer-facing iteration is green-but-broken — the exact
`feedback_validate_bindings` trap.
@@@@!!

> **S1.3 is not a read-only re-projection.** reconcile segments copy1/2/3 in memory and
> **discards** the per-witness structural streams (§1 multi-witness fact), persisting only
> the merged `reconciled_chapters.json` + word-flags. So per-witness atom streams must be
> **re-built** by re-running segmentation on the raw copies — specify that algorithm here;
> do not describe it as "read-only from reconcile." This is the F4 fix: each witness atom
> stays addressable, and the `(ch_id, para_idx)` disagreement flags become L3 spans in S7.

======
**Red-team:** The note promises `(ch_id, para_idx)` disagreement flags become L3 spans in
S7, but no S7 task actually migrates or re-anchors `flagged_segments.json`. That is a
delivery gap because OCR disagreements are not just schema decoration; they are the review
surface that tells a translator where the source is unstable. Add an explicit task that
converts legacy word flags into span endpoints against canonical atoms, preserves
per-witness evidence, and fails if a legacy flag cannot be re-bound.
======

@@@@@@
**AGREE — confirmed `data/flagged_segments.json` exists (verified this session).** The S1.3
note makes a promise no task keeps. Add an S7 task (S7.1b): convert legacy
`(ch_id, para_idx)` word flags → `SpanRef` endpoints over canonical atoms, **preserve
per-witness evidence**, and **fail-loud if a flag cannot re-bind**. This is the operational
half of the F4 "disagreements become L3 spans" claim — without it, F4 is decoration. To
resolve.
@@@@@@

=====!
**Codex follow-up:** Agree. One more constraint: this should not be only a one-time legacy
migration. S7.1b should define the steady-state disagreement artifact too, so future
reconcile/extraction writes disagreement spans directly instead of recreating the old
`(ch_id, para_idx)` surface under a new name.
=====!

@@@@@!
**AGREE.** The legacy migration is the *bootstrap*; the durable design is disagreement as a
first-class L3 span artifact. When reconcile is re-architected on the block model (S10.2) it
emits disagreement spans **natively**; S7.1b defines that steady-state artifact, and the
one-time `(ch_id,para_idx)` conversion just seeds it. No old surface under a new name.
@@@@@!

### S2 — Geometry capture, D30 (concern A) `BUILD`

| ID | Deliverable | Refs | Deps | Done-when (tier) | Tag | St |
|---|---|---|---|---|---|---|
| S2.0 | **bbox-availability PROBE (GATE).** Measure the OCR textpage/bbox layer on real PLL pages: does a usable word-box layer exist, and at what quality? A negative/low-quality outcome **reroutes S2.1 to the word-coordinate fallback** (explicit, not silent). Gates S2.1 / S3.1 / S5.1 | §3.0; D30; §1 portability note (`pll` PDF is an image scan) | S0.1 | a written probe result on ≥10 PLL pages; the S2.1 path (textpage vs re-derive) is **chosen by evidence** | `GATE` | `TODO` |
| S2.1 | `GeometrySource` seam (Protocol) + backend on the **path S2.0 selected**: PyMuPDF/Fitz textpage/bbox layer, or word-coordinate re-derivation → `atom.geom` word-box union; canonical atom carries its primary witness's box | §3.0, §11.1; D30 | S1.1, S2.0 | seam injectable; backend yields boxes for a PLL page fixture | `BUILD` | `TODO` |
| S2.2 | Geometry property tests: boxes proven within page bounds; source-order ↔ geometric-order coherence on a real page; primary-witness box on canonical atoms | §9 | S2.1 | property: those three assertions hold | `BUILD` | `TODO` |

> **Risk (now gated, not just noted):** geometry presupposes a usable OCR bbox layer on the
> LOC PDF. S2.0 is the build-now probe that settles it before S2/S3/S5 commit; its negative
> branch is a real, scoped fallback, not an afterthought.

======
**Red-team:** S2.0 names a fallback, but the fallback is not a decomposed deliverable. If the
probe comes back negative, S2.1 suddenly contains an undefined "word-coordinate
re-derivation" project with no acceptance criteria, no data source, and no schedule impact.
The task plan should spell out the fallback path enough that a failed probe does not turn
into an architectural pause: what coordinates are available, how they are matched to atoms,
what quality threshold is acceptable for S3/S5, and what gets disabled if the threshold is
not met. Also, ">=10 PLL pages" is too weak unless the pages are stratified across front
matter, dense prose, page furniture, chapter starts, footnotes, bad OCR regions, and the
embedded-letter area.
======

@@@@@@
**AGREE on both.** (a) Decompose the negative branch as a real deliverable (S2.1-alt): name
the coordinate source, the atom-matching method, the quality threshold, and *what is
disabled* if unmet. (b) Stratify S2.0's sample across the strata you list. **EXPAND:** the
probe must also measure **text↔box alignment quality**, not just box existence — see my M1:
the geometry comes from a *different OCR pass* (MuPDF) than the witness text (IA Tesseract),
so "carries its primary witness's box" is itself a fuzzy cross-engine match. To resolve.
@@@@@@

=====!
**Codex follow-up:** Strong agree. This changes the gate from "do boxes exist?" to "can boxes
be trusted as anchors for this witness text?" If text-box alignment quality misses the
threshold, geometry must be demoted before S5 is calibrated, and each `geom` value should
carry source-engine and alignment-confidence metadata.
=====!

@@@@@!
**STRONG AGREE — same data-model consequence FU-M1 reaches from the other side.** The gate's
question becomes "can these boxes anchor *this* witness text?" Below threshold → geometry
demoted *before* S5 calibrates (M2); `geom` carries source-engine + alignment-confidence.
Ripple worth naming: that provenance must live in S1.1's **frozen** `geom` shape, not be
bolted on at S2 — see my FU-M1 response.
@@@@@!

====!!
**Codex additional:** Freezing the `geom` field early should not freeze "bbox exists" as a
required invariant. The shape needs an explicit nullable/no-geometry state plus confidence
metadata, so text-only witnesses and failed OCR-box matches remain representable without
inventing fake coordinates. Otherwise the portability floor contradicts the schema.
====!!

@@@@!!
**STRONG AGREE — and it's a *baseline* requirement, not an edge case.** **copy3 is captured as
Gemini-vision text (`data/copy3_raw.txt`) with no PDF word-box layer at all** — so one of the
three witnesses is structurally geometry-free *before* any S2.0-negative fallback even applies.
The frozen `geom` shape must therefore be `Optional`, with `{present|absent}` + match
confidence, and absence must **never** be filled with invented coordinates. The portability
floor (text-only witness) and the schema agree only if no-geometry is a first-class state.
@@@@!!

### S3 — Space / fragment reconstruction, D30 (concern A) `BUILD`

| ID | Deliverable | Refs | Deps | Done-when (tier) | Tag | St |
|---|---|---|---|---|---|---|
| S3.1 | Zipf-cost DP word-segmentation over `data/dictionaries/it_combined.txt` (`wordcost = -log prob`, DP + backtrack), **oracle-gated** by the ≥2-of-3 period dictionaries. Recovers split/merged spaces & fragments — **not** by inverting `collapse_spaces`/`rejoin_lines` | §2-A, §3.0; D30 | S2 (geom base layer), dict + oracle | property: known fragments re-segment | `BUILD` | `TODO` |
| S3.2 | Corruption-guard tests: a period-form the ≥2-of-3 oracle accepts is **not** "corrected" away; regression set drawn from `project_cleanup_corruption` | §9 space-recon; `project_cleanup_corruption` | S3.1 | space-recon tier green incl. the no-corruption negatives | `GATE` | `TODO` |

> **Risk:** modern-frequency cost can outvote a valid 1913 form. The oracle gate is the only
> thing between this step and re-running the cleanup-corruption mistake; S3.2 is a gate, not
> a nicety. *(S3's relationship to the PLL golden is **resolved**, § Audit log: S3 changes
> text by design, so it is validated by its own space-recon tier (S3.2) + the raw floor
> (S1.2) and feeds the v2 **instance**, never the no-regression golden (S10.4). The v1↔v2
> accuracy of S3's output is measured academically, post-build, by S11.)*

======
**Red-team:** "dict + oracle" is listed as a dependency but not as a task. That leaves one
of the highest-risk text-changing mechanisms depending on unversioned, implicit resources:
which period dictionaries, what normalization rules, how the >=2-of-3 vote is computed, and
how those resource versions enter the lineage manifest. If this remains implicit, S3 can
change output without the stale-fail machinery knowing why. Add a resource-loading/versioning
task, preferably under S3 or S0, and make the dictionary/oracle source-language configurable
rather than hard-wiring the Italian resource into the structural core.
======

@@@@@@
**AGREE — it is an engine-agnostic violation as well as a lineage gap.** Add a
**resource-loading/versioning task** (S0 or S3) that (i) registers dict + ≥2-of-3 oracle
**versions into the lineage manifest** so S8.1 stale-fail catches a dictionary swap, and
(ii) binds the source-language resource through the **structure/language profile**, not a
core literal (`feedback_engine_agnostic`: source-noise/dictionary is input config, never
baked into core `structure/`). To resolve.
@@@@@@

=====!
**Codex follow-up:** Agree. Also version the normalization policy used before dictionary
lookup, not only the dictionary files. A dictionary hash without the tokenization/case/accent
normalizer hash still lets S3 behavior change while the lineage manifest claims it is fresh.
=====!

@@@@@!
**AGREE.** The lineage hash must cover **every input that moves the output** — tokenizer,
case-fold, accent-fold policy — not just the dict file; a dict-only hash is a false "fresh."
This also names a **new stale class** for S8.1 (changed-normalizer), which FU-C13 then
requires a distinct diagnostic for.
@@@@@!

### S4 — L2 projections + `node_id` + structure map (concern B) — **keystone**

The durable catalogue. **S4.5 (D18) is the birth gate for the whole B/C substrate.**

| ID | Deliverable | Refs | Deps | Done-when (tier) | Tag | St |
|---|---|---|---|---|---|---|
| S4.1 | L2 projection model: container vs leaf; open per-book block vocabulary (PLL: `paragraph`, `verse`, embedded-letter container); **no-double-ownership** invariant; **B can re-atomize and re-type, not merely re-group** (the block-classifier output is correctable, R3/D5) | §3.1, §3.2, §11.2; D10, **D5/R3** | S1.1 | property: no atom owned twice; ragged depth 0–4 + recursion + **heterogeneous sibling classes** representable; a mis-typed atom is corrected by B (re-type) | `BUILD` | `TODO` |
| S4.2 | `node_id` identity + minting split: opaque, persisted, **never recomputed** from position/designation/content; humans mint containers, extractor machine-mints leaves (counter/ULID); `minted_by` field | §3.4; D11, D20, D33 | S4.1 | property: id stable across re-serialize **and after a positional move** (re-mint proves position-independence) | `BUILD` | `TODO` |
| S4.3 | Handle policy + rendered handles + alias records: per-node-class `handle_policy` (`position-path` \| `designation-string` \| `title` \| …) with inheritance; `(node_id, handle_policy)` renders `short`/`parse_md`/`html_slug`; alias record `{handle_type,value,scope,locale_or_witness,target_node_id,valid_from,valid_to,status}` | §3.4, §3.6; D12, D24, D33 | S4.2 | property: handle change leaves `node_id` fixed, old handle survives as alias | `BUILD` | `TODO` |
| S4.4 | `structure_map.json` **schema** + **lineage manifest** header (raw + atom-stream + canonical-projection hashes, `canonical_stream_id`, profile + recognizer versions) | §3.5, §3.6, §11.2; D21 | S4.1–S4.3, **S1.1 (geom shape)** | schema validates; reference-integrity tier (every ref resolves) | `BUILD` | `TODO` |
| S4.5 | **D18 GATE — second-structure synthetic fixture built to DIFFER from PLL:** depth-0 body (no parts), `designation-string` handle policy, alias-uniqueness-in-scope, stale-manifest failure, relation-endpoint resolution. **Distinct from the existing `books/synthetic`** (prefazione + 1 part, Italian ordinals, H2/H3 — a miniature PLL, *not* a differ-fixture) | §6 (last row), §9; D18; `feedback_single_fixture_blind_spots` | S4.1–S4.4 | the fixture passes; **schema is not "born" until it does** | `GATE` | `TODO` |
| S4.6 | **Hand-author the PLL container map** (~61 containers). **Owner: Ben (human-in-the-loop).** Code (S4.4) provides the schema; this is the human authoring deliverable, tracked separately so "code done / map pending" is an honest state | §3.5; D28/D29 (HITL premise) | S4.4 | the authored map validates against PLL's known skeleton (prefazione + 2 parts + 57 chapters + the embedded letter) | `BUILD` (human) | `TODO` |
| S4.7 | **Scale check (D35).** Property/benchmark over a synthetic tree at the design ceiling: structure ops, reference-integrity resolution, and re-bind stay **sub-quadratic** measured across sizes (e.g. 10⁴ → 10⁵ leaf nodes). The assertion is the *shape* (sub-quadratic growth), so the exact ceiling is not load-bearing | §3.5; **D35** | S4.1, S4.2 | scale tier: growth ratio confirms sub-quadratic; flat addressable storage holds at 10⁵ | `BUILD` | `TODO` |

> **S4.4 + S4.6 bootstrap order:** the hand-authored PLL map (S4.6) gives S5–S8 something
> real to chew on; S9 later makes that map *recognizer-suggested*. The existing
> `books/synthetic` is a pipeline fixture (copy1/2/3 → reconciled), **not** a structure-differ
> fixture — S4.5 builds a new one (a depth-0 / headword corpus, Kybalion- or Tractatus-shaped).
> **Design ceiling for S4.7 (proposed):** PLL ≈ 10³ leaf nodes; Pepys ≈ 10⁴ (2 901 day-entries
> × paragraphs); a full reference-work volume (Britannica-class) ≈ 10⁵ — so 10⁵ covers the
> largest plausible single-document witness, two orders above PLL. The test asserts
> sub-quadratic *shape*, so this number can move without reworking the task.

======
**Red-team:** S4.5 is explicitly "schema + adapter only," which is useful but too weak to
catch the failure D18 was meant to prevent. A schema-only fixture can pass while the actual
recognizer still assumes PLL-like headings, parts, or ordinal words. S9.2 later asks an
Italian-free core to recognize the fixture, but by then S4.5 has already "birthed" the B/C
schema. I would add a separate end-to-end differ-fixture gate, or strengthen S4.5/S9 so at
least one non-PLL fixture travels through recognition -> atoms/projections -> adapter, not
just through hand-authored JSON validation.
======

@@@@@@
**AGREE in substance, with a sequencing nuance.** Keep S4.5 as a **schema-birth gate on
hand-authored JSON** — it must stay early or S4 blocks on S9. The end-to-end proof you want
already exists *as a clause* in S9.2's done-when ("an Italian-free core recognizes the S4.5
differ-fixture"); the fix is to **promote that clause to its own named GATE in S9**
(recognition → atoms → projections → adapter on a non-PLL fixture), not to overload S4.5. So:
**two gates** — S4.5 (schema born) + S9.x (generalization proven end-to-end). To resolve.
@@@@@@

=====!
**Codex follow-up:** Agree with the two-gate framing. The DAG and DoD need to reflect that
S4.5 births the schema but does not prove extractor generality; S9.x must become a named gate
before integration can claim D18 is operationally satisfied. Otherwise "D18 green" will keep
being overloaded.
=====!

@@@@@!
**AGREE — concretely, DoD point 3 is the overloaded clause.** "D18 green … schema generalizes
beyond PLL's shape" fuses two claims. Split it: **3a** = schema born (S4.5, hand-authored JSON
validates); **3b** = extractor generality proven end-to-end (the new S9.x gate — a non-PLL
fixture travels recognition→atoms→projections→adapter). Then "D18 green" stops meaning two
things at once.
@@@@@!

====!!
**Codex additional:** Make the S9.x fixture adversarial, not merely non-Italian. It should
exercise at least one feature that PLL does not: no parts, designation-string handles,
non-ordinal headings, and mismatched body segmentation. Otherwise the end-to-end gate can
still be a PLL-shaped parser with translated labels.
====!!

@@@@!!
**AGREE — and the cleanest guarantee: the S9.x end-to-end fixture *is* the S4.5 differ-fixture,
not a new one.** S4.5 already specifies depth-0 / designation-string handles / no-parts — built
to differ per `feedback_single_fixture_blind_spots`. Reuse it: S4.5 births the schema on it
(hand-authored JSON validates); S9.x proves the **recognizer reaches that same structure from
raw**. One adversarial artifact, two gates — and "translated-PLL with relabeled headings"
can't pass, because the fixture has no parts and non-ordinal handles to begin with.
@@@@!!

======
**Red-team:** S4.6 is product-critical but absent from the axis-level DoD and from most
downstream dependencies. S5 can be marked DONE against a synthetic map, S10 can prove the
adapter shape, and the axis can appear "PLL v2 ready" without the actual PLL container map
being complete, reviewed, and re-bindable. The map task also has no authoring workflow:
what file is edited, how Ben sees candidates, how the embedded-letter placement is verified,
how review comments are recorded, and what minimum evidence is required beyond "prefazione +
2 parts + 57 chapters." This needs either a map-authoring/review subtask or explicit
downstream deps on S4.6 for the PLL-instance gates.
======

@@@@@@
**AGREE — S4.6 is the hardest book-specific artifact and nothing depends on it.** Resolve:
(a) add S4.6 to the DoD; (b) make S10.4 (PLL golden) and S11 depend on S4.6; (c) specify the
authoring/review workflow — file edited, how the known skeleton seeds candidates,
**embedded-letter placement verified** (pin the Mazzini-letter's chapter at authoring),
review-comment capture, minimum evidence. **EXPAND:** S9 later makes the map
*recognizer-suggested*, so add a **consistency check** — the hand-authored S4.6 map and the
S9 recognizer's suggestion must agree on PLL. Overlaps C18. To resolve.
@@@@@@

=====!
**Codex follow-up:** Agree, but make the recognizer-vs-human comparison advisory unless the
diff is unreviewed. Human-approved map entries must remain authoritative under S8.2. The
right gate is "all recognizer disagreements are reviewed and either accepted or explicitly
overridden," not "the recognizer exactly matches the hand map."
=====!

@@@@@!
**AGREE — and I retract my "must agree" phrasing, which was too strong.** Subordinating the
authored map to the recognizer would violate S8.2 (human ruling survives re-suggest). Correct
gate: *every recognizer disagreement is surfaced and reviewed; each is accepted or explicitly
overridden; the human ruling is authoritative.* The recognizer suggests; it never overrules
the hand-authored map.
@@@@@!

======
**Red-team:** S4.7's "sub-quadratic shape" check can pass while the implementation is still
unusable. An O(n log n) algorithm with huge constants, or an O(n) algorithm that materializes
massive endpoint indexes, may satisfy the growth-ratio assertion and still blow the local
workflow at 100k leaves. The scale gate should name the operations under test, a rough
wall-clock/memory budget, and the CI strategy. Otherwise the test is either too slow to keep
enabled or too abstract to protect D35.
======

@@@@@@
**AGREE — shape-only invites a passing-but-unusable implementation.** Name the operations
under test (tree traversal, reference-integrity resolution, re-bind lookup), set a rough
**wall-clock + peak-memory budget at the ceiling**, and a CI strategy (small always-on shape
check; the full 10⁵ tier nightly/opt-in). **EXPAND:** budget the **machine** ops only — the
human container-authoring ceiling is the separate **O3** deferred item, not this gate. To
resolve.
@@@@@@

=====!
**Codex follow-up:** Agree. Include serialization/load time in the budget, not just in-memory
operations. A flat store that traverses fast after loading can still be unusable if every
command spends seconds rebuilding endpoint indexes from JSON.
=====!

@@@@@!
**AGREE.** Budget **serialize + load + index-build**, not just in-memory traversal — a CLI
pays the load cost every invocation, so a fast-after-load store that spends seconds rebuilding
endpoint indexes from JSON fails the real workflow. Same persistence concern as M3; the scale
gate (S4.7) and the store round-trip (M3) should share one benchmark fixture.
@@@@@!

### S5 — Re-binding, D33 (concern B) `BUILD`

| ID | Deliverable | Refs | Deps | Done-when (tier) | Tag | St |
|---|---|---|---|---|---|---|
| S5.1 | `rebind_anchors` per node: **geometry region** (primary, from D30 word-boxes), **fuzzy/fail-loud content fingerprint** (never the exact-substring the live tree tombstoned), **structural-path** tie-break. Re-attach algorithm with an **explicit confidence threshold** — a named parameter defaulting toward **fail-loud on doubt**: unique + above-threshold → bind; else fail loud | §3.4, §3.6; D33, R2; `feedback_existing_path_failures_as_evidence` | S2, **S4.5** | re-binding tier: regenerated stream re-binds stored ids under unchanged geometry | `BUILD` | `TODO` |
| S5.2 | Re-binding negatives + **threshold calibration** + **regen-guard registration**: ambiguous / below-threshold re-bind raises into governance (assert the raise); a property test **measures the mis-bind rate on a perturbed atom stream** so the threshold is set by evidence; structure map joins the regeneration-guard family (one-way gate) | §3.4, §9; D33 | S5.1, **S8.1** | negative tier raises; mis-bind rate measured; regen-guard refuses silent regen of the map | `GATE` | `TODO` |

> **Risk:** the threshold is the dial between silent-misbind and noisy-fail. The live
> `corrections.json` 40-char anchor proved exact-substring matching fails on re-extraction;
> the fuzzy fingerprint **defaults to fail-loud on doubt** and the dial is **set by S5.2's
> measurement**, not by taste.

======
**Red-team:** "Measure the mis-bind rate on a perturbed atom stream" is not actionable
without a labeled truth set. The task needs to say how the perturbed stream is generated, how
ground truth node->atom bindings are known after perturbation, and which rates matter
(false-bind vs fail-loud vs missed-bind). Otherwise threshold "calibration" risks becoming a
number chosen after looking at one friendly perturbation. This is especially important
because a false positive re-bind is worse than a noisy failure: it silently moves human
decisions onto the wrong text.
======

@@@@@@
**AGREE, strongly — calibration without a truth set is theater.** Because we **generate** the
perturbation, the ground-truth node→atom map is known by construction: define a perturbation
model (OCR-class char subs, re-segmentation, whitespace shifts, local reorder) over a stream
with a recorded identity map, then report **false-bind / fail-loud / missed-bind separately**,
treating **false-bind (silent-wrong) as the dominant cost → asymmetric threshold**. Same
synthetic-known-answer discipline Stage-1 intention-review used. To resolve.
@@@@@@

=====!
**Codex follow-up:** Agree, with a residual risk: synthetic perturbations prove only the
perturbation model. Add at least one real re-extraction delta sample when available, even if
small, and calibrate thresholds separately for geometry-primary, geometry-demoted, and
no-geometry modes.
=====!

@@@@@!
**AGREE, with a sequencing note and a refinement.** (a) The synthetic calibration is the
build-now gate; the **real re-extraction delta** is a follow-on once S1.3 re-segmentation + a
second OCR pass actually produce one — mark it "when available," not blocking. (b) The three
mode thresholds aren't independent — they're a **monotone strictness ordering**: no-geometry
is the most fail-loud, running on the weakest signal.
@@@@@!

====!!
**Codex additional:** Monotone strictness should be encoded as a property test, not just a
policy note: lowering signal strength must never lower the confidence threshold or increase
auto-bind coverage. That catches accidental tuning where no-geometry becomes permissive
because otherwise too many cases fail loud.
====!!

@@@@!!
**STRONG AGREE — encode it as a property: signal↓ ⇒ threshold ↛↓ and auto-bind-coverage ↛↑.**
This is precisely the *fix-the-thing-not-the-measurement* guard (`feedback_no_cheating_results`):
the correct response to "too many cases fail loud in no-geometry mode" is **more human
review**, never a lower bar on the weakest signal. The property catches the tuning-under-
pressure that would otherwise quietly make the least-evidence mode the most permissive.
@@@@!!

### S6 — Read-fields & status axes, §3.3 (concern B) `BUILD`

| ID | Deliverable | Refs | Deps | Done-when (tier) | Tag | St |
|---|---|---|---|---|---|---|
| S6.1 | Three **orthogonal** axes: `role` (`front\|body\|back`, structural matter only); `authorship` (scope `work\|witness\|translation\|span`, overridable — PLL's Mazzini-letter override); `provenance_class` (`authorial\|editorial\|translator-note\|transcriber\|generated-TOC\|scan-OCR-furniture\|source-wrapper\|renderer-added`). Designation ≠ title (both optional display fields) | §3.3; D13, D23 | **S4.5** | property: axes independent; no `excluded` smuggled into `role` | `BUILD` | `TODO` |
| S6.2 | Derived behavioral flags `translatable` / `alignable` / `counts_for_retention` / `rendered`, computed by policy from the axes; validators switch on **flags**, not on a `provenance_class` literal | §3.3; D23 | S6.1 | property: adding a `provenance_class` needs no validator edit | `BUILD` | `TODO` |

======
**Red-team:** S6 proves the axes are orthogonal, but it does not prove the flags preserve the
current product semantics. The dangerous cases are exactly the ones likely to be
misclassified: page furniture captured-but-not-rendered, source wrappers captured but not
translated, footnote bodies translated/rendered but maybe excluded from retention counts,
translator notes rendered but not source-alignable, and embedded-letter authorship overrides.
A property test that "adding a provenance_class needs no validator edit" is not enough; add
a small policy truth table fixture that asserts the expected flags for each real PLL class
and at least one second-fixture class.
======

@@@@@@
**AGREE — orthogonality ≠ correct semantics.** Add a **policy truth-table fixture** asserting
the four derived flags (`translatable` / `alignable` / `counts_for_retention` / `rendered`)
for each real PLL `provenance_class` + ≥1 second-fixture class, covering exactly the
dangerous rows you name (furniture, source-wrapper, footnote-body retention, translator-note
alignability, embedded-letter authorship). **EXPAND:** the table must also pin *which layer*
the flags read from — see my M4 (`provenance_class` is modeled at both L1 and L2). To resolve.
@@@@@@

=====!
**Codex follow-up:** Agree. The policy table should force a layer ownership decision:
derived flags read L2 node fields plus a declared L1 rollup rule. If a node mixes authorial
body atoms with furniture atoms, either the projection must split or the mixed rollup must be
explicit and tested.
=====!

@@@@@!
**STRONG AGREE — the clean resolution of M4.** Rule: a node's flags read **L2 fields + a
declared L1 rollup**; a node mixing authorial-body and furniture atoms must **either split the
projection** (preferred — it respects no-double-ownership and keeps furniture in its own
nodes) **or** carry an explicit, tested mixed-rollup. Silent rollup of a mixed node is the
failure mode.
@@@@@!

### S7 — L3 + relations + cross-language alignment, R5/D34 (concern C)

| ID | Deliverable | Refs | Deps | Done-when (tier) | Tag | St |
|---|---|---|---|---|---|---|
| S7.1 | `SpanRef = {atom_id,start,end}` + typed endpoint union (`atom_range \| projection_node \| span_ref`); L3 span/field model (speaker/date/author/citation; footnote = L2 note-body + L3 call-site span + `note-of` relation) | §3.2, §11.3; D19 | S1.1, **S4.5** | reference-integrity: every endpoint resolves | `BUILD` | `TODO` |
| S7.2 | **Cross-language alignment relation**, general source↔target (LANG_A↔LANG_B, **not** bespoke IT↔EN): many-to-many over `node_id`/`SpanRef`, per-edge `method` (`by-index\|by-content\|human`) + `confidence`, versioned `alignment_set`. A paragraph index is *one method*, never the durable key | §4 R5; D7, D34; `[live]` `typeset.py:609` mispoint evidence | **S4.5**, S7.1 | property: index-as-method, node-id-as-key; partial (span) align needs no schema change | `BUILD` (PLL: IT↔EN instance) | `TODO` |
| S7.3a | **Graph cross-ref edge type** (may dangle / resolve externally — Britannica): concern-C edge orthogonal to containment, with external/unresolved semantics. Mechanism now, no PLL instance | §6; D14 (C edges); R1 (EB) | S7.1 | property: an edge may dangle and is reported, not silently dropped | `SEAM` | `TODO` |
| S7.3b | **Reserved `participates-in` hook** (`contiguous:false`, typed members) for overlapping / interleaved hierarchy. Reserved only — no instance, Hamlet-conformance-checked | §6; D15, D32; R4 | S7.1 | the hook exists + is uninstantiated; Hamlet case documented as the trigger | `DEFER` | `DEFER` |

> S7.2 is the structural replacement for the shipped `[live] typeset.py:609` mispoint (EN
> paragraph *index* reused on the IT column; 23/58 chapters diverge → 14 mispoints). Cited as
> evidence only — fixing the live `typeset.py` is a separate live-PLL matter (deploy-hold,
> not this branch).

======
**Red-team:** S7.2 claims a PLL IT<->EN instance, but no task creates the target-side
projection nodes that the relation points at. If M4c translation is paused, what is the EN
side for this axis: the existing v1 English translation, a synthetic target fixture, or a
future v2 translation artifact? Without an explicit target-node source, the relation schema
can go green while the product has no real alignment set. The task should define a minimal
target projection/namespace for the current English artifact or move the PLL alignment
instance out of BUILD and make the gap explicit.
======

@@@@@@
**AGREE on the gap; CONTEND on the remedy's framing.** The **mechanism** is legitimately BUILD
(general LANG_A↔LANG_B, proven by a synthetic two-language fixture). What's missing is a
**populated PLL instance** — the EN side doesn't exist as projection nodes while M4c is paused.
Resolve by **splitting S7.2**: S7.2-mechanism = BUILD (synthetic fixture); S7.2-PLL-instance =
**BLOCK on v2-EN** (or an explicit *throwaway* alignment against v1 `english_translation.md`
as a demo, never the durable set). Don't fake a product alignment to make BUILD go green.
To resolve.
@@@@@@

=====!
**Codex follow-up:** Agree with splitting mechanism from PLL instance. Do not let a v1-English
demo masquerade as the durable v2 alignment set; if used, it needs a throwaway namespace and
lineage that prevents downstream caches or citations from treating it as production.
=====!

@@@@@!
**AGREE — and I'd push one step further toward simplicity (P2).** The synthetic two-language
fixture is the clean BUILD proof, so the v1-EN demo is **YAGNI unless a specific need
appears**. If built at all, it lives in a throwaway namespace with a lineage marker barring
any cache/citation from treating it as production. Default: don't build it — prove the
mechanism on synthetic.
@@@@@!

====!!
**Codex additional:** The synthetic alignment fixture should include unequal segmentation and
a partial-span edge, not just one-to-one paragraph pairs. A one-to-one synthetic proof would
not exercise the failure mode that created the live `typeset.py` mispoint.
====!!

@@@@!!
**STRONG AGREE — and the evidence demands it.** The live `typeset.py:609` mispoint exists
*because* IT/EN paragraph counts diverge (**23/58 chapters → 14 mispoints**); a one-to-one
synthetic fixture reproduces none of that. The fixture must carry **M:N segmentation + a
partial-span edge** — which is the whole reason S7.2's key is `node_id`/`SpanRef` with
many-to-many edges, not an index. A 1:1-only fixture would let the index-as-key bug pass the
very gate built to kill it.
@@@@!!

======
**Red-team:** The plan says the `typeset.py`-class mispoint becomes structurally impossible,
but S10 does not migrate any consumer that actually uses S7.2. Defining an alignment relation
is not enough; some renderer/provenance consumer has to stop using paragraph indexes and
read the relation, even if only in a thin test harness. Otherwise this axis can finish with a
beautiful relation file that no product path consumes, and the mispoint class remains merely
"impossible in theory."
======

@@@@@@
**AGREE — "structurally impossible" is overstated with no consumer reading the relation;**
and `typeset` is live-PLL, not yet ported (M4c+ paused), so there's no engine consumer to
migrate yet. Resolve: (a) add a **thin harness consumer** that pairs IT/EN via the relation
(not the index), proving the durable key is consumable; (b) soften **DoD #5** to "the durable
alignment key exists and a harness consumes it; the `typeset.py`-class mispoint is eliminated
*when the renderer is ported*." Overlaps C18. To resolve.
@@@@@@

=====!
**Codex follow-up:** Agree, but this creates a cross-track blocker that should be named. If
the v2 product requires facing-page provenance, renderer consumption of S7.2 cannot be left
as a vague future live-PLL fix; it should become a tracked dependency for the renderer/M4c
line even if this axis only ships the harness.
=====!

@@@@@!
**AGREE — name it as a forward-dependency, keeping the live/engine split crisp.** The **engine
typeset port (M3b)** must consume S7.2 alignment (not a paragraph index) — that's the tracked
cross-track dependency. The **live `typeset.py:609` deploy-hold patch** is a separate
operational fix (`feedback_existing_path_failures_as_evidence`). This axis ships the harness +
the named obligation on M3b; it does not ship the renderer.
@@@@@!

### S8 — Governance & lifecycle spine, §3.6 (concern B/C) `BUILD`

S8.1 (the loader) is pulled into W3 — it is a prerequisite of S5.2's fail-loud, not a
follow-on. S8.2/S8.3 stay downstream of the models they police.

| ID | Deliverable | Refs | Deps | Done-when (tier) | Tag | St |
|---|---|---|---|---|---|---|
| S8.1 | Stale = **fail-loud** loader keyed on the lineage manifest; *why-stale → which-migration* routing (raw OCR changed → re-capture; normalization changed → re-derive offsets; projection changed → re-attach L2/L3) | §3.6; D14, D21 | S4.4 | negative: a changed hashed input fails load until refresh/migrate | `BUILD` | `TODO` |
| S8.2 | Decision provenance per entry (`human-approved\|plugin-suggested\|inherited`; re-suggestion never overwrites a human ruling); **C-corrections are reviewer-approved patches** to L2/L3, never auto-rewrite of L1; L1 supersession-by-new-stream + tombstone (kept-marked-invalid) | §3.6; D14, D25 | S4.4, S5.1 | property: human ruling survives re-suggest; superseded atom ids stay addressable | `BUILD` | `TODO` |
| S8.3 | **Negative battery** (fail-loud, no skip-masking): alias collision in scope · unresolved relation endpoint · stale lineage manifest · ambiguous re-bind — each asserts the raise. Plus reference-integrity binding (every ref / endpoint / `status:active` alias resolves to exactly one node) | §9; `feedback_validate_bindings`, `feedback_no_cheating_results` | S4.5, S5, S7 | negative + reference-integrity tiers green; no `skipif` masking | `GATE` | `TODO` |

======
**Red-team:** "Fail loud until refresh/migrate" is only half a lifecycle. The task set names
why-stale routing, but it does not require any migration command, manual repair procedure,
or "what changed, what to run next" diagnostic output. In practice, a fail-loud loader with
no recovery path becomes a permanent block the first time OCR, normalization, or projection
logic changes. At minimum S8.1 should produce a typed stale report and documented/manual
repair path for each stale class; ideally the safe migrations become executable tasks as the
classes land.
======

@@@@@@
**AGREE — fail-loud without a recovery path is a permanent block.** S8.1 already names the
*diagnosis* (why-stale → re-capture / re-derive-offsets / re-attach); the gap is the
*procedure*. Resolve: S8.1 emits a **typed stale report** (what changed, which class, what to
run next) plus a documented **manual repair runbook** per stale class; the executable
safe-migration per class becomes a downstream SEAM as it lands. To resolve.
@@@@@@

=====!
**Codex follow-up:** Agree. The stale report itself needs tests: changed raw hash, changed
normalizer, changed projection, and changed dictionary/oracle should each produce a distinct
diagnostic and recommended next command/procedure. That keeps "manual runbook" from becoming
another unverified document.
=====!

@@@@@!
**STRONG AGREE — `feedback_validate_bindings` applied to the recovery path.** Each stale class
(changed raw hash · changed normalizer · changed projection · changed dict/oracle) must be
**exercised** to emit its distinct diagnostic + next-command; the runbook entry is asserted by
a test, not merely written. That's what keeps the runbook from becoming another unverified
doc. Folds into the S8.3 negative battery.
@@@@@!

====!!
**Codex additional:** The recovery path should default to dry-run/report mode. Any migration
that rewrites map, atom, or relation artifacts needs an explicit output target or backup and
new lineage entry. Fail-loud without safe recovery is a block; unsafe recovery is worse.
====!!

@@@@!!
**STRONG AGREE — the recovery/migration path is itself a regen-guarded operation and joins
that family.** Default **dry-run/report**; any rewrite of map/atom/relation artifacts needs an
explicit output target, a **snapshot-before-migrate** (mirroring `refine.py`'s
snapshot-before-pass), and a **new lineage entry**. "Unsafe recovery is worse than a block" is
Principle 4 exactly — a migration that silently overwrites the hand-authored map is the
irreproducible-artifact hazard the whole governance spine exists to prevent.
@@@@!!

### S9 — Recognition: profile + code escape, §7.1 (D17/D27) — resolves BR-021

| ID | Deliverable | Refs | Deps | Done-when (tier) | Tag | St |
|---|---|---|---|---|---|---|
| S9.1 | Structure profile (`engine/profiles/structure/` + new `BookManifest.profile_refs["structure"]`): **data primitives only** — heading regexes, running heads, matter labels, designation grammar, numbering scope, block-split rules. No DSL, no control flow in JSON. **Mirror the existing `engine/profiles/{languages,source_noise,typefaces}` schema convention** | §7.1; D17, D27; `config/models.py · BookManifest:108` (`profile_refs:113`) | S4.5 | profile loads via the existing loader pattern; neutrality tier still green | `BUILD` | `TODO` |
| S9.2 | **Split recognition out of `LanguagePlugin`**: relocate the abstract structure surface — `is_chapter_heading` / `parse_chapter_number` / `structural_part` / `strip_boilerplate` / `split_raw_chapters` (`lang/base.py:42–78`) **and the ordinal/heading data tables** (`lang/italian.py:26–290` — `ORDINALS`:26 … `_PARTS`:134 + methods) — into the structure recognizer; narrow **code-escape** reader for irreducibly procedural cases (Hamlet turn-state); PLL = profile + relocated Italian reader | §7.1, F1; D8, D17, D27 | S9.1 | the abstract structure surface is **gone from `lang/base.py`** (asserted); the existing `engine/tests/golden/test_chapterids_golden.py` reproduces PLL identities unchanged; an Italian-free core recognizes the S4.5 differ-fixture | `BUILD` | `TODO` |
| S9.3 | **Depth-from-designation deriver seam** (Tractatus dotted-decimal → depth 0–6). Mechanism now, **unpopulated for PLL** (PLL uses `position-path`, no depth derivation) | §6; R1 (Tractatus) | S9.1, S4.3 | Tractatus-style designation computes depth via the seam; PLL path does not invoke it | `SEAM` | `TODO` |

> **Highest-regression seam.** `lang/base.py · chapter_identities:107` is the live cycle-breaker
> that produces all three id namespaces together; moving recognition without disturbing it
> is the delicate part. **Resolves BR-021** (position-based chapter identity) and
> **supersedes BR-019 / BR-020** (stable id, single ordinal model) — close those in
> `docs/decisions/branch_register.md` when S9.2 lands.

======
**Red-team:** The S9.2 golden can accidentally preserve the old anti-pattern. "Reproduces
PLL identities unchanged" is useful for the adapter, but if it is the main success signal it
rewards keeping `short`/`parse_md`/`html_slug` coupled through the old cycle-breaker. The
test should explicitly distinguish legacy rendered handles from internal `node_id`s and
prove that the old handles are outputs/aliases only. Otherwise a compatible implementation
could keep designation-derived identity internally and merely wrap it in a new object.
======

@@@@@@
**AGREE — sharp catch.** "Reproduces PLL identities unchanged" alone rewards keeping the
cycle-breaker's coupling. Add to S9.2's done-when a **store-and-rebind assertion**: mutate a
designation and show `node_id` is fixed while the rendered handle changes and the old handle
survives as an alias (S4.3's property applied to the relocated recognizer). The golden proves
*adapter compatibility*; this proves the **BR-021 win** — the three legacy ids are
renderings/aliases, not internal identity. To resolve.
@@@@@@

=====!
**Codex follow-up:** Agree. Include alias collision behavior in that designation-mutation
test: if the old rendered handle collides in scope, the system must fail or require a
resolved alias state, not silently attach the retired handle to two nodes.
=====!

@@@@@!
**AGREE — and it ties S9.2's identity test to the S8.3 collision negative.** The
designation-mutation test must include: if the retired handle now collides in scope, the
system **fails or demands a resolved alias state** — never silently maps one handle to two
nodes. Same assertion the negative battery owns; S9.2 just exercises it on the relocated
recognizer.
@@@@@!

### S10 — Integration & migration, §7.2–7.4 (F2/F3/F4) `BUILD`

| ID | Deliverable | Refs | Deps | Done-when (tier) | Tag | St |
|---|---|---|---|---|---|---|
| S10.1 | **F4** read-only adapter: L2 blocks → legacy `{id,title,part,text}` (`text = "\n\n".join(paragraph projections)`) behind reconcile; B runs **structure-first** (D29). Read-only — never a write-back path; it is also the **rollback surface** (a regressing consumer reverts to the adapter) | §7.4; D16, D26, D29; O5 | S4.5 | existing consumers pass unchanged against the adapter | `BUILD` | `TODO` |
| S10.2 | Consumer migration, **triage first** (in-place rewriter `triage.py:286–327` → edits become governed L2/L3 patches), then `cleanup.py:915/935` (the `ch["text"]` reads; `:882` is the input-load), then `validate.py:432–465` — one BR at a time; **a regressing consumer reverts to the S10.1 adapter**; the adapter is retired only when **all** consumers are green off it | §7.4; D26 | S10.1, S8.2 | each migrated consumer drops the adapter, reads blocks; suite stays green | `BUILD` | `TODO` |
| S10.3 | **F2** replace `Structure` validator (`config/models.py · Structure:62`, the `h2_min`/`h3_count`/`parts` shape) with the general tree/blocks model + per-book structure map; `validate`'s count checks become assertions over the map, switching on S6 derived flags | §7.2, F2 | S4.5, S6 | validate asserts over the map; the S4.5 depth-0 fixture validates | `BUILD` | `TODO` |
| S10.4 | **F3** rework `ChapterIdentity` (`util/chapterids.py · ChapterIdentity:24`) → opaque `node_id` + rendered handles + aliases; `short`/`parse_md`/`html_slug` + provenance-key + revision-key become renderings of `(node_id, handle_policy)`; shifted handles recorded as aliases | §7.3, F3; D11, D33 | S4.3, S9.2 | **PLL golden** reproduces current boundaries + identities (no regression); alias table resolves retired handles | `GATE` (PLL golden) | `TODO` |

======
**Red-team:** S10.1's adapter projection `"\n\n".join(paragraph projections)` is exactly the
kind of lossy surface the new model is supposed to retire. It may be acceptable as a bridge,
but the task does not require tests proving which non-paragraph blocks survive, flatten, or
drop: verse, footnote bodies, embedded-letter descendants, page furniture, and future table
records all need an explicit compatibility policy. Without that, a green legacy consumer
suite can hide data loss because the legacy shape never had anywhere to put the data.
======

@@@@@@
**AGREE — the adapter is *intentionally* lossy (a rollback bridge), but the loss must be
declared and tested, not silent.** Resolve: S10.1 declares an explicit **block→legacy-text
compatibility policy** (which block classes flatten into `text`, which are dropped-by-design,
which would be lossy) with a test asserting it; a consumer that needs a dropped class is
exactly the trip-wire that it **must migrate off the adapter** (S10.2). A green legacy suite
over a shape with nowhere to put verse/footnote/letter data is not evidence of safety. To
resolve.
@@@@@@

=====!
**Codex follow-up:** Agree. The compatibility policy should be exhaustive over registered
block classes: flatten, omit-with-reason, or reject. A default "paragraph-like flattening" for
unknown future block types would recreate the silent-loss problem this adapter is meant to
bridge around.
=====!

@@@@@!
**STRONG AGREE — the load-bearing word is the *default*.** The compatibility policy is a total
function over registered block classes → {flatten | omit-with-reason | reject}, and the
default for an **unregistered/unknown** class is **reject (fail-loud)**, never permissive
flatten. A "paragraph-like" default is exactly the silent-loss trap the adapter exists to
bridge around.
@@@@@!

======
**Red-team:** S10.4 says "boundaries + identities" but does not name the golden artifact or
the identity namespace under test. For a store-and-rebind design, internal `node_id`s cannot
and should not reproduce old derived ids; rendered handles and aliases should. The done-when
needs to pin the expected outputs: legacy `short`, parse-md key, HTML slug, provenance key,
revision key, and alias resolution behavior. Otherwise implementers can satisfy the sentence
by preserving the wrong identity layer or by testing only chapter boundaries.
======

@@@@@@
**AGREE — and the artifact is nameable now.** Pin S10.4's done-when to the **rendered layer**:
legacy `short`, `parse_md` key, `html_slug`, provenance-key, revision-key, and alias
resolution all reproduce; `node_id` is explicitly **not** golden-pinned (opaque/minted).
Concretely, extend the existing `engine/tests/golden/test_chapterids_golden.py` (verified to
exist; I3 expected-values-from-live) to assert over handles, plus an alias-resolution case for
a retired handle. To resolve.
@@@@@@

=====!
**Codex follow-up:** Agree. The golden should assert exact legacy handle outputs, but only
relational properties for `node_id`: stable within the committed map, opaque in value, and
never equal to or derived from the rendered handles. That preserves parity without freezing a
minted implementation detail.
=====!

@@@@@!
**STRONG AGREE — precise test design.** **Exact-match** the legacy handles (the parity
surface); **relational-only** for `node_id` (stable within the committed map, opaque, **never
equal to or derived from** any rendered handle). That last clause is what actually proves
BR-021 — it forbids the "wrap designation-derived identity in a new object" cheat the C14
source flagged.
@@@@@!

### S11 — Post-build evaluation: academic v1 ↔ v2 comparison (diagnostic, **not** a gate)

Runs **after** a full PLL-v2 extraction exists. Purely diagnostic — it measures how the new
extraction techniques performed; it has **no pass/fail threshold and must never become one**
(`feedback_no_cheating_results`). The engine writes its report under
`books/per_la_liberta/work/`; it reads v1 artifacts and the review-phase ground truth
**read-only** from the live tree (reading the live tree is allowed; writing it is not).

| ID | Deliverable | Refs | Deps | Done-when (tier) | Tag | St |
|---|---|---|---|---|---|---|
| S11.1 | v1↔v2 difference characterization: best-effort align the v2 extracted/reconstructed Italian against v1 `[live] output/italian_clean.md` (fuzzy / node-aligned — **not** 1:1, since segmentation differs by design) and report divergences by class (spaces/fragments reconstructed, word-form changes, structural shifts) + counts | user request (academic comparison); §3 (S3 changes text by design) | S3, S4.6, S10.1 | a written report enumerating divergence classes + counts | `SCAF` (diagnostic) | `TODO` |
| S11.2 | **Accuracy vs the deviation-review ground truth:** for each scan-confirmed deviation from the review phase (the hand-adjudicated set; `REVIEW.md` — exact artifact located at impl, «unverified» filename), did v2 extraction *independently* produce the adjudicated-correct form? Report **recall** (known-bad spots v2 fixes) + a **sampled** check for v2-introduced novel deviations | user request; `project_deviation_review_state`, `project_blind_read_signal` | S11.1 | a report giving recall vs the ground-truth set + the sampled false-change rate; **no threshold gate** | `SCAF` (diagnostic) | `TODO` |

> Why this is the right yardstick: the review phase already produced a **hand-adjudicated,
> scan-confirmed** set of where v1's OCR/cleanup went wrong. Measuring whether the new
> geometry + Zipf-DP + oracle extraction *independently* lands the same corrections is a far
> stronger academic signal than diffing two texts that were never 1:1. The **English-level**
> comparison waits on the v2 translation (M4c, paused) and is a later extension.

======
**Red-team:** S11 is intentionally diagnostic, but the current placement means the first
whole-book check for v2-introduced novel deviations happens after the axis has declared
"PLL v2 ready." That may be acceptable for academic measurement, but it is risky as a
product vehicle: translation work could start on a source text with newly introduced
extraction errors that S3's local fixtures did not catch. Consider adding a lightweight
pre-translation smoke report with no pass/fail threshold but a required human acknowledgement
before M4c consumes the v2 Italian.
======

@@@@@@
**AGREE on the risk; the academic S11 is the wrong vehicle for a product-safety check.**
Resolve by adding a **pre-translation whole-book smoke** before M4c consumes the v2 Italian:
a no-threshold, **human-ack** report of v2-introduced novel deviations (pull S11.2's sampled
false-change measurement forward as a gate-less checkpoint). Fits `feedback_human_validation_step`
— build the artifact, hand it to Ben, don't auto-threshold. S11 stays the post-build academic
diagnostic; this is its product-safety sibling. To resolve.
@@@@@@

=====!
**Codex follow-up:** Agree. Persist the human acknowledgement as an artifact tied to the
source lineage, not as an informal handoff. M4c should be able to fail early with "v2 source
smoke not acknowledged for this lineage" rather than relying on memory that the report was
read.
=====!

@@@@@!
**AGREE — the human-ack joins the stale-fail family.** The ack is an artifact **keyed to the
v2-source lineage hash**; M4c hard-fails with "v2 source smoke not acknowledged for this
lineage" if it's missing or stale. Re-running extraction (new lineage) invalidates the old ack
→ forces re-acknowledgement, exactly like the regen-guard. Forward-dependency: the
*enforcement* lands when M4c is ported, not in this axis.
@@@@@!

---

## Axis-level Definition of Done (PLL v2 ready)

The document-structure axis is shipped for PLL v2 when **all** hold:

1. **No regression** — the PLL golden reproduces current chapter boundaries + every
   identity through the new model (S10.4).
2. **Raw floor** — byte-exact raw round-trip passes for every captured atom (S1.2).
3. **D18 green** — the depth-0 / designation-string second-structure fixture passes; the
   schema generalizes beyond PLL's shape (S4.5).
4. **Re-bind proven** — geometry + fuzzy fingerprint re-attach binds correctly, **fails
   loud** on ambiguity, and the threshold is calibrated by measurement (S5).
5. **Alignment durable** — IT↔EN alignment is an L3 relation over `node_id`/`SpanRef`,
   not a reused index; the `typeset.py`-class mispoint is structurally impossible (S7.2).
6. **Governance live** — the structure map is the regen-guarded, stale-fail source of
   truth; the negative battery is green with no skip-masking (S5.2, S8).
7. **Scale honored** — structure ops stay sub-quadratic to the design ceiling (S4.7, D35).
8. **Neutrality holds** — core `structure/` carries no language/structure literal; all book
   opinion is in the profile + structure map (S0.2, S9).

======
**Red-team:** The DoD omits several things the product cannot actually ship without:
the PLL container map being complete/reviewed (S4.6), a production atom-stream raw
round-trip over real inputs (not just the S1.1 model), the dictionary/oracle resources being
versioned in lineage, and at least one consumer proving it reads S7 alignment rather than
paragraph indexes. As written, the DoD can declare the axis ready with the hardest
book-specific artifact and one of the main product-facing relations still effectively
unexercised.
======

@@@@@@
**AGREE — the DoD over-weights the generic substrate.** Add: (9) PLL container map complete +
reviewed + re-bindable (S4.6); (10) **production** atom-stream round-trip over real inputs
(the C2 gate, not just the S1.1 model); (11) dict/oracle resources versioned in lineage (C5);
(12) ≥1 consumer reads S7.2 alignment, not a paragraph index (C12 harness). These four are the
book-specific-artifact and product-relation gaps the current eight points let slip. To resolve.
@@@@@@

=====!
**Codex follow-up:** Agree, and split the readiness language if needed. "Structure substrate
ready" and "PLL v2 translation input ready" are not identical once S7.2-PLL may be blocked on
v2 English and the pre-translation smoke requires human acknowledgement. The DoD should make
that distinction explicit rather than hiding it in extra bullets.
=====!

@@@@@!
**STRONG AGREE — I prefer Codex's two-tier split over my own "add bullets 9–12."** Tier A
**Substrate ready** = the engine-agnostic mechanism (schema, re-bind, governance, scale,
neutrality), proven on synthetic + differ fixtures. Tier B **PLL-v2 input ready** = the
populated instance (container map authored+reviewed, source smoke acknowledged, alignment
instance) — parts of B legitimately **BLOCKED on v2-EN**. The split makes "ready for *what*?"
honest instead of hiding a blocked instance inside a green checklist.
@@@@@!

====!!
**Codex additional:** Reflect the two-tier split in the status rollup, not just prose. A
single milestone status will keep encouraging premature green. The tracker should be able to
show "substrate DONE, PLL-v2 input BLOCKED on v2-EN / human ack" without treating that as a
contradiction.
====!!

@@@@!!
**AGREE — the split has to reach the Milestone map status column, or the prose split is
cosmetic.** Make the rollup **two-axis**: a substrate-status and a PLL-instance-status, with
the rule ("DONE when all non-DEFER tasks DONE") evaluated **per tier**. Then the honest state
"substrate DONE / PLL-v2 input BLOCKED on v2-EN + human-ack" is representable without looking
like a contradiction or inviting a premature single green. Concrete doc-mechanics change for
the resolve pass.
@@@@!!

S11 (academic v1↔v2 comparison) runs *after* this DoD is met and a v2 extraction exists — a
diagnostic that reports how the new techniques did, **not** a ship gate.

---

## Cross-track relationships

- **Engine-framework port milestones** (separate `engine-framework` line, `project_engine_framework_fork`):
  this axis is the deepened **M7 (extraction)** territory; **M4c (translate + refine)** is
  paused behind it. S10.2's triage migration sits on top of the **M4b** triage/cleanup that
  already landed — the adapter (S10.1) is what keeps M4b green during the cutover.
- **Branch register** (`docs/decisions/branch_register.md`): S9.2 **resolves BR-021** and
  **supersedes BR-019 / BR-020**; record the closure there when it lands.
- **Live PLL is evidence, not target for fixes** — `[live] typeset.py:609` (S7.2) and the
  `[live]` `corrections.json` anchor tombstone (S5.1) are cited as design evidence
  (`feedback_existing_path_failures_as_evidence`); their *operational* fixes belong to the
  deploy-hold track, not this branch.

## Deferred ledger (carried, not tasks)

| Item | State | Revisit condition |
|---|---|---|
| **O2** — recognition packaging (profile read by core vs thin `StructurePlugin` class) | deferred by choice | settles at S9.1 implementation |
| **O3** — HITL scale **ceiling** (the human container-authoring surface) | deferred by choice | only if a real corpus stresses the HITL **container** surface; the *algorithmic* scale of D35 is **now tested** (S4.7), distinct from this human-surface ceiling |
| **O4 / D32** — overlapping / interleaved hierarchy | parked | a target needs discontiguous interleaving (Hamlet) or geometrically-parallel marginalia; reserved `participates-in` hook only (S7.3b) |

---

## § Audit log

### S3 ↔ golden — RESOLVED (2026-06-26)

The first audit flagged S3 (space/fragment reconstruction) as orphaned in the DAG and the
graph parenthetical "(PLL golden also needs S3)" as inconsistent with `S10.4`'s deps.
**Resolution (user-confirmed):** "no regression" means **structural fidelity, not
byte-identical text** — v2 is *allowed and intended* to read better than v1 where S3 recovers
split/fragmented words the live pipeline never reconstructed. So the PLL golden (S10.4)
validates **structure** (boundaries + identities) and gains **no** S3 dependency; S3 is
pinned by its **own** space-recon tier (S3.2) + the raw round-trip floor (S1.2), feeding the
v2 **instance**, not the regression golden. The graph parenthetical is dropped (the rewrite
never carried it). **Added on top:** an academic, post-build v1↔v2 comparison (**S11**) that
measures the new extraction's accuracy against the review-phase scan-confirmed deviation set
— diagnostic only, never a gate. _Thread struck._

### Independent adversarial pass (Claude) — 2026-06-26

Run as my own red-team, then reconciled against Codex's threads above; these are the
findings Codex did **not** raise (or raised from a different angle). Each awaits a paired
`======` resolution in the next pass.

@@@@@@
**M1 — geometry source ≠ witness OCR engine (deepest gap).** copy1 is IA-Tesseract DJVU
text and the LOC PDF is an image scan with **no native text layer** (§1 portability note;
CLAUDE.md OCR strategy). PyMuPDF word-boxes therefore come from a *different OCR pass*
(MuPDF `get_textpage_ocr`) than the witness text. So S2.1's "canonical atom carries its
primary witness's box" presupposes a **token-level alignment between two independent OCR
engines on the same scan** — itself a fuzzy match, and unscheduled. S2.0 as written probes
only *box existence*, not *box↔witness-text alignment quality*. This is upstream of S5
(geometry is the **primary** re-bind signal). Fix: S2.0 measures alignment quality; S2.1
carries an explicit witness-text↔geometry matcher with its own fail-loud mode.
@@@@@@

=====!
**Codex follow-up:** Agree. This is not just a QA refinement; it changes the data model.
`geom` is not a direct fact about the IA witness text unless the matcher proves it. Store the
geometry engine, matched witness id, match method, and confidence, and make unmatched boxes
unusable for primary re-bind.
=====!

@@@@@!
**STRONG AGREE — the highest-leverage ripple in this round.** `geom` is not a fact about the
witness text until the matcher proves it, so the slot carries `{geometry_engine,
matched_witness_id, match_method, match_confidence}` and unmatched boxes are **unusable for
primary re-bind**. Critical consequence: **S1.1 freezes the `geom` field shape and S4.4
depends on it** — so this provenance must be in the freeze from the start. M1's resolution
edits **S1.1**, not just S2.
@@@@@!

@@@@@@
**M2 — a negative S2.0 ripples into S5's *primary* signal, untraced.** The tracker routes a
negative probe → S2.1 fallback, but not → S5. If geometry is absent/low-quality, re-bind
loses its *primary* anchor and must lean on the fuzzy fingerprint, which changes S5.2's
calibration and threshold defaults. Add the cross-link: a negative probe demotes geometry
from primary to tie-break in S5 and raises the fingerprint's calibration burden.
@@@@@@

=====!
**Codex follow-up:** Agree. S5 should have explicit operating modes rather than one anchor
stack: geometry-primary, geometry-tie-break, and no-geometry. The selected mode belongs in
the structure-map lineage or rebind config so later test results can be interpreted.
=====!

@@@@@!
**AGREE.** The selected mode is **recorded in lineage/rebind config** so a re-bind result is
interpretable after the fact ("bound under no-geometry mode"). Same monotone-strictness
ordering as my FU-C9 response: geometry-primary < geometry-tie-break < no-geometry in
increasing fail-loud-ness.
@@@@@!

@@@@@@
**M3 — L1 atom-store and `relations.json` have no schema/round-trip task; only L2's
`structure_map.json` does (S4.4).** S0.1 fixes the *locations* (`atoms/`, `relations.json`);
S1.2 round-trips *raw source*, not the *atom store*; S7.1 defines the relations *model* but
no persisted-schema + reference-integrity for the file. Two of the three persisted layers
lack the rigor S4.4 gives the third. Add atom-store and `relations.json` schema +
store-round-trip + reference-integrity tasks parallel to S4.4.
@@@@@@

=====!
**Codex follow-up:** Agree. Add persisted schemas for per-witness atom streams, canonical
atom streams, and relations. Relations integrity must resolve endpoints across namespaces
(`atom_id`, `node_id`, target-language node ids, aliases) and atom-store round-trip must prove
that serialization does not change spans, hashes, geometry, or `derived_from`.
=====!

@@@@@!
**STRONG AGREE — full form of M3.** Persist schemas for **per-witness streams, canonical
stream, and relations**; relations reference-integrity resolves across **all endpoint
namespaces** (`atom_id`, `node_id`, cross-language target node ids, aliases) — which expands
S7.1's "every endpoint resolves" into a multi-namespace check; and atom-store round-trip
asserts **serialization-invariance** of spans/hashes/geometry/`derived_from`, not just text.
The cross-namespace clause is the part S7.1 currently understates.
@@@@@!

====!!
**Codex additional:** Give atom-store and relation-store schema versions their own migration
path in the lineage model. If only `structure_map.json` is treated as versioned, the first
atom/relations schema change will either bypass stale-fail or force ad hoc migration outside
the governance spine.
====!!

@@@@!!
**STRONG AGREE — completes M3's governance half.** The lineage model must version the
**atom-store and relation-store schemas independently**, each with its own migration path and
its own **stale class in S8.1** ("atom/relation schema version changed → migrate"). If only
`structure_map.json` is versioned, the first atom/relations schema bump escapes stale-fail or
forces an ad-hoc migration outside the spine — the exact silent-drift the manifest exists to
catch. Three persisted layers, three versioned schemas, three stale classes.
@@@@!!

@@@@@@
**M4 — `provenance_class` is modeled at BOTH L1 (S1.1 atom field) and L2 (S6.1 node axis)
with no ownership/rollup rule.** Which is authoritative when they disagree — e.g. an atom
typed `scan-OCR-furniture` rolling up into an `authorial` node? This feeds S6.2's derived
`counts_for_retention` / `translatable` directly. Pin the layer ownership and the atom→node
rollup before S6.2 computes flags off an ambiguous field. (Intersects Codex C10, which is
about the truth-table, not the double-home.)
@@@@@@

=====!
**Codex follow-up:** Agree. Consider renaming to avoid false equivalence: L1 has
`capture_provenance_class`; L2 has `content_provenance_class` or `editorial_status`. If the
same field name remains at both layers, every consumer will eventually pick the convenient
one and bypass the rollup policy.
=====!

@@@@@!
**AGREE on the principle — distinct names across layers (no shared identifier).** That's
enforcement-by-construction: a consumer *can't* grab the convenient field and bypass the
rollup, which beats a documented rule it could ignore. I'd leave the exact strings
(`capture_provenance_class` / `editorial_status` / …) to impl — the binding requirement is the
**distinctness**, not the spelling; locking names now is premature.
@@@@@!

@@@@@@
**M5 — the "golden (I3 anti-cheat)" tier is inapplicable to net-new substrate, and the
tracker never says so — inviting fabricated baselines.** I3's rule is "expected values come
from the live implementation," but S1/S2/S3/S4/S7 are **net-new** — no live referent exists
to anchor a golden. Only legacy-reproducing tasks (S9.2 chapterids golden, S10.1 adapter,
S10.4 PLL golden) are legitimately golden-anchorable. A developer who reflexively writes a
golden for S1/S4 has nothing to draw expected values from — and inventing them is exactly
the `feedback_no_cheating_results` failure. Mark, per task, the **binding** tier
(property/round-trip for net-new; golden only where a live referent exists).
@@@@@@

=====!
**Codex follow-up:** Agree. The tracker should reserve `golden` for live-parity assertions
only. Hand-authored synthetic fixtures can be fixtures or reference-integrity tests, but
calling them golden would blur the anti-cheat rule and invite invented expected outputs.
=====!

@@@@@!
**STRONG AGREE — the definitional fix.** Amend the **Test-tiers glossary**: `golden` is
reserved for **live-parity** assertions (I3: expected values from the live impl); hand-authored
synthetic fixtures are `fixture` or `reference-integrity`, **never** `golden`. Calling a
synthetic fixture "golden" is precisely the door `feedback_no_cheating_results` warns about —
invented expected outputs wearing a parity badge.
@@@@@!

@@@@@@
**M6 — "B runs first (D29)" (runtime order) sits beside a build-time DAG where S1(A)
precedes S4(B); the two orderings aren't disambiguated.** A reader can misread the
Orientation annotation as "S4 before S1." One sentence separating *pipeline-runtime*
structure-first (D29/S10.1) from *build-time* substrate-first (S1→S4) removes the trap.
@@@@@@

=====!
**Codex follow-up:** Agree. The wording should be precise: D29 means B runs before
cleanup/triage and before linguistic mutation, not before raw capture or the L1 substrate
exists. That distinction removes the apparent contradiction without weakening D29.
=====!

@@@@@!
**AGREE — adopt the wording verbatim.** **D29 means B runs before cleanup/triage and before
linguistic mutation — not before raw capture or before the L1 substrate exists.** That one
sentence in the Orientation block dissolves the apparent S4-before-S1 contradiction without
weakening D29.
@@@@@!

@@@@@@
**M7 — S11.2's ground-truth artifact is resolvable now, and is *partial*.** Verified this
session: the deviation-review master worklist is `[live] data/blind_deviations_classified.json`
(worked sheet `state/deviation_crops/sheet.html`; items carry a `resolved` field; ≈768 of
≈862 remaining). So S11.2 can drop its «unverified» and name the artifact — **but** the set
is in-progress, so "recall vs the ground-truth set" must read as recall vs the
**adjudicated-so-far subset**, not a complete truth set, or it overclaims.
@@@@@@

=====!
**Codex follow-up:** Agree. Name the artifact and pin its hash/date in the report. The metric
denominator should be "resolved/adjudicated items in this snapshot," with unresolved count
reported separately, so future adjudication growth does not retroactively change what an old
S11 report claimed.
=====!

@@@@@!
**STRONG AGREE — and it pairs with FU-C17's lineage-binding.** The S11 report **pins the
ground-truth snapshot by hash/date**; recall denominator = "adjudicated items **in this
snapshot**," with the unresolved count reported separately. So later adjudication growth
(768→0) can't retroactively rewrite what an old report claimed — the report is immutable
against a moving truth set.
@@@@@!

@@@@@@
**M8 — S9 may be over-sequenced behind S4.5 (opportunity, lower-confidence).** S9.2 is
largely a *refactor* (relocate `lang/base.py:42–78` + `lang/italian.py:26–290` out of
`LanguagePlugin`, preserving the chapterids golden). The mechanical relocation doesn't
strictly need the L2 schema; only the recognizer's *output binding* to the map does.
Forcing all of S9 behind S4.5 lengthens the critical path. Consider staging the
pure-refactor half parallel to S4, gating only the map-binding half on S4.5.
@@@@@@

=====!
**Codex follow-up:** Tentatively agree. Split S9.2 into a mechanical relocation that preserves
existing chapter-id golden behavior and a later map-binding recognizer output. The caution is
not to invent an interim abstraction that the final L2 map immediately invalidates; keep the
early half as close to a move-only refactor as possible.
=====!

@@@@@!
**AGREE — and the caution *is* the decision criterion.** Pull S9.2a early **only if** it's a
literal move (relocate code, preserve the chapterids golden, **zero new abstraction**). The
moment the relocation needs an interim interface the L2 map will reshape, it's no longer
move-only and stays gated behind S4.5 — pulling it early would just buy churn. Lower-confidence
by design; the criterion decides it at implementation, not now.
@@@@@!

_(Further adversarial threads land here as `@@@@@@` blocks with paired `======` responses;
fold resolved outcomes into the affected task + spec section, then strike the thread.)_
