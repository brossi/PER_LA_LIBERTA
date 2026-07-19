# S4.7 Priority 5 adversarial audit — #48 production re-anchoring

> **Follow-up — 2026-07-19 / #88:** the `rebind.restamp-evidence` span now reports
> `evidence_supplied: false` only when `RebindContext.old_evidence is None`; supplied empty or
> unqualified evidence reports `true` while retaining `restamped_entries: 0`. Exact three-state
> tests pin the JSON boolean and restamp counts, and a hard-coded-false mutant proves the distinction
> is maintained. The refreshed mutation profile kills **136/136** with byte-identical restoration
> and **449 focused tests passing**. The complete default suite reports **1991 passed, 1 scale test
> deselected**; the source-locked INV-7 baseline remains green at **0.143184 s** median and
> **1,417,936 bytes** peak.
>
> **Follow-up — 2026-07-19 / #87:** rebind evidence restamping now shares the focused bottom-up
> extent reduction introduced by `S4.7-E`. On the purpose-built all-bound depth-3,000 production
> `_restamp_evidence()` diagnostic, the exact-equivalent median moved from **18.027 s wall / 17.911
> s CPU** to **9.941 s wall / 9.897 s CPU** (1.814× / 1.810×); separately measured Python allocation
> remained effectively flat at **39,450,384 bytes** versus **39,232,392 bytes** (+0.56%). Fixture
> work stayed outside the measured span and every one of the five timing and five allocation samples
> revalidated the same complete output digest. The comparison is diagnostic, not a new gate. See
> `s4_7_restamp_bottom_up_before.json` and `s4_7_restamp_bottom_up_after.json`.
>
> The refreshed full mutation profile kills **135/135** with byte-identical restoration, including
> restoration of per-entry subtree walks, duplicate scalar extent construction, and removal of the
> whole-subtree eligibility gate. Its focused green command reports **446 passed**. The complete
> default suite reports **1988 passed, 1 scale test deselected**, with no xfails; the registered INV-7
> baseline remains green at **0.145460 s** median and **1,417,936 bytes** peak.

> **Follow-up — 2026-07-18:** the historical INV-7 residual recorded below is resolved by
> `S4.7-E`. The unchanged depth-3,000 source-locked measurement is now 0.148400 seconds median and
> 1,285,736 bytes peak; the strict xfail is an ordinary passing regression test. See the current
> `s4_7_priority5_perf_baseline.json` and the closing section of `s4_7_priority6_prereg.md`.

**Date:** 2026-07-18  
**Branch:** `spike/s4_7`  
**Result:** CLEAN after remediation for item 3; INV-1…INV-6 are green. INV-7 remains one
characterized strict residual under named local tracker `S4.7-E`.  
**Scope:** production anchored alignment and token→atom projection, stored v3 boundary anchors,
shared seam resolution, report/policy provenance, strict-consumption behavior, the inherited
INV-1…INV-7 corpus, production performance baseline, and mutation evidence.

## Outcome first

The shipped per-slot cubic assignment has been removed. Production re-bind now materializes one
normalized token stream per generation, discovers unique-in-both 3-gram landmarks, selects a
monotone LIS chain, fills only gaps of at most 512 tokens with pinned RapidFuzz Levenshtein
opcodes, and projects every contiguous slot through the resulting shared alignment. Gaps over the
cap become explicit `unaligned` blocks; radically length-skewed or anchor-poor streams fail the
near-duplicate precheck without invoking the backend.

Every slot is then gated by stored prefix/exact/suffix boundary anchors, content similarity, the
active geometry mode, atom-boundary representability, and the global ownership checks. Adjacent
slot seams are resolved as shared decisions: an unconfirmed insertion, disagreement, or a clean
token boundary inside a merged atom fails both affected sides as `global-conflict`. A valid but
non-contiguous slot is explicitly re-bind-ineligible and fails loud.

Structure-map schema v3 is born, not dual-read with v2. It persists typed per-slot start/end anchor
families under `rebind_anchors.boundary_anchors`. The deterministic allocation consumes six tokens
per boundary within the ratified total maximum `W=24`; tests pin determinism, content-only
derivation, side bias, exact-token placement, total footprint, wire shape, and born-gate behavior.

The inherited correctness surface is green. The final locked evidence command records **266
passed, 1 xfailed**. Its only xfail is the isolated INV-7 wall-clock residual; all #48 mechanism
tests and INV-1…INV-6 assertions pass.

After the post-campaign observability controls, the repository-wide gate completes with **1944
passed, 1 scale test deselected by the registered default, and 1 xfailed** in 165.93 s. The five warnings are the
pre-existing SWIG deprecations. `ruff` and `git diff --check` both pass.

## Performance result

The final baseline is `docs/probes/s4_7_priority5_perf_baseline.json`, SHA-256
`e98cee33ccb557ed7146f5b1fcdb344ab9e21cff595edce7fd0e76472f8bdd7d`. It uses the unchanged
registered `T=300/600/1200/2400/4800` ladder and five repetitions per phase.

| Phase | wall-clock slope | max adjacent wall ratio | Python-allocation slope | Result |
|---|---:|---:|---:|---|
| serialize | 0.932003 | 2.182187× | 0.933472 | green |
| load | 0.316957 | 1.448520× | 0.836574 | green |
| index | 0.674711 | 2.162653× | 0.704128 | green |
| anchored rebind | 0.991053 | 2.179850× | 0.938579 | green |
| end-to-end | 0.499507 | 1.623694× | 0.926484 | green |

Every slope is below the preregistered 1.5 bar and every adjacent ratio is below 50×. The result
is a genuine flip from Priority 4's cubic rebind wall slope of 3.188630; no ladder, repetition
count, estimator, or acceptance limit changed.

INV-7 is deliberately not relabeled green. At D=3000, `evidence_findings` takes a median
**4.082733 s** against the fixed **2.0 s** ceiling. Its operation peak is **934,592 bytes** against
512 MiB, so the memory conjunct is green. The raw `--runxfail` assertion exits 1 and is stored in
the audit manifest. Local tracker row `S4.7-E` owns the unchanged-fixture traversal follow-up; a
future ceiling change requires a new preregistration.

## Adversarial findings and remediations

| ID | Finding | Resolution |
|---|---|---|
| P5-A1 | The initial backend test compared RapidFuzz variants directly, but the production normalizer collapsed a one-token Indel insert/delete pair back to the same replace block. | Added an overlapping `("a","b") → ("b","c")` production case whose optimal block geometry remains different after normalization. The Levenshtein→Indel mutant now dies on production behavior. |
| P5-A2 | The boundary-anchor test covered a fuzzy singleton and an exact repeat tie separately; it never proved that an exact occurrence suppresses a weaker above-threshold competitor. | Added one stream containing an exact and a fuzzy copy. Only maximum-score occurrences compete; the weaker-competitor mutant is killed. |
| P5-A3 | The merged-atom integration case still failed through another shared-seam check when atom-boundary representability was mutated, leaving the load-bearing guard unpinned. | Added a direct production `TokenAtomStream.atom_boundary_for_token_boundary` witness. A boundary inside one two-token atom must return `None`; rounding it now fails independently. |
| P5-A4 | The first non-contiguous fixture happened to fail downstream even after the explicit eligibility guard was removed. | Replaced its interposed content with tokenless atoms so the downstream token interval looks deceptively clean. Removing the guard can then steal the other slot's punctuation, and the invariant kills the mutant. |
| P5-A5 | An exact schema-description edit accidentally dropped the previously pinned BR-022 coordinate-space citation. | Restored BR-022 while retaining the v3 anchor description; the pre-existing contract test is green. |
| P5-A6 | A saved Priority 5 baseline generated before the last source changes had a stale `rebind.py` identity. | Expanded baseline identity to the alignment, anchor, schema, loader, evidence, fixture, scale, and capture sources; regenerated only after code stabilization; the green loader verifies every stored hash. |
| P5-A7 | A fully bound result under the named defaults could be mistaken for calibrated output even though S5.2 owns threshold calibration. | `RebindReport` carries `policy_identity` and derives `consumable`; `assert_all_bound` first rejects unresolved nodes and then raises `RebindNotConsumableError` for a fully bound result lacking a registered identity. |
| P5-A8 | Per-slot resolution could independently choose opposite sides of an inserted shared seam. | Added one shared seam reconciliation pass. Any missing/disagreeing side marks every adjacent owner `global-conflict`; the production insertion case and targeted mutation pin this behavior. |
| P5-A9 | No-geometry repeated content can create a unique-old→duplicated-fresh hazard before a local slot score exposes it. | Added a conservative whole-stream duplication precheck over widths 1…3 and tokenless text. It abstains rather than silently bind; INV-1 and the mutation guard pin the fail-loud behavior. |
| P5-A10 | Priority 6's first density×N run falsified the implementation's “O(1)-per-slot boundary lookup” claim: `locate_boundary_anchor` still scanned all `T` tokens for each of `K` slot edges, so rebind remained O(K·T) after alignment. | Reopened Priority 5 and replaced per-slot scans with `BoundaryAnchorBatchLocator`. It deduplicates actual v3 anchor+side queries, scans each stream once per `(anchor width, edit budget)` group using deletion-signature candidate selection, and retains RapidFuzz as the final maximum-score/tie oracle. Random bounded-edit equivalence tests compare it to the brute locator; a production mutation that restores all four per-slot scans is killed. The density surface then completed through N=2400 with zero wrong binds and sub-quadratic timing. |

## Mutation and lock evidence

The immutable run manifest is `docs/probes/s4_7_priority5_mutation_manifest.json`, SHA-256
`841b03b3867afcac7588e07a7c66cb63b2693943cd44af7de30932712e3fafa2`. It records:

- **117/117 detected mutants**, zero survivors and zero runner errors;
- normalized patches and exact single-test scopes;
- runner SHA-256 `698b60f6d3e892963c8a0d2da18ec586a8c85d780f01ea698bccbfae0d73d1c4`;
- mutant-table SHA-256 `6692ab0574d101f55c88860a693a73ea9f6823272c612e8a5fb2067e00f61f58`;
- byte-identical restoration across 34 mutated or locked files;
- the raw INV-7 residual at pytest rc 1; and
- the 267-pass focused green command.

The first expanded hunt killed 62/66. P5-A1…A4 are the concrete result of refusing to accept those
four survivors as “equivalent” without proving it. After strengthening the witnesses, the complete
table was rerun—not just the four new cases—and reached 66/66. Priority 6 later exposed P5-A10;
the reopened table added the batch-equivalence, no-per-slot-scan, policy-domain, RSS, density×N,
and CI attacks and was rerun completely at **82/82**. The post-campaign observability pass added
step-coordinate, internal-span, raw-density, all-failures, and drift-sentinel attacks; the complete
table—not only those additions—was rerun at **117/117**.

The DR-3 pointer in `s4_7_item2_prereg.md` now locks to that manifest. The pointer document is
excluded from the manifest's own source set solely to avoid a circular content hash; the generator,
oracle, matrix, modes, implementation, tests, baseline, table, and runner identity remain inside.

## R-b backend resolution and report contract

R-b resolves to `rapidfuzz@3.14.5:Levenshtein.opcodes` with unit weights, single composite replace
blocks, and backend-deterministic tie behavior. This identity is carried in every `RebindReport` and
is pinned by conformance and mutation tests. The required interior OCR-class character
substitution binds through token-level Levenshtein alignment, so no unregistered character-level
oracle escalation is introduced.

The preserved report role is extended with bounded ambiguity count, boundary classes,
confirmation methods, alignment backend, policy identity, and consumability. The closed unresolved
reason vocabulary is unchanged. The compatibility alias `candidates_ge_tau` remains, but now maps
to the saturated anchor-location ambiguity count rather than the deleted tiling candidate count.

## Parameter and behavior ledger

- alignment landmark width: `k=3`;
- per-gap backend cap: 512 tokens;
- near-duplicate maximum length ratio: 4.0;
- minimum large-stream anchor-chain density: 1/1024;
- stored boundary-anchor total maximum: `W=24`;
- deterministic actual allocation: six tokens per boundary;
- anchor matching: Levenshtein normalized similarity at the active policy threshold;
- geometry: page equality filters in primary mode and narrows an actual content tie in tie-break
  mode; no richer geometric claim is made;
- policy defaults remain uncalibrated and therefore non-consumable without an explicit registered
  identity.

## Bounded claim / non-claims

- This proves the #48 mechanism against the registered synthetic drift/oracle families. It does
  not replace the required true PLL re-extraction gate `S5.1-RG`.
- It proves sub-quadratic shape on the item-2 ladder and Python-managed allocation shape. It does
  not claim child-process RSS, filesystem I/O, the 10³/10⁴/10⁵ production ladder, or nightly CI;
  those remain Priority 6/item 4.
- The conservative duplication hazard may increase fail-loud coverage. It is intentionally not a
  calibrated acceptance policy; S5.2 owns threshold and yield calibration.
- Non-contiguous maps remain valid artifacts, but their affected slots cannot auto-rebind in v3.
  Multi-interval rebind remains deferred.
- INV-7 is one named unresolved performance residual, not a #48 correctness failure and not a
  hidden green. `S4.7-E` owns its optimization under the unchanged ceiling.
