"""``BookWorkspace`` — every generated artifact lives under ``books/<id>/work/``.

This is the isolation primitive the whole forward-fork rests on (plan §"Keeping the live
edition safe"): the engine must never write into the parent repo's live tree (``data/``,
``output/``, ``state/``, …) at the repo root. A step asks the workspace for an output path via
``resolve``, which *asserts the path stays inside the work tree* and raises on any escape
(``..`` traversal or an absolute path). The three areas mirror the live pipeline's
``DATA_DIR``/``OUTPUT_DIR``/``STATE_DIR`` seam (``pipeline.py:12-15``), now per-book and
sandboxed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .errors import MissingInputError

# paths.py -> engine(pkg) -> src -> engine/ (project root)
ENGINE_ROOT = Path(__file__).resolve().parents[2]

#: Root for read-only heavy assets. During dev these are symlinks into the live tree
#: (``assets/dictionary`` → period dicts, ``assets/frequency`` → the frequency dict,
#: ``assets/fonts`` → OFL fonts); at extraction they become real copies. Resolving every
#: asset path through here keeps symlink-vs-copy invisible to step code (plan §"Heavy assets").
ASSETS_ROOT = ENGINE_ROOT / "assets"


def asset_path(rel: str) -> Path:
    """Resolve an assets-relative path (e.g. ``"frequency/it_combined.txt"``) to absolute.

    Does not assert existence — callers that require the file present use ``require_asset``
    (and ``tests/unit/test_assets.py`` asserts every config-referenced asset resolves).
    """
    return ASSETS_ROOT / rel


def require_asset(rel: str, *, kind: str = "file") -> Path:
    """Resolve an assets-relative path and assert it exists, else raise ``MissingInputError``.

    The typed counterpart to ``asset_path`` for callers that *need* the asset present. A
    config that names a missing/typo'd dictionary or dir is a known, user-facing failure, so
    it exits cleanly (``MissingInputError``, code 3) naming the offending path — not a bare
    ``FileNotFoundError`` traceback from deep in a loader (invariant I1; plan F7). ``kind`` is
    ``"file"`` or ``"dir"``, and the check matches the kind so a file where a dir is expected
    (or vice versa) is caught rather than passing silently.
    """
    path = asset_path(rel)
    present = path.is_dir() if kind == "dir" else path.is_file()
    if not present:
        raise MissingInputError(f"required {kind} asset not found: {rel!r} (resolved to {path})")
    return path


_AREAS = ("data", "output", "state")


@dataclass(frozen=True, slots=True)
class BookWorkspace:
    book_id: str
    root: Path  # books/<id>/work

    @classmethod
    def for_book(cls, book_id: str, books_dir: Path) -> BookWorkspace:
        return cls(book_id=book_id, root=(Path(books_dir) / book_id / "work").resolve())

    @property
    def data(self) -> Path:
        return self.root / "data"

    @property
    def output(self) -> Path:
        return self.root / "output"

    @property
    def state(self) -> Path:
        return self.root / "state"

    @property
    def scans(self) -> Path:
        """Per-book source scans (``books/<id>/scans/``) — the large PDFs ``ocr`` renders (D7).

        A read-only *input* sibling of the ``work`` tree (gitignored), distinct from the frozen
        ``inputs/`` fixtures. It sits outside the write-sandbox by design: ``ocr`` only *reads* the
        PDF, and a book supplies it out-of-band, so it is never produced into ``work``. Reading it
        needs no containment check (``resolve`` guards *writes*); a missing PDF is a clean
        ``MissingInputError`` raised by ``ocr``, not a path-escape.
        """
        return self.root.parent / "scans"

    def ensure(self) -> BookWorkspace:
        """Create the work tree (the three areas). Idempotent."""
        for area in _AREAS:
            (self.root / area).mkdir(parents=True, exist_ok=True)
        return self

    def _contained(self, base: Path, parts: tuple[str, ...]) -> Path:
        """Join ``parts`` onto ``base`` and assert the result stays inside the work tree.

        The single containment chokepoint behind ``resolve``/``resolve_root`` — the assertion
        that makes the live tree unreachable lives here and *only* here, so it cannot be hardened
        in one resolver and missed in the other. ``base`` is itself always inside ``root``.
        Raises ``ValueError`` on an absolute part or any ``..`` traversal that escapes ``root``.
        """
        if any(Path(p).is_absolute() for p in parts):
            raise ValueError(f"workspace path parts must be relative, got {parts!r}")

        candidate = base.joinpath(*parts).resolve()
        # is_relative_to is reflexive (root is relative to itself), so this already permits the
        # no-parts resolve_root() == root case without a separate `candidate != self.root` clause.
        if not candidate.is_relative_to(self.root):
            raise ValueError(
                f"path {candidate} escapes workspace {self.root} (rejected)"
            )
        return candidate

    def resolve(self, area: str, *parts: str) -> Path:
        """Resolve ``<work>/<area>/<*parts>``, guaranteeing the result stays in the work tree.

        Raises ``ValueError`` for an unknown area, an absolute part, or any ``..`` traversal
        that would escape ``root`` — the assertion that makes the live tree unreachable.
        """
        if area not in _AREAS:
            raise ValueError(f"unknown workspace area {area!r}; expected one of {_AREAS}")
        return self._contained(self.root / area, parts)

    def resolve_root(self, *parts: str) -> Path:
        """Resolve ``<work>/<*parts>`` at the work-tree **root**, with the same escape guard.

        The area-less counterpart to ``resolve``, for the few artifacts pinned at the work root
        rather than under ``data``/``output``/``state`` (e.g. the structure substrate's durable
        ``structure_map.json`` and ``relations.json`` — ENGINE_STRUCTURE_PLAN §11.2/§11.3). Same
        containment contract via the shared ``_contained`` guard: an absolute part, or a ``..``
        traversal that would escape ``root``, raises ``ValueError`` — the live tree stays
        unreachable through this resolver too.
        """
        return self._contained(self.root, parts)
