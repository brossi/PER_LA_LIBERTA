"""Mutant table for the S2.1.3 matcher + geometry sidecar (issue #37).

Run with the mutation-hunt runner:

    python3 ~/.claude/skills/mutation-hunt/hunt.py \
        --table tests/hunts/hunt_geom_match.py --artifact <scratch>/hunt37.json

One mutant per named G-row violation minimum (the plan's §4 red column), plus the ruled-constant
pins (P-2/P-4/P-5) and the page-locate DP's internal machinery (band centering, incremental theta,
suffix query, activation compensation) — the "incremental-update invariant" the plan assigns to
the mutation pass. TEST_CMD uses the engine venv's python directly (same rationale as
hunt_geometry_backend.py); the runner pins purge + bytecode hygiene itself.
"""
from pathlib import Path

REPO = str(Path(__file__).resolve().parents[2])
TEST_CMD = [str(Path(REPO) / ".venv" / "bin" / "python"), "-m", "pytest", "{scope}",
            "-q", "--no-header", "-x", "-p", "no:cacheprovider"]
TIMEOUT = 300

M = "src/engine/structure/geom_match.py"
S = "src/engine/structure/geom_sidecar.py"
TM = "tests/unit/test_geom_match.py"
TS = "tests/unit/test_geom_sidecar.py"


def m(label, old, new, test_id, file=M, tests=TM):
    return {"label": label, "file": file, "old": old, "new": new,
            "scope": f"{tests}::{test_id}"}


MUTANTS = [
    # --- normalizer (DT-8: NFC / edge strip / casefold each load-bearing) ---
    m("norm-nfc-dropped",
      '    for raw in unicodedata.normalize("NFC", text).split():',
      "    for raw in text.split():",
      "test_normalizer_pipeline_nfc_split_edge_strip_casefold"),
    m("norm-casefold-dropped",
      "            out.append(raw[start:end].casefold())",
      "            out.append(raw[start:end])",
      "test_normalizer_pipeline_nfc_split_edge_strip_casefold"),
    m("norm-edge-strip-dropped",
      "        while start < end and not raw[start].isalnum():",
      "        while False:",
      "test_normalizer_pipeline_nfc_split_edge_strip_casefold"),
    # --- page-locate: bands (P-2 / DT-3 positioning) ---
    m("p2-band-multiplier-drifted",
      "BAND_BAG_MULTIPLIER = 3",
      "BAND_BAG_MULTIPLIER = 30",
      "test_locate_band_multiplier_is_the_ruled_p2_value"),
    m("band-center-uniform-not-ratio",
      "        center = round(n_tokens * cum / total) if total else round(n_tokens * p / k)",
      "        center = round(n_tokens * p / k)",
      "test_locate_band_positions_by_cumulative_token_ratio"),
    # --- page-locate: DP machinery (the incremental-update invariant, G-7 objective) ---
    m("theta-gain-range-widened",
      "                    theta = plist[idx + m - 1] if idx + m - 1 < len(plist) else nhi",
      "                    theta = plist[idx + m] if idx + m < len(plist) else nhi",
      "test_locate_matches_the_brute_force_reference_on_random_streams"),
    # (Two earlier mutants here — suffix_max(nlo) and an activation-compensation drop — SURVIVED
    # the first hunt run and were dispositioned EQUIVALENT: activation strictly precedes any add
    # that could touch the position, so both belts were dead code. The compensation was removed
    # from the module; these two replace them with real bug classes in the same machinery.)
    m("suffix-query-excludes-empty-window",
      "                cur[c] = struct.suffix_max(c)",
      "                cur[c] = struct.suffix_max(c + 1)",
      "test_locate_matches_the_brute_force_reference_on_random_streams"),
    m("add-range-bleeds-below-the-sweep",
      "        jlo = max(0, plo - self.lo)",
      "        jlo = 0",
      "test_locate_matches_the_brute_force_reference_on_random_streams"),
    m("forward-walk-ignores-previous-boundary",
      "        for c in range(c_prev, hi_c + 1):",
      "        for c in range(lo_c, hi_c + 1):",
      "test_locate_matches_the_brute_force_reference_on_random_streams"),
    m("g7-tie-break-flipped-to-latest",
      "            if best_total is None or total_score > best_total:",
      "            if best_total is None or total_score >= best_total:",
      "test_locate_tie_break_takes_the_earliest_boundary_exactly"),
    # --- matcher: G-4 / G-5 / G-6 / G-24 / P-4 ---
    m("g4-invented-box-on-zero-match",
      "            if matched == 0:\n"
      "                record = AtomRecord(status=ATOM_UNMATCHED, match_confidence=confidence, reason=REASON_ZERO_MATCH)",
      "            if matched == 0:\n"
      "                record = AtomRecord(status=ATOM_MATCHED, match_confidence=confidence, page=pg.page, "
      "bbox=(0.0, 0.0, pg.width, pg.height), match_method=MATCH_METHOD)",
      "test_zero_match_atom_writes_absent_never_an_invented_box"),
    m("g5-confidence-constant",
      "            confidence = (matched / total) if total else 0.0",
      "            confidence = 1.0 if matched else 0.0",
      "test_match_confidence_is_matched_over_total_pinned_by_value"),
    m("zero-token-division-guard-dropped",
      "            confidence = (matched / total) if total else 0.0",
      "            confidence = matched / total",
      "test_tokenless_atom_is_addressed_and_zero_matched"),
    m("g6-union-over-all-page-boxes",
      "                x0 = min(pg.words[b].bbox[0] for b in consumed)\n"
      "                y0 = min(pg.words[b].bbox[1] for b in consumed)\n"
      "                x1 = max(pg.words[b].bbox[2] for b in consumed)\n"
      "                y1 = max(pg.words[b].bbox[3] for b in consumed)",
      "                x0 = min(w.bbox[0] for w in pg.words)\n"
      "                y0 = min(w.bbox[1] for w in pg.words)\n"
      "                x1 = max(w.bbox[2] for w in pg.words)\n"
      "                y1 = max(w.bbox[3] for w in pg.words)",
      "test_union_bbox_spans_matched_boxes_only"),
    m("g24-consumption-dropped",
      "                    cursor[t] = at + 1",
      "                    cursor[t] = at",
      "test_repeated_phrase_cannot_double_bind"),
    m("g24-canonical-sort-skipped",
      "    return sorted(range(len(page.words)), key=key)",
      "    return list(range(len(page.words)))",
      "test_output_is_invariant_to_backend_emission_order"),
    m("p4-floor-drifted",
      "MIN_DISTINCTIVE_TOKENS = 3",
      "MIN_DISTINCTIVE_TOKENS = 1",
      "test_distinctive_floor_is_the_ruled_p4_value_and_page_unique_rescues"),
    m("p4-page-unique-rescue-dropped",
      "            elif matched < MIN_DISTINCTIVE_TOKENS and not has_page_unique:",
      "            elif matched < MIN_DISTINCTIVE_TOKENS:",
      "test_distinctive_floor_is_the_ruled_p4_value_and_page_unique_rescues"),
    m("bag-admits-multi-token-boxes",
      "            keys.append(norm[0] if len(norm) == 1 else None)",
      "            keys.append(norm[0] if norm else None)",
      "test_unusable_boxes_never_enter_the_bag"),
    m("cross-page-assignment-takes-last-not-majority",
      "            assigned_idx = max(overlaps, key=lambda item: item[1])[0]",
      "            assigned_idx = overlaps[-1][0]",
      "test_cross_page_atom_assigned_to_majority_page_earliest_on_tie"),
    # --- G-12: routed page writes nothing (matcher side; the model side is in S below) ---
    m("g12-routed-page-writes-tentative-records",
      "            page_records[pg.page] = PageRecord(\n"
      "                status=PAGE_ROUTED, stage=\"match\", signal=\"match-rate\", value=rate, dropped_boxes=dropped\n"
      "            )",
      "            page_records[pg.page] = PageRecord(\n"
      "                status=PAGE_ROUTED, stage=\"match\", signal=\"match-rate\", value=rate, dropped_boxes=dropped\n"
      "            )\n"
      "            atom_records.update(tentative)",
      "test_routed_page_atoms_stay_pending_not_written_absent", tests=TS),
    # --- G-3: provenance fields hardcoded (two independent mutants) ---
    m("g3-engine-id-hardcoded",
      "                geometry_engine=sidecar.engine_id,",
      '                geometry_engine="engine-hardcoded",',
      "test_matched_geom_carries_all_configured_provenance_verbatim"),
    m("g3-witness-id-hardcoded",
      "                matched_witness_id=sidecar.witness_id,",
      '                matched_witness_id="copy1",',
      "test_matched_geom_carries_all_configured_provenance_verbatim"),
    # --- attach: G-15 binding, pending state, G-20/G-25 canonical resolution ---
    m("g15-witness-binding-skipped",
      "        _check_binding(sidecar, stream)",
      "        pass",
      "test_stream_source_hash_mismatch_is_stale_fail_loud", tests=TS),
    m("g15-canonical-binding-skipped",
      "        _check_binding(sidecar, witness_stream)",
      "        pass",
      "test_stream_source_hash_bind_runs_in_canonical_mode_too", tests=TS),
    m("pending-reported-as-unmatched",
      "    if status == PAGE_ROUTED:\n"
      "        return Geom.absent(), AttachOutcome(status=OUTCOME_PENDING)",
      "    if status == PAGE_ROUTED:\n"
      "        return Geom.absent(), AttachOutcome(status=OUTCOME_UNMATCHED)",
      "test_routed_page_atoms_stay_pending_not_written_absent", tests=TS),
    m("g20-canonical-direct-id-lookup",
      "            return _witness_geom(derivations[0].atom_id, sidecar)",
      "            return _witness_geom(atom.atom_id, sidecar)",
      "test_canonical_attach_resolves_through_derived_from_not_id"),
    m("g20-multi-primary-picks-first",
      "            if len(derivations) > 1:",
      "            if False:",
      "test_canonical_multi_primary_is_unmatched_never_union_or_first_pick"),
    m("g25-ineligible-reported-as-zero-match",
      "                    status=OUTCOME_INELIGIBLE, reason=REASON_NO_PRIMARY_DERIVATION",
      '                    status=OUTCOME_UNMATCHED, reason="zero_match"',
      "test_no_primary_derivation_is_ineligible_never_a_match_failure"),
    m("g25-ineligible-counted-as-match-failure",
      '        "atoms_unmatched_on_accepted_pages": sum(\n'
      "            1 for r in outcome.atoms.values() if r.status == ATOM_UNMATCHED\n"
      "        ),",
      '        "atoms_unmatched_on_accepted_pages": sum(\n'
      "            1 for r in outcome.atoms.values() if r.status == ATOM_UNMATCHED\n"
      "        ) + no_primary,",
      "test_canonical_coverage_counters_count_by_cause"),
    # --- sidecar model: G-12 structural + closed reason enum (G-25's persistence face) ---
    m("g12-model-scope-guard-dropped",
      "            if self.pages[assigned].status != PAGE_MATCHED:",
      "            if False:",
      "test_atom_record_on_a_routed_page_is_unconstructible", file=S, tests=TS),
    m("unmatched-reason-enum-opened",
      "            if self.reason not in UNMATCHED_REASONS:",
      "            if self.reason is None:",
      "test_atom_record_rejects_malformed_shapes", file=S, tests=TS),
    # --- loader totality (G-18) ---
    m("g18-version-check-dropped",
      "    if version != GEOM_SIDECAR_SCHEMA_VERSION:",
      "    if False:",
      "test_loader_rejects_stale_version_and_wrong_class", file=S, tests=TS),
    m("g18-stale-class-check-dropped",
      "    if stale_class != GEOM_SIDECAR_STALE_CLASS:",
      "    if False:",
      "test_loader_rejects_stale_version_and_wrong_class", file=S, tests=TS),
    # --- G-19: generation + replay fingerprints ---
    m("g19-generation-guard-dropped",
      '        if old_scan.get("sha256") != new.sha256 or old_scan.get("n_pages") != new.n_pages:',
      "        if False:",
      "test_regeneration_over_a_different_scan_fails_loud", file=S, tests=TS),
    m("g19-replay-page-count-clause-dropped",
      "    if recorded.sha256 != sha256 or recorded.n_pages != n_pages:",
      "    if recorded.sha256 != sha256:",
      "test_replay_fingerprint_check", file=S, tests=TS),
    # --- G-26: tripwire legs, constants, scope ---
    m("g26-leg-a-dropped",
      "    if absent_mass_rate > TRIPWIRE_ABSENT_MASS_MAX:",
      "    if False:",
      "test_tripwire_leg_a_fires_on_absent_token_mass", file=S, tests=TS),
    m("g26-leg-b-dropped",
      "    if prose_absent_rate > TRIPWIRE_PROSE_ABSENT_RATE_MAX:",
      "    if False:",
      "test_tripwire_leg_b_fires_on_prose_absent_rate", file=S, tests=TS),
    m("g26-leg-a-bar-raised",
      "TRIPWIRE_ABSENT_MASS_MAX = 0.02",
      "TRIPWIRE_ABSENT_MASS_MAX = 0.5",
      "test_tripwire_constants_are_the_ruled_p5_values", file=S, tests=TS),
    m("g26-leg-b-bar-raised",
      "TRIPWIRE_PROSE_ABSENT_RATE_MAX = 0.05",
      "TRIPWIRE_PROSE_ABSENT_RATE_MAX = 0.5",
      "test_tripwire_constants_are_the_ruled_p5_values", file=S, tests=TS),
    m("g26-prose-scope-drifted",
      "TRIPWIRE_PROSE_MIN_TOKENS = 4",
      "TRIPWIRE_PROSE_MIN_TOKENS = 1",
      "test_tripwire_constants_are_the_ruled_p5_values", file=S, tests=TS),
    m("g26-denominator-counts-pending-atoms",
      "    absent_mass_rate = (absent_mass / total_mass) if total_mass else 0.0",
      "    total_mass = sum(token_counts.values())\n"
      "    absent_mass_rate = (absent_mass / total_mass) if total_mass else 0.0",
      "test_tripwire_scope_is_accepted_pages_only", file=S, tests=TS),
    m("g26-missing-counts-accepted",
      "    missing = [a for a in sidecar.atoms if a not in token_counts]",
      "    missing = []",
      "test_tripwire_requires_counts_for_every_record_bearing_atom", file=S, tests=TS),
    # --- serialization determinism (G-24's byte-stability + #40's idempotent replay substrate) ---
    m("to-json-atoms-unsorted",
      '        "atoms": {a: _atom_record_to_json(sidecar.atoms[a]) for a in sorted(sidecar.atoms)},',
      '        "atoms": {a: _atom_record_to_json(sidecar.atoms[a]) for a in sidecar.atoms},',
      "test_to_json_is_a_pure_function_of_content_not_insertion_order", file=S, tests=TS),
    # ==== added in the post-audit remediation (two-lens findings; Rule-A delta) ====
    # --- scan page numbers, never page indices (coverage finding 1) ---
    m("page-key-is-index-not-scan-number",
      "            page_records[pg.page] = PageRecord(status=PAGE_MATCHED, match_rate=rate, dropped_boxes=dropped)",
      "            page_records[p_idx + 1] = PageRecord(status=PAGE_MATCHED, match_rate=rate, dropped_boxes=dropped)",
      "test_scan_page_numbers_flow_through_never_page_indices"),
    m("record-page-is-index-not-scan-number",
      "                    page=pg.page,",
      "                    page=p_idx + 1,",
      "test_scan_page_numbers_flow_through_never_page_indices"),
    m("window-pages-are-indices-not-scan-numbers",
      "            first=pages[first_idx].page, last=pages[last_idx].page, assigned=pages[assigned_idx].page",
      "            first=first_idx + 1, last=last_idx + 1, assigned=assigned_idx + 1",
      "test_scan_page_numbers_flow_through_never_page_indices"),
    # --- DT-8 page gate: token-mass weighting + >= boundary (coverage findings 2/4) ---
    m("rate-is-atom-mean-not-token-mass",
      "        rate = (matched_sum / total_sum) if total_sum else 0.0",
      "        rate = (sum(r.match_confidence for _, r in tentative) / len(tentative)) if tentative else 0.0",
      "test_page_rate_is_token_mass_weighted_not_an_atom_mean"),
    m("accept-boundary-made-strict",
      "        if rate >= page_accept_rate:",
      "        if rate > page_accept_rate:",
      "test_page_accepts_at_exactly_the_accept_rate"),
    # --- P-4 floor boundary (coverage finding 3) ---
    m("p4-floor-boundary-off-by-one",
      "            elif matched < MIN_DISTINCTIVE_TOKENS and not has_page_unique:",
      "            elif matched <= MIN_DISTINCTIVE_TOKENS and not has_page_unique:",
      "test_distinctive_floor_binds_at_exactly_three_matched_without_page_unique"),
    # --- canonical sort degraded to a same-row tie (coverage finding 6) ---
    m("sort-key-degraded-to-y0",
      "        return (y0, x0, x1, y1, page.words[i].text)",
      "        return (y0,)",
      "test_output_is_invariant_to_backend_emission_order"),
    # --- G-3's remaining fields at attach (coverage finding 5) ---
    m("attach-confidence-hardcoded",
      "                match_confidence=record.match_confidence,",
      "                match_confidence=1.0,",
      "test_matched_geom_carries_all_configured_provenance_verbatim"),
    m("attach-bbox-hardcoded",
      "                bbox=record.bbox,",
      "                bbox=(1.0, 1.0, 2.0, 2.0),",
      "test_matched_geom_carries_all_configured_provenance_verbatim"),
    # --- contiguity pin (drift finding 2) ---
    m("consecutive-check-weakened-to-increasing",
      "    if any(b != a + 1 for a, b in zip(page_numbers, page_numbers[1:])):",
      "    if any(b <= a for a, b in zip(page_numbers, page_numbers[1:])):",
      "test_match_stream_rejects_bad_inputs"),
    # --- default band width + upper edge (coverage finding 9) ---
    m("band-width-from-smallest-bag",
      "    width = band_tokens if band_tokens is not None else max(1, BAND_BAG_MULTIPLIER * max(sizes))",
      "    width = band_tokens if band_tokens is not None else max(1, BAND_BAG_MULTIPLIER * min(sizes))",
      "test_locate_default_band_is_the_ruled_width_of_the_largest_bag"),
    m("band-upper-edge-shaved",
      "        bands.append((max(0, center - half), min(n_tokens, center + half)))",
      "        bands.append((max(0, center - half), min(n_tokens, center + half - 1)))",
      "test_locate_default_band_is_the_ruled_width_of_the_largest_bag"),
    # --- unmeasured canonical counters stay null (drift finding 6) ---
    m("unmeasured-counters-flattened-to-zero",
      "    no_primary: int | None = None\n"
      "    multi_primary: int | None = None",
      "    no_primary: int | None = 0\n"
      "    multi_primary: int | None = 0",
      "test_unmeasured_canonical_counters_persist_as_null_not_zero", tests=TS),
    # --- loader totality: the full wrap set (drift finding 1) ---
    m("loader-wrap-narrowed-to-json-errors",
      "        data = read_json(path)\n"
      "    except (json.JSONDecodeError, OSError, UnicodeDecodeError, RecursionError) as exc:",
      "        data = read_json(path)\n"
      "    except json.JSONDecodeError as exc:",
      "test_loader_wraps_non_utf8_bytes_as_stale_not_a_traceback", file=S, tests=TS),
    # --- tripwire boundary + warn tier (coverage findings 7/13) ---
    m("g26-leg-a-boundary-inclusive",
      "    if absent_mass_rate > TRIPWIRE_ABSENT_MASS_MAX:",
      "    if absent_mass_rate >= TRIPWIRE_ABSENT_MASS_MAX:",
      "test_tripwire_leg_a_boundary_does_not_fire_at_exactly_the_max", file=S, tests=TS),
    m("g26-leg-b-boundary-inclusive",
      "    if prose_absent_rate > TRIPWIRE_PROSE_ABSENT_RATE_MAX:",
      "    if prose_absent_rate >= TRIPWIRE_PROSE_ABSENT_RATE_MAX:",
      "test_tripwire_leg_b_boundary_does_not_fire_at_exactly_the_max", file=S, tests=TS),
    m("warn-band-mass-drifted",
      "TRIPWIRE_WARN_BAND_MASS = 0.01",
      "TRIPWIRE_WARN_BAND_MASS = 0.5",
      "test_tripwire_constants_are_the_ruled_p5_values", file=S, tests=TS),
    m("band-edge-shrunk-drops-ten-to-fallback",
      '_BANDS = (("<=3", 1, TRIPWIRE_PROSE_MIN_TOKENS - 1), ("4-10", TRIPWIRE_PROSE_MIN_TOKENS, 10), (">10", 11, None))',
      '_BANDS = (("<=3", 1, TRIPWIRE_PROSE_MIN_TOKENS - 1), ("4-10", TRIPWIRE_PROSE_MIN_TOKENS, 9), (">10", 11, None))',
      "test_tripwire_band_edges_and_top_histogram_bin_are_exact", file=S, tests=TS),
    # --- strict record keys + recursive canonicalization (drift findings 7b/4) ---
    m("unknown-record-keys-accepted",
      "    if unknown:",
      "    if False:",
      "test_loader_rejects_unknown_record_keys_never_field_loss", file=S, tests=TS),
    m("nested-canonicalization-unsorted",
      "        return {k: _canonical_json(value[k]) for k in sorted(value)}",
      "        return {k: _canonical_json(value[k]) for k in value}",
      "test_to_json_canonicalizes_nested_payloads_too", file=S, tests=TS),
    # --- generation guard's fingerprintless branch (coverage finding 16) ---
    m("fingerprintless-existing-guard-dropped",
      "        if not isinstance(old_scan, Mapping):",
      "        if False:",
      "test_regeneration_over_a_fingerprintless_file_refuses", file=S, tests=TS),
]
