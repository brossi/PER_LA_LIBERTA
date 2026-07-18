"""``LanguagePlugin`` — the abstraction the core threads instead of touching any
language-specific constant.

Language-specific *recognition* is abstract (ordinals, heading keywords, part phrases,
title→English); the *mechanics* that assemble chapter identities are concrete and shared
here, so every language gets the same correct three-namespace derivation for free. This
is the seam that breaks the live ``utils`` → ``translate`` import cycle (plan §"hard
cases"): all id forms are produced together by one object.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable, Sequence

from ..util.chapterids import ChapterIdentity
from ..util.text import slug

#: Process-wide spaCy pipeline cache, keyed by (model, disabled-components). Shared across
#: plugin instances (the registry makes a fresh instance per call), keyed by model so
#: languages never collide. Mirrors the live pipeline's function-attribute singletons.
_SPACY_PIPELINES: dict[tuple, object] = {}


def _as_range(value) -> tuple[int, int] | None:
    """Normalise a sidecar [start, end] (list/tuple) to a 2-tuple, or None."""
    if value is None:
        return None
    start, end = value
    return (int(start), int(end))


class LanguagePlugin(ABC):
    """Per-language recognition + shared chapter-identity assembly."""

    #: spaCy-style language id, e.g. ``"it"``. Set by each implementation.
    language_id: str = ""

    # ------------------------------------------------------------------ #
    # Language-specific recognition (implemented per language)
    # ------------------------------------------------------------------ #
    @abstractmethod
    def structural_part(self, title: str) -> tuple[str, int, str] | None:
        """If ``title`` is a part header, return (short_code, part_number,
        canonical_title) — e.g. ("p1", 1, "Parte Prima"); else None."""

    @abstractmethod
    def title_to_english(self, title: str) -> str:
        """Translate a chapter/part title to English (``Capitolo Primo`` →
        ``Chapter One``). Returns the input unchanged if unrecognised."""

    @abstractmethod
    def is_chapter_heading(self, line: str) -> tuple[int, str] | None:
        """Detect a chapter heading in *raw OCR text* (pre-markdown). Returns
        (chapter_number, raw_title) or None. Used by reconcile/cleanup."""

    @abstractmethod
    def parse_chapter_number(self, words: Sequence[str]) -> int | None:
        """Parse a chapter number from the words after the heading keyword."""

    @abstractmethod
    def strip_boilerplate(self, text: str) -> str:
        """Trim front/back matter outside the book's content bounds."""

    @abstractmethod
    def split_raw_chapters(
        self, text: str, *, running_heads: Sequence[str] = ()
    ) -> list[dict]:
        """Segment *raw OCR text* into chapters via structural markers + chapter headings.

        Returns ``[{"id", "title", "part", "text"}]`` with short ids
        (``prefazione`` / ``p1_ch01`` / ``p2_ch01``). Used by reconcile — distinct from
        ``chapter_identities``, which parses finished ``##``/``###`` markdown.

        ``running_heads`` are **book-level** regex bodies (from ``cfg.structure.running_heads``,
        passed by the caller) for page-furniture lines — typically the repeated book title — that
        must be dropped, not treated as content. They live in the book manifest, not the language
        plugin, so the plugin stays cross-title (BR-004)."""

    # ------------------------------------------------------------------ #
    # Shared mechanics (language-agnostic)
    # ------------------------------------------------------------------ #
    def load_spacy(self, model: str, *, disable: Sequence[str] = ()):
        """Load and cache a spaCy pipeline for ``model``, disabling ``disable`` components.

        Cached by ``(model, disable)`` so an NER-only pipeline (``disable=["parser",
        "lemmatizer"]``, as cleanup/validate use) and a lemmatizer-bearing one for
        dictionary lookup never share the wrong pipeline (plan §"spaCy per-language
        packaging"). The model name comes from config (``cfg.language.spacy_model``), so a
        book can override it without touching code.
        """
        import spacy

        key = (model, tuple(disable))
        nlp = _SPACY_PIPELINES.get(key)
        if nlp is None:
            try:
                nlp = spacy.load(model, disable=list(disable))
            except OSError as exc:
                raise OSError(
                    f"spaCy model {model!r} is not installed; install the book's language "
                    f"extra (e.g. `uv sync --extra it`)."
                ) from exc
            _SPACY_PIPELINES[key] = nlp
        return nlp

    def chapter_identities(
        self,
        markdown_text: str,
        *,
        page_ranges: dict[str, tuple[int, int]] | None = None,
        skip_titles: Iterable[str] = (),
    ) -> list[ChapterIdentity]:
        """Produce a ``ChapterIdentity`` for every content chapter in the cleaned
        markdown, deriving all three id namespaces together.

        Mirrors ``translate.parse_italian_markdown`` (only ``##``/``###`` headers;
        the H1 book title is ignored), ``typeset._slug`` for the HTML anchor, and the
        sequential-per-part short-id assignment. ``page_ranges`` is keyed by parse_md
        id (as ``chapter_start_pages.json`` is) and supplied precomputed by the caller.
        """
        ranges = page_ranges or {}
        skip = set(skip_titles)

        out: list[ChapterIdentity] = []
        part_short: str | None = None
        part_num = 0
        part_title: str | None = None
        counter = 0

        for line in markdown_text.split("\n"):
            if not (line.startswith("## ") or line.startswith("### ")):
                continue
            title = line.lstrip("#").strip()
            if title in skip:
                continue

            part = self.structural_part(title)
            if part is not None:
                part_short, part_num, part_title = part
                counter = 0
                continue

            base_us = slug(title, "_")
            base_hy = slug(title, "-")
            if part_short:
                parse_md = f"{part_short}_{base_us}"
                html_slug = f"{slug(part_title or '', '-')}-{base_hy}"
                counter += 1
                short = f"{part_short}_ch{counter:02d}"
                number: int | None = counter
                chapter_part = part_num
            else:
                # Pre-part content chapter (the prefazione): no part prefix.
                parse_md = base_us
                html_slug = base_hy
                short = base_us
                number = None
                chapter_part = 0

            out.append(
                ChapterIdentity(
                    short=short,
                    parse_md=parse_md,
                    html_slug=html_slug,
                    english_title=self.title_to_english(title),
                    part=chapter_part,
                    number=number,
                    title=title,
                    page_range=_as_range(ranges.get(parse_md)),
                )
            )
        return out
