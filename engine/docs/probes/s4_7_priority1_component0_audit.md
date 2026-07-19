# S4.7 Priority 1 adversarial audit — Component 0 fixture truth

**Date:** 2026-07-18  
**Branch:** `spike/s4_7`  
**Scope:** `tests/harness/{relation,materialize}.py` and their focused tests.  
**Verdict:** **GREEN after remediation.** No Priority-1 finding remains open; INV-1/2 may consume
the fixture bundle only after the commands below remain green.

## Audit question

Could the generator or its validators manufacture a false green for later S4.7 invariants by
building impossible maps, reusing old identity, deriving truth from production rebind code,
misreporting realized drift, or silently admitting an out-of-contract perturbation?

## Method

1. Line-by-line reconciliation against `s4_7_item2_invariants_plan.md` §1.1–§1.6 and §3 item 1.
2. Narrow code audit of each mutation transition and the independent event interpreter.
3. Constructed negative inputs for every relation law and every bundle boundary.
4. AST independence guard: no harness import of `engine.structure.rebind`; the incremental mutation
   engine has no direct `compose_events`/`rebind` reference.
5. Randomized deterministic replay over 250 fixed seeds in both `no-geometry` and
   `geometry-tie-break` (500 fully composed fixtures total).
6. Neighboring rebind/structure suite, then the complete unit suite.

## Findings and resolutions

| ID | Finding | Severity | Resolution / permanent evidence |
|---|---|---:|---|
| P1-A1 | Generated maps passed the narrow rebind baseline but failed aggregate structure validation because class handle policies were unresolved. | High | Generate resolved `position-path` policies and run `validate_structure_map` in every bundle validation. Negative: `test_bundle_validator_runs_the_aggregate_structure_gate_not_only_hash_checks`. |
| P1-A2 | The map builder called `structure_map_from_json` without meeting its documented Tier-1 precondition; the manifest was only a minimal rebind subset. | High | Build through the real `build_manifest` producer, validate against the packaged schema before typed construction, and repeat Tier-1 validation at the bundle boundary. Negative: `test_bundle_validator_enforces_the_persisted_tier1_shape`. |
| P1-A3 | Page topology lived only in optional `Geom`; `no-geometry` fixtures could therefore admit forbidden cross-page merges/inserts. | High | Carry page independently on every working atom and reject cross-page compositions in every mode. Negatives cover merge and insert with absent geometry. |
| P1-A4 | Re-segmentation counts described emitted events, so split→merge-back could falsely satisfy the ≥30% realized floor. Move-out→move-back had the same final-truth problem. | High | Derive realized re-segmentation and movement from the final provenance relation; retain separate generated counts. Net-zero split/merge and move negatives pin both directions. |
| P1-A5 | Stream-edge insertion was classified with `{adjacent owner, abstain}` even though only a true two-slot seam admits abstention. | Medium | Edge insertion now belongs to its sole adjacent slot; two-sided differing owners produce `{left, right, abstain}`. Interior/edge/seam tests pin all three. |
| P1-A6 | The duplicate transform lacked the required distinct-page variant, and multi-copy geometry was staged against the wrong intermediate list. | Medium | Add per-copy page override for duplicate only; stage each copy into the working list before locating the next. Tests cover same-page, distinct-page, and two-copy boxes/ids. |
| P1-A7 | The deterministic matrix did not explicitly exercise the tokenless cross-slot merge boundary or the registered ≥30% re-segmentation floor. | Medium | Add `merge-cross-slot-seam` and `heavy-resegmentation` mandatory cases, with complete many-to-many ancestry assertions. |
| P1-A8 | Manual `char_sub` configs could provide arbitrary replacement text rather than one in-token OCR-class substitution. | Medium | Materialization now admits exactly one registered OCR confusion and rejects arbitrary rewrites. |
| P1-A9 | The reference interpreter accepted some malformed authoring inputs (duplicate initial ids, reversed merge sources, output-id reuse, out-of-range positions, and net-zero final move attribution). | Medium | Fail loud on each form; focused relation negatives pin the rejection surface. |
| P1-A10 | Composition tags and active output labels could claim misleading coverage without the required operations or could create ambiguous fixture handles. | Low | Tags are bound to their required op sets; composed op pairs are explicitly declared; active output-label reuse is rejected. |

## Gate evidence

From `engine/`:

```text
uv run ruff check tests/harness tests/unit/test_harness_relation_laws.py tests/unit/test_harness_materialize.py
  All checks passed!

uv run pytest -q tests/unit/test_harness_relation_laws.py tests/unit/test_harness_materialize.py
  78 passed in 2.27s

500 randomized fixtures (seeds 0..249 × no-geometry/tie-break)
  passed relation, Tier-1, Tier-2, witness, and baseline gates

uv run pytest -q \
  tests/unit/test_harness_relation_laws.py \
  tests/unit/test_harness_materialize.py \
  tests/unit/test_rebind.py \
  tests/unit/test_structure_map.py \
  tests/unit/test_structure_projection.py \
  tests/unit/test_structure_handles.py
  361 passed in 5.25s

uv run pytest -q tests/unit
  1826 passed, 5 third-party SWIG deprecation warnings in 55.61s

uv run pytest -q
  1831 passed, 5 third-party SWIG deprecation warnings in 124.44s
```

## Bounded claim

This audit proves that Component 0 produces internally lawful, persistable synthetic fixture truth
for the modeled drift classes and that its relation closure is independent of production rebind.
It does **not** prove the drift model resembles a real PLL re-extraction, does not lock DR-3, and
does not make any bind-rate claim. Those remain with INV-1/2, S5.2 calibration, and the registered
post-S4.6 real-data gate.
