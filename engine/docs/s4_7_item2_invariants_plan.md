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
- **Anchor-density knob (ties §8.4, the ratified DoD requirement):** a control that thins unique-in-both
  anchors (dilutes type-unique 3-grams) so INV-1 is exercised on **anchor-poor** input, not only PLL's
  anchor-rich end (71% type-unique 3-grams). As anchors thin, a false-bind must convert to **fail-loud**,
  not silent mis-bind — the correctness-at-density axis.

**Guard:** the identity map is the oracle; the mechanism is judged against it. If any invariant's "expected"
is ever computed from `rebind()`'s own result, the test is circular and void.

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
5. **INV-6, INV-7** — scale/evidence. **Overlap flag:** INV-6/INV-7's *red tests* can be written now
   against the cubic mechanism (item 2), but the *harness* they need is DoD item 4. Proposal: write the
   RED here (proves teeth), build the green-making harness in item 4. Confirm during review (§5).

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

## §5 Open sub-decisions surfaced for your review

1. **R-b token granularity** (DR-1's deferred sub-choice): char-level diff vs shingle-tokens vs
   tolerate-via-ratio. Which INV fixture drives the measured decision — INV-1's char-sub axis, or a
   dedicated micro-benchmark?
2. **INV-6/INV-7 ↔ item-4 overlap:** write the red scale/evidence tests here against the cubic mechanism
   (my proposal), or fold them entirely into item 4?
3. **Anchor-poor density target (§8.4):** what type-unique-3-gram % defines "anchor-poor"? PLL's rich end
   is 71%; the gate needs a low-density point — pick a target (e.g. ≤30%?) or sweep a curve.
4. **Fixture substrate:** synthetic-only for the invariants, or also a real-PLL re-extract? (Real-PLL
   re-extraction needs S4.6 — human-gated — so synthetic is the item-2 default; confirm.)
