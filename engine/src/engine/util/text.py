"""Generic text normalisation — ported verbatim from the top-level utils.py.

Nothing here is language-specific: accent stripping is Unicode-general and slugging
is pure string mechanics. The Italian-specific pieces (ordinals, heading keywords)
live in ``engine.lang.italian``.
"""

from __future__ import annotations

import re
import unicodedata


def strip_accents(text: str) -> str:
    """Remove combining accents (NFKD decomposition). utils.strip_accents."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def build_fold_table(fold: dict) -> dict:
    """Build a ``str.translate`` table from a config accent-fold ``{"from", "to"}`` pair.

    The fixed accent→base fold cleanup uses (``cfg.language.accent_fold``), made generic here so
    no step hand-rolls ``str.maketrans``. Deliberately distinct from ``strip_accents`` (NFKD): the
    two diverge on non-Italian Latin glyphs (e.g. ``ç``/``ñ``), and cleanup's detcore golden is
    pinned to this fixed table, so the difference is load-bearing (M4b-D1)."""
    return str.maketrans(fold["from"], fold["to"])


def normalize_for_comparison(text: str) -> str:
    """Lowercase, strip accents, drop non-[a-z]. utils.normalize_for_comparison.

    The accent-insensitive comparison key used for ordinal/heading matching.
    """
    text = strip_accents(text.lower())
    return re.sub(r"[^a-z]", "", text)


def collapse_spaces(text: str) -> str:
    """Collapse runs of spaces to one. utils.collapse_spaces."""
    return re.sub(r"  +", " ", text)


def slug(text: str, sep: str) -> str:
    """Slugify ``text`` with the given separator.

    The single mechanic behind two of the three chapter-id namespaces:
      - ``sep="_"`` reproduces ``translate.parse_italian_markdown`` base ids;
      - ``sep="-"`` reproduces ``typeset._slug`` HTML-anchor ids.
    Both are ``re.sub(r"[^a-z0-9]", sep, text.lower()).strip(sep)``.
    """
    return re.sub(r"[^a-z0-9]", sep, text.lower()).strip(sep)


def rejoin_lines(text: str) -> str:
    """Rejoin short OCR lines into paragraphs; blank lines separate. utils.rejoin_lines.

    A line-end hyphen is healed only when the next line starts lowercase (a word broken across
    the break); a trailing hyphen before an uppercase word is kept (a real compound).
    """
    paragraphs: list[str] = []
    current: list[str] = []

    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            if current:
                paragraphs.append(" ".join(current))
                current = []
        else:
            if current and current[-1].endswith("-"):
                if stripped[0].islower():
                    current[-1] = current[-1][:-1] + stripped
                else:
                    current.append(stripped)
            else:
                current.append(stripped)

    if current:
        paragraphs.append(" ".join(current))

    return "\n\n".join(paragraphs)
