# S4 — L2 projections + `node_id` + structure map (build plan)

Status: **DRAFT v2 — distilled, post correctness-pass, pending deep audit.** v1 was distilled from
`s4_plan_discussion.md` after the six-round inline audit + the O1–O5 rulings; **v2 incorporates the six-reviewer
correctness pass** (findings H1–H4, M1–M11, LOW — see §0). Every actionable claim carries a stable id
(`§x.y`, `D-S4-x`, `inv N`, `M-Sx`, `EC.*`, `B-N`, `O-N`); §8 maps every carried audit/follow-up block to the
id that absorbed it. Code-evidence anchor: **HEAD `d611702`** (symbol + test names given; verified byte-identical
to current HEAD by the code-fidelity reviewer).

Task: **S4 — the keystone** (milestone S4, concern B, wave W2). Tracker rows S4.1–S4.7.
Spec refs: PLAN §3.1–§3.6, §11.2; D5/R3, D10, D11, D12, D13, D18, D20, D21, D25, D29, D30, D33, D35.
Upstreams, **all DONE and verified consumable**: S1.1 (frozen `Atom.geom` slot), S1.5 (atom-store schema +
version), S3.0 (`ResourceLineage` + normalizer policy).

---

## 0. Revision note — correctness-pass fix-map (v1 → v2)

Each finding from the six-reviewer pass and where v2 closes it. (Reviewer verdicts on code-claim fidelity,
decision-fidelity, and neutrality *design* were clean; the fixes concentrate in edge-cases, red-first coverage,
and guard binding.)

| Finding | Severity | Fix location |
|---------|----------|--------------|
| **H1** root node unspecified; inv 14 flags the root as `ORPHAN_NODE` ("non-root" was dropped in distillation); no `root_id`; no `NO_ROOT`/`MULTIPLE_ROOTS`; empty/forest undecided | HIGH | §3.B.0 (root spec), inv 14 reworded, EC.NO_ROOT/EC.MULTIPLE_ROOTS, §3.B.5 empty-map ruling |
| **H2** `node_id` uniqueness not an invariant | HIGH | inv 16, EC.DUPLICATE_NODE_ID |
| **H3** `validate_structure_map(map)` can't construct inv 1b coverage / owned-atom existence; no `DANGLING_ATOM_REF` | HIGH | §4.0 two-input signature `validate_structure_map(map, atom_store)`, inv 1b red mutation, inv 17, EC.DANGLING_ATOM_REF |
| **H4** declared codes with no firing red mutation (`UNOWNED_INCLUDED_ATOM`, `CYCLE`, minted_by split, rebind reject, `SCHEMA_NOT_BORN`) | HIGH | §4.0 code table requires a red mutation per code; inv 1b/7/14/23/24 mutations added |
| **M1** no consolidated Node field table; reserved-field vs `additionalProperties:false`; undefined terms | MED | §3.J Node object schema; defs for signature atoms, `scope`, furniture bucket, `block_vocabulary` entry, handle_type/policy/format |
| **M2** error-code set not closed/coherent; "not exhaustive" vs "pins the code set"; producer of `SCHEMA_NOT_BORN`; `EC-*` token | MED | §4.0 closed code table (producer + red mutation per code); `EC.*` naming |
| **M3** alias-uniqueness enforcement site contradictory (resolve-time vs load-time) | MED | §3.D.4 + inv 18 (eager at load AND re-guard at resolve) |
| **M4** `schema_status` "lying constant" regression | MED | §1.2.2 + inv 23 (`born ⟺ differ-fixture validates`; bump re-enters provisional; missing-key fail-safe) |
| **M5** D-S4-I orphan; digest producer/atom-ordering/structure-map self-hash unspecified | MED | D-S4-I rewritten + inv 20; names `lineage._sha256_bytes`; §3.E.9 staleness basis |
| **M6** neutrality/guard binding not enforced (inv 15 single-point; schema-open `node_class`; regen-guard untested; `RELATION_STORE_STALE_CLASS` inert prose-only) | MED | inv 15 across all new modules + `*.json`; inv 21 (regen-guard); inv 22 (schema-open); inv 12a extended |
| **M7** handle/policy: no `⊆ block_vocabulary` check, no resolvability, table-vs-tree ambiguity, class↔kind | MED | §3.D.1 resolution order; inv 19; EC.POLICY_NOT_IN_VOCAB/POLICY_UNRESOLVED/CLASS_KIND_MISMATCH; `block_vocabulary` entry carries `kind` |
| **M8** `children`/`body_atoms` ordering meaning + contiguity unspecified | MED | §3.B.6 ordering/contiguity |
| **M9** boundary labels: S4.5 "stale-manifest failure"; renderer-version routing; sidecar engine half floats | MED | §1.2 axis rename; §3.D.6 routing→S8.1; §1.4.1c sidecar engine forward row |
| **M10** alias target resolution unchecked; node deletion/merge-split identity unassigned; alias minting trigger | MED | inv 18 (EC.ALIAS_DANGLING_TARGET); §3.B.7 node lifecycle → S8.2; §3.D.7 aliases hand-authored in S4 |
| **M11** stale-class constant double-framed; §8.2 "exactly one id" false; M-S4.4 cell omits hygiene+regen | MED | §1.1/§2.1/D-S4-F framing; §8.2 reworded "≥1"; M-S4.4 cell updated |
| **LOW** §2.6 list; inv 6 forward-dep; inv 2 Tier-1; §4.2 route-through-loader; diamond test; `map_revision` cross-write→S8.1; smoke `k`; "prefer no escape" | LOW | folded inline below |

---

## 1. Scope & boundaries

### §1.1 What this wave delivers — **S4.0–S4.5** (S4.5 folded in, O5)

The S4 keystone is the schema half of concern B *plus its birth gate*: the projection model, the identity
model, the handle/alias model, the `structure_map.json` schema + lineage manifest, **and** the D18
differ-fixture. Per O5, **S4.5 is folded in** — the S4 milestone closes only when S4.5's differ-fixture
validates and flips `schema_status` `provisional`→`born` (§1.2, D-S4-A).

- **S4.0 — constants** (built first; **the constant is decision-owned by D-S4-F but built as its own step
  B-1/M-S4.0**, not "inside S4.4" — M11): add `STRUCTURE_MAP_STALE_CLASS`; pre-place `RELATION_STORE_STALE_CLASS`
  (O1, D-S4-F); add the `schema_status` module map (§1.2.2).
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
  fragment; schema-const binding; **regen-guarded writer**) (D-S4-E).
- **S4.5 — D18 birth gate (folded).** The differ-fixture validates → `schema_status` `provisional`→`born`;
  **closes the milestone** (§1.2, D-S4-A).

### §1.2 The closing gate — **S4.5, D18 schema-born** (part of this wave)

S4.5 hand-authors a **second-structure synthetic fixture built to DIFFER from PLL** (depth-0 body,
`designation-string` handle policy, non-ordinal headings, mismatched body segmentation, alias-uniqueness,
**malformed/incomplete-manifest rejection** — *not* "stale-manifest failure"; a stored-vs-live staleness
**comparison** is S8.1, in S4 the only mechanism is structural-completeness rejection per inv 11, M9 —
**relation-endpoint shape / reference placeholders** — *not* "resolution", reserved for S7/S9.4, R2-03). It is
the **same** adversarial fixture S9.4 later drives end-to-end, and is **distinct from `books/synthetic`** (a
miniature PLL, §2.8). The differ-fixture is the natural place to pin the degenerate-shape rulings (§3.B.5).

- **§1.2.1** The conforming (PLL-shaped) fixture proves the schema *accepts* a valid map; the differ-fixture
  proves it *generalizes*. The schema's defining correctness property (not PLL-overfit) is established **only**
  by the differ-fixture, so S4.4 alone is **not** a born schema (O5).
- **§1.2.2 `schema_status`** is a property of the **schema version**, tracked in a module-level mapping beside
  the version constant — version N is `provisional` until S4.5's differ-fixture test passes, then `born`.
  **Nothing lifecycle-ish persists in any map file** (Audit 2). The flip is a human edit *bound* by inv 23: the
  S4.5 test asserts `schema_status[current] == born` **iff** the differ-fixture validates, so a later
  differ-fixture regression turns the suite red instead of leaving a "lying constant" `born` (M4). A
  schema-version **bump** (e.g. the S6 role/authorship addition) **re-enters `provisional`** and needs its own
  birth gate; a **missing** `schema_status` key is **fail-safe** (treated as `provisional`/raise).
- **§1.2.3** A downstream B/C task harness or S8.1 loader meeting a `provisional` schema version raises a typed
  **`SCHEMA_NOT_BORN`** (EC, raised at the load/harness gate — **not** by `validate_structure_map`, M2/M11)
  naming **S4.5** as the repair, distinct from ordinary M3 version staleness (Audit 2). There is **no silent
  override**; **prefer no schema-birth escape at all** — a provisional schema simply cannot pass a gate (LOW,
  Audit-2 preference). Any local-only escape is loud, **distinctly named (NOT the regen flag, which stays
  scoped to artifact regeneration)**, and **structurally impossible inside a DONE/GATE harness path** (the gate
  reads no override). Folding S4.5 means no completed S4 ever sits in a `provisional` state.

### §1.3 Explicitly NOT in this wave (owned by neighbours)

1. **§1.3.1 — `rebind_anchors.region` *population* / the re-attach algorithm → S5.1.** S4.4's schema *admits*
   the optional anchor sub-object (`{region?}`); populating it and the bind/fail-loud logic are S5. The slot is
   `region`, never `geom` (D-S4-H, Audit 11).
2. **§1.3.2 — the stale-fail *loader* / migration router → S8.1.** S4.4 *produces and stamps* the manifest +
   stale classes; S8.1 *consumes* and compares stored-vs-live (including the `handle_renderer_version` mismatch
   **routing**, §3.D.6, M9). **Vanished-artifact detection is S8.1's** (R2-04). `map_revision` cross-write
   monotonicity (a hand-edit lowering it across writes, needing the prior snapshot) is also **S8.1** (LOW).
3. **§1.3.3 — the relation-store schema + its stale-class *behavior* → S7.1c.** S4.4 carries the relation-store
   version slot and **pre-places the inert constant `RELATION_STORE_STALE_CLASS`** (O1); every early
   relation-store manifest example pins `present: false` (R2-04, Audit 1). No relation-store loader/reader is
   exported from `structure/` in S4 (pinned, inv 12a).
4. **§1.3.4 — the read-axes (`role` / `authorship` / `content_provenance_class`) → S6.1.** S4's schema **OMITS
   `role`/`authorship` entirely** (the Node schema §3.J does not list them; `additionalProperties:false` blocks
   smuggling); **S6 adds them with a schema-version bump** (→ `provisional`, §1.2.2). `designation`/`title`
   remain handle/display inputs only (Audit 14).
5. **§1.3.5 — true re-atomization (split/merge → *new* atom ids) → S8.2/D25.** S4.1 corrects the projection by
   re-grouping + re-typing over existing atom ids; minting new atoms is L1 supersession (Audit 10). Node-level
   *retirement* (merging containers retires a `node_id`) is also S8.2 (§3.B.7, M10). **Tracker edit required**
   (§8.3).

### §1.4 Forward, with their own tracker rows

- **§1.4.1 — S4.6: hand-author the PLL container map (~61 containers). Owner: Ben (HITL).** Depends on S4.4's
  schema. The in-map **`decision` provenance enum** per node (`human-approved | plugin-suggested | inherited`)
  is **reserved present-but-inert** in S4 (§3.J; value-semantics are S8.2; pinned by a test that no S4 code
  reads it — consistent with `RELATION_STORE_STALE_CLASS`, not omitted, M9). The prose authoring evidence lives
  in a named **authoring-evidence sidecar**.
  - **§1.4.1a** The sidecar is **optional at load** (generic `load_structure_map()` never requires it) and
    **required at the S4.6 PLL-authored-map gate** (every `minted_by:human` container ↔ one non-stale evidence
    entry, Audit 15).
  - **§1.4.1b** Evidence-staleness keys on a **recomputed canonical node-structure digest** (named field list:
    `node_class` + ordered `children` + owned `atom_id`s, via `lineage._canonical` + `_sha256_bytes`); evidence
    is stale **iff its bound node's digest changes**. `map_revision` is **informational bookkeeping, NOT** a
    staleness trigger (Audit 15). The sidecar hash does **not** enter structure-map lineage.
  - **§1.4.1c — sidecar engine half (forward engine row, named — M9).** The sidecar **schema + the digest-
    staleness validator** are *engine code* (not prose Ben authors), so they get an explicit forward tracker
    row with an **engine owner**, scheduled with/before S4.6; they are **not** silently folded into the
    human-owned S4.6 nor smuggled into the S4.0–S4.5 matrix (which would breach §1.5's amendment rule).
- **§1.4.2 — S4.7: scale check (D35).** S4.4 commits the addressable posture (§3.B.4, Audit 17); S4.7 measures
  the 10⁵ tier.

### §1.5 Deliverable matrix (bounded-surface guard — R2-02)

**Amendment rule:** any helper / module / **fixture generator / validator path** introduced during S4 —
production *or* test-only — **either maps to a row here or amends this matrix in the same commit**.

| Id | Step | Module(s) | Public exports | Schema / fixture path | Acceptance tests |
|----|------|-----------|----------------|-----------------------|------------------|
| **M-S4.0** | Constants | `structure/artifacts.py` | `STRUCTURE_MAP_STALE_CLASS`, `RELATION_STORE_STALE_CLASS`, `schema_status` map | — | inv 12a, inv 15 |
| **M-S4.1** | Projection model | `structure/projection.py` (new) | `Node`, `ProjectionMap`, ownership/registry/root validators | — | inv 1a, 1b, 2, 3, 15, 16 |
| **M-S4.2** | Identity | `structure/projection.py` | `mint_node_id()` seam, `minted_by` | — | inv 4, 5, 6, 7 |
| **M-S4.3** | Handles + aliases | `structure/handles.py` (new) | `render_handle()`, `Alias`, `resolve()` | — | inv 8, 9, 18, 19, 15 |
| **M-S4.4** | Schema + manifest | `structure/schema/` + `structure/structure_map.py` (new) | `load_structure_map(path, atom_store)`, `validate_structure_map(map, atom_store)`, `schema_version_const()`, regen-guarded `write_structure_map()` | `structure/schema/structure_map.schema.json`; evolve `tests/fixtures/_generate_structure_fixture.py` → conforming | inv 10, 11, 12b, 13, 14, 17, 20, 21, 22, 24 + §4.3 contract + §4.4 smoke + §4.2 read-path + §4.5 hygiene + §3.E.8 regen-guard + inv 15 |
| **M-S4.5** | Birth gate | (test) | — | `tests/fixtures/structure/differ_structure_map.json` (new) | inv 23 (differ-fixture validates → `schema_status` → `born`) |

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
`$ref` form is **optional future hardening**, not a requirement — no resource-lineage schema exists today
(R2-06). The digest producer `_sha256_bytes` and canonicalizer `_canonical` (sort_keys, fixed separators) both
exist here and are the **named** building blocks for every S4 hash (D-S4-I, M5).

### §2.3 `config/schema/manifest.schema.json` — the anti-pattern S4.4 must NOT repeat
Hard-codes `"schema_version": {"const": 1}` with no Python constant. S4.4 binds via **two assertions** (Audit
3): (a) `schema_version_const(schema) == STRUCTURE_MAP_SCHEMA_VERSION` (helper fails loud if the path moves);
(b) a version-derived fixture validates.

### §2.4 `tests/fixtures/_generate_structure_fixture.py` — binding precedent to evolve
Derives `schema_version` from the live constant; one byte-exact `render()` shared by writer + test; docstring
"MUST NOT anticipate" S4.4. S4.4 evolves it trivial→conforming; the conforming fixture **emits
`rebind_anchors.region`, never `.geom`** (inv 13/24).

### §2.5 `tests/unit/test_structure_artifacts.py` — already pins the three versions as independent positive ints + distinct locations + exports.

### §2.6 No L2 module yet
`structure/` holds `__init__.py, artifacts.py, atom_store.py, atoms.py, capture.py, classify.py, lineage.py,
roundtrip.py, roundtrip_gate.py, typed.py` — **no projection/node/map module** (LOW: list now complete). S4.1
creates `structure/projection.py`.

### §2.7 Two `geom`s — kept distinct (D-S4-H)
Atom-level `Atom.geom` (S1.1, frozen `{present|absent}` + match-provenance) is authoritative, on atoms.
Node-level `rebind_anchors.region` is a plain nullable `{page, bbox_region}` — **no `present` flag, no
atom-`Geom` sub-object** (the schema rejects either via `additionalProperties:false`, inv 24). Optional (O4).
Population is S5.

### §2.8 `books/synthetic` — the mini-PLL S4.5 differs from. The differ-fixture is new (depth-0, designation-string, non-ordinal), not an extension.

---

## 3. Design decisions

### D-S4-A — Scope seam (folded, O5)
Linear chain S4.0→S4.1→S4.2→S4.3→S4.4→S4.5, each a red-first checkpoint. S4.4 is validated by a conforming
fixture; **S4.5's differ-fixture is the birth certificate that closes the milestone.**

### D-S4-B — L2 projection model (S4.1)
A node is **container** (owns ordered `children` + optional `heading_atoms`/`signature_atoms`) or **leaf** (owns
`body_atoms`). The full field list is §3.J.

- **§3.B.0 — ROOT node (H1).** A valid map declares **exactly one root**, named by **`root_id` in the map
  header**. The root is a **container** (a leaf-only or empty map is rejected, §3.B.5), **`minted_by:human`**
  (top of the human-authored container hierarchy), and carries a `node_class` that is a **container class in
  `block_vocabulary`** (PLL adds a document/root container class). The root has **no parent**; its
  `handle_policy` resolves from the `handle_policies` table for its class (no ancestor to inherit from,
  §3.D.1). The root is the **anchor** for inv 14's traversal and is **exempt** from the `ORPHAN_NODE` rule (it
  legitimately has zero children-occurrences).
- **§3.B.1 — Ownership (Audit 9).** **inv 1a (no double-ownership):** no `atom_id` in two ownership slots; not
  both child-owned heading/signature and body. **inv 1b (coverage):** every *included* **canonical-stream**
  atom (keyed on `canonical_stream_id`) is owned by exactly one node; *excluded/furniture* atoms are listed in
  the map header's **`furniture_atoms`** array with their capture role (§3.J), never in a node, never forced
  into body. Per-witness ownership is S7.
- **§3.B.2 — `node_class`** is an **open string vocabulary** declared in the header's `block_vocabulary`
  (§3.J), never a core enum; a **distinct axis** from `role` (S6, absent in S4) and `handle_policy` (R2-07).
  Each `block_vocabulary` entry declares a **`kind` (`container|leaf|either`)**; the validator checks a node's
  slot usage matches its class kind (EC.CLASS_KIND_MISMATCH, inv 19, M7).
- **§3.B.3 — Correction scope:** B re-groups + re-types over existing atom ids; true re-atomization is S8.2/D25
  (§1.3.5).
- **§3.B.4 — Storage posture (Audit 12, Audit 17).** Flat node table keyed by `node_id`; persist **`children`
  only** (canonical ordered source); **derive `parent` on load**. Reference-validation resolves through the
  id-keyed table — no per-reference tree scan.
- **§3.B.5 — Degenerate shapes (M-edge, M10).** **Empty map** (zero nodes) → `NO_ROOT` (reject). **Leaf-only /
  zero-container map** → `NO_ROOT` (the root must be a container). **Container with zero children and no
  heading/signature atoms** → reject as an empty container (a coverage/structure error). These rulings are
  pinned by the S4.5 differ-fixture.
- **§3.B.6 — Ordering & contiguity (M8).** `children` is ordered = **reading order** (feeds `position-path`
  handles + the §1.4.1b digest). `body_atoms` is ordered by **ascending canonical-stream index** and **need not
  be contiguous** (it may interleave around excluded furniture), but must be strictly ascending.
- **§3.B.7 — Node lifecycle (M10).** In S4 a structure map is authored **fresh**; there is **no in-place node
  deletion**. Re-group/re-type changes no stored leaf field (`parent` is derived); **merging containers retires
  a `node_id`** — node-level **retirement/tombstone semantics + id-reuse prohibition are S8.2** (its scope
  extends to L2 node identity, not only atoms; tracker note, §8.3).
- Pure dataclass; no language literal in `structure/` (inv 15 across all new modules + `*.json`).

### D-S4-C — `node_id` identity + minting split (S4.2): pin PROPERTIES (O3)
- **§3.C.1** Opaque string; pinned: (a) stable re-serialize; (b) stable positional move; (c) never derived from
  position/designation/content (D33/BR-021); (d) `minted_by ∈ {human, machine}`; **(e) unique within the map**
  (inv 16, EC.DUPLICATE_NODE_ID — H2; checked **before** the `node_id`-keyed table is built, raising on the
  second insert rather than silently overwriting).
- **§3.C.2 `minted_by` = conceptual minting authority** (human ⇒ a container; machine ⇒ a leaf) — not the
  runtime writer. Schema `description` carries **"conceptual minting authority" verbatim** (test-asserted).
  Name kept `minted_by` (R2-08). The human/machine **split is enforced** (container⇒human, leaf⇒machine):
  EC.MINTED_BY_SPLIT, inv 7 (H4 — a container with `minted_by:machine` must raise).
- **§3.C.3 Non-derivation control (Audit 5).** inv 6 = "rejects common derivation cheats" (equality +
  substring/slug/known-transform of any handle/designation → EC.NODE_ID_DERIVED), backed by a **structural
  seam**: `mint_node_id()` takes no designation/path/content arg and is **called before any handle/designation
  attaches** (ordering control). One fixture mutates designation, position, and content with the id fixed. (LOW:
  the designation-derivation cheat is tested at S4.2; the rendered-handle cheat **re-runs at/after S4.3** when
  `render_handle` exists.)
- **§3.C.4** Default scheme (revisitable, fixture-only): counter for human containers, ULID-like for leaves.

### D-S4-D — Handle policy + rendered handles + alias records (S4.3)
- **§3.D.1 Policy resolution order (M7).** `handle_policy` is declared per `node_class` in the
  `handle_policies` table. A node's effective policy = **(1)** its own `handle_policy` override if present, else
  **(2)** the nearest ancestor's override, else **(3)** the `handle_policies` default for its `node_class`. The
  validator asserts every `handle_policies` key is in `block_vocabulary` (EC.POLICY_NOT_IN_VOCAB) and every
  used `node_class` resolves to a policy (EC.POLICY_UNRESOLVED) — inv 19.
- **§3.D.2 Rendering signature (Audit 6):** `render_handle(map, node_id, policy, target_format, scope)` — not
  `f(node_id, policy)`. `target_format ∈ {short, parse_md, html_slug}`. "One source of truth" survives.
- **§3.D.3 Derived-only (R2-09):** rendered handles are **NOT persisted** in S4 — only policy inputs
  (`designation`/`title`/position-via-tree). No "if cached" branch.
- **§3.D.4 Alias record:** `{handle_type, value, scope, locale_or_witness, target_node_id, valid_from,
  valid_to, status}`. **Term defs (M1):** `handle_type` = which rendered `target_format` the alias preserves;
  `value` = the literal retired handle string; `scope` = the resolution namespace (`global` or a container
  `node_id` for chapter-scoped — a declared value vocabulary, §3.J); `locale_or_witness` = the locale (active
  in S4) or witness (reserved for S7, M10). **Active-alias uniqueness (Audit 7)** key =
  `(handle_type, value, scope, locale_or_witness)`. **Enforced at BOTH sites (M3):** eagerly in
  `validate_structure_map` (EC.ALIAS_COLLISION, inv 18 — so a dup-alias map fails at **load**, satisfying the
  §4.2 headline) **and** re-guarded as a `resolve()` precondition. Every alias `target_node_id` must resolve to
  a live node (EC.ALIAS_DANGLING_TARGET, inv 18, M10).
- **§3.D.5 Temporal coordinate (Audit 8):** a monotonic `map_revision` integer in the header is the clock;
  `valid_from`/`valid_to` reference it. Rules: `valid_from ≤ current`; `valid_to` null or `≥ valid_from`; a
  non-`active` alias must carry `valid_to`; an `active` alias lies within its interval. Writer increments
  `map_revision` once per authoring change (same event as the regen snapshot, §3.E.8). **Historical
  resolution:** `resolve(handle, at_revision=N)` returns the node whose interval contained N; the **default**
  resolve returns only `status:active`.
- **§3.D.6 Renderer versioning (Audit 6, M9):** `handle_renderer_version` in the manifest, bumped on
  slug/disambiguation-rule changes, participating in stale logic — distinct from `recognizer_version`. **S4
  reserves the field + its stale-class participation only;** the mismatch→**routing** (handle-review /
  alias-migration diagnostic, distinct from schema migration) is **S8.1's** (like `SCHEMA_NOT_BORN`, §1.3.2).
- **§3.D.7 Alias minting (M10):** in S4, aliases are **hand-authored**; the engine **resolves + validates**
  them (it does not auto-mint an alias on a designation/renderer change). inv 9 tests a hand-authored fixture.

### D-S4-E — `structure_map.json` schema + lineage manifest (S4.4): build to the ROW
- **§3.E.1** `source_artifacts` (raw witness hashes); `atom_streams` + `canonical_stream_id`; the **two split
  canonical hashes** (R2-10): **`canonical_content_hash`** over `{atom_id, text, raw_span, raw_source_hash}` and
  **`canonical_geometry_hash`** over the geom-region fields. Each is computed by **`lineage._sha256_bytes` over
  `lineage._canonical`** of the **canonical-stream-ordered** atom payloads (atom order = ascending
  canonical-stream index — pinned, M5/M8); explicit field list, no "hash whatever's in the dict." *Caveat:*
  geometry is `Geom.absent()` everywhere today (`capture.py`), so `canonical_geometry_hash` currently covers
  absent slots; field membership firms when S2.1 populates geom. The split shape is correct now.
- **§3.E.2** atom-store / structure-map / relation-store **schema versions, each with its stale class** (M3);
  relation-store pins `present:false` until S7.1c.
- **§3.E.3** the `ResourceLineage.to_json()` fragment verbatim, bound by §4.3.
- **§3.E.4** `profile_version`, `recognizer_version`, `handle_renderer_version`, `map_revision`, `root_id`,
  `block_vocabulary`, `handle_policies`, `furniture_atoms`.
- **§3.E.5 Schema-const binding (Audit 3):** the two assertions + `schema_version_const()` (§2.3).
- **§3.E.6 `schema_status`** beside the version constant (module-level), not per-map (§1.2.2).
- **§3.E.7 `block_vocabulary`** self-declared in the header; each entry `{name, kind, status:active|reserved}`
  (M1/M7). **Hygiene (Audit 13, inv 13-hygiene/§4.5):** reject an entry colliding with `classify.UNKNOWN`
  (`"unknown"`), empty/whitespace, near-duplicates; every declared class used or explicitly `reserved`.
- **§3.E.8 Production regen-guard (D33, Audit 16, inv 21).** `structure_map.json` is irreproducible committed
  data. Fixture/test generation writes freely under `tests/fixtures/`. The production
  **`write_structure_map()` fails loud on overwrite of a hand-authored map** (EC.MAP_OVERWRITE_BLOCKED); the
  only path through is **explicit output target + snapshot-before-overwrite + a new lineage/`map_revision`
  entry**. **No env-var as the primary escape.** Guard implemented in the S4.4 writer (not deferred to S8.1) and
  **red-first tested** (inv 21, M6).
- **§3.E.9 Structure-map staleness basis (M5).** S8.1 detects structure-map staleness from the **manifest's
  version + the two canonical hashes + the per-layer stale classes** — there is **no separate structure-map
  self-hash**; the canonical hashes are the content signal. Stated so S8.1 inherits an explicit basis.

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
**Producers named:** every hash is `lineage._sha256_bytes(lineage._canonical(obj))` (sort_keys, fixed
separators, `ensure_ascii=False`) — an implementer may **not** substitute a different hash. **Ordering:** atoms
within a content/geometry hash are ordered by **ascending canonical-stream index**; `children`/aliases serialize
in their stored order; manifest keys are canonicalized. The human-authored map file stays diffable `indent=2`;
only the hashed sub-objects use canonical byte-form. **Proof obligation:** inv 20 (D-S4-I is no longer an
orphan — it has a binding invariant and is cited at §3.E.1 / §1.4.1b).

### D-S4-J — Node object schema (consolidated field list) (M1)
The single canonical Node field list S4.4's JSON-Schema enumerates (`additionalProperties:false`):

| Field | Kind | Req? | Tier | Notes |
|-------|------|------|------|-------|
| `node_id` | both | required | schema + inv 4–7,16 | opaque, unique |
| `minted_by` | both | required | schema + inv 7 | `human`\|`machine`; split enforced |
| `node_class` | both | required | schema + inv 19 | open string; `∈ block_vocabulary`; kind must match slot |
| `children` | container | required-for-container | schema(`oneOf`) + inv 2,14 | ordered = reading order |
| `body_atoms` | leaf | required-for-leaf | schema(`oneOf`) + inv 1,2 | ordered ascending canonical-stream index; non-contiguous OK |
| `heading_atoms` | container | optional | schema + inv 1 | container's heading atoms |
| `signature_atoms` | container | optional | schema + inv 1 | **def:** a container's closing/attribution atoms (e.g. an embedded letter's signature line) |
| `designation` | both | optional | schema | handle input only |
| `title` | both | optional | schema | handle/display input only |
| `handle_policy` | both | optional | schema + inv 19 | per-node override; else inherit/default (§3.D.1) |
| `rebind_anchors` | both | optional | schema(`additionalProperties:false`) + inv 13,24 | `{region?:{page,bbox_region}}`; no `present`/`geom` |
| `decision` | both | reserved | schema (present, inert) | `human-approved\|plugin-suggested\|inherited`; value-semantics S8.2; no S4 code reads it |

Header-level (not per node): `root_id`, `block_vocabulary[{name,kind,status}]`, `handle_policies`,
`furniture_atoms[{atom_id, role}]`, `map_revision`, the manifest block (§3.E). **Omitted until S6:**
`role`, `authorship` (§1.3.4). `oneOf` enforces container-xor-leaf (inv 2 is **Tier-1**, LOW).

---

## 4. Two-tier validation + red-first invariant battery

**Two tiers (R2-11, refined H3).** **Tier 1 — JSON-Schema** validates *shape* (field presence/type;
`node_class` is a non-empty string with **no `enum`** (inv 22); container-xor-leaf `oneOf`; no extra keys).
**Tier 2 — the public semantic validator `validate_structure_map(map, atom_store)`** (two inputs — the second is
the canonical atom store/`AtomStream`, **required** to enumerate the included-atom universe and verify owned
`atom_id`s exist, H3) enforces what JSON Schema cannot.

- **§4.1 Error model (R2-11).** `validate_structure_map()` **collects all** semantic failures in one pass and
  raises with the collected set as payload. Codes are a **closed set declared in one module** as an
  enum/constant set, **pinned by a test** — there is **no "non-exhaustive" hedge** (M2). Each code names its
  **producer** and has a **red-first mutation** (§4.0). S8.1 routes on the code value.
- **§4.2 Public read-path binding (R2-12).** Every semantic invariant's red test routes **through the public
  `load_structure_map(path, atom_store)`** (which delegates to the single `validate_structure_map`), **not** by
  calling the public validator directly — that is what proves loader wiring (LOW). **Headline test:** corrupt a
  fixture that passes JSON-parse + Tier-1 shape but fails only semantically (a dangling `children` ref that is a
  well-formed string; two `status:active` aliases sharing the uniqueness tuple) and assert `load_structure_map`
  rejects it.

### §4.0 Closed error-code set (`EC.*`) — producer + red-first mutation per code (H4, M2)

| Code | Producer | Red-first mutation that fires it |
|------|----------|----------------------------------|
| `DUP_OWNERSHIP` | validator | an `atom_id` in two ownership slots |
| `UNOWNED_INCLUDED_ATOM` | validator | an *included* canonical-stream atom owned by **no** node (H4/H3) |
| `DANGLING_ATOM_REF` | validator | an owned `atom_id` absent from `atom_store` (H3) |
| `DUPLICATE_NODE_ID` | validator (pre-table) | two nodes with the same `node_id` (H2) |
| `DANGLING_REF` | validator | a `children` entry naming no node |
| `ORPHAN_NODE` | validator | a **non-root** node with zero children-occurrences (root exempt, H1) |
| `MULTI_PARENT` | validator | a node in two parents' `children` |
| `DUPLICATE_CHILD_REF` | validator | a node twice in one parent's `children` |
| `NO_ROOT` | validator | zero zero-occurrence nodes / empty map / leaf-only map (H1) |
| `MULTIPLE_ROOTS` | validator | >1 zero-occurrence node, or it ≠ `root_id` (H1) |
| `CYCLE` | validator | a **reachable** back-edge (on-stack) — e.g. `root→A→B→A` (H4) |
| `UNREACHABLE_NODE` | validator | a node not visited from `root_id` (incl. a disconnected cycle) |
| `ALIAS_COLLISION` | validator | two `status:active` aliases sharing `(handle_type,value,scope,locale_or_witness)` (M3) |
| `ALIAS_DANGLING_TARGET` | validator | an alias `target_node_id` naming no live node (M10) |
| `NODE_ID_DERIVED` | validator | `node_id == html_slug` / substring-transform of a handle/designation |
| `MINTED_BY_SPLIT` | validator | a container with `minted_by:machine` (or leaf `human`) (H4) |
| `CLASS_KIND_MISMATCH` | validator | a node whose slot usage contradicts its `node_class` kind (M7) |
| `POLICY_NOT_IN_VOCAB` | validator | a `handle_policies` key not in `block_vocabulary` (M7) |
| `POLICY_UNRESOLVED` | validator | a used `node_class` with no resolvable policy (M7) |
| `VOCAB_UNKNOWN_COLLISION` / `VOCAB_EMPTY` / `VOCAB_DUPLICATE` / `VOCAB_UNUSED` | validator | a `block_vocabulary` entry `== "unknown"` / empty / dup / declared-unused-and-not-reserved (Audit 13) |
| `MAP_OVERWRITE_BLOCKED` | **writer** | `write_structure_map()` over a hand-authored map without explicit-target+snapshot+lineage (M6) |
| `SCHEMA_NOT_BORN` | **load/harness gate** (not the validator) | a DONE/GATE harness/S8.1 loader meets a `provisional` schema version (M2) |

### §4.1.x Invariant battery (each RED first against the stated mutation; mutation pass purges `__pycache__`)

Tier-2 enumeration covers: ownership (1a/1b), uniqueness (16), atom-ref integrity (17), container/leaf (2 —
*Tier-1* `oneOf`), depth (3), identity (4–7), handles (8/19), aliases (9/18), reference-integrity (14),
determinism (20), neutrality (15/22), regen-guard (21), rebind shape (13/24), birth gate (23), vocab hygiene
(§4.5). inv 2 and inv 3 are explicitly placed (inv 2 Tier-1, LOW).

1. **inv 1a — no double-ownership** → `DUP_OWNERSHIP`. Mutation: drop the dedup check.
2. **inv 1b — coverage** → `UNOWNED_INCLUDED_ATOM` (H3/H4). Mutation (A, the firing case): a fixture with one
   unowned *included* canonical-stream atom **must raise** (kill the drop-the-coverage-check mutant). Mutation
   (B, exemption): an unowned *excluded* furniture atom **passes**.
3. **inv 2 — container/leaf (Tier-1 `oneOf`)** → schema rejects a node with both `children` and `body_atoms`.
4. **inv 3 — ragged depth + heterogeneous siblings** validate; mutation: hard-code a fixed depth.
5. **inv 4 — `node_id` stable across re-serialize.**
6. **inv 5 — `node_id` stable across a positional move.**
7. **inv 6 — `node_id` rejects derivation cheats** → `NODE_ID_DERIVED` (designation cheat @S4.2; rendered-handle
   cheat re-runs @S4.3, LOW). Backed by the §3.C.3 seam.
8. **inv 7 — `minted_by` recorded + split enforced** → `MINTED_BY_SPLIT` (H4). Mutations: blank `minted_by`
   fails (presence); **a container with `minted_by:machine` fails** (split). Schema `description` carries
   "conceptual minting authority" verbatim.
9. **inv 8 — handle renders from `render_handle(map, node_id, policy, target_format, scope)`** with
   ancestor-context + slug-disambiguation cases.
10. **inv 9 — alias survives a handle change**; old value resolves to the same `node_id` as a `status:active`
    alias (hand-authored fixture, §3.D.7).
11. **inv 10 — schema `const` ↔ `STRUCTURE_MAP_SCHEMA_VERSION`** (two assertions); a bump without refreshing the
    fixture fails.
12. **inv 11 — manifest lists all required versions, each with a stale class** (relation-store `present:false`)
    + the lineage fragment.
13. **inv 12a — stale-class constants (extended, M6):** `STRUCTURE_MAP_STALE_CLASS` and
    `RELATION_STORE_STALE_CLASS` present/exported/distinct from all other classes; **no relation-store loader
    exported from `structure/`** (inertness). **inv 12b — manifest declares `STRUCTURE_MAP_STALE_CLASS`.**
14. **inv 13 — `rebind_anchors` optional + `region` shape**; a node with no `rebind_anchors` validates; a
    `{page, bbox_region}` region validates. **inv 24 (H4/M6): the schema REJECTS a `present` or `geom` key
    inside `rebind_anchors`** (`additionalProperties:false`) — mutation: smuggle `rebind_anchors.geom` → Tier-1
    rejects.
15. **inv 14 — reference-integrity (compound, precedence-pinned — Audit 12, H1):**
    - **(local)** every `children` entry resolves (`DANGLING_REF`); **every non-root node appears exactly once
      across the multiset union of all `children` lists** — zero → `ORPHAN_NODE` *(root exempt, identified by
      `root_id`)*, two parents → `MULTI_PARENT`, twice in one list → `DUPLICATE_CHILD_REF`. The unique
      zero-occurrence node **must equal `root_id`**: zero such nodes / empty / leaf-only → `NO_ROOT`; >1 or
      mismatch → `MULTIPLE_ROOTS` (H1).
    - **(global)** a traversal **from `root_id`** visits every node exactly once: unvisited → `UNREACHABLE_NODE`;
      an **on-stack** back-edge within the reachable set → `CYCLE` (mutation: `root→A→B→A`, H4). **No
      unvisited-component scan** — a disconnected cycle reports `UNREACHABLE_NODE`. **(LOW)** pin a DAG-diamond
      test that yields `MULTI_PARENT` **only** (no spurious `CYCLE` — cycle detection is on-stack, not
      already-visited).
16. **inv 15 — neutrality (all new modules + schema, M6):** `projection.py`, `handles.py`, `structure_map.py`,
    `artifacts.py` **and** `structure/schema/*.json` carry no language/book/typeface literal; the scanner
    enumerates every module in the package at each checkpoint. Mutation: plant `"italiano"` (or a `node_class`
    `enum` of PLL values in the schema) → caught.
17. **inv 16 — `node_id` unique within the map** → `DUPLICATE_NODE_ID` (H2); checked before the keyed table.
18. **inv 17 — atom-ref integrity (H3):** every owned `atom_id` exists in `atom_store` → `DANGLING_ATOM_REF`.
19. **inv 18 — alias integrity (M3/M10):** active-alias uniqueness enforced **eagerly at load** (`ALIAS_COLLISION`)
    and re-guarded at `resolve()`; every `target_node_id` resolves (`ALIAS_DANGLING_TARGET`) + the §3.D.5
    temporal rules.
20. **inv 19 — handle-policy resolvability (M7):** `handle_policies` keys ⊆ `block_vocabulary`
    (`POLICY_NOT_IN_VOCAB`); every used `node_class` resolves to a policy (`POLICY_UNRESOLVED`); class-kind ↔
    slot (`CLASS_KIND_MISMATCH`).
21. **inv 20 — determinism (M5):** `dump→load→dump` is byte-identical; the two canonical hashes are stable under
    re-serialize and change under a content/geometry edit; computed via `_sha256_bytes(_canonical(...))` with
    canonical-stream atom ordering. Mutation: swap the hash producer or atom order → fails.
22. **inv 21 — regen-guard (M6):** `write_structure_map()` over an existing hand-authored map **raises
    `MAP_OVERWRITE_BLOCKED`**; the explicit-target + snapshot + lineage/`map_revision` path **succeeds**.
    Mutation: drop the overwrite check → the overwrite passes, caught.
23. **inv 22 — schema keeps `node_class` open (M6):** the schema's `node_class` is `{"type":"string"}` with **no
    `enum`**; mutation: add a PLL `enum` → caught (also covered by the inv 15 `.json` scan).
24. **inv 23 — birth gate (M4):** the S4.5 differ-fixture **shape- and semantically-validates**, and
    `schema_status[current] == born` **iff** it validates (a differ-fixture regression flips the suite red);
    a load against a `provisional` schema version raises `SCHEMA_NOT_BORN` (the negative red test); a missing
    `schema_status` key is fail-safe (provisional/raise).

### §4.3 ResourceLineage contract test (R2-06); §4.4 complexity smoke; §4.5 vocab hygiene
- **§4.3** a live `ResourceLineage(...).to_json()` validates against the schema; a `lineage.py` shape change
  fails.
- **§4.4 Complexity smoke (Audit 17, hardened — invariant-logic reviewer).** Over a few-thousand-node synthetic
  flat table, reference-integrity does **no per-reference full-tree scan**. The `node_id` table is reachable
  **only** through an **instrumented accessor** owned by the validation context — **no raw dict/list handle
  escapes** (else an O(n²) plain scan would bypass the counter). `context.ref_ops` increments at every node/child
  access **including index/precompute**; assert `context.ref_ops <= k · node_count`. **(LOW)** state a nominal
  `k` at test-authoring time; optionally assert the ratio across two sizes scales sub-linearly. S4.7 owns the
  10⁵ timing/memory measurement.
- **§4.5** vocab hygiene → `VOCAB_*` (Audit 13).

### Done-when → proof map
- **S4.0** → inv 12a, 15
- **S4.1** → inv 1a, 1b, 2, 3, 15, 16 (+ §3.B.0 root, §3.B.5 degenerate, §3.B.6 ordering)
- **S4.2** → inv 4, 5, 6, 7
- **S4.3** → inv 8, 9, 18, 19, 15
- **S4.4** → inv 10, 11, 12b, 13, 14, 17, 20, 21, 22, 24, 15 + §4.2 read-path + §4.3 contract + §4.4 smoke + §4.5 hygiene + §3.E.8 regen-guard
- **S4.5** → inv 23 (`schema_status` `provisional`→`born`)

---

## 5. Build order (red-first)

- **B-1 — Constants (S4.0/M-S4.0):** `STRUCTURE_MAP_STALE_CLASS` + pre-placed `RELATION_STORE_STALE_CLASS` +
  the `schema_status` module map; red-first inv 12a (constant-only) + inv 15 (artifacts.py). *Decision-owned by
  D-S4-F; this is where it is built (M11).*
- **B-2 — S4.1 projection model** (`projection.py`): dataclasses + root spec + ownership/coverage/uniqueness +
  flat-table/children-only + ordering; inv 1a, 1b, 2, 3, 15, 16.
- **B-3 — S4.2 identity:** `node_id` + `minted_by` + `mint_node_id()` seam; inv 4–7.
- **B-4 — S4.3 handles + aliases** (`handles.py`): `render_handle()` + alias record + resolve + eager
  uniqueness + policy resolvability; inv 8, 9, 18, 19.
- **B-5 — S4.4 schema + manifest** (`structure/schema/structure_map.schema.json`, `structure_map.py`): the Node
  schema (§3.J), two-input `validate_structure_map(map, atom_store)`, evolve the generator → conforming,
  manifest assembly + `schema_version_const()` + regen-guarded `write_structure_map()`; inv 10, 11, 12b, 13,
  14, 17, 20, 21, 22, 24 + §4.2–4.5.
- **B-6 — S4.5 differ-fixture birth gate:** author `differ_structure_map.json` (pins the degenerate-shape
  rulings, §3.B.5); it shape- + semantically-validates; flip `schema_status`→`born` (inv 23). **Closes the
  milestone.**
- **B-7 — Checkpoint → PAUSE → pre-commit adversarial audit → dispositions → apply → commit → close the
  S4.0–S4.5 issues.** Issues = tracker bookkeeping, minted at wave-start, closed per commit; the proof is the
  green battery + the audit (R2-13).

---

## 6. Rulings (O1–O5, settled 2026-06-30)
- **O1 — pre-place `RELATION_STORE_STALE_CLASS`** (inert + `present:false`) — D-S4-F.
- **O2 — schema at `structure/schema/`**; helper inlined now, factored at S7.1c — D-S4-G.
- **O3 — `node_id` properties-only**; counter+ULID fixture default — D-S4-C.
- **O4 — `rebind_anchors` optional** (absence first-class; freezable later) — D-S4-H.
- **O5 — fold S4.5 into the keystone** — D-S4-A, §1.2.

---

## 7. Provenance & durable references
Code-evidence anchor **`d611702`** (verified byte-identical to current HEAD): `structure/artifacts.py`;
`structure/lineage.py` (`to_json`, `_canonical`, `_sha256_bytes`); `config/schema/manifest.schema.json`;
`tests/fixtures/_generate_structure_fixture.py`; `tests/unit/test_structure_artifacts.py`;
`tests/unit/test_atom_store.py` (read-path negatives); `structure/capture.py`
(`geom=Geom.absent()`, `processing_scope="excluded"`); `structure/classify.py` (`UNKNOWN`); `books/synthetic/`.
Spec: PLAN §3.1–§3.6, §11.2. Audit trail: `s4_plan_discussion.md` (six rounds) + this v2 correctness pass.
**Durable rules (inlined where load-bearing, R2-14):** `docs/invariants.md` — I3 port-fidelity, I4
core-separability/neutrality, I5 wire-protocol single-sourcing, I7 write-containment, I8 atomicity, I9
determinism; `docs/port_discipline.md`.

---

## 8. Acceptance checklist (this plan's distillation gate — R2-01)

- **§8.1** Every actionable claim carries a stable id. ☐ verify at audit.
- **§8.2** Every carried audit/follow-up block maps to **≥1** id (the id(s) that absorbed it — many map to
  several; "exactly one" was wrong, M11). Crosswalk below.
- **§8.3 Tracker-wording changes required** (anchor by **row identity**, not line number — R2-03):
  - **S4.5 row** — "relation-endpoint **resolution**" → "**shape / reference placeholders**"; reserve
    "resolution" for S7/S9.4. Also "stale-manifest failure" → "malformed/incomplete-manifest rejection" (M9).
  - **S4.1 row** — "B can **re-atomize** and re-type" → "B **re-groups / re-types**"; true re-atomization →
    **S8.2/D25** (Audit 10).
  - **S8.2 row** — extend scope from atom re-atomization to **L2 node retirement/identity** (§3.B.7, M10).
  - **S4 milestone / S4.5 row** — record S4.5 as the **closing birth gate of the S4 keystone** (folded, O5).
  - **New forward row** — the **authoring-evidence sidecar engine half** (schema + digest-staleness validator),
    engine owner (§1.4.1c, M9).
- **§8.4** Ratification mints the S4.0–S4.5 issues (bookkeeping); O1 struck from any open-fork list (Audit 1).

### Audit-block → plan-id crosswalk (R2-01 §8.2)

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
