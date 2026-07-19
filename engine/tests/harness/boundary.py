"""Independent analytic boundary classifier for S4.7 INV-4.

The mandatory fixtures author opcode geometry directly; this module never calls a production
aligner. Boundaries are token gaps and blocks are half-open. The classifier therefore tests the
contract #48 must satisfy without allowing its tie-breaking to define expected truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

BoundaryClass = Literal[
    "clean-candidate", "edge-candidate", "no-candidate", "two-candidate"
]
BlockTag = Literal["equal", "replace", "delete", "insert", "unaligned"]


@dataclass(frozen=True, slots=True)
class AnalyticBlock:
    tag: BlockTag
    old_lo: int
    old_hi: int
    fresh_lo: int
    fresh_hi: int

    def __post_init__(self) -> None:
        if self.tag not in {"equal", "replace", "delete", "insert", "unaligned"}:
            raise ValueError(f"unknown analytic block tag {self.tag!r}")
        values = (self.old_lo, self.old_hi, self.fresh_lo, self.fresh_hi)
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in values
        ):
            raise ValueError("analytic block coordinates must be non-negative ints")
        if self.old_hi < self.old_lo or self.fresh_hi < self.fresh_lo:
            raise ValueError("analytic block intervals must be ordered")
        if self.tag == "insert" and self.old_lo != self.old_hi:
            raise ValueError("insert must have an empty old interval")
        if self.tag == "delete" and self.fresh_lo != self.fresh_hi:
            raise ValueError("delete must have an empty fresh interval")
        if self.tag in {"equal", "replace", "unaligned"} and self.old_lo == self.old_hi:
            raise ValueError(f"{self.tag} must cover at least one old token")


@dataclass(frozen=True, slots=True)
class BoundaryCase:
    name: str
    old_token_count: int
    blocks: tuple[AnalyticBlock, ...]
    boundary: int
    expected: BoundaryClass
    old_tokens: tuple[str, ...]
    fresh_tokens: tuple[str, ...]

    def __post_init__(self) -> None:
        if len(self.old_tokens) != self.old_token_count:
            raise ValueError(
                "BoundaryCase old_tokens length disagrees with old_token_count"
            )


def validate_analytic_tiling(
    old_token_count: int, blocks: tuple[AnalyticBlock, ...]
) -> None:
    if (
        isinstance(old_token_count, bool)
        or not isinstance(old_token_count, int)
        or old_token_count < 0
    ):
        raise ValueError("old_token_count must be an int >= 0")
    if not blocks:
        raise ValueError("analytic tiling must contain at least one block")
    old_cursor = fresh_cursor = 0
    for block in blocks:
        if block.old_lo != old_cursor or block.fresh_lo != fresh_cursor:
            raise ValueError(
                "analytic blocks must tile both streams without gaps/overlap"
            )
        if block.tag != "insert":
            old_cursor = block.old_hi
        fresh_cursor = block.fresh_hi
        if block.tag == "equal" and (
            block.old_hi - block.old_lo != block.fresh_hi - block.fresh_lo
        ):
            raise ValueError("equal analytic blocks must have equal old/fresh widths")
    if old_cursor != old_token_count:
        raise ValueError("analytic blocks do not cover the full old stream")
    for left, right in zip(blocks, blocks[1:]):
        if left.tag != "equal" and right.tag != "equal":
            raise ValueError("adjacent non-equal analytic blocks are forbidden")


def classify_boundary(
    old_token_count: int, blocks: tuple[AnalyticBlock, ...], boundary: int
) -> BoundaryClass:
    """Apply the ruled precedence: insert > strict interior > non-equal edge > clean."""
    validate_analytic_tiling(old_token_count, blocks)
    if (
        isinstance(boundary, bool)
        or not isinstance(boundary, int)
        or not 0 <= boundary <= old_token_count
    ):
        raise ValueError(f"boundary {boundary!r} outside [0, {old_token_count}]")

    if any(block.tag == "insert" and block.old_lo == boundary for block in blocks):
        return "two-candidate"
    if any(
        block.tag in {"replace", "delete", "unaligned"}
        and block.old_lo < boundary < block.old_hi
        for block in blocks
    ):
        return "no-candidate"

    def token_tag(token_index: int) -> str:
        if token_index < 0 or token_index >= old_token_count:
            return "equal"
        return next(
            block.tag
            for block in blocks
            if block.tag != "insert" and block.old_lo <= token_index < block.old_hi
        )

    if token_tag(boundary - 1) != "equal" or token_tag(boundary) != "equal":
        return "edge-candidate"
    return "clean-candidate"


def mandatory_boundary_cases() -> tuple[BoundaryCase, ...]:
    equal = AnalyticBlock("equal", 0, 4, 0, 4)
    return (
        BoundaryCase(
            "clean",
            4,
            (equal,),
            2,
            "clean-candidate",
            ("a", "b", "c", "d"),
            ("a", "b", "c", "d"),
        ),
        BoundaryCase(
            "replace-edge",
            4,
            (
                AnalyticBlock("replace", 0, 2, 0, 2),
                AnalyticBlock("equal", 2, 4, 2, 4),
            ),
            2,
            "edge-candidate",
            ("a", "b", "c", "d"),
            ("x", "y", "c", "d"),
        ),
        BoundaryCase(
            "replace-interior",
            4,
            (
                AnalyticBlock("equal", 0, 1, 0, 1),
                AnalyticBlock("replace", 1, 3, 1, 3),
                AnalyticBlock("equal", 3, 4, 3, 4),
            ),
            2,
            "no-candidate",
            ("a", "b", "c", "d"),
            ("a", "x", "y", "d"),
        ),
        BoundaryCase(
            "delete-interior",
            4,
            (
                AnalyticBlock("equal", 0, 1, 0, 1),
                AnalyticBlock("delete", 1, 3, 1, 1),
                AnalyticBlock("equal", 3, 4, 1, 2),
            ),
            2,
            "no-candidate",
            ("a", "b", "c", "d"),
            ("a", "d"),
        ),
        BoundaryCase(
            "insert-at-gap",
            4,
            (
                AnalyticBlock("equal", 0, 2, 0, 2),
                AnalyticBlock("insert", 2, 2, 2, 3),
                AnalyticBlock("equal", 2, 4, 3, 5),
            ),
            2,
            "two-candidate",
            ("a", "b", "c", "d"),
            ("a", "b", "x", "c", "d"),
        ),
        BoundaryCase(
            "capped-gap",
            5,
            (
                AnalyticBlock("equal", 0, 1, 0, 1),
                AnalyticBlock("unaligned", 1, 4, 1, 4),
                AnalyticBlock("equal", 4, 5, 4, 5),
            ),
            2,
            "no-candidate",
            ("a", "b", "c", "d", "e"),
            ("a", "w", "x", "y", "e"),
        ),
        BoundaryCase(
            "stream-start-edge",
            4,
            (
                AnalyticBlock("replace", 0, 1, 0, 1),
                AnalyticBlock("equal", 1, 4, 1, 4),
            ),
            0,
            "edge-candidate",
            ("a", "b", "c", "d"),
            ("x", "b", "c", "d"),
        ),
        BoundaryCase(
            "empty-old-insert",
            0,
            (AnalyticBlock("insert", 0, 0, 0, 2),),
            0,
            "two-candidate",
            (),
            ("x", "y"),
        ),
    )
