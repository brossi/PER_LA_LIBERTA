"""Sidecar contract basics for ``chapter_start_pages.json``.

This is the one hand-curated sidecar that is already a live M1 input (typeset reads it; no
code writes it), so it is where the sidecar-contracts track starts. The richer per-step
schemas the plan envisions (``review_flags``, ``triage_resolved``, ``source_pages`` …) land
with the steps that *produce* them in M3–M5 — writing them now, before a producer exists,
would be schema-without-a-consumer.

The contracts here are the ones that would actually catch a corrupted or drifted sidecar:
the page-offset arithmetic, agreement with the manifest's declared leaf offset, and that
every content-chapter id resolves to a real chapter in the text (the parse_md namespace).
"""

from __future__ import annotations

import json
from pathlib import Path

from engine.config.loader import load_book
from engine.lang.italian import ItalianLanguagePlugin

# test_sidecar_contracts.py -> unit -> tests -> engine
INPUTS = Path(__file__).resolve().parents[2] / "books" / "per_la_liberta" / "inputs"
SIDECAR = INPUTS / "chapter_start_pages.json"
CLEAN = INPUTS / "clean.md"
RECONCILED = INPUTS / "reconciled_chapters.json"


def _sidecar() -> dict:
    # Hard, not skipped: chapter_start_pages.json is committed and required (typeset reads it; no
    # code writes it). A module-level skipif here would silently turn all five contracts green if the
    # file ever moved — a latent vacuous-green. This matches the discipline
    # test_reconciled_chapters_well_formed already states for its own frozen input.
    assert SIDECAR.is_file(), f"frozen PLL sidecar missing: {SIDECAR}"
    return json.loads(SIDECAR.read_text(encoding="utf-8"))


def test_sidecar_well_formed():
    d = _sidecar()
    assert isinstance(d["_pdf_page_offset"], int)
    assert isinstance(d["_last_scan_page"], int)
    chapters = d["chapters"]
    assert isinstance(chapters, list) and chapters

    for ch in chapters:
        assert isinstance(ch["id"], str) and ch["id"]
        assert isinstance(ch["start_scan"], int)

    starts = [ch["start_scan"] for ch in chapters]
    assert starts == sorted(starts), "start_scan must be non-decreasing"
    assert len(set(starts)) == len(starts), "start_scan must be unique"
    assert d["_last_scan_page"] >= starts[-1]


def test_book_page_offset_invariant():
    # book_page == start_scan - _pdf_page_offset for every entry — the relationship the
    # whole scan→book page mapping depends on; a hand-edit that breaks it is caught here.
    d = _sidecar()
    offset = d["_pdf_page_offset"]
    for ch in d["chapters"]:
        if "book_page" in ch:
            assert ch["book_page"] == ch["start_scan"] - offset, ch["id"]


def test_offset_matches_manifest_leaf_offset():
    cfg = load_book("per_la_liberta")
    assert _sidecar()["_pdf_page_offset"] == cfg.manifest.scan.leaf_offset


def test_content_chapter_ids_resolve_to_real_chapters():
    # Every sidecar id that names a content chapter (prefazione / p1_* / p2_*) must be a
    # real parse_md id produced from the text — catches a stale/typo'd sidecar entry that
    # the golden test would silently tolerate (it would just yield page_range=None).
    assert CLEAN.is_file(), f"frozen PLL clean text missing: {CLEAN}"
    known = {
        ci.parse_md
        for ci in ItalianLanguagePlugin().chapter_identities(
            CLEAN.read_text(encoding="utf-8")
        )
    }
    content = [
        ch["id"]
        for ch in _sidecar()["chapters"]
        if ch["id"] == "prefazione" or ch["id"].startswith(("p1_", "p2_"))
    ]
    assert content, "expected content-chapter ids in the sidecar"
    missing = [cid for cid in content if cid not in known]
    assert not missing, f"sidecar content ids absent from text structure: {missing}"


def test_reconciled_chapters_well_formed():
    # reconciled_chapters.json is validate's word-count witness, frozen as an M2 input. The
    # golden exercises it only on the happy path; this pins its shape so a malformed or
    # truncated freeze fails here with a clear message, not a deep KeyError/TypeError inside
    # word_count_preservation. (Hard, not skipped: the file is committed and required.)
    assert RECONCILED.is_file(), f"frozen reconciled witness missing: {RECONCILED}"
    data = json.loads(RECONCILED.read_text(encoding="utf-8"))
    assert isinstance(data, list) and data, "reconciled_chapters.json must be a non-empty list"
    for ch in data:
        assert isinstance(ch.get("id"), str) and ch["id"], ch
        assert isinstance(ch.get("title"), str), ch
        assert isinstance(ch.get("part"), int), ch
        assert isinstance(ch.get("text"), str) and ch["text"].strip(), ch
