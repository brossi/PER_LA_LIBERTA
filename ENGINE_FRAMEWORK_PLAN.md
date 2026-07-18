# Engine Framework — Implementation Plan

> **Status:** In execution on branch `engine-framework`. M0–M3 complete (scaffold; config model +
> Italian LanguagePlugin; `validate` ported with golden reproduction; `reconcile` + `adjudicate`
> ported — all required tiers green, full suite passing with 0 skips). See `ENGINE_M3_PLAN.md` for
> the M3 port + its "Implementation status" section; `typeset` is split out
> as M3b (task #9). **Amended
> 2026-06-22** to carry the *port discipline*: see the
> "Port discipline (governance)" decision below and the reframed "Validation strategy" section; the
> canonical statement is `engine/docs/port_discipline.md`. The review-pass decisions that produced the
> original plan live in the project conversation history.

## Context

The pipeline at the repo root is a single-book OCR → reconcile → clean → translate → typeset
system built specifically for *Per la Libertà!* (1913 Italian). Many constants encode facts
about that one book/language/scan — IA identifiers, the validation header structure (≥3 `##`
headers + exactly 57 `###` chapter headers), the 58 content units including the prefazione,
Bodoni OCR confusion pairs, Italian ordinals, the book's identity baked into LLM prompts,
bibliographic metadata. (All catalogued in CLAUDE.md's "Portability profile" and the
`archive/doc_audits/2026-06/` notes.)

The goal is to reuse this machinery for future books and other languages **without risking
the live edition**, which is close to completion and under active review-phase editing. The
chosen approach is to build a **nested, parameterized copy of the code under a new top-level
`engine/` directory, on a new git branch**. The top-level scripts keep producing *Per la
Libertà!* exactly as today; `engine/` becomes a clean, config-driven, multi-book seed that can
later be extracted into its own repository. This is a deliberate forward fork, not a maintained
mirror.

Governance rule: fixes in the live PLL tree are **not** backported to `engine/` unless they
correct generic-engine behavior. `engine/` is a forward seed; the live tree remains the source
of truth until PLL is frozen. No bidirectional sync. The only sanctioned cross-flow is refreshing
the frozen golden fixtures from live (read-only).

**Why nested-copy-on-a-branch (not in-place refactor):** in-place generalization with PLL as the
default config is cleaner long-term but touches the live pipeline near completion — exactly the
regression risk to avoid. The nested copy isolates all new work; the one real cost is
duplication/divergence, which is acceptable because the top-level tree is frozen-for-this-book and
`engine/` is the seed for what comes next.

## Decisions

- **Scope:** the reusable build subset through `typeset` **plus** the two genuinely-reusable
  review primitives — the vision re-read native-resolution layer and the ≥2-of-N
  period-dictionary membership oracle. `refine` is manual-only, not part of `--step all`;
  `companion` is intentionally excluded as situational content. The rest of the review phase
  (scan_adjudicate, comprehension, stage2, the `apply_*.py`/`re_*.py` one-offs) is **excluded** —
  bespoke, human-in-the-loop, committed as audit trail.
- **Companion:** **not generalized.** It is closer to hand-authored content than reusable code
  (~50 notable-people entries, personae aliases, glossary, citation parsing). The framework's last
  build step is `typeset`. Companion stays in the top-level live code only.
- **Validation target:** prove the architecture on one real implementation (PLL) by reproducing
  its **safe/deterministic** steps, and prove injection/non-leakage on a tiny **synthetic
  2-chapter fixture**. No second real book yet; the LanguagePlugin abstraction is built
  generically (Italian the only implementation), but multi-book correctness is not claimed until
  a second-book smoke fixture or real title is added.
- **Port discipline (governance).** Validation is **three tiers** — *equivalence* (golden; the
  port didn't change behavior), *contract/property* (invariants true for any input), *separability*
  (config swap changes behavior; no PLL leakage). Golden is one tier, **not "the strategy."**
  Redesign is **free at the architecture level** (equivalence makes it safe), **held to equivalence
  at the algorithm level** (changed only when external ground truth licenses it, logged), and a **deliberate, recorded divergence at the
  pipeline-shape level**. **One-way doors** (step contracts, plugin surface, step inventory, config
  schema) are decided on the record; two-way doors are picked and moved. Two standing registers — a
  **divergence ledger** and a **branch register** (`engine/docs/decisions/`) — record behavioral
  changes made and forks deferred, so we never silently reproduce *or* silently "fix" PLL. Canonical
  statement: `engine/docs/port_discipline.md`; each milestone plan *applies* it, it is not re-argued.
- **Document-structure axis (discovered 2026-06-23, M4c audit).** Language and typeface each became a
  clean engine axis; **document structure did not** — the part→chapter→paragraph model and
  ordinal-derived chapter identity rode in as an un-examined default, entangled across the language
  plugin, the manifest, and a baked markdown convention (`##`=part, `###`=chapter). **Direction
  taken:** chapter identity = **position in container**, with the printed ordinal demoted to a display
  projection (the more universal primitive — it survives named/dated/non-ordinal divisions).
  **Not taken:** designing a universal document model now (speculative generality with one real book).
  Recorded as **BR-021** with a near-term validation step — pressure-test against a candidate second
  corpus (Athanor's Kybalion; its structural difference is *expected but not yet verified*, the test
  reads its actual structure) *before* M4c hardens the id contract. Guards the standing
  trap: for *model* decisions the live PLL is one data point, not the spec — equivalence proves we
  didn't change behavior, never that the behavior is right.

## Approach

A self-contained package under `engine/` with a book/language-agnostic core, reusable shared
profiles, per-book manifests, and a test suite. Every book/language/scan-specific constant leaves
core; implementation details stay as code defaults (e.g. retry/backoff timing, cache filenames,
chunk sizes, LLM max-token defaults, and internal tag protocols). The orchestrator builds one
`ResolvedConfig` + `LanguagePlugin` and threads them into step functions — the same seam
`pipeline.py` already uses for `DATA_DIR/OUTPUT_DIR/STATE_DIR` (`pipeline.py:12-15`).

### Package layout

```
engine/
  pyproject.toml                 # self-contained; jinja2/jsonschema + spaCy models as optional per-language extras
  README.md
  src/engine/                    # importable package (true src layout)
    cli.py                       # orchestrator: argparse → resolve book → run steps (replaces pipeline.py)
    paths.py                     # BookWorkspace: derives data/output/state under books/<id>/work/ only
    config/{models,loader}.py    # BookManifest, LanguageProfile, ScanProfile, TypefaceProfile + JSON-schema validation
    config/schema/*.json
    prompts/templating.py        # Jinja2 StrictUndefined PromptTemplate
    lang/{base,registry,italian}.py   # LanguagePlugin ABC + Italian impl (ordinals, headings, ChapterIdentity)
    steps/{download,ocr,reconcile,triage,cleanup,adjudicate,validate,
           translate,multi_translate,refine,typeset}.py
    providers.py                 # small port of top-level providers.py (retry import + dictionary prompt generalized)
    dictionaries/{period_dict,membership_oracle}.py   # chunked-dict loader + ≥2-of-N oracle (reusable)
    review/vision_reread.py      # native-resolution scan re-read layer (reusable review primitive)
    util/{text,jsonio,chapterids}.py   # port of utils.py, split by concern
    contracts/*.json             # versioned sidecar schemas + id/path-shape assertions
  profiles/                      # SHARED reusable knowledge (outlives any one book)
    languages/italian_1900_1922.json
    typefaces/{bodoni_didone,spectral_fraunces}.json
    prompts/{ocr,triage,cleanup,translate,refine,multi_eval,synthesis,provenance}.txt.j2
    prompts/eval_rubric.json.j2
  books/per_la_liberta/
    manifest.json                # the per-book profile
    typography.json              # copy of data/typography.json (scan-verified styling sidecar)
    chapter_start_pages.json     # hand-curated per-book sidecar (chapter→start page + _last_scan_page); contract-checked
    inputs/                      # frozen copies of committed live inputs, for golden tests
    work/{data,output,state}     # ALL generated artifacts for this book (isolated; never the repo root)
  assets/{dictionary,fonts}      # corrected symlinks to read-only heavy assets during dev; real copies at extraction
  tests/{unit,golden,fixtures}
```

- `engine/src/engine/**` names no book; it reads `cfg` + the active `LanguagePlugin`.
- `profiles/` holds reusable language/typeface/prompt knowledge — a second early-1900s Italian
  book reuses the language profile, supplies its own scan/typeface profile, and may override the
  dictionary set.
- `books/<id>/` holds this-book data (manifest + hand-curated sidecars) and a self-contained
  `work/` tree. Companion is **absent** here (out of scope).

### Config model

JSON (matches existing `data/` sidecars; validate with JSON Schema via `jsonschema`; write via
ported `utils.atomic_write_json` at `utils.py:332-341`). `ResolvedConfig` = `BookManifest` ⊕
referenced `LanguageProfile` ⊕ `ScanProfile` ⊕ `OutputTypefaceProfile`. Merge semantics are
declared per field and tested: scalars replace, mappings deep-merge, and ordered lists
(`substitution_rules`, prompt vars, `sources`, validation thresholds) declare append-or-replace
strategy explicitly. There is no blanket order-blind deep merge.

Constant → config destination (the parameterization map):

| Current constant (file) | Goes to |
|---|---|
| `COPY1_URL`/`COPY2_URL` (`download.py:6-7`), `IA_ITEM_ID` (`typeset.py:13`, `translate.py:414`) | `manifest.sources[]` |
| `DEFAULT_PDF` (`ocr.py:17`), page-image scheme, `SCAN_LEAF_OFFSET` (`typeset.py:17`), `_last_scan_page` fallback (`typeset.py:731`, default 278) | `manifest.scan` |
| `SITE_BASE` (`typeset.py:14`) | `manifest` (top-level edition/deploy field) |
| ≥3 H2 + exactly 57 H3 (24+33) plus 58 content units including prefazione (`validate.py:16-19`, id iteration) | `manifest.structure` |
| Book/era/entities across OCR, triage, cleanup, translate, refine, multi-eval/synthesis/provenance, and provider dictionary-context prompts | `manifest.prompt_context` → rendered templates |
| Bibliographic metadata and edition colophon/body copy (`typeset.py`) | `manifest.edition` |
| `it_core_news_lg` (`cleanup.py:67` +4 sites), `it_combined.txt` (`cleanup.py:56,90`), accento-facoltativo skip, consonant-cluster regex (`validate.py:235`), english_markers/skip_words (`validate.py:221-232`) | `LanguageProfile` |
| Zingarelli/Edgren/Hoare dirs + IA URLs (`adjudicate.py:19`, `edgren.py:16`, `hoare.py:30`), ≥2-of-3 oracle | `LanguageProfile.period_dictionaries[]` + `oracle_min` |
| `BOUNDARY_SUBSTITUTIONS` (`cleanup.py:76-78`), `SUBSTITUTION_RULES` (`cleanup.py:20-47`), `NOISE_LINE_PATTERN` (`cleanup.py:14-16`) | `ScanProfile` |
| `PAGE_MARKER` (`ocr.py:20`) + the reconcile-side page-marker regex | **code default** (internal tag protocol, not scan-observable noise — per the Approach section's "internal tag protocols stay as code defaults"). *Superseded 2026-06-22:* an earlier draft routed these to `ScanProfile`; M3 baked the marker as a shared code constant (`reconcile.py:21`). See `ENGINE_M4_PLAN.md` F6. |
| Live font/CSS paths (`static/bilingual.css`, `docs/assets/fonts/`); dead `FONT_DIR` is not elevated | `OutputTypefaceProfile` |
| Italian `ORDINALS`/`COMPOUND_ORDINALS`/`ORDINAL_FIXES`/`WORD_FIXES` + heading regex (`utils.py:13-69,209`), `_ITALIAN_NUMBERS`/title→English (`translate.py:297-359`), boilerplate markers | `lang/italian.py` (LanguagePlugin) |

`chapter_start_pages.json` is **not** in this map: it is a hand-curated per-book sidecar (only
`typeset.py` reads it; no code writes it), so it lives under `books/<id>/` next to `typography.json`
and is covered by the sidecar-contracts track — not flattened into manifest scalars. The only true
manifest scalar hiding inside it is the `_last_scan_page` fallback (above).

Before M1, rebuild this table as a complete grep-backed constant + prompt + sidecar inventory; that
inventory becomes the M1 acceptance checklist.

Port the mostly-generic `providers.py` (Anthropic/Gemini/OpenAI `TranslationProvider` +
`TranslationResult`) with two required changes: import retry helpers from `engine.util`, and
replace the Edgren-specific dictionary-context fragment with a neutral hook driven by
`LanguageProfile.period_dictionaries`.

### Per-step parameterization

Each step function already takes dirs; add `cfg: ResolvedConfig` and `lang: LanguagePlugin`, then
replace constants with `cfg.*`/`lang.*` reads. Difficulty: `download/ocr/refine` easy;
`reconcile/triage/adjudicate/validate/typeset` medium; `cleanup/translate/multi_translate` hard.
Hard cases called out below. Per module, grep for `Path(__file__).parent`, `data/`, `docs/`,
`assets/`, `static/`, and top-level imports; route every hit through `BookWorkspace`, `cfg`, or
the package namespace.

### The hard cases (highest regression risk — built/validated first)

- **Chapter identity namespaces.** Short `p1_ch18` (`utils.split_into_chapters`, `utils.py:278`),
  parse-markdown IDs such as `p1_capitolo_decimo_ottavo` / `p2_capitolo_decimottavo`
  (`translate.parse_italian_markdown`, `translate.py:44-45`), and HTML slugs from `typeset._slug()`
  are distinct but related. Move all derivations into a single `ChapterIdentity` value object
  (`short`, `parse_md`, `html_slug`, `part`, `number`, `page_range`) produced by the
  `LanguagePlugin`, breaking the `utils` → `translate` cycle. Golden tests assert every PLL form
  against frozen expected fixtures. **This is the single most regression-prone refactor — proven in
  M1 before anything depends on it.**
- **Language-specific ordinals/headings** live entirely in `lang/italian.py`; the core never sees
  ordinals. Heading regex is data; number-word→int is code.
- **spaCy per-language packaging:** declare each model as an optional extra in `engine/pyproject.toml`
  (`[project.optional-dependencies] it = ["it-core-news-lg @ <wheel-url>"]`, etc.); `uv sync --extra it`
  installs only what a book needs. Expose `lang.load_spacy(components={...})`, cached by
  `(model, components)`, so NER-only cleanup and lemmatizer-dependent dictionary lookup do not
  share the wrong pipeline. Config/error text distinguishes the package distribution name
  (`it-core-news-lg`) from the spaCy model name (`it_core_news_lg`).
- **Prompt templating:** Jinja2 `StrictUndefined` (missing var = error). Templates in
  `profiles/prompts/`; books override only via `prompt_context` vars. Add prompt-leakage tests that
  render every prompt for a non-PLL fixture and grep for PLL-specific strings (`Per la Libertà`,
  Crespi, di Rudio, Orsini, Mazzini, Radetzky, Risorgimento, and dictionary names when disabled).
- **`claude` CLI synthesis dependency:** `multi_translate._run_claude_code` (`multi_translate.py:507-522`)
  shells out to the `claude` CLI (alias `opus`, not an API id). Abstract behind a `SynthesisBackend`
  protocol whose contract returns `{text, provenance}` as data; engine code owns all workspace writes.
  `ClaudeCliBackend` adapts the current file-writing behavior by parsing the files it writes;
  `ApiBackend` returns data directly. Reproduction never re-runs synthesis (guarded/non-deterministic),
  so the CLI is an optional capability.

### Reusable review primitives (in scope, kept minimal)

- `dictionaries/membership_oracle.py` — the ≥2-of-N period-dictionary oracle, generalized over
  `LanguageProfile.period_dictionaries`. This is a reusable primitive and future enhancement, not
  part of the M2/M3 golden reproduction path: current `validate` uses `it_combined` + spaCy NER, and
  current `adjudicate` uses Zingarelli-only lookup.
- `review/vision_reread.py` — the native-resolution scan re-read layer from `vision_review.py` /
  `readjudicate.py`: never downsample; optionally escalate to an independent second physical copy
  (not a second model) when configured. Modes are explicit: `primary_only`,
  `secondary_if_configured`, and `concordance_required`. Ported as a standalone primitive, not wired
  into `--step all`.

### Keeping the live edition safe

- The framework never writes outside `engine/books/<id>/work/`. All artifacts go under that work
  tree, derived by `paths.BookWorkspace`, which asserts every output path is workspace-contained.
  Read-only heavy assets may be symlinked during development.
- A `tests/unit/test_isolation.py` runs each step against a temp `BookWorkspace`, hashes protected
  live roots before/after, and fails on any mutation outside the workspace. A grep for repo-root
  dir names remains as a cheap lint, not the primary guarantee.
- Guarded steps (`cleanup`, `translate`, `all`) write only to disposable `work/`, so they don't
  endanger the live edition. Still port a per-book overwrite guard — its mechanism is refined to a **workspace-internal detect-and-refuse** check at M4b/M4c (branch register **BR-012**), with `ENGINE_ALLOW_REGEN` as a candidate explicit override. Add deny
  entries to `.claude/settings.local.json` for `engine/cli.py … --book per_la_liberta` cleanup/translate/all
  (note: `.claude/` is gitignored and protects only local Claude usage; the portable guarantees are
  the code-level regen guard and path isolation).

### Validation strategy

Three tiers (canonical: `engine/docs/port_discipline.md`) — **equivalence** (golden),
**contract/property**, and **separability**. The **equivalence** tier reproduces only
**deterministic, no-LLM, no-network** steps; its reference is **generated by running the live step
over frozen copies of committed inputs** — *not* diffed against committed live artifacts, which have
drifted (e.g. `data/reconciled_chapters.json` carries hand-applied OCR fixes; see `ENGINE_M3_PLAN.md`
F1). Never run download/ocr/cleanup/translate/multi_translate/refine for reproduction. Equivalence is
the regression net, **not** the definition of done — the contract/property and separability tiers
prove correctness and generalization, which golden cannot.

Golden tests (`tests/golden/`, inputs under `books/per_la_liberta/inputs/` as frozen copies):
- `test_chapterids_golden` — `LanguagePlugin` chapter identities match a frozen expected JSON
  fixture for all forms (`short`, `parse_md`, `html_slug`, page range). It does not call live
  top-level code at test time. (Tripwire for the hardest refactor.)
- `test_validate_golden` — parameterized validate on a frozen copy of the live cleaned text
  (`books/per_la_liberta/inputs/clean.md`) reproduces `data/validation_report.json` per-check
  pass/fail + key counts (h2≥3, h3==57, ≥60% retention, <0.5% foreign, zero high-severity
  word-quality), modulo the one generalised label `italian_char_coverage` → `char_coverage`.
- `test_reconcile_golden` (equivalence tier) — reconcile on frozen copies of
  `data/copy{1,2,3}_raw.txt` reproduces a **generated** reference (live `reconcile.py` over those
  copies), **not** the hand-edited `data/reconciled_chapters.json`; covers `reconciled_chapters.json`,
  `flagged_segments.json`, and `chapter_pages.json`. See `ENGINE_M3_PLAN.md` F1/D1.
- `test_typeset_golden` (M3b) — typeset on copies of the clean/translation/typography inputs
  matches `output/bilingual.html` in a temp docs/static/page-image workspace with deploy-sync
  disabled (normalize CSS version-hash/timestamps before diffing; supplement with semantic
  assertions for anchors, scan links, font/CSS paths, typography spans, and page-overlay bounds).
- adjudicate has **no** golden: its input (`review_flags.json`) is unrecoverable in paired form,
  so it is validated by **property/unit tests** of its classification branches (noise / ner /
  compound / corrected / unknown) on a synthetic flags fixture. (See `ENGINE_M3_PLAN.md` F2/D3.)

Unit tests (`tests/unit/`, no live data): config loader merge/override/schema; Italian ordinals &
title→English; the 7 validate checks on a synthetic 2-chapter book; prompt templating (StrictUndefined
raises; no PLL strings leak under a different manifest); period-dict lookup + ≥2-of-N oracle; isolation.
Add a sidecar-contracts track: versioned schemas plus id/path-shape assertions for
`review_flags.json`, `triage_resolved.json`, `chapter_start_pages.json`, `source_pages.json`,
`typography.json`, `*_progress.json`, `narrative_context.json`, and `page_concordance.json`, with
per-step tests proving each output satisfies the next step's input contract.

### Heavy assets & extraction

- **During dev:** frozen copies for golden inputs; symlink only large read-only assets. From
  `engine/assets/`, three symlink roots: `dictionary` → `../../assets/dictionary` (period dicts),
  `frequency` → `../../data/dictionaries` (the `it_combined.txt` frequency dict, which lives under
  `data/`, not `assets/`, in the live tree), and `fonts` → `../../docs/assets/fonts`. `paths.asset_path`
  resolves against `ASSETS_ROOT` (`engine/assets/`) so symlink-vs-copy is invisible to code; golden
  tests hash live roots before/after and assert they are untouched.
- **At extraction:** replace symlinks with real copies of the three period-dictionary chunk dirs
  (+ index/headwords, not the gitignored `raw.txt`) under `assets/dictionary/`, `it_combined.txt`
  under `assets/frequency/` (mirroring the dev root), OFL fonts under `assets/fonts/`, font OFL files
  (`docs/assets/fonts/{Fraunces,Spectral}/OFL.txt` exist), and dictionary provenance notes (IA URLs
  + rights status). `tests/unit/test_assets.py` then verifies every config-referenced asset resolves
  against the copies.
- **Mechanism:** `git subtree split --prefix=engine <branch>` → fresh repo (history-preserving).
  Gate on a CI grep proving no `from <toplevel_module> import …` under `engine/` and the isolation test.

## Staged milestones (no time estimates)

- **M0 — Branch + scaffold.** New branch (e.g. `engine-framework`); create true-src-layout
  `engine/` tree; own `pyproject.toml` (deps + `jsonschema` + Italian spaCy extra); corrected
  read-only asset symlinks; frozen fixture area; empty step stubs; CI wiring.
  *Done when:* `uv sync` in `engine/` succeeds; empty suite runs.
- **M1 — Config model + Italian LanguagePlugin.** Complete grep-backed constant/prompt/sidecar
  inventory; dataclasses + JSON-schema validation + per-field merge/override; Italian plugin
  (ordinals, heading, title→English, `ChapterIdentity` with all id forms); write
  `books/per_la_liberta/manifest.json` + the language/scan/typeface profiles. *Done when:*
  config-loader, Italian-lang, sidecar-contract basics, and `test_chapterids_golden` pass. (Proves
  the hardest refactor first.)
- **M2 — First safe step: `validate`.** Port the structure/threshold/word-quality engine. *Done when:*
  `test_validate_golden` reproduces `data/validation_report.json`; `test_validate_engine` passes on the
  synthetic book. Framework now reproduces a real PLL result.
- **M3 — `reconcile` (+ `adjudicate`).** Port the deterministic *upstream*; closes the
  `validate` producer/consumer inversion. `adjudicate` stays Zingarelli-only (faithful), ported
  behind a thin interface (oracle re-expression deferred — branch register BR-001). *Done when:*
  `reconciled_chapters.json` / `flagged_segments.json` / `chapter_pages.json` reproduce a
  generated reference (per Validation strategy) and reconcile's required tiers (equivalence +
  property + separability + isolation) pass; adjudicate passes property/unit tests (golden
  deferred — `ENGINE_M3_PLAN.md` F2/D3).
- **M3b — `typeset`.** Port `typeset` (1607 lines) + `typography.py` (219) with deploy-sync
  neutralized to the workspace and the isolation invariant front-and-centre. *Done when:*
  `bilingual.html` reproduces (normalized) given clean + translation + page-mapping inputs. The
  framework can then typeset any book given those inputs; it cannot yet take arbitrary raw OCR to
  a finished bilingual edition.
- **M4a — Acquisition/OCR.** Port `download` and `ocr` with source fetch, PDF/image rendering, OCR
  prompt templating, and workspace-contained progress files. *Done when:* unit tests and synthetic
  smoke prove paths/prompts are configurable.
- **M4b — Text mutation.** Port `triage` and `cleanup`; migrate triage/cleanup prompts; re-key
  cleanup's spaCy/dict/word-set singletons by language id. Do **not** run against PLL (guarded).
  *Done when:* templating + cleanup unit tests pass; manual smoke on the synthetic fixture.
- **M4c — Translation/refinement.** Port `translate` and `refine`; migrate translate/refine prompts
  and state/progress contracts. Do **not** run against PLL (guarded). *Done when:* generation-state
  contract tests pass; manual smoke on the synthetic fixture.
- **M5 — Multi-witness + SynthesisBackend.** Small-port `providers.py` into the package; add CLI +
  API synthesis backends; port `multi_translate` with the eval-rubric/provenance templates. *Done
  when:* draft+evaluate run on the fixture via API; synthesis preflights the CLI cleanly when selected.
- **M6 — Reusable review primitives.** Generalize `membership_oracle` and `vision_reread` (native-res,
  optional second-copy escalation). This is not a dependency of M2/M3 reproduction. *Done when:*
  oracle unit tests pass; `vision_reread` exercises both `primary_only` and concordance-escalation
  modes against configured manifests.
- **M7 — Extraction readiness.** No-toplevel-import grep gate + isolation test; copy heavy assets;
  dry-run `git subtree split --prefix=engine`. *Done when:* a throwaway clone of the split builds and
  passes `tests/unit` + the synthetic golden without the parent repo present.

**Build-first kernel:** M0+M1+M2 (scaffold + config model + `validate` reproducing a real PLL result)
is the proven spine; everything else fans out from it.

## Risks & tradeoffs

- **Duplication/divergence.** Top-level scripts and `engine/` will drift (ongoing PLL review edits to
  `output/italian_clean.md` land only in the live tree). Mitigation: refresh `books/.../inputs/` from
  live for golden tests; treat `engine/` as a forward seed, not a live mirror. Do not attempt
  bidirectional sync — that defeats the safety goal.
- **Synthesis non-reproducibility.** PLL's exact translation text was produced by the `claude` CLI
  path and isn't API-reproducible — so validation deliberately covers the deterministic spine, not LLM
  outputs.
- **spaCy wheel pins** are brittle (a minor bump can break the lock); document the pin-update procedure.
- **Gitignored deny list** is local-only; structural isolation is the real guarantee.
- Companion and the bulk of the review phase are intentionally out of scope (per decisions).
- **Import shadowing** is a nested-development risk; true src layout plus strict pytest
  rootdir/pythonpath must ensure imports resolve to engine modules, not top-level twins.
- **Golden fixture scope and cadence** should stay explicit; spaCy-backed, full-OCR, and HTML-diff
  tests should be marked `golden`/`integration` so CI and local workflows run the intended suite
  deliberately and consistently.
- **Model/version drift** should be recorded in run metadata/manifests without presenting current
  frontier model IDs as stable defaults for future books.
- **Step-contract drift** is likely unless sidecar schemas are versioned and tested.

## Verification

- `cd engine && uv sync --extra it` succeeds; `uv run pytest tests/unit` is green at each milestone,
  with `uv run pytest tests/golden` green for milestones that port golden-gated steps.
- After M2/M3, manually confirm the framework's `validate`/`typeset` output for PLL matches the
  committed `data/validation_report.json` / `output/bilingual.html` (normalized).
- Confirm the live edition is untouched: `git status --short` shows no modifications outside
  `engine/` and an explicit plan/docs allowlist; golden tests assert protected root paths
  (`data/`, `output/`, `state/`, `docs/`, `static/`) are unchanged before/after any `engine/cli.py`
  run.
- Extraction smoke (M7): `git subtree split --prefix=engine` → clone → `uv sync && uv run pytest
  tests/unit` passes without the parent repo.

## Critical files to reference

- `pipeline.py` — orchestration seam (dir threading + regen guard) → port into `engine/cli.py`
- `utils.py` — short chapter-id scheme + ordinals + boilerplate → Italian LanguagePlugin (feeds `ChapterIdentity`)
- `translate.py` — parse-markdown chapter-id scheme, `SYSTEM_PROMPT`, title→English → LanguagePlugin/`ChapterIdentity` + translate template
- `cleanup.py` — largest constant surface (substitution/boundary rules, spaCy+dict singletons)
- `validate.py` — structure/threshold/word-quality engine (M2 first-safe-step golden target)
- `typeset.py` — scan/page IDs, HTML anchor slugs (`_slug`), page ranges, source links, typography and deployment-sync behavior
- `typography.py` — scan-verified sidecar application contract
- `build_concordance.py` — second-copy page concordance generation and review state
- `edgren.py` / `hoare.py` — chunked-dictionary file formats and lemmatized lookup behavior
- `vision_review.py` / `adjudicate.py` — sources for the two reusable review primitives
- `providers.py` — mostly generic, but imports top-level `utils` (`retry_api_call`) and carries Edgren-specific prompt wording — a small port, not a verbatim move
