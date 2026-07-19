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

# The S4.7 item-2 harness package (tests/harness/) is test-support code, deliberately outside
# src/ (spec §1: the oracle must stay independent of production alignment code); tests/ is not
# itself a package, so its root goes on sys.path for `from harness import ...`.
sys.path.insert(0, str(Path(__file__).resolve().parent))

ENGINE_ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC_INPUTS = ENGINE_ROOT / "books" / "synthetic" / "inputs"

# The synthetic image-only PDF generator (S2.1.2 #36, DT-11) lives under tests/fixtures/. Load it
# by explicit file path rather than putting its dir on sys.path — the dir also holds a `structure/`
# subtree and `_generate_*` scripts, so a bare `sys.path` insert would make `import structure`
# resolvable to the fixtures namespace (a latent shadow of `engine.structure`). Path-loading confines
# the import to this one module and never touches sys.modules under a shadowing name.
_GEOMETRY_PDF_PATH = ENGINE_ROOT / "tests" / "fixtures" / "geometry_pdf.py"
_geometry_pdf_mod = None


def _load_geometry_pdf():
    global _geometry_pdf_mod
    if _geometry_pdf_mod is None:
        import importlib.util

        name = "tests_fixtures_geometry_pdf"  # distinctive: registers safely, shadows nothing
        spec = importlib.util.spec_from_file_location(name, _GEOMETRY_PDF_PATH)
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load the geometry_pdf fixture module from {_GEOMETRY_PDF_PATH}")
        mod = importlib.util.module_from_spec(spec)
        # Register before exec: @dataclass resolves its module via sys.modules[__module__], which is
        # None until the module is registered (fails with AttributeError on a frozen dataclass).
        sys.modules[name] = mod
        try:
            spec.loader.exec_module(mod)
        except BaseException:
            # A failed exec must not be cached as success: the first test would error truthfully,
            # then every later `synth` use would get a half-executed module — an AttributeError far
            # from the real cause. Unregister and leave the cache empty so every call re-raises.
            sys.modules.pop(name, None)
            raise
        _geometry_pdf_mod = mod
    return _geometry_pdf_mod


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


# --- S2.1 geometry seam double ---------------------------------------------------------- #
#
# The injectable ``GeometrySource`` double the seam tests (#35) and the matcher/segmentation
# tiers (#37+) bind to — canned pages, no OCR, no PDF (the same BR-009/D6 injected-backend
# posture as the acquisition doubles above). ``engine_id`` is a free string here; the real
# backend derives it from live library versions + params (#36, DT-2).


class _FakeGeometrySource:
    """Canned ``GeometrySource``: yields the pre-built page for every number in range.

    Strict like ``_FakeFetcher``: an unseeded in-range page raises ``KeyError`` (a real backend
    yields *every* page in range — a blank page is zero words, never a silent skip, DT-2), and a
    duplicate seeded page number is a seeding-time ``ValueError`` (never a quiet last-wins).
    """

    def __init__(self, pages, *, engine_id: str = "fake-geometry-v0") -> None:
        pages = list(pages)
        self._pages = {p.page: p for p in pages}
        if len(self._pages) != len(pages):
            raise ValueError("duplicate page numbers seeded in _FakeGeometrySource")
        self._engine_id = engine_id

    @property
    def engine_id(self) -> str:
        return self._engine_id

    def read_pages(self, first_page: int, last_page: int):
        for n in range(first_page, last_page + 1):
            yield self._pages[n]


@pytest.fixture
def geom():
    """Geometry seam test doubles, as one namespace (the ``acq`` exposure pattern)."""
    return SimpleNamespace(Source=_FakeGeometrySource)


# --- S2.1.3 matcher/sidecar stream + page builders (#37, DT-11 tier 2) ------------------ #
#
# The fake-backend tier's raw material: witness/canonical atom streams built from plain text
# lists (spans + hashes derived, so the streams are store-valid), and PageGeometry pages laid out
# deterministically (or with explicit bboxes for distractor/union fixtures). No OCR, no PDF —
# matcher semantics bind to the seam, never the synthetic-PDF tier (DT-11's claim ladder).


def _mk_witness_stream(texts, *, witness="w-sentinel-3", ids=None):
    from engine.structure.atom_store import AtomStream
    from engine.structure.atoms import Atom, Geom
    from engine.structure.capture import PAGE_UNMAPPED
    from engine.structure.roundtrip import hash_raw
    from engine.structure.roundtrip_gate import gap_records

    ids = ids or [f"{witness}-a{i}" for i in range(len(texts))]
    source = "\n".join(texts)
    atoms = []
    offset = 0
    for aid, text in zip(ids, texts):
        start = source.index(text, offset)
        end = start + len(text)
        atoms.append(
            Atom(
                atom_id=aid,
                text=text,
                raw_span=(start, end),
                raw_source_hash=hash_raw(text),
                page_range=PAGE_UNMAPPED,
                norm_layer="raw",
                geom=Geom.absent(),
                capture_provenance_class="ocr_text",
                witness=witness,
            )
        )
        offset = end
    return AtomStream.witness(witness, atoms, gap_records(atoms, source), source)


def _mk_canonical_stream(entries, *, stream_id="canonical"):
    """``entries`` = (atom_id, text, [(witness, witness_atom_id), ...]) triples."""
    from engine.structure.atom_store import AtomStream
    from engine.structure.atoms import Atom, AtomDerivation, Geom
    from engine.structure.capture import PAGE_UNMAPPED
    from engine.structure.roundtrip import hash_raw

    atoms = []
    offset = 0
    for aid, text, derivs in entries:
        atoms.append(
            Atom(
                atom_id=aid,
                text=text,
                raw_span=(offset, offset + len(text)),
                raw_source_hash=hash_raw(text),
                page_range=PAGE_UNMAPPED,
                norm_layer="raw",
                geom=Geom.absent(),
                capture_provenance_class="reconciled",
                derived_from=tuple(AtomDerivation(witness=w, atom_id=a) for w, a in derivs),
            )
        )
        offset += len(text)
    return AtomStream.canonical(atoms, stream_id=stream_id)


def _mk_page(number, words, *, width=500.0, height=700.0):
    """One ``PageGeometry``: ``words`` entries are plain strings (auto-laid on one row, left to
    right) or ``(text, (x0, y0, x1, y1))`` pairs for explicit placement."""
    from engine.structure.geometry import PageGeometry, WordBox

    boxes = []
    x = 10.0
    for entry in words:
        if isinstance(entry, str):
            box = WordBox(text=entry, bbox=(x, 10.0, x + 8.0 * max(1, len(entry)), 22.0))
            x = box.bbox[2] + 6.0
        else:
            text, bbox = entry
            box = WordBox(text=text, bbox=tuple(bbox))
        boxes.append(box)
    return PageGeometry(page=number, width=width, height=height, words=tuple(boxes))


@pytest.fixture
def matchkit():
    """S2.1.3 builders, as one namespace (the ``acq``/``geom`` exposure pattern)."""
    return SimpleNamespace(
        witness_stream=_mk_witness_stream,
        canonical_stream=_mk_canonical_stream,
        page=_mk_page,
    )


# --- S2.1.2 synthetic image-only PDF fixtures (#36, DT-11 tier 1) ----------------------- #
#
# The real-OCR-path test tier: image-only PDFs (no native text layer) drawn by the generator
# under tests/fixtures/, so the PyMuPDF+Tesseract backend's OCR / coordinate-space / fail-loud
# contracts run against a real Tesseract pass in CI (hard-asserted, no skip-masking — DT-11).
# English drawn text is a fixture asset (the D18 differ-fixture posture), not a core literal:
# the backend OCRs with a language *parameter*.


@pytest.fixture
def synth(tmp_path):
    """Synthetic image-only PDF builders + a tmp-path writer, as one namespace (the ``geom``/``acq``
    exposure pattern). ``synth.pdf(specs, ...)`` writes an image-only PDF into the test's tmp_path
    and returns the ``Path`` the backend opens; the DT-11 page variants
    (``single_column``/``two_column``/``near_blank``/``dark``) and the ``rotated``/``cropped``
    decorators are re-exposed so a test names only the pages it needs."""
    g = _load_geometry_pdf()

    def pdf(specs, *, render_dpi: int = 200, name: str = "synth.pdf") -> Path:
        return g.write_image_only_pdf(tmp_path / name, list(specs), render_dpi=render_dpi)

    return SimpleNamespace(
        pdf=pdf,
        render_bytes=g.render_image_only_pdf,
        single_column=g.single_column_page,
        two_column=g.two_column_page,
        near_blank=g.near_blank_page,
        dark=g.dark_page,
        rotated=g.rotated,
        cropped=g.cropped,
        PageSpec=g.PageSpec,
        Line=g.Line,
    )
