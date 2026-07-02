"""S1.3b — typed projection over the raw atoms + profile-scoped completeness (ENGINE_STRUCTURE_TASKS).

S1.3a captures a raw witness into addressed atoms; S1.3b *types* that stream via an injectable
``BlockClassifier`` (S0.4 seam) and asserts **profile-scoped completeness** over the result. The
done-when (property tier): a boundary-class ``unknown`` raises; a body-leaf ``unknown`` routes to
review with count + location; an all-``unknown`` projection fails completeness (§9 — never a
degenerate green).

The discriminator between the two ``unknown`` regimes is the atom's L1 ``capture_provenance_class``
(the structural slot it was captured into) matched against the profile-supplied ``boundary_classes``
— it has to be an axis *independent* of the typed ``block_class``, because an atom can never be both
``block_class in boundary_classes`` **and** ``block_class == UNKNOWN``. ``boundary_classes`` is data
passed in, never a literal in core (the S0.2 neutrality guard scans ``structure/``).

Invariants (each proven red by a targeted SUT mutation — red-first, ENGINE_STRUCTURE_PLAN §9):
  - positional typing: ``typed_projection`` zips atoms↔classifications in order; same length —
    drop the zip-order / use a fixed list → ``test_typed_projection_pairs_in_source_order`` reds.
  - seam-contract count: a classifier returning the wrong count raises (no silent tail-drop) —
    delete the length guard → ``test_typed_projection_rejects_count_mismatch`` reds.
  - degenerate hard-fail: an all-``unknown`` projection raises **even with no boundary classes** —
    remove the all-unknown branch → ``test_all_unknown_projection_is_degenerate_failure`` reds.
  - boundary hard-fail: a boundary-class ``unknown`` raises and is distinct from the degenerate
    case (the projection has resolved atoms) — remove the boundary branch →
    ``test_boundary_class_unknown_hard_fails`` reds; it routes to review instead.
  - body-leaf route-to-review: a body ``unknown`` does **not** raise and is reported with count +
    location — drop the routed items (empty the review list) →
    ``test_body_leaf_unknown_routes_to_review`` reds (count/location lost).
  - keyed on UNKNOWN, not membership: a *resolved* boundary-slot atom does not raise — widen the
    branch to "in boundary_classes" → ``test_resolved_boundary_atom_does_not_fail`` reds.
  - degenerate-before-boundary ordering: an all-unknown-with-a-boundary projection reports the
    degenerate cause — swap the order → ``test_degenerate_check_precedes_boundary_check`` reds.
  - furniture exemption: an EXCLUDED atom left ``unknown`` is out of scope (not routed, not a
    hard-fail) — drop the ``processing_scope`` filter → ``test_excluded_furniture_is_exempt_…`` reds.
  - degenerate ranges over PROCESSED atoms: an all-excluded (furniture-only) stream is vacuously
    complete, not degenerate — drop the ``processed and`` empty-guard →
    ``test_all_excluded_stream_is_vacuously_complete`` reds.

Audit-hardening invariants (5-lens adversarial pass; each mutation-proven red):
  - count guard catches too-MANY, not only too-few: ``!=``→``<`` → ``…rejects_too_many…`` reds.
  - ``processing_scope`` vocabulary is closed at the ``Atom`` model (S1.1): a typo can no longer
    reach this check and vanish (the audit's reopened degenerate green) — bound at the root by
    ``test_atom_rejects_out_of_vocabulary_processing_scope`` (test_atoms.py). The ``!= excluded``
    filter is the remaining semantic scoping, bound by the furniture-exemption tests.
  - ``boundary_classes`` rejects a bare ``str`` (char-set trap): drop the guard →
    ``test_boundary_classes_rejects_a_bare_str`` reds.
  - route-to-review "count + location" bound above cardinality 1: cap to first →
    ``test_multiple_body_leaf_unknowns_are_all_routed_with_locations`` reds.
  - boundary failure names ALL offenders: clamp the list →
    ``test_multiple_boundary_unknowns_are_all_named_in_the_failure`` reds.

Real-path binding (the reviewer's gap): three tests run ``capture_witness → typed_projection →
check_completeness`` on production-shaped atoms (``test_real_capture_stream_is_degenerate_under_the_stub``,
``test_excluded_furniture_is_exempt_…``, ``test_all_excluded_stream_…``), not only on the synthetic
``capture_provenance_class="heading"`` shape S1.3a cannot emit. The boundary hard-fail itself stays
synthetic-only by necessity: no real classifier yet resolves a body atom while leaving a sibling
*included* boundary atom ``unknown`` — that capability is S9 (see ``typed.py`` module docstring).

Canonical-stream + R3/D5 coverage: the typed projection also runs over the **canonical**
(``build_canonical``) stream B/L2 consume (``test_typed_projection_runs_over_the_canonical_stream``);
the override-relevant data survives (``…preserves_typed_by_and_confidence`` — mutation-proven by
clobbering ``confidence``); and re-typing is a new projection over the same untouched frozen atoms
(``test_retyping_is_a_new_projection_over_untouched_atoms`` — the R3/D5 correctability affordance).
"""

from __future__ import annotations

import dataclasses

import pytest

from engine.errors import IncompleteTypingError
from engine.structure import (
    PROCESSING_SCOPE_EXCLUDED,
    PROCESSING_SCOPE_INCLUDED,
    UNKNOWN,
    Atom,
    BlockClassification,
    CompletenessReport,
    DegenerateBlockClassifier,
    Geom,
    ReviewItem,
    TypedAtom,
    build_canonical,
    capture_witness,
    check_completeness,
    hash_raw,
    typed_projection,
)

# Generic, profile-supplied capture-provenance classes. "heading" stands in for a structural
# boundary slot; "body" for a plain body leaf (the neutral capture default — see capture.py). Neither
# is a source-language literal (the neutrality guard's denylist is `capitolo`/guillemets/counts).
BOUNDARY = "heading"
BODY = "body"
BOUNDARY_CLASSES = frozenset({BOUNDARY})


def _atom(seq: int, text: str, *, capture_class: str, page: tuple[int, int] = (1, 1)) -> Atom:
    """A minimal valid L1 atom carrying the fields ``check_completeness`` reads (id, span, page,
    capture class). ``raw_source_hash`` is real for faithfulness though this check never re-hashes."""
    return Atom(
        atom_id=f"w_{seq:05d}",
        text=text,
        raw_span=(seq * 100, seq * 100 + len(text)),
        raw_source_hash=hash_raw(text),
        page_range=page,
        norm_layer="raw",
        geom=Geom.absent(),
        capture_provenance_class=capture_class,
        witness="w",
    )


def _cls(block_class: str, *, typed_by: str = "toy", confidence: float = 1.0) -> BlockClassification:
    return BlockClassification(block_class=block_class, typed_by=typed_by, confidence=confidence)


class _ScriptedClassifier:
    """A classifier that replays a fixed list of block classes (one per atom, in order)."""

    def __init__(self, classes: list[str]) -> None:
        self._classes = classes

    def classify(self, atoms):
        return [_cls(c) for c in self._classes]


class _WrongCountClassifier:
    """A broken classifier that returns one fewer classification than atoms (seam violation)."""

    def classify(self, atoms):
        return [_cls("body") for _ in list(atoms)[:-1]]


# --- typed_projection: positional typing + seam contract ------------------------------------- #

def test_typed_projection_pairs_in_source_order():
    atoms = [_atom(0, "alpha", capture_class=BODY), _atom(1, "beta", capture_class=BOUNDARY)]
    typed = typed_projection(atoms, _ScriptedClassifier(["body", "heading"]))
    assert [t.atom.atom_id for t in typed] == ["w_00000", "w_00001"]
    assert [t.classification.block_class for t in typed] == ["body", "heading"]
    # the pairing is positional: atom i carries classification i
    assert all(t.atom is a for t, a in zip(typed, atoms))


def test_typed_projection_rejects_count_mismatch():
    atoms = [_atom(0, "a", capture_class=BODY), _atom(1, "b", capture_class=BODY)]
    with pytest.raises(ValueError, match="one classification per atom"):
        typed_projection(atoms, _WrongCountClassifier())


def test_typed_projection_on_empty_is_empty():
    assert typed_projection([], _ScriptedClassifier([])) == []


def test_degenerate_stub_output_fails_completeness():
    # Ties S0.4 ↔ S1.3b: the stub types every atom UNKNOWN, so its projection is degenerate and
    # check_completeness refuses it rather than passing an all-UNKNOWN stream off as done.
    atoms = [_atom(0, "a", capture_class=BODY), _atom(1, "b", capture_class=BODY)]
    typed = typed_projection(atoms, DegenerateBlockClassifier())
    with pytest.raises(IncompleteTypingError):
        check_completeness(typed, boundary_classes=BOUNDARY_CLASSES)


# --- check_completeness: the three done-when regimes ---------------------------------------- #

def test_all_unknown_projection_is_degenerate_failure():
    # Property 3. All atoms unknown → hard-fail EVEN WITH NO boundary classes declared: a
    # projection that resolved nothing is degenerate, not a soft route-to-review queue.
    typed = [
        TypedAtom(_atom(0, "a", capture_class=BODY), _cls(UNKNOWN, confidence=0.0)),
        TypedAtom(_atom(1, "b", capture_class=BODY), _cls(UNKNOWN, confidence=0.0)),
    ]
    with pytest.raises(IncompleteTypingError, match="degenerate"):
        check_completeness(typed, boundary_classes=frozenset())


def test_boundary_class_unknown_hard_fails():
    # Property 1. One boundary-slot atom is unknown; the rest are resolved (so this is NOT the
    # degenerate case) → raise, naming the offending atom + its span (location in the message).
    typed = [
        TypedAtom(_atom(0, "title?", capture_class=BOUNDARY), _cls(UNKNOWN, confidence=0.0)),
        TypedAtom(_atom(1, "body", capture_class=BODY), _cls("body")),
    ]
    with pytest.raises(IncompleteTypingError) as exc:
        check_completeness(typed, boundary_classes=BOUNDARY_CLASSES)
    msg = str(exc.value)
    assert "boundary" in msg and "w_00000" in msg and "(0, 6)" in msg


def test_body_leaf_unknown_routes_to_review():
    # Property 2. A body-leaf unknown does NOT raise; it is routed to review with count + location.
    typed = [
        TypedAtom(_atom(0, "head", capture_class=BOUNDARY), _cls("heading")),
        TypedAtom(_atom(1, "good body", capture_class=BODY), _cls("body")),
        TypedAtom(_atom(2, "??", capture_class=BODY, page=(4, 4)), _cls(UNKNOWN, confidence=0.0)),
    ]
    report = check_completeness(typed, boundary_classes=BOUNDARY_CLASSES)
    assert isinstance(report, CompletenessReport)
    assert not report.is_complete
    assert report.review_count == 1
    assert report.processed_count == 3
    (item,) = report.to_review
    assert item == ReviewItem(
        atom_id="w_00002", raw_span=(200, 202), page_range=(4, 4), capture_provenance_class=BODY
    )
    # only the unknown body leaf is routed — resolved atoms are not in the queue
    assert [i.atom_id for i in report.to_review] == ["w_00002"]


def test_fully_typed_projection_is_complete():
    typed = [
        TypedAtom(_atom(0, "head", capture_class=BOUNDARY), _cls("heading")),
        TypedAtom(_atom(1, "body", capture_class=BODY), _cls("body")),
    ]
    report = check_completeness(typed, boundary_classes=BOUNDARY_CLASSES)
    assert report.is_complete
    assert report.to_review == ()
    assert report.review_count == 0
    assert report.processed_count == 2


def test_empty_projection_is_vacuously_complete():
    # Distinct from all-unknown: zero atoms has nothing to type, so it is vacuously complete (not
    # degenerate). Capture-emptiness is S1.3a/S1.4's concern, not typing-completeness.
    report = check_completeness([], boundary_classes=BOUNDARY_CLASSES)
    assert report.is_complete
    assert report.processed_count == 0


def test_resolved_boundary_atom_does_not_fail():
    # The hard-fail keys on UNKNOWN, not on mere membership in boundary_classes: a boundary-slot
    # atom that WAS typed is fine. (Mutating the branch to drop the UNKNOWN check reds this.)
    typed = [TypedAtom(_atom(0, "Title", capture_class=BOUNDARY), _cls("title"))]
    report = check_completeness(typed, boundary_classes=BOUNDARY_CLASSES)
    assert report.is_complete


def test_degenerate_check_precedes_boundary_check():
    # Ordering: when EVERY atom is unknown and one sits in a boundary slot, the reported cause is
    # the degenerate (resolved-nothing) one — the more fundamental diagnosis — not the boundary one.
    typed = [
        TypedAtom(_atom(0, "x", capture_class=BOUNDARY), _cls(UNKNOWN, confidence=0.0)),
        TypedAtom(_atom(1, "y", capture_class=BODY), _cls(UNKNOWN, confidence=0.0)),
    ]
    with pytest.raises(IncompleteTypingError, match="degenerate") as exc:
        check_completeness(typed, boundary_classes=BOUNDARY_CLASSES)
    assert "boundary-class" not in str(exc.value)


def test_boundary_classes_accepts_any_iterable():
    # boundary_classes is normalized internally (frozenset); a plain list works and matching is on
    # capture_provenance_class.
    typed = [
        TypedAtom(_atom(0, "h", capture_class=BOUNDARY), _cls(UNKNOWN, confidence=0.0)),
        TypedAtom(_atom(1, "b", capture_class=BODY), _cls("body")),
    ]
    with pytest.raises(IncompleteTypingError, match="boundary"):
        check_completeness(typed, boundary_classes=[BOUNDARY])  # list, not a set


# --- real S1.3a capture path: furniture exemption (processing_scope) ------------------------- #
# The synthetic atoms above use a `capture_provenance_class="heading"` shape `capture_witness`
# cannot produce (a named classify_line result is forced to processing_scope="excluded"). These
# tests run the *real* path — capture_witness → typed_projection → check_completeness — so the
# processing_scope scoping and the degenerate guard are bound on production-shaped atoms, not only
# on hand-built ones. `[[MARK:N]]` mirrors test_raw_capture's synthetic marker grammar.

_CAPTURE_SOURCE = (
    "Nel mezzo del cammin\n"        # body para 1 (included, capture class "body")
    "di nostra vita.\n"
    "\n"
    "[[MARK:7]]\n"                  # furniture line (excluded, capture class "page-furniture")
    "\n"
    "Mi ritrovai per una selva.\n"  # body para 2 (included)
)


def _marker_class(line: str) -> str | None:
    return "page-furniture" if line.strip().startswith("[[MARK:") else None


class _ScopeAwareClassifier:
    """Types every INCLUDED atom 'body' and every EXCLUDED atom UNKNOWN — so the only ``unknown``
    is furniture, which the completeness check must hold exempt."""

    def classify(self, atoms):
        return [
            _cls("body") if a.processing_scope != PROCESSING_SCOPE_EXCLUDED else _cls(UNKNOWN, confidence=0.0)
            for a in atoms
        ]


def test_real_capture_stream_is_degenerate_under_the_stub():
    # Binds the real path + the degenerate guard on production-shaped atoms: the included body atoms
    # are all UNKNOWN under the stub, so completeness fails loud (not a quiet green).
    atoms = capture_witness(_CAPTURE_SOURCE, "copy1", classify_line=_marker_class)
    typed = typed_projection(atoms, DegenerateBlockClassifier())
    with pytest.raises(IncompleteTypingError, match="degenerate"):
        check_completeness(typed, boundary_classes=frozenset())


def test_excluded_furniture_is_exempt_from_completeness():
    # An excluded furniture atom left UNKNOWN is out of scope: not routed to review, and NOT a
    # hard-fail even when its capture class is (mis-)declared a boundary class — the exemption
    # precedes the boundary check (§3.0 captured-but-excluded).
    atoms = capture_witness(_CAPTURE_SOURCE, "copy1", classify_line=_marker_class)
    assert any(a.processing_scope == PROCESSING_SCOPE_EXCLUDED for a in atoms)  # furniture present
    typed = typed_projection(atoms, _ScopeAwareClassifier())
    report = check_completeness(typed, boundary_classes={"page-furniture"})
    assert report.is_complete            # the unknown furniture did not break completeness
    assert report.to_review == ()        # nor was it routed to review
    assert report.processed_count == 2   # only the two included body atoms were in scope


def test_all_excluded_stream_is_vacuously_complete():
    # A furniture-only slice has no processable content, so it is vacuously complete — the degenerate
    # guard ranges over PROCESSED atoms, not all atoms (an all-excluded all-UNKNOWN stream is fine).
    atoms = capture_witness("[[MARK:1]]\n\n[[MARK:2]]\n", "copy1", classify_line=_marker_class)
    assert atoms and all(a.processing_scope == PROCESSING_SCOPE_EXCLUDED for a in atoms)
    report = check_completeness(typed_projection(atoms, DegenerateBlockClassifier()), boundary_classes=frozenset())
    assert report.is_complete
    assert report.processed_count == 0


# --- canonical-projection stream + B-correctability (R3/D5) ---------------------------------- #
# S1.3a emits per-witness streams AND one canonical (build_canonical) projection; the typed
# projection must run over the canonical stream too — it is what B/L2 consume downstream. And R3/D5:
# typing is a re-runnable projection B re-types, so the data B weighs (typed_by + confidence) must
# survive the projection, and re-projecting with a corrected classifier must yield a different
# typing while the immutable L1 atoms are untouched (typing never mutates the atom).


def test_typed_projection_runs_over_the_canonical_stream():
    src = "Nel mezzo del cammin\n\nMi ritrovai per una selva.\n"
    canon = build_canonical(
        {"copy1": capture_witness(src, "copy1"), "copy2": capture_witness(src, "copy2")},
        ["copy1", "copy2"],
    )
    assert canon and all(a.witness is None and a.derived_from for a in canon)  # genuinely canonical
    # a resolving classifier → complete over every canonical atom; the stub → degenerate hard-fail
    report = check_completeness(typed_projection(canon, _ScopeAwareClassifier()), boundary_classes=frozenset())
    assert report.is_complete and report.processed_count == len(canon)
    with pytest.raises(IncompleteTypingError, match="degenerate"):
        check_completeness(typed_projection(canon, DegenerateBlockClassifier()), boundary_classes=frozenset())


def test_typed_projection_preserves_typed_by_and_confidence():
    # The override-relevant data B weighs must survive the projection intact (not be defaulted/lost).
    class _Prov:
        def classify(self, atoms):
            return [BlockClassification("body", typed_by="recognizer-v1", confidence=0.42) for _ in atoms]

    typed = typed_projection([_atom(0, "a", capture_class=BODY), _atom(1, "b", capture_class=BODY)], _Prov())
    assert [t.classification.typed_by for t in typed] == ["recognizer-v1", "recognizer-v1"]
    assert [t.classification.confidence for t in typed] == [0.42, 0.42]


def test_retyping_is_a_new_projection_over_untouched_atoms():
    # B re-types by re-projecting with a corrected classifier (R3/D5): a different typing results and
    # the immutable atoms are the SAME objects across both projections — typing is never a mutation.
    atoms = [_atom(0, "Head", capture_class=BODY), _atom(1, "body", capture_class=BODY)]
    first = typed_projection(atoms, _ScriptedClassifier([UNKNOWN, "body"]))
    second = typed_projection(atoms, _ScriptedClassifier(["heading", "body"]))
    assert [t.classification.block_class for t in first] == [UNKNOWN, "body"]
    assert [t.classification.block_class for t in second] == ["heading", "body"]
    assert all(t.atom is a for t, a in zip(first, atoms))
    assert all(t.atom is a for t, a in zip(second, atoms))


# --- adversarial-audit hardening (multi-perspective review) ---------------------------------- #
# Findings from a 5-lens adversarial pass: the count guard was bound for too-FEW only; "count +
# location" only at cardinality 1; boundary_classes=str silently neutered the hard-fail; an
# out-of-vocabulary processing_scope reopened the degenerate green; route-to-review had no real-
# capture fixture. Each is now bound below.


class _TooManyClassifier:
    """Returns ONE MORE classification than atoms — the too-many seam violation a `!=`→`<` mutation
    of the count guard would let through, silently dropping the tail of the longer stream."""

    def classify(self, atoms):
        return [_cls("body") for _ in range(len(list(atoms)) + 1)]


def test_typed_projection_rejects_too_many_classifications():
    atoms = [_atom(0, "a", capture_class=BODY), _atom(1, "b", capture_class=BODY)]
    with pytest.raises(ValueError, match="one classification per atom"):
        typed_projection(atoms, _TooManyClassifier())


def test_typed_projection_accepts_a_generator_classifier():
    # The classifier may return a lazy Sequence; typed_projection must materialize it before the
    # count guard and the zip (dropping list() would exhaust it mid-use).
    class _Gen:
        def classify(self, atoms):
            return (_cls("body") for _ in atoms)

    atoms = [_atom(0, "a", capture_class=BODY), _atom(1, "b", capture_class=BODY)]
    assert [t.classification.block_class for t in typed_projection(atoms, _Gen())] == ["body", "body"]


def test_boundary_classes_rejects_a_bare_str():
    # A str is a valid Iterable[str] but iterates characters; interpreting "heading" as {'h','e',…}
    # would silently downgrade the boundary hard-fail to route-to-review (a severity inversion).
    typed = [
        TypedAtom(_atom(0, "h", capture_class=BOUNDARY), _cls(UNKNOWN, confidence=0.0)),
        TypedAtom(_atom(1, "b", capture_class=BODY), _cls("body")),
    ]
    with pytest.raises(TypeError, match="not a bare str"):
        check_completeness(typed, boundary_classes=BOUNDARY)  # "heading", a str, not {"heading"}


def test_boundary_classes_accepts_a_generator():
    typed = [
        TypedAtom(_atom(0, "h", capture_class=BOUNDARY), _cls(UNKNOWN, confidence=0.0)),
        TypedAtom(_atom(1, "b", capture_class=BODY), _cls("body")),
    ]
    with pytest.raises(IncompleteTypingError, match="boundary"):
        check_completeness(typed, boundary_classes=(c for c in [BOUNDARY]))  # one-shot generator


# NB: the reopened-degenerate-green hole the audit found (a typo'd processing_scope slipping past the
# scope filter and vanishing from the check) is now closed at the *root* — the Atom model rejects an
# out-of-vocabulary processing_scope at construction (S1.1), so it can never reach this check. That
# stronger guarantee is bound by ``test_atom_rejects_out_of_vocabulary_processing_scope`` in
# test_atoms.py; check_completeness's ``!= excluded`` filter is the remaining semantic scoping.


def test_multiple_body_leaf_unknowns_are_all_routed_with_locations():
    # "count + location" bound above cardinality 1 — a cap-to-first ([:1]) bug would survive the
    # single-unknown fixture. Three body leaves unknown → all three routed, in source order.
    typed = [
        TypedAtom(_atom(0, "ok", capture_class=BODY), _cls("body")),
        TypedAtom(_atom(1, "??", capture_class=BODY, page=(2, 2)), _cls(UNKNOWN, confidence=0.0)),
        TypedAtom(_atom(2, "???", capture_class=BODY, page=(3, 3)), _cls(UNKNOWN, confidence=0.0)),
        TypedAtom(_atom(3, "????", capture_class=BODY, page=(4, 4)), _cls(UNKNOWN, confidence=0.0)),
    ]
    report = check_completeness(typed, boundary_classes=BOUNDARY_CLASSES)
    assert report.review_count == 3
    assert [i.atom_id for i in report.to_review] == ["w_00001", "w_00002", "w_00003"]
    assert [i.page_range for i in report.to_review] == [(2, 2), (3, 3), (4, 4)]


def test_multiple_boundary_unknowns_are_all_named_in_the_failure():
    typed = [
        TypedAtom(_atom(0, "H1", capture_class=BOUNDARY), _cls(UNKNOWN, confidence=0.0)),
        TypedAtom(_atom(1, "body", capture_class=BODY), _cls("body")),
        TypedAtom(_atom(2, "H2", capture_class=BOUNDARY), _cls(UNKNOWN, confidence=0.0)),
    ]
    with pytest.raises(IncompleteTypingError) as exc:
        check_completeness(typed, boundary_classes=BOUNDARY_CLASSES)
    msg = str(exc.value)
    assert "2 boundary-class atom(s)" in msg and "w_00000" in msg and "w_00002" in msg


def test_real_capture_routes_a_body_leaf_to_review():
    # Property 2 on the REAL path (not the synthetic heading shape): a partial classifier over a
    # capture_witness stream leaves the second body paragraph UNKNOWN → routed to review; the
    # furniture marker (excluded, also UNKNOWN) is exempt; the first body paragraph resolves.
    atoms = capture_witness(_CAPTURE_SOURCE, "copy1", classify_line=_marker_class)
    body = [a for a in atoms if a.processing_scope != PROCESSING_SCOPE_EXCLUDED]
    assert len(body) == 2
    target = body[1].atom_id

    class _PartialByOrder:
        def classify(self, atoms):
            out, seen_body = [], 0
            for a in atoms:
                if a.processing_scope == PROCESSING_SCOPE_EXCLUDED:
                    out.append(_cls(UNKNOWN, confidence=0.0))
                else:
                    seen_body += 1
                    out.append(_cls("body") if seen_body == 1 else _cls(UNKNOWN, confidence=0.0))
            return out

    report = check_completeness(typed_projection(atoms, _PartialByOrder()), boundary_classes=frozenset())
    assert report.review_count == 1
    assert report.to_review[0].atom_id == target
    assert report.to_review[0].capture_provenance_class == BODY  # capture_witness's default body class


@pytest.mark.parametrize("scope", [PROCESSING_SCOPE_INCLUDED, PROCESSING_SCOPE_EXCLUDED])
@pytest.mark.parametrize("block", ["body", UNKNOWN])
@pytest.mark.parametrize("capture", [BODY, BOUNDARY])
def test_single_atom_outcome_table(scope, block, capture):
    # The full single-atom decision table (the partition the example tests sample): an excluded atom
    # is always vacuously complete; an included resolved atom is complete; an included UNKNOWN atom
    # is the all-processed-unknown case → degenerate hard-fail (checked before boundary, so a
    # boundary slot does not change the single-atom outcome — pins the M3 granularity decision).
    a = Atom(
        atom_id="x_0", text="t", raw_span=(0, 1), raw_source_hash=hash_raw("t"),
        page_range=(1, 1), norm_layer="raw", geom=Geom.absent(),
        capture_provenance_class=capture, processing_scope=scope,
    )
    typed = [TypedAtom(a, _cls(block, confidence=0.0 if block == UNKNOWN else 1.0))]
    if scope == PROCESSING_SCOPE_EXCLUDED:
        report = check_completeness(typed, boundary_classes=BOUNDARY_CLASSES)
        assert report.is_complete and report.processed_count == 0
    elif block != UNKNOWN:
        report = check_completeness(typed, boundary_classes=BOUNDARY_CLASSES)
        assert report.is_complete and report.processed_count == 1
    else:
        with pytest.raises(IncompleteTypingError):
            check_completeness(typed, boundary_classes=BOUNDARY_CLASSES)


# --- model + exports ------------------------------------------------------------------------- #

def test_typed_records_are_frozen():
    t = TypedAtom(_atom(0, "a", capture_class=BODY), _cls("body"))
    with pytest.raises(dataclasses.FrozenInstanceError):
        t.classification = _cls("heading")  # type: ignore[misc]
    item = ReviewItem("id", (0, 1), (1, 1), BODY)
    with pytest.raises(dataclasses.FrozenInstanceError):
        item.atom_id = "other"  # type: ignore[misc]
    report = CompletenessReport((), 0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        report.processed_count = 5  # type: ignore[misc]
