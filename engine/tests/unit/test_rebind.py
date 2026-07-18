"""S5.1 — the ``rebind_anchors`` store-and-rebind mechanism (§4 red-first invariants + mutants).

Every invariant is seen red on its named mutation before the code exists (feedback_red_first_tests);
the mutant table lives in ``tests/hunts/hunt_rebind.py``. This file grows with the module: the
foundational slice (fingerprint producer + similarity, mode resolution, the default-ordering policy)
comes first, then RebindContext / the monotone DP / the outputs / the re-stamp.

Threshold tests reference ``DEFAULT_FINGERPRINT_THRESHOLD`` **by name**, never an inline numeric
literal — so a default change cannot silently pass a stale hardcoded number (§5).
"""

from __future__ import annotations

import pytest

from engine.errors import CaptureError, StaleArtifactError
from engine.structure.atom_store import AtomStream
from engine.structure.atoms import Atom, AtomDerivation, Geom
from engine.structure.evidence import (
    AuthoringEvidence,
    build_evidence_entry,
    extent_digest,
)
from engine.structure.geom_regate import MODE_NO_GEOMETRY, MODE_PRIMARY, MODE_TIE_BREAK
from engine.structure.projection import Region, SlotFingerprint
from engine.structure.rebind import (
    DEFAULT_FINGERPRINT_THRESHOLD,
    REBIND_UNRESOLVED_REASONS,
    RebindContext,
    RebindError,
    RebindPolicy,
    assert_all_bound,
    fingerprint_slot,
    normalized_slot_tokens,
    rebind,
    resolve_mode,
    slot_similarity,
)
from engine.structure.roundtrip import hash_raw
from engine.structure.structure_map import (
    STRUCTURE_MAP_SCHEMA_VERSION,
    _hash_canonical,
    canonical_content_hash,
    canonical_geometry_hash,
    structure_map_from_json,
)


# --- fingerprint producer + similarity (§2.2) ---------------------------------------------------- #


def test_fingerprint_slot_produces_a_shingle_set():
    fp = fingerprint_slot(["alpha", "beta", "gamma", "delta"], k=3)
    assert isinstance(fp, SlotFingerprint)
    assert fp.k == 3 and fp.token_count == 4
    assert set(fp.shingles) == {"alpha beta gamma", "beta gamma delta"}
    assert fp.algo_id == "shingle-jaccard@v1"
    assert fp.normalizer_id == "geom_match.normalize_tokens@v1"


def test_fingerprint_slot_short_slot_falls_back_to_available_k():
    # short-slot invariant: a slot shorter than k falls back to k' = min(k, token_count) down to
    # unigrams — never an empty shingle set.
    short = fingerprint_slot(["one", "two"], k=3)
    assert short.k == 2 and set(short.shingles) == {"one two"}
    uni = fingerprint_slot(["solo"], k=3)
    assert uni.k == 1 and set(uni.shingles) == {"solo"}


def test_fingerprint_slot_empty_is_none_never_empty_set():
    # short-slot invariant: an empty slot has NO fingerprint (None), never an empty-shingle
    # fingerprint that could score a spurious 1.0 against another empty window. Mutant
    # (hunt_rebind): return an empty-shingle SlotFingerprint → this reds.
    assert fingerprint_slot([], k=3) is None


def test_slot_similarity_identity_disjoint_and_fuzzy():
    fp = fingerprint_slot(["a", "b", "c", "d"], k=3)
    assert slot_similarity(fp, ["a", "b", "c", "d"]) == 1.0  # identical content → 1.0
    assert slot_similarity(fp, ["x", "y", "z", "w"]) == 0.0  # disjoint → 0.0
    edited = slot_similarity(fp, ["a", "b", "c", "EDIT"])  # a local edit
    assert 0.0 < edited < 1.0  # R2: fuzzy, never the exact-substring all-or-nothing


def test_slot_similarity_empty_window_scores_zero():
    # the short-slot guard on the scoring side: an empty fresh window never binds (0, not vacuous 1.0)
    fp = fingerprint_slot(["a", "b", "c"], k=3)
    assert slot_similarity(fp, []) == 0.0


def test_normalized_slot_tokens_uses_the_shared_normalizer():
    # slot tokens run through geom_match.normalize_tokens (edge punctuation stripped, casefold, accents
    # preserved) so the stored fingerprint and a fresh window normalize identically.
    assert normalized_slot_tokens(["Alpha, BETA!", "gamma"]) == ["alpha", "beta", "gamma"]


# --- mode resolution (§1.2) ---------------------------------------------------------------------- #


@pytest.mark.parametrize("mode", [MODE_PRIMARY, MODE_TIE_BREAK, MODE_NO_GEOMETRY])
def test_resolve_mode_known_tokens_are_manifest_sourced(mode):
    dp_mode, reported, source = resolve_mode(mode)
    assert dp_mode == mode and reported == mode and source == "manifest"


def test_resolve_mode_none_is_conditional_primary_fallback():
    # an unruled book (geometry_mode None) → the conservative tie-break DP behavior, REPORTED as
    # conditional-primary with weaker provenance (source=fallback), never a silently invented mode.
    dp_mode, reported, source = resolve_mode(None)
    assert dp_mode == MODE_TIE_BREAK
    assert reported == "conditional-primary"
    assert source == "fallback"


def test_resolve_mode_unknown_fails_loud():
    # never guessed: a bad geometry_mode is a config error, fail loud (§1.2). Mutant: default an
    # unknown mode to tie-break → this reds.
    with pytest.raises(ValueError, match="unknown geometry_mode"):
        resolve_mode("geometry-sometimes")


# --- policy default-ordering: monotone-strictness reachable (§4, D-4) ---------------------------- #


def test_policy_default_ordering_holds_on_the_named_default():
    policy = RebindPolicy()
    assert (
        policy.threshold(MODE_NO_GEOMETRY)
        >= policy.threshold(MODE_TIE_BREAK)
        >= policy.threshold(MODE_PRIMARY)
    )
    # the tie-break (PLL) bar IS the named default — referenced by name, never a hardcoded literal
    assert policy.threshold(MODE_TIE_BREAK) == DEFAULT_FINGERPRINT_THRESHOLD


def test_policy_inverted_ordering_is_rejected_at_construction():
    # weaker geometry must never LOWER the fingerprint bar — an inverted policy cannot be built
    # (the mutant that inverts the defaults reds here). feedback_no_cheating_results.
    with pytest.raises(ValueError, match="default-ordering"):
        RebindPolicy(tau_primary=0.9, tau_tie_break=0.8, tau_no_geometry=0.7)


# ================================================================================================== #
# Engine core — RebindContext, the monotone-tiling assignment, the re-stamp, the outputs (§1.3–§1.6). #
# The §4 invariants below are red-proven mechanically by tests/hunts/hunt_rebind.py (each cites its   #
# killing mutant); this file exercises the behaviors, the hunt sees each red on its mutation.         #
# ================================================================================================== #

_BBOX = (10.0, 20.0, 30.0, 40.0)


def _canon_atom(aid, text, page, witness_id="w"):
    geom = (
        Geom.matched(
            page=page, bbox=_BBOX, geometry_engine="fx",
            matched_witness_id=witness_id, match_method="fx", match_confidence=1.0,
        )
        if page is not None
        else Geom.absent()
    )
    return Atom(
        atom_id=aid, text=text, raw_span=(0, len(text)), raw_source_hash=hash_raw(text),
        page_range=(page or 1, page or 1), norm_layer="raw", geom=geom,
        capture_provenance_class="fx", witness=None,
        derived_from=(AtomDerivation(witness=witness_id, atom_id=f"{aid}__w"),),
        processing_scope="included",
    )


def _wit_atom(aid, text, witness_id="w"):
    return Atom(
        atom_id=f"{aid}__w", text=text, raw_span=(0, len(text)), raw_source_hash=hash_raw(text),
        page_range=(1, 1), norm_layer="raw", geom=Geom.absent(),
        capture_provenance_class="fx", witness=witness_id, derived_from=(), processing_scope="included",
    )


def _streams(specs, *, canonical_id="canonical", witness_id="w"):
    """``specs`` = list of ``(atom_id, text, page)`` → a ``{canonical + witness}`` stream set whose
    canonical atoms carry the given text/geometry and back-link to a matching witness atom."""
    canon = [_canon_atom(aid, text, page, witness_id) for aid, text, page in specs]
    wit = [_wit_atom(aid, text, witness_id) for aid, text, _ in specs]
    return {
        canonical_id: AtomStream.canonical(canon, stream_id=canonical_id),
        witness_id: AtomStream.witness(witness_id, wit, (), "witness-source"),
    }


def _fp_json(texts, k=3):
    fp = fingerprint_slot(normalized_slot_tokens(texts), k=k)
    return {
        "algo_id": fp.algo_id, "normalizer_id": fp.normalizer_id, "k": fp.k,
        "token_count": fp.token_count, "shingles": list(fp.shingles),
    }


def _leaf(node_id, body_ids, texts, *, with_fp=True, region_page=None):
    node = {"node_id": node_id, "node_class": "blk", "minted_by": "machine", "body_atoms": list(body_ids)}
    anchors = {}
    if with_fp:
        anchors["content_fingerprint"] = {"body": _fp_json(texts)}
    if region_page is not None:
        anchors["region"] = {"page": region_page, "bbox_region": list(_BBOX)}
    if anchors:
        node["rebind_anchors"] = anchors
    return node


def _map(nodes, canonical_stream):
    doc = {
        "schema_version": STRUCTURE_MAP_SCHEMA_VERSION,
        "root_id": nodes[0]["node_id"],
        "map_revision": 1,
        "block_vocabulary": [],
        "handle_policies": {},
        "furniture_atoms": [],
        "aliases": [],
        "manifest": {
            "canonical_stream_id": canonical_stream.stream_id,
            "canonical_content_hash": canonical_content_hash(canonical_stream),
            "canonical_geometry_hash": canonical_geometry_hash(canonical_stream),
        },
        "nodes": nodes,
    }
    return structure_map_from_json(doc)


def _root(children):
    return {"node_id": "n-0", "node_class": "vol", "minted_by": "human", "children": list(children)}


def _fresh_specs(specs):
    """The id-permuted fresh substrate: new atom ids, unchanged text + geometry + reading order."""
    return [(f"f_{aid}", text, page) for aid, text, page in specs]


# --- happy re-bind (§4: happy) --------------------------------------------------------------------- #

_A0 = "alpha beta gamma delta"
_A1 = "epsilon zeta eta theta"


def _happy_case(page=3):
    specs = [("a0", _A0, page), ("a1", _A1, page)]
    old_streams = _streams(specs)
    old_map = _map(
        [_root(["l0", "l1"]), _leaf("l0", ["a0"], [_A0]), _leaf("l1", ["a1"], [_A1])],
        old_streams["canonical"],
    )
    return old_map, old_streams, specs


def test_happy_rebind_binds_every_node_on_an_id_permuted_stream():
    old_map, old_streams, specs = _happy_case()
    fresh = _streams(_fresh_specs(specs))
    ctx = RebindContext(old_map, old_streams, fresh, geometry_mode=MODE_TIE_BREAK)
    result = rebind(ctx)
    assert set(result.report.bound_node_ids) == {"n-0", "l0", "l1"}
    assert result.report.unresolved == ()
    # the leaves bound to the FRESH atom ids, never the old ones
    l0 = next(n for n in result.report.nodes if n.node_id == "l0")
    assert l0.slots[0].fresh_atom_ids == ("f_a0",)
    assert l0.slots[0].score == 1.0
    assert_all_bound(result)  # strict complement does not raise


def test_happy_rebind_restamps_extent_bottom_up_and_carries_the_decision_digest():
    old_map, old_streams, specs = _happy_case()
    root = old_map.projection.by_id["n-0"]
    entry = build_evidence_entry(root, old_map.projection, evidence="root rationale", authored_at_revision=1)
    evidence = AuthoringEvidence(book="fixture", entries=(entry,))
    fresh = _streams(_fresh_specs(specs))
    ctx = RebindContext(old_map, old_streams, fresh, evidence, geometry_mode=MODE_TIE_BREAK)
    result = rebind(ctx)
    (restamped,) = result.restamped_evidence
    assert restamped.node_id == "n-0"
    # decision digest CARRIED verbatim (re-bind-stable; never machine-refreshed)
    assert restamped.decision_digest == entry.decision_digest
    # extent digest MECHANICALLY re-stamped — the atoms are new ids, so it must have changed
    assert restamped.extent_digest != entry.extent_digest
    migrated = structure_map_from_json(result.migrated_doc).projection
    # the re-stamped digest re-verifies through the producer against the rebound projection
    assert restamped.extent_digest == extent_digest(migrated.by_id["n-0"], migrated)


# --- baseline binding (§4: baseline-binding) ------------------------------------------------------- #


def test_rebind_context_refuses_a_content_hash_mismatch():
    old_map, old_streams, specs = _happy_case()
    # a DIFFERENT old canonical stream (extra token) than the map's manifest was stamped against
    tampered = _streams([("a0", _A0 + " x", 3), ("a1", _A1, 3)])
    fresh = _streams(_fresh_specs(specs))
    with pytest.raises(StaleArtifactError, match="canonical_content_hash"):
        RebindContext(old_map, tampered, fresh, geometry_mode=MODE_TIE_BREAK)


def test_rebind_context_refuses_a_geometry_hash_mismatch_when_geometry_is_used():
    old_map, old_streams, specs = _happy_case()
    tampered = _streams([("a0", _A0, 9), ("a1", _A1, 9)])  # same text, different page → geom hash differs
    fresh = _streams(_fresh_specs(specs))
    with pytest.raises(StaleArtifactError, match="canonical_geometry_hash"):
        RebindContext(old_map, tampered, fresh, geometry_mode=MODE_TIE_BREAK)


def test_no_geometry_mode_skips_the_geometry_hash_gate():
    old_map, old_streams, specs = _happy_case()
    tampered = _streams([("a0", _A0, 9), ("a1", _A1, 9)])  # geom hash differs, content hash matches
    fresh = _streams(_fresh_specs(specs))
    # no-geometry does not read geometry, so the geometry-hash mismatch is not a baseline failure
    ctx = RebindContext(old_map, tampered, fresh, geometry_mode=MODE_NO_GEOMETRY)
    assert set(rebind(ctx).report.bound_node_ids) == {"n-0", "l0", "l1"}


def test_rebind_context_fails_loud_without_the_old_canonical():
    old_map, old_streams, specs = _happy_case()
    fresh = _streams(_fresh_specs(specs))
    map_only = {k: v for k, v in old_streams.items() if v.kind != "canonical"}
    with pytest.raises(StaleArtifactError, match="map-only re-bind"):
        RebindContext(old_map, map_only, fresh, geometry_mode=MODE_TIE_BREAK)


def test_rebind_context_runs_reference_integrity_on_both_stream_sets():
    old_map, old_streams, specs = _happy_case()
    # a fresh canonical atom whose derived_from names a witness atom that does not exist
    bad_atom = _canon_atom("f_a0", _A0, 3)
    bad_atom = Atom(
        atom_id=bad_atom.atom_id, text=bad_atom.text, raw_span=bad_atom.raw_span,
        raw_source_hash=bad_atom.raw_source_hash, page_range=bad_atom.page_range,
        norm_layer=bad_atom.norm_layer, geom=bad_atom.geom,
        capture_provenance_class=bad_atom.capture_provenance_class, witness=None,
        derived_from=(AtomDerivation(witness="w", atom_id="ghost"),), processing_scope="included",
    )
    fresh = _streams(_fresh_specs(specs))
    fresh["canonical"] = AtomStream.canonical([bad_atom, fresh["canonical"].atoms[1]], stream_id="canonical")
    with pytest.raises(CaptureError):
        RebindContext(old_map, old_streams, fresh, geometry_mode=MODE_TIE_BREAK)


# --- missing-anchor / below-threshold / ambiguous (§4) --------------------------------------------- #


def test_missing_anchor_node_never_binds_on_geometry_alone():
    specs = [("a0", _A0, 3), ("a1", _A1, 3)]
    old_streams = _streams(specs)
    # l0 carries a region seed but NO fingerprint → missing-anchor in every mode (optional-at-schema
    # ≠ permissive-at-rebind)
    old_map = _map(
        [_root(["l0", "l1"]), _leaf("l0", ["a0"], [_A0], with_fp=False, region_page=3),
         _leaf("l1", ["a1"], [_A1])],
        old_streams["canonical"],
    )
    fresh = _streams(_fresh_specs(specs))
    result = rebind(RebindContext(old_map, old_streams, fresh, geometry_mode=MODE_PRIMARY))
    l0 = next(n for n in result.report.nodes if n.node_id == "l0")
    assert not l0.bound and l0.reason == "missing-anchor"
    with pytest.raises(RebindError):
        assert_all_bound(result)


def test_below_threshold_when_fresh_content_diverges():
    specs = [("a0", _A0, 3), ("a1", _A1, 3)]
    old_streams = _streams(specs)
    old_map = _map(
        [_root(["l0", "l1"]), _leaf("l0", ["a0"], [_A0]), _leaf("l1", ["a1"], [_A1])],
        old_streams["canonical"],
    )
    # l0's fresh content is wholly different → best window < τ → below-threshold, never a re-stamp
    fresh = _streams([("f_a0", "kappa lambda mu nu", 3), ("f_a1", _A1, 3)])
    result = rebind(RebindContext(old_map, old_streams, fresh, geometry_mode=MODE_TIE_BREAK))
    l0 = next(n for n in result.report.nodes if n.node_id == "l0")
    assert not l0.bound and l0.reason == "below-threshold"
    assert next(n for n in result.report.nodes if n.node_id == "l1").bound


def test_ambiguous_repeated_content_fails_loud():
    # three all-"same" atoms + one fingerprinted leaf + one free (missing-anchor) leaf: the fp leaf
    # could own atom [0:1) OR [0:2) (an all-same superset also scores 1.0), the free leaf absorbing the
    # rest either way → two ≥τ windows compatible with a full tiling → ambiguous, never a silent bind.
    same = "same same same"
    specs = [("a0", same, 3), ("a1", same, 3), ("a2", same, 3)]
    old_streams = _streams(specs)
    old_map = _map(
        [_root(["l0", "l1"]),
         _leaf("l0", ["a0"], [same]),
         _leaf("l1", ["a1", "a2"], [same, same], with_fp=False)],
        old_streams["canonical"],
    )
    fresh = _streams(_fresh_specs(specs))
    result = rebind(RebindContext(old_map, old_streams, fresh, geometry_mode=MODE_NO_GEOMETRY))
    l0 = next(n for n in result.report.nodes if n.node_id == "l0")
    assert not l0.bound and l0.reason == "ambiguous"
    assert l0.slots[0].candidates_ge_tau == 2


def test_no_rescue_geometry_does_not_lift_a_subtau_fingerprint():
    # no-rescue: a sub-τ fingerprint on the CORRECT region page still fails loud — geometry is a pin /
    # tie-break, never additive to the score. Mutant (hunt): OR the region-page hit into the ≥τ gate.
    old_streams = _streams([("a0", _A0, 3)])
    old_map = _map([_root(["l0"]), _leaf("l0", ["a0"], [_A0], region_page=3)], old_streams["canonical"])
    fresh = _streams([("f_a0", "kappa lambda mu nu", 3)])  # on page 3 (region-hit) but content diverged
    result = rebind(RebindContext(old_map, old_streams, fresh, geometry_mode=MODE_TIE_BREAK))
    l0 = next(n for n in result.report.nodes if n.node_id == "l0")
    assert not l0.bound and l0.reason == "below-threshold"


def test_region_model_rejects_a_page_below_one():
    # the Tier-2 backing for the schema's minimum:1 — an atom Geom.page is a positive scan number, so
    # a region seed keyed on page 0 is not comparable to any atom and must fail at the model.
    with pytest.raises(ValueError, match="1-based scan number"):
        Region(page=0, bbox_region=_BBOX)


def test_r2_superstring_does_not_auto_bind_at_full_score():
    # R2 tombstone control: a fresh atom that is a SUPERSTRING of the stored content does not bind at
    # full score — Jaccard is fuzzy, and a diluted superset falls below τ (never exact-substring).
    specs = [("a0", _A0, 3)]
    old_streams = _streams(specs)
    old_map = _map([_root(["l0"]), _leaf("l0", ["a0"], [_A0])], old_streams["canonical"])
    fresh = _streams([("f_a0", _A0 + " iota kappa lambda mu", 3)])
    result = rebind(RebindContext(old_map, old_streams, fresh, geometry_mode=MODE_NO_GEOMETRY))
    l0 = next(n for n in result.report.nodes if n.node_id == "l0")
    assert not l0.bound and l0.reason == "below-threshold"
    assert (l0.slots[0].score or 0.0) < 1.0


# --- mode gating + zero-candidate (§4: mode gating) ------------------------------------------------ #


def _region_mismatch_case():
    specs = [("a0", _A0, 3), ("a1", _A1, 3)]
    old_streams = _streams(specs)
    # l0's region seed pins page 9, but its fresh atom is on page 3
    old_map = _map(
        [_root(["l0", "l1"]), _leaf("l0", ["a0"], [_A0], region_page=9), _leaf("l1", ["a1"], [_A1])],
        old_streams["canonical"],
    )
    fresh = _streams(_fresh_specs(specs))
    return old_map, old_streams, fresh


def test_primary_mode_hard_pin_excludes_a_wrong_page_and_yields_zero_candidate():
    old_map, old_streams, fresh = _region_mismatch_case()
    result = rebind(RebindContext(old_map, old_streams, fresh, geometry_mode=MODE_PRIMARY))
    l0 = next(n for n in result.report.nodes if n.node_id == "l0")
    assert not l0.bound and l0.reason == "zero-candidate"


def test_no_geometry_mode_ignores_the_region_and_binds_on_fingerprint():
    old_map, old_streams, fresh = _region_mismatch_case()
    result = rebind(RebindContext(old_map, old_streams, fresh, geometry_mode=MODE_NO_GEOMETRY))
    assert set(result.report.bound_node_ids) == {"n-0", "l0", "l1"}


# --- re-stamp ordering + decision-digest staleness (§4) -------------------------------------------- #


def test_ancestor_not_restamped_while_a_descendant_is_unresolved():
    # a bindable human container 'sec' with a below-threshold leaf child: the leaf does not bind, so
    # its ancestor's extent is NOT re-stamped (bottom-up gate — no stamp over an unresolved subtree).
    specs = [("a0", _A0, 3), ("a1", _A1, 3)]
    old_streams = _streams(specs)
    sec = {"node_id": "n-1", "node_class": "sec", "minted_by": "human", "children": ["l0"]}
    old_map = _map(
        [{"node_id": "n-0", "node_class": "vol", "minted_by": "human", "children": ["n-1", "l1"]},
         sec, _leaf("l0", ["a0"], [_A0]), _leaf("l1", ["a1"], [_A1])],
        old_streams["canonical"],
    )
    sec_node = old_map.projection.by_id["n-1"]
    entry = build_evidence_entry(sec_node, old_map.projection, evidence="sec", authored_at_revision=1)
    evidence = AuthoringEvidence(book="fixture", entries=(entry,))
    # l0 diverges → below-threshold → sec (its parent) must not be re-stamped
    fresh = _streams([("f_a0", "kappa lambda mu nu", 3), ("f_a1", _A1, 3)])
    result = rebind(RebindContext(old_map, old_streams, fresh, evidence, geometry_mode=MODE_TIE_BREAK))
    assert result.restamped_evidence == ()


def test_stale_decision_is_a_finding_not_a_restamp():
    # an evidence entry authored against a DIFFERENT child topology → its decision digest is stale
    # against the (rebound) map; a re-bind never machine-refreshes it — it surfaces as stale-decision.
    old_map, old_streams, specs = _happy_case()
    root = old_map.projection.by_id["n-0"]
    # forge a decision digest for a different topology (swap the child order) — stale by construction
    forged_children = ("l1", "l0")
    stale_decision = _hash_canonical({"node_class": "vol", "children": forged_children})
    stale_entry = build_evidence_entry(root, old_map.projection, evidence="root", authored_at_revision=1)
    object.__setattr__(stale_entry, "decision_digest", stale_decision)
    object.__setattr__(
        stale_entry, "decision_payload",
        type(stale_entry.decision_payload)({"node_class": "vol", "children": forged_children}),
    )
    evidence = AuthoringEvidence(book="fixture", entries=(stale_entry,))
    fresh = _streams(_fresh_specs(specs))
    result = rebind(RebindContext(old_map, old_streams, fresh, evidence, geometry_mode=MODE_TIE_BREAK))
    root_out = next(n for n in result.report.nodes if n.node_id == "n-0")
    assert not root_out.bound and root_out.reason == "stale-decision"
    assert all(e.node_id != "n-0" for e in result.restamped_evidence)


# --- global consistency (§4: global consistency + global-conflict) -------------------------------- #


def test_partial_rebind_never_silently_double_claims_a_fresh_atom():
    # Adversarial (audit-found): two leaves whose stored fingerprints share a boundary phrase can each
    # find a UNIQUE ≥τ window that OVERLAPS the other's on a re-segmented fresh stream. A third leaf
    # diverges (unresolved), so the map is NOT all-bound. The whole-map validate gate must still catch
    # the double-claim on the BOUND SUBSET — never report two overlapping binds as clean (the R2
    # silent-mis-bind this design exists to prevent).
    specs = [("a0", "p q r s", 3), ("a1", "r s t u", 3), ("a2", "zz zz zz zz", 3)]
    old_streams = _streams(specs)
    old_map = _map(
        [_root(["l0", "l1", "l2"]),
         _leaf("l0", ["a0"], ["p q r s"]),
         _leaf("l1", ["a1"], ["r s t u"]),
         _leaf("l2", ["a2"], ["zz zz zz zz"])],
        old_streams["canonical"],
    )
    # a re-extraction that split the atoms so "r s" (f1) is claimable by BOTH l0 ([0,2)) and l1 ([1,3))
    fresh = _streams([("f0", "p q", 3), ("f1", "r s", 3), ("f2", "t u", 3), ("f3", "v w", 3)])
    result = rebind(RebindContext(old_map, old_streams, fresh, geometry_mode=MODE_NO_GEOMETRY))
    # no fresh atom may be owned by two BOUND nodes
    claimed: dict[str, list[str]] = {}
    for n in result.report.nodes:
        if n.bound:
            for slot in n.slots:
                for aid in slot.fresh_atom_ids:
                    claimed.setdefault(aid, []).append(n.node_id)
    doubles = {aid: owners for aid, owners in claimed.items() if len(owners) > 1}
    assert not doubles, f"silent double-bind of fresh atom(s): {doubles}"
    # the two conflicting leaves fail loud as global-conflict, not a silent bind
    unresolved = dict(result.report.unresolved)
    assert unresolved.get("l0") == "global-conflict"
    assert unresolved.get("l1") == "global-conflict"


def test_empty_container_makes_the_rebound_map_fail_global_validation():
    # every node tentatively binds, but the rebound map does not validate globally (an empty container
    # owns nothing and leads nowhere) → global-conflict, never a silent per-node bind.
    specs = [("a0", _A0, 3)]
    old_streams = _streams(specs)
    empty = {"node_id": "n-2", "node_class": "sec", "minted_by": "human", "children": []}
    old_map = _map(
        [_root(["n-2", "l0"]), empty, _leaf("l0", ["a0"], [_A0])],
        old_streams["canonical"],
    )
    fresh = _streams(_fresh_specs(specs))
    result = rebind(RebindContext(old_map, old_streams, fresh, geometry_mode=MODE_NO_GEOMETRY))
    assert result.report.unresolved  # not all bound
    assert all(r == "global-conflict" for _, r in result.report.unresolved)


# --- report provenance + the closed reason enum (§1.5, D-7) ---------------------------------------- #


def test_report_carries_mode_provenance_and_stream_hashes():
    old_map, old_streams, specs = _happy_case()
    fresh = _streams(_fresh_specs(specs))
    result = rebind(RebindContext(old_map, old_streams, fresh, geometry_mode=MODE_TIE_BREAK))
    prov = result.report.mode
    assert prov.mode == MODE_TIE_BREAK and prov.source == "manifest"
    assert prov.manifest_schema_version == STRUCTURE_MAP_SCHEMA_VERSION
    # the two canonical streams compared are surfaced, with distinct content hashes (ids changed)
    assert result.report.old_canonical_stream_id == "canonical"
    assert result.report.old_content_hash != result.report.fresh_content_hash


def test_unruled_geometry_mode_is_reported_conditional_primary_fallback():
    old_map, old_streams, specs = _happy_case()
    fresh = _streams(_fresh_specs(specs))
    result = rebind(RebindContext(old_map, old_streams, fresh, geometry_mode=None))
    assert result.report.mode.mode == "conditional-primary"
    assert result.report.mode.source == "fallback"


def test_rebind_error_reason_enum_is_closed():
    with pytest.raises(ValueError, match="unknown re-bind reason"):
        RebindError([("n-0", "not-a-reason")])
    assert "ambiguous" in REBIND_UNRESOLVED_REASONS
    assert "stale-decision" in REBIND_UNRESOLVED_REASONS
