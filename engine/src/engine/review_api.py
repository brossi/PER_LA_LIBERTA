"""Machine-facing bridge for external review clients."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from engine.config.loader import ConfigError, load_book
from engine.errors import EngineError
from engine.paths import BookWorkspace
from engine.structure.page_evidence import record_page_verdict
from engine.structure.structure_review import (
    build_structure_review_packet,
    record_structure_evidence,
)

ENGINE_ROOT = Path(__file__).resolve().parents[2]
BOOKS_DIR = ENGINE_ROOT / "books"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m engine.review_api")
    subparsers = parser.add_subparsers(dest="command", required=True)
    record = subparsers.add_parser("record-page-verdict")
    record.add_argument("--book", required=True)
    record.add_argument("--witness-id", default="copy1")
    record.add_argument("--model", default="flash")
    record.add_argument("--page", required=True, type=int)
    record.add_argument(
        "--disposition", required=True, choices=("content", "blank", "non_text")
    )
    record.add_argument("--evidence-sha256", required=True)
    record.add_argument("--reviewer", required=True)
    record.add_argument("--note", default=None)
    record.add_argument("--max-review-pages", type=int, default=25)
    packet = subparsers.add_parser("structure-packet")
    packet.add_argument("--book", required=True)
    packet.add_argument("--books-dir", type=Path, default=BOOKS_DIR)
    packet.add_argument("--asset-root", type=Path, default=ENGINE_ROOT.parent)
    structure_write = subparsers.add_parser("record-structure-evidence")
    structure_write.add_argument("--book", required=True)
    structure_write.add_argument("--books-dir", type=Path, default=BOOKS_DIR)
    structure_write.add_argument("--asset-root", type=Path, default=ENGINE_ROOT.parent)
    structure_write.add_argument("--node", required=True)
    structure_write.add_argument("--review-fingerprint", required=True)
    structure_write.add_argument("--evidence", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "structure-packet":
            result = build_structure_review_packet(
                args.books_dir / args.book, asset_root=args.asset_root
            )
        elif args.command == "record-structure-evidence":
            result = record_structure_evidence(
                args.books_dir / args.book,
                node_id=args.node,
                review_fingerprint=args.review_fingerprint,
                evidence=args.evidence,
                asset_root=args.asset_root,
            )
        else:
            cfg = load_book(args.book, books_dir=BOOKS_DIR)
            result = record_page_verdict(
                workspace=BookWorkspace.for_book(args.book, BOOKS_DIR),
                cfg=cfg,
                witness_id=args.witness_id,
                model=args.model,
                page=args.page,
                disposition=args.disposition,
                evidence_sha256=args.evidence_sha256,
                reviewer=args.reviewer,
                note=args.note,
                max_review_pages=args.max_review_pages,
            )
    except ConfigError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except EngineError as exc:
        print(str(exc), file=sys.stderr)
        return exc.exit_code
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
