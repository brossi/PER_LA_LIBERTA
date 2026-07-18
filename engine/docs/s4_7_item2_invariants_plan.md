# S4.7 item-2 — the red-first invariant harness (build spec — rev 2.2)

**Status: rev 2.2, consolidated + delta-audited — FOR SIGN-OFF (not yet ratified; no code until
signed off).** Rev 2 folded the seven-pass adversarial review and the four parent rulings
(**PR-1/PR-2/PR-4/PR-5, Ben 2026-07-17**) into a resolved build spec for DoD item 2 of
`s4_7_plan.md`. Rev 2.1 applies the findings of the post-consolidation adversarial pass (three
overlapping reviewers: trail-fidelity / overengineering / ambiguity-executability, 2026-07-17)
under rulings **A1–A6 (Ben, 2026-07-17)**: A1 item-2 memory = `tracemalloc` (RSS design → item-4
handoff); A2 production-side interface skeleton for the PR-5 anchor family; A3 uniform lifecycle +
normative temporary-red protocol; A4 synthetic geometry semantics + pinned interaction matrix; A5
single pre-registration venue + named owners; A6 micro-confirmations (§8.4 ownership sentence
ruled; pairing-as-rule; retention-not-shrinking). Rev 2.2 adds ruling **A7 (Ben, 2026-07-17,
after a contrarian pass on the rev-2.1 boundary convention)**: INV-4's verdict model is reframed —
the opcode/boundary classification *routes*, the DR-3 confidence gate is the *uniform
confirmation path* for every boundary (diff proposes, anchor confirms); the categorical two-token
rule is retired and PR-3's question is re-expressed as demonstrate-confirmation-in-churn (see
INV-4 and the parent's A7 entry). The **verbatim review trail** (passes 1–7,
escalating `@@@@@@`→`!!!!!!` delimiter pairs, plus the in-situ PR-ruling blockquotes) is retained
in [`s4_7_item2_invariants_plan-discussion.md`](s4_7_item2_invariants_plan-discussion.md). Where a
later pass corrected an earlier response, this spec carries only the final reconciled form.
Cross-references use §/INV anchors (the discussion trail's chat-shorthand `R…` tags are not used
here — that is the ledger commitment from the trail, satisfied by the split).

**Parent authority:** `s4_7_plan.md` (RATIFIED rev 3, Ben 2026-07-09, **plus the dated 2026-07-17
amendments**: §3 "Parent rulings" block; §4 INV-1 as amended per PR-1; §4 INV-3 as amended per
PR-2; §8 INV-7 completion-state model per PR-4; DR-4 anchor-family contract per PR-5; **and the
ER-A1…ER-A5 external-review rulings, Ben 2026-07-17, `s4_7_external_review_dispositions.md` —
notably ER-A1 (anchored alignment is the normative §2.1 architecture; gap cap + k are
contract-fixed constants) and ER-A2 (INV-1's fixture family excludes byte-identical re-insertion
of a deleted span → INV-3/PR-2; anchor confirmation is positional), which this spec's
INV-1/INV-4/INV-6 sections must honor**) — §4 (the
seven invariants), §2 (the mechanism they gate), §8 DoD item 2. Tracker authority: the `S5.1-R`
row (#48) in `ENGINE_STRUCTURE_TASKS.md`. Discipline: [[feedback_red_first_tests]],
[[feedback_adversarial_audit_cadence]], [[feedback_mutation_pyc_staleness]],
[[feedback_no_cheating_results]], [[feedback_validate_bindings]].

**PR-3 is deferred-for-information by design** — re-expressed per A7 as **demonstrate
confirmation-in-churn**: whether the confidence gate can positively confirm a boundary inside a
churned (non-clean) region, decided after the v3 anchor representation + boundary projection land.
Its decision *mechanism* is pinned in this spec (§2 INV-4: the item-2 carried-red
confirmation-path test; the item-3 implementation attempt is the verdict; undemonstrated →
churned classes stay fail-loud in practice as a measured outcome, no design unwind). It is
**not** to be ruled during this spec's sign-off.

---

## §0 What item 2 is, and its one keystone

DoD item 2 verbatim: *"INV-1…INV-7 red-first (drift generator built so INV-2/INV-3 can be seen
red)."*

**Red-first (the binding rule):** every invariant is SEEN RED on a planted violation before the
mechanism makes it green. A test never seen red is a claim, not a check. Two things are distinct
and never conflated: a drift **fixture** only supplies inputs; the red-first **violation** is
either (a) a planted bad *implementation* (guard removed) the assertion is *demonstrated* to fail,
or (b) a mutation of the green implementation. A fixture ≠ a red-first check.

**Keystone:** per ratification, **DR-3's confidence gate is not locked as proven until INV-1
(never-a-false-bind) is seen red-then-green.** INV-1 is not one of seven equals — it is the gate
that converts DR-3 from "build direction" to "locked." Item 2 is, first, the machine that makes
INV-1's **conditional** property checkable (never-false-bind *under modeled drift* — see §1.4
scope-of-proof; item 2 does not certify real re-extraction).

**The DR-3 lock record is bounded and pinned.** It names: the generator + oracle **content
hashes**, the exact case matrix, the seeds, and the mode(s) run. Invalidation trigger: **any**
change to generator, oracle, case matrix, **or a parent-§2.8 fixed design constant (W, the width
allocation, k, the gap cap, the pinned backend identity — B-3) [extended 2026-07-17, audit fix]**
voids the lock and forces a re-run before DR-3 may
re-read "locked" — a later narrowing must not silently weaken a lock that still reads green. The
lock claims the conditional property only; the post-S4.6 real-PLL re-extract gate (§1.4, tracker
row `S5.1-RG`) is retained as a required forward gate.

**Pre-registration + provenance venue (single home — ruled A5, 2026-07-17):**
`docs/probes/s4_7_item2_prereg.md`, **ratified by Ben before any red run**. It holds: the INV-6
acceptance bundle (growth estimator, numeric tolerance/upper bound, repetition statistic
median-of-k with k stated, target hardware profile); the **INV-7 ceiling** (its own pre-registered
number — the evidence-op budget, distinct from DR-7's end-to-end resource ceiling; that
distinction is what lets the item-2 INV-7 red run without waiting on the DR-7 number); the ≥30%
re-segmentation floor (§1.4.3 — a placeholder ratified with this bundle); the **INV-6 red sizes
and their calibration rationale** (§2 INV-6 Red-first); the **fixture size-variable ledger**
(`L/K/A/T/D` + their per-fixture relationships, parent §5 as amended per B-6); and the **DR-3 lock
record**, recorded as a **pointer to the specific run-manifest artifact** — the hashes, matrix,
seeds, and modes live once, in the manifest; the lock record does not duplicate them.

### §0.1 The red-first protocol (auditable, not a slogan)

- **Runner:** the established invariant-targeted runner `~/.claude/skills/mutation-hunt/hunt.py`
  driven by declarative mutant tables under `tests/hunts/` — item 2 **extends the existing
  `hunt_rebind.py` table**; no new mutation tool is adopted (`mutmut` fought the `src/` layout,
  Cosmic Ray leaves source dirty on interrupt — `ENGINE_STRUCTURE_TASKS.md` O5; cosmic-ray remains
  O5's *on-demand isolated-worktree breadth supplement*, never the named-table replacement —
  generic operators do not produce the load-bearing guard flips the hand-authored table names).
- **Execution model, stated honestly:** the runner does **in-place edit + signal-safe,
  byte-identical, verified restore** (deferred handlers guaranteed on SIGINT/SIGTERM, post-restore
  sweep-verify) — strong hygiene, **not** isolated-copy execution. An isolated **worktree** is
  retained specifically for **SIGKILL/process-crash** risk (the one case a deferred handler cannot
  cover). No refuse-dirty-worktree guard — the trail's rationale: this review workflow itself
  leaves the worktree modified, so refuse-dirty would block it. (The trail's §4 thread preferred
  "mutate an isolated copy"; its §0 thread, reaching deeper passes, settled on
  in-place-with-verified-restore as primary — that later, more specific resolution governs here.
  Added observation, not the trail's argument: the byte-identical restore returns the pre-hunt
  bytes, uncommitted edits included.)
- **Fresh subprocess per mutant** — an in-process `__pycache__` purge is insufficient while the
  module stays loaded. The runner already pins `PYTHONDONTWRITEBYTECODE=1` + purges `__pycache__`
  (venv-aware) and `conftest.py` pins `sys.dont_write_bytecode` ([[feedback_mutation_pyc_staleness]]);
  additionally **verify the mutated source is the file actually imported** (module path recorded).
- **Machine-readable run manifest** (the red is recorded as an artifact, not prose). The runner's
  `--artifact` JSON already records the invoked test command (`test_cmd`), per-mutant `{label,
  status, detected, scope, files, rc, duration_s}` (`note` present only on ERROR records), purge
  and restore-verification. Item 2 extends it — **in a repository-local wrapper/artifact step; the
  shared out-of-repo `hunt.py` is left untouched** (editing cross-project tooling exceeds this
  task) — with:
  - **seed, pre/post source hash, environment identity, imported module path** (the fields
    property-based INV-1…4 need);
  - the **normalized patches inlined** + the **mutant-table path and sha256** (the artifact must
    bind to the mutant definitions it claims ran — the runner's own record carries no `old→new`);
  - the **runner file's sha256** (the runner lives outside the repo; version text alone cannot
    bind the artifact to immutable runner behavior).
- **Green** is proven by a named `pytest -k …` command recorded in the same manifest.
- The artifact is **prepared** in the worktree; **committing** it stays separately authorized
  (commit-only-when-Ben-asks).

### §0.2 Lifecycle + the temporary-red protocol (ruled A3, 2026-07-17)

**Uniform lifecycle for all seven invariants:** item 2 = the harness + **every red demonstrated**
(planted violation or shipped-mechanism red, recorded in the run manifest); **all greens land at
item 3** (the #48 mechanism). The committed item-2 suite state is **green-with-carried-reds**:

- **The temporary-red protocol, defined normatively** (nothing in `engine/tests/` uses `xfail`
  today — this protocol is new with item 2): a **single-purpose test** isolating the exact
  expected assertion, marked `xfail(strict=True, reason=<tracker/issue anchor>)`, with a
  **manifest entry** recording the demonstrated red (command, output, source hashes, per §0.1).
  Never a naked failing suite member, never a skip. `strict=True` means an accidental pass fails
  the suite — the flip to green at item 3 is a deliberate edit landing with the mechanism.
- §3's closing gate ("mutation hunt at green; wide+narrow + Rule-A") runs at **item 3**, when the
  invariants green; item 2's mutation work is the red-demonstration mutants of §0.1.
- The token→atom / intra-atom **back-pointer producer is item-3 (#48) work** (§1.2): INV-2's
  split row reds in item 2 against the planted stub without it, and greens at item 3 when the
  producer lands.
- INV-6 and INV-7 additionally follow their own stated lifecycles (§2): INV-6 flips green at
  item 3; INV-7 closes green **or** honestly-UNRESOLVED per PR-4.

---

## §1 Component 0 — the drift generator (the shared prerequisite)

The most load-bearing build in item 2: INV-1/2/3/4 all consume it, and DoD item 2 gates on it. It
reuses the prototype's **perturbation mechanics** only (drop/dup/mutate yielding a re-atomizable
stream); everything else — the provenance model, the oracle, the fixtures — is new harness work
gated by the §3 self-tests. The generator is split into **(a) mutation/provenance** and **(b)
fixture materialization**, so the oracle stays independent of anchor/fingerprint construction.

### §1.1 Input — the fixture bundle

One `RebindFixtureBundle` type with an **explicit bundle validator** (not prose):

- **Required:** `old_map` (`StructureMap`: projection + stored per-slot fingerprints/anchors),
  `old_canonical` (must match the old map manifest's content hash), `fresh_canonical`,
  `geometry_mode`.
- **Optional:** witnesses (may be empty), `old_evidence` (re-stamp paths), `policy`.
- **Baseline gate, as shipped:** `_check_baseline` checks `canonical_content_hash` in **all**
  modes and `canonical_geometry_hash` **only outside `no-geometry`** (content-always +
  geometry-conditional; since INV-1…4 run `no-geometry`, only the content gate fires for them).
  A careless perturb-and-rebuild is rejected, not silently mis-tested.
- **Stored anchors come from the OLD map — never rebuilt from fresh truth.** The validator
  enforces this; a test comparing anchors built from fresh truth would test nothing.

### §1.2 Perturbation classes (precise semantics)

Each independently toggleable, compositions constrained to legal, interpretable fixtures: reorder
window/block sizes, cross-container moves, and permitted compositions are **enumerated in the
fixture config** — with a **required minimum**: the §1.4.3 pairwise list (merge×repeat,
split×boundary, move×container-edge); beyond that minimum the composition set is builder-declared
in the config (visible, diffable), not left open:

- **char-substitution** — OCR-class, *in-token*: the token becomes `replace`, coarsening
  alignment (the R-b axis).
- **atom drop / atom insert.**
- **atom duplication** (dittography).
- **re-segmentation** — split one atom → two, merge two → one (the D25 axis), **including the
  back-pointer-only cases**: tokenization is per-atom concatenated, so a split **at a token
  boundary leaves the token sequence identical** — a pure back-pointer change, invisible to the
  diff (all `equal`). "Atom split with unchanged tokens" is therefore the **primary** split case;
  only a mid-token split perturbs tokens. Merge's two-old-nodes→one-fresh-atom collision is
  likewise explicit (the double-claim case, §2 INV-1 global conjunct).
- **local reorder / moved block** (R-a, the weakest axis; INV-3's target).

**Fixture-content floor (folded per dispositions B-1, 2026-07-17):** the materialized streams must
include **tokenless included atoms** (punctuation-only — `normalize_tokens` drops them, so they
carry no token back-pointer; the real PLL canonical has 50 such included atoms, **5 as the final
atom of an owning slot**), placed both slot-interior and slot-final/seam — so the parent-§2.2
tokenless-ownership rule and the merged-atom-unrepresentable-boundary rule are exercised, never
vacuously green.

The token→atom / intra-atom **back-pointer producer is new Layer-1 work assigned to item 3
(#48)** — production alignment-layer code, not harness code (ruled A3; the shipped
`normalized_slot_tokens` returns plain strings, and the harness must not cite a capability the
shipped function lacks). When it lands, it is tested as its own unit; in item 2, the invariant
rows that need it red against the planted stub (§0.2).

### §1.3 Output — the provenance relation (ground truth by construction)

Not an "identity map": a bidirectional map cannot represent duplication/split (1→many), merge
(many→1), or insertion (no old source), and mapping a move to ∅ destroys exactly the INV-3 oracle.

- **Stable lineage identities** + a derived **final many-to-many old↔fresh provenance relation**
  — this is what every oracle reads. Positions in the oracle relation are **final**
  (post-all-events). The ordered **event log** (`op, old_atom_id(s), fresh_atom_id(s), positions`
  per event) is retained for **diagnostics only** and is non-authoritative.
- Moved atoms keep their identity plus a `moved` flag — the planted destination **is** the truth
  INV-3 checks. **∅ (no final descendants) is reserved for delete.** **[Audit sharpening
  2026-07-17]** The generator therefore **forbids** composing delete(X) with insertion of
  byte-identical X-content (config-enforced, like §1.6's excluded compositions) — that intent is
  expressible only as a move, keeping INV-3's planted-destination oracle well-defined (parent §4
  INV-1 as amended per ER-A2).
- **Insertion attribution (folded per dispositions B-4 (ER-9), 2026-07-17; oracle model
  [Ben-ratified] 2026-07-17):** an inserted atom has
  no old ancestry, but a coverage-valid rebind must still attribute it — "no ancestry" alone is not
  an oracle answer. The relation therefore classifies every insert by **final position**:
  **interior insertion** (strictly inside one slot's final span — its fresh atoms belong to that
  slot's expected tuple) vs **seam insertion** (at the gap between two slots' final spans —
  ownership genuinely ambiguous; the oracle records the legal outcomes {left, right, abstain} per
  fixture instead of one expected tuple, and double-assignment stays illegal under INV-1's
  global-disjointness conjunct).
- **Executable relation laws** — gating generator self-tests, each its own red, run **before any
  invariant consumes the relation** (§3 item 1):
  1. every final fresh atom has old ancestry unless introduced by `insert`;
  2. deleted old atoms have no final descendants;
  3. split/duplicate descendants preserve exactly one source lineage;
  4. a realized merge **must carry the complete set** of its ≥2 old ancestors ("may carry" would
     let a one-ancestor drop pass);
  5. moves preserve ancestry while changing final order;
  6. the final relation **equals the composition of the event transitions**, where the expected
     closure comes from an **independent reference composition or hand-pinned golden composed
     examples** — never the generator's own fold compared to itself (same-fold tautology);
  plus: content edits preserve ancestry. Laws (1)–(5) are deliberately redundant cross-checks of
  master law (6) — defense in depth, each its own red.

### §1.4 The four-part guard (the oracle's epistemics)

1. **Not circular.** No invariant's "expected" may be computed from `rebind()`'s output, and the
   oracle's *decision* must not be computed by the production projection/uniqueness path.
   **Planted provenance is authoritative** for the correct destination. A small, bounded,
   **independent brute-force reference model** (sharing no code with `rebind.py`, enumeration
   bounds stated, kept small enough not to dominate randomized-test runtime or acquire
   production-like pruning) contributes **exactly two facts** — is the planted destination
   *feasible*, and do *alternatives* (≥2 optima) exist — and **never selects a bind**. The oracle
   keeps **three facts separate**: (i) alignment feasibility, (ii) multiple optimal alignments,
   (iii) boundary-anchor uniqueness — related, not equivalent.
   **Allowed auto-bind = planted-destination ∩ brute-force-feasible ∩ (content ≥ τ ∧
   unique-in-both ∧ globally-valid).** Planted destination infeasible or non-unique ⇒ **expected
   = abstention**; the reference model is forbidden to substitute another optimum. The mechanism's
   bound set must be ⊆ that allowed set — consistent with the ratified `bound ⊆ brute-force bound
   set`: brute force is the feasibility **ceiling**, planted provenance the **correctness**
   filter, never a bind *source*.
   **The confidence conjuncts must be independent too**, fixture-class-conditionally:
   **constructed/analytic cases** (score/uniqueness analytically fixed — exact identity, planted
   duplicate) may use mutation-pinned production preconditions **or** independent computation;
   **randomized cases require independent bounded computation** of content-ratio and uniqueness —
   otherwise a production scoring/index bug defines both the mechanism result and which cases the
   oracle deems eligible, greening both sides. (Challenged in the 2026-07-17 adversarial pass;
   **kept** — mutation-pinning polices planted bugs only, independent computation polices the
   class.)
   The production normalizer is **not** blanket-banned (an oracle on differently-normalized text
   rejects correct binds and misses normalizer defects): **normalization is tested as a separate
   contract.**
2. **Scope of proof.** "All synthetic invariants green" proves the invariant properties
   *conditional on the modeled drift* — never "correct on real re-extraction." The **real-PLL
   re-extract (post-S4.6) is a required forward gate**, registered as tracker row **`S5.1-RG`**
   (a new dependent gate on the open S5.1-R #48 row; other rows' acceptance claims are untouched —
   S4.6 itself remains open/TODO, owner Ben). Real failures are **triaged before routing**:
   unmodeled-drift class / oracle-or-ground-truth defect / threshold-policy error / algorithmic
   #48 defect — the **builder classifies; Ben rules the routing** (owner named per the trail's
   requirement) — then routed per DR-9 (mechanism → reopen #48; rate/calibration → S5.2).
3. **Oracle independence + teeth.** Operationalized, not asserted: ≥1 case per perturbation
   class; pairwise compositions for the risky interactions (merge×repeat, split×boundary,
   move×container-edge); a **deterministic mandatory matrix as primary** with randomized
   compositions as supplement (pairwise ≠ higher-order safety); fixed and reported seeds;
   a coverage report of **realized non-no-op** operation counts, distinguished from generated
   events (random generation can silently stop emitting hard cases).
   **Heavy re-segmentation floor:** the gating case records **≥30% of included canonical atoms
   undergoing a realized re-segmentation** in its config — a placeholder default, **ratified with
   the §0 pre-registration bundle**, tunable *up* for exploration; **lowering the gate is a
   visible, diffed config change, never silent** ([[feedback_no_cheating_results]]). Merge
   participation counts **both** source atoms. A realized split/merge must change the **final**
   segmentation — an event that nets zero final change is reclassified a no-op and excluded from
   the realized count (checked by the §1.3 law family against pre/post final segmentation).
4. **Drift-model fidelity is itself unvalidated** — whether the perturbation model resembles real
   re-extraction is checkable only against real data. The copy2-derivation probe is **removed
   from item 2 entirely** (an op-class histogram ignores burst length, locality, severity,
   co-occurrence, content conditioning — and copy2 is itself a proxy); the question is registered
   with the `S5.1-RG` real-data gate. If ever revived it is a *descriptive comparison*, never
   "fidelity validation."

### §1.5 Anchor-density knob (item-2 scope only)

- Item 2 builds the **knob plus deterministic sentinel points** needed to see a red — the 6-point
  **sweep and curve are item 4's** (the parent's ratified §8 item 4 places "the full anchor-poor
  sweep" in productionization; the ownership seam — **item 4 owns the correctness-at-density
  property; S5.2 owns threshold/rate calibration** — is confirmed as ruled, Ben 2026-07-17 A6).
  No "false-bind rate ≈0" language in item 2 — that is a rate claim S5.2 owns; item-2 asserts
  **deterministic set/property facts** over generated truth ("*this* planted wrong copy must not
  bind").
- **The DR-3-locking red is representation-agnostic** (it holds for every anchor in the
  DR-4-ratified family) and blocks on nothing from #48: a passage
  repeated verbatim, with a node boundary deep enough inside it that the anchor window stays
  within the repeat on both sides, has a **byte-identical (hence non-unique) boundary anchor for
  the entire DR-4-ratified anchor family** — because PR-5 pins that family as **deterministic /
  content-only / bounded total footprint W** (prefix + exact + suffix together). The fixture
  plants the **entire selected `exact` content plus >W context, twice**.
- **Interface skeleton (ruled A2, 2026-07-17):** item 2 ships a **production-side interface
  skeleton** for the PR-5 anchor family — the type/protocol for prefix+exact+suffix anchors, a
  **named `W` constant** (the total-footprint bound), and the confidence-gate hook — with **no
  constructor logic**; #48 implements it. This is not the PR-5 divergence trap: that trap is a
  test-only *constructor* production could diverge from; an interface production must implement
  is its opposite. Consequences: the repeated-passage fixture asserts **`repeat_width > 2·W`
  mechanically** against the named constant (if #48 changes W, the assertion reds —
  self-enforcing); the **DR-4 contract test binds to the skeleton** — and the
  deterministic/content-only premises are enforced there, so a later violating anchor choice
  reds the contract instead of silently invalidating the repeated-passage red; INV-4's
  confirmation-path test can
  red on *behavior* (the skeleton imports; confirmation is unimplemented), never on a missing API.
- When the density statistic is measured (item 4), it is measured on the **actual v3
  boundary-anchor object**, not generic type-unique k-grams (their uniqueness distributions
  differ at short slots/boundaries).
- **Confound honesty:** the pairing discipline is a **construction rule, not item-2 machinery**
  (ruled A6): when density fixtures are built, they are **paired** (same N, same atom boundaries,
  same edit locations, matched local frequency structure as far as possible), and density is the
  **intended treatment with named residual confounds** (repetition-run structure, ambiguity,
  shingle-frequency skew, diff tie behavior) — never claimed as the only moving variable. Item
  2's sentinel fixtures need not be paired; the actual paired sets are item-4 work (the sweep).

### §1.6 Synthetic geometry — for the mode×drift interaction matrix only (ruled A4, 2026-07-17)

Geometry-mode rows need geometry-bearing fixtures: when a fixture is built for
`geometry-primary`/`geometry-tie-break`, materialization emits **per-atom geometry (page id +
bbox)** and stamps `canonical_geometry_hash` so `_check_baseline`'s geometry gate (§1.1) passes
honestly. **Per-class geometry transforms (pinned):**

- **char-sub** → geometry unchanged;
- **drop** → the atom's geometry removed;
- **insert** → a box interpolated between its neighbors on the same page;
- **duplicate** → the copy carries its **own distinct position** — the physical reality the
  interaction rows exploit: geometry CAN legitimately disambiguate byte-identical copies (PR-1);
- **split** → the box partitioned proportionally by token count;
- **merge** → the union box;
- **move** → the block's boxes re-homed to the destination position/page.

Edge semantics: an insertion at a stream/page edge abuts its single existing neighbor;
cross-page merges and insertions between cross-page neighbors are **excluded compositions**
(config-enforced, §1.2 — the transforms stay total over what the generator may emit).

The interaction matrix is pinned at **six rows**: {repeated-content, boundary-edit, move} ×
{`geometry-primary`, `geometry-tie-break`}. **Expected outcomes follow PR-1's safety clause:
absent an independently valid geometry disambiguation, a non-unique content anchor still lands
`ambiguous` in every mode; with one, a lone bind is legal in geometry modes — that per-mode
behavior is INV-5's territory (mode orthogonality).**

**[Folded per dispositions B-5 (ER-10), 2026-07-17]** "Independently valid geometry
disambiguation" is executably defined in the parent (§2.4 as amended): **page-equality against the
stored region seed** — nothing richer (bbox/distance comparison is a named non-goal). Matrix
consequence: a duplicated copy on the **same page** as its original is geometry-indistinguishable →
expected `ambiguous` in **every** mode; only a distinct-page copy may be disambiguated in geometry
modes. The §1.6 duplicate transform must therefore emit **both same-page and distinct-page
duplicate variants**, and the six-row expected outcomes are stated against that definition.

---

## §2 The seven invariants (property / oracle / fixture / red-first violation / gates)

> **Property** lines quote the parent §4 **as amended 2026-07-17**. **Execution mode:** INV-1/2/3/4
> run in **`no-geometry`** as the base mode (mode out of the loop; the core properties
> unambiguous), **plus** the §1.6 **mode×drift interaction matrix** (six pinned rows, expected
> outcomes per PR-1's safety clause), run to catch a geometry rescue of a wrong projection —
> INV-5's isolated mode fixtures do not prove those cross-effects safe. **Lifecycle for every invariant: §0.2** (reds demonstrated in item 2;
> greens land at item 3; carried-reds via the temporary-red protocol).

### INV-1 — never a false bind  *(LOAD-BEARING — unlocks DR-3)*

- **Property (§4, amended per PR-1):** over randomized drift fixtures incl. planted repeated
  passages (within- and cross-container), the bound set ⊆ a brute-force alignment oracle's bound
  set; a non-unique boundary anchor forces `ambiguous`, never a lone bind **on content evidence
  alone (`no-geometry` mode)**; geometry-mode disambiguation by an independently valid geometry
  signal is INV-5's per-mode territory. Uniqueness is **whole-stream over the canonical included
  stream**, and **both** boundary anchors must be unique. Oracle from fixture ground truth, never
  the mechanism's output. Mutation-hunt primary. **[Amended per ER-A2, 2026-07-17 — audit
  propagation]** Anchor confirmation is additionally **positional** (the located fresh occurrence
  coincides with the diff-projected boundary; window-contained in A7's no-candidate class), and
  the fixture family **excludes byte-identical re-insertion of a deleted span** — that intent is
  expressible only as an ancestry-preserving move (§1.3), whose destination INV-3 owns; the
  generator config forbids the delete+identical-insert composition.
- **Oracle:** concrete **`(node_id, slot_name, ordered fresh-atom-id tuple)`** pairs derived from
  the §1.3 provenance relation — `slot_name` because containers own heading/signature slots with
  distinct intervals; the **id tuple** (not a numeric interval) because an interval can look right
  after a wrong back-pointer conversion. Ambiguity is represented separately, never as a pair.
  **Two conjuncts:** (i) *pairwise* — every bind ∈ allowed pairs (§1.4 allowed-set definition);
  (ii) *global* — bound fresh-atom ownership is **disjoint** (no fresh atom claimed by more than
  one `(node, slot)`). Conjunct (ii) is necessary: under many-to-one merge, two individually
  provenance-allowed `(slot, fresh-id)` pairs can be globally incompatible — pairwise membership
  alone does not forbid double-claim. It is grounded in the shipped non-overlapping-coverage
  contract (S1.4 round-trip gate; `UNOWNED_INCLUDED_ATOM`; `test_structure_projection.py`).
- **Fixtures:** drift + **planted repeated passages** (within- and cross-container; the §1.5
  repeated-passage construction — full `exact` + >W context, twice, W read from the §1.5
  skeleton constant); the **anchor-poor sentinel** variant; the §1.6 interaction rows. Plus
  **[Folded per dispositions B-1/B-4, 2026-07-17]** a **shared-seam insertion fixture** — an inserted run at the exact gap
  between two adjacent slots — asserting the §1.3 insertion-attribution outcome: never assigned to
  both sides (the global conjunct), never silently dropped from coverage.
- **Red-first:** the red mutant is a **pinned constructed case demonstrated to fail** — never the
  assumption that removing the uniqueness guard produces a wrong bind (a diff may pick the planted
  copy or abstain). Mutation-hunt primary: mutate the uniqueness check (accept a non-unique
  anchor) → must re-RED. **[Added 2026-07-17, audit fix]** The **positional conjunct** (ER-A2)
  gets its own named red: a planted "maps-far" case — a unique-in-both anchor whose located
  occurrence sits far from the diff-projected boundary (the prototype's real false-bind mode, the
  noise end-token that "maps far") — with the positional check mutated out (accept located ≠
  projected) → must re-RED. The **global-disjointness subcase extends the existing named
  mutant/test pair** — `bound-subset-disjointness-disabled` (`hunt_rebind.py`) against
  `test_partial_rebind_never_silently_double_claims_a_fresh_atom`, the S5.1-audit historical
  regression (guard: `_contested_nodes`) — into the drift/many-to-one merge setting, plus a
  **focused `global-conflict` regression asserting the full outcome on the affected nodes — both
  binds' fate + the `global-conflict` reason — not merely that the reason value exists**.
  Anchor-poor sentinel: as density drops, wrong-binds must become `ambiguous`/fail-loud, never
  silent.
- **Also in this build list:** the **DR-4 contract test** (PR-5), bound to the §1.5 interface
  skeleton — anchor family is deterministic / content-only (no positional or structural component
  folded into the content anchor; a *separate* independent positional disambiguator stays legal —
  contamination banned, not disambiguation) / bounded total footprint W.
- **Gates:** **DR-3 lock**, with the §0 bounded lock record.

### INV-2 — binds under drift (anti-inertness)  *(INV-1's counterweight)*

- **Property (§4):** on real re-segmentation / char-sub fixtures the mechanism **binds** the nodes
  it should (a fail-loud-on-everything mechanism fails this). Scoped as a by-construction
  existence check, NOT a rate over a realistic model — that is S5.2.
- **Oracle:** the provenance relation — which nodes survive the perturbation and must bind. **Not
  every non-dropped survivor is bindable**: a survivor can legitimately sit behind an `ambiguous`
  boundary or `global-conflict`.
- **Fixture — the mandatory positive matrix**, each row naming the exact node/span expected to
  bind:
  1. **interior in-token char-substitution with unchanged boundaries → MUST bind** (the
     anti-inertness core);
  2. **atom split with unchanged tokens** (§1.2's primary split case — a back-pointer test; reds
     in item 2 against the stub, greens at item 3 with the producer, per §0.2);
  3. **atom merge with unambiguous ownership.**
  **Boundary char-substitution is a diagnostic axis** (recorded; the §5.1 R-b decision
  instrument), not a bind requirement. The **boundary-edit-with-independent-confirmation row is
  EXCLUDED pending PR-3** (its presence depends on demonstrating confirmation-in-churn, per A7;
  undemonstrated → the case must abstain — the row is eliminated, not unblocked).
- **Red-first:** the empty stub (binds nothing) **plus** a mutant that **over-abstains
  specifically on `replace`/re-segmentation** — so each advertised drift path has its own teeth,
  not one happy case. INV-1 ∧ INV-2 together = correct *and* non-inert.
- **Gates:** the mechanism is not inert (existence only; the rate is S5.2's).

### INV-3 — reorder/move never silently mis-projects

- **Property (§4, amended per PR-2):** a moved block either **fails loud OR binds to its planted
  destination with a globally-valid structure map — never a bind elsewhere**. A
  destination-correct *atom* bind with an invalid *structure-map* result (container reading-order
  / contiguity / decision topology) is **not green**. Fail-loud-only is the documented expected
  outcome of the **#48 diff design** — the mechanism this spec gates, in which a move is
  delete+insert (R-a) — a scoped observation, not the ratified property. (The parent's amended
  text says "the current diff mechanism"; that phrase means the #48 design, not the shipped DP —
  clarified 2026-07-17.)
- **Oracle:** node/slot-level, derived from the provenance relation's preserved moved destination
  (§1.3 — never ∅): which node boundaries intersect the moved block, and the allowed reason(s)
  per outcome.
- **Fixtures:** **separate within-container and cross-container move fixtures** — so a
  contiguity/`global-conflict` red is never mistaken for an R-a red.
- **Red-first:** a mechanism that greedily projects the moved node onto a wrong span → RED against
  planted truth; a destination-correct atom bind with an invalid map → RED.
- **Gates:** R-a honesty.

### INV-4 — boundary-in-edit-block

- **Property (§4):** a node boundary landing in a `replace/insert/delete` block gets a fail-loud
  finding unless the confidence gate independently confirms it (DR-2).
- **Oracle:** classification of the planted edit by the **independent reference model** (§1.4) —
  never the production aligner (circularity). A boundary is a **gap between tokens**, not a
  "boundary token." **The oracle never computes the four classes by running an aligner:**
  INV-4's mandatory fixtures are **constructed**, the class determined analytically from the
  planted edit's geometry (the §1.4 constructed/analytic rule) and built **tie-free** (a unique
  optimal alignment by construction), so the class is well-defined independent of tie-breaking.
  Randomized drift that happens to land boundaries in churn is INV-1/INV-2 territory, where the
  allowed-set verdict oracle governs without class prediction.
- **The half-open boundary classification (interval math authored at rev 2.1 — the trail
  demanded the pin but never carried its content, so the math remains flagged for sign-off
  audit; verdict model reframed per A7 — the classification ROUTES, it does not rule):** old-stream tokens are
  indexed `0…n−1`; boundary `b` is the gap before token `b`, `b ∈ [0, n]`; opcode blocks carry
  half-open old-token intervals `[i1, i2)`. Classification of `b`:
  - **clean-candidate** — both flanking tokens (`b−1`, `b`) in `equal` blocks, no `insert`
    anchored at `b`: the diff projection yields one well-defined fresh position.
  - **edge-candidate** — `b` at a block edge (`b == i1` or `b == i2`) with ≥1 flanking token in
    a non-`equal` block: the projection yields a well-defined candidate, but the aligner cannot
    report whether that edge was one of several optimal placements — a single witness that
    cannot flag its own guesses.
  - **no-candidate** — `b` strictly interior to a `replace`/`delete` block (`i1 < b < i2`): the
    diff defines no old→fresh correspondence inside the block.
  - **two-candidate** — an `insert` anchored at `b` (empty old interval `[b, b)`): the fresh
    position is exactly one of {before, after} the inserted run.
  - Stream ends: a missing flank (`b = 0` or `b = n`) counts as `equal` (the stream edge is
    stable by definition); the degenerate empty old stream (`n = 0`) makes any fresh content an
    `insert` anchored at 0 → two-candidate — vacuously closed in practice: an empty old stream
    has no stored boundary anchors, so the anchor-decides step lands `missing-anchor`/fail-loud
    by construction.
  - **Tiling property + precedence (classes are disjoint):** the opcode tiling is required to
    emit **exactly one non-`equal` block between two `equal` blocks** (no adjacent non-`equal`
    blocks; an insert adjacent to a replace merges into the replace's fresh side) — stated as a
    normative property of whatever produces the tiling, not assumed from a library's habit.
    Under it the four classes are mutually exclusive. Belt-and-suspenders, evaluation order is
    also pinned: **two-candidate (insert anchored at `b`) > no-candidate (strict interior) >
    edge-candidate > clean-candidate** — an insert at `b` routes to two-candidate regardless of
    any block-edge status, since the before/after ambiguity exists however well-defined the edge
    mapping is.
  - **Capped-out gap (anchored composite — parent §2.1/§2.2 as amended; added 2026-07-17, audit
    fix):** a gap the cap refuses enters the tiling as a **single synthetic unaligned block**,
    preserving the one-non-`equal`-between-`equal`s property; a boundary interior to it routes
    **no-candidate** (locate-within-window, the gap's fresh interval as the region constraint). A
    constructed capped-gap case joins the mandatory fixtures; its classification mutant is
    separate, per the existing classification-vs-gate rule.
- **The verdict model (ruled A7, Ben 2026-07-17): diff proposes, anchor confirms — the DR-3
  confidence gate is the UNIFORM confirmation path for every boundary, the literal reading of
  DR-2's "unless the confidence gate independently confirms."** No one eats two-token seam
  noise: the W-wide anchor window amortizes single-token damage into a ratio governed by τ
  (S5.2-calibrated) instead of a categorical two-token cliff. Per class: **clean-candidate** →
  routine confirmation; **edge-candidate** → bind only on unique ≥ τ anchor confirmation of the
  candidate (the anchor is the independent second witness the edge lacks); **no-candidate** →
  the anchor may *locate* the boundary by search within the diff-narrowed window — the diff
  still contributes evidence here (the block's fresh interval bounds the search: a region
  constraint, so locate = confirm-within-diff-constraint, not a single-witness invention) —
  unique (**whole-stream over the canonical included stream**, INV-1's quantifier, never
  window-local) + strong → **bind with `reason=None` like every bind**, the *method* recorded
  in an additive bind-provenance field on the result (`located_by`, a #48 schema addition —
  **DR-5's closed failure-reason enum is untouched**; every enum member stays an
  abstention/failure reason), else fail-loud; **two-candidate** → the anchor's prefix/suffix content decides which side of
  the inserted run owns the boundary; undecidable → fail-loud. **A boundary is never invented
  from the diff alone** — DR-2's sentence, implemented directly. The rev-2.1 categorical rule
  (any non-`equal` contact → fail-loud unless an exception branch rescues) is **retired**: if
  confirmation proves weak inside churn, the mechanism *degrades to that same conservative
  behavior as a measured outcome*, not a design commitment — which dissolves the PR-3 coupling
  the contrarian pass surfaced.
- **Risk moved, named:** uniform confirmation concentrates the wrong-content fuzzy-match risk
  exactly where matching is hardest (churned regions) — controlled by uniqueness-in-both + τ,
  policed directly by INV-1's planted-wrong-copy oracle, made visible by the INV-4 fixtures.
  One gate-letter detail pinned for the #48 skeleton: positional confirmation leans on the
  **anchor's own match ratio** — a small explicit extension of DR-3's wording (which puts the
  ratio on slot content and uniqueness on the anchor).
- **Item-2 scope — the unconditional negative:** any non-clean class with no anchor
  confirmation → **fail-loud**. Red-first now, representation-light.
- **Merged-atom unrepresentable boundary (folded per dispositions B-1, 2026-07-17):** a
  constructed case where the token-level projection is **clean** (`equal` blocks throughout) but
  the mapped boundary lands **interior to one merged fresh atom** — representable at token
  granularity, unrepresentable in the atom-id map (slots own whole atom ids). Expected: fail-loud
  (parent §2.2 as amended), never a rounded atom span. A distinct class from
  boundary-in-edit-block — the diff sees nothing wrong here — so it gets its **own red**.
- **The confirmation path — authored in item 2, carried RED:** via the §0.2 temporary-red
  protocol, asserted against the **§1.5 interface skeleton** so the contract *resolves* (the
  skeleton imports) while the confirmation *behavior* is what is unimplemented. The planted
  violation is **behavioral** — "boundary guard rejects a candidate the confidence gate
  independently confirms" — and must **not** red merely because a future anchor API is absent
  (that would prove interface timing, not the confirmation path). Item 3 implements it;
  **whether a positive fixture can be constructed in churn is PR-3's re-expressed question —
  demonstrate confirmation-in-churn** (undemonstrated → the non-clean classes stay fail-loud in
  practice, a measured outcome with no design unwind). INV-4 stays fully red-first inside
  item 2 (no DoD split needed).
- **Positive-case spec obligation:** a bound outcome carries `reason=None` — the confirmation
  case is specified by its actual independent **evidence + decision procedure** (the anchor
  match: location, ratio, uniqueness), not by "accepted reason codes."
- **Red-first:** a mechanism that silently invents a fresh boundary in a non-clean class →
  RED. **The boundary classification and the confirmation gate are mutated separately** — each
  has its own red.
- **Gates:** **DR-2** (read literally, per A7; PR-3 pending as re-expressed above).

### INV-5 — mode orthogonality

- **Property (§4):** per-mode gating matches the S5.1 mode fixtures.
- **Scope — pure mode orthogonality:** primary page-pin; tie-break-only disambiguation;
  no-geometry region-ignore; **no sub-τ geometry rescue**; threshold ordering. Reason-enum
  closure, non-raising behavior, re-stamp continuity, **and the unruled/unknown-mode provenance
  check** (unowned in the trail's narrowing — assigned here) are **not per-mode** — they belong
  to the **DR-5 regression suite**, which is the set of **existing named tests in
  `tests/unit/test_rebind.py`** (reason-enum assertions, re-stamp behavior — already present),
  designated as the DR-5 gate — **naming, not new building**; only the unknown-mode provenance
  check is a new member if no existing test covers it.
- **Fixtures:** there are no reusable on-disk "mode fixtures" — the S5.1 contracts live inline in
  `tests/unit/test_rebind.py` (the `MODE_PRIMARY`/`TIE_BREAK`/`NO_GEOMETRY` cases). Item 2 names
  those tests/helpers and **restates expected behavior per mode** against the planned
  **projected-span** semantics — not by reusing implementation-shaped fixtures that would
  preserve the old DP's window-pin assumptions.
- **Red-first:** each mode branch gets a **targeted red mutant** (one geometry-rescue example
  does not prove orthogonality).
- **Gates:** **DR-5** (contract preservation).

### INV-6 — scale gate  *(straddles item 4 — see §3/§5.2)*

- **Property (§4):** named ops' wall-clock + peak-memory sub-quadratic across ≥2 decades incl.
  serialize+load+index; small always-on + 10⁵ nightly.
- **Red-first (now-or-never):** run against the **shipped cubic O(K·N³) `_Assignment`** at
  **calibrated smaller red sizes** (two full decades of the cubic is infeasible; the red sizes
  and their calibration rationale are recorded in the §0 pre-registration doc) **before #48
  deletes it** — the shipped defect is the planted violation. The red is captured as a
  **reproducible baseline artifact** (command, sizes, result, commit/implementation identity);
  the **durable** tests target **public named operations** (`rebind()`, `evidence_findings` /
  the public rebind path that re-stamps) so deleting the old implementation does not delete the
  tests' meaning.
- **Acceptance — pre-registered, never baseline-derived:** an **independent growth rule** — a
  fitted log-log slope with a pre-registered tolerance, **plus per-adjacent-size ratio checks
  (and/or confidence bounds)** (a 3-point fit is fragile) — over **≥3 sizes spanning 100×**
  (10³/10⁴/10⁵), with K's behavior as N grows stated. `baseline × margin` is rejected: it derives
  the bar from the cubic defect and institutionalizes it — the old baseline evidences only the
  RED, never the acceptance authority. The estimator, tolerance/upper bound, repetition statistic
  (median-of-k, k stated), and target hardware profile are **pinned in the §0 pre-registration
  doc and ratified by Ben before the red run** (committing separately authorized) — so the
  observed cubic cannot retro-set the bar. **[Folded per B-6, 2026-07-17]** Every measured point
  pins and reports the five size variables **`L/K/A/T/D`** (parent §5 as amended) and the fixture's
  relationships among them; the growth rule is stated against a **named** variable, never a bare
  "N".
- **Phase honesty:** serialize / load / index / rebind timed **separately and end-to-end** (an
  endpoint-only "sub-quadratic" is gameable with fixed overhead). Fixture construction and phase
  completion are asserted **before** the budget assertion, so an expected-failure marker cannot
  mask a setup error.
- **Memory (item 2 — ruled A1, 2026-07-17):** **`tracemalloc` peak** — the parent-ratified
  instrument (§8 item 2: "`perf_counter`/`tracemalloc` wrapper"), sufficient for the item-2 red:
  the shipped cubic DP's costs are Python-managed allocations, fully visible to `tracemalloc`.
  The native-allocation gap (`tracemalloc` misses RapidFuzz) arrives only with the item-3
  replacement mechanism — native-aware measurement (the §5.2 RSS handoff design) attaches to the
  durable memory gate at item 3/4, not to item 2.
- **Absolute resource ceiling — tri-state, recorded:** the **numeric budget is unresolved**; the
  **ceiling requirement is ratified** (the S4.7 tracker row, DR-7: "rough wall-clock +
  peak-memory ceiling incl. serialize + load + index-build"); **Ben sources-or-rules the number
  before item 4 acceptance** (owner named, ruled A5) — item 4 cannot drop the ceiling without a
  parent amendment, and item 2's enforceable INV-6 surface is the **growth** red only, which does
  not block on the absolute number.
- **Lifecycle:** INV-6 flips green at item 3 (half B makes the ops sub-quadratic).
- **Gates:** the scale gate (item-2 half; §8.4's sweep is item 4's).

### INV-7 — evidence composite

- **Property (§4):** measured on a deep map at scale; over budget → algorithm fixed or scoped
  follow-up; ceiling not moved.
- **Completion-state model (§8, amended per PR-4) — exactly two end-states:** **(a) green**
  (within ceiling, or an in-scope fix lands), or **(b) honestly UNRESOLVED** under DR-6
  characterize-and-defer: the characterization artifact is the accepted deliverable, a named
  follow-up issue is opened, and the budget assertion is isolated in a **single-purpose test**
  carrying `xfail(strict=True, reason=<follow-up issue>)` — never a silent skip, never a bare
  suite-level xfail (a strict xfail treats *any* failure as expected unless the test isolates the
  exact budget assertion). DoD item 3's "suite green" reads as green **with INV-7's state
  explicitly annotated**.
- **Ceiling:** **pre-registered and independent of the measured baseline** (derived from D35's
  CLI wall-clock/memory rationale — a baseline-derived ceiling is the INV-6 circularity); never
  moved. **The number is INV-7's own** (the evidence-op budget), recorded and ratified in the §0
  pre-registration doc **before the red run** — it is *not* the DR-7 end-to-end resource ceiling,
  so the item-2 INV-7 red does not stall on that tri-state (ruled A5).
- **Fixture:** a deep synthetic chain (PLL is depth-4-shallow; this is a synthetic worst case,
  stated as such). **Depth is bounded, with a pre-flight proof** that construction, schema
  validation, serialization, and recursion limits do not fail before the measured operation — a
  10⁵-deep Python tree must not measure stack failure and call it the evidence cost. **[Folded per
  dispositions B-7 (ER-12), 2026-07-17]** Two representation facts additionally bind the fixture:
  each evidence entry materializes its full `beneath` union (`extent_payload`), so a deep chain's
  **decoded input is itself O(N²)**; and the sidecar loader enforces a **cumulative 1,000,000-id
  decode budget** (`_MAX_RUN_EXPANSION`) — a persisted full-coverage deep chain at 10⁵ cannot load
  at all. The pre-flight proof therefore includes the decode budget; the measured chain is either
  **built in memory** (bypassing the persisted-sidecar path — stated in the artifact) or sized to
  an **isolated core within budget**; and the characterization reports complexity against **input
  bytes and node count separately** — conflating them reads representation growth as op cost.
- **Red-first:** the shipped O(N²) deep-chain against the pre-registered budget → RED, captured
  per the INV-6 artifact discipline.
- **Lifecycle:** INV-7 does **not** flip at item 3 unless an in-scope fix lands — end-state (b)
  is a legitimate close.
- **Gates:** **DR-6** (per PR-4).

---

## §3 Build order + dependencies

1. **Component 0** — mutation/provenance engine + fixture materialization (split per §1), with the
   **gating generator self-tests before any invariant consumes it**: the §1.3 relation laws;
   relation cardinalities for split/merge/duplicate; moved destination preserved; insert/delete
   null sides; deterministic seed replay; no accidental source-id reuse.
2. **INV-1 + INV-2 together, on the same seeded corpus/config** — otherwise INV-1 sees only
   hostile cases and INV-2 only easy ones, a coverage gap between them. Emit a per-case
   diagnostic breakdown (bound-correct / abstained / wrong) — **reported, not a gated rate**
   (rates are S5.2's).
3. **INV-3, INV-4** — drift honesty + boundary discipline. The merge/duplication
   **global-conflict (double-claim)** case is named explicitly here and runs as the INV-1 global
   conjunct's subcase (no new INV-8 — the ratified seven stand).
4. **INV-5** + the §1.6 mode×drift interaction matrix (six pinned rows).
5. **INV-6, INV-7** — the reds against the shipped cubic mechanisms, per the §5.2 ruling
   (now-or-never before #48 deletes `_Assignment`), with the item-2/item-4 split of §5.2 and the
   separate lifecycles pinned in §2.

**At green — which lands at item 3 (§0.2):** mutation hunt (extend `hunt_rebind.py`, §0.1
protocol); **wide+narrow adversarial audit + Rule-A delta re-audit before commit**
([[feedback_adversarial_audit_cadence]]) with concrete executable checklists/commands, not bare
labels. **The audit's primary target is INV-1 + INV-2 + INV-3 (correct, non-inert, drift-honest)
AND the generator/oracle/perf-harness code itself** — the harness is likelier than the mechanism
to manufacture a false green.

---

## §4 Anti-cheating guards (baked into the harness from line 1)

- Every invariant **seen RED** before green — a planted violation (demonstrated) or a mutation;
  a never-red test is a claim. Protocol per §0.1; lifecycle per §0.2.
- Oracles are **ground-truth-by-construction** (§1.3 provenance relation / planted positions),
  never `rebind()`'s output; independence per §1.4.
- **Randomized-test discipline:** fixed and reported seeds; **minimal-counterexample retention =
  the failing seed + fixture-config dump** (no hand-rolled shrinker — machinery no red needs;
  ruled A6); a minimum case count per operation/composition; failure replay.
- **Mutation hygiene:** fresh subprocess per mutant; `PYTHONDONTWRITEBYTECODE=1` +
  `__pycache__` purge; verify the mutated source is the file imported; byte-identical verified
  restore (isolated worktree for SIGKILL-class risk) — §0.1.
- **`pytest.raises(match=)`** binds **only** to a dedicated strict-path test **among assertions
  on `rebind()` outcomes**: `rebind()` is non-raising (returns a `RebindReport` with typed
  findings) — the invariants assert the **closed reason + affected node/slot on the returned
  report**; only `assert_all_bound()` raises `RebindError`, and its test matches the raise's
  wording, never the feature word or `tmp_path` ([[feedback_pytest_match_leak]]). This
  exclusivity does **not** forbid raise-assertions outside rebind outcomes — the §1.1 bundle
  validator's rejection tests and the `_check_baseline` stale-artifact tests legitimately assert
  raises, as the existing suite already does.
- **No `skipif`-masking**; assert referents actually resolve/import ([[feedback_validate_bindings]]).

---

## §5 Sub-decisions — RULED (Ben, 2026-07-09), as refined by review

1. **R-b token granularity [RULED]:** default **tolerate-via-ratio; do not pre-build
   char-level.** The boundary char-sub axis (INV-2 diagnostic) is the measurement instrument.
   **Escalation trigger (pre-registered, a property not a rate):** a **planted in-token
   char-substitution at/near a node boundary** where (i) the provenance oracle permits exactly
   one bind, (ii) a **small, test-only, bounded independent char-level reference oracle** —
   **built only at item 3, and only if the trigger case is reached for evaluation** (the trigger
   cannot fire before the mechanism exists and abstains) — establishes the refined representation
   WOULD bind (content ≥ τ, boundary context unique-in-both under refinement, globally valid —
   the oracle proves *feasibility*, it is never the production path), and (iii) token-level
   projection nonetheless abstains — isolating granularity as the sole cause. (The
   atom-split-unchanged-token case is *not* the trigger — it produces identical tokens, so char
   refinement cannot fix it; it tests back-pointer projection.) Sequence: **compare Indel vs
   Levenshtein first** (the DR-1 deferred variant choice resolves here — and at that resolution
   the backend **conformance identity** is pinned per parent §2.1/§2.8, dispositions B-2: library
   + version + variant + options + opcode semantics + tie behavior; the `difflib` fallback gets
   its own conformance contract or is dropped); invoke coarse-to-fine
   **only if both** fail the named existence case. Production refinement is built only after the
   trigger fires. The ~5–6× char/token blow-up figure is an estimate, labeled as such.
2. **INV-6/INV-7 ↔ item-4 overlap [RULED]:** the red scale/evidence tests are written **in item
   2, against the shipped cubic mechanisms, before half B lands** (now-or-never). Item 2's
   harness is **minimal, defined by outputs — the parent-ratified set** (§8 item 2):
   parameterized fixture constructor, phase-separated `perf_counter` timer, **`tracemalloc`
   memory wrapper**, deterministic red sizes, saved result artifact — **no** six-point sweep,
   **no** nightly wiring, **no child-process RSS machinery** (item 4 productionizes; it is not
   build-from-zero).
   **RSS handoff design (ruled A1, 2026-07-17 — item 3/4's, NOT built in item 2).** The review
   resolved the honest native-aware memory decomposition after a four-round correction sequence
   (see the trail); it is preserved here as the design the item-3 durable memory gate and item-4
   productionization inherit, because `tracemalloc` cannot see the replacement mechanism's
   RapidFuzz allocations: the measured child receives a minimal descriptor (phase-id + persisted
   input recipe + explicit setup boundary; spawn pinned — a live
   callable may not pickle, and fork-vs-spawn shifts the baseline) and performs the ratified
   serialize→load→index→rebind chain itself; since `save_stream` can only serialize an object
   that exists in memory, no design yields a "clean" lifetime peak of just the chain — so the
   harness reports **three nested values**: (a) lifetime `ru_maxrss` as the conservative
   end-to-end upper bound (includes materialization, labeled as such; units normalized — KB on
   Linux, bytes on macOS/BSD); (b) the absolute sampled peak RSS of the named-ops span (D35's
   real CLI burden); (c) the incremental peak above the post-materialization baseline (operation
   overhead), via a sampled-current-RSS monitor whose cadence/method is pre-registered and
   validated against a planted short-lived allocation (a narrow native peak must not slip
   between samples). Materialization overhead is the
   reconciliation between them (lifetime ≥ absolute-sampled ≥ incremental); the lifetime bound
   and the named-ops growth result gate separately. **The trail's pinned
   `measure(phase_descriptor)` signature is dropped** (its single RSS return value could not
   carry the three nested values it was meant to serve); **item 4 defines the sampler interface**
   when it builds per-phase children, and the concrete sampler is selected and verified with a
   real measurement then.
3. **Anchor-poor density [RULED]:** sweep, not a point — but the sweep is **item 4's** (§1.5);
   item 2 ships the knob + sentinels and no rate claims; the §1.5 pairing discipline is a
   construction rule for when density fixtures are built (item-2 sentinels need not be paired).
   The finite-sample acceptance rule belongs to the owning item (4 for the
   correctness-at-density property, S5.2 for rates).
4. **Fixture substrate [RULED, with caveat]:** **synthetic-only for the item-2 gating
   invariants**; Ben's caveat governs — the synthetic provenance relation is the oracle for the
   *conditional property*, NOT a deployment-correctness certificate (§1.4 guard). The copy2/PLL
   probe is **removed from item 2** (§1.4.4); the real-data obligation lives as the **forward
   gate row `S5.1-RG`** on the open #48 row, with explicit dependencies — historical tracker
   rows' acceptance claims stay intact; any amendment to a completed row is a dated addition,
   never a rewrite of its original acceptance claim.

---

## §6 Open items / handoffs (so nothing evaporates when item 2 closes)

- **PR-3 (deferred-for-information, re-expressed per A7):** demonstrate
  **confirmation-in-churn** — can the confidence gate positively confirm a boundary inside a
  non-clean region? Decision mechanism pinned (§2 INV-4): the item-2 carried-red
  confirmation-path test; the item-3 implementation attempt is the verdict; undemonstrated →
  the non-clean classes stay fail-loud as a measured outcome (no design unwind). Not rulable at
  this spec's sign-off.
- **Absolute resource ceiling (tri-state):** numeric budget unresolved / ceiling requirement
  ratified (S4.7 tracker row, DR-7) / **Ben** sources-or-rules it before item 4 acceptance.
- **Item-4 handoffs:** the density **sweep** — ~6 points from PLL's rich end (71% type-unique
  3-grams) down to ~10–15% (floor and point-count tunable, per the §5.3 ruling) — and the
  correctness-at-density curve on the real v3 anchor object (§1.5), with the ruled **directional
  gate criterion: the wrong-content false-bind rate stays at the S5.2-owned floor across the
  entire sweep; only the abstention/fail-loud rate is allowed to rise as density drops** (a
  single cherry-picked low point is rejected); the **RSS memory design** (§5.2 handoff — three
  nested values, validated sampler; item 4 defines the interface); per-phase memory children; CI
  tiers + 10⁵ nightly **(with the `scale` marker registered in `engine/pyproject.toml` and
  deselected from default runs — parent §5 as amended, dispositions B-6; both CI workflows
  currently run bare `pytest -q`)**; the absolute ceiling above.
- **S5.2 handoffs:** τ calibration; the three-rate negatives; finite-sample acceptance rules;
  τ-calibrated zero-false-bind (DR-9).
- **Real-data gate:** tracker row **`S5.1-RG`** (real-PLL re-extract post-S4.6, with the §1.4.2
  triage rule — builder classifies, Ben rules routing). The copy2 distribution question is
  registered there, descriptive-only if revived.
