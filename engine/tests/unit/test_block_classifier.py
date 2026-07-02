"""S0.4 — the ``BlockClassifier`` seam + degenerate all-``UNKNOWN`` stub (ENGINE_STRUCTURE_TASKS).

Concern A emits a *typed* atom stream that B may re-type (PLAN §2-A, R3): the typing rides an
injectable ``BlockClassifier`` so S1.3b's typed projection — and these tests — bind to the seam,
not the not-yet-existing S9 recognizer. S0.4 builds only the seam + a placeholder stub. The stub
classifies every atom ``UNKNOWN`` and is **incomplete by construction**, so S1.3b's completeness
check (a later task) fails on it rather than mistaking an all-``UNKNOWN`` projection for done.

Invariants (each proven red on violation — red-first, ENGINE_STRUCTURE_PLAN §9):
  - all-UNKNOWN: the stub gives every atom ``block_class == UNKNOWN`` — a real class for any atom
    fails ``test_stub_classifies_every_atom_unknown``.
  - positional correspondence: one classification per atom, count tracks the input (not a fixed
    list) — fails ``test_stub_output_corresponds_to_the_input``.
  - honest incompleteness: every stub result is ``confidence == 0.0`` + a ``typed_by`` naming the
    placeholder, so it can never pass as real — fails ``test_stub_results_are_honestly_incomplete``.
  - total on empty: ``classify([]) == []`` and never raises — fails ``test_stub_on_empty_input``.
  - injectable: a different, non-degenerate classifier substitutes through the same call and gives
    non-UNKNOWN classes — a stub-bound consumer fails ``test_seam_is_injectable``.
  - UNKNOWN is a distinct, non-empty engine sentinel, not a real class — ``test_unknown_sentinel_…``.
  - classifications are immutable (frozen) — ``test_classification_is_frozen``.
  - exports resolve on the package — verified centrally in ``test_public_names_per_concern_resolve``
    and ``test_all_public_exports_resolve_on_the_package`` (test_structure_artifacts).
"""

from __future__ import annotations

import dataclasses

import pytest

from engine.structure import (
    DEGENERATE_CLASSIFIER_NAME,
    UNKNOWN,
    BlockClassification,
    BlockClassifier,
    DegenerateBlockClassifier,
)

# Synthetic "atoms": the seam is defined BEFORE S1.1's real Atom, so it must not presume one.
# Plain strings stand in; the stub ignores content (it classifies everything UNKNOWN regardless).
ATOMS = ["a heading-ish line", "a body paragraph", "a set-off verse line", ""]


def _stub() -> DegenerateBlockClassifier:
    return DegenerateBlockClassifier()


def test_stub_classifies_every_atom_unknown():
    out = _stub().classify(ATOMS)
    assert [c.block_class for c in out] == [UNKNOWN] * len(ATOMS)


def test_stub_output_corresponds_to_the_input():
    # One classification per atom; the count tracks the input rather than being a fixed-size list,
    # so a caller can zip atoms↔classes (the correspondence S1.3b's typed projection relies on).
    assert len(_stub().classify(ATOMS)) == len(ATOMS)
    assert len(_stub().classify(ATOMS[:2])) == 2


def test_stub_results_are_honestly_incomplete():
    # confidence 0.0 + self-naming provenance: the stub can never be mistaken for a real classifier
    # ("never a degenerate green", at the seam level).
    for c in _stub().classify(ATOMS):
        assert c.confidence == 0.0
        assert c.typed_by == DEGENERATE_CLASSIFIER_NAME
        assert c.typed_by  # non-empty: attributable to the placeholder, not anonymous


def test_stub_on_empty_input():
    assert _stub().classify([]) == []


def test_seam_is_injectable():
    # A non-degenerate classifier substitutes through the same call path and yields real classes,
    # proving the seam is a true injection point and consumers are not hard-wired to the stub.
    class ConstantClassifier:
        def classify(self, atoms):
            return [BlockClassification("body", typed_by="toy", confidence=1.0) for _ in atoms]

    def consume(clf: BlockClassifier, atoms):
        return [c.block_class for c in clf.classify(atoms)]

    assert consume(_stub(), ATOMS) == [UNKNOWN] * len(ATOMS)
    assert consume(ConstantClassifier(), ATOMS) == ["body"] * len(ATOMS)
    assert consume(ConstantClassifier(), ATOMS) != consume(_stub(), ATOMS)


def test_unknown_sentinel_is_distinct_and_nonempty():
    assert isinstance(UNKNOWN, str) and UNKNOWN
    # the incomplete state, distinct from any real class a structure profile would declare
    assert UNKNOWN not in {"heading", "body", "verse", "footnote", "title"}


def test_classification_is_frozen():
    c = BlockClassification(UNKNOWN, typed_by="x", confidence=0.0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        c.block_class = "body"  # type: ignore[misc]


def test_classification_rejects_anonymous_typed_by():
    # typed_by is the attribution B weighs to override a typing (R3/D5); an empty one is anonymous,
    # which the "never an anonymous label" guarantee forbids — enforced at construction.
    with pytest.raises(ValueError, match="never anonymous"):
        BlockClassification(UNKNOWN, typed_by="", confidence=0.0)
