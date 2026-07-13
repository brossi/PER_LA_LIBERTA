"""Golden tripwire for the chapter-identity refactor — the plan's M1 "prove first" item.

The ``ItalianLanguagePlugin`` must reproduce every chapter-id form the live pipeline
produces (short / parse_md / html_slug / english_title / part / number / page_range),
for all 58 PLL content units, from a frozen copy of the cleaned text (``clean.md``) —  *without*
importing any top-level pipeline code. The expected JSON was frozen from the live tree by
``_generate_chapterids_fixture.py``; if the plugin and live code ever disagree, this fails.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.lang.italian import ItalianLanguagePlugin

GOLDEN_DIR = Path(__file__).resolve().parent
ENGINE_ROOT = GOLDEN_DIR.parents[1]
INPUTS = ENGINE_ROOT / "books" / "per_la_liberta" / "inputs"
EXPECTED = GOLDEN_DIR / "data" / "chapterids_expected.json"

pytestmark = pytest.mark.golden


def _page_ranges(start_pages: dict) -> dict[str, tuple[int, int]]:
    """Reproduce typeset.py:732-735 (end = next.start_scan - 1; last from fallback).

    This range mechanic is typeset's concern (ported in M3); here it only feeds the
    plugin the precomputed ranges keyed by parse_md id, as chapter_start_pages.json is.
    """
    chapters = start_pages.get("chapters", [])
    last_scan = start_pages.get("_last_scan_page", 278)
    ranges: dict[str, tuple[int, int]] = {}
    for idx, entry in enumerate(chapters):
        start = entry["start_scan"]
        end = chapters[idx + 1]["start_scan"] - 1 if idx + 1 < len(chapters) else last_scan
        ranges[entry["id"]] = (start, end)
    return ranges


def _load_identities():
    text = (INPUTS / "clean.md").read_text(encoding="utf-8")
    start_pages = json.loads((INPUTS / "chapter_start_pages.json").read_text(encoding="utf-8"))
    plugin = ItalianLanguagePlugin()
    return plugin.chapter_identities(text, page_ranges=_page_ranges(start_pages))


def test_chapterids_count_matches_structure():
    # 58 content units = prefazione + 24 (P1) + 33 (P2).
    assert len(_load_identities()) == 58


def test_chapterids_reproduce_frozen_fixture():
    # (A separate short-ids test was folded out (#56): every assertion it made — first/last shorts
    # per part, uniqueness — is implied by this per-chapter dict equality against the frozen
    # fixture, and the count test above survives a bad fixture regeneration.)
    expected = json.loads(EXPECTED.read_text(encoding="utf-8"))
    produced = [ci.to_dict() for ci in _load_identities()]
    assert len(produced) == len(expected)
    # Compare per-chapter so a mismatch names the offending chapter, not a giant blob.
    for got, want in zip(produced, expected, strict=True):
        assert got == want, f"identity mismatch for {want['parse_md']}: {got} != {want}"
