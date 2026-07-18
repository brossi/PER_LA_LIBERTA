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

VALID_OPS = frozenset({"char_sub", "drop", "insert", "duplicate", "split", "merge", "move"})


@dataclass(frozen=True, slots=True)
class LineageEvent:
    """One perturbation event. ``old_ids`` reference the working stream at application time
    (which may be fresh ids minted by earlier events — chains are legal); ``fresh_ids`` are the
    atoms the event leaves behind; ``position`` is the destination index for insert/move."""

    op: str
    old_ids: tuple[str, ...]
    fresh_ids: tuple[str, ...]
    position: int | None = None

    def __post_init__(self) -> None:
        if self.op not in VALID_OPS:
            raise ValueError(f"unknown op {self.op!r}; valid: {sorted(VALID_OPS)}")


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
    ancestor set and are tracked in ``inserted`` (their descendants inherit the inserted mark).
    """
    stream: list[str] = list(old_order)
    ancestors: dict[str, frozenset[str]] = {a: frozenset({a}) for a in old_order}
    inserted_mark: set[str] = set()
    deleted: set[str] = set()
    moved: set[str] = set()

    def _index(atom_id: str, op: str) -> int:
        try:
            return stream.index(atom_id)
        except ValueError:
            raise CompositionError(f"{op}: id {atom_id!r} not in working stream") from None

    for ev in events:
        if ev.op == "drop":
            (target,) = ev.old_ids
            idx = _index(target, ev.op)
            del stream[idx]
            if not ancestors[target] and target in inserted_mark:
                inserted_mark.discard(target)
            deleted.update(ancestors[target])
        elif ev.op == "insert":
            (fresh,) = ev.fresh_ids
            pos = len(stream) if ev.position is None else ev.position
            stream.insert(pos, fresh)
            ancestors[fresh] = frozenset()
            inserted_mark.add(fresh)
        elif ev.op == "char_sub":
            (target,) = ev.old_ids
            (fresh,) = ev.fresh_ids
            stream[_index(target, ev.op)] = fresh
            ancestors[fresh] = ancestors[target]
            if target in inserted_mark:
                inserted_mark.add(fresh)
        elif ev.op == "split":
            (target,) = ev.old_ids
            idx = _index(target, ev.op)
            stream[idx : idx + 1] = list(ev.fresh_ids)
            for fresh in ev.fresh_ids:
                ancestors[fresh] = ancestors[target]
                if target in inserted_mark:
                    inserted_mark.add(fresh)
        elif ev.op == "duplicate":
            (target,) = ev.old_ids
            idx = _index(target, ev.op)
            for offset, fresh in enumerate(ev.fresh_ids, start=1):
                stream.insert(idx + offset, fresh)
                ancestors[fresh] = ancestors[target]
                if target in inserted_mark:
                    inserted_mark.add(fresh)
        elif ev.op == "merge":
            (fresh,) = ev.fresh_ids
            indices = sorted(_index(t, ev.op) for t in ev.old_ids)
            merged: frozenset[str] = frozenset()
            for t in ev.old_ids:
                merged |= ancestors[t]
            for idx in reversed(indices):
                del stream[idx]
            stream.insert(indices[0], fresh)
            ancestors[fresh] = merged
            if any(t in inserted_mark for t in ev.old_ids):
                inserted_mark.add(fresh)
        elif ev.op == "move":
            (target,) = ev.old_ids
            idx = _index(target, ev.op)
            del stream[idx]
            pos = len(stream) if ev.position is None else ev.position
            stream.insert(pos, target)
            moved.update(ancestors[target])

    pairs = frozenset(
        (old, fresh) for fresh in stream for old in ancestors[fresh]
    )
    final_inserted = frozenset(f for f in stream if f in inserted_mark or not ancestors[f])
    # An original old id counts deleted only if NO final atom carries its lineage.
    survivors = {old for old, _ in pairs}
    final_deleted = frozenset(d for d in deleted if d not in survivors)
    return ProvenanceRelation(
        old_order=old_order,
        fresh_order=tuple(stream),
        pairs=pairs,
        inserted=final_inserted,
        deleted=final_deleted,
        moved=frozenset(moved),
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
                RelationLawViolation("orphan-fresh", f"final atom {fresh!r} has no ancestry and no insert event")
            )

    # Law 2 — deleted old atoms have no final descendants.
    final_set = set(rel.fresh_order)
    for old, fresh in rel.pairs:
        if old in rel.deleted and fresh in final_set:
            violations.append(
                RelationLawViolation("deleted-descendant", f"deleted {old!r} has final descendant {fresh!r}")
            )

    # Law 3 — split/duplicate descendants preserve exactly one source lineage.
    single_lineage_products: set[str] = set()
    for ev in events:
        if ev.op in ("split", "duplicate"):
            single_lineage_products.update(ev.fresh_ids)
    for fresh in single_lineage_products:
        if fresh in final_set and len(ancestry_of.get(fresh, set())) > 1:
            violations.append(
                RelationLawViolation(
                    "multi-lineage",
                    f"split/duplicate product {fresh!r} carries {len(ancestry_of[fresh])} lineages",
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
                RelationLawViolation("move-ancestry", f"moved atom {old!r} lost its lineage")
            )

    # Law 6 — the final relation equals the independent composition of the event log.
    try:
        reference = compose_events(rel.old_order, events, rel.old_content, rel.fresh_content)
    except CompositionError as exc:
        violations.append(RelationLawViolation("composition-mismatch", f"event log not applicable: {exc}"))
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
                RelationLawViolation("content-ancestry", f"char_sub product {fresh!r} lost its lineage")
            )

    # Forbidden composition [audit sharpening 2026-07-17] — delete(X) + insertion of
    # byte-identical X-content is expressible only as a move (ER-A2 as sharpened).
    dropped_contents = {
        rel.old_content[t]
        for ev in events
        if ev.op == "drop"
        for t in ev.old_ids
        if t in rel.old_content
    }
    for ev in events:
        if ev.op != "insert":
            continue
        (fresh,) = ev.fresh_ids
        content = rel.fresh_content.get(fresh)
        if content is not None and content in dropped_contents:
            violations.append(
                RelationLawViolation(
                    "forbidden-composition",
                    f"insert {fresh!r} is byte-identical to deleted content — author it as a move",
                )
            )

    return violations


def _transitive_old(working_id: str, events: list[LineageEvent], rel: ProvenanceRelation) -> set[str]:
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
