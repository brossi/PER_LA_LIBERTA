# Runway to "engine-ready" — informal sequencing proposal (post-S4 keystone)

Status: **INFORMAL, for review — not a sign-off sheet.** Drafted 2026-07-02 at the S4 keystone
close, at the user's request: how I would order the remaining work, which items are worth pulling
*out of* strict wave order, and what work is **not yet on any tracker row** but stands between here
and "ready." `ENGINE_STRUCTURE_TASKS.md` remains the authoritative task list and DoD; nothing here
re-argues a ratified decision. Audit convention available as usual (`@@@@@@` / `======`) if you
want to work through it inline.

---

## 1. Where we stand (verified against the tracker + suite, 2026-07-02)

- **DONE:** S0 (scaffolding), S1 entire (atoms → capture → typed → round-trip gate → store),
  S2.0 (geometry probe GATE — conditional geometry-primary, re-gate at S2.1), S3.0 (resource +
  normalizer lineage), **S4.0–S4.5 (the keystone; D18 gate green, schema v1 born)**.
- **OPEN:** S2.1/S2.2 (geometry backend + property tests), S3.1/S3.2 (space reconstruction),
  S4.6a/S4.6/S4.7, S5–S11 (S7.2b `BLOCK` on v2-EN; S7.3b `DEFER`).
- Suite 855 green; branch `spike/document-structure` several commits ahead of origin, unpushed.
- Standing S5-planning inputs from the keystone close: **BR-022** (region coordinate space),
  **fingerprint-first re-bind posture**, the **store-backed reader glue**, S2.1 sequencing.

## 2. Proposed order

The waves (W2→W6) stay the skeleton; the deviations worth making are inside W2/W3, where three
small unlisted items sit on the S4.6 critical path, and one W3 item (S2.1) pays for itself
everywhere if pulled to the front.

**Lane 0 — housekeeping (immediately, cheap).**
Push the branch (user-authorized). Issue hygiene: mint W2-remainder issues (S2.1, S2.2, S4.6a,
S4.7); decide mint-and-close-for-the-record vs skip for the already-done S4.0–S4.5 (my lean:
skip — the tracker rows + commits are the record); #20 (S9.2a) stays open for W4. Rule on the
pre-existing ruff trio (`steps/cleanup.py` E731, `tests/_idempotency_driver.py` E741,
`tests/unit/test_reconcile_engine.py` F401): fix in one sweep or codify as accepted debt — either
is fine, undecided is not.

**Lane 1 — S2.1 → S2.2, pulled to the front of everything else.**
Three consumers are waiting on its *as-built output*, not just its completion: (a) **BR-022** —
the region coordinate space should be pinned to whatever the real matcher emits, and S5 planning
is blocked on that; (b) **S3.1** — space/fragment reconstruction leans on word geometry (D30);
(c) **S5.1's mode re-gate** is explicitly defined against the as-built S2.1 detector. S2.1-alt
only if S2.0's conditional ruling collapses in practice. Everything in Lane 2 can proceed in
parallel — it doesn't consume geometry.

**Lane 2 — the S4.6 runway (mostly small, mostly unlisted — see §3).**
Order within the lane:
1. **Freeze the PLL atom store** (§3 item 1): capture the real copies through the live producers,
   persist via the S1.5 store into the PLL workspace, record the stream hashes. This is the
   id-stability substrate S4.6 authoring references — do it *before* any map references atom ids.
2. **Store-backed reader glue** (§3 item 2): workspace → `load_stream`× → `StreamAtomReader`,
   composing `assert_reference_integrity` on the way in. Small; homed at S4.6a.
3. **S4.6a** — the authoring-evidence sidecar engine half (already a tracker row, owner: engine).
4. **S4.6 authoring tooling** (§3 item 3), then **S4.6 itself — Ben authors the PLL map**.
   BR-022 guard applies: `rebind_anchors` stays absent in authored maps until S5 planning pins
   the space.

**Lane 3 — S5 planning, opened as soon as S2.1's coordinate output exists.**
Fixed agenda from the keystone close: BR-022 (space + witness discriminator — and whether the
answer needs the known schema-bump → re-birth); the **no-geometry/content-fingerprint mode as the
expected initial mode for PLL** (every canonical atom is `Geom.absent()` until S2.1 populates
matched boxes, and only *matched* boxes qualify even after); S5.2's labeled truth set +
regen-guard registration. S5 *build* follows S4.6 (it needs a real map to re-bind).

**Lane 4 — S3.1/S3.2, parallel with Lane 2/3 after S2.1 lands.**
Concern-A work with no dependency on the B lanes. The corruption-guard regression set (S3.2,
drawn from the live cleanup post-mortem) is the gate; treat S3.1's segmenter as a
proposal-generator, oracle-gated, per its row.

**Lane 5 — S8.1 governance loader, before real supersede traffic exists.**
Its scope now includes the writer's crash-state recovery (idempotent re-supersede when snapshot
bytes == live bytes; s4_plan §0.3 A-4). Land it before S4.6's map starts accumulating revisions —
the first real supersede should already have its recovery path.

**Lane 6 — W4 as planned: S5 build → S6 → S7 → S9.**
Notes per milestone: **S6.1** is the natural **schema-bump rehearsal** (§3 item 5) — it adds
role/authorship with a version bump, which re-enters `provisional` and re-runs the birth gate;
budget that drill explicitly. **S7.1b** (legacy flags → SpanRef + canonical page attribution) is
what makes `region.page` meaningful for canonical atoms — schedule it before S5's re-bind
calibration leans on pages. S7.2b stays `BLOCK` on v2-EN. **S9**: S9.1 profile → S9.2a (#20,
move-only) → S9.2b binding → S9.3 seam → **S9.4** drives the differ book end-to-end — its raw
sources + live-bound streams already exist (first step done at the keystone close); S9.1 must
include the differ book's structure profile so S9.4 has one.

**Lane 7 — W5: S8.2/S8.3, then S10 integration.**
S10 is where this tracker **federates with the non-structure engine work** (§3 item 4): the
adapter (S10.1), consumer migration triage-first (S10.2), the F2 validator replacement (S10.3),
and the F3 identity rework with the PLL golden (S10.4). The paused step ports (cleanup's engine
port, M4c translate/typeset) must be resolved before or during this lane — they are consumers of
exactly the artifacts S10 migrates.

**Lane 8 — W6: S11.0 → S11.1/S11.2.**
S11.0 (pre-translation whole-book smoke + human ack) is the last gate before M4c consumes the v2
Italian — it binds this tracker back to the live-edition program (the deploy-hold world).

## 3. Unlisted work flagged (needed before "ready", currently on no row)

1. ~~**Freeze + persist the PLL atom streams (new; proposed as an S4.6 predecessor task).**~~
   **DONE 2026-07-02** as S4.6-pre (#31, `83d7a7c`): streams captured through the live producers,
   persisted via the S1.5 store, pinned by the committed `stream_freeze.json` +
   `assert_freeze_matches` tripwire.
2. ~~**Store-backed reader glue (new; fold into S4.6a).**~~ **DONE 2026-07-02** as part of S4.6a
   (#32, `ebd7f11`): `load_workspace_streams` / `workspace_reader` in
   `structure/atom_store.py`/`structure_map.py`, with `assert_reference_integrity` composed on
   load.
3. ~~**S4.6 authoring-loop tooling (under-specified on the row).**~~ **DONE 2026-07-03** as
   S4.6b (#34; plan `s4_6_tooling_plan.md`, RATIFIED): `structure/authoring/` ships the composite
   gate, validate-on-save (`--watch`), the worklist status listing, the single-node stamp
   (DT-6), and the digest-diff explainer — exact diffs always, via DT-4 payload witnesses
   persisted in the sidecar (schema amended inside the free-edit window). Book side:
   `books/per_la_liberta/seed_structure_map.py` seeded the draft (120 nodes / 61 containers /
   56 chapters, full 4,786-atom coverage, 22 review flags); the gate reds all-`missing` — the
   S4.6 worklist is live.
4. **Branch/program reconciliation (outside this tracker, gating "ready").** The spike carries
   `engine-framework`'s history, and that branch's remaining port work (M4b cleanup step —
   mid-port, not written; M4c translate/typeset) lives in `ENGINE_M4b_PLAN.md`, not here. "Engine
   rebuilds PLL v2" needs both trackers to converge — propose deciding the merge/continuation
   strategy at the start of Lane 7 (S10 is where they structurally meet), or earlier if the spike
   is to become the mainline.
5. **Schema-bump rehearsal (fold into S6 planning).** The provisional→born re-birth path is
   designed and tested in the small, but a real version bump (migrating fixtures, refreshing the
   version-derived conforming fixture, re-running the birth gate on the differ book) has never
   been walked end-to-end. S6.1's additive bump is the drill; plan it as one, not as incidental.
6. **Mutation-harness institutionalization (optional infra, standing question from W0).** The
   B-7-style hunts are session scripts; the discipline is codified but the tooling is not. Either
   commit a reusable hunt harness (a parametrized patch→test→revert runner under `tools/`) or
   explicitly rule session-scripts sufficient. Links the deferred mutmut spike.
7. **The v2-EN chain (external gate).** S7.2b (`BLOCK`), S11.0's human-ack, and the parent repo's
   deploy-hold form one dependency chain the engine can't close alone; "ready" claims should say
   "ready pending v2 Italian input" until M4c runs.

## 4. What "ready" means (proposed reading of the DoD)

Three concentric claims, matching the tracker's two-axis rollup plus the program reality:

- **Substrate-ready:** S0–S9 substrate-tier DONE — in particular S8.3's negative battery and
  **S9.4** (the differ book driven from raw under an Italian-free core) both green. The engine's
  *thesis* is proven here.
- **PLL-instance-ready:** S4.6 map authored + evidenced; S10.4's rendered-handle golden green;
  S11.0's whole-book smoke human-acked. The engine demonstrably reproduces its first book.
- **Program-ready:** the v2 pipeline actually consumes it (M4c + the deploy-hold lifts) — outside
  this tracker, listed so "ready" is never quietly overclaimed.
