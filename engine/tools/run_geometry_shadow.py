"""Restartable per-book geometry + observation-only layout assessment runner."""

from __future__ import annotations

import argparse
import hashlib
from collections import Counter
from pathlib import Path

import fitz

from engine.config.loader import load_book
from engine.paths import BookWorkspace
from engine.structure.geometry import PageGeometry, WordBox
from engine.structure.geometry_pymupdf import PyMuPDFTesseractBackend
from engine.structure.layout_assessment_shadow import (
    MODE_SHADOW,
    STATUS_AVAILABLE,
    observe_page_geometry,
)
from engine.util.jsonio import atomic_write_json, read_json

ENGINE_ROOT = Path(__file__).resolve().parents[1]
BOOKS_DIR = ENGINE_ROOT / "books"
GEOMETRY_SCHEMA_VERSION = 1
GEOMETRY_STALE_CLASS = "layout-shadow-page-geometry"
REPORT_SCHEMA_VERSION = 1
REPORT_STALE_CLASS = "layout-assessment-shadow-run"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _pinned_digest(book_dir: Path, relative_path: str) -> str:
    matches = []
    for line in (book_dir / "resources.sha256").read_text(encoding="utf-8").splitlines():
        digest, separator, name = line.partition("  ")
        if separator and name == relative_path:
            matches.append(digest)
    if len(matches) != 1 or len(matches[0]) != 64:
        raise ValueError(f"expected one valid SHA-256 pin for {relative_path!r}, got {matches}")
    return matches[0]


def _checkpoint_path(workspace: BookWorkspace, witness_id: str, page: int) -> Path:
    return workspace.resolve(
        "data", "geometry", "shadow", witness_id, f"page_{page:04d}.json"
    )


def _checkpoint_envelope(
    *,
    source_ref: str,
    source_sha256: str,
    engine_id: str,
    backend_params: dict[str, object],
    page_geometry: PageGeometry,
    dropped_boxes: int,
    oob_boxes: int,
) -> dict:
    return {
        "schema_version": GEOMETRY_SCHEMA_VERSION,
        "stale_class": GEOMETRY_STALE_CLASS,
        "source_ref": source_ref,
        "source_sha256": source_sha256,
        "geometry_engine_id": engine_id,
        "backend_params": backend_params,
        "page": page_geometry.page,
        "dropped_boxes": dropped_boxes,
        "oob_boxes": oob_boxes,
        "geometry": {
            "width": page_geometry.width,
            "height": page_geometry.height,
            "words": [
                {"text": word.text, "bbox": list(word.bbox)}
                for word in page_geometry.words
            ],
        },
    }


def _load_checkpoint(path: Path, expected: dict[str, object]) -> tuple[PageGeometry, int, int] | None:
    if not path.is_file():
        return None
    try:
        record = read_json(path)
        if not isinstance(record, dict):
            return None
        for key, value in expected.items():
            if record.get(key) != value:
                return None
        if (
            record.get("schema_version") != GEOMETRY_SCHEMA_VERSION
            or record.get("stale_class") != GEOMETRY_STALE_CLASS
            or type(record.get("dropped_boxes")) is not int
            or type(record.get("oob_boxes")) is not int
            or not isinstance(record.get("geometry"), dict)
        ):
            return None
        geometry = record["geometry"]
        words = tuple(
            WordBox(text=item["text"], bbox=tuple(item["bbox"]))
            for item in geometry["words"]
        )
        page_geometry = PageGeometry(
            page=record["page"],
            width=geometry["width"],
            height=geometry["height"],
            words=words,
        )
        return page_geometry, record["dropped_boxes"], record["oob_boxes"]
    except (OSError, UnicodeError, ValueError, TypeError, KeyError, RecursionError):
        return None


def _write_report(
    *,
    book_id: str,
    workspace: BookWorkspace,
    witness_id: str,
    status: str,
    source: dict,
    engine_id: str,
    backend_params: dict[str, object],
    page_records: list[dict],
    available_pages: list[int],
    unavailable_pages: list[int],
    result_counts: Counter,
    failed_page: int | None = None,
    failure_type: str | None = None,
) -> Path:
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "stale_class": REPORT_STALE_CLASS,
        "status": status,
        "book_id": book_id,
        "witness_id": witness_id,
        "source": source,
        "geometry": {
            "engine_id": engine_id,
            "backend_params": backend_params,
            "page_count": len(page_records),
            "word_count": sum(item["word_count"] for item in page_records),
            "dropped_box_count": sum(item["dropped_boxes"] for item in page_records),
            "oob_box_count": sum(item["oob_boxes"] for item in page_records),
            "page_artifacts": page_records,
        },
        "assessment": {
            "mode": MODE_SHADOW,
            "column_policy": None,
            "density_evidence": None,
            "available_pages": sorted(available_pages),
            "unavailable_pages": sorted(unavailable_pages),
            "result_counts": [
                {
                    "module_id": key[0],
                    "capability": key[1],
                    "execution_status": key[2],
                    "assessment": key[3],
                    "count": count,
                }
                for key, count in sorted(result_counts.items())
            ],
        },
        "failure": (
            {"page": failed_page, "type": failure_type}
            if failed_page is not None
            else None
        ),
    }
    path = workspace.resolve("data", "layout_assessment", witness_id, "run_report.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(path, report)
    return path


def run(args: argparse.Namespace) -> Path:
    cfg = load_book(args.book, books_dir=BOOKS_DIR)
    workspace = BookWorkspace.for_book(args.book, BOOKS_DIR).ensure()
    book_dir = BOOKS_DIR / args.book
    pdf_path = workspace.scans / cfg.manifest.scan.pdf
    source_relative = f"scans/{cfg.manifest.scan.pdf}"
    source_ref = f"scan:{args.book}/{cfg.manifest.scan.pdf}"
    actual_sha256 = _sha256_file(pdf_path)
    pinned_sha256 = _pinned_digest(book_dir, source_relative)
    if actual_sha256 != pinned_sha256:
        raise ValueError(
            f"scan SHA-256 differs from resources.sha256: {actual_sha256} != {pinned_sha256}"
        )

    with fitz.open(pdf_path) as document:
        page_count = document.page_count
        rotated = [page.number + 1 for page in document if page.rotation != 0]
    if page_count != cfg.manifest.scan.last_scan_page_default:
        raise ValueError(
            f"scan page count {page_count} != manifest {cfg.manifest.scan.last_scan_page_default}"
        )
    if rotated:
        raise ValueError(f"rotated scan pages are unsupported: {rotated}")

    backend = PyMuPDFTesseractBackend(
        pdf_path, language=args.tesseract_language, dpi=args.dpi
    )
    engine_id = backend.engine_id
    backend_params = backend.backend_params
    source = {
        "ref": source_ref,
        "sha256": actual_sha256,
        "bytes": pdf_path.stat().st_size,
        "pages": page_count,
    }
    page_records: list[dict] = []
    available_pages: list[int] = []
    unavailable_pages: list[int] = []
    result_counts: Counter = Counter()

    for page_number in range(1, page_count + 1):
        checkpoint = _checkpoint_path(workspace, args.witness_id, page_number)
        expected = {
            "source_ref": source_ref,
            "source_sha256": actual_sha256,
            "geometry_engine_id": engine_id,
            "backend_params": backend_params,
            "page": page_number,
        }
        cached = None if args.refresh_geometry else _load_checkpoint(checkpoint, expected)
        try:
            if cached is None:
                page_geometry = next(backend.read_pages(page_number, page_number))
                dropped = backend.dropped_boxes.get(page_number, 0)
                oob = backend.oob_boxes.get(page_number, 0)
                checkpoint.parent.mkdir(parents=True, exist_ok=True)
                atomic_write_json(
                    checkpoint,
                    _checkpoint_envelope(
                        source_ref=source_ref,
                        source_sha256=actual_sha256,
                        engine_id=engine_id,
                        backend_params=backend_params,
                        page_geometry=page_geometry,
                        dropped_boxes=dropped,
                        oob_boxes=oob,
                    ),
                )
            else:
                page_geometry, dropped, oob = cached

            observation = observe_page_geometry(
                workspace=workspace,
                mode=MODE_SHADOW,
                witness_id=args.witness_id,
                source_ref=source_ref,
                source_sha256=actual_sha256,
                page_geometry=page_geometry,
                geometry_engine_id=engine_id,
                column_policy=None,
                refresh=args.refresh_shadow,
            )
            if observation.status == STATUS_AVAILABLE:
                available_pages.append(page_number)
                for item in observation.bundle.results:
                    result_counts[
                        (
                            item.module_id,
                            item.capability,
                            item.execution_status,
                            item.assessment,
                        )
                    ] += 1
            else:
                unavailable_pages.append(page_number)

            page_records.append(
                {
                    "page": page_number,
                    "word_count": len(page_geometry.words),
                    "dropped_boxes": dropped,
                    "oob_boxes": oob,
                    "geometry_path": str(checkpoint.relative_to(workspace.root)),
                    "geometry_sha256": _sha256_file(checkpoint),
                    "assessment_path": (
                        str(observation.path.relative_to(workspace.root))
                        if observation.path is not None
                        else None
                    ),
                    "assessment_sha256": (
                        _sha256_file(observation.path)
                        if observation.path is not None
                        else None
                    ),
                }
            )
            print(
                f"page {page_number:04d}/{page_count}: {len(page_geometry.words)} boxes, "
                f"assessment={observation.status}",
                flush=True,
            )
        except Exception as exc:
            _write_report(
                book_id=args.book,
                workspace=workspace,
                witness_id=args.witness_id,
                status="geometry_failed",
                source=source,
                engine_id=engine_id,
                backend_params=backend_params,
                page_records=page_records,
                available_pages=available_pages,
                unavailable_pages=unavailable_pages,
                result_counts=result_counts,
                failed_page=page_number,
                failure_type=type(exc).__name__,
            )
            raise

    return _write_report(
        book_id=args.book,
        workspace=workspace,
        witness_id=args.witness_id,
        status=("complete_with_unavailable" if unavailable_pages else "complete"),
        source=source,
        engine_id=engine_id,
        backend_params=backend_params,
        page_records=page_records,
        available_pages=available_pages,
        unavailable_pages=unavailable_pages,
        result_counts=result_counts,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--book", required=True)
    parser.add_argument("--tesseract-language", required=True)
    parser.add_argument("--dpi", required=True, type=int)
    parser.add_argument("--witness-id", required=True)
    parser.add_argument("--refresh-geometry", action="store_true")
    parser.add_argument("--refresh-shadow", action="store_true")
    return parser


if __name__ == "__main__":
    report_path = run(build_parser().parse_args())
    print(f"report: {report_path}")
