# S3.1 — Zipf-cost DP word-segmentation + oracle-gating + boundary search (plan)

Status: **NOT YET SCOPED.** Tracker: `ENGINE_STRUCTURE_TASKS.md` line 430 (`BUILD`, `TODO`).
Dep: S3.0 (resource + normalization-policy lineage). Milestone S3, concern A.

This file is a **pre-scoping parking doc**: until S3.1 is planned in full, it accrues the questions and
decisions earlier tasks hand forward, so each is *deferred, not lost* (same discipline as
`decisions/branch_register.md`). When S3.1 is scoped, this grows into the full build spec.

The seam (`s3_0_plan.md` §1): **S3.0 = fold; S3.1 = tokenize + search.** S3.0 defined + versioned the
pre-lookup fold policy (`dictionaries/normalization.NormalizationPolicy` over `{case_fold, accent_fold}`)
and proved its `chunk_key`/`probe_forms` ops reproduce the live oracle fold path. S3.1 is the first
*production consumer*: the Zipf-cost DP word-segmenter over the frequency dictionary, the ≥2-of-3
period-dictionary oracle gate, the boundary-search predicate (`word_letter_class`), the tokenizer identity
(`spacy_model`), and the single canonical membership key (full-token fold) S3.0 deferred to here (D-F).

---

## Open questions carried in

### Q-S3.1-1 — `NormalizationPolicy` hashability when S3.1 keys/caches on a policy
- **Opened:** 2026-06-29 (S3.0.3 / #25 pre-commit adversarial audit, finding LOW-2).
- **Question:** `NormalizationPolicy` is a `@dataclass(frozen=True, slots=True)` with an `accent_fold: dict`
  field. A frozen dataclass auto-generates `__hash__`, but a `dict` field is unhashable, so `hash(policy)`
  raises `TypeError`. Acceptable, or should `accent_fold` become a hashable tuple-of-`(from, to)`-pairs
  (and/or the class be documented "not hashable")?
- **State at S3.0 (why not fixed now):** **harmless and convention-consistent.** Nothing hashes a policy —
  the lineage hashes `policy.descriptor()`'s *output* (a derived dict → canonical string), never
  `hash(policy)`, and no test puts a policy in a `set`/`dict`/`lru_cache`. It also matches the established
  config-layer convention: `LanguageProfile` / `OcrConfig` / `BookManifest` (`config/models.py`) are all
  `frozen=True, slots=True` with `dict` fields. The asymmetry with `ResourceLineage` (all `str`/`int`, so it
  stays hashable + `==`-deterministic, which invariant 6 relies on) is principled: the lineage is the
  persisted/versioned value object; the policy is an ephemeral op provider. Fixing it now would diverge from
  the `models.py` convention for no current consumer (YAGNI).
- **Revisit when:** S3.1's segmenter/oracle path **keys or caches on a `NormalizationPolicy`** — e.g.
  memoizing the fold per policy via `@lru_cache`, or holding policies in a `set`/`dict`. The unhashable
  field bites at the first `hash(policy)`.
- **Resolution options (decide against the real consumer):** (a) document "not hashable" and key the cache
  on a hashable surrogate (e.g. `_canonical(policy.descriptor())`, or the `(case_fold, accent_fold-as-tuple)`
  pair); (b) model `accent_fold` as a tuple-of-pairs so the frozen dataclass is genuinely hashable. Pairs
  with `s3_0_plan.md` D-F (the policy's op/descriptor contract) and S3.0's deferral of the canonical
  membership key.
- **Second motivation (perf) — the same fix unblocks a hot-path win.** The S3.0.4 (#26) adversarial pass
  (forward-durability facet, F4) measured `chunk_key`/`probe_forms` each rebuilding the fold table inline
  via `build_fold_table(self.accent_fold)` on *every* call — ~78% of `chunk_key`'s cost, ~5.7× a prebuilt
  table. The frozen policy's table is invariant, so the natural fix is to memoize it (`@lru_cache` / a
  cached attribute) — but that is **blocked by the same unhashable `dict` field** (an `lru_cache` keyed on
  the policy needs `hash(policy)`). So resolution **(b)** (tuple-of-pairs) unblocks *both* hashability and
  per-call memoization at once. Academic today; at S3.1's "millions of tokens × 2 ops" it is not. Same
  revisit trigger — the segmenter both keys-on a policy *and* rebuilds the fold per call.

### Q-S3.1-2 — S3.1's segmentation/search version must cover `spacy_model` + `word_letter_class`
- **Opened:** 2026-06-29 (S3.0.4 / #26 five-facet adversarial pass, forward-durability facet, finding F6).
- **Question:** S3.0's normalizer descriptor is exactly `{case_fold, accent_fold}` (the fold ops' inputs)
  and **deliberately excludes** the tokenizer identity (`spacy_model`) and the boundary-search predicate
  (`word_letter_class`) — correctly, because those are S3.1's segmentation/search concern, not the fold
  policy's (D-F). But until S3.1 *ships its own* segmentation/search version object, a `spacy_model` or
  `word_letter_class` swap moves **no version at all** — a genuine system-level governance under-detection
  (S8.1 would not route a re-segment on a tokenizer/predicate change).
- **State at S3.0 (why not here):** out of scope by construction — S3.0 versions the fold inputs only; the
  segmentation/search inputs have no consumer yet. Flagged so it is not silently lost between S3.0 and S3.1.
- **Revisit when:** S3.1 builds the segmentation/search version — it **must** fold in `spacy_model` and
  `word_letter_class` (and carry its own stale class), or governance under-detects a tokenizer/predicate swap.
- **Note (direction, not under-detection):** a behavior-preserving reorder of the `accent_fold` parallel
  strings (`"àá"` vs `"áà"`, identical `str.maketrans`) *does* move the normalizer version — the descriptor
  hashes the declaration, not the derived behavior. That is over-migration (the safe bias for governance:
  re-derive offsets needlessly, never miss a real change), so it is acceptable, not a defect.

---

## Carried implementation notes for S3.1 consumers
_(S3.0.4 / #26 forward-durability facet — minor, not blocking, captured so they are not rediscovered cold.)_

- **`descriptor()` returns a live alias of the profile's `accent_fold` dict, not a copy** (F2). Safe for
  #27 (`ResourceLineage.build` canonicalizes-then-discards, read-only), but a later consumer that mutates
  `descriptor()`'s return before hashing would silently corrupt `cfg.language.accent_fold` — every oracle/
  cleanup call *and* the hash. Contract for S3.1: treat the descriptor as read-only; never mutate the
  return. (A defensive `dict(...)` copy in `descriptor()` is the alternative if a mutating consumer appears.)
- **`chunk_key("")` raises a bare `IndexError`; `probe_forms("")` returns `[""]`** (F3). The asymmetry
  matches the live oracle (which short-circuits sub-3-char words before the fold, so `chunk_key`'s non-empty
  precondition is the caller's to honor), but S3.1's Zipf-DP segmenter is a *different* consumer than the
  guarded oracle. If the segmenter can ever present an empty span, guard upstream or consider a typed domain
  error over the bare `IndexError` when S3.1 is scoped.
