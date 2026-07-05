"""S0.2 — structure-core neutrality guard (ENGINE_STRUCTURE_TASKS).

``engine.structure`` models document structure for *any* book/language. Which word marks a
chapter, which ordinal grammar numbers it, how many parts a book has, which marks quote foreign
terms — all of that is data in the structure profile + the per-book structure map
(ENGINE_STRUCTURE_PLAN §7.1), never code. This guard makes that a standing assertion over
``src/engine/structure/``: a source-language heading word, a guillemet used as a structure marker,
or a baked part/chapter count appearing there is a leak — the F1 (recognition in the language
plugin) / F2 (fixed-shape validator) anti-patterns this axis exists to remove.

Distinct from ``test_core_neutrality`` (book *entities* + typeface, across all of core); this one
targets the structure axis's specific failure mode. Like that guard, the denylist is the
known-leak set, not a completeness proof — semantic leakage (an Italian-only segmentation
assumption with no literal) is caught by profile-extraction review, not this scan.

Invariant (proven red below — red-first, §9): no source-language heading, guillemet (literal char
OR ``\\u00ab``/``\\xab`` escape form), or baked part/chapter count appears in ``structure/`` core.
``test_no_language_or_structure_literal_…`` is green on the package; ``test_guard_catches_a_planted_literal``
is the non-vacuity red-proof — it plants each forbidden term and asserts the scan flags it, so the
guard is known to go red on a real reintroduction, not merely green on a clean tree.

Scope (extended at S4.4/B-5 per s4_plan inv 15 / B-1 audit F4): the scan walks the LIVE package
contents dynamically — every ``structure/**/*.py`` **and every ``structure/schema/*.json``** — so
the Tier-1 schema is inside the neutrality boundary too. inv 22's mutation (a PLL ``node_class``
``enum`` in the schema) lands here as well as in the schema-shape test: PLL block names are
source-language words the term scan flags.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

STRUCTURE_SRC = Path(__file__).resolve().parents[2] / "src" / "engine" / "structure"
PY_FILES = sorted(STRUCTURE_SRC.rglob("*.py"))
SCHEMA_JSON_FILES = sorted((STRUCTURE_SRC / "schema").glob("*.json"))
SCANNED_FILES = PY_FILES + SCHEMA_JSON_FILES

# Language / ordinal / structure literals that must live in the profile or structure map, never in
# the structure core. Three categories the S0.2 done-when names: heading grammar, guillemets, count.
FORBIDDEN = [
    # source-language heading + matter grammar (PLL's, but the rule is general: no source headings)
    "capitolo", "prefazione", "parte prima", "parte seconda",
    # guillemets used as quote/structure markers (the profile declares a book's quote marks),
    # BOTH as the literal char and as the unicode/hex escape forms — live validate.py writes them
    # as "«"/"»" (validate.py:108-109), which a char-only scan would miss: the exact
    # reintroduction path the pipeline actually uses.
    "«", "»", "\\u00ab", "\\u00bb", "\\xab", "\\xbb",
    # OCR-language literal (S2.1.2 #36, DT-1/G-2): the Tesseract language code the PyMuPDF+Tesseract
    # backend OCRs with is a per-book scan opinion — it lives in book config, passed to the backend
    # as a required parameter, never baked in core. Scanned in QUOTED form only ("ita"/'ita'): a bare
    # `ita` would false-positive on ordinary English words (italic, vital, capital), whereas the
    # quoted forms only match a string literal — the exact reintroduction path (a hardcoded
    # `language="ita"` default). The engine_id string builds `lang={language}` from the parameter, so
    # no literal appears; the profile/manifest is where "ita" lives. The `+`-anchored forms catch
    # Tesseract's combined-code syntax (`language="ita+eng"` / `"eng+ita"` / mid-position
    # `"deu+ita+eng"`), which the bare quoted pair would miss while staying anchored (quote or `+`
    # adjacent to `ita` on both sides) against English-word false positives.
    '"ita"', "'ita'", '"ita+', "'ita+", '+ita"', "+ita'", "+ita+",
    # PLL's baked structure shape (F2): the live validator's `check_chapter_count` hard-codes the
    # part/chapter count (its `h3_count` result key; the 24+33=57 literals). The general tree model
    # replaces that — either token reappearing in structure/ core is book opinion leaking back in.
    "check_chapter_count", "h3_count",
]


def _hits(term: str, files: list[Path]) -> list[str]:
    """Every ``file:lineno: line`` where ``term`` appears (case-insensitive), the leak report."""
    pat = re.compile(re.escape(term), re.IGNORECASE)
    hits: list[str] = []
    for f in files:
        for lineno, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if pat.search(line):
                hits.append(f"{f.name}:{lineno}: {line.strip()}")
    return hits


def test_structure_src_has_python_files():
    # Guard against a vacuous green: an empty glob would pass every assertion below by scanning
    # nothing (the single-fixture-blind-spot trap). Both globs must be non-empty: the schema dir
    # exists from S4.4/B-5 on, so an empty JSON glob means the scan silently lost its Tier-1 arm.
    assert PY_FILES, f"no .py files under {STRUCTURE_SRC}; the neutrality scan would pass vacuously"
    assert SCHEMA_JSON_FILES, (
        f"no schema .json under {STRUCTURE_SRC / 'schema'}; the inv 15/22 JSON arm would pass vacuously"
    )


@pytest.mark.parametrize("term", FORBIDDEN)
def test_no_language_or_structure_literal_in_structure_core(term):
    hits = _hits(term, SCANNED_FILES)
    assert not hits, (
        f"language/structure literal {term!r} leaked into engine.structure core — move it to the "
        f"structure profile/map:\n" + "\n".join(hits)
    )


@pytest.mark.parametrize("term", FORBIDDEN)
def test_guard_catches_a_planted_literal(tmp_path, term):
    # The non-vacuity proof: plant each forbidden term in a throwaway file and assert the scan flags
    # it. Without this, an over-narrow regex could silently stop catching reintroductions.
    planted = tmp_path / "leak.py"
    planted.write_text(f'HEADING_MARKER = "{term} ..."\n', encoding="utf-8")
    assert _hits(term, [planted]), f"the guard failed to catch a planted {term!r} — scan is vacuous"


@pytest.mark.parametrize("term", FORBIDDEN)
def test_guard_catches_a_planted_literal_in_schema_json(tmp_path, term):
    # The JSON arm's non-vacuity proof (inv 15/22): a book-shaped enum value planted in a schema
    # file — e.g. `"enum": ["capitolo", …]` — is flagged by the same term scan.
    planted = tmp_path / "leak.schema.json"
    planted.write_text(f'{{"node_class": {{"enum": ["{term}"]}}}}\n', encoding="utf-8")
    assert _hits(term, [planted]), f"the JSON arm failed to catch a planted {term!r} — scan is vacuous"
