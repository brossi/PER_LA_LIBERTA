# Specimen vertical-slice plan

**Status:** execution draft
**Date:** 2026-07-12
**Purpose:** falsify the engine's central premises on real books before adding more substrate.

## Questions

1. Can one real book traverse structure -> adapter -> existing consumer without lost, duplicated, or reordered content?
2. Can a simple non-PLL book use the same path through profile/recognizer knowledge rather than core special-casing?
3. Can stable identity survive a real edition change with zero silent false binds?
4. Is human correction understandable and proportionate to the result?

## Scope

One disposable, offline vertical harness; three specimens in order:

1. **PLL** - frozen atom streams + seeded map -> read-only legacy adapter -> validate/deterministic consumer.
2. **The Kybalion** - raw text -> recognition -> atoms/map -> the same adapter/consumer path.
3. **Darwin 1859 -> 1872** - the same structural path plus re-bind against the real inserted/renumbered edition.

Not in scope: translation, typesetting, live-edition writes, provider calls, the full specimen corpus, productionizing every block type, or completing S6-S10 first.

## Harness

Provide one command that:

- creates fresh disposable workspaces;
- runs all three specimens serially;
- uses no prior caches or generated state;
- writes a machine-readable result and a short human report per specimen;
- returns nonzero on any failed invariant;
- can rerun the complete sequence from zero.

Do not use `engine --step all` for this probe. Exercise the required functions directly until the orchestrator is fail-fast.

## Pass conditions

### PLL

- Every included canonical atom is consumed exactly once.
- Adapter traversal is monotonically ordered; sibling subtrees do not cross.
- No unexplained text loss, duplication, or reordering against the frozen/legacy oracle.
- Unknown block classes reject with an identified node and reason; never permissive flattening.
- Existing validation/consumer behavior is reproduced or every divergence is enumerated.

### Kybalion

- Flat chapters work without inventing a part level.
- Roman designation and descriptive title remain distinct.
- Attributed aphorism blocks survive the adapter under an explicit policy.
- No PLL or Italian literal enters core code; book-specific knowledge stays in the specimen profile/recognizer.
- Major boundaries match the hand-reviewed corpus finding, with no silent extras.

### Darwin

- False automatic binds: **zero**.
- Successful, fail-loud, and missed binds are reported separately.
- Insertion/renumbering does not cause an identity cascade for unchanged units.
- Every bind is explainable from persisted evidence; doubtful cases fail loud.

### Human surface

For each specimen record elapsed time, review items, manual decisions, reversals, and time per 100 nodes. Measure first; do not hide cost behind a threshold.

## Execution rule

Run in the order above without skipping a specimen or weakening a gate.

On a roadblock:

1. Record the first failing input, invariant, and smallest reproduction.
2. Fix only the root cause needed to continue.
3. Add a regression test that is seen red, then green.
4. Rerun from PLL on a fresh workspace.
5. Repeat until all three complete in one uninterrupted clean run.

No `skip`, `xfail`, stale-cache reuse, threshold relaxation, permissive fallback, or specimen-specific core branch may turn red into green. Unexpected model pressure becomes an explicit decision, not an inline generalization.

## Stop-and-reassess conditions

Pause further substrate work if:

- PLL cannot round-trip through the adapter without unexplained loss/reordering;
- Kybalion requires reshaping the core rather than adding book knowledge;
- Darwin produces any silent false bind;
- a validated artifact cannot identify the node/input responsible for failure;
- human correction is comparable to writing a narrow parser by hand.

## Complete when

- one command builds fresh state and completes PLL, Kybalion, and both Darwin editions in sequence;
- all pass conditions are machine-checked where deterministic and explicitly reported otherwise;
- the final report lists timings, human workload, divergences, bind rates, and every engine change forced by a specimen;
- the existing test baseline has no new failures;
- no live-edition file or pre-existing unrelated working-tree edit was changed.
