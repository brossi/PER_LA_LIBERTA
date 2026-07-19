"""S4.6c/#90 — source-locked PLL instance of the generalized advisory observer.

The reusable mechanism lives in :mod:`engine.structure.structural_contents`.  This book-side runner
supplies declared part names from ``manifest.json`` and four pinned OCR representations.  It never
loads or writes the structure map or authoring-evidence sidecar.

Usage from ``engine/``::

    uv run python books/per_la_liberta/observe_structural_contents.py
"""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from engine.errors import AcquisitionError, MissingInputError, StaleArtifactError
from engine.structure.structural_contents import (
    SOURCE_FORMATS,
    SourceSpec,
    StructuralExpectation,
    load_source_bytes,
    observe_structural_contents,
    write_structural_contents_report,
)
from engine.util.jsonio import read_json

BOOK_DIR = Path(__file__).resolve().parent
BOOK_ID = "per_la_liberta"
CONFIG_PATH = BOOK_DIR / "structural_contents_sources.json"
MANIFEST_PATH = BOOK_DIR / "manifest.json"
OUTPUT_PATH = BOOK_DIR / "work" / "structure_observations.json"
CONFIG_SCHEMA_VERSION = 1


def _required_object(value, context: str) -> dict:
    if not isinstance(value, dict):
        raise StaleArtifactError(f"{context} must be a JSON object")
    return value


def _load_declarations(path: Path = CONFIG_PATH) -> tuple[SourceSpec, ...]:
    if not path.is_file():
        raise MissingInputError(f"structural observation source declaration not found at {path}")
    try:
        doc = _required_object(read_json(path), "structural observation source declaration")
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise StaleArtifactError(
            f"structural observation source declaration at {path} is unreadable"
        ) from exc
    if doc.get("schema_version") != CONFIG_SCHEMA_VERSION:
        raise StaleArtifactError(
            f"structural observation source declaration schema_version "
            f"{doc.get('schema_version')!r} != {CONFIG_SCHEMA_VERSION}"
        )
    if doc.get("book") != BOOK_ID:
        raise StaleArtifactError(
            f"structural observation source declaration names book {doc.get('book')!r}, not "
            f"{BOOK_ID!r}"
        )
    raw_sources = doc.get("sources")
    if not isinstance(raw_sources, list) or not raw_sources:
        raise StaleArtifactError("structural observation source declaration has no sources")
    declarations: list[SourceSpec] = []
    for index, raw in enumerate(raw_sources):
        source = _required_object(raw, f"structural observation source {index}")
        required = {"source_id", "format", "source_ref", "sha256", "bytes"}
        if set(source) != required:
            raise StaleArtifactError(
                f"structural observation source {index} keys {sorted(source)} != {sorted(required)}"
            )
        try:
            declarations.append(
                SourceSpec(
                    source_id=source["source_id"],
                    format=source["format"],
                    source_ref=source["source_ref"],
                    sha256=source["sha256"],
                    n_bytes=source["bytes"],
                )
            )
        except (TypeError, ValueError) as exc:
            raise StaleArtifactError(
                f"structural observation source {index} is malformed: {exc}"
            ) from exc
    if len({source.source_id for source in declarations}) != len(declarations):
        raise StaleArtifactError("structural observation source declaration has duplicate source ids")
    if any(source.format not in SOURCE_FORMATS for source in declarations):  # model also pins this
        raise StaleArtifactError("structural observation source declaration has an unknown format")
    return tuple(declarations)


def _expectations(path: Path = MANIFEST_PATH) -> tuple[StructuralExpectation, ...]:
    if not path.is_file():
        raise MissingInputError(f"book manifest not found at {path}")
    try:
        manifest = _required_object(read_json(path), "book manifest")
        structure = _required_object(manifest["structure"], "book manifest structure")
        parts = structure["parts"]
        if not isinstance(parts, list) or not parts:
            raise ValueError("parts must be a non-empty list")
        return tuple(
            StructuralExpectation(
                expectation_id=f"part-{index}",
                literal=_required_object(part, f"manifest part {index}")["name"],
                role="part",
            )
            for index, part in enumerate(parts, 1)
        )
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError, KeyError, TypeError,
            ValueError) as exc:
        raise StaleArtifactError(f"book manifest at {path} cannot supply declared parts: {exc}") from exc


def _local_source_path(source_ref: str) -> Path:
    path = (BOOK_DIR / source_ref).resolve()
    try:
        path.relative_to(BOOK_DIR.resolve())
    except ValueError as exc:
        raise StaleArtifactError(
            f"local structural observation source escapes the book directory: {source_ref!r}"
        ) from exc
    return path


def _source_bytes(spec: SourceSpec, *, timeout: float = 60.0) -> bytes:
    parsed = urlparse(spec.source_ref)
    if parsed.scheme in {"http", "https"}:
        try:
            with urllib.request.urlopen(spec.source_ref, timeout=timeout) as response:
                data = response.read(spec.n_bytes + 1)
        except (OSError, urllib.error.URLError) as exc:
            raise AcquisitionError(
                f"could not fetch structural observation source {spec.source_id!r} from "
                f"{spec.source_ref}: {exc}"
            ) from exc
        if len(data) > spec.n_bytes:
            raise StaleArtifactError(
                f"structural observation source {spec.source_id!r} exceeds locked byte length "
                f"{spec.n_bytes}"
            )
        return data
    if parsed.scheme:
        raise StaleArtifactError(
            f"unsupported structural observation source_ref scheme {parsed.scheme!r}"
        )
    path = _local_source_path(spec.source_ref)
    if not path.is_file():
        raise MissingInputError(
            f"structural observation source {spec.source_id!r} not found at {path}"
        )
    try:
        return path.read_bytes()
    except OSError as exc:
        raise MissingInputError(
            f"structural observation source {spec.source_id!r} cannot be read at {path}"
        ) from exc


def build_report(
    declarations: tuple[SourceSpec, ...] | None = None,
    *,
    source_loader=_source_bytes,
) -> dict:
    """Build the source-locked advisory report; injection keeps network out of unit tests."""

    declarations = declarations or _load_declarations()
    documents = tuple(
        load_source_bytes(declaration, source_loader(declaration))
        for declaration in declarations
    )
    return observe_structural_contents(
        book=BOOK_ID,
        sources=documents,
        expectations=_expectations(),
    )


def _print_report(report: dict, path: Path) -> None:
    by_expectation = {item["expectation_id"]: item for item in report["expectations"]}
    print(f"structural observations -> {path}")
    print(
        f"  {len(report['sources'])} source(s), {len(report['sightings'])} sighting(s), "
        f"policy {report['observer_policy']}"
    )
    for summary in report["summaries"]:
        expectation = by_expectation[summary["expectation_id"]]
        print(
            f"  {expectation['literal']!r} @ {summary['source_id']}: "
            f"body-like={summary['body_like']} contents-like={summary['contents_like']} "
            f"unresolved={summary['unresolved']} total={summary['total']}"
        )
    print("  all locus classifications are unverified advisory observations")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force",
        action="store_true",
        help="replace a differing existing advisory report after deliberate review",
    )
    args = parser.parse_args(argv)
    report = build_report()
    path = write_structural_contents_report(OUTPUT_PATH, report, force=args.force)
    _print_report(report, path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
