# Engine Structure — Task Decomposition & Development Tracker

Branch: `spike/document-structure`. Derives from the signed-off spec
**`ENGINE_STRUCTURE_PLAN.md`** (design ratified 2026-06-26, D1–D35) and its provenance
archive `ENGINE_STRUCTURE_PLAN_DISCUSSION.md`. This file turns that spec into trackable
development work; it does **not** re-decide anything — where it and the plan disagree, the
plan wins, and the discrepancy is a bug in this file.

This tracker is the **resolved** form of a multi-round adversarial audit (Codex × Claude,
2026-06-26). Every audit outcome is folded into the task tables, the Definition of Done, and
the milestone map below; the verbatim threads are archived in
**`ENGINE_STRUCTURE_TASKS_DISCUSSION.md`**, and the *§ Resolved-audit ledger* at the end maps
each resolution to where it landed.

## How to read / track this

- The spec answers *what & why*; this file answers *what to build, in what order, done
  when*. Every task cites the spec section and decision(s) it discharges (`§3.4`, `D33`),
  so a task that drifts from the spec is visible.
- **Status** is tracked per milestone in the two-axis rollup of the Milestone map
  (substrate vs PLL-instance — see *Definition of Done* for why the split is real) and in the
  `St` column of each task table. A milestone tier rolls up `DONE` when **all that tier's
  non-`DEFER` tasks are DONE**. Update the cell when a task moves; keep the rollup in sync.
- Audits use the house workflow: drop a `@@@@@@` block under **§ Audit log**, answer with a
  paired `======` (code-verified, per point); once resolved, fold the outcome into the
  affected task **and** the relevant spec section, strike the thread, and record the landing
  site in the *§ Resolved-audit ledger* before moving the verbatim thread to the discussion
  archive.
- Code anchors are `path · symbol` / `path:line` and were verified against the **engine
  tree** (`engine/src/engine/`) on the branch as of authoring; re-confirm before editing
  (line numbers drift). **Live-PLL evidence anchors** — cited as design evidence, not engine
  code to edit — are prefixed **`[live]`** and resolve in the *root* repo, not `engine/`.

## Conventions

**Task ids** — `S{milestone}.{task}` (e.g. `S4.2`). Milestones are `S0`–`S11`. Tasks added
after first authoring keep a stable id (e.g. `S2.0`, `S1.3a/b`, `S7.1b`) rather than
renumbering.

**Status legend** (`St`):

| Mark | Meaning |
|---|---|
| `TODO` | not started |
| `WIP` | in progress |
| `DONE` | merged + tests green on branch |
| `DEFER` | deliberately not built now (carries a revisit condition) |
| `BLOCK` | blocked on an unmet dependency (names the blocker) |

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
`property` · `neutrality` · `golden` · `reference-integrity` · `round-trip` (raw byte-exact +
normalized reversible) · `re-binding` · `space-recon` · `scale` · `negative` (fail-loud, no
skip-masking).

> **`golden` is reserved for live-parity assertions only** (I3 anti-cheat: expected values
> come from the live implementation). It is therefore **applicable only where a live referent
> exists** — `S9.2a` chapterids golden, `S10.1` adapter, `S10.4` PLL golden. The net-new
> substrate (`S1`–`S7`) has **no live referent**, so its binding tiers are
> `property` / `round-trip` / `reference-integrity` / `negative`; a hand-authored synthetic
> artifact is a **`fixture`** or a `reference-integrity` test, **never** a "golden" (calling
> it golden would invite invented expected outputs wearing a parity badge —
> `feedback_no_cheating_results`). Each task's *Done-when* names its binding tier accordingly.

> **Adversarial-audit gate (§9, D36).** A `BUILD`/`GATE` task's *Done-when* is not met until a
> pre-commit adversarial pass is clean — the mutation hunt + overlapping wide/narrow reviewers, with
> any *behavior-changing* remediation re-audited **to a fixpoint** (docs/test-only changes terminate)
> and the apertures re-aimed at the delta. Proportional to surface (a fleet for substantial behavior,
> a single check for a one-liner; signal, not ceremony), self-applied, forward-only — like red-first.
> The S1.3b / S1.4 / S1.5 rows already record this practice; D36 makes it the standing gate.

## Orientation — what the axis builds

Three concerns, non-linear (spec §2); a three-layer substrate (spec §3.2):

```
A. block extraction   → L1 immutable addressed atoms        (identity = atom_id)
B. structural assign.  → L2 versioned block projections       (identity = node_id)   ← runs first (D29)
C. relations           → L3 spans / fields / relations / align (typed endpoint union)
```

> **Runtime order vs build order — not a contradiction.** "B runs first (D29)" is a
> *pipeline-runtime* fact: **B runs before cleanup/triage and before any linguistic mutation
> — not before raw capture, and not before the L1 substrate exists.** The *build-time* DAG is
> the opposite direction — `S1` (A, the atom floor) precedes `S4` (B) because B projects over
> atoms. Read "B first" as "structure-before-text-mutation at runtime," never as "S4 before
> S1 at build time."

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
  beyond PLL's few overrides; block vocabulary beyond `paragraph`/`verse`; the degenerate
  `BlockClassifier` stub (S0.4) the S9 recognizer later replaces.
- **DEFER (genuinely unsolved):** overlapping / interleaved hierarchy — the reserved
  `participates-in` L3 hook only (D15/D32), no instance.

---

## Milestone map

Two-axis rollup (per *Definition of Done*): **Sub** = substrate / engine-agnostic mechanism;
**PLL** = the populated PLL-v2 instance (some of it legitimately `BLOCK` on v2-EN). `—` means
the milestone has no instance-tier work. The split keeps "substrate DONE / PLL-v2 input
BLOCKED" representable without a premature single green.

| # | Milestone | Concern | Gate(s) | St (Sub) | St (PLL) |
|---|---|---|---|---|---|
| S0 | Scaffolding & test spine | — | neutrality | `DONE` | — |
| S1 | L1 atom substrate | A | raw floor (S1.2) + **production round-trip (S1.4)** | `WIP` | `TODO` |
| S2 | Geometry capture (D30) | A | **bbox + text↔box probe (S2.0)** | `TODO` | `TODO` |
| S3 | Space / fragment reconstruction (D30) | A | corruption guard (S3.2) | `TODO` | `TODO` |
| S4 | L2 projections + `node_id` + structure map | B | **D18 schema-born fixture (S4.5)** | `WIP` (S4.0–S4.5 `DONE`, **gate green — schema v1 born**; S4.6-pre freeze + S4.6a sidecar + S4.7 scale pending, #31–#33) | `TODO` (S4.6 map) |
| S5 | Re-binding (D33) | B | rebind fail-loud + regen-guard (S5.2) | `TODO` | — |
| S6 | Read-fields & status axes | B | — | `TODO` | — |
| S7 | L3 + relations + cross-language alignment | C | — | `TODO` | `BLOCK` (S7.2b on v2-EN) |
| S8 | Governance & lifecycle spine | B/C | negative battery (S8.3) | `TODO` | — |
| S9 | Recognition: profile + code escape | — | neutrality + **extractor-generality (S9.4)** | `TODO` | `TODO` |
| S10 | Integration & migration (F2/F3/F4) | — | PLL golden (S10.4) | `TODO` | `TODO` |
| S11 | Pre-translation smoke + post-build evaluation | — | none — diagnostic, **not** a gate | — | `TODO` |

## Dependency graph

```
S0 ──┬─ S0.4 BlockClassifier stub seam ──► S1.3b (nameable dep; real backend = S9)
     │
     └─ S1 ─┬─ S1.1 freezes the geom field SHAPE (Optional + match-provenance) ──► S4 schema
            │                                                          (S4 needs S1.1, NOT S2)
            ├─ S1.3a raw capture ─► S1.3b typed projection ─► S1.4 production round-trip (GATE)
            │                                                  S1.5 atom-store schema + version
            │
            ├─ S2.0 bbox+alignment PROBE (GATE) ─► S2 geom ─┬─► S3 space-recon
            │        └ negative ─► S2.1-alt fallback         └─► S5 rebind ◄─ S4.5
            │        └ negative also ─► S5 mode = geometry-demoted / no-geometry
            │
            ├─ S3.0 resource + normalizer versioning ─► S3.1
            │
            └─ S4 schema ─► S4.5 D18 FIXTURE (schema born, GATE) ─► S5 · S6 · S7 · S8 · S10
                            S4.6 PLL map (human: Ben) · S4.7 scale test  ◄─ S4.1/S4.2
                            └─► S9.4 extractor-generality on the SAME S4.5 fixture (GATE)

 Gate rule:  no B/C task (S5–S8, S10) reaches DONE until S4.5 is green — so every such
             task lists S4.5 (not an S4 sub-task) as its upstream.
 Two D18 gates:  S4.5 = schema born (hand-authored JSON validates) ;
                 S9.4 = extractor generality (the SAME adversarial fixture travels
                        recognition → atoms → projections → adapter from raw).
 S8.1 (governance loader) is pulled EARLY — upstream of S5.2 (rebind fail-loud needs the
       regen-guard); S8.2/S8.3 stay downstream of S5/S7.
 S2.0 is pulled EARLY — a negative outcome reroutes S2 to S2.1-alt AND demotes geometry in
       S5 BEFORE S2/S3/S5 build on a bbox layer that may not exist or may not anchor the text.
 S9.2a (move-only relocation) MAY run parallel to S4 iff it is a literal move (zero new
       abstraction); the moment it needs an interim interface the L2 map reshapes, it becomes
       S9.2b and stays gated behind S4.5.
```

- **S4 is the keystone; S4.5 (D18) is its schema-birth gate.** S4's *schema* needs S1 (atoms)
  + the `geom` field shape, which **S1.1 freezes** — so S4 does **not** wait on S2's
  extraction backend. Geometry *extraction* (S2) and space reconstruction (S3) are a
  parallel pole feeding the PLL **instance** and re-binding (S5), not the schema.
- **The schema-born gate (S4.5) is not the generality proof.** S4.5 only validates
  hand-authored JSON; **S9.4** proves the recognizer reaches that same non-PLL structure from
  raw. Both are required before integration can claim D18 is operationally satisfied.
- **S5 needs both S2 and S4.5** (geometry is the primary re-bind signal where it exists; the
  map stores the anchors). A negative S2.0 does not block S5 — it selects S5's
  geometry-demoted / no-geometry operating mode (M2).

### Critical path

`S0 → S1 → S4 → S4.5 (D18 schema gate) → {S5 → S8.2/S8.3}` for the substrate; `S0 → S1 → S4 →
S10.4 (PLL golden)` for the integration payoff; `S4 → S4.5 → S9.4 (D18 generality gate)` for
the neutrality proof. The geometry pole `S2.0 → S2 → {S3, S5}` runs in parallel and rejoins
at S5. The long poles are **S4** (keystone + schema gate) and **S9** (relocating recognition
off the live cycle-breaker `chapter_identities` + the generality gate).

### Waves (what can run together)

- **W0:** S0 (incl. **S0.4** BlockClassifier stub)
- **W1:** S1 (S1.1 → S1.3a → S1.3b), **S2.0** (bbox+alignment probe — needs only the PLL
  PDF; gates S2), **S3.0** (resource/normalizer versioning), **S9.2a** (only if move-only)
- **W2:** S2 / S2.1-alt (after S2.0), **S1.4** (production round-trip), **S1.5** (atom-store
  schema), S4 schema (S4.1–S4.4, after S1)
- **W3:** S3, **S4.5 (D18 schema gate)**, S4.6 (human map), S4.7 (scale), **S8.1** (governance loader)
- **W4:** S5, S6, S7 (incl. S7.1b/S7.1c), **S9** (S9.1, S9.2b, **S9.4** generality gate) — all after S4.5 green
- **W5:** S8.2, S8.3, S10
- **W6:** **S11.0** (pre-translation smoke, before M4c consumes v2 Italian); S11.1/S11.2
  (academic, only once a full v2 extraction run exists — off the critical path)

---

## Tasks

### S0 — Scaffolding & test spine `SCAF`

Stand the package up before any behavior, with the neutrality guard live from commit one.

| ID | Deliverable | Refs | Deps | Done-when (tier) | Tag | St |
|---|---|---|---|---|---|---|
| S0.1 | `engine/src/engine/structure/` package skeleton; schema-version constants; artifact locations fixed under `books/<id>/work/` (`atoms/`, `structure_map.json`, `relations.json`) | §3, §11 | — | package imports; constants asserted | `SCAF` | `DONE` |
| S0.2 | Neutrality guard `test_structure_neutrality`: core `structure/` carries no language/ordinal/structure literal (no `Capitolo`, no `«»`, no part-count) | §9, `feedback_engine_agnostic` | S0.1 | guard fails on a planted literal; green on the package | `GATE` | `DONE` |
| S0.3 | Test-tier harness stubs (property / fixture / reference-integrity / negative) wired into `uv run --directory engine pytest`; golden generator reuses the existing `engine/tests/golden/_generate_*_fixture.py` pattern (golden reserved for the live-parity tasks only — S9.2a/S10.1/S10.4) | §9 | S0.1 | tiers collect + run; a generator round-trips a trivial fixture | `SCAF` | `DONE` |
| S0.4 | **Minimal `BlockClassifier` Protocol seam + degenerate stub** (all-`unknown` classifier): the thin, nameable dependency S1.3b types against before the real S9 recognizer exists. Stub output is **incomplete-by-construction**, never a degenerate green (see S1.3b) | §2-A; D5/R3; §7.1 | S0.1 | seam injectable; the stub classifies every atom `unknown`; the real backend is S9 | `SEAM` | `DONE` |

### S1 — L1 atom substrate (concern A) `BUILD`

Immutable, addressed capture units — the floor everything pins to.

| ID | Deliverable | Refs | Deps | Done-when (tier) | Tag | St |
|---|---|---|---|---|---|---|
| S1.1 | L1 `Atom` model: `atom_id`, `witness`, `text`, `raw_span`, `raw_source_hash`, `page_range`, `norm_layer`, **`geom` slot — Optional, frozen here with match-provenance** (`{present\|absent}` + `{geometry_engine, matched_witness_id, match_method, match_confidence}`; **absence is a first-class state, never invented coordinates** — copy3 is geometry-free), `capture_provenance_class` (the L1 *capture* class — a **distinct** field from L2's content/editorial provenance, see S6.1/M4; final names are an impl choice, distinctness is the requirement), `derived_from`. Pure core dataclass, no language opinion | §3.0, §3.2, §11.1; D10, D20, D30 | S0 | property: ids unique, immutability holds; `geom` shape (incl. nullable + provenance) is **frozen** — S2/S4.4 depend on it | `BUILD` | `DONE` |
| S1.2 | **Model-level raw round-trip floor:** (a) raw byte-exact reconstruction from `raw_span` + `raw_source_hash` for a captured atom; (b) normalized = raw ⊕ declared reversible transforms. `norm_layer` is a label, never the guarantee. *This is the model floor; S1.4 is the real-input floor* | §3.0, §9; D22 | S1.1 | round-trip tier (a) byte-exact; (b) transform-reversible | `BUILD` | `DONE` |
| S1.3a | **Raw addressed capture** (no typing): re-segment `copy{1,2,3}_raw.txt` into per-witness atom streams **+** one canonical reconciled projection (`derived_from` back-links). `capture_provenance_class` + `processing_scope` carry furniture (captured-but-excluded ≠ never-captured). Re-built by re-running segmentation on the raw copies — **not** read-only from reconcile (see note) | §2-A, §3.0; multi-witness fact `reconcile.py:553–562 / :630–673 / :716 / :485`; D25 | S1.1 | property: every canonical atom has ≥1 witness derivation; furniture captured-with-role | `BUILD` | `DONE` |
| S1.3a.1 | **`build_canonical` fails loud on >2 structural witnesses** — it uses `witness_order[0:2]` and currently **silently ignores** `[2:]`; raise `CaptureError` ("N-way structural alignment unbuilt") so "exactly two structural witnesses" is a documented boundary, not a silent truncation (#16 audit, Thread 2) | §11.1; #16 | S1.3a | negative: ≥3 witnesses raises `CaptureError`; the 2-witness path unchanged | `BUILD` | `DONE` |
| S1.3a.2 | **Make `align_streams`'s `SequenceMatcher` junk policy explicit + owned** — pass `autojunk=True` rather than rely on the implicit default; comment that it is load-bearing (PLL canonical count swings 4786↔5226, ~9%, discarded keys are real OCR noise `3e`/`s:`/`35`) and mirrors `reconcile.align_paragraphs`. **Plus a source-layer guard** (AST, S0.2-guard family) that the `align_streams` `SequenceMatcher` call carries `autojunk` explicitly — a load-bearing default must be *owned, not inherited* (implicit reverts to difflib's default, a silent ~9% shift if that ever diverged across versions/interpreters) (#16 audit, Thread 3B) | `reconcile.py:188`; difflib `autojunk` default=`True` (3.13, verified); #16 | S1.3a | property + negative: junk policy explicit + documented; canonical count unchanged at the chosen setting; source guard reds on the implicit form (live mutation + planted-form discrimination) | `BUILD` | `DONE` |
| S1.3a.3 | **Oracle-back the five frozen real-input counts** (278/521/3621/3356/4786) — bind each to an **independent** re-derivation in-test (regex marker-count for furniture; `re.split` blank-block oracle for body/copy1/copy2, furniture-masked for copy3; difflib opcode→pair algebra for canonical — newly pinned `FROZEN_CANONICAL_ATOMS=4786`) so a segmenter regression **reds** instead of silently tracking a magic int. Frozen ints retained as **oracle-verified scale anchors** (`assert capture == oracle == frozen`), not the sole binding. Independence **graded honestly in-test**: only furniture is genuinely cross-architecture; body oracles are implementation-independent / spec-shared — judged adequate (a fully-independent body oracle must restate the same spec; the merge-not-caught-by-tiling gap is the real value-add) (#16 audit, Thread 3A) | §9; #16 | S1.3a | property: each count == its independent oracle == frozen anchor; **mutation-proven** (blank-flush drop → copy1 count binding reds at `1==3621` while `assert_capture_tiles` still passes — the count oracle catches a merge tiling alone misses) | `SCAF` (test) | `DONE` |
| S1.3a.4 | **Canonical-page tripwire** — pin that every canonical atom is `PAGE_UNMAPPED` today (canonical adopts copy1's unmapped address; copy3, the only page-bearing witness, is word-level → absent from the structural alignment), so S7.1b's page-attribution change is **loud + intentional**; this test is S7.1b's worklist marker (named `test_real_canonical_is_uniformly_page_unmapped_until_s7_1b`, greppable). **Non-vacuity control** in the model floor (`test_canonical_adopts_primary_page…`): a page-mapped primary yields a page-mapped canonical, so the real-input assertion is a genuine constraint, not `assert True` (#16 audit, Thread 1) | §11.1; D25; #16 | S1.3a | property: canonical stream is uniformly `PAGE_UNMAPPED`; assertion referenced by S7.1b; **red seen** (inject a page into copy1's capture → tripwire reds with the S7.1b-intent message) | `SCAF` (test) | `DONE` |
| S1.3a.5 | **Honest-prose fixes** — the "~46% both-derived" claim is a **structural (positional)** pairing stat, **not** content agreement (verified this session: 2191/4786 ≈ 46% `derived_from==2`, of which only 276 ≈ 6% are content-anchored `equal`; the rest are textually-divergent `replace` pairs → S7.1b). Corrected in the **#16 comment** (4817229857, one clause) + in-repo test prose (module docstring + canonical-test comment/message). The other three audit clarifications — `key=` as the per-book alignment lever, the exactly-two-structural-witness boundary, canonical page-attribution → S7.1b — verified **already stated** in `capture.py` docstrings + the #16 design comments (S1.3a.1/.4), not re-stated. **plan §11.1 carried no such claim** (grep-confirmed) — dropped as a target (#16 audit, Thread 3C/2/1) | #16 | S1.3a | both-derived claim corrected in the #16 comment + in-repo prose; other three confirmed present; plan §11.1 had no occurrence | `SCAF` (docs) | `DONE` |
| S1.3b | **Typed projection over the raw atoms** via the `BlockClassifier` (S0.4 stub → S9 real): each typed atom carries `typed_by` + `confidence` that **B may override** (re-type, R3/D5). **Profile-scoped completeness check:** unknowns in the profile's declared `boundary_classes` (heading / footnote-call / embedded-letter boundary — S9.1) **hard-fail**; unknowns in body leaves **route to review** with count + location (reuses the S6 truth-table machinery). An **all-`unknown` projection FAILS** completeness — `unknown` is a first-class *incomplete* state, never a degenerate green. **Built** (`structure/typed.py`): `TypedAtom` (Atom+`BlockClassification` pair — typing is a re-runnable projection B re-types, not a mutation), `typed_projection(atoms, classifier)` (positional zip; fail-loud on a seam-contract count mismatch, no silent tail-drop), `check_completeness(typed, *, boundary_classes) -> CompletenessReport`. **Discriminator decision:** the boundary-vs-body axis is the L1 `capture_provenance_class` matched against the profile-supplied `boundary_classes` — it *must* be independent of the typed `block_class` (an atom can't be both `block_class∈boundary` and `==UNKNOWN`), so the hard-fail keys on (capture-class∈boundary ∧ block_class==UNKNOWN). Degenerate (all-`unknown`) checked **first** (distinct root cause — resolved-nothing) → raises `IncompleteTypingError` (errors.py, exit 9); boundary-class unknown → raises (names atom+span); body-leaf unknown → non-raising `CompletenessReport.to_review` (count+location). Empty projection = vacuously complete (capture-emptiness is S1.3a/S1.4's concern). **S6 reuse is forward** — S6 unbuilt, so `CompletenessReport` is the minimal local shape S6's policy truth-table will subsume, *not* a wire-in. **Adversarial pass (independent reviewer) → two fixes:** (i) the check now scopes to **processed** (`processing_scope`-included) atoms — excluded furniture left `unknown` is exempt (§3.0 captured-but-excluded), never mis-routed to body-review nor hard-failed; `processed_count` (was `typed_count`) counts only in-scope atoms; (ii) the boundary hard-fail is honestly a **mechanism + forward contract, not a real-input guarantee** — today's capture tags every non-furniture line `authorial` and forces named `classify_line` results to `excluded`, so a real boundary left `unknown` routes to **review** (flagged, never silent) until S9 makes capture granular (relaxing the capture.py non-body→excluded coupling). Real-path tests added (`capture_witness → typed_projection → check_completeness`). **5-lens adversarial pass (spec / correctness / test-quality / neutrality / architecture, overlapping coverage) → further fixes:** reject a bare-`str` `boundary_classes` (char-set severity-inversion); switch the scope filter to `!= excluded` (an out-of-vocab `processing_scope` stays in scope, closing a reopened degenerate-green); bind too-many-classifications, ≥2 review-items (count>1), ≥2 boundary offenders, and a real-capture route-to-review; correct the overstated "no design could identify a boundary" premise (a heading recognizer exists; the branch is dead by capture-scope *choice*) + log the considered-rejected "defer regime to S9.1"; flag that `to_review`'s consumer is the governance surface, not S6's truth-table. Cross-file items (body_class neutrality, Atom scope-validation, typed_by enforcement, wholesale-exclusion seam) logged for decision. 36 tests, **15 invariants mutation-proven** red | §2-A; D5/R3 | S1.3a, **S0.4** | property: boundary-class unknown raises; body-leaf unknown routes-to-review with count+location; all-`unknown` fails completeness | `BUILD` | `DONE` |
| S1.4 | **Production-stream round-trip GATE (real-input floor):** reconstruct each of `copy{1,2,3}_raw` byte-for-byte **through the atom-store's public read path consumers use** (witness iteration, filter-by-witness, canonical-projection load — exercise the shapes S10.2's consumers call; never a private helper, never re-reading raw source). Assert the **capture-completeness invariant** (every source byte is inside an atom's `raw_span` or recorded as declared inter-atom/furniture) **and span topology** (ordered, non-overlapping coverage with explicit gap records). **Core landed** (`structure/roundtrip_gate.py`, #21): `GapRecord` (explicit declared gap), `gap_records` (the tiling/topology walk — `assert_capture_tiles` now **delegates** here, single owner), `reconstruct_source` (whole-artifact byte-exact from stored atom+gap text — the gate's `==source` compare catches an `atom.text` drifted off its span, a drift the per-atom hash re-slices past), `assert_no_wholesale_exclusion` (owns the S1.3b-deferred "excluded everything" seam), `assert_production_roundtrip` (the gate entry). Runs over real `copy{1,2,3}_raw` (whole-artifact reconstruct + overlap/implicit-gap/text-drift/all-excluded negatives). **5-lens overlapping adversarial audit** (spec/correctness/test-quality/neutrality/architecture) → no blockers, all mutants killed (2 survivors proven *equivalent*); hardening applied: `GapRecord` whitespace-only enforced at construction (durable record fails loud on content), `reconstruct_source` rejects an out-of-order atom stream (no silent re-sort), canonical-stream out-of-whole-artifact-scope tripwire + the persist-gaps decision recorded for S1.5 (carried note), 0.5-floor over-claim softened. 32 tests, 14 mutants killed. **Closure LANDED (post-S1.5, #21):** `test_roundtrip_gate_closure.py` routes the gate through the S1.5 store's **public read path** — each witness captured → `save_stream` → `load_stream` → reconstructed byte-exact from the **loaded** atoms+gaps, checked against the independently-read fixture (non-tautological — the test brings the oracle, not the store's own `source_hash`); **witness iteration** via a new `stream_ids(workspace)` enumeration primitive (sorted `data/atoms/*.json` stems) + filter-by-`.kind`; **canonical load** routed through `assert_reference_integrity`, never the whole-artifact gate (the carried scope decision); full-gate `assert_no_wholesale_exclusion` over the loaded stream. **Back-door-read negative:** corrupt the **store** on disk while the raw witness fixture stays byte-identical → `load_stream` fails loud (it validates the *store's* bytes, not the still-correct raw file a back-door would have read + falsely passed); + overlap / implicit-gap negatives through the same read path. 7 closure tests; closure binding mutation-proven (`stream_ids` glob + that the negatives genuinely depend on `load_stream`'s self-checks); full suite **520 green**. | §3.0, §9; D22 | S1.3a | round-trip + negative tiers: byte-exact via the public read path; overlap/implicit-gap/back-door read each fail loud | `GATE` | `DONE` |
| S1.5 | **Atom-store persisted schema + independent version** (per-witness + canonical streams), its own lineage entry + **its own S8.1 stale class** (M3); store round-trip asserts **serialization-invariance** of `raw_span` / `raw_source_hash` / `geom` / `derived_from` (not just text); reference-integrity (every `derived_from` back-link resolves). **Core landed** (`structure/atom_store.py`, #22): `AtomStream` (`witness`\|`canonical` — a witness tiles one source so it carries gaps + a `source_hash` anchor; canonical tiles no single source so it carries neither, integrity = reference-integrity + the per-atom S1.2 floor), `to_json`/`from_json` (full-fidelity envelope; `from_json` is a **total load-boundary contract** — a valid stream or `StaleArtifactError`, errors.py exit **10**, the new M3/S8.1 stale-class raiser; a stale `schema_version`, wrong `stale_class`, missing key, unknown kind, or a wrapped model-invariant each fail loud), `save_stream`/`load_stream` (atomic JSON under `data/atoms/<id>.json`; **load runs the anchored round-trip self-check** `hash_raw(reconstruct_source(atoms, gaps)) == source_hash` → a persisted `atom.text`/gap drifted off its span fails loud, the whole-artifact #21 value now anchored in the store), `assert_reference_integrity` (every canonical `derived_from` resolves, else `CaptureError`). **Persist-gaps decision applied** (carried #21 audit): the per-witness `GapRecord` stream is persisted as **bytes** (a mixed-whitespace `\n \t\n` gap proves bytes-not-width — atoms-only would round-trip vacuously on PLL's newline-only copies); `source_hash` anchors the round-trip non-vacuously. `ATOM_STORE_STALE_CLASS="atom-stream"` registered alongside `ATOM_STORE_SCHEMA_VERSION=1` (artifacts.py). **5-lens overlapping adversarial audit** (cold-read / data-loss-falsifier / premise-demolisher / downstream-delivery-skeptic / taxonomy-atomicity — deliberately divergent *stances + briefings* to break confirm-shaped patterning) → real defects found + fixed: (D1) `from_json`/`load_stream` "total contract" leaked raw `TypeError` (wrong-typed field) / `json.JSONDecodeError` (non-JSON file) / non-object document — now a `Mapping` gate + `(ValueError, TypeError)` wrap + JSON-decode wrap, all → `StaleArtifactError`; (D2) the persisted per-atom `raw_source_hash` was **inert** at load (whole-artifact anchor checks the concatenation → a *compensated* drift across an atom boundary false-passed, and canonical streams had **no** load text-integrity) — added `assert_atom_hashes` (per-atom `hash_raw(text)==raw_source_hash`, runs on every load incl. canonical); (D3) `atom_id` uniqueness unenforced despite `atoms.py` naming the store the enforcer — now `duplicate_atom_ids` in `__post_init__`; (D4) NaN/inf geom float broke `==` + wrote non-RFC-JSON — `allow_nan=False` in `jsonio` (fail-loud at save); (J3) read-path `stream_id` not flat-stem-guarded — `_check_stream_id` now in `stream_path`; (J5) canonical atom with empty `derived_from` passed vacuously — reference-integrity now requires ≥1; (J6) invented-coords-on-absent geom silently normalized — `_geom_from_json` reconstructs faithfully + lets the model guard fire; (J2) `CaptureError` docstring broadened to own cross-stream reference-integrity. 64 store tests (synthetic + real `copy{1,2,3}`), **29 atom_store mutants + the jsonio guard killed, 0 survivors**; full suite **513 green**, ruff clean, neutrality 48. **Unblocks the S1.4 (#21) closure** (route #21 reconstruction through `load_stream` + the back-door-read negative). | §3.5, §3.6, §11.1; D21 | S1.3a | reference-integrity + round-trip tiers: schema validates, version registered, serialization-invariant, back-links resolve | `BUILD` | `DONE` |

> **S1.4-closure ↔ S1.5 contract — two decisions surfaced by the S1.4 5-lens audit, recorded here so
> S1.5's store round-trip is not vacuously green.**
> - **Persist the gap records (or the witness source) — gap whitespace is NOT recoverable from span
>   widths.** S1.4's whole-artifact reconstruction rebuilds a witness from `atom.text` ⊕ `gap.text`. The
>   inter-atom whitespace (`GapRecord.text`) is real bytes — a width-N gap can be spaces / tabs /
>   newlines in any mix — so a store holding **atoms only** (as the §11.1 sketch draws, plus the
>   lineage manifest's source *hashes*, which cannot rebuild bytes) **cannot** reconstruct the witness
>   without re-reading the raw file, which is exactly the back-door S1.4's done-when forbids. PLL's
>   copies happen to be newline-only — so an atoms-only store round-trip would pass **vacuously** on PLL
>   and silently lie for a tab/space-mixed witness. **Leading choice:** persist the per-witness
>   `GapRecord` stream (span+text) in the atom store and add `GapRecord` **serialization-invariance** to
>   S1.5's round-trip done-when; alternative is persisting the witness `source`. Decide at S1.5; do not
>   ship an atoms-only store whose round-trip re-reads the raw witness.
> - **The canonical/reconciled stream is OUT of the whole-artifact gate's scope.** Its atoms adopt their
>   `derived_from[0]` witness's address, so different atoms point into different witness sources and no
>   single `source` tiles them — `assert_production_roundtrip(canonical, …)` raises loud (message reads
>   "silent loss", the wrong cause). Canonical atoms are verified **per-atom** against each
>   `derived_from` witness by the S1.2 floor, never through this whole-artifact gate. Pinned by the
>   greppable tripwire `test_canonical_stream_is_out_of_whole_artifact_scope_until_s1_5`
>   (`test_roundtrip_gate_real_input.py`, mirrors the S1.3a.4 page tripwire). When S1.5 wires
>   "canonical-projection load" into the public read path, route per-witness reconstruction through the
>   gate and canonical through the per-atom S1.2 floor — not the whole-artifact gate.

> **S1.5 audit — principled deferrals (not gaps).** Two findings from the 5-lens audit were
> *deferred by decision*, recorded so they are not silently dropped:
> - **Stale-vs-corrupt error split → decide at S8.1.** `from_json` funnels both a genuinely *stale*
>   `schema_version` (migratable — the M3/S8.1 stale-class hook) and a *corrupt/malformed* envelope
>   (un-migratable — re-capture) into one `StaleArtifactError` (exit 10). The message distinguishes
>   them; the *type/code* does not. Harmless until a consumer must branch "auto-migrate vs alert" — and
>   that consumer is **S8.1's stale-class migration router**, which does not exist yet. Deciding the
>   split (sibling `MalformedArtifactError`, or a structured discriminator attr) now would be YAGNI
>   against an unbuilt requirement; revisit when S8.1's router is designed ([[deferral_for_information]]).
> - **`Atom` lacks a `len(text)==raw_span`-width invariant (asymmetry with `GapRecord`, which has it).**
>   This is the structural enabler of the *compensated-drift* false-pass; S1.5 closed the **store's**
>   exposure at load via `assert_atom_hashes` (per-atom `hash_raw(text)==raw_source_hash`), but the
>   model-level invariant is an **S1.1/atoms.py** surface (frozen/`DONE`), out of S1.5 scope. Adding it
>   to `Atom.__post_init__` is defense-in-depth for any future non-store caller — a candidate burnish
>   for an S1.1 follow-up, not reopened here.

> **S1.4 has a delivered first slice — build on it, don't re-derive.** The S1.2 model floor was
> already extended to **real PLL bytes**: `tests/unit/test_roundtrip_real_input.py` (`56f9cba`, landed
> under issue #15) proves the byte-exact floor on the committed copy3 witness (frozen page-61 anchor —
> span + `sha256` + verbatim head/tail via an independent hash) plus a capture-completeness/topology
> chokepoint (`assert_page_map_tiles_witness`: in-bounds/monotonic/non-overlapping spans, `⟨PAGE:N⟩`
> count == map pages, every uncovered char marker-or-whitespace — 278==278, 99.6% covered, 0 residue).
> What remains for the full GATE: reconstruct through the **atom-store public read path** (needs
> **S1.5**) over the S1.3a stream, with explicit inter-atom **gap records** — the whole-artifact
> byte-exactness the S1.2 per-atom slice hashes do **not** pin (the listed dep is S1.3a; sequence S1.5
> accordingly).

> **S1.3a is not a read-only re-projection.** reconcile segments copy1/2/3 in memory and
> **discards** the per-witness structural streams (§1 multi-witness fact), persisting only
> the merged `reconciled_chapters.json` + word-flags. So per-witness atom streams must be
> **re-built** by re-running segmentation on the raw copies — that algorithm is S1.3a's
> deliverable; do not describe it as "read-only from reconcile." This is the F4 fix: each
> witness atom stays addressable, and the legacy `(ch_id, para_idx)` disagreement flags become
> L3 spans in **S7.1b** (the task that keeps the promise).

> **S1.3a.1–.5 are post-review burnish (issue #16 audit), not reopened scope.** S1.3a itself
> shipped `DONE` (`4ff5fc9`); these harden it — loud boundaries (.1/.2), oracle-backed counts
> (.3), a forward tripwire (.4), honest prose (.5). They are **independent of each other**, so
> they run **concurrent with S1.3b/S1.4** (W1) in the listed priority order, and none changes
> the S1 rollup beyond the already-`TODO` S1.3b/S1.4/S1.5.

> **Deferred at S1.3a — `PAGE_PENDING_ANCHOR` sentinel (revisit at S7.1b).** L1 gives every
> page-less atom one sentinel, `PAGE_UNMAPPED (-1,-1)`, and the canonical stream inherits it (it
> adopts copy1's unmapped address; copy3 — the only page-bearing witness — is word-level and
> absent from the structural alignment, so **the whole canonical stream is page-less at L1**). We
> deliberately did **not** split a second sentinel `PAGE_PENDING_ANCHOR` ("page derivable via a
> sibling witness, not yet anchored") from `PAGE_UNMAPPED` ("no witness has a page map at all").
> **Why now:** for PLL, copy3 *always* has a page map, so *every* copy1/copy2/canonical atom is
> equally "pending" — the second sentinel would add a model constant with **no current consumer**
> (YAGNI, Principle 2). **Revisit at S7.1b:** the copy3↔canonical word-level linkage S7.1b
> establishes is the prerequisite for attributing pages to canonical text; *there* "pending vs
> intrinsically-unmapped" finally gains a consumer and may earn the split. The S1.3a.4 tripwire
> pins the exact atom set that change will touch.

> **Carried review concerns (issue #16 audit) — revisit later, opened-not-closed by the burnish.**
> Three threads S1.3a.1–.3 *surface* but do not *settle*:
> - **N-way structural alignment.** S1.3a.1 makes >2 structural witnesses **fail loud**; it does
>   not build genuine N-way (multiple-sequence) structural alignment. No current book needs >2
>   structural witnesses (PLL's copy3 is word-level), so the capability stays deferred — **revisit
>   when a book presents ≥3 paragraph-structural witnesses.** The fix removes the *silent* drop,
>   not the *limitation*.
> - **`autojunk=True` is explicit + source-guarded, but the policy is not *validated*.** S1.3a.2
>   ends the reliance on the *silent default* — and an AST guard keeps the call explicit — but it
>   does not prove `True` is the right policy. The junk heuristic discards high-frequency keys —
>   good on PLL's OCR-noise copies (the discarded keys are noise), but possibly wrong on a cleaner
>   witness set where a legitimately-repeated key (a refrain, a formula) would be junked and an
>   anchor lost. **Return to review the policy itself** (keep `True` / set `False` / inject a
>   per-book junk predicate) when a second book's witnesses are aligned, or if a canonical anchor
>   count looks degraded. (The ownership *guard* is scoped to this one call; extend the pattern if
>   another load-bearing stdlib default enters `structure/`.)
> - **Characterize "both-derived" as a vector, not a scalar.** Today the canonical projection is
>   summarized by one number (~45% both-derived). A single ratio hides *where the unmatched mass
>   sits*: a set `{both-derived, copy1-only, copy2-only}` plus **the source of greatest
>   single-derived density** would expose an OCR-quality asymmetry between the copies (one witness
>   carrying the bulk of the single-derived tail is a real signal, invisible in the headline %).
>   **Revisit when canonical-quality reporting is built** (with S1.3a.5's prose, or a later
>   diagnostic) — report the ratio set + the greatest-density source, not just the scalar.

> **S1.3b completeness discriminator — integration contract for S9.1 (revisit when S9/S9.1 land).**
> `check_completeness` hard-fails a boundary-class `unknown` by matching the atom's L1
> `capture_provenance_class` against the profile's `boundary_classes`. The axis **must** be
> independent of the typed `block_class` — an atom is never both `block_class∈boundary` *and*
> `block_class==UNKNOWN` — so `capture_provenance_class` (the structural slot the bytes were
> captured into) is the only available independent per-atom axis at L1. **Contract for S9.1:** the
> profile's `boundary_classes` must therefore be a set of *capture-provenance-class* values
> (heading / footnote-call / embedded-letter-boundary as **capture** classes), not typed-block-class
> labels — and capture (S1.3a's `classify_line`, eventually S9) must tag those boundary lines with a
> distinct `capture_provenance_class` (today PLL captures every body run as one `authorial` class, so
> headings are *not yet* separately capture-classed — that granularity is S9's job). **Revisit
> condition:** if S9's recognizer proves the coarse capture-class axis too weak (e.g. a heading and a
> body paragraph share a capture class and must be told apart only post-typing), introduce an
> explicit per-atom expected-class/region field then — pinned to `capture_provenance_class` now
> because that is the field that exists and carries the distinction, no new model constant (YAGNI).
>
> **Two residuals surfaced by the S1.3b adversarial pass (independent reviewer), recorded not
> dropped:**
> - **The boundary hard-fail is dead on *real* input today — by a capture-scope CHOICE, not an
>   impossibility (premise corrected by the 5-lens audit).** An earlier framing ("no component could
>   identify a boundary under *any* design") was **wrong**: a heading recognizer already exists in the
>   live tree (`lang/italian.py:211 is_chapter_heading`, a ported regex), and `classify_line` is an
>   injectable seam. The branch is dead for one concrete reason — `capture.py`'s coupling forces a
>   named `classify_line` result to `processing_scope="excluded"` (~124–135), so no *included*
>   boundary capture-class can exist yet. Relaxing that coupling + injecting a heading-aware
>   `classify_line` would make the branch fire on real PLL input **without** the S9 recognizer. S1.3b
>   **deliberately keeps capture coarse** (that relaxation is S9.1/capture scope), so the branch stays
>   synthetic-tested — a scope decision, not a law of physics. **Considered-and-rejected alternative:**
>   *defer the whole boundary regime to S9.1* (ship only the degenerate + body-leaf regimes, which DO
>   fire on real input). Rejected because the mechanism is cheap, de-risks S9, and the degenerate
>   regime reuses the same machinery; **but** the public surface (`boundary_classes` param + the
>   boundary `raise` + S9.1's profile-schema contract) is thereby committed to a discriminator the
>   revisit note above marks provisional — a conscious seam-vs-defer trade, logged here so it is not
>   read as inevitability. Do not re-inflate the synthetic branch to a working real-input guarantee.
> - **A profile declaring a real block class literally named `"unknown"` would alias the
>   sentinel** (`classify.UNKNOWN`), making resolved atoms read as incomplete. Unguardable in
>   `check_completeness` (it never sees the profile's full block-class vocabulary). **Defer to S9.1
>   profile-load validation** — reject a profile whose declared classes collide with `UNKNOWN` — and
>   keep `UNKNOWN` reserved (already asserted in prose, `classify.py` ~14–15).
> - **`to_review`'s forward consumer is the governance surface, NOT S6's truth-table (audit
>   correction).** The done-when says "reuses the S6 truth-table machinery", but S6.2 computes
>   behavioral *flags* for *resolved L2 nodes* from L2 provenance, whereas `to_review` queues
>   *unresolved L1 atoms* keyed on L1 `capture_provenance_class` — a different layer/axis/lifecycle.
>   The likelier home is the **S8.1-style HITL stale/repair report** (where re-bind failures already
>   route a human). `typed.py` now says "feeds a review/governance surface; consumer unsettled" rather
>   than asserting S6 subsumption. **The done-when wording is a spec tension to resolve at S6/S8.1**,
>   not just prose — flagged, not silently rewritten.
>
> **Cross-file items from the 5-lens audit — THREE APPLIED this pass (authorized), two remain:**
> - **APPLIED — Neutrality: `capture.py`'s `body_class` default `"authorial"` → `"body"` (S1.3a).**
>   "Authorial" is a *content/editorial* word ("who authored it") that was baked as the default in a
>   *capture-provenance* field (`atoms.py` defines that field as distinct from L2 content provenance);
>   S0.2's literal scan misses it, and it was asymmetric with `boundary_classes` (required, no default).
>   Renamed to the slot-neutral `"body"`. (Ripple: `test_raw_capture` default assertion + the S1.3b
>   real-capture test updated; hand-built fixtures keep an arbitrary class, proving the field is free.)
> - **APPLIED — Robustness: `Atom.__post_init__` now validates `processing_scope ∈ {included,
>   excluded}` (S1.1).** The free-`str` field was the root cause behind the whitelist hole; the closed
>   vocabulary at the model fixes the class, not the instance — a typo'd scope now fails at
>   construction, so it can never reach `check_completeness` and vanish. (The S1.3b `!= excluded` filter
>   stays as defense-in-depth + the semantic scoping.)
> - **APPLIED — Stated-but-unenforced: `BlockClassification.__post_init__` now rejects an empty
>   `typed_by` (S0.4).** The "never an anonymous label" guarantee is enforced, not just prose — B's
>   override attribution (R3/D5) can no longer be blank.
> - **APPLIED (S1.4, #21) — Unowned seam: "wholesale-wrong-exclusion."** A capture that mis-tags all
>   body as furniture passes `assert_capture_tiles`, the byte round-trip, AND `check_completeness`
>   (vacuously complete, `processed_count=0`). `roundtrip_gate.assert_no_wholesale_exclusion` now owns
>   it: the processed (non-excluded) atoms must carry ≥ a `min_included_fraction` (default 0.5 — the
>   natural "body dominates furniture" boundary, per-book tunable) of the source's non-whitespace
>   content; an all-excluded capture raises. Exercised on real `copy{1,2,3}` (clears the floor with
>   real furniture present) + an all-excluded real witness (raises). Lives in S1.4's gate, not
>   S1.3b's typing-completeness.
> - **REMAINS — spec tension:** the done-when's "reuses the S6 truth-table machinery" vs the audit's
>   finding that `to_review` belongs at the S8.1-style governance surface (layer/axis mismatch) —
>   resolve at S6/S8.1, flagged above.

| ID | Deliverable | Refs | Deps | Done-when (tier) | Tag | St |
|---|---|---|---|---|---|---|
| S2.0 | **bbox + text↔box-alignment PROBE (GATE).** On real PLL pages, measure (i) does a usable OCR word-box layer exist, and (ii) **can those boxes be trusted as anchors for the witness text** — the boxes come from a *different* OCR pass (PyMuPDF) than the witness text (IA-Tesseract / Gemini), so "carries its primary witness's box" is itself a cross-engine match (M1). Sample **stratified across** front matter, dense prose, page furniture, chapter starts, footnotes, bad-OCR regions, and the embedded-letter area (≥10 pages is a floor, not the spec). A negative/low-quality outcome **(a)** reroutes to **S2.1-alt** and **(b)** demotes geometry in **S5** (primary → tie-break / no-geometry, M2) | §3.0; D30; §1 portability note (`pll` PDF is an image scan) | S0.1 | a written probe result over the strata; both the S2.1 path AND the S5 geometry-mode are **chosen by evidence**, with measured text↔box alignment quality | `GATE` | `DONE` |
| | **S2.0 outcome (POSITIVE, conditional — revised post 5-lens audit, `docs/probes/s2_0_adversarial_audit.md`).** Probe `books/per_la_liberta/probes/s2_0_geometry_probe.py`; written result `docs/probes/s2_0_geometry_alignment.md`. Both PDFs are image scans (0 native boxes); box layer **generated** by fresh PyMuPDF+Tesseract(ita,300dpi). Token anchorability vs copy3/Gemini (n=37): BoW median **0.939**/mean 0.925; **content-token** BoW median **0.929** (what re-bind gets). Body is two-column (detector finds **30/37**, not the audit-killed "37/37" artifact) → naive full-width ordered **0.49**, column-order recovered from box coords lifts it to **mean 0.92 / 87% pass@0.85 on two-column pages (n=30)** but **mean 0.851 / 73% pass over all pages** (single-col + hard edges drag it). copy1 (structural witness) confirmed column-ordered (0.98). **Decision (a): S2.1 NORMAL path** (not S2.1-alt) + segmentation front-end (density / column-detect / human-review; see S2.1 row). **Decision (b): S5 geometry = conditional-primary, RE-GATE after S2.1** (NOT settled-PRIMARY — the audit showed the pre-registered *naive* metric is 0.49/no-geometry-band and PRIMARY rested on a median hiding mean 0.82 + a detector prototype); primary-grade on confident two-column body pages, re-gated on mean + per-page pass-rate after S2.1 builds the real detector + two-branch order sourcing; absence first-class, coords never invented | | #18 | written probe result delivered; both decisions evidence-chosen + adversarially audited | `GATE` | `DONE` |
| S2.1 | `GeometrySource` seam (Protocol) + backend on the **path S2.0 selected** (= NORMAL, fresh PyMuPDF+Tesseract(ita) OCR — both PDFs are image scans, no native layer): textpage/bbox layer → `atom.geom` word-box union, via an **explicit witness-text↔geometry matcher with its own fail-loud mode**; the matcher writes `{geometry_engine, match_method, match_confidence}` into S1.1's frozen slot; **unmatched boxes are unusable for primary re-bind**; canonical atom carries its primary witness's box **only where matched**. **S2.0-mandated segmentation front-end** (design inputs in `docs/probes/s2_0_geometry_alignment.md` §"S2.1 design inputs"; revised post-audit): **(0) two-branch reading-order sourcing** — when a column-correct text witness exists (PLL copy1/2/3, copy1 verified 0.98) it is the order ORACLE and boxes position-match it (geometric detector = cross-check); when NO prior witness exists (image-only — must not be presumed away) the geometric detector is the primary order source + human-in-loop backstop; **(1) density pre-check** — a **two-sided / band classifier** (NOT a single fixed ink threshold — audit proved ink-fraction is a non-monotone continuum: dark endpapers read 0.97, content chapter-ends read <0.038) flagging near-blank pages so hallucinated boxes (p6: 658 boxes / 7 tokens) aren't trusted; **(2) column detection** via projection-profile / Recursive X-Y Cut valley (the discriminator; mirror-symmetry rule DROPPED as redundant + wrong on asymmetric multi-column; cross-page prior retained) — yields reading order for free; **(3) human-review worklist** with a SPECIFIED confidence metric/threshold/human-verdict-schema/volume-bound (audit: not a slogan) for pages the front-end can't score, **before** the gate — classifiers calibrate to **abstain** (per [[project-ingestion-human-in-loop]], S5.2 monotone-strictness). `geom.present=false` only after BOTH auto-detection and human review decline | §3.0, §11.1; D30; `docs/probes/s2_0_geometry_alignment.md` | S1.1, S2.0; issue #29 (parent — children minted when the lane opens) | seam injectable; backend yields matched boxes (+ provenance) for a PLL page fixture; unmatched → `geom.present=false`, not invented; low-confidence pages routed to human review | `BUILD` | `TODO` |
| S2.1-alt | **Negative-branch fallback as a real deliverable** (only built if S2.0 is negative/below-threshold): name the coordinate source (word-coordinate re-derivation, or accept no-geometry), the atom-matching method, the acceptable quality threshold for S3/S5, and **what is disabled if unmet** (S3's geometry base layer; geometry as S5's *primary* anchor → S5 runs geometry-demoted / no-geometry). Not an architectural pause — a scoped path. **S2.0 outcome: NOT triggered** (probe positive — geometry viable, S5 conditional-primary); spec retained as the conditional fallback | §3.0; D30 | S2.0 (negative) | the fallback path is specified + (if triggered) implemented; S3/S5 know exactly what they lose | `BUILD` (conditional) | `N/A (S2.0 positive)` |
| S2.2 | Geometry property tests: boxes within page bounds; source-order ↔ geometric-order coherence on a real page; primary-witness box on canonical atoms **where matched**; **absent/unmatched geom is representable and excluded from primary re-bind**. **PLUS the S2.0-mandated RE-GATE** (binding, not prose — the S2.0 verdict was *conditional*-primary): measure col-aware ordered coverage on the **as-built** S2.1 detector over a breadth sample (n≥30), require **mean ≥0.85 AND per-page pass-rate ≥85%** (not a page median — the audit showed median hid a 0.82 mean / ~30% fail tail), and on the result **confirm S5 `geometry-primary` or demote** the mode (record in lineage). Until this passes, S5 runs conditional-primary | §9; `docs/probes/s2_0_geometry_alignment.md` | S2.1; issue #30 | property: those four assertions hold **and** the re-gate measures the as-built detector on mean+pass-rate and sets/confirms the S5 mode | `BUILD`/`GATE` | `TODO` |

> **Risk (now gated, not just noted):** geometry presupposes a usable OCR bbox layer on the
> LOC PDF **and** that the layer anchors the witness text. S2.0 is the build-now probe that
> settles both before S2/S3/S5 commit; its negative branch is a real, scoped fallback
> (S2.1-alt) and a traced S5 ripple (geometry demoted), not afterthoughts.

### S3 — Space / fragment reconstruction, D30 (concern A) `BUILD`

| ID | Deliverable | Refs | Deps | Done-when (tier) | Tag | St |
|---|---|---|---|---|---|---|
| S3.0 | **Resource + normalization-policy loading/versioning.** Register dict + ≥2-of-3 oracle **and** the pre-lookup normalization policy (tokenizer, case-fold, accent-fold) **versions into the lineage manifest** (so an S8.1 stale-fail catches a dictionary swap **or** a normalizer change — two distinct stale classes, M-pass FU). Bind the source-language resource through the **structure/language profile**, not a core literal (`feedback_engine_agnostic`: dictionary/oracle is input config, never baked into `structure/`) | §3.0, §3.6; D14, D21, `feedback_engine_agnostic` | S0.1 | resources + normalizer load via the profile; both hashes enter lineage; neutrality tier green | `BUILD` | `DONE` |
| S3.1 | Zipf-cost DP word-segmentation over `data/dictionaries/it_combined.txt` (`wordcost = -log prob`, DP + backtrack), **oracle-gated** by the ≥2-of-3 period dictionaries. Recovers split/merged spaces & fragments — **not** by inverting `collapse_spaces`/`rejoin_lines` | §2-A, §3.0; D30 | S2 (geom base layer), **S3.0** | property: known fragments re-segment | `BUILD` | `TODO` |
| S3.2 | Corruption-guard tests: a period-form the ≥2-of-3 oracle accepts is **not** "corrected" away; regression set drawn from `project_cleanup_corruption` | §9 space-recon; `project_cleanup_corruption` | S3.1 | space-recon tier green incl. the no-corruption negatives | `GATE` | `TODO` |

> **Risk:** modern-frequency cost can outvote a valid 1913 form. The oracle gate is the only
> thing between this step and re-running the cleanup-corruption mistake; S3.2 is a gate, not
> a nicety. *(S3's relationship to the PLL golden is **resolved**, § Audit log: S3 changes
> text by design, so it is validated by its own space-recon tier (S3.2) + the raw floor
> (S1.2/S1.4) and feeds the v2 **instance**, never the no-regression golden (S10.4). The
> v1↔v2 accuracy of S3's output is measured academically, post-build, by S11.)*

### S4 — L2 projections + `node_id` + structure map (concern B) — **keystone**

The durable catalogue. **S4.5 (D18) is the schema-birth gate for the whole B/C substrate;
S9.4 is its end-to-end generality twin.**

| ID | Deliverable | Refs | Deps | Done-when (tier) | Tag | St |
|---|---|---|---|---|---|---|
| S4.0 | **Constants + error-code module** (moved out of S4.4 — X18; decision-owned by D-S4-F): `STRUCTURE_MAP_STALE_CLASS`; pre-placed **inert** `RELATION_STORE_STALE_CLASS` (O1 — declares a future layer identity, no relation loader exported); the `schema_status` module map (§1.2.2); the closed **`EC.*` code set** in `structure/errors.py` (§4.0) so B-2+ can assert on codes | s4_plan §1.1/§4.0; D-S4-F | S0 | inv 12a (constants + inertness), 12c (closed-set pin + partition), 15 (neutrality) | `BUILD` | `DONE` |
| S4.1 | L2 projection model: container vs leaf; open per-book block vocabulary (PLL: `paragraph`, `verse`, embedded-letter container); **no-double-ownership** invariant; **B re-groups / re-types at the node level** over existing, unchanged atom ids (the block-classifier output is correctable, R3/D5; **true re-atomization — split/merge → new atom ids — is S8.2/D25**, s4_plan §1.3.5) | §3.1, §3.2, §11.2; D10, **D5/R3** | S1.1 | property: no atom owned twice; ragged depth 0–4 + recursion + **heterogeneous sibling classes** representable; a mis-typed atom is corrected by B (re-type) | `BUILD` | `DONE` |
| S4.2 | `node_id` identity + minting split: opaque, persisted, **never recomputed** from position/designation/content; humans mint containers, extractor machine-mints leaves (counter/ULID); `minted_by` field | §3.4; D11, D20, D33 | S4.1 | property: id stable across re-serialize **and after a positional move** (re-mint proves position-independence) | `BUILD` | `DONE` |
| S4.3 | Handle policy + rendered handles + alias records: per-node-class `handle_policy` (`position-path` \| `designation-string` \| `title` \| …) with inheritance; `(node_id, handle_policy)` renders `short`/`parse_md`/`html_slug`; alias record `{handle_type,value,scope,locale_or_witness,target_node_id,valid_from,valid_to,status}` | §3.4, §3.6; D12, D24, D33 | S4.2 | property: handle change leaves `node_id` fixed, old handle survives as alias | `BUILD` | `DONE` |
| S4.4 | `structure_map.json` **schema** + **lineage manifest** header. Manifest carries, **each independently versioned with its own stale class** (M3): raw witness hashes; the **atom-store** schema version (S1.5); the **relation-store** schema version (S7.1c); `canonical_stream_id` + canonical-projection hash; the **resource + normalizer** versions (S3.0); profile + recognizer versions. `geom` shape consumed from S1.1's frozen slot (the frozen field set incl. match-provenance; the `canonical_geometry_hash` covers the REGION fields only — `{atom_id, present, page, bbox}`, provenance deliberately excluded, s4_plan §3.E.1) | §3.5, §3.6, §11.2; D21 | S4.1–S4.3, **S1.1 (geom shape)** | schema validates; reference-integrity tier (every ref resolves); manifest lists all three persisted-layer schema versions; schema's `schema_version` `const` **equals** `STRUCTURE_MAP_SCHEMA_VERSION` — bound by validating the version-derived fixture (`_generate_structure_fixture.py`) against the schema, **not** a hand-copied literal (the `manifest.schema.json` precedent hard-codes the const with no Python constant behind it — do not repeat it) | `BUILD` | `DONE` |
| S4.5 | **D18 GATE (schema born) — second-structure synthetic fixture built to DIFFER from PLL:** depth-0 body (no parts), `designation-string` handle policy, **non-ordinal headings**, **mismatched body segmentation**, alias-uniqueness-in-scope, **malformed/incomplete-manifest rejection** (a negative fixture — a stored-vs-live staleness *comparison* is S8.1, M9), **relation-endpoint shape / reference placeholders** (*resolution* is S7/S9.4, R2-03). **Folded into the S4 keystone (O5): this gate going green is what closes the milestone** — flipped `schema_status` v1 → `born` at B-6. **This is the SAME adversarial fixture S9.4 drives end-to-end** (reuse, not a new one). **Distinct from `books/synthetic`** (prefazione + 1 part, Italian ordinals, H2/H3 — a miniature PLL, *not* a differ-fixture) | §6, §9; D18; `feedback_single_fixture_blind_spots` | S4.1–S4.4 | the hand-authored fixture validates; **schema is not "born" until it does**. (Generality is proven separately at S9.4) | `GATE` | `DONE` |
| S4.6-pre | **Freeze + persist the PLL atom streams** (row added 2026-07-02 from runway.md §3 item 1): canonical atom ids are **positional** (`canonical_NNNNN` from capture) — a capture-algorithm change renumbers the stream, and S4.6's hand-authored map references those ids *before* S5's re-bind machinery exists. Mitigation is procedural: capture the real copies through the live producers, persist via the S1.5 store into the PLL book workspace, record the stream hashes (the manifest's stream hashes turn later drift into S8.1-detectable staleness, not silent corruption). Cheap; **must precede S4.6** | runway.md §3.1 | S1.3a, S1.5 (#22); issue #31 | PLL witness + canonical streams persisted in the book workspace; hashes recorded; S4.6 authoring references only these frozen ids | `BUILD` | `DONE` |
| S4.6a | **Authoring-evidence sidecar — engine half** (runs BEFORE S4.6 despite the id). **Owner: engine** (vs S4.6's Ben/HITL): `structure/evidence.py` — loader for `structure/schema/authoring_evidence.schema.json` + the digest-staleness validator (evidence stale **iff** its bound node's canonical structure digest — `node_class` + ordered `children` + owned atom ids via the `lineage` producers — changes; `map_revision` is bookkeeping, never the trigger). Sidecar optional at generic load, required at the S4.6 authored-map gate (every `minted_by:human` container ↔ one non-stale evidence entry). Own `AUTHORING_EVIDENCE_SCHEMA_VERSION` + stale class (M3). Inherits inv 15 + ships a digest-staleness red test. **PLUS store-backed reader glue (folded 2026-07-02, runway.md §3 item 2):** workspace → `load_stream`× → `StreamAtomReader`, composing `assert_reference_integrity` on load — `StreamAtomReader` takes in-memory streams, and nothing yet loads a workspace's persisted streams into a reader; both the S4.6 authoring gate and S5's re-bind consume it | s4_plan §1.4.1a/b/c; Audit 15, M9/X20; runway.md §3.2 | S4.4, S1.5 (#22); issue #32 | digest-staleness red test; inv 15; the S4.6 gate consumes it; the glue loads a workspace's persisted streams into a `StreamAtomReader` with reference integrity asserted | `BUILD` | `TODO` |
| S4.6 | **Hand-author the PLL container map** (~61 containers). **Owner: Ben (human-in-the-loop).** Workflow specified: which file is edited; the known PLL skeleton (prefazione + 2 parts + 57 chapters + the embedded letter) **seeds candidates**; the **embedded-letter placement is verified at authoring** (pin the Mazzini-letter's chapter); review comments captured; minimum evidence beyond the skeleton recorded. S9 later makes the map *recognizer-suggested* — that comparison is **advisory** (gate = every recognizer disagreement surfaced + reviewed + accepted-or-explicitly-overridden, **human ruling authoritative** per S8.2), never "recognizer must match the hand map" | §3.5; D28/D29 (HITL premise) | S4.4, S4.6-pre (#31), S4.6a (#32) | the authored map validates against PLL's known skeleton; embedded-letter chapter pinned; review trail captured | `BUILD` (human) | `TODO` |
| S4.7 | **Scale check (D35).** Named ops under test — tree traversal, reference-integrity resolution, re-bind lookup — stay **sub-quadratic** across sizes (10⁴ → 10⁵ leaf nodes); budget is a rough **wall-clock + peak-memory ceiling that includes serialize + load + index-build** (a CLI pays the load cost every invocation), **machine ops only** (the human container-authoring ceiling is **O3**, not this gate). CI: a small always-on shape check; the full 10⁵ tier nightly/opt-in. Shares one benchmark fixture with the S1.4/S1.5 store round-trip | §3.5; **D35** | S4.1, S4.2; issue #33 | scale tier: growth ratio sub-quadratic incl. load/index time; flat addressable storage holds at 10⁵ within budget | `BUILD` | `TODO` |

> **S4.4 + S4.6 bootstrap order:** the hand-authored PLL map (S4.6) gives S5–S8 something
> real to chew on; S9 later makes that map *recognizer-suggested* (advisory). The existing
> `books/synthetic` is a pipeline fixture (copy1/2/3 → reconciled), **not** a structure-differ
> fixture — S4.5 builds a new one (depth-0 / designation-string, Kybalion- or
> Tractatus-shaped), reused by S9.4.
> **Design ceiling for S4.7:** PLL ≈ 10³ leaf nodes; Pepys ≈ 10⁴; a full reference-work volume
> (Britannica-class) ≈ 10⁵ — two orders above PLL. The test asserts sub-quadratic *shape*, so
> the number can move without reworking the task.

### S5 — Re-binding, D33 (concern B) `BUILD`

| ID | Deliverable | Refs | Deps | Done-when (tier) | Tag | St |
|---|---|---|---|---|---|---|
| S5.1 | `rebind_anchors` per node: **geometry region** (primary where matched, from D30 word-boxes), **fuzzy/fail-loud content fingerprint** (never the exact-substring the live tree tombstoned), **structural-path** tie-break. **Three explicit operating modes — `geometry-primary` \| `geometry-tie-break` \| `no-geometry` — selected by S2.0's outcome and recorded in the structure-map lineage / rebind config** (M2), so a re-bind result is interpretable after the fact. **S2.0 selected `geometry-primary` CONDITIONALLY — re-gate after S2.1** (post-audit, `docs/probes/s2_0_adversarial_audit.md`): primary-grade on confident two-column body pages (col-aware ordered mean 0.92 / 87% pass@0.85, n=30) but NOT settled (all-pages mean 0.851 / 73% pass; pre-registered naive metric 0.49); geometry primary where the S2.1 matcher is confident, fall back to content + structural-path where `geom.present=false`. Re-gate the mode at **S2.2** on the as-built S2.1 detector, on **mean + per-page pass-rate** (not a median). When a column-correct text witness exists it supplies reading order and geometry cross-checks; the geometric detector is the primary order source only on the no-witness branch. Re-attach algorithm with an **explicit confidence threshold** defaulting toward **fail-loud on doubt**: unique + above-threshold → bind; else fail loud | §3.4, §3.6; D33, R2; `feedback_existing_path_failures_as_evidence` | S2, **S4.5** | re-binding tier: regenerated stream re-binds stored ids under unchanged geometry; the active mode is recorded in lineage | `BUILD` | `TODO` |
| S5.2 | Re-binding negatives + **threshold calibration on a labeled truth set** + **regen-guard registration**. Calibration: a perturbation model (OCR-class char subs, re-segmentation, whitespace shifts, local reorder) over a stream with a **recorded identity map** (ground truth known by construction); report **false-bind / fail-loud / missed-bind separately**, treating **false-bind (silent-wrong) as the dominant cost → asymmetric threshold**; a **real re-extraction delta** sample is added *when available* (non-blocking). **Monotone-strictness property:** lowering signal strength (geometry-primary → tie-break → no-geometry) must **never lower the threshold or raise auto-bind coverage** — the correct response to "too many fail loud in no-geometry" is more human review, not a lower bar (`feedback_no_cheating_results`). Structure map joins the regeneration-guard family (one-way gate) | §3.4, §9; D33 | S5.1, **S8.1** | negative tier raises; the three rate classes measured; monotone-strictness property holds; regen-guard refuses silent regen of the map | `GATE` | `TODO` |

> **Risk:** the threshold is the dial between silent-misbind and noisy-fail. The live
> `corrections.json` 40-char anchor proved exact-substring matching fails on re-extraction;
> the fuzzy fingerprint **defaults to fail-loud on doubt** and the dial is **set by S5.2's
> measurement**, with the weakest-signal mode held the strictest, never the most permissive.

### S6 — Read-fields & status axes, §3.3 (concern B) `BUILD`

| ID | Deliverable | Refs | Deps | Done-when (tier) | Tag | St |
|---|---|---|---|---|---|---|
| S6.1 | Three **orthogonal** axes: `role` (`front\|body\|back`, structural matter only); `authorship` (scope `work\|witness\|translation\|span`, overridable — PLL's Mazzini-letter override); **`content_provenance_class` / editorial-status at L2** (`authorial\|editorial\|translator-note\|transcriber\|generated-TOC\|scan-OCR-furniture\|source-wrapper\|renderer-added`). **Distinct name from L1's `capture_provenance_class` (S1.1) — no shared identifier across layers** (M4: enforcement-by-construction, so no consumer can grab the convenient field and bypass the rollup). Designation ≠ title (both optional display fields) | §3.3; D13, D23 | **S4.5** | property: axes independent; no `excluded` smuggled into `role`; L1 and L2 provenance fields are distinctly named | `BUILD` | `TODO` |
| S6.2 | Derived behavioral flags `translatable` / `alignable` / `counts_for_retention` / `rendered`, computed by policy from the axes; validators switch on **flags**, not on a raw provenance-class literal (either layer). **Layer-ownership pinned: a node's flags read L2 fields + a declared L1 rollup; a node mixing authorial-body and furniture atoms must EITHER split the projection (preferred — respects no-double-ownership) OR carry an explicit, tested mixed-rollup** (silent mixed rollup is the failure mode). A **policy truth-table fixture** asserts the four flags for each real PLL `content_provenance_class` + ≥1 second-fixture class, covering the dangerous rows: furniture (captured-not-rendered), source-wrapper (captured-not-translated), footnote-body retention, translator-note alignability, embedded-letter authorship | §3.3; D23 | S6.1 | property: adding a `provenance_class` needs no validator edit; the truth-table fixture pins every flag (incl. the dangerous rows) and which layer it reads from | `BUILD` | `TODO` |

### S7 — L3 + relations + cross-language alignment, R5/D34 (concern C)

| ID | Deliverable | Refs | Deps | Done-when (tier) | Tag | St |
|---|---|---|---|---|---|---|
| S7.1 | `SpanRef = {atom_id,start,end}` + typed endpoint union (`atom_range \| projection_node \| span_ref`); L3 span/field model (speaker/date/author/citation; footnote = L2 note-body + L3 call-site span + `note-of` relation). **Reference-integrity is multi-namespace** (M3): every endpoint resolves across `atom_id`, `node_id`, cross-language target node ids, and aliases | §3.2, §11.3; D19 | S1.1, **S4.5** | reference-integrity: every endpoint resolves in **every** namespace it can address | `BUILD` | `TODO` |
| S7.1b | **Legacy flag → `SpanRef` migration + steady-state disagreement artifact.** One-time: convert `[live] data/flagged_segments.json` `(ch_id, para_idx)` word flags → `SpanRef` endpoints over canonical atoms, **preserve per-witness evidence**, **fail-loud if a flag cannot re-bind** (the operational half of F4's "disagreements become L3 spans"). Durable: define the steady-state artifact so the re-architected reconcile (S10.2) **emits disagreement spans natively** — the conversion only seeds it; **no old `(ch_id,para_idx)` surface under a new name**; the copy3↔canonical word-level linkage this establishes is also the prerequisite for **canonical page-attribution** (see the S1.3a `PAGE_PENDING` deferral note) | §2-A, §3.2, F4; D19, D25 | S7.1, **S4.5** | every legacy flag re-binds to a SpanRef or fails loud; per-witness evidence preserved; the native-emission artifact is specified | `BUILD` | `TODO` |
| S7.1c | **Relation-store persisted schema + independent version** + **its own S8.1 stale class** (M3 relations half). `relations.json` validates against the schema; the schema version is a distinct lineage entry, not folded under `structure_map.json` | §3.5, §3.6, §11.3; D21 | S7.1 | reference-integrity + round-trip tiers: schema validates, version registered independently | `BUILD` | `TODO` |
| S7.2a | **Cross-language alignment MECHANISM** (general source↔target, LANG_A↔LANG_B, **not** bespoke IT↔EN): many-to-many over `node_id`/`SpanRef`, per-edge `method` (`by-index\|by-content\|human`) + `confidence`, versioned `alignment_set`; a paragraph index is *one method*, never the durable key. **Synthetic two-language fixture carries unequal (M:N) segmentation + a partial-span edge** — a 1:1 fixture would not exercise the failure that created the live `typeset.py` mispoint. **A thin harness consumer pairs source↔target via the relation (not the index)**, proving the durable key is consumable | §4 R5; D7, D34; `[live]` `typeset.py:609` mispoint evidence | **S4.5**, S7.1 | property: index-as-method, node-id-as-key; the M:N + partial-span fixture aligns; the harness consumes the relation, not a paragraph index | `BUILD` | `TODO` |
| S7.2b | **PLL IT↔EN alignment INSTANCE** — the populated source↔target set for PLL. **BLOCK on v2-EN** (the EN side does not exist as projection nodes while M4c is paused). The v1-`english_translation.md` demo is **YAGNI** — built only if a specific need appears, and then only in a **throwaway namespace** with a lineage marker barring any cache/citation from treating it as production; never the durable v2 set | §4 R5; D7, D34 | S7.2a, v2-EN translation | a populated IT↔EN `alignment_set` over real v2 nodes (or, if ever built, an explicitly-throwaway v1 demo) | `BUILD` | `BLOCK` (v2-EN) |
| S7.3a | **Graph cross-ref edge type** (may dangle / resolve externally — Britannica): concern-C edge orthogonal to containment, with external/unresolved semantics. Mechanism now, no PLL instance | §6; D14 (C edges); R1 (EB) | S7.1 | property: an edge may dangle and is reported, not silently dropped | `SEAM` | `TODO` |
| S7.3b | **Reserved `participates-in` hook** (`contiguous:false`, typed members) for overlapping / interleaved hierarchy. Reserved only — no instance, Hamlet-conformance-checked | §6; D15, D32; R4 | S7.1 | the hook exists + is uninstantiated; Hamlet case documented as the trigger | `DEFER` | `DEFER` |

> S7.2a/b are the structural replacement for the shipped `[live] typeset.py:609` mispoint (EN
> paragraph *index* reused on the IT column; 23/58 chapters diverge → 14 mispoints). The
> mispoint exists **because** IT/EN paragraph counts diverge — which is exactly why the
> mechanism's key is `node_id`/`SpanRef` over M:N edges, and why the S7.2a fixture must carry
> M:N + a partial-span edge. Cited as evidence only — fixing the live `typeset.py` is a
> separate live-PLL matter (deploy-hold, not this branch). **Forward dependency:** the engine
> **typeset port (M3b)** must consume S7.2 alignment (not a paragraph index) — see *Cross-track
> relationships*. This axis ships the mechanism + harness + the named obligation on M3b; it
> does not ship the renderer.

### S8 — Governance & lifecycle spine, §3.6 (concern B/C) `BUILD`

S8.1 (the loader) is pulled into W3 — it is a prerequisite of S5.2's fail-loud, not a
follow-on. S8.2/S8.3 stay downstream of the models they police.

| ID | Deliverable | Refs | Deps | Done-when (tier) | Tag | St |
|---|---|---|---|---|---|---|
| S8.1 | Stale = **fail-loud** loader keyed on the lineage manifest; *why-stale → which-migration* routing. **Emits a typed stale report** (what changed · which class · what to run next) + a per-class **manual repair runbook**, each entry **asserted by a test, not just written**: changed raw hash → re-capture; changed normalizer → re-derive offsets; changed projection → re-attach L2/L3; changed dict/oracle → re-segment; **changed atom-store schema (S1.5) / changed relation-store schema (S7.1c) → migrate** — each produces a **distinct diagnostic + next command**. **Recovery defaults to dry-run/report;** any rewrite of map/atom/relation artifacts requires an explicit output target, a **snapshot-before-migrate** (mirroring `refine.py`), and a **new lineage entry** — the migration path itself **joins the regen-guard family** (unsafe recovery is worse than a block, Principle 4); **owns the S4.4 writer's crash-state recovery** (snapshot written, live map not superseded — permit an idempotent re-supersede when the existing snapshot's bytes equal the live map's; s4_plan §0.3 A-4) | §3.6; D14, D21 | S4.4, S1.5, S7.1c | negative: each stale class fails load until refresh/migrate **and** emits its own asserted diagnostic; recovery is dry-run-by-default + snapshot-guarded | `BUILD` | `TODO` |
| S8.2 | Decision provenance per entry (`human-approved\|plugin-suggested\|inherited`; re-suggestion never overwrites a human ruling); **C-corrections are reviewer-approved patches** to L2/L3, never auto-rewrite of L1; L1 supersession-by-new-stream + tombstone (kept-marked-invalid); **scope extends to L2 node identity: node retirement/tombstone semantics + id-reuse prohibition** (merging containers retires a `node_id` — s4_plan §3.B.7, M10) | §3.6; D14, D25 | S4.4, S5.1 | property: human ruling survives re-suggest; superseded atom ids stay addressable | `BUILD` | `TODO` |
| S8.3 | **Negative battery** (fail-loud, no skip-masking): alias collision in scope · unresolved relation endpoint (multi-namespace) · stale lineage manifest (each class) · ambiguous re-bind — each asserts the raise. Plus reference-integrity binding (every ref / endpoint / `status:active` alias resolves to exactly one node) | §9; `feedback_validate_bindings`, `feedback_no_cheating_results` | S4.5, S5, S7 | negative + reference-integrity tiers green; no `skipif` masking | `GATE` | `TODO` |

### S9 — Recognition: profile + code escape, §7.1 (D17/D27) — resolves BR-021

| ID | Deliverable | Refs | Deps | Done-when (tier) | Tag | St |
|---|---|---|---|---|---|---|
| S9.1 | Structure profile (`engine/profiles/structure/` + new `BookManifest.profile_refs["structure"]`): **data primitives only** — heading regexes, running heads, matter labels, designation grammar, numbering scope, block-split rules, **and the `boundary_classes` set** (heading / footnote-call / embedded-letter boundary) that S1.3b's completeness check hard-fails on — declared as ***capture-provenance-class* values** (the axis S1.3b matches; see the S1.3b note) **and granular capture must emit them as *included* classes** (relax the `capture.py` non-body→`excluded` coupling). **Must reject a profile whose declared classes collide with `UNKNOWN`** (`classify.UNKNOWN`) — the sentinel-alias footgun S1.3b cannot guard (no block-class vocabulary in scope there). No DSL, no control flow in JSON. **Mirror the existing `engine/profiles/{languages,source_noise,typefaces}` schema convention** | §7.1; D17, D27; `config/models.py · BookManifest:108` (`profile_refs:113`) | S4.5 | profile loads via the existing loader pattern; `boundary_classes` is consumable by S1.3b; a class colliding with `UNKNOWN` is rejected; neutrality tier still green | `BUILD` | `TODO` |
| S9.2a | **Mechanical relocation (move-only).** Relocate the abstract structure surface — `is_chapter_heading` / `parse_chapter_number` / `structural_part` / `strip_boilerplate` / `split_raw_chapters` (`lang/base.py:42–78`) **and the ordinal/heading data tables** (`lang/italian.py:26–290`) — out of `LanguagePlugin` into the structure recognizer, **preserving the chapterids golden, with ZERO new abstraction**. MAY run parallel to S4 **iff** it stays a literal move; the moment it needs an interim interface the L2 map will reshape, it is no longer move-only → becomes S9.2b (gated). The cycle-breaker `chapter_identities:107` (produces all three id namespaces together) is the delicate part — move without disturbing it | §7.1, F1; D8, D17, D27 | S9.1 *(or parallel to S4 if move-only)* | the abstract structure surface is **gone from `lang/base.py`** (asserted); `engine/tests/golden/test_chapterids_golden.py` reproduces PLL identities **unchanged**; **no new abstraction introduced** | `BUILD` | `TODO` |
| S9.2b | **Map-binding recognizer output + identity proof.** Bind the relocated recognizer's output to the L2 map; narrow **code-escape** reader for irreducibly procedural cases (Hamlet turn-state). **Store-and-rebind assertion** (beyond the golden): mutate a designation and show `node_id` is **fixed** while the rendered handle changes and the **old handle survives as an alias** (S4.3's property on the relocated recognizer — this is the BR-021 win, not mere adapter compatibility). **Alias-collision clause:** if the retired handle now collides in scope, the system **fails or demands a resolved alias state** — never silently maps one handle to two nodes (the S8.3 collision negative, exercised here) | §7.1, F1; D8, D11, D33 | S9.2a, **S4.5** | designation-mutation: `node_id` fixed, handle re-renders, old handle aliased; collision → fail/resolved-alias | `BUILD` | `TODO` |
| S9.3 | **Depth-from-designation deriver seam** (Tractatus dotted-decimal → depth 0–6). Mechanism now, **unpopulated for PLL** (PLL uses `position-path`, no depth derivation) | §6; R1 (Tractatus) | S9.1, S4.3 | Tractatus-style designation computes depth via the seam; PLL path does not invoke it | `SEAM` | `TODO` |
| S9.4 | **D18 GATE (extractor generality, end-to-end).** The **SAME adversarial differ-fixture S4.5 births the schema on** travels **recognition → atoms → projections → adapter from raw** (not hand-authored JSON) under an **Italian-free core**. Because the fixture has no parts and non-ordinal/designation-string handles, a "translated-PLL with relabeled headings" parser cannot pass it. This is the operational proof of D18 that S4.5 alone does not give | §7.1, §9; D18; `feedback_single_fixture_blind_spots` | S9.1, S9.2b, S4.5 | the non-PLL fixture is recognized end-to-end by an Italian-free core; integration may claim D18 operationally satisfied | `GATE` | `TODO` |

> **Highest-regression seam.** `lang/base.py · chapter_identities:107` is the live cycle-breaker
> that produces all three id namespaces together; moving recognition without disturbing it
> is the delicate part (S9.2a). **Resolves BR-021** (position-based chapter identity) and
> **supersedes BR-019 / BR-020** (stable id, single ordinal model) — close those in
> `docs/decisions/branch_register.md` when S9.2b lands.

### S10 — Integration & migration, §7.2–7.4 (F2/F3/F4) `BUILD`

| ID | Deliverable | Refs | Deps | Done-when (tier) | Tag | St |
|---|---|---|---|---|---|---|
| S10.1 | **F4** read-only adapter: L2 blocks → legacy `{id,title,part,text}` (`text = "\n\n".join(paragraph projections)`) behind reconcile; B runs **structure-first** (D29). Read-only — never a write-back path; it is also the **rollback surface** (a regressing consumer reverts to the adapter). **Explicit block→legacy-text compatibility policy — a total function over registered block classes → {flatten \| omit-with-reason \| reject}, with the default for an UNREGISTERED/unknown class = `reject` (fail-loud), never permissive flatten** (the silent-loss trap the adapter exists to bridge around); a test asserts the policy | §7.4; D16, D26, D29; O5 | S4.5 | existing consumers pass unchanged against the adapter; the compatibility policy is total + tested; unknown class → reject | `BUILD` | `TODO` |
| S10.2 | Consumer migration, **triage first** (in-place rewriter `triage.py:286–327` → edits become governed L2/L3 patches), then `cleanup.py:915/935` (the `ch["text"]` reads; `:882` is the input-load), then `validate.py:432–465` — one BR at a time; **a regressing consumer reverts to the S10.1 adapter**; the adapter is retired only when **all** consumers are green off it | §7.4; D26 | S10.1, S8.2 | each migrated consumer drops the adapter, reads blocks; suite stays green | `BUILD` | `TODO` |
| S10.3 | **F2** replace `Structure` validator (`config/models.py · Structure:62`, the `h2_min`/`h3_count`/`parts` shape) with the general tree/blocks model + per-book structure map; `validate`'s count checks become assertions over the map, switching on S6 derived flags | §7.2, F2 | S4.5, S6 | validate asserts over the map; the S4.5 depth-0 fixture validates | `BUILD` | `TODO` |
| S10.4 | **F3** rework `ChapterIdentity` (`util/chapterids.py · ChapterIdentity:24`) → opaque `node_id` + rendered handles + aliases. **PLL golden pins the RENDERED layer by exact match** — legacy `short`, `parse_md` key, `html_slug`, provenance-key, revision-key, **and alias resolution for a retired handle** all reproduce (extend `engine/tests/golden/test_chapterids_golden.py`, I3 expected-from-live). **`node_id` is asserted relational-only — stable within the committed map, opaque, and NEVER equal-to or derived-from any rendered handle** (this clause is what proves BR-021; it forbids the "wrap designation-derived identity in a new object" cheat) | §7.3, F3; D11, D33 | S4.3, S9.2b, **S4.6** | **PLL golden**: rendered handles exact-match + alias resolves; `node_id` relational-only, never handle-derived; no regression | `GATE` (PLL golden) | `TODO` |

### S11 — Pre-translation smoke + post-build evaluation (diagnostic, **not** a ship gate)

S11.0 is the product-safety checkpoint before M4c consumes the v2 Italian; S11.1/S11.2 are
the post-build academic comparison. None has a pass/fail threshold and none must ever become
one (`feedback_no_cheating_results`). The engine writes reports under
`books/per_la_liberta/work/`; it reads v1 artifacts and the review-phase ground truth
**read-only** from the live tree (reading the live tree is allowed; writing it is not).

| ID | Deliverable | Refs | Deps | Done-when (tier) | Tag | St |
|---|---|---|---|---|---|---|
| S11.0 | **Pre-translation whole-book smoke + human-ack** (gate-less product-safety checkpoint). Before M4c consumes the v2 Italian, produce a **no-threshold** report of v2-introduced *novel* deviations (S11.2's sampled false-change measurement, pulled forward). Build the artifact and **hand it to Ben** (`feedback_human_validation_step`) — never auto-threshold. The acknowledgement is an **artifact keyed to the v2-source lineage hash**; re-running extraction (new lineage) invalidates the old ack. **Forward dependency:** M4c hard-fails with "v2 source smoke not acknowledged for this lineage" when missing/stale — that *enforcement* lands when M4c is ported, not in this axis | user request (product safety); §3; `feedback_human_validation_step` | S3, S10.1 | a written novel-deviation report + a lineage-keyed ack artifact; **no threshold** | `SCAF` (checkpoint) | `TODO` |
| S11.1 | v1↔v2 difference characterization: best-effort align the v2 extracted/reconstructed Italian against v1 `[live] output/italian_clean.md` (fuzzy / node-aligned — **not** 1:1, since segmentation differs by design) and report divergences by class (spaces/fragments reconstructed, word-form changes, structural shifts) + counts | user request (academic comparison); §3 (S3 changes text by design) | S3, S4.6, S10.1 | a written report enumerating divergence classes + counts | `SCAF` (diagnostic) | `TODO` |
| S11.2 | **Accuracy vs the deviation-review ground truth:** for each scan-confirmed deviation from the review phase, did v2 extraction *independently* produce the adjudicated-correct form? The ground-truth artifact is **`[live] data/blind_deviations_classified.json`** (master worklist; worked sheet `[live] state/deviation_crops/sheet.html`; items carry a `resolved` field; ≈768 of ≈862 remaining — **in progress**). Report **recall** + a **sampled** v2-introduced-deviation rate. Because the set is in-progress, recall is **recall vs the adjudicated-so-far subset**, and the report **pins the ground-truth snapshot by hash/date** with the unresolved count reported separately — so later adjudication growth (768→0) cannot retroactively rewrite what an old report claimed | user request; `project_deviation_review_state`, `project_blind_read_signal` | S11.1 | a report giving recall vs the snapshot-pinned adjudicated subset + the sampled false-change rate; **no threshold gate** | `SCAF` (diagnostic) | `TODO` |

> Why S11.1/S11.2 are the right yardstick: the review phase already produced a
> **hand-adjudicated, scan-confirmed** set of where v1's OCR/cleanup went wrong. Measuring
> whether the new geometry + Zipf-DP + oracle extraction *independently* lands the same
> corrections is a far stronger academic signal than diffing two texts that were never 1:1.
> The **English-level** comparison waits on the v2 translation (M4c, paused) and is a later
> extension.

---

## Axis-level Definition of Done — two tiers

The earlier single eight-point DoD over-weighted the generic substrate and let the hardest
book-specific artifact (S4.6) and a product-facing relation (S7.2) slip. It is split into two
tiers so "ready for *what*?" is honest: **Tier A** is the engine-agnostic mechanism, provable
now on synthetic + differ fixtures; **Tier B** is the populated PLL-v2 instance, parts of
which are legitimately `BLOCK`ed on the v2 English. A green Tier A with a blocked Tier B is a
**true** state, not a contradiction — and the Milestone map's two-axis rollup shows it.

**Method gate (every task, both tiers — red-first, PLAN §9).** No task is `DONE` until its
invariants are enumerated in the test-module docstring (`Invariants (proven red below)`) **and each
has a test observed red on violation** — TDD for new code; a permanent negative/planted-violation
test for a guard over existing code (never a throwaway probe). A test whose only red-input is
editing its own literal (or a stdlib bug) is a tautology, not a check. This is the standing fix for
the three audits that each recovered a green-but-unbound test after the fact (S0.1 version
tautology, S0.3 unbound generator, the symlink guard with no negative control); worked examples are
the S0.1–S0.3 test-module docstrings.

### Tier A — Substrate ready (engine-agnostic mechanism)

1. **Raw floor** — the model-level byte-exact raw round-trip passes (S1.2) **and** the
   **production-stream round-trip** reconstructs each real witness through the public read
   path, with the capture-completeness + span-topology invariants (S1.4).
2. **D18 schema born** — the depth-0 / designation-string / non-ordinal second-structure
   fixture validates the schema (S4.5).
3. **D18 generality proven** — that **same** adversarial fixture travels
   recognition→atoms→projections→adapter from raw under an Italian-free core (S9.4).
4. **Re-bind proven** — geometry + fuzzy fingerprint re-attach binds correctly, **fails
   loud** on ambiguity, the threshold is calibrated on a labeled truth set, and the
   monotone-strictness property holds across geometry modes (S5).
5. **Alignment mechanism durable** — cross-language alignment is an L3 relation over
   `node_id`/`SpanRef` (not a reused index), proven on the M:N + partial-span synthetic
   fixture, and **a harness consumes the relation key** (S7.2a).
6. **Governance live** — the structure map is the regen-guarded, stale-fail source of truth;
   the negative battery is green with no skip-masking (S5.2, S8); **all three persisted
   layers (atom-store S1.5, structure-map S4.4, relation-store S7.1c) plus the
   resource/normalizer versions (S3.0) are independently versioned in lineage** with their
   own stale classes.
7. **Scale honored** — structure ops stay sub-quadratic to the design ceiling **including
   serialize/load/index time** (S4.7, D35).
8. **Neutrality holds** — core `structure/` carries no language/structure literal; all book
   opinion is in the profile + structure map (S0.2, S9).

### Tier B — PLL-v2 input ready (populated instance; parts BLOCKED on v2-EN)

9. **No regression** — the PLL golden reproduces current chapter boundaries + every
   **rendered** identity (handles + aliases), with `node_id` relational-only (S10.4).
10. **PLL container map** complete + reviewed + re-bindable, embedded-letter placement pinned
    (S4.6).
11. **Alignment instance populated** — the IT↔EN `alignment_set` over real v2 nodes (S7.2b).
    **`BLOCK` on v2-EN** until the v2 translation exists.
12. **Pre-translation source smoke acknowledged** for the v2-source lineage (S11.0); the M4c
    enforcement hook lands when M4c is ported.

S11.1/S11.2 (academic v1↔v2 comparison) run *after* Tier A+B are met and a v2 extraction
exists — diagnostics that report how the new techniques did, **not** ship gates.

---

## Cross-track relationships

- **Engine-framework port milestones** (separate `engine-framework` line, `project_engine_framework_fork`):
  this axis is the deepened **M7 (extraction)** territory; **M4c (translate + refine)** is
  paused behind it. S10.2's triage migration sits on top of the **M4b** triage/cleanup that
  already landed — the adapter (S10.1) is what keeps M4b green during the cutover.
- **Forward dependency on M3b (engine typeset port):** the renderer port **must consume S7.2
  alignment (not a paragraph index)** — the tracked cross-track obligation this axis raises.
  This axis ships the alignment mechanism + a harness consumer (S7.2a); the renderer itself is
  M3b's to migrate. (Distinct from the live `[live] typeset.py:609` deploy-hold patch, which
  is an operational fix on the live edition.)
- **Forward dependency on M4c (translate port):** the S11.0 pre-translation-smoke
  *enforcement* ("v2 source smoke not acknowledged for this lineage" → hard fail) lands when
  M4c is ported; this axis builds the report + the lineage-keyed ack artifact.
- **Branch register** (`docs/decisions/branch_register.md`): S9.2b **resolves BR-021** and
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
| **O5** — mutation-testing tool (the mechanical form of §9 red-first) | deferred by choice; manual invariant-targeted sweep used now | revisit at **S1.5** (first persisted store = first real logic worth mutating): stand up **cosmic-ray** in an isolated worktree, decide gate-vs-on-demand on data |
| **O6** — geometric layout / bbox provider feeding concern A | scanned 2026-06-26; not adopted | revisit when **concern A's atom/block model is real (S1–S2)** and a *second book* motivates auto-layout — lead candidate **kraken**, behind an optional extraction-side provider seam, never in core |

### Deferred-ledger scan notes (2026-06-26)

Captured for the record from two tool scans run this session; both are *information*, not commitments.

- **O5 — mutation testing on Python 3.13.** The lightweight tools are dead on 3.13: `mutmut` 2.x crashes at startup (`pony`/pickle), `mutatest` crashes on the first trial (`random.sample` on a set, removed in 3.11 — it does find 22 targets in `paths.py` first). Only two execute trials on 3.13: `mutmut` 3.x (project-copy model; fought our `src/` layout — its stats phase collected the full `tests/` against a partial copy → `ModuleNotFoundError: engine.lang`) and **cosmic-ray** 8.4.6 (ran 156 mutants on `paths.py` to completion — but heavyweight: a fresh pytest subprocess per mutant, and it **leaves the source file dirty if interrupted** → only ever run it in an isolated git worktree). On today's declarations-only `structure/` surface, mutation testing has almost nothing to bite (`mutatest` found **0** targets there; only `mutmut` mutates bare literals, mapping exactly to the two known-deferred version non-pinnings + the F3 equivalent mutant). Until S1.5 the discipline is the manual invariant-targeted sweep (one mutation per enumerated invariant) — see PLAN §9.
- **O6 — book-layout bbox tools.** A layout provider would automate what PLL already hand-tuned (`typography.json`/verse, header-strip regex, page-citation mapping) — low marginal value for PLL, real value only for onboarding a *second* book book-agnostically, so it belongs behind an optional extraction-side provider seam (like the OCR backends / the spaCy extra), never as an `engine/` core dependency. Clean, Py-3.13-native, permissively-licensed candidates: **kraken** (Apache-2.0, historical-scan-native, regions + baselines + reading order → lead), **Docling / docling-layout-heron** (MIT, but DocLayNet classes → no verse/marginalia, degrades on historical type), **PaddleOCR / PP-StructureV3** (Apache-2.0, richest taxonomy, heavy `paddlepaddle` stack). **Eynollah** has the only native marginalia / drop-cap-initial / header classes but is TensorFlow<2.13 / Py 3.8–3.11 / Linux-only → containerized, off our path. **Avoid:** layoutparser + dhSegment (unmaintained), marker (GPL), DocLayout-YOLO / Ultralytics-YOLO (AGPL network-copyleft). Caveats: no surveyed tool types "verse"; no benchmark exists on a 1913 Bodoni Italian book; all drag in torch/TF/paddle (hundreds of MB). Maturity figures web-verified by the scan agent this session, not re-checked per-repo.

---

## § Audit log

### S3 ↔ golden — RESOLVED (2026-06-26)

The first audit flagged S3 (space/fragment reconstruction) as orphaned in the DAG and the
graph parenthetical "(PLL golden also needs S3)" as inconsistent with `S10.4`'s deps.
**Resolution (user-confirmed):** "no regression" means **structural fidelity, not
byte-identical text** — v2 is *allowed and intended* to read better than v1 where S3 recovers
split/fragmented words the live pipeline never reconstructed. So the PLL golden (S10.4)
validates **structure** (boundaries + identities) and gains **no** S3 dependency; S3 is
pinned by its **own** space-recon tier (S3.2) + the raw round-trip floor (S1.2/S1.4), feeding
the v2 **instance**, not the regression golden. **Added on top:** an academic, post-build
v1↔v2 comparison (**S11.1/S11.2**) that measures the new extraction's accuracy against the
review-phase scan-confirmed deviation set — diagnostic only, never a gate. _Thread struck._

### Multi-round adversarial audit (Codex × Claude) — RESOLVED + FOLDED (2026-06-26)

A three-round adversarial audit (Codex red-team ↔ Claude rebuttal, plus Claude's independent
M1–M8 pass) converged with no open contentions; every outcome is folded into the task tables,
the two-tier DoD, the Milestone map two-axis rollup, and the Test-tiers glossary above. The
**verbatim threads** (`======`/`@@@@@@`, `=====!`/`@@@@@!`, `====!!`/`@@@@!!`) are archived in
**`ENGINE_STRUCTURE_TASKS_DISCUSSION.md`**. _Threads struck._ The landing sites:

#### Resolved-audit ledger

| Thread | Resolution | Landed in |
|---|---|---|
| DAG recognizer bootstrap | split raw capture from typed projection; nameable classifier seam | **S0.4**, **S1.3a**, **S1.3b** |
| typed-projection completeness | all-`unknown` fails; profile-scoped `boundary_classes` hard-fail vs body-leaf route-to-review | **S1.3b**, **S9.1** |
| S1.2 floor too weak | production-stream round-trip through the public read path; capture-completeness + span topology | **S1.4**, DoD A-1 |
| S1.3 note unkept | legacy `(ch_id,para_idx)` flags → `SpanRef` + steady-state disagreement artifact | **S7.1b** |
| S2.0 fallback undefined | negative branch as a real deliverable; stratified sample | **S2.0**, **S2.1-alt** |
| M1 geometry ≠ witness engine | text↔box alignment probe; `geom` Optional + match-provenance, frozen in S1.1; matcher fail-loud | **S1.1**, **S2.0**, **S2.1**; PLAN §3.0/§11.1 |
| M2 negative-probe ripple to S5 | three geometry operating modes recorded in lineage | **S5.1**, **S2.0** |
| S3 resources implicit/Italian-wired | resource + normalizer versioning into lineage via the profile; distinct stale classes | **S3.0**, **S8.1** |
| S4.5 too weak for D18 | two gates — schema-born (S4.5) vs extractor-generality (S9.4) on the **same** adversarial fixture | **S4.5**, **S9.4**, DoD A-2/A-3 |
| S4.6 absent from DoD/deps | authoring+review workflow; embedded-letter pinned; advisory recognizer comparison; in DoD + S10.4/S11 deps | **S4.6**, DoD B-10 |
| S4.7 shape-only | named ops + wall-clock/memory budget incl. load/index; machine-ops only | **S4.7**, DoD A-7 |
| S5.2 calibration theater | labeled truth set; false-bind/fail-loud/missed-bind split; monotone-strictness property | **S5.2** |
| M3 only L2 has schema rigor | atom-store + relation-store persisted schemas, independent versions, multi-namespace integrity | **S1.5**, **S7.1**, **S7.1c**, **S8.1** |
| M4 `provenance_class` double-homed | distinct L1/L2 field names; L2-fields + declared-L1-rollup; split-or-explicit-mixed-rollup | **S1.1**, **S6.1**, **S6.2**; PLAN §3.0/§3.3/D13/D23 |
| S6 orthogonality ≠ semantics | policy truth-table fixture over the dangerous rows; layer ownership pinned | **S6.2** |
| S7.2 fake instance / 1:1 fixture | split mechanism (BUILD) from instance (BLOCK on v2-EN); M:N + partial-span fixture; harness consumer | **S7.2a**, **S7.2b** |
| S7.2 no consumer | thin harness consumes the relation; M3b forward-dependency named | **S7.2a**, Cross-track |
| M5 golden inapplicable to net-new | `golden` reserved for live-parity; synthetic = fixture/reference-integrity | Test-tiers glossary; PLAN §9 |
| M6 runtime vs build order | one disambiguating sentence: D29 = before cleanup/triage, not before raw capture | Orientation; PLAN §2/§10 |
| S8.1 half a lifecycle | typed stale report + tested per-class runbook; dry-run default + snapshot-before-migrate | **S8.1** |
| S9.2 golden preserves anti-pattern | store-and-rebind identity proof + alias-collision clause; split move-only S9.2a vs map-binding S9.2b | **S9.2a**, **S9.2b**; M8 |
| S10.1 silent adapter loss | compatibility policy as a total function; unknown class → reject (fail-loud) | **S10.1** |
| S10.4 unnamed artifact | exact-match rendered handles; `node_id` relational-only, never handle-derived | **S10.4** |
| S11 product-safety vs academic | pre-translation smoke + lineage-keyed human-ack, gate-less | **S11.0** |
| M7 ground-truth resolvable+partial | name `blind_deviations_classified.json`; recall vs snapshot-pinned adjudicated subset | **S11.2** |
| DoD over-weights substrate | two-tier DoD; two-axis milestone rollup | DoD; Milestone map |

_(Further adversarial threads land here as `@@@@@@` blocks with paired `======` responses;
fold resolved outcomes into the affected task + spec section, record the landing in the
ledger, then move the verbatim thread to the discussion archive.)_
