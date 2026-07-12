"""Repair per-book Gemini recitation-filter pages with an explicit Tesseract fallback."""

from __future__ import annotations

import argparse
import hashlib
import subprocess
from pathlib import Path

from engine.config.loader import load_book
from engine.contracts.markers import SENTINEL_OCR_ERROR_PREFIX
from engine.paths import BookWorkspace
from engine.steps.ocr import FitzPageRenderer
from engine.util.jsonio import atomic_write_json, read_json

ENGINE_ROOT = Path(__file__).resolve().parents[1]
BOOKS_DIR = ENGINE_ROOT / "books"


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def run(args: argparse.Namespace) -> Path:
    cfg = load_book(args.book, books_dir=BOOKS_DIR)
    workspace = BookWorkspace.for_book(args.book, BOOKS_DIR).ensure()
    pdf_path = workspace.scans / cfg.manifest.scan.pdf
    source_sha256 = _sha256_file(pdf_path)
    renderer = FitzPageRenderer()
    version = subprocess.run(
        ["tesseract", "--version"], capture_output=True, text=True, check=True
    ).stdout.splitlines()[0]
    progress_dir = workspace.resolve("state", f"ocr_{args.model_role}_pages")
    records = []

    for page in sorted(set(args.pages)):
        checkpoint = progress_dir / f"page_{page:04d}.json"
        current = read_json(checkpoint)
        current_text = current.get("text") if isinstance(current, dict) else None
        if not args.force and (
            not isinstance(current_text, str)
            or not current_text.startswith(SENTINEL_OCR_ERROR_PREFIX)
        ):
            raise ValueError(
                f"page {page} is not an OCR-error checkpoint; refusing fallback overwrite"
            )

        image = renderer.render(pdf_path, page, dpi=args.dpi)
        command = [
            "tesseract",
            "stdin",
            "stdout",
            "-l",
            args.tesseract_language,
            "--psm",
            "3",
        ]
        if args.thresholding_method is not None:
            command.extend(["-c", f"thresholding_method={args.thresholding_method}"])
        process = subprocess.run(
            command,
            input=image,
            capture_output=True,
            check=True,
        )
        text = process.stdout.decode("utf-8").strip()
        if not text:
            raise ValueError(f"Tesseract fallback returned empty text for page {page}")
        provenance = {
            "kind": "explicit_recitation_fallback",
            "source_sha256": source_sha256,
            "backend": version,
            "language": args.tesseract_language,
            "dpi": args.dpi,
            "psm": 3,
            "thresholding_method": args.thresholding_method,
            "image_sha256": _sha256_bytes(image),
            "text_sha256": _sha256_bytes(text.encode("utf-8")),
        }
        atomic_write_json(
            checkpoint,
            {"page": page, "text": text, "provenance": provenance},
        )
        records.append({"page": page, **provenance})
        print(f"page {page}: Tesseract fallback ({len(text):,} chars)")

    report = {
        "schema_version": 1,
        "stale_class": "ocr-recitation-fallbacks",
        "book_id": args.book,
        "model_role": args.model_role,
        "source_sha256": source_sha256,
        "pages": records,
    }
    report_path = workspace.resolve("state", f"ocr_{args.model_role}_fallbacks.json")
    atomic_write_json(report_path, report)
    return report_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--book", required=True)
    parser.add_argument("--model-role", choices=("flash", "pro"), required=True)
    parser.add_argument("--pages", nargs="+", type=int, required=True)
    parser.add_argument("--tesseract-language", required=True)
    parser.add_argument("--dpi", type=int, required=True)
    parser.add_argument("--thresholding-method", type=int, choices=(0, 1, 2))
    parser.add_argument("--force", action="store_true")
    return parser


if __name__ == "__main__":
    path = run(build_parser().parse_args())
    print(f"report: {path}")
