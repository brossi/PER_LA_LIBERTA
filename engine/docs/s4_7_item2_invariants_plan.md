# S4.7 item-2 — the red-first invariant harness (build scaffold)

**Status: DRAFT for your review — not code, not committed.** Scaffold for DoD item 2 of the RATIFIED
`s4_7_plan.md` rev 3. Author it, review it inline (`@@@@@@` / `======`), then build.

**Parent authority:** `s4_7_plan.md` (RATIFIED rev 3, Ben 2026-07-09) §4 (the seven invariants, quoted
verbatim below), §2 (the mechanism the invariants gate), §8 DoD item 2. Discipline:
[[feedback_red_first_tests]], [[feedback_adversarial_audit_cadence]], [[feedback_mutation_pyc_staleness]],
[[feedback_no_cheating_results]], [[feedback_validate_bindings]].

---

## §0 What item 2 is, and its one keystone

DoD item 2 verbatim: *"INV-1…INV-7 red-first (drift generator built so INV-2/INV-3 can be seen red)."*

Red-first (the binding rule): **every invariant is SEEN RED on a planted violation before the mechanism
makes it green.** A test never seen red is a claim, not a check. The mechanical form is the mutation
hunt (mutate the guard the invariant protects; the test must re-red).

**Keystone:** per ratification, **DR-3's confidence gate is not locked as proven until INV-1
(never-a-false-bind) is seen red-then-green.** So INV-1 is not one of seven equals — it is the gate that
converts DR-3 from "build direction" to "locked." Item 2 is, first, the machine that makes INV-1 real.

---

## §1 Component 0 — the drift generator (the shared prerequisite)

The single most load-bearing build in item 2. INV-1/2/3/4 all consume it; DoD item 2 explicitly gates on
it ("drift generator built so INV-2/INV-3 can be seen red"). It reuses the prototype's proven approach
(`perturb_witness` + the copy2-derivation oracle) — a settled design direction, now ported into a test
fixture rather than a scratchpad.

- **Input:** a canonical atom stream + its witnesses (a synthetic fixture, and PLL as a real anchor.)
- **Perturbation classes** — each independently toggleable and composable, matched to the plan's drift
  model (§2.5 R-a/R-b):
  - **char-substitution** (OCR-class, *in-token* → the whole token becomes `replace`, coarsening
    alignment — the R-b axis).
  - **atom drop / atom insert.**
  - **atom duplication** (dittography).
  - **re-segmentation:** split one atom → two, merge two → one (the D25 axis; diff models a split as
    insert-adjacent-to-`equal`).
  - **local reorder / moved block** (R-a — the *weakest* axis; INV-3's target).
- **Output:** the perturbed stream **plus a recorded identity map** `old-atom-id ↔ fresh-atom-id`
  (∅ for a dropped or moved atom). **Ground truth by construction — never derived from the mechanism's
  output.** This is what every oracle below reads.
- **Anchor-density knob (ties §8.4, the ratified DoD requirement) — SWEEP, not a point [§5.3 RULED 2026-07-09]:**
  a control that thins unique-in-both anchors (dilutes type-unique 3-grams), swept across **~6 points from
  PLL's rich end (71% type-unique 3-grams) down to ~10–15%** (verse, fragmentary/OCR-short atoms, dense
  repetition are the natural low-density sources; floor + point-count are tunable). **Gate criterion —
  directional and un-gameable:** the **wrong-content false-bind rate stays at the S5.2-owned floor
  (≈0 / within the characterized residual) across the entire sweep**; only the **abstention/fail-loud rate**
  is allowed to rise as density drops (INV-1's fail-loud-not-silent promise; DR-9's split — S5.2 owns the
  rate). Report the whole curve in `s4_7_scale.md`. A single cherry-picked low point is rejected.

**Guard — the identity map is the oracle for the *conditional property*, NOT a deployment-correctness
certificate [§5.4 RULED 2026-07-09, Ben's caveat]:**
1. **Not circular.** No invariant's "expected" may be computed from `rebind()`'s output — that is circular
   and void.
2. **Scope of proof.** "All synthetic invariants green" proves the invariant properties *conditional on the
   modeled drift* — never "correct on real re-extraction." The real-PLL re-extract (post-S4.6) stays a
   **required** confidence gate, not an optional bonus.
3. **Oracle independence + teeth.** The identity map must be independent of the mechanism's *design
   assumptions*, not just its output. A generator that emits only diff-friendly drift makes INV-2 pass
   **vacuously** — so it **must** include adversarial drift the mechanism could genuinely fail on
   (reorder/move, heavy re-segmentation), or the invariants have no teeth.
4. **Drift-model fidelity is itself unvalidated.** Whether the perturbation model resembles real
   re-extraction is an assumption checkable only against real data — the copy2-derivation PLL proxy now
   (real distribution, softer oracle), the real re-extract post-S4.6 (highest fidelity). An **open
   assumption**, not a settled fact.

---

## §2 The seven invariants (property / oracle / fixture / red-first violation / DR gated)

> §4 text is quoted verbatim in each **Property** line; the rest is the build spec.

### INV-1 — never a false bind  *(LOAD-BEARING — unlocks DR-3)*
- **Property (§4):** "over randomized drift fixtures incl. planted repeated passages (within- and
  cross-container), the bound set ⊆ a brute-force alignment oracle's bound set; a non-unique boundary
  anchor forces `ambiguous`, never a lone bind. Oracle defined from fixture ground truth (planted
  positions), not from the mechanism's own output. Mutation-hunt primary."
- **Oracle:** planted positions from the drift generator's identity map + a brute-force alignment over the
  fixture. Bound set ⊆ oracle's bound set.
- **Fixture:** drift + **planted repeated passages** (within-container AND cross-container) — the
  repeated-content case a greedy diff mis-aligns. Plus the **anchor-poor** variant (§8.4).
- **Red-first:** plant a passage that recurs verbatim; a mechanism **without** the boundary-anchor
  uniqueness guard (DR-3) binds the wrong copy → **RED** against the planted oracle. Add the guard →
  GREEN. Mutation-hunt primary: mutate the uniqueness check (accept a non-unique anchor) → must re-RED.
  Anchor-poor variant: as density drops, wrong-binds must become `ambiguous`/fail-loud, not silent.
- **Gates:** **DR-3 lock.** This invariant is the ratification condition.

### INV-2 — binds under drift (anti-inertness)  *(INV-1's counterweight)*
- **Property (§4):** "on real re-segmentation / char-sub fixtures the mechanism binds the nodes it should
  (a fail-loud-on-everything mechanism fails this). Scoped as a by-construction existence check, NOT a
  rate over a realistic model — that is S5.2."
- **Oracle:** the identity map — which nodes *should* survive the perturbation and bind.
- **Fixture:** drift generator at moderate perturbation (char-sub + re-segmentation, no moves).
- **Red-first:** a stub that binds nothing (or over-fail-louds) → **RED**. This is the guard against
  "pass INV-1 by never binding." INV-1 ∧ INV-2 together = correct *and* non-inert.
- **Gates:** the mechanism is not inert. (Existence check only — the *rate* is S5.2, not here.)

### INV-3 — reorder/move fails loud, not silent
- **Property (§4):** "a moved block does not silently mis-project (R-a)."
- **Oracle:** identity map flags moved atoms; expected outcome = a fail-loud finding, never a bind to the
  wrong location.
- **Fixture:** drift generator with a moved block (R-a, the weakest axis).
- **Red-first:** a mechanism that greedily projects the moved node onto a wrong span → **RED** (silent
  mis-projection caught against ground truth). Fail-loud → GREEN.
- **Gates:** R-a honesty.

### INV-4 — boundary-in-edit-block
- **Property (§4):** "a node boundary landing in a `replace/insert/delete` block gets a fail-loud finding
  unless the confidence gate independently confirms it (DR-2)."
- **Oracle:** opcode classification of the boundary token's block (`equal` vs not).
- **Fixture:** drift placing an edit exactly at a node boundary.
- **Red-first:** a mechanism that silently invents a fresh boundary inside a non-`equal` block → **RED**.
- **Gates:** **DR-2.**

### INV-5 — mode orthogonality
- **Property (§4):** "per-mode gating matches the S5.1 mode fixtures."
- **Oracle:** the existing S5.1 mode fixtures/contracts (`geometry-primary` / `geometry-tie-break` /
  `no-geometry`).
- **Fixture:** reuse S5.1's mode fixtures (no new fixture; DR-5 continuity).
- **Red-first:** a mechanism that ignores mode (e.g. geometry rescues a sub-τ span) → **RED** against the
  S5.1 contract.
- **Gates:** **DR-5** (contract preservation).

### INV-6 — scale gate  *(straddles item 4 — see §3)*
- **Property (§4):** "named ops' wall-clock + peak-memory sub-quadratic across ≥2 decades incl.
  serialize+load+index; small always-on + 10⁵ nightly."
- **Oracle:** a growth-ratio ceiling (wall-clock + `tracemalloc` peak) across ≥2 size decades.
- **Fixture:** the size-parameterized scale fixture (**new work**, DR-7 — reuses the store *primitives*,
  not an existing fixture) + the anchor-poor fixture (§8.4).
- **Red-first (elegant):** run the invariant against the **current O(K·N³) `_Assignment`** → **RED**
  (super-quadratic). The shipped cubic DP *is* the planted violation — the cleanest possible red-first,
  and it proves the gate has teeth before half B replaces the mechanism.
- **Gates:** the scale gate + §8.4 correctness-at-density.

### INV-7 — evidence composite
- **Property (§4):** "measured on a deep map at scale; over budget → algorithm fixed or scoped follow-up;
  ceiling not moved."
- **Oracle:** the budget ceiling on `evidence_findings`/`_restamp` over a deep chain.
- **Fixture:** a deep synthetic chain (PLL is shallow, depth 4 — this is a synthetic worst case; state so).
- **Red-first:** the O(N²) deep-chain on a deep fixture → **RED** against budget. Per **DR-6
  (characterize-and-defer):** the RED is characterized; either fixed (Merkle/rolling subtree digests) or
  a scoped follow-up is opened — **never relax the ceiling** ([[feedback_no_cheating_results]]).
- **Gates:** **DR-6.**

---

## §3 Build order + dependencies

1. **Component 0 — drift generator + identity map** (blocks INV-1/2/3/4). Build first.
2. **INV-1 + INV-2 together** — the correct/non-inert pair; INV-1 is the DR-3 keystone.
3. **INV-3, INV-4** — drift-honesty + boundary discipline.
4. **INV-5** — mode contracts (reuse S5.1 fixtures).
5. **INV-6, INV-7** — scale/evidence. **[§5.2 RULED 2026-07-09] Write the RED tests HERE (item 2), against
   the shipped cubic mechanisms, BEFORE half-B lands.** The real O(K·N³) `_Assignment` (INV-6) and the O(N²)
   deep-chain (INV-7) *are* the planted violations — the honest red-first. **This is a now-or-never window:**
   `#48` deletes `_Assignment`, after which INV-6/7 could only red against a contrived slow-mutant. Item 2
   therefore builds the **minimal** scale scaffolding (size-parameterized fixture + `perf_counter` /
   `tracemalloc` wrapper) needed to see those reds; **item 4 productionizes it** (CI tiers, 10⁵ nightly, the
   full anchor-poor sweep) — item 4 is *not* "build from zero." The DoD split is pinned in `s4_7_plan.md` §8
   so the two items don't double-count.

Mutation hunt at green; **wide+narrow adversarial audit + Rule-A delta re-audit before commit** (§4 +
[[feedback_adversarial_audit_cadence]]). **INV-1 + INV-2 + INV-3 are the audit's primary target** (correct,
non-inert, drift-honest).

---

## §4 Anti-cheating guards (baked into the harness from line 1)

- Every invariant **seen RED** before green — planted violation or mutation; a never-red test is a claim.
- Oracles are **ground-truth-by-construction** (identity map / planted positions), never `rebind()`'s output.
- **pyc staleness:** the mutation cycle purges `__pycache__` / sets `PYTHONDONTWRITEBYTECODE=1` — a stale
  `.pyc` serving pre-mutation bytecode is a false GREEN ([[feedback_mutation_pyc_staleness]]).
- **`pytest.raises(match=)`** matches the raise's wording, never the feature word or `tmp_path`
  ([[feedback_pytest_match_leak]]).
- **No `skipif`-masking;** assert referents actually resolve/import ([[feedback_validate_bindings]]).

---

## §5 Sub-decisions — all RULED (Ben, 2026-07-09)

1. **R-b token granularity [RULED]:** **default tolerate-via-ratio; do not pre-build char-level.** Add a
   *boundary char-sub axis* to INV-1/INV-2 (a char sub landing on a boundary token) as the measurement
   instrument. Escalate to a **coarse-to-fine hybrid** (token alignment + char-level refinement *only* at
   boundaries landing in `replace` blocks) **iff** the measured INV-2 fail-loud rate on trivial in-token
   drift is unacceptable. Deferral-for-information (the invariant fixture *is* the decision instrument),
   not effort-saving; avoids a ~5–6× N blow-up on spec.
2. **INV-6/INV-7 ↔ item-4 overlap [RULED]:** write the red scale/evidence tests **here (item 2), against
   the shipped cubic mechanisms, before half-B lands** (now-or-never — `#48` deletes `_Assignment`). Item 2
   builds the *minimal* harness to see those reds; **item 4 productionizes** (CI tiers, 10⁵ nightly, full
   sweep). DoD wording split in `s4_7_plan.md` §8 so the items don't double-count. (See §3 item 5.)
3. **Anchor-poor density [RULED]:** **sweep, not a point** — ~6 points from 71% down to ~10–15%; gate
   criterion = **false-bind rate ≈ 0 (S5.2 floor) across the whole sweep, abstention rate allowed to rise**.
   (Folded into §1 anchor-density knob.)
4. **Fixture substrate [RULED, with caveat]:** **synthetic-only for the item-2 invariants** — but Ben's
   caveat governs: the synthetic identity map is the oracle for the *conditional property*, **NOT a
   deployment-correctness certificate.** The four-part guard (not-circular / scope-of-proof / oracle-
   independence-and-teeth / drift-fidelity-unvalidated) is in §1. PLL enters only as a real-distribution
   *confidence* proxy (copy2-derivation); a **true real-PLL re-extract is a required post-S4.6 gate**, not
   optional.
