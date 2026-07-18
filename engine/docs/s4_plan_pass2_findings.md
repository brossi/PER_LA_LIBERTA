# S4 plan — second-pass adversarial audit (findings)

Status: **PASS-2 FINDINGS — APPLIED to `s4_plan.md` v3 (see its §0.1 fix-map); open to Ben's review/revert.**
All X1–X20 + the LOW roll-up were folded into v3 with the dispositions recommended below (X7/X8/X9 applied at
my-read MED; X19 folded into X14). The disposition cells are left as the original recommendations — v3's §0.1 is
the authoritative record of what landed and where. Target of the audit: `s4_plan.md` v2 (distilled keystone plan,
HEAD `bac3a29`). Method: six independent read-only reviewers (A–F), deliberately overlapping lenses, re-aimed
at the **v2 remediation delta** per the adversarial-audit cadence (Rule A: a pass certifies only the bytes it
saw — re-audit the fixes themselves; Rule B: wide + narrow apertures on the delta). Convergence (≥2 reviewers,
independent lenses) = act; lone-lens = verify-then-act.

Reviewer lenses: **A** cross-reference & fix-map fidelity · **B** error-code/invariant completeness · **C**
red-first/mutation rigor · **D** two-tier boundary & H3 signature ripple · **E** scope-boundary & neutrality ·
**F** build-order & DoD soundness.

**Adjudication:** drop `@@@@@@`/`======` blocks inline per finding (or against the cluster headers in §2). The
"Disposition" column is left blank for your ruling (ACCEPT / REJECT / DEFER / MODIFY).

---

## 0. What held (clean dimensions — corroborated)

These were probed and found sound; recorded so the delta is auditable and we don't re-litigate them.

- **Code-anchor fidelity — clean (3 reviewers: C, D, E).** `git diff --stat d611702 HEAD -- engine/src
  engine/tests` is empty (the 6 commits since the anchor are docs-only). Every cited code fact holds:
  `lineage._sha256_bytes`/`_canonical` exist (sort_keys, fixed separators, `ensure_ascii=False`);
  `STRUCTURE_MAP_SCHEMA_VERSION`/`RELATION_STORE_SCHEMA_VERSION` present, `STRUCTURE_MAP_STALE_CLASS` absent
  ("the one real code gap"); `classify.UNKNOWN == "unknown"`; `BlockClassification`/`TypedAtom` frozen (L1
  immutable); `Geom.matched()` is a real factory though `capture.py:162` emits only `Geom.absent()`; the four
  to-be-built symbols (`schema_status`, the two stale classes, `SCHEMA_NOT_BORN`) do not yet exist.
- **Export-signature ripple (H3) — clean (A, D).** `validate_structure_map(map, atom_store)` is two-input at
  every operative occurrence; `load_structure_map(path, atom_store)`, `render_handle(map, node_id, policy,
  target_format, scope)`, `schema_version_const(schema)`, `write_structure_map()` all consistent. The lone
  one-arg `validate_structure_map(map)` (line 27) is the §0 fix-map quoting the *old* form H3 closed — correct.
- **Fix-map fidelity (§0) — clean except H1 (A).** Every H1–H4/M1–M11/LOW target resolves and delivers — except
  H1's "inv 14 reworded" landed but is internally broken (A-1, below).
- **Done-when proof map ↔ §1.5 matrix — row-for-row identical (A, F).** The mismatch is *not* in row-matching;
  it is in dependency-*timing* (invariants filed to a step whose producer doesn't exist yet — F-1 cluster).
- **EC-table ↔ invariant coherence — clean except the A-4 mislabel (A).** No invariant cites an absent code;
  every code is fired by some invariant.
- **D10/D33 substrate, neutrality of core requirements — clean in substance (E).** `node_id` persisted/never
  recomputed; parent derived; no L1-mutation path in any S4 deliverable; the root spec is structural with
  "(PLL adds…)" correctly marked illustrative; the differ-fixture exists precisely to prove non-PLL shapes.

---

## 1. Disposition summary (all findings)

Severity shown as **reviewer-rated** (with *my read* where I differ, with reason in the detail section).

| ID | Sev | Converge | One-line | Lands in s4_plan.md | Disposition |
|----|-----|----------|----------|---------------------|-------------|
| **X1** born-gate bootstrap | HIGH | **D-1 + F-2** | `load_structure_map` can't both gate `born` and host the B-5 battery → deadlock | §1.2.2/3, §4.0 SCHEMA_NOT_BORN, inv 23, §1.5 | |
| **X2** red-first chain | HIGH | F-1 (+A,F Done-when) | §4.2 "route through `load_structure_map`" makes B-2/3/4 red tests depend on the B-5 loader/validator/EC-set | §4.2, §5, Done-when map | |
| **X3** degenerate-shape / differ-fixture | HIGH | **B-1 + A-1 + A-2 + F-6 + F-7** | one validating fixture can't also be the rejection battery; inv 14 leaf-only is self-contradictory; empty-container + non-container-root have no code | §3.B.5, inv 14, §4.0, §1.2, §1.5 M-S4.5 | |
| **X4** furniture/excluded atoms | HIGH | **B-4 + D-2 + E-2** | validator can't see excluded atoms (witness-level); no disjointness code; furniture field named `role` collides w/ deferred S6 axis | §3.B.1, inv 1b/17, §4.0, §3.J, §4 header | |
| **X5** CYCLE co-fires | MED | **B-7 + C-3** | `root→A→B→A` always also fires MULTI_PARENT → deleting the cycle check is a surviving mutant under bare-`raises` | §4.0 CYCLE, inv 14 | |
| **X6** temporal alias rules | HIGH | B-2 | 4 §3.D.5 rules bundled behind inv 18 "+ temporal rules"; no code, no per-rule mutation | §3.D.5, inv 18, §4.0 | |
| **X7** inv 4/5 vacuous | HIGH→*MED* | C-1 (+F-11) | no red mutation; inv 5 compares author-supplied literals (no move API in S4) | inv 4/5, §3.C.1 | |
| **X8** inv 20 geometry vacuity | HIGH→*MED* | C-2 | geometry-hash "change under geom edit" unproducible (all `Geom.absent()`) | inv 20, §3.E.1 | |
| **X9** `decision` inertness prose-only | HIGH→*MED* | E-1 | claims parity with `RELATION_STORE_STALE_CLASS` but got no no-reader invariant | §1.4.1, §3.J | |
| **X10** inv 23 lying-constant relocated | MED | C-7 (+born cluster) | "born iff validates" coded literally is green in provisional∧broken | §1.2.2, inv 23 | |
| **X11** inv 6 cheat set + S4.3 re-run | MED | **C-5 + F-3** | "known-transform" open-ended; rendered-handle re-run not in any matrix/Done-when home | §3.C.3, inv 6, M-S4.3 | |
| **X12** §4.4 smoke defeatable | MED | C-4 (+F-10) | quadratic occurrence-check via list membership = 0 ref_ops; non-escape untestable | §4.4 | |
| **X13** stale-`.pyc` guard unwired | MED | C-6 | "purge __pycache__" asserted once, wired nowhere (conftest has none) | §4.1.x header, B-7 | |
| **X14** EC.* module + negative fixtures homeless | MED | **F-8 + F-7 + B-6** | closed code module & rejection fixtures have no §1.5 row; collect-all vs writer/load-gate partition unstated | §1.5, §4.0/§4.1 | |
| **X15** loader Tier-1→Tier-2 ordering | MED | D-4 (+D-5,A-5) | `load_structure_map` contract (parse→Tier-1→Tier-2) unstated; Tier-1 invs' route undefined | §4.2, §4.1.x | |
| **X16** body_atoms ordering unpinned | MED | B-3 | strict-ascending "must" has no code/invariant; hash re-sorts so inv 20 can't catch | §3.B.6, §4.0 | |
| **X17** vocab near-dup/whitespace | MED | B-5 | fuzzy near-dup has no metric/code; whitespace folded into "empty" without its own mutation | §3.E.7, §4.0 VOCAB | |
| **X18** §8.3 missing S4.0 tracker row | MED | F-9 | M11 promoted constants to S4.0 but §8.3 adds no row; issue-set S4.0–5 vs rows S4.1–7 unreconciled | §8.3, header | |
| **X19** producer/collect-all partition | MED | B-6 | "closed set" + "collects all in one pass" conflated; writer/load-gate codes aren't collected | §4.0/§4.1 | |
| **X20** sidecar engine-half under-specified | MED | E-3 | forward row has no module/exports/tests/inv-15 binding; "with/before S4.6" no ordering | §1.4.1c, §8.3 | |
| **L*** LOW roll-up (15) | LOW | various | A-3,A-4,A-5,A-6,B-8,B-9,C-8,C-9,C-10,D-3,D-5,D-6,E-4,E-5,E-6,E-7 | inline (§4) | |

---

## 2. Convergent clusters (≥2 reviewers — act)

### X1 — Born-gate ↔ `load_structure_map` bootstrap deadlock (HIGH; D-1 + F-2)

**Two lenses, one finding.** §4.2 routes *every* semantic invariant red-test "through the public
`load_structure_map`"; §1.2.3 raises `SCHEMA_NOT_BORN` "at the load/harness gate"; inv 23 says "a **load**
against a `provisional` schema version raises `SCHEMA_NOT_BORN`." But `schema_status` is `provisional` through
B-1…B-5 and only flips at B-6. If `load_structure_map` is the gate, every B-5 invariant test short-circuits on
`SCHEMA_NOT_BORN` before its assertion — and inv 23 itself can't reach its positive branch (validating-while-
provisional is what *causes* the flip). Circular. If `load_structure_map` is born-agnostic (required for B-5 to
pass), then the only named `SCHEMA_NOT_BORN` producer is out-of-wave (S6/S7/S8.1) and inv 23's negative clause
has no in-wave producer and no §1.5 matrix home.

**Recommended fix (both reviewers agree):** state `load_structure_map` is **born-agnostic** (the read path
never checks `schema_status` — it runs Tier-1 + the semantic validator only); add a **separate, matrix-homed**
born-gate export (e.g. `assert_schema_born()` in `structure_map.py`, on M-S4.4) that inv 23's negative test
calls directly; reword inv 23 "a load … raises" → "**the born-gate** … raises."

> Disposition:

### X2 — The §4.2 "route through `load_structure_map`" red-first chain contradiction (HIGH; F-1)

The plan promises a linear red-first chain B-2→…→B-5 (D-S4-A: "each a red-first checkpoint"), but §4.2 forbids
testing the validator directly ("not by calling the public validator directly") and `load_structure_map` +
`validate_structure_map` + the closed `EC.*` set are all **B-5** deliverables. So every B-2/B-3/B-4 semantic
invariant (1a, 1b, 16, 6, 7, 18, 19 — all Producer=validator) has no sanctioned test route and no error code
to assert on until B-5. The chain is not linear; B-2…B-4's semantic DoDs are back-loaded onto B-5.

**Recommended fix:** adopt an explicit **two-phase posture** — B-2/B-3/B-4 red-test the per-module validators
**directly** against in-memory dataclasses (soften §4.2 to permit the direct route pre-B-5), and B-5 adds a
re-route layer that re-asserts each through `load_structure_map` (the wiring proof). Make §4.2, §5, and the
Done-when map agree. (This is the same root as X1 — both are "the loader/validator is a B-5 thing but earlier
steps depend on it." Resolve them together.)

> Disposition:

### X3 — Degenerate-shape rulings & the overloaded differ-fixture (HIGH; B-1 + A-1 + A-2 + F-6 + F-7)

Five reviewers converge on a broken negative-case story:

- **A-1 (the H1 remediation's own bug):** inv 14's reworded local rule has a leaf-only map with ≥2 nodes
  satisfying **both** "leaf-only → `NO_ROOT`" **and** ">1 zero-occurrence node → `MULTIPLE_ROOTS`" — the two
  §4.0 rows collide on identical input, and they are semantically opposite. The core validator is
  non-deterministic on this input. *(Verified against lines 457–459.)*
- **B-1 + A-2 (gaps with no code):** an **empty interior container** (referenced once, `children: []`, no
  heading/signature atoms) passes every gate — no `EC.*` fires it. A **non-container / single-leaf root** passes
  every topological check but §3.B.5 says it must be `NO_ROOT` — nothing fires it.
- **B-1 + F-7 (structural contradiction):** §3.B.5 says these rejections are "pinned by the S4.5
  differ-fixture," but inv 23 requires that fixture to **validate** (to flip `born`). **One JSON file cannot
  simultaneously validate and be malformed/empty/leaf-only.** The rejection fixtures are real artifacts with no
  §1.5 M-S4.5 home.
- **F-6 (triple-booked):** the same degenerate rulings are filed to S4.1 (Done-when), S4.4 (inv 14 producer),
  and S4.5 (differ-fixture) at once.

**Recommended fix:** (a) make inv 14's zero-occurrence-set rule a **total order on set size** — 0 → `NO_ROOT`;
>1 → `MULTIPLE_ROOTS`; exactly 1 → must `== root_id` *and* be container-kind else the appropriate code; drop
"leaf-only" from the `NO_ROOT` trigger. (b) Add `EC.EMPTY_CONTAINER` + an invariant; add a non-container-root
check firing `NO_ROOT`. (c) Separate the **passing** generalization fixture (born gate, inv 23) from a named set
of **negative** fixtures (empty / leaf-only / empty-container / non-container-root / malformed-manifest /
alias-collision), and give the negatives a §1.5 home (their own M-S4.4 mutation fixtures or an M-S4.5 negative
set). (d) Assign the rejection tests to S4.4 (where the codes fire); let S4.5 only re-exercise them.

> Disposition:

### X4 — Furniture / excluded-atom handling (HIGH; B-4 + D-2 + E-2)

Three facets of one weak region:

- **B-4 (no disjointness code):** inv 1b iterates only *included* atoms (forward coverage). An *excluded*
  (`processing_scope="excluded"`) atom smuggled into a node's `body_atoms`, an atom in **both**
  `furniture_atoms` and a node, or a dangling `furniture_atoms` entry — none is caught (`DUP_OWNERSHIP` is
  "two ownership *slots*"; furniture isn't a slot; inv 17 checks owned-only).
- **D-2 (code-grounded — the H3 fix is insufficient as typed):** `build_canonical` (capture.py:234–235) aligns
  **only** `included` atoms, so the canonical stream contains no excluded atoms — they live only in **witness**
  streams. The `(map, atom_store)` second input, typed as a single canonical `AtomStream`, **cannot supply** the
  excluded atoms inv 1b's exemption-mutation (B) needs. The type label is also ambiguous ("canonical atom
  store/`AtomStream`" — there is no aggregate `AtomStore` class; a *witness* stream is also an `AtomStream`).
- **E-2 (naming/seam):** §1.3.4 says "schema **OMITS `role` entirely**" yet §3.J's header field is
  `furniture_atoms[{atom_id, role}]` — a key literally named `role`, colliding with the deferred-to-S6 read-axis
  and diverging from the code's term `capture_provenance_class`.

**Recommended fix:** pin the second input's concrete type (a mapping of all streams the map references, or an
explicit "furniture validated map-internally, no witness resolution" scope); add `EC.OWNED_EXCLUDED_ATOM` +
furniture-as-fourth-mutually-exclusive-bucket cross-checks with mutations for the three uncaught cases; rename
the furniture field `capture_role` and scope §1.3.4's claim to node-level `role`.

> Disposition:

### X5 — CYCLE necessarily co-fires MULTI_PARENT (MED; B-7 + C-3)

In the children-once model, `root→A→B→A` makes A appear in both `root.children` and `B.children` → 2
occurrences → `MULTI_PARENT` fires alongside `CYCLE`; a disconnected cycle routes to `UNREACHABLE_NODE`. So
`CYCLE` can never fire in isolation, and **deleting the on-stack back-edge check is a surviving mutant** if the
cycle test asserts only "load raises" (MULTI_PARENT still raises → false green). The plan guards only the
reverse (the diamond test pins "MULTI_PARENT only").

**Recommended fix:** require the cycle red-test to assert the **specific token** `CYCLE ∈ collected_payload`
(the collect-all model allows this); document that a reachable cycle co-fires `MULTI_PARENT`/`NO_ROOT`; pin
CYCLE's real load-bearing job (traversal **termination** on a back-edge); and surface as a design question
whether CYCLE earns a distinct code at all (it may be subsumed by `MULTI_PARENT ∪ UNREACHABLE_NODE`).

> Disposition:

### X11 — inv 6 derivation-cheat set open-ended + S4.3 re-run ungated (MED; C-5 + F-3)

"rejects … known-transform" is unfalsifiable (any un-enumerated transform — base64, reversed slug, hash-of-
title — passes). And the rendered-handle cheat "re-runs @S4.3" is prose only: the S4.3 Done-when lists inv
8/9/18/19/15, **not** inv 6 — an acceptance test with no matrix home (amendment-rule gap).

**Recommended fix:** replace "known-transform" with an explicit **closed** transform list (exact-eq, casefold-
eq, slug(designation), slug(title), substring-of-rendered-handle, position-path), one red fixture each; name the
arg-free `mint_node_id()` seam as the PRIMARY control; add inv 6's rendered-handle clause to the S4.3 Done-when
+ M-S4.3 acceptance column.

> Disposition:

### X12 — §4.4 complexity smoke is defeatable (MED; C-4 + F-10)

A quadratic impl passes: the classic O(n²) occurrence check via `if node in parent.children` over plain lists
touches the counter **0 times** (list membership never increments `ref_ops`) — and that is exactly inv 14's
shape. "No raw dict/list handle escapes" is a code-review aspiration, not runtime-testable. The accessor
constraint is also a production-code requirement surfaced only in test prose (F-10).

**Recommended fix:** make the two-size ratio assertion **mandatory** (assert `ref_ops(2n)/ref_ops(n) ≈ 2`);
instrument **children-list element access**, not just the node table; reword §4.4 to drop the "impossible"
framing (state it as a heuristic floor); surface the instrumentable-accessor constraint in M-S4.4/D-S4-E;
consider pulling a minimal real op-count/timing ratio forward from S4.7.

> Disposition:

### X14 — Closed `EC.*` module & negative fixtures are homeless; collect-all vs writer/load-gate unpartitioned (MED; F-8 + F-7 + B-6)

The closed `EC.*` set is "declared in one module" (consumed by validator, writer, born-gate, and S8.1) but no
§1.5 row lists it; its build step is unstated, yet B-2/B-3/B-4 mutations assert on its codes (compounds X2).
Separately, §4.1 says the validator "collects all semantic failures in one pass" while §4.0 assigns
`MAP_OVERWRITE_BLOCKED` to the **writer** and `SCHEMA_NOT_BORN` to the **load-gate** — two codes never collected
by the validator, so §4.2's universal "every semantic invariant routes through `load_structure_map`" overreaches
(inv 21 is a write path; inv 23 is a load-gate). The partition `EC.* = {validator-collected} ⊎ {writer} ⊎
{load-gate}` is never stated.

**Recommended fix:** add the `EC.*` code module as an explicit export (on M-S4.0 `artifacts.py` so it predates
B-2's first code reference, or a new `structure/errors.py` row); state the three-way producer partition in
§4.0/§4.1; scope §4.2's "every" to validator-collected invariants and carve out inv 21/inv 23.

> Disposition:

---

## 3. Lone-but-verified findings (single lens; verified against plan/code — act)

### X6 — §3.D.5 temporal alias rules have no code and no per-rule mutation (HIGH; B-2)

The four rules (`valid_from ≤ current`; `valid_to` null or `≥ valid_from`; non-active must carry `valid_to`;
active within interval) are bundled behind inv 18's "+ the §3.D.5 temporal rules" — §4.0 has only
`ALIAS_COLLISION`/`ALIAS_DANGLING_TARGET`, neither temporal. A hand-authored alias with `valid_to < valid_from`
or a `retired` alias with null `valid_to` validates clean, then `resolve(at_revision=N)` is undefined.
**Fix:** add `EC.ALIAS_INTERVAL_INVALID` + `EC.ALIAS_TEMPORAL_INCOMPLETE`, each with a red-first mutation; or
enumerate one code per rule in §4.0 + a mutation per rule in inv 18.

> Disposition:

### X7 — inv 4 / inv 5 are vacuous (HIGH reviewer / *MED my read*; C-1 + F-11)

inv 5 ("stable across a positional move") has no move API in S4, so it compares two author-supplied `node_id`
literals — asserts its own literal; no engine transform can break it. inv 4 ("stable across re-serialize") is a
free JSON string round-trip (D33: node_id is stored, never recomputed). *My read MED not HIGH:* these are weak
checks, not data-integrity holes, and the genuine non-derivation guard already lives in inv 6 + the §3.C.3
seam — the fix is cheap. **Fix:** delete the standalone literal-compares; fold the re-serialize + positional
axes into inv 6's seam fixture (which already "mutates designation, position, and content with the id fixed"),
or name a concrete re-deriving mutant for each.

> Disposition:

### X8 — inv 20 geometry-hash mutation is unproducible (HIGH reviewer / *MED my read*; C-2)

Every atom is `Geom.absent()` (capture.py:162), so "the two hashes change under a content/**geometry** edit"
has no geometry field to edit — the `canonical_geometry_hash` half passes green un-exercised (the §3.E.1 caveat
admits it). *My read MED:* it's a partly-vacuous check, fixable cheaply. **Fix:** mandate the determinism
fixture synthesize one `Geom.matched(...)` atom (a real factory, constructible in a test even though
`capture.py` never emits it) and assert content/geometry hash independence both ways; split inv 20 so the two
hashes carry distinct red-first statuses; if matched-geom is ruled out of scope, explicitly **defer** the
geometry-edit assertion to S2.1/S5 rather than leaving a green-by-vacuity mutation listed.

> Disposition:

### X9 — `decision` enum inertness is prose-only (HIGH reviewer / *MED my read*; E-1)

§1.4.1/§3.J claim `decision`'s inertness is "pinned by a test that no S4 code reads it — consistent with
`RELATION_STORE_STALE_CLASS`." That parity is false: M6 promoted the relation constant's inertness into inv 12a
(the no-reader binding), but `decision` got no inv id, no §4.1.x row, no Done-when entry. The plan asserts a
binding it does not have. *My read MED not HIGH:* it's a missing test-binding (and an internal-consistency
defect), not a validator gap that admits bad data — but it does break the plan's own §8.1 "every claim carries a
stable id" discipline, and the asymmetry with the M6 fix is the kind of thing pass-2 exists to catch. **Fix:**
mint a no-reader invariant for `decision` (same form as inv 12a) + a schema-presence positive; add to M-S4.4
Done-when.

> Disposition:

### X10 — inv 23 "born iff validates" relocates the lying-constant (MED; C-7)

Coded literally as `(status==born)==validates`, the biconditional is GREEN in the **provisional∧broken**
quadrant — someone can park S4 green-but-unborn by honestly flipping the constant to `provisional` while the
fixture is broken. The reverse direction (regression⇒red) names no concrete mutation; the `SCHEMA_NOT_BORN`
negative needs a simulated-provisional state that's unspecified. **Fix:** pin the assertion **form** as TWO
unconditional asserts (`assert validates` AND `assert schema_status[current]==born`), not a bare biconditional;
name the reverse mutation (drop a required Node field from `differ_structure_map.json`); specify the
`SCHEMA_NOT_BORN` simulation (monkeypatch `schema_status[current]=provisional`, assert the gate raises); state
the differ-fixture must not be regenerated by the path it validates. (Resolve with X1.)

> Disposition:

### X13 — stale-`.pyc` mutation guard is unwired (MED; C-6)

"mutation pass purges `__pycache__`" appears only in `.gitignore` + the plan docs; `conftest.py` has no cache
handling. B-7's mutation hunt is exactly the sub-second patch→test→revert that defeats CPython's
second-granularity `.pyc` mtime check → false GREEN hiding a survivor (our own [[feedback_mutation_pyc_staleness]]).
Every code-mutation invariant (1a, 3, 15, 20, 21) is exposed. **Fix:** wire it — `PYTHONDONTWRITEBYTECODE=1`
for the B-7 harness (or purge between patch/revert), pin in `conftest.py`/the mutation harness, add an explicit
B-7 step, cross-reference from the code-mutation invariants.

> Disposition:

### X15 — `load_structure_map` Tier-1→Tier-2 ordering unstated (MED; D-4 + D-5 + A-5)

§4.2 says the loader "delegates to the single `validate_structure_map`" (Tier-2) but never says it first runs
the Tier-1 JSON-Schema. inv 2/22/24 are Tier-1 rejections (before the semantic validator); whether their red
tests route through `load_structure_map` (which must then run Tier-1 in a defined order) or directly against the
schema is unspecified. The §4.1.x heading "Tier-2 enumeration covers:" over-claims — it lists the whole battery
including Tier-1 inv 2/22/24 (only inv 2 marked). **Fix:** state the loader contract (parse → Tier-1 → Tier-2,
in order); mark inv 22/24 Tier-1 inline; retitle the enumeration "The invariant battery covers (Tier per
entry)."

> Disposition:

### X16 — `body_atoms` strict-ascending ordering unpinned (MED; B-3)

"must be strictly ascending" (§3.B.6/§3.J) has no `EC.*` and no invariant. inv 20 can't catch it — §3.E.1
re-sorts atoms by canonical-stream index *before* hashing, so a descending hand-authored `body_atoms`
round-trips byte-identically. **Fix:** add `EC.BODY_ATOMS_UNORDERED` (and/or intra-list duplicate) + an
invariant asserting strict ascending, with a permute/duplicate mutation.

> Disposition:

### X17 — vocab near-duplicate/whitespace hygiene under-pinned (MED; B-5)

§3.E.7 lists five conditions; §4.0 gives four codes/mutations. **near-duplicate (fuzzy)** is collapsed into
`VOCAB_DUPLICATE` (exact-dup mutation only) with no distance metric defined (and an undefined metric risks
rejecting legitimately distinct per-book classes); **whitespace-only** folds into `VOCAB_EMPTY` without its own
mutation. **Fix:** either give near-dup its own code + stated metric + mutation, or demote §3.E.7 to "exact
duplicates after normalization" and define the normalization; add a whitespace-only mutation under
`VOCAB_EMPTY`.

> Disposition:

### X18 — §8.3 omits the S4.0 tracker row; issue-set vs row-set unreconciled (MED; F-9)

M11 promoted the constants to a standalone **S4.0** step, but the header still says "Tracker rows S4.1–S4.7" and
§8.3's five edits don't create an S4.0 row or move the stale-class constants out of the S4.4 row — while §8.4/B-7
speak of "the S4.0–S4.5 issues." The S4.0–S4.5 issue scheme and the S4.1–S4.7 row scheme are never mapped.
**Fix:** add a §8.3 edit creating row S4.0 (constants) + moving the constants out of S4.4, and one line
reconciling the two numbering schemes.

> Disposition:

### X19 — "closed set" vs "collects all in one pass" partition (MED; B-6) — folded into X14.

### X20 — sidecar engine-half forward row under-specified (MED; E-3)

The §1.4.1c "authoring-evidence sidecar" engine half (schema + digest-staleness validator) is engine code that
will compute over `lineage._canonical`/`_sha256_bytes` and therefore needs inv 15 coverage, but the forward row
commits no module/exports/tests/neutrality binding and "scheduled with/before S4.6" gives no ordering. *(The
§1.5 amendment-rule consistency itself holds — it is correctly forward, out of the wave matrix.)* **Fix:** in
§8.3's new forward row, pin (tentatively) the module location, state it inherits inv 15 + a digest-staleness red
test, and give it a concrete predecessor/successor relation to S4.6.

> Disposition:

---

## 4. LOW roll-up (clarity / diagnostic / belt-and-suspenders)

- **A-3** §3.J cites "inv 1" (3×); only inv 1a/1b defined → write "inv 1a/1b".
- **A-4** "inv 13-hygiene" is a fabricated id → replace with "§4.5".
- **A-5** "Tier-2 enumeration covers:" omits inv 10/11/12a/12b → add them.
- **A-6** `EC.MINTED_BY_SPLIT` advertises a leaf-`human` trigger inv 7 never mutates → add the second split
  mutation.
- **B-8** a dangling `root_id` is reported as `MULTIPLE_ROOTS` (misleading) → optional `EC.ROOT_ID_DANGLING`
  checked first.
- **B-9** per-node `handle_policy` override value and alias `scope` node-ref are unvalidated → extend inv 19 +
  a scope-resolves check.
- **C-8** inv 18 resolve-time re-guard has no distinct red fixture (load already rejects the colliding input) →
  add a bypass-the-validator resolve() test.
- **C-9** inv 15's "scanner enumerates every module" is itself untested (a hard-coded list relocates the M6
  single-point failure) → assert the enumeration equals live package contents.
- **C-10** positive-only invariants (3, 8, 9, 11) state a property without naming a red mutation → name each.
- **D-3** "included canonical-stream atom (keyed on `canonical_stream_id`)" is redundant/imprecise (all
  canonical atoms are included; atoms key on `atom_id`) → reword.
- **D-5** inv 22/24 unmarked Tier-1 in the enumeration list → mark them (folded into X15).
- **D-6** D-S4-I hash formula elides `.encode("utf-8")` (would `TypeError` literally) → write
  `_sha256_bytes(_canonical(obj).encode("utf-8"))`.
- **E-4** §3.D.6 "participating in stale logic" overstates S4's role (S4 only *stamps* the field) → reword to
  "stamped for S8.1 to compare."
- **E-5** inv 15 fixture/generator exemption is implicit; M-S4.4 lists inv 15 beside the book-shaped generator
  it doesn't scan → add the exemption sentence + footnote the cell.
- **E-6** "re-type over existing atom ids" unqualified (atom `block_class` is L1-frozen) → "re-types at the node
  level (`node_class`); atom `block_class` is L1-immutable."
- **E-7** PLL-flavored words in semi-normative prose (`signature_atoms` "attribution"; "chapter-scoped") →
  "sign-off atoms" (ownership-only; authorship is S6) / "container-scoped".

---

## 5. Suggested remediation grouping (if accepted)

Most fixes are localized and several share a root — proposed batches:

1. **Loader/born-gate/EC-module (X1, X2, X10, X14, X15)** — the biggest structural rework: declare
   `load_structure_map`'s contract (parse→Tier-1→Tier-2, born-agnostic), add `assert_schema_born()` +
   `structure/errors.py` (or `EC.*` on artifacts.py) with the three-way partition, adopt the two-phase red-first
   posture, pin inv 23 as two asserts. Touches §1.2, §4.0, §4.1, §4.2, §5, §1.5, inv 23.
2. **Negative-case / degenerate-shape battery (X3, X6, X16, X17, plus A-6/B-8/B-9)** — inv 14 total-order
   rewrite, new codes (`EMPTY_CONTAINER`, non-container-root path, alias-temporal, `BODY_ATOMS_UNORDERED`, vocab
   near-dup), and split the passing differ-fixture from a homed negative-fixture set.
3. **Atom-universe / furniture (X4)** — pin the second-input type, `OWNED_EXCLUDED_ATOM` + furniture bucket,
   rename `capture_role`.
4. **Mutation rigor (X5, X7, X8, X11, X12, X13, plus C-8/C-9/C-10)** — token-specific CYCLE assertion, fold inv
   4/5, `Geom.matched()` for inv 20, closed cheat list for inv 6, mandatory two-size smoke ratio, wire the
   `.pyc` guard.
5. **Bookkeeping (X9, X18, X20, plus the LOW wording set)** — `decision` no-reader invariant, S4.0 tracker row,
   sidecar forward-row detail, id/wording cleanups.

---

## 6. Counts

Reviewer-rated: **HIGH 9** (X1 X2 X3 X4 X6 X7 X8 X9 + the A-1 component of X3) · **MED ~12** · **LOW 15**.
My-read adjustments: X7/X8/X9 → MED (weak-check / missing-binding, not data-integrity holes — see detail).
Convergent (≥2 independent lenses): **X1, X3, X4, X5, X11, X12, X14** (+ the code-anchor / Done-when / signature
*clean* corroborations). Code-fidelity layer: **clean, triple-confirmed.**
