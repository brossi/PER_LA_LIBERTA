# S4.6c preregistration — generalized structural-contents source observations

**Issue:** #90
**Status:** preregistered before implementation
**Date:** 2026-07-19
**Scope:** advisory source observations before S4.6 evidence stamping

## 1. Purpose and authority

The structure map is upstream of handles, evidence digests, rebind anchors, relations, and
rendering. Before human evidence is stamped, the author must be able to inspect what each available
OCR representation actually says about declared structural divisions, including divisions named
only in a printed contents section.

This pass is an **observer**, not a recognizer. It reports source-bound facts and explicitly marked
candidate interpretations. It does not author, mutate, validate, or gate a structure map. Human
S4.6 judgment remains authoritative. Profile-calibrated grammar, scoring, heading recognition, and
recognizer-to-map binding remain S9.1/S9.2 work (#83/#20).

The first production instance is *Per la libertà!*, but the mechanism and fixtures must contain no
PLL ids, titles, page numbers, atom ids, or chapter counts.

## 2. Normalized input contract

The pure observer consumes:

1. an ordered tuple of `SourceDocument` values;
2. an ordered tuple of `StructuralExpectation` values; and
3. the registered observer policy identity.

Every source declares:

- a non-empty `source_id` unique within the run;
- `format` (`djvu-xml` or `plain-text` in v1);
- a stable `source_ref`;
- a bare lowercase SHA-256 over the exact input bytes;
- the byte length; and
- an ordered line surface produced by the format adapter.

Every line has a one-based line ordinal, literal text, and a format-specific locator. DjVu lines
also carry a one-based XML page ordinal and may carry a union word bounding box. Plain text lines
carry UTF-8 byte offsets. Format-specific coordinates are preserved but never interpreted as a
heading judgment.

Every expectation declares a unique `expectation_id`, non-empty literal text, and a caller-declared
role. V1 roles are descriptive strings, not control flow; the observer performs the same matching
for every role. PLL expectations are supplied from the book manifest and reconciled skeleton, not
from constants in the mechanism.

### 2.1 Source locking

Before parsing, the loader recomputes SHA-256 and byte length and compares both with the source
declaration. A mismatch, missing source, non-UTF-8 plain text, malformed XML, duplicate source id,
duplicate expectation id, or empty expectation fails loudly. A failed source is never converted
into an absence claim and no artifact is written.

The output repeats every source identity and locks the ordered expectations by SHA-256 over their
canonical JSON form. It contains no clock time, host path, network response metadata, or other
nondeterministic field. Equal declared inputs and policy produce byte-identical canonical output.

## 3. Matching semantics

Observer policy v1 is `structural-contents-sightings-v1`:

- Unicode normalization: NFKC;
- comparison case: Unicode `casefold()`;
- token characters: Unicode alphanumeric code points;
- punctuation and whitespace: separators collapsed to one ASCII space;
- matching unit: a contiguous normalized token sequence;
- maximum joined line window: three consecutive lines within the same DjVu page, or three
  consecutive plain-text lines;
- duplicate suppression: for the same source, expectation, and normalized token occurrence, retain
  the shortest line window, then the earliest line window;
- match kinds: `literal` when whitespace-collapsed source text contains the whitespace-collapsed
  expectation with exact case and punctuation; otherwise `normalized`.

The observer emits all retained literal/normalized sightings. V1 performs **no fuzzy matching**.
OCR-tolerant grammar and calibrated fuzzy evidence remain #83's responsibility. A future matcher
change requires a policy-version bump and regeneration of the advisory artifact.

Each sighting carries:

- a deterministic id derived from its source, expectation, and locator;
- source and expectation ids;
- match kind;
- the literal matched line window;
- the normalized expectation;
- its exact locator and optional bounding box;
- one neighboring line of literal context on either side when present;
- a locus classification and its factual features; and
- `unverified: true`.

## 4. Contents-like locus feature

For a paged source, each page records:

- total non-empty lines;
- lines ending in an Arabic or Roman page reference;
- the parsed page-reference sequence;
- nondecreasing adjacent reference pairs and comparable adjacent pairs; and
- whether the page is a `contents-like` candidate.

A page is a v1 `contents-like` candidate exactly when:

1. it has at least five trailing page-reference lines;
2. those reference rows constitute at least 50% of its non-empty lines; and
3. at least 60% of comparable adjacent references are nondecreasing.

A reference row must contain entry text before the trailing reference. Arabic references are
accepted directly. Roman references must be uppercase canonical Roman forms; this prevents
ordinary lowercase words composed of Roman-numeral letters (Italian `di`, `mi`, `ci`, etc.) from
masquerading as page references.

The threshold is a deterministic reporting feature, not a calibrated confidence score. A topical
index can satisfy it. Consequently the persisted value is always named `contents-like`, never
`contents`, `table-of-contents`, or `verified-index`.

Sightings on such a page receive locus `contents-like`; sightings on other paged pages receive
`body-like`; sources without page boundaries receive `unresolved`. These are candidate locus names,
not authority claims. The artifact includes the page features that make the classification
auditable.

## 5. Output artifact and absence semantics

The committed advisory artifact is
`books/<book>/work/structure_observations.json`, schema version 1, stale class
`structural-contents-observation`. Its top-level regions are:

- policy identity and expectations hash;
- searched source identities;
- declared expectations;
- paged-source feature records;
- ordered sightings; and
- one summary per `(expectation, source)` with `body-like`, `contents-like`, `unresolved`, and total
  counts.

A zero is meaningful only as:

> no sighting was produced for this exact expectation by policy v1 over this named, successfully
> loaded, hash-locked source and candidate locus.

It does not mean that the phrase is absent from an unavailable witness, that OCR did not omit it,
or that the logical structure does not exist. Cross-source summaries are computed only by adding
the named per-source counts; they do not turn agreement into authority.

The JSON distinguishes:

- `observed`: literal source records and exact counts;
- `inferred`: the mechanically derived `contents-like`/`body-like` candidate locus; and
- `unresolved`: unpaged locus or conflicting/insufficient evidence.

The human-readable report must use the same vocabulary and identify every source included in an
absence statement.

## 6. Write and consumption rules

- Persist with the repository's atomic JSON writer.
- The first write is allowed.
- An equal rewrite is an idempotent no-op.
- Replacing a different existing report requires an explicit `force=True`; the old report is never
  silently clobbered.
- Neither the generic observer nor the PLL runner reads or writes `structure_map.json` or
  `authoring_evidence.json`.
- No index/contents sighting may be used as a body `heading_atoms` value.
- No output may stamp, bulk-ratify, or change an evidence-gate result.
- Human S4.6 evidence prose may cite an observation id after checking the referenced scan.

## 7. Registered PLL sources and expected diagnostic

The production runner source-locks at least these independent DjVu documents:

| source | URL | SHA-256 |
|---|---|---|
| LOC/IA | `perlalibertdal00cres_djvu.xml` | `634a574c2dab690b4828a075612a6844f6237ddcefd89c4701ce64e39486b16a` |
| Harvard/IA | `perlalibertdall00cresgoog_djvu.xml` | `d9f05dbe620742d7232efb467cb4dd5d04d21a87000e20898b045748e1385dfa` |

It also exercises the plain-text adapter over the committed copy1/copy2 OCR texts, whose source
hashes are pinned in the runner declaration.

For the declared part names, the expected diagnostic is:

- `Parte Prima`: zero `body-like` DjVu sightings and one or more `contents-like` sightings in each
  DjVu witness;
- `Parte Seconda`: at least one `body-like` sighting in each DjVu witness and a contents-like
  sighting where the printed contents section names it;
- no synthesized heading and no automatic structure-map change.

These are registered diagnostic expectations for this artifact, not a general recognition rule.

## 8. Red-first verification matrix

Before implementation is considered complete, tests must independently pin:

1. DjVu XML and plain text produce the same normalized sighting for equivalent text while retaining
   different locators.
2. Unicode/whitespace normalization finds a declared string without dropping its literal witness.
3. A three-line declared string is found once; a fourth-line split is not silently widened.
4. Duplicate source ids and expectation ids fail loudly.
5. Missing, hash-mismatched, malformed XML, and non-UTF-8 inputs fail without an artifact.
6. A five-row monotone contents-like page is classified; four rows are not.
7. A topical-index-shaped page can be `contents-like` but never becomes asserted hierarchy.
8. Reordered/non-monotone references fail the 60% rule.
9. An unpaged plain-text sighting remains `unresolved`.
10. Zero-count summaries name only successfully searched sources.
11. Cross-source disagreement remains visible and does not auto-resolve.
12. Output ordering and bytes are deterministic under repeated construction.
13. Equal report writes are idempotent; a differing overwrite is refused without explicit force.
14. The observer contains no PLL literal/id/page special case and imports no structural surface from
    `engine.lang`.
15. The live PLL report satisfies the registered diagnostic above while the structure map remains
    byte-identical apart from the separately approved schema-v1-to-v3 refresh.

### Post-red clarification A1 — reference-row density

The first live adapter run (before accepting or committing the artifact) falsified the original
two-condition page feature: lowercase Italian line-ending words made solely from Roman-numeral
letters created many body-page false candidates. The final v1 rule above adds entry-text,
uppercase-canonical-Roman, and ≥50% row-density requirements. A planted regression test preserves
the exact false-positive family. The registered PLL part result itself did not change; this
clarification prevents unrelated body pages from acquiring a misleading candidate locus.

## 9. Explicit non-goals

- productive heading or designation grammar;
- discovery of undeclared structural vocabulary;
- language/profile priors or scalar confidence weights;
- authoritative contents-versus-topical-index classification;
- running-head suppression policy;
- geometry-based heading judgment;
- capture provenance classes;
- recognizer-to-map binding; and
- automatic evidence generation or acceptance.

## 10. As-built result (2026-07-19)

The reviewed PLL report is `books/per_la_liberta/work/structure_observations.json`, SHA-256
`cf19c081c461f5aab2228cd3bfa8ad8232c7650fed6a7ccb002d31e754009bac`. It source-locks four
documents (two DjVu XML witnesses and their two plain-text OCR representations) and records 16
sightings:

- each DjVu witness finds `Parte Prima` zero times on body-like pages and once on a
  contents-like page;
- each DjVu witness finds `Parte Seconda` twice on body-like pages and once on a
  contents-like page;
- the plain-text adapters retain the corresponding one/three sightings as `unresolved` because
  their source format has no page geometry; and
- the only contents-like DjVu candidates are copy 1 page 269 and copy 2 page 271, the printed
  end-matter contents pages.

The observer therefore supplies evidence for human review of an implicit first-part container; it
does not manufacture an absent `Parte Prima` heading. The strict loader, source locks, deterministic
writer, generic adapters, cross-witness disagreement, false-positive family, and PLL diagnostic are
covered by the registered unit tests. Closeout verification: the S4.6/S4.6c focused integration
selection passed 338 tests; the complete default suite passed 2,011 tests with one intentional
deselection; the changed Python surface passed Ruff; and the live four-source run reproduced the
committed report byte-for-byte without `--force`.

### Review-flag reassessment

The observer changes none of the seeded map's 22 flags automatically:

- flag 4 (`Parte Prima`) is materially clarified: both independent scans prove that the only
  sighting is the end-matter contents entry. The current unheaded `n-3` shape is therefore the
  correct candidate for human ratification, not a missing atom to recover;
- flags 2–3 (`Parte Seconda` duplicates) are corroborated but remain unresolved: each scan has two
  body-like occurrences plus its contents entry, so the observer preserves both body locators and
  does not choose a canonical boundary;
- flag 22 (unsegmented printed contents) gains independent page locators (copy 1 page 269; copy 2
  page 271), but the exact canonical-atom split remains a human S4.6 judgment; and
- flags 1 and 5–21 concern preface/chapter candidates outside this pass's declared part-name
  expectations. They remain unchanged rather than being inferred from unrelated evidence.

Thus the observation pass sharpens four flags and leaves eighteen untouched; it resolves no flag
by mutation or automatic evidence stamping.
