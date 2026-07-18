"""contracts.markers — the single-sourced OCR page-marker grammar.

The grammar literal exists once (``PAGE_MARKER_TEMPLATE``); ``PAGE_MARKER_RE`` is *derived* from
it, so ``ocr``'s emit format and ``reconcile``'s parse regex cannot drift to different literals
(plan F6). These pin the round-trip and that the regex really is derived.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from engine.contracts.markers import (
    PAGE_MARKER_RE,
    PAGE_MARKER_TEMPLATE,
    SENTINEL_BLANK,
    SENTINEL_OCR_ERROR_PREFIX,
)

_SRC = Path(__file__).resolve().parents[2] / "src" / "engine"
_MARKERS_MODULE = "contracts/markers.py"
# The wire literals that cross step boundaries; consumers must import these from
# contracts.markers, never re-spell them. Substrings, so "[OCR_ERROR: …]" variants are caught.
_WIRE_LITERALS = ("⟨PAGE:", "[BLANK]", "[OCR_ERROR")


def test_page_marker_roundtrip():
    for n in (1, 7, 42, 278, 1000):
        emitted = PAGE_MARKER_TEMPLATE.format(n)
        m = PAGE_MARKER_RE.match(emitted)
        assert m is not None and int(m.group(1)) == n


def test_regex_is_derived_from_the_template_not_a_second_literal():
    expected = re.escape(PAGE_MARKER_TEMPLATE).replace(re.escape("{}"), r"(\d+)")
    assert PAGE_MARKER_RE.pattern == expected
    # and it equals reconcile's original hand-written form (the port preserved the grammar)
    assert PAGE_MARKER_RE.pattern == r"⟨PAGE:(\d+)⟩"


def test_marker_does_not_match_non_marker_lines():
    assert PAGE_MARKER_RE.match("Capitolo Primo") is None
    assert PAGE_MARKER_RE.match("⟨PAGE:⟩") is None        # no digits
    assert PAGE_MARKER_RE.match("testo ⟨PAGE:3⟩") is None  # not anchored at line start


def test_sentinels_are_the_wire_literals():
    # These cross step boundaries (template↔stitcher, ocr↔reconcile-tolerant), so a change is a
    # deliberate, review-visible protocol change — pinned here.
    assert SENTINEL_BLANK == "[BLANK]"
    assert SENTINEL_OCR_ERROR_PREFIX == "[OCR_ERROR"


# --- invariant I5 negative control: single-sourcing across the *whole* package, not just the
# round-trip within markers.py. The tests above prove the regex is derived from the template;
# this proves no other module re-spells the wire literals as a second source-of-truth. Docstrings
# and comments legitimately mention them (documentation), so the scan looks only at executable
# string constants via the AST — a comment/docstring mention is not a drift risk; a hardcoded
# literal in a comparison or regex is (engine/docs/invariants.md, I5).

def _docstring_constant_ids(tree: ast.AST) -> set[int]:
    """ids() of the Constant nodes that are docstrings (first stmt of module/class/function)."""
    ids: set[int] = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and body:
            first = body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(
                first.value.value, str
            ):
                ids.add(id(first.value))
    return ids


def test_wire_literals_are_single_sourced_across_the_package():
    offenders: list[str] = []
    for f in sorted(_SRC.rglob("*.py")):
        if f.as_posix().endswith(_MARKERS_MODULE):
            continue  # the one legitimate definition site
        tree = ast.parse(f.read_text(encoding="utf-8"))
        docstrings = _docstring_constant_ids(tree)
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and id(node) not in docstrings
                and any(lit in node.value for lit in _WIRE_LITERALS)
            ):
                offenders.append(f"{f.relative_to(_SRC)}:{node.lineno}: {node.value!r}")
    assert not offenders, (
        "wire-protocol literal re-spelled outside contracts/markers.py — import the constant "
        "instead so emit/parse cannot drift:\n" + "\n".join(offenders)
    )
