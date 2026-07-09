# S4.7 re-bind prototype — cleaned-stream rerun findings (2026-07-08)

Follow-up to `s4_7_prototype_findings.md`. The raw run left a real wrong-content residual, root-caused
to **foreign content engulfed between a slot's two boundary anchors inside a capped-desync region**,
with the desync driven by OCR page-marker noise atoms (`3E`, `5e:`, `35`, …). Deployment re-binds
**cleaned** text, not raw. This rerun tests the hypothesis: strip the noise class the engine cleaner
strips, re-atomize, and the residual collapses.

Nothing here is ratified. The S4.7 DoD zero-vs-strict-with-residual question is now **ruled** (DR-9,
[Ben-ruled] 2026-07-09): S4.7 ships strict-with-characterized-residual, S5.2 owns the τ-calibrated
zero — see `s4_7_plan.md` DR-9. The remaining governance calls (S5.1 supersession, the §1.3 G-2
correction) remain Ben's.

## Setup

- **Cleaner = the engine's own `is_noise_line`**, config-resolved for `per_la_liberta`
  (`load_book` → `build_rules`), applied per atom: drop noise lines; drop atoms left empty. This is
  the real deployment noise oracle, not a hand regex.
- **Caveat — this is a conservative floor.** `is_noise_line` is only the noise-removal *component* of
  `clean_text`. The full step additionally does dehyphenation, symspell dictionary correction, and LLM
  correction — which would de-garble boundary tokens (e.g. `l presbntk` → `Il presente`). The true
  deployment substrate should do **at least** this well, plausibly better. Measurements below
  understate cleaning's benefit.
- Substrate build: clean copy1+copy2 → `build_canonical` (fresh atom boundaries on cleaned text) →
  remap the stored 120-node structure_map onto the cleaned canon via a witness-id oracle → perturb
  clean-copy1 (drop 2% / dup 1% / mutate 5%) → re-reconcile → re-bind → **strong detector**
  (lenratio>1.2 + midpoint-foreign; the `sim<0.5` detector undercounts, per the prior audit).
- Cleaning: copy1 3621→2632 atoms, copy2 3356→2806; canonical 4786→3075 atoms / 171181→144864 tokens.
  **0 of 117 slots vanish** (no real slot is destroyed); 58 body slots shed interior page-marker atoms.

## Result 1 — capped-desync collapses ~12× (artifact-free, the headline)

The capped-desync count is slot-independent and remap-independent — it is a pure property of the
old→new token projection, so it carries none of the remap uncertainty below.

| substrate | seed 1 capped | seed 7 capped | anchors (seed 1) |
|-----------|--------------:|--------------:|-----------------:|
| RAW       | 15028         | 7190          | 74624            |
| CLEANED   | **1247**      | **429**       | **101200**       |

Cleaning removes ~92% of the capped-desync region and raises unique anchors 74k→101k. **This directly
confirms the root cause**: the desync that engulfs foreign content is overwhelmingly noise-driven, and
cleaning collapses it.

## Result 2 — the residual shrinks but does NOT reach zero

Wrong-content false-binds (strong detector), all 117 slots:

| substrate | seed 1 | seed 7 |
|-----------|-------:|-------:|
| RAW       | 3      | 1      |
| CLEANED   | **0**  | **1**  |

Cleaning eliminated the seed-1 residual entirely (3→0). But seed 7 retains exactly **one** wrong-content
false-bind — and it is a *different* node than raw seed 7's (`…001` vs `…1M`), confirming the residual
is drift/substrate-dependent, not a fixed structural defect. Same verdict as raw: **strict mechanism
alone does not reach zero; S5.2 calibration is still required.**

### The one surviving cleaned false-bind, characterized

- Node `…0001`, `prose` body slot = the **Prefazione's first prose paragraph**.
- OLD span tok [1027,1447) len 420 → FRESH span [1016,1583) len 567, **lenratio 1.35**, boundary
  op-tags both `equal`.
- It over-captured **backward** (fresh start 1016 < projected 1027), engulfing 3 atoms of slot 0
  (front-matter: "class … copyright … digitized by the internet archive") and 1 atom of slot 1 (the
  `prefazione` heading, node `n-2`).
- Mechanism: the slot's left boundary token is `l` (OCR garble of "Il" in "l presbntk volume…"), a
  maximally-common Italian token → non-unique 3-gram anchor → the alignment slid the boundary left
  into the heading + front matter. **Capping is already low here (429)** — this is *not*
  noise-driven desync; it is intrinsic boundary ambiguity.

This is exactly S5.2 territory: a calibrated magnitude/foreign-content check (lenratio 1.35 + foreign
heading content inside → flag), not a structural guard. And note the floor caveat: the full cleaner's
symspell pass would likely correct `l presbntk` → `Il presente`, giving a more unique boundary anchor
and plausibly resolving this very survivor.

## Result 3 — bind yield did NOT collapse; the apparent reduction is remap-contaminated

The earlier all-slots read showed a large yield drop (body 47→26). That was substantially a **remap
artifact**: 29 of 117 slots remap to non-contiguous cleaned-atom sets (witness-id "first-wins"
scatter; gaps up to 236 atoms), inflating their spans so the monotone guards reject them. Restricting
to the 88 contiguously-remappable slots (apples-to-apples, same node_ids both substrates):

| substrate | body bind (s1/s7) | heading bind (s1/s7) |
|-----------|-------------------|----------------------|
| RAW (88)  | 28/36, 30/36      | 47/52, 49/52         |
| CLEANED (88) | 22/36, 24/36   | 41/52, 42/52         |

A modest apparent reduction remains, but even the "contiguous" subset can be contiguous-but-misaligned
(contiguity ≠ correct span), so this number carries **irreducible remap uncertainty**. Honest read:
**yield did not collapse; a precise cleaned-yield figure is not obtainable from a remapped map.**

## The irreducible limitation (and where it's blocked)

A remap can never be as faithful as a **natively-segmented cleaned structure_map**. Producing one needs
the segmentation step run on cleaned atoms, which is not available in the engine port yet (prep-brief
option (d)). Everything reachable *without* that native map has been extracted:
capped-desync (fully artifact-free) → strong confirmation; residual on cleaned (all-slots, full
oracle) → 0/1 with the survivor characterized; yield → directional, remap-contaminated, reported as
such. The precise cleaned-yield number is deferred to when native cleaned segmentation lands.

## Verdict (for Ben's governance)

1. The **root cause is confirmed noise-driven** — cleaning removes ~92% of the desync that produces
   the residual.
2. Cleaned input **still does not reach calibration-free zero** (one intrinsic boundary-ambiguity
   engulfment survives), so **S5.2 calibration remains required on the deployment substrate** — the
   raw-run conclusion stands.
3. But S5.2's job on cleaned input is **far smaller and more tractable**: not fighting 15k-token
   noise-desync regions, just a magnitude/foreign-content check on a handful of intrinsically-hard
   boundaries (here: one, in the front matter, likely further resolved by the full cleaner's symspell
   pass). This strengthens the "strict mechanism + S5.2 owns zero" split over "absorb a calibrated
   guard into S4.7."
