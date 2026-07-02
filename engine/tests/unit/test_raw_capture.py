"""S1.3a — raw addressed capture, the model-level floor (ENGINE_STRUCTURE_PLAN §2-A/§3.0/§11.1; D25).

Synthetic, in-memory witnesses exercise the three neutral primitives of ``structure.capture`` and the
S1.3a done-when properties: a witness segments into a stream of raw atoms that *tile* the source with
furniture captured-with-role (not dropped); a canonical projection built from two witnesses gives
**every canonical atom ≥1 witness derivation**. The real-PLL-bytes floor is ``test_raw_capture_real_input``.

Red-first (PLAN §9): the tiling floor (:func:`assert_capture_tiles`) is exercised positive **and** by
three tampered negatives that share it as a chokepoint (overlap / out-of-bounds / silent loss), so a
weakened check reds at least one. The capture/round-trip coupling is pinned by reconstructing each
atom through the S1.2 floor — drop the hash and a wrong slice would pass capture but red the round-trip.
The canonical-derivation property is asserted over *every* aligned shape (match / primary-only /
secondary-only), so an alignment branch that dropped a derivation reds the headline.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import engine.structure as structure
import engine.structure.capture as capture_mod
from engine.errors import CaptureError
from engine.structure import (
    PAGE_UNMAPPED,
    PROCESSING_SCOPE_EXCLUDED,
    PROCESSING_SCOPE_INCLUDED,
    Atom,
    Geom,
    align_streams,
    assert_capture_tiles,
    build_canonical,
    capture_witness,
    duplicate_atom_ids,
    hash_raw,
    reconstruct_raw,
    verify_atom_roundtrip,
)

# A small source with two body paragraphs (the first multi-line), a furniture marker line, and a
# trailing paragraph — blank-line delimited, with the marker glued to nothing so the role split is
# visible. ``[[MARK:N]]`` stands in for any source-noise marker grammar; it is supplied by the test's
# classifier, never known to core (the copy3 ⟨PAGE:N⟩ grammar lives only in the real-input test).
SOURCE = (
    "Nel mezzo del cammin\n"      # body para 1, line 1
    "di nostra vita.\n"           # body para 1, line 2
    "\n"
    "[[MARK:7]]\n"                # furniture line
    "\n"
    "Mi ritrovai per una selva.\n"  # body para 2
)


def _marker_class(line: str) -> str | None:
    """Classify the synthetic marker line as furniture; everything else is body."""
    return "page-furniture" if line.strip().startswith("[[MARK:") else None


def _page_of(start: int, _end: int) -> tuple[int, int]:
    """A toy page map: marker announces its own page; body before it is page 1, after it page 7."""
    if SOURCE[start:].startswith("[[MARK:7]]"):
        return (7, 7)
    return (1, 1) if start < SOURCE.index("[[MARK") else (7, 7)


# --- capture_witness: tiling + roles + the round-trip coupling ----------------------------- #

def test_capture_witness_tiles_source_and_round_trips_every_atom():
    atoms = capture_witness(SOURCE, "copy3", classify_line=_marker_class, page_of=_page_of)
    # tiles with no silent loss (the capture-completeness floor)
    assert_capture_tiles(atoms, SOURCE)
    # every atom's stored text IS the verbatim slice and survives the S1.2 raw round-trip
    for a in atoms:
        assert a.text == SOURCE[a.raw_span[0]:a.raw_span[1]]
        assert a.norm_layer == "raw"
        assert verify_atom_roundtrip(a, SOURCE) == a.text
    # ids unique + witness-tagged
    assert duplicate_atom_ids(atoms) == []
    assert all(a.witness == "copy3" for a in atoms)


def test_capture_witness_preserves_multiline_paragraph_verbatim():
    # The first body paragraph is two physical lines: its single atom's text keeps the internal
    # newline verbatim (no rejoin/collapse — that would break the byte-exact floor, D30).
    atoms = capture_witness(SOURCE, "copy3", classify_line=_marker_class, page_of=_page_of)
    first_body = next(a for a in atoms if a.processing_scope == PROCESSING_SCOPE_INCLUDED)
    assert first_body.text == "Nel mezzo del cammin\ndi nostra vita."
    assert "\n" in first_body.text


def test_furniture_is_captured_with_role_not_dropped():
    atoms = capture_witness(SOURCE, "copy3", classify_line=_marker_class, page_of=_page_of)
    furniture = [a for a in atoms if a.processing_scope == PROCESSING_SCOPE_EXCLUDED]
    assert len(furniture) == 1
    mark = furniture[0]
    assert mark.text == "[[MARK:7]]"                       # captured verbatim...
    assert mark.capture_provenance_class == "page-furniture"  # ...with a role...
    assert mark.page_range == (7, 7)                       # ...and a page
    # captured-but-excluded ≠ never-captured: the marker bytes are inside an atom span, so dropping
    # furniture atoms from the stream would open a non-whitespace gap the tiling floor rejects.
    body_only = [a for a in atoms if a.processing_scope == PROCESSING_SCOPE_INCLUDED]
    with pytest.raises(CaptureError, match="silent loss"):
        assert_capture_tiles(body_only, SOURCE)


def test_capture_witness_defaults_to_all_body_and_unmapped_pages():
    # A witness with no markers and no page map (PLL copy1/copy2): every line is body, every atom
    # carries the unmapped page sentinel.
    src = "alpha line\n\nbeta line\n"
    atoms = capture_witness(src, "copy1")
    assert [a.capture_provenance_class for a in atoms] == ["body", "body"]
    assert all(a.processing_scope == PROCESSING_SCOPE_INCLUDED for a in atoms)
    assert all(a.page_range == PAGE_UNMAPPED for a in atoms)
    assert_capture_tiles(atoms, src)


# --- assert_capture_tiles: the floor, positive + three tampered negatives ------------------ #

def _atom(source: str, start: int, end: int, atom_id: str) -> Atom:
    slice_ = source[start:end]
    return Atom(
        atom_id=atom_id, text=slice_, raw_span=(start, end), raw_source_hash=hash_raw(slice_),
        page_range=PAGE_UNMAPPED, norm_layer="raw", geom=Geom.absent(),
        capture_provenance_class="authorial",
    )


def test_tiles_raises_on_overlapping_spans():
    src = "0123456789"
    a = [_atom(src, 0, 6, "a0"), _atom(src, 4, 10, "a1")]   # a1 starts before a0 ends
    with pytest.raises(CaptureError, match="overlaps or precedes"):
        assert_capture_tiles(a, src)


def test_tiles_raises_on_out_of_bounds_span():
    src = "short"
    a = [_atom("short and longer", 6, 12, "a0")]            # valid for the long source, not this one
    with pytest.raises(CaptureError, match="out of bounds"):
        assert_capture_tiles(a, src)


def test_tiles_raises_on_silent_loss_of_real_content():
    # A non-whitespace gap between atoms = source bytes captured into no atom. This is the exact
    # failure "everything is brought in" forbids; whitespace gaps are fine, real text is not.
    src = "keep DROPPED keep"
    a = [_atom(src, 0, 4, "a0"), _atom(src, 13, 17, "a1")]   # "DROPPED" (chars 5–11) covered by nothing
    with pytest.raises(CaptureError, match="silent loss"):
        assert_capture_tiles(a, src)


def test_tiles_accepts_whitespace_only_gaps():
    # The positive that makes the silent-loss negative non-vacuous: identical structure but the gap
    # is whitespace, so it passes. (If the check flagged *any* gap, this would red.)
    src = "keep    keep"
    a = [_atom(src, 0, 4, "a0"), _atom(src, 8, 12, "a1")]    # 4-space gap
    assert_capture_tiles(a, src)


# --- align_streams: every opcode shape -------------------------------------------------- #

def _body(texts: list[str], witness: str) -> list[Atom]:
    """Build a witness stream of body atoms from paragraph texts joined by blank lines, so the spans
    are real and the round-trip holds — alignment keys off ``text``."""
    src = "\n\n".join(texts) + "\n"
    return capture_witness(src, witness), src


def test_align_streams_matches_equal_blocks():
    p, _ = _body(["alpha", "beta", "gamma"], "copy1")
    s, _ = _body(["alpha", "beta", "gamma"], "copy2")
    aligned = align_streams(p, s)
    assert len(aligned) == 3
    assert all(pa is not None and sa is not None for pa, sa in aligned)


def test_align_streams_marks_insert_and_delete():
    p, _ = _body(["alpha", "gamma"], "copy1")          # missing "beta"
    s, _ = _body(["alpha", "beta", "gamma"], "copy2")
    aligned = align_streams(p, s)
    # the inserted-in-secondary block aligns to (None, beta)
    inserts = [(pa, sa) for pa, sa in aligned if pa is None and sa is not None]
    assert len(inserts) == 1 and inserts[0][1].text == "beta"


def test_align_streams_normalizes_case_and_whitespace_for_matching():
    # The neutral key folds case + whitespace-run so an OCR-variant block still aligns to its clean
    # twin — without any accent/language rule. The fixture is built so folding changes the *pairing*,
    # not just an opcode label: two primary blocks fold to the same key, and only the variant block
    # ("THE   FOX") should claim the single secondary "the fox" (difflib matches the earliest equal
    # key). A broken identity key pairs the *other* primary block instead, orphaning the variant, so
    # this reds if _alignment_key stops folding — which the old single-block form could not detect,
    # since a 1-1 replace also yields a non-None pair.
    p, _ = _body(["THE   FOX", "the fox"], "copy1")   # block 0: case+spacing variant of "the fox"
    s, _ = _body(["the fox"], "copy2")
    aligned = align_streams(p, s)
    variant = [(pa, sa) for pa, sa in aligned if pa is not None and pa.text == "THE   FOX"]
    assert len(variant) == 1
    assert variant[0][1] is not None and variant[0][1].text == "the fox"  # folded variant found its twin


# --- build_canonical: the S1.3a done-when property -------------------------------------- #

def test_build_canonical_every_atom_has_at_least_one_derivation():
    # The headline property. Streams that match on some blocks and diverge on others — the canonical
    # must still give EVERY atom a witness back-link (none orphaned).
    p, _ = _body(["shared one", "only in copy1", "shared two"], "copy1")
    s, _ = _body(["shared one", "only in copy2", "shared two"], "copy2")
    canon = build_canonical({"copy1": p, "copy2": s}, ["copy1", "copy2"])
    assert canon, "canonical projection is empty"
    assert all(len(a.derived_from) >= 1 for a in canon)
    assert all(a.witness is None for a in canon)          # canonical is no single witness
    assert duplicate_atom_ids(canon) == []


def test_build_canonical_links_both_witnesses_on_a_matched_block():
    p, _ = _body(["identical block"], "copy1")
    s, _ = _body(["identical block"], "copy2")
    canon = build_canonical({"copy1": p, "copy2": s}, ["copy1", "copy2"])
    assert len(canon) == 1
    witnesses = {d.witness for d in canon[0].derived_from}
    assert witnesses == {"copy1", "copy2"}
    # back-links resolve to the actual per-witness atom ids
    ids = {(d.witness, d.atom_id) for d in canon[0].derived_from}
    assert ("copy1", p[0].atom_id) in ids and ("copy2", s[0].atom_id) in ids


def test_build_canonical_single_witness_block_derives_from_that_witness_only():
    # A block only copy1 has: the canonical atom adopts copy1's text and derives from copy1 alone —
    # still ≥1, the property holds for the asymmetric shape too.
    p, _ = _body(["alpha", "copy1 exclusive", "gamma"], "copy1")
    s, _ = _body(["alpha", "gamma"], "copy2")
    canon = build_canonical({"copy1": p, "copy2": s}, ["copy1", "copy2"])
    solo = [a for a in canon if a.text == "copy1 exclusive"]
    assert len(solo) == 1
    assert [d.witness for d in solo[0].derived_from] == ["copy1"]


def test_build_canonical_secondary_only_block_derives_from_secondary_only():
    # The mirror of the primary-only case and the shape the matched/replace fixtures never produce:
    # a block ONLY copy2 has aligns as (None, s), so the canonical atom adopts copy2's text and its
    # SOLE derivation is copy2. This is the fixture that reds a dropped secondary-derivation branch
    # (a replace/primary-only fixture leaves the primary link in place and hides the bug).
    p, _ = _body(["alpha", "gamma"], "copy1")
    s, _ = _body(["alpha", "copy2 exclusive", "gamma"], "copy2")
    canon = build_canonical({"copy1": p, "copy2": s}, ["copy1", "copy2"])
    solo = [a for a in canon if a.text == "copy2 exclusive"]
    assert len(solo) == 1
    assert [d.witness for d in solo[0].derived_from] == ["copy2"]
    assert all(len(a.derived_from) >= 1 for a in canon)   # ≥1 holds for the secondary-only shape too


def test_canonical_atom_round_trips_against_its_primary_witness_source():
    # A canonical atom's address points into the source of its first derivation's witness. Reconstruct
    # it against that source byte-exact — the floor that keeps the canonical projection addressable.
    p, src1 = _body(["shared", "only copy1"], "copy1")
    s, src2 = _body(["shared", "only copy2"], "copy2")
    sources = {"copy1": src1, "copy2": src2}
    canon = build_canonical({"copy1": p, "copy2": s}, ["copy1", "copy2"])
    for a in canon:
        primary = a.derived_from[0].witness
        assert reconstruct_raw(a, sources[primary]) == a.text


def test_canonical_adopts_primary_page_so_the_unmapped_tripwire_is_non_vacuous():
    # S1.3a.4 non-vacuity control (the permanent planted violation for the real-input PAGE_UNMAPPED
    # tripwire). Page provenance flows primary->canonical: build_canonical adopts the primary witness's
    # page_range, so the canonical stream carries a REAL page exactly when its primary does. A
    # page-mapped primary here yields a page-mapped canonical — the very condition that reds the
    # real-input marker once S7.1b page-attributes the canonical stream. So "uniformly PAGE_UNMAPPED"
    # on real bytes is a genuine constraint, not `assert True`.
    src = "alpha\n\nbeta\n"
    prim = capture_witness(src, "copy1", page_of=lambda _s, _e: (7, 7))   # primary carries real pages
    sec = capture_witness(src, "copy2")                                   # secondary is unmapped
    canon = build_canonical({"copy1": prim, "copy2": sec}, ["copy1", "copy2"])
    assert canon
    assert all(a.page_range == (7, 7) for a in canon)                    # adopted from the primary ...
    assert all(a.page_range != PAGE_UNMAPPED for a in canon)             # ... so NOT unmapped


def test_build_canonical_excludes_furniture_from_alignment():
    # Furniture atoms (excluded scope) must not become canonical body atoms — only included atoms
    # align. copy1 here carries a marker; the canonical has no furniture-derived atom.
    src1 = "alpha\n\n[[MARK:1]]\n\nbeta\n"
    p = capture_witness(src1, "copy1", classify_line=_marker_class, page_of=_page_of)
    s, _ = _body(["alpha", "beta"], "copy2")
    canon = build_canonical({"copy1": p, "copy2": s}, ["copy1", "copy2"])
    assert all(a.capture_provenance_class != "page-furniture" for a in canon)
    assert {a.text for a in canon} == {"alpha", "beta"}


def test_build_canonical_requires_two_witnesses():
    p, _ = _body(["alpha"], "copy1")
    with pytest.raises(CaptureError, match="two structural witnesses"):
        build_canonical({"copy1": p}, ["copy1"])


def test_build_canonical_rejects_more_than_two_witnesses():
    # >2 structural witnesses must FAIL LOUD (S1.3a.1): N-way structural alignment is unbuilt, and
    # the prior behavior silently used only witness_order[0:2], dropping the third witness without a
    # trace. A word-level third witness (PLL's copy3) is reconciled separately, never passed here.
    p, _ = _body(["alpha", "beta"], "copy1")
    s, _ = _body(["alpha", "beta"], "copy2")
    t, _ = _body(["alpha", "beta"], "copy3")
    with pytest.raises(CaptureError, match="exactly two structural witnesses"):
        build_canonical({"copy1": p, "copy2": s, "copy3": t}, ["copy1", "copy2", "copy3"])


# --- the junk policy is owned, not inherited: explicit autojunk at the source layer ----- #

def _align_streams_passes_explicit_autojunk(tree_or_module) -> bool:
    """True iff every ``SequenceMatcher`` call inside ``align_streams`` passes ``autojunk``
    explicitly. Accepts a parsed AST (for planted fixtures) or the live capture module (parsed from
    its own source). Returns False if the function or the call is absent — a guard that cannot find
    its target must fail, not pass vacuously."""
    tree = (
        tree_or_module
        if isinstance(tree_or_module, ast.AST)
        else ast.parse(Path(tree_or_module.__file__).read_text(encoding="utf-8"))
    )
    fn = next(
        (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "align_streams"),
        None,
    )
    if fn is None:
        return False
    calls = [
        n for n in ast.walk(fn)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "SequenceMatcher"
    ]
    if not calls:
        return False
    return all("autojunk" in {kw.arg for kw in c.keywords} for c in calls)


def test_align_streams_owns_its_junk_policy_explicitly():
    """Source-layer guard (S1.3a.2): the ``SequenceMatcher`` call inside ``align_streams`` must pass
    ``autojunk`` **explicitly**. The behavioral test pins the *value* (and difflib's default is
    ``True``), but explicit-vs-implicit is not behaviorally observable — yet the value is
    load-bearing for the canonical projection (~9% pair-count swing). Left implicit, a parameter
    that swings the projection is delegated to a default the engine does not own, so a future or
    cross-interpreter default change would be a *silent* shift. Own it. This is the same family as
    the S0.2 neutrality guard: a standing assertion over ``structure/`` source."""
    assert _align_streams_passes_explicit_autojunk(capture_mod), (
        "align_streams must pass autojunk explicitly to SequenceMatcher: the default is "
        "load-bearing for the canonical projection and must be owned, not inherited (S1.3a.2)"
    )


def test_junk_policy_guard_discriminates_explicit_from_implicit():
    """Non-vacuity red-proof (mirrors ``test_structure_neutrality``'s planted-literal proof): the
    guard above is green on the clean tree only because the *same predicate* goes red on the
    implicit form. Plant both forms and assert the predicate splits them — without this, a vacuous
    guard that can never red would pass unnoticed."""
    implicit = ast.parse("def align_streams():\n    return SequenceMatcher(None, a, b).get_opcodes()\n")
    explicit = ast.parse(
        "def align_streams():\n    return SequenceMatcher(None, a, b, autojunk=True).get_opcodes()\n"
    )
    assert _align_streams_passes_explicit_autojunk(implicit) is False  # the silent-default regression reds
    assert _align_streams_passes_explicit_autojunk(explicit) is True   # the owned form greens


# --- exports ---------------------------------------------------------------------------- #

def test_public_exports_resolve():
    for name in (
        "capture_witness", "build_canonical", "align_streams", "assert_capture_tiles",
        "PAGE_UNMAPPED", "PROCESSING_SCOPE_INCLUDED", "PROCESSING_SCOPE_EXCLUDED",
    ):
        assert name in structure.__all__, f"{name!r} missing from structure.__all__"
        assert hasattr(structure, name), f"{name!r} not importable from engine.structure"
