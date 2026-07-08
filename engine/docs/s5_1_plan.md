# S5.1 — `rebind_anchors` + the store-and-rebind mechanism (plan)

**Status: DRAFT for review (2026-07-08).** Not ratified; no code, no schema change, no schema-version
bump, no manifest change until this is signed off. Issue **#TBD** (mint on ratification; none exists
yet). Tracker row `S5.1` in `ENGINE_STRUCTURE_TASKS.md` (~L581) is the authoritative spec — on any
disagreement the tracker wins, then `ENGINE_STRUCTURE_PLAN.md` (§3.4, §3.6, D33, R2), then `s4_plan.md`
(§0.3 A-3/BR-022 coordinate contract, §1.4.1b re-stamp protocol), then this plan. Evidence anchor:
`spike/document-structure`; file:line cites verified on disk **2026-07-08** (this session).

Deps (all MET): **S2** (geometry backend + the #30 re-gate, DONE) and **S4.5** (structure map born,
schema v1, DONE). Scope `BUILD`. Its GATE sibling **S5.2** (threshold *calibration* on a labeled truth
set, the three-rate negative tier, monotone-strictness, and regen-guard registration) is **blocked on
S8.1** — so S5.1 builds the *mechanism* + a *default* threshold + the fail-loud path; **S5.2 calibrates
and gates it**. Keeping that line clean is a load-bearing scope boundary of this plan (§0).

Inputs this plan consolidates:

- **Tracker S5.1 row** — the three anchors (geometry region / fuzzy fail-loud content fingerprint /
  structural-path tie-break), the three operating modes, the explicit-confidence-threshold /
  fail-loud-on-doubt re-attach rule, and **ownership of the authoring-evidence re-stamp protocol**.
- **PLAN §3.4** — identity is an opaque durable `node_id` (D33 store-and-rebind); `rebind_anchors` are
  *checkpoints, not identity* (R2); geometry is the primary re-bind signal *where a scan exists*, the
  text-only floor is content + structural-path; ambiguous/below-threshold → **fail loud → §3.6
  governance**, never a silent mis-bind.
- **PLAN §3.6 / D33** — the structure map is a hand-tuned *irreproducible* artifact that **joins the
  regeneration-guard family**; a re-bind preserves `node_id`s and migrates the map forward (the
  sanctioned path), whereas delete-and-re-author mints *different* ids by design (the guarded path).
- **`s4_plan §0.3 A-3 / BR-022`** — `rebind_anchors.region` shares the atom-level `Geom` coordinate
  space; the concrete space + any witness/space discriminator is an S5-planning decision; **widening
  the `rebind_anchors` shape is a schema-version bump that re-enters `provisional` and re-runs the
  S4.5 birth gate — "cost known and accepted."**
- **`s4_plan §1.4.1b`** — the two-digest evidence-staleness model: **decision digest** (node_class +
  ordered child `node_id`s; re-bind-stable, **never machine-refreshed**) and **extent digest** (the
  slot-aware atom-id binding; **mechanically re-stampable at S5 where a re-bind is unique + above
  threshold** — the protocol this task owns).
- Memory: `feedback_existing_path_failures_as_evidence` (the `corrections.json` 40-char anchor the
  live tree tombstoned — the exact-substring failure R2 exists to prevent),
  `feedback_no_cheating_results` (S5.2 monotone-strictness the S5.1 mechanism must not preclude),
  `feedback_red_first_tests`, `feedback_adversarial_audit_cadence`, `feedback_mutation_pyc_staleness`,
  `project_ingestion_human_in_loop` (fail-loud routes to the human worklist, classifiers abstain).

---

## §0 What S5.1 is — and the S5.2 boundary

S5.1 delivers a **working re-bind mechanism**: given a stored structure map (durable `node_id`s +
`rebind_anchors`) and a **freshly regenerated canonical atom stream**, re-attach each stored node to
the fresh atoms it now owns — unique + above-threshold → bind and mechanically re-stamp its extent
evidence; ambiguous / below-threshold → **fail loud into the §3.6 worklist**, never a silent
mis-bind. Plus the schema surface the anchors need, and the re-stamp protocol.

The boundary with **S5.2** (its GATE sibling, blocked on S8.1) is deliberate and must not blur:

| Concern | S5.1 (this task, `BUILD`) | S5.2 (`GATE`, blocked on S8.1) |
|---|---|---|
| Confidence threshold | ships a **default** + the fail-loud-on-doubt mechanism | **calibrates** it on a labeled truth set |
| Negatives | the **fail-loud raise** at the re-binding tier (ambiguous / below-threshold / stale) | the **three-rate** measurement (false-bind / fail-loud / missed-bind) over a perturbation model |
| Monotone-strictness | the mechanism **must not preclude** it (weaker mode ⇒ threshold never lower) | **asserts** it as a property |
| Regen-guard | mechanism-only (re-bind is the *forward-migration* path, id-preserving) | **registers** `save_stream` + the map writer in the regen-guard family; the two-canonical persist form |

The trap to avoid (`feedback_no_cheating_results` / single-fixture blind-spot): S5.1 must not ship a
threshold *dressed as calibrated* or a happy-path re-bind test *dressed as a negative gate*. The
default threshold is explicitly a placeholder pending S5.2, and the negative tier here asserts the
**raise**, not a rate.

---

## §1 The deliverable — three anchors, three modes, one re-attach algorithm

**`rebind_anchors` per node (checkpoints, R2 — never identity, never a definition of the node):**

1. **geometry region** — `{page, bbox_region}`, already in the schema (populated here). The signal
   most invariant to OCR re-tokenization; **primary where the S2.1 matcher matched the node's atoms**.
2. **content fingerprint** — a **fuzzy, fail-loud** summary of the node's own content, matched against
   candidate fresh atoms. **Never the exact-substring primitive the live tree tombstoned** (R2; the
   `corrections.json` 40-char context that a re-extraction silently invalidated). Stored (see D-1) so
   the map is self-sufficient for re-bind without the old atom stream.
3. **structural-path tie-break** — the node's position in the tree (parent chain + child ordinal).
   **Derived from the map at re-bind time, not a stored field** (see D-1) — the map already holds it.

**Three operating modes** (`manifest.segmentation.geometry_mode`, #30-ruled **`geometry-tie-break`**
for PLL; loader-surfaced as `seg.geometry_mode`):

- `geometry-primary` — region leads candidate selection; fingerprint **verifies**; structural-path
  breaks residual ties.
- `geometry-tie-break` (**PLL**) — fingerprint **leads**; geometry **corroborates / cross-checks**
  (and is primary only where the matcher was confident on the two-column body); structural-path
  breaks ties.
- `no-geometry` — fingerprint + structural-path only; geometry discarded.

**The re-attach algorithm (explicit confidence threshold, fail-loud on doubt):** for each stored node,
gather fresh-atom candidates by the mode's lead signal, score by the combined fingerprint (+ geometry
corroboration per mode), then:

- **unique candidate, score ≥ τ** → **bind**: the node's `body_atoms` / `heading_atoms` / … rebind to
  the fresh atom ids; **mechanically re-stamp** its `extent_digest` (§1.4.1b — the binding is the same
  content under renamed atoms; the extent digest is over atom ids so it *must* change, and a
  unique+above-threshold re-bind is exactly the sanctioned re-stamp bar).
- **zero candidates / multiple candidates / score < τ** → **fail loud → human worklist** (§3.6). No
  re-stamp. The node is reported unresolved with its evidence, never silently bound.

**The re-stamp protocol (this task owns it — §1.4.1b):**

- **extent digest** — re-stamped **mechanically** exactly where the re-bind was unique + above
  threshold (same bar as the bind). Recomputed through THE producer (`extent_digest(node,
  projection)`) against the fresh projection.
- **decision digest** — **never machine-refreshed**. It is over `node_class` + ordered child
  `node_id`s, which are **re-bind-stable** (D33: a re-bind renames atoms, never node ids). If it
  changed, a human changed topology → that is a `stale-decision` finding for human re-verify, not a
  re-bind concern.
- **low-confidence re-binds** route their evidence entries to the worklist, **not** a silent re-stamp.

---

## §2 The schema surface (why a version bump is on the table)

The map schema (`structure_map.schema.json`) reserves `rebind_anchors` **region-only** today
(`additionalProperties:false`, "Population is S5.1"). Adding a `content_fingerprint` sub-object is a
**widening** of that shape — and `s4_plan §0.3 A-3 / BR-022` already ruled and **accepted** that
widening `rebind_anchors` is a **schema-version bump** (`STRUCTURE_MAP_SCHEMA_VERSION 1→2`, both the
schema `const` and the `artifacts.py` constant, bound by `schema_version_const()` / inv 10) that
**re-enters `provisional`** (`STRUCTURE_MAP_SCHEMA_STATUS[2] = provisional`) and **re-runs the S4.5
birth gate** (a *new* conforming differ-fixture that populates the v2 anchor shape flips `2 →
born`). This is the pre-blessed cost, not a surprise. §3 D-1 confirms the path and the smaller-surface
option (fingerprint stored, structural-path derived) that keeps the bump minimal.

---

## §3 The open decisions (for your inline audit)

Consequential and unresolved by the docs. My recommendation follows each; please rule inline
(`@@@@@@` / `======`). D-1 is the keystone; the rest are mechanism shape.

### D-1 — Anchor storage + the schema-version bump

What is *stored* in `rebind_anchors` vs *derived* at re-bind, and do we take the bump?

- **Options.** (a) **In-map bump:** store `content_fingerprint` in `rebind_anchors` (region already
  there), **derive** structural-path from the map (not stored) → bump `STRUCTURE_MAP_SCHEMA_VERSION
  1→2` + re-birth per `s4_plan` A-3. (b) **Separate rebind-fingerprint sidecar** keyed by `node_id`
  (its own schema + born-gate, the `authoring_evidence` precedent) → **no map-schema bump**, but the
  anchors split across two artifacts (region in the map, fingerprint in the sidecar). (c) Recompute
  the fingerprint from the *old* atom stream at re-bind time → **store nothing new**, but the map is
  no longer self-sufficient for re-bind (depends on the old stream still being present).
- **Recommendation: (a).** `s4_plan §0.3 A-3` **already accepted** the `rebind_anchors` widening as a
  schema bump — the design anticipated exactly this, so (a) is the pre-blessed path, not a fresh cost.
  Storing the fingerprint keeps the map self-sufficient (matches R2's "checkpoint" framing and D33's
  "the map is the durable artifact"); (c)'s dependency on the old stream is the fragility R2 warns of.
  (b) is worse than (a) only by splitting the anchor set across artifacts for no gain now that A-3 has
  pre-paid the bump. **Deriving** structural-path (not storing it) keeps the bump minimal — one new
  sub-object, not two. Confirm (a) + derive-structural-path, or redirect to (b)/(c).

### D-2 — Content-fingerprint shape + similarity (fuzzy, fail-loud, non-substring — R2)

The fingerprint must survive OCR re-tokenization / local edits (fuzzy), fail loud below a bar, and
**never** be an exact-substring match (the tombstoned failure).

- **Recommendation.** Store, per node, a **normalized-token k-gram shingle set** (via the existing
  `normalize_tokens` primitive from `geom_match`) **+ the token count**; at re-bind, score a candidate
  by **Jaccard similarity over shingle sets** → `[0,1]`, order-tolerant (robust to local reorder),
  with `ordered_coverage` available as an ordered cross-check where a strict order signal is wanted.
  Shingle size **k=3** (proposed) and the exact similarity formula are build details I will pin in
  code; the **threshold τ is a *default* here and calibrated at S5.2** (D-4). This is fuzzy,
  fail-loud, and R2-clean (a set-similarity, never a substring test). Flag if you want a different
  primitive (e.g. MinHash signature for compactness) — the shingle set is simplest and reuses an
  already-tested normalizer.

### D-3 — Region coordinate space (the BR-022 leftover)

`s4_plan` A-3 pinned region to "the atom-level `Geom` coordinate space" but left the *concrete* space
+ any witness/space discriminator as an S5-planning call.

- **Recommendation.** `region.page` = the **scan page number** the matcher already flows through
  (`geom_match` writes scan-page numbers, not indices); `region.bbox_region` = the union box in the
  **matcher's emitted `Geom.bbox` space** (the canonical atom's primary-witness box space, D30).
  **No separate discriminator field** is needed *for PLL* because there is one geometry space (the
  matched primary witness); if a future book carries geometry from >1 witness space, that discriminator
  is a *further* schema addition (a later bump), explicitly out of scope here. Confirm the single-space
  pin, or say you want the discriminator field reserved now (it would ride the same v2 bump).

### D-4 — Default threshold posture + per-mode weighting

S5.1 ships a **default** τ + the fail-loud mechanism; **S5.2 calibrates** (blocked on S8.1). The
posture of the default matters because it sets the pre-calibration behavior.

- **Recommendation.** Default τ **conservative / fail-loud-leaning** (bias toward routing to the
  worklist over auto-binding) — false-bind (silent-wrong) is the dominant cost (S5.2's own framing),
  so pre-calibration the mechanism should **abstain, not guess** (`project_ingestion_human_in_loop`).
  Per-mode combination: `geometry-primary` requires region-hit **and** fingerprint ≥ τ; `tie-break`
  requires fingerprint ≥ τ with geometry as a corroborating boost / tie-break; `no-geometry` requires
  fingerprint ≥ τ alone with structural-path as the sole tie-break. The mechanism keeps τ and the
  per-mode gating **monotone-adjustable** so S5.2 can prove weaker-mode-⇒-never-lower-τ without a
  redesign. Confirm the conservative default posture.

### D-5 — The two-canonical workspace state (transitional)

Re-bind needs the **old map + old canonical** and the **fresh canonical** side by side, but
`atom_store.load_workspace_streams` **hard-rejects a second canonical-kind stream** in one workspace
(`StaleArtifactError`, "one canonical anchor per workspace"). The tracker parks the *persist* form of
this as S5.2 agenda (b), but the re-bind mechanism forces the *in-memory* call now.

- **Recommendation.** S5.1 loads the two canonical streams via **direct `load_stream` calls** into an
  explicit in-memory `RebindContext(old_map, old_canonical, fresh_canonical)` — it does **not** persist
  a second canonical into the workspace, so it never trips (or weakens) the one-canonical invariant.
  The **sanctioned side-by-side *persist* form** (new-canonical-under-another-id vs a separate
  workspace) **and** the regen-guard on `save_stream` stay **S5.2**. This keeps the S5.1 mechanism pure
  and testable without touching a governance invariant. Confirm the in-memory-context boundary.

### D-6 — Output: in-memory re-bound map + report, or persisted migrated map?

- **Recommendation.** S5.1 produces, **in memory**: (i) the re-bound map (stored `node_id`s now owning
  fresh atom ids), (ii) a **binding report** (per node: bound / unresolved-reason, score, mode,
  candidate evidence), and (iii) the mechanical **extent-digest re-stamps** for confident binds.
  **Persisting** the migrated map under the regen-guard (the forward-migration write path) is **S5.2**
  (its regen-guard registration). This makes the re-binding tier fully testable (regenerated stream →
  re-bind → assert bindings / assert the raise) without a persist step that S5.2 owns. Confirm.

### D-7 — "The active mode recorded in lineage"

The done-when says the active mode is recorded in lineage so a re-bind is interpretable after the
fact. #30 landed the mode in `manifest.segmentation.geometry_mode`.

- **Recommendation.** S5.1 **reads** the mode from `seg.geometry_mode` and **stamps it into the
  re-bind result's provenance** (the binding report), not a new structure-map field. The manifest
  stays the mode's durable home until an S5 rebind-config layer exists (the tracker already records
  this). Confirm the manifest-as-home + report-as-provenance split, or say you want a mode field on
  the persisted re-bind artifact (that would ride D-6's S5.2 persist step).

---

## §4 Red-first invariants, mutation, audit (the method — §9 + D36)

Each invariant is enumerated in the module docstring and **seen red on violation** before the
mechanism is written (`feedback_red_first_tests`). Candidate invariants:

- **Happy re-bind (re-binding tier).** A regenerated canonical stream (fresh atom ids, **unchanged
  geometry + content**) re-binds every stored `node_id` to its fresh atoms; the extent digests are
  re-stamped and re-verify through the producer; the decision digests are **unchanged** (D33 stability
  — a mutant that refreshes the decision digest reds here). *Red input:* an id-permuted fresh stream.
- **Ambiguous → fail loud.** Two fresh candidates above τ for one node → **raise** into the §3.6 path,
  never bind one silently. *Red input:* a duplicated-content fresh page. A mutant that picks the first
  candidate (instead of raising on non-uniqueness) reds.
- **Below-threshold → fail loud.** A degraded candidate scoring < τ → raise, no re-stamp. *Red input:*
  a heavily perturbed fresh node. A mutant that binds the best-under-τ candidate reds.
- **R2 / non-substring.** The fingerprint match is a set-similarity, not a substring test: a fresh
  node whose content is a **superstring** of the stored content (extra atoms appended) does **not**
  auto-bind at full score, and a **locally-edited** node still binds (fuzzy). *Red input:* the
  substring/superstring pair. A mutant that falls back to exact-substring reds (the tombstone control).
- **Decision digest never machine-refreshed.** After a re-bind, a node whose *topology* actually
  changed surfaces `stale-decision` (human re-verify), not a silent refresh. *Red input:* a
  child-reordered node. A mutant that re-stamps the decision digest reds.
- **Mode gating.** In `no-geometry`, a region hit is ignored (fingerprint + structural-path decide);
  in `geometry-primary`, a fingerprint hit with no region hit does not auto-bind. *Red input:* a
  region-only / fingerprint-only candidate per mode. A mutant that ignores `seg.geometry_mode` reds.
- **Schema born (if D-1(a)).** The v2 schema is `provisional` until the new differ-fixture births it;
  `assert_schema_born()` raises `SCHEMA_NOT_BORN` on v2 until the birth gate passes (inv 23 re-run).

**Mutation hunt** at green (`PYTHONDONTWRITEBYTECODE=1`, purge `__pycache__` per
`feedback_mutation_pyc_staleness`) over a `hunt_rebind.py` table; **wide+narrow adversarial audit**
pre-commit; **Rule-A** re-audit of any behavior-changing remediation to a fixpoint (D36). Engine core
stays neutral — the S0.2 neutrality scan globs `structure/`; the re-bind carries no book/language
literal (it rules on stored anchors + a mode string passed in).

## §5 What lands where

- `src/engine/structure/rebind.py` **(new)** — the mechanism: `RebindContext`, the per-mode candidate
  selection, the fingerprint scorer, the fail-loud re-attach, the binding report, the extent-digest
  re-stamp. Engine-neutral.
- `src/engine/structure/schema/structure_map.schema.json` — `rebind_anchors.content_fingerprint`
  sub-object **(D-1(a): + `schema_version` const 1→2)**.
- `src/engine/structure/artifacts.py` — `STRUCTURE_MAP_SCHEMA_VERSION 1→2` +
  `STRUCTURE_MAP_SCHEMA_STATUS = {1: born, 2: provisional}` then `{…, 2: born}` after the birth gate
  **(D-1(a))**.
- `tests/fixtures/structure/` — a **new v2 differ-fixture** that populates the fingerprint anchor +
  the birth-gate test flip **(D-1(a), S4.5-style)**.
- `tests/unit/test_rebind.py` **(new)** — the red-first invariants (§4).
- `tests/hunts/hunt_rebind.py` **(new)** — the mutation table.
- `docs/ENGINE_STRUCTURE_TASKS.md` — `S5.1 → DONE` row + the S5.2 note (the two-canonical persist form
  + regen-guard registration is confirmed S5.2); memory update.
- Issue #TBD close: evidence comment + tracker row in the same commit.

## §6 Definition of Done

1. The re-bind mechanism re-binds a regenerated stream's stored `node_id`s under unchanged geometry
   (happy tier), and **fails loud** into the §3.6 path on ambiguous / below-threshold / stale-decision
   (negative tier) — each red-proven, each with a named red input (§4).
2. The re-stamp protocol holds: extent digests **mechanically** re-stamped only on unique+above-τ
   binds and re-verify through the producer; decision digests **never** machine-refreshed.
3. The three modes are honored, read from `seg.geometry_mode` (PLL = `geometry-tie-break`); the active
   mode is recorded in the re-bind result's provenance (D-7).
4. The schema surface lands per D-1: if (a), the v2 bump + a new differ-fixture **flips v2 `born`** and
   `assert_schema_born()` gates it; the version binding (inv 10) + born gate (inv 23) both hold.
5. A **default** threshold + the fail-loud mechanism only — **no calibration** (that is S5.2); the
   mechanism keeps monotone-strictness reachable.
6. Suite green, ruff clean, mutation hunt kills all, wide+narrow adversarial audit + Rule-A fixpoint
   clean. Pushed to `origin/spike/document-structure` only (deploy-hold on main/Pages untouched).
7. Issue #TBD closed with evidence; tracker `S5.1 → DONE`; run/plan docs + memory updated.

---

**Decisions needed before I code: D-1 … D-7** (§3). D-1 is the keystone (it sets whether we take the
pre-accepted schema bump); the rest are mechanism shape. Everything else I execute as written and
report.
