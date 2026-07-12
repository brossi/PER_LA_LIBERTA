"""Orchestrator CLI — the engine's replacement for the top-level ``pipeline.py``.

Responsibilities (built out across milestones):
  1. parse args (``--book``, ``--step``, step options);
  2. resolve the book → ``ResolvedConfig`` + ``LanguagePlugin`` (M1);
  3. derive an isolated ``BookWorkspace`` under ``books/<id>/work/`` (M1);
  4. dispatch to ``engine.steps.<step>.run(ws, cfg, lang, **opts)``.

The four responsibilities above are wired (book resolution + workspace derivation
landed in M1). Each step is dispatched as it is ported; an unported step's ``run``
raises ``NotImplementedError`` (surfaced as exit 2), naming the milestone that ports it.
"""

from __future__ import annotations

import argparse
import importlib
import inspect
import json
import sys
import time
from pathlib import Path

from engine import STEPS
from engine.config.loader import ConfigError, load_book
from engine.errors import EngineError
from engine.lang.registry import UnknownLanguageError, get_language_plugin
from engine.paths import BookWorkspace
from engine.progress import PipelineTracker, pipeline_snapshot, render_snapshot

PACKAGE_ROOT = Path(__file__).resolve().parent
ENGINE_ROOT = PACKAGE_ROOT.parents[1]  # engine/ (src/engine/cli.py -> engine/)
BOOKS_DIR = ENGINE_ROOT / "books"


def _available_books() -> list[str]:
    """Book ids are the directory names under engine/books/ holding a manifest."""
    if not BOOKS_DIR.is_dir():
        return []
    return sorted(
        p.name for p in BOOKS_DIR.iterdir() if (p / "manifest.json").is_file()
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="engine",
        description="Book/language-agnostic OCR → translate → typeset framework.",
    )
    # --book has no default (the engine is book-agnostic — no "primary" book to bake, and at
    # extraction there is none to point at). It is deliberately NOT argparse `required=True`:
    # that would force --book onto `--list-books` too, but discovery must work without a book id.
    # So it stays optional at parse time and `main()` enforces it only when a step actually runs.
    # (Do not "tidy" this to required=True — it would break `--list-books`.)
    parser.add_argument(
        "--book",
        default=None,
        help="Book id under engine/books/ (required to run a step; see --list-books).",
    )
    parser.add_argument(
        "--step",
        choices=(*STEPS, "all"),
        help="Pipeline step to run (or 'all' for the full build subset).",
    )
    parser.add_argument(
        "--list-books",
        action="store_true",
        help="List the configured books and exit.",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show persisted and artifact-derived progress for a book without running a step.",
    )
    parser.add_argument(
        "--watch",
        nargs="?",
        type=float,
        const=2.0,
        default=None,
        metavar="SECONDS",
        help="Refresh --status continuously (default interval: 2 seconds).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Emit --status as JSON.",
    )
    # Step options (F7) — threaded into each step's run() filtered by signature, so a step that
    # does not declare an option simply never receives it. Defaults are None: an unset option is
    # omitted entirely, leaving the step's own default in force.
    parser.add_argument(
        "--model", choices=("flash", "pro"), default=None,
        help="OCR model role (ocr): 'flash' (page mapping) or 'pro' (quality witness).",
    )
    parser.add_argument(
        "--workers", type=int, default=None,
        help="Concurrent workers (ocr/translate).",
    )
    parser.add_argument(
        "--pages", nargs=2, type=int, metavar=("START", "END"), default=None,
        help="Inclusive 1-indexed page range (ocr).",
    )
    parser.add_argument(
        "--api-key", default=None,
        help="Backend API key (ocr); falls back to the backend's env var.",
    )
    return parser


def _collect_step_opts(args: argparse.Namespace) -> dict:
    """Gather the step options the user actually set (unset → omitted, so step defaults stand)."""
    opts: dict = {}
    if args.model is not None:
        opts["model"] = args.model
    if args.workers is not None:
        opts["workers"] = args.workers
    if args.pages is not None:
        opts["pages"] = tuple(args.pages)
    if args.api_key is not None:
        opts["api_key"] = args.api_key
    return opts


def _accepted_opts(run_func, opts: dict) -> dict:
    """Subset of ``opts`` the step's ``run`` accepts — by name, or all if it takes ``**kwargs``."""
    params = inspect.signature(run_func).parameters
    if any(p.kind is p.VAR_KEYWORD for p in params.values()):
        return dict(opts)
    return {k: v for k, v in opts.items() if k in params}


def _run_step(step: str, book: str, opts: dict | None = None) -> int:
    """Resolve the book, then dispatch to the named step module with its accepted options.

    M1 wires real resolution: the book's manifest + profiles become a ``ResolvedConfig``,
    its language id selects the ``LanguagePlugin``, and an isolated ``BookWorkspace`` is
    derived. Step options (F7) are threaded through ``run(*, ws, cfg, lang, **accepted)``,
    filtered to what each step declares. Unported steps still raise ``NotImplementedError``
    (exit 2); a typed ``EngineError`` maps to its own exit code.
    """
    try:
        cfg = load_book(book, books_dir=BOOKS_DIR)
        lang = get_language_plugin(cfg.language_id)
    except (ConfigError, UnknownLanguageError) as exc:
        print(f"engine: {exc}", file=sys.stderr)
        return 1

    workspace = BookWorkspace.for_book(book, BOOKS_DIR)
    tracker = PipelineTracker(workspace)

    module = importlib.import_module(f"engine.steps.{step}")
    accepted = _accepted_opts(module.run, opts or {})
    tracker.start_step(step)
    try:
        summary = module.run(workspace=workspace, cfg=cfg, lang=lang, **accepted)
    except NotImplementedError as exc:
        tracker.fail_step(step, str(exc))
        print(f"engine: {exc}", file=sys.stderr)
        return 2
    except EngineError as exc:
        tracker.fail_step(step, str(exc))
        print(f"engine: {exc}", file=sys.stderr)
        return exc.exit_code
    except Exception as exc:
        tracker.fail_step(step, f"{type(exc).__name__}: {exc}")
        raise
    tracker.complete_step(step, summary if isinstance(summary, dict) else {})
    return 0


def _show_status(book: str, *, watch: float | None, json_output: bool) -> int:
    try:
        cfg = load_book(book, books_dir=BOOKS_DIR)
    except ConfigError as exc:
        print(f"engine: {exc}", file=sys.stderr)
        return 1
    workspace = BookWorkspace.for_book(book, BOOKS_DIR)
    interval = max(watch or 0, 0.2)
    try:
        while True:
            snapshot = pipeline_snapshot(workspace, cfg)
            output = json.dumps(snapshot, indent=2, ensure_ascii=False) if json_output else render_snapshot(snapshot)
            if watch is not None and not json_output:
                print("\033[2J\033[H", end="")
            print(output, flush=True)
            if watch is None:
                return 0
            time.sleep(interval)
    except KeyboardInterrupt:
        return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.list_books:
        for book in _available_books():
            print(book)
        return 0

    if args.status:
        if not args.book:
            print("engine: --book is required with --status.", file=sys.stderr)
            return 1
        return _show_status(args.book, watch=args.watch, json_output=args.json_output)

    if args.watch is not None or args.json_output:
        print("engine: --watch/--json require --status.", file=sys.stderr)
        return 1

    if not args.step:
        print("engine: nothing to do (pass --step or --list-books).", file=sys.stderr)
        return 1

    # No book is baked as the default (the engine is book-agnostic): running a step needs an
    # explicit --book. (--list-books, handled above, deliberately needs none.)
    if not args.book:
        print("engine: --book is required to run a step (see --list-books).", file=sys.stderr)
        return 1

    opts = _collect_step_opts(args)
    steps = list(STEPS) if args.step == "all" else [args.step]
    rc = 0
    for step in steps:
        rc = _run_step(step, args.book, opts) or rc
    return rc


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
