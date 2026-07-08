# S5.1 — `rebind_anchors` + the store-and-rebind mechanism (plan — rev 2)

**Status: RATIFIED rev 2 — Ben, 2026-07-08.** The rev-2 content Ben read and signed off is commit
`b79f566` on `spike/document-structure`. Provenance of the decisions is deliberately split (see §3):
**seven decisions are Ben's explicit rulings (2026-07-08)** — D-1, D-3b, candidate grammar, no-rescue,
per-slot fingerprint, provenance, and fingerprint-required; **the remaining ledger rows were resolved
during the three-round inline review** (Ben's audit points + my accepted responses), which Ben drove
but did not each rule as standalone decisions. Ratification clears code, the schema-version bump, and
the manifest change to proceed. Tracked as **issue #47** (milestone S5).

This rev consolidates the three-round inline review into a resolved spec. The **verbatim review trail**
(round 1 `@@@@@@`/`======`, round 2 `@@@@@!`/`====!!`, round 3 `@@@@!!`/`===!!!`, plus the D-1…D-7 +
D-3b walk-through) is retained in [`s5_1_plan-discussion.md`](s5_1_plan-discussion.md).

**Spec authority (on any disagreement):** tracker row `S5.1` in `ENGINE_STRUCTURE_TASKS.md` (the
`| S5.1 |` row of the task table) → `ENGINE_STRUCTURE_PLAN.md` (§3.4, §3.6, D33, R2) → `s4_plan.md`
(§0.3 A-3/BR-022 coordinate contract; §1.4.1b re-stamp protocol) → this plan. Evidence anchor:
`spike/document-structure`, ratified rev-2 baseline `b79f566`; file:line cites verified on disk
**2026-07-08**.

**Ratification record** (2026-07-08): the spec-authority pointer above now keys on the `| S5.1 |`
table row (line-number-independent), the ratified rev-2 baseline `b79f566`, and issue **#47**
(milestone S5) — so it does not drift with branch edits. Tracker row `S5.1` moves `TODO → WIP` in the
housekeeping commit that carries this status flip.

Deps (all MET *for the mechanism*): **S2** (geometry backend + #30 re-gate, DONE), **S4.5** (structure
map born, schema v1, DONE). **Live-PLL migration additionally needs S4.6** (the hand-authored PLL
container map, TODO) — so S5.1 is built and tested against **synthetic / differ fixtures only**, never
a live PLL run. Scope `BUILD`. GATE sibling **S5.2** (calibration + three-rate negatives + regen-guard
registration) is blocked on **S8.1**.

---

## §0 What S5.1 is — and the S5.2 boundary

S5.1 delivers a **working re-bind mechanism**: given a stored structure map (durable `node_id`s +
`rebind_anchors`) and a **freshly regenerated canonical atom stream**, re-attach each stored node to
the fresh atoms it now owns — unique + above-threshold → bind and mechanically re-stamp its extent
evidence; ambiguous / below-threshold / no-legal-signal → **fail loud into a typed report** (the
pre-S8.1 worklist seam), never a silent mis-bind. Plus the v2 schema surface the anchors need, and the
re-stamp protocol.

The boundary with **S5.2** is load-bearing and must not blur:

| Concern | S5.1 (this task, `BUILD`) | S5.2 (`GATE`, blocked on S8.1) |
|---|---|---|
| Confidence threshold | ships a **default** (named, high, uncalibrated) + the fail-loud mechanism | **calibrates** it on a labeled truth set |
| Negatives | the **fail-loud raise / finding** at the re-binding tier | the **three-rate** measurement (false-bind / fail-loud / missed-bind) over a perturbation model |
| Monotone-strictness | mechanism **must not preclude** it; a structural default-ordering check only | **asserts** the data property |
| Staleness | **rebind-local `stale-decision`** (via the evidence producer, run against the rebound projection) | — |
| Lineage-manifest staleness | **not S5.1** | — (S8.1 owns lineage stale classes + migration routing) |
| Regen-guard / persist | **mechanism-only** (re-bind is id-preserving forward migration; result is in-memory) | **registers** `save_stream` + the map writer; the two-canonical *persist* form |

**Non-calibration acceptance rule for the default threshold** (anti-cheat, `feedback_no_cheating_results`):
the default τ is acceptable pre-calibration **iff** it (i) passes only exact / id-permuted / near-exact
fixture positives and (ii) makes every adversarial negative raise. No claim about real-data rates —
that is S5.2. **No evidence writer in S5.1:** re-stamped entries are computed **in memory** inside the
result; `authoring_evidence.json` is not written here (that persist + its regen-guard is S5.2).

---

## §1 The deliverable — anchors, modes, the assignment, the re-stamp

### 1.1 `rebind_anchors` per node (checkpoints, R2 — never identity)

1. **region seed** — a single `{page, bbox_region}` object (D-3b): the `bbox` of the node's **first
   own-atom in canonical order whose `geom.present` is True** (absent / routed / pending skipped); if
   **no own-atom has present geometry, the region is absent** and the node rides the assignment
   unpinned. The `Geom` model carries **no outlier predicate**, so S5.1 does **not** invent one (that
   would be a non-deterministic rule); outlier-box exclusion is **deferred to S5.2** calibration if it
   ever proves necessary. `page` is the 1-based scan number (`page >= 1`); `bbox_region` is in the
   matcher's emitted `Geom.bbox` space (D30 primary-witness box space). A locate *seed*, not a
   whole-extent map — a multi-page own-extent is recovered by the assignment (§1.3), not stored per page.
2. **content fingerprint** — **per slot, over own atoms only** (per-slot ruling): a **leaf** fingerprints
   its `body_atoms`; a **container** fingerprints its `heading_atoms` and `signature_atoms` as
   **separate** fingerprints; **never descendant text** (descendants carry their own). Fuzzy,
   fail-loud, **never exact-substring** (R2 — the `corrections.json` 40-char anchor the live tree
   tombstoned). Stored (D-1), so the map is self-sufficient *for the content signal*. Shape in §2.2.
3. **structural-path** — **derived** from the map at re-bind time (parent chain + child ordinal),
   **not stored**. Used only as a tie-break.

**Match-provenance** (`matched_witness_id` / `geometry_engine` / `match_method`) is **not stored** in
the anchor — it is surfaced in the report (D-7/provenance ruling), and is re-derivable from the old
atom's `Geom` whenever the old canonical is present (which the baseline check guarantees, §1.4).

### 1.2 Three operating modes (`manifest.segmentation.geometry_mode`)

Exact enum tokens (bound to the schema enum by test, per D-4): `geometry-primary` | `geometry-tie-break`
| `no-geometry`. #30 ruled **`geometry-tie-break`** for PLL (loader-surfaced as `seg.geometry_mode`;
absent → `conditional-primary` fallback, reported as weaker provenance — never silently invented).

- `geometry-primary` — region pins lead; fingerprint **verifies** (region-hit **AND** fingerprint ≥ τ).
- `geometry-tie-break` (**PLL**) — fingerprint **leads**; geometry **corroborates** (a pin) and breaks
  ties; structural-path breaks residual ties.
- `no-geometry` — fingerprint + structural-path only; geometry discarded (no pins).

**No rescue (ruled):** geometry and structural-path may only **disambiguate among candidates already
≥ τ** — they **never** lift a sub-τ fingerprint over τ. A conjunction in `geometry-primary`, a tie-break
elsewhere; never additive to the score.

### 1.3 The re-attach algorithm — one joint monotone assignment (candidate-grammar ruling)

A **single global monotone alignment/DP** of the old node reading-order against the fresh canonical
atom indices — non-crossing, contiguous spans, **one pass**. Reuses the DT-3 banded monotone-locate
pattern already in `geom_match` (`_bands` / `locate_pages` / `_BandMax`).

- **Pins:** where a node has a region seed, its assignment is constrained to that page/region — a
  **hard pin**. `no-geometry` (and any region-less node) runs the same DP with **no pin**; sibling
  bounds are the DP's **output**, never a per-node precondition.
- **Cost:** the per-slot fingerprint score of the candidate span (§2.2 similarity). Geometry is a pin,
  not a cost term (no-rescue).
- **Global consistency:** the DP yields a non-overlapping ownership assignment; the full rebound
  `ProjectionMap` is then run through `validate_projection` + `assert_reference_integrity`. **No bind
  is "successful" until the whole map validates** — a parent bound with a failed child, an out-of-parent
  child span, or double-owned atoms is a `global-conflict` finding, not a silent bind.
- **Per-node outcome:** unique + score ≥ τ + globally consistent → **bind**; else a typed finding
  (§1.5). **Fingerprint required for auto-bind** (**[Ben-ruled]** 2026-07-08): a node lacking the
  fingerprint its mode needs → `missing-anchor`, never bound on geometry/path alone (optional-at-schema
  ≠ permissive-at-rebind).
- **Complexity:** naive full-shingle storage + all-windows matching is quadratic; the banded monotone
  DP (DT-3 pattern) with a page/path-bounded candidate index holds it to one near-linear pass. This is
  the op **S4.7 names under its scale gate** ("re-bind lookup … sub-quadratic across 10⁴→10⁵ leaf
  nodes", tracker S4.7/#33), so the DP's boundedness is a scale-check obligation, not just a nicety.

### 1.4 `RebindContext` — the two-substrate frame (D-5)

`RebindContext(old_map, old_streams, fresh_streams)`, where each `*_streams` is a `{canonical +
witnesses}` set (the `load_workspace_streams` return shape). Loaded via direct `load_stream` calls
(the two-canonical *persist* form + regen-guard are S5.2). Construction fails loud on:

- **reference integrity** — `assert_reference_integrity(canonical, witnesses)` on *both* sets (the
  escape hatch skips the workspace-level cross-stream check, so we run it explicitly);
- **baseline binding** — `old_canonical`'s id **and both** `canonical_content_hash` **and**
  `canonical_geometry_hash` must match what `old_map.manifest` claims (geometry half gated on geometry
  being used; skipped in `no-geometry`). Computed via the **shared** `canonical_content_hash` /
  `canonical_geometry_hash` producers **extracted from `build_manifest`** — never a lookalike hash in
  `rebind.py` (so a payload/digest change ripples to both; inv 20 already guards `_hash_canonical`).

A re-bind attempted **without** the old canonical fails loud ("cannot verify baseline / re-derive
geometry provenance") — the pre-registered flag for the map-only-re-bind future (§3, provenance).

### 1.5 Output — `RebindResult` / `RebindReport` / `RebindError` (D-6)

- **`RebindResult`** carries: (i) the migrated **structure-map document** (fresh atom ids in the node
  slots, unpersisted — document-shaped so S5.2's writer has something to write); (ii) the typed
  **`RebindReport`**; (iii) the in-memory **re-stamped authoring-evidence entries** — *separate from
  the map* (digests live in the evidence sidecar, never grafted onto the map schema).
- **`RebindReport`** — a dataclass; per node: bound / unresolved-reason, score, mode, candidate
  evidence, the two stream ids+hashes compared, and the geometry match-provenance surfaced. Mode
  provenance = `{mode, source: manifest|fallback, manifest_schema_version}`.
- **Closed unresolved-reason enum:** `zero-candidate | ambiguous | below-threshold | missing-anchor |
  stale-decision | global-conflict` (mirrors evidence.py's closed kind set so a typo can't mint a
  pseudo-reason). `missing-anchor` = "no legal signal to search with"; `zero-candidate` = "searched the
  legal space, found nothing"; `below-threshold` = "found a candidate, score < τ."
- **Both surfaces (evidence.py precedent):** a **non-raising `rebind(...) -> RebindResult`** (all
  tentative binds + all findings, worklist-friendly) and a **strict `assert_all_bound(result)`** that
  raises **`RebindError`** if any node is unresolved. Partial success is represented, never hidden.

### 1.6 The re-stamp protocol (this task owns it — §1.4.1b)

After the assignment is fixed and the map validates:

- **extent digest** — re-stamped **mechanically**, **bottom-up in topological order**, only for nodes
  bound unique + above τ (the atoms are new ids but the same content). Recomputed through the producer
  `extent_digest(node, projection)` against the fresh projection. Bottom-up because the extent payload's
  `beneath` union depends on descendants — no node is re-stamped while a descendant is unresolved.
- **decision digest** — **never machine-refreshed** (over `node_class` + ordered child `node_id`s,
  re-bind-stable by D33). S5.1 runs `evidence_findings` / `assert_evidence_gate` **against the rebound
  projection**; any `stale-decision` is an **unresolved finding** (human re-verify), not a re-stamp.
- **low-confidence** re-binds route their evidence to the report, never a silent re-stamp.

---

## §2 The schema surface — the v2 bump (D-1(a))

### 2.1 The bump

`STRUCTURE_MAP_SCHEMA_VERSION 1→2` (both the schema `const` and the `artifacts.py` constant, bound by
`schema_version_const()` / inv 10). `STRUCTURE_MAP_SCHEMA_STATUS = {1: born, 2: provisional}` →
`{1: born, 2: born}` after the birth gate (v1's entry preserved explicitly, not replaced).
`assert_schema_born()` refuses v2 until birth. **Birth gate (S4.5-style):** a **new conforming
differ-fixture** (non-PLL-shaped) that *populates* the v2 anchor shape validates through the
born-agnostic loader → flips v2 `born`.

**Fixture migration:** `content_fingerprint` is **optional**, so every existing conforming fixture stays
valid after a **mechanical `schema_version: 1→2` field bump** (zero content change). Two disjoint fixture
classes, never conflated: **(1) schema/load fixtures** (bumped, fingerprints *omitted* — exercise schema
validity + born + inv 13/24 incl. malformed-fingerprint rejection; **not** valid rebind inputs) and
**(2) rebind-positive fixtures** (per-slot fingerprints **and** region seeds populated — a rebind
positive is *defined* as carrying the full anchor set its mode requires). v1-reader coverage is S8.1's
concern, not faked here.

### 2.2 The `rebind_anchors` v2 shape

- `region`: unchanged object shape `{page, bbox_region}`, `page` tightened to `minimum: 1` (was `0` —
  the atom `Geom.page` is a positive scan number; a Tier-2 check backs it).
- `content_fingerprint`: **slot-keyed** — `{body: <fp>}` for a leaf, `{heading: <fp>, signature: <fp>}`
  for a container (slots optional/present per the node's own atoms). Each `<fp>` =
  `{algo_id, normalizer_id, k, token_count, shingles: [<sorted, size-bounded>]}`:
  - `normalizer_id` = `geom_match.normalize_tokens@v1` (reused; accent/apostrophe **tolerance is an S5.2
    calibration question**, made *detectable* — a normalizer change flips the id, never a silent swap);
  - `k` = shingle size (default 3, build detail), with a **short-slot fallback** `k' = min(k,
    token_count)` down to unigrams; a slot too short to fingerprint reliably binds only with
    **geometry/path** corroboration or fails loud (never on an empty set);
  - `shingles` sorted + `maxItems`/serialized-size bounded (byte-stable, diff-able);
  - `token_count` retained for the multiplicity check (§ scorer).
- `additionalProperties:false` throughout still **rejects** `.geom` / atom-level `present` smuggling
  (node-level anchors are never the atom-level Geom).

**Similarity (scorer):** Jaccard over the slot's shingle set as the primary `[0,1]` score, with
**`token_count` ratio** and **containment / multiset overlap** as secondary evidence in the report;
**`ordered_coverage`** promoted from "available" to **part of the default report** (order-sensitivity
signal). Common / duplicated content **raises (`ambiguous`)** rather than binding. Exact formula is a
build detail; the **threshold τ is a default here, calibrated at S5.2**.

---

## §3 Decisions ledger

**Provenance key:** rows tagged **[Ben-ruled]** are Ben's explicit rulings (2026-07-08). `[review]`
rows were **resolved in the three-round review** — Ben raised the audit point, I proposed the
resolution and he did not object — and stand **pending his final read**, not as standalone Ben rulings.

| # | Decision | Ruling | Provenance |
|---|---|---|---|
| **D-1** | anchor storage + schema bump (keystone) | **(a) in-map bump** — store fingerprint, derive structural-path, typed anchors, take v1→v2 + re-birth | **[Ben-ruled]** |
| **D-2** | fingerprint shape + similarity | shingle-set Jaccard + `normalizer_id` / short-slot `k'` fallback / `token_count` + multiplicity / `ordered_coverage` in report / sorted-bounded shingles | [review] |
| **D-3** | region coordinate space | scan `page` (`>=1`) + matcher `Geom.bbox` space; single space (no discriminator for PLL); provenance in report | [review] |
| **D-3b** | region shape | **single `{page, bbox_region}` seed** (first present own-atom box), not a per-page list; no outlier predicate invented — outlier exclusion deferred to S5.2 | **[Ben-ruled]** |
| **candidate grammar** | assignment | **one joint monotone DP**, geometry as pins, fingerprint as cost, `no-geometry` = no pins | **[Ben-ruled]** |
| **no-rescue** | signal combination | geometry/path only break ties among **≥ τ** candidates; never lift sub-τ over τ | **[Ben-ruled]** |
| **per-slot fp** | fingerprint granularity | leaf=body; container=heading + signature separately; **never descendant text** | **[Ben-ruled]** |
| **provenance** | where match-provenance lives | **report** (anchor minimal); **map-only re-bind fails loud**; revisit-trigger = *map-only re-bind ∨ multi-witness geometry* | **[Ben-ruled]** |
| **D-4** | default threshold posture | named high uncalibrated `DEFAULT_FINGERPRINT_THRESHOLD`; exact enum tokens; per-mode τ in a `RebindPolicy` object with the structural default-ordering check `τ(no-geometry) ≥ τ(tie-break) ≥ τ(primary)`; non-calibration acceptance rule (§0) | [review] |
| **D-5** | two-canonical state | in-memory `RebindContext(old_map, old_streams, fresh_streams)`; ref-integrity + dual-hash baseline at construction; shared hash producers; persist form = S5.2 | [review] |
| **D-6** | output shape | `RebindResult` (migrated doc + report + separate re-stamped evidence); typed `RebindReport` + closed reason enum; non-raising `rebind()` + strict `assert_all_bound()` | [review] |
| **D-7** | mode recorded in lineage | mode + source in `RebindReport` provenance now; **S5.2 is the named persist owner** | [review] |
| **fingerprint-required** | eligibility | required for auto-bind in all modes; absent → `missing-anchor` → worklist | **[Ben-ruled]** |

---

## §4 Red-first invariants, mutation, audit (§9 + D36)

Each invariant is enumerated in the module docstring and **seen red on violation** before code
(`feedback_red_first_tests`); each cites the mutant that reds it. The set:

- **Happy re-bind** — an id-permuted fresh stream (unchanged geometry + content) re-binds every stored
  `node_id`; extent digests re-stamped + re-verify through the producer; decision digests unchanged;
  the rebound projection validates globally. *Mutant:* refresh the decision digest → red.
- **Global consistency** — two high-scoring nodes claiming the same fresh atom → deterministic
  whole-map assignment or fail loud. *Mutant:* greedy per-node best-match → red.
- **Ambiguous → fail loud** — two candidates ≥ τ for one node → `ambiguous`, never bind one. *Mutant:*
  pick first candidate → red.
- **Below-threshold → fail loud** — a sub-τ candidate → `below-threshold`, no re-stamp. *Mutant:* bind
  best-under-τ → red.
- **Missing-anchor / no permissive rebind** — a node with no fingerprint for its mode → `missing-anchor`,
  never bound on geometry/path alone; a v2 map with omitted fingerprints binds nothing in
  `geometry-tie-break`/`no-geometry`. *Mutant:* bind a fingerprint-less node on geometry alone → red.
- **No rescue** — geometry never lifts a sub-τ fingerprint over τ. *Mutant:* geometry-boost-rescues → red.
- **R2 / non-substring** — a superstring fresh node does not auto-bind at full score; a locally-edited
  node still binds (fuzzy). *Mutant:* exact-substring fallback → red (the tombstone control).
- **Short-slot** — a 1–2 token heading (no k=3 shingles) binds only with geometry/path corroboration
  or fails loud. *Mutant:* empty-shingle-set → false pass → red.
- **Page/coordinate** — `region.page` rejects 0 / any value not comparable to `Geom.page`. *Mutant:*
  keep `minimum:0` → red.
- **Typed-model round-trip** — a loaded v2 map exposes `content_fingerprint` to `rebind.py` and
  re-renders byte-stably. *Mutant:* drop the field on load (today's inv-25 behavior) → red.
- **Baseline binding** — `RebindContext` refuses an `old_canonical` whose id / content-hash /
  geometry-hash ≠ the old map manifest. *Mutant:* accept any caller stream → red.
- **Re-stamp ordering** — bottom-up; *mutant:* re-stamp an ancestor before a descendant resolves → red.
- **Decision digest** — `stale-decision` detected via the evidence producer against the rebound
  projection; *mutant:* machine-refresh the decision digest → red.
- **Mode gating** — `no-geometry` ignores a region hit; `geometry-primary` won't bind fingerprint-only.
  *Mutant:* ignore `seg.geometry_mode` → red.
- **Schema born** — v2 is `provisional` until the new differ-fixture births it; `assert_schema_born()`
  raises `SCHEMA_NOT_BORN` on v2 until then (inv 23 re-run).
- **Default monotone-ordering** — the per-mode τ live in one `RebindPolicy` object (with
  `DEFAULT_FINGERPRINT_THRESHOLD` as the base), and `τ(no-geometry) ≥ τ(tie-break) ≥ τ(primary)` holds
  on the defaults. *Mutant:* a default ordering that inverts → red.

**Mutation hunt** at green (`PYTHONDONTWRITEBYTECODE=1`, purge `__pycache__`) over `hunt_rebind.py`;
**wide+narrow adversarial audit** pre-commit; **Rule-A** re-audit of behavior-changing remediation to a
fixpoint. Core stays mode-agnostic (S0.2 neutrality scan globs `structure/`); the PLL
`geometry-tie-break` assertion lives in a **fixture/probe**, not core. **All three modes** exercised on
synthetic fixtures.

## §5 What lands where

- `src/engine/structure/rebind.py` **(new)** — `RebindContext`, `RebindPolicy` (per-mode τ + the
  `DEFAULT_FINGERPRINT_THRESHOLD` base), the monotone-DP assignment, the per-slot fingerprint scorer,
  eligibility / no-rescue gating, the bottom-up re-stamp, `RebindResult` / `RebindReport` /
  `RebindError`, non-raising `rebind()` + `assert_all_bound()`. Engine-neutral.
- `src/engine/structure/projection.py` — `ContainerNode` / `LeafNode` gain typed `rebind_anchors`.
  **Only `rebind_anchors` is promoted to typed;** the node-level `decision` field stays **raw/inert**
  (S8.2, not read by S5.1) — which is why the inv-25 carve-out is anchors-only, not a general "model
  every reserved field" change.
- `src/engine/structure/structure_map.py` — `_node_from_json` parses anchors; `render_structure_map`
  emits them; **extract shared `canonical_content_hash` / `canonical_geometry_hash` producers** (called
  by `build_manifest` **and** the baseline check).
- `src/engine/structure/schema/structure_map.schema.json` — v2: `region.page minimum:1`,
  `content_fingerprint` slot-keyed sub-object (bounded), `schema_version const 1→2`.
- `src/engine/structure/artifacts.py` — `STRUCTURE_MAP_SCHEMA_VERSION 1→2`; `STRUCTURE_MAP_SCHEMA_STATUS`
  `{1: born, 2: provisional}` → `{1: born, 2: born}`.
- `src/engine/structure/__init__.py` — export pins for the new public rebind types.
- `tests/fixtures/structure/` — mechanical `1→2` bump of conforming fixtures; a **new v2 differ-fixture**
  (populates the fingerprint, births v2); rebind-positive fixtures (full anchor set).
- `tests/unit/test_rebind.py` **(new)** — §4 invariants. Threshold tests **reference
  `DEFAULT_FINGERPRINT_THRESHOLD` by name, never an inline numeric literal**, so a default change
  cannot silently pass a stale hardcoded number. `tests/hunts/hunt_rebind.py` **(new)** — the
  mutant table. `tests/unit/test_structure_map.py` — inv 13/24 updated for the v2 anchor shape +
  malformed-fingerprint rejection + retained `.geom`/`present` smuggling rejection + inv-25 carve-out.
- `docs/ENGINE_STRUCTURE_TASKS.md` — `S5.1 → DONE` row + the S5.2 note (two-canonical persist form +
  regen-guard registration confirmed S5.2); memory update. Issue #TBD close: evidence comment + tracker
  row in the same commit.

## §6 Definition of Done

### §6a Mechanism (the "work is correct" bar — a pre-code audit judges this)

1. Re-binds a regenerated stream's stored `node_id`s under unchanged geometry (happy tier) **and the
   rebound projection validates globally** (`validate_projection` + reference integrity) **and
   `old_canonical` matches the old map's lineage** (dual-hash baseline); **fails loud** on
   zero-candidate / ambiguous / below-threshold / missing-anchor / stale-decision / global-conflict —
   each red-proven with a named red input (§4).
2. Re-stamp protocol holds: extent digests **mechanically** re-stamped bottom-up only on unique+above-τ
   binds and re-verify through the producer; decision digests **never** machine-refreshed.
3. Three modes honored, read from `seg.geometry_mode` (PLL = `geometry-tie-break`); active **mode +
   source** recorded in `RebindReport` provenance (S5.2 is the named persist path).
4. v2 schema lands: bump + a new differ-fixture **flips v2 `born`**; `assert_schema_born()` gates it;
   version binding (inv 10) + born gate (inv 23) both hold; conforming fixtures migrated `1→2`
   (mechanical), v1-reader coverage left to S8.1.
5. A **default** threshold + fail-loud only — **no calibration** (S5.2); the default-ordering check
   holds and the mechanism keeps monotone-strictness reachable.

### §6b Landing (the "it ships" bar — applies once coding is authorized)

6. Suite green, ruff clean, mutation hunt kills all, wide+narrow audit + Rule-A fixpoint clean.
7. Pushed to `origin/spike/document-structure` only (deploy-hold on main/Pages untouched); issue #TBD
   closed with evidence; tracker `S5.1 → DONE`; discussion trail + run docs + memory updated.

---

**On your final read + sign-off:** I mint the S5.1 issue and begin red-first (§4). Until then: no code,
no schema bump, no issue.
