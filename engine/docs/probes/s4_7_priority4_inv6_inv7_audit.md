# S4.7 Priority 4 adversarial audit — INV-6 + INV-7 carried reds

**Date:** 2026-07-18  
**Branch:** `spike/s4_7`  
**Result:** CLEAN after remediation; item 2 is complete and Priority 5/item 3 may begin.  
**Scope:** the minimal parameterized scale fixture, phase-separated `perf_counter` and
`tracemalloc` instruments, deterministic red sizes, deep evidence fixture, saved performance
baseline, strict carried-red tests, shared mutation table, and repository-local evidence wrapper.

## Outcome first

INV-6 is demonstrably red on the shipped cubic matcher. Across the upward-amended token ladder
`T = 300 / 600 / 1200 / 2400 / 4800`, median isolated `rebind()` wall time grows from
0.000529 s to 6.105047 s. Its OLS log-log slope is **3.188630** against the pre-registered
**≤1.5** bar, and its final adjacent ratio is **93.550445×** against **≤50×**. The complete
serialize→load→index→rebind path is independently red: slope **1.884790** and final ratio
**62.882461×**. Serialize, load, and index wall-clock shapes remain below the bar.

The Python-allocation conjunct is green and is recorded as such rather than forced red. Isolated
rebind peak-memory slope is **0.987422**; end-to-end peak-memory slope is **0.937762**. Every
phase's `tracemalloc` slope and adjacent ratios stay within the registered limits. The invariant is
still red because its wall-clock conjunct fails.

INV-7 is also cleanly characterized: on the registered depth-3,000 isolated topology core,
`evidence_findings` takes a median **4.109154 s** against the fixed **2.0 s** ceiling. Its operation
peak is **934,592 bytes**, well below **512 MB**. The fixture has 6,000 nodes, 4,501,500 decoded
witness references, and 3,376,845 serialized input bytes. Construction, structure/evidence schema
validation, serialization, recursion-limit behavior, and decode-budget classification all complete
before the named operation is measured.

The committed-state suite is intentionally green with **three** isolated strict carried reds:

1. shipped `rebind()` wall-clock growth exceeds the INV-6 slope/ratio bar;
2. shipped end-to-end wall-clock growth exceeds the same bar;
3. deep `evidence_findings` wall-clock exceeds the INV-7 ceiling.

The measured baseline is
`docs/probes/s4_7_priority4_perf_baseline.json`, SHA-256
`6eb8ed5c12b2272adb538cb62c7ce3ba082a7559b0093188cd4d6927b45408f7`.
It contains all five raw repetitions per point and phase, medians, full `L/K/A/T/D` ledgers,
preflight results, environment/commit identity, and hashes of the preregistration, harness,
generator, measurement tool, and two production mechanisms.

The mutation/red evidence is `docs/probes/s4_7_priority4_red_manifest.json`, SHA-256
`36b320e5ec32d37fdac98670832a5d6bdfd0aaa26203f0b6ca8c9f54dcb7ca6b`.
It records **50/50 detected mutants**, zero survivors/errors, all three raw assertion reds at pytest
rc 1, an `11 passed, 3 xfailed` green command, normalized patches, runner/table hashes, and
byte-identical pre/post restoration over all 18 mutated or locked files.

## Adversarial findings and remediations

| ID | Finding | Resolution |
|---|---|---|
| P4-A1 | The original preregistered `{300,600,1200}` token ladder rounded through its own PLL ledger to `L=K=1` at every point. The first diagnostic therefore exposed only a whole-stream single-slot path and measured roughly linear growth—a false-green fixture. | Before measuring any added point, record a dated, upward-only amendment adding `2400` and `4800`; these are the first rounded points with `K=2/3`. Keep every original point and every acceptance constant unchanged. |
| P4-A2 | Applying every wide PLL density ratio to the depth-3,000 evidence fixture would materialize about 180 million witness ids before the named op, conflating fixture inflation with the topology defect. | Record a dated deep-family clarification: one leaf/slot/atom/token per backbone level, `L=K=A=T=D=3000`, explicitly designated as the B-7 isolated topology core. Report node count, serialized bytes, and decoded witness references separately. |
| P4-A3 | Putting fixture construction and timing directly inside `xfail` tests would let a schema error, recursion failure, or missing artifact masquerade as the intended performance red. | Generate and validate a saved baseline first. Structural baseline corruption fails at module collection; green tests separately pin phase completion, raw sample cardinality, source identity, and the exact artifact hash. The strict reds contain only budget assertions. |
| P4-A4 | A single endpoint time can hide a super-linear phase behind fixed serialize/load overhead. | Measure serialize, load, index, and rebind separately and also measure the complete chain. Record growth summaries for wall clock and peak memory for every phase. |
| P4-A5 | Timing under `tracemalloc` would conflate instrumentation overhead with the wall-clock quantity, while timing without a completion check could reward an inert phase. | Run separate median-of-five clock and allocation samples; validate every returned phase result after the measured span. Planted mutations kill removal of time validation and forcing memory peaks to zero. |
| P4-A6 | A saved result could survive while its harness or measured mechanism changed. | Hash the preregistration, materializer, scale harness, capture tool, `rebind.py`, and `evidence.py` into the baseline; verify those hashes in green tests. Pin the baseline's complete SHA-256 and include it in the 18-file mutation-wrapper lock set. |
| P4-A7 | The plan anticipated that shipped Python allocations would also red, but the measured memory shape is sub-quadratic. Treating "every invariant must be seen red" as "every conjunct must fail" would encourage fabrication. | Record every memory conjunct green with raw samples. INV-6 is honestly red on its required wall-clock conjunct; no ceiling or fixture was changed to manufacture a memory failure. |
| P4-A8 | A 3,000-deep persisted full-coverage sidecar exceeds the cumulative one-million-id decode budget; attempting the ordinary loader would measure refusal or allocation, not `evidence_findings`. | Build the registered fixture in memory, prove the exact 4,501,500 decoded-reference count is over budget, serialize/schema-validate the run-encoded form, and explicitly record `persisted_decode_feasible=false`. |
| P4-A9 | Deep-chain failure could be Python recursion rather than evidence complexity. | Use flat node storage and iterative production validation; require `D` to exceed the ordinary recursion limit and complete construction/schema/serialization before measurement. |
| P4-A10 | A slope-only three-point fit can hide a pathological last step. | Preserve the pre-registered two-part gate: OLS slope plus every adjacent ratio. The shipped matcher violates both independently at the top rung. |

## Anti-cheating and measurement checks

- The red baseline targets public `rebind()` and `evidence_findings`, so deleting private
  `_Assignment` or changing an implementation detail cannot delete the durable test meaning.
- The red ladder, estimator, two acceptance bounds, median `k=5`, target profile, INV-7 ceiling,
  and deep depth were fixed before the corresponding measurements. The only ladder change is the
  disclosed upward-only correction required when the original integer-rounded family proved inert.
- Rebind leaves own non-empty contiguous canonical-atom blocks in reading order. The scale family
  does not smuggle the separate non-contiguous-slot precondition into the measurement.
- All raw values remain in the baseline. Tests consume saved results and never rerun a slow
  benchmark opportunistically inside the ordinary suite.
- The OLS and adjacent-ratio implementations have independent linear/quadratic and ratio controls.
  The phase wrapper has planted completion and allocation controls.
- A source-identity mismatch is a green-test failure; a malformed ladder, missing phase preflight,
  wrong repetition count, or wrong schema is a load failure, not an expected performance result.
- Raw carried-red executions are accepted only at pytest rc 1 and contain the intended
  `AssertionError`; mutation restoration is byte-identical.

## Executed stability gates

```text
uv run ruff check <all Priority 1/2/3/4 changed Python files>
git diff --check
  All checks passed

uv run pytest -q \
  tests/unit/test_rebind.py \
  tests/unit/test_structure_map.py \
  tests/unit/test_structure_artifacts.py \
  tests/unit/test_structure_born_gate.py \
  tests/unit/test_authoring_evidence.py \
  tests/unit/test_harness_relation_laws.py \
  tests/unit/test_harness_materialize.py \
  tests/unit/test_s4_7_inv1_inv2.py \
  tests/unit/test_s4_7_inv3_inv5.py \
  tests/unit/test_s4_7_inv6_inv7.py
  447 passed, 16 xfailed in 16.27s

uv run pytest -q
  1875 passed, 16 xfailed, 5 pre-existing SWIG deprecation warnings in 143.65s
```

The refreshed Priority 2, Priority 3, and Priority 4 profiles all report **50/50 detected; 0
survived; 0 errors**, with all raw reds at rc 1 and all 18 files restored byte-identically.

## Bounded claim / non-claims

- This closes item 2's **red-first harness**, not item 3's mechanism replacement. INV-6's two
  wall-clock reds are expected to flip with #48; the registered green ladder remains the later
  100× `10³/10⁴/10⁵` atom-scale acceptance family.
- The item-2 memory instrument is `tracemalloc` and sees Python-managed allocations only. It makes
  no native RapidFuzz/RSS claim; the three-value child-process RSS design remains an item-3/4
  handoff.
- Item-2 serialize/load/index phases use deterministic in-memory render/parse/index primitives.
  They are a minimal phase-honesty scaffold, not item 4's filesystem/child-process production
  benchmark or nightly 100k tier.
- INV-7 is red now, but its final state is not yet chosen. After item 3 it must either become green
  or close honestly UNRESOLVED under DR-6 with a named follow-up issue and a single-purpose strict
  xfail; the 2.0 s / 512 MB ceiling never moves.
- The deep fixture is a synthetic worst-case isolated topology core. It does not claim PLL depth,
  production input distribution, or a persisted full-coverage sidecar at this depth.
- No absolute INV-6 end-to-end resource ceiling is invented here. That tri-state number still
  requires Ben's ruling before item 4 acceptance, exactly as the signed-off plan records.
