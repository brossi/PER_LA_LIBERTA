# S4.7 item 2 — pre-registration bundle

**Status: authored + committed 2026-07-18, BEFORE any red run** — per the ceremony-budget ruling
(Ben, 2026-07-18; record in `../s4_7_external_review_dispositions.md`): the
commit-before-measurement act carries the anti-tuning function; values marked **JUDGMENT** are
disclosed for audit-on-pull. Every value here is fixed before the first measurement; changes
after any red run are visible diffed amendments with a dated rationale, and **the acceptance
bounds and ceilings only ever move via a dated amendment — never silently, never post-hoc to fit
a measurement** ([[feedback_no_cheating_results]]). Venue and required contents per
`../s4_7_item2_invariants_plan.md` §0 (ruled A5).

## 1. Target hardware/software profile

All registered numbers are for this profile; a different machine re-registers before running.

| axis | value |
|---|---|
| CPU | Apple M1, 8 cores |
| RAM | 8 GB |
| OS | macOS 26.5.1 (arm64) |
| Python | 3.13.0 (project venv via `uv`) |
| Load | interactive desktop, no other heavy load; wall-clock via `time.perf_counter` |

## 2. Fixture size-variable ledger (`L/K/A/T/D` — parent §5 as amended per B-6)

Every measured point reports all five and the family it came from; growth rules are stated
against a **named** variable, never a bare "N".

| var | meaning | family relationship (**JUDGMENT** — PLL-derived) |
|---|---|---|
| `L` | leaf nodes | free axis on wide shapes; `L = A / 40` (PLL: 4786 atoms / 120 nodes ≈ 40) |
| `K` | slots | `K = L` (one slot per leaf; slots-per-leaf held constant as size grows) |
| `A` | atoms | `A = T / 36` (PLL: 171,181 tokens / 4,786 atoms ≈ 35.8) |
| `T` | tokens | the primary growth axis for alignment/re-bind ops |
| `D` | tree depth | **wide** shape: `D = 4` (PLL-like shallow); **deep** shape: `D = L` (chain) |

Rationale: the ratios mirror the one real book the mechanism must serve (PLL), so synthetic
scale points stress size, not an alien shape. Deep-vs-wide results are reported separately
(parent §5: "say which each result speaks to").

## 3. INV-6 acceptance bundle (pre-registered, never baseline-derived)

- **Growth estimator:** OLS log-log slope of median wall-clock vs the named variable (`T` for
  re-bind/alignment ops; `L` for traversal/reference-integrity), over **≥3 sizes spanning ≥100×**
  (green target ladder `T ≈ 3.6·10⁴ / 3.6·10⁵ / 3.6·10⁶`, i.e. `A = 10³/10⁴/10⁵` — D35's tier is
  the top decade). `K` grows with `L` per the §2 ledger (stated per INV-6: K's behavior as N
  grows = proportional).
- **Acceptance rule (two-part; both must hold; JUDGMENT):**
  1. fitted slope **≤ 1.5** (sub-quadratic bar with margin: the anchored design's measured
     prototype exponent was ≈1.0; 1.5 sits decisively below quadratic while leaving headroom for
     log factors and constant-amortization noise on small points);
  2. every **per-adjacent-decade ratio ≤ 50×** (= 10^1.7; a pure 3-point fit is fragile — one
     anomalous point can hide in the slope; 10× would be exactly linear per decade, 100×
     quadratic).
- **Memory:** same two-part rule on peak memory (item-2 instrument: `tracemalloc` peak, ruled
  A1; item-3/4 durable gate re-registers for the RSS instrument per §2.6).
- **Repetition statistic (JUDGMENT):** **median of k = 5** runs per point (odd, cheap, robust to
  one GC/scheduler outlier on an interactive machine).
- **Phase honesty:** serialize / load / index / re-bind timed separately **and** end-to-end;
  fixture construction and phase completion asserted before any budget assertion.

## 4. INV-6 red sizes + calibration rationale

**Dated upward-only amendment — 2026-07-18, after the first diagnostic measurement and before
measuring any added point.** The original ladder below maps through §2 to
`(L, K, A) = (1, 1, 8) / (1, 1, 17) / (1, 1, 33)`. Because `K` therefore remains one, the
shipped assignment has only the whole-stream window at each point and the registered ladder does
not activate the multi-slot window enumeration whose growth it is meant to expose. The first run
was correspondingly too fast to discriminate the cubic defect. Exercising an invariant with a
degenerate constant-`K` family would be a false-green risk, not a permissible favorable result.

Per the already-registered upward-extension rule, the red ladder is extended—never reduced—to
**`T ∈ {300, 600, 1200, 2400, 4800}`**. The added values are fixed from the ledger before they are
measured: they produce `(L, K, A) = (2, 2, 67)` and `(3, 3, 133)` under nearest-integer fixture
rounding, so both the named token axis and proportional slot axis finally grow. Each leaf owns one
non-empty **contiguous** canonical-atom block in reading order; the scale family does not introduce
the separate non-contiguous-slot precondition while measuring assignment growth. All original
points remain in the artifact. The slope/ratio acceptance bounds, repetition count, instrument,
and target profile are unchanged; this amendment corrects fixture discriminating power only.

The red runs against the **shipped cubic `_Assignment`/`resolve_slot`** (O(K·N³)) before #48
deletes it. Two full decades of the cubic are infeasible (#48: tens of hours extrapolated at
PLL's T = 171k), so the red uses a calibrated smaller ladder:

- **Red ladder (JUDGMENT, upward-amended above):**
  `T ∈ {300, 600, 1200, 2400, 4800}` (family ratios per §2; ≥4 doublings).
- **Calibration rationale:** scaling the #33/#48 finding (tens of hours at T ≈ 1.7·10⁵) by
  (1200/171,181)³ puts the largest red point in the seconds-to-minutes range on the §1 profile —
  each doubling of a cubic multiplies cost ≈8×, so three points spanning 4× expose a fitted
  slope ≥ ~2.5, violating the registered slope ≤ 1.5 bound → RED for the named reason. If the
  largest point proves too fast to discriminate slope from noise, the ladder may be extended
  **upward** (a diffed amendment); red sizes are never tuned downward after a measurement.
- **Artifact discipline:** the red is captured as a reproducible baseline artifact (command,
  ladder, per-point `L/K/A/T/D`, medians, commit + implementation identity); durable tests
  target public named ops (`rebind()`, the public re-stamp path) so deleting the cubic does not
  delete the tests' meaning.

## 5. INV-7 ceiling (the evidence-op budget — INV-7's own number)

**Dated fixture clarification — 2026-07-18, before the first INV-7 measurement.** The deep
evidence family is the §2/B-7 **isolated topology core**, not the PLL-density rebind family: a
depth-3,000 container backbone has one terminal machine leaf at each level, and each leaf owns one
one-token atom. Its reported ledger is therefore `L = K = A = T = D = 3,000`. This keeps both
causes visible—the live gate walks `Θ(D²)` descendants and the decoded evidence witnesses contain
`Θ(D²)` atom-id references—without multiplying that already-quadratic input by PLL's 40
atoms-per-leaf density. Applying every wide-family density ratio here would materialize about
180 million decoded witness ids before the named op and would measure fixture inflation rather
than the isolated deep-topology defect. The artifact reports node count and serialized/decoded
input sizes separately, as B-7 requires. The ceiling, repetition count, and instrument are
unchanged.

- **Ceiling (JUDGMENT): 2.0 s wall-clock (median of 5) and 512 MB `tracemalloc` peak** for the
  named evidence op (`evidence_findings` over the registered deep-chain fixture).
- **Derivation — independent of any measured baseline:** D35's CLI rationale (a CLI pays
  load+op cost every invocation; the standard interactive tolerance for a single CLI verb is
  ~1–3 s) → 2.0 s midpoint for the single named op, leaving invocation headroom. 512 MB = 1/16
  of the §1 profile's 8 GB — an op that takes a quarter of a small machine's RAM for one
  evidence query fails the same interactivity rationale.
- **Disclosure (candor about independence):** the tracker's S4 row records an existing 3.5 s
  measurement of `evidence_findings` on a 3000-deep chain. The 2.0 s number was derived from the
  CLI rationale above, not from that measurement — but the author had seen it. The registered
  ceiling predicts RED on the shipped O(N²) mechanism either way; independence is carried by the
  derivation being stated and checkable, and by the ceiling never moving post-measurement.
- **Fixture (per spec INV-7 + B-7):** deep synthetic chain, **`D = 3,000`, built in memory**
  (bypassing the persisted-sidecar path — stated here because the `_MAX_RUN_EXPANSION`
  1,000,000-id cumulative decode budget makes a persisted full-coverage deep chain unloadable at
  larger D; the bypass is part of the registered method, not a shortcut discovered later).
  Pre-flight proof asserts construction / schema validation / serialization / recursion limits /
  decode budget **before** the measured op. Complexity is reported against **input bytes and
  node count separately**.
- **End states (PR-4):** green, or honestly-UNRESOLVED via DR-6 characterize-and-defer with a
  named follow-up issue and a single-purpose `xfail(strict=True, reason=<issue>)` test. The
  ceiling never moves.

## 6. Heavy re-segmentation floor

**≥30% of included canonical atoms undergoing a realized re-segmentation** in the gating case —
the spec's placeholder (§1.4.3), registered here as-is. Merge participation counts both source
atoms; net-zero events are reclassified no-ops by the §1.3 law family. Tunable **up** for
exploration; lowering is a visible, diffed change, never silent.

## 7. DR-3 lock record (pointer convention)

The DR-3 confidence gate is **locked** by the item-3 run manifest at
`docs/probes/s4_7_priority5_mutation_manifest.json`, SHA-256
`dd584ffb90d1db4f166df7006cef8745d80513ddd09713fd6217cdcacb51a5c8`. The hashes, fixture
matrix, seeds, modes, normalized 136-mutant table, zero carried residuals, and green command live
once in that manifest (spec §0); this document records only the immutable pointer. The manifest
intentionally excludes this pointer document from its own source-identity set to avoid a circular
content hash.
