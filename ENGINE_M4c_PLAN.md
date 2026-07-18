# Engine M4c Plan — Translation / Refinement (`translate` + `refine`)

> Standalone review artifact and development bible for the M4c port. Audit inline with
> `@@@@@@` blocks; I'll answer each with a paired `======` (code-verified, per point)
> before porting anything. File:line anchors into the **live** tree (`translate.py`,
> `refine.py`) and the **engine** plugin (`lang/base.py`, `lang/italian.py`) are read
> directly this session; engine anchors into `cli.py`/`errors.py`/`templating.py`/the
> decision docs are reconnaissance from the M4b landing (re-confirmed before each edit).
>
> Scope is **single-model `translate` + `refine` only.** `multi_translate.py`
> (multi-witness drafts → eval → Opus-CLI synthesis) and `providers.py` are **M5** and are
> explicitly out of scope here — see §1. Discipline is *applied*, not re-argued; canonical
> statement is `engine/docs/port_discipline.md`.

---

## 1. Scope

M4c ports the **default single-model translation path** and its post-hoc refinement:

- **`translate`** (`translate.py:139`) — reads `output/italian_clean.md`, splits into chapters,
  translates each via Anthropic with extended thinking and a `ThreadPoolExecutor`, and writes
  `state/translations/{id}.md`, `state/translation_progress.json`,
  `output/english_translation.md`, and `output/source_pages.json`.
- **`refine`** (`refine.py:241`) + **`revert_to_version`** (`refine.py:351`) — post-hoc Edgren-1901
  review of existing translations, emitting targeted `<change>`-tagged revisions with full
  snapshot/version tracking under `state/translation_revisions/`.

**Out of scope (M5):** `multi_translate.py` in its entirety — multi-provider drafting via
`providers.create_provider`, the six-dimension scored evaluation, the `claude`-CLI Opus synthesis
subprocess (`multi_translate._run_claude_code`), `provenance.json`, `synthesis_integrity.json`, the
`state/multi_drafts/` tree, and `state/multi_translate_progress.json`. The dependency arrow is
one-way: `translate.py` imports **nothing** from `multi_translate.py`/`providers.py`; only
`multi_translate.py` imports *from* `translate` (`SYSTEM_PROMPT`, `assemble_translation`,
`parse_italian_markdown` — `multi_translate.py:30`). So the single-model path lifts cleanly. The
forward-coupling obligation is recorded in §9 (BR-017): M4c must design translate's reusable surface
to serve the M5 multi_translate port.

**Reuse, do not re-port (the M1 dividend).** The hardest refactor — the three chapter-id
namespaces — was already done in M1. `ItalianLanguagePlugin` exposes:
- `chapter_identities(markdown, *, page_ranges, skip_titles)` → `list[ChapterIdentity]` with
  `short` / `parse_md` / `html_slug` / `english_title` / `part` / `number` / `title` / `page_range`,
  and its docstring states it *"Mirrors `translate.parse_italian_markdown`"* (`lang/base.py:107-173`).
- `title_to_english(title)` — a verbatim port of `translate._italian_to_english_title`
  (`lang/italian.py:147-173`, with the `_ITALIAN_NUMBERS`/`_TEENS`/compound tables at 96-137).
- `structural_part(title)` — the `Parte Prima/Seconda` → `(short, num, canonical)` map
  (`lang/italian.py:144-145`).

So M4c's `translate` **must not** re-implement `parse_italian_markdown` (`translate.py:10-62`) or
`_italian_to_english_title` (`translate.py:322-361`). It consumes the plugin. The **one gap**:
`chapter_identities` derives identities but not chapter **body text**; the live
`parse_italian_markdown` returns both. Bridging that gap is the central translate-port design point
(§4 F1, §5, §15-D1).

---

## 2. Branch-register read-obligation dispositions

Per `port_discipline.md §5`, M4c consults the register for entries whose revisit condition it now
satisfies.

- **BR-006 — Bodoni-scan ordinal garbles in the Italian plugin** (revisit "at M4b/M4c when a
  consumer appears"). M4c's title path **is** a consumer: `title_to_english` reads the garble
  entries in `_ITALIAN_NUMBERS` (`lang/italian.py:106-109`: `O^indiccsimo`, `Dccimoscttimo`,
  `Dccimottavo`, `Decimonono`) and `parse_chapter_number` reads `ORDINAL_FIXES`/`WORD_FIXES`
  (`lang/italian.py:40-59`). **Disposition: re-read, re-defer** (same as M4b). The garbles are
  inert-not-wrong for a non-garbled book; their cleaner home is `source_noise`, but that move needs a
  second Italian/same-typeface book to design the seam against. No M4c code change.
- **BR-009 — chat-seam ↔ `providers.py`** (open half explicitly deferred to "M4c's formal
  development"). **Disposition: RESOLVE here** — see §3. This is M4c's headline decision.
- **BR-012 — workspace-internal regen-guard** (owed M4b/M4c). **Disposition: apply** the M4b
  mechanism (`RegenerationGuardError` exit 6, `allow_regen` kwarg / `ENGINE_ALLOW_REGEN` env) to
  `translate`. `refine` is **not** guarded — see §4 F8 / §6.
- **BR-013 — `inputs/` fixture lifecycle** (per-producer resolution; M7 hard deadline). **Disposition:
  M4c adds no new `inputs/` fixture.** The synthetic 2-chapter book covers separability; the
  deterministic id/title derivation is already covered by M1's `test_chapterids_golden`. Freezing the
  hand-refined live `state/translations/` as a golden input is deliberately **declined** (heavy,
  irreproducible, and the refined text would pin an equivalence baseline the LLM path can't honor
  anyway — see §11).

---

## 3. BR-009 resolution — the chat-completion seam (headline decision)

**Context.** M4b established the per-step chat-seam pattern: a minimal `Protocol` co-located with the
step, defaulting to the real Anthropic client, injected via `run(..., chat=None)` so the
property/separability/isolation tiers run offline (BR-014). Two seams exist, shaped to their callers:
`triage.Chat.classify(*, system, tool, user) -> list[dict]` (tool-use) and
`cleanup.Chat.correct(*, system, user) -> str` (text). BR-009 left open whether translate/refine join
a unified `ChatBackend` now or keep per-step seams until M5 generalizes `providers.py`.

**Code-verified shape match.** `translate_chapter` (`translate.py:82-136`) and `_refine_chapter`
(`refine.py:205-238`) make the **identical** call shape: `messages.create` with `system` + a single
user message + extended thinking, `model="claude-sonnet-4-6"`, `max_tokens=128000`, wrapped in
`retry_api_call`, returning `(text, stop_reason)`. They differ from cleanup (`-> str`, no stop_reason)
and triage (tool-use). So translate and refine are genuine twins.

**Recommendation (decision D1).** Introduce **one** text-completion seam shared by translate and
refine — not the full `providers.py` unification:

```python
class Completion(Protocol):
    """One extended-thinking text→text call. Returns (text, stop_reason) — the provider-neutral
    surface translate/refine consume. Injectable so property/separability/isolation run offline."""
    def complete(self, *, system: str, user: str, thinking_budget: int | None) -> tuple[str, str]: ...

class AnthropicCompletion:  # default; model is a code default (the live sonnet id);
    ...                     # missing key -> BackendError (exit 5), matching ocr/triage/cleanup
```

- `thinking_budget=None` ⇒ thinking disabled (the `--no-thinking` path, `translate.py:122-123`);
  an int ⇒ enabled with that budget (`translate.py:125-128`). `max_tokens` stays a code default
  (128000) — an internal call detail, not book/scan config.
- **Why shared, not per-step:** the contract is byte-identical between the two callers, so one seam is
  DRY, not premature unification. M4b kept triage/cleanup separate *because their contracts differed*;
  here they don't. And the live tree already couples them (`refine.py:26` imports from `translate`).
- **Why not the full `providers.py` unification:** `providers.py` is the multi-provider abstraction
  (Anthropic + Gemini + GPT) whose only consumer is `multi_translate`. Unifying now would be modelling
  without a consumer (YAGNI). BR-009's "unify at M5" half stays at M5.
- **Home:** the seam is a two-way door (cheap to move). Recommend a small shared module
  `engine/src/engine/steps/_completion.py` (or co-located in `translate.py` with `refine` importing
  it, mirroring the live `refine`→`translate` import). Flagged in §15-D2 for your ruling.

This **resolves BR-009's open half** and opens **BR-015** (the seam's existence + shape).

---

## 4. Findings from pre-port verification

Code-verified facts that shape the port. (`tp:` = `translate.py`, `rf:` = `refine.py`,
`it:` = `lang/italian.py`, `lb:` = `lang/base.py`.)

- **F1 — chapter parsing splits into "identities" (have) + "bodies" (need).** `chapter_identities`
  (`lb:107`) walks `##`/`###` headers, skips `structural_part` and `skip_titles`, and emits identities
  — but **accumulates no body text.** The live `parse_italian_markdown` (`tp:54-55`) accrues the lines
  between headers into `ch["text"]`. M4c must obtain `(identity, body)` pairs without re-implementing
  the header walk. **Resolution (D3):** add a sibling shared mechanic `chapter_segments(markdown, *,
  page_ranges, skip_titles) -> list[ChapterSegment]` on `LanguagePlugin`, where
  `ChapterSegment = (identity: ChapterIdentity, text: str)`; refactor `chapter_identities` to delegate
  to the same internal walk so the two never drift. Body accumulation is language-agnostic, so it
  lives in the shared base, not per-language. The set of segments equals the 58 content units
  (prefazione + 24 + 33) — identical to `parse_italian_markdown`'s effective output, because both skip
  the same structural headers and the same H1 book title (`tp:29-42`).

- **F2 — `SYSTEM_PROMPT` is pure book identity → template.** `tp:65-79` names the book
  (`'Per la Libertà!'`), author (`Cesare Crespi`), interlocutor (`Count Carlo di Rudio`), subject
  (`Italian unification, the Risorgimento, the Orsini conspiracy against Napoleon III`), era
  (`1913` / `early 20th century`), and the preserve-these entities (`'Felice Orsini', 'Mazzini',
  'Radetzky'`). All of it is `{{ book.* }}` from `manifest.prompt_context` (BR-008). The *translation
  guidelines* (faithful/literary, preserve paragraph structure, translate footnotes in place, no
  commentary, keep untranslatable Italian in italics) are book-neutral and stay literal in the
  template. → `profiles/prompts/translate.txt.j2` (§12).

- **F3 — title→English is fully owned by the plugin already.** `it:147-173` is the verbatim port of
  `tp:322-361`. M4c calls `lang.title_to_english(identity.title)` — or just reads
  `identity.english_title`, which `chapter_identities` already computed (`lb:166`). No constant moves.

- **F4 — page-provenance markers are a generic internal protocol → code default.** The literal
  `<!-- pages:N-M -->` is extracted before translation and reinserted after (`tp:231-236, 252-253`;
  refine `rf:296, 305, 328-330`). It is an internal tag protocol (same class as the reconcile
  `PAGE_MARKER`, which M3 made a shared code constant per `ENGINE_M4_PLAN.md` F6), **not**
  book/scan-observable noise → stays a code constant in the engine, not config. The regex is
  language-agnostic.

- **F5 — `assemble_translation` front-matter is book/edition config + one missing field.** `tp:370-381`
  hardcodes `# For Freedom!`, the English subtitle, `**Cesare Crespi** (1913)`, and
  `*Translated from the Italian*`. Mapping: author/year → the `**{author}** ({year})` byline pattern
  M4b already built for `cleanup.render_markdown`; subtitle → `edition.subtitle_en`; `Italian` →
  `cfg.language.display_name`. **Gap:** the English book title `For Freedom!` has **no config home** —
  `Edition` carries `title_it` but no `title_en` (confirmed against `config/models.py`/loader
  `_build_manifest`, `loader.py:108-117`). → add `edition.title_en` (§7, BR-016). Also verify
  `edition.subtitle_en` equals the live assemble subtitle (`*From my conversations… accomplice of
  Felice Orsini*`); reuse if equal, else note the divergence.

- **F6 — LLM-heading stripping + structural skips in `assemble` are generic regex.** `tp:391-397`
  strips model-emitted chapter headings (`#…chapter|capitolo…` and `CHAPTER …`) before writing the
  canonical heading. These are English/Italian keyword regexes — language-tinged but small; route the
  keyword list through the plugin or keep as a documented code default (§15-D4). The
  `_generate_source_pages` (`tp:417-447`) IA-URL builder reads `IA_ITEM_ID` (`tp:414`) →
  `cfg.edition.ia_item_id`; its output keys are slugged from the **English** assembled headings
  (`tp:433`) — a sidecar contract consumed by the not-yet-ported typeset (M3b). **Reproduce the key
  scheme faithfully**; any change to key by `identity.html_slug` is a divergence-ledger event deferred
  to M3b (§15-D5).

- **F7 — progress/resume is a status machine keyed by `parse_md` id.** `translation_progress.json`
  (`tp:181`) is a flat object `{parse_md_id: {status, file?, error?}}`, statuses
  `in_progress`/`truncated`/`done`/`error` (`tp:227, 265, 268, 271, 279`); `done` chapters are skipped
  on resume (`tp:201-202`); stale keys (ids no longer parsed) are pruned (`tp:188-195`); all writes are
  `atomic_write_json` under a `threading.Lock`. Truncation = `stop_reason == "max_tokens"` **or**
  `len(translated)/len(source) < 0.3` (char ratio, `tp:263-268`). This status machine is a one-way
  step contract → BR-015. **Caveat (audit §16, F-A):** the *live* `translation_progress.json` is a
  stale orphan — its keys ≠ the `state/translations/` filenames (3 garbled Part-2 ids predate a
  heading correction). So the BR-015 contract test asserts shape/round-trip on a **synthetic** fixture;
  it must never freeze the live garbled keys as a reference.

- **F8 — `refine` is manual-only and self-protecting via snapshots; it is NOT in the regen set.**
  Live `pipeline.py:28` `REGEN_STEPS = {"cleanup", "translate"}` — `refine` is absent, and
  `pipeline.py` runs refine only for `--step refine`, never under `"all"`. `refine` snapshots **before
  any edit** (`rf:285-286`, `source="pre_refinement"`) and supports `revert_to_version`. So M4c guards
  `translate` (BR-012) but leaves `refine` unguarded — its snapshot/revert is the safety, faithful to
  live. The engine's `cli` must likewise never dispatch `refine` as part of an `all` run.

- **F9 — `_parse_changes` is pure, language-neutral, and the strongest unit target.** `rf:134-178`:
  the `<change old="…" reason="…">new</change>` regex (`rf:134-137`), no-op filter where `old == new`
  (`rf:172`), `±50`-char `context_sentence` (`rf:154-159`), and the `difflib` sentence fallback when
  no tags are present but text differs (`rf:175-176, 181-200`). Zero book/language coupling → unit +
  property coverage with no backend.

- **F10 — refine's revision tree is a one-way contract with a live-data caveat.**
  `revision_log.json` = `{current_version, revisions:[{version, timestamp, source, scope,
  snapshot_dir}]}` (`rf:64-109`); `changes/v{N+1}_{id}.json` = `{version, timestamp, chapter_id,
  source, model, changes[]}` (`rf:112-129`); `snapshots/<timestamp>/*.md` are full copies. **Caveat:**
  the live `changes/` and `revision_log.json` mix two producers — `refine` (`source="pre_refinement"`/
  `"edgren_refinement"`, model `claude-sonnet-4-6`) and a later drift-audit tool
  (`source="drift_correction"`, model `claude-opus-4-8 (…)`) not emitted by `refine.py`. The contract
  test must treat `source`/`model` as **free strings**, not assert the refine literals. → BR-015.

- **F11 — Edgren is mandatory in refine, optional in translate.** `refine` is built around Edgren
  (`REFINE_SYSTEM_PROMPT`, `rf:31-52`; the four `edgren` functions imported unconditionally `rf:20-25`,
  `chunk_edgren()` always called `rf:264`). `translate` gates Edgren behind `--with-edgren`
  (`tp:163-176`, `store_true`, off by default through `pipeline.py`). Port faithfully: refine's
  period-dictionary context is unconditional; translate's is an opt-in hook. Both should drive the
  dictionary off `cfg.language.period_dictionaries` (the Edgren entry), not a hardcoded `edgren`
  import — the period-dictionary hook the framework plan describes (§"providers.py … neutral hook").

- **F12 — `parse_md` ids are heading-derived, so a cleanup heading edit silently re-keys a chapter
  (audit §16, F-B).** Because the id is `slug(title)`, correcting an OCR-garbled heading changes the id
  and orphans that chapter's progress entry, snapshot filenames, and any id-keyed sidecar. The live
  tree already exhibits this (F-A is its symptom). M4c inherits the fragility: translate's resume keys
  on `parse_md` (a heading edit between runs ⇒ the chapter looks un-done ⇒ re-translated) and refine's
  snapshot/revert key on `parse_md` filenames. Structural, not a one-off → BR-019; a line is added to §5d.

- **F13 — `title_to_english` has a latent ordinal-coverage blind spot (audit §16, F-C).** It resolves
  ordinals from a hand-enumerated `_ITALIAN_NUMBERS` table that is *strictly less complete* than the
  `ORDINALS` table the plugin's own `parse_chapter_number` uses — 12 elided forms are missing. The
  corpus trips it **twice today** (`Capitolo Decimosettimo`/`Decimottavo` render untranslated in the
  live English), both of which `parse_chapter_number` resolves correctly (→17/→18). The principled fix
  is to route `title_to_english`'s ordinal step through `parse_chapter_number` (one ordinal model, not
  two) — a ground-truth-licensed **divergence** from the live English, gated on your go → D9 / BR-020.
  Out of strict M4c scope (touches the M1 plugin + the deploy-hold edition).

---

## 5. `translate` port

Signature mirrors the established step contract (`run(*, workspace, cfg, lang, **opts)`):

```python
def run(*, workspace: BookWorkspace, cfg: ResolvedConfig, lang: LanguagePlugin,
        workers: int = 1, thinking_budget: int = 4096, no_thinking: bool = False,
        with_edgren: bool = False, completion: Completion | None = None,
        oracle: DictionaryOracle | None = None, api_key: str | None = None,
        allow_regen: bool = False) -> dict
```

**5a. Deterministic spine (reuse + units).**
- Read `workspace.output / "italian_clean.md"`.
- `segments = lang.chapter_segments(markdown, page_ranges=…)` (D3). Each segment yields `identity`
  (ids/title/english_title/page_range) + `text` (body). **No `skip_titles` is needed** — the audit
  (§16, F-D) confirmed it is inert for PLL: the H1 `#` book title is filtered by the `##`/`###` gate
  regardless, and the title never appears as `##`/`###`. (An earlier draft bound `skip_titles=
  {cfg.edition.title_it}`, which would not even have matched — `title_it` is cased `"libertà"` vs the
  markdown's `"Libertà"`.)
- Per segment: extract+strip the `<!-- pages:N-M -->` marker (F4), build the user message from
  `identity.title` + body, translate, reinsert marker, write `state/translations/{identity.parse_md}.md`.
- `assemble_translation` → reads each `{parse_md}.md`, strips model headings (F6), writes the
  config-driven front-matter (F5) + per-chapter `{level} {identity.english_title}`, emits
  `output/english_translation.md` and `output/source_pages.json` (F6, `ia_item_id` from config).

**5b. LLM call via the `Completion` seam (§3).** `translate_chapter`'s body becomes
`completion.complete(system=rendered_translate_template, user=user_content, thinking_budget=…)`.
The `--with-edgren` block (F11) appends period-dictionary context built from
`cfg.language.period_dictionaries` (the dictionary loader the M6 oracle will generalize; for M4c, a
direct period-dictionary lookup is acceptable — flag in §15-D6).

**5c. Progress/resume (F7).** Port the status machine verbatim into `workspace.state /
"translation_progress.json"`: load-or-`{}`, prune stale, skip `done`, `ThreadPoolExecutor(workers)`,
atomic writes under a lock, the two truncation rules. Keyed by `identity.parse_md`.

**5d. Regen-guard (BR-012, F8).** At `run` entry: if `allow_regen` is False **and** prior output
exists (`output/english_translation.md` present **or** `state/translations/` holds any `.md`), raise
`RegenerationGuardError` (exit 6). This protects the irreproducible refined translations from a
single-model clobber. Faithful to live `REGEN_STEPS` — note that, as in live, **resume also requires
the override** once artifacts exist (the guard is coarse by design; we do not invent a
resume-without-override nicety the live tree lacks). Fresh book ⇒ no artifacts ⇒ runs free.
**Resume-after-cleanup-edit is unsafe regardless of the guard (F12):** if a chapter heading was
corrected since the last run, its `parse_md` id changed, so resume re-translates it and orphans the
old progress entry/translation file. The guard gates on output existence, not id stability, so it does
not catch this; the safe recovery is a full re-run (override on), not a resume.

**Tiers (required):** property + separability + isolation. Deterministic sub-parts → unit. No
equivalence golden (LLM step); id/title derivation already golden via M1's `test_chapterids_golden`.

---

## 6. `refine` port

```python
def run(*, workspace: BookWorkspace, cfg: ResolvedConfig, lang: LanguagePlugin,
        chapters: list[str] | None = None, thinking_budget: int = 4096,
        revert_to: int | None = None, completion: Completion | None = None,
        oracle: DictionaryOracle | None = None, api_key: str | None = None) -> dict
```

- `revert_to is not None` ⇒ dispatch the `revert_to_version` path (`rf:351-414`): restore the snapshot,
  log the revert as a new revision, reassemble. Else the refinement pass.
- Reuse the engine `translate` step's `assemble` + `lang.chapter_segments` (mirrors the live
  `refine.py:26` import from `translate`). Build the period-dictionary context unconditionally (F11).
- `_refine_chapter`'s body → `completion.complete(...)` with the rendered `refine.txt.j2` system
  prompt (§12). `_parse_changes` ports verbatim (F9). Snapshot before edits (`source="pre_refinement"`),
  write revised `{parse_md}.md`, save `changes/` metadata, reassemble (F10).
- **Not regen-guarded** (F8). The engine `cli` must not reach `refine` under an `all` run; refine is a
  standalone dispatch only.

**Tiers (required):** property + separability + isolation. `_parse_changes` and the
snapshot/version/revert logic → unit (language-neutral; the snapshot/revert path is a strong
deterministic unit target).

---

## 7. New config — `edition.title_en`

The English assembled book title (`For Freedom!`, `tp:371`) has no config home (F5). Add it:

- `config/schema/manifest.schema.json` — `edition.required += ["title_en"]`; `properties.title_en =
  {"type": "string"}`.
- `config/models.py` — `Edition` gains `title_en: str` (beside `title_it`).
- `config/loader.py` — `_build_manifest` sets `title_en=edition["title_en"]`.
- `books/per_la_liberta/manifest.json` — `"title_en": "For Freedom!"`.
- `books/synthetic/manifest.json` — a synthetic English title.

`title_en` is **English-only display metadata**, with no `prompt_context` twin, so it is **not** added
to `_BIBLIOGRAPHIC_PAIRS` (the M4b consistency guard, `loader.py:196`) — there is nothing to cross-check
it against. Note that under §15-D7. (Confirm at port: does `edition.subtitle_en` already equal the live
assemble subtitle? If yes, reuse; if it diverges, the assemble subtitle is a second field.)

---

## 8. Decisions (applied in this plan; ratify or amend in audit)

- **D1** — one shared `Completion` text→text seam for translate+refine (§3); providers.py unification
  stays M5.
- **D2** — seam home: shared `steps/_completion.py` (two-way door; §15-D2).
- **D3** — add `LanguagePlugin.chapter_segments` (identity+body); refactor `chapter_identities` to
  share the walk (§4 F1). Plugin-surface addition → one-way door → BR-018.
- **D4** — `translate` regen-guarded (output-exists check); `refine` not (snapshot is its safety).
- **D5** — `edition.title_en` added; not a bibliographic-pair (English-only).
- **D6** — period-dictionary context (translate `--with-edgren`, refine mandatory) driven off
  `cfg.language.period_dictionaries`, not a hardcoded `edgren` import.
- **D7** — `<!-- pages:N-M -->` and the assemble heading-strip regex stay code defaults, not config.
- **D8** — `translate` regen-guard gates on output existence (resume also needs the override);
  resume-after-heading-edit is explicitly unsafe (F12).
- **D9** *(from audit, needs your ruling)* — fix `title_to_english`'s ordinal blind spot (F13) by
  unifying it onto `parse_chapter_number`. A divergence from the live English (2 headings change from
  untranslated to `Chapter Seventeen`/`Eighteen`) → divergence-ledger + `test_chapterids_golden`
  re-baseline + a live re-assemble. **Recommend doing it**, but it is out of strict M4c scope and
  touches the deploy-hold edition, so it is yours to greenlight. → BR-020.

---

## 9. Branch-register entries M4c opens / resolves

- **BR-009** — *resolved (open half).* Per-step chat seams through M4c; translate+refine share one
  `Completion` seam (identical contract); `providers.py` multi-provider unification deferred to M5.
- **BR-015** *(new)* — translation/revision **state contracts** frozen as engine step contracts:
  `translation_progress.json` status machine (F7) and the `translation_revisions/` tree (F10). The
  contract test asserts **shape/round-trip on a synthetic fixture only**; `source`/`model` are free
  strings (the live two-producer caveat) and the **live progress keys are never frozen as a reference**
  (they are stale — F-A).
- **BR-016** *(new)* — `edition.title_en` config home (schema shape change; the assembled English
  title).
- **BR-017** *(new)* — forward-coupling obligation: `multi_translate` (M5) consumes translate's public
  surface (`SYSTEM_PROMPT`/template, `assemble`, chapter parsing). M4c designs that surface to serve
  M5; recorded so M5's port re-points cleanly.
- **BR-018** *(new)* — `LanguagePlugin.chapter_segments` added to the plugin method surface (the
  identity+body sibling of `chapter_identities`); one-way door (plugin surface).
- **BR-019** *(new)* — `parse_md` id instability under cleanup heading edits (F12): a heading
  correction re-keys a chapter and orphans its progress/snapshot/sidecar. Recorded as a known
  limitation of the title-derived id scheme; the candidate retirement is a **stable persistence id**
  (e.g. the sequential `short` id as the on-disk key), deferred — no consumer forces it within M4c.
- **BR-020** *(new, needs ruling — D9)* — unify `title_to_english` onto `parse_chapter_number` to
  close the ordinal blind spot (F13). Divergence-ledger event (improves on the live English); gated on
  your go.
- **Parent — BR-021** *(framework-level, recorded in `engine/docs/decisions/branch_register.md`)* —
  document-structure is an under-abstracted axis; engine direction = **position-based chapter identity**
  (ordinal demoted to a display projection). BR-019 (stable persistence id) and BR-020 (single ordinal
  model) are both downstream of it. Near-term validation: pressure-test against Athanor's Kybalion
  before M4c hardens the id contract.
- **BR-006** — re-read, **re-deferred** (title-path garbles stay in the plugin until a second
  same-typeface book; §2).
- **Divergence ledger** — expected to stay **empty** for M4c: every port choice is a faithful
  reproduction or an orchestration/contract decision (register, not ledger). The one candidate
  divergence — re-keying `source_pages.json` by `html_slug` — is **declined/deferred** to M3b (§4 F6,
  §15-D5), so no ledger entry and no golden re-baseline.

---

## 10. Invariant controls

- **I8 (atomic writes only).** `steps/translate.py` and `steps/refine.py` must write JSON via
  `atomic_write_json` (the live code already does, `tp:145`, `rf:72/116/256`); the `.md` writes are
  `Path.write_text`/`shutil.copy2` as in live. Add both step modules to the I8 scan.
- **I9 (run-twice idempotency)** applies to **translate only**: a second run with all chapters `done`
  skips everything and re-assembles identically. **Refine is intentionally NOT idempotent** (each pass
  snapshots and may re-edit) — assert that exclusion explicitly so I9 isn't mis-applied to refine.
- **I4 (neutrality scan).** `steps/translate.py`/`steps/refine.py` hold **no** book/language literal
  (the prompts live in templates; identity/title logic lives in the plugin) — extend the cleanup-style
  neutrality test to both modules.
- **I6 (doc-ref resolution).** Any test name this plan cites resolves to a real test.

---

## 11. Validation — tiers per step

**`translate`** (property + separability + isolation; deterministic → unit):
- *unit:* `chapter_segments` pairs each identity with the correct body (new method, D3); page-marker
  extract→strip→reinsert round-trip (F4); truncation detection both rules (F7); `assemble`
  front-matter from config + heading-strip + missing-translation warning (F5/F6);
  `source_pages.json` shape + IA URL from `cfg.edition.ia_item_id` (F6); progress resume skips `done`,
  prunes stale (F7).
- *property:* every parsed segment ⇒ one `translations/{parse_md}.md`; assembled output has exactly one
  heading per content chapter; page markers preserved across the round-trip; output text length never
  silently zero for a non-empty source (truncation flagged, not dropped).
- *separability:* run translate against the synthetic 2-chapter book with a **fake `Completion`**
  (canned `(text, stop_reason)`) ⇒ produces English output with synthetic identities, **zero** PLL
  strings; the rendered `translate.txt.j2` under the synthetic manifest contains no PLL identity.
- *isolation:* against a temp `BookWorkspace`, protected roots (`data/output/state/docs/static`)
  unchanged before/after; all writes inside `work/`.
- *regen-guard:* negative control (output exists, no override ⇒ `RegenerationGuardError` exit 6);
  positive control (`allow_regen=True` / `ENGINE_ALLOW_REGEN=1` ⇒ proceeds).

**`refine`** (property + separability + isolation; deterministic → unit):
- *unit:* `_parse_changes` — tag parse, `old==new` no-op filter, `context_sentence`, `difflib`
  fallback (F9); snapshot copies all `.md` + bumps version; `revert_to_version` restores + logs a
  revert revision; missing version raises (F10).
- *property:* a snapshot is always taken before any edit; every recorded change has `old != new`;
  `clean_text` carries no residual `<change>` tag; `current_version` is monotonic; `source`/`model`
  accepted as free strings (F10 caveat).
- *separability:* refine the synthetic book with a fake `Completion` returning `<change>`-tagged text
  ⇒ revised output + a well-formed revision tree, no PLL strings; rendered `refine.txt.j2` clean.
- *isolation:* temp workspace; protected roots untouched; refine writes only under `work/`.

**Prompt-leakage (mirror M4b's two render tests):** render `translate.txt.j2` and `refine.txt.j2`
under the synthetic manifest and grep for `Per la Libertà`, `Crespi`, `di Rudio`, `Orsini`, `Mazzini`,
`Radetzky`, `Risorgimento`, `Napoleon` — none may appear. `StrictUndefined` ⇒ a missing
`prompt_context` key raises at render, not silent empty text.

**New test files:** `tests/unit/test_translate_engine.py`, `tests/unit/test_refine_engine.py`,
`tests/unit/test_translate_refine_contracts.py` (BR-015 state contracts); extend
`test_invariants_controls.py` (I8/I9/I4) and the leakage test.

---

## 12. Prompts to migrate

- `profiles/prompts/translate.txt.j2` — from `SYSTEM_PROMPT` (`tp:65-79`). `{{ book.* }}` for
  title/author/interlocutor/subject/era/preserve-entities; the translation guidelines stay literal.
- `profiles/prompts/refine.txt.j2` — from `REFINE_SYSTEM_PROMPT` (`rf:31-52`). `{{ book.* }}` for
  identity; the dictionary framing ("period-appropriate definitions from {{ dictionary }}") driven off
  `cfg.language.period_dictionaries`; the `<change>` instruction and MINIMAL-edit guidelines stay
  literal.

Both render through `PromptTemplate.load(...)` + `build_prompt_context(cfg)` (`templating.py`,
`StrictUndefined`), exactly as `ocr`/`triage`/`cleanup_correct` do.

---

## 13. M4c does NOT run against PLL

Both steps are LLM + destructive-to-`state/translations/`. M4c never runs them against the live tree:
the `BookWorkspace` sandbox confines all writes to `work/`, the regen-guard refuses a clobber without
the explicit override, and validation is the synthetic-fixture smoke + offline tiers (fake
`Completion`). No real translation/refinement run is part of M4c. The `.claude/settings.local.json`
deny list already covers `cleanup`/`translate`/`all`; add the engine `translate`/`refine` invocations
if not present.

---

## 14. Done when

- `translate` passes **property + separability + isolation**; deterministic sub-parts unit-tested;
  chapter id/title reuse rides M1's `test_chapterids_golden` (no new golden).
- `refine` passes **property + separability + isolation**; `_parse_changes` + snapshot/revert
  unit-tested.
- One shared `Completion` seam (D1) defaults to Anthropic, injects offline; translate+refine consume it.
- `LanguagePlugin.chapter_segments` added (D3); `chapter_identities` refactored to share the walk;
  existing chapterids golden still green.
- `steps/translate.py`/`steps/refine.py` hold no book/language literal (I4); both pass I8; translate
  passes I9 (refine excluded, by assertion).
- Regen-guard: translate negative + positive controls pass; refine asserted **un**guarded.
- Two prompt-leakage render tests pass (translate + refine, synthetic context).
- `edition.title_en` validates for both books; loader/model/schema updated; bibliographic guard
  unaffected.
- BR-015/016/017/018 recorded; BR-009 open half marked resolved; BR-006 re-deferred; invariants log
  updated. Full suite green from `engine/`: `cd engine && uv run pytest`.

---

## 15. Open decisions for your audit

Numbered for `@@@@@@` targeting; each carries my recommendation.

- **D1 — chat seam (BR-009).** One shared `Completion` seam for translate+refine vs. two per-step
  seams vs. unify all four (incl. triage/cleanup) now. *Rec: one shared seam for the two twins;
  full unification stays M5.*
- **D2 — seam home.** `steps/_completion.py` (shared module) vs. defined in `translate.py` with refine
  importing it (mirrors live). *Rec: `_completion.py` (two-way door; cheap to move).*
- **D3 — `chapter_segments` vs. extend `chapter_identities`.** New sibling method (identity+body) vs.
  add a `text` field to `ChapterIdentity` vs. a non-plugin core markdown-splitter zipped by order.
  *Rec: new sibling method delegating to a shared internal walk — keeps body accumulation language-
  agnostic and avoids re-parsing.*
- **D4 — assemble heading-strip keywords (F6).** Code default vs. plugin-owned keyword list. *Rec:
  documented code default — it's a small English/Italian regex; promote to the plugin only if a second
  language needs it.*
- **D5 — `source_pages.json` key scheme (F6).** Reproduce the live English-title slug faithfully vs.
  re-key by `identity.html_slug`. *Rec: reproduce faithfully now; revisit at M3b (typeset is the
  consumer) — a re-key would be a divergence-ledger event.*
- **D6 — period-dictionary access for translate/refine.** Direct period-dictionary lookup now vs. wait
  for the M6 `DictionaryOracle`/`membership_oracle` generalization. *Rec: direct lookup driven off
  `cfg.language.period_dictionaries` for M4c; the oracle is a separate M6 primitive, not a translate
  dependency.*
- **D7 — `edition.title_en` not a bibliographic pair.** *Rec: correct — English-only, no
  `prompt_context` twin to cross-check.*
- **D8 — regen-guard scope for translate (F8/D4).** Guard on `output/english_translation.md` exists
  **or** `state/translations/` non-empty, accepting that resume then also needs the override (faithful
  to live `REGEN_STEPS`). *Rec: as stated; do not invent resume-without-override.*
- **D9 — title→English ordinal blind spot (F13/audit §16).** Patch the 2 missing entries into
  `_ITALIAN_NUMBERS` vs. unify `title_to_english` onto `parse_chapter_number` (closes all 12 latent
  gaps) vs. leave as-is. *Rec: unify — it retires the second ordinal table entirely. Divergence-ledger
  + golden re-baseline + live re-assemble; needs your go (touches the deploy-hold edition).*

---

## 16. Coverage audit (pre-port) — invariants, controls, findings

A coverage-driven audit (not findings-driven) of the premises this plan's conclusions rest on, run
before any porting. Method: enumerate the invariants, check each by source inspection + positive/
negative controls, with the central reuse premise checked empirically against the live data.

**Passed (positive controls).** `slug()` ≡ the live parse-id regex (source + 0 mismatches over all 58
titles); engine `chapter_identities` parse_md set == the live `state/translations/` filenames exactly
(58, 0 dups); engine `title_to_english` == the live English headings (58/58, identical sequence);
parts carry no body and no `parte_`/title id leaks (prefazione present); `translate.py` imports nothing
from `multi_translate`/`providers` (0 refs) and the reverse coupling is exactly 3 symbols; live
`REGEN_STEPS={"cleanup","translate"}` excludes refine; `Edition` has no `title_en` (gap real);
`edition.subtitle_en` string-equals the live assemble subtitle.

**Findings.**
- **F-A** — live `translation_progress.json` is a stale orphan: keys − files = the 3 garbled Part-2
  ids, files − keys = their 3 corrected ids. Action: BR-015 reworded (synthetic-only contract; §4 F7).
- **F-B** — `parse_md` ids are heading-derived ⇒ cleanup heading edits re-key chapters (the F-A
  mechanism, generalized). Action: F12 + BR-019 + §5d note.
- **F-C** — **blind spot, not a data issue (investigated).** `title_to_english` falls through on
  exactly 2 of 57 headings today (`Decimosettimo`/`Decimottavo` → untranslated in the live English),
  but the cause is systematic: its `_ITALIAN_NUMBERS` table is missing **12** elided ordinal forms
  (`decimosettimo, decimottavo, ventesimoprimo/secondo/quinto/sesto/settimo/ottavo/nono,
  trentesimoprimo/secondo/terzo`) that the plugin's *other* resolver `parse_chapter_number` (via
  `ORDINALS`) already has — and which rescued both fall-throughs (→17/→18). The table was patched
  ad-hoc as chapters surfaced (it even carries OCR-garble entries), the signature of a blind spot being
  whack-a-moled. Action: F13 + D9 + BR-020 (unify onto the one robust resolver; needs your go).
- **F-D** — `skip_titles={title_it}` is inert (negative control: empty / manifest-cased /
  markdown-cased skip sets all yield the identical 58 ids) and mis-cased. Action: dropped from §5a.

**Shared attack surface.** F-A/F-B/F-C are one surface: **chapter-heading text is OCR-derived and
cleanup-mutable, and downstream artifacts derive from it** — ids via `slug` (F-A/F-B), English titles
via the `_ITALIAN_NUMBERS` table (F-C). A heading edit or an unlisted spelling silently breaks the
derived artifact. (F-D is unrelated — a plan over-specification.) The two structural fixes that retire
the surface: a **stable persistence id** (BR-019) and a **single ordinal model** (BR-020).

**Unchecked / unrun (carried forward).** The `Completion` seam offline-testability, `chapter_segments`
language-agnosticism, the cleanup→translate regen-guard reuse, `build_prompt_context` render, and the
engine-side `all`-excludes-refine all await built code. `state/multi_translate_progress.json` (would
confirm F-A's cause) unread (M5 scope).

---

*End of plan. Awaiting inline `@@@@@@` audit before any porting begins.*
