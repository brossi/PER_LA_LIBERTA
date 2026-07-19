"""S4.7/#48 production conformance tests for anchored alignment and v3 anchors."""

from __future__ import annotations

import random
from collections.abc import Sequence

from rapidfuzz.distance import Indel, Levenshtein

from engine.structure.boundary_anchor import (
    BOUNDARY_ANCHOR_FOOTPRINT_W,
    DeterministicBoundaryAnchorFamily,
    derive_boundary_anchor,
)
from engine.structure.reanchor import (
    ALIGNMENT_ANCHOR_K,
    ALIGNMENT_BACKEND_ID,
    ALIGNMENT_GAP_CAP,
    NEAR_DUPLICATE_MAX_LENGTH_RATIO,
    NEAR_DUPLICATE_MIN_CHAIN_DENSITY,
    AnchoredAlignment,
    AlignmentBlock,
    BoundaryAnchorBatchLocator,
    align_token_streams,
    locate_boundary_anchor,
    materialize_token_stream,
    unique_anchor_chain,
)
from harness.materialize import AtomSeed, FixtureSpec, NodeSeed, materialize_fixture
from harness.materialize import DriftConfig as FixtureDriftConfig


def test_alignment_contract_constants_and_backend_identity_are_pinned():
    assert ALIGNMENT_ANCHOR_K == 3
    assert ALIGNMENT_GAP_CAP == 512
    assert NEAR_DUPLICATE_MAX_LENGTH_RATIO == 4.0
    assert NEAR_DUPLICATE_MIN_CHAIN_DENSITY == 1.0 / 1024.0
    assert ALIGNMENT_BACKEND_ID == (
        "rapidfuzz@3.14.5:Levenshtein.opcodes;weights=unit;"
        "replace=single-block;tie=backend-deterministic"
    )


def test_backend_variant_pins_replace_opcode_semantics():
    old, fresh = ("alpha",), ("omega",)
    assert [opcode.tag for opcode in Levenshtein.opcodes(old, fresh)] == ["replace"]
    assert [opcode.tag for opcode in Indel.opcodes(old, fresh)] == ["insert", "delete"]
    production = align_token_streams(
        ("alpha", "beta", "gamma", "delta"),
        ("alpha", "beta", "omega", "delta"),
    )
    assert [block.tag for block in production.blocks] == ["equal", "replace", "equal"]

    # This overlap has genuinely different optimal opcode geometry under the two backends even
    # after adjacent insert/delete normalization, so the production contract—not just a direct
    # RapidFuzz observation—pins the chosen variant.
    distinguishing = align_token_streams(("a", "b"), ("b", "c"))
    assert distinguishing.blocks == (AlignmentBlock("replace", 0, 2, 0, 2),)
    assert not distinguishing.identity


def test_identical_alignment_is_one_equal_block_without_kgram_indexing(monkeypatch):
    import engine.structure.reanchor as reanchor_module

    tokens = tuple(f"token-{index}" for index in range(10_000))

    def forbidden_chain(*_args, **_kwargs):
        raise AssertionError("identity alignment must not build k-gram indexes")

    monkeypatch.setattr(reanchor_module, "unique_anchor_chain", forbidden_chain)
    alignment = align_token_streams(tokens, tokens)
    assert alignment.identity
    assert alignment.near_duplicate
    assert alignment.chained_anchors == ()
    assert alignment.blocks == (
        AlignmentBlock("equal", 0, len(tokens), 0, len(tokens)),
    )
    assert alignment.anchor_density == 1.0
    assert alignment.project_boundary(5_000).candidates == (5_000,)

    empty = align_token_streams((), ())
    assert empty.identity and empty.blocks == () and empty.anchor_density == 1.0


def test_unique_anchor_chain_is_monotone_when_raw_landmarks_cross():
    old = tuple(f"token-{index}" for index in range(18))
    fresh = old[9:15] + old[:9] + old[15:]
    chain = unique_anchor_chain(old, fresh)
    assert chain
    assert all(
        left[0] < right[0] and left[1] < right[1]
        for left, right in zip(chain, chain[1:], strict=False)
    )
    assert len(chain) < len(old) - ALIGNMENT_ANCHOR_K + 1


def test_gap_above_fixed_cap_becomes_one_synthetic_unaligned_block():
    old = (
        ("head-a", "head-b", "head-c")
        + tuple(f"old-{index}" for index in range(ALIGNMENT_GAP_CAP + 1))
        + ("tail-a", "tail-b", "tail-c")
    )
    fresh = (
        ("head-a", "head-b", "head-c")
        + tuple(f"fresh-{index}" for index in range(ALIGNMENT_GAP_CAP + 1))
        + ("tail-a", "tail-b", "tail-c")
    )
    alignment = align_token_streams(old, fresh)
    unaligned = [block for block in alignment.blocks if block.tag == "unaligned"]
    assert len(unaligned) == 1
    assert unaligned[0].old_hi - unaligned[0].old_lo == ALIGNMENT_GAP_CAP + 1
    assert unaligned[0].fresh_hi - unaligned[0].fresh_lo == ALIGNMENT_GAP_CAP + 1


def test_near_duplicate_precheck_rejects_extreme_length_skew_before_alignment():
    alignment = align_token_streams(
        tuple(f"old-{index}" for index in range(600)),
        tuple(f"fresh-{index}" for index in range(3_000)),
    )
    assert not alignment.near_duplicate
    assert alignment.blocks == ()


def test_half_open_production_boundary_projection_precedence():
    alignment = AnchoredAlignment(
        ("a", "b", "c"),
        ("a", "insert", "x", "c"),
        (
            AlignmentBlock("equal", 0, 1, 0, 1),
            AlignmentBlock("insert", 1, 1, 1, 2),
            AlignmentBlock("replace", 1, 2, 2, 3),
            AlignmentBlock("equal", 2, 3, 3, 4),
        ),
        (),
        True,
    )
    assert alignment.project_boundary(1).boundary_class == "two-candidate"
    assert alignment.project_boundary(2).boundary_class == "edge-candidate"

    interior = AnchoredAlignment(
        ("a", "b", "c", "d"),
        ("a", "x", "d"),
        (
            AlignmentBlock("equal", 0, 1, 0, 1),
            AlignmentBlock("unaligned", 1, 3, 1, 2),
            AlignmentBlock("equal", 3, 4, 2, 3),
        ),
        (),
        True,
    )
    projection = interior.project_boundary(2)
    assert projection.boundary_class == "no-candidate"
    assert projection.fresh_window == (1, 2)


def test_v3_anchor_allocation_is_deterministic_content_only_and_bounded():
    tokens = tuple(f"token-{index}" for index in range(40))
    family = DeterministicBoundaryAnchorFamily()
    start = derive_boundary_anchor(family, tokens, 10, side="start")
    end = derive_boundary_anchor(family, tokens, 20, side="end")
    assert start == derive_boundary_anchor(family, tokens, 10, side="start")
    assert start.exact == ("token-10",) and len(start.prefix) == 1
    assert end.exact == ("token-19",) and len(end.suffix) == 1
    assert start.footprint == end.footprint == 6
    assert start.footprint <= BOUNDARY_ANCHOR_FOOTPRINT_W


def test_boundary_anchor_derivation_touches_only_bounded_local_context():
    class MeteredTokens(Sequence[str]):
        def __init__(self, size: int) -> None:
            self.size = size
            self.tokens_touched = 0

        def __len__(self) -> int:
            return self.size

        def __getitem__(self, key):
            if isinstance(key, slice):
                start, stop, step = key.indices(self.size)
                indexes = range(start, stop, step)
                self.tokens_touched += len(indexes)
                return tuple(f"token-{index}" for index in indexes)
            index = key if key >= 0 else self.size + key
            if not 0 <= index < self.size:
                raise IndexError(index)
            self.tokens_touched += 1
            return f"token-{index}"

    tokens = MeteredTokens(10_000_000)
    anchor = derive_boundary_anchor(
        DeterministicBoundaryAnchorFamily(), tokens, 5_000_000, side="start"
    )
    assert anchor.exact == ("token-5000000",)
    assert tokens.tokens_touched <= 3 * BOUNDARY_ANCHOR_FOOTPRINT_W


def test_anchor_location_tolerates_one_token_substitution_but_rejects_repeat_ties():
    old = tuple(f"token-{index}" for index in range(12))
    family = DeterministicBoundaryAnchorFamily()
    anchor = derive_boundary_anchor(family, old, 3, side="start")
    edited = list(old)
    edited[5] = "changed"
    located = locate_boundary_anchor(anchor, edited, side="start", threshold=0.75)
    assert located.boundaries == (3,)

    repeated = old + old
    tied = locate_boundary_anchor(anchor, repeated, side="start", threshold=0.75)
    assert tied.boundaries == (3, 15)

    weaker_copy = list(old)
    weaker_copy[5] = "changed"
    exact_plus_weaker = old + tuple(weaker_copy)
    strongest = locate_boundary_anchor(
        anchor, exact_plus_weaker, side="start", threshold=0.75
    )
    assert strongest.boundaries == (3,)


def test_batch_anchor_locator_matches_single_query_semantics_and_scans_per_width():
    old = tuple(f"token-{index}" for index in range(18))
    family = DeterministicBoundaryAnchorFamily()
    anchors = (
        (derive_boundary_anchor(family, old, 3, side="start"), "start"),
        (derive_boundary_anchor(family, old, 9, side="end"), "end"),
    )
    fresh = old + old
    batch = BoundaryAnchorBatchLocator(fresh, anchors * 50, threshold=0.75)
    assert batch.windows_scanned == len(fresh) - anchors[0][0].footprint + 1
    for anchor, side in anchors:
        assert batch.locate(anchor, side=side) == locate_boundary_anchor(
            anchor, fresh, side=side, threshold=0.75
        )

    edited = list(old)
    edited[5] = "changed"
    mixed = old + tuple(edited)
    fuzzy = BoundaryAnchorBatchLocator(mixed, anchors, threshold=0.75)
    for anchor, side in anchors:
        assert fuzzy.locate(anchor, side=side) == locate_boundary_anchor(
            anchor, mixed, side=side, threshold=0.75
        )


def test_batch_anchor_locator_resolves_exact_ties_without_fuzzy_signatures():
    old = tuple(f"token-{index}" for index in range(18))
    family = DeterministicBoundaryAnchorFamily()
    anchor = derive_boundary_anchor(family, old, 3, side="start")
    repeated = old + old
    batch = BoundaryAnchorBatchLocator(repeated, ((anchor, "start"),), threshold=0.75)

    assert batch.locate(anchor, side="start") == locate_boundary_anchor(
        anchor, repeated, side="start", threshold=0.75
    )
    assert len(batch.locate(anchor, side="start").boundaries) == 2
    assert batch.exact_resolved_query_count == 1
    assert batch.exact_windows_scanned == len(repeated) - anchor.footprint + 1
    assert batch.fuzzy_windows_scanned == 0
    assert batch.fuzzy_searched_query_count == 0
    assert batch.signature_count == 0


def test_batch_anchor_locator_falls_back_to_fuzzy_only_for_unresolved_queries():
    old = tuple(f"token-{index}" for index in range(18))
    family = DeterministicBoundaryAnchorFamily()
    boundary = 6
    anchor = derive_boundary_anchor(family, old, boundary, side="start")
    fresh = list(old)
    fresh[boundary - len(anchor.prefix)] = "changed"
    fresh_tokens = tuple(fresh)
    batch = BoundaryAnchorBatchLocator(
        fresh_tokens, ((anchor, "start"),), threshold=0.75
    )

    assert batch.locate(anchor, side="start") == locate_boundary_anchor(
        anchor, fresh_tokens, side="start", threshold=0.75
    )
    assert batch.fuzzy_resolved_query_count == 1
    assert batch.fuzzy_searched_query_count == 1
    assert batch.fuzzy_windows_scanned == len(fresh_tokens) - anchor.footprint + 1
    assert batch.signature_count > 0


def test_batch_anchor_locator_matches_bruteforce_under_bounded_random_edits():
    rng = random.Random(4817)
    family = DeterministicBoundaryAnchorFamily()
    vocabulary = tuple("abcdef")
    for _ in range(30):
        old = tuple(rng.choice(vocabulary) for _ in range(18))
        queries = tuple(
            (derive_boundary_anchor(family, old, boundary, side=side), side)
            for boundary, side in ((3, "start"), (8, "end"), (12, "start"))
        )
        fresh = list(old)
        for _ in range(rng.randrange(3)):
            fresh[rng.randrange(len(fresh))] = rng.choice(vocabulary)
        fresh_tuple = tuple(fresh)
        for threshold in (0.5, 0.75, 1.0):
            batch = BoundaryAnchorBatchLocator(
                fresh_tuple, queries, threshold=threshold
            )
            for anchor, side in queries:
                assert batch.locate(anchor, side=side) == locate_boundary_anchor(
                    anchor, fresh_tuple, side=side, threshold=threshold
                )


def test_token_boundary_inside_one_fresh_atom_is_not_representable():
    spec = FixtureSpec(
        root_id="root",
        nodes=(
            NodeSeed("root", "volume", "container", children=("leaf",)),
            NodeSeed("leaf", "block", "leaf", body=("a0",)),
        ),
        atoms=(AtomSeed("a0", "alpha beta", "leaf", "body"),),
        require_tokenless_cases=False,
    )
    fixture = materialize_fixture(spec, FixtureDriftConfig("merged-atom", 3701, ()))
    stream = materialize_token_stream(fixture.fresh_canonical)
    assert stream.atom_boundary_for_token_boundary(1) is None


def test_indexed_atom_boundary_lookup_matches_linear_tokenless_gap_semantics():
    spec = FixtureSpec(
        root_id="root",
        nodes=(
            NodeSeed("root", "volume", "container", children=("leaf",)),
            NodeSeed(
                "leaf",
                "block",
                "leaf",
                body=("a0", "a1", "a2", "a3"),
            ),
        ),
        atoms=(
            AtomSeed("a0", "alpha", "leaf", "body"),
            AtomSeed("a1", "", "leaf", "body"),
            AtomSeed("a2", "", "leaf", "body"),
            AtomSeed("a3", "beta gamma", "leaf", "body"),
        ),
        require_tokenless_cases=False,
    )
    fixture = materialize_fixture(spec, FixtureDriftConfig("tokenless-index", 3702, ()))
    stream = materialize_token_stream(fixture.fresh_canonical)

    def linear_reference(
        boundary: int,
        old_gap_offset: int | None,
        old_tokenless_texts: tuple[str, ...],
    ) -> int | None:
        if not 0 <= boundary <= len(stream.tokens):
            return None
        if any(start < boundary < end for start, end in stream.atom_token_ranges):
            return None
        left = 0
        while (
            left < len(stream.atom_ids)
            and stream.atom_token_ranges[left][1] <= boundary
        ):
            left += 1
        gap_start = left
        while gap_start and stream.atom_token_ranges[gap_start - 1] == (
            boundary,
            boundary,
        ):
            gap_start -= 1
        gap_end = gap_start
        while (
            gap_end < len(stream.atom_ids)
            and stream.atom_token_ranges[gap_end] == (boundary, boundary)
        ):
            gap_end += 1
        if old_gap_offset is None:
            return gap_start if gap_start == gap_end else None
        if not 0 <= old_gap_offset <= gap_end - gap_start:
            return None
        if (
            tuple(stream.atom_texts[gap_start : gap_start + old_gap_offset])
            != old_tokenless_texts
        ):
            return None
        return gap_start + old_gap_offset

    for boundary in range(-1, len(stream.tokens) + 2):
        for old_gap_offset in (None, 0, 1, 2, 3):
            for old_tokenless_texts in ((), ("",), ("", ""), ("wrong",)):
                lookup = stream.lookup_atom_boundary_for_token_boundary(
                    boundary,
                    old_gap_offset=old_gap_offset,
                    old_tokenless_texts=old_tokenless_texts,
                )
                assert lookup.atom_boundary == linear_reference(
                    boundary, old_gap_offset, old_tokenless_texts
                )
                assert lookup.inspected_ranges <= len(stream.atom_ids).bit_length() + 1

    assert stream.tokenless_gap_boundaries == (1,)
    assert stream.tokenless_gap_ranges == ((1, 3),)
