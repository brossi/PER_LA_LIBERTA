# S3.0 — resource + normalization-policy loading/versioning (build plan)

Status: **DRAFT — awaiting audit before code.** Task `S3.0` (#19), milestone S3, concern A, wave W1.
Spec refs: ENGINE_STRUCTURE_PLAN §3.0, §3.6; D14, D21; `feedback_engine_agnostic`.
Dep S0.1 (`structure/artifacts.py` skeleton) — DONE.

This is a standalone artifact for inline audit (the `@@@@@@` / `======` workflow). Every point is
numbered so a comment can pin to it. Nothing here is committed yet; no code is written.

---

## 1. What S3.0 delivers (and the boundaries to its neighbours)

Tracker done-when (line 429): *"resources + normalizer load via the profile; both hashes enter
lineage; neutrality tier green."* Decomposed:

- **R1 — Resource registration + content-hash.** Load the frequency dictionary and the ≥N-of-M
  period-dictionary oracle members *through the language profile* (already where they live:
  `cfg.language.frequency_dictionary`, `cfg.language.period_dictionaries`, `cfg.language.oracle_min`),
  and compute a **content-derived version** for the resource set, so a dictionary swap is detectable.

======
Review: "load the >=N-of-M oracle members" overclaims current scope. `membership_oracle.py` and
`period_dict.py` are stubs, and current `adjudicate` only binds the first monolingual dictionary.
S3.0 should not quietly implement M6 or claim oracle loading if it is only resolving and hashing
resources.

Modify wording to "resolve and hash every profile-declared resource member" instead of "load the
>=N-of-M oracle members."

======

@@@@@@
Conceded — the wording imports scope S3.0 doesn't own, and your fix is exact. Verified:
`membership_oracle.py`/`period_dict.py` are stubs and `adjudicate._build_oracle` binds only the
*first monolingual* member, so the ≥N-of-M oracle isn't constructed anywhere yet (that's M6/BR-001;
the oracle-*gating* is S3.1). S3.0 only resolves + content-hashes resources. Adopting "resolve and
hash every profile-declared resource member." One sharpening on top: "member" must be the **declared
resource unit** (each `PeriodDictionary` entry + the frequency dict), fixed by config — not "whatever
a downstream oracle eventually loads", so the resource set can't drift with a future consumer.
@@@@@@

- **R2 — Normalization policy.** Make the *pre-lookup* normalization (tokenizer, case-fold,
  accent-fold) an explicit object **built from the profile**, with a deterministic **version**, so a
  normalizer change is detectable. Today this normalization is scattered and partly baked
  (`util.text.normalize_for_comparison`'s `.lower()`+NFKD; `load_word_set`'s `.lower()`;
  `adjudicate.DictionaryOracle`'s `word[0].lower().translate(fold)` + accent-insensitive retry).
- **R3 — Lineage versioning, two distinct stale classes.** Both versions enter a lineage value
  object with **separate stale classes** so S8.1 can route *dictionary swap → re-segment* vs
  *normalizer change → re-derive offsets* as different repairs (§3.6).
- **R4 — Engine-agnostic.** All of the above sourced through the profile; the `structure/`
  neutrality scan stays green; proven not-Italian-only by a second synthetic profile.

### Explicitly NOT in S3.0 (owned by neighbours — do not build here)

1. **The `structure_map.json` header schema** that *embeds* these versions → **S4.4** (tracker 450
   names "the **resource + normalizer** versions (S3.0)" as an input it consumes). S3.0 produces the
   value object + its `to_json()` fragment; S4.4 assembles the full manifest header.
2. **The stale-fail *loader* / migration router** that *compares* a stored version to the current
   one and routes the repair → **S8.1** (tracker 512: "changed dict/oracle → re-segment; changed
   normalizer → re-derive offsets"). S3.0 *produces and registers* the versions + classes; S8.1
   *consumes* them. (Same split the atom store took: S1.5 registered `ATOM_STORE_STALE_CLASS`;
   S8.1 will route on it.)
3. **The Zipf-DP word-segmentation + oracle-gating** that *uses* the normalization policy →
   **S3.1** (dep on S3.0). S3.0 defines + versions the policy and proves `normalize()` reproduces
   today's behaviour; S3.1 wires it into the segmentation/oracle path.
4. **Rewiring `adjudicate`/`cleanup` consumers** through the shared policy. Out of "load + version"
   scope and it touches the cleanup detcore golden surface. The policy's first production consumer
   is S3.1; until then `normalize()` is bound to reality by tests (§7), not left abstract. (Logged
   as the S3.1 integration hook, not a silent omission.)

---

## 2. Surfaces this binds into (verified this session)

- `config/models.py` `LanguageProfile` already carries `frequency_dictionary` (str),
  `period_dictionaries: tuple[PeriodDictionary,…]`, `oracle_min: int`, `accent_fold: {"from","to"}`,
  `spacy_model`, `word_letter_class`. **No** `case_fold` field exists (the one missing policy axis).
- `paths.py` `asset_path` / `require_asset(rel, kind=…)` — the resolution chokepoint; `MissingInputError`
  (exit 3) for a missing/typo'd asset. `ASSETS_ROOT = engine/assets` (dev symlinks).
- `structure/artifacts.py` — the established home for per-layer **schema-version + stale-class
  constants** (`ATOM_STORE_SCHEMA_VERSION=1`, `ATOM_STORE_STALE_CLASS="atom-stream"`,
  `STRUCTURE_MAP_SCHEMA_VERSION`, `RELATION_STORE_SCHEMA_VERSION`). Neutral by construction.
- `structure/roundtrip.py` `hash_raw(text) -> "sha256:<hex>"` — the canonical substrate hash helper;
  reuse it for version digests (consistency, one producer).

======
Review: do not reuse `hash_raw` for resource files. `hash_raw()` is specifically the atom raw-span
hash: UTF-8 text in, `sha256:` out. Resource versioning should hash bytes, not "file bytes as text."
Otherwise newline/encoding assumptions leak into a content hash.

Modify the design to add a local resource-content helper such as `_sha256_bytes(path.read_bytes())`,
preserving the `sha256:` prefix. Use a separate text helper only for canonical JSON descriptors.

======

@@@@@@
Accepted as a correctness bug, not a style note. `hash_raw(str)` does `.encode("utf-8")` on text that
already went through a decode; routing a resource file through it (`read_text`) forces a UTF-8 decode
**and** Python's universal-newline translation (`\r\n`→`\n`) — so a CRLF or re-encoding change to a
dictionary would hash *identically*, silently defeating the exact swap/re-OCR detection S3.0 exists
for. Fix as written: `_sha256_bytes(path.read_bytes()) -> "sha256:<hex>"` for resource files. The
canonical-JSON descriptor path stays one producer by encoding its string to UTF-8 bytes and calling
the *same* `_sha256_bytes` — so "separate text helper" is a thin `descriptor → utf-8 → _sha256_bytes`
wrapper, not a second digest algorithm. `sha256:` prefix kept for substrate consistency.
@@@@@@

- `util/jsonio.py` `atomic_write_json` (`indent=2, ensure_ascii=False, allow_nan=False`).
- `dictionaries/frequency.py` `load_word_set(path)`, `dictionaries/symspell.py` `load_symspell(path)`
  — existing path-keyed cached loaders. `membership_oracle.py` / `period_dict.py` are M6 stubs.
- Neutrality guards: `test_structure_neutrality` scans `src/engine/structure/**` for source-language
  heading / guillemet / baked-count literals; `test_core_neutrality` scans all of `src/engine/**`
  for book-entity / typeface terms. Any module I add under these trees must stay clean.

---

## 3. Design decisions (audit targets)

**D-A — Module split (two small modules, matching existing package boundaries).**
- `dictionaries/normalization.py` — the **behaviour**: `NormalizationPolicy` built *from the
  profile*, with `normalize(token) -> str` (pre-lookup key) and `descriptor() -> dict` (the
  canonical, hashable definition). Sits beside `frequency.py`/`symspell.py` (resource loaders).
- `structure/lineage.py` — the **versioning**: hash the resource set + the policy descriptor into a
  `ResourceLineage` value object; serialize the lineage fragment S4.4 will embed. Neutral (reads
  paths/tables from the profile; carries no language literal). Stale-class + schema-version
  constants go in `structure/artifacts.py` (alongside the existing three).

  Rationale: mirrors how loaders (`frequency`/`symspell`) are separate from substrate versioning
  (`atom_store`/`artifacts`). Keeps `structure/` carrying only hashes + class strings, never
  language-parameterized behaviour — so the neutrality scan has nothing to catch.

**D-B — Normalization-policy config shape (the one CONSEQUENTIAL schema change).**
Reuse existing profile fields; add **only the one genuinely-missing axis**:
- *tokenizer* → descriptor `{spacy_model, word_letter_class}` (both already on the profile). S3.0
  captures the tokenizer *identity* for versioning; it does not re-implement tokenization (S3.1's
  Zipf-DP owns segmentation).

======
Review: tokenizer identity is versioned but not implemented. If `spacy_model` and
`word_letter_class` enter `normalizer_version`, then a version can change for behavior
`NormalizationPolicy` cannot apply. That contradicts D-F's "not a hollow version" claim.

Modify by either implementing a real tokenizer/predicate in the policy, or moving tokenizer identity
into a later S3.1 segmentation policy version instead of the S3.0 normalizer version.

======

@@@@@@
The sharpest catch — a genuine internal contradiction (D-B versions a tokenizer D-F says must be
applicable). Resolving by splitting your two options along the two tokenizer sub-parts:
- **`spacy_model` leaves the S3.0 normalizer version.** spaCy tokenization/lemmatization is a
  *segmentation* concern — heavy, and the thing S3.1's Zipf-DP/oracle path actually runs — so its
  identity belongs to **S3.1's segmentation-policy version**, applied there. Versioning it in S3.0 is
  the hollow case you name.
- **`word_letter_class` stays only if S3.0 applies it.** It's a lightweight, testable regex
  predicate; it earns a version slot *iff* the policy exposes the operation that runs it. If we
  decide S3.0's `normalize()` only takes an already-isolated token, then `word_letter_class` also
  moves to S3.1 and S3.0's normalizer version is **case-fold + accent-fold only** — every axis
  applied, zero hollow inputs.
Recommend: **S3.0 versions only what `normalize()`/`fold()` actually apply; tokenizer identity is
recorded by S3.1's segmentation policy.** This honours the tracker's "(tokenizer, case-fold,
accent-fold)" by reading it as *the family the spec names* — D-F decides *where each member is
versioned*, and the tokenizer is genuinely S3.1's to apply. (Dovetails with catch 9: every exposed op
becomes one the policy runs.)
@@@@@@

- *case-fold* → **ADD `case_fold: str`** to `LanguageProfile` + schema + the Italian profile
  (`"lower"`). Enum over `{"lower","casefold","none"}`. This is the axis currently baked as a literal
  `.lower()` — exactly the "core literal" the task says to source from the profile (and a non-Latin
  book needs `"none"`/`"casefold"`, so it must be config).
- *accent-fold* → **reuse `accent_fold`** (`{"from","to"}`). Do **not** add a second copy — the
  M4b-D1 note warns that duplicating the fold table reintroduces the multi-site-divergence bug it
  was consolidated to kill.

  Net schema delta: **one new required field, `case_fold`.** Minimal, faithful, sourced-not-baked.

  **Extensibility (RATIFIED — single field, descriptor is the seam).** The clean-extension worry
  (more `*_fold` axes later) is answered by indirection, not by pre-nesting JSON. `NormalizationPolicy`
  assembles a **descriptor** — an ordered map of named normalization axes — from whatever profile
  fields exist, and the normalizer version hashes the *whole descriptor*. So a future axis (e.g.
  `width_fold` for CJK full/half-width, `digit_fold`) costs exactly: one profile field + one schema
  entry + one line in `descriptor()`. The version / lineage / stale-class machinery is **untouched** —
  a new axis automatically becomes a normalizer-version input (correct stale behaviour) for free. We
  keep new folds as **flat siblings of `accent_fold`** (which already lives top-level, shared with
  cleanup) rather than splitting the family across a `normalization` sub-object + a top-level
  `accent_fold`. Revisit JSON nesting only when a *second* new fold axis actually arrives and gives a
  concrete grouping to design against (same defer-until-real-second-case discipline as BR-007 / the
  override deep-merge) — not speculatively now.

**D-C — Resource hashing = content-derived, not mtime.**
A swap means *different content*; `mtime` false-positives on a no-op `touch`/re-checkout and
false-negatives on a content-preserving copy. So:
- frequency dict → `hash_raw(file_bytes_as_text)` (one file).
- each period dictionary → digest over its chunk files' contents (sorted by filename), plus its
  `name` + `kind`; swapping/adding/removing any chunk or member changes it.

======
Review: "chunk files" is underspecified. Real dictionary dirs contain `raw.txt`, `headwords.json`,
`index.json`, letter chunks, `00_front_matter.txt`, and for Hoare `en_index.txt`. Hashing every file
makes generated metadata or irrelevant files stale the resource; hashing only letter chunks may miss
files future oracle code actually consumes.

Add an exact file-set rule per dictionary member, preferably via `index.json` or a stable filter.
Add tests for "ignored extra file does not change version" and "declared chunk/member change does."

======

@@@@@@
Accepted — and the gitignored file makes it a live bug, not just vagueness. Per the dictionary
CLAUDE.md, each member dir mixes letter chunks, *derived* metadata (`index.json`, `headwords.json`),
and — for Hoare — `raw.txt`, which is **gitignored**. A blind `glob('*')` digest would then be
(a) **unstable across checkouts** (raw.txt present on the authoring machine, absent in CI → different
hash for *identical* dictionary content) and (b) double-count derived metadata that changes
independently of the source. The rule must be the files the **oracle consumes**: the `{letter}.txt`
chunks + the declared back-index for a bilingual member (Hoare's `en_index.txt`). One honest
prerequisite I will not assert blind: I have **not** read `index.json`'s contents this session — if it
canonically enumerates the member's files it's the principled driver (hash the files it names);
otherwise the rule is an explicit chunk-glob + declared-extras filter. I'll read `index.json` first,
then implement, with both-direction tests exactly as you specify (ignored extra file ⇒ no change;
declared chunk/member change ⇒ change). Flagging the read as a gating step, «unverified» until done.
@@@@@@

======!
Follow-up: I checked the three `index.json` files after this response. They do canonically enumerate
the consumed files under `chunks[*].file`; Hoare's `en_index.txt` is included there rather than
needing a separate bilingual special case. So I would tighten the plan now: for each period member,
hash exactly the files listed by `index.json`'s `chunks` table, sorted by the chunk key or file name
for determinism; do not fall back to a glob unless a future profile explicitly marks a legacy member
with no index. Also treat the `index.json` metadata itself as the file manifest, not as hashed
content, so regenerated counts/sizes do not stale the resource unless the declared file set changes.

======!

@@@@@!
Resolves the «unverified» — thanks for doing the read; that's my last open prerequisite closed.
Adopting the `index.json` `chunks[*].file` rule (sorted by chunk key for determinism), no glob. Two
sharpenings:
- **The digest must cover the declared file *identities*, not only their content.** Hash over the
  sorted list of `(chunk_key/file, content_hash)` pairs — so adding/removing a declared chunk in
  `index.json` trips the version (your "unless the declared file set changes"), while `index.json`'s
  incidental metadata (counts/sizes) does not, since its bytes aren't hashed. Identity-in + content-in,
  manifest-bytes-out.
- **A declared-but-absent file fails loud**, never silently skipped — else a truncated dictionary (a
  chunk listed in `index.json` but missing on disk) would hash as if complete. `MissingInputError` +
  a negative test. (A present-but-undeclared stray file is correctly ignored → your "extra file ⇒ no
  change".)
And one push past your wording: for a member with **no** `index.json`, I'd **fail loud**, not fall
back to a glob even behind a flag — a bare glob is exactly the instability we just removed. A future
legacy member should opt in with an *explicit file filter*, never an implicit glob.
@@@@@!

- `oracle_min` folds into the resource descriptor (2-of-3 → 3-of-3 is a semantic resource change).
Hashing multi-MB dicts is a once-per-extraction lineage op (not per-token); cache by resolved path
(the existing loader-cache idiom) so a process rehashes nothing.

======
Review: path-only caching is unsafe for the thing being detected. S3.0's job is to detect content
swaps. If a long-running process rewrites the same asset path, a path-keyed cache can return the
stale digest and miss the swap.

Modify by removing digest caching unless there is a demonstrated performance problem. If caching
remains, key it by a file fingerprint and still read content when the fingerprint changes.

======

@@@@@@
Agreed, with a severity calibration: the hazard is **latent, not active**. `build(cfg)` runs once per
extraction, not in a loop that rewrites assets mid-process, so today's path wouldn't hit the stale
cache. But you're right that a path-keyed cache *on the very digest whose job is to detect content
change* is a self-defeating construct waiting for a future caller — and it buys nothing (hashing
~40 MB once per `build()` is milliseconds). So I'm **removing the digest cache outright** (YAGNI: no
demonstrated perf problem), not fingerprint-keying it; the fingerprint fallback is the right design
only if a perf problem ever appears. Bonus: removing it is what lets catch-10's strengthened test fire
— rewrite-bytes-at-same-path can only change the version if nothing caches past it. (I'm *not* copying
the `frequency.load_word_set`/`symspell` path-cache here — those cache a loaded *index for use*, a
different purpose than hashing for change-detection.)
@@@@@@


*Why content-hash, not a name/version label.* A period dictionary's **text** is a frozen historical
artifact (Zingarelli 1922 will not change), so the hash is not guarding "the edition mutated". It
guards the axes that do move: a **member swap/add/remove** (Hoare 1915 was in fact added as the third
oracle member; a sibling book can swap the set via a manifest `override`), a **re-OCR of the same
source** (same name "Zingarelli 1922", different bytes — the case a *label* silently passes while the
oracle's answers shift), `oracle_min` changing, and the one regenerable member, the **frequency
dictionary** (`it_combined.txt`, built from FrequencyWords + Morph-it). Only a content hash catches a
re-OCR, so the cheaper label is wrong, not just coarser. We do **not** add a frozen-vs-mutable config
distinction to skip hashing the frozen members: it would add a config axis, save only milliseconds on
a once-per-run path, and *miss* the re-OCR case. Uniform content-hash is simpler and correct across
all four axes; the per-member machinery is reusable for any future book's dictionaries.

**Atomic levels (RATIFIED — full hash, expose at the swap-unit, compute finer).** The lineage
fragment carries **two tiers**, mirroring the atom store's whole-artifact-anchor + per-atom-hash
duality: a **rolled-up `resource_version`** (the fast stale-trip wire S8.1 keys on) *and* the
**per-member hashes** that produced it (`frequency:it_combined`, `Zingarelli 1922`, `Edgren 1901`,
`Hoare 1915`). Granularity = the **swap unit**: a book swaps a whole dictionary, not a letter-chunk,
so per-*member* is the meaningful exposed level. Per-chunk (per-letter-file) hashing is done
*internally* to fold each member's digest (so a single changed chunk still trips its member's hash),
but is **not** surfaced — chunk-level lineage would be noise below any real swap. The payoff is for
S8.1's mandate (*why-stale → which-migration*): a coarse single version can only say "resources
changed → re-segment"; the per-member tier lets the S8.1 diagnostic localize to "**Zingarelli 1922**
changed" specifically. Cheap to retain now (the descriptor already assembles per-member entries);
S8.1 *consumes* them.

**D-D — Two distinct stale classes** in `structure/artifacts.py`:
`RESOURCE_STALE_CLASS = "resource-set"`, `NORMALIZER_STALE_CLASS = "normalization-policy"`, plus
`RESOURCE_LINEAGE_SCHEMA_VERSION = 1`. Asserted distinct from each other **and** from the three
existing classes (no collision across the now-five lineage classes).

======
Review: this collision check names stale classes that do not exist yet. Current `artifacts.py` only
has `ATOM_STORE_STALE_CLASS`. There are schema constants for structure-map and relation-store, but no
stale-class constants for them yet.

Modify by testing distinctness against currently existing stale classes only, or explicitly add
structure-map/relation stale-class constants in the owning tasks, not incidentally in S3.0.

======

@@@@@@
Correct — verified in `artifacts.py`: it defines `ATOM_STORE_STALE_CLASS` but only
`STRUCTURE_MAP_SCHEMA_VERSION` / `RELATION_STORE_SCHEMA_VERSION` — **no** stale-class constants for
those layers. So test 5 asserts distinctness against constants that don't exist: it would either
`AttributeError`, or tempt me to *mint* them here, which is scope creep into S4.4/S7.1c (each owns its
own stale class). Adopting your first option: S3.0's collision test checks distinctness among the
classes that exist *after this task* — `ATOM_STORE_STALE_CLASS`, `RESOURCE_STALE_CLASS`,
`NORMALIZER_STALE_CLASS`. The structure-map/relation classes get their distinctness assertions when
their owning tasks mint them. This was me asserting an unchecked fact about a sibling module — the
exact "verify before asserting" failure, caught.
@@@@@@


**D-E — Lineage value object** (`structure/lineage.py`), frozen dataclass roughly:
```
ResourceLineage(
    resource_version: str,          # "sha256:…" rolled-up over the resource-set descriptor
    resource_members: tuple[...],   # per-member {name, kind, hash} — the swap-unit tier (D-C)
    resource_stale_class: str,      # RESOURCE_STALE_CLASS
    normalizer_version: str,        # "sha256:…" over the policy descriptor
    normalizer_descriptor: dict,    # the named-axis map the version hashes (transparency)
    normalizer_stale_class: str,    # NORMALIZER_STALE_CLASS
    schema_version: int,            # RESOURCE_LINEAGE_SCHEMA_VERSION — tracks schema evolution
)
```
with `to_json()` (the header fragment S4.4 embeds) and `build(cfg) -> ResourceLineage` (loads +
hashes via the profile). **No `from_json` + fail-loud comparison here** — that is S8.1. S3.0 emits
values; it does not yet decide staleness.

======
Review: journal-readiness is overstated without the resource descriptor. `oracle_min` is folded into
`resource_version`, but `to_json()` only shows `resource_members`. If `oracle_min` changes, future
S8.1 can see "resource_version changed" but cannot localize "oracle_min 2 -> 3."

Add a canonical `resource_descriptor` or at least top-level `oracle_min` and member `dir`/relative
path in the lineage fragment.

======

@@@@@@
Accepted — it's an inconsistency with my own localization claim. I fold `oracle_min` into
`resource_version` but surface only `resource_members` (per-member hashes), so an `oracle_min` 2→3
moves the version with nothing in `to_json()` to localize it to — exactly the "can't say what changed"
failure the journal-readiness section promises to prevent. Fix: surface the full canonical
**`resource_descriptor`** — `oracle_min` at top level plus per member `{name, kind, dir, hash}` —
symmetric with the `normalizer_descriptor` I already include. Then every input to `resource_version`
is visible to a future diff, *and* catch-11's recompute-from-descriptor assertion becomes possible on
the resource side too (you can't recompute a hash from a descriptor that isn't serialized).
@@@@@@

======
Review: a frozen dataclass with mutable `dict` fields is not actually frozen.
`normalizer_descriptor: dict` can be mutated after construction, making the dataclass value drift
from the version hash it supposedly represents.

Modify by storing immutable descriptor structures internally, or make descriptors private canonical
JSON strings / tuples and have `to_json()` materialize dicts.

======

@@@@@@
Correct, and it's the same hole the atom store already closes. `@dataclass(frozen=True)` blocks
attribute *rebinding*, not in-place mutation of a `dict`/`list` field — and a `normalizer_descriptor`
mutated after construction can drift from the `normalizer_version` that hashed it, the precise
integrity violation lineage exists to prevent. `atom_store.AtomStream.__post_init__` already coerces
fields to tuples via `object.__setattr__`; I'll go one better, taking your canonical-JSON-string
option: **store each descriptor as its canonical JSON string** — immutable, and *by construction the
exact bytes that were hashed*, so descriptor-vs-version drift is structurally impossible — and have
`to_json()` `json.loads` it back to a dict for embedding. Strictly better than tuple-of-tuples here
because it also makes catch-11's recompute an identity against the literal hashed input, not a
re-canonicalization that could itself diverge.
@@@@@@

======!
Tightening: storing canonical JSON strings internally is good, but `to_json()` turning them back into
dicts means the persisted lineage fragment no longer contains the literal byte string that was
hashed. So catch-11 should not be phrased as "identity against the literal hashed input" unless the
canonical string is also serialized. Prefer this contract: one canonicalization helper produces the
stored private string and the hash; `to_json()` emits parsed descriptors for readability; the test
re-canonicalizes `to_json()["resource_descriptor"]` / `to_json()["normalizer_descriptor"]` with that
same helper and asserts the hashes match. That still proves binding without adding duplicate
canonical-string fields to the public fragment.

======!

@@@@@!
Right — "identity against the literal hashed input" was imprecise once `to_json()` emits parsed dicts:
the hashed bytes aren't in the fragment, so the test recomputes *modulo the canonicalizer*, not a raw
byte-compare. Adopting your contract: one `_canonical(descriptor) -> str` helper produces both the
stored hash and (privately) the canonical string; `to_json()` emits parsed descriptors for
readability; the test re-canonicalizes `to_json()["resource_descriptor"]` / `["normalizer_descriptor"]`
through that same helper and asserts the hash matches — binding proven, no duplicate string field in
the public fragment.
The one precondition that makes this sound, which I'll **assert rather than assume**: `_canonical`
must be **stable under a JSON round-trip** — `_canonical(json.loads(_canonical(d))) == _canonical(d)`
— or the recompute-from-parsed-dict isn't a valid identity. With `sort_keys` + fixed separators +
`ensure_ascii=False` it holds for our descriptor types (strings, the `oracle_min` int, nested string
maps; no floats, no non-string keys), but I'll pin it with a tiny idempotence test so the contract
rests on a checked property, not a presumed one.
@@@@@!


**Journal-readiness (RATIFIED — record now, history at S8.1).** The over-time tracking ask is
served by *design*, not by a history log built here (which would be scope-creep into S8.1's
"new-lineage-entry + snapshot-before-migrate" governance). Three properties make this record
**journalable**: (i) `schema_version` tracks schema evolution explicitly; (ii) canonical
serialization (D-G) makes two records byte-diffable; (iii) the per-member + per-axis tiers make a
diff *localizable* ("Zingarelli changed", "case_fold changed lower→casefold"), not just "something
moved". So a future S8.1 stale-report can show *what changed since the last extraction* by diffing
two `ResourceLineage` records. S3.0 builds the diffable record; S8.1 builds the diff + history.

**D-F — `normalize()` is real and tested, not a hollow version.** A version hash over a descriptor
no code can apply is meaningless. `NormalizationPolicy.normalize()` is exercised by tests that
assert it reproduces the existing oracle/lookup normalization on representative tokens (e.g.
`normalize("Pàtria")` yields the same key the `DictionaryOracle` fold path produces). This binds the
version to behaviour without forcing a consumer refactor in S3.0.

======
Review: one `normalize(token)` cannot reproduce the current scattered behavior. The three cited
paths are not equivalent: `load_word_set` lowercases entries, `normalize_for_comparison` lowercases
+ NFKD + drops non-`a-z`, and `DictionaryOracle` lowercases only chunk selection while searching
original and accent-stripped forms. A single "same key" test for `Pàtria` is likely false or at
least underspecified.

Modify by either narrowing the policy to the S3.1 pre-lookup key only, or exposing separate
operations: `frequency_key`, `comparison_key`, `oracle_chunk_key`, and `oracle_probe_forms`.

======

@@@@@@
Conceded — this dismantles the "one `normalize()` reproduces the live behaviour" framing, and the
code backs you exactly: `load_word_set` lowercases only (accents *preserved*); `normalize_for_comparison`
is `lower → NFKD-strip → drop [^a-z]`; `DictionaryOracle` folds only the *first char* for chunk
selection, then probes **two** forms (original, then `accent_fold`-**table**-folded — not NFKD).
Three normalizations, two different accent mechanisms, different scopes. There is no single "the key",
so my Pàtria test was underspecified.
Where I diverge slightly on the *remedy*: I'd take your **narrow** (option a), not the full
`frequency_key`/`comparison_key`/`oracle_chunk_key`/`oracle_probe_forms` quartet (option b). S3.0 owns
the pre-lookup normalization for the **S3.1 dictionary/segmentation path** — concretely the *oracle
fold path* (the `accent_fold`-table fold + first-char chunk key + the ordered probe forms), because
that's the membership path S3.1 oracle-gates on. It does **not** own `normalize_for_comparison`
(heading/ordinal matching — a different consumer) or the frequency-set bare-lower; unifying all three
is the consumer refactor Q4 explicitly defers. So: define the policy as the oracle/segmentation fold
path, expose the operations *that path* needs (`fold(token)` for the case+accent key and the ordered
`probe_forms` the oracle searches), and bind the test to the **oracle fold path specifically**, not a
vague "live behaviour". Your quartet is the right shape only if we later decide S3.0 *is* the
unification point — which I'd resist on scope. (This also closes catch 3: every exposed op is one the
policy runs.)
@@@@@@

======!
Suggested API tightening: avoid keeping the public method name as plain `normalize()` if S3.0 now
owns only the oracle/segmentation lookup path. Name the operations after the contract they actually
serve, e.g. `lookup_key(token)`, `chunk_key(token)`, and `probe_forms(token)`, with
`normalizer_descriptor` covering exactly those operations' profile inputs (`case_fold` +
`accent_fold`, and `word_letter_class` only if an operation actually uses it). That prevents a future
consumer from assuming this is the universal replacement for `normalize_for_comparison` or
`load_word_set` lowercasing.

======!

@@@@@!
Strongly agree — `normalize()` is a false-universality magnet; it implies "the normalization", the
very thing catch-9 showed doesn't exist, and invites a future consumer to mis-bind to it. Adopting
contract-named ops: `lookup_key(token)`, `chunk_key(token)`, `probe_forms(token)` (keeping the class
`NormalizationPolicy` — it *is* a policy over those ops; it was the *method* name that over-claimed).
And I'll make your descriptor-honesty point a **tested invariant**, not just a convention: the
`normalizer_descriptor` keys must equal **exactly** the profile fields those three ops read —
`case_fold` + `accent_fold`, with `word_letter_class` present iff an op applies it, and `spacy_model`
absent (S3.1). A test asserts descriptor-keys == ops'-actual-inputs, so a hollow version input (a
field hashed but unused) *or* a silent omission (a field used but unhashed) turns the suite red. That
operationalizes catch-3's "version only what you apply" permanently, rather than trusting the naming.
@@@@@!

====!!
One final tightening: with the three named operations as written (`lookup_key`, `chunk_key`,
`probe_forms`), I do not see an operation that actually consumes `word_letter_class`. The current
consumer of `word_letter_class` is the boundary search regex (`_search_chunk`), not the fold/probe
normalization itself. So unless S3.0 explicitly exposes a boundary/search predicate that applies the
regex, `word_letter_class` should be absent from `normalizer_descriptor` and belong to S3.1's
segmentation/oracle-search policy alongside the tokenizer identity. That keeps the "version only what
you apply" invariant concrete, not conditional.

====!!

@@@@!!
Verified and conceded — `word_letter_class` is consumed only by `_search_chunk`'s boundary-anchor
regex (`(?<![{wlc}])…(?![{wlc}])`, adjudicate.py:68-70), which is the *search*, not the fold. None of
the fold ops touch it: `chunk_key` is `token[0].lower().translate(fold)` (adjudicate.py:114); the probe
forms are `[token, token.translate(fold)]` (adjudicate.py:116-122) — `accent_fold` + `case_fold` only,
every case. So `word_letter_class` in `normalizer_descriptor` would be precisely the hollow input
catch-3 forbids, just relocated. Removing it: **`normalizer_descriptor` = `{case_fold, accent_fold}`,
unconditionally** — "version only what you apply" is now concrete, not "iff an op uses it".
`word_letter_class` joins S3.1's segmentation/oracle-**search** policy alongside the `spacy_model`
tokenizer identity (the boundary predicate is a search concern — exactly the layer that owns it).
This also pins the op set, which had been loose: the two fold ops the oracle actually applies are
**`chunk_key(token)`** (first-char case+accent fold → which chunk to load) and **`probe_forms(token)`**
(the ordered `[original, accent-folded]` forms the legacy oracle boundary-searches). `lookup_key(token)`
survives only as the **single canonical folded key** (`token` case+accent folded — the membership key
S3.1's Zipf-DP will consult), distinct from `probe_forms`' ordered search list; it too reads only
`{case_fold, accent_fold}`. If at build it proves identical to a probe form, it collapses into
`probe_forms` rather than living as a vestigial alias. Either way: every exposed op reads exactly
`{case_fold, accent_fold}`, so the descriptor-keys==ops-inputs test has a definite, unconditional
target — and the S3.0/S3.1 seam is now clean: **S3.0 = fold; S3.1 = tokenize + search**.
@@@@!!


**D-G — Determinism.** Descriptors are hashed via canonical JSON
(`json.dumps(…, sort_keys=True, ensure_ascii=False, separators=(",",":"))`) → `hash_raw`. `build(cfg)`
twice yields byte-identical versions; period-dictionary order in the descriptor is normalized (sorted
by name) so a reordering in the profile JSON does not spuriously change the resource version.

---

## 4. Red-first test matrix (invariants → the red each is born from)

Per `feedback_red_first_tests`: each invariant is written to fail first on its violation, named by
the red input. Planned home: `tests/unit/test_resource_lineage.py` (+ a neutrality assertion folded
into the existing structure scan via the new module being under `structure/`).

1. **Resource version moves on a dict swap.** Build over a tmp profile pointing at dict-A; rebuild
   pointing at dict-B (different bytes) → `resource_version` differs. *Red:* a hash that ignores
   content (e.g. path-only) → versions equal → fail.

======
Review: this red case does not kill path-only hashing. If dict-A and dict-B are different paths, a
path-only hash changes and the test passes while still ignoring content.

Modify the test to rewrite bytes at the same resolved path and assert `resource_version` changes.
Also touch/rewrite identical bytes and assert it does not change.

======

@@@@@@
Right — the red-first discipline turned on my own test. Test 1 as written (dict-A vs dict-B at
*different paths*) passes for a path-only hash too, so it never sees the mutant it claims to kill — a
test never shown red on the real violation is a claim, not a check. The killing pair is yours: **(a)**
rewrite *different bytes at the same resolved path* ⇒ `resource_version` must change (kills path-only
*and* a stale cache, catch 5); **(b)** rewrite *identical bytes* / `touch` at that path ⇒ version must
**not** change (kills mtime-based and proves content-determinism). Replacing test 1 with that pair.
@@@@@@

2. **Resource-version independence from the normalizer.** Change *only* `case_fold`/`accent_fold` →
   `resource_version` unchanged. (Half of "two distinct stale classes.")
3. **Normalizer version moves on a policy change.** Change `case_fold` (lower→casefold) or
   `accent_fold` → `normalizer_version` differs.
4. **Normalizer-version independence from resources.** Swap a dict → `normalizer_version` unchanged.
   (Other half of the distinctness property.)
5. **Two distinct stale classes, no collision.** `RESOURCE_STALE_CLASS != NORMALIZER_STALE_CLASS`,
   and both differ from `ATOM_STORE_STALE_CLASS` and the structure-map/relation-store classes.
6. **Determinism.** `build(cfg)` twice → identical `ResourceLineage`; reordering `period_dictionaries`
   in the profile JSON does not change `resource_version`.
7. **Both hashes + both classes enter the lineage fragment.** `to_json()` carries non-empty
   `resource_version`, `normalizer_version`, `resource_stale_class`, `normalizer_stale_class`,
   `schema_version`; shape asserted.

======
Review: this shape check is too weak. "Non-empty versions exist" does not prove versions correspond
to the descriptors.

Add assertions that recompute `resource_version` and `normalizer_version` from the serialized
descriptors in `to_json()` and match them exactly.

======

@@@@@@
Accepted — test 7 is a shape check ("non-empty exists"), the exact validate-bindings anti-pattern
(shape-valid passes green while unbound). The binding assertion: pull the serialized descriptors from
`to_json()`, recompute `resource_version`/`normalizer_version` from them, assert exact equality —
proving the stored version *is* the hash of the stored descriptor, no drift. This composes with
catch 8 (descriptor stored as the canonical JSON that was hashed → recompute is a literal identity)
and catch 7 (the resource descriptor is now actually present to recompute from). Adopting.
@@@@@@

8. **`normalize()` reproduces existing behaviour.** On representative tokens it yields the same key
   the live oracle fold path produces (binds D-F).
9. **Loads via the profile, bindings resolve (hard, no skip).** `build(load_book("per_la_liberta"))`
   succeeds; the frequency dict + every period-dictionary dir actually resolve via `require_asset`
   (`feedback_validate_bindings`); a missing/typo'd asset raises `MissingInputError`.
10. **Sourced-not-baked / not-Italian-only.** A **second synthetic** language profile with a
    *different* `accent_fold`/`case_fold` produces a correspondingly different `normalizer_version`
    and `normalize()` output — proving no Italian literal is baked
    (`feedback_single_fixture_blind_spots`: a fixture built to *differ*, not to pass).
11. **Neutrality green.** The new `structure/lineage.py` trips no `test_structure_neutrality` term;
    `dictionaries/normalization.py` trips no `test_core_neutrality` term.

======
Review: `test_core_neutrality` is not enough for normalization neutrality. It catches book/typeface
terms, not hidden language assumptions like `[a-z]`, `.lower()` baked in a new path, or an
Italian-only fold.

Add either a source-language literal/static scan covering `dictionaries/normalization.py`, or make
test 10 strong enough to catch every branch: non-Latin token, case-sensitive profile, and
accent-fold table different from Italian.

======

@@@@@@
Correct, and I'll sharpen it: `test_structure_neutrality` covers `structure/**` (so `structure/lineage.py`
*is* scanned), but **nothing** language-scans `dictionaries/normalization.py`, and `test_core_neutrality`
catches only book/typeface tokens — a baked `.lower()`, `[a-z]`, or Italian fold there sails through
both. The module that most needs the neutrality proof is the one currently unguarded. Primary fix is
behavioural (your second option): strengthen test 10 into a profile built to *break on any bake* — a
**non-Latin-script** token (catches `[a-z]`/ASCII assumptions), `case_fold:"none"` or a **case-sensitive**
profile (catches a hardcoded `.lower()`), and an **accent-fold table unlike Italian's** (catches a baked
`_ACCENT_MAP`) — exercising every branch behaviourally, which a substring scan can't. I'll add a
targeted literal scan as belt-and-suspenders, but the behavioural fixture is the real guard: `.lower()`
and `a-z` legitimately appear in neutral code, so a naive static scan false-positives. This is the
single-fixture-blind-spot rule — the Italian fixture proves one point; only a fixture built to *differ*
proves the generalization.
@@@@@@

12. **Mutation proof.** Hand-mutate the hashing + the policy descriptor assembly (drop a field from
    the descriptor, weaken the fold, collapse the two classes) and confirm the suite kills each — the
    established "0 survivors" discipline.
13. **Per-member tier localizes a change (D-C).** Changing *one* period dictionary's bytes moves
    that member's hash **and** the rolled-up `resource_version`, while the *other* members' hashes are
    unchanged — so a diff can name which member changed. *Red:* a rolled-up-only version (no member
    tier) → the change is unlocalizable → fail. Also: the rolled-up version is a pure function of the
    member hashes (changing a member without changing the roll-up is impossible).
14. **Lineage record is journal-diffable (D-E).** Two `to_json()` records differing only in
    `case_fold` differ *only* in `normalizer_version` + `normalizer_descriptor` (resource tier
    byte-identical), and vice-versa — the localized-diff property a future S8.1 history rests on.

---

## 5. Done-when → proof map

| Done-when clause | Proven by |
|---|---|
| resources load via the profile | tests 9 (binding, hard) + 1 |
| normalizer loads via the profile | tests 8, 10 |
| both hashes enter lineage | test 7 |
| two distinct stale classes | tests 2, 4, 5 |
| neutrality tier green | test 11 (+ existing scans) |

---

## 6. Ratified rulings (2026-06-29)

All four resolved by the user; the design above is updated to match. No open questions remain.

- **Q1 (D-B) → single `case_fold` field, descriptor is the extension seam.** Single field + reuse
  `accent_fold` (no sub-object, no re-declared table). Clean extension for future `*_fold` axes is
  bought by the descriptor indirection, not pre-nested JSON — a new axis = one field + one
  `descriptor()` line, machinery untouched. JSON nesting revisited only when a *second* new fold
  axis arrives (defer-until-real-second-case). See D-B "Extensibility".
- **Q2 (D-C) → full content hash, plus a finer atomic tier exposed at the swap unit.** Full
  content hash confirmed. Added: the lineage fragment carries the rolled-up `resource_version` **and**
  per-**member** hashes (per-chunk computed internally, not surfaced), so an S8.1 diagnostic can
  localize *which* dictionary changed. See D-C "Atomic levels" + tests 13.
- **Q3 (scope) → emit-only confirmed, *and* make the record journal-ready.** S3.0 stops at emitting
  versions + classes (no `from_json`/stale-compare — S8.1; no manifest header — S4.4). The
  over-time-tracking ask is honoured by making the record diffable now (schema_version + canonical
  serialization + per-member/per-axis tiers); the history/diff machinery itself is S8.1. See D-E
  "Journal-readiness" + tests 14.
- **Q4 (consumer) → confirmed.** `normalize()` stays test-bound in S3.0; first production wiring is
  S3.1; no `adjudicate`/`cleanup` refactor now.
