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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
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
