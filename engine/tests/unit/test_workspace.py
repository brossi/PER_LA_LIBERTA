"""``BookWorkspace`` — area derivation and the path-containment guarantee.

The containment assertion is the unit-level guarantee that the engine cannot write into
the live PLL tree: ``resolve``/``resolve_root`` must reject any ``..`` traversal, absolute
part, or symlink that escapes the work tree. (The fuller before/after-hash isolation test
arrives in M2, once a real step actually writes.)

Invariants (each proven red on violation below — red-first, ENGINE_STRUCTURE_PLAN §9):
  - areas derive under the work tree; ``ensure`` creates all three — the ``test_areas/ensure_…``.
  - ``resolve``/``resolve_root`` return in-tree paths for valid input — the two ``returns_…`` tests.
  - they reject unknown area, ``..`` escape, and absolute part — the ``rejects_…`` tests
    (pytest.raises: a non-raise is red); ``resolve_root()`` with no parts == root.
  - **the guard canonicalizes THROUGH symlinks** — an in-tree link pointing outside is rejected
    (``test_resolve…escape_through_an_in_tree_symlink``). The load-bearing red-proof: a lexical
    (``normpath``) refactor keeps every ``..`` test green yet lets this through, so this is the
    only test that pins ``.resolve()`` as the live-tree-unreachable mechanism.
"""

from __future__ import annotations

import pytest

from engine.paths import BookWorkspace


def test_areas_are_under_the_book_work_tree(tmp_path):
    ws = BookWorkspace.for_book("demo", tmp_path)
    assert ws.root == (tmp_path / "demo" / "work").resolve()
    assert ws.data == ws.root / "data"
    assert ws.output == ws.root / "output"
    assert ws.state == ws.root / "state"


def test_ensure_creates_the_three_areas(tmp_path):
    ws = BookWorkspace.for_book("demo", tmp_path).ensure()
    assert ws.data.is_dir() and ws.output.is_dir() and ws.state.is_dir()


def test_resolve_returns_paths_inside_the_workspace(tmp_path):
    ws = BookWorkspace.for_book("demo", tmp_path)
    p = ws.resolve("data", "reconciled_chapters.json")
    assert p == ws.data / "reconciled_chapters.json"
    assert p.is_relative_to(ws.root)


def test_resolve_rejects_unknown_area(tmp_path):
    ws = BookWorkspace.for_book("demo", tmp_path)
    with pytest.raises(ValueError, match="unknown workspace area"):
        ws.resolve("nope", "x.json")


@pytest.mark.parametrize("escape", ["../../../etc/passwd", "a/../../../x"])  # leading vs mid-path ..; a third variant shared their branch (#56)
def test_resolve_rejects_traversal_escape(tmp_path, escape):
    ws = BookWorkspace.for_book("demo", tmp_path)
    with pytest.raises(ValueError, match="escapes workspace"):
        ws.resolve("data", escape)


def test_resolve_rejects_absolute_part(tmp_path):
    ws = BookWorkspace.for_book("demo", tmp_path)
    with pytest.raises(ValueError, match="must be relative"):
        ws.resolve("data", "/etc/passwd")


# --- resolve_root: the area-less work-root resolver (S0.1 structure artifacts) ---------- #

def test_resolve_root_returns_paths_at_the_work_root(tmp_path):
    ws = BookWorkspace.for_book("demo", tmp_path)
    p = ws.resolve_root("structure_map.json")
    assert p == ws.root / "structure_map.json"
    assert p.parent == ws.root  # at the root, not under data/output/state
    assert p.is_relative_to(ws.root)


@pytest.mark.parametrize("escape", ["../../../etc/passwd", "../sibling", "a/../../x"])
def test_resolve_root_rejects_traversal_escape(tmp_path, escape):
    ws = BookWorkspace.for_book("demo", tmp_path)
    with pytest.raises(ValueError, match="escapes workspace"):
        ws.resolve_root(escape)


def test_resolve_root_rejects_absolute_part(tmp_path):
    ws = BookWorkspace.for_book("demo", tmp_path)
    with pytest.raises(ValueError, match="must be relative"):
        ws.resolve_root("/etc/passwd")


def test_resolve_root_with_no_parts_returns_the_root(tmp_path):
    # Contract pin: the area-less resolver with no parts resolves to the work root itself
    # (resolving nothing relative to root *is* root) — contained, intentional, not an escape.
    ws = BookWorkspace.for_book("demo", tmp_path)
    assert ws.resolve_root() == ws.root


# --- the canonicalization contract: the guard resolves THROUGH symlinks ------------------ #
#
# These are the load-bearing negative controls for the whole live-tree-unreachable guarantee.
# Every other escape test uses ".." strings, which *lexical* normalization collapses identically
# — so a refactor swapping resolve()'s symlink canonicalization for os.path.normpath would keep
# all of those green while opening a real escape. A symlink planted INSIDE the work tree but
# pointing OUTSIDE it is the input that distinguishes the two: only true canonicalization catches
# it. If either of these ever fails, the guard has stopped resolving symlinks — a real hole.

def test_resolve_rejects_escape_through_an_in_tree_symlink(tmp_path):
    ws = BookWorkspace.for_book("demo", tmp_path).ensure()
    outside = tmp_path / "outside"
    outside.mkdir()
    (ws.data / "evil").symlink_to(outside, target_is_directory=True)  # in-tree link → outside
    with pytest.raises(ValueError, match="escapes workspace"):
        ws.resolve("data", "evil", "secret.txt")


def test_resolve_root_rejects_escape_through_an_in_tree_symlink(tmp_path):
    ws = BookWorkspace.for_book("demo", tmp_path).ensure()
    outside = tmp_path / "outside"
    outside.mkdir()
    (ws.root / "evil").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="escapes workspace"):
        ws.resolve_root("evil", "secret.txt")
