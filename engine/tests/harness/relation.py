"""Component 0(a) — lineage events, event composition, and the §1.3 relation-law checker.

Two deliberately separate mechanisms (spec §1.3 law 6):

- ``compose_events`` is the INDEPENDENT reference composition — a small interpreter that folds
  an event log over the old stream. The future mutation engine must build its relation
  incrementally as it perturbs (its own fold); comparing that against this interpreter (and
  against the hand-pinned goldens in the tests) is what keeps law 6 from being a same-fold
  tautology.
- ``check_relation_laws`` validates any (relation, events) pair and returns named violations.
  Laws 1–5 are deliberately redundant cross-checks of master law 6 — defense in depth, each its
  own red (spec §1.3).

The relation is final-position truth (post-all-events); the event log is diagnostics-grade and
non-authoritative — except for law 6, where it is the input to the reference composition, and
the forbidden-composition guard, which is defined over events + content.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

# ``remint`` is the materialization transition from a working atom id to the regenerated
# canonical stream's id.  It is deliberately not a perturbation class: without it an unchanged
# atom would retain its old id and the harness would never exercise annotation transfer between
# generations.  Keeping it in the event log also lets law 6 account for every final fresh id.
VALID_OPS = frozenset(
    {"char_sub", "drop", "insert", "duplicate", "split", "merge", "move", "remint"}
)


@dataclass(frozen=True, slots=True)
class LineageEvent:
    """One perturbation event. ``old_ids`` reference the working stream at application time
    (which may be fresh ids minted by earlier events — chains are legal); ``fresh_ids`` are the
    atoms the event leaves behind; ``position`` is the destination index for insert/move."""

    op: str
    old_ids: tuple[str, ...]
    fresh_ids: tuple[str, ...]
    position: int | None = None
    old_position: int | None = None
    old_texts: tuple[str, ...] = ()
    fresh_texts: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.op not in VALID_OPS:
            raise ValueError(f"unknown op {self.op!r}; valid: {sorted(VALID_OPS)}")
        object.__setattr__(self, "old_ids", tuple(self.old_ids))
        object.__setattr__(self, "fresh_ids", tuple(self.fresh_ids))
        object.__setattr__(self, "old_texts", tuple(self.old_texts))
        object.__setattr__(self, "fresh_texts", tuple(self.fresh_texts))
        expected = {
            "drop": (1, 0),
            "insert": (0, 1),
            "char_sub": (1, 1),
            "remint": (1, 1),
            "split": (1, None),
            "duplicate": (1, None),
            "merge": (None, 1),
            "move": (None, None),
        }[self.op]
        old_n, fresh_n = expected
        if old_n is not None and len(self.old_ids) != old_n:
            raise ValueError(
                f"{self.op}: expected {old_n} old id(s), got {len(self.old_ids)}"
            )
        if fresh_n is not None and len(self.fresh_ids) != fresh_n:
            raise ValueError(
                f"{self.op}: expected {fresh_n} fresh id(s), got {len(self.fresh_ids)}"
            )
        if (
            self.op in {"split", "merge"}
            and max(len(self.old_ids), len(self.fresh_ids)) < 2
        ):
            raise ValueError(
                f"{self.op}: re-segmentation requires at least two source/product ids"
            )
        if self.op == "duplicate" and not self.fresh_ids:
            raise ValueError("duplicate: expected at least one copied fresh id")
        if self.op == "move":
            if not self.old_ids or self.fresh_ids != self.old_ids:
                raise ValueError(
                    "move: fresh_ids must repeat the non-empty moved old_ids block"
                )
            if self.position is None:
                raise ValueError("move: destination position is required")
        if len(set(self.old_ids)) != len(self.old_ids) or len(
            set(self.fresh_ids)
        ) != len(self.fresh_ids):
            raise ValueError(f"{self.op}: event ids must be unique within each side")
        if self.old_texts and len(self.old_texts) != len(self.old_ids):
            raise ValueError(f"{self.op}: old_texts cardinality must match old_ids")
        if self.fresh_texts and len(self.fresh_texts) != len(self.fresh_ids):
            raise ValueError(f"{self.op}: fresh_texts cardinality must match fresh_ids")


@dataclass(frozen=True, slots=True)
class ProvenanceRelation:
    """The final many-to-many old<->fresh relation the invariant oracles read."""

    old_order: tuple[str, ...]
    fresh_order: tuple[str, ...]
    pairs: frozenset[tuple[str, str]]  # (original old id, final fresh id)
    inserted: frozenset[str]  # fresh ids introduced with no old ancestry
    deleted: frozenset[str]  # original old ids with no final descendants (delete only)
    moved: frozenset[str]  # original old ids relocated by a move event
    old_content: Mapping[str, str] = field(default_factory=dict)
    fresh_content: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RelationLawViolation:
    law: str  # named code, e.g. "merge-incomplete"
    detail: str


class CompositionError(ValueError):
    """The event log is not applicable to the stream (bad id, bad position) — an authoring
    error in the fixture, always loud, never a silently-skipped event."""


def compose_events(
    old_order: tuple[str, ...],
    events: list[LineageEvent],
    old_content: Mapping[str, str] | None = None,
    fresh_content: Mapping[str, str] | None = None,
) -> ProvenanceRelation:
    """Fold the event log over the old stream; return the final relation.

    Working state maps each live stream id to its set of ORIGINAL old-id ancestors, so lineage
    survives chains (split then char_sub then move). Insert-introduced atoms carry an empty
    ancestor set; any surviving descendant with an empty set is therefore classified as inserted
    without a second, drift-prone bookkeeping channel.
    """
    if len(set(old_order)) != len(old_order):
        raise CompositionError("old_order contains duplicate atom ids")
    stream: list[str] = list(old_order)
    ancestors: dict[str, frozenset[str]] = {a: frozenset({a}) for a in old_order}
    positions = {atom_id: index for index, atom_id in enumerate(stream)}
    deleted: set[str] = set()
    moved_candidates: set[str] = set()

    def _refresh_positions(start: int) -> None:
        for index in range(start, len(stream)):
            positions[stream[index]] = index

    def _index(atom_id: str, op: str) -> int:
        idx = positions.get(atom_id)
        if idx is None or stream[idx] != atom_id:
            raise CompositionError(
                f"{op}: id {atom_id!r} not in working stream"
            )
        return idx

    def _new_ids(ids: tuple[str, ...], op: str) -> None:
        # ``ancestors`` intentionally retains every id ever seen, including ids no longer live.
        # It is therefore the stronger used-id index; scanning ``stream`` here made an all-remint
        # event log quadratic without detecting anything the mapping did not already detect.
        duplicates = [atom_id for atom_id in ids if atom_id in ancestors]
        if duplicates:
            raise CompositionError(f"{op}: output id(s) already used: {duplicates}")

    def _position(position: int | None, op: str, *, maximum: int) -> int:
        pos = maximum if position is None else position
        if isinstance(pos, bool) or not isinstance(pos, int) or not 0 <= pos <= maximum:
            raise CompositionError(f"{op}: position {pos!r} outside [0, {maximum}]")
        return pos

    for ev in events:
        if ev.op == "drop":
            (target,) = ev.old_ids
            idx = _index(target, ev.op)
            del stream[idx]
            positions.pop(target)
            _refresh_positions(idx)
            deleted.update(ancestors[target])
        elif ev.op == "insert":
            (fresh,) = ev.fresh_ids
            _new_ids(ev.fresh_ids, ev.op)
            pos = _position(ev.position, ev.op, maximum=len(stream))
            stream.insert(pos, fresh)
            ancestors[fresh] = frozenset()
            _refresh_positions(pos)
        elif ev.op in {"char_sub", "remint"}:
            (target,) = ev.old_ids
            (fresh,) = ev.fresh_ids
            _new_ids(ev.fresh_ids, ev.op)
            idx = _index(target, ev.op)
            stream[idx] = fresh
            ancestors[fresh] = ancestors[target]
            positions.pop(target)
            positions[fresh] = idx
        elif ev.op == "split":
            (target,) = ev.old_ids
            idx = _index(target, ev.op)
            _new_ids(ev.fresh_ids, ev.op)
            stream[idx : idx + 1] = list(ev.fresh_ids)
            positions.pop(target)
            for fresh in ev.fresh_ids:
                ancestors[fresh] = ancestors[target]
            _refresh_positions(idx)
        elif ev.op == "duplicate":
            (target,) = ev.old_ids
            idx = _index(target, ev.op)
            _new_ids(ev.fresh_ids, ev.op)
            for offset, fresh in enumerate(ev.fresh_ids, start=1):
                stream.insert(idx + offset, fresh)
                ancestors[fresh] = ancestors[target]
            _refresh_positions(idx + 1)
        elif ev.op == "merge":
            (fresh,) = ev.fresh_ids
            indices = [_index(t, ev.op) for t in ev.old_ids]
            if indices != list(range(indices[0], indices[0] + len(indices))):
                raise CompositionError(
                    f"merge: sources must be a contiguous working-stream block: {ev.old_ids}"
                )
            _new_ids(ev.fresh_ids, ev.op)
            merged: frozenset[str] = frozenset()
            for t in ev.old_ids:
                merged |= ancestors[t]
            for idx in reversed(indices):
                del stream[idx]
            stream.insert(indices[0], fresh)
            ancestors[fresh] = merged
            for target in ev.old_ids:
                positions.pop(target)
            _refresh_positions(indices[0])
        elif ev.op == "move":
            indices = [_index(target, ev.op) for target in ev.old_ids]
            if indices != list(range(indices[0], indices[0] + len(indices))):
                raise CompositionError(
                    f"move: sources must be a contiguous working-stream block: {ev.old_ids}"
                )
            block = stream[indices[0] : indices[-1] + 1]
            del stream[indices[0] : indices[-1] + 1]
            pos = _position(ev.position, ev.op, maximum=len(stream))
            before = tuple(stream)
            stream[pos:pos] = block
            # A destination that reconstructs the old order is a generated no-op, not a realized
            # move.  Rejecting it keeps realized-operation counts and law 5 honest.
            old_again = list(before)
            old_again[indices[0] : indices[0]] = block
            if stream == old_again:
                raise CompositionError(
                    "move: destination leaves the working order unchanged"
                )
            _refresh_positions(min(indices[0], pos))
            for target in ev.old_ids:
                moved_candidates.update(ancestors[target])

    pairs = frozenset((old, fresh) for fresh in stream for old in ancestors[fresh])
    final_inserted = frozenset(f for f in stream if not ancestors[f])
    # An original old id counts deleted only if NO final atom carries its lineage.
    survivors = {old for old, _ in pairs}
    final_deleted = frozenset(d for d in deleted if d not in survivors)
    final_moved = _final_moved_old_ids(
        old_order, tuple(stream), pairs, moved_candidates
    )
    return ProvenanceRelation(
        old_order=old_order,
        fresh_order=tuple(stream),
        pairs=pairs,
        inserted=final_inserted,
        deleted=final_deleted,
        moved=final_moved,
        old_content=dict(old_content or {}),
        fresh_content=dict(fresh_content or {}),
    )


def check_relation_laws(
    rel: ProvenanceRelation, events: list[LineageEvent]
) -> list[RelationLawViolation]:
    """Validate (relation, events) against the §1.3 law family; empty list = legal."""
    violations: list[RelationLawViolation] = []
    ancestry_of: dict[str, set[str]] = {}
    for old, fresh in rel.pairs:
        ancestry_of.setdefault(fresh, set()).add(old)

    # Law 1 — every final fresh atom has ancestry unless insert-introduced.
    for fresh in rel.fresh_order:
        if fresh not in rel.inserted and not ancestry_of.get(fresh):
            violations.append(
                RelationLawViolation(
                    "orphan-fresh",
                    f"final atom {fresh!r} has no ancestry and no insert event",
                )
            )

    # Law 2 — deleted old atoms have no final descendants.
    final_set = set(rel.fresh_order)
    for old, fresh in rel.pairs:
        if old in rel.deleted and fresh in final_set:
            violations.append(
                RelationLawViolation(
                    "deleted-descendant",
                    f"deleted {old!r} has final descendant {fresh!r}",
                )
            )

    # Law 3 — split/duplicate descendants preserve the source lineage exactly. For the normal
    # old-derived case that is exactly one original lineage; an insert-derived atom legitimately
    # has none. Comparing to the event source catches both an added and a dropped lineage.
    single_lineage_products: dict[str, set[str]] = {}
    for ev in events:
        if ev.op in ("split", "duplicate"):
            expected: set[str] = set()
            for source in ev.old_ids:
                expected.update(_transitive_old(source, events, rel))
            for fresh in ev.fresh_ids:
                single_lineage_products[fresh] = expected
    for fresh, expected in single_lineage_products.items():
        if fresh in final_set and ancestry_of.get(fresh, set()) != expected:
            violations.append(
                RelationLawViolation(
                    "multi-lineage",
                    f"split/duplicate product {fresh!r} carries "
                    f"{sorted(ancestry_of.get(fresh, set()))}; expected exactly {sorted(expected)}",
                )
            )

    # Law 4 — a realized merge carries the COMPLETE set of its >=2 old ancestors.
    for ev in events:
        if ev.op != "merge":
            continue
        (product,) = ev.fresh_ids
        if product not in final_set:
            continue  # merged then later dropped: not a realized final merge
        expected = set()
        for source in ev.old_ids:
            expected.update(_transitive_old(source, events, rel))
        got = ancestry_of.get(product, set())
        if not expected <= got:
            violations.append(
                RelationLawViolation(
                    "merge-incomplete",
                    f"merge product {product!r} carries {sorted(got)}, missing {sorted(expected - got)}",
                )
            )

    # Law 5 — moves preserve ancestry while changing final order.
    for old in rel.moved:
        if old not in {o for o, _ in rel.pairs}:
            violations.append(
                RelationLawViolation(
                    "move-ancestry", f"moved atom {old!r} lost its lineage"
                )
            )

    # Law 6 — the final relation equals the independent composition of the event log.
    try:
        reference = compose_events(
            rel.old_order, events, rel.old_content, rel.fresh_content
        )
    except CompositionError as exc:
        violations.append(
            RelationLawViolation(
                "composition-mismatch", f"event log not applicable: {exc}"
            )
        )
    else:
        for field_name in ("fresh_order", "pairs", "inserted", "deleted", "moved"):
            if getattr(reference, field_name) != getattr(rel, field_name):
                violations.append(
                    RelationLawViolation(
                        "composition-mismatch",
                        f"{field_name} diverges from the event-log composition",
                    )
                )

    # Content-edit law — char_sub output preserves ancestry.
    for ev in events:
        if ev.op != "char_sub":
            continue
        (fresh,) = ev.fresh_ids
        if fresh in final_set and not ancestry_of.get(fresh):
            violations.append(
                RelationLawViolation(
                    "content-ancestry", f"char_sub product {fresh!r} lost its lineage"
                )
            )

    # Forbidden composition [audit sharpening 2026-07-17] — delete(X) + insertion of
    # byte-identical X-content is expressible only as a move (ER-A2 as sharpened).
    dropped_contents: set[str] = set()
    for ev in events:
        if ev.op != "drop":
            continue
        if ev.old_texts:
            dropped_contents.update(ev.old_texts)
        else:
            dropped_contents.update(
                rel.old_content[t] for t in ev.old_ids if t in rel.old_content
            )
    for ev in events:
        if ev.op != "insert":
            continue
        (fresh,) = ev.fresh_ids
        content = ev.fresh_texts[0] if ev.fresh_texts else rel.fresh_content.get(fresh)
        if content is not None and content in dropped_contents:
            violations.append(
                RelationLawViolation(
                    "forbidden-composition",
                    f"insert {fresh!r} is byte-identical to deleted content — author it as a move",
                )
            )

    return violations


def _transitive_old(
    working_id: str, events: list[LineageEvent], rel: ProvenanceRelation
) -> set[str]:
    """Original-old ancestors of a working id at merge time: original ids map to themselves;
    ids minted by earlier events resolve through those events' sources, recursively."""
    if working_id in rel.old_order:
        return {working_id}
    for ev in events:
        if working_id in ev.fresh_ids and ev.op != "insert":
            out: set[str] = set()
            for src in ev.old_ids:
                out |= _transitive_old(src, events, rel)
            return out
    return set()  # insert-introduced: no old ancestry


def _final_moved_old_ids(
    old_order: tuple[str, ...],
    fresh_order: tuple[str, ...],
    pairs: frozenset[tuple[str, str]],
    candidates: set[str] | frozenset[str],
) -> frozenset[str]:
    """Move candidates whose final relative order actually differs from the old generation."""
    old_position = {old_id: index for index, old_id in enumerate(old_order)}
    fresh_index = {fresh_id: index for index, fresh_id in enumerate(fresh_order)}
    final_position: dict[str, int] = {}
    for old_id, fresh_id in pairs:
        index = fresh_index[fresh_id]
        final_position[old_id] = min(index, final_position.get(old_id, index))
    survivors = set(final_position)
    return frozenset(
        candidate
        for candidate in candidates & survivors
        if any(
            other != candidate
            and (
                final_position[candidate] == final_position[other]
                or (old_position[candidate] < old_position[other])
                != (final_position[candidate] < final_position[other])
            )
            for other in survivors
        )
    )
