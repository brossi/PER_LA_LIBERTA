# S4.7 external review (2026-07-17) — verification + proposed dispositions

**Status: ER-A1…ER-A5 RULED — Ben, 2026-07-17, each per the recommendation below (ER-A1 =
option (a)). Amendments applied same day:** `s4_7_plan.md` (header rulings block; §2.1 rewritten
to anchored alignment; §2.2 composite-projection note; §2.3 positional-confirmation amendment +
gap-cap note; §2.5 R-c pointer; §2.6 rewritten; DR-1/DR-3/DR-9 rows amended; G-4 amended; §4
INV-1 amended; §7 G-2 staleness corrected (C-1); §8 item-3 wiring amended),
`ENGINE_STRUCTURE_PLAN.md` (D35 coherence note, ER-A5), `ENGINE_STRUCTURE_TASKS.md` (S5.1-R row:
anchored design, positional confirmation, ER-A3 identity, G-4 re-wording), and
`s4_7_item2_invariants_plan.md` (parent-authority block now names ER-A1…A5). Bucket C applied
(C-1; C-2 folded into the §2.6 rewrite). **Bucket B folded into the specs 2026-07-17** — see the
location map at the end of its section.

**Provenance.** An external reviewer audited `s4_7_plan.md` rev 3 (15 findings + a
"minimum re-ratification delta"). Claude verified the findings own-eyes 2026-07-17 on the
working tree (branch `integration/assessment-provider-boundary`; includes the uncommitted
PR-1…PR-5/A7 amendments): every file citation was read, and the one empirical claim was
reproduced by running it (50 tokenless included atoms in the real PLL canonical; 5 are final
atoms of owning slots — exact match). The reviewer appears to have read the **committed**
state (HEAD `862b547`, 2026-07-12), so findings 14 (second half) and the item-2 tracemalloc
point are stale against the A1/A7 amendments; the load-bearing findings (1, 3, 4, 12) survive
the amendments unchanged.

**Routing model.** Four buckets, matching the plan's own governance:
- **A — needs a Ben ruling** (amends a ruled decision or ratified text; the PR-* pattern).
- **B — build obligation** (folds into item 2 / #48 spec as a requirement; no ruled decision
  is contradicted).
- **C — text fix** (stale/incoherent doc text; dated correction, no design content).
- **D — no action** (finding stale or subsumed; reason recorded so it isn't re-raised).

---

## Disposition ledger

| ER | Reviewer finding | Verified? | Bucket | Disposition |
|---|---|---|---|---|
| ER-1 | §2.1 global-diff architecture ≠ the prototype's anchored architecture; §2.6 memory claim contradicts rapidfuzz's own `O([N/64]·M)`; DoD item 4 cites a gap cap §2 doesn't define | **Confirmed** (docstrings, findings doc, plan) | **A** | **ER-A1** below — select one architecture |
| ER-2 | INV-1's planted-lineage oracle admits observationally-indistinguishable cases (delete + identical re-insert); anchor uniqueness not tied to the diff-projected boundary | **Sound** (construction checks out; A7's window-local confirm partially covers the tie) | **A** | **ER-A2** below — oracle scope ruling |
| ER-3 | `assert_all_bound` passes wrong-but-bound spans; report carries no backend/policy/calibration identity → pre-S5.2 results are consumable | **Confirmed** (`rebind.py:971`, report fields) | **A** | **ER-A3** below — DR-9 wiring amendment |
| ER-4 | Token→atom projection unspecified: per-slot (not per-node) intervals; boundary inside a merged fresh atom unrepresentable; 50 tokenless included atoms (5 slot-final) have no token back-pointer | **Confirmed incl. empirics (reproduced)** | **B** | Projection contract section added to the #48 spec before build (B-1) |
| ER-5 | G-4 conflicts with §3.B.6/D18 non-contiguous leaf bodies; "container subtree contiguous" misses interleaved leaf slots | **Half** — conflict real; "invalidates the fixture" overstated (G-4's letter governs containers, not leaves) | **A** | **ER-A4** below — G-4 wording ruling |
| ER-6 | PR-4 xfail closure leaves D35's "no super-linear" false; tracker demands the composite in the 10⁵ gate | **Predicates confirmed**; framing re-litigates ruled DR-6/PR-4; "sub-quadratic" already in the ratified tracker row | **A** (doc-coherence only) | **ER-A5** below — reconcile D35 wording, not reopen PR-4 |
| ER-7 | Backend undecided while invariants branch on opcode shape (Indel: no `replace`); difflib fallback has no conformance contract; autojunk proven load-bearing | **Confirmed** (docstring examples; item-2 §1.2 char-substitution bullet; test exists). DR-1 already names the resolution point ("compare Indel vs Levenshtein first") | **B** | Pin at the DR-1 resolution point: version+options recorded; fallback gets a conformance contract or is dropped (B-2) |
| ER-8 | "Only τ is tunable" (plan:134) is false — W, k, allocation, backend, (cap) all behavior-relevant; k-sweep inverted | **Textually confirmed**; framing uncharitable (PR-5 makes W a contract-fixed constant, not a knob) | **B** | Parameter ledger added to the plan: each parameter → fixed-constant (DR-4 contract-tested) vs calibrated (S5.2), with owner + test axis (B-3) |
| ER-9 | Adjacent slots share seam gaps; independent boundary resolution can double-assign/orphan inserted runs; oracle lacks insertion classes | **Valid gap** (rev 3 drops the disjointness gate from §2.4's preserved list; oracle insertion classes not fully verified) | **B** | Shared-boundary resolution + explicit disjointness carry-forward + oracle insertion classes into item 2/#48 (B-4) |
| ER-10 | "Independently valid geometry disambiguation" (PR-1/INV-5) has no executable definition — `Region` is a seed; `_pin_ok` is page-equality only | **Confirmed** | **B** | Define it as what exists: page-equality on the region seed, stated in the #48 spec; anything richer is future work, named (B-5) |
| ER-11 | Scale harness: "N" ambiguous; one decade vs INV-6's two; ceiling/runner not frozen; `scale` marker unregistered + CI runs bare `pytest -q`; no near-duplicate precheck | **Confirmed** (workflows, pyproject, plan text) | **B** | Harness spec additions: L/K/A/T/D defined per fixture; ≥2 decades; pre-registered ceiling+runner (PR-4 already mandates); register `scale` marker + deselect in default runs (B-6) |
| ER-12 | Evidence deep-chain input is itself O(N²) (`extent_payload` beneath-union) and the 1M cumulative decode budget makes a persisted 10⁵ full-coverage deep chain unloadable | **Confirmed** (`evidence.py:150,487`; arithmetic sound) | **B** | INV-7 fixture spec: distinguish complexity-vs-node-count from complexity-vs-input-bytes; construct in memory or measure an isolated core within budget (B-7) |
| ER-13 | Harness can't persist two canonical generations in one workspace (`load_workspace_streams` hard-rejects; tracker defers two-canonical to S5.2) | **Confirmed** (tracker S5.2 row verbatim) | **B** | One line in plan §5: harness uses separate old/fresh workspaces (no S5.2 pre-emption) (B-8) |
| ER-14a | "Preserve RebindReport unchanged" misleads — `candidates_ge_tau` is tiling-defined; report needs backend/policy/boundary-class/confirmation-method provenance | **Confirmed** (`rebind.py:293-294`) | **B** | #48 schema work: redefine/rename the ambiguity signal for diff projection; add provenance fields (extends the ruled `located_by` addition) (B-9) |
| ER-14b | Child spec calls `anchor-located` a new reason, contradicting `reason=None` | **Not found in any current revision** — but not a phantom: the code existed mid-rev-2.2 and was caught/fixed by that revision's own Rule-A audit (bind → `reason=None` + `located_by`) before this review was evaluated; the reviewer read a real intermediate state | **D** | No action; already fixed upstream of this review |
| ER-15a | §7 still says "pending G-2; not pre-applied" while the ledger says G-2 LANDED | **Confirmed** | **C** | Dated correction to §7 (C-1) |
| ER-15b | Item-2 scaffold is process overengineering for a triple-reproduced defect | Opinion | **D** | No action — the scaffold's scope was ruled (PR-1…5, A1…A7); revisit only if item-2 cost proves out |
| ER-16 | Item-2 tracemalloc "knowingly stale" (misses native rapidfuzz allocations) | **Stale** — A1 ruling + the §5.2 RSS handoff already handle it; parent §2.6 wording only | **C** | Fold the §2.6 wording fix into ER-A1's rewrite (C-2) |

---

## Bucket A — rulings requested → **RULED (Ben, 2026-07-17): all five per the recommendations; ER-A1 = option (a)**

### ER-A1 — select the alignment architecture (amends §2.1/§2.6; DR-1's tool choice survives)

The ratification blocker with teeth. §2.1 specifies one whole-stream diff; the linear evidence
(prototype) is for **anchors → LIS → capped per-gap rapidfuzz**; DoD item 4's anchor-poor/gap-cap
language already assumes the anchored design; rapidfuzz's packaged docs state `O([N/64]·M)` time
**and memory** for whole-stream opcodes, contradicting §2.6's O(N) memory claim.

- **Option (a) — RECOMMENDED: make the anchored architecture normative.** Rewrite §2.1 as the
  prototype mechanism (unique k-gram anchors → LIS → per-gap opcodes, gap cap fail-loud). It is
  the design the evidence validates; the gap cap becomes a *defined* term the DoD already relies
  on; §2.6's memory claim becomes true (per-gap alignments are bounded). Cost: the cap and k
  join the ER-8 parameter ledger as contract-fixed constants — they are already correctness-
  relevant per the findings doc, so the ledger names what exists either way.
- **Option (b): keep the global diff, add a mandatory 10⁵-scale + native-RSS benchmark of that
  exact implementation before item 3.** Honest, but it schedules a probable failure (the
  prototype measured the blind global diff at ~3.5 s / 171k tokens; the 10⁵-leaf gate is an
  order beyond) and leaves the DoD's gap-cap language dangling meanwhile.

DR-1 (tool = rapidfuzz, difflib fallback) is unchanged by (a) — the tool runs per-gap.

### ER-A2 — INV-1 oracle scope (amends INV-1's fixture contract; DR-3 lock unaffected in direction)

Ruling needed on the delete-plus-identical-re-insert construction: content evidence is perfect
(unique anchors, ratio 1.0), planted lineage says foreign — no content-only mechanism can pass.
- **Recommended:** (i) the drift generator **excludes** byte-identical re-insertion of deleted
  spans from INV-1's fixture family, reclassifying that construction as a *move destination*
  governed by PR-2's amended INV-3 (bind-to-planted-destination is legal); (ii) make explicit in
  DR-3 what A7 implies: anchor confirmation is **positional** — the located anchor must coincide
  with (or, in the no-candidate class, fall within) the diff-projected window; bare
  unique-in-both counting is insufficient (the prototype's real false-binds were unique-in-both
  anchors that "map far").
- Alternative: define INV-1 correctness observationally (bound span byte-equals the planted
  span's content) — weaker, and it would let genuinely-foreign near-identical content pass; not
  recommended.

### ER-A3 — pre-S5.2 non-consumability (amends DR-9's wiring obligation)

`assert_all_bound` rejects only unresolved nodes; the characterized residual consists of
*bound* nodes, so the "strict path" does not protect a consumer from it. **Recommended:** amend
DR-9's wiring sentence — strict consumption pre-S5.2 additionally requires a registered
policy/calibration identity in the report (a #48 schema field, alongside `located_by` and
ER-14a's provenance fields); absent it, `RebindResult` is marked not-for-consumption. Mechanical,
not a reversal of the DR-9 split (S5.2 still owns τ-zero).

### ER-A4 — G-4 wording (amends G-4; does not reopen its intent)

G-4's letter ("container subtree = one contiguous included span") is either too weak (an
interleaved **leaf** slot under a contiguous root passes authoring, then breaks the mechanism's
per-slot span assumption) or, read per-slot, contradicts the ratified §3.B.6 model, its green
regression, and the D18 differ fixture. **Recommended:** contiguity becomes a **per-slot
rebind-eligibility precondition**, not an authoring invalidation — a non-contiguous slot fails
loud at rebind (`ambiguous`, or a named new finding) while the map stays valid; §3.B.6/D18
stand; multi-interval projection stays deferred exactly as G-4 ruled. Alternative (formally
supersede §3.B.6 + D18 and replace the generality coverage) is a much larger contract change
with no current consumer needing it.

### ER-A5 — D35/tracker coherence (doc governance; PR-4 not reopened)

D35 says "no super-linear structure ops"; the ratified S4.7 tracker row and this plan gate
**sub-quadratic**; PR-4 (ruled) permits INV-7 to close characterized-unresolved. **Recommended:**
a dated note on D35 recording that the enforceable gate is the S4.7 row's sub-quadratic ceiling
and that INV-7 may close per DR-6/PR-4 with a named follow-up — reconciling the texts without
re-litigating either ruling. The alternative (hold S4.7 open until the composite is green)
re-litigates DR-6, which PR-4 already rejected.

---

## Bucket B — build obligations (**FOLDED into the specs 2026-07-17** — location map below)

- **B-1 (ER-4):** projection contract — per-slot intervals (`body`/`heading`/`signature`
  independently); shared seam boundaries resolved once as objects, spans derived (with B-4);
  explicit rule for a boundary landing inside a merged fresh atom (fail-loud, never rounded —
  DR-2's discipline); tokenless included atoms (50 real instances, 5 slot-final) get defined
  ownership without token back-pointers (boundary sentinels or atom-level attachment).
- **B-2 (ER-7):** at DR-1's named resolution point, pin backend + version + options + opcode
  semantics; difflib fallback gets its own conformance contract (incl. the proven-load-bearing
  junk policy) or is dropped.
- **B-3 (ER-8):** parameter ledger in the plan — {W, prefix/exact/suffix allocation, k, anchor
  match mode, backend, (gap cap per ER-A1), τ} × {fixed-constant under a DR-4-style contract
  test | S5.2-calibrated} × owner × invalidation rule.
- **B-4 (ER-9):** carry the disjointness/`_contested_nodes` gate forward explicitly in §2.4's
  preserved list; oracle gains insertion classes ("inserted within slot" vs "ambiguous seam
  insertion"), not only "no ancestry".
- **B-5 (ER-10):** INV-5's geometry disambiguation defined as page-equality on the region seed
  (what `_pin_ok` implements); richer geometry comparison is a named non-goal.
- **B-6 (ER-11):** harness spec — variables L/K/A/T/D pinned per fixture; ≥2 decades (INV-6's own
  text); ceiling + runner pre-registered (PR-4 already mandates); `scale` marker registered in
  `pyproject.toml` **and** deselected from default runs (addopts `-m "not scale"` or a nightly
  workflow) — today a marked 10⁵ test would run on every bare `pytest -q`, including both CI
  workflows; near-duplicate precheck before invoking the aligner.
- **B-7 (ER-12):** INV-7 fixture respects the 1M cumulative decode budget — measure the deep
  chain in memory or on an isolated core; report complexity against input bytes and node count
  separately.
- **B-8 (ER-13):** §5 one-liner — the harness persists old/fresh generations in **separate
  workspaces** (leaves S5.2's two-canonical decision untouched).
- **B-9 (ER-14a):** #48 schema — redefine or rename `candidates_ge_tau` for diff projection;
  add backend/version, policy identity, boundary classification, confirmation method (extends
  the ruled `located_by` field).

**Authored-rule ratifications (Ben, 2026-07-17):** the two design rules authored during the fold —
(a) tokenless-atom neighbor-derived ownership (parent §2.2, B-1) and (b) the seam-insertion
`{left, right, abstain}` oracle model (item-2 §1.3, B-4) — are **ratified as written**. The item-2
spec sign-off (incl. the INV-4 interval math) remains **open**.

**Folded locations (2026-07-17):**
- **B-1** → parent §2.2 projection contract (per-slot; shared-boundary objects; merged-atom
  fail-loud; tokenless-atom ownership rule) + item-2 §1.2 fixture-content floor + item-2 INV-4
  merged-atom-unrepresentable row + item-2 INV-1 shared-seam fixture.
- **B-2** → parent §2.1 conformance-identity paragraph + §2.8 backend row + item-2 §5.1 R-b
  sequence pointer.
- **B-3** → parent **§2.8 (new)** parameter ledger, wired to the item-2 §0 DR-3-lock invalidation
  trigger.
- **B-4** → parent §2.4 preserved list (disjointness gate explicit) + item-2 §1.3 insertion
  attribution (interior vs seam) + item-2 INV-1 seam fixture.
- **B-5** → parent §2.4 modes (page-equality definition, named non-goals) + item-2 §1.6 note
  (same-page vs distinct-page duplicate variants).
- **B-6** → parent §2.1 near-duplicate pre-check + parent §5 (L/K/A/T/D variables, ≥2 decades, CI
  marker registration + deselection) + item-2 §0 prereg bundle, INV-6 acceptance, §6 item-4
  handoffs.
- **B-7** → item-2 INV-7 fixture (decode-budget pre-flight; in-memory or isolated core; bytes vs
  node-count reported separately).
- **B-8** → parent §5 two-workspace rule.
- **B-9** → parent §2.4 (`RebindReport` "preserved" scoped to type/role; `candidates_ge_tau`
  redefined/renamed; provenance fields incl. the ER-A3 policy identity).

## Bucket C — text fixes (**applied 2026-07-17**, with the Bucket-A amendments)

- **C-1 (ER-15a):** §7 dated correction — "(pending G-2)" → "(G-2 landed `7e5d612`, 2026-07-09;
  this section records the pre-landing proposal)".
- **C-2 (ER-16):** §2.6 "tracemalloc measures it" → cite the A1 ruling (tracemalloc for the
  item-2 red; child-process RSS for the replacement mechanism); folds naturally into ER-A1's
  §2.6 rewrite.

## Bucket D — no action (recorded)

- **ER-14b:** "anchor-located as a new reason" exists in no revision (working tree, HEAD,
  discussion file); A7 already specifies `reason=None` + `located_by` provenance.
- **ER-15b:** scaffold-weight objection is process opinion against ruled scope (PR-1…5, A1…A7).

## Sequencing note

ER-A1 gates **item 3** (the #48 port) and the INV-6 green target, and informs the DR-4 anchor
contract test; it does **not** gate item 2's Component 0 (drift generator), the oracle, or the
INV-1…3 fixture reds, which are architecture-independent (they red against the shipped cubic
DP either way). ER-A2 gates INV-1's fixture family before its red is authored. The Bucket B
items land as spec text in the item-2/#48 documents before the corresponding tests are written
(red-first: each new obligation gets its violation seen red, per the plan's §4 discipline).

## Rule-A delta re-audit (2026-07-17) — record

Two independent lenses (NARROW: delta line audit incl. own-eyes re-verification of every embedded
factual claim, which independently reproduced the 50/5 tokenless-atom count; WIDE: staleness sweep
of everything outside the delta across all engine docs + rebind.py docstrings) plus the
reconciler's own leg (`load_workspace_streams` rejection, `addopts` absence, tie-break page-equality
path). **Findings: 2 converged defects, 9 verified lone-lens findings, 0 dropped-as-wrong. All
acted same day** (this remediation is itself the delta of the follow-up pass below):

- **Fixed:** item-2 §0 lock-trigger extended to the §2.8 fixed constants (the parent's claim was
  unpropagated); §5 harness memory instrument corrected to the §2.6 tracemalloc/RSS split; the B-1
  per-slot correction's scope extended to §2.3; item-2 INV-1 Property/Red-first now carry ER-A2
  (positional conjunct + its named "maps-far" red mutant); the delete+identical-insert exclusion
  made generator-enforceable (forbidden composition; expressible only as a move — parent §4 INV-1
  + item-2 §1.3); INV-4 gains the capped-out-gap class (single synthetic unaligned block →
  no-candidate) mirrored in parent §2.2; §0/§1 ER-A1 notes added (anchored pipeline, decade
  qualifier, contrast-paragraph scoping); tracker S5.1-R "node token-span"→per-slot +
  B-9-scoped Report preservation; tracker S4.7 row ≥2-decades note; `_pin_ok`/`_on_region_page`
  attribution corrected; ER-7's line-number cite → section anchor; short-form fold tags normalized
  to `[Folded per dispositions B-…]`.
- **Deliberately left (pre-delta, logged):** the two findings docs' "awaits G-2" staleness
  (dated 2026-07-08 snapshots; G-2 landed 2026-07-09); the discussion trail's historical content
  (allowed to be stale by design).

**Follow-up pass (Rule A on the remediation):** reconciler-only, grep-verified tag set + re-read of
every remediation site; no new findings. Suite state untouched (doc-only delta; no code changed).

## Sign-off focused read (2026-07-17) — record

Ben's focused read of the item-2 spec's flagged content, per the post-audit plan (INV-4 math +
the two audit-sharpenings; the already-Ben-ratified items not reopened):

- **INV-4 half-open boundary classification (the interval math authored at rev 2.1, never
  previously Ben-audited): audited.** Presented with per-point verification (class coherence,
  coverage of `b ∈ [0, n]`, disjointness under the tiling property, stream-end degenerates).
  One consequence made explicit at Ben's direction: both edges of a `delete` block project to
  the same fresh position (empty fresh interval), so two old boundaries flanking a
  wholly-deleted span collapse onto one fresh gap — recorded as a `[Sign-off note 2026-07-17]`
  in the edge-candidate bullet; behavior judged honest, not a defect.
- **Both audit-sharpenings [Ben-confirmed 2026-07-17]** as faithful implementations of prior
  rulings, not new rulings:
  - (a) delete + byte-identical insert is **generator-FORBIDDEN** (expressible only as an
    ancestry-preserving move) — forced by ER-A2's exclusion composed with the §1.3 relation law
    "∅ reserved for delete"; oracle-side filtering rejected as re-introducing the ambiguity the
    ruling removed. Sites: parent §4 INV-1; item-2 §1.3.
  - (b) a capped-out gap enters the INV-4 tiling as a **single synthetic unaligned block →
    no-candidate** (interior; edges follow the general edge-candidate rule) — forced by ER-A1
    (refused gaps project nothing) + DR-2 (never invent a boundary) + A7 (locate-within-window,
    with the gap's inter-anchor fresh span as the region constraint). Sites: parent §2.2;
    item-2 INV-4.
- **PR-3 verified still unruled** (spec header: deferred-for-information, mechanism pinned).
- Housekeeping note: the "deliberately left" findings-doc staleness recorded in the audit
  section above was subsequently closed (dated G-1/G-2 closure notes in both findings docs,
  same commit `25d8a55`), at Ben's direction, before commit.

**Sign-off stamp:** the spec is **SIGNED OFF (Ben, 2026-07-17)** — the ratifying act is
"I confirm both readings" at the close of the focused read above; Ben clarified 2026-07-18 that
this confirmation was intended as the full document sign-off (recorded verbatim, both dates, so
the provenance is exact). Header updated; build authorized per spec §3; the §0 prereg bundle
remains a Ben-ratified gate before any red run.

## Ceremony-budget ruling (Ben, 2026-07-18)

Ben: «We need to cut down on the ceremony. I've let it get too onerous because while it may have
served a purpose, adding ceremony to every single decision to the n-th degree means I'm less
likely to pay attention to the important things because everything has the same effective level
of importance: "priority must sign off".»

**Effect — escalation is routed by consequence, three tiers:**

- **Escalate (blocking, rare):** reversals/changes of Ben-ruled decisions (DR/G/PR/ER rows),
  exported interfaces & schemas, the live edition/deploy-hold, irreproducible artifacts, and the
  results-driven rulings Ben explicitly reserved (PR-3 confirmation-in-churn; S5.1-RG failure
  routing).
- **Disclose (non-blocking, default):** judgment parameters, forced compositions of ruled
  decisions, audit remediations — done and committed, the judgment calls surfaced in the
  reply/commit; Ben audits on pull.
- **Just do:** mechanical folds, tracker syncs, red-first internals, mutation hunts.

**First application:** the §0 prereg-bundle gate is re-ruled from "Ben-ratified before any red
run" to "**authored + committed before any red run, judgment values disclosed**" —
commit-before-measurement is the anti-tuning mechanism, not Ben's eyes. Spec header + §0 venue
paragraph amended with dated notes. Prior sign-offs and rulings are unaffected; this governs
process going forward.
