# S4.7 — scale check (D35), and the re-bind re-architecture it forces (plan — rev 3)

**Status: RATIFIED rev 3 — Ben, 2026-07-09.** All decision rows (DR-1…DR-9) and governance forks
(G-1…G-4) are ruled (§3 ledger); build (DoD §8 items 2→6) is greenlit. **One conditional:** DR-3 (the
load-bearing confidence gate) is ratified as *build direction*, **not locked as proven** until INV-1
(never-a-false-bind, over drift + planted repeated passages) is seen red-then-green. Rev 3 replaced
rev 2's mechanism wholesale after a second five-lens adversarial pass (2026-07-08) demolished rev 2's
*candidate-index-as-uniqueness* approach, and after Ben's steer to **stop hand-rolling and reach for the
solved-problem tooling** ([[feedback_solved_problem_first]]). `rebind.py` may now be modified via the
S5.1-remediation route (G-1).

**Revision history (recorded, not hidden):**
- **rev 1** — banding a global monotone-tiling DP. Rejected: a band prunes candidates, but re-bind is a
  *uniqueness* test that needs the full set; the §1 baseline was shape-only (timed construction, missed
  the cubic `resolve_slot`).
- **rev 2** — per-container decomposition + a fingerprint-anchored candidate index. Rejected: the index
  can't replace the tiling-feasibility constraint that makes uniqueness bounded; "clustering" is a band
  by another name (a hidden calibration knob); top-down committed recursion adds a *confident*
  false-bind under drift (worse than fail-loud); the contiguity premise was verified only vacuously.
- **rev 3 (this)** — recognizes the task as a **solved problem: sequence alignment + annotation
  transfer** (a.k.a. robust annotation re-anchoring / diff-based offset projection). The bespoke
  `SlotFingerprint` + monotone-tiling DP was a worse reimplementation of `diff`. Rev 3 aligns the two
  streams with **off-the-shelf tooling** (`rapidfuzz` — already a dep — or `difflib` — stdlib) and
  projects each node's span through the alignment, with a **post-alignment confidence gate** for
  fail-loud.

**Spec authority:** tracker row `S4.7` (`| S4.7 |`) → `ENGINE_STRUCTURE_PLAN.md` §3.5 + **D35** + DoD
A-7 (line 813) → `s5_1_plan.md` §1.3 (**whose complexity claim this task falsifies — §7**) → this
plan. Evidence anchor: `spike/document-structure`, HEAD `f1649a4`; cites + empirical checks verified on
disk **2026-07-08**.

**Deps (MET):** S4.1, S4.2, S5.1 (the op under test). Real-PLL rebind additionally needs S4.6
(human-gated). Scope `BUILD`. Issue **#33**. **Tooling verified present (2026-07-08):**
`rapidfuzz>=3.14.3` is already a core dependency; `rapidfuzz.distance.{Indel,Levenshtein}.opcodes`
runs on **token lists** and returns `equal/insert/delete/replace` opcodes with src/dest ranges;
`difflib` (stdlib) `get_opcodes()` runs in ms on near-duplicate 10³–10⁴ token streams.

---

## §0 What S4.7 is — and the reframe

S4.7 is D35's scale gate: prove the engine's named machine ops (**tree traversal**,
**reference-integrity resolution**, **re-bind lookup**) stay **sub-quadratic** 10⁴→10⁵ leaf nodes,
under a **wall-clock + peak-memory ceiling including serialize + load + index-build**, machine ops only.
Ops 1 & 2 pass linear (§1). Op 3 (re-bind) is cubic and cannot run at book scale — the defect the gate
exists to catch. So S4.7 has two halves:
- **(A) the scale gate** — the measurement harness + CI tiers;
- **(B) the re-bind re-architecture** — replace the bespoke matcher with **diff-based annotation
  re-anchoring**.

**The reframe (the heart of rev 3).** Re-bind is: *"transfer stored span annotations from an old atom
sequence onto a regenerated near-duplicate of it."* That is a solved problem in two mature domains —
**sequence diff/alignment** (`git`/`difflib`/Myers/patience/`rapidfuzz`) and **robust annotation
re-anchoring** (W3C Web Annotation selectors + fuzzy re-locate). The bespoke DP fused three separable
concerns; the mature approach keeps them apart, which is why it is both faster and correct:

1. **Alignment** — which fresh region corresponds to which old region → **off-the-shelf diff opcodes**.
2. **Projection** — map each node's old token-span through the opcodes to a fresh span → trivial.
3. **Confidence / fail-loud** — is a node's projected span trustworthy → a **post-alignment** per-node
   check (match ratio + boundary-anchor uniqueness), *not* a bespoke uniqueness-constrained DP.

The genuinely-novel design surface shrinks to **(3)** — layers (1)+(2) are library + arithmetic. Rev 3
therefore specifies (3) carefully; that is where the last two revisions hid their unsoundness.

---

## §1 The corrected baseline (probe, 2026-07-08; triple-confirmed)

Ops 1 & 2 — `validate_reference_integrity`/`_position_paths`: **LINEAR** (~2.0×/2× to 40k). PASS.

Op 3 — the shipped `_Assignment` DP: **CUBIC** (independently reproduced 3×: me, and two reviewers).
`resolve_slot` (called K times, `rebind.py:837-838`) dominates construction by ~10³–10⁴×; the O(N²)
window scan (`672-683`) × per-window re-shingle (`589-598`) gives O(K·N³). Measured resolve: ~1.4 s /
17 s / 163 s at N=100/200/400 (~10×/2×); at real PLL N=4786 this extrapolates to **tens of hours**.
The op cannot run on the book. **(B) is mandatory.**

**Contrast (verified this session):** `difflib.SequenceMatcher(...).get_matching_blocks()` on drifted
token streams: **2.7 / 9.8 / 19.5 ms at N=2000/4000/8000** — near-linear on near-duplicate content.
Diff is the right complexity class by construction.

---

## §2 The re-architecture (B): diff-based annotation re-anchoring

### §2.1 Layer 1 — alignment (off-the-shelf)

- Materialize the **old** canonical included stream and the **fresh** one as **token lists** via the
  shared `normalize_tokens` (the same normalizer the fingerprint uses, so alignment and scoring agree).
  Each token carries a back-pointer to its atom id + intra-atom offset.
- Compute alignment **opcodes** old↔fresh. **Tool (DR-1, [review]):** default `rapidfuzz.distance`
  (`Indel.opcodes` — insert/delete/equal — or `Levenshtein.opcodes` with substitution) — already a dep,
  C++-fast, opcodes on lists (verified). `difflib.get_opcodes()` is the zero-dep stdlib fallback. Both
  return `(tag, old_lo, old_hi, new_lo, new_hi)` blocks.
- **No dependency added** (rapidfuzz present; difflib stdlib) — satisfies Principle 2.

### §2.2 Layer 2 — projection (arithmetic)

Each node owns an old atom-span → an old **token**-span `[t0, t1)`. Map each boundary through the
opcodes to a fresh token index, then back to a fresh atom span:
- A boundary inside an **`equal`** block maps exactly (offset preserved).
- A boundary inside a **`replace`/`insert`/`delete`** block is *ambiguous by construction* — the old
  position has no exact fresh image. **Rule (DR-2, [review], fail-loud-biased):** a node whose
  **boundary** lands in a non-`equal` block does not get a silently-invented fresh boundary; it is a
  `below-threshold`/`ambiguous` finding unless the confidence gate (§2.3) independently confirms the
  span. Never round a boundary into a neighbor's atoms (the R2 discipline).

### §2.3 Layer 3 — confidence / fail-loud (THE design surface)

Alignment gives a *candidate* fresh span per node; binding it requires two independent confirmations,
both cheap post-checks:

- **Content ratio ≥ τ.** Score the candidate fresh span against the node's stored fingerprint
  (`slot_similarity`, unchanged) — reuse S5.1's τ + the closed reason enum. `< τ` → `below-threshold`.
- **Boundary-anchor uniqueness (the repeated-content guard).** A greedy diff can mis-align a passage
  that recurs (the classic diff failure). Guard it the W3C-robust-anchoring way: each node stores
  **boundary anchors** = a short **prefix+exact+suffix** shingle context at each end (richer than a
  bag-of-shingles — the design lesson from rev 2's failure). A bind requires each boundary anchor to
  be **unique in both** the old and fresh streams (an inverted shingle→positions index, built once,
  gives this in O(1) per anchor). Non-unique anchor → `ambiguous` (the diff's alignment there is not
  trustworthy). **This is where uniqueness is enforced — globally, once, on anchors — replacing the
  bespoke tiling's whole-stream uniqueness count** without its O(N³) cost.

Uniqueness is thus a property of **anchors**, computed once over the whole stream — so it is *not*
subject to a span/cluster/band parameter (rev 1/rev 2's fatal knob). The only tunable is τ, which is
**S5.2's** to calibrate (§6). No new calibration surface.

### §2.4 The three geometry modes + the S5.1 contracts (preserved)

- **Modes** re-express onto the projected span: `geometry-primary` pins the projected fresh span to the
  node's `region.page` (a projected span off-page → fail-loud); `geometry-tie-break` uses geometry only
  to disambiguate a non-unique anchor (never to rescue a sub-τ span); `no-geometry` = content + anchors
  only. Read from `manifest.segmentation.geometry_mode` as S5.1 does.
- **Preserved unchanged:** `node_id` identity; the non-raising `rebind()` + strict `assert_all_bound`;
  the **closed reason enum** (`zero-candidate | ambiguous | below-threshold | missing-anchor |
  stale-decision | global-conflict`) — diff/projection outcomes map onto it; the **re-stamp protocol**
  (mechanical `extent_digest` re-stamp on bound nodes, `decision_digest` never machine-refreshed); the
  `RebindContext` dual-hash baseline; `RebindResult`/`RebindReport`.
- **Replaced:** `_Assignment`, `_prefix_ways`/`_suffix_ways`, `resolve_slot` (the O(N³) DP). The
  stored-anchor shape is **enriched** (prefix/suffix context added to the fingerprint) — a v2→v3 schema
  touch, in the still-open schema window; call it out for G-3.

### §2.5 Honest risk register (the axes a third pass should press)

Rev 3 is a standard technique, but it has real edges — named so the adversarial pass targets them, not
so they're hidden:

- **R-a: drift-model mismatch.** Diff's edit model is insert/delete/(replace). OCR/cleanup drift is
  mostly that — **but re-atomization (split/merge) and local reorder are not.** A split atom (one old
  token → two fresh) shows as insert-adjacent-to-equal (projects fine). A **moved block** shows as
  delete+insert → the moved node's correspondence is *lost* → it should fail loud (acceptable), but
  verify it does not silently mis-project. Reorder is the weakest axis; INV must exercise it.
- **R-b: token granularity.** A char-sub *inside* a token makes the whole token `replace`, coarsening
  the alignment. Mitigation options ([review]): char-level diff, or shingle-tokens, or tolerate via the
  ratio gate. Decide on measured behavior.
- **R-c: contiguity/interleaving** (the cross-cutting question, unresolved since rev 2). A node's span
  is defined by its boundary anchors; an **interleaved** container (embedded letter, footnotes) has no
  single contiguous token span, so boundary-anchor projection under-specifies it. **This is orthogonal
  to the matcher** and must be ruled explicitly (G-4): either (i) enforce "container subtree = a
  contiguous included span" as a validated map precondition (reject interleaved maps at authoring), or
  (ii) extend projection to multi-interval spans. PLL's frozen map is contiguous (but only vacuously —
  it has no embedded-letter node), so (i) is viable for PLL now; the engine-general answer is a ruling.
- **R-d: the `evidence_findings` / `_restamp` deep-chain O(N²) is a SEPARATE sub-problem** — unaffected
  by the matcher choice, likely needs its own standard answer (Merkle/rolling subtree digests). §2.7.

---

## §2.6 Complexity + memory

- Alignment: `rapidfuzz`/`difflib` — near-linear on near-duplicate streams (verified ms); worst case
  O(N²) but the input is a near-duplicate by construction. INV-6 measures it.
- Projection + confidence: one pass over opcodes + O(1)-per-anchor index lookups → **O(N)**.
- Memory: replaces the O(K·N) DP matrices (which **OOM at 10⁵**, rev 1/2 confirmed) with O(N) token
  lists + O(N) anchor index. `tracemalloc` measures it (INV-6).

## §2.7 The evidence-composite hot path (separate, honestly open)

`evidence_findings`/`_restamp_evidence` are O(entries × subtree); on a **deep** chain Σ|subtree| =
O(N²), and `extent_digest` hashes the materialized sorted union → **no digest-preserving O(N) fix** by
naive memo. Candidate standard answer: **Merkle/rolling subtree digests** (a node's digest from its
children's digests) — investigate. Decide (DR-6) whether #33 closes this or characterizes-and-defers on
the measured number ([[feedback_deferral_for_information]]); **never relax the ceiling**
([[feedback_no_cheating_results]]). Real books are shallow (PLL depth 4) so the pathology is a synthetic
worst case — state which shape each gate result speaks to.

---

## §3 Decision ledger (rev 3)

| # | Decision | Disposition |
|---|---|---|
| DR-0 | **Direction:** solved-problem tooling (diff-based re-anchoring), not a bespoke matcher | **[Ben-ruled]** 2026-07-08 (the reframe steer; the specific mechanism below is [review]) |
| DR-1 | Alignment tool = `rapidfuzz.distance` (present) default; `difflib` (stdlib) fallback | **[Ben-ruled] 2026-07-09** (Indel-vs-Levenshtein variant deferred to the R-b measured decision) |
| DR-2 | Boundary-in-non-`equal`-block → fail-loud-biased finding, never a silently-invented boundary | **[Ben-ruled] 2026-07-09** |
| DR-3 | Confidence gate = ratio ≥ τ **and** boundary-anchor uniqueness in both streams (§2.3) | **[Ben-ruled] 2026-07-09 — build direction only; NOT locked as proven until INV-1 (never-a-false-bind, over drift + planted repeated passages) is seen red-then-green** (load-bearing) |
| DR-4 | Stored anchors enriched to prefix+exact+suffix context (schema v2→v3 touch) | **[Ben-ruled] 2026-07-09** (schema bump = G-3, approved) |
| DR-5 | Modes + S5.1 contracts (reason enum, re-stamp, non-raising) preserved (§2.4) | **[Ben-ruled] 2026-07-09** |
| DR-6 | evidence-composite deep-chain: fix (Merkle/rolling) vs characterize-and-defer, on the number | **[Ben-ruled] 2026-07-09 — characterize-and-defer**: measure the deep-chain number at scale, **never relax the ceiling**; open a follow-up only if the synthetic worst case proves it matters |
| DR-7 | Scale fixture built on the S1.5 store round-trip primitives (not a new persistence path) | **[Ben-ruled] 2026-07-09** (framing pinned: the store *primitives* are reused; the scale fixture itself is **new work**, §5) |
| DR-8 | CI: always-on small ratio + `@pytest.mark.scale` 10⁵ nightly | tracker-fixed |
| DR-9 | **Zero-false-bind ownership:** S4.7 ships the abstention/fail-loud *mechanism* (`below-threshold`/`ambiguous` reason enum + `assert_all_bound`→`RebindError`); **S5.2 owns the τ calibration that drives the residual to zero.** S4.7 DoD = strict-with-characterized-residual (INV-1 by construction + every survivor magnitude/foreign-content-detectable), **not literal zero** (§8.3). Safe: no consumer of binds exists yet — only `tests/unit/test_rebind.py` calls `rebind()`, no `steps/*.py` imports `engine.structure`, no S5.2 module. Split already encoded in `rebind.py` `RebindPolicy` ("S5.1 ships a default; S5.2 calibrates"). Wiring obligation: any future consumer of bound spans runs post-S5.2 or via the strict `assert_all_bound` path. | **[Ben-ruled] 2026-07-09** (consumer trace this session) |

**Governance forks — all resolved (Ben, §7):**
- **G-1 [RULED 2026-07-09]:** rev 3 replaces the whole S5.1 matcher → **routed as S5.1 remediation, a new issue** (referenced by #33), not folded into #33's scale-check scope — so the provenance that S5.1's shipped mechanism was replaced stays visible.
- **G-2 [LANDED 2026-07-09]:** the `s5_1_plan.md` §1.3 falsified-claim correction — applied (commit `7e5d612`).
- **G-3 [RULED 2026-07-09]:** the schema v2→v3 anchor-enrichment touch → **bump to 3** (window open; only internal fixtures + the PLL probe pin v2; migrate them, no v2/v3 dual-support).
- **G-4 [RULED 2026-07-09]:** the R-c contiguity ruling → **adopt (i) now** — enforce "container subtree = one contiguous included span" as a fail-loud validated authoring precondition; **defer (ii)** multi-interval spans for information until a genuinely interleaved book constrains the design.

---

## §4 Red-first invariants

- **INV-1 (never a false bind):** over randomized drift fixtures incl. planted repeated passages
  (within- and cross-container), the bound set ⊆ a brute-force alignment oracle's bound set; a
  non-unique boundary anchor forces `ambiguous`, never a lone bind. Oracle defined from **fixture
  ground truth** (planted positions), not from the mechanism's own output. Mutation-hunt primary.
- **INV-2 (binds under drift — anti-inertness):** on real re-segmentation / char-sub fixtures the
  mechanism **binds** the nodes it should (a fail-loud-on-everything mechanism fails this). *Scoped as a
  by-construction existence check, NOT a rate over a realistic model — that is S5.2.*
- **INV-3 (reorder/move fails loud, not silent):** a moved block does not silently mis-project (R-a).
- **INV-4 (boundary-in-edit-block):** a node boundary landing in a `replace/insert/delete` block gets a
  fail-loud finding unless the confidence gate independently confirms it (DR-2).
- **INV-5 (mode orthogonality):** per-mode gating matches the S5.1 mode fixtures.
- **INV-6 (scale gate):** named ops' wall-clock + peak-memory sub-quadratic across ≥2 decades incl.
  serialize+load+index; small always-on + 10⁵ nightly.
- **INV-7 (evidence composite):** measured on a **deep** map at scale; over budget → algorithm fixed or
  scoped follow-up; ceiling not moved.

Mutation hunt at green; wide+narrow adversarial audit + Rule-A delta re-audit before commit. INV-1 +
INV-2 + INV-3 together are the audit's primary target (correct, non-inert, drift-honest).

---

## §5 Scale-gate harness (A)

Size-parameterized fixture persisted through the S1.5 store (`save_stream`/`load_stream`) so load/index
cost is real; measure re-bind on **deep** and **wide** shapes (say which each result speaks to). Named
ops timed with serialize+load+index inside the span; `tracemalloc` peak; `perf_counter` wall-clock.
CI = always-on small ratio + `@pytest.mark.scale` 10⁵ nightly. **Framing (DR-7, pinned unambiguous per
Ben 2026-07-09):** what is reused from S1.4/S1.5 is the **store round-trip *primitives*** (`save_stream`
/ `load_stream`) — **not a fixture.** No scale fixture exists; the size-parameterized scale fixture is
**new work built for S4.7**. Any tracker/plan wording that reads as "shares an existing benchmark
fixture" is to be corrected to "reuses the store primitives; builds its own scale fixture."

---

## §6 Out of scope
τ calibration + three-rate negatives = **S5.2**. Real-PLL re-extraction = needs S4.6. Human O3 = D35.
INV-2's drift fixtures are by-construction existence checks, **not** S5.2's perturbation-model rates.

---

## §7 Governance: the falsified `s5_1_plan.md` §1.3 claim

`s5_1_plan.md` §1.3 (ratified) says the DP "holds it to one near-linear pass." **False** (deferred, not
built; shipped is O(K·N³) — §1). Rev 3 proposes (pending G-2; **not pre-applied**): a dated correction
note preserving the original claim, flagged falsified-by-#33, pointing here; route the rewrite as S5.1
remediation (G-1); correct the stale S5.1 tracker-row text (still reads "joint monotone-tiling
assignment," which #33 replaces) and the S4.7 Deliverable text.

---

## §8 Definition of Done
1. Plan ratified; `[review]` rows + G-1…G-4 resolved. 2. INV-1…INV-7 red-first (drift generator built
so INV-2/INV-3 can be seen red). 3. Diff-based re-anchor lands; `bound ⊆ oracle` + anti-inertness
proven; suite green (1728). **Acceptance is strict-with-characterized-residual, not literal zero (DR-9, [Ben-ruled] 2026-07-09):** INV-1 holds by construction, and the emitted residual is bounded with every survivor magnitude/foreign-content-detectable (routed to the worklist, handed to S5.2 which owns τ-calibrated zero). Forcing "literal zero" here would hard-code a τ value S4.7 explicitly defers (`RebindPolicy`: "S5.1 ships a default; S5.2 calibrates"), baking an uncalibrated knob into the mechanism. Wiring obligation: any future consumer of bound spans runs post-S5.2 or via the strict `assert_all_bound` path. 4. Scale harness + CI; ratios (wall-clock + peak-mem, deep + wide) in
`docs/probes/s4_7_scale.md`. **[ratified DoD requirement — Ben, 2026-07-09]** the harness must
include a **deliberately anchor-poor fixture** (low unique-in-both k-gram density — the anchor-rich PLL
prose measured 71% type-unique 3-grams, the favorable end), because the gap cap that buys linear *time*
is the same knob that leaks the wrong-content residual: as anchors thin, **time stays linear while
correctness degrades**, so a wall-clock-only ratio passes green while the mechanism silently mis-binds.
The gate therefore measures a **correctness-at-density axis** (residual / fail-loud rate vs. anchor
density and N), not just the timing ratio. See `s4_7_prototype_findings.md` FRAME. 5. Mutation hunt all-killed; wide+narrow + Rule-A clean. 6. `s5_1` §1.3
correction landed (G-2); S5.1 + S4.7 tracker rows corrected; #33 closed; push `origin/spike` only.
Commit only when Ben asks.
