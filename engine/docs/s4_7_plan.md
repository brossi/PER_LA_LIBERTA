# S4.7 — scale check (D35), and the re-bind re-architecture it forces (plan — rev 3)

**Status: RATIFIED rev 3 — Ben, 2026-07-09.** All decision rows (DR-1…DR-9) and governance forks
(G-1…G-4) are ruled (§3 ledger); build (DoD §8 items 2→6) is greenlit. **One conditional:** DR-3 (the
load-bearing confidence gate) is ratified as *build direction*, **not locked as proven** until INV-1
(never-a-false-bind, over drift + planted repeated passages) is seen red-then-green. Rev 3 replaced
rev 2's mechanism wholesale after a second five-lens adversarial pass (2026-07-08) demolished rev 2's
*candidate-index-as-uniqueness* approach, and after Ben's steer to **stop hand-rolling and reach for the
solved-problem tooling** ([[feedback_solved_problem_first]]). `rebind.py` may now be modified via the
S5.1-remediation route (G-1).

**Amendments after ratification (dated additions, §3):** PR-5, PR-1, PR-2, and PR-4 ruled
2026-07-17 (anchor-family contract under DR-4; INV-1 scoped to `no-geometry`; INV-3 refined to
fail-loud-or-correct-destination; INV-7 two-end-state DoD model — see "Parent rulings" block and the
§8 dated amendment; A7 boundary-verdict reframe added 2026-07-17, see Parent rulings). PR-3
is **deferred-for-information** by design — re-expressed by A7 as **demonstrate
confirmation-in-churn** (undemonstrated → the non-clean boundary classes stay fail-loud as a
measured outcome, no design unwind); its original "demonstrate-or-remove" formulation is
superseded by that re-expression. Decided after the v3 anchor representation + boundary
projection land — not ruled now.

**External-review rulings (Ben, 2026-07-17):** ER-A1…ER-A5 ruled per
`s4_7_external_review_dispositions.md` — **ER-A1** §2.1/§2.6/DR-1: architecture pinned to **anchored
alignment** (the prototype's validated design; the whole-stream-diff reading retired); **ER-A2**
§2.3/§4/DR-3: INV-1 oracle scoped (byte-identical re-insertion of a deleted span → INV-3/PR-2) +
anchor confirmation made **positional**; **ER-A3** DR-9/§8.3: pre-S5.2 strict consumption requires a
registered policy/calibration identity (bound-but-wrong passes `assert_all_bound`); **ER-A4** G-4
re-worded to a **per-slot rebind-eligibility** precondition (never authoring invalidation); **ER-A5**
D35 coherence note added in `ENGINE_STRUCTURE_PLAN.md`.

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
**[ER-A1 note, 2026-07-17]** After the ER-A1 rewrite, layer (1) is the **anchored** §2.1 pipeline
(k-gram anchor index → LIS → capped per-gap opcodes) with two contract-fixed constants (k, gap cap —
§2.8), so "(1)+(2) are library + arithmetic" overstates: the anchored layer is designed mechanism
whose correctness-at-density §8 item 4 measures. And the gate is asserted across **≥2 decades**
(§5); this section's "10⁴→10⁵" names the top decade of the sweep.

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
Diff is the right complexity class by construction. **[ER-A1 note, 2026-07-17]** This ms-scale
contrast validates the complexity *class* on small near-duplicates; the normative mechanism is
§2.1's **anchored** pipeline — a whole-stream diff is not the gate architecture (its opcode APIs
are `O([N/64]·M)` time **and** memory).

---

## §2 The re-architecture (B): diff-based annotation re-anchoring

### §2.1 Layer 1 — alignment (anchored — the architecture the prototype validated)

**[Rewritten per ER-A1, Ben-ruled 2026-07-17 — `s4_7_external_review_dispositions.md`.]** Rev 3 as
ratified specified one whole-stream opcode diff here. That is **not** the architecture the prototype's
linear evidence validated, and `rapidfuzz`'s packaged opcode APIs document `O([N/64]·M)` **time and
memory** — at gate scale a whole-stream diff is neither linear nor O(N)-memory. The normative
architecture is the prototype's **anchored alignment** (`s4_7_prototype_findings.md` "The mechanism"):

1. Materialize the **old** and **fresh** canonical included streams as **token lists** via the shared
   `normalize_tokens` (the same normalizer the fingerprint uses, so alignment and scoring agree). Each
   token carries a back-pointer to its atom id + intra-atom offset.
2. **Anchor:** k-gram shingle index over both streams; **unique-in-both** shingles become landmark
   anchor pairs.
3. **Chain:** longest increasing subsequence over the anchor pairs (patience, O(A log A)) → a monotone
   anchor chain (reorder crossings drop out).
4. **Fill:** between consecutive chained anchors, align the small bounded gap with per-gap opcodes.
   **Tool (DR-1, ruled):** `rapidfuzz.distance` (`Indel.opcodes` or `Levenshtein.opcodes` — variant
   resolved at the R-b measured decision); `difflib.get_opcodes()` is the zero-dep stdlib fallback.
   Both return `(tag, old_lo, old_hi, new_lo, new_hi)` blocks. A gap wider than the **gap cap** fails
   loud — the cap is what bounds worst-case work (Σgap² ≤ cap·N = O(N) regardless of anchor density),
   and it is the same knob §8 item 4's anchor-poor gate measures correctness against.

The gap cap and k are **contract-fixed design constants** (the DR-4/PR-5 discipline — a violating
change reds a contract test), not calibration knobs; τ stays the only calibrated parameter (§2.3,
S5.2). **No dependency added** (rapidfuzz present; difflib stdlib) — satisfies Principle 2.

**[Folded per dispositions B-2 (ER-7), 2026-07-17]** At the R-b resolution point the backend is
pinned as a **conformance identity** — library + version + variant + options + **opcode semantics**
(Indel has no `replace`: a substitution arrives as insert+delete; Levenshtein emits `replace` — the
boundary classification consumes whichever shape is pinned) + tie behavior — recorded in the §2.8
ledger. The `difflib` fallback either receives its **own conformance contract** (its junk policy is
proven load-bearing on real streams — `test_align_streams_pins_explicit_autojunk_and_it_is_load_bearing`)
or is **dropped**. **[Folded per dispositions B-6]** A cheap **near-duplicate pre-check** (stream length ratio + chained-anchor
density floor) runs before any alignment work: inputs that are not near-duplicates fail loud instead
of paying a degenerate alignment.

### §2.2 Layer 2 — projection (arithmetic)

Each node owns an old atom-span → an old **token**-span `[t0, t1)`. Map each boundary through the
opcodes to a fresh token index, then back to a fresh atom span:
- A boundary inside an **`equal`** block maps exactly (offset preserved).
- A boundary inside a **`replace`/`insert`/`delete`** block is *ambiguous by construction* — the old
  position has no exact fresh image. **Rule (DR-2, [review], fail-loud-biased):** a node whose
  **boundary** lands in a non-`equal` block does not get a silently-invented fresh boundary; it is a
  `below-threshold`/`ambiguous` finding unless the confidence gate (§2.3) independently confirms the
  span. Never round a boundary into a neighbor's atoms (the R2 discipline). **[ER-A1 note,
  2026-07-17]** "the opcodes" here = the **composite projection**: chained anchor positions project
  exactly; per-gap opcodes cover the spans between them; a capped-out gap projects nothing (its
  boundaries land in this same fail-loud rule). **[Audit sharpening 2026-07-17]** In the boundary
  classification (item-2 INV-4) a capped-out gap enters the tiling as a **single synthetic
  unaligned block** — preserving the one-non-`equal`-between-`equal`s tiling property — so a
  boundary interior to it routes **no-candidate** (A7's locate-within-window applies, with the
  gap's fresh interval as the region constraint).

**[Folded per dispositions B-1 (ER-4), 2026-07-17 — the projection contract, correcting this
section's "each node owns an old atom-span" shorthand:]**
- **Per-slot, not per-node.** The projected unit is the **owning slot** (`body` / `heading` /
  `signature` — `FINGERPRINT_SLOTS`); a container owns separate heading and signature spans with
  descendants between them. Every rule in this section **and §2.3** binds per slot **[scope
  extended 2026-07-17, audit fix]** — §2.3's surviving "node" shorthand ("candidate fresh span per
  node", "the node's stored fingerprint", "each node stores boundary anchors") reads as "the
  node-slot owning the span" (fingerprints and anchors are per-slot: `FINGERPRINT_SLOTS`).
- **Shared seam boundaries resolve once.** Adjacent slots sharing a token gap resolve that boundary
  as **one shared object**; both slots' spans derive from it. Independent per-slot resolution of a
  shared seam (which can assign an inserted run to both sides, neither, or opposite sides) is
  forbidden — the disjointness gate (§2.4) is the backstop, not the mechanism.
- **Token-clean but atom-unrepresentable.** A token boundary that maps cleanly but lands **interior
  to one merged fresh atom** is unrepresentable in the atom-id map (slots own whole atom ids) → a
  fail-loud finding, never rounded (DR-2). The diff sees nothing wrong in this case; it is a
  distinct failure class from boundary-in-edit-block.
- **Tokenless atoms.** `normalize_tokens` drops punctuation-only atoms, so an included atom can
  carry **no token back-pointer** (the real PLL canonical has 50 such included atoms, 5 of them the
  final atom of an owning slot) — yet the coverage contract requires every included atom owned.
  **Rule ([Ben-ratified] 2026-07-17):** a tokenless atom's fresh ownership derives from its
  **neighboring tokened atoms' resolved slots** (interior → the enclosing slot; slot-final/seam →
  the shared-boundary object decides); neighbors resolving to different slots with no
  shared-boundary decision → a fail-loud finding. Red-first tests in item 2 (§1.2 fixture floor)
  before the item-3 implementation.

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
  bespoke tiling's whole-stream uniqueness count** without its O(N³) cost. **[Amended per ER-A2,
  Ben-ruled 2026-07-17]** Uniqueness alone is **insufficient**: the anchor must also be
  **positionally confirming** — its located fresh occurrence must coincide with the diff-projected
  boundary (or, in A7's no-candidate class, fall within the diff-narrowed window). Bare
  unique-in-both counting admits the prototype's real false-bind mode (a unique-in-both token that
  "maps far"); located ≠ projected → `ambiguous`, fail-loud.

Uniqueness is thus a property of **anchors**, computed once over the whole stream — so it is *not*
subject to a span/cluster/band parameter (rev 1/rev 2's fatal knob). The only tunable is τ, which is
**S5.2's** to calibrate (§6). No new calibration surface. **[ER-A1 note, 2026-07-17]** §2.1's gap
cap *is* a bounded-work parameter — the difference from rev 1/2's fatal knob is that it is a
**contract-fixed design constant** (a change reds its DR-4-style contract test; never calibrated
per-book), and its correctness impact is measured explicitly by §8 item 4's
correctness-at-density axis. The only **calibrated** parameter remains τ. The full parameter ledger
is dispositions item B-3.

### §2.4 The three geometry modes + the S5.1 contracts (preserved)

- **Modes** re-express onto the projected span: `geometry-primary` pins the projected fresh span to the
  node's `region.page` (a projected span off-page → fail-loud); `geometry-tie-break` uses geometry only
  to disambiguate a non-unique anchor (never to rescue a sub-τ span); `no-geometry` = content + anchors
  only. Read from `manifest.segmentation.geometry_mode` as S5.1 does. **[Folded per dispositions B-5 (ER-10),
  2026-07-17]** "Independently valid geometry disambiguation" (PR-1) is **defined executably as
  page-equality against the stored region seed** — exactly what the shipped page checks implement
  (`_pin_ok`, the `geometry-primary` pin; `_on_region_page`, the tie-break resolution path — both
  page-equality only).
  The stored `Region` is a first-own-atom *seed*, not an extent, so bbox/distance comparison,
  same-page duplicate discrimination, and multi-page extent semantics are **named non-goals** until
  a ruling adds them. Consequence (INV-5 / item-2 §1.6): byte-identical copies on the **same page**
  are geometry-indistinguishable → `ambiguous` in every mode; only a distinct-page copy may be
  disambiguated in geometry modes.
- **Preserved unchanged:** `node_id` identity; the non-raising `rebind()` + strict `assert_all_bound`;
  the **closed reason enum** (`zero-candidate | ambiguous | below-threshold | missing-anchor |
  stale-decision | global-conflict`) — diff/projection outcomes map onto it; the **re-stamp protocol**
  (mechanical `extent_digest` re-stamp on bound nodes, `decision_digest` never machine-refreshed); the
  `RebindContext` dual-hash baseline; `RebindResult`/`RebindReport`; **[Folded per dispositions B-4 (ER-9)]** and the
  **always-on global disjointness gate** (the `_contested_nodes` analog → `global-conflict`) —
  carried forward **explicitly** (rev 3's original text omitted it from this list; the prototype
  proved it load-bearing, the INV-3 merge red). **[Folded per dispositions B-9 (ER-14a)]** "Preserved" for `RebindReport`
  means the **type and its role**, not every field's semantics: `candidates_ge_tau` is defined as
  *full-tiling-compatible windows ≥ τ*, which has no meaning under diff projection — #48
  **redefines or renames** the ambiguity signal (anchor/candidate-based), and adds the provenance
  fields: backend identity (B-2), policy/calibration identity (ER-A3), boundary classification +
  confirmation method (`located_by`, A7) — all inside the open v3 schema window (G-3).
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
  (ii) extend projection to multi-interval spans. **[G-4 as amended 2026-07-17, ER-A4: (i) is
  re-worded — a per-slot rebind-eligibility precondition, fail-loud at rebind, never map
  invalidation; see §3.]** PLL's frozen map is contiguous (but only vacuously —
  it has no embedded-letter node), so (i) is viable for PLL now; the engine-general answer is a ruling.
- **R-d: the `evidence_findings` / `_restamp` deep-chain O(N²) is a SEPARATE sub-problem** — unaffected
  by the matcher choice, likely needs its own standard answer (Merkle/rolling subtree digests). §2.7.

---

## §2.6 Complexity + memory

**[Rewritten per ER-A1 (+ dispositions C-2), 2026-07-17.]**
- Alignment: anchored (§2.1) — measured **linear** on the real 171k-token stream across ≥2 decades
  (prototype: exponent ≈1.0, ≤~2 s / 70 MB at full book); the gap cap bounds worst-case per-gap work
  to O(cap·N). A whole-stream `rapidfuzz` opcode call is NOT this bound — its packaged docs state
  `O([N/64]·M)` time **and memory**; the anchored decomposition is what makes both linear. INV-6
  measures the as-built op.
- Projection + confidence: one pass over the composite projection + O(1)-per-anchor index lookups →
  **O(N)**.
- Memory: replaces the O(K·N) DP matrices (which **OOM at 10⁵**, rev 1/2 confirmed) with O(N) token
  lists + O(N) anchor index + bounded per-gap alignments. Measurement: item 2's red uses
  `tracemalloc` (sufficient — the shipped cubic DP's allocations are Python-managed; item-2 ruling
  A1); the replacement mechanism's native `rapidfuzz` allocations are invisible to `tracemalloc`, so
  its memory evidence uses the child-process-RSS design (item-2 §5.2 handoff). A `tracemalloc`-only
  number for the new mechanism is not evidence.

## §2.7 The evidence-composite hot path (separate, honestly open)

`evidence_findings`/`_restamp_evidence` are O(entries × subtree); on a **deep** chain Σ|subtree| =
O(N²), and `extent_digest` hashes the materialized sorted union → **no digest-preserving O(N) fix** by
naive memo. Candidate standard answer: **Merkle/rolling subtree digests** (a node's digest from its
children's digests) — investigate. Decide (DR-6) whether #33 closes this or characterizes-and-defers on
the measured number ([[feedback_deferral_for_information]]); **never relax the ceiling**
([[feedback_no_cheating_results]]). Real books are shallow (PLL depth 4) so the pathology is a synthetic
worst case — state which shape each gate result speaks to.

## §2.8 Parameter ledger (folded per dispositions B-3 (ER-8), 2026-07-17)

§2.3's "the only tunable is τ" is precise only as "the only **calibrated** parameter." The full
behavior-relevant parameter set, each with its class and owner — a change to any **fixed** row reds
its contract test and **voids the DR-3 lock record** (the item-2 §0 invalidation trigger extends to
these constants):

| Parameter | Class | Owner / test |
|---|---|---|
| `W` — total boundary-anchor footprint (prefix+exact+suffix together) | fixed design constant (PR-5) | #48; DR-4 contract test; the item-2 §1.5 skeleton names the constant |
| prefix/exact/suffix width allocation within `W` | fixed design constant (PR-5) | #48; DR-4 contract test (the byte-identity argument holds under any split) |
| `k` — shingle length (anchor index) | fixed design constant — correctness-relevant (the prototype k-sweep is **inverted**: longer k worsens seam false-binds) | #48; contract test; item-4 density sweep measures impact |
| gap cap (anchored fill, §2.1) | fixed design constant — the linearity/correctness coupling knob | #48; §8 item 4 correctness-at-density axis |
| backend identity (library, version, Indel-vs-Levenshtein variant, options, opcode semantics, tie behavior) | pinned conformance identity at the R-b resolution point (B-2) | #48; conformance tests; fallback contract or drop |
| anchor match mode (anchor's own match ratio, A7) | design-fixed per A7; ratio governed by τ | #48 / INV-4 |
| τ — confidence threshold | **calibrated** | S5.2 (DR-9) |

No row is a per-book tuning surface; only τ ever moves post-ship, and only via S5.2.

---

## §3 Decision ledger (rev 3)

| # | Decision | Disposition |
|---|---|---|
| DR-0 | **Direction:** solved-problem tooling (diff-based re-anchoring), not a bespoke matcher | **[Ben-ruled]** 2026-07-08 (the reframe steer; the specific mechanism below is [review]) |
| DR-1 | Alignment tool = `rapidfuzz.distance` (present) default; `difflib` (stdlib) fallback | **[Ben-ruled] 2026-07-09** (Indel-vs-Levenshtein variant deferred to the R-b measured decision) **[Amended 2026-07-17, ER-A1]** the *architecture* is pinned: **anchored alignment** (unique k-gram anchors → LIS → capped per-gap opcodes, §2.1 as rewritten); the ratified whole-stream-diff reading is retired (packaged complexity `O([N/64]·M)` time+memory); the tool choice is unchanged and applies per-gap |
| DR-2 | Boundary-in-non-`equal`-block → fail-loud-biased finding, never a silently-invented boundary | **[Ben-ruled] 2026-07-09** |
| DR-3 | Confidence gate = ratio ≥ τ **and** boundary-anchor uniqueness in both streams (§2.3) | **[Ben-ruled] 2026-07-09 — build direction only; NOT locked as proven until INV-1 (never-a-false-bind, over drift + planted repeated passages) is seen red-then-green** (load-bearing) **[Amended 2026-07-17, ER-A2]** anchor confirmation is **positional** (located occurrence == diff-projected boundary; window-contained in A7's no-candidate class); INV-1's fixture family excludes byte-identical re-insertion of a deleted span (reclassified → INV-3/PR-2) |
| DR-4 | Stored anchors enriched to prefix+exact+suffix context (schema v2→v3 touch) | **[Ben-ruled] 2026-07-09** (schema bump = G-3, approved) **[Amended 2026-07-17, PR-5]** anchor-family contract ratified — deterministic / content-only / bounded-total-footprint, see Parent rulings below |
| DR-5 | Modes + S5.1 contracts (reason enum, re-stamp, non-raising) preserved (§2.4) | **[Ben-ruled] 2026-07-09** |
| DR-6 | evidence-composite deep-chain: fix (Merkle/rolling) vs characterize-and-defer, on the number | **[Ben-ruled] 2026-07-09 — characterize-and-defer**: measure the deep-chain number at scale, **never relax the ceiling**; open a follow-up only if the synthetic worst case proves it matters |
| DR-7 | Scale fixture built on the S1.5 store round-trip primitives (not a new persistence path) | **[Ben-ruled] 2026-07-09** (framing pinned: the store *primitives* are reused; the scale fixture itself is **new work**, §5) |
| DR-8 | CI: always-on small ratio + `@pytest.mark.scale` 10⁵ nightly | tracker-fixed |
| DR-9 | **Zero-false-bind ownership:** S4.7 ships the abstention/fail-loud *mechanism* (`below-threshold`/`ambiguous` reason enum + `assert_all_bound`→`RebindError`); **S5.2 owns the τ calibration that drives the residual to zero.** S4.7 DoD = strict-with-characterized-residual (INV-1 by construction + every survivor magnitude/foreign-content-detectable), **not literal zero** (§8.3). Safe: no consumer of binds exists yet — only `tests/unit/test_rebind.py` calls `rebind()`, no `steps/*.py` imports `engine.structure`, no S5.2 module. Split already encoded in `rebind.py` `RebindPolicy` ("S5.1 ships a default; S5.2 calibrates"). Wiring obligation: any future consumer of bound spans runs post-S5.2 or via the strict `assert_all_bound` path. | **[Ben-ruled] 2026-07-09** (consumer trace this session) **[Amended 2026-07-17, ER-A3]** `assert_all_bound` rejects only *unresolved* nodes — a bound-but-wrong span passes it, so the strict path alone does not shield a consumer from the characterized residual. Strict consumption **pre-S5.2** additionally requires a **registered policy/calibration identity** carried in the report (a #48 schema field, beside `located_by` and the B-9 provenance fields); a result lacking it is **not-for-consumption** |

**Governance forks — all resolved (Ben, §7):**
- **G-1 [RULED 2026-07-09]:** rev 3 replaces the whole S5.1 matcher → **routed as S5.1 remediation, issue #48** (referenced by #33), not folded into #33's scale-check scope — so the provenance that S5.1's shipped mechanism was replaced stays visible.
- **G-2 [LANDED 2026-07-09]:** the `s5_1_plan.md` §1.3 falsified-claim correction — applied (commit `7e5d612`).
- **G-3 [RULED 2026-07-09]:** the schema v2→v3 anchor-enrichment touch → **bump to 3** (window open; only internal fixtures + the PLL probe pin v2; migrate them, no v2/v3 dual-support).
- **G-4 [RULED 2026-07-09]:** the R-c contiguity ruling → **adopt (i) now** — enforce "container subtree = one contiguous included span" as a fail-loud validated authoring precondition; **defer (ii)** multi-interval spans for information until a genuinely interleaved book constrains the design. **[Amended 2026-07-17, ER-A4]** (i) is re-worded: contiguity is a **per-slot rebind-eligibility precondition** — a slot whose owned atoms are not one contiguous included span **fails loud at rebind** (a named finding), and the map stays **valid**; NOT an authoring invalidation, which would contradict the ratified §3.B.6 non-contiguous-leaf-body model, its green regression (`test_body_atoms_ascending_but_non_contiguous_passes`), and the D18 differ fixture. (ii) stays deferred as ruled.

**Parent rulings — item-2 scaffold escalations (`s4_7_item2_invariants_plan.md`):**
- **PR-1 [RULED 2026-07-17, Ben]:** §4 INV-1's "non-unique boundary anchor forces `ambiguous`,
  never a lone bind" is **scoped to content evidence alone (`no-geometry` mode)** — reconciling it
  with §2.4/DR-5's preserved `geometry-tie-break` contract (the mode the S2.2 re-gate ruled for
  PLL), under which an **independently valid geometry disambiguation** may resolve a non-unique
  content anchor into a lone bind; that per-mode behavior is gated by **INV-5** (mode
  orthogonality), not INV-1. The safety property is not relaxed: absent independent geometry
  confirmation, a non-unique anchor still lands `ambiguous` in every mode. Item 2 runs INV-1's
  fixtures in `no-geometry`; uniqueness quantifiers as pinned in review (whole-stream, canonical
  included stream, both boundary anchors). Coheres with PR-5: contamination of the content anchor
  banned, separate independent disambiguation legal. The alternative (absolute over all modes) was
  **rejected** — it would strip `geometry-tie-break`'s ratified power, a mechanism change
  contradicting DR-5 and the S2.2 re-gate.
- **PR-2 [RULED 2026-07-17, Ben]:** §4 INV-3's title/property "reorder/move **fails loud**" is
  amended to the review's refined form: a moved block either **fails loud OR binds to its planted
  destination with a globally-valid structure map — never a bind elsewhere**. Rationale: "fails
  loud" as a required outcome baked the current diff mechanism's limitation (move = delete+insert,
  R-a ⇒ it cannot correctly bind a move) into the ratified invariant, so a future mechanism that
  correctly binds a moved block would red a test detecting no harm — a constraint preserving a
  test's failure mode with no architectural justification. The safety property INV-3 protects is
  "never a silent bind *elsewhere*," and the amendment states exactly that. Destination-correct
  atom binds with invalid structure-map results stay red; cross-container moves get separate
  fixtures. The alternative (keep fail-loud absolute) **rejected** per the above.
- **PR-4 [RULED 2026-07-17, Ben]:** the DoD is amended (see §8 dated amendment) so **INV-7 may close
  honestly-unresolved** under DR-6's characterize-and-defer: two end-states only — green, or
  unresolved-with-named-follow-up (isolated `xfail(strict, reason=<issue>)` budget test +
  characterization artifact as the accepted deliverable + DoD item-3 annotation). Ceiling
  **pre-registered, independent of the measured baseline, never moved**; deep-chain depth bounded
  with a pre-flight non-failure proof. Rationale: §4 INV-7's own text ("algorithm fixed **or scoped
  follow-up**") and DR-6 already permit the deferred outcome — the DoD's "INV-1…7 red-first / suite
  green" phrasing was the drafting gap. The alternative (INV-7 must be green to close S4.7)
  **rejected**: it re-litigates DR-6 and expands #48 by an unbounded algorithmic item before the
  measurement exists.
- **PR-5 [RULED 2026-07-17, Ben]:** the #48 anchor family is contract-constrained under **DR-4**. Every
  stored boundary anchor is (1) **deterministic** — same content → same anchor (re-derivability is what
  comparing fresh-stream anchors against schema-v3 stored anchors requires); (2) **content-only** — no
  positional/structural component folded into the content boundary anchor (it would fail under exactly the
  positional drift the anchor exists to survive). The contract bans *contamination*, not future
  disambiguation: a **separate** independent positional signal (e.g. `geometry-tie-break`) remains legal;
  (3) **bounded total footprint** — a finite max width **W bounds prefix + exact + suffix together**, so
  the INV-1 fixture plants the entire selected `exact` content plus >W context, twice, and the
  byte-identity argument holds however #48 splits its width budget between components. Enforced by a
  **DR-4 contract test** built in item 2: a later violating anchor choice reds the contract instead of
  silently invalidating INV-1's representation-agnostic red (the DR-3-locking red). The alternative — a
  specifically ratified minimal non-unique anchor fixture — was **rejected** as the test-only-representation
  divergence trap (item 2 must not mint a constructor production can diverge from).
- **A7 [RULED 2026-07-17, Ben — dated addition]:** INV-4's boundary **verdict model is reframed**
  (item-2 spec rev 2.2, after a contrarian pass on the rev-2.1 two-token convention): the
  opcode/boundary classification **routes** (clean-candidate / edge-candidate / no-candidate /
  two-candidate — candidate well-definedness + churn context), and the **DR-3 confidence gate is
  the uniform confirmation path** for every boundary verdict — the literal reading of DR-2's
  "unless the confidence gate independently confirms." Diff proposes, anchor confirms; a boundary
  is never invented from the diff alone. In the **no-candidate** class (boundary interior to an
  edit block, where the diff proposes no position) the anchor may **locate** the boundary within
  the diff-narrowed window — the block's fresh interval is the region constraint, so this is
  confirm-within-diff-constraint, loud and τ-gated: a **stated, deliberate extension of DR-2's
  "confirms," part of this dated amendment**. A successful confirmation/locate **binds with
  `reason=None`** like every bind; the method is recorded in an **additive bind-provenance field**
  (a #48 schema addition) — **DR-5's closed failure-reason enum is untouched** (every member
  stays an abstention/failure reason). The categorical two-token rule (any non-`equal` contact
  → fail-loud unless an exception branch rescues) is retired: if confirmation proves weak in
  churn, the mechanism degrades to that conservative behavior as a **measured outcome**, not a
  design commitment. **PR-3's question is re-expressed as "demonstrate confirmation-in-churn"**
  (still deferred-for-information, unchanged in status). One gate-letter extension pinned for the
  #48 skeleton: positional confirmation leans on the anchor's own match ratio.

---

## §4 Red-first invariants

- **INV-1 (never a false bind):** over randomized drift fixtures incl. planted repeated passages
  (within- and cross-container), the bound set ⊆ a brute-force alignment oracle's bound set; a
  non-unique boundary anchor forces `ambiguous`, never a lone bind **on content evidence alone
  (`no-geometry` mode) [amended per PR-1, 2026-07-17]**; in geometry modes an **independently
  valid geometry disambiguation** may resolve a non-unique anchor — that per-mode behavior is
  INV-5's (mode orthogonality), not INV-1's. Item 2 runs INV-1 in `no-geometry`; uniqueness is
  whole-stream over the canonical included stream, both boundary anchors required unique. Oracle
  defined from **fixture ground truth** (planted positions), not from the mechanism's own output.
  Mutation-hunt primary. **[Amended per ER-A2, Ben-ruled 2026-07-17]** Oracle scope: the fixture
  family **excludes byte-identical re-insertion of a deleted span** — on content evidence it is
  observationally indistinguishable from a move, so it is reclassified as a move-destination case
  under INV-3 (PR-2's form), never an INV-1 false-bind. Enforcement is the generator's **[audit
  sharpening 2026-07-17]**: the drift config **forbids composing** delete(X) with insertion of
  byte-identical X-content — that intent is expressible only as an ancestry-preserving **move**
  (item-2 §1.3), whose planted destination INV-3's oracle can then check; a planted
  delete+identical-insert is a fixture-authoring error, not an oracle case. Anchor confirmation is
  **positional** per §2.3 as amended (located == diff-projected; window-contained in A7's
  no-candidate class).
- **INV-2 (binds under drift — anti-inertness):** on real re-segmentation / char-sub fixtures the
  mechanism **binds** the nodes it should (a fail-loud-on-everything mechanism fails this). *Scoped as a
  by-construction existence check, NOT a rate over a realistic model — that is S5.2.*
- **INV-3 (reorder/move never silently mis-projects):** a moved block either **fails loud OR binds
  to its planted destination with a globally-valid structure map — never a bind elsewhere**
  **[amended per PR-2, 2026-07-17]**. A destination-correct *atom* bind with an invalid
  *structure-map* result (container reading-order / contiguity / decision topology) is not green.
  Fail-loud-only is the documented expected outcome of the current diff mechanism (a move is
  delete+insert, R-a) — a scoped observation, not the ratified property. *[Clarified 2026-07-17:
  "the current diff mechanism" means the #48 diff design this plan specifies, not the shipped
  monotone-tiling DP — the DP is not a diff mechanism and its move behavior is undocumented.]*
  Cross-container moves get
  separate fixtures so a contiguity/`global-conflict` red is never mistaken for an R-a red.
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
ops timed with serialize+load+index inside the span; `perf_counter` wall-clock; memory per the
§2.6 split **[audit fix 2026-07-17]** — `tracemalloc` peak for the item-2 red against the shipped
Python-managed DP; the child-process-RSS design (item-2 §5.2 handoff) for the as-built replacement
mechanism, whose native `rapidfuzz` allocations `tracemalloc` cannot see.
CI = always-on small ratio + `@pytest.mark.scale` 10⁵ nightly. **Framing (DR-7, pinned unambiguous per
Ben 2026-07-09):** what is reused from S1.4/S1.5 is the **store round-trip *primitives*** (`save_stream`
/ `load_stream`) — **not a fixture.** No scale fixture exists; the size-parameterized scale fixture is
**new work built for S4.7**. Any tracker/plan wording that reads as "shares an existing benchmark
fixture" is to be corrected to "reuses the store primitives; builds its own scale fixture."

**[Folded per dispositions B-6/B-8 (ER-11/ER-13), 2026-07-17]**
- **Variables pinned per fixture:** every scale result names `L` (leaf nodes), `K` (slots), `A`
  (atoms), `T` (tokens), `D` (depth) and the fixture's relationships among them — a bare "N" is not
  a reportable axis. Growth is asserted across **≥2 decades** (INV-6's quantifier; D35's 10⁴→10⁵
  tier is the top decade of the sweep, not the whole sweep).
- **CI wiring is explicit:** the `scale` marker must be **registered** in `engine/pyproject.toml`
  and **deselected from default runs** (addopts `-m "not scale"` or an equivalent nightly-only
  workflow). Both CI workflows currently run bare `pytest -q` and the registered markers are only
  `golden`/`integration` — an unregistered mark would run the 10⁵ tier on every push.
- **Two workspaces:** the harness persists the old and fresh canonical generations in **separate
  workspaces** — `load_workspace_streams` hard-rejects a second canonical-kind stream, and the
  sanctioned two-canonical form is S5.2's open decision (tracker S5.2 row item (b)), not pre-empted
  here.

---

## §6 Out of scope
τ calibration + three-rate negatives = **S5.2**. Real-PLL re-extraction = needs S4.6. Human O3 = D35.
INV-2's drift fixtures are by-construction existence checks, **not** S5.2's perturbation-model rates.

---

## §7 Governance: the falsified `s5_1_plan.md` §1.3 claim

`s5_1_plan.md` §1.3 (ratified) says the DP "holds it to one near-linear pass." **False** (deferred, not
built; shipped is O(K·N³) — §1). Rev 3 proposed (G-2 **landed**, commit `7e5d612`, 2026-07-09 — this paragraph records the
pre-landing proposal): a dated correction
note preserving the original claim, flagged falsified-by-#33, pointing here; route the rewrite as S5.1
remediation (G-1); correct the stale S5.1 tracker-row text (still reads "joint monotone-tiling
assignment," which #33 replaces) and the S4.7 Deliverable text.

---

## §8 Definition of Done
1. Plan ratified; `[review]` rows + G-1…G-4 resolved. 2. INV-1…INV-7 red-first (drift generator built
so INV-2/INV-3 can be seen red). **[§5.2 split, Ben 2026-07-09]** INV-6/INV-7 are seen RED **in item 2**,
against the shipped cubic `_Assignment` / O(N²) deep-chain, **before** the G-1 port (#48) deletes them
(now-or-never — after the port they could only red against a contrived mutant); item 2 builds the
*minimal* size-parameterized fixture + `perf_counter`/`tracemalloc` wrapper for those reds. 3. Diff-based re-anchor lands; `bound ⊆ oracle` + anti-inertness
proven; suite green (1728). **Acceptance is strict-with-characterized-residual, not literal zero (DR-9, [Ben-ruled] 2026-07-09):** INV-1 holds by construction, and the emitted residual is bounded with every survivor magnitude/foreign-content-detectable (routed to the worklist, handed to S5.2 which owns τ-calibrated zero). Forcing "literal zero" here would hard-code a τ value S4.7 explicitly defers (`RebindPolicy`: "S5.1 ships a default; S5.2 calibrates"), baking an uncalibrated knob into the mechanism. Wiring obligation: any future consumer of bound spans runs post-S5.2 or via the strict `assert_all_bound` path — **[amended per ER-A3, 2026-07-17]** where the strict path additionally requires the registered policy/calibration identity (DR-9 as amended); `assert_all_bound` alone rejects only unresolved nodes and passes a bound-but-wrong span. 4. **Productionize** the scale harness + CI (the minimal timing/`tracemalloc` scaffolding is built in item 2 for the INV-6/7 reds — item 4 is **not** build-from-zero): CI tiers (always-on small ratio + `@pytest.mark.scale` 10⁵ nightly), the full anchor-poor **sweep**, ratios (wall-clock + peak-mem, deep + wide) in
`docs/probes/s4_7_scale.md`. **[ratified DoD requirement — Ben, 2026-07-09]** the harness must
include a **deliberately anchor-poor fixture** (low unique-in-both k-gram density — the anchor-rich PLL
prose measured 71% type-unique 3-grams, the favorable end), because the gap cap that buys linear *time*
is the same knob that leaks the wrong-content residual: as anchors thin, **time stays linear while
correctness degrades**, so a wall-clock-only ratio passes green while the mechanism silently mis-binds.
The gate therefore measures a **correctness-at-density axis** (residual / fail-loud rate vs. anchor
density and N), not just the timing ratio. See `s4_7_prototype_findings.md` FRAME. 5. Mutation hunt all-killed; wide+narrow + Rule-A clean. 6. `s5_1` §1.3
correction landed (G-2); S5.1 + S4.7 tracker rows corrected; #33 closed; push `origin/spike` only.
Commit only when Ben asks.

**[Closeout 2026-07-19, Ben-approved]:** items 1–5 are satisfied by the committed red-first
manifests, production mechanism audit, registered scale evidence, current all-killed mutation
manifest, and green default suite. Item 6 is the dedicated closeout synchronization: the S4.7 and
S5.1-R tracker rows are `DONE`; #84, #48, #33, and epic #85 receive their evidence and close in that
order; `spike/s4_7` is integrated before S4.6 authoring begins. S5.1-RG remains a separate required
post-S4.6 real-data gate and is not silently folded into #48.

Ben explicitly declined a second 100,000-atom registered campaign at closeout. The retained final
campaign remains the authoritative median-of-five result. The commits after that artifact affect the
separate authoring-evidence gate, evidence-bearing restamp path, and observer telemetry; the
registered production-scale contexts supply no `old_evidence`, so they do not execute the changed
restamp path. This is a disclosed no-rerun ruling, not a claim that the old artifact was regenerated
against the final commit.

**[Amended per PR-4, 2026-07-17] INV-7 completion-state model (items 2/3):** INV-7 has exactly two
acceptable end-states — **(a) green** (within ceiling, or an in-scope fix lands), or **(b) honestly
UNRESOLVED** per DR-6 characterize-and-defer: the characterization artifact is the accepted
deliverable, a named follow-up issue is opened, and the budget assertion is isolated in a
single-purpose test carrying `xfail(strict=True, reason=<follow-up issue>)` — never a silent skip,
never a bare suite-level xfail. Item 3's "suite green" is read as **green with INV-7's state
explicitly annotated** (one of the two states above). Bindings: the numeric ceiling is
**pre-registered and independent** of the measured baseline (derived from D35's CLI wall-clock/memory
rationale — a baseline-derived ceiling is the INV-6 circularity); ceiling never moved; the deep-chain
depth is bounded with a pre-flight proof that construction / schema validation / serialization /
recursion limits do not fail before the measured op (a 10⁵-deep tree must not measure stack failure
and call it the evidence cost).
