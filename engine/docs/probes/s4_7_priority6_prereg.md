# S4.7 Priority 6 — DR-7 absolute production-scale budget

**Status: ruled and registered 2026-07-18, before any 100,000-atom measurement.** Ben approved
the numeric budget in the S4.7 development task with the exact ruling: **“Approve 300 seconds and
6 GiB.”** These values are acceptance authority, not values inferred from the production-scale
baseline. They must not be relaxed after measurement; a failure requires an implementation or
harness fix, or an honestly failed gate.

## Registered gate

- **Target profile:** Apple M1, 8 GiB physical memory, macOS; Python and dependency identities are
  captured in the measurement artifact.
- **Fixture:** the registered production ladder `A ∈ {1,000, 10,000, 100,000}`, with both wide and
  deep shapes. At the top point `T = 36A = 3,600,000`, `K = L = round(A/40) = 2,500`, and
  `D = 4` wide / `D = 2,500` deep.
- **Named path:** end-to-end `serialize → load → index → rebind`, using separate persisted old and
  fresh workspaces. The conservative lifetime RSS additionally includes the in-child fixture
  materialization required before serialization, as disclosed by the ratified RSS design.
- **Repetitions/statistic:** five spawn-isolated repetitions per point and phase; the gate statistic
  is the **median of five**, independently for each shape. Every raw repetition remains in the
  artifact.
- **Wall-clock ceiling:** median end-to-end time at `A = 100,000` is **≤ 300.0 seconds**, for each
  of wide and deep.
- **Memory ceiling:** median conservative lifetime RSS at `A = 100,000` is
  **≤ 6 GiB = 6,442,450,944 bytes**, for each of wide and deep. `ru_maxrss` units are normalized to
  bytes and its raw reading is retained. The gated lifetime value is
  `max(normalized raw ru_maxrss, absolute sampled named-span peak)`. Since it must be at least the
  sampled peak, this is also a conservative bound on that nested value.
- **Separate growth gate:** every named phase's median wall-clock, lifetime RSS, and sampled-span
  RSS must still satisfy the already registered subquadratic slope and adjacent-ratio limits. The
  absolute budget does not replace or weaken that gate.

## Independent rationale

The 300-second limit is the five-minute ceiling for the full opt-in/nightly CLI-scale operation.
The 6-GiB limit leaves 2 GiB of the registered 8-GiB machine for the OS, interpreter surroundings,
and measurement process. These operational limits were selected before the top production point
was measured and are intentionally independent of the earlier small/10,000-atom diagnostics.

**Dated pre-top-rung instrumentation clarification — 2026-07-18.** During the always-on small
control, before any 100,000-atom run, macOS returned a parent-sampled current RSS exactly one
16-KiB page above the child's normalized `ru_maxrss`. The counters use different kernel views, so
rejecting either valid reading would make the nesting check flaky. The raw `ru_maxrss` is retained;
the conservative lifetime value is their maximum as specified above. This can only tighten the
approved 6-GiB gate and does not alter its number, fixture, repetitions, or named path.

## Failure-artifact rule

The full runner captures raw measurements, evaluates all registered gates without short-circuiting,
atomically writes the artifact, and only then exits nonzero if a gate failed. A gate failure may not
be hidden by omitting its artifact or by increasing either ceiling.

**Dated observability amendment — 2026-07-18, after an interrupted first full-campaign attempt and
before the authoritative restart.** The first attempt exposed no operating descriptor while a
long-running child was active: the internal 5-ms RSS polling existed, but its queue carried only
`span-ready` / `span-done`, and the tool retained completed samples only in memory. Ben directed a
**15-second progress interval**. The interrupted attempt produced no artifact or gate verdict and
did not authorize any budget change.

The restarted runner therefore emits parent-side structured heartbeats every **15.0 seconds** with
shape, atom rung, phase, repetition, overall measurement index, setup-vs-named-span state, child
PID, elapsed time, current RSS, and observed span peak. Start/transition/completion events are also
emitted. Completed density points and phase repetitions are atomically checkpointed; interruption
retains that checkpoint, and normal completion binds it to the final artifact hash. Heartbeat I/O
runs in the parent and is not inside the measured child span. Both CI workflows use tee capture and
upload the checkpoint alongside the final artifact. This amendment changes observability and
failure recovery only—not the fixture, operation, repetitions, statistic, or approved ceilings.

**Dated prerequisite-cache amendment — 2026-07-18, after the cancelled diagnostic reached one
100,000-atom serialize sample and before the authoritative restart.** That diagnostic exposed
1,100.673 seconds of fixture setup before a 27.938-second serialize span. Profiling traced the
dominant defect to boundary-anchor construction repeatedly copying and scanning the complete token
stream for every boundary (`O(K*T)`), plus repeated construction of identical prerequisites in all
150 children. The completed diagnostic evidence is retained as
`s4_7_scale_infeasible_setup.checkpoint.json` and `s4_7_scale_infeasible_setup.live.log`; it is not a
gate verdict.

The restarted harness fixes the full-stream anchor scan and creates one versioned, source-locked
substrate per `(shape, atom_count)`. Substrate materialization is itself a cold, spawn-isolated RSS
sample reported separately. After an in-memory versus persisted round-trip equivalence check,
ordinary serialize/load/index/rebind children receive isolated filesystem clones and prepare only
the prerequisite state for their named phase. Children remain serial. **Every end-to-end sample at
every rung remains cold and materialization-inclusive**, not merely the two top-rung gate samples.
Thus caching cannot improve either registered A=100,000 lifetime-RSS result, and the three-point
end-to-end growth series retains one consistent definition. The cache changes campaign duration,
not the registered fixture, end-to-end path, repetitions, statistic, or ceilings.

The CLI now mirrors structured progress directly to a caller-selected log rather than relying on a
shell `tee` pipeline. This lets SIGINT reach the Python runner, which atomically marks the checkpoint
`INTERRUPTED`; it also leaves the same live output visible in the shared PTY.

**Second setup-diagnostic amendment — 2026-07-18, before any authoritative A=100,000 phase
sample.** The first cache-enabled restart reached the separately measured wide A=100,000
materialization span and was interrupted at 270 seconds. Its checkpoint and live log are retained
as `s4_7_scale_relation_quadratic.checkpoint.json` and
`s4_7_scale_relation_quadratic.live.log`. Profiling identified two more reference-harness list scans:
the independent event composer located every reminted id with `list.index` and redundantly scanned
the live stream for new-id membership, while fixture-spec validation used `list.index` for every
atom claim. These are now explicit position maps. The relation laws, generated fixture, registered
end-to-end path, metric boundaries, repetitions, and ceilings are unchanged; only prerequisite
construction complexity changes. The optimized interpreter and spec validator have planted
anti-scan tests and mutation kills before the next source-locked restart.

The same pre-restart diagnostic then showed that the independent fixture tree checker used Python
recursion and could not construct the registered deep shape (`D=2,500`). It now uses an explicit
enter/exit stack with the same cycle and reachability semantics. A planted 2,500-depth test passes;
cold diagnostic construction completed in 40.548 seconds wide and 57.801 seconds deep at
`A=100,000`. These diagnostics establish campaign feasibility only and are not substituted for any
registered phase repetition or gate statistic.

**Completed-campaign failure and unchanged-gate rerun note — 2026-07-18.** A local power outage
ended the visible shared stream, but the direct progress log and atomic checkpoint survived and the
runner completed all 150 measurements. The absolute top-rung gate passed (wide 229.230 s / 1.886 GB
median lifetime RSS; deep 245.137 s / 2.455 GB), as did every non-index growth metric and the full
density surface with zero wrong binds. The campaign honestly finalized `COMPLETE_GATE_FAILED`: index
wall-time slope was 1.678177 wide and 1.818795 deep, both above 1.5. Its immutable evidence is retained
as `s4_7_scale_failed_index_growth.json`, its hash-bound checkpoint, and its live log.

Profiling localized more than 90% of the index span to `validate_handle_policies`: each node's four
derivation witnesses rebuilt the complete parent table, searched sibling tuples, and walked ancestor
chains independently. The production validator now builds one batch render context, pre-indexes child
positions and collision ranks, resolves inherited policies once, and compares position-path candidates
without materializing every deep ancestor prefix. At `A=10,000`, identical before/after profiles moved
from 0.333 s to 0.032 s wide and from 1.572 s to 0.040 s deep. Focused correctness tests are green and
the complete mutation table kills 111/111, including planted regressions to the two quadratic paths and
the two source-identity locks. `handles.py` and `projection.py` are now explicitly included in both the
campaign source identity and substrate source lock. The replacement campaign uses the same fixture,
phases, five repetitions, statistic, 1.5/50 growth limits, and 300-second/6-GiB absolute ceilings; no
measured threshold is changed or reinterpreted.

**Replacement-campaign result and post-campaign telemetry amendment — 2026-07-18.** The unchanged-gate
replacement completed all 150 measurements. Every shape/phase growth gate passed after the handle-index
fix. The absolute top rung also passed: wide end-to-end was 221.709379 s / 1,851,736,064 bytes median
lifetime RSS and deep was 222.511297 s / 1,907,818,496 bytes. The artifact nevertheless retained an
honest `FAIL` because the `0.71` density treatment's top adjacent timing ratio was 56.935855, above 50.
A post-run audit also found a `55.2928` ratio for treatment `0.60`; the then-current evaluator reported
only the first density exception. The evaluator now preserves every treatment failure independently.
This reporting repair does not reinterpret or replace the source-locked campaign artifact.

Before production optimization, the harness observability contract is revised to
`s4.7-scale-progress@v2`:

- Every phase repetition carries both its global campaign coordinate (`n/150`) and an explicit
  `phase.repetition` coordinate: `1.1` through `5.5`, plus the local `1/25` through `25/25` position.
  Source-locked substrate materialization is labeled `prep`, outside the registered 5×5 phase grid.
- The default terminal stream contains a compact human line and structured NDJSON. Records include a
  run UUID, monotonic event sequence, UTC timestamp, child PID, setup/named-span state, and the stable
  internal stage. The 15-second heartbeat additionally includes stage elapsed/progress, child
  user/system CPU and one-core percentage, thread/status data, current/peak RSS, host available memory,
  swap, and load where the platform exposes them.
- Rebind now exposes opt-in, in-memory wall/CPU spans for token materialization, alignment, old/fresh
  anchor location, boundary-owner indexing, token and tokenless duplication detection, slot resolution,
  migration, validation, restamping, and report assembly. Locator span attributes retain query/window,
  exact/fuzzy/unresolved, and old-locator-reuse counts. Production callers that do not provide a
  recorder perform no logging or filesystem I/O.
- Per-stage RSS summaries and the complete child span trace are retained with every raw RSS repetition.
  Density artifacts now retain every raw repetition and its correctness outcome/trace instead of only
  the median. Child failures retain the internal trace and traceback.
- The append-only progress log, latest-event active-state file, checkpoint, and final artifact use
  flushed/fsynced writes; active state is initialized before measurement and atomically replaced after
  each event. Human output remains outside the measured child span.

The pre-optimization comparison is retained as `s4_7_rebind_telemetry_baseline.json` (SHA-256
`ade09cb2f692cace096a3cbd19cdcb85bde18cecb9b276aa09c881e58a047d30`). It uses five spawn-isolated
rebind samples at `A=10,000` for each shape and for both the registered token-identical fixture and a
deterministic drift sentinel. Per 400 old atoms, the sentinel applies one OCR-class token edit, one
split, and one merge; its token stream differs while aggregate atom cardinality and correct binding are
preserved. Median named rebind times were 3.825209 s wide / 3.666562 s deep for identical input and
4.509409 s wide / 4.475899 s deep for drifted input. Across shapes, alignment consumed 0.939–0.990 s,
old-anchor location 0.841–0.862 s, duplication detection 0.534–0.548 s, and slot resolution
0.840–0.884 s. Drift added 0.833–0.838 s for fresh-anchor location; identical input reused the old
locator in about 20 microseconds. Thus later identity-fast-path results must be reported separately from
drift performance. Focused tests pass and the expanded mutation table kills 117/117, including the six
new telemetry, raw-repetition, all-failures, coordinate, and drift-sentinel regressions.

## Post-instrumentation single-cycle diagnostic

Before production optimization, one source-locked wide `A=100,000` cycle exercised the five named
phases once each. It is retained as `s4_7_scale_cycle_wide_a100000.json` (SHA-256
`35df492bd2789f17f581a5fb6c12f60fe72abec866fb5d28f669beb9400e83e7`) with its direct progress log
(SHA-256 `28873fb82e4d428e75eeaee7e7bfd03717f50ff214eb16603cac7e4f69caabf8`), hash-bound checkpoint,
and final active state. The source identity matches all 13 current files. The checkpoint is `COMPLETE`
with one `prep` event and all five named measurements; the active state is `COMPLETE` at coordinate
`5.1`. This diagnostic deliberately has no registered-gate verdict because it has one repetition, not
the ratified median of five.

| Coordinate | Named phase | Wall time | Lifetime RSS | Earlier authoritative median |
|---|---|---:|---:|---:|
| `prep` | materialize cached substrate | 93.258 s | 1,288,667,136 B | n/a |
| `1.1` | serialize | 58.762 s | 1,307,688,960 B | 28.893 s |
| `2.1` | load | 55.549 s | 987,561,984 B | 32.728 s |
| `3.1` | index | 3.335 s | 1,073,446,912 B | 0.773 s |
| `4.1` | rebind | 307.917 s | 1,233,321,984 B | 158.800 s |
| `5.1` | cold end-to-end | 454.073 s | 1,339,588,608 B | 221.709 s |

The wall times are an operating-condition baseline, not a clean performance baseline. Across 87
15-second heartbeats, host available memory fell as low as 1,047,281,664 bytes, memory use reached
87.8%, swap reached 10,736,959,488 bytes, and one-minute load reached 38.2505. Child CPU ranged from
39.5% to 89.9% of one core. The roughly 2× end-to-end inflation relative to the completed campaign is
therefore recorded context, not evidence of a production regression. Memory remained safely below the
registered 6-GiB ceiling, and the telemetry distinguished sustained CPU work from a stall.

The standalone rebind trace localizes 92.7% of its 307.917 seconds to four spans:

| Rebind span | Wall time | Share of named rebind | Diagnostic fact |
|---|---:|---:|---|
| slot resolution | 179.136 s | 58.2% | 2,500 slots completed steadily in 128-slot progress units |
| token alignment | 55.592 s | 18.1% | old and fresh 3.6-million-token streams were identical |
| token-duplication detection | 26.099 s | 8.5% | six 1/2/3-gram counters proved no new duplication |
| old-anchor location | 24.513 s | 8.0% | all 5,000 queries resolved exactly, yet 7,199,991 windows were scanned |

The cold end-to-end trace independently reproduced the hierarchy: slot resolution 180.741 s,
alignment 70.936 s, duplication detection 25.975 s, and old-anchor location 20.117 s. This repeat within
the same cycle makes the optimization order evidence-based despite host contention:

1. Compute each fresh slot fingerprint once and reuse its score, containment, and token ratio. The
   current successful path constructs the same shingle fingerprint in the threshold check and then
   reconstructs it twice while assembling the outcome.
2. Add the identical-token identity-alignment fast path, while keeping drifted-sentinel results separate.
3. Skip old/fresh duplication counters when token streams are identical.
4. Make anchor location exact-first; build fuzzy deletion signatures only for unresolved queries.
5. Treat structure-map persistence and loading as a separate production stream: they consumed
   41.728 seconds of serialize and 42.369 seconds of load in the named standalone phases.
6. Optimize cached-substrate finalization separately as harness work. It shortens developer feedback
   but must not alter the materialization-inclusive cold end-to-end metric.

Every production fast path must be A/B checked for identical results, planted against regression, and
paired with the deterministic drift sentinel so favorable remint-only input cannot conceal general
re-segmentation performance.

## Issue #86 staged optimization evidence

The production-rebind work is tracked in GitHub issue #86. Each change below was kept independently
measurable, passed its focused invariant tests, and was deliberately mutated red before restoration.
The approved gate remains 300 seconds / 6 GiB, median of five; none of the contended diagnostics below
recalibrates it.

1. **One fresh fingerprint per evaluated slot.** The immutable slot metrics object now supplies
   similarity, containment, and token ratio to both thresholding and the ordered outcome. Complete
   result digests cover success, scored/unscored below-threshold, missing-anchor, page mismatch, and
   ambiguous paths. The direct counter invariant is exactly 250/250 at `A=10,000` and 2,500/2,500 at
   `A=100,000`; a planted second construction fails functionally. Evidence:
   `s4_7_rebind_fingerprint_reuse_a10000.json` (`f5ce010a...8c49`) and
   `s4_7_rebind_fingerprint_reuse_wide_a100000.json` (`0b480bda...1c46`). Under comparable severe
   host pressure, wide `A=100,000` slot resolution moved from 179.136 to 142.596 seconds wall and
   141.640 to 124.720 seconds CPU.
2. **Identical-token alignment.** Exact token equality returns one identity alignment block without
   constructing k-gram indexes. All ten identical `A=10,000` samples reported the identity branch;
   all ten deterministic-drift samples reported the general branch. Median alignment was 0.0039
   seconds wide / 0.0067 seconds deep for identical streams, versus 2.352 / 2.229 seconds for drift.
   Evidence: `s4_7_rebind_identity_alignment_a10000.json` (`79a56c16...ff3`).
3. **Identical-token duplication bypass.** Demonstrably identical streams skip all token 1/2/3-gram
   counters, but tokenless-atom analysis remains active because token equality does not prove atom
   segmentation equality. Every identical sample reported `analysis_skipped=true` and zero analyzed
   widths; every drift sample reported false and three widths. The identical phase fell to about
   7–8 microseconds. Evidence: `s4_7_rebind_duplication_skip_a10000.json` (`0217ec9f...7356`).
4. **Exact-first boundary lookup.** One exact pass collects every exact tie; deletion signatures and
   the second scan are restricted to unresolved queries. Focused tests prove exact ties, fuzzy
   fallback, sorted ambiguity, brute-force equivalence, and zero-signature mutation protection. At
   `A=10,000`, all 500 old and drift-fresh queries per case resolved exactly with zero fuzzy
   signatures, reducing locator spans to 0.13–0.20 seconds. The contended wide `A=100,000` sample
   resolved all 5,000 old queries exactly with zero fuzzy signatures; old-anchor location was 2.491
   seconds, named rebind 183.704 seconds, and lifetime RSS 1,274,986,496 bytes. Slot resolution
   remained dominant at 161.119 seconds. Evidence: `s4_7_rebind_exact_first_a10000.json`
   (`4a797a09...dea3`) and `s4_7_rebind_exact_first_wide_a100000.json` (`cfab3a24...bd16`).
5. **Structure-map Tier-1 validation.** Added nested read/parse/Tier-1/typed/Tier-2/render/I/O spans.
   The before profile localized 3.559 of 3.721 write seconds and 5.220 of 5.571 load seconds to the
   Python JSON Schema walk at `A=10,000`. A cached native Draft 2020-12 validator now handles the
   valid hot path; the established Python implementation still checks the schema definition and is
   consulted on native rejection to preserve edge decisions and error locations. Differential
   fixture/mutation tests and the non-finite writer contract pass. Persist/load became 0.180/0.189
   seconds, with Tier-1 at 0.060/0.038 seconds. Evidence:
   `s4_7_structure_map_profile_wide_a10000.json` (`c208a39a...6481`) and
   `s4_7_structure_map_native_validator_wide_a10000.json` (`ef7596c5...3ca9`).

All timing artifacts retain raw wall/CPU/RSS samples, host memory/load/swap context, source identity,
the 15-second direct progress log, and the exact fingerprint counters. Absolute wall comparisons made
under changing contention are labeled diagnostic; CPU and wall are reported separately and their
difference is called non-CPU elapsed time.

### Pre-milestone telemetry cadence refinement

Before the optimized milestone cycle, live capture was refined without changing any measured span,
RSS sampler, fixture, phase boundary, repetition count, or gate threshold:

- The registered/routine campaign heartbeat remains **15 seconds**. The one-cycle and focused rebind
  optimization tools now default to **5 seconds**, and all three runners accept an explicit positive
  finite cadence override (including 1 second for temporary stall/resource diagnosis). The effective
  cadence is recorded in sample telemetry and run/checkpoint provenance.
- Slot-resolution work progress is no longer published at a fixed 128-slot stride. With telemetry
  enabled, the loop checks after every completed slot and updates the shared stage register when about
  one second has elapsed; the final slot is always published. The parent heartbeat remains solely
  responsible for appending/displaying that shared state.
- The telemetry-disabled path retains its direct list-comprehension fast path and does not consult the
  progress clock. Exact nested wall/CPU spans remain self-timed, and RSS continues to be sampled every
  5 milliseconds, so changing the operator heartbeat cannot alter exact span duration or sampled peak
  semantics.

An already-started single-cycle attempt was interrupted before rebind when this refinement arrived.
Its active state, checkpoint, and progress log are retained under the explicit
`interrupted-before-telemetry-refinement` name and are non-authoritative; the milestone restarts from
the beginning with a new run UUID and source identity.

The refinement's focused tests are green, including a short run-scoped cadence probe, deterministic
time-throttle publication at slots 3/6/9/final, and a planted clock access that the telemetry-disabled
path must avoid. The refreshed performance source lock is
`s4_7_priority5_perf_baseline.json` (SHA-256 `7e9d1d43...4666`). The expanded mutation manifest is
`s4_7_priority5_mutation_manifest.json` (SHA-256 `f8e51f87...ed67`): 125/125 mutants were detected,
zero survived or errored, restoration was byte-verified, and its post-restore green run passed 278
tests with the one preregistered strict timing xfail retained.

## Optimized single-cycle milestone

The restarted wide `A=100,000` milestone completed `prep` plus all five named phases with a new run
UUID. The artifact is `s4_7_scale_cycle_optimized_wide_a100000.json` (SHA-256
`e7b106db...d6a9`), its 5-second progress log is `a571614d...7b42`, and its atomic checkpoint is
`32a112e0...1dae`. The checkpoint is `COMPLETE` with six completed events, active state is `COMPLETE`
at `5.1`, and all 13 source-identity hashes match current files. This remains a single-repetition
milestone and therefore does not substitute for the registered median-of-five verdict.

| Coordinate | Named phase | Wall | Phase CPU | Lifetime RSS | Change from pre-optimization cycle |
|---|---|---:|---:|---:|---:|
| `prep` | materialize cached substrate | 64.996 s | 50.169 s | 1,257,635,840 B | n/a |
| `1.1` | serialize | 18.560 s | 14.042 s | 1,624,506,368 B | -68.4% wall |
| `2.1` | load | 15.258 s | 11.731 s | 1,426,522,112 B | -72.5% wall |
| `3.1` | index | 1.134 s | 0.953 s | 1,545,666,560 B | -66.0% wall |
| `4.1` | rebind | 171.741 s | 142.607 s | 1,607,090,176 B | -44.2% wall |
| `5.1` | cold end-to-end | 212.233 s | 171.180 s | 1,534,656,512 B | -53.3% wall |

The cold sample is below both registered absolute ceilings without changing them. Operating pressure
remained material: across 127 heartbeats, available host memory reached 1,082,736,640 bytes, swap
reached 5,774,835,712 bytes, and one-minute load reached 10.7798. Wall and CPU are therefore retained
separately; no clean-baseline claim is made.

Telemetry captured 63 slot-resolution heartbeats across the two rebind executions with non-stride
counts such as 81, 200, and 328, directly demonstrating fresh time-throttled shared progress. The
standalone rebind breakdown was 158.584 seconds slot resolution, 2.202 seconds old-anchor lookup,
0.062 seconds identity alignment, and 7 microseconds token-duplication analysis. Slot resolution is
still the residual production bottleneck; the identity/duplication/locator work is no longer a
material share of this identical-stream workload.

## Registered median-of-five campaign

The complete registered campaign ran all 150 named measurements plus six cached-substrate
materializations in 5,186.24 seconds. The artifact is
`s4_7_scale_registered_optimized.json` (SHA-256 `3ea4b373...3dfd`), its 15-second progress log is
`c584a9bf...3da`, and its atomic checkpoint is `df5d4d09...8622`. The checkpoint honestly records
`COMPLETE_GATE_FAILED`; the issue remains open and no threshold was changed. The progress stream
contains the terminal `scale-campaign-complete` event, but the active-state file remains
`IN_PROGRESS` because the assertion path did not publish a terminal failed state. That telemetry
finalization defect is follow-up work, not a reason to alter the measurement artifact.

The absolute registered gate passed for both shapes:

| Shape | `A=100,000` cold median | Lifetime RSS median | 300 s / 6 GiB verdict |
|---|---:|---:|---|
| wide | 194.272 s | 1,693,515,776 B | PASS |
| deep | 186.640 s | 1,791,852,544 B | PASS |

All 18 correctness-at-density points had zero wrong binds, and every density timing slope and
adjacent ratio passed. The registered verdict failed only the rebind wall-growth sentinels:

- wide rebind medians were 0.095894, 1.957887, and 160.487762 seconds. The fitted slope was
  1.611825 against the 1.5 ceiling (and the final adjacent ratio was 81.9699).
- deep rebind medians were 0.168527, 2.391419, and 142.262374 seconds. The slope passed at 1.463211,
  but the final adjacent ratio was 59.4887 against the 50 ceiling.
- every RSS-growth check passed. Across the progress heartbeats, available host memory reached
  1,053,966,336 bytes, swap reached 5,803,212,800 bytes, and one-minute load reached 32.6592. The
  median-of-five result, not any individual pressured sample, remains authoritative.

At the top rung, slot resolution remained the dominant span even after all five preceding
optimizations:

| Shape | Rebind median | Slot-resolution wall | Slot-resolution CPU | Share of rebind |
|---|---:|---:|---:|---:|
| wide | 160.488 s | 145.612 s | 126.982 s | 90.7% |
| deep | 142.262 s | 128.642 s | 118.032 s | 90.4% |

Every top-rung sample evaluated 2,500 slots and constructed exactly 2,500 fresh fingerprints, so the
remaining cost is not a regression to repeated fingerprint calls. Code inspection instead found a
specific scaling defect: `TokenAtomStream.atom_boundary_for_token_boundary()` scans
`atom_token_ranges` from the beginning for every resolved boundary. Resolution calls it twice per
slot, producing about 5,000 scans over as many as 100,000 atom ranges. The documented O(1)-per-slot
boundary projection therefore contains an O(A) conversion and trends toward O(A²), consistent with
the failed 10,000→100,000 growth ratios.

The next optimization milestone is therefore preregistered in this order:

1. Add resolver subspans/counters for old-span discovery, boundary projection, atom-boundary
   conversion, fingerprint construction, metric derivation, page checks, and outcome assembly. Count
   atom-boundary lookup calls and inspected ranges so the suspected quadratic work is directly
   falsifiable.
2. Build one reusable atom-boundary index per materialized token stream. Preserve the exact
   tokenless-gap and unrepresentable-inside-atom semantics while replacing each full scan with an
   O(log A) or O(1) lookup. Prefer this general-path improvement over an identical-segmentation-only
   shortcut.
3. Re-run focused equivalence, direct-count, mutation, identical, and drift tests, then the
   `A=10,000` and isolated `A=100,000` comparisons. Both rebind growth failures must improve without
   changing the registered ceilings.
4. Only after boundary conversion is no longer dominant, optimize fresh fingerprint internals:
   avoid unnecessary sorted-tuple construction, derive intersection/union/containment from one set
   intersection, and evaluate whether an indexed or rolling range-shingle representation pays for
   itself. The maintained one-computation-per-evaluated-slot invariant remains mandatory.
5. Treat structure-map I/O and fixture materialization separately. Top-rung serialize/load medians
   remain roughly 11.5–15.2 seconds, while cached-substrate materialization consumed 44.9–47.4 seconds.
   The former affects production cold latency; the latter affects harness feedback and must not be
   removed from the registered cold lifetime metric.
6. Publish `COMPLETE_GATE_FAILED` to the live active-state file from a `finally` path so an operator
   never sees a completed failed campaign as still running.

Every boundary-index or fingerprint change must retain bit-for-bit outcomes and ordering, include a
mutation that restores the eliminated work, and repeat the deterministic drift sentinel immediately.
The remint-only identity fixture remains useful but cannot serve as the sole performance proof.

## Boundary-index and runtime-fingerprint milestone

The six follow-up resolutions from the failed-growth campaign were completed without changing any
registered threshold or metric boundary:

1. Slot resolution now reports aggregate wall/CPU subspans for old-span discovery, boundary
   projection, atom-boundary conversion, fingerprint construction, metric derivation, page checks,
   and outcome assembly. The parent span retains lookup calls, inspected ranges, outcomes, evaluated
   slots, and exact fresh-fingerprint computation counts. Aggregate component spans are explicitly
   labeled `disjoint-call-total`; they do not perturb the one-second live work publisher.
2. Every materialized `TokenAtomStream` now carries a compact atom-boundary index. Indexed lookup
   preserves invalid-boundary, inside-token-bearing-atom, tokenless-gap offset/range, and tokenless
   prefix-mismatch outcomes while replacing the repeated full range walk with binary search. The
   exhaustive unit oracle compares every boundary against the original linear semantics, including
   tokenless cases.
3. The direct linear-versus-indexed `A=10,000` experiment reduced inspected atom ranges from exactly
   7,500,000 to 7,168 for the same 500 lookups in every sample. Boundary-conversion wall/CPU fell by
   about 99.6--99.7%, while all identical and deterministic-drift outcomes and 250/250 fingerprint
   counts remained unchanged. The isolated wide `A=100,000` sample performed 5,000 lookups with
   88,462 inspected ranges; boundary conversion was 0.048 seconds wall / 0.036 seconds CPU and named
   rebind was 16.954 seconds. Evidence:
   `s4_7_rebind_boundary_lookup_linear_a10000.json` (`b10490fd...c707`),
   `s4_7_rebind_boundary_index_a10000.json` (`21973766...04f`), and
   `s4_7_rebind_boundary_index_wide_a100000.json` (`e1fbc9be...84f4`).
4. Fresh comparison-only fingerprints now use an immutable runtime representation without persisted
   tuple sorting. Similarity, containment, and token ratio derive from one intersection cardinality,
   without allocating a union or repeating the intersection. The persisted/public fingerprint
   representation is byte-stable. At wide `A=100,000`, resolver CPU fell from 3.173 to 1.798 seconds,
   construction CPU from 1.738 to 0.770 seconds, and metrics CPU from 1.169 to 0.610 seconds; the
   exact count remained 2,500/2,500. Evidence: `s4_7_rebind_runtime_fingerprint_a10000.json`
   (`e294920a...30e1`) and `s4_7_rebind_runtime_fingerprint_wide_a100000.json`
   (`dc8e3550...395`).
5. Structure-map read/write remains separately spanned production work, and cached-substrate
   materialization remains a separately reported harness phase that is still included in every cold
   end-to-end sample. No work was shifted across the registered cold boundary.
6. Campaign assertion evaluation now runs under a finalizer that publishes `COMPLETE` or
   `COMPLETE_GATE_FAILED`. A planted stale-`IN_PROGRESS` mutation fails the terminal-state test.

The final source-locked wide `A=100,000` single-cycle milestone is
`s4_7_scale_cycle_boundary_index_fingerprint_wide_a100000.json` (SHA-256
`048b3407c49991e225cc832c4bf321ea379132386cbc255b9a39a2c8efd694a6`), with progress log
`c969cc15fd64f9f44fab670b6b25bd88ed507313237dfb606f1cad3e77bcad95`, checkpoint
`29386afc1171fb5df9e7c87eeddbce8e3a2813497b136514982d15bc950b5462`, and active state
`a79b4bb6ebb8b72ee1c287caa23292f6296dc4e9ffc09f7414b723b5f32cfd2a`. The checkpoint and active
state are both `COMPLETE` at `5.1`.

| Coordinate | Named phase | Wall | Phase CPU | Lifetime RSS |
|---|---|---:|---:|---:|
| `prep` | materialize cached substrate | 59.650 s | n/a | 1,825,144,832 B |
| `1.1` | serialize | 12.633 s | 11.059 s | 1,958,494,208 B |
| `2.1` | load | 10.957 s | 9.496 s | 1,352,204,288 B |
| `3.1` | index | 0.923 s | 0.828 s | 1,660,125,184 B |
| `4.1` | rebind | 14.103 s | 10.987 s | 1,573,765,120 B |
| `5.1` | cold end-to-end | 59.211 s | 42.443 s | 1,558,839,296 B |

The issue-#86-close performance source lock was `s4_7_priority5_perf_baseline.json` (SHA-256
`689b9e044e729198406301e1a71ead05dc8017af970e1dbe961e5fedeff71113`). The completed mutation
manifest is `s4_7_priority5_mutation_manifest.json` (SHA-256
`1117bdbc1d65caf3f9191bf10964c434462d689681e5b81160419bddef0aef90`): 131/131 mutants were
detected, zero survived or errored, and restoration was byte-verified. Planted mutations specifically
restored the linear range walk, discarded aggregate telemetry, added a second runtime fingerprint,
left terminal status in progress, relaxed the mutation heartbeat, disabled its live tee, and exposed
an interrupt traceback; each failed before restoration. Ruff is clean, and the full default suite
passes with 1,974 passed, one deselected, and the preregistered strict timing xfail.
That snapshot is historical; S4.7-E regenerates the governed files and removes the residual below.

## Final registered verdict — issue #86 acceptance

The unchanged registered median-of-five campaign completed all 150 named measurements plus six
source-locked substrate materializations in 2,325.56 seconds. The artifact is
`s4_7_scale_registered_boundary_index_fingerprint.json` (SHA-256
`2fe4aea8ddb50b1214d6f6b53c2dc4a14e58b868e3fdcff47dc8c2f43979b752`), its 15-second progress
log is `81c09b6ccc9ab74adca637139ec9aafdf13dde408e9b7e77be90da05310b0162`, its checkpoint is
`8b9b47c13abf73fe6af52b2f70264d017acc366b5b01f6edd2cf182f797af426`, and its terminal active
state is `432a8b5e432f2c96bd14b019a6444a1f968cb35a5235d85190935a2a142c8972`.
The checkpoint is `COMPLETE` with all 174 completed events and no failure; active state is terminal
`COMPLETE`; the artifact verdict is `PASS`.

| Shape | `A=100,000` rebind median | Cold end-to-end median | Lifetime RSS median | Absolute verdict |
|---|---:|---:|---:|---|
| wide | 12.579 s | 49.572 s | 2,180,317,184 B | PASS |
| deep | 13.588 s | 40.608 s | 2,142,126,080 B | PASS |

The prior registered growth failures are resolved. Wide rebind medians are 0.096222, 0.943507, and
12.579421 seconds, with slope 1.058192 and a maximum adjacent ratio of 13.332625. Deep medians are
0.148808, 1.416401, and 13.587623 seconds, with slope 0.980258 and a maximum adjacent ratio of
9.593064. Both are below the unchanged 1.5 slope and 50 ratio ceilings. Every phase wall/RSS growth
check, every density timing check, every density correctness point, and both unchanged 300-second /
6-GiB absolute checks pass.

Issue #86's staged contract is therefore satisfied: all reported fields and ordering remain covered
by equivalence tests; exactly one fresh fingerprint is telemetry-visible per evaluated slot and
mutation-protected; drift remains on the general path and correct; each optimization has independent
wall/CPU/RSS/source evidence; cold end-to-end remains materialization-inclusive; lint, the full suite,
the complete mutation manifest, and the registered scale gate all pass. Remaining structure-map and
fixture-materialization opportunities are separately measured prospective work, not unresolved #86
acceptance defects.

## Post-stability mutation-campaign liveness

After the registered gate and issue #86 acceptance were stable, the shared mutation runner gained
observer-only liveness. The default remains quiet between events for short scopes, but any active
phase now publishes at five-second cadence. Each mutant reports `patch`, `test`, `restore`, and
`verify` transitions plus coordinate, label, scope, result, whole-mutant elapsed time, and separately
measured child-scope time. Heartbeats add child PID/status and age of the last captured output. Scope
output remains private to the runner's capture/tail and is never forwarded as telemetry. Timeout
publishes a distinct `watchdog-timeout` event. Every started campaign publishes exactly one terminal
`COMPLETE`, `FAILED`, `INTERRUPTED`, or `RESTORE_FAILED` event to stderr and, when selected, a
structured NDJSON progress log.

The heartbeat is emitted by a daemon observer thread that never writes production files or controls
classification. This keeps liveness active even if patch or restore stalls. The mutation thread alone
owns patching, child execution, classification, and byte restoration. A macOS pipe-lifecycle test
found and fixed a selector edge after this separation: child output is now drained nonblocking with a
250-ms process-state poll while preserving the existing process-group watchdog and bounded drain.
Wrapper interruption signals the runner, waits for its verified restore, exits 130 without a Python
traceback, and leaves the terminal progress record intact.

The shared runner is version 1.1.0. Its self-hunt artifact is
`s4_7_mutation_runner_self_hunt.json` (SHA-256
`e01287da3a7b8c8e1494239ab35cb8a3df215ec8cd2bfa950ee1910b1859907d`) and its progress log is
`c72f1dbdd7c91cf99585970fdecd5b60a56d7e1c560feb33c0e190cd49584dde`. All 58/58 runner mutants
were detected, zero survived or errored, restoration was byte-verified, 21 heartbeats were retained,
and the sole terminal event is `COMPLETE`.

The refreshed S4.7 production mutation manifest contains 131/131 detected mutants with zero
survivors/errors, byte-identical source restoration, and a green post-restore run. Its SHA-256 is
`1117bdbc1d65caf3f9191bf10964c434462d689681e5b81160419bddef0aef90`; the five-second progress
log is `c045665cb686598120070d93d879b5f04302466a48938958bf1afc8aff0aee19`. It retained 52
heartbeats across patch/test/verify activity and one terminal `COMPLETE` event. A separate deliberate
interrupt during development retained terminal `INTERRUPTED` with `restore_verified=true`, proving
that visible liveness does not weaken the existing restoration contract. This observability follow-up
does not change production rebind code, registered scale metrics, or the completed 300-second / 6-GiB
verdict.

## S4.7-E deep-evidence traversal resolution

The final carried INV-7 residual was resolved after issue #86 stability without changing its
fixture, measured operation, repetitions, statistic, or ceilings. The depth remains 3,000; the
fixture still contains 3,000 evidence entries, 6,000 projection nodes, and 4,501,500 decoded
witness references. The registered operation remains production `evidence_findings()` and the
acceptance limits remain a median of five at or below 2.0 seconds and a Python-allocation peak at
or below 512 MiB.

The former gate path independently walked every entry's descendants. The replacement performs one
iterative bottom-up projection pass, examining every node and child edge once and transferring a
completed child subtree set into its parent accumulator. For a fresh entry, exact equality of the
live `own` and `beneath` payload with the constructor-verified stored witness permits reuse of the
stored digest; this is byte-identical to rehashing the same canonical payload. Any unequal payload
is still hashed through THE canonical producer, preserving stale findings, live digest text,
ordering, diagnostics, and even hash-collision comparison behavior. Dangling, cyclic,
duplicate-edge, and multi-parent maps decline the batch path and retain the scalar error verbatim.

The regenerated source-locked artifact is `s4_7_priority5_perf_baseline.json` (SHA-256
`65e8c9a4b283ab4b299524bb717ec02df492dc8bf82a32653cfbefa1ca7bc412`). Its five wall samples are
0.163821, 0.156699, 0.146292, 0.146118, and 0.148400 seconds, for a 0.148400-second median. Every
allocation sample is 1,285,736 bytes. Both registered verdict fields are `true`, giving more than
13x wall-clock margin and using under 0.25% of the memory ceiling. Exact batch-versus-scalar
findings, one-visit work counts, scalar-walk exclusion, fresh-witness reuse, and all malformed-map
fallback classes are directly tested. The strict xfail is removed; INV-7 is now an ordinary passing
regression assertion.

The refreshed production mutation manifest is `s4_7_priority5_mutation_manifest.json` (SHA-256
`a89f2fc74b227041e5d16aab8c279eb8cf68d771f382fd62a033250610e37922`) and its five-second
progress log is SHA-256
`cd4db58a0d42766a86ae38b84a5b5c4de1a9154acfacd86ca89739a7d73454b1`. All 133/133 mutants
were detected with zero survivors or errors, including attacks that restore the per-entry scalar
walk, disable fresh-witness reuse, shrink the depth, and relax the ceiling. Restoration is
byte-identical, post-verification is green, 45 heartbeats were retained, and the sole terminal event
is `COMPLETE`. With no carried red remaining, the focused manifest command passes 438 tests and the
repository-wide default gate passes 1,980 tests with one registered scale test deselected, zero
xfails, and only the five pre-existing SWIG deprecation warnings. Ruff and `git diff --check` are
clean.
