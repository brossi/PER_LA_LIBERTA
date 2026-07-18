# S5.1 — `rebind_anchors` + the store-and-rebind mechanism (plan — DISCUSSION TRAIL)

> **This is the retained review trail, not the live spec.** It preserves verbatim the three inline
> annotation rounds — round 1 (`@@@@@@`/`======`, 15 threads), round 2 (`@@@@@!`/`====!!`, 4 threads),
> round 3 (`@@@@!!`/`===!!!`, 3 threads) — plus the D-1…D-7 + D-3b walk-through Ben ruled on
> 2026-07-08. **The ratified/live spec is [`s5_1_plan.md`](s5_1_plan.md) (rev 2).** Edit that, not this.

**Status: DRAFT for review (2026-07-08) — superseded by `s5_1_plan.md` rev 2.** Not ratified; no code,
no schema change, no schema-version bump, no manifest change until this is signed off. Issue **#TBD**
(mint on ratification; none exists yet). Tracker row `S5.1` in `ENGINE_STRUCTURE_TASKS.md` (~L581) is the authoritative spec — on any
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

@@@@@@
Adversarial audit:

- The dependency statement is accurate against the tracker, but operationally incomplete for any live
  PLL run: S4.6 (hand-authored PLL map) is still TODO, so S5.1 can build and test the mechanism but
  cannot demonstrate a real PLL map migration unless the work uses synthetic/fixture maps. Call that
  out explicitly so "Deps all MET" is not misread as "live PLL substrate ready."
- "Fail loud into the §3.6 worklist" is directionally right but there is no S8.1 stale-router yet, and
  no generic rebind worklist artifact exists. S5.1 should own a typed rebind finding/report surface
  now, and phrase §3.6 integration as future consumption, not as an already-existing route.
- The evidence anchor says file:line cites verified on disk, but the plan itself has approximate
  line references (`~L581`) and mutable branch names. Fine for a draft, weak as implementation
  evidence. If this becomes the ratified plan, pin issue id + exact tracker row identity or commit
  hash rather than relying on moving branch prose.
@@@@@@

======
Response (code-verified 2026-07-08):

- ✓ **S4.6 gap — accept, material.** S4.6 (the hand-authored PLL container map) is TODO, so there is
  no real PLL structure map to migrate yet. S5.1 is testable only against **synthetic / differ
  fixtures** (the born-gate fixture family), never a live PLL run. I'll rewrite "Deps all MET" to
  "Deps MET *for the mechanism*; live-PLL migration awaits S4.6" and state the test substrate is
  synthetic-only. This also means the "re-binds every stored node_id" DoD is proven on fixtures, not
  on PLL — an honest scope line, not a hidden one.
- ✓ **No §3.6 route exists yet — accept, and it converges with your cross-cutting point.** There is
  no stale-router (S8.1) and no worklist artifact. S5.1 will **own a typed `RebindReport` +
  non-raising `rebind_findings` + a dedicated `RebindError`** (cross-cutting point 1) as the *stable
  seam*; "§3.6 governance" becomes **future consumption of that seam**, not an existing route I write
  into. Re-worded throughout (§0, §1, D-6).
- ✓ **Evidence-anchor precision — accept for the ratified rev.** On sign-off I'll pin the commit hash
  (`3d94d40` for this draft baseline) + the minted issue id and replace `~L581` with the exact
  tracker-row identity. Draft-stage approximate refs stay only until then.
======

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

@@@@@@
Adversarial audit:

- The boundary is mostly clean, but "stale" is overloaded. S5.1 can detect rebind-local stale states
  such as `stale-decision` through the authoring-evidence digest model. S8.1 owns lineage-manifest
  stale classes and migration routing. The table should distinguish those, or an implementer may
  accidentally build part of S8.1 under the S5.1 "stale" bullet.
- The BUILD/GATE split says S5.1 ships a default threshold, but it does not define what makes that
  default acceptable before calibration. Add a non-calibration acceptance rule such as "chosen to
  pass only exact/id-permuted and near-exact fixture positives, with all adversarial negatives
  raising." Otherwise a numeric default can still become an unreviewed policy decision.
- "Mechanism-only" plus "re-stamp protocol" needs one more boundary sentence: S5.1 may compute
  re-stamped evidence entries in memory, but must not overwrite `authoring_evidence.json` unless the
  plan deliberately accepts a writer path here. Right now §0 can be read both ways.
@@@@@@

======
Response (code-verified 2026-07-08):

- ✓ **"stale" overloaded — accept, sharpen the table.** Two distinct staleness concepts collide.
  S5.1 detects **rebind-local `stale-decision`** — and per your §1 point 6 the right framing is *"run
  the existing `evidence_findings` producer against the rebound projection"*, not "the rebind
  algorithm observes a changing decision digest." **Lineage-manifest stale classes + migration
  routing are S8.1**, untouched here. I'll split the table's "Negatives" row to name the
  evidence-digest `stale-decision` as the only staleness S5.1 raises, and add a one-line "S8.1 owns
  lineage-manifest staleness" exclusion so no one builds S8.1 under this bullet.
- ✓ **Non-calibration acceptance rule — accept, this is the anti-cheat teeth I was missing.** A bare
  "conservative default" is exactly the unreviewed-policy trap. I'll adopt your rule verbatim into
  D-4/DoD: *the default τ is acceptable pre-calibration iff it (i) passes only exact / id-permuted /
  near-exact positives and (ii) makes every adversarial negative raise* — nothing about real-data
  rates (that's S5.2). This makes the default falsifiable without pretending it's calibrated.
- ✓ **In-memory re-stamp only, no writer — accept, state it once, unambiguously.** S5.1 computes
  re-stamped evidence entries **in memory** inside the `RebindResult`; it does **not** write
  `authoring_evidence.json`. The persist path (and its regen-guard) is S5.2, consistent with D-6.
  I'll add the explicit "no evidence writer in S5.1" sentence to §0.
======

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

@@@@@@
Adversarial audit:

- The current typed model does not carry `rebind_anchors`: `ContainerNode` and `LeafNode` in
  `engine/src/engine/structure/projection.py` omit the field, and `structure_map_from_json()` keeps
  anchors only in the retained raw `doc`. S5.1 must either extend the dataclasses (and all
  load/render tests) or make `rebind.py` explicitly consume the raw document sidecar. The plan should
  name that choice; otherwise the mechanism may silently ignore anchors after load.
- Region population is underspecified for containers and mixed geometry. A node can own heading and
  signature atoms directly, plus descendant body atoms indirectly. Define whether the region is over
  own slots only, descendant union, or separate per-slot regions. Also define fail-loud behavior for
  multi-page nodes, absent geometry on some owned atoms, routed/pending geometry, and outlier boxes.
- The algorithm is phrased per node, but per-node independent best matches can produce an invalid
  projection: overlapping fresh atom ownership, child atoms outside a rebound parent extent, or a
  parent bound while a child fails. S5.1 needs a global consistency pass over the full rebound map
  (`ProjectionMap` + `validate_projection`/reference integrity) before any bind is considered
  successful.
- Candidate generation is the largest ambiguity. "Gather fresh-atom candidates" does not say what a
  candidate is: contiguous atom window, slot-shaped tuple of windows, heading/body split, page-local
  window, descendant subtree, or arbitrary set. Without a candidate grammar, the confidence score is
  not reproducible and tests can pass against an overly convenient fixture.
- The re-stamp protocol must define ordering. Extent digests for ancestors depend on descendant
  coverage, so a bottom-up/topology-aware recomputation is needed after all successful node bindings
  are assembled. Re-stamping a node immediately after its local bind can hide a later descendant
  failure or global ownership conflict.
- "Decision digest changed" cannot happen from atom rebinding alone if `node_id`/class/children are
  preserved. The actual stale-decision check compares old evidence against the current/rebound
  projection. The plan should say S5.1 runs the existing `evidence_findings`/decision producer against
  the rebound projection and treats any `stale-decision` as unresolved, rather than implying the
  rebind algorithm independently observes a changing decision digest.
@@@@@@

======
Response (code-verified 2026-07-08):

- ✓ **Typed model drops `rebind_anchors` — CONFIRMED, keystone build reality.** Verified:
  `ContainerNode` (projection.py:162) and `LeafNode` (:196) carry only
  `node_id/node_class/minted_by/children|body_atoms/designation/title/handle_policy`; `_node_from_json`
  (structure_map.py:176) never reads `rebind_anchors` or `decision` — both survive **only in raw
  `doc`** (the deliberate inv-25 "unmodeled reserved fields round-trip byte-stably without any code
  reading them" posture). But `rebind.py` **must** read the anchors, so inv-25's premise no longer
  holds for this field. **Decision (folds into D-1): model `rebind_anchors` in the typed layer** —
  extend both dataclasses + `_node_from_json` + render + the inv-25 test (which must now say "except
  `rebind_anchors`, consumed by S5.1"). `decision` **stays** raw/inert (S8.2, not read here). This is
  a real ripple I under-counted; §5 now lists projection.py + structure_map.py edits.
- ✓ **Region for containers / mixed geometry underspecified — accept, and it forces a new ruling.**
  You're right this is undefined. My proposed resolution (needs your sign-off — added as **D-3b**):
  the region anchor is a **local locate-checkpoint over the node's OWN atoms only** (leaf → its
  `body_atoms`; container → its `heading_atoms`/`signature_atoms`), **never the descendant union** —
  descendants carry their own anchors, and a union region would make a chapter container span the
  whole part. For own-atoms spanning pages, store a **per-page list of `{page, bbox}` checkpoints**
  (not one impossible cross-page box). Absent geometry on some own-atoms → the region covers only the
  present ones; **all own-atoms absent → no region anchor** (fingerprint + path carry it, honestly
  weaker). Routed/pending or outlier boxes → excluded from the region and surfaced in the report.
- ✓ **Per-node best-match → invalid projection — accept, this is the biggest correctness hole.** A
  greedy per-node pass can double-own a fresh atom, bind a parent whose child failed, or place child
  atoms outside a parent extent. **The mechanism becomes: (1) per-node candidate scoring → (2) a
  whole-map assignment that resolves ownership globally → (3) `validate_projection` +
  `assert_reference_integrity` over the full rebound `ProjectionMap` before ANY bind is "successful."**
  A node is bound iff the global map validates; otherwise its conflict is a finding. Promoted to a
  first-class algorithm phase (§1), a §4 invariant, and a DoD item. Non-negotiable — agreed.
- ✓ **Candidate grammar — accept, define it.** Undefined candidates make the score unreproducible.
  **Grammar (added to §1):** a candidate is a **page-local contiguous run of fresh canonical atoms**
  within the anchor region's page(s), scored **per owning slot** (body vs heading/signature). This
  bounds the search (answers the cross-cutting complexity point — no all-pairs scan) and makes the
  slot-shaped comparison explicit. The whole-map pass (above) then picks a non-overlapping assignment.
- ✓ **Re-stamp ordering — accept.** The extent payload's `beneath` union means an ancestor's extent
  digest depends on descendants, so re-stamping inline per bind is wrong. **Re-stamp is a single
  post-pass in bottom-up topological order, after the whole-map assignment is fixed** — so no node is
  re-stamped while a descendant is still unresolved. Folded into the protocol + a §4 invariant.
- ✓ **`stale-decision` framing — accept, reword.** Correct: atom re-binding alone cannot move a
  decision digest (class + child node_ids are re-bind-stable). S5.1 does **not** "watch a changing
  decision digest"; it **runs `evidence_findings`/`assert_evidence_gate` against the rebound
  projection** and treats any `stale-decision` as unresolved → report, no re-stamp. §1 reworded to
  say exactly that.
======

@@@@@!
Continued adversarial feedback:

- The proposed candidate grammar says candidates are "page-local contiguous runs ... within the
  anchor region's page(s)." That works for geometry-backed nodes, but not for `no-geometry`, nodes
  with all own-atoms geometry-absent, or short headings where region is intentionally absent. Define
  the non-geometry candidate index explicitly. Otherwise the `no-geometry` mode can only work by
  falling back to an unstated all-stream scan, which reopens the complexity and false-positive risks.
- D-3b changes `rebind_anchors.region` from today's nullable `{page,bbox_region}` object into a
  per-page checkpoint list. That is more than tightening `page >= 1`; it is a region-shape change.
  Rev 2 should name the exact wire shape (`region` as list? `regions`? one object with
  `checkpoints`?) and update the inv 13/24 schema tests around that shape, not only the content
  fingerprint tests.
@@@@@!

====!!
Response (code-verified 2026-07-08):

- ✓ **Non-geometry candidate index — accept, and it has a natural bound: reading order.** Right that
  region-bounded page-local windows only exist where geometry does; `no-geometry`, all-absent nodes,
  and (intentionally region-less) short headings would otherwise fall to an all-stream scan. The fix:
  **structural path *is* the index.** In reading order a node's fresh atoms lie in the band bounded by
  its already-assigned preceding/following siblings — a **monotone, non-crossing alignment** of the
  old node order against the fresh atom stream. So candidate generation is mode-parameterized:
  geometry present → region page-local window; geometry absent → reading-order band bounded by
  neighbor assignments. Neither is an all-stream scan. This reuses the DT-3 monotone banded-locate
  pattern already in `geom_match` (`_bands` / `locate_pages` / `_BandMax`) — not new machinery. **New
  sub-decision for your nod: the no-geometry candidate index = monotone reading-order band.**
- ◑ **D-3b region shape — partial: I'll retreat to a single seed and *avoid* the shape change you
  flagged.** You're right a per-page checkpoint *list* is a region-shape change (inv 13/24 rewrite),
  not just `page>=1`. On reflection the list is over-built for a *checkpoint*: region stays a **single
  `{page, bbox_region}` object** = the node's **first own-atom page + box** (a locate *seed*),
  tightened to `page>=1`. A multi-page own-extent is recovered by the reading-order alignment above,
  not by storing every page's box. So the wire shape is unchanged (region-only → region + fingerprint),
  inv 13/24 need only the `page>=1` tightening + the fingerprint addition, and **D-3b becomes "single
  seed," not "per-page list."** If you'd rather store the full per-page list (richer checkpoint, bigger
  surface + test rewrite), say so — but the seed is the honest minimum for a checkpoint.
====!!

@@@@!!
Continued adversarial feedback:

- "Bounded by its already-assigned preceding/following siblings" is circular unless the whole-map
  assignment establishes those bounds. Rev 2 should frame this as a joint monotone assignment/DP over
  old node order and fresh atom indices, with sibling bounds produced by the assignment, not as a
  per-node step that assumes neighbors are already settled.
- The "single seed" region needs an explicit seed-selection rule. If the first own atom has absent,
  routed, pending, or outlier geometry, does S5.1 pick the first eligible present own-atom box, or mark
  the region missing? Without that rule, two implementations can produce different candidate windows
  from the same stored node.
@@@@!!

===!!!
Response (code-verified 2026-07-08):

- ✓ **Circularity — accept, reframe as one joint monotone assignment, not per-node bands.** You're
  right my "bounded by already-assigned siblings" was circular. The correct frame: a **single global
  monotone alignment/DP** of the old node reading-order against the fresh canonical atom indices
  (non-crossing, contiguous spans) — the **sibling bounds are the DP's *output*, not a precondition**.
  Geometry supplies **hard pins** that constrain the DP where a region seed exists; the fingerprint is
  the per-span **scoring function**; `no-geometry` is the *same* DP with zero pins. This unifies the
  three modes into one assignment pass and subsumes the "whole-map assignment" phase I already
  conceded — there is no per-node step that assumes neighbors are settled. Rev 2 will state it as the
  DP, citing the DT-3 banded precedent (`geom_match._bands`) for the monotone-band mechanics.
- ✓ **Seed-selection rule — accept, make it deterministic.** Rule: the region seed is the `bbox` of
  the node's **first own-atom in canonical order whose `geom.present` is True** (absent / routed /
  pending geometry is skipped, since those atoms have no present box); **if no own-atom has present
  geometry, the region is absent** — the node is geometry-less and rides the DP with no pin (its mode
  decides whether that means `missing-anchor`). On **outliers**: the `Geom` model carries only
  `present / bbox / page / provenance` — there is **no outlier predicate**, so S5.1 will **not** invent
  one (that would be an undefined, non-deterministic rule); outlier-box exclusion is deferred to S5.2
  calibration if it ever proves necessary. Stated honestly rather than claiming a rule with no backing
  field.
===!!!

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

@@@@@@
Adversarial audit:

- The schema bump blast radius is understated. Changing the schema `const` to 2 means all v1 fixture
  documents and any live v1 map fail Tier-1 unless migrated or explicitly version-routed. The plan
  names a new v2 differ-fixture, but should also say whether existing v1 fixtures are upgraded in
  place, duplicated as v1 historical fixtures, or migrated by a small test helper.
- `STRUCTURE_MAP_SCHEMA_STATUS = {1: born, 2: provisional}` is conceptually right, but the current
  status map is keyed by the live constant only. S5.1 should preserve v1's born status explicitly
  when the live constant moves to 2, or tests that inspect historical status lose useful signal.
- A fingerprint sub-object needs a tight schema now, not just "sub-object": algorithm id, normalizer
  id, k, token_count, shingles/signature representation, and enough bounds to prevent huge embedded
  arrays. Without these fields, a future normalizer or k change can make old fingerprints look valid
  but semantically stale.
@@@@@@

======
Response (code-verified 2026-07-08):

- ✓ **Blast radius — accept, and it's smaller than it looks *if* the fingerprint is optional.**
  Because the schema `const` is a single live value, every `schema_version:1` fixture fails Tier-1
  against a v2 schema. But `content_fingerprint` will be **optional** in `rebind_anchors`, so a v2 map
  with no fingerprint is valid — meaning the migration for existing conforming fixtures is a
  **mechanical `schema_version: 1→2` field bump with zero content change**. Strategy (added to §2/§5):
  bump all conforming fixtures to v2; the **new differ-fixture** is the one that *populates* the
  fingerprint (and births v2). **v1 historical read-coverage is genuinely S8.1's concern** (stale-
  version routing/migration), not S5.1's — I'll say so rather than fabricate a v1-reader test here.
- ✓ **Preserve v1's born status — accept.** `STRUCTURE_MAP_SCHEMA_STATUS` becomes `{1: born, 2:
  provisional}` → `{1: born, 2: born}` post-birth, keeping v1's entry explicitly rather than replacing
  the sole key. Cheap and keeps the historical signal.
- ✓ **Tight fingerprint schema now — accept, this is D-2's on-disk realization.** The sub-object
  carries `{algo_id, normalizer_id, k, token_count, shingles: [sorted, bounded]}` with a
  `maxItems`/size bound and canonical (sorted) ordering. `normalizer_id` is the exact lever that makes
  your D-2 accent/punctuation point detectable: a normalizer change flips the id → the fingerprint
  reads as stale rather than silently mismatching. Folded into §2 + D-2.
======

@@@@@!
Continued adversarial feedback:

- Making `content_fingerprint` optional is fine for mechanical fixture migration, but S5.1's rebind
  mechanism requires it for any node that lacks a usable region. Rev 2 should distinguish "schema
  admits absent fingerprint" from "rebind eligibility requires the needed anchor set." Otherwise a v2
  map can be born and valid but fail every content-led bind for reasons the schema could have made
  visible through a report finding such as `missing-anchor`.
- If the response keeps v1-reader coverage in S8.1, S5.1 still needs one test proving a v2 map with
  omitted optional fingerprints does not accidentally auto-bind via geometry/path alone in
  `geometry-tie-break` or `no-geometry`. Optional-at-schema cannot become permissive-at-rebind.
@@@@@!

====!!
Response (code-verified 2026-07-08):

- ✓ **Schema-optional ≠ rebind-permissive — accept, sharp distinction.** Two separate gates: (i)
  *schema* validity — a v2 map with an absent `content_fingerprint` is well-formed and born; (ii)
  *rebind eligibility* — a node whose mode needs an anchor it lacks is **not** bindable. That node
  yields a **`missing-anchor` report finding** (added to the closed enum per your D-6 point), never a
  silent skip and never a fall-through bind. So "born and valid but fails every content-led bind"
  surfaces as N explicit `missing-anchor` findings — the visibility you want, made a first-class
  reason rather than an inferred absence.
- ✓ **Optional-at-schema cannot become permissive-at-rebind — accept, and it forces a policy I want
  you to confirm.** The guard: a v2 map with omitted fingerprints must **not** auto-bind via
  geometry/path alone in `geometry-tie-break` or `no-geometry`. This makes the fingerprint **de-facto
  required for auto-bind** — in content-led modes it is the *lead* signal, and under no-rescue (D-4)
  geometry/path only *disambiguate ≥τ candidates*, never *are* the bind evidence; even in
  `geometry-primary` the fingerprint is the *verify* step, so its absence → `missing-anchor`. Net: **a
  node with no fingerprint routes to the worklist in every mode.** That's the abstain-not-guess
  reading — but it effectively makes the optional field mandatory-for-bind, so I'm flagging it as a
  policy point: **confirm "fingerprint required for auto-bind; absent → `missing-anchor` → worklist"
  in all three modes.** On your yes I add it as a §4 invariant + a mutant (binding a fingerprint-less
  node on geometry alone must red).
====!!

@@@@!!
Continued adversarial feedback:

- Fingerprint-required-for-auto-bind is coherent, but it means mechanically bumped v2 fixtures with
  omitted fingerprints are **load/schema fixtures only**, not valid happy-path rebind fixtures. Rev 2
  should say every S5.1 happy rebind fixture must populate the per-slot fingerprints, or the test
  substrate will contradict the new eligibility rule.
@@@@!!

===!!!
Response (code-verified 2026-07-08):

- ✓ **Accept — and I read this as your confirmation of the fingerprint-required policy** ("coherent"),
  so I'll lock it. Consequence for the test substrate: **two disjoint fixture classes**, never
  conflated —
  1. **schema/load fixtures** — the mechanically bumped v1→v2 maps with fingerprints *omitted*;
     exercise only schema validity + the born gate + inv 13/24 (incl. malformed-fingerprint
     rejection). They are **not** valid rebind inputs and no rebind test may bind against them.
  2. **rebind happy-path fixtures** — per-slot fingerprints **and** region seeds populated; exercise
     the actual bind / re-stamp / whole-map validation.
  A happy-path fixture with omitted fingerprints would make every node `missing-anchor` — so using one
  as a "positive" would silently contradict the eligibility rule (exactly the single-fixture-blind-spot
  trap). §5 will name the two classes explicitly, and a rebind positive fixture is *defined* as one
  carrying the full anchor set its mode requires.
===!!!

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

@@@@@@
Adversarial audit:

- I agree with (a), but only if the plan also updates the typed read surface or explicitly documents
  raw-doc access. A schema-only anchor is a trap: it validates and round-trips while the in-memory
  `ProjectionMap` has no anchor field for `rebind.py` to consume.
- Self-sufficiency is overstated if the fingerprint stores only shingles and token count. Rebinding
  also needs enough slot/path context to reconstruct the old node's intended span shape. Structural
  path can be derived, but slot shape (`heading_atoms`, `signature_atoms`, `body_atoms`, descendant
  extent) and old atom counts must either remain in the map or be derivable from it under a precise
  rule.
- Option (b) is dismissed too quickly. If fingerprints get large, a sidecar has one real advantage:
  it keeps the hand-authored map readable and limits schema churn in the durable catalogue. I still
  prefer (a) for atomicity, but the reason should be "anchors must travel with node identity," not
  "no gain."
@@@@@@

======
Response (code-verified 2026-07-08) — **(a) confirmed, with your corrections folded in:**

- ✓ **Typed read surface — accept, this is the condition that makes (a) real.** As in §1 point 1:
  (a) is only coherent if the anchors are **modeled typed**, not left in raw `doc`. That edit
  (dataclasses + loader + render + inv-25 carve-out) is now an explicit part of choosing (a), listed
  in §5. Without it, (a) is the schema-only trap you name.
- ◑ **Self-sufficiency — partial: the map already carries most of what you list.** Slot *shape*
  (`heading_atoms`/`signature_atoms`/`body_atoms`) and the **old** atom-id lists (hence old counts)
  are already in the stored map, and structural-path is derivable — so the map *is* self-sufficient
  for those. What it does **not** carry is the old *content summary* (the fresh atoms have new ids and
  possibly re-tokenized text), which is exactly why the **fingerprint** must be stored. So I'll
  narrow the claim to "self-sufficient *for the content signal*, given the slot shape + path already
  in the map," and make fingerprint granularity **per-slot** (leaf: body; container: heading +
  signature separately) so the shape context you want is preserved — see the cross-cutting response.
- ✓ **Reason correction — accept.** The real argument for (a) over (b) is **atomicity: the anchor
  must travel with node identity** (one artifact, one lineage, one regen-guard), not "no gain." (b)'s
  readability advantage is real if fingerprints are large — which is why D-2 now **bounds + compacts**
  the shingle representation (cap + sorted canonical form), buying (a) the readability (b) offered.
  Rationale rewritten.
======

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

@@@@@@
Adversarial audit:

- The normalizer citation is good, but `geom_match.normalize_tokens` preserves accents and interior
  punctuation by design. That is defensible for matching OCR text, but it may be brittle under OCR
  accent loss or apostrophe variants. If accent/punctuation tolerance is intentionally deferred to
  S5.2 calibration, say so; if not, the fingerprint normalizer needs its own algorithm id.
- K=3 Jaccard has bad behavior on short nodes/headings: fewer than three tokens yields an empty
  shingle set unless special-cased, and many chapter headings are exactly the sort of short text
  where structural-path and geometry matter. Define fallback k/min-token behavior for short nodes.
- Plain set Jaccard discards multiplicity. Repeated formulaic paragraphs, duplicated headings, and
  boilerplate can collide. At minimum the report should include token_count ratio and maybe multiset
  Jaccard or containment as secondary evidence, with ambiguity raising when content is common.
- "Order-tolerant (robust to local reorder)" is not free: too much order tolerance makes common
  rephrased or repeated material look safe. The `ordered_coverage` cross-check should be promoted
  from "available" to part of the default scoring/report, even if not a hard gate in every mode.
- Storing full shingle sets may bloat large maps. If you keep sets, cap/check serialized size and
  define deterministic ordering in the schema. If compactness matters, MinHash can wait, but the
  on-disk representation still needs stable canonicalization.
@@@@@@

======
Response (code-verified 2026-07-08):

- ✓ **Normalizer accent/punct behavior — accept, verified + record it.** Confirmed
  `geom_match.normalize_tokens` (geom_match.py:109): NFC → whitespace split → strip *edge*
  non-alphanumerics → casefold; **accents preserved (no folding), interior apostrophes/hyphens
  kept**. So it is brittle under OCR accent loss / apostrophe variants. **Ruling: that tolerance is an
  S5.2 calibration question, made *detectable* now via the stored `normalizer_id`** — S5.1 reuses
  `normalize_tokens` as `normalizer_id="geom_match.normalize_tokens@v1"`; if S5.2 wants accent-folding
  it's a new id, never a silent swap. Stated in D-2 + §2.
- ✓ **Short-node / empty-shingle — accept, real and headings are the victim.** For a node with
  `< k` tokens the k=3 shingle set is empty → a false "no evidence" pass. **Fallback:** `k' =
  min(k, token_count)` (down to unigrams) with `token_count` always stored; a node too short to
  fingerprint reliably **binds only with geometry/path corroboration or fails loud** (never on an
  empty set). Added as the short-node §4 invariant you request below.
- ✓ **Multiplicity — accept.** Set Jaccard collides on repeated/boilerplate paragraphs and duplicate
  headings. The report will carry the **`token_count` ratio** as secondary evidence and **containment
  + multiset overlap** alongside Jaccard; **common/duplicated content raises (ambiguous)** rather than
  binding. Folded into the scorer + report.
- ✓ **Promote `ordered_coverage` — accept.** Moved from "available" to **part of the default report**
  (an order-sensitivity signal), so too-order-tolerant collisions are visible; whether it is a *hard*
  gate stays per-mode (S5.2 may tighten). Consistent with the geom_match primitive already used for
  order_qa.
- ✓ **Bloat / canonicalization — accept.** Schema stores shingles as a **sorted, size-bounded**
  list (`maxItems` + a serialized-size check), deterministic ordering pinned so the map is
  byte-stable and diff-able. MinHash deferred; if adopted later it's a `normalizer_id`/`algo_id`
  change, not a silent representation swap.
======

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

@@@@@@
Adversarial audit:

- The single-space pin matches the current `Geom` model: `PageGeometry.page` is 1-based scan number
  and `WordBox.bbox` is PDF page-point space. However, the schema currently allows `page >= 0`, while
  geometry pages require `page > 0`. S5.1 should tighten the schema or add a Tier-2 check, otherwise
  the anchor space is not actually the atom `Geom` space.
- "No discriminator needed for PLL" is true only if the anchor includes enough provenance to ensure
  the stored region and fresh atom boxes came from the same primary witness policy. `Geom` already
  carries `matched_witness_id`, `geometry_engine`, `match_method`, and confidence; the region hash
  in S4 excludes provenance. If S5.1 stores no discriminator, the report should still surface the
  witness/engine/method used to build and compare the region.
- Multi-page node policy is missing. A single `{page,bbox_region}` cannot represent a chapter or
  container spanning pages unless the region is for a local checkpoint (heading) rather than the
  whole extent. That choice affects D-2 and candidate generation; define it before implementing.
@@@@@@

======
Response (code-verified 2026-07-08):

- ✓ **Page-bound mismatch — CONFIRMED, tighten it.** Verified: `PageGeometry.__post_init__`
  (geometry.py:133) raises on non-positive → `page` is a 1-based scan number; the schema's
  `region.page` is `minimum: 0` (schema:159), so it admits a `page` that can never equal a real
  `Geom.page`. That is not the atom-`Geom` space it claims to share. **Fix (rides the v2 bump):
  tighten `region.page` to `minimum: 1`** + a Tier-2 check; added as the page/coordinate §4 invariant.
- ✓ **Provenance surfacing — accept.** Correct that the stored region carries no witness/engine/method
  and the S4 region hash excludes provenance, so "same primary-witness policy" isn't guaranteed by the
  region alone. Rather than widen the *stored* anchor (more schema surface), the **`RebindReport`
  surfaces the `matched_witness_id` / `geometry_engine` / `match_method` used to build-and-compare the
  region**, so a reviewer can see whether the two sides share a policy. If you'd rather pin it in the
  anchor, that's a bigger v2 surface — flag it and I'll add it.
- ✓ **Multi-page node policy — accept, resolved by D-3b (§1 point 2).** A single `{page,bbox_region}`
  cannot hold a page-spanning extent, and it shouldn't try: the region is a **local locate-checkpoint
  over own-atoms**, stored **per-page** where own-atoms span pages. This is the "checkpoint, not whole
  extent" reading you land on, and it's now an explicit sub-decision (**D-3b**) tied to the candidate
  grammar (page-local windows) and the per-slot fingerprint.
======

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

@@@@@@
Adversarial audit:

- "Conservative" needs a number or a named constant plus rationale, even if uncalibrated. A default
  like `DEFAULT_FINGERPRINT_THRESHOLD` should be deliberately high and documented as uncalibrated;
  tests should assert the constant is used, not inline literals.
- The mode names are inconsistent here: the tracker/config enum says `geometry-tie-break`, but this
  bullet says `tie-break`. Use the exact enum token everywhere to avoid a branch that never fires.
- The proposed per-mode weighting still leaves "geometry corroborating boost" ambiguous. A boost can
  make a below-threshold fingerprint auto-bind, which conflicts with the fail-loud posture. State
  whether geometry can only break ties among already-above-threshold candidates, or can raise a score
  over the threshold. For PLL, the safer default is "no threshold rescue by geometry."
- Monotone-adjustable is weaker than monotone-checkable. S5.1 can expose per-mode thresholds in one
  config object and include a small invariant that `no-geometry >= geometry-tie-break >=
  geometry-primary` for defaults, leaving S5.2 to calibrate/prove the property over data.
@@@@@@

======
Response (code-verified 2026-07-08):

- ✓ **Named constant, not a literal — accept.** `DEFAULT_FINGERPRINT_THRESHOLD` (a deliberately
  **high**, docstring-flagged *uncalibrated* placeholder), asserted-by-name in tests, never an inline
  number. Its acceptance is your §0 non-calibration rule (positives-only + all-negatives-raise), not a
  claimed rate.
- ✓ **Mode-token consistency — accept, and it's a genuine bug risk.** The config enum is
  `geometry-tie-break`; my "tie-break" shorthand could branch on a token that never matches
  `seg.geometry_mode`. I'll use the **exact enum tokens** (`geometry-primary` / `geometry-tie-break` /
  `no-geometry`) everywhere in code and plan, with a test binding the branch set to the schema enum
  (same anti-drift pattern as #30's `test_geom_regate` enum↔constant binding).
- ✓ **No threshold rescue by geometry — accept, and make it the explicit PLL posture.** Critical: a
  geometry "boost" that lifts a sub-τ fingerprint over the line silently defeats fail-loud. **Ruling:
  geometry (and structural-path) may only *disambiguate among candidates already ≥ τ* — never raise a
  score across τ.** `geometry-primary` = region-hit **AND** fingerprint ≥ τ (conjunction, not sum);
  `geometry-tie-break` = fingerprint ≥ τ, geometry breaks ties; `no-geometry` = fingerprint ≥ τ, path
  breaks ties. Added the "geometry-rescues-below-threshold" mutant to the hunt (your §4 point).
- ✓ **Monotone-*checkable* not just adjustable — accept, cheap win.** Per-mode τ live in one
  `RebindPolicy` object, and S5.1 adds a **structural** default-ordering invariant
  `τ(no-geometry) ≥ τ(geometry-tie-break) ≥ τ(geometry-primary)`. That's a check on the *defaults*,
  not the data property (which stays S5.2) — so it strengthens without crossing the calibration line.
======

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

@@@@@@
Adversarial audit:

- Direct `load_stream` is the right escape hatch, but it bypasses `load_workspace_streams`'
  cross-stream reference-integrity assertion. S5.1 must explicitly call `assert_reference_integrity`
  for each canonical+witness set it relies on, or document that `RebindContext` accepts already
  validated streams only.
- A fresh canonical loaded from a path outside the workspace will not have a manifest home, freeze
  pin, or canonical hash comparison. That is acceptable for mechanism tests, but the context should
  record stream ids/hashes in the binding report so a user can tell which two streams were compared.
- The old map's manifest names a canonical stream id and hashes. The plan should require checking
  that `old_canonical` is the stream the old map claims, not merely any caller-provided stream.
  Otherwise the mechanism can faithfully rebind from the wrong baseline.
@@@@@@

======
Response (code-verified 2026-07-08):

- ✓ **Reference-integrity on the escape hatch — accept.** Correct: `load_stream` alone skips the
  cross-stream `assert_reference_integrity` that `load_workspace_streams` (atom_store.py:515) runs.
  **`RebindContext.__post_init__` calls `assert_reference_integrity(old_canonical, old_witnesses)`**
  (and the same for the fresh set) so a dangling `derived_from` reds at construction, not mid-rebind.
- ✓ **Record the two streams — accept.** A fresh canonical loaded outside a workspace has no manifest
  home; the `RebindReport` records **both streams' ids + content/geometry hashes** so a reader knows
  exactly which baseline→target was compared. (Persisting it is S5.2.)
- ✓ **Baseline-binding check — accept, this is a silent-wrong guard I missed.** `RebindContext` must
  verify `old_canonical`'s id + `canonical_content_hash` match what `old_map.manifest` claims
  (`canonical_stream_id` / `canonical_content_hash`), else a perfectly-scored rebind runs against the
  wrong baseline. Added as a construction-time fail-loud + the baseline-binding §4 invariant you name.
======

@@@@@!
Continued adversarial feedback:

- `RebindContext(old_map, old_canonical, fresh_canonical)` is no longer enough if construction runs
  `assert_reference_integrity` for both stream sets. The context needs `old_witnesses` and
  `fresh_witnesses`, or it must explicitly require pre-validated canonical streams and skip that
  assertion. The response chooses assertion, so update the constructor shape in D-5/§5/§7.
- The baseline check should compare both `canonical_content_hash` and `canonical_geometry_hash` when
  geometry is used. Matching only content can still bind from a baseline with drifted geometry
  anchors, which is exactly the class of wrong substrate S5.1 is trying to avoid.
@@@@@!

====!!
Response (code-verified 2026-07-08):

- ✓ **Constructor shape — accept, witnesses are required.** Confirmed `assert_reference_integrity`
  (atom_store.py) takes `(canonical, witnesses)` and resolves each canonical atom's `derived_from`
  against the witness set — so running it needs the witnesses. Constructor becomes **`RebindContext(
  old_map, old_streams, fresh_streams)`** where each `*_streams` is a `{canonical + witnesses}` set
  (the `load_workspace_streams` return shape), integrity-asserted at construction. Updated in
  D-5/§5/§7. Honest cost: mechanism-test fixtures must build a proper canonical+witness set with
  resolving `derived_from` (not a bare `AtomStream.canonical(atoms)`) — the born-gate fixtures already
  do this, so precedent not new burden. (Alternative you could pick instead: `RebindContext` accepts
  *pre-validated* streams and skips re-assertion — but I read your D-5 point as choosing assertion,
  and re-asserting a valid set is cheap + kills the "who validated the escape-hatch streams"
  ambiguity.)
- ✓ **Baseline check compares both hashes — accept.** Confirmed the manifest carries both
  `canonical_content_hash` and `canonical_geometry_hash` (schema §manifest, split precisely so a
  geometry re-match doesn't masquerade as a content change). Since the region anchors ride the
  geometry space, a baseline with drifted geometry is exactly the wrong-substrate class S5.1 guards.
  So the baseline-binding check verifies **both** `old_canonical`'s content hash **and** its geometry
  hash against `old_map.manifest` — the geometry half gated on geometry actually being used (skipped
  in `no-geometry`, where there is no region to trust). Folded into the baseline-binding invariant.
====!!

@@@@!!
Continued adversarial feedback:

- The content/geometry baseline checks should call the same hash producers used by
  `build_manifest()` (`canonical_content_hash` / `canonical_geometry_hash` payload definitions), not
  reimplement equivalent-looking hashes inside `rebind.py`. Otherwise S5.1 can drift from the
  manifest contract while still passing its own tests.
@@@@!!

===!!!
Response (code-verified 2026-07-08):

- ✓ **Accept, and it needs a small extraction — the shared producer doesn't exist yet.** Confirmed:
  `build_manifest` (structure_map.py:473–503) builds the content payload
  (`{atom_id, text, raw_span, raw_source_hash}`) and geometry payload (`{atom_id, present, page,
  bbox}`) **inline** and hashes via the module-private `_hash_canonical` (:434, "THE hash producer,
  D-S4-I"). So today there is no public function `rebind.py` could call — importing `_hash_canonical`
  and re-inlining the payload field-lists is precisely the drift you name (the payload *definition*,
  not just the digest, is the contract). **Fix: extract `canonical_content_hash(stream)` /
  `canonical_geometry_hash(stream)` as shared producers, have `build_manifest` call them, and have the
  baseline check call the *same* functions** — one definition, so a payload/digest change ripples to
  both (and inv 20 already guards `_hash_canonical` substitution). A small, contract-preserving
  refactor of structure_map.py (already in §5's edit list); the rebind baseline check never carries a
  lookalike hash.
===!!!

### D-6 — Output: in-memory re-bound map + report, or persisted migrated map?

- **Recommendation.** S5.1 produces, **in memory**: (i) the re-bound map (stored `node_id`s now owning
  fresh atom ids), (ii) a **binding report** (per node: bound / unresolved-reason, score, mode,
  candidate evidence), and (iii) the mechanical **extent-digest re-stamps** for confident binds.
  **Persisting** the migrated map under the regen-guard (the forward-migration write path) is **S5.2**
  (its regen-guard registration). This makes the re-binding tier fully testable (regenerated stream →
  re-bind → assert bindings / assert the raise) without a persist step that S5.2 owns. Confirm.

@@@@@@
Adversarial audit:

- In-memory output is the right S5.1 boundary, but "re-bound map" is ambiguous because the current
  loaded `StructureMap` contains both raw `doc` and typed `ProjectionMap`. The result should specify
  whether it returns a new `ProjectionMap`, a full JSON document, or both. If evidence re-stamps are
  included, a full document-like structure is probably necessary for downstream writer tests.
- The binding report should be a typed dataclass with a closed unresolved-reason vocabulary, not a
  loose dict. This is the substitute for the not-yet-built §3.6 worklist and becomes the stable seam
  S5.2 can measure.
- A partial success policy is missing. If 60 nodes bind and 1 fails, does the result carry the 60
  tentative bindings plus one unresolved finding, or does the whole operation raise? For human
  worklists, non-raising findings are more useful; for API safety, a final `assert_all_bound()` can
  raise. The plan should pick both surfaces deliberately.
@@@@@@

======
Response (code-verified 2026-07-08):

- ✓ **Result type made concrete — accept.** `RebindResult` carries: (i) the **migrated document**
  (a full JSON-shaped structure-map with fresh atom ids + re-stamped extent digests, **unpersisted** —
  document-shaped precisely so S5.2's writer tests have something to write), (ii) the typed
  `RebindReport`, (iii) the in-memory re-stamped evidence entries. Not a bare `ProjectionMap` (too
  thin for the writer) and not a persisted file (that's S5.2).
- ✓ **Typed report + closed reason vocabulary — accept.** `RebindReport` is a dataclass; unresolved
  reasons are a **closed enum** (`zero-candidate | ambiguous | below-threshold | stale-decision |
  global-conflict`), mirroring evidence.py's closed `EVIDENCE_FINDING_KINDS` so a typo can't mint a
  pseudo-reason. This is the stable seam S5.2/S8.1 consume.
- ✓ **Both surfaces — accept, and there's a precedent to copy.** Exactly the evidence.py split:
  a **non-raising `rebind(...) -> RebindResult`** (all tentative binds + all findings, worklist-
  friendly) and a **strict `assert_all_bound(result)`** that raises `RebindError` if any node is
  unresolved (API safety). Partial success is represented, never hidden; the caller chooses.
======

@@@@@!
Continued adversarial feedback:

- The phrase "migrated document ... with fresh atom ids + re-stamped extent digests" is structurally
  inaccurate: extent digests live in the authoring-evidence sidecar, not in `structure_map.json`.
  Rev 2 should say `RebindResult` carries a migrated **structure-map document** plus separate
  in-memory **re-stamped evidence entries**. Keeping that boundary explicit prevents an implementer
  from trying to add digest fields to the map schema.
- The closed unresolved-reason enum should include `missing-anchor` or equivalent. With optional
  fingerprints, absent geometry, and short-node fallbacks, "zero-candidate" and "below-threshold" do
  not accurately distinguish "we had no legal signal to search with" from "we searched and found
  nothing."
@@@@@!

====!!
Response (code-verified 2026-07-08):

- ✓ **Digests live in the evidence sidecar, not the map — accept, my wording was structurally wrong.**
  Confirmed: `structure_map.json` nodes carry no digest field (the node shape is
  ids/class/atoms/handle/anchors/decision only); the extent/decision digests live in the **separate
  authoring-evidence sidecar** (`evidence.py` `load_authoring_evidence`, its own schema + stale_class +
  book), and §1.4.1b states the sidecar hash does not enter structure-map lineage. So `RebindResult`
  carries **two separate things**: (i) the migrated **structure-map document** (fresh atom ids in the
  node slots) and (ii) the in-memory **re-stamped authoring-evidence entries** — never digest fields
  grafted onto the map. Fixed in D-6/§7 so no implementer tries to add digests to the map schema.
- ✓ **`missing-anchor` in the enum — accept, converges with block 2.** The closed unresolved-reason
  enum becomes **`zero-candidate | ambiguous | below-threshold | missing-anchor | stale-decision |
  global-conflict`**. `missing-anchor` = "no legal signal to search with" (the anchor the mode needs
  is absent), distinct from `zero-candidate` = "searched the legal space, found nothing" and
  `below-threshold` = "found a candidate, score < τ." That three-way split is the diagnostic precision
  you're asking for.
====!!

### D-7 — "The active mode recorded in lineage"

The done-when says the active mode is recorded in lineage so a re-bind is interpretable after the
fact. #30 landed the mode in `manifest.segmentation.geometry_mode`.

- **Recommendation.** S5.1 **reads** the mode from `seg.geometry_mode` and **stamps it into the
  re-bind result's provenance** (the binding report), not a new structure-map field. The manifest
  stays the mode's durable home until an S5 rebind-config layer exists (the tracker already records
  this). Confirm the manifest-as-home + report-as-provenance split, or say you want a mode field on
  the persisted re-bind artifact (that would ride D-6's S5.2 persist step).

@@@@@@
Adversarial audit:

- This recommendation is too weak against the tracker wording. The S5.1 done-when says the active
  mode is recorded in lineage; a purely transient report does not satisfy "after the fact" unless
  that report is persisted or attached to the migrated artifact later. At minimum, S5.1 should define
  the report's provenance fields now and S5.2 should be named as the persist owner.
- The mode source should be recorded as well as the mode: manifest path, manifest schema version, and
  whether `geometry_mode` was explicit or absent/fallback. The config model says absent means
  "conditional-primary" fallback; S5.1 must not silently invent a mode without reporting that weaker
  provenance.
@@@@@@

======
Response (code-verified 2026-07-08):

- ✓ **Too weak vs the tracker — accept, and name the persist owner.** You're right that "recorded in
  lineage / after the fact" is not met by a purely transient report. S5.1 **defines the report's
  provenance fields now** (mode + source, below) and **S5.2 is the named persist owner** (it attaches
  the provenance to the migrated artifact under the regen-guard). I'll state that split explicitly so
  the DoD doesn't over-claim "after the fact" for an unpersisted object.
- ✓ **Record source, not just mode — CONFIRMED against the model.** Verified: models.py:163 comment
  says `geometry_mode` absent means "S5 falls back to conditional-primary." So S5.1 must **not**
  silently proceed on an invented mode. The report records `{mode, source: manifest|fallback,
  manifest_schema_version}`; when `seg.geometry_mode is None` the report flags **`source=fallback
  (conditional-primary)`** as weaker provenance rather than pretending the manifest ruled it. For PLL
  it's `source=manifest (geometry-tie-break)`, so this only bites generic/unrun books — exactly where
  a silent invention would be worst.
======

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

@@@@@@
Adversarial audit:

- Add a global-consistency invariant: two individually high-scoring node candidates that overlap in
  fresh atom ownership must fail loud or be resolved by a deterministic whole-map assignment. This
  is the main misbind class not covered by the current per-node tests.
- Add a short-node invariant: a one- or two-token heading with no k=3 shingles still behaves
  intentionally (binds only with geometry/path corroboration or fails loud). This catches the empty
  shingle-set false pass.
- Add a page/coordinate invariant: `rebind_anchors.region.page` rejects 0 or any page convention that
  cannot compare to `Geom.page`. The current schema says minimum 0 while `PageGeometry` requires
  positive scan numbers.
- Add a typed-model/round-trip invariant: a loaded v2 map exposes `content_fingerprint` to the rebind
  mechanism and re-renders byte-stably. This specifically catches the current risk where schema
  admits anchors but `ProjectionMap` drops them.
- Add a baseline-binding invariant: `RebindContext` refuses an `old_canonical` whose id/hash does not
  match the old map manifest. This prevents a perfectly scored rebind from the wrong old substrate.
- The mutation hunt should include "geometry boost rescues below-threshold fingerprint" if the
  intended PLL posture is no rescue. Otherwise that policy will drift unnoticed.
@@@@@@

======
Response (code-verified 2026-07-08): **all six accepted into the §4 invariant/mutant set.**

- ✓ **Global-consistency (overlap) invariant** — two high-scoring nodes claiming the same fresh atom
  → whole-map assignment resolves deterministically or fails loud; the greedy-per-node mutant reds.
  This is the §1-point-3 correctness phase given a test.
- ✓ **Short-node invariant** — a 1–2 token heading (no k=3 shingles) binds only with geometry/path
  corroboration or fails loud; the empty-shingle-set false-pass mutant reds.
- ✓ **Page/coordinate invariant** — `region.page` rejects 0 / any value not comparable to
  `Geom.page`; mutant that keeps `minimum:0` reds. (Verified mismatch, D-3.)
- ✓ **Typed-model round-trip invariant** — a loaded v2 map **exposes `content_fingerprint` to
  `rebind.py`** and re-renders byte-stably; the mutant that drops the field on load (today's inv-25
  behavior) reds. This is the guard on the §1-point-1 trap.
- ✓ **Baseline-binding invariant** — `RebindContext` refuses an `old_canonical` whose id/hash ≠ the
  old map's manifest; the mutant that accepts any caller stream reds. (D-5.)
- ✓ **Geometry-no-rescue mutant** — "geometry boost lifts a sub-τ fingerprint over the line" must be
  killed; it encodes the D-4 no-rescue posture so the policy can't drift silently.

Added on top (from my own responses): **re-stamp ordering** (bottom-up; a mutant re-stamping an
ancestor before a descendant resolves reds) and **`stale-decision` via the evidence producer** (a
mutant that machine-refreshes the decision digest reds).
======

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

@@@@@@
Adversarial audit:

- Missing files/surfaces: `src/engine/structure/projection.py` and `src/engine/structure/structure_map.py`
  almost certainly need edits if anchors become typed or if v2 load/render must expose fingerprints.
  `src/engine/structure/__init__.py` export pins will need updates for the new public rebind types.
- Missing tests: existing `test_structure_map.py` inv 13/24 tests must be updated for the v2 anchor
  shape, including rejection of malformed fingerprint fields and retained rejection of `.geom` /
  atom-level `present` smuggling.
- Missing fixture/migration work: every existing conforming structure fixture currently has
  `schema_version: 1`; the plan should say which ones become v2 and how v1 historical coverage is
  preserved, if at all.
- If the binding report is the S5.1 worklist substitute, add its module/test location explicitly.
  Otherwise unresolved rebinds have no durable or typed place to go before S8.1/S5.2.
@@@@@@

======
Response (code-verified 2026-07-08): **all accepted; §5 expands to:**

- ✓ **`projection.py`** — `ContainerNode`/`LeafNode` gain typed `rebind_anchors`; **`structure_map.py`**
  — `_node_from_json` parses it + `render_structure_map` emits it; **`__init__.py`** export pins for
  the new public rebind types (`RebindContext`/`RebindResult`/`RebindReport`/`RebindError`). (These are
  the edits §1-point-1 forces; I under-listed them.)
- ✓ **`test_structure_map.py`** — inv 13/24 tests updated for the v2 anchor shape: accept the
  `content_fingerprint` sub-object, **still reject** `.geom` / atom-level `present` smuggling
  (`additionalProperties:false` holds) and now reject **malformed fingerprint fields** (bad
  `k`/`token_count`/oversized `shingles`); plus the inv-25 test carve-out (anchors now consumed).
- ✓ **Fixture migration** — every conforming fixture `schema_version: 1→2` (mechanical, fingerprint
  optional); the new differ-fixture populates the fingerprint + births v2; v1-reader coverage is
  **S8.1's** (stated, not faked here).
- ✓ **Report home** — `RebindReport`/`rebind_findings` live in `rebind.py`, tested in `test_rebind.py`;
  named as the pre-S8.1/S5.2 worklist substitute.
======

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

@@@@@@
Adversarial audit:

- DoD item 1 should include "the rebound projection validates globally" and "old canonical matches
  old map lineage." Without those, the happy tier can prove only local matching, not a valid migrated
  map.
- DoD item 3 should be strengthened: active mode recorded in a typed report provenance now, and a
  named S5.2 persist path later. If the final report is not persisted anywhere, it does not fully
  satisfy the tracker phrase "after the fact."
- DoD item 4 should include the v1-to-v2 fixture/update strategy. A schema const bump that simply
  rewrites all fixtures can erase historical coverage; a bump that leaves v1 fixtures untouched can
  break the suite.
- DoD item 6 says "Pushed to origin" and "Issue closed." That is process, not mechanism quality, and
  may not be appropriate if this plan is audited before coding authorization. Consider separating
  implementation DoD from branch-management DoD.
@@@@@@

======
Response (code-verified 2026-07-08): **all accepted; the DoD splits into two sections.**

- ✓ **Item 1 — add the two correctness clauses.** "…re-binds under unchanged geometry **and the
  rebound projection validates globally** (`validate_projection` + `assert_reference_integrity`)
  **and `old_canonical` matches the old map's lineage**." Local matching alone is not a valid
  migration — agreed.
- ✓ **Item 3 — strengthen + name the persist owner.** "active mode **+ source** recorded in the typed
  `RebindReport` provenance now; **S5.2 is the named persist path**." Removes the "after the fact"
  over-claim on an unpersisted object (D-7).
- ✓ **Item 4 — add the fixture strategy.** "…all conforming fixtures bumped `1→2` (mechanical,
  fingerprint optional); v1-reader coverage is S8.1." So the const bump neither erases historical
  coverage silently nor breaks the suite.
- ✓ **Split process from mechanism — accept, good hygiene given plan-before-code.** DoD becomes
  **§6a Mechanism DoD** (items 1–5: the re-bind behavior, re-stamp, modes, schema birth, uncalibrated-
  default rule) — the bar for "the work is correct" — and **§6b Landing DoD** (suite/ruff/hunt/audit
  green; push to `origin/spike` only; issue close + tracker row) — the bar for "it ships." A pre-code
  audit judges §6a; §6b only applies once you authorize coding.
======

---

## §7 What this review changes (revision summary)

Your audit is accepted almost in full — every factual claim verified against the code
(typed-model anchor drop, `normalize_tokens` accent/punct behavior, `region.page` 0-vs-1 mismatch,
the `geometry_mode` absent→conditional-primary fallback). The material reshaping, to fold into a
**plan rev 2** before coding:

1. **Mechanism is whole-map, not per-node** — candidate scoring → global non-overlapping assignment →
   `validate_projection`/reference-integrity over the full rebound map before any bind counts.
2. **A candidate grammar** — page-local contiguous fresh-atom runs within the anchor region, scored
   per owning slot; bounds the search (complexity) and pins reproducibility.
3. **Typed anchors** — `rebind_anchors` modeled on the node dataclasses (+ loader/render/inv-25
   carve-out); `decision` stays inert. Without this, (a) is the schema-only trap.
4. **Region = per-page local checkpoint over own-atoms** (new sub-decision **D-3b**), not descendant
   union, not a whole multi-page extent; `region.page` tightened to `minimum:1`.
5. **Per-slot fingerprint** (leaf=body; container=heading/signature) with a tight schema
   (`algo_id/normalizer_id/k/token_count/sorted-bounded shingles`), short-node fallback, multiplicity
   + `ordered_coverage` in the report.
6. **No threshold rescue by geometry** — geometry/path disambiguate only among ≥τ candidates; named
   high uncalibrated `DEFAULT_FINGERPRINT_THRESHOLD`; exact enum tokens; structural monotone-ordering
   check on defaults.
7. **Typed seam** — `RebindContext` (asserts reference-integrity + baseline-binding at construction),
   `RebindResult` (migrated doc + report + in-memory re-stamps), `RebindReport` (closed reason enum),
   `RebindError`; non-raising `rebind()` + strict `assert_all_bound()`. No evidence writer in S5.1.
8. **Re-stamp is a bottom-up post-pass**; `stale-decision` detected by running the evidence producer
   against the rebound projection, not by watching a digest.
9. **DoD split** into mechanism (§6a) vs landing (§6b); S4.6-gap and synthetic-only test substrate
   stated honestly.

**New rulings I need from you** (surfaced by the audit, beyond the original D-1…D-7):

- **D-3b** — region as per-page own-atoms checkpoint (not descendant union / not whole extent). *Rec:
  yes.*
- **Candidate grammar** — page-local contiguous run, scored per slot. *Rec: yes.*
- **No-rescue posture** — geometry/path never lift a sub-τ fingerprint over τ. *Rec: yes (safest for
  PLL).*
- **Per-slot fingerprint granularity** — leaf=body, container=heading+signature separately. *Rec:
  yes.*
- **Provenance in report vs stored anchor** — surface `matched_witness_id`/engine/method in the
  report rather than widening the stored anchor. *Rec: report (smaller v2 surface); say if you want it
  pinned in the anchor.*

On your sign-off (or edits) to these, I'll issue **plan rev 2** as the ratified spec, then mint the
S5.1 issue and begin red-first.

---

**Decisions needed before I code: D-1 … D-7** (§3) **+ D-3b and the four new rulings** (§7). D-1 is
the keystone (it sets whether we take the pre-accepted schema bump); the rest are mechanism shape.
Everything else I execute as written and report.

@@@@@@
Additional cross-cutting feedback:

- The plan should name the failure carrier. Reusing `EvidenceGateError` for rebind ambiguity would
  pollute an evidence-specific closed kind set; reusing `StructureValidationError` would imply EC
  codes that do not exist. A dedicated `RebindError` plus non-raising `rebind_findings`/report is the
  cleanest S5.1 seam.
- The plan should decide whether rebinding is top-down, bottom-up, or whole-map assignment. The
  current language reads local/per-node, but the data model is a tree with atom-ownership invariants.
  Whole-map validation after candidate selection is non-negotiable.
- The plan should include a complexity note. S4.7 explicitly names re-bind lookup in scale checks;
  storing full shingles and scanning every possible fresh atom window per node can go quadratic fast.
  Even a simple page/path-bounded candidate index would make the intended shape clear.
- The plan should define how fingerprints are produced for machine leaves versus human containers.
  Leaves have body text; containers may have headings/signatures and descendant text. A single
  "node's own content" phrase is not enough to avoid inconsistent anchor semantics.
- The plan should keep "PLL mode is geometry-tie-break" separate from the generic mechanism. Tests
  need all three modes with synthetic fixtures; PLL-specific assertions should be a fixture or probe,
  not assumptions in core code.
@@@@@@

======
Response (code-verified 2026-07-08): **all five accepted; these set the mechanism's spine.**

- ✓ **Failure carrier = dedicated `RebindError` + non-raising `rebind_findings`/`RebindReport`.**
  Confirmed the pollution risk: `EvidenceGateError` validates against the closed
  `EVIDENCE_FINDING_KINDS` (evidence.py:639/661 — a foreign kind raises), and
  `StructureValidationError` carries `EC.*` codes from the closed structure-map vocab — reusing either
  would smuggle rebind reasons into a set that rejects them. So a **new `RebindError`** (its own
  closed reason enum) + non-raising `rebind_findings`. Folded into D-6/§7.
- ✓ **Bottom-up / whole-map — accept, non-negotiable, already promoted.** The mechanism is
  candidate-select → **whole-map assignment** → validate → **bottom-up re-stamp**. The per-node
  reading is gone. (§1 point 3 + §4 global-consistency invariant.)
- ✓ **Complexity note — accept.** «unverified: that S4.7 names re-bind lookup in the scale checks —
  plausible from the D35 scale posture, but I have not opened the S4.7 row this session; I'll confirm
  the exact wording when I cite it in rev 2.» Regardless, the concern stands on its own: full-shingle
  storage + an all-windows scan per node is quadratic. The **page-local candidate grammar bounds the
  search** (candidates live within the anchor region's page(s)), and the plan will carry an explicit
  complexity note + a page/path-bounded candidate index. Folded into §1 + §7 item 2.
- ✓ **Leaf vs container fingerprints — accept, this resolves the "own content" ambiguity.**
  **Per-slot, own-atoms only:** a **leaf** fingerprints its `body_atoms`; a **container** fingerprints
  its `heading_atoms` and `signature_atoms` **separately**, and **never descendant text** (descendants
  carry their own fingerprints — folding their text in would double-count and make the container span
  the subtree). Matches the own-atoms region (D-3b). Folded into D-2/§7 item 5.
- ✓ **PLL mode kept out of core — accept.** `rebind.py` is mode-agnostic (rules on the mode string +
  policy object passed in — keeps the S0.2 neutrality scan clean). **All three modes are tested on
  synthetic fixtures**; the `geometry-tie-break`-for-PLL assertion lives in a **PLL fixture/probe**,
  never a literal in core. Folded into §4 + §5.
======
