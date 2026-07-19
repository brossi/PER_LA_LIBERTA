"""Anchored, bounded-work token alignment for structure-map re-binding (S4.7/#48).

The module deliberately stops at token/atom arithmetic.  Policy (fingerprint thresholds,
geometry modes, report assembly, and the closed failure vocabulary) remains in ``rebind``.
"""

from __future__ import annotations

from bisect import bisect_left
from collections import defaultdict
from dataclasses import dataclass
from itertools import combinations
import math
from typing import Literal, Sequence

import rapidfuzz
from rapidfuzz.distance import Levenshtein

from engine.structure.atom_store import AtomStream
from engine.structure.atoms import PROCESSING_SCOPE_INCLUDED
from engine.structure.boundary_anchor import BoundaryAnchor, BoundarySide
from engine.structure.geom_match import normalize_tokens

# These are mechanism constants, not book calibration knobs.  Changing either invalidates the
# S4.7 confidence lock and the scale/correctness-at-density baselines.
ALIGNMENT_ANCHOR_K = 3
ALIGNMENT_GAP_CAP = 512
NEAR_DUPLICATE_MAX_LENGTH_RATIO = 4.0
NEAR_DUPLICATE_MIN_CHAIN_DENSITY = 1.0 / 1024.0

ALIGNMENT_BACKEND_ID = (
    f"rapidfuzz@{rapidfuzz.__version__}:Levenshtein.opcodes;"
    "weights=unit;replace=single-block;tie=backend-deterministic"
)

BlockTag = Literal["equal", "replace", "insert", "delete", "unaligned"]


@dataclass(frozen=True, slots=True)
class AtomBoundaryLookup:
    """One token-boundary conversion plus deterministic work diagnostics."""

    atom_boundary: int | None
    inspected_ranges: int
    outcome: str


@dataclass(frozen=True, slots=True)
class TokenAtomStream:
    """A normalized included-token stream with total token↔atom back-pointers."""

    tokens: tuple[str, ...]
    atom_ids: tuple[str, ...]
    atom_pages: tuple[int | None, ...]
    token_atom_indexes: tuple[int, ...]
    atom_token_ranges: tuple[tuple[int, int], ...]
    atom_texts: tuple[str, ...]
    atom_token_range_ends: tuple[int, ...]
    tokenless_gap_boundaries: tuple[int, ...]
    tokenless_gap_ranges: tuple[tuple[int, int], ...]

    def _first_atom_ending_after(self, boundary: int) -> tuple[int, int]:
        """Return the first range whose end exceeds ``boundary`` plus comparisons made."""
        lo = 0
        hi = len(self.atom_token_range_ends)
        inspected_ranges = 0
        while lo < hi:
            mid = (lo + hi) // 2
            inspected_ranges += 1
            if self.atom_token_range_ends[mid] <= boundary:
                lo = mid + 1
            else:
                hi = mid
        return lo, inspected_ranges

    def lookup_atom_boundary_for_token_boundary(
        self,
        boundary: int,
        *,
        old_gap_offset: int | None = None,
        old_tokenless_texts: tuple[str, ...] = (),
    ) -> AtomBoundaryLookup:
        """Return a representable atom gap and the number of atom ranges inspected.

        A token boundary inside a token-bearing atom is unrepresentable.  When tokenless atoms
        occupy the token gap, a preserved old offset is admitted only when the corresponding
        tokenless text prefix is byte-identical; otherwise ownership is not invented.

        Monotone atom token-range ends provide an indexed first-candidate lookup.  Separate compact
        tokenless-gap metadata preserves the old within-gap offset rules without walking backward or
        forward through the atom stream.  ``inspected_ranges`` counts binary-search comparisons plus
        the one candidate range checked for an inside-atom boundary.
        """
        if not 0 <= boundary <= len(self.tokens):
            return AtomBoundaryLookup(None, 0, "out-of-range")
        left, inspected_ranges = self._first_atom_ending_after(boundary)
        if left < len(self.atom_token_ranges):
            start, end = self.atom_token_ranges[left]
            inspected_ranges += 1
            if start < boundary < end:
                return AtomBoundaryLookup(None, inspected_ranges, "inside-atom")

        gap_index = bisect_left(self.tokenless_gap_boundaries, boundary)
        if (
            gap_index < len(self.tokenless_gap_boundaries)
            and self.tokenless_gap_boundaries[gap_index] == boundary
        ):
            gap_start, gap_end = self.tokenless_gap_ranges[gap_index]
        else:
            gap_start = gap_end = left

        if old_gap_offset is None:
            return AtomBoundaryLookup(
                gap_start if gap_start == gap_end else None,
                inspected_ranges,
                "resolved" if gap_start == gap_end else "tokenless-offset-required",
            )
        if not 0 <= old_gap_offset <= gap_end - gap_start:
            return AtomBoundaryLookup(
                None, inspected_ranges, "tokenless-offset-out-of-range"
            )
        fresh_prefix = self.atom_texts[gap_start : gap_start + old_gap_offset]
        if tuple(fresh_prefix) != old_tokenless_texts:
            return AtomBoundaryLookup(
                None, inspected_ranges, "tokenless-prefix-mismatch"
            )
        return AtomBoundaryLookup(
            gap_start + old_gap_offset, inspected_ranges, "resolved"
        )

    def atom_boundary_for_token_boundary(
        self,
        boundary: int,
        *,
        old_gap_offset: int | None = None,
        old_tokenless_texts: tuple[str, ...] = (),
    ) -> int | None:
        """Return a representable atom gap for ``boundary`` or ``None``."""
        return self.lookup_atom_boundary_for_token_boundary(
            boundary,
            old_gap_offset=old_gap_offset,
            old_tokenless_texts=old_tokenless_texts,
        ).atom_boundary


def materialize_token_stream(stream: AtomStream) -> TokenAtomStream:
    tokens: list[str] = []
    atom_ids: list[str] = []
    atom_pages: list[int | None] = []
    token_atom_indexes: list[int] = []
    atom_ranges: list[tuple[int, int]] = []
    atom_texts: list[str] = []
    atom_range_ends: list[int] = []
    tokenless_gap_boundaries: list[int] = []
    tokenless_gap_ranges: list[tuple[int, int]] = []
    for atom in stream.atoms:
        if atom.processing_scope != PROCESSING_SCOPE_INCLUDED:
            continue
        atom_index = len(atom_ids)
        atom_ids.append(atom.atom_id)
        atom_pages.append(atom.geom.page if atom.geom.present else None)
        atom_texts.append(atom.text)
        start = len(tokens)
        normalized = normalize_tokens(atom.text)
        tokens.extend(normalized)
        token_atom_indexes.extend([atom_index] * len(normalized))
        end = len(tokens)
        atom_ranges.append((start, end))
        atom_range_ends.append(end)
        if start == end:
            if tokenless_gap_boundaries and tokenless_gap_boundaries[-1] == start:
                gap_start, _ = tokenless_gap_ranges[-1]
                tokenless_gap_ranges[-1] = (gap_start, atom_index + 1)
            else:
                tokenless_gap_boundaries.append(start)
                tokenless_gap_ranges.append((atom_index, atom_index + 1))
    return TokenAtomStream(
        tokens=tuple(tokens),
        atom_ids=tuple(atom_ids),
        atom_pages=tuple(atom_pages),
        token_atom_indexes=tuple(token_atom_indexes),
        atom_token_ranges=tuple(atom_ranges),
        atom_texts=tuple(atom_texts),
        atom_token_range_ends=tuple(atom_range_ends),
        tokenless_gap_boundaries=tuple(tokenless_gap_boundaries),
        tokenless_gap_ranges=tuple(tokenless_gap_ranges),
    )


@dataclass(frozen=True, slots=True)
class AlignmentBlock:
    tag: BlockTag
    old_lo: int
    old_hi: int
    fresh_lo: int
    fresh_hi: int


@dataclass(frozen=True, slots=True)
class BoundaryProjection:
    boundary_class: str
    candidates: tuple[int, ...]
    fresh_window: tuple[int, int]


@dataclass(frozen=True, slots=True)
class AnchoredAlignment:
    old_tokens: tuple[str, ...]
    fresh_tokens: tuple[str, ...]
    blocks: tuple[AlignmentBlock, ...]
    chained_anchors: tuple[tuple[int, int], ...]
    near_duplicate: bool
    identity: bool = False

    @property
    def anchor_density(self) -> float:
        if self.identity:
            return 1.0
        denominator = min(len(self.old_tokens), len(self.fresh_tokens))
        return (
            min(1.0, len(self.chained_anchors) * ALIGNMENT_ANCHOR_K / denominator)
            if denominator
            else 1.0
        )

    def project_boundary(self, boundary: int) -> BoundaryProjection:
        if not 0 <= boundary <= len(self.old_tokens):
            raise ValueError(f"old token boundary {boundary} is outside the alignment")
        inserts = [
            block
            for block in self.blocks
            if block.tag == "insert" and block.old_lo == block.old_hi == boundary
        ]
        if inserts:
            block = inserts[0]
            return BoundaryProjection(
                "two-candidate",
                (block.fresh_lo, block.fresh_hi),
                (block.fresh_lo, block.fresh_hi),
            )

        for block in self.blocks:
            if block.old_lo < boundary < block.old_hi:
                if block.tag == "equal":
                    projected = block.fresh_lo + boundary - block.old_lo
                    return BoundaryProjection(
                        "clean-candidate", (projected,), (projected, projected)
                    )
                return BoundaryProjection(
                    "no-candidate", (), (block.fresh_lo, block.fresh_hi)
                )

        touching = [
            block
            for block in self.blocks
            if block.old_lo == boundary or block.old_hi == boundary
        ]
        non_equal = [block for block in touching if block.tag != "equal"]
        if non_equal:
            candidates: set[int] = set()
            windows: list[int] = []
            for block in non_equal:
                if block.old_lo == boundary:
                    candidates.add(block.fresh_lo)
                if block.old_hi == boundary:
                    candidates.add(block.fresh_hi)
                windows.extend((block.fresh_lo, block.fresh_hi))
            return BoundaryProjection(
                "edge-candidate",
                tuple(sorted(candidates)),
                (min(windows), max(windows)),
            )

        for block in touching:
            if block.tag == "equal":
                projected = (
                    block.fresh_lo if block.old_lo == boundary else block.fresh_hi
                )
                return BoundaryProjection(
                    "clean-candidate", (projected,), (projected, projected)
                )
        # Only the empty/empty alignment reaches this path.
        return BoundaryProjection("clean-candidate", (0,), (0, 0))


def _kgram_positions(tokens: Sequence[str], k: int) -> dict[tuple[str, ...], list[int]]:
    positions: dict[tuple[str, ...], list[int]] = defaultdict(list)
    for index in range(max(0, len(tokens) - k + 1)):
        positions[tuple(tokens[index : index + k])].append(index)
    return positions


def _lis_pairs(pairs: Sequence[tuple[int, int]]) -> list[tuple[int, int]]:
    """Patience LIS on fresh positions, deterministic toward the earliest chain."""
    if not pairs:
        return []
    tails: list[int] = []
    tails_pair: list[int] = []
    previous = [-1] * len(pairs)
    for pair_index, (_, fresh) in enumerate(pairs):
        level = bisect_left(tails, fresh)
        if level == len(tails):
            tails.append(fresh)
            tails_pair.append(pair_index)
        elif fresh < tails[level]:
            tails[level] = fresh
            tails_pair[level] = pair_index
        if level:
            previous[pair_index] = tails_pair[level - 1]
    cursor = tails_pair[-1]
    result: list[tuple[int, int]] = []
    while cursor >= 0:
        result.append(pairs[cursor])
        cursor = previous[cursor]
    result.reverse()
    # Overlapping k-grams carry duplicate evidence and complicate gap tiling.  Keep a maximal
    # non-overlapping subsequence; the work bound and monotonicity are unchanged.
    pruned: list[tuple[int, int]] = []
    for pair in result:
        if not pruned or (
            pair[0] >= pruned[-1][0] + ALIGNMENT_ANCHOR_K
            and pair[1] >= pruned[-1][1] + ALIGNMENT_ANCHOR_K
        ):
            pruned.append(pair)
    return pruned


def unique_anchor_chain(
    old_tokens: Sequence[str], fresh_tokens: Sequence[str]
) -> tuple[tuple[int, int], ...]:
    old_index = _kgram_positions(old_tokens, ALIGNMENT_ANCHOR_K)
    fresh_index = _kgram_positions(fresh_tokens, ALIGNMENT_ANCHOR_K)
    pairs = sorted(
        (old_positions[0], fresh_index[gram][0])
        for gram, old_positions in old_index.items()
        if len(old_positions) == 1
        and gram in fresh_index
        and len(fresh_index[gram]) == 1
    )
    return tuple(_lis_pairs(pairs))


def _append_block(blocks: list[AlignmentBlock], block: AlignmentBlock) -> None:
    if block.old_lo == block.old_hi and block.fresh_lo == block.fresh_hi:
        return
    if blocks:
        previous = blocks[-1]
        if (
            previous.tag == block.tag
            and previous.old_hi == block.old_lo
            and previous.fresh_hi == block.fresh_lo
        ):
            blocks[-1] = AlignmentBlock(
                previous.tag,
                previous.old_lo,
                block.old_hi,
                previous.fresh_lo,
                block.fresh_hi,
            )
            return
        if (
            previous.tag != "equal"
            and block.tag != "equal"
            and previous.old_hi == block.old_lo
            and previous.fresh_hi == block.fresh_lo
        ):
            # The INV-4 analytic contract admits one non-equal block between equals.  Normalize
            # backend insert/delete adjacency into that composite replace block.
            blocks[-1] = AlignmentBlock(
                "replace",
                previous.old_lo,
                block.old_hi,
                previous.fresh_lo,
                block.fresh_hi,
            )
            return
    blocks.append(block)


def _fill_gap(
    blocks: list[AlignmentBlock],
    old: Sequence[str],
    fresh: Sequence[str],
    old_lo: int,
    old_hi: int,
    fresh_lo: int,
    fresh_hi: int,
) -> None:
    if max(old_hi - old_lo, fresh_hi - fresh_lo) > ALIGNMENT_GAP_CAP:
        _append_block(
            blocks,
            AlignmentBlock("unaligned", old_lo, old_hi, fresh_lo, fresh_hi),
        )
        return
    for opcode in Levenshtein.opcodes(old[old_lo:old_hi], fresh[fresh_lo:fresh_hi]):
        _append_block(
            blocks,
            AlignmentBlock(
                opcode.tag,
                old_lo + opcode.src_start,
                old_lo + opcode.src_end,
                fresh_lo + opcode.dest_start,
                fresh_lo + opcode.dest_end,
            ),
        )


def align_token_streams(
    old_tokens: Sequence[str], fresh_tokens: Sequence[str]
) -> AnchoredAlignment:
    old, fresh = tuple(old_tokens), tuple(fresh_tokens)
    if old == fresh:
        blocks = (AlignmentBlock("equal", 0, len(old), 0, len(fresh)),) if old else ()
        return AnchoredAlignment(old, fresh, blocks, (), True, identity=True)
    chain = unique_anchor_chain(old, fresh)
    smaller, larger = sorted((len(old), len(fresh)))
    length_ratio = larger / max(1, smaller)
    density = (
        min(1.0, len(chain) * ALIGNMENT_ANCHOR_K / min(len(old), len(fresh)))
        if old and fresh
        else (1.0 if not old and not fresh else 0.0)
    )
    # A small stream is itself one bounded gap, so density cannot expose degenerate work.  Large
    # low-density or radically length-skewed inputs abstain before invoking an expensive backend.
    near_duplicate = length_ratio <= NEAR_DUPLICATE_MAX_LENGTH_RATIO and (
        max(len(old), len(fresh)) <= ALIGNMENT_GAP_CAP
        or density >= NEAR_DUPLICATE_MIN_CHAIN_DENSITY
    )
    if not near_duplicate:
        return AnchoredAlignment(old, fresh, (), chain, False)

    blocks: list[AlignmentBlock] = []
    old_cursor = fresh_cursor = 0
    for old_anchor, fresh_anchor in chain:
        _fill_gap(
            blocks,
            old,
            fresh,
            old_cursor,
            old_anchor,
            fresh_cursor,
            fresh_anchor,
        )
        _append_block(
            blocks,
            AlignmentBlock(
                "equal",
                old_anchor,
                old_anchor + ALIGNMENT_ANCHOR_K,
                fresh_anchor,
                fresh_anchor + ALIGNMENT_ANCHOR_K,
            ),
        )
        old_cursor = old_anchor + ALIGNMENT_ANCHOR_K
        fresh_cursor = fresh_anchor + ALIGNMENT_ANCHOR_K
    _fill_gap(
        blocks,
        old,
        fresh,
        old_cursor,
        len(old),
        fresh_cursor,
        len(fresh),
    )
    return AnchoredAlignment(old, fresh, tuple(blocks), chain, True)


@dataclass(frozen=True, slots=True)
class AnchorLocation:
    boundaries: tuple[int, ...]
    best_score: float


AnchorQuery = tuple[BoundaryAnchor, BoundarySide]


def _deletion_signatures(tokens: tuple[str, ...], deletions: int):
    if deletions == 0:
        yield tokens
        return
    if deletions == 1:
        for index in range(len(tokens)):
            yield tokens[:index] + tokens[index + 1 :]
        return
    for removed in combinations(range(len(tokens)), deletions):
        removed_set = frozenset(removed)
        yield tuple(
            token for index, token in enumerate(tokens) if index not in removed_set
        )


class BoundaryAnchorBatchLocator:
    """Resolve all stored v3 anchors with one scan per ``(width, edit-budget)`` group.

    The old per-slot locator scanned the complete stream for every slot (``O(K*T)``), negating the
    shared alignment at the production scale gate.  Here queries are deduplicated by their actual
    v3 value and side.  Query deletion signatures select candidate windows; RapidFuzz still makes
    the final score/tie decision, preserving the exact single-query semantics.  With the shipped
    six-token allocation and thresholds the edit budget is one, so each stream window performs six
    bounded signature lookups independent of slot count.
    """

    def __init__(
        self,
        tokens: Sequence[str],
        queries: Sequence[AnchorQuery],
        *,
        threshold: float,
    ) -> None:
        if (
            isinstance(threshold, bool)
            or not isinstance(threshold, (int, float))
            or not math.isfinite(threshold)
            or not 0.0 <= threshold <= 1.0
        ):
            raise ValueError("boundary-anchor threshold must be finite in [0, 1]")
        stream = tuple(tokens)
        unique_queries = tuple(dict.fromkeys(queries))
        grouped: dict[tuple[int, int], list[AnchorQuery]] = defaultdict(list)
        for query in unique_queries:
            anchor, side = query
            if side not in {"start", "end"}:
                raise ValueError(f"unknown boundary side {side!r}")
            width = anchor.footprint
            budget = min(
                width,
                max(0, math.floor((1.0 - float(threshold)) * width + 1e-12)),
            )
            grouped[(width, budget)].append(query)

        locations: dict[AnchorQuery, AnchorLocation] = {
            query: AnchorLocation((), 0.0) for query in unique_queries
        }
        exact_windows_scanned = 0
        fuzzy_windows_scanned = 0
        signature_count = 0
        fuzzy_searched_query_count = 0
        for (width, budget), group in grouped.items():
            if width > len(stream):
                continue
            needles: dict[AnchorQuery, tuple[str, ...]] = {}
            exact_queries: dict[tuple[str, ...], list[AnchorQuery]] = defaultdict(list)
            for query in group:
                anchor, _ = query
                needle = anchor.prefix + anchor.exact + anchor.suffix
                needles[query] = needle
                exact_queries[needle].append(query)

            best_scores = {query: 0.0 for query in group}
            best_boundaries = {query: set() for query in group}
            for start in range(len(stream) - width + 1):
                exact_windows_scanned += 1
                window = stream[start : start + width]
                for query in exact_queries.get(window, ()):
                    anchor, side = query
                    boundary = start + len(anchor.prefix)
                    if side == "end":
                        boundary += len(anchor.exact)
                    best_scores[query] = 1.0
                    best_boundaries[query].add(boundary)

            unresolved = [query for query in group if not best_boundaries[query]]
            if unresolved and budget > 0:
                fuzzy_searched_query_count += len(unresolved)
                signature_queries: dict[tuple[str, ...], list[AnchorQuery]] = (
                    defaultdict(list)
                )
                for query in unresolved:
                    for signature in set(_deletion_signatures(needles[query], budget)):
                        signature_queries[signature].append(query)
                signature_count += len(signature_queries)

                for start in range(len(stream) - width + 1):
                    fuzzy_windows_scanned += 1
                    window = stream[start : start + width]
                    candidates: set[AnchorQuery] = set()
                    for signature in _deletion_signatures(window, budget):
                        candidates.update(signature_queries.get(signature, ()))
                    for query in candidates:
                        anchor, side = query
                        score = Levenshtein.normalized_similarity(
                            needles[query], window
                        )
                        if score < threshold:
                            continue
                        boundary = start + len(anchor.prefix)
                        if side == "end":
                            boundary += len(anchor.exact)
                        if score > best_scores[query]:
                            best_scores[query] = score
                            best_boundaries[query] = {boundary}
                        elif score == best_scores[query]:
                            best_boundaries[query].add(boundary)
            for query in group:
                locations[query] = AnchorLocation(
                    tuple(sorted(best_boundaries[query])), best_scores[query]
                )
        self._locations = locations
        self.exact_windows_scanned = exact_windows_scanned
        self.fuzzy_windows_scanned = fuzzy_windows_scanned
        self.windows_scanned = exact_windows_scanned + fuzzy_windows_scanned
        self.query_count = len(queries)
        self.unique_query_count = len(unique_queries)
        self.group_count = len(grouped)
        self.signature_count = signature_count
        self.fuzzy_searched_query_count = fuzzy_searched_query_count
        self.exact_resolved_query_count = sum(
            location.best_score == 1.0 for location in locations.values()
        )
        self.fuzzy_resolved_query_count = sum(
            0.0 < location.best_score < 1.0 for location in locations.values()
        )
        self.unresolved_query_count = sum(
            not location.boundaries for location in locations.values()
        )

    def locate(self, anchor: BoundaryAnchor, *, side: BoundarySide) -> AnchorLocation:
        try:
            return self._locations[(anchor, side)]
        except KeyError as exc:
            raise KeyError("boundary anchor was not registered in this batch") from exc


def locate_boundary_anchor(
    anchor: BoundaryAnchor,
    tokens: Sequence[str],
    *,
    side: BoundarySide,
    threshold: float,
) -> AnchorLocation:
    """Locate every whole-stream anchor window at or above ``threshold``."""
    needle = anchor.prefix + anchor.exact + anchor.suffix
    width = len(needle)
    scored: list[tuple[float, int]] = []
    if width <= len(tokens):
        for start in range(len(tokens) - width + 1):
            score = Levenshtein.normalized_similarity(
                needle, tuple(tokens[start : start + width])
            )
            if score >= threshold:
                boundary = start + len(anchor.prefix)
                if side == "end":
                    boundary += len(anchor.exact)
                scored.append((score, boundary))
    if not scored:
        return AnchorLocation((), 0.0)
    best = max(score for score, _ in scored)
    # Only maximum-score occurrences compete.  A weak approximate occurrence must not make an
    # otherwise exact anchor falsely non-unique.
    boundaries = tuple(
        sorted({boundary for score, boundary in scored if score == best})
    )
    return AnchorLocation(boundaries, best)


def tokenless_gap_context(
    stream: TokenAtomStream, atom_boundary: int, token_boundary: int
) -> tuple[int, tuple[str, ...]]:
    """Old within-token-gap offset + preserved tokenless prefix for one atom boundary."""
    gap_start = atom_boundary
    while gap_start and stream.atom_token_ranges[gap_start - 1] == (
        token_boundary,
        token_boundary,
    ):
        gap_start -= 1
    offset = atom_boundary - gap_start
    return offset, tuple(stream.atom_texts[gap_start:atom_boundary])
