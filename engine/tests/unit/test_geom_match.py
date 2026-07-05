"""S2.1.3 #37 — matcher greens: normalizer, monotone page-locate, token-bow-v1, attach overlay.

Homes (``s2_1_plan.md`` §4): G-3 (provenance verbatim), G-4 (zero-match → absent), G-5
(confidence value pin), G-6 (union over matched boxes only), G-7 (monotone + earliest tie-break),
G-20 (canonical attach via ``derived_from``, multi-primary never unioned/picked), G-24
(consumption + emission-order determinism), G-25 (eligibility ≠ match failure), plus the P-2/P-4
ruled-value pins and the DT-8 normalizer contract. Everything binds to the seam fakes
(``matchkit`` — fake-backend tier, DT-11): no OCR, no PDF, no synthetic-PDF evidence for matcher
semantics (the claim-ladder rule)."""

from __future__ import annotations

import inspect
import json
import random
from collections import Counter

import pytest

from engine.structure.geom_match import (
    BAND_BAG_MULTIPLIER,
    LOCATE_METHOD,
    MATCH_METHOD,
    MIN_DISTINCTIVE_TOKENS,
    OUTCOME_INELIGIBLE,
    OUTCOME_MATCHED,
    OUTCOME_UNMATCHED,
    REASON_MULTI_PRIMARY_DERIVATION,
    REASON_NO_PRIMARY_DERIVATION,
    attach_geometry,
    build_geom_sidecar,
    locate_pages,
    match_stream,
    normalize_tokens,
)
from engine.structure.geom_sidecar import (
    ATOM_MATCHED,
    ATOM_UNMATCHED,
    REASON_AMBIGUOUS,
    REASON_BELOW_ATOM_FLOOR,
    REASON_ZERO_MATCH,
    SourceScan,
    to_json,
)

SCAN = SourceScan(kind="pdf", sha256="scan-sentinel-hash", n_pages=9, n_bytes=1234)
PARAMS = {"dpi": 217, "language": "lang-sentinel"}


def build(outcome, **kw):
    kw.setdefault("source_scan", SCAN)
    kw.setdefault("backend_params", PARAMS)
    kw.setdefault("engine_id", "engine-sentinel-77")
    return build_geom_sidecar(outcome, **kw)


# --- the shared normalizer (DT-8) --------------------------------------------------------- #


def test_normalizer_pipeline_nfc_split_edge_strip_casefold():
    # One call exercises all four stages: NFC (composed == decomposed), whitespace split, edge
    # punctuation stripped per Unicode (quotes/brackets/commas as *data*), casefold.
    composed = "Libertà"
    decomposed = "Libertà"
    assert normalize_tokens(composed) == normalize_tokens(decomposed) == ["libertà"]
    assert normalize_tokens("  (Alfa),  'BRAVO!'  charlie-9  ") == ["alfa", "bravo", "charlie-9"]


def test_normalizer_preserves_accents_stopwords_and_digits():
    # No accent stripping and no stopword removal in core — both are language opinions (DT-8);
    # digits are tokens (folios are page-anchoring signal, DT-3).
    assert normalize_tokens("perché") == ["perché"]
    assert normalize_tokens("perché") != ["perche"]
    assert normalize_tokens("di e la 1913.") == ["di", "e", "la", "1913"]


def test_normalizer_drops_pure_punctuation_tokens():
    assert normalize_tokens("... — !!") == []
    assert normalize_tokens("") == []


def test_normalizer_casefolds_not_lowers():
    # casefold is the pinned stage (language-neutral core): the sharp-s folds to "ss", which
    # .lower() would leave untouched.
    assert normalize_tokens("Straße") == ["strasse"]


# --- monotone page-locate (DT-3, G-7) ------------------------------------------------------ #


def _brute_locate(tokens, bags):
    """Independent reference: unbanded O(N^2 K) DP over the same objective, forward-lexicographic
    earliest tie-break. Deliberately naive — full re-scoring per window, no incremental trick —
    so a bug in the fast implementation's band/sweep machinery cannot be mirrored here."""
    neg = -(10**18)
    k, n = len(bags), len(tokens)

    def score(a, b, bag):
        window = Counter(tokens[a:b])
        return sum(min(count, bag.get(t, 0)) for t, count in window.items())

    dp = [[neg] * (n + 1) for _ in range(k + 1)]
    dp[k][n] = 0
    for p in range(k - 1, -1, -1):
        for c in range(n + 1):
            dp[p][c] = max(
                (score(c, c2, bags[p]) + dp[p + 1][c2] for c2 in range(c, n + 1) if dp[p + 1][c2] > neg),
                default=neg,
            )
    bounds, prev = [0], 0
    for p in range(1, k + 1):
        best, best_c = None, None
        for c in range(prev, n + 1):
            if dp[p][c] > neg:
                value = score(prev, c, bags[p - 1]) + dp[p][c]
                if best is None or value > best:
                    best, best_c = value, c
        bounds.append(best_c)
        prev = best_c
    return tuple(bounds)


def test_locate_matches_the_brute_force_reference_on_random_streams():
    # Whole-range band (band_tokens wide) == the global optimum, boundaries AND tie-break: the
    # fast DP's band/sweep/incremental-scoring machinery against a naive independent twin.
    rng = random.Random(917)
    vocab = list("abcdefgh")
    for _ in range(150):
        n_pages = rng.randint(1, 4)
        tokens = [rng.choice(vocab) for _ in range(rng.randint(0, 16))]
        bags = []
        for _ in range(n_pages):
            bags.append({t: rng.randint(1, 3) for t in rng.sample(vocab, rng.randint(0, 5))})
        got = locate_pages(tokens, bags, band_tokens=10_000)
        assert got == _brute_locate(tokens, bags), (tokens, bags)


def test_locate_boundaries_are_monotone_and_cover_the_stream():
    rng = random.Random(41)
    vocab = list("mnopqr")
    for _ in range(60):
        tokens = [rng.choice(vocab) for _ in range(rng.randint(0, 30))]
        bags = [
            {t: rng.randint(1, 2) for t in rng.sample(vocab, rng.randint(0, 4))}
            for _ in range(rng.randint(1, 5))
        ]
        bounds = locate_pages(tokens, bags)  # the ruled default band
        assert bounds[0] == 0 and bounds[-1] == len(tokens)
        assert all(a <= b for a, b in zip(bounds, bounds[1:])), bounds


def test_locate_tie_break_takes_the_earliest_boundary_exactly():
    # G-7's committed fixture: a repeated-token run with a furniture token straddling the
    # boundary region, built so boundary positions 2 and 3 tie on total score (2 + 2 each); the
    # furniture token matches neither bag and scores zero. Earliest must win, exactly.
    tokens = ["run", "run", "furniture", "run", "run"]
    bags = [{"run": 2}, {"run": 2}]
    assert locate_pages(tokens, bags, band_tokens=100) == (0, 2, 5)


def test_locate_default_band_is_the_ruled_width_of_the_largest_bag():
    # The P-2 width in *use* (no band_tokens override): 3x the largest bag (20 tokens -> width 60,
    # half 30) around the ratio center (20) reaches the optimum at exactly the band's upper edge
    # (50). A narrower rule (1x, or 3x the smallest bag) or a shaved edge (center+half-1) cannot
    # reach it and reds on the boundary value.
    tokens = ["f"] * 40 + ["aa"] * 10 + ["bb"] * 10
    bags = [{"aa": 10}, {"bb": 10, "cc": 10}]
    assert locate_pages(tokens, bags) == (0, 50, 60)


def test_locate_all_empty_bags_fall_back_deterministically():
    # total bag mass 0 -> the uniform center fallback; degenerate but a pure function.
    assert locate_pages(["x"], [{}, {}]) == locate_pages(["x"], [{}, {}]) == (0, 0, 1)


def test_locate_band_positions_by_cumulative_token_ratio():
    # DT-3: the band is *positioned* by the cumulative-token ratio, not spread uniformly. With a
    # deliberately narrow band, the correct centers (10/22 and 20/22 of the stream) still contain
    # the optimal boundaries; a uniformly-centered band (N/3, 2N/3) could not reach them.
    tokens = ["aa"] * 10 + ["bb"] * 10 + ["cc"] * 2
    bags = [{"aa": 10}, {"bb": 10}, {"cc": 2}]
    assert locate_pages(tokens, bags, band_tokens=3) == (0, 10, 20, 22)


def test_locate_band_multiplier_is_the_ruled_p2_value():
    assert BAND_BAG_MULTIPLIER == 3, (
        "P-2 (RULED 2026-07-03) fixes the DP band at 3x the max page bag — a different multiplier "
        "is an unruled re-tune, not a tweak"
    )


def test_locate_method_strings_are_the_pinned_wire_values():
    # DT-3/DT-8 name these in the sidecar schema; the run report and S2.2 grep on them.
    assert LOCATE_METHOD == "monotone-align-v1"
    assert MATCH_METHOD == "token-bow-v1"


def test_locate_rejects_malformed_inputs():
    with pytest.raises(ValueError, match="at least one page bag"):
        locate_pages(["a"], [])
    with pytest.raises(ValueError, match="token->count mapping"):
        locate_pages(["a"], [["not", "a", "mapping"]])
    with pytest.raises(ValueError, match="non-negative int counts"):
        locate_pages(["a"], [{"a": -1}])
    with pytest.raises(ValueError, match="band_tokens must be a positive integer"):
        locate_pages(["a"], [{"a": 1}], band_tokens=0)


def test_locate_empty_stream_is_the_all_zero_degenerate():
    assert locate_pages([], [{"a": 1}, {"b": 2}]) == (0, 0, 0)


# --- token-bow-v1 (DT-8: G-3/G-4/G-5/G-6, P-4, consumption) -------------------------------- #


def test_matched_geom_carries_all_configured_provenance_verbatim(matchkit):
    # G-3: equality on EVERY provenance field, against sentinel/measured values no default could
    # produce — a non-1 page, a non-1.0 confidence, and the record's own bbox, so a hardcode of
    # any field (engine, witness, page, confidence, bbox) reds independently.
    stream = matchkit.witness_stream(["alfa bravo charlie delta"], witness="witness-sentinel-3")
    page = matchkit.page(
        7,
        [
            ("alfa", (10.0, 10.0, 42.0, 22.0)),
            ("bravo", (48.0, 10.0, 88.0, 22.0)),
            ("charlie", (94.0, 10.0, 150.0, 22.0)),
        ],
    )
    outcome = match_stream(stream, [page], page_accept_rate=0.5, atom_match_floor=0.6)
    sidecar = build(outcome, engine_id="engine-sentinel-77")
    assert sidecar.engine_id == "engine-sentinel-77"
    assert sidecar.witness_id == "witness-sentinel-3"
    geom = attach_geometry(stream, sidecar).atoms[0].geom
    assert geom.present
    assert geom.geometry_engine == "engine-sentinel-77"
    assert geom.matched_witness_id == "witness-sentinel-3"
    assert geom.match_method == "token-bow-v1"
    assert geom.page == 7
    assert geom.match_confidence == 0.75
    assert geom.bbox == (10.0, 10.0, 150.0, 22.0)


def test_scan_page_numbers_flow_through_never_page_indices(matchkit):
    # DT-4 pins 1-based *scan* numbers; every earlier fixture numbered pages 1..K, where a
    # pg.page ↔ (index+1) conflation is an identity. Pages 7..10 make each site observable —
    # matched keys/records/windows/attached geoms, AND the routed-page key (9, match stage), AND
    # the locate-failure key (10, empty window).
    stream = matchkit.witness_stream(
        ["alfa bravo charlie", "delta echo foxtrot", "x1 x2 x3"], ids=["a7", "a8", "a9"]
    )
    pages = [
        matchkit.page(7, ["alfa", "bravo", "charlie"]),
        matchkit.page(8, ["delta", "echo", "foxtrot"]),
        matchkit.page(9, ["qq", "ww", "ee"]),
        matchkit.page(10, ["zz"]),
    ]
    outcome = match_stream(stream, pages, page_accept_rate=0.5, atom_match_floor=0.5)
    assert set(outcome.pages) == {7, 8, 9, 10}
    assert outcome.atoms["a7"].page == 7 and outcome.atoms["a8"].page == 8
    assert (outcome.atom_pages["a7"].first, outcome.atom_pages["a7"].assigned) == (7, 7)
    assert (outcome.atom_pages["a8"].last, outcome.atom_pages["a8"].assigned) == (8, 8)
    # a9 matches neither trailing bag, so boundary c3 ties across [6, 9] and the earliest wins:
    # page 9's window is empty (locate failure) and a9 lands in page 10's window (routed at match)
    assert outcome.pages[9].status == "routed" and outcome.pages[9].stage == "locate"
    assert outcome.pages[10].status == "routed" and outcome.pages[10].stage == "match"
    assert outcome.atom_pages["a9"].assigned == 10
    assert outcome.locate_failed_pages == (9,)
    result = attach_geometry(stream, build(outcome))
    assert result.atoms[0].geom.page == 7 and result.atoms[1].geom.page == 8


def test_zero_match_atom_writes_absent_never_an_invented_box(matchkit):
    # G-4: the second atom shares no token with the page; its record and its attached geom must
    # both be coordinate-free.
    stream = matchkit.witness_stream(["alfa bravo charlie delta", "zulu yankee xray"])
    page = matchkit.page(1, ["alfa", "bravo", "charlie", "delta"])
    outcome = match_stream(stream, [page], page_accept_rate=0.5, atom_match_floor=0.6)
    record = outcome.atoms["w-sentinel-3-a1"]
    assert record.status == ATOM_UNMATCHED
    assert record.reason == REASON_ZERO_MATCH
    assert record.match_confidence == 0.0
    assert record.bbox is None and record.page is None
    result = attach_geometry(stream, build(outcome))
    geom = result.atoms[1].geom
    assert not geom.present and geom.bbox is None
    assert result.outcomes["w-sentinel-3-a1"].status == OUTCOME_UNMATCHED


def test_match_confidence_is_matched_over_total_pinned_by_value(matchkit):
    # G-5: 3 of 5 tokens present -> exactly 0.6, on both sides of the atom floor. A constant-1.0
    # (or matched/matched) mutant reds on the value.
    stream = matchkit.witness_stream(["tok1 tok2 tok3 tok4 tok5"])
    page = matchkit.page(1, ["tok1", "tok2", "tok3"])
    low = match_stream(stream, [page], page_accept_rate=0.5, atom_match_floor=0.0)
    record = low.atoms["w-sentinel-3-a0"]
    assert record.status == ATOM_MATCHED and record.match_confidence == 0.6
    high = match_stream(stream, [page], page_accept_rate=0.5, atom_match_floor=0.7)
    record = high.atoms["w-sentinel-3-a0"]
    assert record.status == ATOM_UNMATCHED and record.reason == REASON_BELOW_ATOM_FLOOR
    assert record.match_confidence == 0.6


def test_page_rate_is_token_mass_weighted_not_an_atom_mean(matchkit):
    # DT-8's "atom-weighted match rate" = sum(matched)/sum(tokens). Long-matched (8/8) + short-
    # unmatched (0/2) weighs 0.8; the unweighted per-atom mean is 0.5. accept_rate 0.7 splits
    # them: the weighted form accepts, a mean mutant routes.
    stream = matchkit.witness_stream(["t1 t2 t3 t4 t5 t6 t7 t8", "zz yy"], ids=["long", "short"])
    page = matchkit.page(1, ["t1", "t2", "t3", "t4", "t5", "t6", "t7", "t8"])
    outcome = match_stream(stream, [page], page_accept_rate=0.7, atom_match_floor=0.5)
    assert outcome.pages[1].status == "matched"
    assert outcome.pages[1].match_rate == 0.8


def test_page_accepts_at_exactly_the_accept_rate(matchkit):
    # DT-8 pins acceptance at >= — a page landing exactly on the threshold is accepted.
    stream = matchkit.witness_stream(["a1 a2 a3 a4 a5"])
    page = matchkit.page(1, ["a1", "a2", "a3", "a4"])
    outcome = match_stream(stream, [page], page_accept_rate=0.8, atom_match_floor=0.6)
    assert outcome.pages[1].status == "matched"
    assert outcome.pages[1].match_rate == 0.8


def test_distinctive_floor_binds_at_exactly_three_matched_without_page_unique(matchkit):
    # P-4's >= boundary, isolated from the page-unique rescue: every matched token appears twice
    # on the page (no unique), matched == 3 exactly -> binds. A <= mutant writes ambiguous.
    stream = matchkit.witness_stream(["pp qq rr"])
    page = matchkit.page(1, ["pp", "pp", "qq", "qq", "rr", "rr"])
    outcome = match_stream(stream, [page], page_accept_rate=0.4, atom_match_floor=0.5)
    assert outcome.atoms["w-sentinel-3-a0"].status == ATOM_MATCHED


def test_union_bbox_spans_matched_boxes_only(matchkit):
    # G-6: a distractor box (a token the atom never carries) parked far away must not widen the
    # union; the bbox equals the min/max over exactly the consumed boxes.
    stream = matchkit.witness_stream(["echo foxtrot golf"])
    page = matchkit.page(
        1,
        [
            ("echo", (10.0, 10.0, 50.0, 22.0)),
            ("foxtrot", (55.0, 10.0, 120.0, 22.0)),
            ("golf", (10.0, 30.0, 45.0, 42.0)),
            ("victor", (400.0, 600.0, 460.0, 640.0)),  # the distractor
        ],
    )
    outcome = match_stream(stream, [page], page_accept_rate=0.5, atom_match_floor=0.6)
    record = outcome.atoms["w-sentinel-3-a0"]
    assert record.status == ATOM_MATCHED
    assert record.bbox == (10.0, 10.0, 120.0, 42.0)


def test_repeated_phrase_cannot_double_bind(matchkit):
    # G-24 consumption: two identical atoms, one printed copy — the second atom must come up
    # empty, never re-bind the same boxes. Removing consumption reds this.
    stream = matchkit.witness_stream(["lima mike november", "lima mike november"], ids=["first", "second"])
    page = matchkit.page(1, ["lima", "mike", "november"])
    outcome = match_stream(stream, [page], page_accept_rate=0.4, atom_match_floor=0.6)
    assert outcome.atoms["first"].status == ATOM_MATCHED
    assert outcome.atoms["first"].match_confidence == 1.0
    second = outcome.atoms["second"]
    assert second.status == ATOM_UNMATCHED and second.reason == REASON_ZERO_MATCH


def test_output_is_invariant_to_backend_emission_order(matchkit):
    # G-24 determinism: same box *set*, shuffled emission -> byte-identical sidecar JSON. The
    # duplicate-text boxes sit on the SAME row (equal y0, different x0) — the live nondeterminism
    # case: a sort degraded to (y0,) is a stable sort on a tie, so first-available would follow
    # emission order and the union would flip with the shuffle.
    stream = matchkit.witness_stream(["sierra tango uniform"])
    boxes = [
        ("sierra", (10.0, 10.0, 60.0, 22.0)),
        ("sierra", (70.0, 10.0, 120.0, 22.0)),
        ("tango", (130.0, 10.0, 180.0, 22.0)),
        ("uniform", (190.0, 10.0, 260.0, 22.0)),
    ]
    outcomes = []
    for order in (boxes, boxes[::-1]):
        page = matchkit.page(1, order)
        outcome = match_stream(stream, [page], page_accept_rate=0.5, atom_match_floor=0.5)
        outcomes.append(json.dumps(to_json(build(outcome)), sort_keys=False))
    assert outcomes[0] == outcomes[1]
    reparsed = json.loads(outcomes[0])
    # one 'sierra' consumed, and it is the canonically-first copy (equal y0 -> smaller x0)
    assert reparsed["atoms"]["w-sentinel-3-a0"]["bbox"] == [10.0, 10.0, 260.0, 22.0]


def test_distinctive_floor_is_the_ruled_p4_value_and_page_unique_rescues(matchkit):
    assert MIN_DISTINCTIVE_TOKENS == 3, (
        "P-4 (RULED 2026-07-03) fixes the distinctive-token floor at 3 — a different floor is an "
        "unruled re-tune"
    )
    # Two matched tokens, both with page-bag count 2: below the floor, no page-unique token ->
    # ambiguous (absent, not a plausible wrong bbox).
    stream = matchkit.witness_stream(["whiskey xray"])
    crowded = matchkit.page(1, ["whiskey", "whiskey", "xray", "xray"])
    outcome = match_stream(stream, [crowded], page_accept_rate=0.5, atom_match_floor=0.5)
    record = outcome.atoms["w-sentinel-3-a0"]
    assert record.status == ATOM_UNMATCHED and record.reason == REASON_AMBIGUOUS
    assert record.match_confidence == 1.0  # confidence is measured; the floor is what blocked it
    # Same atom, one 'xray' on the page: a matched page-unique token rescues the bind (P-4's OR).
    unique = matchkit.page(1, ["whiskey", "whiskey", "xray"])
    outcome = match_stream(stream, [unique], page_accept_rate=0.5, atom_match_floor=0.5)
    assert outcome.atoms["w-sentinel-3-a0"].status == ATOM_MATCHED


def test_hyphen_fragments_never_wrongly_bind_and_degrade_truthfully(matchkit):
    # DT-8's pinned honest v1: line-break fragments (perso- / ne) do NOT match the witness's
    # joined form; they count as unmatched residue, degrade confidence truthfully, and stay out
    # of the union when the atom does bind.
    stream = matchkit.witness_stream(["persone intere"])
    page = matchkit.page(
        1,
        [
            ("perso-", (10.0, 10.0, 60.0, 22.0)),
            ("ne", (10.0, 30.0, 30.0, 42.0)),
            ("intere", (40.0, 30.0, 90.0, 42.0)),
        ],
    )
    strict = match_stream(stream, [page], page_accept_rate=0.4, atom_match_floor=0.6)
    record = strict.atoms["w-sentinel-3-a0"]
    assert record.status == ATOM_UNMATCHED and record.reason == REASON_BELOW_ATOM_FLOOR
    assert record.match_confidence == 0.5
    loose = match_stream(stream, [page], page_accept_rate=0.4, atom_match_floor=0.5)
    record = loose.atoms["w-sentinel-3-a0"]
    assert record.status == ATOM_MATCHED
    assert record.bbox == (40.0, 30.0, 90.0, 42.0)  # intere's box only — no fragment in the union


def test_unusable_boxes_never_enter_the_bag(matchkit):
    # A box normalizing to zero tokens (pure punctuation) or to several tokens has no unambiguous
    # token key: it must never bind (counted nowhere as a match).
    stream = matchkit.witness_stream(["kilo lima"])
    page = matchkit.page(
        1,
        [
            ("kilo", (10.0, 10.0, 40.0, 22.0)),
            ("—", (50.0, 10.0, 60.0, 22.0)),
            ("lima extra", (70.0, 10.0, 150.0, 22.0)),
        ],
    )
    outcome = match_stream(stream, [page], page_accept_rate=0.0, atom_match_floor=0.0)
    record = outcome.atoms["w-sentinel-3-a0"]
    assert record.match_confidence == 0.5  # kilo matched; 'lima' inside the two-token box did not


def test_thresholds_are_required_parameters_with_no_defaults(matchkit):
    # The 0.80/0.60 values are proposals ratified only at the slice-1 run report (plan §8): a
    # baked default would be an unruled constant (the G-1 posture, applied to the matcher).
    signature = inspect.signature(match_stream)
    for name in ("page_accept_rate", "atom_match_floor"):
        parameter = signature.parameters[name]
        assert parameter.default is inspect.Parameter.empty, f"{name} must have no default"
        assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
    stream = matchkit.witness_stream(["alfa"])
    with pytest.raises(TypeError):
        match_stream(stream, [matchkit.page(1, ["alfa"])])


def test_match_stream_rejects_bad_inputs(matchkit):
    canonical = matchkit.canonical_stream([("c0", "alfa", [("w-sentinel-3", "a0")])])
    with pytest.raises(ValueError, match="matches a witness stream"):
        match_stream(canonical, [matchkit.page(1, ["alfa"])], page_accept_rate=0.5, atom_match_floor=0.5)
    stream = matchkit.witness_stream(["alfa"])
    with pytest.raises(ValueError, match="at least one PageGeometry"):
        match_stream(stream, [], page_accept_rate=0.5, atom_match_floor=0.5)
    with pytest.raises(ValueError, match="consecutive scan range"):
        match_stream(
            stream,
            [matchkit.page(2, ["alfa"]), matchkit.page(1, ["alfa"])],
            page_accept_rate=0.5,
            atom_match_floor=0.5,
        )
    with pytest.raises(ValueError, match="consecutive scan range"):
        # a gap is as unrepresentable as a reversal: the derived windows would name a page the
        # sidecar has no record for
        match_stream(
            stream,
            [matchkit.page(1, ["alfa"]), matchkit.page(3, ["alfa"])],
            page_accept_rate=0.5,
            atom_match_floor=0.5,
        )
    with pytest.raises(ValueError, match="must be a rate"):
        match_stream(stream, [matchkit.page(1, ["alfa"])], page_accept_rate=1.5, atom_match_floor=0.5)


def test_cross_page_atom_assigned_to_majority_page_earliest_on_tie(matchkit):
    # DT-3: the derived window records every overlapped page; the assigned page is the majority
    # token overlap, earliest on a tie. The atom matches only within its assigned page — the
    # honest v1 for straddlers (residue quantified in the run report).
    majority = matchkit.witness_stream(["k1 k2 k3", "k4 k5 k6 k7 k8"], ids=["head", "straddle"])
    pages = [matchkit.page(1, ["k1", "k2", "k3", "k4", "k5"]), matchkit.page(2, ["k6", "k7", "k8"])]
    outcome = match_stream(majority, pages, page_accept_rate=0.0, atom_match_floor=0.0)
    window = outcome.atom_pages["straddle"]
    assert (window.first, window.last, window.assigned) == (1, 2, 2)
    tie = matchkit.witness_stream(["k1 k2 k3", "k4 k5 k6 k7"], ids=["head", "straddle"])
    pages = [matchkit.page(1, ["k1", "k2", "k3", "k4", "k5"]), matchkit.page(2, ["k6", "k7"])]
    outcome = match_stream(tie, pages, page_accept_rate=0.0, atom_match_floor=0.0)
    window = outcome.atom_pages["straddle"]
    assert (window.first, window.last, window.assigned) == (1, 2, 1)


def test_tokenless_atom_is_addressed_and_zero_matched(matchkit):
    stream = matchkit.witness_stream(["alfa bravo charlie", "...", "delta echo fox"], ids=["a", "dots", "b"])
    pages = [matchkit.page(1, ["alfa", "bravo", "charlie"]), matchkit.page(2, ["delta", "echo", "fox"])]
    outcome = match_stream(stream, pages, page_accept_rate=0.5, atom_match_floor=0.5)
    assert outcome.token_counts["dots"] == 0
    record = outcome.atoms["dots"]
    assert record.status == ATOM_UNMATCHED and record.reason == REASON_ZERO_MATCH
    assert record.match_confidence == 0.0
    window = outcome.atom_pages["dots"]
    assert window.first == window.last == window.assigned == 1  # earliest page at the boundary


# --- attach_geometry: canonical mode (G-20 / G-25) ----------------------------------------- #


@pytest.fixture
def matched_world(matchkit):
    """A witness stream fully matched on one page, plus its sidecar — the base the canonical
    attach fixtures link into. Witness atom ids and canonical atom ids live in deliberately
    disjoint namespaces, so an id-lookup shortcut can never accidentally resolve (G-20)."""
    witness = matchkit.witness_stream(
        ["alfa bravo charlie", "delta echo foxtrot"], witness="w-anchor", ids=["w-one", "w-two"]
    )
    page = matchkit.page(1, ["alfa", "bravo", "charlie", "delta", "echo", "foxtrot"])
    outcome = match_stream(witness, [page], page_accept_rate=0.5, atom_match_floor=0.5)
    return witness, build(outcome)


def test_canonical_attach_resolves_through_derived_from_not_id(matchkit, matched_world):
    witness, sidecar = matched_world
    canonical = matchkit.canonical_stream(
        [("canon-1", "alfa bravo charlie", [("w-anchor", "w-one")])]
    )
    result = attach_geometry(canonical, sidecar, witness_stream=witness)
    geom = result.atoms[0].geom
    assert geom.present and geom.matched_witness_id == "w-anchor"
    assert result.outcomes["canon-1"].status == OUTCOME_MATCHED


def test_canonical_multi_primary_is_unmatched_never_union_or_first_pick(matchkit, matched_world):
    # G-20: both back-linked witness atoms are MATCHED with different bboxes — a mutant that
    # unions them or picks the first produces a present geom and reds here.
    witness, sidecar = matched_world
    canonical = matchkit.canonical_stream(
        [("canon-multi", "alfa bravo charlie delta echo foxtrot",
          [("w-anchor", "w-one"), ("w-anchor", "w-two")])]
    )
    result = attach_geometry(canonical, sidecar, witness_stream=witness)
    geom = result.atoms[0].geom
    assert not geom.present and geom.bbox is None
    outcome = result.outcomes["canon-multi"]
    assert outcome.status == OUTCOME_UNMATCHED
    assert outcome.reason == REASON_MULTI_PRIMARY_DERIVATION


def test_no_primary_derivation_is_ineligible_never_a_match_failure(matchkit, matched_world):
    # G-25: a canonical atom derived only from another witness is *ineligible* — its outcome is
    # not "unmatched", it carries the eligibility reason, and it lands in the eligibility coverage
    # counter, never the match-failure one.
    witness, sidecar = matched_world
    canonical = matchkit.canonical_stream(
        [
            ("canon-1", "alfa bravo charlie", [("w-anchor", "w-one")]),
            ("canon-other", "golf hotel india", [("w-other", "other-a0")]),
        ]
    )
    result = attach_geometry(canonical, sidecar, witness_stream=witness)
    outcome = result.outcomes["canon-other"]
    assert outcome.status == OUTCOME_INELIGIBLE
    assert outcome.status != OUTCOME_UNMATCHED
    assert outcome.reason == REASON_NO_PRIMARY_DERIVATION
    assert not result.atoms[1].geom.present


def test_canonical_coverage_counters_count_by_cause(matchkit, matched_world):
    witness, sidecar = matched_world
    canonical = matchkit.canonical_stream(
        [
            ("canon-1", "alfa bravo charlie", [("w-anchor", "w-one")]),
            ("canon-other", "golf hotel india", [("w-other", "other-a0")]),
            ("canon-multi", "alfa delta", [("w-anchor", "w-one"), ("w-anchor", "w-two")]),
        ]
    )
    page = matchkit.page(1, ["alfa", "bravo", "charlie", "delta", "echo", "foxtrot"])
    outcome = match_stream(witness, [page], page_accept_rate=0.5, atom_match_floor=0.5)
    sidecar = build(outcome, canonical_stream=canonical)
    assert sidecar.coverage["canonical_no_primary_derivation"] == 1
    assert sidecar.coverage["canonical_multi_primary_derivation"] == 1
    # eligibility is not match failure: the unmatched-on-accepted-pages counter saw neither
    assert sidecar.coverage["atoms_unmatched_on_accepted_pages"] == 0


def test_attach_mode_arguments_are_validated(matchkit, matched_world):
    witness, sidecar = matched_world
    canonical = matchkit.canonical_stream([("canon-1", "alfa", [("w-anchor", "w-one")])])
    with pytest.raises(ValueError, match="requires the matched witness stream"):
        attach_geometry(canonical, sidecar)
    with pytest.raises(ValueError, match="witness_stream must be a witness stream"):
        attach_geometry(canonical, sidecar, witness_stream=canonical)
    with pytest.raises(ValueError, match="takes no separate witness_stream"):
        attach_geometry(witness, sidecar, witness_stream=witness)


def test_attach_produces_new_instances_and_leaves_the_stream_untouched(matched_world):
    witness, sidecar = matched_world
    result = attach_geometry(witness, sidecar)
    assert all(not atom.geom.present for atom in witness.atoms)  # originals untouched
    assert all(atom.geom.present for atom in result.atoms)
    assert [a.atom_id for a in result.atoms] == [a.atom_id for a in witness.atoms]
    assert all(new is not old for new, old in zip(result.atoms, witness.atoms))


def test_page_below_accept_rate_routes_and_discards_tentative_outcomes(matchkit):
    # The matcher-side face of G-12 (the sidecar-state face lives in test_geom_sidecar): a page
    # under the accept rate routes at the match stage with the failing value, and none of its
    # atoms get records.
    stream = matchkit.witness_stream(["alfa bravo charlie golf hotel india"])
    page = matchkit.page(1, ["alfa", "kilo", "lima", "mike"])
    outcome = match_stream(stream, [page], page_accept_rate=0.8, atom_match_floor=0.5)
    record = outcome.pages[1]
    assert record.status == "routed"
    assert record.stage == "match" and record.signal == "match-rate"
    assert record.value == pytest.approx(1 / 6)
    assert outcome.atoms == {}


def test_empty_window_page_routes_as_a_locate_failure(matchkit):
    # All witness tokens sit on page 1; page 2's located window is empty -> routed at the locate
    # stage and counted in the coverage counter, never silently "matched with nothing".
    stream = matchkit.witness_stream(["alfa bravo charlie"])
    pages = [matchkit.page(1, ["alfa", "bravo", "charlie"]), matchkit.page(2, ["zulu"])]
    outcome = match_stream(stream, [pages[0], pages[1]], page_accept_rate=0.5, atom_match_floor=0.5)
    record = outcome.pages[2]
    assert record.status == "routed" and record.stage == "locate" and record.signal == "empty-window"
    assert outcome.locate_failed_pages == (2,)
    assert build(outcome).coverage["pages_locate_failed"] == 1


def test_zero_word_page_routes_as_a_locate_failure_not_a_crash(matchkit):
    # A genuinely blank page (zero words — DT-2's "empty ≠ failed") gets an empty bag and an
    # empty window: routed at the locate stage, never a crash or a silent "matched with nothing".
    stream = matchkit.witness_stream(["alfa bravo charlie"])
    pages = [matchkit.page(1, ["alfa", "bravo", "charlie"]), matchkit.page(2, [])]
    outcome = match_stream(stream, pages, page_accept_rate=0.5, atom_match_floor=0.5)
    assert outcome.pages[1].status == "matched"
    assert outcome.pages[2].status == "routed" and outcome.pages[2].stage == "locate"


def test_dropped_boxes_pass_through_to_page_records(matchkit):
    stream = matchkit.witness_stream(["alfa bravo charlie"])
    page = matchkit.page(1, ["alfa", "bravo", "charlie"])
    with_counts = match_stream(
        stream, [page], page_accept_rate=0.5, atom_match_floor=0.5, dropped_boxes={1: 4}
    )
    assert with_counts.pages[1].dropped_boxes == 4
    without = match_stream(stream, [page], page_accept_rate=0.5, atom_match_floor=0.5)
    assert without.pages[1].dropped_boxes is None  # no count is not the same claim as zero
