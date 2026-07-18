"""Invariant I8 — atomic / no-partial-output: every artifact a later step consumes is written
through an atomic helper (temp file + ``os.replace``), never a raw write a mid-write crash could
truncate into a file the next step then reads as *complete*. This is the assumption the I2 residual
rests on: a present internal artifact is never half-written, so a sibling step's read failure is
bug-class, not an expected error. Found violated in the post-M4a completeness audit (download and
ocr wrote their text witnesses with raw ``Path.write_text``); these controls keep it fixed.

Positive control: ``atomic_write_text`` round-trips and leaves no temp residue. Negative controls: a
forced failure leaves nothing half-written at the destination, and an AST scan forbids raw file
writes anywhere under ``steps/`` (the sanctioned writers live in ``util/jsonio.py``, excluded).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from engine.util.jsonio import atomic_write_text

_SRC = Path(__file__).resolve().parents[2] / "src" / "engine"
_STEPS = _SRC / "steps"


def test_atomic_write_text_roundtrips_and_leaves_no_tmp(tmp_path):
    target = tmp_path / "witness.txt"
    atomic_write_text(target, "héllo ⟨PAGE:1⟩\nworld")
    assert target.read_text(encoding="utf-8") == "héllo ⟨PAGE:1⟩\nworld"
    assert [p.name for p in tmp_path.iterdir()] == ["witness.txt"]  # no .tmp residue


def test_atomic_write_text_failure_leaves_nothing_partial(tmp_path):
    # Force a failure mid-write (f.write of a non-str raises TypeError): the destination must not
    # exist and the temp file must be cleaned up — the property the whole invariant turns on.
    target = tmp_path / "witness.txt"
    with pytest.raises(TypeError):
        atomic_write_text(target, 123)  # type: ignore[arg-type]
    assert not target.exists()
    assert list(tmp_path.iterdir()) == []


def _open_mode(call: ast.Call, pos: int = 1) -> str | None:
    # mode is positional arg `pos` (1 for builtin open(path, "w"); 0 for path.open("w")) or mode=.
    if len(call.args) > pos and isinstance(call.args[pos], ast.Constant) and isinstance(
        call.args[pos].value, str
    ):
        return call.args[pos].value
    for kw in call.keywords:
        if kw.arg == "mode" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
            return kw.value.value
    return None


def _raw_writes_in(path: Path) -> list[str]:
    hits: list[str] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr in ("write_text", "write_bytes"):
            hits.append(f"{path.name}:{node.lineno}: .{func.attr}(...)")
        elif isinstance(func, ast.Attribute) and func.attr == "open":
            mode = _open_mode(node, 0)  # path.open("w"): mode is the first positional arg
            if mode and any(c in mode for c in "wax"):
                hits.append(f"{path.name}:{node.lineno}: .open(..., {mode!r})")
        elif isinstance(func, ast.Name) and func.id == "open":
            mode = _open_mode(node)  # open(path, "w"): mode is the second positional arg
            if mode and any(c in mode for c in "wax"):
                hits.append(f"{path.name}:{node.lineno}: open(..., {mode!r})")
    return hits


def test_steps_have_python_files():
    # Guard against a vacuous green if the glob ever finds nothing.
    assert sorted(_STEPS.glob("*.py")), f"no step modules under {_STEPS}"


def test_no_raw_artifact_writes_in_steps():
    offenders: list[str] = []
    for f in sorted(_STEPS.glob("*.py")):
        offenders += _raw_writes_in(f)
    assert not offenders, (
        "raw (non-atomic) file write in a step — route artifacts through "
        "util.jsonio.atomic_write_{json,text} so a crash can't truncate a consumed artifact:\n"
        + "\n".join(offenders)
    )


def test_detector_catches_pathlib_open_write(tmp_path):
    # The detector must flag the pathlib `.open("w")` write idiom, not only `.write_text` / bare
    # `open()` — else a step could bypass the atomic helper through the most idiomatic raw write and
    # stay green. This proves the AST scan's reach matches its claim ("anywhere under steps/").
    probe = tmp_path / "probe.py"
    probe.write_text(
        "from pathlib import Path\n"
        "def w(p):\n"
        "    Path(p).open('w').write('x')\n"   # raw write — must be flagged
        "    Path(p).open('r').read()\n",      # read — must NOT be flagged
        encoding="utf-8",
    )
    hits = _raw_writes_in(probe)
    assert any(".open(..., 'w')" in h for h in hits), "pathlib .open('w') must be detected"
    assert not any("'r'" in h for h in hits), "a read-mode .open must not be flagged"
