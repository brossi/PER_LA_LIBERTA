# S4 — L2 projections + `node_id` + structure map (build plan — **DISCUSSION**)

Status: **DRAFT — discussion stage.** This is the working surface for the `@@@@@@` / `======`
inline audit; once the open forks (§6) are ruled and the design settles, it is distilled into the
"final" `s4_plan.md` (the `s3_0_plan_discussion.md` → `s3_0_plan.md` precedent). Nothing here is
committed as code; no GitHub issue is minted yet.

Task: **S4 — the keystone** (milestone S4, concern B, wave W2). Tracker rows S4.1–S4.7
(`ENGINE_STRUCTURE_TASKS.md:447–467`).
Spec refs: PLAN §3.1–§3.6, §11.2; D5/R3, D10, D11, D12, D13, D18, D20, D21, D29, D30, D33.
Upstreams, **all DONE and verified consumable this session**: S1.1 (frozen `geom` slot),
S1.5 (atom-store schema + version), S3.0 (`ResourceLineage` + normalizer policy).

Every point is numbered so an audit comment can pin to it.

@@@@@@
**Audit R2-01 - the review anchors are not actually stable yet.** The draft says every point is
numbered, but many audit-relevant claims are compound bullets or dense paragraphs rather than numbered
sub-points. If this artifact is meant to support round-by-round inline review, split the major claims
inside 1.1, D-S4-B through D-S4-I, and the invariant battery into stable labels. Otherwise a later
edit can move the sentence an audit block refers to, and the disposition trail becomes ambiguous.
@@@@@@

======
**Response (R2-01) — AGREE, with a scope note.** Correct for the *distilled* `s4_plan.md`: there,
every claim gets a stable `S4-§x.y` label. For *this* draft I'm deliberately not renumbering mid-review
— that would break the anchors your own blocks already pin to. The invariant battery (§4) is already
numbered; at the next revision I'll (a) split each compound D-S4-x into lettered sub-claims and (b)
give §1.1/§1.3 list items stable ids. The discussion doc's job is to surface the design *before* the
numbering hardens, so the labels land at distillation, not now. Closed.
======

---

## 1. Scope & boundaries

### 1.1 What this wave delivers — **S4.1–S4.4 + one missing constant**

The W2 keystone chunk is the **schema half** of S4: the projection model, the identity model, the
handle/alias model, and the `structure_map.json` schema + lineage manifest that binds them. Per the
wave table (`ENGINE_STRUCTURE_TASKS.md:203`, "W2: … S4 schema (S4.1–S4.4, after S1)") S4.5 (the D18
gate) is the *next* checkpoint, not this one — see 1.2.

- **S4.1 — L2 projection model.** Container vs leaf node; open per-book block vocabulary
  (PLL build-now: `paragraph`, `verse`, `embedded-letter` container); the **no-double-ownership**
  invariant (a container owns children + heading/signature atoms; a leaf owns body atoms; no atom
  owned twice); **B can re-atomize and re-type, not merely re-group** (R3/D5 — the block-classifier
  output is correctable). Pure core dataclass, **no language opinion** (S0.2 neutrality holds).
- **S4.2 — `node_id` identity + minting split.** Opaque, persisted, **never recomputed** from
  position/designation/content (D33 store-and-rebind). Humans mint *container* ids; the extractor
  machine-mints *leaf* ids; a `minted_by` field records which. Property: id stable across
  re-serialize **and after a positional move**.
- **S4.3 — Handle policy + rendered handles + alias records.** Per-node-class `handle_policy`
  (`position-path` | `designation-string` | `title` | …) with inheritance; `(node_id, handle_policy)`
  *renders* `short` / `parse_md` / `html_slug` (one source of truth, not parallel schemes); alias
  record `{handle_type, value, scope, locale_or_witness, target_node_id, valid_from, valid_to,
  status}`. Property: a handle change leaves `node_id` fixed, old handle survives as an alias.
- **S4.4 — `structure_map.json` schema + lineage-manifest header.** The JSON-Schema for the durable
  catalogue; the manifest carries **each persisted layer independently versioned with its own stale
  class** (M3): raw witness hashes, atom-store version (S1.5), relation-store version (S7.1c),
  `canonical_stream_id` + canonical-projection hash, the resource + normalizer versions (S3.0),
  profile + recognizer versions. `geom` shape consumed from S1.1's frozen slot.
- **+ the constant gap (S4.4-owned):** add `STRUCTURE_MAP_STALE_CLASS` to `structure/artifacts.py`
  (§2.1 — it is **missing**, and the M3 "each layer its own stale class" rule has a hole there today).

@@@@@@
**Audit R2-02 - the scope needs an explicit artifact/API inventory.** "S4.1-S4.4 + constant" is a good
milestone boundary, but it does not name the concrete outputs per step: model module(s), public exports,
validator entry points, schema path, fixture path, reader/writer functions, and tests. Without that
inventory, S4.4 can quietly absorb S5/S8 behavior because "schema + manifest" is too broad. Add a
small deliverable matrix so each checkpoint has a bounded surface and a reviewer can tell when a
proposed helper is scope creep.
@@@@@@

======
**Response (R2-02) — AGREE.** Strong; this is the bounded-surface guard against S4.4 absorbing S5/S8.
Resolution: the revision adds a **§1.5 deliverable matrix** — per step a row of {module · public exports ·
schema/fixture path · reader/writer fn · tests}. A proposed helper that doesn't map onto a row is, by
construction, scope creep and gets challenged. (This pairs with R2-11/R2-12: the matrix names the
**public reader/validator** as the one entry point, so "helper outside the matrix" and "integrity check
outside the public path" are the same smell.)
======

### 1.2 The closing gate (next checkpoint, not this wave) — **S4.5, D18 schema-born**

S4.5 hand-authors a **second-structure synthetic fixture built to DIFFER from PLL** (depth-0 body,
`designation-string` handle policy, non-ordinal headings, mismatched body segmentation, alias-uniqueness,
stale-manifest failure, relation-endpoint resolution) and ratifies the schema by validating it. It is
the **same** adversarial fixture S9.4 later drives end-to-end, and is **distinct from `books/synthetic`**
(which is a *miniature PLL* — prefazione + Italian ordinals + H2/H3, §2.8). The gate rule:
**no B/C task (S5–S8, S10) reaches DONE until S4.5 is green** (`ENGINE_STRUCTURE_TASKS.md:164`).

> The coupling between S4.4 and S4.5 is real and is **fork O5 (§6).** This wave validates the schema
> against a *conforming* (PLL-shaped) fixture — proving it *accepts* a valid map. S4.5 validates it
> against the *differ*-fixture — proving it *generalizes*. The S4.5 done-when says "the schema is not
> 'born' until [the differ-fixture] validates," which is an argument for folding S4.5 into this push.
> Defaulting to the wave split (S4.5 next), open to folding.

@@@@@@
**Audit R2-03 - S4.5 currently depends on C-layer behavior the wave explicitly excludes.** The S4.5
fixture includes relation-endpoint resolution, while 1.3.3 says the relation-store schema is S7.1c and
out of scope. That can only work if S4.5 defines a minimal endpoint-reference contract over `node_id`
that does not require `relations.json`, or if relation-endpoint resolution is removed from S4.5 and
left to S7/S8. As written, the gate can be blocked by an artifact this plan says not to build.
@@@@@@

======
**Response (R2-03) — AGREE; real tension, resolved by a split done-when.** Verified: the S4.5 tracker
row does list "relation-endpoint resolution" among the fixture's dimensions, and relations are C-layer
(S7). Resolution: S4.5 **authors** the differ-fixture with relation endpoints expressed as the §3.2
typed endpoint union over `node_id`/`SpanRef` (a structural reference, needing no `relations.json`
schema), but the **resolution** of those endpoints is exercised when S7/S9.4 land. So S4.5-green =
*schema-born* (structure validates · alias-uniqueness-in-scope · stale-manifest fails) with the relation
dimension **present-but-not-yet-resolved**; the endpoint-resolution check is explicitly a **S9.4-time**
gate on the same fixture (which is exactly why the tracker pairs S4.5 with S9.4 on one fixture). I'll
split S4.5's done-when accordingly so no C artifact can block the schema-birth gate.
======

@@@@@@
**Audit 2 — the S4.5 split needs a hard "not born / not downstream-eligible" state, not a soft fork.**
The tracker is explicit: S4.5 is the D18 schema-birth gate and no B/C task reaches DONE until it is
green. The draft acknowledges this but still treats folding S4.5 as an open implementation choice.
That is fine only if S4.4's output is labelled "provisional schema accepted by conforming fixture" and
the build order makes it impossible to treat S4.4 as a stable downstream contract before S4.5 passes.
Otherwise the conforming PLL-shaped fixture becomes the de facto schema lock, and S4.5 turns into a
post-hoc compatibility test rather than the birth gate it is supposed to be.
@@@@@@

======
**Response (Audit 2) — AGREE; this sharpens O5 from a soft fork to a hard state.** Resolution: regardless
of whether S4.5 is folded in, S4.4's output is labelled with an explicit **`schema_status`** token —
`provisional` (accepted by a conforming PLL-shaped fixture only) until S4.5 flips it to `born`. The build
order **forbids** any B/C task (S5–S8, S10) from treating a `provisional` schema as a stable contract —
they list S4.5, not S4.4, as upstream (the tracker already does this at line 164; I'll make the state token
the mechanism that enforces it). That makes folding S4.5 a **scheduling** choice, never a **correctness**
one: the conforming fixture can't masquerade as the birth certificate because the token says it isn't.
======

### 1.3 Explicitly NOT in this wave (owned by neighbours — do not build here)

1. **`rebind_anchors` *population* / the re-attach algorithm** → **S5.1.** S4.4's schema *admits* the
   anchor sub-object (geom region + content fingerprint + struct-path), but populating it and the
   bind/fail-loud logic are S5. The active rebind *mode* (`geometry-primary | …`, conditionally
   selected at S2.0, re-gated at S2.2) is *recorded in* the lineage by S5 — S4.4 only reserves the slot.
2. **The stale-fail *loader* / migration router** that *compares* a stored manifest to the live
   constants and routes the repair → **S8.1.** S4.4 *produces and stamps* the manifest + stale class;
   S8.1 *consumes* it. (Same split atom-store took: S1.5 registered the class, S8.1 routes on it.)
3. **The relation-store schema + its stale class** → **S7.1c.** S4.4's manifest carries a *slot* for
   the relation-store version (`RELATION_STORE_SCHEMA_VERSION` already exists, §2.1); the relation
   schema itself and `RELATION_STORE_STALE_CLASS` are C-layer, built at S7.1c. (Boundary fork O1, §6.)

@@@@@@
**Audit R2-04 - define the "relation store absent" state now.** If S4.4 stamps a relation-store schema
version before `relations.json` exists, the loader/schema needs a legal representation for "no relation
store has been authored yet." That is different from "relation store exists and is stale" and different
from "relation store missing unexpectedly." Without an explicit absent/pending state, S8.1 will inherit
an ambiguity that could either mask a missing C artifact or fail every early B-only workspace.
@@@@@@

======
**Response (R2-04) — AGREE.** Resolution: the manifest's per-layer entry carries an explicit **presence
state** — `present: false` for the relation-store until S7.1c authors `relations.json` — a third, legal
state distinct from `present:true + stale` and from `missing-unexpectedly` (a hard load error). S8.1
then routes on `(present, version-match)`, never on file-existence alone, so a B-only workspace is valid
(relation-store legitimately absent) while a *vanished* relation-store after one existed is still caught.
This folds together with Audit 1's resolution below — both are about legally representing the not-yet-built
C layer.
======

@@@@@@
**Audit 1 — O1 is currently a contradiction, not just a fork.** The draft says S4.4's manifest carries
all three persisted-layer versions "each with its stale class" (1.1, D-S4-E, inv 11), but 1.3.3 and
O1 recommend not minting `RELATION_STORE_STALE_CLASS` until S7.1c. Both cannot be true in an executable
S4.4 manifest. Pick one: either S4.4 pre-places `RELATION_STORE_STALE_CLASS` as a declared forward
contract, or the S4.4 manifest/schema only carries the relation-store **schema version** plus an
explicit `stale_class: null | pending` shape until S7.1c upgrades it. The current wording lets the
test battery demand a field no constant can legally supply.
@@@@@@

======
**Response (Audit 1) — CONCEDE; you're right, it's a contradiction, not a fork.** inv 11 + D-S4-E demand
"all three versions, each with its stale class" while O1/1.3.3/D-S4-F default to *not* minting
`RELATION_STORE_STALE_CLASS`. Both cannot hold in an executable manifest. **I'm overruling my own O1
default:** pre-place `RELATION_STORE_STALE_CLASS` now. Rationale: it's an inert wire-string — the
`artifacts.py:43` atom-store docstring already forward-references "the structure-map (B) and relation-store
(C) classes" — and minting a constant is not "building C behavior" (no relation schema, no loader). Combined
with R2-04's `present:false`, the manifest legally declares the relation-store layer (class + version +
presence) before `relations.json` exists. This dissolves the contradiction and the absent-state ambiguity
in one move. **O1 is therefore resolved (pre-place), not left open** — I'll rewrite 1.3.3 / D-S4-F / inv 11
and strike O1 from the §6 fork list.
======

4. **The three orthogonal read-axes** (`role` / `authorship` / `content_provenance_class`) → **S6.1.**
   S4.1 carries the *fields* the §11.2 sketch shows (`role`, `designation`, `title`, `authorship`
   override), but the derived-flag policy (`translatable` / `counts_for_retention` / …) and the
   L1↔L2 provenance-distinctness enforcement are S6.

@@@@@@
**Audit 14 — S6 fields are being smuggled into S4 without their semantics.** Section 1.3.4 says S6 owns
the three orthogonal read axes and derived-flag policy, but D-S4-B says S4.1 carries fields such as
`role`, `designation`, `title`, and `authorship`. `designation`/`title` are needed for handles, but
`role` and `authorship` are policy-bearing fields. If they exist in S4.1, consumers may start depending
on them before S6 defines enforcement. Either keep S4.1 to display/handle metadata only, or mark the S6
fields as schema-reserved and non-semantic until S6 activates validation.
@@@@@@

======
**Response (Audit 14) — CONCEDE.** The split is exactly right: `designation`/`title` are handle inputs
(active in S4.3); `role`/`authorship` are policy-bearing (S6). Resolution: S4.1 carries `role`/`authorship`
as **schema-reserved, non-semantic** fields — present so S6 needn't bump the schema, but **no S4-era
validator or derived-flag reads them**, and a test asserts that (grep/AST control: no S4 module references
them in a switch). This is the "reserved-not-active" discipline; it also satisfies §3.3's requirement that
the L1↔L2 provenance *distinctness* enforcement is S6's, not smuggled in early.
======

### 1.4 Forward, with their own tracker rows (named, not silently dropped)

- **S4.6 — hand-author the PLL container map (~61 containers). Owner: Ben (human-in-the-loop).**
  Depends on S4.4's schema. Not engine code; a human authoring task. Named here so the schema is
  designed to be *hand-authorable* (the `typography.json` precedent), but built later.

@@@@@@
**Audit 15 — S4.6's human-evidence requirements are not reflected in the schema planning.** The tracker
requires the PLL map authoring workflow to capture review comments, minimum evidence beyond the skeleton,
and the embedded-letter placement ruling. The draft says S4.6 is later and the schema should be
hand-authorable, but it does not reserve anywhere for authoring evidence, comments, or rulings. If those
live in a sidecar, name it. If they live in `structure_map.json`, reserve the fields now. Otherwise S4.6
will force schema churn immediately after S4.4.
@@@@@@

======
**Response (Audit 15) — CONCEDE the gap; refine the fix.** The *ruling* already has a home: §3.6 specs a
`decision` provenance enum per node (`human-approved | plugin-suggested | inherited`) — that belongs **in
the map** and S4.4 reserves it now. The *prose* evidence (review comments, minimum-evidence-beyond-skeleton,
the embedded-letter placement rationale the tracker requires) should **not** inflate `structure_map.json`;
it lives in a named **authoring-evidence sidecar** keyed by `node_id` (the `typography.json`-vs-its-review-notes
split). Resolution: S4.4 reserves the in-map `decision` field + names the sidecar path; S4.6 populates both.
That forecloses the churn you flag without turning the map into a comment log.
======

- **S4.7 — scale check (D35).** Sub-quadratic traversal / reference-integrity / re-bind at 10⁴→10⁵
  leaves; shares the S1.4/S1.5 round-trip benchmark fixture. Its own row; not this wave.

@@@@@@
**Audit 17 — S4.7 is deferred, but representation choices made here can make it impossible.** The scale
row requires sub-quadratic traversal, reference resolution, and rebind lookup including serialize, load,
and index-build. S4.1/S4.4 should at least commit to an addressable storage/indexing posture: flat node
table keyed by `node_id`, precomputed parent/child indexes on load, and no repeated tree scans inside
reference validation. Leaving this entirely to S4.7 risks discovering the O(n^2) problem after the JSON
shape is already blessed.
@@@@@@

======
**Response (Audit 17) — AGREE on the storage posture; push back on prescribing the index impl.** D35/§3.5
already **mandate** "node storage is a flat addressable list" and "no structure operation super-linear in
unit count" — so I'll make that explicit in D-S4-B: a **flat node table keyed by `node_id`**, and
reference-validation must **not** re-scan the tree per ref (it resolves through the id-keyed table). That's
your core point and it's non-negotiable in the schema shape. But *precomputed parent/child indexes on load*
is an **implementation strategy** S4.7 should measure, not S4.4 freeze — the schema must **enable**
sub-quadratic (flat list + id keying + child-list ordering), not **prescribe** a specific index build.
So: addressable posture committed now; index mechanism validated at S4.7. (This dovetails with Audit 12's
flat-table + canonical-child-ordering decision.)
======

---

## 2. Surfaces it binds into (verified this session — line numbers are this-session reads)

@@@@@@
**Audit R2-05 - "verified this session" is not durable evidence.** This section is useful working
context, but line numbers in an untracked draft and active codebase will rot. Before distilling into
`s4_plan.md`, replace line-number-only evidence with stable anchors: symbol names, test names, commit
hash/branch if available, and the exact invariant each read supports. Otherwise the final plan will
look more precise than it is.
@@@@@@

======
**Response (R2-05) — AGREE.** The line numbers are working-context for *this* review against HEAD
`d611702`; they will rot. Resolution: the distilled `s4_plan.md` replaces line-number evidence with
**symbol names + test names + the commit hash** (e.g. "`structure.Geom` present/absent state machine,
`atoms.py`; pinned by `test_atoms.py::…`"). I've stamped `d611702` in §7 now so every read in this draft is
reproducible at a fixed tree, and the precision claim is honest.
======

### 2.1 `structure/artifacts.py` — constants: what exists, what's **missing**

- `STRUCTURE_MAP_SCHEMA_VERSION = 1` (`:47`) and `RELATION_STORE_SCHEMA_VERSION = 1` (`:49`)
  **already exist**, minted with M3-aware docstrings ("Bound by S4.4" / "Bound by S7.1c"). S4.4 does
  **not** mint these — it *consumes* `STRUCTURE_MAP_SCHEMA_VERSION` and binds it (§2.4).
- `ATOM_STORE_STALE_CLASS = "atom-stream"` (`:45`), `RESOURCE_STALE_CLASS = "resource-set"` (`:61`),
  `NORMALIZER_STALE_CLASS = "normalization-policy"` (`:66`) exist.
- **`STRUCTURE_MAP_STALE_CLASS` does NOT exist.** The structure-map and relation-store layers have a
  schema *version* but **no stale *class*** — yet the atom-store docstring (`:43`) forward-references
  "the structure-map (B) and relation-store (C) classes" as if they do. **This is the one real code
  gap; S4.4 closes the B half** (D-S4-F).
- Path accessors are **already built** (S0.1 scaffold): `STRUCTURE_MAP_FILENAME = "structure_map.json"`
  (`:75`), `structure_map_path(workspace)` (`:88`) → `<work>/structure_map.json` at the work root.
  S4.4 fills the schema + writer/reader; the path is done.

### 2.2 `structure/lineage.py` — `ResourceLineage.to_json()` is consumed verbatim

`to_json()` (`:187–207`) already emits a clean embeddable fragment:
`{schema_version, resource:{version, stale_class, descriptor}, normalizer:{version, stale_class,
descriptor}}`. S4.4's lineage manifest **drops this in under a header key** (e.g. `lineage.resources`).
No re-shaping; S3.0 built exactly the fragment S4.4 needs. (`RESOURCE_LINEAGE_SCHEMA_VERSION` is
versioned *independently* of the three persisted-layer versions — `artifacts.py:53–56`.)

@@@@@@
**Audit R2-06 - embedding `ResourceLineage.to_json()` still needs a schema contract.** "Drop this in
verbatim" is a good anti-reshaping rule, but the structure-map schema must still validate the embedded
fragment against either shared `$defs` or a contract test that fails when `ResourceLineage.to_json()`
changes shape. Otherwise S3.0 can evolve its lineage envelope while S4.4 keeps accepting stale or
misnested resource metadata.
@@@@@@

======
**Response (R2-06) — AGREE; strong.** "Drop in verbatim" is an anti-reshaping rule, not a validation rule —
it rots silently when S3.0's envelope evolves. Resolution: S4.4 adds a **contract test** that constructs a
real `ResourceLineage(...).to_json()` and asserts the structure-map schema validates **exactly that object**
(via a shared `$defs` fragment referencing the same shape, so there is one definition, not two). A shape
change in `lineage.py:187` then fails S4.4 loudly. Added to the §4 battery as a binding invariant
(`feedback_validate_bindings` / `invariants.md` I5 wire-protocol single-sourcing).
======

### 2.3 `config/schema/manifest.schema.json` — the anti-pattern S4.4 must NOT repeat

Line 11: `"schema_version": {"type": "integer", "const": 1}` — a **hard-coded `1` with no Python
constant behind it.** S4.4's row forbids repeating this: the structure-map schema's `schema_version`
`const` must be **bound to `STRUCTURE_MAP_SCHEMA_VERSION`** by validating a version-*derived* fixture
against the schema, not a hand-copied literal. (Schema-dir convention today:
`src/engine/config/schema/*.schema.json` — four config-profile schemas. Location fork O2, §6.)

@@@@@@
**Audit 3 — "version-derived fixture validates against the schema" is not enough by itself to prove the
schema const is not hand-copied.** A static JSON Schema necessarily contains some literal `const`
unless the schema is generated or patched at test time. The plan should state the actual mechanism:
load the schema and assert its `schema_version.const == structure.STRUCTURE_MAP_SCHEMA_VERSION`, or
generate the schema from Python, or keep the static literal but bind it with a byte-exact fixture test
that fails on a constant bump. Right now the prose says "never a hand-copied `1`", but the implementation
path still looks like a hand-copied literal plus a stale-detection test.
@@@@@@

======
**Response (Audit 3) — CONCEDE; precise.** You're right: a static schema with `const: <int>` *is* a
hand-copied literal unless something binds it. Resolution: the binding is **two assertions, not one** —
(a) load the schema JSON and assert
`schema["properties"]["schema_version"]["const"] == structure.STRUCTURE_MAP_SCHEMA_VERSION` (this directly
kills the hand-copy — a divergent literal fails the test), **and** (b) the version-derived fixture validates
against the schema (kills value drift). (a) is the teeth I was hand-waving as "never a hand-copied 1." I'll
rewrite inv 10 and D-S4-E/G to state mechanism (a) explicitly. (Generating the schema from Python was the
alternative; rejected — a static `*.schema.json` is the house convention, §2.3, and (a) gives the same
guarantee without a codegen step.)
======

### 2.4 `tests/fixtures/_generate_structure_fixture.py` — the **correct** precedent to evolve

This generator **already exists** as a trivial S0.3 tier-spine placeholder. It writes
`{schema_version: structure.STRUCTURE_MAP_SCHEMA_VERSION, _placeholder: …}` to
`tests/fixtures/structure/trivial_structure_map.json`, **deriving the version from the live constant**
(`:38–39`), with a single byte-exact `render()` shared by the writer (`main`) and the binding test
(`:47–53`). Its docstring is explicit: *"The real structure-map schema is S4.4; this MUST NOT
anticipate it."* So S4.4 **evolves this generator** from trivial→real (a conforming PLL-shaped map),
keeping the *derive-don't-hardcode* + *one-renderer* discipline it already encodes. This is the
binding pattern to follow; `manifest.schema.json` (§2.3) is the one to avoid.

### 2.5 `tests/unit/test_structure_artifacts.py` — what's already pinned

The three persisted-layer versions are pinned **independent positive ints** (`:30–44`); the work-root
locations are pinned distinct (`:63–80`); the package exports resolve (`:90`). So S4.4's "manifest
lists all three versions" has the *constants* + their *independence* already covered; S4.4 adds the
*schema* that embeds them and the *manifest assembly*.

### 2.6 No L2 node/projection model exists yet

`structure/` holds `atoms.py`, `atom_store.py`, `typed.py`, `classify.py`, `capture.py`,
`roundtrip*.py`, `lineage.py` — **no projection/node/map module.** S4.1 creates it (proposed
`structure/projection.py` or `structure/nodes.py`; name is an impl detail). The package docstring
(`structure/__init__.py:4`) already frames the L1→L2→L3 substrate, so the home is reserved.

### 2.7 Two different "geom"s — keep them distinct (S1.1 vs §11.2)

- **Atom-level `geom`** (S1.1, frozen): a slot **on each L1 atom**, `{present|absent}` +
  `{geometry_engine, matched_witness_id, match_method, match_confidence}` — **absence is first-class,
  never-invented coordinates** (copy3 is geometry-free). This is the **authoritative** geometry record.
- **Node-level `rebind_anchors.geom`** (§11.2 sketch: `{page, bbox_region}`): a **derived checkpoint
  region** on an L2 node, used by S5 to re-attach a stored `node_id` to fresh atoms. It is *not* the
  atom provenance and must **not duplicate it.** S4.4's schema admits the region as **optional /
  nullable** (mirroring S1.1's first-class absence; the differ-fixture is geometry-free by design,
  like copy3). Population is S5 (§1.3.1). (Fork O4, §6 — required-vs-optional on the node.)

@@@@@@
**Audit 11 — the node-level `geom` story is internally inconsistent.** Section 2.7 says node
`rebind_anchors.geom` is an optional derived checkpoint region (`page` + `bbox_region`) and must not
duplicate atom provenance. Inv 13 then says an anchor with `geom.present=false` validates, which imports
the atom-level `Geom` state machine into the node. The tracker row also says S4.4 consumes S1.1's geom
shape including match-provenance. Resolve this before schema work: either node anchors store a separate
nullable region summary with no `present` flag, or they embed/refer to atom-level `Geom` records with
provenance. The current mixed model will produce a schema nobody can reason about.
@@@@@@

======
**Response (Audit 11) — CONCEDE; verified against code, you're exactly right.** `structure.Geom`
(`atoms.py:41`, HEAD `d611702`) is a real `{present | absent}` state machine with six match-provenance
fields (`page`, `bbox`, `geometry_engine`, `matched_witness_id`, `match_method`, `match_confidence`) —
present → all six required, absent → all `None` — and it lives **on atoms**. The node
`rebind_anchors.geom` (§11.2) is a *different*, simpler `{page, bbox_region}` region summary. My inv 13
wrote "anchor present with `geom.present=false`," which wrongly imports the atom state machine into the
node — your "schema nobody can reason about" is the precise consequence. Resolution: the node anchor stores
a **plain nullable region** (`{page, bbox_region}`, or the whole `rebind_anchors` absent) with **no
`present` flag and no atom-`Geom` sub-object**; the authoritative `Geom` provenance stays on atoms, and the
node merely points at atoms that carry it. I'll rewrite §2.7, D-S4-H, and inv 13 to: "a node with no
`rebind_anchors` validates; a node with a `{page, bbox_region}` region validates." Good catch.
======

### 2.8 `books/synthetic` — the mini-PLL, the thing S4.5 differs from

`books/synthetic/manifest.json` + `inputs/` is a **miniature PLL** (prefazione + 1 part, Italian
ordinals, H2/H3). S4.5's gate fixture must be a **new, differ fixture** (depth-0, designation-string,
non-ordinal) — *not* an extension of `books/synthetic`. Confirmed it exists so we don't conflate them.

---

## 3. Design decisions (proposed — `D-S4-x`; each is RECOMMENDED-with-rationale unless tagged OPEN)

### D-S4-A — Scope seam: build S4.1→S4.4 + the constant; gate at S4.5 next
Linear build chain (S4.1→S4.2→S4.3→S4.4, each its own green checkpoint), validated this wave by a
*conforming* fixture. S4.5's *differ*-fixture is the birth-certificate gate, defaulted to the next
checkpoint (fork O5). Rationale: matches the W2/W3 wave split and the per-step cadence; keeps the
keystone reviewable in bounded slices.

### D-S4-B — L2 projection model (S4.1)
A node is **container** (owns ordered `children` + optional `heading_atoms`/signature atoms) **or
leaf** (owns `body_atoms`). The **no-double-ownership** invariant is a hard, tested property: the
union of all owned `atom_id`s across all nodes has no duplicate, and no atom is both a child-owned
heading and a body atom. Block `class` is an **open string vocabulary** (PLL: `paragraph`, `verse`,
`embedded-letter`, `front-matter`, `chapter`), validated against a **per-book registered set**, never
a core enum (neutrality). B can **re-type** a node (correct a mis-classified atom) and **re-atomize**
(split/merge), not only re-group (R3/D5). Pure dataclass; no language literal in `structure/`.

@@@@@@
**Audit R2-07 - `class`, `node class`, and `block vocabulary` are overloaded.** The plan uses one
`class` field for leaves (`paragraph`, `verse`), containers (`chapter`, `embedded-letter`), matter
roles (`front-matter`), and handle-policy lookup keys. Those are not all the same axis. Either define
a single intentionally broad `node_class` vocabulary and keep `role`/matter separate, or split leaf
block type from container type. If this stays implicit, S6/S10 can start treating a structural role as
a block class or vice versa.
@@@@@@

======
**Response (R2-07) — CONCEDE.** `class` is doing four jobs. Verified the §11.2 sketch already half-separates
them: the `n_chap` node carries **both** `class:"chapter"` and `role:"body"`. Resolution: pin three distinct
axes — **`node_class`** = the structural/block type vocabulary (container types {`chapter`, `front-matter`,
`embedded-letter`} ∪ leaf types {`paragraph`, `verse`, …}); **`role`** (front|body|back) = a *separate*
reserved axis (S6, per Audit 14); **`handle_policy`** = its own per-`node_class` table. `front-matter` is a
`node_class`, and `role:front` is the orthogonal matter flag — not the same field. I'll split these in
D-S4-B so S6/S10 cannot conflate a role with a block class.
======

@@@@@@
**Audit 9 — no-double-ownership and coverage are conflated.** Inv 1 says every `atom_id` is owned by
exactly one node, but L1 explicitly supports captured-but-excluded atoms and source furniture. The hard
invariant should be "no owned atom appears in two ownership slots"; a separate coverage invariant should
state which canonical atoms must be owned (probably included body/heading/signature atoms) and which may
remain unowned or assigned to a furniture bucket. If this is not separated, the schema will either reject
valid captured-excluded atoms or silently force furniture into body structure.
@@@@@@

======
**Response (Audit 9) — CONCEDE; verified.** `capture.py` captures furniture as `processing_scope="excluded"`
atoms — "captured-with-role, never dropped" (`capture.py:18`, HEAD `d611702`) — so inv 1 as written ("every
`atom_id` owned by exactly one node") would reject them. Resolution: split inv 1 into **1a — no
double-ownership** (no atom appears in two ownership slots; not both a child-owned heading and a body atom —
the hard structural invariant) and **1b — coverage** (every *included* canonical atom — body/heading/signature
— is owned by exactly one node; *excluded/furniture* atoms may be unowned or assigned to an explicit
furniture bucket, **never forced into body structure**). I'll rewrite inv 1 → 1a/1b and D-S4-B. This also
keeps S4 honest about the `processing_scope` axis L1 already carries.
======

@@@@@@
**Audit 10 — "B can re-atomize" is underspecified against an atom-id ownership model.** If a leaf owns
`body_atoms: [atom_id]`, then split/merge re-atomization changes L1 atom identity or requires owned spans
rather than atom ids. The draft says S4.1 supports re-atomization, but no side effect on the atom store,
derived-atom lineage, or rebind/regen guard is named. Either constrain S4.1 to representing corrected
grouping/re-typing over existing atoms, or explicitly add the re-atomization protocol it needs
(new atom ids, derivation links, stale class impact, and ownership migration).
@@@@@@

======
**Response (Audit 10) — CONCEDE; important.** Right: if a leaf owns `body_atoms:[atom_id]`, true
re-atomization (split/merge → *new* atom identities) is an **L1 event** — supersession-by-new-stream
(D25/§3.6), with derivation links and an atom-store stale-class impact — **not** an S4.1 capability.
Resolution: scope S4.1 to **re-group + re-type over existing atom ids** (the projection is corrected without
minting atoms); genuine re-atomization is the L1 supersession path owned by **S8.2/D25** and is explicitly
**out of S4.1**. The tracker's word "re-atomize" describes the *eventual* B capability; S4.1 builds the
re-group/re-type half, and I'll log the L1 re-atomization protocol (new ids · `derived_from` links · stale
impact · ownership migration) as its own later surface so it isn't silently dropped. D-S4-B reworded.
======

@@@@@@
**Audit 12 — flat vs nested representation is not pinned.** The draft mentions containers with ordered
`children`, plus `parent`/`children` reference-integrity checks. If both parent pointers and child lists
are persisted, S4.4 needs bidirectional consistency invariants, root-count rules, orphan rules, and a
canonical ordering source. If only one direction is persisted and the other derived, say so now. This
choice affects schema shape, move semantics, diffability, and S4.7 complexity.
@@@@@@

======
**Response (Audit 12) — CONCEDE.** Verified: the §11.2 sketch persists **both** `parent` (on `n_chap_p1`)
and `children` (on `n_chap`). Resolution: pin the **`children` list as the canonical, ordered source of
truth**; `parent` is a **persisted-but-derived** back-reference carrying a **bidirectional-consistency
invariant** — every `parent` agrees with exactly one node's `children`; exactly one root; no orphans; no
cycles. Reading order comes from the child list (not from `parent`). This is the flat-table + child-ordering
posture Audit 17 needs for sub-quadratic traversal, and it gives inv 14 concrete reference-integrity
sub-checks (parent↔child agreement, single-root, acyclicity). Added to D-S4-B.
======

@@@@@@
**Audit 13 — per-book block vocabulary needs a storage and validator contract.** D-S4-B says block
`class` is an open string vocabulary validated against a per-book registered set, but the plan does not
say whether that set lives in the structure map header, the language/profile config, or a recognizer
profile. Plain JSON Schema cannot validate against an external per-book registry without a custom
validator. S4.1/S4.4 should name the registry location and the validation boundary, or this will fall
back to either an accidental core enum or no validation at all.
@@@@@@

======
**Response (Audit 13) — CONCEDE; interlocks with R2-11.** Plain JSON Schema can't validate against an
external per-book registry. Resolution: the registered `node_class` set lives in the **structure-map header**
as a self-declared `block_vocabulary` (the map is the HITL-authored, self-describing artifact — so it
validates standalone; S9.1's structure *profile* may later *seed* candidates, but the map remains the
authority). The **validation boundary**: JSON Schema validates *shape* (a `node_class` is a non-empty
string); the **semantic validator** (R2-11) enforces `node.node_class ∈ header.block_vocabulary`. That keeps
the vocabulary out of core (no enum, neutrality holds) and gives it real teeth (not "no validation"). I'll
name the registry location (map header) and the boundary in D-S4-B/D-S4-E.
======

### D-S4-C — `node_id` identity + minting split (S4.2): pin PROPERTIES, scheme is impl
The id is an **opaque string**; the binding requirements are pinned as tests, the concrete scheme is
an implementation detail (fork O3). Pinned properties: (a) **stable across re-serialize**; (b) **stable
across a positional move** (re-mint proves position-independence — move a node, id unchanged);
(c) **never derived from** position, designation, or content (the D33/BR-021 clause — forbids the
"wrap a designation-derived string in a new field" cheat); (d) `minted_by ∈ {human, machine}` recorded
per node (human for containers, machine for leaves). Proposed default scheme (revisitable): a short
opaque prefix + monotonic counter for human containers (`n_…`), a ULID-like token for machine leaves —
chosen *for the fixtures*, not load-bearing.

@@@@@@
**Audit R2-08 - `minted_by` needs actor semantics for generated fixtures.** The conforming fixture and
S4.5 differ-fixture will be generated or hand-authored by test code, but the nodes inside them are
supposed to model human-minted containers and machine-minted leaves. Say whether `minted_by` records the
conceptual authority for the id, the runtime actor that wrote the JSON, or both. If it is only an enum
with no provenance semantics, tests can pass while the authoring workflow mints all ids through one
mechanical path.
@@@@@@

======
**Response (R2-08) — CONCEDE.** Resolution: `minted_by` records the **conceptual minting authority** —
`human` = a human authored/approved this *container's* id; `machine` = the extractor minted this *leaf* id —
**not** the runtime process that serialized the bytes. A fixture generator writing all the JSON does not make
every node `machine`; the fixture *models* the authority split (container nodes are `human` even though test
code emitted them). I'll state this in D-S4-C so a test can't pass while the real authoring workflow collapses
the distinction into one mechanical path. (This is the field's *semantics*; the *enforcement* that containers
are human-authored is the S4.6 HITL workflow's, named in Audit 15's sidecar.)
======

@@@@@@
**Audit 5 — `node_id` non-derivation is under-proven.** Inv 6 catches the obvious cheat
(`node_id = html_slug`) but not a hash/base64/ULID-seeded transform of position, designation, or content.
No unit test can fully prove a negative here. The plan should downgrade the test claim to "reject common
derivation cheats" and add a design-control requirement: id minting happens through a store/rebind API
that receives no designation/path/content inputs for id generation, plus fixture examples where ids
survive changes to all three. Otherwise the audit will overtrust a substring test.
@@@@@@

======
**Response (Audit 5) — CONCEDE.** You're right: no unit test proves the negative. Resolution: downgrade the
*test* claim (inv 6) to **"rejects common derivation cheats"** (equality + substring/slug/known-transform of
handle/designation), AND add a **design control**: id minting goes through a `mint_node_id()` seam that
receives **no** designation/path/content argument — it cannot derive from inputs it never sees — plus fixture
cases where an id survives changes to designation, position, **and** content. The negative-proof is
*structural* (the API's input set), the substring test only catches the lazy cheat. I'll rewrite inv 6 and
D-S4-C to state both, so the audit trusts the seam shape, not the substring.
======

### D-S4-D — Handle policy + rendered handles + alias records (S4.3)
`handle_policy` is **per node-class**, declared in the map's `handle_policies` table, **inherited down
the tree** unless a node overrides. The visible handle (`short`/`parse_md`/`html_slug`, the provenance
key, the revision key) is a **rendering of `(node_id, handle_policy)`** — one source of truth. An
**alias record** preserves a retired handle: `{handle_type, value, scope, locale_or_witness,
target_node_id, valid_from, valid_to, status}`. Pinned property: change a handle → `node_id` fixed,
new handle renders, **old handle survives as a `status:active` alias** resolving to the same node.
(Alias **collision-in-scope** is a fail-loud negative — but that negative is S8.3/S9.2b; S4.3 builds
the record + the resolve, the collision battery lands with governance.)

@@@@@@
**Audit R2-09 - decide whether rendered handles are persisted or derived-only.** The prose says handles
render from policy, but the §11.2 sketch stores a `"handle"` field on nodes. If persisted, it is a cache
that needs stale-cache detection when designation/title/position changes. If derived-only, it should not
be required by the schema. This matters for round-trip tests: a load-dump cycle can preserve a stale
stored handle unless the reader recomputes and compares it.
@@@@@@

======
**Response (R2-09) — CONCEDE; pairs with Audit 6.** Verified the §11.2 sketch shows a `"handle"` field, which
reads as persisted. Resolution: rendered handles are **derived-only, not source-of-truth**. Lean: don't
persist them — persist only the policy inputs (`designation`/`title`/position-via-tree). **If** a `handle`
value is persisted as a convenience, it is a **non-authoritative cache** the reader **recomputes and compares
on load**, fail-loud on mismatch — exactly the atom-store precedent (`test_load_detects_stale_raw_source_hash`,
`atom_store.py`). I'll decide derived-only in D-S4-D and, if any handle is cached, bind it with the
recompute-on-load check so a load-dump can't launder a stale handle.
======

@@@@@@
**Audit 6 — handle rendering cannot literally be a function of `(node_id, handle_policy)` alone.**
`designation-string` and `title` policies need node data; `position-path` needs ancestor/sibling context;
HTML slugs need collision/disambiguation rules. The safe contract is closer to
`render_handle(map, node_id, policy, target_format, scope)`. Keep "one source of truth", but do not
encode the false idea that `node_id + policy` contains enough information. That false simplification
will hide slug collisions and ancestor-context bugs.
@@@@@@

======
**Response (Audit 6) — CONCEDE the contract.** Right: `position-path` needs ancestor/sibling context, slugs
need collision/disambiguation rules — so the real signature is
`render_handle(map, node_id, policy, target_format, scope)`, not `f(node_id, policy)`. Note: PLAN §3.4 itself
says "a rendering of `(node_id, handle_policy)`" — that's the same shorthand for "the policy applied within
the map context"; I'll spell out the full signature in D-S4-D so the shorthand can't hide ancestor-context or
slug-collision bugs. "One source of truth" survives (the map + policy fully determine the handle); the false
simplification (the pair *contains* enough info) does not. inv 8 gets ancestor-context and slug-disambiguation
cases added.
======

@@@@@@
**Audit 7 — alias collision handling is too late if S4.3 ships a resolver.** D-S4-D says S4.3 builds
the alias record and resolve behavior, while collision-in-scope negatives land later with governance.
That creates a window where resolver semantics are undefined for two active aliases in the same scope.
If a resolver exists in S4.3, active alias uniqueness in scope must be enforced in S4.3, even if S8/S9
later add broader governance batteries. Otherwise the first resolver implementation can accidentally
choose "first match wins" and become observable behavior.
@@@@@@

======
**Response (Audit 7) — CONCEDE; sharp.** If S4.3 ships a resolver, two active aliases in one scope is
undefined behavior that hardens into "first-match-wins." Resolution: **active-alias-uniqueness-in-scope is
enforced in S4.3** as the resolver's precondition — `resolve()` raises on a scope containing two
`status:active` aliases for one handle value (rather than silently picking one). The *comprehensive* negative
battery (every collision class, the fail-loud governance sweep) still lands at **S8.3/S9.2b**, but the local
uniqueness guard ships **with** the resolver so the first implementation can't make "first match wins"
observable. I'll move the uniqueness invariant into S4.3's done-when (and add it to inv 9's neighborhood).
======

@@@@@@
**Audit 8 — `valid_from` / `valid_to` are named but not grounded.** Alias records include temporal
validity fields, but the plan never defines the clock: structure-map revision number, schema version,
Git commit, source-artifact hash, wall date, or map-local generation counter. Without that, validity
cannot be validated or compared. S4.3 should either define a map-local revision coordinate now or defer
the fields until the governance layer has a concrete revision model.
@@@@@@

======
**Response (Audit 8) — CONCEDE.** No clock is defined. Resolution: introduce a **map-local revision
coordinate** now — a monotonic `map_revision` integer in the manifest header, bumped on each authoring change;
`valid_from`/`valid_to` reference *that* coordinate (not wall-time, not git SHA, not schema version). It's
self-contained (no governance-layer dependency) and totally ordered, so an alias can express "retired at rev
N" and validity is comparable/testable. I considered your alternative (defer the temporal fields to S8.2) and
**reject** it: aliases ship in S4.3, and an alias without a validity coordinate can't represent retirement —
the very thing the alias exists for. `map_revision` defined in D-S4-D/E.
======

### D-S4-E — `structure_map.json` schema + lineage manifest (S4.4): build to the **ROW**, not the §11.2 sketch
The §11.2 jsonc (PLAN:717–764) **predates S1.5/S3.0** — its `lineage` block lacks the three
persisted-layer versions and the S3.0 resource/normalizer record the **S4.4 *row* now requires**. Build
to the row. The manifest carries: `source_artifacts` (raw witness hashes), `atom_streams` +
`canonical_stream_id` + canonical-projection hash, **atom-store / structure-map / relation-store schema
versions** (each with its stale class — M3), the **`ResourceLineage.to_json()` fragment** verbatim
(§2.2), `profile_version`, `recognizer_version`. The schema lives as a `*.schema.json` (location: O2),
its `schema_version` `const` **bound to `STRUCTURE_MAP_SCHEMA_VERSION`** via the evolved
`_generate_structure_fixture.py` (§2.4), validated by a test that round-trips the derived fixture
through the schema — **never a hand-copied `1`** (§2.3).

@@@@@@
**Audit R2-10 - the canonical-projection hash needs an exact hash target.** The manifest names a
canonical-projection hash, but not the byte/object boundary: raw canonical stream file bytes, normalized
atom payloads, a sorted subset of fields, or a loader-canonicalized envelope. That choice affects stale
behavior. Pin it now, including whether excluded/furniture atoms, gaps, geometry, and stream metadata
participate, so S8.1 does not later discover that the hash either misses real changes or fires on
irrelevant formatting churn.
@@@@@@

======
**Response (R2-10) — CONCEDE; needs an exact target.** Verified the floor: `roundtrip.hash_raw` (`:41`) is
`sha256` over the UTF-8 bytes of the *addressed raw slice* — per-atom, not stream-level. The manifest's
**canonical-projection hash** is a distinct, not-yet-defined digest. Resolution: pin it as a digest over the
**ordered canonical-atom payloads**, with an explicit participating field set — `atom_id` + `text` +
`raw_span` + `raw_source_hash` (the addressing identity) — canonicalized via `lineage._canonical`
(sort_keys/fixed separators), **excluding** volatile metadata so it doesn't fire on formatting churn. The
real sub-question is whether `geom` participates: **lean include** (a geometry change is re-bind-affecting, so
S8.1 should see it), normalizing absent→canonical-null first. Furniture/excluded atoms: included in the
canonical-stream digest iff they're in the canonical stream (per `atom_store`, the canonical stream tiles no
single source and carries no gaps). I'll flag this as an S4.4 sub-decision with its own pin, since "what's in
the hash" determines every stale-routing outcome.
======

@@@@@@
**Audit 16 — D33's regen-guard implication is missing from the build shape.** D33 says the structure map
joins the one-way regen-guard family: it is irreproducible committed data, never silently regenerated.
This plan leans heavily on a generator fixture and writer/reader work but does not state that production
map writes must fail loud on overwrite/regeneration without an explicit human-authoring path. Add this
as an S4.4/S8.1 boundary: fixture generation is allowed for tests; production map regeneration is guarded.
@@@@@@

======
**Response (Audit 16) — CONCEDE; important omission.** D33 puts `structure_map.json` in the
**regeneration-guard family** (irreproducible committed data, alongside translations / `typography.json`), and
my plan leaned on a generator + writer without stating production writes are guarded. Resolution: add the
boundary — **fixture/test generation writes freely under `tests/fixtures/`; a production `structure_map.json`
write fails loud on overwrite of a hand-authored map without an explicit human-authoring / `ALLOW_REGEN`-style
path** (the live `refine.py`/cleanup regen-guard pattern; `invariants.md` I7 write-containment + the
deny-list discipline). The *enforcement* may sit at S8.1, but the *boundary* is declared at S4.4 and the
production writer carries the guard from the start. Named in D-S4-E and added to the §1.3 not-in-scope list as
"enforcement → S8.1, boundary declared here."
======

### D-S4-F — Close the stale-class gap (S4.4): add `STRUCTURE_MAP_STALE_CLASS`
Add `STRUCTURE_MAP_STALE_CLASS = "structure-map"` to `artifacts.py`, mirroring
`ATOM_STORE_STALE_CLASS = "atom-stream"` (wire value + a docstring matching the M3 family).
Export it; pin it in `test_structure_artifacts.py` (distinct from the other classes; the manifest
declares it). **Boundary (fork O1):** whether to *also* pre-place `RELATION_STORE_STALE_CLASS` (S7.1c's)
now, since the atom-store docstring already forward-references it — default **no** (don't claim C-layer
scope; S7.1c adds it), but flagged.

### D-S4-G — Schema-file location + version-binding helper (S4.4) — partly OPEN (O2)
The binding *pattern* is settled (evolve `_generate_structure_fixture.py`, derive-not-hardcode,
one-renderer byte-exact). **Open:** where `structure_map.schema.json` lives — `config/schema/`
(alongside the four config-profile schemas, one loader) vs a new `structure/schema/` (B is a
*work-artifact* schema, conceptually under the `structure/` package, not a config profile). Lean
**`structure/schema/`** (work-artifact, not config), but it introduces a second schema dir + possibly a
second validator entry point — hence a fork, not a unilateral call. Whether the derive-validate test is
**factored as a shared helper now** (S7.1c's relation schema will want the identical binding) or
inlined and factored at S7.1c is a sub-question (lean: inline now, factor at the second consumer —
YAGNI until two real users).

### D-S4-H — Two geoms, no duplication (S4.1/S4.4)
Per §2.7: the node's `rebind_anchors.geom` is an **optional** region checkpoint; the authoritative
geometry provenance lives on atoms (S1.1). S4.4's schema makes `rebind_anchors` (and its `geom`)
**optional** — absence first-class — so a geometry-free differ-fixture (S4.5) and copy3-only nodes
validate. (Required-vs-optional is fork O4 — but "optional" is strongly indicated by S1.1's frozen
absence-is-first-class and by S4.5 being scan-free.)

### D-S4-I — Determinism / canonical serialization (S4.4)
The committed map + the fixture serialize deterministically. Two candidates: (a) reuse the
`lineage._canonical` discipline (`sort_keys`, fixed separators) for any hashed sub-object, while the
human-authored map file itself stays human-diffable `indent=2` like `_generate_structure_fixture.render()`;
or (b) one canonical form throughout. Lean **(a)** — the map is hand-authored (HITL, §3.5), so it must
stay diffable; only the *hashed inputs* in the manifest need canonical byte-form. (Carries the S3.0
determinism lesson forward; not a fork, but called out for the audit.)

---

## 4. Red-first invariant battery (proposed — each written RED first, mutation-pinned)

Numbered for audit pinning. Each must be seen RED against a stated mutation before green
(`feedback_red_first_tests`), and the mechanical mutation pass must purge `__pycache__` between
sub-second cycles (`feedback_mutation_pyc_staleness`).

@@@@@@
**Audit R2-11 - split JSON Schema validation from semantic map validation.** Several listed
invariants cannot be enforced by JSON Schema alone: no-double-ownership, alias uniqueness by scope,
parent/child consistency, handle derivation, and "every ref resolves." The plan should name a public
semantic validator, its error model, and which tests exercise it through the same reader path clients
will call. Otherwise the word "schema validates" will be overloaded and reviewers will miss custom
integrity logic hiding outside the schema.
@@@@@@

======
**Response (R2-11) — CONCEDE; architectural and correct.** Ownership (1a/1b), alias-uniqueness-in-scope,
parent↔child consistency, handle derivation, and ref-resolution are **not** JSON-Schema-expressible.
Resolution: name a **public semantic validator** — `validate_structure_map(map) -> raises` with its own
typed error model — distinct from JSON-Schema *shape* validation; the done-when map tags each invariant with
its tier (**shape** vs **semantic**), and the tests exercise the semantic validator **through the public
reader path** (R2-12), never a private builder. "schema validates" splits into "shape-validates" +
"semantically-validates" so no custom integrity logic hides outside the schema. I'll restructure §4 around the
two tiers and add the validator to the §1.5 deliverable matrix as the single public entry point.
======

1. **No-double-ownership** — across a multi-node map, every `atom_id` is owned by exactly one node;
   a heading atom is not also a body atom. Mutation: drop the dedup check → a shared atom passes.
2. **Container/leaf discipline** — a leaf has no `children`; a container has no `body_atoms`. Mutation:
   allow a node with both → fails.
3. **Ragged depth + heterogeneous siblings** — depth 0–4, recursion, and mixed sibling classes are
   representable and validate. Mutation: hard-code a fixed depth → the depth-0 and depth-4 cases fail.
4. **`node_id` stable across re-serialize** — load→dump→load preserves every id. Mutation: regenerate
   ids on load → fails.
5. **`node_id` stable across a positional move** — move a node among siblings; its id is unchanged,
   its rendered handle re-renders. Mutation: derive id from `struct_path` → id moves, fails.
6. **`node_id` never handle-derived** — assert `node_id` is not equal to / not a substring transform of
   any rendered handle or designation (the BR-021 clause). Mutation: set `node_id = html_slug` → fails.
7. **`minted_by` recorded + correct split** — containers `human`, leaves `machine` in the fixture.
   Mutation: blank `minted_by` → fails.
8. **Handle renders from `(node_id, policy)`** — the same node under `position-path` vs
   `designation-string` renders different handles; the handle is reproducible from the pair. Mutation:
   store a literal handle ignoring policy → the policy-swap case fails.
9. **Alias survives a handle change** — retire a handle; the old value resolves to the same `node_id`
   as a `status:active` alias. Mutation: drop the alias on rename → resolution fails.
10. **Schema `const` ↔ `STRUCTURE_MAP_SCHEMA_VERSION`** — the version-derived fixture validates against
    the schema; bumping the constant without refreshing the fixture **fails** (the manifest.schema.json
    anti-pattern, inverted). Mutation: hard-code `const: 1` → a constant bump passes silently, caught.
11. **Manifest lists all required versions** — the assembled manifest carries atom-store + structure-map
    + relation-store versions, each with its stale class, plus the resource/normalizer fragment.
    Mutation: drop the relation-store slot → fails.
12. **`STRUCTURE_MAP_STALE_CLASS` distinct + wired** — present, exported, `== "structure-map"`, distinct
    from the other three classes, declared in the manifest. Mutation: alias it to `"atom-stream"` → the
    distinctness assertion fails.
13. **`rebind_anchors` optional, absence first-class** — a geometry-free node (no `rebind_anchors`)
    validates; an anchor present with `geom.present=false` validates. Mutation: make `rebind_anchors`
    required → the scan-free fixture fails.
14. **Reference-integrity (intra-map)** — every `parent`/`children` ref resolves to a node in the map;
    every owned `atom_id` is well-formed. Mutation: dangling child ref → fails.
15. **Neutrality** — the new `structure/` modules carry no language/book/typeface literal (extend the
    `test_structure_neutrality.py` scan to the new module). Mutation: plant `"italiano"` → caught.

### Done-when → proof map (to be filled as decisions settle)
- S4.1 → inv 1, 2, 3, 15
- S4.2 → inv 4, 5, 6, 7
- S4.3 → inv 8, 9
- S4.4 → inv 10, 11, 12, 13, 14 (+ the constant from D-S4-F)

@@@@@@
**Audit R2-12 - add a public read-path binding invariant.** The battery proves many properties, but it
does not yet say that the committed fixture is loaded through the same structure-map reader/validator
future consumers will use. S1.4/S1.5 already learned this lesson with back-door-read negatives. Add an
S4.4 invariant that corrupts the on-disk fixture or bypasses the reader and proves the public load path,
not a private fixture builder, is what enforces schema plus semantic integrity.
@@@@@@

======
**Response (R2-12) — CONCEDE; precedent verified.** `test_atom_store.py` already has exactly this pattern —
`test_load_detects_persisted_text_drift`, `test_load_detects_canonical_text_corruption`,
`test_load_detects_stale_raw_source_hash`, `test_load_rejects_non_json_or_non_object_file` — corruption-on-disk
negatives proving the **public load path** enforces integrity, not a private builder. Resolution: add an S4.4
invariant in that mold — corrupt the committed fixture on disk (dangling ref, duplicate ownership, stale
cached handle, two active aliases in scope) and assert the **public `load_structure_map()`** raises; building
the map in memory and skipping the reader is the anti-pattern. §4's tests bind to the public reader, and the
deliverable matrix (§1.5) names that reader as the one entry point. (`invariants.md` I8/I9; `feedback_validate_bindings`.)
======

---

## 5. Build order (red-first, within this wave)

1. **D-S4-F constant first** (`STRUCTURE_MAP_STALE_CLASS`) — smallest surface, unblocks the manifest;
   red-first the distinctness pin (inv 12).
2. **S4.1 projection model** (`structure/projection.py`) — dataclasses + ownership/registry validation;
   inv 1–3, 15 red→green.
3. **S4.2 identity** — `node_id` + `minted_by` on the model; inv 4–7.
4. **S4.3 handles + aliases** — render-from-pair + alias record + resolve; inv 8–9.
5. **S4.4 schema + manifest** — `structure_map.schema.json` (location O2), evolve
   `_generate_structure_fixture.py` trivial→conforming, manifest assembly embedding
   `ResourceLineage.to_json()`; inv 10, 11, 13, 14.
6. **Checkpoint → PAUSE → pre-commit adversarial audit** (mutation hunt + wide/narrow reviewers) →
   dispositions → apply → commit → mint/close the S4.1–S4.4 issues. **Then** S4.5 (gate) as the next
   checkpoint (or folded in, per O5).

@@@@@@
**Audit 4 — the step-1 constant test is over-scoped.** Build order item 1 says add
`STRUCTURE_MAP_STALE_CLASS` first and red-first inv 12. But inv 12 also requires the manifest to declare
that stale class, and the manifest is not built until item 5. Split the invariant into two tests:
`STRUCTURE_MAP_STALE_CLASS` exists/exported/distinct in the constant step, then the S4.4 manifest
declares it later. As written, the first checkpoint either cannot go green or will force a premature
manifest stub.
@@@@@@

======
**Response (Audit 4) — CONCEDE.** inv 12 bundles "constant exists/distinct" (step 1) with "manifest declares
it" (step 5). Resolution: split inv 12 → **12a** (`STRUCTURE_MAP_STALE_CLASS` exists / exported / `==
"structure-map"` / distinct from the other classes — green at step 1, no manifest needed) and **12b** (the
assembled manifest declares it — green at step 5). Step 1 stops forcing a premature manifest stub. Renumbered
in the §4 revision; the done-when→proof map gets 12a→step 1, 12b→step 5.
======

@@@@@@
**Audit R2-13 - issue lifecycle is backwards or underspecified.** The header says no GitHub issue is
minted yet, while build step 6 says "mint/close" after the commit. If issues are audit artifacts, they
need to exist before implementation or at least before disposition, not only at closure. If they are
just tracker bookkeeping, say so and avoid making issue closure part of the engineering proof.
@@@@@@

======
**Response (R2-13) — CONCEDE the inconsistency.** Resolution: issues are **tracker bookkeeping, not
engineering proof**. Lifecycle: mint S4.1–S4.4 issues at the **start** of the build wave (once *this* plan is
ratified), each **closed at its own commit**. The header's "no issue minted yet" is true *now* because the
plan isn't ratified; once it is, minting precedes code. I'll reword build-step 6 to "close the S4.1–S4.4
issues (minted at wave-start)" and drop any implication that closure is part of the proof — the proof is the
green battery + the audit, the issue is just where it's tracked.
======

---

## 6. Open forks for this audit (the genuine branches — your ruling)

- **O1 — relation-store stale class now or at S7.1c?** D-S4-F adds `STRUCTURE_MAP_STALE_CLASS`. Do we
  *also* pre-place `RELATION_STORE_STALE_CLASS` (C-layer) now, since the atom-store docstring already
  forward-references it? **Recommend: no** (S7.1c owns it; don't claim C scope) — but it's a one-liner
  if you'd rather close both forward-refs at once.
- **O2 — schema-file location.** `config/schema/structure_map.schema.json` (one schema dir, existing
  loader) vs `structure/schema/structure_map.schema.json` (work-artifact under its own package).
  **Recommend: `structure/schema/`** (B is a work artifact, not a config profile). And: factor the
  derive-validate binding helper **now** or **at S7.1c**? **Recommend: inline now, factor at the second
  consumer.**
- **O3 — pin a concrete `node_id` scheme, or only its properties?** **Recommend: pin properties
  (inv 4–7), pick counter+ULID as the fixture default**, scheme revisitable.
- **O4 — `rebind_anchors` required or optional on a node?** **Recommend: optional** (absence
  first-class, mirrors S1.1; S4.5 differ-fixture is scan-free). Population is S5 regardless.
- **O5 — fold S4.5 into this push, or keep it the next checkpoint?** The "schema isn't born until the
  differ-fixture validates" language couples them. **Recommend: keep the wave split** (S4.1–S4.4 now
  against a conforming fixture; S4.5 next against the differ-fixture) — but if you want the keystone
  delivered as one ratified unit, we fold S4.5 in and close the schema with its real birth certificate.

---

## 7. Provenance

Drafted from code-verified reads this session: `structure/artifacts.py` (constants + paths),
`structure/lineage.py:187` (`to_json`), `config/schema/manifest.schema.json` (anti-pattern),
`tests/fixtures/_generate_structure_fixture.py` (binding precedent),
`tests/unit/test_structure_artifacts.py` (existing pins), `books/synthetic/` (mini-PLL),
PLAN §3.1–§3.6 + §11.2, tracker rows S4.1–S4.7. Memory: `feedback_red_first_tests`,
`feedback_mutation_pyc_staleness`, `feedback_plan_review_workflow`, `feedback_single_fixture_blind_spots`,
`feedback_engine_agnostic`, `feedback_validate_bindings`.

@@@@@@
**Audit R2-14 - "Memory" is not a sufficient source for the final plan.** The feedback labels are useful
shorthand for the current agent, but a future reviewer cannot inspect them unless the rule is restated
or linked to a durable doc. For each memory-derived constraint that is load-bearing
(`red_first_tests`, `single_fixture_blind_spots`, `validate_bindings`), inline the operative rule in
the final `s4_plan.md` or cite a checked-in source. Otherwise the plan depends on context that will not
travel with the artifact.
@@@@@@

======
**Response (R2-14) — CONCEDE; durable replacements verified to exist.** `docs/invariants.md` (the "audit
denominator," I1–I10, each with positive + negative + residual-risk) and `docs/port_discipline.md` are
checked in (HEAD `d611702`). Resolution: the distilled `s4_plan.md` cites **invariants.md** (I3 port-fidelity,
I4 core-separability/neutrality, I5 wire-protocol single-sourcing, I7 write-containment, I8 atomicity, I9
determinism) and **port_discipline.md** for load-bearing rules, **inlining the operative sentence** where the
rule is the crux (red-first, validate-bindings) rather than a bare slug. Memory slugs stay only as *my*
working pointers in this discussion draft, never as the final plan's authority. I'll add an "S4 invariants ↔
invariants.md" mapping at distillation so the plan travels self-contained.
======
