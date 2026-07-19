"""Deterministic stored boundary anchors and their independent confidence gate (S4.7/#48)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, Sequence, runtime_checkable

BoundarySide = Literal["start", "end"]
BoundaryCandidateClass = Literal[
    "clean-candidate", "edge-candidate", "no-candidate", "two-candidate"
]

#: PR-5's fixed maximum total token footprint across prefix + exact + suffix.  A change to this
#: constant invalidates the DR-3 lock record and requires the S4.7 invariant manifest to be rerun.
BOUNDARY_ANCHOR_FOOTPRINT_W = 24


@dataclass(frozen=True, slots=True)
class BoundaryAnchor:
    """A deterministic, content-only prefix/exact/suffix boundary anchor value.

    The value contains no node id, structural path, ordinal, geometry, or absolute stream position.
    Those signals may independently corroborate a proposed match, but cannot contaminate the content
    anchor.  Item 2 validates only the interface; #48 owns the deterministic producer.
    """

    prefix: tuple[str, ...]
    exact: tuple[str, ...]
    suffix: tuple[str, ...]

    def __post_init__(self) -> None:
        for field_name in ("prefix", "exact", "suffix"):
            value = getattr(self, field_name)
            if not isinstance(value, tuple) or not all(
                isinstance(token, str) and token for token in value
            ):
                raise ValueError(
                    f"BoundaryAnchor.{field_name} must be a tuple of non-empty content tokens"
                )
        if not self.exact:
            raise ValueError(
                "BoundaryAnchor.exact must contain at least one content token"
            )
        if self.footprint > BOUNDARY_ANCHOR_FOOTPRINT_W:
            raise ValueError(
                f"boundary-anchor footprint {self.footprint} exceeds fixed W="
                f"{BOUNDARY_ANCHOR_FOOTPRINT_W}"
            )

    @property
    def footprint(self) -> int:
        """Total prefix + exact + suffix token count."""
        return len(self.prefix) + len(self.exact) + len(self.suffix)


@dataclass(frozen=True, slots=True)
class BoundaryConfirmation:
    """The confidence hook's evidence for one projected slot boundary.

    Uniqueness is whole-stream in both generations.  ``located_fresh_boundary`` remains separate
    from ``projected_fresh_boundary`` so a unique anchor that maps far cannot masquerade as
    positional confirmation.
    """

    unique_in_old: bool
    unique_in_fresh: bool
    projected_fresh_boundary: int
    located_fresh_boundary: int | None

    def __post_init__(self) -> None:
        if (
            isinstance(self.projected_fresh_boundary, bool)
            or not isinstance(self.projected_fresh_boundary, int)
            or self.projected_fresh_boundary < 0
        ):
            raise ValueError("projected_fresh_boundary must be an int >= 0")
        if self.located_fresh_boundary is not None and (
            isinstance(self.located_fresh_boundary, bool)
            or not isinstance(self.located_fresh_boundary, int)
            or self.located_fresh_boundary < 0
        ):
            raise ValueError("located_fresh_boundary must be None or an int >= 0")

    @property
    def confirmed(self) -> bool:
        return (
            self.unique_in_old
            and self.unique_in_fresh
            and self.located_fresh_boundary == self.projected_fresh_boundary
        )


@runtime_checkable
class BoundaryAnchorFamily(Protocol):
    """The deterministic content-only constructor contract implemented by #48.

    Repeated calls with the same normalized ``tokens``, ``boundary`` and ``side`` must return the
    same value.  ``exact`` must contain the token immediately inside the named slot boundary;
    ``prefix`` and ``suffix`` are contiguous content context around it.  The deliberately narrow
    signature provides no geometry, node, path, ordinal, randomness, or clock input from which a
    non-content component could be manufactured.
    """

    def derive(
        self,
        tokens: Sequence[str],
        boundary: int,
        *,
        side: BoundarySide,
    ) -> BoundaryAnchor: ...


@runtime_checkable
class BoundaryConfidenceGate(Protocol):
    """Independent whole-stream uniqueness + positional-confirmation hook implemented by #48."""

    def confirm(
        self,
        anchor: BoundaryAnchor,
        *,
        old_tokens: Sequence[str],
        fresh_tokens: Sequence[str],
        projected_fresh_boundary: int,
    ) -> BoundaryConfirmation: ...


@runtime_checkable
class BoundaryDecisionHook(Protocol):
    """The #48 seam that consumes classification plus independent confirmation.

    Item 2 supplies only this callable contract.  The decision behavior deliberately remains a
    carried red until #48 implements the boundary projection/confidence path.
    """

    def admits(
        self,
        boundary_class: BoundaryCandidateClass,
        confirmation: BoundaryConfirmation,
        *,
        within_window: bool,
        atom_representable: bool,
    ) -> bool: ...


@dataclass(frozen=True, slots=True)
class DeterministicBoundaryAnchorFamily:
    """The v3 content-only anchor producer.

    ``exact`` is the single token immediately inside the slot.  The remaining fixed footprint is
    allocated as evenly as stream edges permit, with the extra context token on the slot-interior
    side.  No node/path/position value is persisted in the result.
    """

    # Six tokens (one outer + boundary token + up to four slot-interior tokens) is the fixed
    # v3 allocation.  W=24 remains the hard maximum/invalidation bound, not a padding quota.
    footprint: int = 6

    def __post_init__(self) -> None:
        if (
            isinstance(self.footprint, bool)
            or not isinstance(self.footprint, int)
            or not 1 <= self.footprint <= BOUNDARY_ANCHOR_FOOTPRINT_W
        ):
            raise ValueError(
                f"boundary anchor footprint must be an int in [1, {BOUNDARY_ANCHOR_FOOTPRINT_W}]"
            )

    def derive(
        self,
        tokens: Sequence[str],
        boundary: int,
        *,
        side: BoundarySide,
    ) -> BoundaryAnchor:
        if side not in {"start", "end"}:
            raise ValueError(f"unknown boundary side {side!r}")
        inside = boundary if side == "start" else boundary - 1
        token_count = len(tokens)
        if not 0 <= inside < token_count:
            raise ValueError(
                f"{side} boundary {boundary!r} has no inside token in stream of {token_count}"
            )
        remaining = self.footprint - 1
        # Most context stays inside the owning slot (suffix for a start, prefix for an end).
        # One outer token still makes a shared seam observable without allowing a short edit in a
        # neighbouring slot to poison the whole anchor.  Edge-shortage is not back-filled across
        # the seam: W is a maximum footprint, not a quota.
        preferred_left = 1 if side == "start" else max(0, remaining - 1)
        left = min(inside, preferred_left)
        right = min(token_count - inside - 1, remaining - left)
        return BoundaryAnchor(
            prefix=tuple(tokens[inside - left : inside]),
            exact=(tokens[inside],),
            suffix=tuple(tokens[inside + 1 : inside + 1 + right]),
        )


@dataclass(frozen=True, slots=True)
class ConfirmingBoundaryDecision:
    """Uniform ``diff proposes, anchor confirms`` decision hook from INV-4/A7."""

    def admits(
        self,
        boundary_class: BoundaryCandidateClass,
        confirmation: BoundaryConfirmation,
        *,
        within_window: bool,
        atom_representable: bool,
    ) -> bool:
        if boundary_class not in {
            "clean-candidate",
            "edge-candidate",
            "no-candidate",
            "two-candidate",
        }:
            raise ValueError(f"unknown boundary class {boundary_class!r}")
        if not atom_representable or not confirmation.confirmed:
            return False
        return boundary_class != "no-candidate" or within_window


def derive_boundary_anchor(
    family: BoundaryAnchorFamily,
    tokens: Sequence[str],
    boundary: int,
    *,
    side: BoundarySide,
) -> BoundaryAnchor:
    """Enforce DR-4 around a #48-provided producer without choosing anchor content.

    The producer is invoked twice to pin determinism.  Its three segments must form a contiguous
    slice of the supplied content, and ``exact`` must touch the token immediately inside the named
    boundary.  This validator is the interface skeleton's executable contract, not an anchor
    constructor; selection and width allocation remain #48's work.
    """
    if side not in {"start", "end"}:
        raise ValueError(f"unknown boundary side {side!r}")
    token_count = len(tokens)
    inside = boundary if side == "start" else boundary - 1
    if (
        isinstance(boundary, bool)
        or not isinstance(boundary, int)
        or not 0 <= inside < token_count
    ):
        raise ValueError(
            f"{side} boundary {boundary!r} has no inside token in stream of {token_count}"
        )
    first = family.derive(tokens, boundary, side=side)
    second = family.derive(tokens, boundary, side=side)
    if not isinstance(first, BoundaryAnchor) or not isinstance(second, BoundaryAnchor):
        raise ValueError("boundary-anchor family must return BoundaryAnchor values")
    if first != second:
        raise ValueError(
            "boundary-anchor family is not deterministic for identical content input"
        )

    selected = first.prefix + first.exact + first.suffix
    exact_offset = len(first.prefix)
    # Only placements whose exact segment covers ``inside`` can satisfy the contract.  Testing
    # those at-most-W placements avoids copying or scanning the entire stream for every stored
    # boundary, which would make fixture construction O(K*T) at production scale.
    matches_boundary = False
    for inside_exact_offset in range(len(first.exact)):
        start = inside - exact_offset - inside_exact_offset
        end = start + len(selected)
        if 0 <= start and end <= token_count and tuple(tokens[start:end]) == selected:
            matches_boundary = True
            break
    if not matches_boundary:
        raise ValueError(
            "boundary-anchor prefix+exact+suffix is not contiguous supplied content with exact "
            "touching the inside boundary token"
        )
    return first
