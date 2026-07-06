"""S2.1.6 #40 — human-review worklist + verdict CLI + volume bound (``s2_1_plan.md`` DT-10).

Homes: G-13 (review fraction > ``review_fraction_max`` per stage → hard fail), G-14 (verdict
application total; unknown action fails loud), G-22 (worklist replay: idempotent re-apply +
stale-fingerprint verdict refused and re-routed). The records make the DT-10 worklist schema
(``{page, stage, signal, value, threshold, tentative, verdict}``, stable id, input fingerprint)
constructible only in its valid shape; the behavioral tests drive ``build_worklist`` /
``assert_review_within_bound`` / the verdict application directly.

Red-first: every assertion here was seen failing (module absent, then each guard mutated) before
its green. See ``tests/hunts/hunt_review.py`` for the mutation table.
"""
from __future__ import annotations

import pytest

from engine.errors import MissingInputError, StaleArtifactError
from engine.paths import BookWorkspace
from engine.structure.geometry import GeometryError
from engine.structure.geom_review import (
    REVIEW_FRACTION_MAX_DEFAULT,
    WORKLIST_SCHEMA_VERSION,
    WORKLIST_STAGES,
    WORKLIST_STALE_CLASS,
    RouteInput,
    Worklist,
    WorklistCandidate,
    assert_review_within_bound,
    build_worklist,
    candidate_id,
    input_fingerprint,
    load_worklist,
    save_worklist,
    worklist_path,
    worklist_from_json,
    worklist_to_json,
)

FP = "sha256:fingerprint-sentinel"


def route(page, stage="density", *, signal="band-margin", value=0.012, threshold=0.02, tentative=None):
    return RouteInput(
        page=page,
        stage=stage,
        signal=signal,
        value=value,
        threshold=threshold,
        tentative=tentative if tentative is not None else {"box_count": 658, "token_count": 7},
    )


def build(routes, *, witness_id="copy1", n_pages=278, review_fraction_max=0.15, fingerprint=FP):
    return build_worklist(
        routes,
        witness_id=witness_id,
        n_pages=n_pages,
        review_fraction_max=review_fraction_max,
        fingerprint=fingerprint,
    )


# --- fingerprint: a pure function of every binding input (DT-9/DT-10) ---------------------- #


def _fp(**overrides):
    kwargs = dict(
        stream_source_hash="sha256:stream",
        source_scan_sha256="sha256:scan",
        engine_id="pymupdf-1+tesseract-5:dpi=300:lang=ita",
        classifier_version="density-bands-v1",
        policy_values={"decision_threshold": 0.5, "hysteresis_margin": 0.15, "review_fraction_max": 0.15},
    )
    kwargs.update(overrides)
    return input_fingerprint(**kwargs)


def test_input_fingerprint_is_a_pure_function_of_its_inputs():
    assert _fp() == _fp()  # same inputs → same hash (idempotent replay depends on this)
    assert _fp().startswith("sha256:")


@pytest.mark.parametrize(
    "overrides",
    [
        {"stream_source_hash": "sha256:other"},
        {"source_scan_sha256": "sha256:other"},
        {"engine_id": "pymupdf-9:dpi=150:lang=eng"},
        {"classifier_version": "density-bands-v2"},
        {"policy_values": {"decision_threshold": 0.6, "hysteresis_margin": 0.15, "review_fraction_max": 0.15}},
        {"policy_values": {"decision_threshold": 0.5, "hysteresis_margin": 0.15, "review_fraction_max": 0.10}},
    ],
)
def test_input_fingerprint_changes_when_any_binding_input_changes(overrides):
    # G-22's stale-guard rests on this: a verdict taken under different inputs must not match.
    assert _fp(**overrides) != _fp()


def test_policy_values_order_does_not_change_the_fingerprint():
    a = _fp(policy_values={"decision_threshold": 0.5, "hysteresis_margin": 0.15})
    b = _fp(policy_values={"hysteresis_margin": 0.15, "decision_threshold": 0.5})
    assert a == b  # canonical over content, not dict insertion order


# --- candidate id + record shape ---------------------------------------------------------- #


def test_candidate_id_is_the_stable_dt10_template():
    assert candidate_id("copy1", 6, "density") == "copy1:p0006:density"
    assert candidate_id("copy1", 278, "match") == "copy1:p0278:match"


@pytest.mark.parametrize(
    "kwargs, phrase",
    [
        (dict(stage="bogus"), "stage must be one of"),
        (dict(page=0), "positive scan page"),
        (dict(value=float("nan")), "finite"),
        (dict(threshold=float("inf")), "finite"),
        (dict(signal=""), "signal"),
        (dict(input_fingerprint=""), "fingerprint"),
    ],
)
def test_worklist_candidate_rejects_malformed_fields(kwargs, phrase):
    base = dict(
        id="copy1:p0006:density",
        page=6,
        stage="density",
        signal="band-margin",
        value=0.012,
        threshold=0.02,
        input_fingerprint=FP,
        tentative={"box_count": 658},
    )
    base.update(kwargs)
    with pytest.raises(ValueError, match=phrase):
        WorklistCandidate(**base)


def test_worklist_candidate_id_must_match_its_page_and_stage():
    with pytest.raises(ValueError, match="id must be"):
        WorklistCandidate(
            id="copy1:p9999:density",  # disagrees with page=6
            page=6,
            stage="density",
            signal="band-margin",
            value=0.012,
            threshold=0.02,
            input_fingerprint=FP,
            tentative={},
        )


# --- build_worklist ----------------------------------------------------------------------- #


def test_build_worklist_emits_one_candidate_per_routed_page():
    wl = build([route(6), route(47, stage="columns", signal="valley-confidence", value=0.55, threshold=0.5)])
    assert isinstance(wl, Worklist)
    assert [c.id for c in wl.candidates] == ["copy1:p0006:density", "copy1:p0047:columns"]
    assert all(c.input_fingerprint == FP for c in wl.candidates)
    assert all(c.verdict is None and c.history == () for c in wl.candidates)


def test_build_worklist_is_deterministic_in_page_then_stage_order():
    # Emission order is a pure function of (page, stage), independent of input order.
    a = build([route(47, stage="columns"), route(6, stage="density"), route(6, stage="match", value=0.79, threshold=0.8)])
    assert [c.id for c in a.candidates] == [
        "copy1:p0006:density",
        "copy1:p0006:match",
        "copy1:p0047:columns",
    ]


def test_build_worklist_empty_is_a_valid_empty_worklist():
    wl = build([])
    assert wl.candidates == ()
    assert wl.witness_id == "copy1"


def test_build_worklist_rejects_duplicate_page_stage_routes():
    # One candidate per (page, stage) — the id is (page, stage)-derived and is the verdicts-dict key,
    # so a duplicate would collide ids and (with a stable sort) make emission order input-dependent.
    # A front-end emitting a gate twice for a page is malformed → fail loud, never silently absorbed.
    with pytest.raises(ValueError, match="duplicate route"):
        build([route(6, stage="density", signal="A"), route(6, stage="density", signal="B")])


# --- volume bound (G-13): review_fraction_max per stage, hard-fail ------------------------- #


def test_review_within_bound_passes_under_quota():
    # 2 density routes / 100 pages = 0.02 ≤ 0.15 — fine.
    assert_review_within_bound([route(6), route(7)], n_pages=100, review_fraction_max=0.15)


def test_review_fraction_over_quota_hard_fails_naming_the_stage():
    # 3 density routes / 10 pages = 0.30 > 0.15 → the automation premise failed.
    routes = [route(1), route(2), route(3)]
    with pytest.raises(GeometryError, match="density"):
        assert_review_within_bound(routes, n_pages=10, review_fraction_max=0.15)


def test_volume_bound_is_per_stage_not_aggregate():
    # 2 density + 2 columns over 10 pages: aggregate 0.40 > 0.15, but NO single stage exceeds
    # 0.20 — a per-stage bound of 0.25 must PASS (the aggregate would wrongly fail here). Then a
    # third density route (0.30) trips density alone.
    ok = [route(1), route(2), route(3, stage="columns"), route(4, stage="columns")]
    assert_review_within_bound(ok, n_pages=10, review_fraction_max=0.25)
    with pytest.raises(GeometryError, match="density"):
        assert_review_within_bound([*ok, route(5)], n_pages=10, review_fraction_max=0.25)


def test_volume_bound_boundary_is_inclusive():
    # Exactly at the bound is tolerated (`>` not `>=`): 3/20 = 0.15 passes; 4/20 = 0.20 fails.
    at = [route(i) for i in range(1, 4)]
    assert_review_within_bound(at, n_pages=20, review_fraction_max=0.15)
    with pytest.raises(GeometryError, match="0.20|density"):
        assert_review_within_bound([route(i) for i in range(1, 5)], n_pages=20, review_fraction_max=0.15)


def test_build_worklist_enforces_the_volume_bound():
    # build_worklist routes through the same guard — an over-quota run never produces a worklist.
    with pytest.raises(GeometryError, match="density"):
        build([route(1), route(2), route(3)], n_pages=10, review_fraction_max=0.15)


def test_review_fraction_max_default_is_the_ruled_p6_value():
    # Value-pin (P-6, RULED 2026-07-03): 0.15 per stage. A silent drift re-opens the budget.
    assert REVIEW_FRACTION_MAX_DEFAULT == 0.15


def test_worklist_stages_are_the_four_dt10_gates():
    assert WORKLIST_STAGES == ("density", "columns", "locate", "match")


# --- save / load round-trip + loader totality (G-18 posture) ------------------------------ #


@pytest.fixture
def workspace(tmp_path):
    return BookWorkspace.for_book("geombook", tmp_path).ensure()


def test_worklist_round_trips_through_json(workspace):
    wl = build([route(6), route(47, stage="columns", signal="valley-confidence", value=0.55, threshold=0.5)])
    path = save_worklist(workspace, wl)
    assert path == worklist_path(workspace)
    loaded = load_worklist(workspace)
    assert loaded == wl


def test_worklist_to_json_is_byte_stable(workspace):
    # Idempotent replay (G-22) rests on canonical serialization.
    wl = build([route(47, stage="columns", value=0.55, threshold=0.5), route(6)])
    assert json.dumps(worklist_to_json(wl), sort_keys=True) == json.dumps(worklist_to_json(wl), sort_keys=True)
    assert worklist_to_json(wl)["schema_version"] == WORKLIST_SCHEMA_VERSION
    assert worklist_to_json(wl)["stale_class"] == WORKLIST_STALE_CLASS


def test_load_absent_worklist_is_missing_input(workspace):
    with pytest.raises(MissingInputError):
        load_worklist(workspace)


def test_load_wrong_schema_version_is_stale(workspace):
    wl = build([route(6)])
    data = worklist_to_json(wl)
    data["schema_version"] = 99
    with pytest.raises(StaleArtifactError, match="schema version"):
        worklist_from_json(data)


def test_load_unknown_key_is_stale():
    wl = build([route(6)])
    data = worklist_to_json(wl)
    data["surprise"] = True
    with pytest.raises(StaleArtifactError, match="unknown key"):
        worklist_from_json(data)


def test_load_wrong_stale_class_is_stale():
    wl = build([route(6)])
    data = worklist_to_json(wl)
    data["stale_class"] = "geometry-sidecar"
    with pytest.raises(StaleArtifactError, match="stale_class"):
        worklist_from_json(data)


# =============================================================================================== #
# Verdict application (G-14 totality, G-22 replay) + the tracked verdicts file + the CLI.
# =============================================================================================== #

import json  # noqa: E402  (grouped with the verdict-suite additions)

from engine.structure.geom_review import (  # noqa: E402
    ACTION_DECLINE_GEOMETRY,
    OUTCOME_DECLINED,
    OUTCOME_REENTERED,
    VERDICT_ACTIONS,
    VERDICTS_STALE_CLASS,
    apply_declines_to_sidecar,
    apply_verdicts,
    load_verdicts,
    main,
    record_verdict,
    save_verdicts,
    validate_verdict,
    verdict_outcome,
    verdicts_path,
    verdicts_to_json,
)
from engine.structure.geom_sidecar import (  # noqa: E402
    PAGE_DECLINED,
    PAGE_ROUTED,
    GeomSidecar,
    PageRecord,
    SourceScan,
)


def verdict(action=ACTION_DECLINE_GEOMETRY, *, by="ben", at="2026-07-06T10:00:00Z", params=None, fingerprint=FP):
    v = {"action": action, "by": by, "at": at, "params": params if params is not None else {}}
    if fingerprint is not None:
        v["input_fingerprint"] = fingerprint
    return v


# --- G-14: verdict_outcome is total; unknown action fails loud ---------------------------------- #


def test_verdict_actions_are_the_four_dt10_actions():
    assert VERDICT_ACTIONS == ("confirm", "redraw_split", "reclassify", "decline_geometry")


def test_verdict_outcome_maps_decline_to_declined():
    assert verdict_outcome(verdict(action="decline_geometry")) == OUTCOME_DECLINED


@pytest.mark.parametrize("action", ["confirm", "redraw_split", "reclassify"])
def test_verdict_outcome_maps_reentry_actions_to_reentered(action):
    assert verdict_outcome(verdict(action=action)) == OUTCOME_REENTERED


def test_verdict_outcome_unknown_action_fails_loud():
    with pytest.raises(GeometryError, match="unknown verdict action"):
        verdict_outcome(verdict(action="delete_everything"))


def test_verdict_outcome_missing_action_fails_loud():
    with pytest.raises(GeometryError, match="unknown verdict action"):
        verdict_outcome({"by": "ben", "at": "t", "input_fingerprint": FP, "params": {}})


@pytest.mark.parametrize(
    "drop",
    ["by", "at", "input_fingerprint"],
)
def test_validate_verdict_requires_provenance(drop):
    v = verdict()
    del v[drop]
    with pytest.raises(GeometryError, match=drop):
        validate_verdict(v)


def test_validate_verdict_accepts_a_well_formed_verdict():
    validate_verdict(verdict())  # no raise


# --- G-22: apply_verdicts projection, idempotent, stale-guarded --------------------------------- #


def test_apply_verdicts_applies_a_matching_fingerprint_verdict():
    wl = build([route(230, stage="match", value=0.5, threshold=0.8)])
    applied, stats = apply_verdicts(wl, {"copy1:p0230:match": verdict()})
    (c,) = applied.candidates
    assert c.verdict == verdict()
    assert c.history == ()
    assert stats["applied"] == 1 and stats[OUTCOME_DECLINED] == 1


def test_apply_verdicts_open_candidate_is_unchanged():
    wl = build([route(6)])
    applied, stats = apply_verdicts(wl, {})  # no verdicts yet
    (c,) = applied.candidates
    assert c.verdict is None and c.history == ()
    assert stats["open"] == 1


def test_apply_verdicts_is_idempotent():
    wl = build([route(230, stage="match", value=0.5, threshold=0.8), route(6)])
    verdicts = {"copy1:p0230:match": verdict()}
    once, _ = apply_verdicts(wl, verdicts)
    twice, _ = apply_verdicts(once, verdicts)  # re-apply on an already-applied worklist
    assert worklist_to_json(once) == worklist_to_json(twice)  # byte-identical (G-22)


def test_apply_verdicts_removing_a_verdict_reopens_the_candidate():
    # The projection is a pure function of the CURRENT verdicts, not accumulated state: deleting a
    # verdict from the tracked file and re-applying must reopen the candidate — a verdict never gets
    # stuck on it. (Guards the project-from-base reset, which same-verdict idempotency can't see.)
    wl = build([route(230, stage="match", value=0.5, threshold=0.8)])
    applied, _ = apply_verdicts(wl, {"copy1:p0230:match": verdict()})
    assert applied.candidates[0].verdict is not None
    reopened, stats = apply_verdicts(applied, {})  # the human deleted the verdict
    assert reopened.candidates[0].verdict is None and stats["open"] == 1


def test_apply_verdicts_stale_fingerprint_is_refused_and_retained():
    wl = build([route(230, stage="match", value=0.5, threshold=0.8)])  # candidate fp == FP
    stale = verdict(fingerprint="sha256:OLD-inputs")  # authored under different inputs
    applied, stats = apply_verdicts(wl, {"copy1:p0230:match": stale})
    (c,) = applied.candidates
    assert c.verdict is None  # refused — the page re-routes as a fresh open record
    assert c.history == (stale,)  # old verdict retained as evidence, never silently re-applied
    assert stats["stale"] == 1 and stats["applied"] == 0


def test_apply_verdicts_unknown_action_propagates_fail_loud():
    wl = build([route(230, stage="match", value=0.5, threshold=0.8)])
    with pytest.raises(GeometryError, match="unknown verdict action"):
        apply_verdicts(wl, {"copy1:p0230:match": verdict(action="rm_rf")})


def test_apply_verdicts_ignores_verdicts_for_absent_candidates():
    # A verdict whose id is not in the current worklist (its page no longer routes) is not applied
    # — it cannot fabricate a candidate. It is reported so it is never silently dropped.
    wl = build([route(6)])
    applied, stats = apply_verdicts(wl, {"copy1:p0999:match": verdict()})
    assert all(c.verdict is None for c in applied.candidates)
    assert stats["orphaned"] == 1


# --- G-14 concrete: decline_geometry → the page's geometry declines ----------------------------- #


def _routed_sidecar(page=230):
    return GeomSidecar(
        witness_id="copy1",
        stream_source_hash="sha256:stream",
        source_scan=SourceScan(kind="pdf", sha256="sha256:scan", n_pages=278, n_bytes=1234),
        backend_params={"dpi": 300},
        engine_id="pymupdf-1+tesseract-5:dpi=300:lang=ita",
        locate_method="monotone-align-v1",
        pages={page: PageRecord(status=PAGE_ROUTED, stage="match", signal="match-rate", value=0.5)},
        atoms={},
        atom_pages={},
        coverage=dict.fromkeys(
            ("pages_locate_failed", "atoms_unmatched_on_accepted_pages",
             "canonical_no_primary_derivation", "canonical_multi_primary_derivation"), 0
        ),
    )


def test_apply_declines_to_sidecar_declines_the_routed_page():
    sidecar = _routed_sidecar(230)
    wl = build([route(230, stage="match", value=0.5, threshold=0.8)])
    applied, _ = apply_verdicts(wl, {"copy1:p0230:match": verdict()})
    new = apply_declines_to_sidecar(sidecar, applied)
    assert new.pages[230].status == PAGE_DECLINED
    assert new.pages[230].verdict["action"] == "decline_geometry"


def test_apply_declines_leaves_non_decline_pages_routed():
    sidecar = _routed_sidecar(230)
    wl = build([route(230, stage="match", value=0.5, threshold=0.8)])
    applied, _ = apply_verdicts(wl, {"copy1:p0230:match": verdict(action="confirm")})
    new = apply_declines_to_sidecar(sidecar, applied)
    assert new.pages[230].status == PAGE_ROUTED  # confirm re-enters via the runner, not a decline


# --- the tracked verdicts file (book-level review/, sibling of work/) --------------------------- #


@pytest.fixture
def book_dir(tmp_path):
    (tmp_path / "geombook" / "work").mkdir(parents=True)
    return tmp_path / "geombook"


def test_verdicts_path_is_the_tracked_review_sibling(book_dir):
    path = verdicts_path(book_dir)
    assert path == book_dir / "review" / "geometry_verdicts.json"
    assert "work" not in path.parts  # durable, never in the disposable tree (DT-10)


def test_load_absent_verdicts_is_empty_not_missing(book_dir):
    # Absent verdicts is the normal fresh state (no human has ruled yet) — a clean no-op apply,
    # NOT a MissingInputError.
    assert load_verdicts(book_dir) == {}


def test_verdicts_round_trip(book_dir):
    verdicts = {"copy1:p0230:match": verdict()}
    save_verdicts(book_dir, verdicts)
    assert load_verdicts(book_dir) == verdicts


def test_load_unknown_verdicts_key_is_stale(book_dir):
    data = verdicts_to_json({"copy1:p0230:match": verdict()})
    data["surprise"] = 1
    with pytest.raises(StaleArtifactError, match="unknown key"):
        from engine.structure.geom_review import verdicts_from_json

        verdicts_from_json(data)


def test_verdicts_to_json_carries_the_stale_class(book_dir):
    assert verdicts_to_json({})["stale_class"] == VERDICTS_STALE_CLASS


def test_record_verdict_stamps_the_candidate_fingerprint(book_dir):
    # The CLI stamps the current candidate's input_fingerprint so a later inputs change makes the
    # verdict stale (G-22). Given a worklist, record a decline for one candidate.
    workspace = BookWorkspace.for_book("geombook", book_dir.parent).ensure()
    wl = build([route(230, stage="match", value=0.5, threshold=0.8)])
    save_worklist(workspace, wl)
    path = record_verdict(book_dir, "copy1:p0230:match", action="decline_geometry", by="ben")
    assert path == verdicts_path(book_dir)
    stored = load_verdicts(book_dir)["copy1:p0230:match"]
    assert stored["input_fingerprint"] == FP and stored["by"] == "ben"
    assert stored["action"] == "decline_geometry"


def test_record_verdict_unknown_action_fails_loud(book_dir):
    workspace = BookWorkspace.for_book("geombook", book_dir.parent).ensure()
    save_worklist(workspace, build([route(230, stage="match", value=0.5, threshold=0.8)]))
    with pytest.raises(GeometryError, match="unknown verdict action"):
        record_verdict(book_dir, "copy1:p0230:match", action="nuke", by="ben")


# --- the CLI (S4.6b gate-CLI pattern) ----------------------------------------------------------- #


def _cli_book(tmp_path):
    workspace = BookWorkspace.for_book("geombook", tmp_path).ensure()
    save_worklist(workspace, build([route(230, stage="match", value=0.5, threshold=0.8), route(6)]))
    return tmp_path


def test_cli_apply_projects_and_reports(tmp_path, capsys):
    root = _cli_book(tmp_path)
    save_verdicts(root / "geombook", {"copy1:p0230:match": verdict()})
    rc = main(["--book", "geombook", "--books-dir", str(root), "apply"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "1 applied" in out or "applied 1" in out or "applied=1" in out


def test_cli_status_lists_open_candidates(tmp_path, capsys):
    root = _cli_book(tmp_path)
    rc = main(["--book", "geombook", "--books-dir", str(root), "status"])
    assert rc == 0
    assert "copy1:p0230:match" in capsys.readouterr().out


def test_cli_unknown_action_exits_13(tmp_path):
    root = _cli_book(tmp_path)
    save_verdicts(root / "geombook", {"copy1:p0230:match": verdict(action="halt_and_catch_fire")})
    rc = main(["--book", "geombook", "--books-dir", str(root), "apply"])
    assert rc == 13  # GeometryError.exit_code — fail loud, never silently guess (G-14)


# --- on-demand PNG overlays (DT-10) ------------------------------------------------------------- #

from engine.structure.geom_review import overlay_path, render_overlay  # noqa: E402


def test_overlay_path_is_under_work_output(workspace):
    path = overlay_path(workspace, 6)
    assert path == workspace.resolve("output", "geometry_review", "overlays", "page_0006.png")


def test_render_overlay_two_columns_produces_a_png(workspace, tmp_path):
    out = overlay_path(workspace, 47)
    boxes = [(50.0, 40.0, 260.0, 55.0), (330.0, 40.0, 540.0, 55.0), (50.0, 60.0, 260.0, 75.0)]
    result = render_overlay(width=612.0, height=792.0, boxes=boxes, split_x=300.0, out_path=out, dpi=72)
    assert result == out and out.is_file()
    data = out.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) > 100  # a real, non-trivial PNG


def test_render_overlay_single_column_without_a_split(workspace):
    out = overlay_path(workspace, 6)
    render_overlay(width=612.0, height=792.0, boxes=[(50.0, 40.0, 540.0, 55.0)], split_x=None, out_path=out, dpi=72)
    assert out.is_file() and out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_overlay_rejects_nonpositive_dimensions(workspace):
    out = overlay_path(workspace, 6)
    with pytest.raises(ValueError, match="positive"):
        render_overlay(width=0.0, height=792.0, boxes=[], split_x=None, out_path=out)


# --- page_order_qa: the S2.2 measurement feed (DT-12) ------------------------------------------- #

from types import SimpleNamespace  # noqa: E402

from engine.structure.geom_review import page_order_qa  # noqa: E402


def _box(text, x0, y0):
    return SimpleNamespace(text=text, bbox=(x0, y0, x0 + 40.0, y0 + 12.0))


def test_page_order_qa_is_one_when_detector_order_matches_the_witness():
    # Two columns: left reads "alfa bravo", right reads "charlie delta"; the witness reads them in
    # column order. The detector, given the correct split, recovers exactly that order → 1.0.
    boxes = [_box("alfa", 50, 40), _box("bravo", 50, 60), _box("charlie", 330, 40), _box("delta", 330, 60)]
    witness = ["alfa", "bravo", "charlie", "delta"]
    assert page_order_qa(witness, boxes, split_x=300.0) == pytest.approx(1.0)


def test_page_order_qa_drops_below_one_when_columns_interleave():
    # The SAME boxes read as a single column (split_x=None) interleave the rows across the columns
    # ("alfa charlie bravo delta"), so the witness's column order is NOT recovered.
    boxes = [_box("alfa", 50, 40), _box("bravo", 50, 60), _box("charlie", 330, 40), _box("delta", 330, 60)]
    witness = ["alfa", "bravo", "charlie", "delta"]
    assert page_order_qa(witness, boxes, split_x=None) < 1.0


def test_page_order_qa_normalizes_box_text_into_the_witness_token_space():
    # A box carrying two whitespace-separated words + punctuation normalizes to two witness tokens.
    boxes = [_box("Alfa, bravo", 50, 40)]
    assert page_order_qa(["alfa", "bravo"], boxes, split_x=None) == pytest.approx(1.0)
