# S4.7 Priority 2 adversarial audit — INV-1 + INV-2 carried reds

**Date:** 2026-07-18  
**Branch:** `spike/s4_7`  
**Result:** CLEAN after remediation; Priority 3 may begin.  
**Scope:** the Priority 2 oracle, shared corpus, DR-4 interface skeleton, strict carried-red
tests, mutation table extension, and repository-local evidence wrapper. Component 0's separate
Priority 1 audit remains `docs/probes/s4_7_priority1_component0_audit.md`.

## Outcome first

INV-1 and INV-2 now consume the same 29-case corpus: nine mandatory Component 0 cases, one
long interior-char-sub case, one isolated merge case, within- and cross-container repeated-passage
sentinels, and 16 fixed randomized seeds (`2700…2715`). The independent oracle works in concrete
`(node_id, slot_name, ordered fresh-atom-id tuple)` pairs, and separately checks pairwise membership,
fresh-atom disjointness, and fail-loud insertion coverage.

The committed-state suite is intentionally green with **six** `xfail(strict=True,
reason="S5.1-R/#48 (S4.7 item 3)")` carried reds. Each was also run raw with `--runxfail` and failed
with pytest rc 1 for its named assertion:

1. INV-1 bound-set subset on the full shared corpus;
2. repeated-passage abstention, both within and across containers;
3. cross-slot merge: both affected nodes become `global-conflict`;
4. interior in-token char substitution binds;
5. atom split with unchanged tokens binds the exact descendant tuple;
6. unambiguous atom merge binds.

The machine-readable evidence is
`docs/probes/s4_7_priority2_red_manifest.json`, SHA-256
`17a4133a163ab262901b9023d5c4e0d42743ed6e13e74b2aa2fd17056b76791c`.
It records 50/50 detected mutants, zero survivors/errors, six raw assertion reds, the named green
command, all 29 diagnostic rows, seeds/configs, imported module path, environment identity, inlined
normalized patches, table/runner hashes, and byte-identical pre/post hashes over every mutated file
plus the generator/oracle/wrapper lock set.

## Adversarial findings and remediations

| ID | Finding | Resolution |
|---|---|---|
| P2-A1 | The first repeated-passage sentinel covered only one container, leaving the explicit cross-container quantifier untested. | Added separate within- and nested cross-container sentinels to the shared corpus; both repeat a `4W+2`-token passage and place the boundary more than `W` tokens from either passage edge. |
| P2-A2 | The shipped monotone tiler silently used order to bind all four byte-identical repeated slots in `no-geometry`; a fixture-only check would have missed the actual violation. | Added a dedicated strict carried red that evaluates both repeated topologies. Disabling the oracle uniqueness guard is mutation-killed by that exact test. |
| P2-A3 | Pairwise allowed tuples plus disjointness did not forbid an inserted seam atom from being claimed by neither side after both legal owners reported bound. | Added `assert_insert_coverage_not_silent`: omission is legal only while a legal owner fails loud. A planted all-bound silent-drop case and named mutant prove the guard has teeth. |
| P2-A4 | The original merge-positive row shared a fixture with an unrelated split, obscuring whether a red belonged to merge handling. | Added `inv2-atom-merge`, containing one same-slot merge and one exact required tuple; the shipped matcher independently over-abstains on it. |
| P2-A5 | The initial DR-4 skeleton structurally named the fields and `W`, but determinism/content-only behavior lived largely in prose. | Added `derive_boundary_anchor`, which invokes a #48-provided family twice, requires a `BoundaryAnchor`, enforces contiguous supplied content with `exact` touching the inside boundary token, and leaves selection/allocation unimplemented. Determinism, foreign-content, `W`, and maps-far mutations are all killed. |
| P2-A6 | Converting observed binds to a set before comparison could hide duplicate outcome records for one slot. | Reject duplicate `SlotRef` records before set conversion; a focused planted violation and named mutant pin it. |
| P2-A7 | The reference model bounded tokens but not the optional insertion-attribution product. | Added `REFERENCE_MAX_OPTIONAL_INSERTS = 8`; larger reference cases fail loud rather than acquiring unbounded production-like search. |
| P2-A8 | The first manifest wrapper hand-copied the case names, permitting the recorded matrix to drift from the materialized corpus. | The wrapper now resolves `priority2_shared_corpus()` itself and rejects seed disagreement. A unit test pins manifest matrix equality to the live corpus. |
| P2-A9 | Pre/post restoration hashes initially covered the new lock files but not every older production file targeted by the extended mutant table. | The wrapper unions the lock set with every normalized patch target before hashing; the refreshed artifact covers eighteen source files and records equal aggregate hashes. |
| P2-A10 | Per-case diagnostics existed in tests but were not emitted into the durable artifact. | The wrapper now records all 29 `bound_correct / abstained / wrong` rows, the exact config/seed, allowed-pair count, and required INV-2 target status. It emits no rate field and gates on no rate. |
| P2-A11 | Accepting any nonzero raw-red rc could misclassify a signal death or infrastructure error as invariant evidence. | Raw red is accepted only at pytest rc **1**; rc 0, usage errors, signals, and other failures invalidate the wrapper run. |
| P2-A12 | Importing the live corpus after the shared runner's post-verify could recreate bytecode after the runner's purge. | The wrapper sets `sys.dont_write_bytecode = True` before any harness import; child runs also pin `PYTHONDONTWRITEBYTECODE=1` and strip cache-injection variables. |
| P2-A13 | A randomized failure could expose its tuple without a retained seed/config dump. | The shared INV-1 assertion re-raises with case name, fixed seed, and full `DriftConfig`; the manifest also stores every case config independently. |

## Oracle and anti-cheating checks

- `tests/harness/oracle.py` has an AST gate forbidding an
  `engine.structure.rebind` import or report readback. It may reuse the shared normalizer, whose
  contract is tested separately, but scoring, alignment feasibility, uniqueness, provenance, and
  insertion attribution do not call production rebind logic.
- The edit-grid reference enumerates the full bounded grid up to 512 tokens, saturates optimal-path
  counts at two, and exposes all fresh states through each old boundary. A pinned insertion example
  proves that one optimal path can still make a boundary ambiguous at both sides of an inserted run.
- Planted destinations come only from the many-to-many provenance relation. Cross-slot merged atoms
  are atom-granularity-unrepresentable; duplication requires every descendant in the ordered tuple;
  tokenless atoms remain in the tuple even though they have no token back-pointer.
- Randomized confidence uses independent shingle arithmetic and a strict content-only sentinel:
  the inside-adjacent start/end tokens must be unchanged and whole-stream unique in both generations.
  The production policy defaults are copied independently and contract-bound by a separate test.
- The maps-far conjunct remains separate from uniqueness: a unique-in-both anchor at fresh boundary
  91 does not confirm a projection to boundary 10. Weakening that equality is mutation-killed.
- The anchor-density artifact is a sentinel knob (`repeat_copies`), not item 4's six-point sweep and
  not a rate claim.

## Executed stability gates

```text
uv run ruff check <all Priority 1/2 changed Python files>
git diff --check
  All checks passed

uv run pytest -q \
  tests/unit/test_rebind.py \
  tests/unit/test_structure_map.py \
  tests/unit/test_structure_artifacts.py \
  tests/unit/test_structure_born_gate.py \
  tests/unit/test_harness_relation_laws.py \
  tests/unit/test_harness_materialize.py \
  tests/unit/test_s4_7_inv1_inv2.py
  277 passed, 6 xfailed in 13.02s

uv run pytest -q
  1847 passed, 6 xfailed, 5 pre-existing SWIG deprecation warnings in 136.28s
```

The evidence wrapper's own green command reported the same six strict carried reds while staying
green, and its refreshed mutation run reported **50/50 detected; 0 survived; 0 errors**. The
additional entries are the later Priority 3/4 table rows carried by the shared mutation runner; they
do not widen the Priority 2 invariant claim.

## Bounded claim / non-claims

- This is item 2's **red harness**, not item 3's replacement mechanism. INV-1 and INV-2 are not
  green; the strict xfails deliberately prevent accidental progress from being hidden.
- **DR-3 remains unlocked.** The preregistration document receives no lock pointer until INV-1 is
  genuinely red-then-green under #48. Any later change to the generator, oracle, matrix, `W`, or
  other fixed design constants invalidates this artifact and requires a rerun.
- `BOUNDARY_ANCHOR_FOOTPRINT_W = 24` is the current contract-fixed build value. Item 2 does not choose
  prefix/exact/suffix allocation and contains no production anchor constructor.
- These results establish only conditional properties over the modeled synthetic drift. They do
  not certify a real PLL re-extraction, a calibrated false-bind rate, geometry-mode behavior, the
  item-4 density curve, or production-scale complexity. Those obligations remain with `S5.1-RG`,
  S5.2, and later S4.7 priorities exactly as registered.
