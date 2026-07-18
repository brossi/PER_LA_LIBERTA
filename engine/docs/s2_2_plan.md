# S2.2 — geometry property tests + the binding S2.0 RE-GATE (plan)

**Status: DRAFT for review (2026-07-07).** Not ratified; no code, no manifest change, no mode
landing until this is signed off. Parent issue **#30** (blocked-by #29, S2.1 — substantively done:
#35–#40 all closed, milestone S2.1 DONE; #29 is an administrative-close loose end, not a build
blocker). Tracker row `S2.2` in `ENGINE_STRUCTURE_TASKS.md` (~L527) is the authoritative spec — on
any disagreement the tracker wins, then `ENGINE_STRUCTURE_PLAN.md` (§9, §3.0, §3.4, D30), then this
plan. Evidence anchor: `spike/document-structure`, commit `6ff4419`; file:line cites verified on
disk 2026-07-07; the re-gate numbers are read from the frozen `docs/probes/s2_1_run_stats.json`
(`order_qa` block).

Inputs this plan consolidates:

- `docs/probes/s2_0_geometry_alignment.md` — the S2.0 GATE verdict: S5 geometry mode =
  **conditional-primary, re-gated at S2.2 on the as-built detector, on mean + per-page pass-rate**
  (§Verdict (b); §"Implications for downstream → S5"). The pre-registered thresholds:
  **ordered coverage ≥0.85 → primary; 0.50–0.85 → tie-break; <0.50 → no-geometry**, applied as
  **mean AND pass@0.85**, not a median (§Method; audit Finding A).
- `docs/probes/s2_1_run_report.md` §"order_qa — the S2.2 (#30) measurement feed" + the persisted
  `order_qa` block in `s2_1_run_stats.json` — the as-built numbers (below).
- `ENGINE_STRUCTURE_PLAN.md` §9 (test strategy: red-first, adversarial-audit gate, the re-binding /
  reference-integrity tiers) and §3.4/D30/D33 (geom is the primary re-bind signal; unmatched box is
  unusable for primary re-bind; `geom.present=false` never invented).
- The three S5 operating modes named in the tracker's S5.1 row: **`geometry-primary` |
  `geometry-tie-break` | `no-geometry`**, "selected by S2.0's outcome and recorded in the
  structure-map lineage / rebind config (M2)."

---

## §0 The two halves of #30

The done-when has two independent deliverables:

- **Half A — four geometry property tests** (`BUILD`), binding against the as-built S2.1 backend.
- **Half B — the binding S2.0 RE-GATE** (`GATE`): measure the as-built detector on mean +
  per-page pass-rate over an n≥30 breadth sample, and **confirm `geometry-primary` or demote**,
  recorded in lineage.

Half B's *machinery* is deliberately thin: #40 pre-built the feed so #30 is "a ruling over
persisted numbers, not new machinery" (runner comment, `run_s2_1_slice1.py:525`). The weight of
Half B is not code — it is the **ruling** and **where the resulting mode is durably recorded**.
That is where the three open decisions live (§3).

---

## §1 Half A — the four property tests

The done-when names four properties. Each is mapped below to **what already exists** (so we don't
re-assert green under a new name — `feedback_no_cheating_results`) and **the genuine gap** S2.2
closes. Net-new tests land in a dedicated `tests/unit/test_geom_properties.py` with an
`Invariants (proven red below)` docstring block (§9 red-first); each cites the mutant that turns it
red.

**P1 — boxes within page bounds.**
- *Existing:* `test_geometry_backend.py` proves `WordBox` rejects non-finite / degenerate / unordered
  coords and `PageGeometry` rejects non-positive page/width/height (construction-level).
- *S2.0 caveat (Finding 2):* "in-bounds is a smoke test, not anchorability" — boxes are in-bounds
  **by construction**, so a bare in-bounds assertion carries no signal.
- *Gap → S2.2:* a **binding, real-page** property over the as-built backend's actual output: for a
  real PLL page's `PageGeometry`, **every** `WordBox` satisfies `0 ≤ x0 < x1 ≤ width` and
  `0 ≤ y0 < y1 ≤ height`. Red control: inject one out-of-bounds box → the property fails loud (not
  silently clamped). This is the property form of the existing `oob_boxes` stat, asserted rather
  than reported.

**P2 — source-order ↔ geometric-order coherence on a real page.**
- *Existing:* `test_geometry_e2e.py` proves the **no-witness** branch on a **synthetic** two-column
  page (`reading_order` + `ordered_coverage == 1.0`), with the naive-full-width control < 1.0.
- *Gap → S2.2:* the done-when says **"on a real page."** Net-new: take a real PLL two-column body
  page, source order = the column-ordered witness window, geometric order = `reading_order` over the
  as-built boxes at the detected `split_x`; assert `ordered_coverage ≥ τ` on that page and that the
  **naive (split_x=None)** order scores strictly lower (the control that gives the pin teeth). τ is a
  per-page floor for a *confident two-column body page* (candidate: the S2.0 two-column body regime,
  ≥0.85), **not** the book-wide re-gate bar — this is a coherence property on a known-good page, and
  its point is that the mechanism recovers column order, distinct from Half B's breadth ruling.

**P3 — primary-witness box on canonical atoms where matched.**
- *Existing:* `test_geom_match.py` proves matched geom carries all four provenance fields verbatim
  (`geometry_engine/matched_witness_id/match_method/match_confidence`), scan-page numbers (not
  indices) flow through, confidence is `matched/total` by value, and a zero-match atom writes absent.
- *Gap → S2.2:* the **canonical-projection** framing (D30, PLAN §3.4): a **canonical** atom carries
  its **primary witness's** box **where matched**, and multi-primary is never unioned/picked (G-20).
  This is largely covered; S2.2 adds the property as a named, real-data assertion if a clean gap
  exists after reading the matcher tests closely — otherwise it is **cited as already-binding** in
  the plan and the run report, not duplicated. (Flagging honestly: this may reduce to a citation,
  not net-new code. I will confirm on the read and report which.)

**P4 — absent/unmatched geom is representable and excluded from primary re-bind.**
- *Existing:* `test_geom_match.py` (zero-match → absent, never an invented box) +
  `test_geom_sidecar.py` (routed page atoms stay PENDING, declined surfaces at attach; absent ≠
  pending). Representability is proven.
- *The honest limit:* **"excluded from primary re-bind" cannot be fully proven at S2.2 — re-bind is
  S5 (`rebind_anchors`), which is TODO.** What S2.2 *can* bind is the **contract marker** S5 will
  key on: an unmatched/absent atom is representable (`geom.present=false`, no `match_confidence`) and
  **carries no primary-bind-eligible geometry** — i.e. the data shape makes a primary re-bind on it
  unconstructible. The property asserts the marker + its exclusion-eligibility; a comment + the
  tracker record that the **operational** exclusion is re-proven at S5.5 (the re-binding tier in §9).
  I will **not** dress a representability test as a re-bind test (that would be the single-fixture
  blind-spot / cheating-results trap).

**Half-A deliverable:** `test_geom_properties.py` with P1, P2, and P4 as net-new binding properties
(each red-proven), P3 either net-new or cited-as-covered per the read, plus a one-line map in the
run report of property → assertion → red-input. No production code changes are expected for Half A
(the backend + matcher exist); if a property cannot be asserted without a backend change, that is a
finding I surface, not a silent patch.

---

## §2 Half B — the re-gate ruling (the persisted numbers)

The re-gate metric is already computed and frozen in `s2_1_run_stats.json` → `order_qa`:

| quantity | value | bar | verdict |
|---|---|---|---|
| n (matched pages measured) | **253** | ≥30 | ✓ breadth |
| mean order_qa | **0.8417** | ≥0.85 | ✗ below |
| pass@0.85 (per-page pass-rate) | **0.7786** | ≥0.85 | ✗ below |
| median (context only, **not** the bar) | 0.908 | — | — |

Both binding quantities fail the primary bar. The pre-registered bands place the **mean 0.842 in
[0.50, 0.85) → the tie-break band**. The histogram shows the drag is a specific tail, not uniform
weakness: **148 pages at ≥0.9** and a hard **32-page cluster at ~0.4** (single-column / edge /
TOC / chapter-end pages where the column-aware order disagrees with the witness) — exactly the
"single-column edge pages drag the mean" pattern S2.0 predicted (all-pages 0.851 / 73% there;
0.842 / 77.9% here on the as-built detector). The median (0.908) would *hide* this — which is why
S2.0's audit pre-registered mean + pass-rate, not median.

**Mechanical verdict: DEMOTE. Target mode: `geometry-tie-break`.** Rationale: the geometry is not
noise (mean 0.84, 148/253 pages primary-grade), so `no-geometry` would throw away real signal; it
is simply not book-wide primary-grade, so `geometry-primary` is unsupported. Tie-break is the
band the number lands in and the honest description: **geometry is a corroborating / cross-check
signal, primary only on the confident two-column pages where the S2.1 matcher is confident;
content + structural-path lead elsewhere.** This is precisely S2.0's "conditional-primary" made
binding by the as-built numbers.

Note this is **consistent with S5.1's own design**: the tracker's S5.1 row already says the
geometric detector "is the primary order source only on the no-witness branch," and "when a
column-correct text witness exists it supplies reading order and geometry cross-checks." PLL *has*
column-correct witnesses (copy1 at 0.98), so `order_source = witness` (already in the manifest) and
geometry-as-tie-break is the coherent end state, not a disappointment.

---

## §3 The three open decisions (for your inline audit)

These are consequential and unresolved by the docs. My recommendation follows each; please rule
inline (@@@@@@ / ======).

### D-A — Where is the demoted mode durably recorded?

The spec says "recorded in the structure-map lineage / rebind config (M2)." **Neither exists for
this purpose:** `lineage.py` is S3.0 *resource/normalizer* lineage (not a rebind-mode field); the
rebind config is S5 (`rebind_anchors`), TODO; `structure_map.py` is a per-build persisted layer, not
a book-policy home. So "record in lineage" has no current home and must be decided.

- **Options.** (a) Land `manifest.segmentation.geometry_mode: "geometry-tie-break"` — the durable,
  book-level, book-tunable home that already holds `order_source`, the density bands, and the
  ratified DT-7 column policy; S5.1 reads it from the manifest when built. (b) Emit only a gate
  artifact (`docs/probes/s2_2_regate.md` + a `geometry_regate` block in the run stats) and **defer**
  the manifest/lineage landing to S5 when the field has a consumer. (c) Both: artifact now +
  manifest field now.
- **Recommendation: (c).** The manifest is where segmentation policy already lives and is exactly
  parallel to how DT-7's column policy was landed (a ratified value in `manifest.segmentation`); the
  probe doc is the auditable evidence trail. This makes the mode a first-class, greppable book fact
  the moment S5.1 exists, and matches "recorded in lineage" in spirit (the manifest is the book's
  durable policy record). The structure-map-lineage wording is aspirational for a layer that isn't
  built; I read the manifest as its current stand-in and would note that in the S5.1 row.

### D-B — Do I land the mode mechanically, or measure-and-hand-it-to-you-to-ratify?

The thresholds are **pre-registered** (you ratified them at S2.0), so the verdict DEMOTE→tie-break
is a *mechanical consequence*, not a fresh discretionary ruling — an argument that I may land it.
**Against:** landing an operating-mode value into the book manifest is exactly the class of
consequential lineage record that DT-7 shows you ratify **personally** (tooling proposes; you
freeze the manifest value), and `feedback_no_fabricated_provenance` forbids me stamping a
ratification in your name.

- **Recommendation:** I **build the machinery + run it + produce the verdict artifact**
  (DEMOTE→tie-break, with the numbers and the pre-registered rule shown), and the property tests —
  all mechanical and audited. The **manifest landing of `geometry_mode` I leave for your
  ratification** (your name, real date), exactly as DT-7. The tracker row goes `DONE` when the
  machinery + tests are in and the artifact is produced; the manifest value lands under your
  ratification in the same or a follow-up commit, your call. This keeps the mechanical work moving
  without me self-stamping a book-policy ruling. If you'd rather I treat the pre-registered rule as
  standing authorization and land the manifest value directly (citing the S2.0 pre-registration as
  the ratifying act), say so and I will.

### D-C — Demotion target: `geometry-tie-break` vs `no-geometry`?

The spec frames the verdict binary ("confirm `geometry-primary` or demote the mode") without naming
the demotion target. The pre-registered bands make it unambiguous: **mean 0.842 ∈ [0.50, 0.85) →
tie-break.** `no-geometry` is the <0.50 band and would discard 148 primary-grade pages of real
signal.

- **Recommendation: `geometry-tie-break`.** Flagging only because the done-when's binary phrasing
  doesn't say it outright; the bands + the histogram + S2.0's "conditional-primary" all converge on
  tie-break. If you read "demote" as all-the-way to `no-geometry`, that's a one-word change to the
  landed value — but I'd argue against it on the evidence.

---

## §4 Red-first invariants, mutation, audit (the method, §9 + D36)

- **Half A:** each property has a **named red input** (P1: an injected OOB box; P2: `split_x=None`
  naive control scoring strictly lower + a shuffled-order control; P4: a present-box mutant that
  would let an absent atom look bind-eligible). TDD/planted-violation controls, no throwaway probes.
- **Half B:** the ruling logic (read `order_qa` → apply `mean≥0.85 AND pass@0.85≥0.85` → emit
  mode) is a pure function with red controls: a mutant that rules on **median** (0.908) instead of
  mean+pass-rate must flip the verdict to a wrong PASS (this is the exact S2.0-audit failure the
  rule exists to prevent — a high-value regression test); a mutant that uses **OR** instead of
  **AND** must not change the (already-failing) verdict but must be caught by a fixture where only
  one bar is met; a mutant that mis-bands 0.842 into `no-geometry` must fail. The band function is
  value-pinned at the three boundaries (0.50, 0.85).
- **Mutation hunt** at green (`PYTHONDONTWRITEBYTECODE=1`, purge `__pycache__` per
  `feedback_mutation_pyc_staleness`); **wide+narrow adversarial audit** pre-commit; **Rule-A**
  re-audit of any behavior-changing remediation to a fixpoint (D36).

## §5 What lands where

- `tests/unit/test_geom_properties.py` — Half A (net-new).
- A small pure ruling module for Half B — **candidate** `structure/geom_regate.py`
  (`regate_verdict(order_qa_block) -> {mode, mean, pass_at, bars, passed}`) — engine-neutral (reads
  numbers, carries no book/language literal; the S0.2 neutrality scan globs `structure/`). *Open:*
  whether this is worth a module vs a function on the runner — I lean module (it's the binding
  gate logic, and it wants its own red tests). Flag if you disagree.
- `docs/probes/s2_2_regate.md` — the gate artifact (numbers, rule, verdict, the tail analysis).
- `books/per_la_liberta/manifest.json` — `segmentation.geometry_mode` **(only under D-B ratification)**.
- `docs/ENGINE_STRUCTURE_TASKS.md` (S2.2 → DONE row + S5.1 note that the manifest is the mode's
  current lineage home), `docs/probes/s2_1_run_report.md` (a #30 section), memory.
- Issue #30 close: evidence comment + tracker row in the same commit.

## §6 Definition of Done

1. Four property assertions (P1–P4) hold, each red-proven; P3 net-new or cited-as-covered per the
   read (reported either way).
2. The re-gate measures the **as-built** detector on **mean + per-page pass-rate** (n=253 ≥ 30) and
   emits **DEMOTE → `geometry-tie-break`**, with the artifact.
3. The S5 mode is recorded per D-A/D-B (manifest field under your ratification, + probe doc).
4. Suite green, ruff clean, mutation hunt kills all, adversarial audit + Rule-A fixpoint clean.
5. #30 closed with evidence; tracker `S2.2` → DONE; run report + memory updated. Pushed to
   `origin/spike/document-structure` only (deploy-hold on main/Pages untouched).

---

**Decisions needed before I code: D-A, D-B, D-C** (§3). Everything else I'll execute as written and
report.
