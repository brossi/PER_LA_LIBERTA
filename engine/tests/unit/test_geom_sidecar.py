"""S2.1.3 #37 — sidecar greens: pending ≠ absent, binding, loader totality, tripwire.

Homes (``s2_1_plan.md`` §4): G-12 (routed page's atoms stay PENDING — no absent-write before
verdict), G-15 (``stream_source_hash`` mismatch → stale fail-loud), G-18 (loader totality on the
shared Missing/Stale taxonomy), G-19 (``source_scan`` fingerprint at generation and replay), G-26
(the P-5 two-leg auto-absent tripwire, value-pinned, with the never-fire-on-honest control).
Model-invariant tests make the forbidden states unconstructible; the behavioral tests drive the
real matcher through ``matchkit`` (fake-backend tier, DT-11)."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from engine.errors import MissingInputError, StaleArtifactError
from engine.paths import BookWorkspace
from engine.structure.geometry import GeometryError
from engine.structure.geom_match import (
    OUTCOME_DECLINED,
    OUTCOME_PENDING,
    attach_geometry,
    build_geom_sidecar,
    match_stream,
)
from engine.structure.geom_sidecar import (
    ATOM_MATCHED,
    ATOM_UNMATCHED,
    COVERAGE_KEYS,
    GEOM_SIDECAR_SCHEMA_VERSION,
    GEOM_SIDECAR_STALE_CLASS,
    TRIPWIRE_ABSENT_MASS_MAX,
    TRIPWIRE_PROSE_ABSENT_RATE_MAX,
    TRIPWIRE_PROSE_MIN_TOKENS,
    TRIPWIRE_WARN_BAND_MASS,
    AtomPages,
    AtomRecord,
    GeomSidecar,
    PAGE_DECLINED,
    PAGE_MATCHED,
    PAGE_ROUTED,
    PageRecord,
    SourceScan,
    assert_auto_absent_tripwire,
    assert_source_scan_matches,
    from_json,
    geom_sidecar_path,
    load_geom_sidecar,
    save_geom_sidecar,
    to_json,
    with_detector_fields,
)

SCAN = SourceScan(kind="pdf", sha256="scan-sentinel-hash", n_pages=9, n_bytes=1234)
VERDICT = {"action": "decline_geometry", "by": "reviewer", "at": "stamp"}


def matched_page(rate=0.9):
    return PageRecord(status=PAGE_MATCHED, match_rate=rate)


def routed_page(value=0.1):
    return PageRecord(status=PAGE_ROUTED, stage="match", signal="match-rate", value=value)


def matched_atom(page=1, confidence=0.9):
    return AtomRecord(
        status=ATOM_MATCHED, match_confidence=confidence, page=page,
        bbox=(1.0, 2.0, 3.0, 4.0), match_method="token-bow-v1",
    )


def unmatched_atom(reason="zero_match", confidence=0.0):
    return AtomRecord(status=ATOM_UNMATCHED, match_confidence=confidence, reason=reason)


def coverage(**overrides):
    base = dict.fromkeys(COVERAGE_KEYS, 0)
    base.update(overrides)
    return base


def mk_sidecar(pages=None, atoms=None, atom_pages=None, **overrides):
    kwargs = dict(
        witness_id="w-sentinel-3",
        stream_source_hash="sha256:aaaa",
        source_scan=SCAN,
        backend_params={"dpi": 217},
        engine_id="engine-sentinel-77",
        locate_method="monotone-align-v1",
        pages=pages if pages is not None else {1: matched_page()},
        atoms=atoms if atoms is not None else {"a0": matched_atom()},
        atom_pages=atom_pages if atom_pages is not None else {"a0": AtomPages(1, 1, 1)},
        coverage=coverage(),
    )
    kwargs.update(overrides)
    return GeomSidecar(**kwargs)


def routed_world(matchkit):
    """A real matcher run with one accepted and one routed page: the G-12 substrate."""
    stream = matchkit.witness_stream(["alfa bravo charlie", "xero yulu zeta"], ids=["good", "pend"])
    pages = [
        matchkit.page(1, ["alfa", "bravo", "charlie"]),
        matchkit.page(2, ["qq", "ww", "ee"]),
    ]
    outcome = match_stream(stream, pages, page_accept_rate=0.8, atom_match_floor=0.6)
    sidecar = build_geom_sidecar(
        outcome, source_scan=SCAN, backend_params={"dpi": 217}, engine_id="engine-sentinel-77"
    )
    return stream, sidecar


# --- record shapes: forbidden states unconstructible -------------------------------------- #


@pytest.mark.parametrize(
    "kwargs, phrase",
    [
        (dict(status="unknown"), "page status must be one of"),
        (dict(status=PAGE_MATCHED), "requires match_rate"),
        (dict(status=PAGE_MATCHED, match_rate=1.5), "requires match_rate"),
        (dict(status=PAGE_MATCHED, match_rate=0.9, stage="match"), "no routing fields"),
        (dict(status=PAGE_ROUTED, signal="s", value=0.1), "requires the stage"),
        (dict(status=PAGE_ROUTED, stage="match", value=0.1), "requires the signal"),
        (dict(status=PAGE_ROUTED, stage="match", signal="s"), "requires the finite signal value"),
        (dict(status=PAGE_ROUTED, stage="match", signal="s", value=float("nan")), "finite signal value"),
        (dict(status=PAGE_ROUTED, stage="match", signal="s", value=0.1, match_rate=0.5), "atoms are pending"),
        (dict(status=PAGE_DECLINED), "requires the non-empty human verdict"),
        (dict(status=PAGE_DECLINED, verdict={}), "requires the non-empty human verdict"),
        (dict(status=PAGE_DECLINED, verdict=VERDICT, stage="match"), "only its verdict"),
        (dict(status=PAGE_MATCHED, match_rate=0.9, dropped_boxes=-1), "dropped_boxes"),
    ],
)
def test_page_record_rejects_malformed_shapes(kwargs, phrase):
    with pytest.raises(ValueError, match=phrase):
        PageRecord(**kwargs)


@pytest.mark.parametrize(
    "kwargs, phrase",
    [
        (dict(status="pending", match_confidence=0.5), "atom status must be one of"),
        (dict(status=ATOM_MATCHED, match_confidence=1.2, page=1, bbox=(1, 2, 3, 4), match_method="m"),
         "match_confidence must be in"),
        (dict(status=ATOM_MATCHED, match_confidence=float("nan"), page=1, bbox=(1, 2, 3, 4), match_method="m"),
         "match_confidence must be in"),
        (dict(status=ATOM_MATCHED, match_confidence=0.9, bbox=(1, 2, 3, 4), match_method="m"),
         "requires its positive scan page"),
        (dict(status=ATOM_MATCHED, match_confidence=0.9, page=1, match_method="m"),
         "requires a four-float bbox"),
        (dict(status=ATOM_MATCHED, match_confidence=0.9, page=1, bbox=(3, 2, 1, 4), match_method="m"),
         "non-degenerate"),
        (dict(status=ATOM_MATCHED, match_confidence=0.9, page=1, bbox=(1, 2, float("inf"), 4), match_method="m"),
         "must be finite"),
        (dict(status=ATOM_MATCHED, match_confidence=0.9, page=1, bbox=(1, 2, 3, 4)),
         "requires its match_method"),
        (dict(status=ATOM_MATCHED, match_confidence=0.9, page=1, bbox=(1, 2, 3, 4), match_method="m",
              reason="zero_match"), "no unmatched reason"),
        (dict(status=ATOM_UNMATCHED, match_confidence=0.0), "reason must be one of"),
        (dict(status=ATOM_UNMATCHED, match_confidence=0.0, reason="no_primary_derivation"),
         "reason must be one of"),
        (dict(status=ATOM_UNMATCHED, match_confidence=0.0, reason="multi_primary_derivation"),
         "reason must be one of"),
        (dict(status=ATOM_UNMATCHED, match_confidence=0.0, reason="zero_match", bbox=(1, 2, 3, 4)),
         "never invented"),
    ],
)
def test_atom_record_rejects_malformed_shapes(kwargs, phrase):
    # The two attach-time reasons are deliberately inadmissible: persisting an eligibility outcome
    # as a match failure is the exact conflation G-25 forbids.
    with pytest.raises(ValueError, match=phrase):
        AtomRecord(**kwargs)


def test_atom_pages_window_must_contain_assigned():
    with pytest.raises(ValueError, match="first <= assigned <= last"):
        AtomPages(first=2, last=5, assigned=1)
    with pytest.raises(ValueError, match="positive scan page"):
        AtomPages(first=0, last=1, assigned=1)


def test_source_scan_rejects_malformed_fingerprints():
    with pytest.raises(ValueError, match="non-empty content hash"):
        SourceScan(kind="pdf", sha256=" ", n_pages=1, n_bytes=1)
    with pytest.raises(ValueError, match="n_pages must be a positive integer"):
        SourceScan(kind="pdf", sha256="x", n_pages=0, n_bytes=1)
    with pytest.raises(ValueError, match="non-empty discriminator"):
        SourceScan(kind="", sha256="x", n_pages=1, n_bytes=1)


# --- sidecar cross-record invariants (G-12 structural) ------------------------------------- #


def test_atom_record_on_a_routed_page_is_unconstructible():
    # G-12's structural form: an atom record whose assigned page is routed IS an absent-write
    # before the verdict — the model refuses to represent it.
    with pytest.raises(ValueError, match="atom records exist only on matched pages"):
        mk_sidecar(
            pages={1: matched_page(), 2: routed_page()},
            atoms={"a0": matched_atom(page=1), "p0": unmatched_atom()},
            atom_pages={"a0": AtomPages(1, 1, 1), "p0": AtomPages(2, 2, 2)},
        )


@pytest.mark.parametrize(
    "mutation, phrase",
    [
        (dict(atoms={"ghost": matched_atom()}), "no atom_pages window"),
        (dict(atoms={"a0": matched_atom(page=3)},
              pages={1: matched_page(), 3: matched_page()}), "disagree"),
        (dict(atom_pages={"a0": AtomPages(1, 2, 1)}), "no page record"),
        # the FIRST page of a straddler window unrecorded (the mirror of the case above)
        (dict(atoms={}, atom_pages={"a0": AtomPages(1, 2, 2)}, pages={2: matched_page()}),
         "no page record"),
        (dict(coverage={"pages_locate_failed": 0}), "coverage must carry exactly"),
        (dict(coverage=coverage(pages_locate_failed=-1)), "non-negative integer"),
        # None means "unmeasured" and only the two canonical counters may say it
        (dict(coverage=coverage(pages_locate_failed=None)), "non-negative integer"),
        (dict(coverage=coverage(atoms_unmatched_on_accepted_pages=None)), "non-negative integer"),
        (dict(witness_id="../evil"), "flat filename stem"),
        (dict(backend_params={}), "non-empty structured contract"),
        (dict(stream_source_hash=""), "non-empty source_hash anchor"),
    ],
)
def test_sidecar_cross_record_invariants(mutation, phrase):
    with pytest.raises(ValueError, match=phrase):
        mk_sidecar(**mutation)


# --- G-12 behavioral: pending is absence-from-records, never an absent write ---------------- #


def test_routed_page_atoms_stay_pending_not_written_absent(matchkit):
    stream, sidecar = routed_world(matchkit)
    assert sidecar.pages[2].status == PAGE_ROUTED
    assert sidecar.pages[2].stage == "match" and sidecar.pages[2].signal == "match-rate"
    # THE G-12 bind: the routed page's atom got no record of any kind — pending is absence.
    assert "pend" not in sidecar.atoms
    assert set(sidecar.atoms) == {"good"}
    # ...but it is still addressed (the DT-3 byproduct covers pending atoms too).
    assert sidecar.atom_pages["pend"].assigned == 2
    result = attach_geometry(stream, sidecar)
    assert result.outcomes["pend"].status == OUTCOME_PENDING
    assert not result.atoms[1].geom.present


def test_declined_page_atoms_surface_as_declined_at_attach(matchkit):
    stream, sidecar = routed_world(matchkit)
    declined = replace(
        sidecar,
        pages={1: sidecar.pages[1], 2: PageRecord(status=PAGE_DECLINED, verdict=VERDICT)},
    )
    result = attach_geometry(stream, declined)
    outcome = result.outcomes["pend"]
    assert outcome.status == OUTCOME_DECLINED
    assert outcome.status != OUTCOME_PENDING  # the four S5 states stay distinguishable
    assert not result.atoms[1].geom.present


# --- G-15: stream_source_hash binding ------------------------------------------------------- #


def test_stream_source_hash_mismatch_is_stale_fail_loud(matchkit):
    stream, sidecar = routed_world(matchkit)
    stale = replace(sidecar, stream_source_hash=sidecar.stream_source_hash[:-4] + "beef")
    with pytest.raises(StaleArtifactError, match="the stream changed since matching"):
        attach_geometry(stream, stale)


def test_stream_source_hash_bind_runs_in_canonical_mode_too(matchkit):
    stream, sidecar = routed_world(matchkit)
    canonical = matchkit.canonical_stream([("c0", "alfa bravo charlie", [("w-sentinel-3", "good")])])
    stale = replace(sidecar, stream_source_hash=sidecar.stream_source_hash[:-4] + "beef")
    with pytest.raises(StaleArtifactError, match="the stream changed since matching"):
        attach_geometry(canonical, stale, witness_stream=stream)
    # and the healthy path resolves through the same bind
    assert attach_geometry(canonical, sidecar, witness_stream=stream).outcomes["c0"].status == "matched"


def test_wrong_witness_stream_is_refused(matchkit):
    _, sidecar = routed_world(matchkit)
    other = matchkit.witness_stream(["alfa bravo charlie"], witness="w-other")
    with pytest.raises(StaleArtifactError, match="wrong sidecar for this stream"):
        attach_geometry(other, sidecar)


def test_attach_fails_loud_on_corrupt_correspondence(matchkit):
    # The two _witness_geom corruption branches: a stream atom the sidecar never addressed, and a
    # record-less atom on a *matched* page. Both are sidecar↔stream corruption — fail loud, never
    # a silent "pending".
    stream, sidecar = routed_world(matchkit)
    unaddressed = replace(
        sidecar, atom_pages={k: v for k, v in sidecar.atom_pages.items() if k != "pend"}
    )
    with pytest.raises(StaleArtifactError, match="no page attribution"):
        attach_geometry(stream, unaddressed)
    recordless = replace(sidecar, atoms={})
    with pytest.raises(StaleArtifactError, match="has no record yet sits on matched page"):
        attach_geometry(stream, recordless)


# --- persistence + loader totality (G-18) ---------------------------------------------------- #


@pytest.fixture
def workspace(tmp_path):
    return BookWorkspace.for_book("geombook", tmp_path).ensure()


def test_save_load_roundtrip_is_faithful(workspace, matchkit):
    _, sidecar = routed_world(matchkit)
    path = save_geom_sidecar(workspace, sidecar)
    assert path == geom_sidecar_path(workspace, "w-sentinel-3")
    loaded = load_geom_sidecar(workspace, "w-sentinel-3")
    assert to_json(loaded) == to_json(sidecar)
    assert loaded.pages[2].status == PAGE_ROUTED
    assert loaded.atom_pages["pend"].assigned == 2


def test_missing_sidecar_is_missing_input(workspace):
    with pytest.raises(MissingInputError, match="not found"):
        load_geom_sidecar(workspace, "w-sentinel-3")


def test_loader_rejects_non_json_and_non_object_documents(workspace):
    path = geom_sidecar_path(workspace, "w-sentinel-3")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not json {{", encoding="utf-8")
    with pytest.raises(StaleArtifactError, match="unloadable"):
        load_geom_sidecar(workspace, "w-sentinel-3")
    path.write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(StaleArtifactError, match="must be a JSON object"):
        load_geom_sidecar(workspace, "w-sentinel-3")


def test_loader_wraps_non_utf8_bytes_as_stale_not_a_traceback(workspace):
    # G-18's totality covers the full house wrap set — a present-but-undecodable file is
    # StaleArtifactError, never a raw UnicodeDecodeError (the gap atom_store still records).
    path = geom_sidecar_path(workspace, "w-sentinel-3")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\xff\xfe\x00garbage")
    with pytest.raises(StaleArtifactError, match="unloadable"):
        load_geom_sidecar(workspace, "w-sentinel-3")


def test_loader_rejects_stale_version_and_wrong_class(workspace, matchkit):
    _, sidecar = routed_world(matchkit)
    envelope = to_json(sidecar)
    with pytest.raises(StaleArtifactError, match="schema version"):
        from_json({**envelope, "schema_version": 99})
    with pytest.raises(StaleArtifactError, match="not a geometry sidecar"):
        from_json({**envelope, "stale_class": "atom-stream"})


@pytest.mark.parametrize(
    "key",
    ["schema_version", "stale_class", "witness_id", "stream_source_hash", "source_scan",
     "backend_params", "engine_id", "locate_method", "pages", "atoms", "atom_pages", "coverage"],
)
def test_loader_rejects_missing_required_keys(matchkit, key):
    _, sidecar = routed_world(matchkit)
    envelope = to_json(sidecar)
    del envelope[key]
    with pytest.raises(StaleArtifactError, match="missing required key"):
        from_json(envelope)


def test_loader_wraps_model_violations_as_stale(matchkit):
    _, sidecar = routed_world(matchkit)
    envelope = json.loads(json.dumps(to_json(sidecar)))
    # a persisted unmatched record carrying a bbox is invented geometry: corrupt data at the load
    # boundary, never a bare ValueError traceback
    envelope["atoms"]["good"] = {
        "status": "unmatched", "match_confidence": 0.0, "reason": "zero_match", "bbox": [1, 2, 3, 4],
    }
    with pytest.raises(StaleArtifactError, match="malformed geometry sidecar"):
        from_json(envelope)
    bad_pages = json.loads(json.dumps(to_json(sidecar)))
    bad_pages["pages"]["not-a-number"] = {"status": "matched", "match_rate": 0.9}
    with pytest.raises(StaleArtifactError, match="scan-page integers"):
        from_json(bad_pages)


def test_loader_rejects_unknown_record_keys_never_field_loss(matchkit):
    # A record carrying a key this schema version does not define is a wrong-era or corrupt file:
    # refused loud, never loaded with silent field loss. (n_cols/n_cols_source/order_qa ARE defined
    # on a page record at schema v2 — DT-12 — so an unknown key must be a genuinely-undefined one.)
    _, sidecar = routed_world(matchkit)
    with_page_extra = json.loads(json.dumps(to_json(sidecar)))
    with_page_extra["pages"]["1"]["mystery_field"] = 2
    with pytest.raises(StaleArtifactError, match="unknown key"):
        from_json(with_page_extra)
    with_atom_extra = json.loads(json.dumps(to_json(sidecar)))
    with_atom_extra["atoms"]["good"]["order_qa"] = 0.9  # order_qa is a PAGE field, never an atom key
    with pytest.raises(StaleArtifactError, match="unknown key"):
        from_json(with_atom_extra)
    # ...and the same at the envelope and source_scan levels, not only inside records
    with_envelope_extra = json.loads(json.dumps(to_json(sidecar)))
    with_envelope_extra["worklist"] = []
    with pytest.raises(StaleArtifactError, match="unknown key"):
        from_json(with_envelope_extra)
    with_scan_extra = json.loads(json.dumps(to_json(sidecar)))
    with_scan_extra["source_scan"]["dpi"] = 300
    with pytest.raises(StaleArtifactError, match="unknown key"):
        from_json(with_scan_extra)


def test_unmeasured_canonical_counters_persist_as_null_not_zero(workspace, matchkit):
    # DT-13's evidence honesty: routed_world builds WITHOUT a canonical stream, so the two
    # canonical counters are unmeasured — null, distinguishable from a measured 0, through the
    # full save/load round trip.
    _, sidecar = routed_world(matchkit)
    assert sidecar.coverage["canonical_no_primary_derivation"] is None
    assert sidecar.coverage["canonical_multi_primary_derivation"] is None
    save_geom_sidecar(workspace, sidecar)
    loaded = load_geom_sidecar(workspace, "w-sentinel-3")
    assert loaded.coverage["canonical_no_primary_derivation"] is None


def test_declined_page_and_straddler_window_round_trip(workspace):
    # The #40 substrate: a declined page's verdict payload and a first != last window must
    # survive persistence byte-faithfully (nothing in routed_world exercises either).
    sidecar = mk_sidecar(
        pages={1: PageRecord(status=PAGE_DECLINED, verdict=VERDICT), 2: matched_page()},
        atoms={"a0": matched_atom(page=2)},
        atom_pages={"a0": AtomPages(1, 2, 2)},
    )
    save_geom_sidecar(workspace, sidecar)
    loaded = load_geom_sidecar(workspace, "w-sentinel-3")
    assert to_json(loaded) == to_json(sidecar)
    assert loaded.pages[1].verdict == VERDICT
    window = loaded.atom_pages["a0"]
    assert (window.first, window.last, window.assigned) == (1, 2, 2)


def test_classifier_fields_round_trip_when_provided():
    sidecar = mk_sidecar(classifier_version="clf-sentinel-v9", classifier_params={"band": 0.5})
    reloaded = from_json(json.loads(json.dumps(to_json(sidecar))))
    assert reloaded.classifier_version == "clf-sentinel-v9"
    assert reloaded.classifier_params == {"band": 0.5}


def test_loader_rejects_id_filename_mismatch(workspace, matchkit):
    _, sidecar = routed_world(matchkit)
    path = geom_sidecar_path(workspace, "w-imposter")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(to_json(sidecar)), encoding="utf-8")
    with pytest.raises(StaleArtifactError, match="id mismatch"):
        load_geom_sidecar(workspace, "w-imposter")


def test_path_accessor_rejects_path_shaped_witness_ids(workspace):
    with pytest.raises(ValueError, match="flat filename stem"):
        geom_sidecar_path(workspace, "../evil")


# --- G-19: source_scan fingerprint at generation and replay ---------------------------------- #


def test_regeneration_with_the_same_scan_is_allowed(workspace, matchkit):
    _, sidecar = routed_world(matchkit)
    save_geom_sidecar(workspace, sidecar)
    save_geom_sidecar(workspace, sidecar)  # same inputs — the disposable artifact may regenerate
    assert load_geom_sidecar(workspace, "w-sentinel-3").source_scan == SCAN


def test_regeneration_over_a_different_scan_fails_loud(workspace, matchkit):
    _, sidecar = routed_world(matchkit)
    save_geom_sidecar(workspace, sidecar)
    drifted = replace(sidecar, source_scan=SourceScan(kind="pdf", sha256="other-scan", n_pages=9, n_bytes=1234))
    with pytest.raises(StaleArtifactError, match="scan changed under the sidecar"):
        save_geom_sidecar(workspace, drifted)
    shrunk = replace(sidecar, source_scan=SourceScan(kind="pdf", sha256=SCAN.sha256, n_pages=7, n_bytes=1234))
    with pytest.raises(StaleArtifactError, match="scan changed under the sidecar"):
        save_geom_sidecar(workspace, shrunk)


def test_regeneration_over_an_unreadable_sidecar_refuses(workspace, matchkit):
    _, sidecar = routed_world(matchkit)
    path = geom_sidecar_path(workspace, "w-sentinel-3")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("garbage{{", encoding="utf-8")
    with pytest.raises(StaleArtifactError, match="refusing to clobber"):
        save_geom_sidecar(workspace, sidecar)
    # the full wrap set on the save-side read too: a parse-depth bomb is unloadable, not a
    # bare RecursionError escaping the regen guard
    path.write_text("[" * 100_000, encoding="utf-8")
    with pytest.raises(StaleArtifactError, match="refusing to clobber"):
        save_geom_sidecar(workspace, sidecar)


def test_regeneration_over_a_fingerprintless_file_refuses(workspace, matchkit):
    # Valid JSON at the target but no source_scan to compare against: the guard cannot verify
    # scan identity, so it refuses rather than degrading to a clobber (or an AttributeError).
    _, sidecar = routed_world(matchkit)
    path = geom_sidecar_path(workspace, "w-sentinel-3")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"schema_version": 1}', encoding="utf-8")
    with pytest.raises(StaleArtifactError, match="carries no source_scan fingerprint"):
        save_geom_sidecar(workspace, sidecar)


def test_replay_fingerprint_check(matchkit):
    _, sidecar = routed_world(matchkit)
    assert_source_scan_matches(sidecar, sha256=SCAN.sha256, n_pages=SCAN.n_pages)  # healthy replay
    with pytest.raises(StaleArtifactError, match="drifted under the geometry sidecar"):
        assert_source_scan_matches(sidecar, sha256="other", n_pages=SCAN.n_pages)
    with pytest.raises(StaleArtifactError, match="drifted under the geometry sidecar"):
        assert_source_scan_matches(sidecar, sha256=SCAN.sha256, n_pages=SCAN.n_pages + 1)


# --- serialization determinism ---------------------------------------------------------------- #


def test_to_json_is_a_pure_function_of_content_not_insertion_order():
    pages = {1: matched_page(), 2: matched_page(0.8)}
    atoms = {"a0": matched_atom(1), "b1": matched_atom(2)}
    windows = {"a0": AtomPages(1, 1, 1), "b1": AtomPages(2, 2, 2)}
    forward = mk_sidecar(pages=pages, atoms=atoms, atom_pages=windows)
    backward = mk_sidecar(
        pages=dict(reversed(pages.items())),
        atoms=dict(reversed(atoms.items())),
        atom_pages=dict(reversed(windows.items())),
    )
    assert json.dumps(to_json(forward)) == json.dumps(to_json(backward))


def test_to_json_canonicalizes_nested_payloads_too():
    # The purity claim holds all the way down: a declined verdict's nested params and
    # backend_params values serialize identically whatever their insertion order (#40's
    # idempotent-replay substrate — verdicts are its payload).
    def world(verdict, params):
        return mk_sidecar(
            pages={1: matched_page(), 2: PageRecord(status=PAGE_DECLINED, verdict=verdict)},
            backend_params=params,
        )

    one = world(
        {"action": "decline_geometry", "by": "r", "at": "t", "params": {"a": 1, "b": 2}},
        {"dpi": 217, "opts": {"x": 1, "y": 2}},
    )
    other = world(
        {"at": "t", "by": "r", "params": {"b": 2, "a": 1}, "action": "decline_geometry"},
        {"opts": {"y": 2, "x": 1}, "dpi": 217},
    )
    assert json.dumps(to_json(one)) == json.dumps(to_json(other))


def test_schema_constants_are_pinned():
    assert GEOM_SIDECAR_SCHEMA_VERSION == 2  # bumped at #40 (DT-12: page-record detector fields)
    assert GEOM_SIDECAR_STALE_CLASS == "geometry-sidecar"


# --- schema v2: the detector fields (DT-12, the S2.2 order_qa feed) ------------------------ #


def test_matched_page_carries_detector_fields():
    rec = PageRecord(status=PAGE_MATCHED, match_rate=0.94, n_cols=2, n_cols_source="evidence", order_qa=0.91)
    assert (rec.n_cols, rec.n_cols_source, rec.order_qa) == (2, "evidence", 0.91)


@pytest.mark.parametrize(
    "kwargs, phrase",
    [
        (dict(n_cols=3, n_cols_source="evidence"), "n_cols must be 1, 2, or None"),
        (dict(n_cols=True, n_cols_source="evidence"), "n_cols must be 1, 2, or None"),  # bool is not a count
        (dict(n_cols=2, n_cols_source="oracle"), "n_cols_source must be one of"),
        (dict(n_cols=2, n_cols_source=None), "set together"),  # count without an origin
        (dict(n_cols=None, n_cols_source="evidence"), "set together"),  # origin without a count
        (dict(order_qa=1.5), "order_qa must be a rate"),
        (dict(order_qa=float("nan")), "order_qa must be a rate"),
    ],
)
def test_detector_field_domains_are_enforced(kwargs, phrase):
    with pytest.raises(ValueError, match=phrase):
        PageRecord(status=PAGE_MATCHED, match_rate=0.9, **kwargs)


@pytest.mark.parametrize(
    "route_kwargs",
    [
        dict(status=PAGE_ROUTED, stage="match", signal="match-rate", value=0.7),
        dict(status=PAGE_DECLINED, verdict=VERDICT),
    ],
)
def test_detector_fields_forbidden_on_non_matched_pages(route_kwargs):
    with pytest.raises(ValueError, match="only a matched page carries detector fields"):
        PageRecord(n_cols=2, n_cols_source="evidence", **route_kwargs)


def test_detector_fields_round_trip_through_save_load(workspace):
    sidecar = mk_sidecar(
        pages={1: PageRecord(status=PAGE_MATCHED, match_rate=0.9, n_cols=1, n_cols_source="prior", order_qa=0.87)},
    )
    save_geom_sidecar(workspace, sidecar)
    loaded = load_geom_sidecar(workspace, "w-sentinel-3")
    assert loaded.pages[1].n_cols == 1 and loaded.pages[1].n_cols_source == "prior" and loaded.pages[1].order_qa == 0.87


def test_with_detector_fields_populates_matched_pages():
    sidecar = mk_sidecar()  # one matched page (1), one matched atom
    out = with_detector_fields(sidecar, {1: {"n_cols": 2, "n_cols_source": "evidence", "order_qa": 0.91}})
    assert out.pages[1].n_cols == 2 and out.pages[1].order_qa == 0.91
    assert sidecar.pages[1].n_cols is None  # input untouched (frozen)


def test_with_detector_fields_empty_is_identity():
    sidecar = mk_sidecar()
    assert with_detector_fields(sidecar, {}) is sidecar


def test_with_detector_fields_rejects_a_non_matched_page():
    sidecar = mk_sidecar(
        pages={1: matched_page(), 2: routed_page()},
        atoms={"a0": matched_atom(1)},
        atom_pages={"a0": AtomPages(1, 1, 1)},
    )
    with pytest.raises(ValueError, match="not 'matched'"):
        with_detector_fields(sidecar, {2: {"n_cols": 2, "n_cols_source": "evidence", "order_qa": 0.9}})


def test_with_detector_fields_rejects_unknown_field_keys():
    # A typo'd key would otherwise be silently dropped (partial data loss); reject it like the
    # loaders do — the field dict carries only n_cols/n_cols_source/order_qa.
    sidecar = mk_sidecar()
    with pytest.raises(ValueError, match="unknown"):
        with_detector_fields(sidecar, {1: {"n_colz": 2, "order_qa": 0.7}})


# --- G-26: the P-5 two-leg auto-absent tripwire ------------------------------------------------ #


def test_tripwire_constants_are_the_ruled_p5_values():
    assert TRIPWIRE_ABSENT_MASS_MAX == 0.02, (
        "P-5 (RULED 2026-07-03) sizes leg A at 2% of accepted-page token mass — retuning it is a "
        "ruling, and it is never raised to un-fire a trip"
    )
    assert TRIPWIRE_PROSE_ABSENT_RATE_MAX == 0.05, (
        "P-5 (RULED 2026-07-03) sizes leg B at 5% of prose-sized atoms — retuning it is a ruling, "
        "and it is never raised to un-fire a trip"
    )
    assert TRIPWIRE_PROSE_MIN_TOKENS == 4, "P-5 scopes leg B to atoms with >= 4 witness tokens"
    assert TRIPWIRE_WARN_BAND_MASS == 0.01, (
        "P-5's warn tier flags any band above 1% of accepted-page token mass — part of the ruled "
        "form, never thresholded away"
    )


def _mass_world(matched_tokens, absent_tokens):
    """One accepted page: one big matched atom + one short absent atom, with exact token masses."""
    sidecar = mk_sidecar(
        atoms={"big": matched_atom(), "small": unmatched_atom()},
        atom_pages={"big": AtomPages(1, 1, 1), "small": AtomPages(1, 1, 1)},
    )
    return sidecar, {"big": matched_tokens, "small": absent_tokens}


def test_tripwire_leg_a_fires_on_absent_token_mass():
    sidecar, counts = _mass_world(matched_tokens=97, absent_tokens=3)  # 3% > 2%
    with pytest.raises(GeometryError, match="tripwire leg A fired"):
        assert_auto_absent_tripwire(sidecar, counts)


def test_tripwire_leg_a_boundary_does_not_fire_at_exactly_the_max():
    sidecar, counts = _mass_world(matched_tokens=98, absent_tokens=2)  # exactly 2%: > is the rule
    stats = assert_auto_absent_tripwire(sidecar, counts)
    assert stats["absent_token_mass_rate"] == pytest.approx(0.02)


def _prose_world(n_matched, n_absent, matched_tokens=30, absent_tokens=4):
    atoms = {}
    windows = {}
    counts = {}
    for i in range(n_matched):
        atoms[f"m{i}"] = matched_atom()
        windows[f"m{i}"] = AtomPages(1, 1, 1)
        counts[f"m{i}"] = matched_tokens
    for i in range(n_absent):
        atoms[f"u{i}"] = unmatched_atom(reason="below_atom_floor", confidence=0.4)
        windows[f"u{i}"] = AtomPages(1, 1, 1)
        counts[f"u{i}"] = absent_tokens
    return mk_sidecar(atoms=atoms, atom_pages=windows), counts


def test_tripwire_leg_b_fires_on_prose_absent_rate():
    # 2 of 21 prose atoms absent (9.5% > 5%) while leg A stays quiet (8 of 578 tokens = 1.4%):
    # the wide-but-thin failure leg A underweights.
    sidecar, counts = _prose_world(n_matched=19, n_absent=2)
    with pytest.raises(GeometryError, match="tripwire leg B fired"):
        assert_auto_absent_tripwire(sidecar, counts)


def test_tripwire_leg_b_under_the_rate_stays_quiet():
    sidecar, counts = _prose_world(n_matched=20, n_absent=1)  # 1/21 = 4.8% <= 5%
    stats = assert_auto_absent_tripwire(sidecar, counts)
    assert stats["prose_absent_rate"] == pytest.approx(1 / 21)


def test_tripwire_leg_b_boundary_does_not_fire_at_exactly_the_max():
    # 1 of 20 prose atoms = exactly 0.05: > is the rule (mirror of leg A's boundary control).
    sidecar, counts = _prose_world(n_matched=19, n_absent=1)
    stats = assert_auto_absent_tripwire(sidecar, counts)
    assert stats["prose_absent_rate"] == pytest.approx(0.05)


def test_tripwire_never_fires_on_a_total_short_tail_wipeout():
    # The charter control (G-26): the ENTIRE <=3-token class absent must not trip either leg —
    # leg A is sized above the short tail's whole mass, and leg B never sees sub-prose atoms.
    atoms = {}
    windows = {}
    counts = {}
    for i in range(10):  # long prose, all matched
        atoms[f"m{i}"] = matched_atom()
        windows[f"m{i}"] = AtomPages(1, 1, 1)
        counts[f"m{i}"] = 50
    for i in range(5):  # the whole furniture tail, wiped out
        atoms[f"f{i}"] = unmatched_atom()
        windows[f"f{i}"] = AtomPages(1, 1, 1)
        counts[f"f{i}"] = 2
    sidecar = mk_sidecar(atoms=atoms, atom_pages=windows)
    stats = assert_auto_absent_tripwire(sidecar, counts)  # must NOT raise
    assert stats["prose_absent_rate"] == 0.0
    assert stats["absent_token_mass_rate"] == pytest.approx(10 / 510)
    # ...but the warn tier still surfaces the band (non-blocking honesty: 1.96% > 1%)
    assert any("<=3" in flag for flag in stats["flags"])
    assert stats["bands"]["<=3"]["absent_atoms"] == 5
    assert stats["bands"]["<=3"]["reasons"] == {"zero_match": 5}


def test_tripwire_scope_is_accepted_pages_only(matchkit):
    # The mis-scope mutant: summing every stream atom's tokens (pending ones included) inflates
    # the denominator and un-fires a real leg-A trip. Accepted-only mass: 3/100 = 3% -> FIRES,
    # even though all-stream mass would be 3/200 = 1.5%.
    sidecar, counts = _mass_world(matched_tokens=97, absent_tokens=3)
    routed = replace(
        sidecar,
        pages={1: sidecar.pages[1], 2: routed_page()},
        atom_pages={**sidecar.atom_pages, "pending-atom": AtomPages(2, 2, 2)},
    )
    counts["pending-atom"] = 100  # visible to a mis-scoped sum, invisible to the correct one
    with pytest.raises(GeometryError, match="tripwire leg A fired"):
        assert_auto_absent_tripwire(routed, counts)


def test_tripwire_requires_counts_for_every_record_bearing_atom():
    sidecar, counts = _mass_world(matched_tokens=97, absent_tokens=3)
    del counts["small"]
    with pytest.raises(ValueError, match="must cover every accepted-page atom"):
        assert_auto_absent_tripwire(sidecar, counts)
    with pytest.raises(ValueError, match="non-negative integer"):
        assert_auto_absent_tripwire(sidecar, {"big": 97, "small": -1})


def test_tripwire_warn_tier_reports_bands_and_confidence_histogram():
    sidecar, counts = _mass_world(matched_tokens=98, absent_tokens=2)
    stats = assert_auto_absent_tripwire(sidecar, counts)
    assert stats["bands"][">10"]["atoms"] == 1 and stats["bands"]["<=3"]["atoms"] == 1
    assert sum(stats["confidence_histogram"].values()) == len(sidecar.atoms)
    assert stats["confidence_histogram"]["0.9-1.0"] == 1  # the matched atom at 0.9
    assert stats["confidence_histogram"]["0.0-0.1"] == 1  # the absent atom at 0.0


def test_tripwire_band_edges_and_top_histogram_bin_are_exact():
    # 10 belongs to "4-10", 11 to ">10", and a confidence of exactly 1.0 lands in the top bin
    # (not off the end of a half-open [0.9, 1.0) bucket).
    sidecar = mk_sidecar(
        atoms={
            "ten": matched_atom(confidence=1.0),
            "eleven": matched_atom(confidence=0.9),
            "tail": unmatched_atom(),
            "bulk": matched_atom(confidence=0.5),  # mass ballast keeping leg A under its max
        },
        atom_pages={
            "ten": AtomPages(1, 1, 1), "eleven": AtomPages(1, 1, 1),
            "tail": AtomPages(1, 1, 1), "bulk": AtomPages(1, 1, 1),
        },
    )
    stats = assert_auto_absent_tripwire(sidecar, {"ten": 10, "eleven": 11, "tail": 2, "bulk": 200})
    assert stats["bands"]["4-10"]["atoms"] == 1
    assert stats["bands"][">10"]["atoms"] == 2  # eleven + bulk
    assert stats["bands"]["<=3"]["atoms"] == 1
    assert stats["confidence_histogram"]["0.9-1.0"] == 2  # 0.9 and the exact 1.0
    assert stats["confidence_histogram"]["0.5-0.6"] == 1
