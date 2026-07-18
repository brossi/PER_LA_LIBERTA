# Engine test-suite audit — value scoring pass

**Date:** 2026-07-02
**Scope:** all 45 test files / 575 test functions under `engine/tests/`
**Method:** 10 concern-clustered reviewers, one shared rubric, no test modified.
**Status:** review artifact. **No test has been removed or edited.** This is the "score first, decide together" pass requested — it flags candidates; it does not act on them.

---

## 1. Rubric

Each test scored **0–10** = sum of four sub-scores, derived from this repo's own codified test principles (binding-not-shape, red-first/mutation-pinned, deliberate-second-fixture protection, no cheating).

| Dimension | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| **Binding** | tautology (asserts its own input / a constant against itself) | shape/type/membership/`in __all__` only | asserts real behavior loosely (direction/contains/inequality) | asserts an exact value/state/error the SUT produces on real input |
| **Distinct axis** | duplicate of a named sibling (same path + same axis) | minor variation (one more example, same path) | a deliberate second fixture on a genuinely different axis | unique failure branch / error code / boundary / non-default-config path |
| **Regression sensitivity** (0–2) | cannot red on a real SUT defect (tests the mock/framework, or assertion too loose) | reds only on a coarse regression | — | a plausible SUT mutation reds *this test specifically* |
| **Structural importance** (0–2) | incidental / cosmetic | meaningful internal behavior | — | public surface / cross-module contract / neutrality / born gate / regen guard / round-trip floor |

**Buckets:** KEEP = 7–10 · CONSOLIDATE = 4–6 (valuable but mergeable/parametrizable) · REVIEW-FOR-CUT = 0–3.

**PROTECT rule:** the `*_real_input`, `*_golden`, `*_neutrality` files and the invariant *control* tests are deliberate axis-adders — scored on the axis they actually add, never down-scored for resembling a synthetic sibling. Every reviewer was handed the existing mutation harnesses (`mutate_b1..b4`, `mutate_atom_store`, `mutate_gate`, `mutate.py`) so any test a real mutation already reds is credited as proven load-bearing.

**Regression-score caveat (honesty):** "mutation-proven" (R=2) is *empirically* established only for the tests a running harness actually selects — `test_roundtrip_gate.py` (via `mutate_gate.py`), `test_atom_store.py` (via `mutate_atom_store.py`), `test_structure_projection.py` (b2/b3), `test_structure_handles.py` (b4), `test_resource_lineage.py` (`mutate.py`), and the b1-targeted artifacts/errors tests. For `roundtrip.py`, `typed.py`, the real-input files, and the closure file there is no running harness; their R scores are inferred from assertion tightness against the SUT, not machine-verified.

---

## 2. Headline verdict

The suite is **unusually disciplined**. Exit codes, error types, and messages are asserted exactly; neutrality and stub-honesty guards carry explicit planted-violation red-first controls and anti-vacuity meta-guards; the real-input/golden fixtures are genuine differ-on-axis second fixtures, not happy-path clones. Across 575 tests:

| Bucket | Count | Share |
|---|---|---|
| KEEP (7–10) | ~538 | ~93.5% |
| CONSOLIDATE (4–6) | ~36 | ~6.3% |
| REVIEW-FOR-CUT (0–3) | **1** | ~0.2% |

**There is no widespread over-testing to prune.** The actionable output is three narrow tracks:

1. **Three "cannot-red" tests** (§3) — the only genuinely *meaningless* category: they pass green regardless of the SUT defect they name. One is a straight cut; two need a stronger fixture or should be folded.
2. **Parametrize-to-compress families** (§4) — ~30 tests that each pin a distinct mutation but share a body; merging into parametrized tables cuts count/LOC **without losing any coverage**. This is compression, not deletion.
3. **Test-infra integrity findings** (§5) — a stale mutation-harness target that reports a *false catch*, plus two real mutation/branch coverage gaps. These matter more than any single test's score.

---

## 2b. Disposition — actions applied (2026-07-02)

Acted on the two clear-win tracks; **deferred the strong-pair concision collapses** with rationale (below) so they stay triageable. All changes are granular commits on `spike/document-structure`; the suite stayed green throughout.

**Applied:**
- **§3 cannot-red tests** — cut `test_addressing_fields_round_trip_as_tuples`; folded `test_duplicate_atom_ids_empty_on_empty_stream` into `_empty_when_unique`; **strengthened** `test_align_streams_normalizes_case_and_whitespace_for_matching` with a two-block fixture, red-proven to fail against an identity `_alignment_key`. Commit `1434e68`.
- **I6 scope correction** (forced by §3) — narrowed the governance doc-scan to the *decision record* per `docs/invariants.md` I6, excluding point-in-time `docs/probes/` reports (an audit that documents a removal must be free to name the removed test). Red-proven it still catches a dangling ref planted in a non-probe doc. Same commit.
- **§4.1** — config_loader required-field family 5→1 parametrized (`test_profile_schema_rejects_a_missing_required_field`). Commit `924c8ad`.
- **§4.8** — six per-module export-surface checks → one per-concern `test_public_names_per_concern_resolve` in `test_structure_artifacts`. Commit `4f3c8a5`.
- **§4.3 (delegation subset)** — merged the two `production_roundtrip` gate-wrapper delegation duplicates into `test_production_roundtrip_delegates_to_the_gap_floor`; `mutate_gate.py` re-run confirms all 14 gate mutants still killed.

**Deferred — strong pairs kept as separate tests (intentional; do not casually collapse):**

| Family | Tests kept separate | Why (the non-obvious reason they exist as they do) |
|---|---|---|
| §4.2 roundtrip wholesale-exclusion | `..._raises_when_all_body_excluded`, `..._raises_when_below_fraction`, `..._floor_is_tunable`, `..._exempts_all_whitespace_source` | Each pins a **distinct branch** (all-excluded vs below-fraction vs tunable floor vs `total_nonws==0` exemption); all four are mutation-proven by `mutate_gate`. Parametrizable, but every case is a separately-killed mutant. |
| §4.4 resource-lineage fold-mode / digest-component pairs | `test_chunk_key_casefold_mode_differs_from_lower` + `..._lower_mode_differs_from_casefold`; `..._tracks_the_chunk_routing_key` + `..._tracks_a_declared_filename_rename` | The fold-mode pair kills **M10/M11** (casefold≠lower and its symmetric); the digest pair pins different members of the `(key, file, content)` triple. Mutation-proven by `mutate.py`. |
| §4.5 atoms geom / arity pairs | `test_present_geom_round_trips_exact` + `test_absent_geom_round_trips_as_absent`; `test_atom_raw_span_must_be_a_pair` + `test_atom_page_range_must_be_a_pair` | present-geom is a **non-default axis `capture` never emits**; raw_span vs page_range are distinct fields with distinct arity guards. |
| §4.6 projection construction-shape | `test_container_and_leaf_distinct_variants`, `test_nodes_store_children_not_parent`, `test_nodes_and_map_frozen`, `test_sequence_fields_normalize_to_tuples`, `test_typed_records_are_frozen` | Immutability / list→tuple-normalization construction guards; each is the **sole guard** of its construction invariant on a distinct dataclass/field. |
| §4.7 misc step pairs | `test_collect_step_opts_includes_only_set_options` + `..._empty_when_none_set`; `test_require_asset_missing_file_is_typed` + `..._missing_dir`; `test_plausibility_requires_both_strings` + `..._accepts_near_match_rejects_drift` | Each pair covers a **distinct axis** (set vs empty namespace; file vs dir kind; empty-guard vs ratio-boundary). |

Why deferred, not done: these score **9–10** individually. Collapsing trades explicit, individually-named intent for marginal concision — and the proof for the non-`mutate_gate`/`mutate.py` families would be *structural* (no harness), so the added risk lands on the lowest-value collapses. **Revisit if** a family grows a 6th+ case, or a file becomes a maintenance burden. They are now flagged and understood; leaving them is a deliberate choice, not an oversight.

**Still open (not this pass) — §5 infra findings:** the `mutate_b1` stale target, the `POLICY_TITLE` mutation gap, the `align_streams` direct `delete`-branch test, and the divergence-validator `RF` cases remain as documented in §5. These *add* coverage rather than compress; a natural follow-up when next touching test-infra.

---

## 3. REVIEW-FOR-CUT and cannot-red tests (the actionable "ditch" core)

These are the only tests that fail to bind on a real defect. Ranked by score.

| # | Test | File | Score | Why | Recommendation |
|---|---|---|---|---|---|
| 1 | `test_addressing_fields_round_trip_as_tuples` | `test_atom_store.py` | **3** | **Cannot red.** Its own docstring admits dropping `tuple()` in the store would not fail it — the model re-coerces. Redundant with `test_atom_sequence_fields_are_tuples` (which *can* red). | **CUT.** The model-level sibling is the load-bearing one. |
| 2 | `test_align_streams_normalizes_case_and_whitespace_for_matching` | `test_raw_capture.py` | **4** | **Cannot red.** For two single-element streams, an `equal` match and a `replace` non-match produce the *identical* `[(p0,s0)]` output — a broken `_alignment_key` passes green. | **STRENGTHEN** with a multi-element fixture where fold-vs-no-fold changes opcode structure, or assert an `equal` match specifically. Do not cut — the intent is real, the fixture is too weak. |
| 3 | `test_duplicate_atom_ids_empty_on_empty_stream` | `test_atoms.py` | **5** | **Cannot red.** `[] → []` passes even a fully-broken helper. | **FOLD** into `test_duplicate_atom_ids_empty_when_unique`. |

Everything else scoring ≤6 is a *parametrize/merge* candidate that still reds on a real defect (§4), or a deliberate cheap guard held by PROTECT (§6).

---

## 4. CONSOLIDATE — parametrize-to-compress families

Each member below still names a distinct killing mutation. **Merging preserves coverage; it reduces test count and body duplication.** Grouped by the merge.

### 4.1 The `config_loader` required-field family (biggest single lever) — 5 → 1
Identical body ("stage real profiles, delete one required field, assert `ConfigError` match 'schema validation'"), differing only in which `_validate` call fires:
`test_profile_schema_guards_its_builder` · `test_source_noise_schema_is_enforced` · `test_typeface_schema_is_enforced` · `test_malformed_coverage_fails_schema` · `test_case_fold_is_required` (all score 9–10).
→ Parametrize over `(profile_subpath, field_path)`. The distinct-`_validate`-call axis is preserved by the parameter.

### 4.2 Roundtrip wholesale-exclusion family — 4 → 1
`test_wholesale_exclusion_passes_when_body_dominates` (5) · `..._raises_when_all_body_excluded` (9) · `..._raises_when_below_fraction` (9) · `..._floor_is_tunable` (10).
→ Parametrize `(scope-config, min_included_fraction, expect_raise)`. Keep `..._exempts_all_whitespace_source` **separate** (distinct `total_nonws==0` branch).

### 4.3 Roundtrip small pairs
- `test_hash_raw_distinguishes_and_is_deterministic` (5) → parametrize with `test_hash_raw_is_sha256_utf8_with_prefix` (the contract test implies it).
- `test_is_reversible_true_for_a_reversible_transform` (5) → subsumed by `test_is_reversible_false_for_a_lossy_transform`'s second assertion; parametrize.
- Gap-emission pair (`emit_ordered_inter_atom` / `emit_leading_and_trailing`) and rebuild pair (`rebuilds_the_whole_artifact` / `rebuilds_with_edge_gaps`) → parametrize on gap-position; each keeps its axis.
- Two **gate-wrapper delegation duplicates** — `test_production_roundtrip_raises_on_silent_loss` (8) and `test_production_roundtrip_returns_declared_gaps_on_clean_input` (7) re-assert, through the bundled entry, what the `gap_records` tests already pin. Value-add is only "the wrapper propagates." Keep one as the integration proof, or thin.

### 4.4 Resource-lineage pairs
- `test_chunk_key_casefold_mode_differs_from_lower` + `..._lower_mode_differs_from_casefold` → one parametrized `(mode, "ẞoo", expected, anti)` (each still pins M10/M11 — parametrize, don't drop).
- `test_resource_version_tracks_the_chunk_routing_key` + `..._tracks_a_declared_filename_rename` → parametrize over which component of the `(key, file, content)` triple changes.
- `test_index_metadata_churn_does_not_move_the_version` + `test_chunk_order_within_a_member_does_not_move_the_version` → shared "no-op manifest change → version stable" fixture.
- `test_resource_lineage_schema_version_is_a_positive_int` (4, shape-only) → subsumed by `test_resource_descriptor_and_schema_version_wire_shape_is_pinned`; fold.

### 4.5 Atoms/geom pairs
- `test_present_geom_round_trips_exact` + `test_absent_geom_round_trips_as_absent` (6) → one parametrized present/absent round-trip (keep present as the load-bearing non-default axis capture never emits).
- `test_atom_raw_span_must_be_a_pair` + `test_atom_page_range_must_be_a_pair` → parametrize `(field, bad-arity)`.
- Frozen trio (`test_geom_is_frozen` / `test_atom_is_frozen` / `test_derivation_is_frozen`) → parametrizable over the `frozen=True` mutation class (low priority; each is a distinct dataclass).

### 4.6 Structure-projection construction-shape checks (score 5–6)
`test_container_and_leaf_are_distinct_variants_of_the_node_union` · `test_nodes_store_children_not_parent` · `test_nodes_and_map_are_frozen` · `test_sequence_fields_normalize_to_tuples` · `test_typed_records_are_frozen` — immutability/normalization construction guards; consolidate into a small construction-invariants block. Plus `test_correct_split_validates_clean` (5, admits redundancy with `test_base_map_validates_clean` in its own docstring) — drop or keep only as a named mutation target.

### 4.7 Misc step pairs
`test_collect_step_opts_includes_only_set_options` + `..._empty_when_none_set` → parametrize on the namespace; `test_require_asset_missing_file...` + `..._missing_dir...` → parametrize on `kind`; `test_plausibility_requires_both_strings` + `..._accepts_near_match_rejects_drift` → one `_is_plausible_correction` table.

### 4.8 The export-surface family (cross-cutting) — the largest low-binding cluster by count
`test_public_exports_resolve` (or a near-variant) recurs, shape-only (score 5–7), in **six** files: `test_roundtrip.py`, `test_raw_capture.py`, `test_atoms.py`, `test_typed_projection.py`, `test_block_classifier.py`, and structure-handles (`test_handle_surface_is_exported` + `test_all_public_exports_resolve_on_the_package`). Each is a deliberate `validate-bindings` guard of its own module surface. The **strong** one — `test_public_export_surface_is_bounded` (artifacts, score 10) — is the amendment tripwire (exact `__all__` allowlist, no dups).
→ **Option A (recommended):** keep the bounded-set gate + fold the six per-module hasattr resolvers into **one** package-level parametrized resolver test.
→ Option B: keep them — they are cheap and each fails at its own module's first use. Not cruft, but the biggest "many low-binding tests" pattern in the suite.

---

## 5. Test-infra integrity findings (higher priority than any single score)

These are about the *proof machinery*, not the tests themselves — a false-green in the tooling is worse than a low-value test.

1. **Stale mutation-harness target → a false "caught" (fix this).** `mutate_b1.py` targets `test_structure_artifacts.py::test_no_relation_store_loader_is_exported_from_structure`, which was **renamed** to `test_no_relation_named_export_beyond_the_inert_set`. `mutate_b1.py` has no pre-flight, so `pytest <nonexistent node>` exits non-zero and the harness scores the mutant "RED (caught)" — **the inertness-leak mutant is never actually verified.** Coverage still exists (the renamed test + `test_public_export_surface_is_bounded` both catch the `load_relations` leak), so this is a *proof* gap, not a *coverage* gap. This is the [[feedback_mutation_pyc_staleness]] family (false-green tooling). **Fix:** update the b1 target name; add the F8-style pre-flight (present in `mutate_b4.py`) to b1/b2/b3.
2. **`POLICY_TITLE` render arm is a b4 mutation gap.** No `mutate_b4.py` mutation touches `_title_source` / the title render arm. `test_title_policy_renders_from_the_title_field` is tight (exact strings) and would catch a regression, but it is **not mutation-proven.** Add a title-branch mutation.
3. **Divergence-ledger validator: only the `DL` entry kind is exercised.** `test_validator_*` cover DL accept/reject; the `RF` ("Re-froze:") cite and RF non-sequential branches share the validator path but are untested.
4. **`align_streams` delete branch is only covered transitively.** `test_align_streams_marks_insert_and_delete` exercises only the `insert` branch despite its name; `delete` is reached only via `build_canonical` single-witness tests, never directly on `align_streams`.
5. **`test_wire_literals_are_single_sourced_across_the_package`** has no detector-reach meta-test (unlike `test_no_raw_artifact_writes_in_steps`, which is guarded by `test_detector_catches_pathlib_open_write`). Its AST scan could silently under-match. Minor; consider a planted-violation control.

---

## 6. PROTECT register — deliberate fixtures that look redundant but must NOT be cut

The audit confirmed the PROTECT rule fired correctly everywhere; recording it so these are not later mistaken for cruft:

- **All `*_real_input` files** (roundtrip, roundtrip_gate, raw_capture, atom_store, resource) — real PLL bytes at scale (500K–790K codepoints, thousands of atoms, real `⟨PAGE:N⟩` furniture) surface UTF-8/codepoint/page-map confusions synthetic 10-char sources cannot. Per-book source-noise grammar lives *in the test*, not core (neutrality preserved).
- **All `@golden` tests** (chapterids ×3, cleanup, reconcile, validate) — characterization reproductions of committed live artifacts, with **real** spaCy/symspell hard-asserted (no `skipif`).
- **All `*_neutrality` scans + their planted-literal red-first controls + their has-python-files anti-vacuity guards** (core, structure, resource, cleanup).
- **Invariant controls** — `test_m4b_deterministic_surfaces_are_hashseed_independent` (I9) and `test_governance_docs_cite_only_resolvable_test_names` (I6).
- **All 7 `test_isolation.py` live-tree write-boundary tests** — each guards a distinct ported `run()`'s write path.
- **The adversarial-audit regression fixtures** in handles/projection — `test_disambiguation_does_not_collide_with_a_naturally_numbered_sibling`, `test_three_colliding_siblings_rank_incrementally`, `test_position_path_own_scope_is_zero_for_every_node`, `test_parse_md_derived_node_id_raises_derived`, `test_node_id_inside_an_ancestor_slug_only_validates_clean`, the `Über→uber` word-internal-accent cheat, the interval-boundary aliases, etc. Each looks like "one more render/clean case" but each kills a specific survived mutant.
- **The must-not-bake identity guards** (`test_node_id_survives_dataclass_round_trip`, `..._independent_of_owned_content`, `..._stable_across_positional_move`, `test_ragged_depth_and_heterogeneous_siblings_validate`) and the **negative-exemption fixtures** (the "does NOT fire" boundaries a widened check would break).
- **The typed-projection real-capture-path tests** (`test_excluded_furniture_is_exempt_from_completeness`, `test_real_capture_routes_a_body_leaf_to_review`, `test_typed_projection_runs_over_the_canonical_stream`, …) — production-shaped atoms, not hand-built.
- **The AST detector meta-tests** (`test_detector_catches_pathlib_open_write`, `test_steps_have_python_files`) — test-the-test guards that keep the negative controls from passing false-green.
- **The templating separability pair** and every `no_pll_string_leaks` / `carries_real_book_identity` differ-on-book pair.

---

## 7. Recommended actions (for review — not yet applied)

1. **Cut 1** test: `test_addressing_fields_round_trip_as_tuples` (§3.1).
2. **Strengthen 2** cannot-red tests: `test_align_streams_normalizes_case_and_whitespace_for_matching` (multi-element fixture), and fold `test_duplicate_atom_ids_empty_on_empty_stream` (§3.2–3.3).
3. **Fix the b1 harness stale target** and backfill F8 pre-flight into b1/b2/b3 (§5.1) — highest-leverage item.
4. **Close the two coverage gaps:** a `POLICY_TITLE` mutation (§5.2) and an `align_streams` direct `delete` test / `RF` divergence-validator cases (§5.3–5.4).
5. **Optional compression** (no coverage loss): the parametrize families in §4 — biggest wins are `config_loader` required-field (5→1) and the export-surface family (6→1). Net reduction on the order of ~20–25 test functions with zero mutation-coverage change.

Net: this is a *tightening* pass, not a cull. The suite earns its size.

---

## 8. Per-cluster scored rows

Full per-test scores from each reviewer. Format: `test — score (bucket) — pin/why`. Bucket omitted where KEEP. `[×N]` = internally parametrized, counted once.

### 8.1 Acquisition + golden (21 tests — 21 KEEP, 0 CONSOLIDATE, 0 CUT)
`test_ocr_engine.py`: render_ocr_prompt_faithful_to_live 10 (PROTECT) · stitch_pages_map_invariants 10 · blank_sentinel_template_and_stitcher_use_one_constant 10 · failing_backend_yields_ocr_error_sentinel 10 · transient_backend_failure_retries 10 · unreadable_pdf_page_count_failure 10 · per_page_render_failure_becomes_sentinel 10 · resume_skips_completed_pages 10 · ocr_to_reconcile_marker_roundtrip 10 (PROTECT) · unknown_model_role_rejected 9 · default_gemini_backend_without_key 10 · missing_scan_pdf_clean_error 10 · fitz_renderer_and_run_against_real_pdf 10 (PROTECT).
`test_download_engine.py`: url_derivation_fallback 10 · target_name_keyed_off_role 8 (parametrize) · writes_exactly_the_fetched_bytes 9 · idempotent_skip_if_exists 10 · network_failure_typed_error 10.
`test_acquisition_separability.py`: synthetic_acquisition_feeds_reconcile 9 (PROTECT) · download_then_reconcile_without_ocr_is_two_way 10 (PROTECT) · reconcile_without_copies_typed_missing_input 10.
`golden/`: chapterids_count_matches_structure 7 (PROTECT) · chapterids_reproduce_frozen_fixture 10 (PROTECT) · short_ids_match_chapter_pages_keys 7 (PROTECT) · clean_text_reproduces_frozen_detcore 10 (PROTECT) · reconcile_reproduces_frozen_outputs 10 (PROTECT) · validate_reproduces_frozen_report 10 (PROTECT).
Lever: `test_target_name_keyed_off_role` (two-role parametrize). Do **not** merge the ocr failure-branch family (each pins a distinct exit code).

### 8.2 Text-steps: adjudicate / cleanup (40 tests — 39 KEEP, 1 CONSOLIDATE, 0 CUT)
`test_adjudicate_engine.py`: noise_branch 9 · ner_branch_neither_part 9 · ner_branch_both_caps 9 · compound_requires_both_long 9 · compound_rejected_short_part 8 · corrected_via_simple_join 9 · unknown_partial_then_neither 9 · boundary_substitutions_drive_corrections 10 (PROTECT) · try_corrections_covers_each_pass 9 · dictionary_oracle_membership_and_floor 10 (PROTECT) · oracle_accent_insensitive_retry 9 (PROTECT) · oracle_lookup_and_context 10 (PROTECT) · search_chunk_respects_word_boundaries 9 · build_oracle_selects_monolingual 10 (PROTECT) · run_without_flags_declares_no_input 10 · run_with_injected_oracle 10 (PROTECT) · run_with_real_zingarelli_oracle 7 (PROTECT).
`test_cleanup_engine.py`: render_markdown_config_driven 10 (PROTECT) · render_markdown_rule_separates_subsequent_parts 10 · sort_chapters_stable_long_ids 10 · rules_built_from_config 10 (PROTECT) · build_user_content_appends_reference_conditional 8 · strip_preamble_removes_known_lead 9 · build_batch_requests_skips_cached 10 · **build_batch_requests_appends_dictionary_context_when_flagged 6 (CONSOLIDATE — shape-only "REFERENCE" membership; fold into skips_cached as flags-present param, assert the context content)** · reconcile_flags_keeps_surviving 10 · reconcile_flags_skips_when_missing 9 · regen_guard_blocks_existing 10 · regen_guard_allows_with_kwarg_or_env 9 · regen_guard_inert_without_output 8 · run_refuses_to_clobber_clean_md 8 · run_without_reconciled_typed_missing 10 · no_pll_string_leaks_in_prompt 10 (PROTECT) · correct_prompt_carries_real_book_identity 9 (PROTECT) · cleanup_runs_deterministically_synthetic 10 (PROTECT) · cleanup_llm_path_drives_chat_seam 10 (PROTECT) · cleanup_llm_failure_degrades 10 (PROTECT) · cleanup_cache_wins_over_fresh 10.
`test_cleanup_neutrality.py`: no_italian_or_source_noise_literal 10 (PROTECT) · scan_excludes_docstrings_finds_real_leaks 10 (PROTECT).

### 8.3 Core-steps: reconcile / validate / triage (48 tests — 47 KEEP, 1 CONSOLIDATE, 0 CUT)
`test_reconcile_engine.py`: score_word_exact_values 10 · **score_word_prefers_cleaner_witness 5 (CONSOLIDATE — arithmetically subsumed by exact-values)** · score_word_accent_set_is_seam 9 (PROTECT) · align_paragraphs_equal_replace_insert_delete 10 · align_paragraphs_insert_delete_none_pads 9 · reconcile_words_2way_merges 10 · 3way_unanimous_keeps_text 8 *(low-regression: shadowed by `elif n1==n2`)* · 3way_two_of_three_majority 10 · 3way_copy1_copy3_agreement 10 · 3way_all_differ 10 · is_near_duplicate_short_strings 9 · is_near_duplicate_identical_distinct 9 · is_near_duplicate_window_merged 10 · strip_page_markers_removes_and_maps 10 · split_paragraphs_heals_breaks 10 · split_merged_chapters_recovers 10 · split_raw_chapters_structural_markers 10 (PROTECT) · running_head_drop_is_config 9 (PROTECT) · reconcile_end_to_end_synthetic 10 (PROTECT) · reconcile_two_way_without_copy3 10 (PROTECT) · reconcile_output_satisfies_validate_word_count 10 (PROTECT).
`test_validate_engine.py`: chapter_count_reads_declared_structure 10 · char_coverage_reads_set_and_threshold 10 · coverage_set_honours_toggles 9 (PROTECT) · no_ascii_remnants_reads_page_marker 9 · no_ascii_remnants_flags_uppercase_digit 9 · word_count_preservation_reads_floor 10 · word_count_preservation_fails_closed_on_zero 10 · no_empty_chapters_flags_short 9 · quote_balance_detects_imbalance 9 (PROTECT) · word_quality_high_severity_reads_ceiling 10 · mid_word_noise_unreachable_faithful 9 · word_quality_capitalised_cluster_not_high 10 · run_without_clean_text_returns_error 10 · validate_runs_on_synthetic_book 10 (PROTECT).
`test_triage_engine.py`: plausibility_requires_both_strings 9 · plausibility_accepts_near_rejects_drift 9 · resolution_passes_map_every_branch 10 · medium_confidence_auto_accepted 10 · build_witnesses_lists_sources_then_copy3 10 · user_message_blocks_every_item 9 · apply_resolutions_idempotent 10 · apply_resolutions_occurrence_safe 10 · synthetic_triage_resolves_and_mutates 10 (PROTECT) · triage_no_needs_items_noop 10 · triage_without_flagged_segments_missing_input 10 · no_pll_string_leaks_synthetic 10 (PROTECT) · real_book_render_carries_identity 7 (PROTECT).

### 8.4 Roundtrip (63 tests — 59 KEEP, 4 CONSOLIDATE, 0 CUT)
`test_roundtrip.py`: hash_raw_is_sha256_utf8 10 · **hash_raw_distinguishes_and_is_deterministic 5 (CONSOLIDATE)** · reconstruct_raw_recovers_slice 9 · reconstruct_raw_byte_exact_nonascii 10 · reconstruct_raw_empty_slice 8 · reconstruct_raw_raises_on_hash_mismatch 10 · reconstruct_raw_raises_oob 10 · reconstruct_raw_bounds_guard_beats_hash 10 · apply_forward_folds_in_order 8 · apply_inverse_reverses_order 10 · **is_reversible_true 5 (CONSOLIDATE)** · is_reversible_false_lossy 10 · verify_atom_roundtrip_raw_only 8 · verify_atom_roundtrip_reversible 10 · verify_atom_roundtrip_raises_no_text 10 · verify_atom_roundtrip_raises_lossy 10 · verify_atom_roundtrip_gates_raw_first 10 · norm_layer_label_does_not_fake_floor 7 · **public_exports_resolve 5 (CONSOLIDATE)**.
`test_roundtrip_real_input.py` (all PROTECT): frozen_page_round_trips 10 · span_of_real_pages 8 · drift_fails_the_floor 9 · page_map_tiles_zero_loss 8 · negative_overlapping_span 9 · negative_dropped_page 9 · negative_uncovered_content 9.
`test_roundtrip_gate.py` (mutation-proven file): gap emit ordered 9 · emit leading/trailing 10 · rejects oob 10 · rejects overlap 10 · rejects non-ws silent-loss 10 · rejects trailing non-ws 10 · gap_record width mismatch 10 · gap_record non-ws text 10 · reconstruct rebuilds whole 9 · rebuilds with edge gaps 9 · rejects undeclared gap 10 · rejects overlap 10 · rejects out-of-order 10 · trailing shortfall shows in gate 9 · text_drift_per_atom_vs_whole 10 · **wholesale_passes_body_dominates 5 (CONSOLIDATE)** · wholesale_raises_all_excluded 9 · wholesale_raises_below_fraction 9 · wholesale_exempts_all_ws 9 · wholesale_floor_tunable 10 · production_roundtrip_returns_declared_gaps 7 · production_roundtrip_raises_silent_loss 8.
`test_roundtrip_gate_real_input.py` (all PROTECT): copy1/2 reconstruct 10 · copy3 furniture clears floor 10 · real overlap 9 · real dropped atom 9 · real text drift 10 · real implicit gap 9 · canonical out-of-scope tripwire 8 · real wholesale exclusion 9.
`test_roundtrip_gate_closure.py` (all PROTECT): each_witness_reconstructs_through_store 10 · witness_iteration_via_stream_ids 10 · canonical_loads_and_resolves 10 · stream_ids_empty_before_save 8 · back_door_read_negative 10 · store_overlap_through_read_path 9 · store_implicit_gap_through_read_path 9.

### 8.5 Raw-capture + divergence (37 tests — 34 KEEP, 2 CONSOLIDATE, 0 CUT)
`test_raw_capture.py`: capture_witness_tiles_and_round_trips 9 · preserves_multiline_paragraph 10 · furniture_captured_with_role 10 · defaults_all_body_unmapped 9 · tiles_raises_overlap 10 · tiles_raises_oob 10 · tiles_raises_silent_loss 10 · tiles_accepts_ws_gaps 9 · align_streams_matches_equal 9 · align_streams_marks_insert_delete 10 *(only insert exercised — see §5.4)* · **align_streams_normalizes_case_ws 4 (CONSOLIDATE — cannot red, §3.2)** · build_canonical_every_atom_derived 8 · build_canonical_links_both_witnesses 10 · build_canonical_single_witness 10 · build_canonical_secondary_only 10 (PROTECT) · canonical_atom_round_trips_primary 10 · canonical_adopts_primary_page 10 (PROTECT) · build_canonical_excludes_furniture 10 · build_canonical_requires_two 10 · build_canonical_rejects_more_than_two 10 · align_streams_owns_junk_policy 9 · junk_policy_guard_discriminates 10 (PROTECT) · **public_exports_resolve 5 (CONSOLIDATE)**.
`test_raw_capture_real_input.py` (all PROTECT): copy3_segments_tiles_zero_loss 10 · copy3_furniture_count_binds_oracle 10 · copy3_pages_attributed 10 · copy1_copy2_tile_page_unmapped 9 · real_overlap_fails 9 · real_dropped_atom_silent_loss 9 · real_canonical_every_atom_derived 10 · real_canonical_page_unmapped_until_s7_1b 10 · align_streams_pins_autojunk_real_scale 10.
`test_divergence_ledger.py`: real_ledger_is_coherent 7 *(near-vacuous, subsumed)* · format_template_lines_not_counted 10 · validator_accepts_well_formed_dl 10 (PROTECT) · validator_rejects_missing_golden_cite 10 · validator_rejects_non_sequential_ids 10. *(Gap: only DL kind tested — §5.3.)*

### 8.6 Structure-handles + artifacts + errors (70 fns / 51 entries — 40 KEEP, 8 CONSOLIDATE, 0 CUT)
`test_structure_handles.py` — CONSOLIDATE: `clean_policies_validate` 6, `clean_aliases_validate` 6, `opaque_node_id_not_a_substring_validates_clean` 6, `handle_surface_is_exported` 6. All others KEEP 7–10 (render formats/scope/disambiguation/accent, inv19 policy resolution, inv6 derivation arms, inv18 alias integrity + temporal, resolve default/miss/reguard/at_revision, inv9 handle-change, hygiene blanks). See raw reviewer output for the full 40-row list; nearly every one is pinned by a distinct b4 mutant.
`test_structure_artifacts.py` — CONSOLIDATE: `each_layer_has_independent_positive_int_version[×3]` 5, `s4_stale_class_is_a_nonempty_exported_string[×2]` 4, `the_three_versions_are_independently_addressable` 6, `all_public_exports_resolve_on_the_package` 6. KEEP: atoms_dir_under_data 10, structure_map_at_work_root 10, relations_at_work_root 10, three_artifact_locations_distinct 7, all_stale_classes_pairwise_distinct 9, no_relation_named_export_beyond_inert_set 8, public_export_surface_is_bounded 10, schema_status_marks_provisional 10.
`test_structure_errors.py` — all KEEP: ec_set_is_exactly_closed 10 · ec_values_equal_names 9 · ec_member_is_wire_token 10 · no_duplicate_value_aliases 8 · special_buckets_match_partition 10 · four_buckets_partition 10 · tier_2b_explicit_complement 9 · validator_codes_are_2a_plus_2b 9.

### 8.7 Infra + neutrality (66 tests — 64 KEEP, 2 CONSOLIDATE, 0 CUT)
`test_smoke.py`: package_imports_has_version 7 · unported_step_stub_run 7 · ported_step_real_run 7 · cli_parser_builds 8 · cli_main_no_step_noop 10 · cli_step_without_book 10 · cli_list_books_no_book 10 · cli_resolves_then_stub 10 · cli_unknown_book_config_error 10 · registry_unknown_language 10 · cli_unknown_language_exit_1 10 · collect_step_opts_only_set 9 · collect_step_opts_empty 7 · accepted_opts_filters_by_signature 9 · cli_engine_error_maps_exit_code 10.
`test_workspace.py`: areas_under_work_tree 9 · ensure_creates_three_areas 8 · resolve_returns_inside 8 · resolve_rejects_unknown_area 10 · resolve_rejects_traversal 10 (PROTECT) · resolve_rejects_absolute 10 · resolve_root_at_work_root 9 · resolve_root_rejects_traversal 9 · resolve_root_rejects_absolute 8 · resolve_root_no_parts 10 · resolve_rejects_symlink_escape 10 (PROTECT) · resolve_root_rejects_symlink_escape 9 (PROTECT).
`test_isolation.py` (all PROTECT, all 10): validate / reconcile / download / ocr / triage / adjudicate / cleanup leave_live_tree_untouched.
`test_invariants_controls.py` (both PROTECT, 10): hashseed_independent · governance_docs_cite_resolvable_names.
`test_assets.py`: frequency_dict_resolves 8 (PROTECT) · period_dicts_resolve 8 (PROTECT) · require_asset_missing_file_typed 10 · require_asset_missing_dir_typed 9 · require_asset_kind_mismatch 9 · require_asset_returns_resolved 7 · spacy_model_installed 7 (PROTECT) · load_spacy_caches 9 · load_spacy_missing_model_actionable 10 · **load_spacy_real_model_returns_pipeline 5 (CONSOLIDATE — isinstance-only @integration; strengthen to assert lang=="it")**.
`test_block_classifier.py`: stub_classifies_unknown 8 · stub_output_corresponds 9 · stub_honestly_incomplete 10 (PROTECT) · stub_on_empty 9 · seam_is_injectable 10 (PROTECT) · **unknown_sentinel_distinct_nonempty 6 (CONSOLIDATE)** · classification_frozen 9 · classification_rejects_anonymous_typed_by 10 · public_exports_resolve 7.
`test_core_neutrality.py`: engine_src_has_py_files 7 (PROTECT) · no_book_or_typeface_opinion 10 (PROTECT) · guard_catches_planted_literal 10 (PROTECT).
`test_structure_neutrality.py`: structure_src_has_py_files 7 (PROTECT) · no_language_literal_in_structure_core 10 (PROTECT) · guard_catches_planted_literal 10 (PROTECT).
`test_templating.py`: template_profile_resident_loadable 9 · load_missing_template_clean_error 10 · build_prompt_context_namespaced 10 · strict_undefined_raises 10 · synthetic_fixture_non_pll_facts 10 (PROTECT) · no_pll_string_leaks_synthetic 10 (PROTECT).

### 8.8 Structure-projection + typed + tiers (79 tests — 70 KEEP, 9 CONSOLIDATE, 0 CUT)
`test_structure_projection.py` — CONSOLIDATE: `container_and_leaf_distinct_variants` 6, `nodes_store_children_not_parent` 5, `nodes_and_map_frozen` 6, `sequence_fields_normalize_to_tuples` 5, `structure_validation_error_is_exported` 6, `correct_split_validates_clean` 5. KEEP (10 unless noted): base_map_validates_clean 8, duplicate_node_id_rejected 10, duplicate_node_id_short_circuits 10, atom_heading_and_body_double_ownership 10, atom_slot_and_furniture_double_ownership 10, same_atom_two_leaves 9, duplicate_furniture_not_double 8, duplicate_heading_not_double 7, excluded_repeated_owned_excluded_once 9, unowned_included_raises 10, unowned_excluded_furniture_passes 8, excluded_in_slot_owned_excluded 10, empty_container_raises 10, container_only_heading_not_empty 8, body_atoms_out_of_order 10, body_atoms_intra_dup 10, body_atoms_ascending_noncontiguous 8, ragged_depth_validates 8, flat_table_by_node_id 10, collect_all_multiple_violations 10, structure_validation_error_contract 10, leaf_empty_identity_rejected 7, container_empty_identity_rejected 7, furniture_empty_fields_rejected 7, empty_root_id_rejected 7, mint_takes_no_content_arg 10, mint_deterministic 8, mint_human_machine_distinct 9, mint_rejects_unknown_authority 8, container_minted_by_machine_split 10, leaf_minted_by_human_split 10, blank_minted_by_split 10, node_id_matching_cheat_derived 10, opaque_id_with_designation_title_clean 8, minted_ids_survive_derivation 7, node_id_survives_round_trip 10, node_id_independent_of_content 10, node_id_stable_positional_move 9, position_derived_id_position_dependent 10, collect_all_identity_codes 10.
`test_typed_projection.py` — CONSOLIDATE: `typed_projection_on_empty_is_empty` 6, `typed_records_are_frozen` 6, `public_exports_resolve` 6. KEEP: pairs_in_source_order 10, rejects_count_mismatch 10, degenerate_stub_fails_completeness 7, all_unknown_degenerate 10, boundary_class_unknown_hard_fails 10, body_leaf_unknown_routes_review 10, fully_typed_complete 8, empty_vacuously_complete 9 (PROTECT), resolved_boundary_no_fail 8 (PROTECT), degenerate_precedes_boundary 9, boundary_accepts_iterable 8, excluded_furniture_exempt 10 (PROTECT), all_excluded_vacuously_complete 10 (PROTECT), real_capture_degenerate_under_stub 10 (PROTECT), runs_over_canonical_stream 10 (PROTECT), preserves_typed_by_confidence 10, retyping_new_projection 10, rejects_too_many_classifications 10 (PROTECT), accepts_generator_classifier 9, boundary_rejects_bare_str 10 (PROTECT), boundary_accepts_generator 8, multiple_body_leaf_unknowns_routed 10 (PROTECT), multiple_boundary_unknowns_named 10 (PROTECT), real_capture_routes_body_leaf 10 (PROTECT), single_atom_outcome_table 10 (PROTECT).
`test_structure_tiers.py` (all PROTECT): fixture_writes_back_byte_exact 10 · committed_fixture_byte_exact_to_generator 10 · fixture_schema_version_binds_live 9 · artifact_locations_distinct_contained 9 · negative_drifted_version_fails 10.

### 8.9 Resource + config (65 tests — 62 KEEP, 3 CONSOLIDATE, 0 CUT)
`test_resource_lineage.py` — CONSOLIDATE: `resource_lineage_schema_version_is_positive_int` 4. All others KEEP 9–10 (resource/normalizer version independence + tracking, reorder-invariance incl. dup-name total-order, per-member hash localization, fail-loud on absent chunk / missing index / malformed index[×5], canonical round-trip + key-order independence, sha256 NIST KAT, chunk-order stability, filename-rename tracking, every-chunk-contributes, case-fold mode differences M10/M11, case-before-accent M3, wire values pinned). Full 34-row list in raw reviewer output.
`test_resource_neutrality.py` (all PROTECT): `s3_0_modules_exist` 6 (CONSOLIDATE — anti-vacuity meta-guard, keep) · no_resource_literal 9 · guard_catches_planted_literal 9.
`test_config_loader.py` — all KEEP 9–10: resolves_real_pll_constants (PROTECT), cleanup_accented_letters_full_set, schema_rejects_missing_field, schema_rejects_wrong_type, prompt_context_requires_ocr_keys, prompt_context_extensible (PROTECT), override_replaces_field, missing_book_clean_error, language_id_mismatch, bibliographic_drift_rejected, missing_edition_year_schema_first, missing_profile_ref, profile_schema_guards_builder, override_validated_after_merge, override_replaces_list_wholesale, source_noise_schema, typeface_schema, malformed_coverage, requires_monolingual_dict, case_fold_required, case_fold_enum_rejects_unknown, case_fold_enum_accepts_all (PROTECT), unimplemented_consistent_language_reaches_unknown. *(Lever: the 5-test required-field family → §4.1.)*
`test_sidecar_contracts.py`: sidecar_well_formed 7 · book_page_offset_invariant 9 · offset_matches_manifest_leaf 9 · content_chapter_ids_resolve 10 (PROTECT) · **reconciled_chapters_well_formed 6 (CONSOLIDATE — shape-only)**.

### 8.10 Atoms / atom_store / markers (79 tests — ~68 KEEP, ~10 CONSOLIDATE, 1 CUT)
`test_atom_store.py` — **CUT**: `addressing_fields_round_trip_as_tuples` 3 (§3.1). CONSOLIDATE: `absent_geom_round_trips_as_absent` 6, `reference_integrity_passes_when_all_resolve` 6, `assert_atom_hashes_passes_on_valid_capture` 6. All others KEEP 9–10 (witness/canonical round-trip, present-geom, mixed-ws gap bytes-not-width (PROTECT), scope-split envelope, save path + dir-create, load missing-file, from_json stale schema/class/key/kind/model-invariant/non-object/wrong-typed, id-filename mismatch, whole-artifact anchor drift/dropped-gap/compensated/canonical-corruption/stale-hash, canonical/witness construct guards, flat-id security guard ×2 entry points, dup atom_id in-memory + persisted, non-finite geom, invented-coords-on-absent). 31 of 41 named killers in `mutate_atom_store.py`.
`test_atom_store_real_input.py` (all PROTECT): real_witness_round_trips 9 · real_copy3_furniture 9 · real_text_drift_fails 10 · real_canonical_reference_integrity 9 · real_canonical_dangling_backlink 9.
`test_atoms.py` — CONSOLIDATE: `atom_sequence_fields_are_tuples` 6 *(shape-only but CAN red — the load-bearing sibling of the cut test)*, `public_exports_resolve` 6, **`duplicate_atom_ids_empty_on_empty_stream` 5 (cannot-red, §3.3)**. KEEP: geom_shape_frozen 10, geom_absent_first_class 10, geom_present_full_provenance 8, geom_absent_no_coords 10, geom_present_carries_coords 10, geom_bbox_four_floats 9, geom_present_bbox_is_tuple 7, geom_is_frozen 10, witness_atom_full_l1 9, canonical_atom_derivations 9, atom_is_frozen 10, atom_is_hashable 10, atom_raw_span_pair 9, atom_page_range_pair 9, atom_rejects_oov_scope 10, derivation_frozen 10, dup_ids_empty_when_unique 8, dup_ids_detects_planted 10, dup_ids_reports_each_once 10, atom_ids_unique_generated 8.
`test_atomic_writes.py`: atomic_write_roundtrips_no_tmp 10 · atomic_write_failure_no_partial 10 · **steps_have_python_files 6 (CONSOLIDATE — anti-vacuity meta-guard, PROTECT, keep)** · no_raw_artifact_writes_in_steps 10 · detector_catches_pathlib_open_write 10 (PROTECT).
`test_markers.py` (all KEEP 10): page_marker_roundtrip · regex_derived_from_template · marker_no_match_non_marker · sentinels_are_wire_literals · wire_literals_single_sourced.

---

*Generated by a 10-reviewer fan-out under `engine/docs/probes/`. Raw per-reviewer outputs (with full per-row flags/reasoning) are in the session task transcripts.*
