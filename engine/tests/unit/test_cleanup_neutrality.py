"""M4b-D1 / BR-002 code-neutrality: ``steps/cleanup.py`` carries no Italian or source-noise
*literal* in its functional code. Every accent/letter class and OCR-noise pattern the deterministic
core parameterises on is sourced from ``cfg.language`` / ``cfg.source_noise`` (proven behaviourally
by the detcore golden); this is the static guard that no such literal silently creeps back.

The scan forbids, in functional code:
  - any character in the accented-Latin block ``À–ÿ`` (U+00C0–U+00FF) — the Italian accents and the
    ``word_letter_class`` range, all of which must interpolate from config; and
  - ``£`` (U+00A3) — the relocated ``£→E`` source-noise confusion (now ``char_substitutions``).

Docstrings and comments are excluded: they legitimately *name* ``À-ÿ`` / ``£`` when documenting the
relocation (that is exactly where the prose lives). Universal typography (``« » — “ ” ‘ ’``) and
universal OCR-decoration glyphs (``■ • ¶ §``) are intentionally allowed — they sit OUTSIDE the
forbidden block, carry no language/typeface opinion, and stay in code as engine-general mechanics.
"""

from __future__ import annotations

import ast
import io
import tokenize
from pathlib import Path

CLEANUP = Path(__file__).resolve().parents[2] / "src" / "engine" / "steps" / "cleanup.py"

# Accented-Latin block (the Italian accents + the word_letter_class À-ÿ range) plus the relocated £.
FORBIDDEN = {chr(c) for c in range(0x00C0, 0x0100)} | {"£"}


def _functional_lines(path: Path) -> list[tuple[int, str]]:
    """Return ``(lineno, text)`` for every source line, with comments blanked and docstring lines
    dropped — so the scan sees only functional code, never the prose that documents the change."""
    src = path.read_text(encoding="utf-8")
    rows = [list(line) for line in src.splitlines()]

    # Blank comment spans (tokenize gives exact columns).
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type == tokenize.COMMENT:
            (srow, scol), (_erow, ecol) = tok.start, tok.end
            for col in range(scol, min(ecol, len(rows[srow - 1]))):
                rows[srow - 1][col] = " "

    # Identify docstring line ranges (module/class/function first-statement string).
    doc_lines: set[int] = set()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.body and isinstance(node.body[0], ast.Expr):
                value = node.body[0].value
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    doc_lines.update(range(value.lineno, value.end_lineno + 1))

    return [
        (i, "".join(chars))
        for i, chars in enumerate(rows, 1)
        if i not in doc_lines
    ]


def _scan(path: Path) -> list[str]:
    """Forbidden-char hits in ``path``'s functional code (comments blanked, docstrings dropped) —
    the scan the guard and its non-vacuity proof share, so the proof runs the *real* path, not a
    set-membership stand-in that can't catch an over-blanking bug in ``_functional_lines``."""
    return [
        f"{path.name}:{lineno}: {line.strip()}  (contains {ch!r})"
        for lineno, line in _functional_lines(path)
        for ch in line
        if ch in FORBIDDEN
    ]


def test_no_italian_or_source_noise_literal_in_cleanup():
    hits = _scan(CLEANUP)
    assert not hits, (
        "Italian/source-noise literal leaked into cleanup's functional code — source it from "
        "cfg.language / cfg.source_noise instead:\n" + "\n".join(hits)
    )


def test_scan_actually_excludes_docstrings_and_finds_real_leaks(tmp_path):
    # Two vacuity guards, BOTH through the real scan path (no set-membership tautology):
    # (1) the live source must be non-trivial; (2) a planted leak in functional code is flagged while
    # the same char in a docstring/comment is excluded — so an over-blanking regression in
    # _functional_lines (which would silently make the real scan miss leaks) reddens right here.
    assert len(_functional_lines(CLEANUP)) > 100, "functional-line extraction too small — scan hollow"

    leaky = tmp_path / "leak.py"
    leaky.write_text('"""Doc names à and £ legitimately."""\nx = "à"  # tail à\n', encoding="utf-8")
    hits = _scan(leaky)
    assert any('x = "' in h for h in hits), "a functional à must be flagged by the real scan"
    assert not any("Doc names" in h for h in hits), "a docstring à/£ must be excluded"
    assert all("tail" not in h for h in hits), "a comment à must be blanked, not flagged"
