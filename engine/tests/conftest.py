"""Shared pytest fixtures for the engine test suite."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

# Stale-.pyc discipline (s4_plan §4.1.x / X13, feedback_mutation_pyc_staleness): mutation hunts run
# sub-second patch→test→revert cycles that defeat CPython's second-granularity .pyc mtime check —
# a stale cache serves pre-mutation bytecode and turns a caught mutant into a false GREEN. Pinning
# dont_write_bytecode here wires the discipline into every pytest run (conftest imports before the
# SUT), instead of trusting each harness to remember PYTHONDONTWRITEBYTECODE=1.
sys.dont_write_bytecode = True

ENGINE_ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC_INPUTS = ENGINE_ROOT / "books" / "synthetic" / "inputs"


@pytest.fixture
def engine_root() -> Path:
    """Absolute path to the engine/ package root (parent of src/, books/, profiles/)."""
    return ENGINE_ROOT


# --- M4a acquisition test doubles ------------------------------------------------------- #
#
# download/ocr are non-deterministic (network / vision model), so their property + separability
# tiers run against injected backends seeded from the frozen synthetic ``inputs/`` (BR-009/D6).
# The page identity is threaded renderer→backend through the rendered bytes (the FakeRenderer
# encodes the page number; the FakeBackend reads it back) so canned responses stay order- and
# resume-independent — there is no reliance on call order.


def _split_pages_by_marker(text: str) -> dict[int, str]:
    """Split marker-delimited OCR text into ``{page_number: body}`` (markers stripped)."""
    from engine.contracts.markers import PAGE_MARKER_RE

    pages: dict[int, str] = {}
    current: int | None = None
    buf: list[str] = []
    for line in text.split("\n"):
        m = PAGE_MARKER_RE.match(line.strip())
        if m:
            if current is not None:
                pages[current] = "\n".join(buf).strip()
            current = int(m.group(1))
            buf = []
        else:
            buf.append(line)
    if current is not None:
        pages[current] = "\n".join(buf).strip()
    return pages


class _FakeFetcher:
    """``download.Fetcher`` double: returns canned text keyed by URL (KeyError on an unseeded URL,
    which is itself a useful assertion that download computed the URL we expected)."""

    def __init__(self, url_to_text: dict[str, str]) -> None:
        self._map = url_to_text

    def fetch(self, url: str) -> str:
        return self._map[url]


class _FakePageRenderer:
    """``ocr.PageRenderer`` double: needs no PDF. Renders the page number as bytes — the page
    identity the ``_FakeOcrBackend`` reads back."""

    def __init__(self, page_count: int) -> None:
        self._n = page_count

    def page_count(self, pdf_path) -> int:
        return self._n

    def render(self, pdf_path, page: int, *, dpi: int) -> bytes:
        return str(page).encode()


class _FakeOcrBackend:
    """``ocr.OcrBackend`` double: returns canned per-page text keyed by the page number encoded in
    the rendered bytes."""

    def __init__(self, page_texts: dict[int, str]) -> None:
        self._texts = page_texts

    def transcribe(self, image_bytes: bytes, prompt: str) -> str:
        return self._texts[int(image_bytes.decode())]


@pytest.fixture
def acq():
    """Acquisition test doubles + the frozen synthetic inputs dir, as one namespace."""
    return SimpleNamespace(
        Fetcher=_FakeFetcher,
        Renderer=_FakePageRenderer,
        Backend=_FakeOcrBackend,
        split=_split_pages_by_marker,
        inputs=SYNTHETIC_INPUTS,
    )
