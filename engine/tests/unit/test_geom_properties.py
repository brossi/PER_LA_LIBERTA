"""S2.2 (#30) — the geometry property tier (§9), binding against the as-built S2.1 backend.

The done-when names four properties. Two are **net-new here** because they need a *real page* the
existing synthetic/construction-level tests can't supply; two already hold, bindingly, elsewhere and
are **cited, not re-asserted** (§9 anti-cheat: re-asserting green under a new name proves nothing —
`feedback_no_cheating_results`):

- **P1 — boxes within page bounds (real page).** NET-NEW below. `test_geometry_backend` proves
  `WordBox`/`PageGeometry` reject malformed coords at *construction*, but a `WordBox` does not know
  its page's width/height, so "box ⊆ page" is genuinely unchecked there. This asserts it over the
  as-built backend's real output — the property form of the run's `oob_boxes` stat.
- **P2 — source-order ↔ geometric-order coherence (real page).** NET-NEW below. `test_geometry_e2e`
  proves the no-witness branch on a *synthetic* two-column page; the done-when says *a real page*.
  This runs the real `reading_order` over a real PLL two-column body page (p219) and checks it
  recovers the column-ordered witness order, with the naive full-width order as the strict control.
- **P3 — primary-witness box on canonical atoms where matched.** CITED (not re-coded):
  `test_geom_match.test_canonical_attach_resolves_through_derived_from_not_id` (G-20, canonical atom
  carries its primary witness's box via `derived_from`) +
  `test_canonical_multi_primary_is_unmatched_never_union_or_first_pick` (multi-primary never
  unioned/picked) + `test_matched_geom_carries_all_configured_provenance_verbatim` (all four
  provenance fields verbatim). Those bind the property; duplicating them here would only add a
  green with no discriminating power.
- **P4 — absent/unmatched geom representable and excluded from primary re-bind.** The
  *representability* half is bound by `test_atoms` (the `Geom` absent/present invariant, all six
  fields) + `test_geom_match.test_zero_match_atom_writes_absent_never_an_invented_box`. What is
  NET-NEW below is the **exclusion contract** across all three unmatched causes expressed as the
  executable predicate S5's `geometry-primary` re-bind will consume — with the honest limit that the
  *operational* exclusion (a re-bind actually skipping these atoms) is S5 code and is re-proven at
  S5.5 (`ENGINE_STRUCTURE_PLAN.md` §9 re-binding tier). This test binds the data contract, not a
  re-bind that does not exist yet — it does not dress a representability check as an S5 test.

Invariants (proven red below):
1. P1: every real box lies within [0,width]×[0,height]; an injected off-page box fails the same
   predicate (so the check is not vacuous).
2. P2: real-page col-aware order coverage ≥0.85 and strictly exceeds the naive full-width order;
   both pinned to the captured values as regression sentinels.
3. P4: for zero-match / multi-primary / no-primary atoms the attached geom is absent and NOT
   primary-rebind-eligible; a matched atom IS eligible (the predicate does real work).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.structure import (
    PageGeometry,
    WordBox,
    ordered_coverage,
    reading_order,
)
from engine.structure.geom_match import (
    OUTCOME_MATCHED,
    attach_geometry,
    build_geom_sidecar,
    match_stream,
    normalize_tokens,
)
from engine.structure.geom_review import page_order_qa
from engine.structure.geom_sidecar import REASON_ZERO_MATCH, SourceScan

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures/geometry/pll_page_two_column.json"


@pytest.fixture(scope="module")
def real_page():
    """A real PLL two-column body page (p219) captured from the frozen run — boxes + the copy1
    witness window + the detected column split. Real data; the captured order_qa values are
    reproduced byte-for-byte by the runner (cross-checked against the sidecar at capture time)."""
    data = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    page = PageGeometry(
        page=data["page"], width=data["width"], height=data["height"],
        words=tuple(WordBox(text=w[0], bbox=(w[1], w[2], w[3], w[4])) for w in data["words"]),
    )
    return page, data


# --- P1: boxes within page bounds, on a real page ------------------------------------------- #


def _within_bounds(box: WordBox, width: float, height: float) -> bool:
    x0, y0, x1, y1 = box.bbox
    return 0.0 <= x0 < x1 <= width and 0.0 <= y0 < y1 <= height


def test_p1_every_real_box_lies_within_page_bounds(real_page):
    page, _ = real_page
    assert page.words, "fixture must carry a populated real page"
    offenders = [w for w in page.words if not _within_bounds(w, page.width, page.height)]
    assert offenders == [], f"{len(offenders)} real box(es) fell outside the page: {offenders[:3]}"


def test_p1_predicate_catches_an_off_page_box(real_page):
    # The red teeth for P1: the property is not vacuously true. A box whose right edge overruns the
    # page width constructs fine as a WordBox (WordBox has no page-width context) yet is out of
    # bounds — exactly the class the as-built run drops-and-counts (`oob_boxes`).
    page, _ = real_page
    overrun = WordBox(text="x", bbox=(10.0, 10.0, page.width + 5.0, 22.0))
    assert not _within_bounds(overrun, page.width, page.height)


# --- P2: source-order (witness) ↔ geometric-order (boxes) coherence, on a real page --------- #


def test_p2_real_page_column_order_recovers_the_witness_order(real_page):
    page, data = real_page
    window, split_x = data["witness_window"], data["split_x"]
    col_aware = page_order_qa(window, page.words, split_x)
    # Recovers the column-ordered witness order to primary grade on this confident two-column page.
    assert col_aware == pytest.approx(data["order_qa_col_aware"])
    assert col_aware >= 0.85


def test_p2_naive_full_width_order_is_strictly_worse(real_page):
    # The control that gives P2 its teeth (mirrors test_geometry_e2e on real data): ignoring the
    # column split interleaves the two columns row-by-row and collapses ordered coverage. RED
    # (mutant): if `reading_order` ignored `split_x`, col-aware would equal naive and the > below
    # would fail.
    page, data = real_page
    window, split_x = data["witness_window"], data["split_x"]
    col_aware = page_order_qa(window, page.words, split_x)
    naive = page_order_qa(window, page.words, None)
    assert naive == pytest.approx(data["order_qa_naive"])
    assert naive < col_aware
    assert col_aware - naive > 0.3  # p219: ~0.956 vs ~0.502


def test_p2_binds_the_real_reading_order_functions(real_page):
    # page_order_qa is the thin wrapper; assert the underlying reading_order + normalize + ordered_
    # coverage compose to the same value, so P2 binds the actual detector functions, not the wrapper.
    page, data = real_page
    ordered_texts = reading_order(page.words, split_x=data["split_x"])
    tokens = [tok for text in ordered_texts for tok in normalize_tokens(text)]
    assert ordered_coverage(
        list(data["witness_window"]), tokens
    ) == pytest.approx(data["order_qa_col_aware"])


# --- P4: absent/unmatched geom is representable AND ineligible for primary re-bind ---------- #


def _primary_rebind_eligible(geom) -> bool:
    """The contract S5's `geometry-primary` re-bind will require to anchor on a box: a present geom
    with real coordinates and a confidence. An absent geom has none of these, so it is structurally
    ineligible — the exclusion the done-when names. (Operational exclusion is re-proven at S5.5, when
    the re-bind exists; here we bind the *data* contract the re-bind reads.)"""
    return bool(geom.present and geom.bbox is not None and geom.match_confidence is not None)


def _build(outcome, **kw):
    kw.setdefault("source_scan", SourceScan(kind="pdf", sha256="h", n_pages=1, n_bytes=1))
    kw.setdefault("backend_params", {"dpi": 1, "language": "x"})
    kw.setdefault("engine_id", "engine-x")
    return build_geom_sidecar(outcome, **kw)


def test_p4_zero_match_atom_is_absent_and_rebind_ineligible(matchkit):
    stream = matchkit.witness_stream(["alfa bravo charlie delta", "zulu yankee xray"])
    page = matchkit.page(1, ["alfa", "bravo", "charlie", "delta"])
    outcome = match_stream(stream, [page], page_accept_rate=0.5, atom_match_floor=0.6)
    assert outcome.atoms["w-sentinel-3-a1"].reason == REASON_ZERO_MATCH
    result = attach_geometry(stream, _build(outcome))
    absent = result.atoms[1].geom
    assert not absent.present
    assert not _primary_rebind_eligible(absent)


def test_p4_multi_and_no_primary_canonical_atoms_are_rebind_ineligible(matchkit):
    # The other two unmatched causes on the canonical projection: multi-primary (two matched
    # back-links, never unioned) and no-primary (derived only from a witness with no box layer).
    witness = matchkit.witness_stream(
        ["alfa bravo charlie", "delta echo foxtrot"], witness="w-anchor", ids=["w-one", "w-two"]
    )
    page = matchkit.page(1, ["alfa", "bravo", "charlie", "delta", "echo", "foxtrot"])
    sidecar = _build(match_stream(witness, [page], page_accept_rate=0.5, atom_match_floor=0.5))
    canonical = matchkit.canonical_stream(
        [
            ("canon-multi", "alfa bravo charlie delta echo foxtrot",
             [("w-anchor", "w-one"), ("w-anchor", "w-two")]),
            ("canon-noprimary", "golf hotel india", [("w-other", "other-a0")]),
        ]
    )
    result = attach_geometry(canonical, sidecar, witness_stream=witness)
    for atom in result.atoms:
        assert not atom.geom.present
        assert not _primary_rebind_eligible(atom.geom)


def test_p4_a_matched_atom_is_rebind_eligible_predicate_does_real_work(matchkit):
    # Positive control: without it, `_primary_rebind_eligible` could be a constant-False that passes
    # every negative above vacuously.
    stream = matchkit.witness_stream(["alfa bravo charlie"], witness="w-anchor", ids=["w-one"])
    page = matchkit.page(1, ["alfa", "bravo", "charlie"])
    outcome = match_stream(stream, [page], page_accept_rate=0.5, atom_match_floor=0.5)
    result = attach_geometry(stream, _build(outcome))
    geom = result.atoms[0].geom
    assert geom.present and result.outcomes["w-one"].status == OUTCOME_MATCHED
    assert _primary_rebind_eligible(geom)
