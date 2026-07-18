"""``ChapterIdentity`` — the single value object that unifies the three chapter-id
namespaces the live pipeline keeps in separate code paths.

In the top-level tree the same chapter is named three different ways, derived in three
different modules, with no shared object — the highest-regression-risk seam in the port
(plan §"The hard cases"). Here every form is computed once, together, by the active
``LanguagePlugin`` (which owns the language-specific recognition) using only generic
mechanics. ``test_chapterids_golden`` freezes all forms for the example book and asserts
reproduction.

The three forms (see engine/docs/constant_inventory.md for code provenance):
  short      ``p1_ch01`` / ``prefazione``        — keys ``chapter_pages.json``
  parse_md   ``p1_capitolo_primo`` / ``prefazione`` — keys ``chapter_start_pages.json``,
                                                      ``typography.json``, translate state
  html_slug  ``parte-prima-capitolo-primo``      — HTML anchors in the edition
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class ChapterIdentity:
    """All identifiers + structural facts for one content chapter.

    ``part`` is 0 for the prefazione (no part), else the 1-based part number.
    ``number`` is the 1-based chapter index within its part (None for the prefazione).
    ``page_range`` is an inclusive (start_scan, end_scan) leaf pair, or None when the
    per-book ``chapter_start_pages`` sidecar has no entry for this chapter.
    """

    short: str
    parse_md: str
    html_slug: str
    english_title: str
    part: int
    number: int | None
    title: str
    page_range: tuple[int, int] | None = None

    def to_dict(self) -> dict:
        """JSON-friendly dict; page_range becomes a 2-list to match sidecar JSON."""
        d = asdict(self)
        if self.page_range is not None:
            d["page_range"] = list(self.page_range)
        return d
