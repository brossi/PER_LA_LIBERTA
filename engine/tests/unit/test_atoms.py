"""S1.1 — the L1 ``Atom`` model + its ``Geom`` slot (ENGINE_STRUCTURE_TASKS / PLAN §3.0/§3.2/§11.1).

An L1 atom is an immutable, addressed capture unit: its identity is ``atom_id`` (text evidence +
coordinates), distinct from the structural ``node_id`` of L2. The model is pure core — no language,
ordinal, or book-structure opinion (the S0.2 neutrality guard scans the module). S1.1 freezes the
``geom`` field **shape** (Optional word-box bbox + match-provenance, with absence first-class) that
S2's matcher writes and S4.4's schema consumes — so S4 depends on S1.1, not on S2's backend.

Invariants (each proven red on violation — red-first, ENGINE_STRUCTURE_PLAN §9):
  - Atom/Geom/AtomDerivation are **immutable** (frozen): any field assignment raises
    ``FrozenInstanceError`` — ``test_atom_is_frozen`` / ``test_geom_is_frozen`` /
    ``test_derivation_is_frozen`` (red-input: drop ``frozen=True``).
  - **geom shape is frozen**: ``Geom`` has exactly {present, page, bbox, geometry_engine,
    matched_witness_id, match_method, match_confidence} — ``test_geom_shape_is_frozen``
    (red-input: add/remove a field; S2/S4.4 bind to this set).
  - **absence is a first-class state, never invented coordinates**: an absent geom carries no
    page/bbox/provenance, and constructing ``present=False`` *with* any coordinate raises —
    ``test_geom_absent_is_first_class`` / ``test_geom_absent_must_not_carry_coordinates``
    (red-input: drop the absent-branch check).
  - **a present geom carries full match-provenance**: ``present=True`` requires all six coordinate/
    provenance fields, and bbox is exactly four floats — ``test_geom_present_carries_full_provenance``
    / ``test_geom_present_must_carry_coordinates`` / ``test_geom_bbox_must_be_four_floats``
    (red-input: drop the present-branch check).
  - **an atom carries the full L1 address**: id, text, raw_span, raw_source_hash, page_range,
    norm_layer, geom, capture_provenance_class, (optional) witness + derived_from —
    ``test_witness_atom_carries_the_full_l1_address`` / ``test_canonical_atom_has_derivations``.
  - **sequence fields are immutable tuples** (raw_span, page_range, derived_from) so the frozen
    guarantee is not undermined by a mutable default/argument — ``test_atom_sequence_fields_are_tuples``.
  - **atom_id is the identity key — uniqueness is checkable**: ``duplicate_atom_ids`` reports ids
    appearing more than once (empty = all unique) — ``test_duplicate_atom_ids_*`` and the property
    ``test_atom_ids_unique_over_a_generated_stream`` (red-input: helper that never reports a dup).
  - exports resolve on the package — verified centrally in ``test_public_names_per_concern_resolve``
    (test_structure_artifacts).
"""

from __future__ import annotations

import dataclasses

import pytest

from engine.structure import (
    PROCESSING_SCOPE_EXCLUDED,
    PROCESSING_SCOPE_INCLUDED,
    Atom,
    AtomDerivation,
    Geom,
    duplicate_atom_ids,
)

# A well-formed present geom + its illustrative box. Neutral values — no book/language content.
_BBOX = (72.0, 118.4, 523.1, 134.8)


def _present_geom() -> Geom:
    return Geom.matched(
        page=12,
        bbox=_BBOX,
        geometry_engine="pymupdf-ocr",
        matched_witness_id="copy1",
        match_method="token-bbox",
        match_confidence=0.97,
    )


def _atom(atom_id: str = "ac_0007", **over) -> Atom:
    base = dict(
        atom_id=atom_id,
        text="some captured text",
        raw_span=(10432, 10446),
        raw_source_hash="sha256:deadbeef",
        page_range=(12, 12),
        norm_layer="rejoin+collapse",
        geom=Geom.absent(),
        capture_provenance_class="authorial",
    )
    base.update(over)
    return Atom(**base)


# --- Geom: shape, present/absent factories, and the never-invented-coordinates invariant ----- #

def test_geom_shape_is_frozen():
    # S2's matcher writes these fields and S4.4's schema consumes them: the field SET is the
    # contract those tasks bind to, so lock it exactly.
    assert {f.name for f in dataclasses.fields(Geom)} == {
        "present",
        "page",
        "bbox",
        "geometry_engine",
        "matched_witness_id",
        "match_method",
        "match_confidence",
    }


def test_geom_absent_is_first_class():
    g = Geom.absent()
    assert g.present is False
    # absence carries NO coordinates — never invented geometry (copy3 has no word-box layer at all)
    assert g.page is None
    assert g.bbox is None
    assert g.geometry_engine is None
    assert g.matched_witness_id is None
    assert g.match_method is None
    assert g.match_confidence is None


def test_geom_present_carries_full_provenance():
    g = _present_geom()
    assert g.present is True
    assert g.page == 12
    assert g.bbox == _BBOX
    assert g.geometry_engine == "pymupdf-ocr"
    assert g.matched_witness_id == "copy1"
    assert g.match_method == "token-bbox"
    assert g.match_confidence == 0.97


@pytest.mark.parametrize(
    "field, value",
    [
        ("page", 12),
        ("bbox", _BBOX),
        ("geometry_engine", "pymupdf-ocr"),
        ("matched_witness_id", "copy1"),
        ("match_method", "token-bbox"),
        ("match_confidence", 0.97),
    ],
)
def test_geom_absent_must_not_carry_coordinates(field, value):
    # The core invariant: an absent geom that still carries ANY coordinate/provenance field is
    # *invented geometry* and must be unrepresentable. Each of the six fields independently trips the
    # guard — so dropping any single field from the absent-branch coords check is caught here, not
    # just a whole-clause removal (the per-field granularity the discrimination sweep missed).
    with pytest.raises(ValueError):
        Geom(present=False, **{field: value})


def test_geom_present_must_carry_coordinates():
    # A present geom with a missing provenance field is a half-built box — fail loud, not silently
    # half-present (S2's matcher must write the whole tuple or declare absence).
    with pytest.raises(ValueError):
        Geom(present=True)  # no coordinates at all
    with pytest.raises(ValueError):
        Geom(present=True, bbox=_BBOX, geometry_engine="pymupdf-ocr")  # missing the rest


def test_geom_bbox_must_be_four_floats():
    with pytest.raises(ValueError):
        Geom.matched(
            page=12,
            bbox=(1.0, 2.0, 3.0),  # only three — not [x0, y0, x1, y1]
            geometry_engine="pymupdf-ocr",
            matched_witness_id="copy1",
            match_method="token-bbox",
            match_confidence=0.97,
        )


def test_geom_present_bbox_is_a_tuple():
    # A list bbox would undermine the frozen guarantee; construction normalizes to a tuple.
    g = Geom.matched(
        page=12,
        bbox=[72.0, 118.4, 523.1, 134.8],
        geometry_engine="pymupdf-ocr",
        matched_witness_id="copy1",
        match_method="token-bbox",
        match_confidence=0.97,
    )
    assert isinstance(g.bbox, tuple)
    assert g.bbox == _BBOX


def test_geom_is_frozen():
    g = Geom.absent()
    with pytest.raises(dataclasses.FrozenInstanceError):
        g.present = True  # type: ignore[misc]


# --- Atom: the full L1 address, witness vs canonical, immutability ------------------------- #

def test_witness_atom_carries_the_full_l1_address():
    a = _atom(witness="copy1", geom=_present_geom())
    assert a.atom_id == "ac_0007"
    assert a.witness == "copy1"
    assert a.text == "some captured text"
    assert a.raw_span == (10432, 10446)
    assert a.raw_source_hash == "sha256:deadbeef"
    assert a.page_range == (12, 12)
    assert a.norm_layer == "rejoin+collapse"
    assert a.geom.present is True
    assert a.capture_provenance_class == "authorial"
    assert a.derived_from == ()  # a per-witness atom has no canonical back-links


def test_canonical_atom_has_derivations():
    # A canonical (reconciled) atom has no single witness; it back-links to the per-witness atoms it
    # was reconciled from (S1.3a's "every canonical atom has ≥1 witness derivation").
    a = _atom(
        witness=None,
        derived_from=(
            AtomDerivation(witness="copy1", atom_id="a1_0007"),
            AtomDerivation(witness="copy2", atom_id="a2_0007"),
        ),
    )
    assert a.witness is None
    assert [d.witness for d in a.derived_from] == ["copy1", "copy2"]
    assert a.derived_from[0].atom_id == "a1_0007"


def test_atom_is_frozen():
    a = _atom()
    with pytest.raises(dataclasses.FrozenInstanceError):
        a.text = "mutated"  # type: ignore[misc]


def test_atom_is_hashable():
    # frozen + tuple fields → hashable, so atoms can key sets/dicts (the store relies on this).
    assert len({_atom("ac_0001"), _atom("ac_0002")}) == 2
    # value equality, not identity: two atoms built the same dedup to one — guards an eq=False /
    # identity-hash regression that the two-distinct-atoms case alone would pass through.
    assert len({_atom("ac_0001"), _atom("ac_0001")}) == 1


def test_atom_sequence_fields_are_tuples():
    # Pass lists; the model must normalize to tuples so a caller cannot retain a mutable handle into
    # a "frozen" atom.
    a = _atom(
        raw_span=[1, 2],
        page_range=[3, 4],
        derived_from=[AtomDerivation(witness="copy1", atom_id="a1_0001")],
    )
    assert isinstance(a.raw_span, tuple)
    assert isinstance(a.page_range, tuple)
    assert isinstance(a.derived_from, tuple)


def test_atom_raw_span_must_be_a_pair():
    with pytest.raises(ValueError):
        _atom(raw_span=(1, 2, 3))


def test_atom_page_range_must_be_a_pair():
    with pytest.raises(ValueError):
        _atom(page_range=(1,))


def test_atom_rejects_out_of_vocabulary_processing_scope():
    # processing_scope is a closed vocabulary {included, excluded}: a typo'd / stray value fails at
    # construction, so it can never slip past a downstream filter keyed on those two states (e.g.
    # the S1.3b completeness scope) and vanish from a check that should have seen it.
    with pytest.raises(ValueError, match="processing_scope must be"):
        _atom(processing_scope="include")  # typo of "included"
    # the two valid states construct fine
    assert _atom(processing_scope=PROCESSING_SCOPE_INCLUDED).processing_scope == PROCESSING_SCOPE_INCLUDED
    assert _atom(processing_scope=PROCESSING_SCOPE_EXCLUDED).processing_scope == PROCESSING_SCOPE_EXCLUDED


def test_derivation_is_frozen():
    d = AtomDerivation(witness="copy1", atom_id="a1_0007")
    assert d.witness == "copy1" and d.atom_id == "a1_0007"
    with pytest.raises(dataclasses.FrozenInstanceError):
        d.atom_id = "x"  # type: ignore[misc]


# --- atom_id uniqueness primitive (the "ids unique" done-when) ----------------------------- #

def test_duplicate_atom_ids_empty_when_unique():
    assert duplicate_atom_ids([]) == []  # empty stream: no crash, no false positive
    assert duplicate_atom_ids([_atom("ac_0001"), _atom("ac_0002"), _atom("ac_0003")]) == []


def test_duplicate_atom_ids_detects_planted_collision():
    dups = duplicate_atom_ids([_atom("ac_0001"), _atom("ac_0002"), _atom("ac_0001")])
    assert dups == ["ac_0001"]


def test_duplicate_atom_ids_reports_each_collision_once():
    dups = duplicate_atom_ids(
        [_atom("ac_0001"), _atom("ac_0001"), _atom("ac_0001"), _atom("ac_0002"), _atom("ac_0002")]
    )
    assert dups == ["ac_0001", "ac_0002"]


def test_atom_ids_unique_over_a_generated_stream():
    # property: a stream minted with distinct ids has no duplicates; planting one collision is the
    # single thing that makes the check report — so the check is bound to real ids, not a tautology.
    stream = [_atom(f"ac_{i:04d}") for i in range(200)]
    assert duplicate_atom_ids(stream) == []
    stream.append(_atom("ac_0100"))  # re-mint an id that already exists
    assert duplicate_atom_ids(stream) == ["ac_0100"]
