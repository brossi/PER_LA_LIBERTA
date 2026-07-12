# Engine Adversarial Evaluation - Independent Companion

**Date:** 2026-07-12
**Scope:** `engine/` on `integration/assessment-provider-boundary`, HEAD `f42d17d`
**Disposition:** Audit only - no remediation applied
**Method:** Main review plus three independent read-only review legs (structure integrity, pipeline boundaries, and test/operational credibility), followed by reconciliation and targeted reproductions.

## Executive verdict

The engine has a disciplined architecture and an unusually serious test culture, but it is not yet safe to treat its green paths as a certification boundary. The most consequential defects are in the places where the design claims authority: canonical-to-witness provenance is not semantically bound, sibling subtree order is not enforced, compare-and-swap persistence loses concurrent updates, validation can fail while the CLI exits zero, and OCR can publish stale or empty witnesses as success.

This narrows the supplied artifact's visible thesis. "The certification apparatus is weaker than it looks" is correct, but several failures are not merely apparatus problems: they permit invalid content, reordered structure, lost human decisions, or stale witnesses to enter the authoritative state while the engine reports success.

**Finding count:** 10 primary high-severity findings plus 2 secondary medium-severity findings. Nine primary findings were reproduced directly; the packaging/runtime finding was confirmed with a built wheel.

## Review of the supplied artifact

The PDF is a single 1440 x 818 point landscape page and ends halfway through the first verdict paragraph. Sections 1-10 named in its navigation are not present in the file. This companion therefore reviews only the visible claims and methodology, not the absent evidence.

What held up:

- Branch and HEAD match: `integration/assessment-provider-boundary`, `f42d17d`.
- The full hygiene suite reproduced the headline result: 1,727 passed, 1 failed, 5 warnings.
- The single red test is the governance-document scanner treating the uncommitted plan field name `test_cmd` as a cited test. That is a detector false positive, not a production failure.
- No production pipeline module imports `engine.structure`; the substrate still has no pipeline consumer.
- The visible confidence vocabulary and explicit residual-risk framing are good audit practice.

What could not be reviewed:

- The detailed evidence for the artifact's sections 1-10, including its defect list, mutation-hunt assessment, governance drift, missed opportunities, and residual-risk analysis, was not included in the PDF.
- The claim that "the architecture is sound" is too broad when applied to the implementation as a certification boundary. The decomposition is sound; several enforcement mechanisms are not.

## Findings

### H1 - Canonical atoms are not semantically bound to their witness derivations

**Confidence:** Verified live
**Evidence:** `src/engine/structure/atom_store.py:448-560`; `src/engine/structure/atoms.py:153-168`

`assert_atom_hashes` proves only that a canonical atom's stored hash matches its own stored text. `assert_reference_integrity` proves only that each `derived_from` identifier exists. Neither proves that canonical text, span, page range, witness marker, or provenance matches the referenced witness atom.

A persisted canonical atom with text `INJECTED`, impossible spans and pages, forged witness metadata, and a back-link to a real witness atom containing `ORIGINAL` passed `load_workspace_streams()`.

**Impact:** A buggy or hostile canonical producer can inject content absent from every source witness, after which the freeze mechanism pins the invalid stream and later authoring gates treat it as authoritative.

**Remediation:** Enforce per-kind atom invariants and compare each canonical atom's adopted content/address fields to the designated primary witness derivation. Independently validate span/page/geometry domains.

### H2 - Projection validation accepts crossing and out-of-order sibling subtrees

**Confidence:** Verified live
**Evidence:** `src/engine/structure/projection.py:405-436,516-554,675-799`; contract in `docs/s4_plan.md:406-411`

The validator checks order within each leaf's `body_atoms`, but not the canonical extents owned by consecutive children. A fixture mutated to traverse canonical indices in the effective order `0, 2, 1` validated successfully.

**Impact:** A green structure map can reorder source content or interleave sibling subtrees despite the explicit non-overlapping reading-order contract. Fresh authoring evidence preserves the authored sequence rather than detecting the contradiction.

**Remediation:** Compute canonical-index extents bottom-up and require every preceding child's maximum extent to be less than the next child's minimum. Define and check how container-owned headings/signatures relate to child extents.

### H3 - Persistence that is described as compare-and-swap loses concurrent updates

**Confidence:** Verified live
**Evidence:** `src/engine/structure/structure_map.py:646-717`; `src/engine/util/jsonio.py:27-39`; `src/engine/structure/geom_review.py:714-739`

Revision check, snapshot check, snapshot write, and live replacement are separate operations with no lock. A barrier-forced two-writer run allowed two different revision-2 maps to supersede revision 1; both callers returned success and the last writer silently won. Geometry verdict recording has the same unlocked read-modify-write shape; two concurrent decisions reduced to one persisted verdict.

**Impact:** Irreproducible human authoring work or review decisions can be silently lost while both commands report success and the files remain well-formed.

**Remediation:** Lock the entire read/check/snapshot/write transaction and re-read the expected revision under the lock. Prefer immutable per-decision records for human verdicts, or otherwise serialize their read-modify-write cycle.

### H4 - Validation failure is a successful CLI run, and `--step all` is not fail-fast

**Confidence:** Verified live
**Evidence:** `src/engine/steps/validate.py:421-479`; `src/engine/cli.py:111-165`

Missing input returns `{"overall": "error"}` and ordinary failed checks return `{"overall": "fail"}`. `_run_step` ignores return values and returns zero unless an exception is raised. The `all` loop retains a nonzero status but continues running every downstream step.

Reproduction: `engine --book synthetic --step validate` printed `Overall: ERROR` for missing `clean.md` and exited 0. A mocked first-step failure still ran OCR, reconcile, cleanup, validation, and every later step.

**Impact:** Automation can publish or consume stale artifacts after a failed prerequisite, and CI/shell callers cannot rely on exit status as the engine's truth signal.

**Remediation:** Make failed/error validation raise a typed engine error or introduce an explicit step result contract that the CLI enforces. Stop on the first failed step by default; reserve continuation for a separately named diagnostic mode.

### H5 - Invalid OCR page ranges can erase a valid witness and return success

**Confidence:** Verified live
**Evidence:** `src/engine/steps/ocr.py:317-355`; `src/engine/cli.py:72-84`

The OCR step clamps only the end page. It does not require `1 <= start <= end <= total_pages`. With a ten-page fake scan and `pages=(8,3)`, it reported `-4 pages`, performed no OCR, atomically replaced a pre-existing good `copy3_raw.txt` with zero bytes, wrote an empty page map, and returned success.

Page zero is also accepted and can select the final PDF page through negative indexing. Worker counts are likewise unbounded and not required to be positive.

**Impact:** A CLI typo can destroy the current quality witness and provenance map without any error signal.

**Remediation:** Validate all range and worker constraints before creating progress state or writing output. Ranged OCR should write a distinct partial artifact or require an explicit overwrite license.

### H6 - OCR resume state is provenance-blind, and a failed witness is still reported as three-way

**Confidence:** Verified live
**Evidence:** `src/engine/steps/ocr.py:169-194,323-345`; `src/engine/steps/reconcile.py:531-563,718-727`

OCR progress is keyed only by model role and page number. It carries no digest of the PDF, concrete model ID, prompt, DPI, renderer, or engine version. In a two-run reproduction, a second backend with different output was never called; the first run's text was silently reused.

Separately, a `copy3_raw.txt` containing only an OCR error sentinel produced zero Copy 3 chapters, yet reconciliation printed and returned `3-way` with zero third-witness coverage.

**Impact:** A build can mix old and new provenance or claim three-witness adjudication when no third witness influenced the result.

**Remediation:** Store a checkpoint envelope binding source hash, model, prompt, render settings, schema/code version, page identity, and output hash. Fail on any page error by default or publish an explicit partial-completeness manifest. Derive reconciliation mode from actual coverage and enforce a declared minimum.

### H7 - Workspace and cleanup cache boundaries are rooted in unvalidated identifiers

**Confidence:** Verified live / code-read
**Evidence:** `src/engine/paths.py:63-65`; `src/engine/config/loader.py:257-298`; `src/engine/steps/cleanup.py:935-956`

`BookWorkspace.for_book` resolves an unchecked `book_id` but never requires the result to remain below `books_dir`. Absolute IDs and traversal therefore redefine the trusted workspace root. The loader also does not require `manifest.id` to equal the requested ID.

Cleanup builds `cache_dir / f"{chapter_id}.txt"` directly. An absolute or traversing chapter ID can escape the cache directory; the existing file is read even when `use_llm=False`, and LLM mode can write through the escaped path.

**Impact:** The advertised workspace isolation is false at its root and at a production cache path. Malformed local artifacts can also smuggle unrelated text into output.

**Remediation:** Use one flat-slug validator for every book/chapter/stream identifier, cross-check manifest identity, resolve and contain book roots, and route every cache path through `BookWorkspace.resolve`.

### H8 - One generic CLI key can be presented to multiple providers

**Confidence:** Code-read with option-routing reproduction
**Evidence:** `src/engine/cli.py:82-108,160-164`; `src/engine/steps/ocr.py:276,308-309`; `src/engine/steps/triage.py:340,366-367`; `src/engine/steps/cleanup.py:867,901-905`

The global `--api-key` option is filtered only by parameter name. OCR, triage, and cleanup all accept an `api_key`, while `--step all` reuses the same option dictionary for every step. The same secret can therefore be offered to Gemini and Anthropic in one run. Passing secrets in argv also exposes them to shell history and, on some systems, process inspection.

**Impact:** Credential confidentiality depends on the caller never combining a generic key with multi-provider orchestration.

**Remediation:** Remove the generic cross-step credential. Use provider-specific environment variables or secret-file inputs, and reject secret flags on `--step all`.

### H9 - Triage application is not idempotent for repeated tokens

**Confidence:** Verified live
**Evidence:** `src/engine/steps/triage.py:278-327`; incomplete coverage in `tests/unit/test_triage_engine.py:137-169`

Resolution application searches from the beginning for the first token equal to the original word. It has no stable occurrence identity or input fingerprint. Applying the same resolution twice to `foo foo` produced `bar foo`, then `bar bar`.

The suite's idempotency test uses a word that appears once, and its repeated-word test performs only one application. Both pass independently while their composition fails.

**Impact:** Retrying triage after an interruption can alter a different, unflagged occurrence and corrupt reconciled source text.

**Remediation:** Bind decisions to chapter, paragraph, token index, surrounding context, and source digest. Treat an already-applied resolution as a no-op and add a repeated-token, run-twice regression test.

### H10 - The installed wheel cannot discover books or load prompts

**Confidence:** Verified by wheel build
**Evidence:** `pyproject.toml:59-63`; `src/engine/config/loader.py:43-46`; `src/engine/prompts/templating.py:30-44`; `src/engine/cli.py:28-30`

The wheel includes only `src/engine`, while runtime code expects repository-level `books/` and `profiles/`. A clean wheel import reported no books and failed to load the OCR prompt because `profiles/prompts/ocr.txt.j2` was absent.

**Impact:** The declared console script is operational only in an editable source checkout, not as the package its metadata describes.

**Remediation:** Decide whether this is a repository-only application or a distributable package. For distribution, move immutable runtime resources into package data, make workspace/book roots explicit, and add a clean-venv wheel smoke test.

## Secondary findings

### M1 - Atom-store parsing is not type-strict or total

`schema_version=true` compares equal to integer version 1, and `geom=[]` escapes as an `AttributeError` instead of the documented typed stale-artifact error. Evidence: `src/engine/structure/atom_store.py:214-229,293-352,393-421`.

### M2 - Atomic replacement is not crash durability or multi-file transactional integrity

`os.replace` provides strong process-level atomic visibility, but the writer does not `fsync` the file or directory, and related artifacts are replaced independently. The documentation's crash guarantee is stronger than the implementation. Evidence: `src/engine/util/jsonio.py:27-39`.

## Test and evidence credibility

Full wrapper run: **1,727 passed, 1 failed, 5 warnings in 115.21 seconds**. The failure is a governance scanner false positive on the uncommitted plan token `test_cmd`.

The suite is broad and unusually adversarial, with real-input, golden, isolation, neutrality, atomic-write, and deterministic-ordering coverage. Its main residual blind spots are composition over reruns, concurrency, installed-package behavior, cache provenance, and cross-step exit semantics. The mutation hunt scripts under `tests/hunts/` are not pytest-collected and are not run by the current engine CI workflow, so mutation claims are point-in-time rather than continuously enforced.

## What held

- Once a workspace root is trusted and callers use `BookWorkspace.resolve`, nested absolute paths, traversal, and symlink escapes are rejected.
- JSON outputs reject non-finite floats and use same-directory temporary files plus atomic replacement.
- Structure loaders enforce substantial schema, identity, topology, ownership, staleness, and hash checks; the findings target missing semantic or cross-node constraints, not an absence of validation.
- Geometry verdicts are fingerprinted against their inputs and stale verdict application is rejected; the defect is concurrent persistence.
- Prompt templates use Jinja `StrictUndefined`, and production template names are constants.
- No production `eval`, `exec`, pickle/YAML deserialization, `shell=True`, or shell-string subprocess execution was found.
- No committed API credential was found in the reviewed engine source/configuration tree.

## Remediation order

1. Make the orchestrator and validation fail closed; reject invalid OCR ranges before any write.
2. Bind canonical atoms to witness semantics and enforce sibling subtree extents.
3. Add real transactions/locks for maps and human verdicts.
4. Add provenance envelopes for OCR, cleanup, and download caches; gate third-witness coverage.
5. Close identifier/path boundaries and separate provider credentials.
6. Make triage decisions occurrence-addressed and idempotent.
7. Decide and test the installed-package contract.
8. Harden atom-store type validation, durability language, and continuous mutation coverage.

## Residual risk and limits

- The supplied source PDF omitted most of the original artifact, so this is a companion to its visible thesis rather than a line-by-line response to its absent sections.
- Network/provider behavior was reviewed through injectable seams and code inspection; no paid live model calls were made.
- Concurrency was tested with synchronized local writers, not on networked filesystems.
- This was an audit-only pass. No production code, tests, plans, or governance records were changed.
