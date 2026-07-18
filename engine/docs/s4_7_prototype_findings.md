# S4.7 re-bind prototype — findings (2026-07-08)

> **FRAME — read first (what this spike was for, and what it did/didn't settle).**
> This was a **design spike for S4.7 half (B)** — the re-bind re-architecture (`s4_7_plan.md §0`) —
> run **before** landing it in `src/`. It was **not** the shipped artifact and **not** the scale gate
> (half A). Judge it against that charter.
>
> **What it settled (its job):** (1) diff-based anchored alignment is **linear-in-shape** → the cubic
> re-bind DP is retired *as a design direction* (the cubic path is "the defect the gate exists to
> catch", §0 — not a surprise this spike found). (2) It **falsified** the ratified `s5_1_plan.md §1.3`
> "near-linear pass" claim (§7). (3) DR-3: **zero false-bind is NOT calibration-free** → calibration is
> S5.2's, not S4.7's (§6) — the layer boundary is now set. (4) The cleaned rerun measured the residual
> as ~92% noise-driven with one intrinsic remainder (`s4_7_cleaned_rerun_findings.md`).
>
> **What it did NOT (and was never chartered to) settle — these are scheduled, not gaps:** the **port**
> of (B) into `src/` (DoD §8 item 3, pending); the **scale gate itself** (half A — harness/CI/serialize
> ·load·index, DoD §8 item 4, not built); **τ calibration + three-rate negatives** (§6 → S5.2);
> **real-PLL re-extraction** (§6 → S4.6); the **cleaned-substrate correctness number** (blocked on
> native cleaned segmentation, tracked on the S5.2 row).
>
> **The one open item this spike's critique added:** the scale gate (half A) must include a
> **deliberately anchor-poor fixture** — "linear" was measured on anchor-rich PLL prose (71% type-unique
> 3-grams), and time vs. correctness diverge as anchors thin (the gap cap that buys linear time is the
> same knob that leaks the residual). Logged into half A's fixture obligations in `s4_7_plan.md`.

> **HEADLINE CORRECTION (after the real re-atomizer test).** An earlier draft concluded S4.7 could be
> "calibration-free zero false-bind at atom granularity." **That is FALSE and retracted.** It held only
> on the oracle-partition proxy. Running the ACTUAL atomizer (`build_canonical` on a perturbed witness,
> `s4_7_reatomize.py`) exposed a residual **wrong-content false-bind** (1–2 slots/run) that survives
> every calibration-free guard built here (disjointness + anchor-boundary + interior-containment). It
> is real (a copy2-derivation oracle confirms the bound span engulfs *foreign* slots), localized to
> prose slots whose END boundary sits on recurring OCR page-marker noise. **DR-1 (shape) still passes;
> DR-3's "zero" does NOT hold calibration-free under real re-atomization** — driving it to zero needs
> S5.2 calibration (span-length/anchor-density) or a cleaned input stream. See "Real re-atomizer" below.

## Adversarial audit corrections (2026-07-08, 5 divergent-lens panel + verification)

A 5-lens adversarial panel (harness / red-first / conclusions / missed-modes / facts) audited this
doc and the scripts. Net: **DR-1 (shape) survives; DR-3's "not calibration-free-zero" is reinforced.**
But several specific claims below are WRONG or imprecise and are corrected here (this section
supersedes the inline text where they conflict):

1. **"capped_pos=0 on real PLL" is FALSE** (was measured on the oracle proxy only). On the real
   re-atomizer the gap cap engages heavily: **15,028 capped positions (seed 1), 7,190 (seed 7)**, incl.
   a single ~19k-token desync region. DR-1 linearity still holds *because* the cap bounds Σgap² ≤
   cap·N = O(N) regardless of anchor density — but large slots bridge these unaligned regions with
   interior-containment running **vacuously** (>50% of their interior is `proj=-1`). Verified.
2. **The residual is UNDERCOUNTED.** The doc's "1–2 wrong-content false-binds/run" used a `sim<0.5`
   gate that misses moderate over-captures. A stronger `lenratio>1.2 + midpoint-foreign` detector
   finds **seed 1 = 3** (adds slot engulfing 62–64 at 1.5×), seed 7 = 1. And the copy2 oracle covers
   only **70%** of atoms (blind to copy1-only) and over-attributes on 1-token boundary clips, so even
   3 is a **lower bound**. DR-3 "not zero" is reinforced.
3. **Root cause (crisp):** the bound span `(b0,b1)` is defined purely by the two endpoint anchors;
   interior-containment checks only that *old* interior positions stay monotone in `[b0,b1]` — it never
   checks that *fresh* interior tokens belong to the slot. So **foreign content inserted between a
   slot's two boundary anchors is always engulfed** (reproduced with the cap off, all interior
   checked). It is caught only if the engulfed slot *also* binds (the disjointness gate) — which
   noise/desync-region slots don't. Over-capture can also run **backward** (a slot engulfing an
   *earlier* node), so a forward-only calibration guard would miss it.
4. **The proposed calibration-free "landmark-straddle" gate was TESTED and FAILS** (catches 0). The
   over-capture spans exactly the desync region where the intervening chapter headings project just
   *outside* the span (span ends 163031; heading projects 163032), so no landmark is strictly inside.
   So catching the residual needs a **calibrated** magnitude/coverage check (lenratio) = S5.2. The
   "zero is S5.2's" scope call therefore stands **for raw input**, but is **OPEN for cleaned input**
   (the deployment target) — do not read it as settled there.
5. **Heading "no red reachable" is FALSE.** The construction not tried — two identical headings,
   delete the *target's own home* — makes the naive path bind the orphan to its **wrong-chapter twin**
   (verified: `bound={0:1}`, wrong-chapter=True). Strict is saved by the **collision/disjointness
   gate**, NOT by "monotonicity cannot swap" (my causal claim was wrong). "Four constructions" is
   actually **three**. The heading constructions also resolve against the oracle partition, the same
   proxy weakness the headline retraction was about.
6. **Some invariants are proven on TOY re-implementations, not the shipped path.** INV-8's contiguity
   gate does **not exist** in the mechanism (`s4_7_slots.py` collapses a node's atoms to one interval,
   so the real path *would* swallow a foreign node). INV-3/INV-7 toggle local re-implementations. The
   slot-variant disjointness gate (`s4_7_slots.py`) is **weaker** than reatomize's (keys on
   resolved-slot-id, not span overlap). These are guards to ADD/UNIFY, demonstrated — not shipped green.
7. **"Cause CONFIRMED (noise boundaries)" → necessary, not sufficient.** ~29 noise-bounded slots bind
   correctly; the guard's zeroing is partly collateral (it drops 2/3 of body binds). Defensible
   statement: "all observed false-binds have a noise END boundary; refusing noise boundaries removes
   them at heavy raw-yield cost." The causal claim survives the stronger detector, but the wording
   overclaimed.
8. **Precision:** "71% anchor uniqueness" is 3-gram *type*-uniqueness; position-level landmark density
   is ~54% (unique-in-both lower). DR-1 per-row *exponents* are timing noise (indicative only; the
   conclusion is robust). `normalize_tokens` is "behaviorally identical," not verbatim. Drift's
   insertion rate is 5%, not the ~2% claimed. Body re-atomizer bind range is 47–51/59 (not "47–54").
9. **Still untested** (panel-confirmed gaps): container heading-slot bind acceptance when its whole
   subtree fails loud (INV-7 tested ancestor *re-stamp*, not this); slot-scale anchor-conflict from
   dittography; `signature_atoms`.

---

Throwaway prototype (`scratchpad/s4_7_prototype.py` + `s4_7_diag.py`, `s4_7_ksweep.py`,
`s4_7_atomgrain.py`, `s4_7_slots.py`, `s4_7_*_inv.py`, `s4_7_reatomize.py`, `s4_7_audit_followup.py`),
run on the **real** frozen PLL workspace, to settle empirically the two questions three adversarial
rounds could not settle on paper:

- **DR-1 (tool/shape):** does an anchored/segmented aligner stay sub-quadratic on real low-vocab
  prose, where the shipped `_Assignment` DP is O(K·N³) and a blind global diff is O(N·M/64) ≈ 3.5s?
- **DR-3 (the gate):** does STRICT projection (score only the projected span, NO search) give
  zero false-bind under the real drift mix, and at what yield?

**Grounding.** Old stream = the real canonical atom stream (171,181 tokens / 4,786 atoms). Drift is
synthesized from the real deviation catalog (`data/blind_deviations_classified.json`, 862
scan-confirmed deviations) at its measured class frequencies (~87% substitution drawing actual
printed→published pairs, ~8% deletion, ~2% dittography, plus one planted moved block for the ~0%
reorder case). The drift's identity map is recorded by construction → the oracle. The mechanism
never sees it.

## The mechanism (settled family: flat anchored sequence alignment)

1. k-gram shingle index over old + fresh; **unique-in-both** shingles are landmark anchor pairs.
2. Longest increasing subsequence on the pairs (patience, O(A log A)) → monotone anchor chain
   (drops reorder crossings).
3. Between consecutive chained anchors, align the (small, bounded) gap with
   `rapidfuzz Levenshtein.opcodes` → per-old-position projection (equal/replace project exactly;
   delete/insert leave gaps). Gaps wider than a cap fail loud (keeps the worst case linear).
4. **Calibration-free strict guards** (each a pure consistency check, no threshold):
   - anchor-conflict refusal — a position two anchors disagree on is nulled;
   - span defined by the two boundary fixed points (not min/max of interior);
   - interior monotone-containment — a stray interior projection → refuse;
   - always-on disjointness gate (the `_contested_nodes` analog).
5. Boundary policy = weakest op-tag admitted at a slot boundary: `anchor` ⊂ `equal` ⊂ `replace`.

## DR-1 — SHAPE: PASS decisively (linear)

| old tok | new tok | sec | peak MB | exponent |
|--------:|--------:|----:|--------:|---------:|
| 1,981 | 1,976 | 0.025 | 1.0 | – |
| 4,973 | 4,962 | 0.055 | 2.2 | 0.86 |
| 9,995 | 10,007 | 0.11 | 4.5 | 0.9 |
| 20,000 | 20,049 | 0.21 | 8.6 | 0.9 |
| 49,938 | 50,073 | 0.57 | 23.0 | 1.1 |
| 99,928 | 100,206 | 1.16 | 40.5 | 1.0 |
| 171,181 | 171,695 | ~1.9 | 70.1 | ~1.0 |

Exponent stays ≈1.0 across ≥2 decades; ≤~2s and 70 MB at full book scale; **no gap ever hit the cap**
(real prose has ample unique anchors). The O(K·N³) DP is decisively replaced. `rapidfuzz` is already
a repo dep (only in `steps/reconcile.py`); routing core re-bind through it is a new coupling to
justify in the plan, but the shape win is real. A hand-rolled anchored aligner is viable too since
each gap is small.

## DR-3 — the gate: token granularity is NOT calibration-free-zero; atom granularity IS

**At token-span granularity** the strict guards drive false-bind from 0.68% down but not to zero:

| boundary policy | yield | token false-bind (3 seeds) |
|---|---:|---:|
| anchor | ~62% | 0 / 2 / 3 |
| equal | ~90% | 4 / 8 / 11 |
| replace | ~98% | 23 / 24 / 31 |

Every residual token false-bind is a ±1–2 token **seam** error. Diagnosed to an exact cause
(`s4_7_diag.py`): at a **dittographic near-repeat**, a seam-spanning shingle is unique-in-both yet
maps the old boundary to the *duplicated* copy, with no local contradiction. The k-sweep is
**inverted** — raising shingle length makes it *worse* (anchor-policy fb 3→10→20→34 at k=3→6),
because longer shingles pin the seam to the wrong copy more confidently and produce fewer competing
anchors for conflict-refusal to catch. So the residual is **not** removable by cranking a knob; its
tradeoff surface is non-trivial — which is exactly why calibration is a separate concern (S5.2).

**At atom granularity** (re-bind's real target — a node binds to fresh *atoms*, ~36 tokens each;
projected span resolved to a fresh atom by dominant overlap) the residual **vanishes entirely**.
Both false-bind directions were measured — **mis-target** (old *i* resolves to a fresh atom ≠ *i*)
and **collision** (two distinct old atoms resolve to the *same* fresh atom — a silent double-bind,
the exact mode the S5.1 audit caught):

| boundary policy | yield | atom mis-target (3 seeds) | collisions (3 seeds) |
|---|---:|---:|---:|
| anchor | ~62% | 0 / 0 / 0 | 0 / 0 / 0 |
| equal | ~90% | 0 / 0 / 0 | 0 / 0 / 0 |
| replace | ~98% | 0 / 0 / 0 | 0 / 0 / 0 |

A ±2-token seam error cannot flip a 36-token atom's membership. All three policies are zero-false-bind
at atom granularity (both directions) **on the oracle-partition proxy**, calibration-free,
sub-quadratic. The planted moved block **fails loud** (atom 2494 → `boundary_ambiguous`), never
mis-binds. **⚠ This "zero" is proxy-only and is OVERTURNED by the real re-atomizer test below** — do
not cite it as the DR-3 answer; the real-atomizer section supersedes it.

**Collision caveat (important, limits the guarantee).** The rate fixture models substitution /
deletion / insertion / reorder but **no atom merge or split** (two old atoms collapsing into one
fresh atom, or one splitting) — the case that actually *produces* collisions. So the `collisions = 0`
in the rate table means the collision path was **not stressed** — reporting it as a guarantee would
be a green from an untriggered branch. Correctness invariants are therefore established separately,
red-first (below), not read off the rate fixture.

## Correctness invariants — red-first (`scratchpad/s4_7_invariants.py`)

Rates above are MEASUREMENTS on realistic drift. The zero-false-bind GUARANTEES are separate: each is
a planted violation seen **RED** (guard off → the mechanism false-binds, proving the failure is
reachable) then **GREEN** (guard on → it fails loud). A guard whose red was never seen is not a check.

| invariant | planted violation | RED (guard off) | GREEN (guard on) |
|---|---|---|---|
| **INV-2 reorder fails loud** | a moved/swapped block | raw unique-in-both anchor pairs cross | LIS monotone chain drops the crossing anchors |
| **INV-3 no collision (merge)** | re-atomizer merges 2 old atoms → 1 fresh | both old atoms bind the same fresh atom (silent double-bind — the S5.1-audit mode) | atom-granularity disjointness gate revokes both → fail loud; no-merge control still binds distinctly |
| **INV-3b atom split** | 1 old atom split across 2 fresh atoms | — | dominant overlap picks the larger share; the orphan fresh atom is detectable → **must reach the worklist, not be silently dropped** (new design requirement) |
| **INV-4 anchor conflict refused** | dittographic duplicate → 2 shingles claim one old pos with different targets | blind painting clobbers → boundary silently maps to the duplicate | conflict refusal nulls the contested position (`proj=-1`, fail loud) |

The atom-granularity disjointness gate is thus **demonstrably load-bearing** (INV-3 red), not merely
carried by convention; the merge/split fixture that stresses it is INV-3/INV-3b, not the rate fixture.

## Node/slot granularity on the REAL structure map (`s4_7_slots.py`)

The atom-level runs above hid the structurally critical case. Binding the **real** 120-node PLL
`structure_map.json` by its slots — 58 heading slots (each 1–3 tokens: "Capitolo <ordinal>",
recurring/near-identical across 56 chapters — the reviewer's "gate weakest on headings") + 59 body
slots (median 65 atoms) — reported PER KIND (natural drift, 3 seeds):

| kind | policy | yield | mis-bind | collision | wrong-chapter |
|---|---|---|---:|---:|---:|
| heading | anchor | 79–86% | 0 | 0 | 0 |
| heading | equal | 86–90% | 0 | 0 | 0 |
| heading | replace | 95–100% | 0 | 0 | 0 |
| body | anchor | 71–76% | 0 | 0 | — |
| body | equal | 85–93% | 0 | 0 | — |
| body | replace | 97% | 0 | 0 | — |

Body body_atoms are 100% atom-id-contiguous in the real map (probed). **But natural drift rarely
stresses a chapter boundary**, so those heading zeros are the untriggered-branch trap again. Four
adversarial constructions were built to *force* a heading mis-bind (`s4_7_heading_inv.py`,
`s4_7_identical_slots.py`):

1. delete only the 2-token heading → fails loud (correctly gone);
2. delete a chapter's entire 2,535-token **body** → two "Capitolo" headings become adjacent → target
   still binds to its own chapter, neighbor fails loud; **no wrong-chapter**;
3. two **identical** headings, all context stripped → both fail loud (below k=3, no shingle);
4. two identical headings **adjacent, outer anchors intact** → both bind correctly.

**⚠ CORRECTED by the audit (see correction #5).** This originally claimed "no red was reachable… four
constructions." Both are wrong: (a) only **three** constructions exist; (b) a red **is** reachable —
the untried construction (two identical headings, delete the target's own home) makes the naive path
bind the orphan to its **wrong-chapter twin** (`bound={0:1}`, verified in `s4_7_audit_followup.py`).
What actually holds the line under strict is the **collision/disjointness gate** (both revoked), NOT
"monotonicity cannot swap" — that causal explanation was wrong (there is no swap; the home is gone).
So the guarantee "no silent wrong-chapter bind *survives*" holds, but via a guard-caught red, and the
guard also revokes the legitimate twin (a correct heading knocked to fail-loud). These constructions
also resolve against the oracle partition, not the real re-atomizer.

## What is now tested vs still UNTESTED (the honest surface)

**Tested** (this session): sub-quadratic shape on real 171k stream; token- and atom-granularity
false-bind (both directions) on realistic drift; real 120-node slot binding per kind; INV-2 reorder /
INV-3 collision-merge / INV-3b split / INV-4 anchor-conflict red-first; heading anti-confusion across
4 adversarial constructions.

**Now tested (this session, red-first):**
- **Container bottom-up re-stamp (INV-7).** On the real tree (volume→part→chapter→prose leaf): fail one
  prose leaf's body → gate OFF re-stamps all ancestors (chapter/part/volume) = reachable corruption;
  gate ON blocks all three; a fully-bound sibling still re-stamps. The bottom-up gate is load-bearing.
- **Non-contiguous body slots (INV-8).** A slot owning non-adjacent atoms → naive single-interval
  projection swallows the foreign node's tokens (corruption); contiguity gate fails it loud, the
  foreign node binds cleanly.
- **Real re-atomizer** — see below; this is what overturned the headline.

**Still UNTESTED:**
- **`signature_atoms` slot kind** — absent in the PLL map, never exercised (mechanically identical to
  heading; low risk but uncovered).

## Real re-atomizer — retires the oracle proxy, overturns "calibration-free zero" (`s4_7_reatomize.py`)

Everything above used the fixture's own oracle as the fresh partition, so binding could have been
coasting on partition==oracle. This test uses the ACTUAL atomizer: `build_canonical` reproduces the
on-disk canonical exactly (determinism ✓), then a witness (copy1) is perturbed (drop ~2% / duplicate
~1% / mutate ~5% of atoms) and re-reconciled → a genuinely re-atomized fresh stream whose atom
boundaries are drawn by `align_streams`, not by us. A **real oracle** comes from the UNPERTURBED copy2
derivations (canon0 atom ↔ copy2 id ↔ canon1 atom), so "false-bind" is measured against ground truth,
not a text-similarity heuristic.

Result (2 seeds, both `equal` and `anchor` policy):
- Most slots bind correctly: body 47–54/59, heading 51–54/58, span-similarity median 0.99–1.0.
- **A residual 1–2 slots/run are WRONG-CONTENT false-binds** (copy2 oracle: the bound span engulfs
  *foreign* slots — e.g. one slot's fresh span covered old slots 99–103). They are **normal prose
  chapter bodies** (1,233–2,641 tokens, clean starts) whose **END boundary token sits on recurring OCR
  page-marker noise** ("142 31 3s se sme 3s"). The noise end-token anchors to a far occurrence across a
  heavily-reflowed region → the span over-captures 3–16× its length across the following (failed-loud)
  slots.
- **These survive every calibration-free guard here:** the disjointness gate revokes 0 (the engulfed
  slots independently failed loud, so there is no *surviving* bound span to overlap); anchor-boundary
  does not help (the noise token genuinely is unique-in-both, it just maps far); interior-containment
  passes (the path stays monotone out to the wrong end).

**Why it matters.** Catching it requires reasoning the cheap strict projection deliberately avoids: a
span-length / anchor-density plausibility check (a threshold → calibration → S5.2), or the expensive
joint monotone tiling over ALL slots incl. failed ones (the O(K·N³) DP S4.7 was retiring). So:
- **DR-3 corrected:** strict calibration-free projection does NOT reach zero false-bind under real
  re-atomization. The scope split is *reinforced* (the residual is genuinely calibration's job) but the
  "S4.7 delivers zero" claim is withdrawn — S4.7 delivers *sub-quadratic + strict-with-a-characterized-
  residual*; zero moves to S5.2.
- **Cause CONFIRMED (noise boundaries):** adding a guard that refuses to anchor a slot boundary on a
  page-marker/noise token drives WRONG-CONTENT false-binds to **0** on both seeds and lifts min
  span-sim 0.11→0.91. So the residual is entirely slot boundaries landing on raw OCR page-marker noise
  — not a general mechanism flaw. **But on raw input that guard costs 2/3 of body yield** (47→18
  bound): raw slots are pervasively noise-bounded. So the guard is the wrong fix *for raw input*.
- **Expected on cleaned input, NOT yet proven:** the live pipeline re-binds *cleaned* text where those
  noise tokens don't exist, so boundaries are real words → both zero false-bind AND full yield are
  expected. What's proven is the *cause*; guarding noise boundaries on raw input is a *model* of
  cleaning, not cleaning. The remaining confirmation = re-run on an actually-cleaned re-atomized stream
  (norm_layer ≠ raw). Until then: zero-false-bind is demonstrated only with a noise-boundary guard,
  which itself is calibration-shaped (what counts as "noise") — i.e. still S5.2-adjacent.

## What this means (for Ben to rule — not ratified here)

1. **DR-1 shape is settled: PASS.** Anchored/segmented alignment is linear on the real 171k stream; the
   O(K·N³) `_Assignment` DP is retired. This is not in question.
2. **DR-3 is settled the OTHER way: strict calibration-free projection does NOT reach zero false-bind
   under real re-atomization.** The residual (1–2 prose slots/run, wrong-content over-capture anchored
   on OCR page-marker noise) survives disjointness + anchor-boundary + interior-containment. The
   earlier "calibration-free zero at atom granularity" is **withdrawn** — it was true only on the
   oracle proxy. So the scope split is confirmed but the boundary moves: **zero is S5.2's**, achieved
   by a calibrated span-length/anchor-density plausibility check (or the expensive joint tiling).
3. **S4.7 delivers:** sub-quadratic alignment + strict projection + the load-bearing gates proven
   red-first (bottom-up re-stamp INV-7, disjointness INV-3, contiguity INV-8, anchor-conflict INV-4,
   reorder INV-2) + a **characterized residual** routed to the worklist. Not "zero," but "sound
   mechanism with a named, bounded, calibration-shaped hole."
4. **RULED (DR-9, [Ben-ruled] 2026-07-09):** S4.7 ships **strict-with-characterized-residual; S5.2 owns
   the zero.** A consumer trace this session found no consumer of `rebind()` binds exists yet (only
   `tests/unit/test_rebind.py`; no `steps/*.py` imports `engine.structure`; no S5.2 module), and the
   mechanism/calibration split is already encoded in `rebind.py` `RebindPolicy` ("S5.1 ships a default;
   S5.2 calibrates"). Forcing zero into S4.7's DoD would hard-code a τ value S4.7 defers. See
   `s4_7_plan.md` DR-9 + §8 item 3.
5. **Before either:** re-run the real re-atomizer on a **cleaned** atom stream (norm_layer ≠ raw). If
   the residual vanishes on cleaned input (every current instance is a raw page-marker boundary), the
   calibration need is far smaller than the raw-layer numbers suggest.

## Caveats / follow-ups (honest limits of the prototype)

- The residual-false-bind characterization is on the **raw** (norm_layer=raw) canonical stream, which
  still carries OCR page-marker noise — the boundary tokens every false-bind is anchored on. **Not yet
  re-run on cleaned text**; that is the single most important follow-up (it may shrink the residual to
  ~0). Until then the residual stands as a real defect on raw input.
- Witness perturbation is synthetic (drop/dup/mutate at plausible rates on copy1). Realistic in kind;
  the exact rates are not from a measured re-run pair (none exists on disk). Two seeds shown.
- `signature_atoms` never exercised (absent in the PLL map). Same code path as heading.
- Slot-level results use the real 120-node structure map and the real `build_canonical`; only the
  gates/invariants were toggled — the mechanism itself is the throwaway prototype, not `rebind.py`.
- ~~`capped_pos=0` on real PLL~~ **FALSE — see correction #1.** That was the oracle proxy; the real
  re-atomizer caps 7k–15k positions incl. a ~19k desync region. The cap is what *keeps* DR-1 linear
  (Σgap² ≤ cap·N = O(N)), but it also means large slots bridge unaligned regions with interior
  containment vacuous — a guard-coverage hole, not (in these 2 seeds) a demonstrated false-bind.

## Recommended plan rescope (proposal)

- S4.7 = anchored/segmented alignment + **atom-granularity dominant-overlap projection** + strict
  fail-loud (calibration-free, sub-quadratic, zero atom-false-bind). Default boundary policy `equal`.
  Carry the always-on disjointness / `_contested_nodes` gate **at atom granularity** (INV-3 proves it
  load-bearing) and port the red-first invariant suite (INV-2/3/3b/4). Atom **split** must surface
  the orphan fresh atom to the worklist rather than silently drop it (INV-3b).
- S5.2 = confidence/calibration (perturbation generator, three rates, recovering the fail-loud
  remainder). The S5.1 `_Assignment` O(K·N³) DP is retired; `RebindContext` / reason enum / re-stamp
  protocol / modes / `_contested_nodes` are kept.
- Governance unchanged: the rewrite reverses two signed [Ben-ruled] S5.1 decisions and touches a born
  schema → formal S5.1 supersession + a new S5-milestone issue, **not** a tracker edit; §1.3
  falsified-claim correction still awaits Ben's G-2 ruling. **[Dated note 2026-07-17: both since
  ruled — the supersession is issue #48 (G-1, 2026-07-09) and the G-2 correction landed, commit
  `7e5d612`, 2026-07-09. This snapshot predates those rulings.]**
