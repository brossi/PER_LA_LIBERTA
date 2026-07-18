# Engine M4 Plan — Acquisition / Text-mutation / Translation (`M4a` · `M4b` · `M4c`)

> Standalone review artifact. Audit inline with `@@@@@@` blocks; I'll answer each
> with a paired `======` (code-verified, per point) before porting anything.
> File:line anchors for **M4a** are read directly against the live tree at plan time;
> **M4b/M4c** anchors are reconnaissance-level (symbol names verified, line regions
> approximate) — those sub-milestones get their detail when reached, not now.

## Sequencing (ratified 2026-06-22)

- **M4 = three sub-milestones, ported in order:**
  - **M4a — Acquisition/OCR:** `download` (32 ln) + `ocr` (331 ln). *Detailed here — the buildable part.*
  - **M4b — Text mutation:** `triage` (350 ln) + `cleanup` (1509 ln). *Sketched at decision/seam altitude.*
  - **M4c — Translation/refinement:** `translate` (468 ln) + `refine` (442 ln). *Sketched.*
- **M3b (`typeset`) is deferred** (user decision, 2026-06-22): not a dependency of the
  acquisition→mutation→translation spine, and built when actually needed. It stays task #9,
  unblocked. M4 leapfrogs it; nothing in M4 depends on it and it depends on nothing in M4.
- **Why M4a first.** `download`/`ocr` are the deterministic-*upstream* producers of the
  `copy{1,2,3}` witnesses that M3's `reconcile` currently reads from frozen `inputs/`. Porting
  them closes the same producer/consumer inversion M3 closed for `validate` — and lets us prove
  the **acquisition → reconcile** contract on engine-produced witnesses. They are also the two
  *smallest* M4 steps and the ones that force the new machinery the rest of M4 inherits — the
  **prompt-templating machinery** (reused by every later prompt) and the **backend-injection
  pattern** (inject a backend for offline tests). The *specific* acquisition seams
  (`Fetcher`/`PageRenderer`/`OcrBackend`) do **not** propagate — per BR-009 the chat-seam is
  re-decided at M4c; the *pattern* carries forward, not the seams. So building them first de-risks
  M4b/M4c.
- **Why one plan, not three.** The user asked for `ENGINE_M4_PLAN.md`. This covers the arc so the
  shape is visible, details M4a, and holds M4b/M4c at altitude. If M4b (cleanup, the codebase's
  largest single file) or M4c warrants a focused sub-plan when reached — as `typeset` earned M3b —
  it gets one then. Over-specifying them now would go stale (the code isn't touched yet) and would
  design language-generalization seams blind, against only PLL (the single-fixture blind spot).

## Discipline (applied — canonical: `engine/docs/port_discipline.md`)

This section *applies* the canonical discipline to M4; it does not restate it.

### Required tiers — the M4 shift: most of M4 is **non-deterministic**

M2/M3 were deterministic and led with equivalence. **Every M4 step except one path is
non-deterministic** (network fetch / LLM call), so per `port_discipline.md` §1 their floor is
**property + separability + isolation** — there is *no* equivalence golden, by construction
(§1: "Deterministic, no-LLM, no-network steps only"). The network/LLM boundary is made
**injectable** so the property/separability tiers run fast and offline (the adjudicate
`DictionaryOracle` pattern, applied to fetch + OCR + chat backends).

| Step | Regime | Required tiers |
|---|---|---|
| `download` | network | property + separability + isolation |
| `ocr` | LLM (vision) | property + separability + isolation *(deterministic `_stitch_pages` → unit)* |
| `triage` | LLM | property + separability + isolation *(deterministic plausibility check → unit)* |
| `cleanup` **deterministic core** (`use_llm=False`) | deterministic | **equivalence + property + separability + isolation** (D4) |
| `cleanup` **LLM-correction path** | LLM | property + separability + isolation |
| `translate` | LLM | property + separability + isolation *(parse/title/assemble/sidecar → unit)* |
| `refine` | LLM | property + separability + isolation *(change-parse + snapshot/revert → unit)* |

The one equivalence golden in M4 is **cleanup's deterministic core** (D4): its `use_llm=False`
path is deterministic / no-LLM / no-network, so the "for a step that *can* support a tier, that
tier is **required**" floor (§1) applies — pinning the largest deterministic transformation
surface in the whole codebase. *Skipping it because the step's default path uses the LLM would be
weakening the measurement, not the thing.*

### One-way doors (decided on the record → branch register when porting)

- **The prompt-context contract** (M4a). M1 left `manifest.prompt_context` a free dict
  ("keys defined by the M4 prompt templates"). M4a's OCR template is the **first consumer** and
  thereby *defines* the first keys + the template-resolution mechanism every later prompt inherits.
  Config-schema/contract surface → BR-008.
- **The M4a acquisition backend seams** (`Fetcher` / `PageRenderer` / `OcrBackend`). Minimal,
  purpose-built, injectable; `providers.py` untouched → **BR-009 (resolved)**. The distinct
  **chat-seam ↔ `providers.py`** question (triage/cleanup/translate/refine, text→text) is split out
  and **deferred to M4c's formal development** — not an M4a concern.
- **OCR model-id config home** (M4a, D3 — **resolved**: a `manifest` `ocr` block). A config-schema shape change.
- **`triage` tool-schema + category taxonomy home** (M4b, D5).
- **cleanup language-singleton re-keying** (M4b) and **the translation/refinement state contracts**
  (`translation_progress.json`, `translation_revisions/`) (M4c) are step contracts.

### Branch-register read obligation — M4 is where three deferrals come due

Per §5 ("Before starting, each milestone consults the branch register for entries whose revisit
condition it satisfies"):

- **BR-002** (non-Italian separability fixture) — revisit "after the language-config-consuming
  steps are ported (**M4b cleanup is the largest consumer**)." **Comes due at M4b.**
- **BR-006** (Bodoni-scan ordinal garbles living in the Italian plugin) — revisit "when a 2nd
  Italian/same-typeface book is added, or at M7." M4b/M4c *consume* those garbles (cleanup's
  substitution tables; translate's `_ITALIAN_NUMBERS` title path) → **re-read at M4b/M4c**, expect
  to re-defer (no 2nd book yet).
- **BR-007** (literal word-fix vs. layered char-confusion model) — revisit "during M4b cleanup
  (where the confusion→dictionary mechanism lives)." **Comes due at M4b.**

M4a itself touches none of these (it is acquisition, language-neutral). The honest plan: name them
now; resolve-or-re-defer them *with the information M4b porting surfaces*, not speculatively here.

## Findings from pre-port verification (these reshape the strategy)

**F1 — M4 is the non-deterministic frontier.** Unlike validate/reconcile/adjudicate, every M4
entry point calls a network or LLM backend: `download` HTTP-GETs Internet Archive
(`download.py:23`); `ocr` calls Gemini vision (`ocr.py:71`); triage/cleanup/translate/refine call
Anthropic (and cleanup optionally Gemini). Consequence: **no equivalence golden** except cleanup's
deterministic core (F5). Validation leans on property + separability with the backend injected.

**F2 — the new machinery is already scaffolded as stubs M4 fills; no new deps.**
- `prompts/templating.py` is a 1-line stub: *"Jinja2 StrictUndefined PromptTemplate … deferred to
  M4 deliberately: its first consumer is an OCR/translate prompt … built then, co-located with its
  first template, so its shape is consumer-informed."* M4a builds it.
- `providers.py` is a stub (*"M5"*). M4a does **not** build it — it stands up a *minimal* seam (D1)
  and leaves the unified provider abstraction to M5.
- **Every M4a dependency is already declared** in `engine/pyproject.toml` (verified): `jinja2`,
  `google-genai`, `pillow`, `pymupdf`, `requests`. M4a adds **no** new dependency — M0 pre-declared
  them.

**F3 — `manifest.prompt_context` is already seeded; M4a's OCR template binds the first subset.**
The PLL manifest already carries `book_title`, `author`, `year`, `language_name`, `subject`,
`entities` (`books/per_la_liberta/manifest.json:53-66`). The live `OCR_PROMPT` (`ocr.py:27-38`)
**bakes those facts in as literal text** — *year (1913), language name (Italian), book title,
author*, plus a language accent inventory (`à è ì ò ù é`) — all hardcoded, none interpolated (which
makes the templating case *stronger*: nothing is parameterized today, so the port must *extract* the
baked literals into the book/language layers). So M4a's template consumes a **subset** of an already-declared context — it does
not invent the keys, it ratifies them (the translate/triage/refine prompts later bind `subject` +
`entities`). The accent inventory comes from the **language profile**, not `prompt_context` (it is
a cross-title language fact, like `word_score_accents` — BR-004 logic). **D2/BR-008 reshapes the
seam:** `language_name` also moves out of `prompt_context` into the profile, leaving `prompt_context`
book-identity-only.

**F4 — the source PDF is a per-book *input*, not a shared asset; the synthetic book has none.**
`ocr` renders pages from the LOC PDF (`ocr.py:17`, 82 MB, gitignored). `paths.asset_path` resolves
*shared* read-only assets (dictionaries, fonts) — the PDF is neither shared nor an asset. It is a
book input, and the synthetic fixture ships no PDF. Consequence (D7): a per-book scan-path
resolution + an **injectable `PageRenderer`** so unit tests need neither a real PDF nor PyMuPDF,
plus **one** `integration`-marked test that creates a tiny PDF via `fitz` and renders it — so the
PyMuPDF binding is actually exercised, not shape-asserted (validate-bindings).

**F5 — cleanup's deterministic core is golden-able; its LLM path is not.** `cleanup(use_llm=False)`
runs only deterministic stages (noise strip, regex prefilters, dehyphenation, sentence-dedup,
symspell + spaCy NER) — deterministic given pinned `spaCy it_core_news_lg` + `symspellpy` (the
rapidfuzz situation: pin + golden-as-tripwire). So the deterministic core **can** support
equivalence → the floor **requires** it (D4). The `use_llm=True` correction pass is non-deterministic
→ property only.

**F6 — substrate already in place for M4 (from M3 + M0).**
- **Two emit/parse protocols span producer↔consumer here**, both needing shared-constant
  discipline so emitter and parser cannot silently drift:
  - **`⟨PAGE:N⟩` page marker** — `ocr` emits it (`ocr.py:20`), `reconcile` parses it
    (`reconcile.py:21`, a code default in M3). M4a must single-source the marker grammar (the literal
    `⟨PAGE:{}⟩`) — `ocr`'s emit-format and `reconcile`'s parse-regex *derived* from it, since they
    are a `.format()` string and a compiled regex, not one interchangeable object (property test:
    `ocr` output is parseable by `reconcile._strip_page_markers` + the page-map consumer). This is a **code default** — superseding the framework plan's constant map, which
    earlier routed `PAGE_MARKER` → `ScanProfile`; internal tag protocols stay code defaults per that
    plan's own Approach, and M3 already baked the marker as a shared code constant.
  - **`[BLANK]` / `[OCR_ERROR]` page sentinels** — easy to miss because `[BLANK]` *crosses the
    template boundary*: `OCR_PROMPT` instructs the model to emit it (`ocr.py:36`) and
    `_stitch_pages` matches it (`ocr.py:244`), so once the prompt becomes a book-neutral template
    the sentinel sits in the *template* while the stitcher checks it in *code* — drift with nothing
    turning red, the same hazard as the page marker. (`[OCR_ERROR]` is code↔code: emitted
    `ocr.py:172`, prefix-matched `:244`.) M4a factors both as shared sentinel constants the template
    references and the stitcher asserts.
- `adjudicate.DictionaryOracle.lookup` / `dictionary_context_for_flags` were ported in M3
  *specifically so cleanup can reuse them* (M3 plan §adjudicate). M4b's cleanup receives the oracle
  from config rather than re-deriving Zingarelli context.
- translate's chapter-title path (`_ITALIAN_NUMBERS`, ordinal compounding) reuses the Italian
  plugin's already-ported `parse_chapter_number` + ordinal maps (incl. the BR-006 garbles).

**F7 — CLI exception taxonomy + step-option threading were deferred to M4a (M3 residual).**
The CLI catches only `NotImplementedError` (`cli.py:83`) and `run()` passes only `ws/cfg/lang`
(`cli.py:82`) — no step options. `reconcile.run` raises a bare `FileNotFoundError` on missing
copies (M3 known residual, "Deferred to M4a"). M4a builds out: (a) a small engine exception set
mapped to exit codes, folding in reconcile's missing-input case; (b) `--step` option threading
(`--workers`, `--model`, `--pages`, api keys) into `run(*, ws, cfg, lang, **opts)`.

---

## M4a — `download` + `ocr` (the detailed port)

### `download` port

**Language-neutral mechanics → `steps/download.py`** (port ~verbatim): idempotent
skip-if-exists; write `copy1_raw.txt` / `copy2_raw.txt` (`download.py:12-13`).

**Config bindings**

| Live constant (file:line) | → destination |
|---|---|
| `COPY1_URL` / `COPY2_URL` (`download.py:6-7`) | **`manifest.sources[].url`** — *already present* (`manifest.json:11-23`). The two `{role:copy1\|copy2}` sources carry both `ia_item_id` and an explicit `url`. |
| the `{id}/{id}_djvu.txt` IA convention | **code default** in the step: when a source has no `url`, derive it from `ia_item_id`. The explicit `url` (present for PLL) wins; the convention is the fallback. |
| target filename `copy{role}_raw.txt` | **code default** keyed off `source.role`. |
| network fetch (`requests.get`, `download.py:23`) | **injectable `Fetcher` seam** (D1): `fetch(url) -> str`; default = `requests`; tests inject canned bytes. |

**Output (→ `ws.data`):** `copy1_raw.txt`, `copy2_raw.txt`. Only sources with a `download` regime
(IA djvu text) are fetched; the `copy3` witness is *produced by `ocr`*, not downloaded — the
manifest's `sources[]` lists copy1/copy2 only, so the step iterates exactly those.

### `ocr` port

**Language-neutral mechanics → `steps/ocr.py`** (port ~verbatim): page-range + resume via a
progress dir of `page_{n:04d}.json` (`ocr.py:128-134`), sequential / `ThreadPoolExecutor` workers
(`ocr.py:181-222`), retry with `[2,8,16]` backoff (`ocr.py:163-172`), `_stitch_pages` →
text + `page_map` of `{page,char_start,char_end}` (`ocr.py:225-270`). `_stitch_pages` is **pure**
given page texts → unit-tested directly.

**Config bindings**

| Live constant (file:line) | → destination |
|---|---|
| `DEFAULT_PDF` (`ocr.py:17`) | **`manifest.scan.pdf`** (already present) resolved to a per-book scan path (D7). |
| `PAGE_MARKER = ⟨PAGE:{}⟩` (`ocr.py:20`) | **shared code-default protocol** — a single-sourced marker *grammar*: `ocr`'s emit-format + `reconcile`'s parse-regex (`reconcile.py:21`) derived from one literal (F6), so emitter/parser can't drift. |
| `[BLANK]` / `[OCR_ERROR]` sentinels (`ocr.py:36,172,244`) | **shared code-default sentinels** (F6) — `[BLANK]` crosses the template↔stitcher boundary, so it is a referenced constant, not a free literal duplicated in template and `_stitch_pages`. |
| `GEMINI_MODELS` flash/pro ids (`ocr.py:22-25`) | **config, no engine default** (D3) — frontier ids are not baked (framework risk note). |
| `OCR_PROMPT` (`ocr.py:27-38`) | **prompt template** (D2): book facts from `prompt_context`, accent inventory from the language profile, generic rules in the template body. |
| `dpi=200` / JPEG `quality=85` (`ocr.py:47,52`) | **code defaults** (scan-render tuning); promotable to the `ocr` config block later if a book needs them (noted, not elevated). |
| PDF render (`fitz`, `ocr.py:41-53`) | **injectable `PageRenderer` seam** (D7): `render(pdf_path, page, dpi) -> bytes`; default = PyMuPDF. |
| Gemini call (`ocr.py:66-83`) | **injectable `OcrBackend` seam** (D1): `transcribe(image_bytes, prompt) -> str`; default = Gemini; tests inject canned page text. |
| api-key resolution (`ocr.py:106-109`) | step opt / `GEMINI_API_KEY` env (unchanged), threaded via `**opts` (F7). |

**Outputs (→ `ws.data`):** `copy3_raw.txt` (pro) / `copy3_flash.txt` (flash) +
`copy3_{model}_page_map.json` — the exact names `reconcile` reads. **Progress → `ws.state`**
(`ocr_{model}_pages/`): resume scaffolding is transient state, matching translate's
`state/translation_progress.json` convention (live `ocr` parks it beside the output in `data/`;
routing it to `state/` is a two-way door, aligned to the engine's area semantics).

### Prompt templating machinery (built here, first consumer = OCR)

- **`prompts/templating.py`:** a `PromptTemplate` over **Jinja2 `StrictUndefined`** (per the stub's
  declared design). StrictUndefined makes a template referencing an absent context key a **hard
  error**, not a silent empty string — validate-bindings at render time.
- **Template *files* are book-neutral and profile-resident** — `engine/profiles/prompts/ocr.txt.j2`,
  the framework layout's shared `profiles/prompts/*.txt.j2` home for reusable knowledge that outlives
  any one book (the dir already exists, `.gitkeep`-empty). This is **distinct from the rendering
  *machinery*** at `src/engine/prompts/templating.py`: the template *engine* is engine-package-owned;
  the *templates* are one shared profile-level set (not per-book, D2a); the *book/language* supply
  only values. This keeps the engine core free of book identity (engine-agnostic memory). A future
  book needing a structurally different OCR prompt pulls a per-book template override — deferred until
  one does (BR-008 note).
- **Context assembly (BR-008 boundary):** a **namespaced merge** — `{{ book.* }}` from
  `manifest.prompt_context` (book identity), `{{ language.* }}` from the language profile (display
  name + accent inventory). `language_name` is dropped from `prompt_context` and the profile gains a
  display-name field. One builder function, reused by every later prompt that renders book/language facts
  (triage/cleanup/translate/refine in M4b/M4c; multi-eval/synthesis/provenance in M5).
- **Separability/leakage test (the genericity bite the stub names):** a **single** render of
  `ocr.txt.j2` with the **synthetic** book's *own loaded context* → assert **no PLL string leaks at
  all**: book identity (`Per la libertà`, `Crespi`, `1913`) **and** language facts (the name
  `Italian`, the accent list `à è ì ò ù é`). For the language-fact half to bite while the synthetic
  book keeps the Italian *plugin* (it must — only `it` is registered, BR-002), the synthetic manifest
  **overrides** its prompt-facing language facts (`display_name`, `accent_inventory`) to non-Italian
  values; `language_id` stays `it`, so reconcile/validate's Italian word-scoring is untouched. A baked
  Italian name or accent then shows up here as a leak. This is the prompt's separability tier and the
  reason the template work waited for a non-PLL fixture. (The fixture, not the assertion, is what
  carries the non-PLL-ness — splitting the tier or exempting the accent list would be weakening the
  measurement; the synthetic fixture is built so the one decided assertion holds.)

### CLI hardening (F7)

- **Exception taxonomy:** a small `engine.errors` set (e.g. `MissingInputError`,
  `AcquisitionError`, `BackendError`) → distinct non-zero exit codes; fold in reconcile's
  missing-copies case (replacing its bare `FileNotFoundError`). **Keep it minimal — one type per
  concrete M4a raiser** (`MissingInputError` = reconcile's missing copies; `AcquisitionError` =
  `download` network failure; `BackendError` = `ocr` Gemini failure); do not add categories "for
  completeness" without a raiser (YAGNI).
- **Step options:** extend the parser + `_run_step` to thread `--workers / --model / --pages /
  --api-key` into `run(*, ws, cfg, lang, **opts)`.

### Validation — M4a tiers

- **Property / contract (fast, injected backends):**
  - `download`: writes exactly the fetcher's bytes to `copy{1,2}_raw.txt`; URL-derivation fallback
    equals the explicit `url` for a source that omits it.
  - `ocr`: `_stitch_pages` page-map invariants (every page has a marker; `char_start/char_end`
    bound that page's text; `[BLANK]`/`[OCR_ERROR]` pages contribute a marker but no body); the
    blank/error sentinels the template+backend emit equal the ones `_stitch_pages` matches (no
    template↔code drift); resume skips completed pages.
  - **`ocr` → `reconcile` contract** (closes the inversion): a canned multi-page OCR run produces
    output that `reconcile._strip_page_markers` + the page-map consumer accept — i.e. the marker
    protocol round-trips between the two ported steps.
- **Separability:** run `download` (injected `Fetcher`) + `ocr` (injected `PageRenderer` +
  `OcrBackend`) on the **synthetic** book → produces `copy{1,2,3}` + page map in `work/data`; then
  the existing M3 synthetic `reconcile` runs on them. The injected backends are *seeded from the
  frozen synthetic `inputs/`* (so `inputs/copy{1,2,3}` are the **expected acquisition output**, read
  as canned-response seed — they are **not** re-frozen; single-owner intact). **Per-page `OcrBackend`
  responses are sourced by splitting the frozen synthetic `copy3` on its `⟨PAGE:N⟩` markers** —
  porting must confirm the synthetic `copy3` carries them (author per-page responses if it is flat).
  **The synthetic fixture also takes the schema additions** (its manifest an `ocr` block, BR-010; its
  language profile the display-name field, BR-008 — the schema changes apply to every
  manifest/profile, fixtures included). Plus the prompt leakage test above.
- **Isolation:** `download.run` / `ocr.run` against a temp workspace; the five protected roots
  (`data/output/state/docs/static`) unchanged before/after. (`ocr`'s real-render path is the lone
  `integration` test, D7; everything else is fast.)
- **No equivalence golden** (F1) — recorded explicitly, not omitted silently.

### M4a does **not** run against PLL's real sources (D6)

The PLL witnesses are already frozen in `books/per_la_liberta/inputs/`. Re-fetching IA / re-running
Gemini is pointless (we have them) and costly. M4a is validated on the synthetic book with injected
backends + the one real-`fitz` render smoke. **No regen-guard prompt is needed** (unlike
cleanup/translate): the `BookWorkspace` sandbox already makes a stray engine acquisition run
harmless — it writes to `work/`, which cannot reach `inputs/` or the live tree. The guard was a
live-tree concern; the engine has no live tree to endanger.

### M4a — done when

- `download` + `ocr` pass **property + separability + isolation** (the non-deterministic floor; no
  equivalence golden, F1), all with injected backends.
- The **`ocr` → `reconcile`** marker round-trip **and** the `[BLANK]`/`[OCR_ERROR]` sentinel
  template↔stitcher sync pass (the two shared protocols, F6).
- One real-`fitz` **`integration`** render smoke passes (PyMuPDF binding exercised, not
  shape-asserted, D7).
- The **prompt-leakage** render test passes — no PLL strings leak from `ocr.txt.j2` under the
  synthetic book (the templating-machinery + namespaced-context separability proof, BR-008).
- CLI **exception taxonomy** + **step-option threading** (F7) land, folding in reconcile's
  missing-input case.
- Isolation holds: the five protected roots unchanged before/after any `download`/`ocr` run.
- The synthetic book runs acquisition with **no special invocation** (D6); M4a is **not** run against
  PLL's real IA/Gemini sources.

---

## M4b — `triage` + `cleanup` (sketch; detail at porting time)

**`triage`** (`triage.py`) — `triage_items(...)`: reads `flagged_segments.json`, calls Anthropic
(sync, batched, tool-use `classify_disagreement`), merges resolutions into `reconciled_chapters.json`.
- **Injectable chat seam** (D1 shape) for the Anthropic call; deterministic plausibility check
  (`SequenceMatcher ≥ 0.4`) → unit.
- **Disagreement taxonomy + tool schema** (`TRIAGE_SYSTEM` ~`:59-80`; the `classify_disagreement`
  enum) → **D5/BR-011**, decomposed by nature: the seven-member enum is a *general*
  OCR-disagreement taxonomy → **code default**; the Italian/Bodoni example patterns → **config**
  (template, `source_noise` + language); the physical-witness descriptions →
  **`manifest.sources[].label`** + the ocr-produced `copy3`.
- Prompt → template (book facts + witness descriptions from config).

**`cleanup`** (`cleanup.py`, 1509 ln — the largest file) — `cleanup(data_dir, output_dir,
use_llm=False, …)`.
- **Deterministic core (golden, D4):** noise strip → `SUBSTITUTION_RULES` (`:20-47`) +
  `BOUNDARY_SUBSTITUTIONS` (`:76-78`) prefilters → punctuation normalize → broken-paragraph join →
  sentence dedup → multi-pass dehyphenation → symspell + spaCy NER (`it_core_news_lg`, `:67`).
  Generator runs live `cleanup(use_llm=False)` over the **frozen `reconciled_chapters.json`** in a
  **temp dir** → `italian_clean_detcore_expected.md` (never touches live `output/` — the guard is a
  live-tree concern; the generator is sandboxed like M2/M3's). Pin spaCy model + symspell; golden as
  drift tripwire.
- **LLM-correction path (property only):** sync per-chapter **and** Batch API
  (`messages.batches.*`); `state/llm_cleaned/{ch}.txt` cache; `corrections.json` audit; reuses
  `adjudicate` Zingarelli context (F6).
- **Config bindings:** the substitution/boundary tables → `SourceNoiseProfile` (already loaded);
  dictionary + spaCy model → `LanguageProfile`; the three lazy **global singletons**
  (`_get_spellchecker`/`_get_ner_nlp`/`_get_word_set`) → **re-keyed by language id** (the framework
  plan's named cleanup task) so two languages don't collide in module state.
- **BR convergence:** **BR-002** (build the non-Italian fixture now that cleanup defines what it must
  differ on), **BR-006** (ordinal-garble homing), **BR-007** (char-confusion vs literal word-fix
  layering) all come due here — re-read and resolve-or-re-defer with cleanup's concrete surface in
  hand.
- **Regen-guard (BR-012):** `cleanup` overwrites `work/output/italian_clean.md` (hand-edited in the
  deviation-review workflow) — destructive to re-run *inside* the sandbox. M4b designs the
  workspace-internal guard (refuse to overwrite protectable output without an explicit override)
  against this concrete surface.

## M4c — `translate` + `refine` (sketch; detail at porting time)

**Chat-seam decision (split here from M4a per BR-009).** Whether M4b/M4c's text→text chat calls
(triage / cleanup-LLM / translate / refine) share the injectable seam that M5's `providers.py`
generalizes — a single `ChatBackend` now, or per-step seams generalized at M5 — is **M4c's** call,
made when M4c is formally developed (it needs the chat consumers in front of it, not OCR's vision
seam). Recorded as the open half of BR-009.

**`translate`** (`translate.py`) — `translate(output_dir, state_dir, …, workers, thinking_budget,
with_edgren)`: reads `italian_clean.md`; per-chapter Anthropic (extended thinking, `ThreadPoolExecutor`);
writes `state/translations/{ch}.md`, `state/translation_progress.json`, `output/english_translation.md`,
`output/source_pages.json`.
- **Default single-model path only** (`translate.py`). The multi-witness synthesis path
  (`multi_translate.py`, the `claude -p … --model opus` subprocess) is **M5**, not M4c — out of scope.
- **Deterministic → unit:** `parse_italian_markdown`, chapter-title translation
  (`_ITALIAN_NUMBERS` `:297-312` — reuses the Italian plugin's ordinal logic, BR-006), `assemble`,
  `_generate_source_pages` (IA-URL sidecar; `IA_ITEM_ID :414` → `manifest.edition.ia_item_id`).
- `SYSTEM_PROMPT` (`:65-79`, binds `book_title/author/subject/entities`) → template; injectable chat
  seam; `with_edgren` enrichment is an optional language-dictionary hook.
- **State contract** (`translation_progress.json` status machine) is a one-way door → recorded.

**`refine`** (`refine.py`) — `refine(...)` + `revert_to_version(...)`: per-chapter Anthropic against
Edgren context; writes revised `state/translations/{ch}.md` + the `translation_revisions/` tree
(snapshot/changes/log).
- **Deterministic → unit:** `_parse_changes` (the `<change old=… reason=…>` regex, `:134-137`, with
  difflib fallback) and the snapshot/revert/version logic are **language-neutral** → strong unit
  coverage with no backend.
- `REFINE_SYSTEM_PROMPT` (`:31-52`) → template; Edgren dictionary is the period-dictionary hook
  (currently mandatory in `refine`, optional in `translate` — noted).
- **Revision-state contract** (`revision_log.json`, snapshot dirs) is a one-way door → recorded.

**Regen-guard (BR-012).** `translate`/`refine` overwrite `work/state/translations/` — the
irreproducible synthesis + refinements (CLAUDE.md), destructive to re-run inside the sandbox. M4c
applies the same workspace-internal guard M4b designs, against its translation/revision artifacts.

---

## Decisions (recommendations; please rule per point)

**D1 — network/LLM backend seam: minimal-now vs. pull `providers.py` forward.**
**Resolved 2026-06-22 (user): minimal acquisition seams in M4a; split M4a from M4c; BR-009 logged.**
M4a stands up three minimal injectable seams — `Fetcher` (download), `PageRenderer` + `OcrBackend`
(ocr) — defaulting to the real backends, mirroring adjudicate's injected `DictionaryOracle`;
`providers.py` is left a stub. These are *acquisition* seams (image→text vision; pure IO), **siblings
of** `providers.py`'s *translation* (text→text) family, not a premature version of it — so "minimal
now" is not throwaway work. The distinct **chat-seam ↔ `providers.py`** question
(triage/cleanup/translate/refine) is **moved to M4c's formal development**. Recorded as **BR-009** in
`engine/docs/decisions/branch_register.md`. *Alt rejected:* build `providers.py` now (designs M5's
translation abstraction blind against OCR-only — the single-fixture blind spot).

**D2 — prompt templates: engine-level Jinja2 `StrictUndefined`, and the book/language boundary.**
**Resolved 2026-06-22 (user): (a) engine-owned book-neutral templates; (b) clean two-layer
boundary.** The template *files* are book-neutral and profile-resident
(`engine/profiles/prompts/*.txt.j2`), rendered by the engine-owned Jinja2 machinery
(`src/engine/prompts/templating.py`) with StrictUndefined — one engine, many templates. The render context is a **namespaced merge** drawing a clean line:
`{{ book.* }}` = book-identity facts (`book_title, author, year, subject, entities`) from
`manifest.prompt_context`; `{{ language.* }}` = cross-title language facts (display name, accent
inventory) from the language profile. `language_name` leaves `prompt_context`; a language display
name is added to the profile (the profile has `language_id` but no human-readable name today). The
synthetic-render leakage test is the separability tier. Recorded as **BR-008** (the boundary is the
one-way door; field names are porting-time two-way doors). *Alt rejected:* keep the live flat blob
(`language_name` beside book identity — redundant, boundary-blurred, lets a language fact vary per
book).

**D3 — OCR model-id home (no baked frontier default). ⟵ the consequential one.**
**Resolved 2026-06-22 (user): (a) — a `manifest` `ocr` block.** Model ids change on a reasonable
cadence as new models ship, so hardcoding them is unsafe; they belong in per-book config (provenance,
explicit, no engine default). → opens **BR-010** (config-schema one-way door).
The framework risk note forbids shipping `gemini-3.1-pro-preview` as a stable engine default.
Options:
- **(a)** a small `manifest` `ocr` block — `{models:{flash,pro}, dpi?, prompt_ref?}` — per-book,
  explicit, no engine default; gives provenance (which model produced `copy3`). *Config-schema
  one-way door.*
- **(b)** CLI-only `--ocr-model` with no default (nothing in config).
- **(c)** keep ids in a code constant (faithful, but bakes a frontier id — violates the risk note).

Recommend **(a)**: OCR is per-book acquisition, the manifest already records `scan` facts, and a
declared model is provenance, not a baked default. Records as a config-schema decision in the branch
register. — Which?

**D4 — cleanup deterministic core gets an equivalence golden.**
**Resolved 2026-06-22 (user): yes — make the core deterministic and golden it.**
Recommend **yes**: `cleanup(use_llm=False)` is deterministic/no-LLM/no-network → the required-tiers
floor applies; it pins the largest deterministic surface in the codebase, generated in a temp dir
(never the live tree). The LLM path stays property-only. *Skipping it because the default path is
non-deterministic would be gaming the measurement.* Flag: version-sensitivity (pin spaCy model +
symspell; golden as tripwire). This is executed at **M4b**, ratified now. *Alt:* property-only
(the discipline's loose default for "cleanup"). — OK?

**D5 — triage disagreement taxonomy + tool schema (M4b; principle ratified now, executed at M4b).**
**Resolved 2026-06-22 (user): code-default *because general* — decompose by actual nature.**
On reading the seven enum members (`ocr_confusion, ocr_corruption, punctuation_artifact,
alignment_drift, missing_text, archaic_spelling, unknown`) they are language-neutral
OCR-disagreement categories (none Italian; `archaic_spelling` is era-general). So:
(1) **category enum + `classify_disagreement` schema → code default** (settled general engine logic,
*not* a deferred-language item); (2) **OCR example patterns → config** via the prompt template
(`source_noise` + language accento, BR-008 machinery); (3) **witness descriptions →
`manifest.sources[].label`** (already present) + the ocr-produced `copy3`. Recorded as **BR-011**
with the own-framing correction (original plan mislabeled the enum "Italian-OCR-flavored"; revisit is
now narrow — only a real 2nd book needing *different categories*, not a language deferral).
*Alt rejected:* lift the enum to `LanguageProfile`/manifest now (it is not language data —
speculative generality).

**D6 — M4a is not run against PLL's real sources; (a) sandbox-only, no guard.**
**Resolved 2026-06-22 (user): (a).** Witnesses already frozen; validate on synthetic + injected
backends + one real-`fitz` smoke. No regen-guard for M4a: acquisition outputs (`copy*`) are
reproducible, and the sandbox makes a stray run harmless to the live tree and `inputs/`. A new book
runs acquisition with **no special invocation** — `--step download`/`ocr` just work (the ceremony-free
normal path (a) is designed to preserve; (b) would have taxed every new book's first acquisition).
**Scope caveat (user catch → BR-012):** the sandbox does **not** protect hand-tuned/expensive
artifacts *within* `work/`. `cleanup` (`work/output/italian_clean.md`) and `translate`/`refine`
(`work/state/translations/`) **are** destructive to re-run inside the sandbox, so a
**workspace-internal regen-guard is owed at M4b/M4c** — designed there against the concrete surface,
as an additive top-of-run check (two-way door; (a) forecloses nothing).

**D7 — scan/PDF path + render seam.**
**Resolved 2026-06-22 (user): (b) — a dedicated `books/<id>/scans/<scan.pdf>` (gitignored),**
distinct from `inputs/` (frozen fixtures) — the same source-vs-frozen separation as D2b. Unit tests
inject `PageRenderer` (no PDF, no PyMuPDF); `manifest.scan.pdf` path-resolution is unit-tested by the
resolved `Path` (no file needed — per D6 the engine never consumes PLL's actual PDF, and the synthetic
ships none); **one** `integration` test creates a 2-page PDF via `fitz` and renders it
(validate-bindings: the PyMuPDF import + render path is exercised, not shape-asserted; no network).
**Follow-up (user catch → BR-013):** introducing `scans/` sharpened the `inputs/` frozen-fixture vs.
engine-producible **shadow** — resolved as a fixture-lifecycle principle (permanent non-det entry
points; per-producer keep-or-retire for deterministic outputs; hard coherence deadline at M7, where
"refresh from live" dies).

## Branch register — entries M4 will open

- **BR-008** — ✓ **logged** — prompt-context contract: book-identity vs. language-fact boundary, namespaced (M4a, D2).
- **BR-009** — ✓ **logged** — M4a acquisition seams (minimal, purpose-built); chat-seam↔`providers.py` split to M4c (M4a, D1).
- **BR-010** — ✓ **logged** — OCR model ids in a per-book manifest `ocr` block (config-schema, M4a, D3).
- **BR-011** — ✓ **logged** — triage taxonomy is general engine logic (code-default *because general*) (M4b, D5).
- **BR-012** — ✓ **logged** — engine regen-guard owed at M4b/M4c (not M4a); workspace-internal, additive (D6 follow-up).
- **BR-013** — ✓ **logged** — `inputs/` fixture lifecycle / frozen-vs-producible shadow; per-producer resolution, hard deadline M7 (D7 follow-up).
- Plus the §"read obligation" dispositions of **BR-002 / BR-006 / BR-007** recorded at M4b.

## Test plan (tiers × step)

- **Equivalence (golden):** `test_cleanup_detcore_golden` only (D4) — `use_llm=False` over frozen
  `reconciled_chapters.json`, freshly generated reference, marker `golden`.
- **Contract / property (fast, injected backends):** download byte-faithfulness + URL fallback;
  `_stitch_pages` page-map invariants + blank/error sentinel template↔stitcher sync;
  **`ocr`→`reconcile`** marker round-trip; triage plausibility check; translate
  `parse/title/assemble/source_pages`; refine `_parse_changes` + snapshot/revert.
- **Separability:** acquisition (download+ocr, injected backends) runs the **synthetic** book and
  feeds M3's synthetic `reconcile`; **prompt leakage** render test (no PLL strings); cleanup runs the
  synthetic book end-to-end (the BR-002 non-Italian fixture is built here once cleanup defines what
  it must differ on).
- **Isolation:** every M4 step against a temp workspace; five protected roots unchanged. Fast tier
  except `ocr`'s one real-render `integration` smoke.

## Out of scope (explicit)

- **`typeset` → M3b** (deferred, task #9, built when needed).
- **Multi-witness synthesis** (`multi_translate.py`, the `claude -p`/`opus` subprocess, eval rubric,
  provenance) → **M5**. M4c ports only `translate.py`'s default single-model path.
- **The ≥2-of-N period-dictionary oracle and vision re-read** → **M6**. cleanup reuses adjudicate's
  Zingarelli-only context (faithful), not the general oracle.
- **Running M4a against PLL's real IA/Gemini sources** (D6).
