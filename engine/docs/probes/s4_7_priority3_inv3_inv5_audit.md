# S4.7 Priority 3 adversarial audit — INV-3 + INV-4 + INV-5 carried reds

**Date:** 2026-07-18  
**Branch:** `spike/s4_7`  
**Result:** CLEAN after remediation; Priority 4 may begin.  
**Scope:** the independent move oracle, analytic boundary classifier, six-row geometry
interaction matrix, strict carried-red tests, shared mutation table, and repository-local evidence
wrapper. The Priority 1 and Priority 2 claims remain separately bounded by their own audit records.

## Outcome first

INV-3 now exercises separate within-container and cross-container moves. A moved slot may either
fail loud with a closed reason or bind the exact planted atom tuple while the resulting structure
map remains globally valid. Duplicate observations and correct-looking local binds embedded in an
invalid global map are independently rejected.

INV-4 is represented by an analytic half-open block model that does not call the production
aligner. Its eight mandatory cases pin the ruled precedence `insert > strict interior > non-equal
edge > clean`, including stream start, empty-old insertion, deletion collapse, and capped unaligned
regions. Each fixture supplies concrete old/fresh tokens and has exactly one optimal reference
alignment, so the authored block geometry cannot hide a tie. The future #48 decision surface is
closed over the four candidate classes and requires an explicit confirmation path for non-clean
boundaries.

INV-5 uses the exact Cartesian matrix `{repeated-content, boundary-edit, move} ×
{geometry-primary, geometry-tie-break}`. Repeated content is same-page ambiguous with distinct-page
companions; boundary edits may not use geometry as a content rescue; move rows reuse the full
INV-3 destination and global-map checks. A separate fixture demonstrates that tie-break geometry
only reduces an already-above-threshold content tie.

The committed-state suite is intentionally green with **seven** `xfail(strict=True,
reason="S5.1-R/#48 (S4.7 item 3)")` carried reds:

1. a planted greedy move span away from the destination is rejected;
2. a destination-correct move bind with an invalid global map is rejected;
3. an unconfirmed inserted boundary fails both adjacent slots loud in both geometry modes;
4. a projection inside a cross-slot merged atom never rounds to a slot;
5. every non-clean boundary class abstains without independent confirmation;
6. an independently confirmed boundary uses the confirmation path;
7. same-page repeated content remains ambiguous in both geometry modes.

The machine-readable evidence is
`docs/probes/s4_7_priority3_red_manifest.json`, SHA-256
`2cdb0bb8237932a5aa0e9098ed21ef39d62bff56e6fae363586de5ce230769cd`.
It records 50/50 detected mutants, zero survivors/errors, seven raw assertion reds, the named green
command, all 16 case/diagnostic rows, seeds and geometry modes, imported module path, environment
identity, normalized patches, table/runner hashes, and byte-identical pre/post hashes over all 18
mutated or locked source files.

## Adversarial findings and remediations

| ID | Finding | Resolution |
|---|---|---|
| P3-A1 | The first analytic validator allowed at most one non-equal block, excluding legal streams with multiple separated edits. | Permit multiple edits when equal blocks separate them; retain a hard rejection for adjacent non-equal blocks whose authored precedence would be ambiguous. |
| P3-A2 | The production adapter initially read a slot's tentative outcome even after the containing node had failed the global allocator. | Derive final bound/reason from `NodeOutcome` and use slot atom ids only when both node and slot are bound. |
| P3-A3 | Converting move observations to a map could silently collapse duplicate records for one affected slot. | Reject duplicates before comparing the observed and required slot sets; pin the check with a focused planted violation and mutant. |
| P3-A4 | The first analytic tiling check proved old-stream coverage only. | Tile old and fresh streams simultaneously and require equal old/fresh widths for every `equal` block. |
| P3-A5 | Authoring only block coordinates left the "unambiguous alignment" premise unexecutable. | Add concrete old/fresh token sequences to every boundary case and require the independent bounded edit reference to report exactly one optimal path. |
| P3-A6 | The original capped-gap token fixture accidentally admitted two optimal edit paths. | Replace it with a unique equal-length substitution while retaining the capped `unaligned` classification geometry. |
| P3-A7 | A behavioral carried red covered unconfirmed insertion but not all non-clean candidate classes. | Add a closed-class permissive-hook red over edge, no-candidate, and two-candidate classes, plus a rejecting-hook red for the confirmed path. |
| P3-A8 | The boundary decision protocol initially accepted an open `str`, allowing misspelled or invented candidate states. | Introduce the closed `BoundaryCandidateClass` literal and use it in the future decision hook. |
| P3-A9 | The geometry matrix's dimensions and fixture premises were implicit. | Assert the exact six-row product, mode propagation, canonical geometry hash, `100 > 2W` repeated passage width, and distinct companion pages `{1, 2}`. |
| P3-A10 | Geometry move rows originally checked only that some node abstained or bound. | Route both rows through the complete INV-3 oracle, including planted tuple truth, closed fail-loud reasons, and global structure-map validity. |

## Oracle and anti-cheating checks

- The boundary classifier consumes authored analytic blocks and never imports or calls a production
  aligner. The independent edit reference is used only to establish the unique-alignment premise.
- Candidate classification uses token gaps and half-open intervals. Insertions at the gap take
  precedence; strict interiors take precedence over non-equal edges; stream endpoints are explicit.
- Move truth comes from Component 0 provenance via planted tuples, not from the rebind report.
  Destination correctness and global-map validity are separate conjuncts.
- Geometry fixtures state their pages synthetically and preserve identical content where ambiguity
  is required. The same-page and distinct-page cases differ only in the intended page signal.
- The tie-break-only row observes two above-threshold candidates before checking page reduction;
  it does not permit geometry to manufacture an otherwise-ineligible candidate.
- Raw carried-red runs are accepted only at pytest rc 1 and must contain the intended
  `AssertionError`. Mutation runs restore all touched files and compare aggregate hashes.

## Executed stability gates

```text
uv run ruff check <all Priority 1/2/3 changed Python files>
git diff --check
  All checks passed

uv run pytest -q \
  tests/unit/test_rebind.py \
  tests/unit/test_structure_map.py \
  tests/unit/test_structure_artifacts.py \
  tests/unit/test_structure_born_gate.py \
  tests/unit/test_harness_relation_laws.py \
  tests/unit/test_harness_materialize.py \
  tests/unit/test_s4_7_inv1_inv2.py \
  tests/unit/test_s4_7_inv3_inv5.py
  294 passed, 13 xfailed in 12.36s

uv run pytest -q
  1864 passed, 13 xfailed, 5 pre-existing SWIG deprecation warnings in 138.44s
```

The Priority 3 evidence wrapper's focused green command reported `17 passed, 7 xfailed`. Both the
refreshed Priority 2 profile and the Priority 3 profile reported **50/50 detected; 0 survived; 0
errors**, with all raw reds at rc 1 and all 18 source files byte-identical after mutation. The later
Priority 4 rows are carried by the shared table and do not widen this audit's INV-3/4/5 claim.

## Bounded claim / non-claims

- This is item 2's **red harness**, not item 3's replacement mechanism. The seven strict failures
  remain deliberate obligations for #48; no production classifier or boundary-decision policy has
  been implemented here.
- The analytic classifier proves the registered half-open precedence over bounded synthetic
  cases. It does not claim equivalence to any future aligner's opcode selection outside the stated
  unique-alignment premise.
- Geometry is modeled by synthetic page identity only. This audit makes no bounding-box,
  coordinate-distance, OCR-quality, or real-document claim.
- The repeated-content rows establish abstention/disambiguation behavior for this fixture family;
  they do not establish a calibrated false-bind rate or the item-4 anchor-density curve.
- Any later change to the shared generator, oracle, boundary model, geometry matrix, `W`, mutation
  table, or evidence wrapper invalidates the recorded hash and requires the corresponding profiles
  to be rerun.
