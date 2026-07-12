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

@@@@@@
**Adversarial audit:** "Seen red" needs an auditable protocol, not just a slogan. State where the red
result is recorded, whether each run occurs in a fresh subprocess, how the production source is restored,
and what command proves the subsequent green. Also distinguish two different things currently conflated:
a planted bad implementation/fixture used to validate the test, and a mutation of the eventual green
implementation. A fixture containing drift is not itself a red-first violation unless the assertion is
known to fail for the intended defect.
@@@@@@

======
**Conceded.** The protocol belongs consolidated in §4, not as a §0 slogan. Will specify: red result
recorded as a committed **artifact** (baseline doc + the failing-assert output), **fresh subprocess per
mutant** (not in-process reload — see R25), production source restored in a `finally`-path, green proven
by a named `pytest -k …` command. And I adopt your distinction explicitly: a drift **fixture** only
supplies inputs; the red-first **violation** is either (a) a planted bad *implementation* (guard removed)
the assertion is *shown* to fail, or (b) a mutation of the green impl. A fixture ≠ a red-first check.
======

@@@@@!
**Second-pass audit:** A prose artifact plus pasted failing output is not enough to prove the intended
mutant ran. Record a machine-readable manifest containing the test node ids, command, exit code, mutant
diff/hash, imported module path, pre/post source hash, seed, and environment identity. Prefer mutating an
isolated temporary checkout/copy rather than production source; a `finally` restoration does not run after
every hard interruption. Also reconcile "committed artifact" with the parent plan's "commit only when Ben
asks": the artifact may be prepared in the worktree, but committing remains separately authorized.
@@@@@!

=====!
**Accepted.** Machine-readable run manifest (node ids, command, exit code, mutant diff/hash, imported
module path, pre/post source hash, seed, env). Constructive: don't hand-roll it — a mutation-testing tool
(`mutmut`/`cosmic-ray`) provides the isolated-copy execution + provenance for free (a hand-rolled harness
is itself a false-green risk, per the §4 point). `finally` isn't interruption-proof → mutate an isolated
temp checkout, not production source. And yes: artifact **prepared** in the worktree; **committing** stays
separately authorized (commit-only-when-Ben-asks).
=====!

@@@@!!
**Third-pass audit:** `mutmut`/`cosmic-ray` do not provide this "for free" here. Neither is a declared
project dependency, while the repository already has an established invariant-targeted runner and records
that `mutmut` 3.x fought the `src/` layout and Cosmic Ray leaves source dirty if interrupted
(`ENGINE_STRUCTURE_TASKS.md` O5). First spike the existing runner in an isolated worktree against the
required manifest; adopt a new tool only if it demonstrably supplies the exact semantic mutants and
provenance fields. Generic mutation operators will not necessarily produce the load-bearing guard removals,
so an off-the-shelf tool may supplement, not replace, the named mutant table.
@@@@!!

====!!
**Accepted — verified against the repo; corrects my own second-pass.** The established runner is
`~/.claude/skills/mutation-hunt/hunt.py`, driven by declarative mutant tables under `tests/hunts/` —
**including an existing `hunt_rebind.py`**. So INV-1…7 red-first **extends that table** (a new/extended
rebind table), it does not adopt a new tool. Verified specifics that kill my "mutmut/cosmic-ray for free"
line: (a) the runner **restores byte-identical, signal-deferred, guaranteed on SIGINT/SIGTERM** with a
post-restore `_sweep_clean` verify (`hunt.py`: "CRITICAL: restore is not byte-identical", exit 130 =
interrupted-but-restored) — that *is* the isolated-copy safety I demanded, achieved by verified-restore, not
by copy; (b) `conftest.py` already pins `sys.dont_write_bytecode=True` globally, and the child env pins
`PYTHONDONTWRITEBYTECODE=1` + purges `__pycache__` (venv-aware); (c) it already emits the `--artifact` JSON
recording `test_cmd`, per-mutant `{file, old→new}` (the diff), `scope` (test node id), `rc` (exit code),
`purge`, `restore_verified`. **One honest correction to the third-pass framing (not a disagreement):** the
manifest is *mostly* there — the fields still missing for the **property-based** INV-1…4 are **seed,
pre/post source-hash, env identity, module path**, a small artifact extension, not a tool swap. And the
residual case for an isolated **worktree** is narrow — **SIGKILL/crash only** (a deferred handler cannot
survive `kill -9`); that is exactly O5's "stand up cosmic-ray in an isolated worktree" S1.5 on-demand breadth
sweep — a supplement to the named table, never its replacement. Net: the spike outcome is pre-visible
(existing runner primary; cosmic-ray = worktree breadth supplement; generic operators can't hit the
load-bearing guard flips the hand-authored table names).
====!!

@@@!!!
**Fourth-pass audit — artifact claim correction:** The existing runner is the right primary path, but its
current JSON record does **not** contain each patch's `old→new`; the per-mutant record contains label,
scope, files, rc, duration, and status. `old`/`new` remain only in the separately loaded table. Extend the
artifact with the normalized patches or record the table path **and content hash** so the manifest actually
binds to the mutant definitions it claims ran. The runner also edits the active source tree in place and
restores it; signal-safe restoration is strong hygiene, but it is not "isolated-copy execution." Preserve
that honest distinction and retain an isolated worktree for SIGKILL/process-crash risk when warranted.
@@@!!!

===!!!
**Accepted — verified; my round-3 "records the diff" was wrong (second §0 slip, owned).** Confirmed at
`hunt.py:514-522`: the per-mutant artifact record is `{label, status, detected, scope, files (rel paths),
rc, note}` — **no `old`/`new`**; the patch bodies live only in the parsed table, never the artifact. Fix
(adopt yours, both halves): record the **table path + content hash** *and* inline the **normalized patches**
in the manifest — the hash proves *which* table ran, the inlined patches let a reader see the mutation
without the table. And I retract "isolated-copy execution": the runner does **in-place edit + signal-safe
verified restore** — strong hygiene, but **not** an isolated copy — so I keep that distinction and retain an
isolated **worktree** specifically for **SIGKILL/process-crash** (the one case a deferred handler can't
cover). Net: runner = right primary, restore = strong, but the manifest needs the patch-binding extension
and the copy-vs-restore wording stays honest.
===!!!

@@!!!!
**Fifth-pass audit:** One reproducibility field remains: the runner lives outside the repository at
`~/.claude/skills/.../hunt.py`, so its reported name/version does not bind to immutable code. Add the
runner's content hash (and table content hash) to the artifact. Otherwise the same artifact can be replayed
through a locally changed runner with identical version text and different classification/restoration
behavior.
@@!!!!

==!!!!
**Accepted — verified; a real reproducibility gap given the out-of-repo runner.** Confirmed `hunt.py:447`:
the artifact records `{"runner": RUNNER, "version": RUNNER_VERSION, …}` — **version is a text constant, no
content hash**. Since the runner lives at `~/.claude/skills/mutation-hunt/hunt.py` (outside the repo, shared
across the skill suite), a locally-edited runner reporting the same `RUNNER_VERSION` yields an
indistinguishable artifact with different classification/restore behavior. Fix: record **sha256 of the runner
file + sha256 of the mutant table** in the manifest (alongside the round-4 table-path + inlined-patches). Right
home is **upstream in `hunt.py`** (self-hash — benefits every hunt's reproducibility, a low-risk shared-tool
improvement); if we don't touch the shared runner, the item-2 harness wrapper computes and records both
hashes. Either way the manifest binds to the actual runner+table bytes, not mutable version text.
==!!!!

@!!!!!
**Sixth-pass audit — scope boundary:** The hash requirement is resolved, but item 2 should implement it in
the repository-local wrapper/artifact step. Editing the shared out-of-repo `hunt.py` changes every project's
tooling and exceeds this engine task unless separately authorized and regression-tested. A later upstream
improvement can deduplicate the wrapper behavior; it is not required for this harness to produce bound
evidence now.
@!!!!!

=!!!!!
**Accepted — my "upstream in `hunt.py`" was scope creep on a shared global tool.** `~/.claude/skills/mutation-hunt/hunt.py`
is cross-project infrastructure; editing it for item 2 changes every project's tooling and needs separate
authorization + regression, exceeding this engine task (Principle 3 — edit only what the task requires).
Disposition: **compute the runner-sha + table-sha in the repository-local wrapper/artifact step** and record
them in item 2's manifest; **leave the shared `hunt.py` untouched**. Upstream dedup is a separate, later,
optionally-authorized improvement — not required for item 2 to produce bound evidence now. I withdraw the
"right home is upstream" lean.
=!!!!!

**Keystone:** per ratification, **DR-3's confidence gate is not locked as proven until INV-1
(never-a-false-bind) is seen red-then-green.** So INV-1 is not one of seven equals — it is the gate that
converts DR-3 from "build direction" to "locked." Item 2 is, first, the machine that makes INV-1 real.

@@@@@@
**Adversarial audit:** Correct emphasis, but "makes INV-1 real" overstates what the synthetic harness can
lock. Per this draft's own §1 guard, it establishes a conditional property under modeled drift, not
real-re-extraction correctness. The lock record should explicitly name that bounded claim and retain the
post-S4.6 real gate; otherwise this paragraph invites later readers to treat DR-3 as generally proven.
@@@@@@

======
**Conceded** — it contradicts my own §1 guard. Reword: item 2 makes INV-1's **conditional** property
checkable (never-false-bind *under modeled drift*); the DR-3 lock record names that bounded claim and
retains the post-S4.6 real gate (R9). "makes INV-1 real" → "makes INV-1's conditional property checkable."
======

@@@@@!
**Second-pass audit:** The bounded lock must identify the generator/oracle version and quantifiers (seeded
corpus, operation matrix, case count, and modes), not merely say "modeled drift." Otherwise the generator
can later narrow while DR-3 remains labeled locked. Define what changes invalidate and require re-running
the lock.
@@@@@!

=====!
**Accepted.** The lock record pins: generator + oracle **version hashes**, the exact case matrix, seeds,
and the mode(s) run. Invalidation trigger: **any** change to the generator, oracle, or case matrix voids
the lock and forces a re-run before DR-3 may re-read "locked." Otherwise a later narrowing silently
weakens a lock that still reads green.
=====!

---

## §1 Component 0 — the drift generator (the shared prerequisite)

The single most load-bearing build in item 2. INV-1/2/3/4 all consume it; DoD item 2 explicitly gates on
it ("drift generator built so INV-2/INV-3 can be seen red"). It reuses the prototype's proven approach
(`perturb_witness` + the copy2-derivation oracle) — a settled design direction, now ported into a test
fixture rather than a scratchpad.

@@@@@@
**Adversarial audit:** "Proven" and "settled" are stronger than the cited evidence supports: the draft
later says drift-model fidelity is unvalidated and calls copy2 a softer oracle. Identify exactly which
generator behaviors the prototype validated and treat everything else as new test-harness work. Porting
scratch code without first specifying its invariants risks carrying prototype assumptions into the oracle.
@@@@@@

======
**Conceded** — "proven/settled" over-claims vs the later "fidelity unvalidated." The prototype validated
only the *perturbation mechanics* (drop/dup/mutate yield a re-atomizable stream) and the copy2-derivation
*oracle wiring* — **not** that the drift distribution matches real re-extraction, and not the provenance
model (which R6 shows was wrong). Reword to "reuses the prototype's perturbation mechanics"; everything
else is new harness work gated by the §3 generator self-tests. Will not port scratch code before its
invariants are specified.
======

@@@@@!
**Second-pass audit:** The `R6`/`R9`/`R25`-style references used throughout these responses have no labeled
targets in this document. Replace them with section/INV references or introduce an explicit response ledger;
otherwise the proposed cross-references are not reviewable after blocks are rearranged or resolved.
@@@@@!

=====!
**Accepted — my process error.** The `R6/R9/R25` tags are chat-summary shorthand; in-doc they're dangling.
Rev 2 will carry a numbered **response ledger** (stable ids) or use §/INV anchors, so cross-refs survive
block reordering/resolution.
=====!

- **Input:** a canonical atom stream + its witnesses (a synthetic fixture, and PLL as a real anchor.)

@@@@@@
**Adversarial audit:** This input is underspecified for `rebind()`. The harness also needs an old
`StructureMap`/projection, stored anchors or a specified anchor builder, fresh stream metadata, mode, and
(for re-stamp paths) evidence. Define a single fixture-bundle type and who regenerates each derived field;
otherwise tests may accidentally compare anchors built from fresh truth rather than the stored old state.
"PLL as a real anchor" also conflicts with §5.4's synthetic-only item-2 ruling and the stated S4.6
dependency. Decide whether PLL/copy2 is built now as a non-gating probe or deferred, and say so once.
@@@@@@

======
**Conceded — code-verified.** `RebindContext.__init__` requires `old_map: StructureMap` (projection +
stored per-slot fingerprints/anchors), `old_streams` (canonical **+** witnesses), `fresh_streams`,
`old_evidence` (re-stamp paths), `geometry_mode`, `policy`. And `_check_baseline` enforces a **dual-hash**:
the old canonical must be *exactly* the stream the old map's manifest was stamped against — so a careless
perturb-and-rebuild is **rejected**, not silently mis-tested. Will define one `RebindFixtureBundle` type
naming every field + who regenerates it, and pin that **stored anchors come from the OLD map, never
rebuilt from fresh truth** (your exact trap). "PLL as a real anchor" is struck here — it's a non-gating
probe defined once in §5.4 (R11/R29), not a Component-0 input.
======

@@@@@!
**Second-pass audit — factual correction:** `old_evidence` and `policy` are optional constructor inputs,
and the old/fresh mappings need not contain a non-empty witness set. Describe the bundle's required versus
optional fields accurately so simple invariants do not manufacture evidence/witness complexity. The
baseline is content-hash gated in all modes but geometry-hash gated only outside `no-geometry`; calling it
an unconditional "dual-hash" check is misleading, especially after proposing that INV-1…4 all run in
`no-geometry`. Add an explicit bundle validator rather than relying on prose about who generated fields.
@@@@@!

=====!
**Accepted — code-verified, corrects my own claim.** `_check_baseline` checks `canonical_content_hash` in
**all** modes (rebind.py:458) but `canonical_geometry_hash` **only** `if dp_mode != MODE_NO_GEOMETRY`
(rebind.py:465). So "dual-hash" is loose; it's **content-always + geometry-conditional** — and since
INV-1…4 run `no-geometry`, only the content-hash gate fires for them. `old_evidence` and `policy` default
`None` (optional); the witness set may be empty. Bundle: **required** = {`old_map`, `old_canonical`
matching the manifest content-hash, `fresh_canonical`, `geometry_mode`}; **optional** = {witnesses,
`old_evidence`, `policy`}. Add an explicit **bundle validator**, not prose.
=====!
- **Perturbation classes** — each independently toggleable and composable, matched to the plan's drift
  model (§2.5 R-a/R-b):
  - **char-substitution** (OCR-class, *in-token* → the whole token becomes `replace`, coarsening
    alignment — the R-b axis).
  - **atom drop / atom insert.**
  - **atom duplication** (dittography).
  - **re-segmentation:** split one atom → two, merge two → one (the D25 axis; diff models a split as
    insert-adjacent-to-`equal`).
  - **local reorder / moved block** (R-a — the *weakest* axis; INV-3's target).

@@@@@@
**Adversarial audit:** The axes need precise semantics and coverage constraints. Splitting an atom at a
token boundary does **not** necessarily appear as an insert adjacent to equal after the specified
concatenate-then-tokenize pipeline; it can leave the token sequence completely unchanged and only alter
token→atom back-pointers. Likewise merge can create the already-known two-old-nodes→one-fresh-atom
collision. Include these back-pointer-only cases explicitly. Define reorder window/block sizes,
cross-container moves, repeated-content interaction, and legal compositions; unconstrained composition
can create invalid or uninterpretable fixtures rather than adversarial valid ones.
@@@@@@

======
**Conceded — code-verified; I was wrong.** `normalized_slot_tokens` tokenizes **per-atom, concatenated**
(each token carries an intra-atom offset), so a split **at a token boundary leaves the token sequence
identical** — pure back-pointer change, invisible to the diff (all `equal`). My "split → insert-adjacent-
to-equal" is inaccurate; only a *mid-token* split perturbs tokens. So **"atom split with unchanged
tokens" is the primary split case** and must be explicit, as must merge's two-old→one-fresh collision
(the double-claim the S5.1 audit already caught — R21). Will replace the axis bullets with precise
semantics + coverage constraints (reorder window/block sizes, cross-container moves, legal compositions,
the back-pointer-only cases).
======

@@@@@!
**Second-pass audit:** Keep current-code facts separate from the planned v3 implementation. The current
`normalized_slot_tokens` returns strings and does not attach the proposed token→atom/intra-atom
back-pointers; those are new Layer-1 work. The unchanged-token split conclusion is still correct, but the
harness must explicitly test the new back-pointer producer rather than cite a capability the current
function does not have.
@@@@@!

=====!
**Accepted — code-verified.** `normalized_slot_tokens` returns `list[str]` with **no** back-pointers; the
per-atom concatenation (the basis for split-invisibility) is current, but the token→atom / intra-atom
back-pointer producer is **new §2.1 Layer-1 work**. The harness must test that new producer as its own
unit, not cite a capability the shipped function lacks. The split-invisibility conclusion stands; the
capability citation was wrong.
=====!
- **Output:** the perturbed stream **plus a recorded identity map** `old-atom-id ↔ fresh-atom-id`
  (∅ for a dropped or moved atom). **Ground truth by construction — never derived from the mechanism's
  output.** This is what every oracle below reads.

@@@@@@
**Adversarial audit — blocking defect:** This cannot be a bidirectional map. Duplication and split are
one-to-many; merge is many-to-one; insertion has no old source. A moved atom is **not** ∅—its planted
fresh destination is precisely the truth INV-3 needs. Model provenance as a relation (with operation and
source/destination positions), then derive node-level allowed outcomes from it. Preserve moved identity
while separately marking it `moved`; reserve ∅ for deletion. Without this correction INV-1 can accept
the wrong duplicate and INV-3 cannot distinguish the planted destination from a mis-projection.
@@@@@@

======
**Conceded — blocking; the single most important fix in the audit.** A bidirectional `old↔fresh` map
cannot represent duplication/split (1→many), merge (many→1), or insertion (no old source), and mapping a
move to ∅ destroys exactly the INV-3 oracle. Replace with a **provenance relation**: per event, record
`(op, old_atom_id(s), fresh_atom_id(s), old_pos, fresh_pos)`; derive node-level allowed outcomes from it.
Moved atom keeps its identity + a `moved` flag (its planted destination **is** the truth INV-3 checks);
∅ reserved for delete only. This propagates to every oracle below (INV-1/2/3/4 all re-cut against the
relation, not a map).
======

@@@@@!
**Second-pass audit:** An event tuple alone is not yet a usable final oracle when perturbations compose.
For duplicate→move→split or merge→edit, `old_atom_id(s)` and positions at one event no longer directly
describe final fresh ancestry. Define stable lineage identities and a composed final many-to-many
old↔fresh provenance relation, while retaining the ordered event log only for diagnostics. Specify whether
positions are pre-event, post-event, or final; otherwise compositions can yield internally inconsistent
truth.
@@@@@!

=====!
**Accepted — strengthens the fix.** A flat event list doesn't compose (duplicate→move→split, merge→edit).
Model: stable **lineage identities** + a derived **final many-to-many old↔fresh provenance relation** that
the oracle reads; keep the ordered event log for **diagnostics only**. Positions in the oracle relation
are **final** (post-all-events); event-log positions are per-event and non-authoritative. A generator
self-test asserts the composed relation is internally consistent before any invariant consumes it.
=====!

@@@@!!
**Third-pass audit:** Define "internally consistent" as executable relation invariants, not a generic
self-test: every final fresh atom has old ancestry unless introduced by insert; deleted old atoms have no
final descendants; split/duplicate descendants preserve one source lineage; merge may carry multiple old
ancestors; moves preserve ancestry while changing final order; and the final relation equals composition of
the event transitions. Content edits should preserve ancestry. Without these laws, the implementation can
declare its own malformed relation consistent.
@@@@!!

====!!
**Accepted — adopt the six laws verbatim as the executable spec.** "Internally consistent" becomes these
named, individually-mutated generator self-tests: (1) every final fresh atom has old ancestry unless
`insert`; (2) deleted old atoms have no final descendants; (3) split/duplicate descendants preserve exactly
one source lineage; (4) merge may carry ≥2 old ancestors; (5) moves preserve ancestry, change final order;
(6) **final relation == composition of the event transitions**; plus content-edits preserve ancestry. Law
(6) is the master check; (1)–(5) are deliberately **redundant** cross-checks — a composition bug can satisfy
(6)'s fold yet violate a cardinality law, and a hand-miscount can pass (1)–(5) yet break (6) — defense in
depth, each its own red. These gate as §3-item-1 prerequisites **before any invariant consumes the
relation**.
====!!

@@@!!!
**Fourth-pass audit:** Tighten law (4): a **realized merge must** carry the complete set of its ≥2 old
ancestors; "may carry" is permissive enough for a one-ancestor bug to pass. Also ensure law (6) is not a
tautological comparison between two views produced by the same fold. Compute the expected closure with a
small independent reference composition (or assert against hand-pinned composed examples) while the
generator produces the reported final relation.
@@@!!!

===!!!
**Accepted — both tighten the generator self-tests.** Law (4): **"a realized merge MUST carry the complete
set of its ≥2 old ancestors"** — "may carry" would let a one-ancestor drop pass, exactly the
permissive-quantifier bug red-first targets. Law (6): guard the **same-fold tautology** — the "expected"
composition must come from an **independent reference composition (or hand-pinned golden composed
examples)**, never the generator's own fold compared to itself (that proves nothing), the same not-circular
rule as the §1 oracle. Both fold into §3-item-1's gating self-tests, each its own red.
===!!!
- **Anchor-density knob (ties §8.4, the ratified DoD requirement) — SWEEP, not a point [§5.3 RULED 2026-07-09]:**
  a control that thins unique-in-both anchors (dilutes type-unique 3-grams), swept across **~6 points from
  PLL's rich end (71% type-unique 3-grams) down to ~10–15%** (verse, fragmentary/OCR-short atoms, dense
  repetition are the natural low-density sources; floor + point-count are tunable). **Gate criterion —
  directional and un-gameable:** the **wrong-content false-bind rate stays at the S5.2-owned floor
  (≈0 / within the characterized residual) across the entire sweep**; only the **abstention/fail-loud rate**
  is allowed to rise as density drops (INV-1's fail-loud-not-silent promise; DR-9's split — S5.2 owns the
  rate). Report the whole curve in `s4_7_scale.md`. A single cherry-picked low point is rejected.

@@@@@@
**Adversarial audit:** This imports item 4's full sweep and rate reporting into Component 0/item 2 despite
§3 and the ratified DoD assigning productionization and the full sweep to item 4. For item 2, build only
the knob plus deterministic sentinel points needed to see a red. Also, "wrong-content false-bind rate
≈0" is both undefined (sample count, confidence bound, denominator, and "characterized residual" are
missing) and perilously close to taking S5.2's rate/calibration ownership. Keep INV-1 as a deterministic
set/property assertion over generated truth; reserve the population curve and statistical acceptance rule
for item 4/S5.2 as ratified. Finally, specify how density is measured after perturbation and how thinning
changes density without simultaneously changing unrelated difficulty variables.
@@@@@@

======
**Conceded — this is my scope creep, on both counts.** (1) The full 6-point sweep + curve reporting is
**item 4** (per §3/§5.2/ratified §8); item 2 builds only the density **knob** + a couple of deterministic
**sentinel** points needed to see a red. (2) "false-bind rate ≈0" drifts into S5.2's rate/calibration
ownership (DR-9) and is undefined (no sample/denominator). Demote item-2 to a **deterministic
set/property assertion** over generated truth ("*this* planted wrong-copy must not bind"); move the
population curve + statistical acceptance to item 4/S5.2. The confound problem (varying density without
varying difficulty) is real and answered in R28 (controlled-vocabulary generator).
======

@@@@@!
**Second-pass audit:** The knob must target the actual v3 boundary-anchor object, not merely type-unique
3-grams. Prefix+exact+suffix anchors can have a different uniqueness distribution from generic 3-grams,
especially at short slots and boundaries. Schema/anchor construction must be fixed before sentinel density
has a stable meaning. Also say whether item 4 owns the correctness-at-density property while S5.2 owns only
threshold/rate calibration; writing "item 4/S5.2" leaves the same ownership seam unresolved.
@@@@@!

=====!
**Accepted.** Density must be measured on the **actual v3 boundary-anchor object** (prefix+exact+suffix),
not generic type-unique 3-grams — their uniqueness distributions differ at short slots/boundaries — so the
anchor **schema must be fixed first** (a dependency on the #48 anchor design). Seam resolved: **item 4
owns the correctness-at-density property; S5.2 owns threshold/rate calibration.** "item 4/S5.2" replaced
with that split.
=====!

@@@@!!
**Third-pass audit — unresolved build-order dependency:** Item 2 precedes the #48 mechanism landing, yet
this response makes its density knob depend on the actual v3 anchor schema being fixed first. Resolve
whether item 2 owns a small, ratified pure anchor-construction/reference function that later production code
must match, or whether the density sentinel moves to item 4 after schema v3 lands. Do not let tests invent a
test-only anchor representation that production can later implement differently.
@@@@!!

====!!
**Real dependency I created — and it dissolves without either of your two options.** The circularity is only
apparent because I conflated two item-2 needs. The **DR-3-locking red** (INV-1 binds the *wrong repeated
copy* without the uniqueness guard) needs *planted repeated content*, **not** a calibrated anchor-density —
and a passage repeated verbatim, with a node boundary sitting deep enough inside it that the window stays
within the repeat on both sides, has a **byte-identical (hence non-unique) boundary anchor for the entire
ratified prefix+exact+suffix shape family (DR-4)**, for *any* width/normalization params #48 later fixes. So
that red is **representation-agnostic and stays in item 2**, blocking on nothing from #48. What genuinely
needs the fixed v3 anchor object is the **density-vs-correctness *curve*** (§8.4's parameterized sweep) →
**item 4**, post-schema-v3. So **§8.4 splits**: item-2 = the repeated-passage red (agnostic); item-4 = the
density curve (on the real anchor). **Item 2 invents no test-only anchor representation** — it asserts a
property (verbatim-repeat ⇒ non-unique boundary) true for every anchor in the ratified family, not a
concrete constructor production could diverge from. This is tighter than deferring the sentinel wholesale
(your option b) and dodges the divergence trap of item 2 minting a reference constructor (your option a).
Flagging as a **build-order confirmation** (not a ratified-authority change): confirm §8.4 lands with this
item-2/item-4 split.
====!!

@@@!!!
**Fourth-pass audit:** The split is promising but the representation-agnostic proof needs one bounded
premise that is not yet ratified: prefix/exact/suffix anchors must be deterministic, content-only, and have
a finite maximum context width smaller than the planted repeated region. "Any width" is false if #48 may
choose context extending beyond the repeat; a positional/structural component would also distinguish the
copies despite byte identity. Either pin those anchor-family constraints now or construct the item-2 red
against a specifically ratified minimal non-unique anchor. Otherwise a later legitimate anchor choice can
invalidate the supposedly schema-independent red.
@@@!!!

===!!!
**Accepted — "any width" over-claimed; the red is contingent, not unconditional.** The representation-agnostic
proof holds only under three anchor-family premises: the anchor is **deterministic, content-only (no
positional/structural component), and has a bounded max context width W smaller than the planted repeat**. A
positional/structural component makes the two byte-identical copies distinguishable; context extending
*beyond* the repeat diverges into the differing flanks — either kills the red. Disposition: **pin those three
premises as ratified #48 anchor-family constraints now** (reasonable properties DR-4's prefix+exact+suffix
should have anyway) and enforce them with an **INV-5-style contract test** (a later violating anchor choice
then reds the contract instead of silently invalidating the red); item 2 plants a repeat wider than 2W and
asserts the property *given* the premises. Fallback if you'd rather not pin them: your alternative — build
against a **specifically ratified minimal non-unique anchor**. Either keeps item 2 from minting a divergent
constructor, but I concede it's **premise-contingent**, not the unconditional "any width" I claimed.
===!!!

@@!!!!
**Fifth-pass audit — ruling required:** Pinning deterministic/content-only/bounded anchors is a material
new #48 design constraint, not a reviewer-local cleanup; "reasonable properties" is not authority. Present
it as an explicit parent decision with the alternative minimal-anchor fixture. If accepted, put its contract
under **DR-4**, not "INV-5-style" mode orthogonality. Define whether W bounds only prefix/suffix context or
also the `exact` component, and plant the entire selected exact content plus >W context twice. A later
positional/structural corroborator may be a legitimate separate signal; the contract should prohibit it from
being smuggled into the **content boundary anchor**, not prohibit future independent disambiguation.
@@!!!!

==!!!!
**Accepted — and you're right it's an authority overreach on my part; this is parent-ruling #5.** Pinning
deterministic/content-only/bounded-width anchors is a **material #48 design constraint**, not reviewer
cleanup — "reasonable properties it should have anyway" is not authority (the same self-narrowing trap I
flagged elsewhere). So: **present it as an explicit parent decision, with the minimal-anchor-fixture
alternative** (ruling #5). Three corrections adopted: (a) if ratified, the contract lives under **DR-4**
(anchor enrichment), **not** "INV-5-style" — INV-5 is mode orthogonality, wrong home; my label was wrong.
(b) Define **W's scope explicitly** — whether the bound covers only prefix/suffix context or also the `exact`
component — and the fixture plants the **entire selected `exact` content + >W context, twice**. (c) Sharpen
"content-only": the contract prohibits folding a **positional/structural component into the content boundary
anchor**, but does **not** prohibit a separate independent positional disambiguator (a legitimate future
signal) — ban contamination, not future disambiguation. **Priority flag:** #5 is load-bearing — the
representation-agnostic INV-1 red that **locks DR-3** (block C) and the INV-4 exception red (block 4) both
depend on it.
==!!!!

**Guard — the identity map is the oracle for the *conditional property*, NOT a deployment-correctness
certificate [§5.4 RULED 2026-07-09, Ben's caveat]:**
1. **Not circular.** No invariant's "expected" may be computed from `rebind()`'s output — that is circular
   and void.

@@@@@@
**Adversarial audit:** Necessary but insufficient. Ban reuse of the production alignment opcodes,
normalizer, anchor-index builder, and boundary-projection helper in the oracle too; otherwise a shared bug
can green both sides without reading `rebind()` output. Name the small independent reference model the
tests will use.
@@@@@@

======
**Conceded + strengthened.** Not-circular must ban the shared **production helpers** too — the alignment
opcodes, `normalize_tokens`, the anchor-index builder, the boundary-projection helper — not just
`rebind()`'s return. Will name a small **independent reference oracle**: a bounded brute-force alignment
(R12) + a hand-rolled half-open boundary classifier sharing **no code** with `rebind.py`. A shared-bug
greening both sides is precisely the failure this closes.
======

@@@@@!
**Second-pass audit:** Do not ban the production normalizer without defining semantic equivalence: an
oracle operating on differently normalized text may reject a bind that is correct under the contract or
miss a normalizer defect entirely. Prefer deriving allowed fresh atom ancestry directly from planted
provenance, then test normalization as a separate contract. Clarify the brute-force aligner's role: if
planted provenance is authoritative, brute force should check feasibility/ambiguity under a separately
specified cost model, not overwrite planted identity with whichever optimal alignment it finds.
@@@@@!

=====!
**Accepted — sharper than my R8.** Don't blanket-ban the normalizer; that just moves the oracle onto
differently-normalized text (rejecting correct binds / missing normalizer defects). Correct design:
**planted provenance is authoritative** for allowed fresh ancestry; **normalization is tested as a
separate contract**; the brute-force aligner only **checks feasibility/ambiguity under a separately-
specified cost model** — it never overwrites planted identity with its own optimal alignment. The "ban
shared helpers" rule narrows to: the oracle's *decision* must not be computed by the production
projection/uniqueness path.
=====!

@@@@!!
**Third-pass audit:** Reconcile this explicitly with the ratified wording `bound set ⊆ brute-force
alignment oracle's bound set`. The clean formulation appears to be: planted provenance determines the
correct destination; the independent brute-force model determines whether that destination is feasible and
whether alternatives exist; an allowed auto-bind is their intersection plus the confidence/global-validity
conditions. If the planted destination is infeasible or non-unique, the correct expected result is
abstention, not permission for the brute-force model to select another optimum.
@@@@!!

====!!
**Accepted — this is the clean synthesis; adopt as the INV-1 oracle definition (§2.3), superseding my
"bound set" language.** Pinned: planted provenance fixes the *correct destination*; the independent
brute-force model contributes **only two facts** — is that destination *feasible*, and do *alternatives*
exist (≥2 optima) — it **never selects** a bind (which also keeps it from acquiring production-like pruning
that would mirror the mechanism and dominate randomized-test runtime, the first-pass INV-1 concern). Allowed
auto-bind = planted-destination ∩ brute-force-feasible ∩ (content ≥ τ ∧ unique-in-both ∧ globally-valid).
Planted destination infeasible **or** non-unique ⇒ **expected = abstention**, and the brute-force model is
*forbidden* to substitute another optimum. The mechanism's actual bound set must be ⊆ that allowed set.
Consistent with the ratified `bound ⊆ brute-force bound set`: brute-force is the feasibility **ceiling**,
planted provenance the **correctness** filter — never a bind *source*.
====!!

@@@!!!
**Fourth-pass audit:** Keep three notions separate in the executable oracle: (1) alignment feasibility,
(2) multiple optimal alignments, and (3) boundary-anchor uniqueness. Multiple brute-force optima and a
non-unique boundary anchor are related but not equivalent. The allowed-set confidence conjunct also risks
circularity if `content ≥ τ` and `unique-in-both` are read from production helpers; either compute those
facts with independent bounded reference functions or treat them as separately mutation-pinned contract
preconditions. The provenance∩feasibility synthesis is sound only if the confidence filter cannot reproduce
the same production bug on both sides.
@@@!!!

===!!!
**Accepted — three separate oracle facts, and the confidence conjunct must be independent.** Split the oracle
into **(1) alignment feasibility, (2) multiple optimal alignments, (3) boundary-anchor uniqueness** — related
but not equivalent (an aligner can have ≥2 optimal paths without the boundary *anchor* being non-unique, and
vice-versa); each is its own fact, not folded. And `content ≥ τ` / `unique-in-both` must **not** be read from
production helpers (a shared bug greens both sides): compute the ratio with an **independent bounded reference
function** compared to the ratified τ *value*, compute uniqueness with an **independent index**, **or** treat
each as a **separately mutation-pinned contract precondition**. Governing constraint I'll state explicitly:
the synthesis is sound only when the confidence filter cannot reproduce the same production bug on both sides.
===!!!

@@!!!!
**Fifth-pass audit:** Narrow the offered "or." Mutation-pinned production preconditions are sufficient only
for deliberately constructed cases whose score/uniqueness is analytically fixed (for example exact identity
or a planted duplicate). The randomized INV-1 oracle needs independent bounded computations; otherwise a
production scoring/index bug can still define both the mechanism result and which randomized cases the
oracle considers eligible. State which path applies to which fixture class.
@@!!!!

==!!!!
**Accepted — the "or" isn't a free choice; it's fixture-class-conditional.** Mutation-pinned production
preconditions are sufficient **only for deliberately-constructed cases whose score/uniqueness is analytically
fixed** (exact identity, planted duplicate) — there the "expected" is known by construction, not computed by
production. The **randomized INV-1 oracle requires independent bounded computation** of content-ratio and
uniqueness — otherwise a production scoring/index bug defines **both** the mechanism result **and** which
randomized cases the oracle deems eligible, greening both sides. Rule stated per fixture class:
**constructed/analytic → either path; randomized → independent computation mandatory.**
==!!!!
2. **Scope of proof.** "All synthetic invariants green" proves the invariant properties *conditional on the
   modeled drift* — never "correct on real re-extraction." The real-PLL re-extract (post-S4.6) stays a
   **required** confidence gate, not an optional bonus.

@@@@@@
**Adversarial audit:** Good boundary, but it needs an owner and acceptance artifact. Point to the exact
future DoD/tracker row that blocks deployment, or this is merely prose and can be lost when item 2 closes.
Clarify whether failure there reopens DR-3/#48 or routes to S5.2.
@@@@@@

======
**Conceded.** The post-S4.6 gate needs a real home or it evaporates. Will register it as a
DoD line/row in `ENGINE_STRUCTURE_TASKS.md` (on the S5.1-R #48 and S4.6 rows) with an explicit block
condition, and route failure by the DR-9 split: a **mis-bind** reopens #48 (mechanism); a **rate/
calibration** gap routes to S5.2. Not left as scaffold prose.
======

@@@@@!
**Second-pass audit:** Real-data failures will not always classify this cleanly. A mis-bind may expose an
unmodeled drift class, an oracle/ground-truth defect, or a threshold policy error rather than an algorithmic
#48 defect. Register a triage rule and owner before prescribing issue routing. Editing an already completed
S4.6 row also risks rewriting history; prefer a new dependent gate/checkpoint or an explicit forward
obligation on S5.1-R unless the tracker convention authorizes retroactive amendments.
@@@@@!

=====!
**Accepted.** Real mis-binds need a **triage rule** before routing: is it unmodeled-drift, an oracle/
ground-truth defect, a threshold-policy error, or an algorithmic #48 defect? Add that classifier + an
owner; route only after triage. And put the forward obligation on the **open S5.1-R #48 row** (a new
dependent gate), not the completed S4.6 row — no retroactive history rewrite.
=====!
3. **Oracle independence + teeth.** The identity map must be independent of the mechanism's *design
   assumptions*, not just its output. A generator that emits only diff-friendly drift makes INV-2 pass
   **vacuously** — so it **must** include adversarial drift the mechanism could genuinely fail on
   (reorder/move, heavy re-segmentation), or the invariants have no teeth.

@@@@@@
**Adversarial audit:** Independence is asserted but not operationalized. Require at least one case from
each perturbation class, pairwise compositions for the risky interactions, reproducible seeds, and a
coverage report of generated operation counts. Random generation alone can silently stop producing the
hard cases. "Heavy" also needs a numeric definition.
@@@@@@

======
**Conceded.** Operationalize: ≥1 case per perturbation class; pairwise compositions for the risky
interactions (merge×repeat, split×boundary, move×container-edge); fixed/reported seeds; a coverage report
of realized op counts (random gen can silently stop emitting hard cases). "Heavy re-segmentation" gets a
numeric floor (e.g. ≥X% of atoms split/merged). Folds into the §3 generator self-tests.
======

@@@@@!
**Second-pass audit:** "e.g. ≥X%" still defers the decision the response claims to resolve. Pin X and the
denominator now, and distinguish generated events from successfully realized non-no-op events. Pairwise
coverage is a minimum, not proof that higher-order compositions are safe; keep a deterministic mandatory
matrix and use randomized compositions only as a supplement.
@@@@@!

=====!
**Mostly accepted; one push-back.** Accepted: distinguish **generated** events from **realized non-no-op**
events (a perturbation can no-op); deterministic mandatory matrix primary, randomized compositions a
supplement (pairwise ≠ higher-order safety). **Push-back on "pin X now":** the exact "heavy" fraction is a
build-time knob, not a scaffold constant — I'll **pre-register a defensible default** (≥30% of included
canonical atoms undergo a realized re-segmentation) as tunable, not a guessed final. Pinning a made-up
"final X" now is the same false-precision I (wrongly) defended for the INV-6 ceiling.
=====!

@@@@!!
**Third-pass audit:** The compromise is acceptable only if the gating case pins 30% in its recorded config;
"tunable" may support exploration but must not let a caller lower the gate silently. Define how atoms
participating in a merge are counted (both source atoms) and ensure realized split/merge operations actually
change final segmentation rather than cancel through later composition.
@@@@!!

====!!
**Accepted — all three.** (a) The **gating** case records **30% in its config**; `tunable` means tunable
*up* for exploration — **lowering the gate is a visible, diffed config change, never silent**
([[feedback_no_cheating_results]]); the knob cannot green a run by quietly dropping the floor. (b) Merge
participation counts **both** source atoms. (c) A realized split/merge must change the **final** segmentation,
not cancel through later composition — enforced by the block-2 law family: compare pre/post **final**
segmentation in the generator self-test, and a re-segmentation event that nets zero final change is
reclassified a **no-op** and excluded from the realized count.
====!!
4. **Drift-model fidelity is itself unvalidated.** Whether the perturbation model resembles real
   re-extraction is an assumption checkable only against real data — the copy2-derivation PLL proxy now
   (real distribution, softer oracle), the real re-extract post-S4.6 (highest fidelity). An **open
   assumption**, not a settled fact.

@@@@@@
**Adversarial audit:** Sound caveat. The phrase "copy2-derivation PLL proxy now" nevertheless creates
unplanned work and a "softer oracle" with no definition. Specify its metric and non-gating status, or remove
it from item 2. A proxy should validate the generator's operation distribution, not be blended into the
identity-ground-truth invariant results.
@@@@@@

======
**Conceded.** Scope the copy2 proxy to exactly one job — a **non-gating distribution check** that the
generator's operation mix resembles real copy2-derived drift — explicitly fenced from any
identity-ground-truth invariant. Define its metric (op-class histogram distance) and mark it non-gating,
or cut it from item 2 and defer wholly to the S4.6 gate. Recommend keeping it as a one-shot fenced probe.
======

@@@@@!
**Second-pass audit:** An operation-class histogram is too weak to establish distribution resemblance: it
ignores burst lengths, locality, severity, co-occurrence, content/atom-length conditioning, and the fact
that copy2 derivation is itself only a proxy. Because this probe is optional, non-gating, and needs a new
metric, the scope-disciplined choice is to remove it from item 2 and register it with the real-data gate.
If retained, call it a descriptive comparison, not validation of fidelity.
@@@@@!

=====!
**Accepted — cut it.** An op-class histogram ignores burst length, locality, severity, co-occurrence, and
content conditioning, and copy2 is itself a proxy — too weak to call "fidelity validation." The
scope-disciplined move is to **remove the copy2 probe from item 2** entirely and register it with the
real-data (S4.6) gate. If ever revived it's a *descriptive comparison*, never fidelity validation. This
demotes my own R11 "keep as fenced probe."
=====!

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

@@@@@@
**Adversarial audit:** The oracle is still ambiguous. Define the compared set as concrete
`(node_id, fresh atom interval)` pairs, not merely a "bound set." A brute-force oracle that returns the
union of all feasible alignments can accidentally bless either copy of a repeated passage; the planted
origin/provenance relation must define the allowed pair(s), and ambiguity must be represented separately.
The red fixture also assumes removing the guard necessarily produces a wrong bind, but a diff may choose
the planted copy or abstain. Construct and pin a case demonstrated to fail that mutant rather than relying
on that outcome. Keep brute-force cases deliberately small and specify enumeration bounds; otherwise the
reference oracle can dominate randomized-test runtime or acquire pruning assumptions that mirror the
production algorithm. Finally, the absolute statement "non-unique anchor forces ambiguous" conflicts with the
ratified mode contract saying `geometry-tie-break` may disambiguate a non-unique anchor. State whether
INV-1 is run in `no-geometry`, or amend the expected result to allow an independently valid geometry
disambiguation. Cross-container repetition must also specify whether uniqueness is stream-global,
container-local, or book-global—the mechanism currently describes a whole-stream index.
@@@@@@

======
**Conceded — and it reaches into the ratified plan, not just this scaffold.** (a) Oracle = concrete
`(node_id, fresh_atom_interval)` pairs from the provenance relation (R6), not a "bound set"; ambiguity
represented separately. (b) The red mutant must be a **pinned constructed case demonstrated to fail** —
"remove the guard → wrong bind" is not guaranteed (a diff may pick the planted copy or abstain); correct.
(c) **The mode contradiction is real and lives in the RATIFIED plan:** §4's INV-1 ("non-unique anchor
forces `ambiguous`, never a lone bind") contradicts §2.4 + `resolve_slot:692`, where `geometry-tie-break`
*may* disambiguate a non-unique anchor into a lone bind. INV-1 must be scoped to **`no-geometry`**; I'll
flag the §4/§2.4 latent tension back to the parent plan for a one-line reconciliation (not silently
patch it in the scaffold). (d) Uniqueness scope: the shipped index is **whole-stream** — will state that
and make cross-container repetition test it.
======

@@@@@!
**Second-pass audit:** The concrete oracle key needs `slot_name` as well as `node_id`; containers can own
heading and signature slots with distinct intervals. Prefer the exact ordered fresh-atom-id tuple (or a
formally defined contiguous interval plus stream id), since numeric intervals can look correct after an
incorrect atom back-pointer conversion. Scope "whole-stream" to the canonical included stream and specify
whether **both** boundary anchors must be unique or either non-unique anchor forces ambiguity. Scoping the
base property to `no-geometry` resolves the textual contradiction only after the parent ratified plan is
formally reconciled; the scaffold cannot silently narrow its authority.
@@@@@!

=====!
**Accepted.** Oracle key = `(node_id, slot_name, ordered fresh-atom-id tuple)` — `slot_name` because
containers own heading/signature slots with distinct intervals; the **id tuple** (not a numeric interval)
because an interval can look right after a wrong back-pointer conversion. "whole-stream" scoped to the
**canonical included stream**; uniqueness quantifier stated per §2.3 (**both** boundary anchors unique in
both streams). And your governance point stands: **the `no-geometry` scoping only resolves the §4/§2.4
contradiction after you formally reconcile the parent plan** — the scaffold cannot self-narrow ratified
authority. That's parent-ruling **#1** in my summary.
=====!

### INV-2 — binds under drift (anti-inertness)  *(INV-1's counterweight)*
- **Property (§4):** "on real re-segmentation / char-sub fixtures the mechanism binds the nodes it should
  (a fail-loud-on-everything mechanism fails this). Scoped as a by-construction existence check, NOT a
  rate over a realistic model — that is S5.2."
- **Oracle:** the identity map — which nodes *should* survive the perturbation and bind.
- **Fixture:** drift generator at moderate perturbation (char-sub + re-segmentation, no moves).
- **Red-first:** a stub that binds nothing (or over-fail-louds) → **RED**. This is the guard against
  "pass INV-1 by never binding." INV-1 ∧ INV-2 together = correct *and* non-inert.
- **Gates:** the mechanism is not inert. (Existence check only — the *rate* is S5.2, not here.)

@@@@@@
**Adversarial audit:** "Nodes it should" and "moderate perturbation" are not executable criteria. List a
small mandatory positive matrix: interior char substitution, atom split with unchanged tokens, atom merge
where ownership remains unambiguous, and boundary edit with an independent confirmation. For each, name
the exact node/span expected to bind. Do not label every non-dropped identity survivor bindable: a surviving
atom can still sit behind an ambiguous boundary or global conflict. The proposed always-empty stub is a
weak red-first target that only proves one happy case; add a mutant that over-abstains specifically on
`replace` or re-segmentation so each advertised drift path has teeth. Resolve the tension with §5.1,
which says boundary char substitution is a measurement instrument, while this section currently implies a
binary bind requirement.
@@@@@@

======
**Conceded.** Replace "nodes it should / moderate" with a mandatory **positive matrix**, each naming the
exact node/span expected to bind: interior char-sub; atom-split-with-unchanged-tokens (R5); atom-merge-
with-unambiguous-ownership; boundary-edit-with-independent-confirmation. Drop the implication that every
non-dropped survivor is bindable — a survivor can sit behind an `ambiguous` boundary or `global-conflict`.
The empty-stub red is weak; add a mutant that **over-abstains specifically on `replace`/re-segmentation**
so each drift path has teeth. §5.1 tension resolved: boundary char-sub is the *measurement* axis (INV-2
**records** the outcome), not a hard bind requirement — will state that split explicitly.
======

@@@@@!
**Second-pass audit:** Merely recording the boundary char-sub outcome no longer satisfies the quoted INV-2
property that the mechanism binds on char-sub fixtures. Split the axis into (a) an interior in-token
substitution with unchanged boundaries that **must bind** and proves anti-inertness, and (b) a boundary
substitution that is diagnostic for the R-b decision. Do not include "boundary edit with independent
confirmation" in the mandatory positive matrix until INV-4 defines a realizable, non-circular confirmation
rule; otherwise INV-2 depends on its unresolved exception.
@@@@@!

=====!
**Accepted — corrects my R13.** My "record the outcome" weakened INV-2's ratified property (it *must*
bind on char-sub). Split the axis: **(a) interior in-token substitution, unchanged boundaries → MUST
bind** (the anti-inertness teeth); **(b) boundary substitution → diagnostic** for the R-b decision. And
**remove "boundary-edit-with-confirmation" from INV-2's mandatory matrix** until INV-4's exception is
shown realizable (block below) — INV-2 must not depend on an unresolved exception.
=====!

### INV-3 — reorder/move fails loud, not silent
- **Property (§4):** "a moved block does not silently mis-project (R-a)."
- **Oracle:** identity map flags moved atoms; expected outcome = a fail-loud finding, never a bind to the
  wrong location.
- **Fixture:** drift generator with a moved block (R-a, the weakest axis).
- **Red-first:** a mechanism that greedily projects the moved node onto a wrong span → **RED** (silent
  mis-projection caught against ground truth). Fail-loud → GREEN.
- **Gates:** R-a honesty.

@@@@@@
**Adversarial audit:** The oracle is stated at atom level but the result is node/slot level. Define which
node boundaries intersect the moved block and the allowed reason(s) for each outcome. Preserve the moved
atom's true destination in provenance (do not map it to ∅). Also decide whether a correct bind to the
planted moved destination is allowed: the ratified property only forbids silent **mis**-projection, whereas
this fixture declares fail-loud to be the only green outcome. If fail-loud is intentionally stricter, say
that this is a scoped policy choice. Exercise both within-container and cross-container moves; the latter
can trigger contiguity/global-conflict logic rather than the intended R-a guard, yielding a misleading red.
@@@@@@

======
**Conceded — three real gaps.** (a) Oracle is atom-level, result is node/slot-level: define which node
boundaries intersect the moved block + allowed reason(s); preserve the moved destination in provenance
(not ∅ — R6). (b) My "fail-loud is the only green" is **stricter than the ratified property** ("no silent
mis-projection" also permits a correct bind to the *true* destination). The diff models a move as
delete+insert (R-a) so this mechanism *cannot* correctly bind it → fail-loud is what it achieves, but I'll
write the invariant as "**fail-loud OR correct-bind-to-planted-destination; never a bind elsewhere**" and
mark the fail-loud-only expectation as a scoped policy choice, not the ratified property. (c) Separate
within- vs cross-container move fixtures so a contiguity/`global-conflict` red doesn't masquerade as R-a.
======

@@@@@!
**Second-pass audit:** Once correct binding is allowed, the invariant title and oracle can no longer say
"reorder/move fails loud." Reconcile that wording in the parent authority as well. For cross-container
moves, define whether preserving the planted atom destination would violate container reading order,
contiguity, or decision topology; a destination-correct atom bind can still be an invalid structure-map
bind and should not automatically count green.
@@@@@!

=====!
**Accepted — two escalations.** (a) My "fail-loud OR correct-bind" changes INV-3's character, so the §4
title/property "reorder/move **fails loud**" must be reconciled in the parent plan — **parent-ruling #2**.
(b) Correct: a destination-correct **atom** bind can still be an invalid **structure-map** bind (violates
container reading-order / contiguity / decision topology). Refine the green condition to **fail-loud OR
(correct planted destination AND a globally-valid structure-map)**, never elsewhere; cross-container moves
get their own fixtures so a contiguity/`global-conflict` red isn't mistaken for an R-a red.
=====!

### INV-4 — boundary-in-edit-block
- **Property (§4):** "a node boundary landing in a `replace/insert/delete` block gets a fail-loud finding
  unless the confidence gate independently confirms it (DR-2)."
- **Oracle:** opcode classification of the boundary token's block (`equal` vs not).
- **Fixture:** drift placing an edit exactly at a node boundary.
- **Red-first:** a mechanism that silently invents a fresh boundary inside a non-`equal` block → **RED**.
- **Gates:** **DR-2.**

@@@@@@
**Adversarial audit — oracle circularity risk:** "Opcode classification" cannot be taken from the same
production aligner used by the mechanism. Plant the edit and classify the old boundary independently.
A boundary is a gap between tokens, not a "boundary token"; an `insert` has an empty old interval, and
block-edge ownership (left block, right block, or both) is undefined here. Specify half-open boundary
mapping for `replace`, `delete`, and insertion exactly at a boundary. The exception "unless the confidence
gate independently confirms it" can swallow the property unless its confirmations and accepted reason
codes are enumerated. Include a negative case where confirmation is absent and a positive case where it is
present, and mutate the boundary rule separately from the confidence gate.
@@@@@@

======
**Conceded.** (a) Opcode classification must **not** come from the production aligner (circularity) —
classify the planted edit with the independent reference model (R8). (b) "boundary token" is wrong — a
boundary is a **gap between tokens**; specify half-open boundary mapping for `replace`/`delete` and
insertion-exactly-at-a-boundary (empty old interval). (c) The "unless the confidence gate confirms"
exception can swallow the property — enumerate the accepted reason codes, include a **negative** (no
confirmation → fail-loud) and a **positive** (confirmation present → bind) case, and mutate the boundary
rule **separately** from the confidence gate so each has its own red.
======

@@@@@!
**Second-pass audit:** Failure reason codes do not describe the positive confirmation case—a bound outcome
has `reason=None`. Specify the actual independent evidence and decision procedure, not just "accepted reason
codes." There is also a feasibility question: DR-3 requires boundary-anchor uniqueness, while INV-4 starts
with a boundary inside a non-equal block. Demonstrate a concrete fixture in which that gate can independently
confirm the projected span; if none exists, the exception is dead specification and should be removed.
@@@@@!

=====!
**Accepted — and I'm elevating the dead-spec finding.** (a) A bound outcome carries `reason=None`, not a
reason code; specify the actual independent-confirmation **evidence + decision procedure**, not "accepted
reason codes." (b) **The dead-spec question is a real finding that reaches a ratified DR.** DR-2's
exception ("boundary in a non-`equal` block *may* be confirmed by the confidence gate") requires DR-3's
boundary-anchor uniqueness — but a boundary landing *inside* an edit block plausibly has **no** unique
anchor there. If no fixture can make the gate confirm such a span, **DR-2's exception is unreachable** and
DR-2 simplifies to "boundary in a non-`equal` block → **always** fail-loud." I lean dead (the exception
reads as defensive) → **demonstrate-or-remove**, and it's **parent-ruling #3** (a DR-2 simplification is
yours). This also unblocks INV-2's dropped matrix row (block above).
=====!

@@@@!!
**Third-pass audit:** "Demonstrate-or-remove" is the right gate, but do not lean dead before the v3 anchor
representation and boundary-projection semantics are fixed. A boundary can lie in a non-equal opcode while
surrounding prefix/suffix context remains unique; whether the stored exact component can match or be refined
is precisely the unresolved design question. Require the positive fixture before retaining the exception,
but treat failure as evidence after implementation/prototype, not as a conclusion from opcode membership
alone. Removing the exception does not "unblock" an INV-2 positive row; it eliminates that row and clarifies
that the case must abstain.
@@@@!!

====!!
**Accepted — and it reclassifies parent-ruling #3, correcting my "I lean remove."** Opcode-membership alone
can't kill the exception: the boundary token sits in a non-`equal` block, but the **prefix/suffix**
components of the prefix+exact+suffix anchor (DR-4) can survive unchanged and unique, and whether the stored
**exact** component can still match or be **refined** is exactly the open #48 design question. So: **require
a positive fixture before *retaining* the exception; treat its absence as post-implementation evidence,
never an a-priori conclusion.** Consequence for the summary: **DR-2 dead-spec is not rulable now** — it
becomes a **deferred-for-information decision** (decide at max clarity, after the v3 anchor rep +
boundary-projection land and a positive fixture is attempted), per [[feedback_deferral_for_information]]. I
withdraw "I lean remove" and drop #3 from the *rule-now* list. Wording fix accepted: removing the exception
**eliminates** the INV-2 matrix row (the case must abstain) — it does not "unblock" it; my "unblocks" was
wrong.
====!!

@@@!!!
**Fourth-pass audit — sequencing remains:** Deferring the exception decision until the v3 representation
and projection "land" conflicts with item 2's mandate to author INV-4 red-first **before** the mechanism
lands. Resolve this by attempting the positive fixture against a bounded prototype/reference anchor design
during item 2, or scope item 2's INV-4 to the unconditional negative and explicitly add the exception branch
as a red-first item-3 test before implementing that branch. Do not let implementation precede the test that
decides whether its exception is reachable.
@@@!!!

===!!!
**Accepted — my "defer until it lands" inverts red-first; adopt your option (b).** Waiting for the v3 rep to
"land" to decide the exception would let implementation precede its test. Disposition: **item-2 INV-4 = the
unconditional negative** (boundary in a non-`equal` block → fail-loud), red-first now, representation-light.
The **exception branch** (DR-2's "unless the gate confirms") gets its **own red-first test authored in item 3
BEFORE that branch is implemented**, against the real anchor; whether a positive fixture can be constructed
there **is** the reachability verdict (reachable → implement+green; unbuildable → DR-2 simplifies to
always-fail-loud). Test precedes implementation. This supersedes block-6's vague "post-prototype defer": #3's
*verdict* is still not rulable now, but its *decision mechanism* is now pinned (the item-3 red-first exception
test). I reject option (a) — a prototype/reference anchor here reintroduces the block-C divergence risk.
===!!!

@@!!!!
**Fifth-pass audit — still violates the ratified checkpoint:** DoD item 2 requires **INV-1…INV-7
red-first**; moving DR-2's exception-branch red to item 3 leaves INV-4 only partially red in item 2. Either
obtain a parent amendment explicitly splitting INV-4, or author the exception test in item 2 against the
ratified minimal anchor/confidence contract and carry it red until item 3 implements it. Avoiding a divergent
prototype is good, but it does not authorize implementation-era test authorship after the mandated
invariant-harness checkpoint.
@@!!!!

==!!!!
**Accepted — my item-3 deferral breaks the ratified item-2 checkpoint.** DoD item 2 requires **INV-1…INV-7
red-first**, so moving DR-2's exception red to item 3 leaves INV-4 only partially red in item 2 — not
authorized by "avoid a divergent prototype." Correct path (your option b): **author the exception test in
item 2, carried RED, against the ratified minimal-anchor/confidence contract, until item 3 implements the
branch** — INV-4 is then fully red-first in item 2, no DoD amendment needed. This **depends on ruling #5**
(the ratified minimal anchor is what the item-2 exception test asserts against). If #5 is **rejected**, the
fallback is your option (a) — a **parent amendment explicitly splitting INV-4** across items 2/3 (a distinct
DoD-change ruling). So block 4's disposition is a **function of #5's outcome**, not an independent ruling.
==!!!!

@!!!!!
**Sixth-pass audit:** If ruling #5 is accepted, carry this test red through the same explicit temporary-red
protocol already established (specific expected assertion/xfail plus manifest), not as an ordinary failing
suite member. Its planted violation must exercise "boundary guard rejects despite independently confirmed
confidence," rather than red merely because the future anchor API is absent; otherwise it proves interface
timing, not the DR-2 exception branch.
@!!!!!

=!!!!!
**Accepted — the carried red must fire on behavior, not on a missing API.** Two disciplines, both adopted:
(1) carry it via the **established temporary-red protocol** (exact expected assertion + `xfail(strict)` +
baseline manifest), the same as INV-6/INV-7 — never a naked failing suite member. (2) The planted violation
is **"boundary guard rejects a span the confidence gate independently confirms"** — a *behavior* red; it must
**not** red merely because the future anchor API is absent (that proves interface timing, not the DR-2
branch). This forces the test to be authored against **#5's ratified minimal-anchor/confidence contract** so
the contract *resolves* (types/interfaces present) while the exception-branch *behavior* is what's
unimplemented → the red isolates the branch. Reinforces the #5 dependency: without the ratified contract, the
only available red is "API absent," which is the wrong red.
=!!!!!

### INV-5 — mode orthogonality
- **Property (§4):** "per-mode gating matches the S5.1 mode fixtures."
- **Oracle:** the existing S5.1 mode fixtures/contracts (`geometry-primary` / `geometry-tie-break` /
  `no-geometry`).
- **Fixture:** reuse S5.1's mode fixtures (no new fixture; DR-5 continuity).
- **Red-first:** a mechanism that ignores mode (e.g. geometry rescues a sub-τ span) → **RED** against the
  S5.1 contract.
- **Gates:** **DR-5** (contract preservation).

@@@@@@
**Adversarial audit:** There do not appear to be reusable on-disk "mode fixtures"; the current contracts
are spread across builders/tests in `tests/unit/test_rebind.py`. Name the exact tests/helpers or create a
shared fixture deliberately. More importantly, "ignores mode" covers too little. Pin the full behavioral
matrix: primary page pin, tie-break-only disambiguation, no-geometry ignoring region, no geometry rescue
below τ, threshold ordering, unknown/unruled mode provenance, reason enum, and re-stamp/non-raising
continuity where affected by the rewrite. Reusing implementation-shaped fixtures without restating expected
behavior risks preserving old DP assumptions instead of the S5.1 contract. Each mode branch needs a
targeted red mutant; one geometry-rescue example does not prove orthogonality.
@@@@@@

======
**Conceded — code-verified.** There are no reusable on-disk "mode fixtures"; the contracts are **inline
in `tests/unit/test_rebind.py`** (the `MODE_PRIMARY/TIE_BREAK/NO_GEOMETRY` cases, ~354–451). "reuse S5.1's
mode fixtures" is inaccurate. Will name those exact tests/helpers **and** — your stronger point — restate
expected behavior per mode rather than reusing implementation-shaped fixtures (which would preserve DP
assumptions). Pin the full matrix, each with a targeted red mutant: primary page-pin, tie-break-only
disambiguation, no-geometry region-ignore, **no sub-τ geometry rescue**, threshold ordering,
unruled/unknown-mode provenance, reason enum, re-stamp/non-raising continuity.
======

@@@@@!
**Second-pass audit:** Separate mode orthogonality from general DR-5 regression coverage. Reason-enum
closure, non-raising behavior, and re-stamping are important but are not per-mode properties; forcing a
targeted mutant for every item under INV-5 overloads the invariant and obscures failures. Also ensure new
fixtures assert the planned projected-span geometry semantics, not the current DP's window-pin mechanics.
@@@@@!

=====!
**Accepted — corrects my R16 over-load.** INV-5 = **pure mode orthogonality** (the three modes' gating:
primary page-pin, tie-break-only disambiguation, no-geometry region-ignore, no sub-τ geometry rescue,
threshold ordering). Reason-enum closure, non-raising, and re-stamp are **not per-mode** — they move to a
separate **DR-5 regression suite**. New fixtures assert the **planned projected-span** semantics, not the
current DP's window-pin mechanics.
=====!

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

@@@@@@
**Adversarial audit — acceptance is not specified:** `10^4→10^5` is one decade, not "≥2 decades."
Name at least three sizes spanning 100× (for example 10³, 10⁴, 10⁵), what K does as N grows, the
ratio formula, numeric time/memory ceilings, repetitions, warm-up, statistic, and machine-variance policy.
A generic "sub-quadratic" endpoint ceiling is easy to game with fixed overhead. Time serialize, load,
index, and rebind both separately and end-to-end so a regression cannot hide behind another phase.
`tracemalloc` does not account for all native allocations (material for RapidFuzz); pair it with process
RSS or explicitly limit the claim to Python-managed memory. Running the cubic implementation across two
full decades is likely infeasible, so item 2 needs smaller calibrated red sizes distinct from item 4's
production sizes. The anchor-poor correctness curve belongs to item 4 per §3/§5.2; here only its minimal
red sentinel should be required. Finally, "the current implementation is the planted violation" gives no
way for this invariant test to coexist green before the rewrite—document the red artifact/workflow rather
than committing an ordinary permanently failing test.
@@@@@@

======
**Conceded across the board.** (a) 10⁴→10⁵ is **one** decade — will name ≥3 sizes spanning 100×
(10³/10⁴/10⁵) and state what K does as N grows. (b) ratio formula, ceilings, reps, warm-up, statistic,
variance policy pinned **at build from the measured baseline** — I'll push one form here: the ceiling is
`baseline × margin`, *derived*, not a guessed constant (a made-up number now would be arbitrary). (c)
endpoint-only "sub-quadratic" is gameable with fixed overhead → time serialize/load/index/rebind
**separately and** end-to-end. (d) `tracemalloc` misses native RapidFuzz allocations — correct; pair with
process RSS or scope the claim to Python-managed memory. (e) cubic across two full decades is infeasible →
item 2 uses smaller **calibrated red sizes**; the anchor-poor curve is item 4, only its minimal sentinel
here. (f) permanently-red → the artifact workflow in R23 (xfail-to-baseline, not a live red test).
======

@@@@@!
**Second-pass audit — blocking performance flaw:** A ceiling derived as `baseline × margin` from the
known cubic implementation institutionalizes the defect and does not test sub-quadratic growth. Use an
independent growth rule (per-adjacent-size ratios or fitted log-log slope with a pre-registered tolerance)
and a separately justified absolute resource budget. The old baseline is evidence that the test turns red,
not the authority for what counts acceptable. `xfail` can also hide setup errors or the wrong failure;
assert fixture construction and phase completion first, and ensure only the specific budget assertion is
expected to fail. RSS measurement must occur in a fresh child process with a defined platform unit/delta,
or peak history will contaminate results.
@@@@@!

=====!
**Accepted — I was wrong in round 1.** My `baseline × margin` is refuted: it derives the sub-quadratic bar
from the cubic defect → institutionalizes it. Correct: an **independent growth-rate test** (fitted log-log
slope, or per-adjacent-size ratios, with a **pre-registered tolerance**) that never references the cubic
baseline, **plus** a separately-justified **absolute** resource budget. The old baseline evidences only the
RED, not the acceptance authority. Also: assert fixture construction + phase completion **before** the
budget assertion (so `xfail` can't mask a setup error); RSS in a **fresh child process** with a defined
unit/delta.
=====!

@@@@!!
**Third-pass audit:** This still postpones the enforceable numbers. Before running the red baseline, pin the
chosen growth estimator, numeric tolerance/upper bound, repetition statistic, and target hardware profile;
otherwise the observed cubic result can influence the bar. With only three sizes, a fitted slope is fragile,
so retain adjacent-ratio checks or confidence bounds as a guard. The absolute budget also needs an authority
(CLI latency/memory requirement or named machine envelope), not merely the phrase "separately justified."
@@@@!!

====!!
**Accepted — pre-registration is the anti-cheating discipline, applied to the bar itself.** Before the red
baseline runs, pin and commit: the **growth estimator** (fitted log-log slope), the **numeric
tolerance/upper bound**, the **repetition statistic** (median-of-k, k stated), and the **target hardware
profile** — so the observed cubic cannot retro-set the bar. Belt-and-suspenders on 3 sizes: **keep
per-adjacent-ratio checks (and/or confidence bounds) alongside** the slope, since a 3-point fit is fragile.
**One honest gap I won't paper over (now verified):** the *absolute* budget needs a real **authority**, and
**no ratified absolute number exists** — `s4_7_plan.md §2` and the DoD-A-7 tracker row name a "wall-clock +
peak-memory ceiling incl. serialize/load/index," but only in the **growth-rate (sub-quadratic)** sense,
never an absolute latency/memory figure with a product/machine authority. So the disposition is: name the
**machine envelope** + source a **product latency/memory target** — or record that none exists and the
absolute budget is **provisional-pending-that-target** — not invent a number and call it "separately
justified." Sourcing that target is a small open item for the summary, not something item 2 can
self-authorize.
====!!

@@@!!!
**Fourth-pass audit:** Replace "pin and commit" with "pin in the review artifact and obtain the required
ratification before the red run"; committing remains separately authorized. Since no absolute product
budget exists, do not let sourcing one block the already-ratified **growth** red. Treat the growth criterion
as item 2's enforceable INV-6 surface and elevate the missing absolute ceiling as an explicit parent decision
for item 4, unless the parent authority is amended now with a sourced machine/product target.
@@@!!!

===!!!
**Accepted — two fixes.** (1) "pin and commit" → **"pin in the review artifact + obtain ratification before
the red run; committing separately authorized"** — my "commit" overstepped commit-only-when-you-ask. (2) The
**absolute ceiling was never ratified — it was my round-1 addition**; §4 INV-6 ratifies only the sub-quadratic
*growth* + 10⁵ scale. So the **growth red is item-2's enforceable INV-6 surface now** and must **not** block on
a sourced absolute number; the missing absolute ceiling is **elevated as an explicit item-4 parent decision**
(source a machine/product target then, or drop it), unless you amend the parent authority now. Removes it from
item 2's critical path entirely.
===!!!

@@!!!!
**Fifth-pass audit — authority correction:** An absolute **number** is absent, but an absolute-resource
ceiling is not merely a Claude addition: the authoritative tracker S4.7 row requires a "rough wall-clock +
peak-memory ceiling" including serialize/load/index. Item 2 may gate only the ratified growth red under the
item-2/item-4 split, but item 4 cannot simply "drop" the ceiling without a parent amendment. Record: numeric
budget unresolved; ceiling requirement ratified; owner must source or rule it before item 4.
@@!!!!

==!!!!
**Accepted — verified; my round-4 "never ratified" was a factual authority error.** `ENGINE_STRUCTURE_TASKS.md:566`
(the S4.7 row, DR-7) ratifies exactly your quote: "budget is a **rough wall-clock + peak-memory ceiling that
includes serialize + load + index-build**." So the **ceiling requirement is ratified**; only the **number** is
absent — I conflated the two. Correct record (tri-state): **numeric budget unresolved / ceiling requirement
ratified / owner must source-or-rule it before item 4.** Item 2 still gates only the sub-quadratic **growth**
red (the item-2/item-4 split holds), but **item 4 cannot "drop" the ceiling** — dropping it needs a parent
amendment. I retract "it was my round-1 addition": the absolute-ceiling *requirement* predates me; my round-1
addition was only an attempt to attach a *number* to it.
==!!!!

### INV-7 — evidence composite
- **Property (§4):** "measured on a deep map at scale; over budget → algorithm fixed or scoped follow-up;
  ceiling not moved."
- **Oracle:** the budget ceiling on `evidence_findings`/`_restamp` over a deep chain.
- **Fixture:** a deep synthetic chain (PLL is shallow, depth 4 — this is a synthetic worst case; state so).
- **Red-first:** the O(N²) deep-chain on a deep fixture → **RED** against budget. Per **DR-6
  (characterize-and-defer):** the RED is characterized; either fixed (Merkle/rolling subtree digests) or
  a scoped follow-up is opened — **never relax the ceiling** ([[feedback_no_cheating_results]]).
- **Gates:** **DR-6.**

@@@@@@
**Adversarial audit — unresolved contradiction:** DR-6 is ruled **characterize-and-defer**, but this point
says "either fixed" and calls the current O(N²) behavior a red invariant. If the ceiling cannot move and the
algorithm is deferred, what makes INV-7 green and lets the suite pass in DoD item 3? An `xfail`, skip, or
assertion that only writes a follow-up would not prove the stated invariant. Define the state machine:
numeric ceiling fixed in advance; measured result; either an in-scope fix makes the assertion green, or a
specific follow-up artifact is the accepted deliverable and INV-7 is honestly recorded as unresolved (not
green). Also set the deep-chain size and establish that construction, schema validation, serialization,
and recursion limits do not fail before the measured operation. A 10⁵-deep Python tree may measure stack
failure rather than O(N²) evidence cost. The current plan provides no budget number, so "ceiling not moved"
is presently unenforceable.
@@@@@@

======
**Conceded — a genuine unresolved contradiction.** DR-6 = characterize-and-defer + ceiling-not-moved, so
INV-7 **cannot be "green"** while deferred. State machine: (1) numeric ceiling fixed in advance (from the
measured baseline); (2) measure; (3) either an in-scope fix greens the assertion, **or** a named
follow-up artifact is the accepted deliverable and **INV-7 is honestly recorded UNRESOLVED, not green** —
an `xfail(strict=True, reason=<follow-up issue>)`, never a silent skip. Consequently **DoD item 3's
"suite green" must explicitly annotate INV-7's deferred state** (I'll flag that back to plan §8). Also:
bound the deep-chain depth and prove construction/schema-validation/serialize/recursion-limit don't fail
before the measured op — a 10⁵-deep Python tree may measure stack failure, not O(N²).
======

@@@@@!
**Second-pass audit — governance still required:** `xfail(strict=True)` treats any failure in the test as
the expected failure unless the test isolates and validates the exact budget assertion; it is not an
honest unresolved-state model by itself. More fundamentally, the ratified DoD says INV-1…INV-7 red-first
and item 3 says suite green. Changing that to "INV-7 unresolved but accepted" requires a new user ruling,
not a scaffold annotation. A numeric ceiling derived from the failing O(N²) baseline also violates
"ceiling not moved" for the same reason as INV-6. Pre-register an independent ceiling or explicitly record
that no invariant has yet been established.
@@@@@!

=====!
**Accepted — escalates to a required ruling.** (a) `xfail(strict)` treats *any* failure as expected → not
an honest unresolved model unless the test isolates the exact budget assertion. (b) The baseline-derived
ceiling is the same INV-6 circularity → pre-register an **independent** ceiling. (c) **The governance
point is decisive: DoD item 2 says INV-1…7 red-first and item 3 says "suite green." Recording INV-7 as
"accepted-unresolved" is a change to the ratified DoD — your ruling, not a scaffold annotation.** So INV-7
**cannot be finalized without parent-ruling #4**: either an in-scope fix greens it, or you accept it as a
deferred deliverable. I'll stop labeling it "green."
=====!

---

## §3 Build order + dependencies

1. **Component 0 — drift generator + identity map** (blocks INV-1/2/3/4). Build first.

@@@@@@
**Adversarial audit:** Replace "identity map" with the provenance relation described above and split the
generator into (a) mutation/provenance and (b) fixture materialization. That separation lets the oracle
remain independent from anchor/fingerprint construction. Add direct generator self-tests before any
invariant consumes it: relation cardinalities for split/merge/duplicate, moved destination preserved,
insert/delete null sides, deterministic seed replay, and no accidental source-id reuse.
@@@@@@

======
**Conceded — adopt in full.** Replace "identity map" with the provenance relation (R6); split the
generator into **(a) mutation/provenance** and **(b) fixture materialization**, so the oracle stays
independent of anchor/fingerprint construction. The listed self-tests become gating prerequisites before
any invariant consumes the generator.
======
2. **INV-1 + INV-2 together** — the correct/non-inert pair; INV-1 is the DR-3 keystone.

@@@@@@
**Adversarial audit:** Correct dependency, but "together" should mean the same seeded corpus/configuration
where possible; otherwise INV-1 can be tested only on hostile cases and INV-2 only on easy cases, leaving a
coverage gap between them. Report bound-correct, abstained, and wrong for each generated case even though
item 2 gates on properties rather than calibrated rates.
@@@@@@

======
**Conceded.** INV-1 ∧ INV-2 run on the **same seeded corpus/config** (else INV-1 sees only hostile cases,
INV-2 only easy ones — a coverage gap in between). Emit a per-case **diagnostic** breakdown
(bound-correct / abstained / wrong) — reported, not a gated rate (that stays S5.2's).
======
3. **INV-3, INV-4** — drift-honesty + boundary discipline.

@@@@@@
**Adversarial audit:** Add the missing global-disjointness/collision case exposed by merge/duplication. It
may be covered by INV-1, but the build order should name it explicitly because the shipped S5.1 audit
already found silent double-claim behavior and the new atom back-pointer projection can reintroduce it.
@@@@@@

======
**Conceded — strong catch.** The merge/duplication **global-conflict (double-claim)** case is named
explicitly in the build order. Open question back to you: fold it into INV-1's disjointness, or make it a
dedicated **INV-8** (a small amendment to the ratified §4 list)? Given the shipped S5.1 audit *already*
caught a silent double-bind and the back-pointer projection is a fresh re-introduction risk, I lean
INV-8 — the `global-conflict` reason code deserves its own red rather than riding inside INV-1. Your call.
======

@@@@@!
**Second-pass audit — recommendation:** Keep the ratified seven invariants and make global disjointness a
named, red-first INV-1 subcase/test. A new INV-8 adds governance and DoD scope without adding protection;
INV-1's `bound ⊆ allowed pairs` already forbids a doubly claimed fresh atom when the oracle is slot-aware.
Pin the `global-conflict` reason in a focused regression test alongside it. Amend the ratified list only if
the property genuinely cannot be expressed under INV-1.
@@@@@!

=====!
**Accepted — you've answered my open question; dropping INV-8.** Slot-aware `bound ⊆ allowed pairs`
already forbids a doubly-claimed fresh atom, so global-disjointness is a **named red-first INV-1 subcase**
+ a focused `global-conflict`-reason regression — **no ratified-list amendment**. Keeps the seven and
adds no DoD scope. My INV-8 lean is withdrawn.
=====!

@@@@!!
**Third-pass audit — correction to the prior recommendation:** Slot-wise membership in allowed pairs does
**not** by itself forbid double-claim under many-to-one provenance. If two old slots' atoms are merged into
one fresh atom, both `(slot, fresh-id)` pairs can be individually provenance-allowed while the two binds are
globally incompatible. Keep this as an INV-1 subcase, but make the oracle assert both pairwise correctness
**and global composability/disjoint ownership**; the focused `global-conflict` regression is essential, not
merely a reason-code pin.
@@@@!!

====!!
**Accepted — you're correcting your own second-pass, and it's right.** Slot-wise `bound ⊆ allowed pairs`
does **not** forbid double-claim under **many-to-one**: two old slots' atoms merged into one fresh atom
yield two individually-provenance-allowed `(slot, fresh-id)` pairs that are **globally incompatible**. So
INV-1's oracle carries **two conjuncts**: (i) *pairwise* — every bind ∈ allowed pairs; (ii) *global* —
bound fresh-atom ownership is **disjoint** (no fresh atom claimed by >1 `(node, slot)`). Conjunct (ii) is
grounded, not invented: the shipped **non-overlapping-coverage** contract (S1.4 round-trip gate +
`UNOWNED_INCLUDED_ATOM`/coverage in `test_structure_projection.py`) already makes included-atom ownership a
partition. Kept as an **INV-1 subcase** (no INV-8, per your prior call), but the subcase asserts global
composability, and the focused **`global-conflict` regression is essential**, not a reason-code pin. And it
reds against the **actual shipped S5.1 double-claim defect** — a historical bug is a stronger red-first
target than a synthetic one.
====!!

@@@!!!
**Fourth-pass audit — historical wording correction:** The silent double-claim defect is not present in the
current shipped code; it was caught and fixed during the S5.1 audit, and `hunt_rebind.py` now recreates it by
mutating `_contested_nodes`. Therefore the item-2 red target is the **existing named mutant/historical
regression**, not an "actual shipped defect" in the current baseline. Record the fixing commit or mutant
definition so the historical claim is reproducible.
@@@!!!

===!!!
**Accepted — verified; "actual shipped defect" was wrong (my second factual slip this round).** The guard
**is** in shipped code — `_contested_nodes` (`rebind.py:871`, def `:919`), the S5.1-audit fix. The red target
is the **existing named mutant** `bound-subset-disjointness-disabled` (`hunt_rebind.py:108`: "neuters the
contested-atom witness [so] two bound nodes share a fresh atom"), scoped to the **existing test**
`test_partial_rebind_never_silently_double_claims_a_fresh_atom`. So it's a **historical regression reproduced
by a named mutant**, not a live defect. Better: INV-1's global-disjointness subcase **extends that existing
test+mutant** into the drift/many-to-one-merge setting rather than inventing one. Reproducible record =
mutant label + `_contested_nodes` guard + the named test (the fixing commit is one `git blame rebind.py` away
if you want it pinned in rev 2).
===!!!
4. **INV-5** — mode contracts (reuse S5.1 fixtures).

@@@@@@
**Adversarial audit:** Run this before declaring INV-1 green if INV-1 permits geometry disambiguation;
otherwise a broken mode branch can masquerade as a uniqueness failure. At minimum, state the mode under
which INV-1/2/3/4 execute.
@@@@@@

======
**Conceded — ties to R12.** Resolution: run **INV-1/2/3/4 in `no-geometry`** so mode is out of their loop
(and INV-1's "non-unique → ambiguous" absolute holds); INV-5 then independently covers all three modes.
Will state the execution mode explicitly at the top of §2. This dissolves the masquerade risk without
reordering.
======

@@@@@!
**Second-pass audit:** Running every drift invariant only in `no-geometry` creates a mode×drift blind spot:
primary/tie-break geometry could rescue a wrong repeated-passage projection or alter boundary/move
outcomes, while INV-5's isolated mode fixtures still pass. Use `no-geometry` as the base mode to make the
core properties unambiguous, then add a small targeted interaction matrix for repeated content, boundary
edits, and moves under primary/tie-break. INV-5 alone does not prove those cross-effects safe.
@@@@@!

=====!
**Accepted — a real coverage gap in my "no-geometry only."** Use `no-geometry` as the **base** mode (keeps
INV-1…4's core properties unambiguous), **plus** a small targeted **mode×drift interaction matrix**:
repeated-content, boundary-edit, and move cases run under `primary`/`tie-break` to catch a geometry rescue
of a wrong projection. INV-5's isolated mode fixtures don't prove those cross-effects. Modest added scope,
justified.
=====!
5. **INV-6, INV-7** — scale/evidence. **[§5.2 RULED 2026-07-09] Write the RED tests HERE (item 2), against
   the shipped cubic mechanisms, BEFORE half-B lands.** The real O(K·N³) `_Assignment` (INV-6) and the O(N²)
   deep-chain (INV-7) *are* the planted violations — the honest red-first. **This is a now-or-never window:**
   `#48` deletes `_Assignment`, after which INV-6/7 could only red against a contrived slow-mutant. Item 2
   therefore builds the **minimal** scale scaffolding (size-parameterized fixture + `perf_counter` /
   `tracemalloc` wrapper) needed to see those reds; **item 4 productionizes it** (CI tiers, 10⁵ nightly, the
   full anchor-poor sweep) — item 4 is *not* "build from zero." The DoD split is pinned in `s4_7_plan.md` §8
   so the two items don't double-count.

@@@@@@
**Adversarial audit:** The now-or-never rationale applies to capturing a reproducible baseline, not
necessarily to retaining production tests coupled to private symbols `_Assignment` and `_restamp_evidence`.
Store the red command, sizes, result, and commit/implementation identity in an artifact; make the lasting
invariants target public named operations so deletion of the old implementation does not delete the test's
meaning. Clarify whether item 2 is expected to finish with known failing tests and how item 3 selects them;
ordinary suite collection cannot be both red by design here and green at the item-3 checkpoint without an
explicit workflow.
@@@@@@

======
**Conceded — and it improves my §5.2 ruling.** The now-or-never applies to capturing a **reproducible
baseline artifact** (command, sizes, result, commit/impl id), **not** to keeping live tests coupled to
private `_Assignment`/`_restamp_evidence`. The durable INV-6/7 tests target **public named ops**
(`rebind()`, the evidence op) so deleting the old impl doesn't delete the test's meaning. Item 2 finishes
with: the baseline artifact + `xfail`-marked durable tests; item 3 flips them green. I'll rewrite §5.2/§3
item 5 accordingly — a real improvement over "write the red against `_Assignment`."
======

@@@@@!
**Second-pass audit:** This contradicts the INV-7 response immediately above: item 3 cannot "flip" both
tests green if INV-7 remains deliberately unresolved under DR-6. State separate lifecycles for INV-6 and
INV-7. Also name the public evidence operation precisely (`evidence_findings` and/or the public `rebind`
path that invokes re-stamping); "the evidence op" is not a stable callable contract. An xfail-marked test
is acceptable only as a temporary red record with the exact-failure safeguards above, not evidence that
the invariant is satisfied.
@@@@@!

=====!
**Accepted — separate lifecycles.** **INV-6** flips green at item 3 (half-B makes the op sub-quadratic).
**INV-7** does **not** flip — it stays deferred under DR-6 pending parent-ruling #4. Name the public op
precisely: `evidence_findings` and/or the public `rebind` path that invokes re-stamping — not "the
evidence op." `xfail` is a temporary red **record** with the exact-failure safeguards, never evidence the
invariant holds.
=====!

Mutation hunt at green; **wide+narrow adversarial audit + Rule-A delta re-audit before commit** (§4 +
[[feedback_adversarial_audit_cadence]]). **INV-1 + INV-2 + INV-3 are the audit's primary target** (correct,
non-inert, drift-honest).

@@@@@@
**Adversarial audit:** Add generator/oracle code and the performance harness themselves to the primary
audit target. They are more likely than the mechanism to create a false green. "Rule-A delta re-audit" and
"wide+narrow" should point to executable checklists or commands rather than wiki labels alone.
@@@@@@

======
**Conceded.** The generator/oracle/perf-harness join the **primary** audit target — they're likelier
than the mechanism to manufacture a false green. "Rule-A / wide+narrow" get concrete executable checklists
+ commands in §4, not bare `[[...]]` labels.
======

---

## §4 Anti-cheating guards (baked into the harness from line 1)

- Every invariant **seen RED** before green — planted violation or mutation; a never-red test is a claim.
- Oracles are **ground-truth-by-construction** (identity map / planted positions), never `rebind()`'s output.
- **pyc staleness:** the mutation cycle purges `__pycache__` / sets `PYTHONDONTWRITEBYTECODE=1` — a stale
  `.pyc` serving pre-mutation bytecode is a false GREEN ([[feedback_mutation_pyc_staleness]]).
- **`pytest.raises(match=)`** matches the raise's wording, never the feature word or `tmp_path`
  ([[feedback_pytest_match_leak]]).
- **No `skipif`-masking;** assert referents actually resolve/import ([[feedback_validate_bindings]]).

@@@@@@
**Adversarial audit:** These guards miss the largest randomized-test risks: fixed/reported seeds, shrinking
or minimal counterexample retention, a minimum case count per operation/composition, and failure replay.
For mutation hunts, purging `__pycache__` is not enough if the module stays loaded in the same interpreter;
require a fresh subprocess per mutant, verify the mutated source is the file imported, and restore it in a
`finally`-equivalent path. `PYTHONDONTWRITEBYTECODE=1` prevents writing but does not itself prove that no
pre-existing bytecode/module cache was used. Also protect a dirty worktree: mutation tooling must refuse or
preserve pre-existing user edits. The `pytest.raises(match=)` rule is generic boilerplate unless a listed
invariant actually asserts a raise; identify its concrete application or omit it from this scaffold.
@@@@@@

======
**Conceded, mostly.** Add: fixed/reported seeds, **shrink/minimal-counterexample retention**, min case
count per op/composition, failure replay. Mutation: **fresh subprocess per mutant** — you're right that
in-process `__pycache__` purge is insufficient while the module stays loaded; [[feedback_mutation_pyc_staleness]]
covered only the pyc half, subprocess is the robust fix — plus verify the mutated source is the file
imported, restore in a `finally`-path, and **refuse a dirty worktree**. On `pytest.raises(match=)`: it
*does* apply — INV-3/INV-4 fail-loud paths raise/emit findings — so I'll bind it to those, not leave it
generic.
======

@@@@@!
**Second-pass audit — factual correction:** `rebind()` is explicitly non-raising; INV-3/INV-4 normally
assert typed findings in its returned report. Only the separate strict `assert_all_bound()` path raises
`RebindError`. Do not conflate "raise/emit": bind `pytest.raises(match=...)` only to a named strict-path
test, while the invariant itself should assert the closed reason and affected node/slot directly. Prefer
mutating an isolated copy to refusing all dirty worktrees, since this review workflow intentionally leaves
the plan modified.
@@@@@!

=====!
**Accepted — code-verified, corrects my R25.** `rebind()` is non-raising (returns `RebindReport` with
typed findings); only `assert_all_bound()` raises `RebindError`. So INV-3/INV-4 assert the **closed reason
+ affected node/slot on the returned report**; `pytest.raises(match=…)` binds **only** to a dedicated
strict-`assert_all_bound` test — not to the invariants. And on hygiene: **mutate an isolated copy** rather
than refuse-dirty-worktree — this very review workflow leaves the worktree modified, so refuse-dirty would
block it.
=====!

---

## §5 Sub-decisions — all RULED (Ben, 2026-07-09)

1. **R-b token granularity [RULED]:** **default tolerate-via-ratio; do not pre-build char-level.** Add a
   *boundary char-sub axis* to INV-1/INV-2 (a char sub landing on a boundary token) as the measurement
   instrument. Escalate to a **coarse-to-fine hybrid** (token alignment + char-level refinement *only* at
   boundaries landing in `replace` blocks) **iff** the measured INV-2 fail-loud rate on trivial in-token
   drift is unacceptable. Deferral-for-information (the invariant fixture *is* the decision instrument),
   not effort-saving; avoids a ~5–6× N blow-up on spec.

@@@@@@
**Adversarial audit:** "Unacceptable" is an unruly threshold and contradicts the otherwise careful
S4.7/S5.2 ownership split. Pre-register the item-2 observation that would trigger coarse-to-fine (for
example failure of a named by-construction existence case), without turning it into a calibrated rate.
The asserted 5–6× blow-up needs a source or should be labeled an estimate. Also specify which aligner
variant (Indel vs Levenshtein) the measurement compares, since DR-1 explicitly defers that choice to R-b.
@@@@@@

======
**Conceded.** "Unacceptable" → a **pre-registered by-construction existence trigger**: e.g. "INV-2's
atom-split-unchanged-token case fails to bind under token-level alignment" — a property, not a calibrated
rate. The 5–6× is an **estimate** (char/token count ratio for Italian prose) — will label it so. And name
the aligner the measurement compares: **Indel vs Levenshtein** — DR-1 defers exactly this to the R-b
measurement, so the R-b fixture *is* where that sub-choice resolves.
======

@@@@@!
**Second-pass audit — proposed trigger is irrelevant:** An atom split at an unchanged token boundary
produces the same token sequence, so char-level refinement cannot fix its failure; that case tests
token→atom back-pointer projection, not R-b granularity. The trigger must be a planted in-token character
substitution at/near a node boundary for which the provenance oracle permits one bind and token-level
projection abstains. Compare Indel/Levenshtein first, then invoke coarse-to-fine only if both fail the named
existence case.
@@@@@!

=====!
**Accepted — corrects my R26; wrong trigger.** The atom-split-unchanged-token case produces identical
tokens, so char-level refinement can't fix it — that's an **INV-2 back-pointer** test, **not** an R-b
granularity test. The R-b trigger is a **planted in-token char-sub at/near a node boundary** where the
provenance oracle permits exactly one bind but token-level projection abstains. And the sequence is:
**compare Indel vs Levenshtein first**, invoke coarse-to-fine **only if both** fail that named existence
case.
=====!

@@@@!!
**Third-pass audit:** Provenance can identify exactly one correct destination, but it cannot by itself say
that auto-bind is permitted. The trigger fixture must additionally pre-establish above-τ content,
unique-in-both boundary context under the intended refined representation, and global validity. Otherwise
token-level abstention may be the correct confidence result rather than evidence that character refinement
is required.
@@@@!!

====!!
**Accepted — same discipline as INV-4: don't blame the mechanism when abstention is correct.** Provenance
fixes the one correct *destination* but does not establish that auto-bind is *permitted*. So the R-b trigger
fixture must **pre-establish, independently, that the refined representation WOULD bind**: content ≥ τ,
boundary context **unique-in-both under the refined (char-level) representation**, and global validity —
**and** that token-level projection nonetheless abstains. Only that isolates **granularity** as the sole
cause and proves char-refinement is *needed*; without those preconditions, token-level abstention may be the
*correct* confidence result and the fixture would falsely indict granularity. Pin the fuller precondition on
the trigger.
====!!

@@@!!!
**Fourth-pass audit:** State how the refined preconditions are established without pre-building the very
coarse-to-fine mechanism the decision is meant to justify. A small independent char-level reference oracle
is appropriate here, but it must remain test-only and bounded; production refinement is built only after the
trigger fires. Otherwise "the refined representation would bind" becomes either circular or hidden scope
creep.
@@@!!!

===!!!
**Accepted — the "refined would bind" precondition must not smuggle in the mechanism it justifies.** Establish
it with a **small, test-only, bounded independent char-level reference oracle** — never by pre-building
production coarse-to-fine (which is built **only after** the trigger fires). If the reference oracle says a
char-level view binds (τ met, unique-in-both under refinement, global-valid) **and** token-level abstains,
granularity is isolated as the cause → *then* production refinement is justified. Same discipline as the
brute-force alignment reference (block D): the oracle proves *feasibility*, it is not the production path.
Otherwise "refined would bind" is circular or hidden scope creep, exactly as you say.
===!!!
2. **INV-6/INV-7 ↔ item-4 overlap [RULED]:** write the red scale/evidence tests **here (item 2), against
   the shipped cubic mechanisms, before half-B lands** (now-or-never — `#48` deletes `_Assignment`). Item 2
   builds the *minimal* harness to see those reds; **item 4 productionizes** (CI tiers, 10⁵ nightly, full
   sweep). DoD wording split in `s4_7_plan.md` §8 so the items don't double-count. (See §3 item 5.)

@@@@@@
**Adversarial audit:** Define "minimal" by outputs: parameterized constructor, phase-separated timer,
memory sampler, deterministic red sizes, and a saved result artifact. Do not implement the six-point sweep
or nightly wiring here. INV-7 still needs the characterize/defer resolution described above; repeating the
ruling does not resolve how its red test eventually passes.
@@@@@@

======
**Conceded.** "Minimal" defined by **outputs**: parameterized constructor, phase-separated timer, memory
sampler, deterministic red sizes, saved result artifact — no six-point sweep, no nightly wiring. INV-7's
green-state is the R18 state machine (xfail-to-follow-up, honestly unresolved) — cross-referenced, not
re-asserted.
======

@@@@@!
**Second-pass audit:** "Green-state" and "honestly unresolved" are mutually exclusive, and `R18` is not a
resolvable reference. Call this an accepted deferred deliverable only after the required governance ruling;
do not label it green. The minimal memory sampler must also state whether item 2 measures Python allocations
or child-process RSS so item 4 does not have to replace its interface.
@@@@@!

=====!
**Accepted.** "Green" is dropped for INV-7 — it's an **accepted-deferred deliverable only after
parent-ruling #4**, not green now; and the `R18` shorthand becomes a stable ledger id (block 3). The
memory sampler's interface is fixed in item 2 — **child-process RSS** (per the native-allocation point, so
`tracemalloc` alone won't do) — so item 4 inherits rather than replaces it.
=====!

@@@@!!
**Third-pass audit:** Child-process RSS gives an end-to-end peak but does not automatically support the
promised phase-separated memory measurements: RSS is a high-water mark and cannot be reset between
serialize/load/index/rebind phases. Specify one fresh child per measured phase plus one end-to-end child (or
limit phase separation to timing). Normalize platform units and subtract/report the interpreter baseline;
otherwise item 4 still has to redesign the sampler.
@@@@!!

====!!
**Accepted — RSS is a high-water mark; my "child-process RSS" answer didn't survive phase decomposition.**
Item-2 minimal disposition (your "limit phase separation to timing" option): **phase-separate *timing***
(`perf_counter` around serialize/load/index/rebind in one process — timing composes intra-process), and
**measure memory end-to-end only** — one fresh child, **peak RSS minus a measured interpreter baseline,
normalized to bytes**. Per-phase *memory* (one fresh child per phase) is the item-4 extension. To honor
"item 4 inherits, not redesigns," fix the sampler **interface** now as
`measure(phase_callable) -> (wall_ns, peak_rss_delta_bytes)` running its callable in a fresh child over the
baselined RSS — item 4 plugs one phase-callable per child without touching the interface. Item 2 calls it
once (whole chain); item 4 calls it per phase.
====!!

@@@!!!
**Fourth-pass audit:** A raw `phase_callable` is a fragile subprocess interface: closures and fixture state
may not be pickleable, and fork-vs-spawn behavior can change results. Prefer a serializable phase descriptor
or command plus persisted fixture path and explicit setup boundary. Define whether fixture construction is
inside the end-to-end memory span; D35 requires serialize+load+index, but synthetic fixture generation
should not silently inflate that peak. Also pin the OS-specific RSS source and unit conversion rather than
assuming every platform reports the same units.
@@@!!!

===!!!
**Accepted — the raw-callable interface is fragile; three fixes.** (1) Replace `phase_callable` with a
**serializable phase descriptor** (phase-id + **persisted fixture path** + explicit setup boundary) — a live
closure/fixture may not pickle under **spawn**, and **fork-vs-spawn** shifts the memory baseline; pin
**spawn** and pass a descriptor, not a callable. (2) **Exclude fixture *generation* from the measured span** —
D35 requires serialize+load+index *inside* the span, but synthetic generation sits *outside* (the child
**loads a persisted fixture**, then the span starts), else generation silently inflates the peak. (3) Pin the
**OS-specific RSS source + unit conversion** — notably `resource.getrusage` `ru_maxrss` is **KB on Linux,
bytes on macOS/BSD**; normalize to bytes explicitly or the cross-platform numbers are wrong. Interface becomes
`measure(phase_descriptor) -> (wall_ns, peak_rss_delta_bytes)` with those three pinned.
===!!!

@@!!!!
**Fifth-pass audit — RSS setup contamination:** `ru_maxrss` is a process-lifetime high-water mark, so
loading/materializing a persisted fixture **before** the span still raises the reported peak and cannot be
subtracted reliably with an interpreter-only baseline. The proposed exclusion of fixture generation/setup
therefore is not achieved by merely starting the timer later. Choose one honest design: include all child
setup in the memory claim; prepare input in a separate process and have the measured child perform the
ratified serialize/load/index chain from a minimal descriptor; or use a sampled-current-RSS monitor with an
explicit pre-span baseline instead of `ru_maxrss`. Also clarify how serialize remains inside the span if the
child begins by loading an already-persisted fixture.
@@!!!!

==!!!!
**Accepted — `ru_maxrss`'s high-water-mark semantics defeat "start the timer later" for memory (my third RSS
slip — owned).** A pre-span fixture load raises the process-lifetime peak and can't be subtracted with an
interpreter-only baseline. Honest design (your options 2+1, with 3 for per-phase): the **measured child
receives a minimal descriptor** (not a materialized fixture) and performs the **ratified
serialize→load→index→rebind chain itself** — so (i) fixture *generation* runs in a separate prep process and
never touches the measured child's peak, and (ii) **serialize stays inside the span** because the child
performs it (it loads a *descriptor*, not a pre-serialized artifact — fixing my round-4 "loads a persisted
fixture," which broke D35). With nothing else in the child, its **whole-lifetime `ru_maxrss` is the honest
peak** (your option 1, now clean). For finer per-phase memory, a **sampled-current-RSS monitor with an
explicit pre-span baseline** (your option 3), not `ru_maxrss`. Interface updated accordingly.
==!!!!

@!!!!!
**Sixth-pass audit — materialization impossibility:** A descriptor alone cannot be serialized as the full
scale fixture. The measured child must either materialize the fixture from that recipe (fixture generation
then contaminates lifetime `ru_maxrss`) or load/receive a materialized object (which adds a pre-serialize
load/IPC serialization and its peak). So the claimed clean whole-lifetime peak is not yet achievable.
Choose explicitly: include generation and label the result a conservative end-to-end upper bound; use a
sampled-current-RSS monitor after child-side materialization for the named operation span; or accept and
quantify the setup/transfer overhead. Do not claim prep-process isolation removes memory needed to construct
the object that `save_stream` will serialize.
@!!!!!

=!!!!!
**Accepted — and this is my fourth RSS correction in four rounds; owning the pattern.** You're right:
`save_stream` can only serialize an object that already exists in memory, so the measured child must either
generate it (generation contaminates lifetime `ru_maxrss`) or load/receive it (adds load/IPC peak) — the
"clean whole-lifetime peak of just the ratified chain" is **not achievable**, and prep-process isolation does
**not** remove the memory needed to construct the object serialize consumes. Honest decomposition (your three,
combined): **(a)** report lifetime `ru_maxrss` as a **conservative end-to-end upper bound** (includes
materialization — labeled as such); **(b)** attribute the **named-ops span** (serialize→load→index→rebind) via
a **sampled-current-RSS monitor** taken *after* child-side materialization (current-RSS delta, not the
lifetime high-water mark); **(c)** **separately quantify** the materialization/transfer overhead. Given four
straight misses on this in prose, the scaffold should **pin the constraints and the three-way choice, not a
single mechanism** — the actual sampler is selected and **verified with a real measurement at build**, not
asserted here. I've stopped claiming isolation yields a clean peak.
=!!!!!

!!!!!!
**Seventh-pass audit — close with two reported values:** This decomposition is technically honest. For the
named-ops monitor, report both **absolute sampled peak RSS** and **incremental peak above the post-
materialization baseline**; the delta attributes operation overhead, while the absolute value preserves
D35's real CLI memory burden. Pre-register sampling cadence/collection method and validate it against a
planted short-lived allocation so the sampler cannot miss narrow native peaks. Gate the conservative
lifetime upper bound and the named-ops growth result separately, with materialization overhead reported as
the reconciliation between them. With those bindings, the RSS issue is closed at scaffold level.
!!!!!!

!!!!!!
**Accepted — RSS closed at scaffold level.** All three bindings adopted: (1) the named-ops monitor reports
**both** the **absolute sampled peak** (D35's real CLI burden — the resident materialized structure is part
of what the CLI actually pays while operating) **and** the **incremental peak above the post-materialization
baseline** (operation overhead); (2) sampling cadence/method is **pre-registered and validated against a
planted short-lived allocation**, so a narrow native peak cannot slip between samples — this closes the
resolution caveat I raised; (3) the conservative **lifetime upper bound** and the **named-ops growth** result
are **gated separately**, with materialization overhead reported as the reconciliation between them
(lifetime ≥ absolute-sampled ≥ incremental-delta — three nested, honest values). No further RSS elaboration
from me: the mechanism is pinned to these bindings and verified with a real measurement at build.
!!!!!!
3. **Anchor-poor density [RULED]:** **sweep, not a point** — ~6 points from 71% down to ~10–15%; gate
   criterion = **false-bind rate ≈ 0 (S5.2 floor) across the whole sweep, abstention rate allowed to rise**.
   (Folded into §1 anchor-density knob.)

@@@@@@
**Adversarial audit:** A density percentage is not independently controllable if it is achieved by changing
genre, atom length, or repetition. Define the exact statistic (type-unique vs occurrence-weighted,
unique-in-both, k after normalization), tolerance around each target, and a construction that holds N and
edit magnitude constant. Replace "≈0" with a finite-sample rule or defer that rule to the owning item;
otherwise the gate can neither be reproduced nor falsified.
@@@@@@

======
**Conceded — the deepest fixture point.** A density % reached by changing genre/atom-length/repetition
**confounds** difficulty — and my "verse/fragmentary/repetition sources" is exactly that confounded
approach. The clean fix: a **controlled-vocabulary synthetic generator** — draw tokens from a vocabulary
of tunable size (Zipf param / type-token ratio), holding N and edit-magnitude constant, so density is the
*only* moving variable. Will define the exact statistic (**type-unique-in-both k-grams after
normalization, k stated**), a tolerance band per target, and defer the finite-sample acceptance rule to
the owning item (4/S5.2). "≈0" replaced accordingly.
======

@@@@@!
**Second-pass audit:** A Zipf/vocabulary change does not make density the **only** moving variable; it also
changes repetition run structure, ambiguity, shingle-frequency skew, and diff tie behavior. Use paired
fixtures with the same N, atom boundaries, edit locations, and as much local frequency structure as
possible, then describe density as the intended treatment rather than claiming perfect causal isolation.
Most importantly, measure uniqueness of the actual boundary-anchor representation, not generic k-grams.
@@@@@!

=====!
**Accepted — my "only moving variable" over-claimed.** A Zipf/vocabulary change also shifts repetition-run
structure, ambiguity, and shingle-frequency skew. Correct framing: **paired fixtures** holding N, atom
boundaries, and edit locations constant; density is the **intended treatment**, not a perfectly-isolated
cause. And (again) measure uniqueness of the **actual boundary-anchor representation**, not generic
k-grams. I'll state it as a controlled treatment with named residual confounds, not causal isolation.
=====!
4. **Fixture substrate [RULED, with caveat]:** **synthetic-only for the item-2 invariants** — but Ben's
   caveat governs: the synthetic identity map is the oracle for the *conditional property*, **NOT a
   deployment-correctness certificate.** The four-part guard (not-circular / scope-of-proof / oracle-
   independence-and-teeth / drift-fidelity-unvalidated) is in §1. PLL enters only as a real-distribution
   *confidence* proxy (copy2-derivation); a **true real-PLL re-extract is a required post-S4.6 gate**, not
   optional.

@@@@@@
**Adversarial audit:** This decision is internally inconsistent as written: "synthetic-only" and "PLL
enters" cannot both define item 2 without distinguishing gating invariants from an optional/non-gating
probe. Make that distinction explicit. More importantly, register the post-S4.6 gate in the authoritative
tracker/DoD with an owner and block condition; repeating "required" in this scaffold does not ensure it
happens.
@@@@@@

======
**Conceded.** State it once: **gating invariants = synthetic-only; PLL/copy2 = an optional non-gating
distribution probe** (R11). And register the post-S4.6 gate in `ENGINE_STRUCTURE_TASKS.md` (S5.1-R #48 /
S4.6 rows) with an owner + block condition (R9), not scaffold prose.
======

@@@@@!
**Second-pass audit:** This repeats the unresolved optional-probe scope and retroactive-tracker concerns.
The clean disposition is: remove PLL/copy2 from item 2, add one forward real-data gate row with explicit
dependencies, and leave completed historical rows intact. If the project deliberately amends completed
rows, record the dated amendment rather than rewriting their original acceptance claim.
@@@@@!

=====!
**Accepted — the clean disposition.** Remove PLL/copy2 from item 2; add **one forward real-data gate row**
(on S5.1-R #48) with explicit dependencies; leave completed historical rows **intact**; if a completed row
must ever be amended, it's a **dated addition**, never a rewrite of its original acceptance claim.
=====!
