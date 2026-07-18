# S4 — L2 projections + `node_id` + structure map (build plan)

Status: **DRAFT v4 — post third-pass confirmation audit.** v1 distilled `s4_plan_discussion.md` (six-round inline
audit + O1–O5 rulings); **v2** folded the six-reviewer correctness pass (H1–H4/M1–M11/LOW — §0); **v3** folded the
six-reviewer second pass (findings X1–X20 + LOW roll-up, `s4_plan_pass2_findings.md` — §0.1); **v4** folds the
three-reviewer focused third pass that confirmed the v3 delta and caught the residual issues it introduced
(findings P3A/P3B/P3C — §0.2). Every
actionable claim carries a stable id (`§x.y`, `D-S4-x`, `inv N`, `M-Sx`, `EC.*`, `B-N`, `O-N`); §8 maps every
carried audit/follow-up block to the id that absorbed it. Code-evidence anchor: **fixed commit `d611702`**
(the anchor is a pinned commit, **distinct from the moving document HEAD** — R2-05; symbol + test names given;
verified byte-identical to current code by three pass-3 reviewers — `git diff --stat d611702 HEAD -- engine/src
engine/tests` is empty, docs-only).

Task: **S4 — the keystone** (milestone S4, concern B, wave W2). Tracker rows **S4.0–S4.7** (S4.0 added, X18).
Spec refs: PLAN §3.1–§3.6, §11.2; D5/R3, D10, D11, D12, D13, D18, D20, D21, D25, D29, D30, D33, D35.
Upstreams, **all DONE and verified consumable**: S1.1 (frozen `Atom.geom` slot), S1.5 (atom-store schema +
version), S3.0 (`ResourceLineage` + normalizer policy).

---

## 0. Revision note — correctness-pass fix-map (v1 → v2)

Each finding from the six-reviewer **first** pass and where v2 closed it. (Reviewer verdicts on code-claim
fidelity, decision-fidelity, and neutrality *design* were clean; the fixes concentrate in edge-cases, red-first
coverage, and guard binding.)

| Finding | Severity | Fix location |
|---------|----------|--------------|
| **H1** root node unspecified; inv 14 flags the root as `ORPHAN_NODE`; no `root_id`; no `NO_ROOT`/`MULTIPLE_ROOTS`; empty/forest undecided | HIGH | §3.B.0, inv 14, EC.NO_ROOT/EC.MULTIPLE_ROOTS, §3.B.5 |
| **H2** `node_id` uniqueness not an invariant | HIGH | inv 16, EC.DUPLICATE_NODE_ID |
| **H3** `validate_structure_map(map)` can't construct inv 1b coverage / owned-atom existence; no `DANGLING_ATOM_REF` | HIGH | §4.0 two-input signature `validate_structure_map(map, atom_store)`, inv 1b, inv 17, EC.DANGLING_ATOM_REF |
| **H4** declared codes with no firing red mutation | HIGH | §4.0 code table requires a red mutation per code |
| **M1** no consolidated Node field table; reserved-field vs `additionalProperties:false`; undefined terms | MED | §3.J Node object schema; term defs |
| **M2** error-code set not closed/coherent | MED | §4.0 closed code table; `EC.*` naming |
| **M3** alias-uniqueness enforcement site contradictory | MED | §3.D.4 + inv 18 (eager at load AND re-guard at resolve) |
| **M4** `schema_status` "lying constant" regression | MED | §1.2.2 + inv 23 |
| **M5** D-S4-I orphan; digest producer/atom-ordering unspecified | MED | D-S4-I + inv 20; §3.E.9 |
| **M6** neutrality/guard binding not enforced | MED | inv 15, 21, 22, 12a |
| **M7** handle/policy: no `⊆ block_vocabulary`, no resolvability, class↔kind | MED | §3.D.1, inv 19, EC.POLICY_*/CLASS_KIND_MISMATCH |
| **M8** `children`/`body_atoms` ordering + contiguity unspecified | MED | §3.B.6 |
| **M9** boundary labels; renderer-version routing; sidecar engine half floats | MED | §1.2, §3.D.6, §1.4.1c |
| **M10** alias target resolution unchecked; node lifecycle unassigned; alias minting trigger | MED | inv 18, §3.B.7, §3.D.7 |
| **M11** stale-class constant double-framed; §8.2 "exactly one id" false | MED | §1.1/§2.1/D-S4-F; §8.2 |
| **LOW** (v1) | LOW | folded inline |

### §0.1 Second-pass fix-map (v2 → v3)

Each finding from the six-reviewer **second** pass and where v3 closes it. **This fix-map is the authoritative,
self-contained record** (finding · severity · fix location); `s4_plan_pass2_findings.md` is a **supplementary
audit-trail artifact committed alongside this plan** — the citation is non-essential (P3). Convergent findings
(≥2 independent reviewer lenses) marked **‡**. My-read severity adjustments (reviewer HIGH → MED) noted.

| Finding | Severity | Fix location |
|---------|----------|--------------|
| **X1‡** born-gate ↔ `load_structure_map` bootstrap deadlock | HIGH | §1.2.2/§1.2.3 (loader born-agnostic), §1.5 M-S4.4 (`assert_schema_born()`), §4.0 SCHEMA_NOT_BORN, inv 23 |
| **X2‡** §4.2 "route through loader" makes B-2/3/4 red tests depend on the B-5 loader/validator/EC-set | HIGH | §4.2 (two-phase posture), §5, Done-when map |
| **X3‡** inv 14 leaf-only self-contradiction; empty-container / non-container-root no code; one fixture can't both validate and reject | HIGH | inv 14 (total-order rewrite), §4.0 (EC.EMPTY_CONTAINER, EC.ROOT_ID_DANGLING), inv 26, §3.B.5, §1.2, §1.5 M-S4.5 |
| **X4‡** validator can't see excluded atoms; no disjointness code; furniture field named `role` | HIGH | §4 header (atom_store contract), §3.B.1, §4.0 (EC.OWNED_EXCLUDED_ATOM + furniture bucket), inv 1b/17, §3.J/§1.3.4 (`capture_role`) |
| **X5‡** CYCLE necessarily co-fires MULTI_PARENT | MED | §4.0 CYCLE, inv 14 (assert token in payload) |
| **X6** §3.D.5 temporal alias rules: no code, no per-rule mutation | HIGH | §4.0 (EC.ALIAS_INTERVAL_INVALID, EC.ALIAS_TEMPORAL_INCOMPLETE), inv 18, §3.D.5 |
| **X7** inv 4/5 vacuous (no red mutation) | HIGH→**MED** | inv 4/5 (concrete re-deriving mutants + fold note) |
| **X8** inv 20 geometry-hash mutation unproducible (all `Geom.absent()`) | HIGH→**MED** | inv 20 (synthesize `Geom.matched()`), §3.E.1 |
| **X9** `decision` inertness prose-only (no no-reader binding) | HIGH→**MED** | inv 25, §1.4.1, §3.J, Done-when |
| **X10** inv 23 "born iff" green in provisional∧broken | MED | inv 23 (two unconditional asserts), §1.2.2 |
| **X11‡** inv 6 cheat set open-ended; S4.3 re-run ungated | MED | §3.C.3, inv 6, §1.5 M-S4.3, Done-when |
| **X12‡** §4.4 smoke defeatable (0-`ref_op` quadratic) | MED | §4.4, D-S4-E |
| **X13** stale-`.pyc` mutation guard unwired | MED | §4.1.x header, B-7 |
| **X14‡** EC.* module + negative fixtures homeless; collect-all vs writer/load-gate partition unstated | MED | §1.5 (`structure/errors.py`), §4.0/§4.1 (partition), §4.2 |
| **X15** loader Tier-1→Tier-2 ordering unstated | MED | §4.2 (loader contract), §4.1.x header |
| **X16** `body_atoms` strict-ascending unpinned | MED | §4.0 (EC.BODY_ATOMS_UNORDERED), inv 27, §3.B.6 |
| **X17** vocab near-dup/whitespace under-pinned | MED | §3.E.7 (exact-after-normalization), §4.0 VOCAB |
| **X18** §8.3 omits S4.0 tracker row; issue-set vs row-set unreconciled | MED | §8.3, header Task line |
| **X20** sidecar engine-half forward row under-specified | MED | §1.4.1c, §8.3 |
| **LOW** (v2 pass) A-3/A-4/A-5/A-6, B-8/B-9, C-8/C-9/C-10, D-3/D-6, E-4/E-5/E-6/E-7 | LOW | folded inline below |

### §0.2 Third-pass fix-map (v3 → v4)

The focused third pass **confirmed** the two load-bearing v3 rewrites (inv 14's `|Z|` total-order closes the v2
A-1 leaf-only collision; the born-agnostic loader + `assert_schema_born()` breaks the X1 deadlock) and the
fix-map fidelity (20/20 v3 rows deliver; the atom_store contract is code-grounded satisfiable). It also caught a
family of residual defects v3's *own* edits introduced — chiefly that the X5 token-assertion / co-firing
discipline was not applied uniformly when the collect-all framing and the new root/identity codes were added.
Convergent (≥2 reviewers) marked **‡**.

| Finding | Severity | Fix location |
|---------|----------|--------------|
| **P3A-3 / P3B-2‡** `ROOT_ID_DANGLING` co-fires a second root code under collect-all (v2 double-root bug relocated to the dangling-root axis) | HIGH | §4.1 Tier-2a precondition phase, §4.0 (ROOT_ID_DANGLING/DUPLICATE_NODE_ID short-circuit), inv 14, inv 16 |
| **P3A-5** `DUPLICATE_NODE_ID` "pre-table" short-circuit contradicts "collects all in one pass" | MED | §4.1 Tier-2a, inv 16 |
| **P3A-4** `ORPHAN_NODE` ⟺ `MULTIPLE_ROOTS` — never fires alone (X5-class, unguarded) | MED | §4.0 ORPHAN_NODE, inv 14 (assert token + co-fire note) |
| **P3A-2** "empty map → `NO_ROOT`" unreachable (zero nodes ⇒ `ROOT_ID_DANGLING`) | MED | §3.B.5, §4.0 (NO_ROOT/ROOT_ID_DANGLING), inv 14 |
| **P3A-7** two-phase Phase-1 asserts on `EC.*` codes with no specified producer | MED | §4.0 producer note, §4.2 (per-module validators raise; aggregate composed, I5-sourced) |
| **P3B-1** atom_store contract under-specifies the canonical-vs-witness **id namespace** | MED | §3.B.1, §4 header |
| **P3C-2** §1.2 lead still calls "malformed-manifest rejection" a *differ-fixture* property (X3 conflation, residual) | MED | §1.2 lead |
| **P3C-3** inv 2 (Tier-1 schema) mis-filed at B-2 while siblings 22/24 moved to B-5 | MED | §1.5 M-S4.1→M-S4.4, Done-when, B-2/B-5, inv 2 |
| **P3B-9** inv 26 (empty-container, a pure projection check) filed at S4.4 not S4.1 | LOW | §1.5, Done-when, B-2/B-5 |
| **P3B-3/6, P3B-7, P3B-10, P3B-11, P3A-6, P3C-4/5/6** test-specificity / mechanization / dangling-tag tightenings | LOW | inv 18/23/25/27, §3.E.10, §4.4, §8.3, B-N cites |


### §0.3 Post-keystone dispositions (2026-07-02, user-ratified after the B-7 adversarial audit)

B-5/B-6 shipped; the pre-commit audit pair (plan-fidelity 14/14 SATISFIED; correctness) plus the
user's review produced these ratified amendments — recorded here so the plan stays the authority:

| Disposition | Fix location |
|-------------|--------------|
| **A-1 `CLASS_NOT_IN_VOCAB` added to the closed code set** — a node using an UNDECLARED `node_class` while carrying a per-node `handle_policy` override validated completely clean (kind lookup skips undeclared classes; the override short-circuits `POLICY_UNRESOLVED`; `VOCAB_*` reads declared entries only). The mirror of `VOCAB_UNUSED`. Producer: `validate_block_vocabulary` (handles.py), Tier-2b. Reserved-but-used stays legal in S4 (a reservation is still a declaration). | §4.0 table, inv 19, §3.B.2; `test_structure_handles.py::test_undeclared_node_class_fires_even_with_a_policy_override` |
| **A-2 `aliases` is a required header-level array** — §3.J's header enumeration omitted it, but inv 18's eager load check requires aliases on disk and the Node schema's `additionalProperties:false` bars per-node nesting; header-level is the only consistent placement (implemented at B-5; plan text now matches). | §3.J header list |
| **A-3 `rebind_anchors.region` coordinate-space contract locked, space itself deferred** — region shares the atom-level `Geom`'s coordinate space (whatever S2.1 pins), never a second convention; the space's concrete definition + any witness/space discriminator field are S5-planning decisions (BR-022). Widening the region shape later is a schema-version bump → re-enters `provisional` → re-birth (§1.2.2) — cost known and accepted. | schema `rebind_anchors` description; BR-022; `test_structure_map.py::test_region_description_pins_the_shared_coordinate_space_contract` |
| **A-4 writer crash-state recovery routed to S8.1** — the licensed supersede is per-file-atomic but not one transaction; a process kill between the snapshot write and the live write leaves snapshot-present/live-stale, and the retry is indistinguishable from a snapshot clobber. S8.1's recovery runbook owns the idempotent-retry rule (permit re-supersede when the existing snapshot's bytes equal the live map's). | §1.3.2; tracker S8.1 row |
| **A-5 two writer letter-deviations ratified** — the writer *validates* the caller's `map_revision` tick (CAS) rather than incrementing (§3.D.5's letter), and "explicit output target" is implemented as naming the exact stored revision being superseded. Both judged stricter than the letter. | §3.E.8 (as-built), `structure_map.write_structure_map` docstring |

---

## 1. Scope & boundaries

### §1.1 What this wave delivers — **S4.0–S4.5** (S4.5 folded in, O5)

The S4 keystone is the schema half of concern B *plus its birth gate*: the projection model, the identity
model, the handle/alias model, the `structure_map.json` schema + lineage manifest, **and** the D18
differ-fixture. Per O5, **S4.5 is folded in** — the S4 milestone closes only when S4.5's differ-fixture
validates and flips `schema_status` `provisional`→`born` (§1.2, D-S4-A).

- **S4.0 — constants + error-code module** (built first; **decision-owned by D-S4-F but built as its own step
  B-1/M-S4.0**, not "inside S4.4" — M11): add `STRUCTURE_MAP_STALE_CLASS`; pre-place `RELATION_STORE_STALE_CLASS`
  (O1, D-S4-F); add the `schema_status` module map (§1.2.2); add the closed **`EC.*` error-code module**
  (`structure/errors.py`) so the codes exist before B-2's first reference (X14).
- **S4.1 — L2 projection model.** Container vs leaf node; the **root spec** (§3.B.0); open per-book `node_class`
  vocabulary; ownership + coverage + uniqueness (inv 1a/1b/16); ordering/contiguity (§3.B.6); B re-groups +
  re-types over existing atom ids — NOT true re-atomization (§1.3.5, D-S4-B). Pure core, no language opinion.
- **S4.2 — `node_id` identity + minting split.** Opaque, persisted, never recomputed (D33). Humans mint
  containers, the extractor machine-mints leaves; `minted_by` = conceptual minting authority (D-S4-C).
- **S4.3 — handle policy + rendered handles + alias records.** Per-`node_class` `handle_policy` with a defined
  resolution order; handles rendered, derived-only; alias records with a temporal coordinate; active-alias
  uniqueness enforced **at load and at resolve** (D-S4-D).
- **S4.4 — `structure_map.json` schema + lineage manifest.** JSON-Schema + the consolidated **Node object
  schema** (§3.J) + the manifest (M3 per-layer versions/stale-classes; split canonical hashes; lineage
  fragment; schema-const binding; **regen-guarded writer**; **born-gate `assert_schema_born()`**) (D-S4-E).
- **S4.5 — D18 birth gate (folded).** The differ-fixture validates → `schema_status` `provisional`→`born`;
  **closes the milestone** (§1.2, D-S4-A).

### §1.2 The closing gate — **S4.5, D18 schema-born** (part of this wave)

S4.5 hand-authors a **conforming second-structure synthetic fixture built to DIFFER from PLL** (depth-0 body,
`designation-string` handle policy, non-ordinal headings, mismatched body segmentation, alias-uniqueness,
**relation-endpoint shape / reference placeholders** — *not* "resolution", reserved for S7/S9.4, R2-03). It is
the **same** adversarial fixture S9.4 later drives end-to-end, and is **distinct from `books/synthetic`** (a
miniature PLL, §2.8). The **malformed/incomplete-manifest rejection** (*not* "stale-manifest failure" — a
stored-vs-live staleness **comparison** is S8.1; in S4 the only mechanism is structural-completeness rejection
per inv 11, M9) belongs to the **negative-fixture set** (§1.2.0/§3.B.5), **not** this conforming fixture (P3C-2).

- **§1.2.0 — passing vs negative fixtures are distinct files (X3).** The S4.5 differ-fixture is a **conforming**
  (must-validate) map: it proves the schema *generalizes* to a non-PLL shape, and it is what flips `born` (inv
  23). The **degenerate-shape and malformed-manifest *rejections*** (§3.B.5) are a **separate, named set of
  negative fixtures** owned by S4.4's mutation battery (inv 11/14/26 — listed in M-S4.4) — a single file cannot
  simultaneously validate and be empty/leaf-only/malformed. The differ-fixture *re-exercises* nothing it must
  reject; it only adds non-PLL-shape generalization coverage.
- **§1.2.1** The conforming (PLL-shaped) fixture proves the schema *accepts* a valid map; the differ-fixture
  proves it *generalizes*. The schema's defining correctness property (not PLL-overfit) is established **only**
  by the differ-fixture, so S4.4 alone is **not** a born schema (O5).
- **§1.2.2 `schema_status`** is a property of the **schema version**, tracked in a module-level mapping beside
  the version constant — version N is `provisional` until S4.5's differ-fixture test passes, then `born`.
  **Nothing lifecycle-ish persists in any map file** (Audit 2). The flip is a human edit *bound* by inv 23,
  whose assertion **form is two unconditional asserts** (`assert differ_validates` **and** `assert
  schema_status[current] == born`), **not** a bare biconditional — a literal `(status==born)==validates` is
  green in the provisional∧broken quadrant and would let S4 sit green-but-unborn (X10). A schema-version **bump**
  (e.g. the S6 role/authorship addition) **re-enters `provisional`** and needs its own birth gate; a **missing**
  `schema_status` key is **fail-safe** (treated as `provisional`/raise).
- **§1.2.3** A downstream B/C task harness or S8.1 loader meeting a `provisional` schema version raises a typed
  **`SCHEMA_NOT_BORN`**. **The producer is the dedicated born-gate `assert_schema_born()` (M-S4.4), NOT the
  read-path `load_structure_map` and NOT `validate_structure_map`** (X1, M2/M11): `load_structure_map` is
  **born-agnostic** so the S4.1–S4.4 invariant red-tests (which route through it on a still-`provisional`
  schema, §4.2) are not short-circuited, and inv 23's negative test calls `assert_schema_born()` **directly**.
  `SCHEMA_NOT_BORN` names **S4.5** as the repair, distinct from ordinary M3 version staleness (Audit 2). There
  is **no silent override**; **prefer no schema-birth escape at all** — a provisional schema simply cannot pass
  the born-gate. Any local-only escape is loud, **distinctly named (NOT the regen flag)**, and **structurally
  impossible inside a DONE/GATE harness path** (the gate reads no override). Folding S4.5 means no completed S4
  ever sits in a `provisional` state.

### §1.3 Explicitly NOT in this wave (owned by neighbours)

1. **§1.3.1 — `rebind_anchors.region` *population* / the re-attach algorithm → S5.1.** S4.4's schema *admits*
   the optional anchor sub-object (`{region?}`); populating it and the bind/fail-loud logic are S5. The slot is
   `region`, never `geom` (D-S4-H, Audit 11).
2. **§1.3.2 — the stale-fail *loader* / migration router → S8.1.** *(Also S8.1's, per §0.3 A-4:
   the writer's snapshot-present/live-stale crash state + the idempotent-retry recovery rule.)* S4.4 *produces and stamps* the manifest +
   stale classes; S8.1 *consumes* and compares stored-vs-live (including the `handle_renderer_version` mismatch
   **routing**, §3.D.6, M9). **Vanished-artifact detection is S8.1's** (R2-04). `map_revision` cross-write
   monotonicity is also **S8.1** (LOW).
3. **§1.3.3 — the relation-store schema + its stale-class *behavior* → S7.1c.** S4.4 carries the relation-store
   version slot and **pre-places the inert constant `RELATION_STORE_STALE_CLASS`** (O1); every early
   relation-store manifest example pins `present: false` (R2-04, Audit 1). No relation-store loader/reader is
   exported from `structure/` in S4 (pinned, inv 12a).
4. **§1.3.4 — the read-axes (`role` / `authorship` / `content_provenance_class`) → S6.1.** S4's **Node** schema
   **OMITS node-level `role`/`authorship` entirely** (the Node schema §3.J does not list them;
   `additionalProperties:false` blocks smuggling); **S6 adds them with a schema-version bump** (→ `provisional`,
   §1.2.2). No key literally named `role` exists anywhere in S4 — the furniture field is `capture_role` (X4/E-2),
   distinct from the deferred read-axis. `designation`/`title` remain handle/display inputs only (Audit 14).
5. **§1.3.5 — true re-atomization (split/merge → *new* atom ids) → S8.2/D25.** S4.1 corrects the projection by
   re-grouping + re-typing **at the node level (`node_class`)** over existing, unchanged atom ids — atom
   `block_class` is L1-immutable/frozen (E-6); minting new atoms is L1 supersession (Audit 10). Node-level
   *retirement* (merging containers retires a `node_id`) is also S8.2 (§3.B.7, M10). **Tracker edit required**
   (§8.3).

### §1.4 Forward, with their own tracker rows

- **§1.4.1 — S4.6: hand-author the PLL container map (~61 containers). Owner: Ben (HITL).** Depends on S4.4's
  schema. The in-map **`decision` provenance enum** per node (`human-approved | plugin-suggested | inherited`)
  is **reserved present-but-inert** in S4 (§3.J; value-semantics are S8.2; **pinned by inv 25 — a no-reader
  static check, the same binding form inv 12a uses for `RELATION_STORE_STALE_CLASS`, not prose** (X9/E-1)). The
  prose authoring evidence lives in a named **authoring-evidence sidecar**, whose ownership is fixed **before
  S4.6 authoring begins** so it cannot drift into ad hoc notes (P2): artifact path
  **`<work>/authoring_evidence.json`** (a per-book committed companion to `structure_map.json`); schema
  **`structure/schema/authoring_evidence.schema.json`**; independently versioned by its own
  **`AUTHORING_EVIDENCE_SCHEMA_VERSION` + stale class** (M3 per-layer versioning). The engine half that owns the
  schema + digest-staleness validator is §1.4.1c.
  - **§1.4.1a** The sidecar is **optional at load** (generic `load_structure_map()` never requires it) and
    **required at the S4.6 PLL-authored-map gate** (every `minted_by:human` container ↔ one non-stale evidence
    entry, Audit 15). Gate failures are `EvidenceGateError` (exit 12, beside its raiser in
    `structure/evidence.py`) carrying typed `(kind, message)` findings from the closed
    `EVIDENCE_FINDING_KINDS` set (`missing | orphaned | misbound | stale-decision | stale-extent` —
    deliberately NOT `EC` codes, §4.0 stays the closed structure-map vocabulary), produced by the ONE
    non-raising `evidence_findings()` the S4.6 tooling status listing also consumes.
  - **§1.4.1b** *(amended 2026-07-02, post-audit remediation, user-ratified — supersedes the single
    node-structure digest, which conflated two change domains).* Evidence-staleness keys on **two recomputed
    canonical digests per entry**, both via THE producer (`_hash_canonical` = `lineage._canonical` +
    `_sha256_bytes`, D-S4-I):
    - **decision digest** — exact payload `{"node_class": <str>, "children": [<ordered child node ids>]}` (a
      leaf contributes `[]`). Witnesses the human's **topology decision**; re-bind-stable by D33
      store-and-rebind (a re-bind renames atoms, never node ids) and therefore **never machine-refreshed** —
      a drift always means a human changed the map's shape.
    - **extent digest** — exact payload `{"own": <the node's per-slot binding — {"heading": […],
      "signature": […]} for a container, {"body": […]} for a leaf, each slot a sorted set>, "beneath":
      [<flat sorted union of every descendant's coverage>]}` *(slot-aware form, F5/Option B closure —
      user-ratified 2026-07-02; supersedes the initial slot-flattened single-set payload, changed inside
      the schema-v1 free-edit window)*. Witnesses the **substrate binding**; semantics that fall out: any
      re-slot touching the node's own binding (heading→signature within the node, or a heading atom moved
      into its own child leaf — the F5 case the flat payload missed) stales exactly that node; a boundary
      move stales exactly the subtrees whose union changed (an unchanged-union ancestor stays fresh);
      internal re-segmentation under an unchanged boundary stales nothing above it; content addition
      cascades to every ancestor (honest). Mechanically re-stampable at S5 where a re-bind is unique +
      above threshold (protocol owned by S5.1).

    Evidence is stale **iff either digest changes**, each half its own finding kind (`stale-decision` /
    `stale-extent`). `map_revision` is **informational bookkeeping, NOT** a staleness trigger (Audit 15).
    The sidecar hash does **not** enter structure-map lineage; the document persists its own
    `schema_version` + `stale_class` + `book` (loader `expected_book` binding).

    **F5 closure (2026-07-02, Option B, user-ratified):** the delta re-audit found that under the
    original flat-set extent payload, a re-slot ACROSS nodes inside one subtree (a container's heading
    atom moved into its own child leaf's body) changed **neither** digest despite redrawing the heading
    boundary. Closed by making the extent payload slot-aware (the `own`/`beneath` form above) rather
    than adding a third digest: the two-domain taxonomy stands (decision = id-free human topology;
    extent = id-bearing binding, now complete over the node's binding surface), no new schema field or
    finding kind, and the S5 re-stamp protocol is untouched. One earlier acceptance deliberately
    reversed: a within-node heading↔signature re-slot now stales that node's extent (locally — the
    parent's `beneath` union is unchanged), since the role assignment is part of what the human
    verified.

    **Payload witnesses (2026-07-03, S4.6b DT-4 — user-ratified; s4_6_tooling_plan):** each
    sidecar entry additionally persists the exact payload behind each digest — the decision
    payload verbatim, the extent payload with its sorted atom-id lists run-length encoded on the
    wire — as **explanation data, never attestation**: the digests remain the only staleness
    authority, the gate never reads a witness, and `load_authoring_evidence` **self-verifies**
    every witness by recomputing its digest through THE producer (an incoherent pair is a
    `StaleArtifactError` naming the node, never a quiet degraded mode; under
    coherence-at-construction a forged digest cannot even load). This is what lets the S4.6b
    digest-diff explainer name WHICH children/atoms moved with no baseline snapshot or git
    archaeology. Amended inside the still-open schema-v1 free-edit window (no sidecar existed
    yet); the digest producers and payload shapes above are untouched.
  - **§1.4.1c — sidecar engine half (forward engine row, named — M9/X20).** The sidecar **schema + the digest-
    staleness validator** are *engine code* (not prose Ben authors), so they get an explicit forward tracker
    row with an **engine owner**, scheduled **immediately before S4.6 (predecessor: S4.4 schema; successor:
    S4.6 authoring gate)**. Home: `structure/evidence.py` (loader for the `authoring_evidence.schema.json`
    named in §1.4.1 + the digest-staleness validator) — the engine owner of the sidecar's schema + version
    constant. It **inherits inv 15 neutrality coverage** (it computes over `lineage` producers, carries no book
    literal)
    and ships with **a digest-staleness red test** (edit a bound node's `node_class`/`children`/owned atoms →
    its evidence entry goes stale). It is **not** silently folded into the human-owned S4.6 nor smuggled into
    the S4.0–S4.5 matrix (which would breach §1.5's amendment rule).
- **§1.4.2 — S4.7: scale check (D35).** S4.4 commits the addressable posture (§3.B.4, Audit 17); S4.7 measures
  the 10⁵ tier.

### §1.5 Deliverable matrix (bounded-surface guard — R2-02)

**Amendment rule:** any helper / module / **fixture generator / validator path** introduced during S4 —
production *or* test-only — **either maps to a row here or amends this matrix in the same commit**.

> **Successor ambiguity (flagged 2026-07-02, decide at S5 planning):** this rule says "during S4" and the
> matrix rows stop at M-S4.5, but S4.6-pre/S4.6a work (freeze, evidence, reader glue) already landed under
> the *export-surface pin* (`test_structure_artifacts.py`) rather than new matrix rows. Which instrument
> governs post-S4 additions — a per-milestone matrix like this one, or the pin alone — is undecided; the
> pin is currently doing the whole job. Decide when S5's plan is drafted, not ad hoc per commit.

| Id | Step | Module(s) | Public exports | Schema / fixture path | Acceptance tests | Non-goals (defers to) |
|----|------|-----------|----------------|-----------------------|------------------|-----------------------|
| **M-S4.0** | Constants + codes | `structure/artifacts.py`, `structure/errors.py` (new) | `STRUCTURE_MAP_STALE_CLASS`, `RELATION_STORE_STALE_CLASS`, `schema_status` map; the closed `EC.*` code set | — | inv 12a, 12c, 15 | no stale **comparison** (S8.1); no relation-store schema/behavior (S7.1c) — the relation constant is inert |
| **M-S4.1** | Projection model | `structure/projection.py` (new) | `Node`, `ProjectionMap`, ownership/registry/root validators | — | inv 1a, 1b, 3, 15, 16, 26, 27 | no true re-atomization / new atom ids (S8.2); no per-witness ownership (S7); no read-axes `role`/`authorship` (S6.1) |
| **M-S4.2** | Identity | `structure/projection.py` | `mint_node_id()` seam, `minted_by` | — | inv 4, 5, 6, 7 | no node retirement / tombstone / id-reuse (S8.2); no `node_id` scheme lock-in (revisitable) |
| **M-S4.3** | Handles + aliases | `structure/handles.py` (new) | `render_handle()`, `Alias`, `resolve()` | — | inv 6 (rendered-handle clause), 8, 9, 18, 19, 15 | no auto-mint of aliases (hand-authored, §3.D.7); no `handle_renderer_version` mismatch **routing** (S8.1); no persisted rendered handles |
| **M-S4.4** | Schema + manifest | `structure/schema/` + `structure/structure_map.py` (new) | `load_structure_map(path, atom_store)` (born-agnostic), `validate_structure_map(map, atom_store)`, `schema_version_const()`, regen-guarded `write_structure_map()`, `assert_schema_born()` | `structure/schema/structure_map.schema.json`; evolve `tests/fixtures/_generate_structure_fixture.py` → conforming; **negative-fixture set** `tests/fixtures/structure/invalid/*.json` (empty / leaf-only / empty-container / non-container-root / malformed-manifest / alias-collision) | inv 2, 10, 11, 12b, 13, 14, 17, 20, 21, 22, 24, 25 + §4.3 contract + §4.4 smoke + §4.2 read-path + §4.5 hygiene + §3.E.8 regen-guard + inv 15 (inv 26's negative fixture lives here; its check is M-S4.1) | no stale-loader / migration router (S8.1); no `rebind_anchors.region` **population** (S5.1); no relation-store behavior (S7.1c); no read-axes (S6.1) |
| **M-S4.5** | Birth gate | (test) | — | `tests/fixtures/structure/differ_structure_map.json` (new, **conforming**) | inv 23 (differ-fixture validates → `assert_schema_born()` → `schema_status` `born`) | no end-to-end drive of the differ-fixture (S9.4); no negative-case rejections (those are M-S4.4's `invalid/*.json`) |

---

## 2. Surfaces it binds into (code-evidence anchor `d611702`)

### §2.1 `structure/artifacts.py` — constants
- `STRUCTURE_MAP_SCHEMA_VERSION = 1`, `RELATION_STORE_SCHEMA_VERSION = 1` exist ("Bound by S4.4"/"Bound by
  S7.1c"). S4.4 **consumes** `STRUCTURE_MAP_SCHEMA_VERSION`.
- `ATOM_STORE_STALE_CLASS = "atom-stream"`, `RESOURCE_STALE_CLASS`, `NORMALIZER_STALE_CLASS` exist.
- **`STRUCTURE_MAP_STALE_CLASS` does NOT exist** (the one real code gap); the atom-store docstring already
  forward-references "the structure-map (B) and relation-store (C) classes." **Both new constants are
  decision-owned by D-S4-F and built first as step B-1/M-S4.0** (inv 12a); only inv 12b (manifest declares the
  class) is inside S4.4 (M11).
- `STRUCTURE_MAP_FILENAME`, `structure_map_path()` → `<work>/structure_map.json` already built (S0.1).

### §2.2 `structure/lineage.py` — consumed verbatim
`ResourceLineage.to_json()` emits `{schema_version, resource:{version,stale_class,descriptor},
normalizer:{version,stale_class,descriptor}}` — dropped under a header key, no re-shaping. **Binding: a contract
test** asserts the structure-map schema validates a live `ResourceLineage(...).to_json()` (§4.3). The shared
`$ref` form is **optional future hardening** (R2-06). The digest producer `_sha256_bytes(data: bytes)` and
canonicalizer `_canonical` (sort_keys, fixed separators, `ensure_ascii=False`) both exist here and are the
**named** building blocks for every S4 hash (D-S4-I, M5). A hash is `_sha256_bytes(_canonical(obj).encode(
"utf-8"))` — the UTF-8 encode is part of the call (D-6).

### §2.3 `config/schema/manifest.schema.json` — the anti-pattern S4.4 must NOT repeat
Hard-codes `"schema_version": {"const": 1}` with no Python constant. S4.4 binds via **two assertions** (Audit
3): (a) `schema_version_const(schema) == STRUCTURE_MAP_SCHEMA_VERSION`; (b) a version-derived fixture validates.

### §2.4 `tests/fixtures/_generate_structure_fixture.py` — binding precedent to evolve
Derives `schema_version` from the live constant; one byte-exact `render()` shared by writer + test; docstring
"MUST NOT anticipate" S4.4. S4.4 evolves it trivial→conforming; the conforming fixture **emits
`rebind_anchors.region`, never `.geom`** (inv 13/24).

### §2.5 `tests/unit/test_structure_artifacts.py` — already pins the three versions as independent positive ints + distinct locations + exports.

### §2.6 No L2 module yet
`structure/` holds `__init__.py, artifacts.py, atom_store.py, atoms.py, capture.py, classify.py, lineage.py,
roundtrip.py, roundtrip_gate.py, typed.py` — **no projection/node/map/handles/errors module**. S4 creates
`projection.py`, `handles.py`, `structure_map.py`, `errors.py`, and possibly `evidence.py` (§1.4.1c, forward).

### §2.7 Two `geom`s — kept distinct (D-S4-H)
Atom-level `Atom.geom` (S1.1, frozen `{present|absent}` + match-provenance) is authoritative, on atoms.
Node-level `rebind_anchors.region` is a plain nullable `{page, bbox_region}` — **no `present` flag, no
atom-`Geom` sub-object** (the schema rejects either via `additionalProperties:false`, inv 24). Optional (O4).
Population is S5.

### §2.8 `books/synthetic` — the mini-PLL S4.5 differs from. The differ-fixture is new (depth-0, designation-string, non-ordinal), not an extension.

---

## 3. Design decisions

### D-S4-A — Scope seam (folded, O5)
Linear chain S4.0→S4.1→S4.2→S4.3→S4.4→S4.5, each a red-first checkpoint **under the two-phase test posture of
§4.2** (early steps red-test the per-module validators directly against in-memory dataclasses; B-5 re-routes
each through `load_structure_map`). S4.4 is validated by a conforming fixture; **S4.5's differ-fixture is the
birth certificate that closes the milestone.**

### D-S4-B — L2 projection model (S4.1)
A node is **container** (owns ordered `children` + optional `heading_atoms`/`signature_atoms`) or **leaf** (owns
`body_atoms`). The full field list is §3.J.

- **§3.B.0 — ROOT node (H1).** A valid map declares **exactly one root**, named by **`root_id` in the map
  header**. The root is a **container** (a leaf-only or empty map is rejected, §3.B.5), **`minted_by:human`**,
  and carries a `node_class` that is a **container-kind class in `block_vocabulary`** (PLL adds a document/root
  container class — illustrative). The root has **no parent**; its `handle_policy` resolves from the
  `handle_policies` table for its class (§3.D.1). The root is the **anchor** for inv 14's traversal and is
  **exempt** from the `ORPHAN_NODE` rule (it legitimately has zero children-occurrences).
- **§3.B.1 — Ownership (Audit 9, X4).** **inv 1a (no double-ownership):** no `atom_id` appears in two of the
  **four mutually-exclusive buckets** `{heading_atoms, signature_atoms, body_atoms, header furniture_atoms}` —
  furniture is now an ownership bucket for disjointness, not a slot-only afterthought. **inv 1b (coverage):**
  every *included* **canonical-stream** atom (the universe is `atom_store.included_atom_ids()`, §4-header) is
  owned by exactly one node; *excluded/furniture* atoms are listed in the map header's **`furniture_atoms`**
  array with their `capture_role` (§3.J), never in a node, never forced into body. **An atom owned by a node
  slot must itself be `included`** (`EC.OWNED_EXCLUDED_ATOM`, inv 17) — the validator checks scope via
  `atom_store.scope_of()`. Per-witness ownership is S7.
  - **Id namespace (P3B-1).** Node slots own **canonical** atom ids (`included_atom_ids()` is the canonical-stream
    universe). Excluded/furniture atoms never enter the canonical stream (`build_canonical` keeps only `included`
    atoms, `capture.py`), so they are **witness** ids — therefore `furniture_atoms` entries and any
    `OWNED_EXCLUDED_ATOM` trigger carry witness ids, and `contains()`/`scope_of()` union canonical+witness while
    `included_atom_ids()` is canonical-only. When ≥2 witnesses furniture-capture the same marker, **which**
    witness id goes in `furniture_atoms` is pinned to the **primary witness** for S4 fixtures; the general
    multi-witness selection is an S5/S7 forward.
- **§3.B.2 — `node_class`** is an **open string vocabulary** declared in the header's `block_vocabulary`
  (§3.J), never a core enum; a **distinct axis** from `role` (S6, absent in S4) and `handle_policy` (R2-07).
  **Open never means undeclared:** every used `node_class` must appear in `block_vocabulary`
  (`CLASS_NOT_IN_VOCAB`, §0.3 A-1).
  Each `block_vocabulary` entry declares a **`kind` (`container|leaf|either`)**; the validator checks a node's
  slot usage matches its class kind (EC.CLASS_KIND_MISMATCH, inv 19, M7).
- **§3.B.3 — Correction scope:** B re-groups + re-types **at the node level** over existing atom ids; true
  re-atomization is S8.2/D25 (§1.3.5). Atom `block_class` is L1-frozen and never mutated (E-6).
- **§3.B.4 — Storage posture (Audit 12, Audit 17).** Flat node table keyed by `node_id`; persist **`children`
  only** (canonical ordered source); **derive `parent` on load**. Reference-validation resolves through the
  id-keyed table — no per-reference tree scan.
- **§3.B.5 — Degenerate shapes (X3, M-edge, M10).** Each rejection has a code + an invariant + a dedicated
  **negative fixture** (§1.2.0, M-S4.4 `invalid/*.json`):
  - **Empty map** (zero nodes) → `EC.ROOT_ID_DANGLING` (inv 14 Tier-2a — `root_id` cannot resolve against zero
    nodes; **not** `NO_ROOT`, which is reserved for a non-empty graph whose `root_id` resolves but `|Z|==0` —
    P3A-2).
  - **Leaf-only / zero-container map** → resolved by inv 14's total-order rule (`MULTIPLE_ROOTS` if ≥2
    parentless leaves; a single leaf named `root_id` that is not container-kind → `NO_ROOT`). No single input
    triggers two codes (the v2 leaf-only ambiguity is closed — X3/A-1).
  - **Container with zero `children` and no `heading_atoms`/`signature_atoms`** → `EC.EMPTY_CONTAINER` (inv 26).
  - **`root_id` naming no node** → `EC.ROOT_ID_DANGLING` (inv 14, Tier-2a precondition, short-circuit).
- **§3.B.6 — Ordering & contiguity (M8, X16).** `children` is ordered = **reading order** (feeds `position-path`
  handles + the §1.4.1b *decision* digest; the extent digest is set-canonicalized and order-blind). `body_atoms`
  is ordered by **strictly ascending canonical-stream index** and
  **need not be contiguous** (it may interleave around excluded furniture). Out-of-order or intra-list-duplicate
  `body_atoms` → `EC.BODY_ATOMS_UNORDERED` (inv 27) — note inv 20 cannot catch this because §3.E.1 re-sorts
  atoms before hashing, so a descending list round-trips byte-identically.
- **§3.B.7 — Node lifecycle (M10).** In S4 a structure map is authored **fresh**; there is **no in-place node
  deletion**. Re-group/re-type changes no stored leaf field (`parent` is derived); **merging containers retires
  a `node_id`** — node-level **retirement/tombstone semantics + id-reuse prohibition are S8.2** (its scope
  extends to L2 node identity; tracker note, §8.3).
- Pure dataclass; no language literal in `structure/` (inv 15 across all new modules + `*.json`).

### D-S4-C — `node_id` identity + minting split (S4.2): pin PROPERTIES (O3)
- **§3.C.1** Opaque string; pinned: (a) stable re-serialize; (b) stable positional move; (c) never derived from
  position/designation/content (D33/BR-021); (d) `minted_by ∈ {human, machine}`; **(e) unique within the map**
  (inv 16, EC.DUPLICATE_NODE_ID — H2; checked **before** the `node_id`-keyed table is built, raising on the
  second insert rather than silently overwriting).
- **§3.C.2 `minted_by` = conceptual minting authority** (human ⇒ a container; machine ⇒ a leaf) — not the
  runtime writer. Schema `description` carries **"conceptual minting authority" verbatim** (test-asserted).
  Name kept `minted_by` (R2-08). The human/machine **split is enforced both directions** (container⇒human,
  leaf⇒machine): EC.MINTED_BY_SPLIT, inv 7 (H4).
- **§3.C.3 Non-derivation control (Audit 5, X11).** inv 6 rejects a **closed, enumerated** set of derivation
  cheats (no open-ended "known-transform"): `{exact-eq, casefold-eq, slug(designation), slug(title),
  substring-of-rendered-handle, position-path string}` → `EC.NODE_ID_DERIVED`, one red fixture per transform.
  The **primary control** is the **structural seam**: `mint_node_id()` takes no designation/path/content arg and
  is **called before any handle/designation attaches** (ordering control). One fixture mutates designation,
  position, and content with the id fixed. The designation/slug/position cheats run at S4.2; the
  **substring-of-rendered-handle cheat re-runs at S4.3** when `render_handle` exists — filed under **M-S4.3 +
  the S4.3 Done-when** (X11/F-3), not S4.2-only.
- **§3.C.4** Default scheme (revisitable, fixture-only): counter for human containers, ULID-like for leaves.

### D-S4-D — Handle policy + rendered handles + alias records (S4.3)
- **§3.D.1 Policy resolution order (M7).** `handle_policy` is declared per `node_class` in the
  `handle_policies` table. A node's effective policy = **(1)** its own `handle_policy` override if present (the
  override value must be a known policy — `EC.POLICY_UNRESOLVED`), else **(2)** the nearest ancestor's
  override, else **(3)** the `handle_policies` default for its `node_class`. The validator asserts every
  `handle_policies` key is in `block_vocabulary` (EC.POLICY_NOT_IN_VOCAB) and every used `node_class` resolves
  to a policy (EC.POLICY_UNRESOLVED) — inv 19.
- **§3.D.2 Rendering signature (Audit 6):** `render_handle(map, node_id, policy, target_format, scope)`.
  `target_format ∈ {short, parse_md, html_slug}`.
- **§3.D.3 Derived-only (R2-09):** rendered handles are **NOT persisted** in S4 — only policy inputs. No "if
  cached" branch.
- **§3.D.4 Alias record:** `{handle_type, value, scope, locale_or_witness, target_node_id, valid_from,
  valid_to, status}`. **Term defs (M1):** `handle_type` = which rendered `target_format` the alias preserves;
  `value` = the literal retired handle string; `scope` = the resolution namespace (`global` or a container
  `node_id`; a non-`global` `scope` must name a live container node — `EC.ALIAS_DANGLING_TARGET`);
  `locale_or_witness` = the locale (active in S4) or witness (reserved for S7, M10). **Active-alias uniqueness
  (Audit 7)** key = `(handle_type, value, scope, locale_or_witness)`. **Enforced at BOTH sites (M3):** eagerly
  in `validate_structure_map` (EC.ALIAS_COLLISION, inv 18 — so a dup-alias map fails at **load**) **and**
  re-guarded as a `resolve()` precondition. Every alias `target_node_id` must resolve to a live node
  (EC.ALIAS_DANGLING_TARGET, inv 18, M10).
- **§3.D.5 Temporal coordinate (Audit 8, X6):** a monotonic `map_revision` integer in the header is the clock;
  `valid_from`/`valid_to` reference it. **Rules, each with its own code + red mutation (X6):**
  - `valid_from ≤ current` **and** `valid_to` null or `≥ valid_from` → else `EC.ALIAS_INTERVAL_INVALID`;
  - a non-`active` alias must carry `valid_to`, and an `active` alias must lie within its interval → else
    `EC.ALIAS_TEMPORAL_INCOMPLETE`.

  Writer increments `map_revision` once per authoring change (same event as the regen snapshot, §3.E.8).
  **Historical resolution:** `resolve(handle, at_revision=N)` returns the node whose interval contained N; the
  **default** resolve returns only `status:active`.
- **§3.D.6 Renderer versioning (Audit 6, M9, E-4):** `handle_renderer_version` is **stamped** into the manifest
  (bumped on slug/disambiguation-rule changes) **for S8.1 to compare**; S4 reserves the field only and
  implements no stale comparison. The mismatch→**routing** (handle-review / alias-migration diagnostic) is
  **S8.1's** (like `SCHEMA_NOT_BORN`, §1.3.2).
- **§3.D.7 Alias minting (M10):** in S4, aliases are **hand-authored**; the engine **resolves + validates**
  them (it does not auto-mint an alias on a designation/renderer change). inv 9 tests a hand-authored fixture.

### D-S4-E — `structure_map.json` schema + lineage manifest (S4.4): build to the ROW
- **§3.E.1** `source_artifacts` (raw witness hashes); `atom_streams` + `canonical_stream_id`; the **two split
  canonical hashes** (R2-10): **`canonical_content_hash`** over `{atom_id, text, raw_span, raw_source_hash}` and
  **`canonical_geometry_hash`** over the geom-region fields. Each is computed by **`lineage._sha256_bytes` over
  `lineage._canonical(...).encode("utf-8")`** of the **canonical-stream-ordered** atom payloads (atom order =
  ascending canonical-stream index — pinned, M5/M8); explicit field list, no "hash whatever's in the dict."
  *Caveat:* geometry is `Geom.absent()` everywhere today (`capture.py`), so `canonical_geometry_hash` currently
  covers absent slots; **the inv 20 geometry-edit red-test therefore synthesizes a `Geom.matched(...)` atom
  directly** (X8). Field membership firms when S2.1 populates geom.
- **§3.E.2** atom-store / structure-map / relation-store **schema versions, each with its stale class** (M3);
  relation-store pins `present:false` until S7.1c.
- **§3.E.3** the `ResourceLineage.to_json()` fragment verbatim, bound by §4.3.
- **§3.E.4** `profile_version`, `recognizer_version`, `handle_renderer_version`, `map_revision`, `root_id`,
  `block_vocabulary`, `handle_policies`, `furniture_atoms`.
- **§3.E.5 Schema-const binding (Audit 3):** the two assertions + `schema_version_const()` (§2.3).
- **§3.E.6 `schema_status`** beside the version constant (module-level), not per-map (§1.2.2).
- **§3.E.7 `block_vocabulary`** self-declared in the header; each entry `{name, kind, status:active|reserved}`
  (M1/M7). **Hygiene (Audit 13, §4.5, X17):** an entry is rejected when, **after normalization (Unicode NFC +
  casefold + strip)**, it (a) equals `classify.UNKNOWN` (`"unknown"`) → `VOCAB_UNKNOWN_COLLISION`; (b) is empty
  or whitespace-only → `VOCAB_EMPTY`; (c) collides with another normalized entry → `VOCAB_DUPLICATE` (this is
  the only de-duplication — there is **no undefined fuzzy near-duplicate metric**, which would risk rejecting
  legitimately distinct per-book classes); (d) is declared but unused and not `reserved` → `VOCAB_UNUSED`.
- **§3.E.8 Production regen-guard (D33, Audit 16, inv 21).** `structure_map.json` is irreproducible committed
  data. Fixture/test generation writes freely under `tests/fixtures/`. The production
  **`write_structure_map()` fails loud on overwrite of a hand-authored map** (EC.MAP_OVERWRITE_BLOCKED); the
  only path through is **explicit output target + snapshot-before-overwrite + a new lineage/`map_revision`
  entry**. **No env-var as the primary escape.** Guard implemented in the S4.4 writer and **red-first tested**
  (inv 21, M6).
- **§3.E.9 Structure-map staleness basis (M5).** S8.1 detects structure-map staleness from the **manifest's
  version + the two canonical hashes + the per-layer stale classes** — there is **no separate structure-map
  self-hash**. S4 stamps this basis but implements **no** stale comparison (that is S8.1's).
- **§3.E.10 Instrumented node-table access (X12, P3B-10).** `validate_structure_map`'s node-table and child-list
  access goes through an **injectable, countable accessor** owned by the validation context. "No raw dict/list
  handle escapes" is a **design/review constraint**, not a mechanically-guaranteed property — its only automated
  backstop is the §4.4 heuristic `ref_ops` ratio (a linear-but-uncounted bypass would under-count and is not
  caught short of an AST/import lint or S4.7's real op-count). Stated honestly so the smoke is read as a floor,
  not a proof.

### D-S4-F — Close the stale-class gap (S4.0); pre-place the relation constant (O1)
Add `STRUCTURE_MAP_STALE_CLASS = "structure-map"`; pre-place `RELATION_STORE_STALE_CLASS` as an **inert
wire-string** whose docstring states it **declares a future layer identity, not the existence of a relation
schema/artifact**. Both exported; pinned in `test_structure_artifacts.py`. **inv 12a (extended, M6)** asserts
each is present/exported/distinct from all other stale classes **and** that **no relation-store loader/reader is
exported from `structure/` in S4** (the inertness binding, not prose). Every early relation manifest example
pins `present:false`.

### D-S4-G — Schema-file location + binding helper (O2)
Schema at **`structure/schema/structure_map.schema.json`**. `schema_version_const(schema) -> int` inlined now,
factored at S7.1c.

### D-S4-H — Two geoms, no duplication (O4)
`rebind_anchors.region` optional/nullable `{page, bbox_region}`; authoritative geometry on atoms. The schema
**rejects a `present`/`geom` key inside `rebind_anchors`** via `additionalProperties:false` (inv 24, M6/H4).

### D-S4-I — Determinism / canonical serialization (S4.4) (M5)
**Producers named:** every hash is `lineage._sha256_bytes(lineage._canonical(obj).encode("utf-8"))` (sort_keys,
fixed separators, `ensure_ascii=False`) — an implementer may **not** substitute a different hash. **Ordering:**
atoms within a content/geometry hash are ordered by **ascending canonical-stream index**; `children`/aliases
serialize in their stored order; manifest keys are canonicalized. The human-authored map file stays diffable
`indent=2`; only the hashed sub-objects use canonical byte-form. **Proof obligation:** inv 20.

### D-S4-J — Node object schema (consolidated field list) (M1)
The single canonical Node field list S4.4's JSON-Schema enumerates (`additionalProperties:false`):

| Field | Kind | Req? | Tier | Notes |
|-------|------|------|------|-------|
| `node_id` | both | required | schema + inv 4–7,16 | opaque, unique |
| `minted_by` | both | required | schema + inv 7 | `human`\|`machine`; split enforced both ways |
| `node_class` | both | required | schema + inv 19 | open string; `∈ block_vocabulary`; kind must match slot |
| `children` | container | required-for-container | schema(`oneOf`) + inv 2,14,26 | ordered = reading order |
| `body_atoms` | leaf | required-for-leaf | schema(`oneOf`) + inv 1a/1b,2,27 | strictly ascending canonical-stream index; non-contiguous OK |
| `heading_atoms` | container | optional | schema + inv 1a/1b | container's heading atoms |
| `signature_atoms` | container | optional | schema + inv 1a/1b | **def:** a container's closing/sign-off atoms (e.g. an embedded letter's signature line — illustrative); ownership-only, authorship is S6 (E-7) |
| `designation` | both | optional | schema | handle input only |
| `title` | both | optional | schema | handle/display input only |
| `handle_policy` | both | optional | schema + inv 19 | per-node override; value must be a known policy; else inherit/default (§3.D.1) |
| `rebind_anchors` | both | optional | schema(`additionalProperties:false`) + inv 13,24 | `{region?:{page,bbox_region}}`; no `present`/`geom` |
| `decision` | both | reserved | schema (present, inert) + inv 25 | `human-approved\|plugin-suggested\|inherited`; value-semantics S8.2; **no S4 code reads it (inv 25)** |

Header-level (not per node): `root_id`, `block_vocabulary[{name,kind,status}]`, `handle_policies`,
`furniture_atoms[{atom_id, capture_role}]`, **`aliases[…]` (the §3.D.4 records — header-level, since
inv 18 checks them eagerly at load and `additionalProperties:false` bars per-node nesting; §0.3 A-2)**,
`map_revision`, the manifest block (§3.E). **Omitted until S6:**
node-level `role`, `authorship` (§1.3.4). `oneOf` enforces container-xor-leaf (inv 2 is **Tier-1**, LOW).

---

## 4. Two-tier validation + red-first invariant battery

**Two tiers (R2-11, refined H3).** **Tier 1 — JSON-Schema** validates *shape* (field presence/type;
`node_class` is a non-empty string with **no `enum`** (inv 22); container-xor-leaf `oneOf`; no extra keys).
**Tier 2 — the public semantic validator `validate_structure_map(map, atom_store)`** enforces what JSON Schema
cannot. **`atom_store` contract (X4/D-2):** the second input is the **atom store for all streams the map
references** (there is no single aggregate `AtomStore` class yet — S4 takes a thin reader or a mapping of
streams) exposing exactly two capabilities the validator needs: **`included_atom_ids()`** → the included
canonical-stream universe (inv 1b coverage) and **`contains(atom_id)` / `scope_of(atom_id)`** over the **full**
atom population across streams, including excluded/witness atoms (inv 17 existence + `OWNED_EXCLUDED_ATOM` +
furniture resolution — excluded atoms live only in witness streams, never the canonical stream, so the
canonical stream alone cannot supply them).

**Loader contract (X15).** `load_structure_map(path, atom_store)` runs, in order: **parse JSON → Tier-1
JSON-Schema → Tier-2 `validate_structure_map(map, atom_store)`**. It is **born-agnostic** (never checks
`schema_status`; the born-gate is the separate `assert_schema_born()`, §1.2.3/X1). It raises on the first tier
that fails.

- **§4.1 Error model (R2-11, X14/X19; precondition tier — P3A-3/P3A-5/P3B-2).** `validate_structure_map()` runs
  in **two sub-phases** so the structural preconditions cannot co-fire spurious downstream codes:
  - **Tier-2a (preconditions, short-circuit):** `DUPLICATE_NODE_ID` (you cannot build the `node_id`-keyed table
    with duplicate ids) and `ROOT_ID_DANGLING` (you cannot anchor a from-`root_id` traversal on a missing root).
    The **first** Tier-2a failure raises immediately; the Z root-topology and global-traversal checks **do not
    run**. This is why §3.C.1(e)/inv 16 say "checked before the table" and inv 14 says `root_id` is "checked
    first" — they are Tier-2a, **deliberately exempt from collect-all**, which is the only reason
    `ROOT_ID_DANGLING` and the Z codes (`NO_ROOT`/`MULTIPLE_ROOTS`) are mutually exclusive (P3A-3).
  - **Tier-2b (collect-all):** every remaining semantic code is **collected in one pass** and raised with the
    collected set as payload.

  The **closed code set partitions three ways (X14/X19):** `EC.* = {validator-collected: Tier-2a ⊎ Tier-2b}  ⊎
  {writer: MAP_OVERWRITE_BLOCKED}  ⊎  {born-gate: SCHEMA_NOT_BORN}`. The set is **declared in one module
  (`structure/errors.py`, M-S4.0)** as an enum/constant set, **pinned by a test** (inv 12c) — **no
  "non-exhaustive" hedge** (M2). Each code names its **producer** and has a **red-first mutation** (§4.0). S8.1
  routes on the code value.
- **§4.2 Two-phase read-path binding (R2-12, X2/X15).** The semantic invariants are exercised in **two phases**
  so each build step's red-first checkpoint is achievable when its producer exists:
  - **Phase 1 (B-2/B-3/B-4):** the per-module validators (`projection.py`, `handles.py`) **raise the relevant
    `EC.*` codes directly** (the codes live in `errors.py`, built B-1, and are importable by every module), and
    are red-tested **directly against in-memory dataclasses**. **Producer (P3A-7/I5):** the aggregate
    `validate_structure_map` (B-5) is **composed from** these per-module validators and re-raises/collects the
    **same** codes — the code is single-sourced (one producer per `docs/invariants.md` I5), so §4.0's
    "validator" producer = "the per-module validator, aggregated by `validate_structure_map`."
    `load_structure_map` does not yet exist.
  - **Phase 2 (B-5):** every Tier-2 invariant is **re-routed through the public `load_structure_map(path,
    atom_store)`** (which delegates to the single `validate_structure_map`) — that is the loader-wiring proof.
    Tier-1 invariants (inv 2, 22, 24) are exercised at JSON-Schema time inside `load_structure_map`'s Tier-1
    step.
  - **Headline test:** corrupt a fixture that passes JSON-parse + Tier-1 shape but fails only semantically (a
    dangling `children` ref that is a well-formed string; two `status:active` aliases sharing the uniqueness
    tuple) and assert `load_structure_map` rejects it.

### §4.0 Closed error-code set (`EC.*`) — producer + red-first mutation per code (H4, M2, X-pass)

| Code | Producer | Red-first mutation that fires it |
|------|----------|----------------------------------|
| `DUP_OWNERSHIP` | validator | an `atom_id` in two of the four ownership buckets (incl. furniture, X4) |
| `UNOWNED_INCLUDED_ATOM` | validator | an *included* canonical-stream atom (`atom_store.included_atom_ids()`) owned by **no** node (H4/H3) |
| `OWNED_EXCLUDED_ATOM` | validator | a node-slot atom whose `atom_store.scope_of()` ≠ `included` (X4) |
| `DANGLING_ATOM_REF` | validator | an owned-or-furniture `atom_id` failing `atom_store.contains()` (H3/X4) |
| `DUPLICATE_NODE_ID` | validator · **Tier-2a** (short-circuit) | two nodes with the same `node_id` (H2) — raised before the keyed table is built |
| `DANGLING_REF` | validator | a `children` entry naming no node |
| `ORPHAN_NODE` | validator | a **non-root** node with zero children-occurrences (root exempt, H1) — **co-fires `MULTIPLE_ROOTS`** (an orphan ∈ Z, root ∈ Z ⇒ `\|Z\|≥2`), so the red test asserts `ORPHAN_NODE ∈ payload`, not bare-raises (X5/P3A-4) |
| `MULTI_PARENT` | validator | a node in two parents' `children` |
| `DUPLICATE_CHILD_REF` | validator | a node twice in one parent's `children` |
| `ROOT_ID_DANGLING` | validator · **Tier-2a** (short-circuit) | `root_id` naming no node — **incl. the empty map** (zero nodes ⇒ `root_id` cannot resolve, P3A-2); suppresses the Z/traversal checks so no second root code co-fires (X3/P3A-3) |
| `NO_ROOT` | validator | `root_id` **resolves** but the zero-occurrence set `\|Z\|==0` (a fully-parented graph / pure cycle), **or** the single `\|Z\|==1` node is not container-kind (X3/P3A-2) |
| `MULTIPLE_ROOTS` | validator | `\|Z\| > 1`, or the single `\|Z\|==1` node ≠ `root_id` (root_id resolved but is not the topological root) (X3) |
| `EMPTY_CONTAINER` | validator | a container with zero `children` and no `heading_atoms`/`signature_atoms` (X3) |
| `CYCLE` | validator | a **reachable** on-stack back-edge — e.g. `root→A→B→A` (asserted as `CYCLE ∈ payload`; co-fires `MULTI_PARENT`, X5) |
| `UNREACHABLE_NODE` | validator | a node not visited from `root_id` (incl. a disconnected cycle) |
| `BODY_ATOMS_UNORDERED` | validator | a `body_atoms` list not strictly ascending by canonical-stream index, or with an intra-list duplicate (X16) |
| `ALIAS_COLLISION` | validator | two `status:active` aliases sharing `(handle_type,value,scope,locale_or_witness)` (M3) |
| `ALIAS_DANGLING_TARGET` | validator | an alias `target_node_id` (or non-`global` `scope`) naming no live node (M10) |
| `ALIAS_INTERVAL_INVALID` | validator | `valid_to < valid_from`, or `valid_from > map_revision` (X6) |
| `ALIAS_TEMPORAL_INCOMPLETE` | validator | a non-`active` alias missing `valid_to`, or an `active` alias outside its interval (X6) |
| `NODE_ID_DERIVED` | validator | `node_id` matching any enumerated cheat (eq / casefold / slug(designation) / slug(title) / substring-of-handle / position-path) (X11) |
| `MINTED_BY_SPLIT` | validator | a container with `minted_by:machine` **or** a leaf with `minted_by:human` (H4/A-6) |
| `CLASS_KIND_MISMATCH` | validator | a node whose slot usage contradicts its `node_class` kind (M7) |
| `CLASS_NOT_IN_VOCAB` | validator | a node using a `node_class` that `block_vocabulary` does not declare — incl. the audit repro: undeclared class + per-node `handle_policy` override, which previously validated clean (§0.3 A-1) |
| `POLICY_NOT_IN_VOCAB` | validator | a `handle_policies` key not in `block_vocabulary` (M7) |
| `POLICY_UNRESOLVED` | validator | a used `node_class` with no resolvable policy, or a per-node `handle_policy` override naming an unknown policy (M7) |
| `VOCAB_UNKNOWN_COLLISION` / `VOCAB_EMPTY` / `VOCAB_DUPLICATE` / `VOCAB_UNUSED` | validator | a normalized `block_vocabulary` entry `== "unknown"` / empty-or-whitespace / normalized-duplicate / declared-unused-and-not-reserved (Audit 13, X17) |
| `MAP_OVERWRITE_BLOCKED` | **writer** | `write_structure_map()` over a hand-authored map without explicit-target+snapshot+lineage (M6) |
| `SCHEMA_NOT_BORN` | **born-gate** `assert_schema_born()` (not the validator, not the loader) | a DONE/GATE harness/S8.1 path calls `assert_schema_born()` on a `provisional` schema version (X1/M2) |

**Producer note (P3A-7/I5):** "validator" in the table = the per-module validator (`projection.py`/`handles.py`)
that raises the code directly, **aggregated by** `validate_structure_map`; the code is single-sourced, not raised
independently in two places. `DUPLICATE_NODE_ID` and `ROOT_ID_DANGLING` are **Tier-2a** (short-circuit, §4.1);
all other validator codes are **Tier-2b** (collect-all).

### §4.1.x Invariant battery (each RED first against the stated mutation; the mutation harness runs with `PYTHONDONTWRITEBYTECODE=1` / purges `__pycache__` — X13)

**Stale-`.pyc` discipline (X13).** The B-7 mutation hunt is the sub-second patch→test→revert cycle that defeats
CPython's second-granularity `.pyc` mtime check, serving pre-mutation bytecode → false GREEN hiding a survivor
([[feedback_mutation_pyc_staleness]]). It is **wired, not asserted**: `PYTHONDONTWRITEBYTECODE=1` is set for the
mutation harness (and pinned in `conftest.py`), and every **code**-mutation invariant below (1a, 3, 15, 20, 21,
26, 27) inherits it.

The battery covers (Tier shown per entry — the list is the whole battery, not Tier-2-only, X15/A-5): ownership
(1a/1b), uniqueness (16), atom-ref integrity (17), container/leaf (2 — **Tier-1** `oneOf`), depth (3), identity
(4–7), handles (8/19), aliases (9/18), reference-integrity (14), ordering (27), determinism (20), neutrality
(15/22 — **22 is Tier-1 schema**), regen-guard (21), rebind shape (13/24 — **24 is Tier-1 schema**), empty
container (26), reserved-inert no-reader (25), schema/manifest/stale-class/code-set (10/11/12a/12b/12c), birth
gate (23), vocab hygiene (§4.5).

1. **inv 1a — no double-ownership** → `DUP_OWNERSHIP`. Mutation: place an `atom_id` in two of the four buckets
   (incl. furniture); drop the dedup check → passes, caught.
2. **inv 1b — coverage** → `UNOWNED_INCLUDED_ATOM` / `OWNED_EXCLUDED_ATOM` (H3/H4/X4). Mutation (A): a fixture
   with one unowned *included* atom (from `atom_store.included_atom_ids()`) **must raise**. Mutation (B,
   exemption): an unowned *excluded* furniture atom **passes**. Mutation (C): an *excluded* atom (witness-level,
   `scope_of() != included`) placed in a node's `body_atoms` → `OWNED_EXCLUDED_ATOM` raises.
3. **inv 2 — container/leaf (Tier-1 `oneOf`)** → schema rejects a node with both `children` and `body_atoms`.
   **Filed at S4.4/B-5** with its Tier-1 siblings inv 22/24 (the schema is a B-5 deliverable, P3C-3); at B-2 the
   `projection.py` dataclass enforces container-xor-leaf **by construction** (a node is instantiated as either a
   container or a leaf variant), so no separate B-2 invariant is owed.
4. **inv 3 — ragged depth + heterogeneous siblings** validate; mutation: hard-code a fixed depth → a
   legitimately ragged fixture fails, caught.
5. **inv 4 — `node_id` stable across re-serialize (X7).** Mutation: an impl that **re-derives `node_id` from a
   position index on serialize** → the round-tripped id changes → caught. (Folds with inv 6's seam — the genuine
   non-derivation guard; kept here only as the serialize-axis red.)
6. **inv 5 — `node_id` stable across a positional move (X7).** Mutation: a **position-deriving** impl → two
   arrangements of the same nodes disagree on `node_id` → caught (the same position cheat inv 6 enumerates).
7. **inv 6 — `node_id` rejects the enumerated derivation cheats** → `NODE_ID_DERIVED` (closed list, §3.C.3, X11):
   eq / casefold / slug(designation) / slug(title) / position-path at S4.2; **substring-of-rendered-handle
   re-runs at S4.3** (M-S4.3 + Done-when). Primary control = the arg-free `mint_node_id()` seam.
8. **inv 7 — `minted_by` recorded + split enforced both ways** → `MINTED_BY_SPLIT` (H4/A-6). Mutations: blank
   `minted_by` fails (presence); a container with `minted_by:machine` fails; **a leaf with `minted_by:human`
   fails**. Schema `description` carries "conceptual minting authority" verbatim.
9. **inv 8 — handle renders from `render_handle(map, node_id, policy, target_format, scope)`** with
   ancestor-context + slug-disambiguation cases. Mutation (C-10): corrupt the slug-disambiguation rule → assert
   the exact rendered string changes, caught.
10. **inv 9 — alias survives a handle change**; old value resolves to the same `node_id` as a `status:active`
    alias (hand-authored fixture, §3.D.7). Mutation (C-10): delete the alias → `resolve()` of the old handle
    misses, caught.
11. **inv 10 — schema `const` ↔ `STRUCTURE_MAP_SCHEMA_VERSION`** (two assertions); a bump without refreshing the
    fixture fails.
12. **inv 11 — manifest lists all required versions, each with a stale class** (relation-store `present:false`)
    + the lineage fragment. Mutation (C-10): drop one required version → raise.
13. **inv 12a — stale-class constants (extended, M6):** `STRUCTURE_MAP_STALE_CLASS` and
    `RELATION_STORE_STALE_CLASS` present/exported/distinct from all other classes; **no relation-store loader
    exported from `structure/`** (inertness). **inv 12b — manifest declares `STRUCTURE_MAP_STALE_CLASS`. inv
    12c — the `EC.*` code set in `errors.py` equals the closed set §4.0 enumerates** (the partition test, X14)
    — adding/removing a code without updating the test fails.
14. **inv 13 — `rebind_anchors` optional + `region` shape**; a node with no `rebind_anchors` validates; a
    `{page, bbox_region}` region validates. **inv 24 (H4/M6, Tier-1): the schema REJECTS a `present` or `geom`
    key inside `rebind_anchors`** (`additionalProperties:false`) — mutation: smuggle `rebind_anchors.geom` →
    Tier-1 rejects.
15. **inv 14 — reference-integrity (compound, precedence-pinned — Audit 12, H1, X3/X5/P3A):**
    - **(root id — Tier-2a precondition, short-circuit, §4.1)** `root_id` must name an existing node, **checked
      first**; **the empty map (zero nodes) fails here too** (`root_id` cannot resolve) → `ROOT_ID_DANGLING`. On
      this failure the Z and global-traversal checks **do not run**, so no second root code co-fires (P3A-3/P3A-2).
    - **(local)** every `children` entry resolves (`DANGLING_REF`); **every non-root node appears exactly once
      across the multiset union of all `children` lists** — zero → `ORPHAN_NODE` *(root exempt)*, two parents →
      `MULTI_PARENT`, twice in one list → `DUPLICATE_CHILD_REF`. **An `ORPHAN_NODE` necessarily co-fires
      `MULTIPLE_ROOTS`** (an orphan ∈ Z and the root ∈ Z ⇒ `|Z|≥2`), so the orphan red-test asserts the
      **specific token `ORPHAN_NODE ∈ collected_payload`**, not a bare "raises" (else deleting the orphan check
      is a surviving mutant — the X5 lesson, here for `ORPHAN_NODE` — P3A-4).
    - **(root, total order on the zero-occurrence set `Z`, root_id already resolved — closes the v2 leaf-only
      ambiguity, X3/A-1):** `|Z| == 0` → `NO_ROOT` (fully-parented graph / pure cycle); `|Z| > 1` →
      `MULTIPLE_ROOTS`; `|Z| == 1` → the single node must `== root_id` (**else `MULTIPLE_ROOTS`**) **and** be
      container-kind (**else `NO_ROOT`**). No input triggers two root codes. (A leaf-only map with ≥2 leaves →
      `MULTIPLE_ROOTS`; a single-leaf-as-root → `NO_ROOT`; the empty map is caught earlier at the Tier-2a
      precondition → `ROOT_ID_DANGLING`, not `NO_ROOT`.)
    - **(global)** a traversal **from `root_id`** visits every node exactly once: unvisited → `UNREACHABLE_NODE`;
      an **on-stack** back-edge within the reachable set → `CYCLE`. **A reachable cycle necessarily co-fires
      `MULTI_PARENT`** (the entry node gains a second occurrence), so the cycle red-test asserts the **specific
      token `CYCLE ∈ collected_payload`**, not a bare "raises" (else deleting the on-stack check is a surviving
      mutant — X5); CYCLE's load-bearing job is **traversal termination** on the back-edge. **No
      unvisited-component scan** — a disconnected cycle reports `UNREACHABLE_NODE`. **(LOW)** pin a DAG-diamond
      test yielding `MULTI_PARENT` only (no spurious `CYCLE`).
16. **inv 15 — neutrality (all new modules + schema, M6, C-9):** `projection.py`, `handles.py`,
    `structure_map.py`, `errors.py`, `artifacts.py` **and** `structure/schema/*.json` carry no
    language/book/typeface literal. The scanner **enumerates the live package contents** (a dynamic walk of
    `structure/*.py` + `structure/schema/*.json`, asserted **equal** to the live set — a hard-coded list would
    relocate the M6 single-point failure, C-9); the planted-literal mutation is applied **per enumerated
    module** (or against a freshly-added throwaway module). Fixtures/fixture-generators under `tests/` are
    **exempt** — they are synthetic, intentionally book-shaped test data; the scan is the `structure/` package
    only (E-5). Mutation: plant `"italiano"` (or a `node_class` `enum` of PLL values in the schema) → caught.
17. **inv 16 — `node_id` unique within the map** → `DUPLICATE_NODE_ID` (H2); a **Tier-2a precondition** (§4.1) —
    raised on the second-insert before the keyed table is built, short-circuiting (deliberately exempt from
    collect-all, P3A-5).
18. **inv 17 — atom-ref integrity (H3/X4):** every owned-or-furniture `atom_id` satisfies
    `atom_store.contains()` → else `DANGLING_ATOM_REF`; every node-slot atom is `included` → else
    `OWNED_EXCLUDED_ATOM`.
19. **inv 18 — alias integrity (M3/M10/X6):** active-alias uniqueness enforced **eagerly at load**
    (`ALIAS_COLLISION`) **and** re-guarded at `resolve()` (C-8: a distinct red fixture constructs colliding
    aliases bypassing the validator, calls `resolve()`, asserts `ALIAS_COLLISION` — else removing the resolve
    re-guard survives); every `target_node_id`/non-`global` `scope` resolves (`ALIAS_DANGLING_TARGET`); the
    §3.D.5 temporal rules each fire their own code (`ALIAS_INTERVAL_INVALID`, `ALIAS_TEMPORAL_INCOMPLETE`) with
    a per-rule mutation that **asserts its specific token and isolates** — a `TEMPORAL_INCOMPLETE` fixture uses a
    well-formed interval so `INTERVAL_INVALID` cannot co-fire (P3B-6).
20. **inv 19 — handle-policy resolvability (M7):** `handle_policies` keys ⊆ `block_vocabulary`
    (`POLICY_NOT_IN_VOCAB`); every used `node_class` resolves to a policy and every per-node `handle_policy`
    override names a known policy (`POLICY_UNRESOLVED`); class-kind ↔ slot (`CLASS_KIND_MISMATCH`);
    **every used `node_class` is declared in `block_vocabulary`** (`CLASS_NOT_IN_VOCAB`, §0.3 A-1 —
    mutation: drop the declared-membership check → the undeclared-class-with-override fixture passes
    clean, caught).
21. **inv 20 — determinism (M5/X8):** `dump→load→dump` is byte-identical; `canonical_content_hash` is stable
    under re-serialize and changes under a **content** edit. For geometry: the fixture **synthesizes one
    `Geom.matched(...)` atom** (a real factory, even though `capture.py` emits only `Geom.absent()`), then
    asserts editing its bbox/page changes `canonical_geometry_hash` but **not** `canonical_content_hash`, and a
    text edit the converse. Mutation: swap the hash producer or atom order → fails. (If matched-geom is later
    ruled out of scope, the geometry-edit assertion **defers explicitly to S2.1/S5** — it is not left as a
    green-by-vacuity mutation.)
22. **inv 21 — regen-guard (M6):** `write_structure_map()` over an existing hand-authored map **raises
    `MAP_OVERWRITE_BLOCKED`**; the explicit-target + snapshot + lineage/`map_revision` path **succeeds**.
    Mutation: drop the overwrite check → the overwrite passes, caught.
23. **inv 22 — schema keeps `node_class` open (M6, Tier-1):** the schema's `node_class` is `{"type":"string"}`
    with **no `enum`**; mutation: add a PLL `enum` → caught (also covered by the inv 15 `.json` scan).
24. **inv 23 — birth gate (M4/X1/X10):** the S4.5 differ-fixture **shape- and semantically-validates** through
    the born-agnostic `load_structure_map`, and the test asserts, **as two unconditional asserts**, `assert
    differ_validates` **and** `assert schema_status[current] == born`. The reverse-direction red is a **named
    mutation**: drop a required Node field from `differ_structure_map.json` (or inject one
    `UNOWNED_INCLUDED_ATOM`) → assertion 1 reddens. The negative `SCHEMA_NOT_BORN` red **monkeypatches
    `schema_status[current] = provisional`** and asserts **`assert_schema_born()`** (not the loader) raises;
    `assert_schema_born()` reads `schema_status[schema_version_const()]` (P3A-6). A **missing** `schema_status`
    key is fail-safe — its own named mutation: **delete the key** (or query an unknown version) → `assert_schema_born()`
    treats it as provisional and raises (P3B-11). The differ-fixture **must not be regenerated by the path it
    validates**.
25. **inv 25 — reserved-inert `decision` no-reader (X9/E-1):** a static check that **no module in `structure/`
    reads the `decision` field/key** — by **AST access-pattern matching** (a `Subscript`/`Attribute`/`.get(
    "decision")` access), **not bare substring** (which false-positives on comments/docstrings), exempting
    comments/docstrings and the schema `.json` that legitimately defines the property (P3B-7); the same no-reader
    binding form inv 12a uses for `RELATION_STORE_STALE_CLASS`. Plus a schema-presence positive (a conforming
    fixture carrying `decision` validates). Mutation: add a `node["decision"]` read in `structure_map.py` →
    caught.
26. **inv 26 — empty-container rejection (X3, P3B-9):** a container with zero `children` and no
    `heading_atoms`/`signature_atoms` raises `EMPTY_CONTAINER`. **The check is a pure projection-model rejection
    (no atom_store), so it is a Phase-1 `projection.py` invariant at S4.1/B-2** (alongside inv 27); its dedicated
    negative fixture is authored with the B-5 `invalid/*.json` set. Mutation: drop the empty-container check →
    the empty container passes, caught.
27. **inv 27 — `body_atoms` strict ordering (X16):** a `body_atoms` list out of ascending canonical-stream
    order, or with an intra-list duplicate, raises `BODY_ATOMS_UNORDERED`. The validator checks `node.body_atoms`
    **as-stored** (it must **never** `sorted()`-copy first, or it re-introduces the vacuity, P3B-3). Mutation:
    permute/duplicate a `body_atoms` entry → caught (inv 20 cannot, because §3.E.1 re-sorts before hashing on a
    different object — the canonical stream, which never reads `body_atoms`).

### §4.3 ResourceLineage contract test (R2-06); §4.4 complexity smoke; §4.5 vocab hygiene
- **§4.3** a live `ResourceLineage(...).to_json()` validates against the schema; a `lineage.py` shape change
  fails.
- **§4.4 Complexity smoke (Audit 17, hardened — X12).** Over a few-thousand-node synthetic flat table,
  reference-integrity does **no per-reference full-tree scan**. The `node_id` table **and the child lists** are
  reachable **only** through the **instrumented accessor** owned by the validation context (§3.E.10) —
  `context.ref_ops` increments at every node **and child-list element** access (including index/precompute and
  list membership, so the classic O(n²) `if node in parent.children` cannot bypass the counter, X12). The
  **two-size ratio assertion is mandatory** (not optional): assert `ref_ops(2n)/ref_ops(n) ≈ 2` (sub-linear),
  not `≈ 4`. This is a **heuristic floor**, not an impossibility proof; S4.7 owns the 10⁵ timing/memory
  measurement (a minimal real op-count ratio may be pulled forward as the actual quadratic catch).
- **§4.5** vocab hygiene → `VOCAB_*` (Audit 13, normalized exact-match, §3.E.7/X17).

### Done-when → proof map
- **S4.0** → inv 12a, 12c, 15
- **S4.1** → inv 1a, 1b, 3, 15, 16, 26, 27 (+ §3.B.0 root, §3.B.6 ordering) — inv 26 is a pure projection
  rejection (P3B-9); inv 2 moves to S4.4 (Tier-1 schema, P3C-3)
- **S4.2** → inv 4, 5, 6 (designation/slug/position cheats), 7
- **S4.3** → inv 6 (rendered-handle cheat), 8, 9, 18, 19, 15
- **S4.4** → inv 2, 10, 11, 12b, 13, 14, 17, 20, 21, 22, 24, 25, 15 + §4.2 read-path + §4.3 contract + §4.4
  smoke + §4.5 hygiene + §3.E.8 regen-guard + the §3.B.5 negative-fixture set (incl. inv 26's empty-container
  fixture)
- **S4.5** → inv 23 (`assert_schema_born()` → `schema_status` `provisional`→`born`)

---

## 5. Build order (red-first, two-phase — §4.2)

- **B-1 — Constants + codes (S4.0/M-S4.0):** `STRUCTURE_MAP_STALE_CLASS` + pre-placed
  `RELATION_STORE_STALE_CLASS` + the `schema_status` module map + the closed **`EC.*` set in
  `structure/errors.py`** (so B-2 onward can assert on codes); red-first inv 12a/12c (constant+code-set) + inv
  15 (artifacts.py, errors.py). *Decision-owned by D-S4-F (M11).*
- **B-2 — S4.1 projection model** (`projection.py`): dataclasses + root spec + ownership/coverage/uniqueness +
  flat-table/children-only + ordering + empty-container rejection; inv 1a, 1b, 3, 15, 16, 26, 27 — **Phase-1 red
  tests directly against the dataclass validators** (§4.2). (Container-xor-leaf is enforced by the dataclass
  variant by construction; the Tier-1 `oneOf` red test, inv 2, is at B-5.)
- **B-3 — S4.2 identity:** `node_id` + `minted_by` + `mint_node_id()` seam; inv 4–7 (designation/slug/position
  cheats) — Phase-1 direct.
- **B-4 — S4.3 handles + aliases** (`handles.py`): `render_handle()` + alias record + resolve + eager
  uniqueness + policy resolvability + temporal rules; inv 6 (rendered-handle clause), 8, 9, 18, 19, 15 — Phase-1
  direct (inv 15 re-runs as `handles.py` appears, P3C-5).
- **B-5 — S4.4 schema + manifest** (`structure/schema/structure_map.schema.json`, `structure_map.py`): the Node
  schema (§3.J), two-input `validate_structure_map(map, atom_store)`, born-agnostic `load_structure_map`,
  `assert_schema_born()`, evolve the generator → conforming + author the `invalid/*.json` negative set, manifest
  assembly + `schema_version_const()` + regen-guarded `write_structure_map()`; inv 2, 10, 11, 12b, 13, 14, 17,
  20, 21, 22, 24, 25, 15 + §4.2–4.5. **Phase-2: re-route every Tier-2 invariant through `load_structure_map`**
  (the wiring proof). **When the schema file lands, extend the S0.2 neutrality scan
  (`test_structure_neutrality.py`) from `*.py`-only to also glob `structure/schema/*.json`** — inv 15's stated
  scope (`structure/*.py` + `structure/schema/*.json`) and inv 22's "a PLL `node_class` `enum` in the schema"
  mutation both depend on `.json` coverage that the B-1 scan does not yet provide (B-1 audit F4).
- **B-6 — S4.5 differ-fixture birth gate:** author the **conforming** `differ_structure_map.json`; it shape- +
  semantically-validates through the born-agnostic loader; **a human edit flips `schema_status`→`born`** (the
  ratification act, §1.2.2), and the test (inv 23) **asserts** — as two unconditional asserts — that the
  differ-fixture validates **and** `schema_status[current]==born`. The test does not itself mutate the status.
  **Closes the milestone.**
- **B-7 — Checkpoint → PAUSE → pre-commit adversarial audit → dispositions → apply → commit → close the
  S4.0–S4.5 issues.** The mutation hunt runs with `PYTHONDONTWRITEBYTECODE=1` / `__pycache__` purge (X13).
  Issues = tracker bookkeeping, minted at wave-start, closed per commit; the proof is the green battery + the
  audit (R2-13).

---

## 6. Rulings (O1–O5, settled 2026-06-30)
- **O1 — pre-place `RELATION_STORE_STALE_CLASS`** (inert + `present:false`) — D-S4-F.
- **O2 — schema at `structure/schema/`**; helper inlined now, factored at S7.1c — D-S4-G.
- **O3 — `node_id` properties-only**; counter+ULID fixture default — D-S4-C.
- **O4 — `rebind_anchors` optional** (absence first-class; freezable later) — D-S4-H.
- **O5 — fold S4.5 into the keystone** — D-S4-A, §1.2.

---

## 7. Provenance & durable references
Code-evidence anchor **`d611702`** (verified byte-identical to current code by three pass-2 reviewers):
`structure/artifacts.py`; `structure/lineage.py` (`to_json`, `_canonical`, `_sha256_bytes`);
`structure/atom_store.py` (`AtomStream`); `structure/capture.py` (`build_canonical` aligns only `included`
atoms; `geom=Geom.absent()`); `structure/atoms.py` (`Geom.matched()` factory); `structure/classify.py`
(`UNKNOWN == "unknown"`; frozen `BlockClassification`); `structure/typed.py` (frozen `TypedAtom`);
`config/schema/manifest.schema.json`; `tests/fixtures/_generate_structure_fixture.py`;
`tests/unit/test_structure_artifacts.py`; `books/synthetic/`. Spec: PLAN §3.1–§3.6, §11.2. **Audit trail —
the inline fix-maps §0 / §0.1 / §0.2 are authoritative and self-contained;** the following are supplementary
artifacts **committed alongside this plan** (so the references stay durable, P3): `s4_plan_discussion.md` (six
rounds), `s4_plan_pass2_findings.md` (second pass). **Durable rules (inlined where load-bearing, R2-14):**
`docs/invariants.md`
— I3 port-fidelity, I4 core-separability/neutrality, I5 wire-protocol single-sourcing, I7 write-containment, I8
atomicity, I9 determinism; `docs/port_discipline.md`.

---

## 8. Acceptance checklist (this plan's distillation gate — R2-01)

- **§8.1** Every actionable claim carries a stable id. ☐ verify at audit.
- **§8.2** Every carried audit/follow-up block maps to **≥1** id. Crosswalk below.
- **§8.3 Tracker-wording changes required** (anchor by **row identity**, not line number — R2-03):
  - **New S4.0 row** — create **S4.0 (constants + error-code module)**; move
    `STRUCTURE_MAP_STALE_CLASS`/`RELATION_STORE_STALE_CLASS`/`schema_status` **and** the `EC.*` code module out
    of the S4.4 row (X18). **Issue↔row mapping (P3C-6):** wave issues **S4.0–S4.5 ↔ tracker rows S4.0–S4.5**
    (one-to-one); rows **S4.6 and S4.7 are forward** (§1.4 — HITL container map / scale check) and carry **no**
    wave issue; the sidecar engine-half is its own forward row (below).
  - **S4.5 row** — "relation-endpoint **resolution**" → "**shape / reference placeholders**"; reserve
    "resolution" for S7/S9.4. Also "stale-manifest failure" → "malformed/incomplete-manifest rejection" (M9).
  - **S4.1 row** — "B can **re-atomize** and re-type" → "B **re-groups / re-types at the node level**"; true
    re-atomization → **S8.2/D25** (Audit 10).
  - **S8.2 row** — extend scope from atom re-atomization to **L2 node retirement/identity** (§3.B.7, M10).
  - **S4 milestone / S4.5 row** — record S4.5 as the **closing birth gate of the S4 keystone** (folded, O5).
  - **New forward row** — the **authoring-evidence sidecar engine half** (`structure/evidence.py`: schema +
    digest-staleness validator), engine owner, **scheduled immediately before S4.6** (predecessor S4.4, inherits
    inv 15 + a digest-staleness red test) (§1.4.1c, M9/X20).
- **§8.4** Ratification mints the S4.0–S4.5 issues (bookkeeping); O1 struck from any open-fork list (Audit 1).

### Audit-block → plan-id crosswalk (R2-01 §8.2)

The first-pass blocks (R2-NN / Audit NN) and their landing ids are below; the second-pass findings (X1–X20 +
LOW) land per the §0.1 fix-map.

| Block | Lands at | Block | Lands at |
|-------|----------|-------|----------|
| R2-01 | §8 | Audit 1 | D-S4-F, O1 |
| R2-02 | §1.5 + amendment rule | Audit 2 | §1.2.2/§1.2.3, §3.D.6 |
| R2-03 | §8.3, §1.2 | Audit 3 | §2.3, §3.E.5 |
| R2-04 | §1.3.2, §1.3.3 | Audit 4 | inv 12a/12b, B-1 |
| R2-05 | §2 header, §7 | Audit 5 | §3.C.3 |
| R2-06 | §2.2, §4.3 | Audit 6 | §3.D.2, §3.D.6 |
| R2-07 | §3.B.2 | Audit 7 | §3.D.4 |
| R2-08 | §3.C.2 | Audit 8 | §3.D.5 |
| R2-09 | §3.D.3 | Audit 9 | inv 1a/1b, §3.B.1 |
| R2-10 | §3.E.1 | Audit 10 | §1.3.5, §3.B.3, §8.3 |
| R2-11 | §4, §4.0, §4.1 | Audit 11 | §2.7, D-S4-H, inv 13/24 |
| R2-12 | §4.2 | Audit 12 | §3.B.4, inv 14 |
| R2-13 | B-7 | Audit 13 | §3.E.7, §4.5 |
| R2-14 | §7 | Audit 14 | §1.3.4 |
| | | Audit 15 | §1.4.1a/b/c |
| | | Audit 16 | §3.E.8, inv 21 |
| | | Audit 17 | §3.B.4, §4.4 |
