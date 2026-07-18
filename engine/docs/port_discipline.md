# Engine Port Discipline — Validation Tiers & Change Governance

> Canonical governance for porting the live *Per la Libertà!* pipeline into the engine. It
> governs **every** milestone. Per-milestone plans (`ENGINE_M3_PLAN.md`, …) *apply* this; they
> do not restate it. `ENGINE_FRAMEWORK_PLAN.md` embodies it; **this file is the authority where
> they differ.**

## Why this exists

The engine is a forward fork of an organically-grown, single-book pipeline. Two goals pull
against each other:

1. **Parity** — reach the live tool's output and don't regress.
2. **A better seed** — become a well-designed, extensible base for future books, rather than
   faithfully enshrining accidental cruft (the live pipeline was never examined for whether
   each step is decomposed the right way).

Byte-for-byte reproduction serves (1); progressive refactor serves (2). This document is how we
hold both at once without *railroading* — committing down one path that silently forecloses a
useful alternative.

## Terminology — "contract" carries three meanings; keep them apart

- **property** — an invariant test (the §1 *contract/property tier*).
- **step contract** — a step's on-disk output shape consumed by the next step (a one-way door,
  §4). When this doc says "contract" unqualified, it means this.
- **sidecar schema** — the versioned JSON schema of a sidecar file (`ENGINE_FRAMEWORK_PLAN.md`).

## 1. Validation is three tiers + one cross-cutting invariant

Golden tests prove **equivalence**, which is necessary for a faithful port but silent on
correctness and generalization — the reasons the engine exists. So validation is three tiers:

- **Equivalence (golden).** Engine step == live code on a frozen input, byte-exact vs. a
  *freshly generated* reference (§5 — never the drifted live artifact). The regression net.
  *Deterministic, no-LLM, no-network steps only.*
- **Contract / property.** Invariants true for *any* valid input, not one frozen trajectory
  (e.g. reconcile: kept-paragraph count ≤ Σ inputs; every flag carries both witnesses; ids
  unique + sequential-per-part; output is a valid `validate` input). Specifications that survive
  input change and port to a second book.
- **Separability.** Swap the config → correspondingly different behavior; no PLL strings leak;
  the synthetic non-PLL book runs. Proves the config seam — the engine's actual thesis.

**Isolation** is a **cross-cutting invariant, not a tier:** every step, deterministic or not,
must write only inside its `BookWorkspace` and leave the protected live roots untouched. It
always applies.

**Required, not merely "leading."** For a step that *can* support a tier, that tier is
**required** — a step is **not done on equivalence alone.** Deterministic steps require
equivalence + property + separability + isolation; non-deterministic steps (no equivalence
possible) require property + separability + isolation. "Lead with the tier that proves the most"
governs emphasis and ordering, never *whether the others exist*. Each milestone plan declares
its required tiers explicitly.

**Green equivalence ≠ correct.** A green golden means "matches PLL," PLL's bugs included.
Correctness is the property tier's job; generalization is separability's. Equivalence is a
regression net, not a correctness certificate — never report a green golden as "validated."

## 2. Where a change is allowed — gate by *regime*, not by *label*

A change is governed by **what it can break**, decided by an operational test — not by which
"level" you choose to call it (labels can be relabelled; this gate cannot):

- **Within a step → gate on the golden.** If a change keeps the step's equivalence golden green,
  it is structure / architecture — **redesign freely** (the green golden *is* the proof it
  changed no behavior). If it would change the golden, it is behavioral — either an unintended
  regression (**revert/fix**) or a **deliberate divergence** (§5 ledger entry + re-baseline).
- **Across steps → one-way door, gate on a recorded decision.** Changes to the step inventory,
  which artifacts exist, or a *step contract* are not caught by any single golden (merging a
  step makes its artifact *cease to exist* — nothing turns red). These are one-way doors (§4):
  decided on the record in the branch register, never silently.

**Hold equivalence unless ground truth licenses the change.** Within-step behavioral change is
held to equivalence **unless an external ground truth licenses a specific change** — the source
scans (vision re-read), the period-dictionary oracle, the review-phase findings. (A *second
book* tests generalization, not PLL-correctness: it is a different text and cannot tell you a
heuristic chose right *for PLL*. The oracle is the scans, not another book.) Absent ground
truth, an "improvement" is an unverifiable guess — hold equivalence. With ground truth, change
it, as a logged divergence.

## 3. Sequencing — golden-gated from first green

Establish the equivalence baseline **as soon as the step compiles in the engine.** There is no
verbatim-copy stage in a forward fork — the minimal port already embeds architecture changes
(it cannot import top-level `utils`). From first green, every change is golden-gated (§2).
Reproduce to *understand* and to *gate*, not as the deliverable; "generalizes" and "correct, not
just unchanged" are in the definition of done too.

**Non-deterministic steps** (cleanup / translate / multi_translate / refine — no golden
possible) have no equivalence baseline. Their floor is **step-contract conformance + manual
smoke on the synthetic fixture**, and improvements there are judged by the property tier, not by
reproduction.

## 4. One-way vs. two-way doors

- **Two-way** (cheap to reverse: algorithm internals behind a function, fixture layout, a
  constant's home, file names) → **pick one and move.** Deliberating is waste.
- **One-way** (expensive once depended on: a **step contract**, the **plugin method surface**,
  the **step inventory**, the **config schema shape**) → **pause, lay out the alternatives,
  decide on the record.** A one-way-door decision **is a branch-register entry** (§5): the path
  taken, the alternatives rejected, and the revisit condition.

The skill is not keeping every branch open — optionality has a carrying cost (every "keep it
open" is indirection / a version field / a pluggable seam, the same speculative generality we
resist). It is *recognizing which doors only open once*, slowing down only for those, and
engineering one-way doors into two-way ones where cheap (versioned additive contracts; a minimal
plugin surface; constants whose home isn't baked until a second book pulls them).

## 5. Two registers

**Location & form.** `engine/docs/decisions/`, append-only Markdown — the lightest format that
carries the fields below (a short dated heading + bullets), kept deliberately trivial so it is
actually used. Owner: whoever makes the change, at the moment of the decision/divergence.

**Birth times differ.** The **branch register exists now** — planning already generates forks
(the deferrals below seed it). The **divergence ledger** opens at the first behavioral
divergence (expected during M3 porting); until then it carries only its format header.

- **Divergence ledger** (`divergence_ledger.md`) — every *deliberate behavioral change*: what
  PLL did, what we now do, *why it is better* (and the ground truth that licenses it, §2), the
  property test that proves the new behavior, and the re-baselined golden.
- **Branch register** (`branch_register.md`) — every fork *seen and not taken* (and every
  one-way-door decision): the alternative, why passed *now*, and the revisit condition.

**Enforcement (teeth).** Any change to a `*_expected` golden fixture **must cite** a divergence
ledger entry **or** a refresh entry (below). Review-enforced now; automating the check is itself
a deferred branch (BR-003) — building it before a re-baseline workflow exists would be
speculative. This rule is the guard against the cheapest cheat: silently re-baselining a golden
to make a test pass.

**Read obligation.** Before starting, each milestone **consults the branch register** for entries
whose revisit condition it satisfies. A write-only register is a graveyard; the read step is what
makes "deferred, not lost" true.

**Two kinds of golden re-baseline — distinct categories** (conflating them breaks the teeth rule):
- **Input refresh** — the frozen `books/<id>/inputs/` are re-frozen from the evolving live tree
  (e.g. new deviation-review fixes land in `italian_clean.md`). Output changes; behavior does
  not. Logged as a *refresh* (date + source commit), **not** a divergence.
- **Behavioral divergence** — the engine deliberately does something different. Logged in the
  divergence ledger.

## 6. The second fixture pulls generalization — and its current limit

Do not *push* speculative abstraction toward imagined future books. Let the synthetic non-PLL
fixture — and eventually a real second title — *pull* each generalization into existence. A seam
justified by "the second book forced it" is real; one justified by "this feels cleaner" is a
guess.

**Known limit (do not overclaim).** The present synthetic book is **Italian** (it reuses the
Italian profiles). It pulls *structural* injection (different chapter count) but **not language
generalization** — the language-axis seams (`word_score_accents`, the consonant alphabet, the
period dictionaries) remain born-untested for any non-Italian text. A non-Italian fixture is
deliberately deferred (BR-002): built now it would not know which seams to differ on; built after
the language-config-consuming steps are ported, it can be built to *differ where it matters*.

## How each milestone plan applies this

A per-step plan: (a) **declares its required tiers** (§1) and leads with the dominant one;
(b) names its one-way doors and records each decision in the branch register; (c) logs behavioral
divergences in the ledger (with the §2 ground-truth justification); (d) **first consults the
branch register** for entries this milestone unblocks; (e) holds the isolation invariant. It does
not re-argue the discipline.
