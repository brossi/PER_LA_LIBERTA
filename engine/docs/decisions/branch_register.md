# Branch Register

> Forks *seen and not taken*, and one-way-door decisions: the alternative, why passed now, and
> the revisit condition. A recorded passed-branch is **deferred, not lost.** Append-only.
> See `engine/docs/port_discipline.md` §4–§5. Deferral is never to save effort — only when
> intervening work resolves an open question the decision needs.

---

## BR-001 — adjudicate: own step vs. special case of the M6 oracle
- **Opened:** 2026-06-22 (M3 planning).
- **Context:** adjudicate's Zingarelli-only lookup is a special case of the planned M6 ≥2-of-N
  period-dictionary membership oracle.
- **Taken now:** port adjudicate's code in M3 behind a thin interface; keep Zingarelli-only and
  faithful.
- **Not taken:** re-express adjudicate on the general oracle now.
- **Why defer (information, not effort):** the oracle does not exist until M6; deciding now would
  commit blind. M6 builds it and is the point of maximum information.
- **Revisit:** M6, when the oracle exists. (See `ENGINE_M3_PLAN.md` D3.)

## BR-002 — non-Italian separability fixture: build now vs. after the language steps
- **Opened:** 2026-06-22 (governance review).
- **Context:** the synthetic book is Italian, so it tests structural injection, not language
  generalization; the language-axis seams (`word_score_accents`, consonant alphabet, period
  dictionaries) are untested for any non-Italian text.
- **Taken now:** defer; the limit is named in `port_discipline.md` §6.
- **Not taken:** build a non-Italian fixture now.
- **Why defer (information, not effort):** built now it would not know which seams to differ on
  and would pass trivially (the single-fixture blind spot). Porting the language-config-consuming
  steps resolves *what it must exercise*, so a later fixture is built to differ where it matters.
- **Revisit:** after the language-config-heavy steps are ported (M4b cleanup is the largest
  consumer); at the latest before M7 extraction, which claims portability.
- **Resolved (code-neutrality half) at M4b cleanup (2026-06-23):** the obligation split as the plan
  recommended. The **code-neutrality half is done**: cleanup's step code holds no Italian/source-noise
  literal — the accent-fold table, the accented-letter superset (`accented_letters`), and the
  permissive `word_letter_class` are all sourced from `cfg.language`; every OCR-noise pattern from
  `cfg.source_noise`. Proven statically by `test_cleanup_neutrality` (forbids any `À-ÿ`/`£` in
  functional code, docstrings/comments excluded) and behaviourally by the detcore golden (every
  relocation is byte-neutral). The **full non-Italian fixture stays re-deferred to M7** (it needs a
  second registered `LanguagePlugin` + a non-Italian frequency dict + spaCy model — the semantic axis
  no single speculative fixture can pre-design). Adjudicate's identical in-step accent map was
  reconciled to the same `cfg.language.accent_fold` source in the same pass.

## BR-003 — re-baseline-cites-ledger enforcement: automate now vs. review-enforce
- **Opened:** 2026-06-22 (governance review).
- **Context:** the anti-cheat rule (a `*_expected` golden change must cite a divergence or refresh
  entry) needs enforcement.
- **Taken now:** the rule is binding and **review-enforced** (human); stated in `port_discipline.md`
  §5.
- **Not taken:** build an automated check now.
- **Why defer (information, not effort):** no re-baseline workflow exists yet to enforce against;
  building the check now is speculative. M3 produces the first golden and the first possible
  re-baseline.
- **Revisit:** if/when re-baselines become frequent enough that human enforcement is unreliable
  (no earlier than M3's first re-baseline).

## BR-004 — running-head marker: book title lifted out of the *language* plugin (RESOLVED)
- **Opened:** 2026-06-22 (M3 reconcile port / separability work).
- **Context:** `ItalianLanguagePlugin.split_raw_chapters` dropped a running-head line via a
  hardcoded `_PER_LA_LIBERTA_RE = r"\s*PER\s+LA\s+LIBERT[AÀ]!?\s*$"` — that marker is the **book
  title**, not an Italian-language fact, yet it lived beside genuinely language-level markers
  (PREFAZIONE / PARTE SECONDA / FINE DELLA PRIMA PARTE, which are Italian structural *words*). The
  synthetic separability fixture exposed the seam: a non-PLL book has a different running head (or
  none), so the title marker was correct only by accident.
- **Resolved 2026-06-22 (user decision — lift now, do not defer):** for the language plugin/config
  to be a true cross-title resource, the title must not live there. Lifted to **book-level**
  config: new `manifest.structure.running_heads` (a list of regex bodies); the plugin now takes
  `running_heads` as a parameter and anchors each as `\s*(?:<body>)\s*$`, and `reconcile.run`
  passes `cfg.structure.running_heads`. PLL declares `["PER\\s+LA\\s+LIBERT[AÀ]!?"]`; synthetic
  declares `[]`. The Italian structural *words* (PREFAZIONE/PARTE/FINE) stay in the plugin — they
  are language-level and cross-title.
- **Equivalence preserved:** the anchored config pattern reproduces the live marker exactly —
  `test_reconcile_golden` still reproduces (byte-identical).
- **One-way-door note:** this added a `manifest.structure.running_heads` field (config schema
  change). Proven config-driven, not plugin-baked, by
  `test_running_head_drop_is_book_config_not_plugin_baked`.
- **Required, not optional-with-default (rationale):** the field is schema-**required** with no
  code default. Every book declares it explicitly — `[]` is the explicit "this book has no
  running heads", distinct from a forgotten field — so segmentation behavior is always visible in
  the manifest and never silently implicit. This matches the sibling `structure` fields, which are
  all required, and the engine's no-baked-default principle. The cost is one line of boilerplate
  (`"running_heads": []`) for a book that has none; accepted in favor of explicitness. (If a future
  book load proves this boilerplate burdensome, making it optional-defaulting-to-`[]` is a
  backward-compatible schema relaxation.)
- **Why decide now (not defer):** the user called it; a cross-title language layer is a standing
  requirement, not something a second book is needed to clarify. (Other non-cross-title data still
  in the language layer — the Bodoni-scan ordinal garbles — is a separate *homing* concern,
  audited and deferred as **BR-006**; distinct from **BR-002**, which is about a non-Italian test
  fixture, not where scan-noise lives.)

## BR-005 — adjudicate result contract: bare dict vs. self-describing envelope (one-way door)
- **Opened:** 2026-06-22 (M3 adjudicate port; decided with the user).
- **Context:** live `adjudicate.main()` wrote a bare `{chapter_id: [...]}` and, with no input, an
  empty `{}` — which is ambiguous (zero results vs. no input vs. an upstream failure that ate the
  flags). adjudicate has no equivalence golden (F2/D3) and no current consumer (triage, M4b), so
  the output shape is still open to design.
- **Taken now (decided, not deferred):** `run` always writes a self-describing envelope
  `{"input_present", "tokens", "stats", "results"}`. A missing input is an **explicit** no-input
  envelope (`input_present: false`, empty `results`), distinguishable from a populated run and from
  a silent `{}`. Classified entries inside `results` stay byte-faithful to live.
- **Not taken:** stay faithful to the bare-dict / empty-`{}` shape.
- **Why decide now (not defer):** the user called it explicitly; the ambiguity is a real
  upstream-failure-masking hazard worth removing before any consumer is built against the shape.
- **One-way-door note:** this is the step's output contract. M4b's `triage`/consumers read
  `envelope["results"]`. Not a divergence-ledger entry (orchestration contract, not an
  algorithm change licensed by ground truth — the ledger forbids unlicensed entries; §2/§5).
- **Revisit:** only if a consumer needs a different shape (M4b).

## BR-006 — Bodoni-scan OCR garbles living in the cross-title language plugin
- **Opened:** 2026-06-22 (M3; book-vs-language audit the user requested after BR-004).
- **Context:** beyond the title (BR-004), `ItalianLanguagePlugin` still holds data that is *not*
  Italian-language fact but **PLL's specific Bodoni-scan OCR damage**:
  `ORDINAL_FIXES` (`"dccimoscttimo"→"decimosettimo"`, `"qyinto"→"quinto"`, …), `WORD_FIXES`, the
  garble entries baked into `_ITALIAN_NUMBERS` (`"O^indiccsimo": "Eleven"`, …), and the
  `[GC][a-z]*pitolo` OCR tolerance in `_HEADING_RE`. These are the *scan-noise* analog of the
  title: inert (not wrong) for another Italian book, but they'd accumulate per-book garbles in the
  shared Italian layer. Their natural relative is the `source_noise`/`bodoni_didone` profile (which
  already holds Bodoni fixes like `cbe→che`). This placement was a **deliberate** plan decision
  ("observed-scan data the plugin owns… routes all four ordinal tables here"), not an oversight.
  *(Adjacent, separate axis: `bodoni_didone.json`'s `substitution_rules` are themselves
  Italian-word-specific — that profile is "Bodoni ∩ Italian," not pure typeface. Noted, not this
  entry's subject.)*
- **Taken now:** leave them in the plugin, faithful to the plan's routing; inert for PLL and any
  non-matching book.
- **Not taken:** design the `source_noise`↔plugin seam and move the garble tables out now.
- **Why defer (information, not effort):** unlike the title (a one-line check with an obvious
  manifest home, *actively wrong* for other books), these are **entangled with `parse_chapter_number`'s
  logic** and some map garble→English directly. The clean seam — does `source_noise` grow an
  ordinal-garble map? does the plugin take a garble dict keyed by the source-noise profile? — is
  genuinely unclear, and designing it against *only* PLL's garbles is the single-fixture blind spot.
  A second Italian (esp. same-typeface) book supplies the concrete second garble set to design the
  seam against.
- **Revisit:** when a second Italian/same-typeface book is added, or at M7 extraction (which claims
  portability). Pairs with BR-004 (book-identity lift, done) and BR-002 (non-Italian fixture).
- **Re-read at M4b cleanup (2026-06-23) — re-deferred, unchanged:** `ENGINE_M4_PLAN.md` expected
  cleanup to *consume* these ordinal garbles; reading both confirms it **does not** (they feed
  `parse_chapter_number` in reconcile, ported M3, and `title_to_english` in translate, M4c — never
  cleanup). cleanup consumes a *different* table, `source_noise.substitution_rules` (BR-007's
  subject). So M4b is not BR-006's consumer; disposition unchanged. M4c re-reads it as translate's
  title path is a real consumer.

## BR-007 — source_noise: literal word-fixes vs. a layered character-confusion model
- **Opened:** 2026-06-22 (M3; `source_noise` audit extending BR-006, user discussion).
- **Context:** `bodoni_didone.json`'s `substitution_rules` are literal `garble → word` pairs
  (`eolla→colla`, `cbe→che`, `5AN→SAN`, `piii→più`) that **bake together two independent facts**:
  a typeface *character confusion* (`c↔e`, `h↔b`, `S↔5`, `u/n→ii`) and a specific *Italian target
  word*. So the profile is really "Bodoni ∩ Italian ∩ observed-scan", not pure typeface.
  `boundary_substitutions` (`{i:[r,e]}`) is the clean char-confusion form — applied generatively
  and dictionary-validated by cleanup.
- **Two paths weighed:** (1) keep literal substitution rules per profile (status quo); (2) factor
  substitutions and elevate ones that recur across typefaces into a shared/general layer.
- **Taken now:** Path 1. Treat `substitution_rules` as observed literal word-fixes — the same
  family as BR-006's ordinal garbles (specific, per profile).
- **Not taken:** Path 2 — a layered {general OCR-universal + per-typeface} character-confusion
  model.
- **Why defer (information, not effort):**
  - The entangled thing (the *literal pairs*) is a **product** of typeface × word × scan; a
    different face garbles differently, so literal pairs rarely recur across typefaces — elevating
    them yields a near-empty "general" section = overhead (the user's own suspicion).
  - The genuinely elevatable unit is the **character confusion**, not the word-pair (the cases
    that do recur, e.g. `5↔S`, recur *because* they are char confusions). That is a different,
    currently tiny surface (`boundary_substitutions` is one rule today).
  - You cannot tell which confusions are "universal" vs. Bodoni-specific from a single typeface —
    the same single-fixture blind spot as BR-006.
  - The generative machinery that makes a confusion model pay off (apply confusions → validate
    against the period dictionary) lives in **cleanup (M4b)**; elevating the model before its
    consumer exists is schema-without-a-consumer.
- **Sharper seam recorded:** "per-typeface" is itself imprecise — `substitution_rules` are
  *language-bound* (a German book in Bodoni couldn't reuse them as-is). The real seam is
  **char-confusion (language-neutral, layerable)** vs. **literal word-fix (language-bound,
  specific)**, *not* per-typeface vs. cross-typeface. Cut that seam when a 2nd typeface and/or 2nd
  language exists to design against.
- **Revisit:** when a 2nd typeface and/or language is added, and/or during M4b cleanup (where the
  confusion→dictionary mechanism lives). Pairs with BR-002 (non-Italian fixture) and BR-006
  (scan-noise homing).
- **Sharpened at M4b cleanup (2026-06-23) — placement done, layering still deferred:** cleanup is the
  consumer BR-007 named, and now visibly applies **both** kinds, already config-resident in
  `bodoni_didone.json` — `boundary_substitutions` + the new `ligature_substitutions` (the clean
  char-confusion forms, generative + dictionary-validated) and `substitution_rules` (literal
  word-fixes). So the **placement** worry is resolved: cleanup reads them from `cfg.source_noise`,
  nothing baked. M4b also relocated the remaining source-noise literals (`£→E` →
  `char_substitutions`; the noise-line regexes → `noise_line_patterns`; the page-marker class →
  `page_marker_line_pattern`; the inline markers → `inline_page_marker_patterns`). What stays open is
  only the **layering** (factor a typeface-neutral char-confusion layer from the per-typeface
  literals) — re-deferred, needs a 2nd typeface/language to tell "universal" from "Bodoni-specific".

## BR-008 — prompt-context contract: the book-identity vs. language-fact boundary (one-way door)
- **Opened:** 2026-06-22 (M4 planning; decided with the user, `ENGINE_M4_PLAN.md` D2).
- **Context:** M1 left `manifest.prompt_context` a free dict ("keys defined by the M4 prompt
  templates"). M4a's OCR template is the **first consumer** → it fixes the first keys and the
  render-context contract every later prompt (triage / cleanup / translate / refine /
  multi-eval / synthesis / provenance) inherits. The live `OCR_PROMPT` (`ocr.py:27-38`)
  **hardcodes — as literal text, not interpolated —** a *mix* of book facts (title, author, year) and
  language facts (the language name "Italian"; the accent inventory `à è ì ò ù é`) in one flat blob; the seeded PLL
  `prompt_context` likewise carries `language_name` beside book identity — a latent redundancy
  (`language_name` is already implied by `language_id`) and a blurred layer boundary.
- **Taken now:** a clean **two-layer, namespaced** boundary (three layers counting the
  book/language-neutral engine template itself):
  - `manifest.prompt_context` = **book-identity facts only** (`book_title`, `author`, `year`,
    `subject`, `entities`) → `{{ book.* }}`;
  - the **language profile** = cross-title **language facts** (a human-readable display name; the
    accent inventory) → `{{ language.* }}`;
  - render context = the namespaced merge; the template *files* are book-neutral and
    profile-resident (`engine/profiles/prompts/`), rendered by the engine-owned Jinja2 machinery
    (`src/engine/prompts/templating.py`) with **`StrictUndefined`** (a missing key is a hard error,
    not silent empty).
  Mirrors **BR-004** (which lifted the book *title* out of the language plugin): book facts in the
  book layer, language facts in the language layer.
- **Not taken:** keep `prompt_context` as the live flat blob (`language_name` beside book identity)
  — faithful, but redundant, boundary-blurred, and it would let a language fact vary per book.
- **Schema implications (executed at M4a porting; the field-level choices are two-way doors):**
  drop `language_name` from `prompt_context`; add a language **display name** to the
  `LanguageProfile` schema (the profile has `language_id` but no human-readable name today); the
  prompt accent inventory is **single-sourced from the profile** (likely the lowercase run of
  `word_score_accents`, or a dedicated prompt-facing field — decided at porting). The *boundary* is
  the one-way door; the field names are not.
- **Why decide now (not defer):** the OCR template is the first consumer and freezes the
  render-context contract every later prompt reads (the M4b/M4c prompts triage/cleanup/translate/refine
  plus M5's multi-eval/synthesis/provenance); deciding the boundary before they bind to a blurred one
  is the point of maximum leverage. The user called it.
- **Resolved at M4a porting (2026-06-22):** the two-way-door field choices landed as —
  `prompt_context` dropped `language_name`; `LanguageProfile` gained `display_name` (`"Italian"`)
  **and a dedicated `accent_inventory` list** (`["à","è","ì","ò","ù","é"]`), *not* a derived lowercase
  run of `word_score_accents` (which mixes case and serves the OCR scorer) — a dedicated prompt-facing
  field reproduces the live prompt's accent list exactly and keeps the three accent sets purpose-named.
  Render context is the namespaced `{{ book.* }}`/`{{ language.* }}` merge (`prompts.templating.build_prompt_context`);
  templates live at `profiles/prompts/*.txt.j2`, rendered by `prompts/templating.py` under
  `StrictUndefined`. The rendered PLL OCR prompt is **byte-identical to the live `OCR_PROMPT`**
  (`test_ocr_engine::test_render_ocr_prompt_is_faithful_to_live_for_pll`).
- **Separability proof — realized as decided (M4a):** the decided tier stands unchanged — a
  **single** render of the synthetic book's *own loaded context* asserting **no PLL string leaks at
  all**, book identity *and* language facts (the name `Italian`, the accent list `à è ì ò ù é`). For
  the language-fact half to bite while the synthetic book keeps the Italian *plugin* (required — only
  `it` is registered, BR-002), the synthetic manifest **overrides** its prompt-facing language facts
  (`display_name` → `"Sintetico"`, `accent_inventory` → `["ñ","ç","ø"]`) via the existing
  shallow-replace override mechanism; `language_id` stays `it`, so reconcile/validate's Italian
  word-scoring is untouched. `test_templating.py::test_no_pll_string_leaks_under_synthetic_render`
  renders that context and asserts every PLL/Italian string is absent and the synthetic identity +
  facts present. *(Correction: an earlier port build left the synthetic facts Italian, hit the wall
  that the accent list then legitimately appears, and "fixed" it by splitting the tier into two and
  declaring the accent list "not a leak" — a measurement change, not the decided design. Reverted:
  the fixture, not the test, was the thing to fix.)*
- **Follow-up (2026-06-23, post-M4a audit):** the manifest schema now **pins** the prompt-context
  keys the OCR template actually consumes — `prompt_context` gained `required: [book_title, author,
  year]` — so a forgotten key fails at config-**load** with a clean `ConfigError`, not a late
  `jinja2.UndefinedError` at render (which escaped the F7 CLI exception taxonomy as a raw traceback).
  `prompt_context` stays **extensible**: keys are pinned incrementally *as each later prompt becomes
  their consumer*; `subject`/`entities` are carried now and pinned when triage/translate (M4b/M4c)
  bind them. This ratifies in the schema what `StrictUndefined` already enforced at render
  (`test_config_loader.py::test_prompt_context_requires_the_ocr_template_keys`).
- **Revisit:** only if a later prompt needs a fact that fits neither layer (e.g. a scan /
  source-noise fact) — extend the namespaced context with a *third* source rather than collapsing
  the boundary.

## BR-009 — M4a acquisition backend seams: purpose-built minimal seams vs. unified `providers.py`
- **Opened:** 2026-06-22 (M4 planning; decided with the user, `ENGINE_M4_PLAN.md` D1). *(Numbering
  follows that plan's reservation: BR-008 prompt-context contract is above; BR-010 OCR model-id
  home and BR-011 triage taxonomy to follow at porting.)*
- **Context:** M4a's `download` and `ocr` cross three external boundaries that must be injectable for
  offline property/separability tests — HTTP fetch (`download`), PDF page render (`ocr`, PyMuPDF),
  and the vision-OCR model call (`ocr`, Gemini). M5 separately plans a unified `providers.py`
  *TranslationProvider* abstraction. Fork: build the unified provider now and route OCR through it,
  or stand up minimal purpose-built seams.
- **Taken now:** three minimal injectable seams in M4a — `Fetcher.fetch(url)→str`,
  `PageRenderer.render(pdf,page,*,dpi)→bytes`, `OcrBackend.transcribe(image,prompt)→str` — each
  defaulting to the real backend (requests / fitz / Gemini) and injected via
  `run(*, ws, cfg, lang, fetcher=None, renderer=None, backend=None, **opts)`. `providers.py` is left
  a stub. Mirrors M3's injected `DictionaryOracle` (BR-001).
- **Not taken:** pull `providers.py` (M5) forward and express OCR through it.
- **Why decide now (not defer):** the user called it, and the alternative is *actively worse*, not
  merely premature — `providers.py` is the **translation** (text→text) provider family, while these
  are **acquisition** operations (image→text vision; pure IO with no model). Designing the unifying
  translation abstraction against OCR-only is the single-fixture blind spot. The seams are **siblings
  of `providers.py`, not a premature version of it** — they never converge, so "minimal now" is not
  throwaway work.
- **Two-way door:** a seam signature behind a step function is cheap to change (§4) — no config
  schema, no locked-in consumer. If multi-model OCR later wants a different shape, change it then.
- **Scope split (M4a vs. M4c):** the *acquisition* seams are M4a (this entry, resolved). The distinct
  question — whether M4b/M4c's **chat** calls (triage / cleanup-LLM / translate / refine, all
  text→text) should share the seam `providers.py` generalizes — is the real `providers.py`-prefiguring
  decision and is **deferred to M4c's formal development**, not settled here.
- **Resolved at M4a porting (2026-06-22):** shipped as specified — `download.Fetcher` (default
  `RequestsFetcher`), `ocr.PageRenderer` (default `FitzPageRenderer`: `page_count` + `render`→JPEG)
  and `ocr.OcrBackend` (default `GeminiOcrBackend`, model id from `manifest.ocr.models`), each a
  `typing.Protocol` co-located with its step and injected via `run(*, …, fetcher/renderer/backend=None)`.
  `providers.py` untouched. The page identity is threaded renderer→backend through the rendered bytes
  (fakes encode/decode the page number), so canned responses are order- and resume-independent. All of
  property/separability/isolation run offline against injected doubles seeded from the frozen synthetic
  `inputs/`; one `integration`-marked test exercises the real PyMuPDF render path.
- **Revisit:** M4c (chat-seam ↔ `providers.py` relationship); M5 (the unified provider family
  itself). The acquisition seams themselves revisit only if a backend's modality changes.

## BR-010 — OCR model ids: per-book manifest block vs. baked code default (one-way door)
- **Opened:** 2026-06-22 (M4 planning; decided with the user, `ENGINE_M4_PLAN.md` D3).
- **Context:** live `ocr.py:22-25` bakes frontier ids (`gemini-2.5-flash`,
  `gemini-3.1-pro-preview`) as a code constant. The framework risk note forbids shipping frontier
  ids as stable engine defaults, and model ids rot on a regular cadence as new models ship (user).
- **Taken now:** a per-book **`manifest` `ocr` block** carrying the model ids (flash/pro roles → ids)
  and related acquisition details, explicit, with **no engine default** — and giving provenance
  (which model produced `copy3`).
- **Not taken:** (b) a CLI-only flag with no default (loses the recorded provenance); (c) keep the
  ids as a code constant (bakes a frontier id — violates the risk note and the no-baked-default
  principle).
- **One-way door:** config-schema shape (manifest gains an `ocr` block → schema + loader + models).
- **Why decide now (not defer):** the user called it; model-id rot is a standing concern, not
  something a second book clarifies.
- **Resolved at M4a porting (2026-06-22):** the block shipped as **`{"models": {"flash", "pro"}}`
  only** — `dpi` / JPEG quality stay code defaults (`ocr._DEFAULT_DPI` / `_JPEG_QUALITY`), and there is
  **no `prompt_ref`** (the OCR template is profile-resident at a fixed path) — each omitted per YAGNI
  until a book needs it. Schema-**required** (consistent with the sibling `scan` block); modelled as
  `OcrConfig(models: dict)` (role → id); both PLL and synthetic declare it. The role drives the output
  name (`pro`→`copy3_raw.txt`, `flash`→`copy3_flash.txt`) and is the provenance of which model produced
  `copy3`.
- **Revisit:** if a book needs per-book `dpi`/quality or a structurally different prompt, promote those
  into the block then (additive, two-way). The *existence* of the per-book model-id block is settled.

## BR-011 — triage disagreement taxonomy: general code-default, not a deferred-language item
- **Opened:** 2026-06-22 (M4 planning; decided with the user, `ENGINE_M4_PLAN.md` D5). Executed at
  M4b porting.
- **Context:** live `triage.py` classifies OCR-witness disagreements via a `classify_disagreement`
  tool whose `category` enum is `{ocr_confusion, ocr_corruption, punctuation_artifact,
  alignment_drift, missing_text, archaic_spelling, unknown}`, inside a `TRIAGE_SYSTEM` prompt that
  *also* carries Italian/Bodoni example patterns and physical-witness descriptions.
- **Taken now — decompose by actual nature, not by surface appearance:**
  - **category enum + tool schema → code default**, because the labels are a *general*
    OCR-disagreement taxonomy (none is Italian; `archaic_spelling` is era-general). Settled general
    engine logic.
  - **OCR example patterns → config** via the prompt template (`source_noise` char-confusions +
    language accento), the BR-008 machinery.
  - **witness descriptions → `manifest.sources[].label`** (already present) + the ocr-produced
    `copy3` role.
- **Not taken:** lift the enum to `LanguageProfile`/manifest now — rejected: it is **not language
  data**; configuring it would be speculative generality (engine-agnostic / let-the-fixture-pull-it).
- **Correction recorded (own framing):** the original plan called this the *"Italian-OCR category
  enum"* and treated the code default as a 2nd-language deferral (single-fixture blind spot). On
  reading the seven members they are language-neutral → reframed to **"code-default because
  general."** The labels are general; whether these exact seven are the *universal* set or merely
  PLL's is the lone residual generalization question.
- **Revisit:** only if a real second book needs **different categories** (a genuine "second book
  forced it") — **not** an expected language deferral, and distinct from BR-002 (a non-Italian *test
  fixture*, not this taxonomy).

## BR-012 — engine regen-guard for destructive steps: owed at M4b/M4c, not M4a
- **Opened:** 2026-06-22 (M4 planning; `ENGINE_M4_PLAN.md` D6 follow-up, user-raised).
- **Context:** the live pipeline guards `cleanup`/`translate`/`all` behind an interactive
  `regenerate <step>` TTY prompt + a `.claude` deny-list + a `PER_LA_LIBERTA_ALLOW_REGEN` escape,
  because they overwrite committed, hand-tuned, non-reproducible text. D6 settled that M4a's
  `download`/`ocr` need **no** such guard: their outputs (`copy*`) are reproducible acquisition, not
  hand-tuned, and the `BookWorkspace` sandbox already makes a stray run harmless to the live tree and
  the frozen `inputs/`.
- **The catch (user):** the sandbox protects the live tree and `inputs/`, but **not hand-tuned /
  expensive artifacts *within* `work/`**. `cleanup` (`work/output/italian_clean.md` — hand-edited in
  the deviation-review workflow) and `translate`/`refine` (`work/state/translations/` — the
  irreproducible synthesis + refinements) **are** destructive to re-run even inside the sandbox — the
  same hazard the live guard addresses.
- **Taken now:** **no guard in M4a** (acquisition is non-destructive). The destructive-step guard is
  **owed at M4b (cleanup) and M4c (translate/refine)**, designed there against the concrete
  protectable surface.
- **Not taken:** design the guard seam now (M4a). Rejected as speculative — M4a has nothing to
  protect, and M4b/M4c's exact hand-tuned/expensive surface isn't known yet. The guard is an
  **additive top-of-run check** (a step refuses to overwrite existing protectable output in `work/`
  without an explicit override) — a **two-way door** that forecloses nothing and is cheap to add when
  its consumer is concrete.
- **Mechanism note (for M4b/M4c, not decided now):** the engine's guard is **workspace-internal**
  (detect protectable output in `work/` → refuse without an explicit override). This **revises** the
  framework plan's earlier guard sketch (lines 216-220: a per-book `ENGINE_ALLOW_REGEN` env escape +
  `.claude` deny entries) — the detection-based refusal is the settled core, **not** a copy of the
  live TTY / deny-list / `PER_LA_LIBERTA_ALLOW_REGEN` construct (a live-tree + Claude-settings
  mechanism). The two reconcile: the "explicit override" can *be* `ENGINE_ALLOW_REGEN`, so the open
  M4b decision is the **override's form** (env flag? deny entries? both?), not whether detection-based
  refusal is the mechanism.
- **Revisit:** M4b (cleanup) and M4c (translate/refine) — each decides its guard before its first run
  that can overwrite expensive/hand-tuned output. Pairs with the live regen-guard rationale (CLAUDE.md).
- **Resolved at M4b cleanup (2026-06-23) — M4b-D2 (b):** detection-based refusal, as the mechanism
  note settled. `cleanup.run` checks `ws.output/clean.md` at top-of-run (before any model load); if it
  exists and the override is absent → `RegenerationGuardError` (new `EngineError`, exit code 6, message
  naming the escape). **Override form = `allow_regen` kwarg + global `ENGINE_ALLOW_REGEN=1` env, no CLI
  flag** — the env mirrors the live `PER_LA_LIBERTA_ALLOW_REGEN`; a CLI flag's only value over the env
  is typing convenience (future-need-only, YAGNI) and discoverability is handled by the error message.
  Negative + positive controls in `test_cleanup_engine` (`_check_regen_guard` + a `run`-level refusal).
  Reused unchanged by `cleanup`'s LLM path and, at M4c, by `translate`/`refine`.

## BR-013 — `inputs/` fixture lifecycle: the frozen-fixture vs. engine-producible shadow
- **Opened:** 2026-06-22 (M4 planning; `ENGINE_M4_PLAN.md` D7 follow-up, user-raised).
- **Context:** D7(b) adds `books/<id>/scans/` for the raw PDF, distinct from `books/<id>/inputs/`
  (frozen golden fixtures). That sharpened a parallel/shadow concern: as step *producers* get ported
  (M4a `download`/`ocr`; M3 `reconcile`; M4b `cleanup`), the engine can itself produce artifacts that
  `inputs/` also holds frozen — risking duplication/divergence and source-of-truth ambiguity. **Not
  hypothetical:** as of M3, `validate`'s golden already reads a *frozen* `inputs/reconciled_chapters.json`
  that engine-`reconcile` can now produce.
- **Key distinction — not all of `inputs/` is shadow-risky:**
  - **non-deterministic-step outputs** (`copy{1,2,3}` + page maps) — the *irreducible* deterministic
    test-entry point; a test can never regenerate them (network/LLM). **Permanent; never removed.**
  - **deterministic-step outputs** (`reconciled_chapters`, `clean`-detcore, `chapter_pages`) — the
    engine can reproduce them → the **shadow-risky subset**.
  - **F1 wrinkle:** some frozen deterministic outputs are *hand-edited* (`validate`'s frozen
    `reconciled_chapters.json` is 2 lines off pristine engine output, M3 F1) — intentionally distinct,
    so chaining would *lose* the edits and a naive drift-check would flag them.
- **Taken now (principle):** `inputs/` is the permanent deterministic-test-input layer and is **not**
  removed wholesale. The shadow-risky subset is resolved **per deterministic producer as it is
  ported**, default **keep + drift-guard** (a consistency test pinning frozen == engine-produced for
  unedited cases; hand-edited F1 fixtures carry a logged "diverges by intent" note instead),
  **retire-via-chaining** only where a fixture is purely mechanical and isolation isn't worth the
  upkeep.
- **Hard forcing function — M7 (extraction).** The subtree-split clone must build + pass tests
  **self-contained**, and the framework plan's current mitigation ("refresh `inputs/` from live")
  **dies at extraction** (no parent/live tree to refresh from). So by M7 the fixture graph must be
  coherent, minimal, and non-shadowed; **the shadow cannot survive M7.**
- **Not taken:** remove/disable `inputs/` now (breaks every golden — the non-det entry points are
  irreducible); or defer the whole question blind to M7 (risks discovering a shadow mess at the worst
  time).
- **Revisit:** per deterministic producer as ported — the first concrete case is `validate`'s frozen
  `reconciled` (evaluable now; F1 hand-edits make it non-trivial), then M4b `cleanup`'s outputs;
  **final coherence enforced at M7.** Pairs with the framework plan's "Duplication/divergence" risk
  and `port_discipline.md` §5 "Input refresh."
- **M4b cleanup (2026-06-23) — no new frozen fixture; reuses validate's:** cleanup's detcore golden
  isolates `clean_text` **per chapter** (`cleanup_detcore_expected.json` under `tests/golden/data/`,
  not `inputs/`), reading the **same** frozen `inputs/reconciled_chapters.json` the validate golden
  froze (read, never re-frozen — both goldens stay pinned to one input). So M4b adds **no** new
  shadow-risky `inputs/` fixture: the golden output lives in `tests/golden/data/` (a fixture, not a
  step-input), and `chapter_pages.json` is deliberately not frozen (the golden tests the algorithm,
  not the config-driven wrapper). The wrapper is property-tested on the synthetic book instead.

## BR-014 — M4b chat seam: minimal per-step injectable `Chat` vs. the unified `providers.py`
- **Opened:** 2026-06-23 (M4b porting; the M4b sibling of BR-009's deferred half).
- **Context:** triage and cleanup-LLM each cross a text→text model boundary that must be injectable
  for offline property/separability tests. M5 separately plans a unified `providers.py`
  *TranslationProvider*. BR-009 settled the **acquisition** seams (M4a) but explicitly left open
  whether the **chat** calls (triage / cleanup-LLM / translate / refine) should share the abstraction
  `providers.py` will generalize — deferring that to M4c "with all the chat consumers in front of it".
- **Taken now:** a **minimal per-step `Chat` seam** for each — `triage.Chat.classify(*, system, tool,
  user) → list[dict]` (tool-use classification) and `cleanup.Chat.correct(*, system, user) → str`
  (single-model correction) — each a `typing.Protocol` co-located with its step, defaulting to the
  real Anthropic client (`AnthropicChat`), injected via `run(*, …, chat=None)`. Mirrors M4a's
  acquisition seams (BR-009) and M3's `DictionaryOracle` (BR-001). cleanup's Batch-API path stays
  default-only (anthropic-direct), with its deterministic request-building (`build_batch_requests`)
  property-tested.
- **Not taken:** pull `providers.py` (M5) forward and route triage/cleanup chat through it now.
- **Why decide now (not defer):** the seam is needed *this milestone* (offline tests), and standing
  up the unifying translation abstraction against only triage+cleanup — before translate/refine are
  in front of it — is the single-fixture blind spot. Two small per-step seams now is the same
  "siblings, not a premature unification" logic M4a used; they are cheap two-way doors.
- **Revisit:** **M4c** decides whether triage/cleanup/translate/refine share one `ChatBackend` that
  M5's `providers.py` generalizes (BR-009's open half). Until then each step owns its minimal seam.

## BR-021 — document-structure is an under-abstracted axis: engine direction = position-based chapter identity (one-way door)
- **Opened:** 2026-06-23 (M4c pre-port coverage audit + design discussion with the user). *(Numbering:
  BR-015–020 are reserved by `ENGINE_M4c_PLAN.md` §9 for M4c's porting entries; this is a
  framework-level decision opened ahead of them, so it takes 021.)*
- **Context:** **language** got a clean engine abstraction (`LanguagePlugin`) and **typeface** a clean
  profile, but **document structure did not.** The part→chapter→paragraph model and "a chapter's
  identity is its printed ordinal" ride in as an un-examined default, smeared across three homes: the
  language plugin (`is_chapter_heading`, `structural_part`, the ordinal tables — *entangling structure
  with language*), the manifest (`structure.h3_count`, `structure.parts`), and a baked markdown
  convention (`##`=part, `###`=chapter). The M4c audit's F-A/F-B/F-C are leaks from this single gap:
  the same chapter is encoded ≥4 ways — printed-ordinal int (`parse_chapter_number`/`ORDINALS`),
  positional counter (`chapter_identities.number`), lexical title-slug (`parse_md`), and a separate
  English-word table (`title_to_english`/`_ITALIAN_NUMBERS`) — kept in sync by hand, with persistence
  keyed on the **most fragile** encoding (the lexical slug). The robust ordinal resolver sits unused
  beside the brittle one; two code paths even derive the *same* `short` id two different ways
  (positional counter in `chapter_identities` vs. parsed ordinal in `split_raw_chapters`), never
  cross-checked.
- **Taken now (direction):** chapter identity = **position in its container** (`p{part}_ch{NN}`), with
  the printed ordinal **demoted to a display projection** — the source-language title stays verbatim
  source, the English title is *formatted* from the resolved integer by a total function (no per-form
  lookup table). Position-in-container is the more universal primitive: it survives named, dated, or
  non-ordinal divisions where ordinal-identity does not. This is the through-line behind the
  M4c-plan consequences **BR-019** (stable persistence id) and **BR-020** (single ordinal model); they
  are *downstream* of this entry.
- **Not taken — and deliberately:** (a) keep the status quo (≥4 hand-synced encodings keyed on the
  fragile slug); (b) **design a universal document model now** — rejected as the mirror trap
  (speculative generality with one real book; the port plan forbids claiming generality without a
  second book). We do **not** factor structure into its own plugin/profile axis yet, nor fix a
  containment depth or an identity scheme beyond what PLL needs.
- **Why decide the *direction* now (not defer):** the audit surfaced the gap concretely and M4c is
  about to harden an id contract (the `state/translations/` key + the sidecar keys). Choosing
  position-based identity *before* the engine binds to the slug is the point of maximum leverage and
  **zero migration cost** (the engine is a fresh build). Deferring the *extent* (does structure become
  its own axis?) is information-not-effort: only a structurally-different second book tells us which
  pieces are PLL-specific.
- **Discipline note (the trap this guards):** for **model** decisions — distinct from the equivalence
  regression net — the live PLL is **one data point, not the spec.** The faithfulness tier proves "we
  didn't change behavior," never "the behavior is right." This entry exists so the part/chapter/ordinal
  model is a **named, revisitable** choice rather than an immutable default that rode in on the port
  (`port_discipline.md` §1: equivalence is the net, not the definition of done).
- **Revisit / validate when:** the first structurally-different book is in hand. **Near-term validation
  step (before M4c hardens the id contract):** pressure-test the part/chapter/position model against a
  real second structure — **Athanor's Kybalion** (a real second corpus whose *actual* structure the
  test reads; it is *expected* — not yet verified this session — to break the ordinal-identity
  assumption, e.g. named rather than ordinal-numbered divisions) — to learn which pieces are
  PLL-specific and whether *structure* must become its own plugin axis. Pairs with
  BR-004 (book title lifted out of the plugin — precedent for structure facts leaking in, extracted
  case-by-case), BR-006 (ordinal garbles entangled in the plugin), BR-002 (generalization unproven
  with one fixture). Children: BR-019, BR-020.

## BR-022 — `rebind_anchors.region` coordinate space + witness discriminator: locked to "shares atom-Geom's space", concrete space deferred to S5 planning

- **Date / owner:** 2026-07-02, S4 keystone close (B-7 dispositions, user-ratified).
- **Context:** S4.4 froze the region shape as a plain nullable `{page, bbox_region}` (D-S4-H:
  no `present` flag, no atom-`Geom` sub-object). The S4 build surfaced that the plan never says
  *which* coordinate space those values live in — page-image pixels vs PDF points, and which
  page numbering (the live PLL tree needs a `SCAN_LEAF_OFFSET=6` to reconcile scan leaves with
  printed pages; only copy3 carries a page map at all — canonical atoms are `PAGE_UNMAPPED`
  until S7.1b). S5.1's re-bind is exactly the consumer that must compare a stored region against
  `Atom.geom`.
- **Decision (the lock):** region is DEFINED to share the atom-level `Geom`'s coordinate space —
  whatever space S2.1's matcher pins for `atom.geom` is region's space, one convention, never
  two. Normative sentence lives in the schema's `rebind_anchors` description, pinned by
  `test_structure_map.py::test_region_description_pins_the_shared_coordinate_space_contract`.
  This is the property S5 needs (region ↔ atom-box comparability) without prematurely choosing
  the space itself.
- **Deferred (the open fork):** (a) the concrete space definition (falls out of S2.1's as-built
  backend — PyMuPDF/Tesseract page raster coordinates are the expected shape, decided there, not
  here); (b) whether region needs a witness and/or space discriminator field (a two-witness
  re-bind may need to know WHOSE scan the bbox indexes).
- **Cost if reopened:** adding any field to region is a Node-schema change → structure-map
  schema-version bump → the version re-enters `provisional` (s4_plan §1.2.2) → the D18 birth
  gate re-runs on the differ fixture. Known, accepted, and cheap while the only committed maps
  are fixtures — the reason to decide at S5 planning and not after S4.6's hand-authored PLL map
  exists.
- **Revisit condition:** S5 planning (mandatory agenda item), informed by S2.1's as-built
  coordinate output. If S4.6 authoring starts before S5 planning settles this, authored maps
  must leave `rebind_anchors` absent (it is optional, O4) rather than guess a space.
