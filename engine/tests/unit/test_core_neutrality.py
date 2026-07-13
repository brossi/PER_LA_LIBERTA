"""Invariant I4 — core neutrality: the engine package carries no book-identity or typeface
opinion. Which book, which entities, which typeface are config (``books/<id>/manifest.json`` +
``profiles/``), never code — that is what lets the engine port to a second book by swapping
config, with no source edit (the M7 extraction premise).

This is the negative control whose absence let "Bodoni" survive in three core docstrings until a
manual grep caught it (scrubbed in c6790d6). A grep is a one-time act; this makes it a standing
guard that fails the moment a this-book / this-typeface term reappears in code *or* prose
(docstrings and comments included — that is exactly where the leak hid). The denylist is the
known-leak set, not a completeness proof; semantic leakage (a hardcoded chapter count, an
Italian-only assumption) is caught by config-extraction review, not this scan — see
``engine/docs/invariants.md`` (I4 residual risk).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src" / "engine"
PY_FILES = sorted(SRC.rglob("*.py"))

# This-book identity + this-typeface terms that must live in config, never in engine code.
# The Italian *language* plugin may carry Italian-language opinion (its job); it may not carry
# the book's entities/subject/title or the printing's typeface — those are not language facts.
FORBIDDEN = [
    "bodoni", "didone",                                      # typeface (output) opinion
    "orsini", "mazzini", "crespi", "di rudio", "radetzky",   # book entities
    "canessa",                                               # printer
    "risorgimento", "per la libert", "perlalibert",          # book subject / title / IA-id stem
]


def _hits(term: str, files: list[Path]) -> list[str]:
    """Every ``file:lineno: line`` where ``term`` appears (case-insensitive) — the leak report. The
    real-scan test and the planted-literal proof share this one function, so the proof exercises the
    *same* path the guard does (not a re-implemented copy that could drift)."""
    pat = re.compile(re.escape(term), re.IGNORECASE)
    hits: list[str] = []
    for f in files:
        for lineno, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if pat.search(line):
                hits.append(f"{f.name}:{lineno}: {line.strip()}")
    return hits


def test_engine_src_has_python_files():
    # Guard the scan against a vacuous green: if the glob found nothing, every assertion below
    # would pass by examining nothing (the single-fixture-blind-spot trap).
    assert PY_FILES, f"no .py files under {SRC}; the neutrality scan would pass vacuously"


@pytest.mark.parametrize("term", FORBIDDEN)
def test_no_book_or_typeface_opinion_in_core(term):
    hits = _hits(term, PY_FILES)
    assert not hits, (
        f"book/typeface opinion {term!r} leaked into engine core — move it to "
        f"manifest/profile:\n" + "\n".join(hits)
    )


@pytest.mark.parametrize("term", ["bodoni", "di rudio"])
def test_guard_catches_a_planted_literal(tmp_path, term):
    # The non-vacuity proof this guard lacked (its structure/cleanup siblings have one): plant a
    # forbidden term and assert the SAME scan flags it. Without this, a regex/loop regression passes
    # green on a clean tree — exactly how "bodoni" survived in three docstrings before this control.
    # Two representatives (#56): the historical leak term, and a space-containing entity — the only
    # input shapes in FORBIDDEN (all-ASCII list); the full per-term sweep re-proved one code path.
    planted = tmp_path / "leak.py"
    planted.write_text(f'BOOK_OPINION = "{term} ..."\n', encoding="utf-8")
    assert _hits(term, [planted]), f"the guard failed to catch a planted {term!r} — scan is vacuous"
