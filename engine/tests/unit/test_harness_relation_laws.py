"""Component 0(a) — the §1.3 provenance-relation law family (item-2 spec, S4.7).

Red-first: every law is exercised by a constructed VIOLATING (relation, events) input and must
be rejected with that law's named violation code — a checker that cannot fail a bad relation
gates nothing. The legal fixtures pin the composition semantics as hand-authored goldens
(spec §1.3 law 6: the expected closure comes from an independent reference composition or
hand-pinned golden composed examples — never the generator's own fold compared to itself).

Laws (spec §1.3, verbatim numbering):
  1. every final fresh atom has old ancestry unless introduced by ``insert``;
  2. deleted old atoms have no final descendants;
  3. split/duplicate descendants preserve exactly one source lineage;
  4. a realized merge must carry the COMPLETE set of its >=2 old ancestors;
  5. moves preserve ancestry while changing final order;
  6. the final relation equals the composition of the event transitions;
  plus: content edits preserve ancestry (law code ``content-ancestry``),
  and the [audit sharpening 2026-07-17] forbidden composition: delete(X) composed with
  insertion of byte-identical X-content is a fixture-authoring error (``forbidden-composition``),
  expressible only as a move (parent §4 INV-1 as amended per ER-A2).
"""

from __future__ import annotations

import pytest

from harness.relation import (
    LineageEvent,
    ProvenanceRelation,
    RelationLawViolation,
    check_relation_laws,
    compose_events,
)

# --- hand-pinned golden compositions (law 6's independent closure) ------------------------------- #


def test_compose_split_then_char_sub_golden():
    # Golden, hand-computed: a1 splits into f1+f2; f2 then char-subbed to f3.
    # Final stream: [f1, f3]; both trace to a1; no inserts, no deletes.
    events = [
        LineageEvent(op="split", old_ids=("a1",), fresh_ids=("f1", "f2")),
        LineageEvent(op="char_sub", old_ids=("f2",), fresh_ids=("f3",)),
    ]
    rel = compose_events(old_order=("a1",), events=events)
    assert rel.fresh_order == ("f1", "f3")
    assert rel.pairs == frozenset({("a1", "f1"), ("a1", "f3")})
    assert rel.inserted == frozenset()
    assert rel.deleted == frozenset()


def test_compose_merge_move_insert_golden():
    # Golden, hand-computed: [a1, a2, a3] -> merge(a1,a2)=m1 -> move a3 to front ->
    # insert n1 at end. Final: [a3, m1, n1]; m1 carries BOTH ancestors; a3 moved; n1 inserted.
    events = [
        LineageEvent(op="merge", old_ids=("a1", "a2"), fresh_ids=("m1",)),
        LineageEvent(op="move", old_ids=("a3",), fresh_ids=("a3",), position=0),
        LineageEvent(op="insert", old_ids=(), fresh_ids=("n1",), position=2),
    ]
    rel = compose_events(old_order=("a1", "a2", "a3"), events=events)
    assert rel.fresh_order == ("a3", "m1", "n1")
    assert rel.pairs == frozenset({("a1", "m1"), ("a2", "m1"), ("a3", "a3")})
    assert rel.inserted == frozenset({"n1"})
    assert rel.moved == frozenset({"a3"})


def test_compose_drop_and_duplicate_golden():
    # Golden: [a1, a2] -> drop a1 -> duplicate a2 (dittography d1 after it).
    # a1 deleted (no descendants); a2 yields two fresh atoms, each single-lineage.
    events = [
        LineageEvent(op="drop", old_ids=("a1",), fresh_ids=()),
        LineageEvent(op="duplicate", old_ids=("a2",), fresh_ids=("d1",)),
    ]
    rel = compose_events(old_order=("a1", "a2"), events=events)
    assert rel.fresh_order == ("a2", "d1")
    assert rel.pairs == frozenset({("a2", "a2"), ("a2", "d1")})
    assert rel.deleted == frozenset({"a1"})


def _legal_relation() -> tuple[ProvenanceRelation, list[LineageEvent]]:
    """A composed legal fixture reused by the violation tests as their pre-mutation base."""
    events = [
        LineageEvent(op="split", old_ids=("a1",), fresh_ids=("f1", "f2")),
        LineageEvent(op="drop", old_ids=("a2",), fresh_ids=()),
        LineageEvent(op="insert", old_ids=(), fresh_ids=("n1",), position=0),
    ]
    return compose_events(old_order=("a1", "a2", "a3"), events=events), events


def test_legal_relation_passes_all_laws():
    rel, events = _legal_relation()
    assert check_relation_laws(rel, events) == []


# --- the violating inputs: each law seen RED on its named violation ------------------------------ #
# ProvenanceRelation is a frozen value object; violations are constructed by rebuilding the
# relation with one field corrupted — the named red-input is stated per test.


def _rebuild(rel: ProvenanceRelation, **overrides) -> ProvenanceRelation:
    fields = {
        "old_order": rel.old_order,
        "fresh_order": rel.fresh_order,
        "pairs": rel.pairs,
        "inserted": rel.inserted,
        "deleted": rel.deleted,
        "moved": rel.moved,
        "old_content": rel.old_content,
        "fresh_content": rel.fresh_content,
    }
    fields.update(overrides)
    return ProvenanceRelation(**fields)


def _codes(violations: list[RelationLawViolation]) -> set[str]:
    return {v.law for v in violations}


def test_law1_orphan_fresh_atom_reds():
    # Red-input: fresh atom "ghost" appears in the final order with no ancestry pair and no
    # insert event introducing it.
    rel, events = _legal_relation()
    bad = _rebuild(rel, fresh_order=rel.fresh_order + ("ghost",))
    assert "orphan-fresh" in _codes(check_relation_laws(bad, events))


def test_law2_deleted_atom_with_descendant_reds():
    # Red-input: a2 is recorded deleted AND carries a lineage pair to a surviving fresh atom.
    rel, events = _legal_relation()
    bad = _rebuild(rel, pairs=rel.pairs | {("a2", "f1")})
    assert "deleted-descendant" in _codes(check_relation_laws(bad, events))


def test_law3_split_descendant_with_two_lineages_reds():
    # Red-input: split product f2 claims a second source lineage (a3) — split/duplicate
    # descendants must preserve exactly one.
    rel, events = _legal_relation()
    bad = _rebuild(rel, pairs=rel.pairs | {("a3", "f2")})
    assert "multi-lineage" in _codes(check_relation_laws(bad, events))


def test_law4_merge_dropping_an_ancestor_reds():
    # Red-input: merge(a1,a2)=m1 recorded with only ONE ancestor pair — "may carry" would let a
    # one-ancestor drop pass; the law demands the complete set.
    events = [LineageEvent(op="merge", old_ids=("a1", "a2"), fresh_ids=("m1",))]
    rel = compose_events(old_order=("a1", "a2"), events=events)
    bad = _rebuild(rel, pairs=frozenset({("a1", "m1")}))
    assert "merge-incomplete" in _codes(check_relation_laws(bad, events))


def test_law5_move_losing_ancestry_reds():
    # Red-input: a3 flagged moved but stripped of any lineage pair — a move must preserve
    # ancestry while changing final order.
    events = [LineageEvent(op="move", old_ids=("a3",), fresh_ids=("a3",), position=0)]
    rel = compose_events(old_order=("a1", "a2", "a3"), events=events)
    bad = _rebuild(
        rel,
        pairs=frozenset(p for p in rel.pairs if p[0] != "a3"),
        fresh_order=tuple(f for f in rel.fresh_order if f != "a3"),
    )
    assert "move-ancestry" in _codes(check_relation_laws(bad, events))


def test_law6_relation_diverging_from_event_composition_reds():
    # Red-input: the relation claims a1 -> f1 only, while the event log's independent
    # composition yields a1 -> {f1, f2}; the final relation must equal the composed closure.
    rel, events = _legal_relation()
    bad = _rebuild(
        rel,
        pairs=frozenset(p for p in rel.pairs if p != ("a1", "f2")),
        fresh_order=tuple(f for f in rel.fresh_order if f != "f2"),
    )
    assert "composition-mismatch" in _codes(check_relation_laws(bad, events))


def test_content_edit_dropping_ancestry_reds():
    # Red-input: char_sub output f1 present in the final stream with its lineage pair removed —
    # content edits preserve ancestry (spec §1.3 "plus" law).
    events = [LineageEvent(op="char_sub", old_ids=("a1",), fresh_ids=("f1",))]
    rel = compose_events(old_order=("a1",), events=events)
    bad = _rebuild(rel, pairs=frozenset())
    codes = _codes(check_relation_laws(bad, events))
    assert "content-ancestry" in codes or "orphan-fresh" in codes


def test_forbidden_delete_plus_identical_insert_reds():
    # Red-input: delete(a1) composed with insertion of byte-identical content — the
    # [audit sharpening 2026-07-17] generator-FORBIDDEN composition; expressible only as a move.
    events = [
        LineageEvent(op="drop", old_ids=("a1",), fresh_ids=()),
        LineageEvent(op="insert", old_ids=(), fresh_ids=("n1",), position=0),
    ]
    rel = compose_events(
        old_order=("a1", "a2"),
        events=events,
        old_content={"a1": "identical text", "a2": "other"},
        fresh_content={"n1": "identical text"},
    )
    assert "forbidden-composition" in _codes(check_relation_laws(rel, events))


def test_forbidden_composition_requires_byte_identity():
    # Load-bearing in BOTH directions: delete + a merely-similar insert is legal (it is real
    # drop+insert drift, not a disguised move) — the guard must not fire on it.
    events = [
        LineageEvent(op="drop", old_ids=("a1",), fresh_ids=()),
        LineageEvent(op="insert", old_ids=(), fresh_ids=("n1",), position=0),
    ]
    rel = compose_events(
        old_order=("a1", "a2"),
        events=events,
        old_content={"a1": "identical text", "a2": "other"},
        fresh_content={"n1": "identical text."},
    )
    assert "forbidden-composition" not in _codes(check_relation_laws(rel, events))
