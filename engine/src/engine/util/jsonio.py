"""Atomic file I/O — ported from utils.atomic_write_json (utils.py:332-341).

The atomic write (temp file + os.replace) is how every sidecar in the pipeline is
written; reproducing it byte-for-byte keeps the engine's outputs diffable against the
committed live artifacts (indent=2, ensure_ascii=False). Atomicity is also the load-bearing
assumption under invariant I8 / the I2 residual: a *present* artifact is never half-written, so
a sibling step that reads it may treat a parse failure as bug-class. Every artifact a later
step consumes must therefore be written through one of these helpers — the JSON sidecars via
``atomic_write_json``, the plain-text witnesses (OCR copies, stitched text) via
``atomic_write_text`` — never a raw ``Path.write_text``/``open(...)`` (enforced by
``tests/unit/test_atomic_writes.py``).
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


def read_json(path: Path):
    """Load JSON from ``path`` (UTF-8)."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _atomic_write(path: Path, render) -> None:
    """Write whatever ``render(file_handle)`` emits atomically: temp file in the same dir,
    then ``os.replace`` (atomic on POSIX). On any failure the temp file is removed, so a crash
    never leaves a half-written artifact at ``path``."""
    path = Path(path)
    tmp_fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            render(f)
        os.replace(tmp_path, path)
    except BaseException:
        os.unlink(tmp_path)
        raise


def atomic_write_json(path: Path, data: dict | list) -> None:
    """Write JSON atomically: temp file in the same dir, then os.replace.

    ``allow_nan=False`` so a non-finite float (``NaN`` / ``±inf``) fails **loud** at write rather than
    emitting the bare ``NaN``/``Infinity`` tokens (which are not RFC-8259 JSON — a strict or
    cross-language reader rejects the whole file, and ``NaN`` silently breaks every ``==`` round-trip
    check since ``NaN != NaN``). A finite-float producer is unaffected.
    """
    _atomic_write(path, lambda f: json.dump(data, f, indent=2, ensure_ascii=False, allow_nan=False))


def atomic_write_text(path: Path, text: str) -> None:
    """Write plain UTF-8 text atomically — the text sibling of ``atomic_write_json``.

    For the artifacts that are text, not JSON (the downloaded OCR witnesses, ocr's stitched
    copy3 text, reconcile's human-readable dump). A raw ``Path.write_text`` here would leave a
    truncated file on a mid-write crash that a later step reads as complete (invariant I8).
    """
    _atomic_write(path, lambda f: f.write(text))


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Write a binary artifact atomically.

    Raster checkpoints use this sibling of :func:`atomic_write_text`; a PNG must never become
    visible at its final path until every byte has been written successfully.
    """
    path = Path(path)
    tmp_fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "wb") as handle:
            handle.write(data)
        os.replace(tmp_path, path)
    except BaseException:
        os.unlink(tmp_path)
        raise
