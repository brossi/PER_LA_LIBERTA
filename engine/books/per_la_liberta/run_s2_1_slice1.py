"""S2.1.3 — the PLL slice-1 geometry run (issue #37; ``s2_1_plan.md`` DT-3/DT-8/DT-9/DT-11 tier 3).

The LOCAL-ONLY real run (the scan PDF is gitignored and CI has no copy — DT-11's honest split):

1. OCR the LOC scan (copy1's physical copy) with the #36 backend — PLL's book profile:
   ``language="ita"``, ``dpi=300``. Boxes are cached **incrementally** in the disposable workspace
   (``work/data/geometry/_boxes_dpi300.json``, keyed on scan hash + engine id, checkpointed every
   20 pages and resumable), so neither a mid-pass fail-loud nor an interrupted ~40-minute pass
   discards completed pages, and matcher re-runs never repeat the OCR.
2. **Calibration gate (P-1, RULED 2026-07-03):** page-locate runs on copy3 *blind* (its page map
   ignored) and the derived pages are compared to the map — the only ground truth we own.
   "Exact" is strict page equality on single-page-truth body atoms; unmapped or multi-page-truth
   atoms are excluded AND counted (the map-coverage cross-check). Below the 95% floor the run
   HARD-BLOCKS: no ``copy1_geom.json`` is published, the failure distribution is **persisted** to
   the stats file (status ``calibration_blocked``), and the ruling goes to Ben with DT-3's three
   named options.
3. copy1 page-locate + token-bow-v1 match -> ``build_geom_sidecar`` (canonical stream loaded for
   the DT-13 coverage counters) -> P-5 tripwire -> ``save_geom_sidecar``. A tripwire trip also
   persists its evidence (status ``tripwire_blocked``) before failing; the sidecar is not saved.
4. Run-report evidence -> ``docs/probes/s2_1_run_stats.json`` (the numbers behind
   ``docs/probes/s2_1_run_report.md``), ``status: "ok"`` only on a fully green run.

The 0.80/0.60 thresholds passed below are DT-8 **proposals** — this runner is their book-side
consumer; they are ratified (or retuned) at the run report, which is why the engine core refuses
to default them.

Usage (from ``engine/``):  uv run python books/per_la_liberta/run_s2_1_slice1.py
  --accept-rate / --atom-floor    override the proposal thresholds for sensitivity probes
  --refresh-boxes       ignore the box cache and re-run OCR

(No page-subrange option on purpose: page-locate distributes the ENTIRE witness stream over
whatever pages it is given, so a partial-page run would squeeze the book into the slice and
produce garbage boundaries — the full scan is the only honest run.)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import Counter
from pathlib import Path

import fitz

from engine.paths import BookWorkspace
from engine.structure import (
    GeometryError,
    PageGeometry,
    SourceScan,
    WordBox,
    assert_auto_absent_tripwire,
    build_geom_sidecar,
    load_stream,
    match_stream,
    save_geom_sidecar,
)
from engine.structure.geometry_pymupdf import PyMuPDFTesseractBackend
from engine.util.jsonio import atomic_write_json

BOOK_DIR = Path(__file__).resolve().parent
ENGINE_ROOT = BOOK_DIR.parents[1]
MANIFEST = json.loads((BOOK_DIR / "manifest.json").read_text(encoding="utf-8"))
STATS_PATH = ENGINE_ROOT / "docs" / "probes" / "s2_1_run_stats.json"

LANGUAGE = "ita"
DPI = 300
CALIBRATION_FLOOR = 0.95  # P-1 (RULED 2026-07-03); re-evaluated at the run report
CHECKPOINT_EVERY = 20  # pages between incremental cache writes during the OCR pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _pages_from_cache(entries) -> list[PageGeometry]:
    return [
        PageGeometry(
            page=entry["page"],
            width=entry["width"],
            height=entry["height"],
            words=tuple(WordBox(text=w[0], bbox=(w[1], w[2], w[3], w[4])) for w in entry["words"]),
        )
        for entry in entries
    ]


def _pages_to_cache(pages) -> list[dict]:
    return [
        {
            "page": pg.page,
            "width": pg.width,
            "height": pg.height,
            "words": [[w.text, *w.bbox] for w in pg.words],
        }
        for pg in pages
    ]


def _load_or_ocr_pages(workspace, pdf_path, scan_sha, first, last, refresh):
    """The cached OCR pass: PageGeometry list + dropped_boxes + provenance strings.

    The cache is written incrementally (every CHECKPOINT_EVERY pages, and on a mid-pass
    fail-loud) with ``complete: false`` until the whole range is in, so an interrupted or
    backend-blocked pass resumes instead of repeating finished pages."""
    cache_path = workspace.resolve("data", "geometry", f"_boxes_dpi{DPI}.json")
    backend = PyMuPDFTesseractBackend(pdf_path, language=LANGUAGE, dpi=DPI)
    pages: list[PageGeometry] = []
    dropped: dict[int, int] = {}
    if cache_path.is_file() and not refresh:
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            usable = (
                cached["scan_sha256"] == scan_sha
                and cached["engine_id"] == backend.engine_id
                and cached["first"] == first
                and cached["last"] == last
                and len(cached["pages"]) == len({e["page"] for e in cached["pages"]})
            )
        except (json.JSONDecodeError, KeyError, TypeError, UnicodeDecodeError) as exc:
            print(f"box cache unreadable ({exc}) — regenerating (or pass --refresh-boxes)")
            usable = False
        if usable:
            pages = _pages_from_cache(cached["pages"])
            dropped = {int(k): v for k, v in cached["dropped_boxes"].items()}
            if cached.get("complete") and len(pages) == last - first + 1:
                print(f"box cache hit: {len(pages)} pages from {cache_path.name}")
                return pages, dropped, cached["engine_id"], cached["backend_params"]
            print(f"box cache partial: {len(pages)} pages banked; resuming OCR")

    def checkpoint(complete: bool) -> None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(
            cache_path,
            {
                "scan_sha256": scan_sha,
                "engine_id": backend.engine_id,
                "backend_params": backend.backend_params,
                "first": first,
                "last": last,
                "complete": complete,
                "dropped_boxes": {str(k): v for k, v in dropped.items()},
                "pages": _pages_to_cache(pages),
            },
        )

    resume_from = first + len(pages)
    if resume_from <= last:
        print(
            f"OCR pass: pages {resume_from}..{last} at dpi={DPI} lang={LANGUAGE} "
            f"(the slow step; checkpointed every {CHECKPOINT_EVERY} pages)"
        )
        started = time.monotonic()
        try:
            for geometry in backend.read_pages(resume_from, last):
                pages.append(geometry)
                dropped[geometry.page] = backend.dropped_boxes[geometry.page]
                if geometry.page % CHECKPOINT_EVERY == 0 or geometry.page == last:
                    checkpoint(complete=(geometry.page == last))
                    elapsed = time.monotonic() - started
                    print(f"  page {geometry.page}/{last}  ({elapsed:.0f}s elapsed)")
        except GeometryError:
            checkpoint(complete=False)  # bank the finished pages before failing loud
            raise
    else:
        checkpoint(complete=True)
    return pages, dropped, backend.engine_id, backend.backend_params


def _calibrate_copy3_blind(copy3, pages, floor):
    """P-1's gate: page-locate copy3 blind, hold the derived pages against its map.

    Exact = strict page equality, scoped to single-page-truth included-scope atoms; unmapped and
    multi-page-truth atoms are excluded from the denominator and counted (the plan's exactness
    claim must never silently loosen into window containment)."""
    started = time.monotonic()
    outcome = match_stream(copy3, pages, page_accept_rate=0.0, atom_match_floor=0.0)
    wall = time.monotonic() - started
    in_range = {pg.page for pg in pages}
    excluded_unmapped = 0
    excluded_multi_page_truth = 0
    excluded_out_of_range = 0
    deltas = Counter()
    small_total = small_exact = 0
    body_total = exact = 0
    for atom in copy3.atoms:
        if atom.processing_scope != "included":
            continue
        true_first, true_last = atom.page_range
        if true_first < 0 or true_last < 0:
            excluded_unmapped += 1
            continue
        if true_first != true_last:
            excluded_multi_page_truth += 1
            continue
        if true_first not in in_range:
            excluded_out_of_range += 1
            continue
        assigned = outcome.atom_pages[atom.atom_id].assigned
        hit = assigned == true_first
        body_total += 1
        exact += hit
        deltas[assigned - true_first] += 1
        if outcome.token_counts[atom.atom_id] <= 5:
            small_total += 1
            small_exact += hit
    rate = exact / body_total if body_total else 0.0
    stats = {
        "body_atoms": body_total,
        "exact": exact,
        "exact_rate": rate,
        "floor": floor,
        "excluded_unmapped": excluded_unmapped,
        "excluded_multi_page_truth": excluded_multi_page_truth,
        "excluded_out_of_range": excluded_out_of_range,
        "delta_histogram": {str(k): v for k, v in sorted(deltas.items())},
        "small_atom_total_le5_tokens": small_total,
        "small_atom_exact_le5_tokens": small_exact,
        "small_atom_exact_rate": (small_exact / small_total) if small_total else None,
        "wall_seconds": wall,
    }
    print(
        f"calibration (copy3 blind): {exact}/{body_total} single-page body atoms exact = "
        f"{rate:.4f} (floor {floor}); <=5-token slice {small_exact}/{small_total}; "
        f"excluded unmapped={excluded_unmapped} multi-page={excluded_multi_page_truth}; {wall:.1f}s"
    )
    return stats, rate >= floor


def _decade_bin(rate: float) -> str:
    for i in range(10):
        if rate < (i + 1) / 10:
            return f"{i / 10:.1f}"
    return "0.9"


def _write_stats(status: str, **sections) -> None:
    STATS_PATH.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(STATS_PATH, {"status": status, **sections})
    print(f"run stats ({status}) -> {STATS_PATH}")


def main() -> None:
    parser = argparse.ArgumentParser(description="PLL slice-1 geometry run (S2.1.3 #37)")
    parser.add_argument("--accept-rate", type=float, default=0.80,
                        help="DT-8 page-acceptance proposal (ratified at the run report)")
    parser.add_argument("--atom-floor", type=float, default=0.60,
                        help="DT-8 per-atom floor proposal (ratified at the run report)")
    parser.add_argument("--refresh-boxes", action="store_true")
    args = parser.parse_args()

    pdf_path = ENGINE_ROOT.parent / MANIFEST["scan"]["pdf"]
    if not pdf_path.is_file():
        raise SystemExit(
            f"scan PDF not found: {pdf_path}\nThe slice-1 run is LOCAL-ONLY (DT-11): it needs the "
            f"gitignored LOC scan at the PLL repo root."
        )
    scan_sha = _sha256(pdf_path)
    with fitz.open(pdf_path) as document:
        page_count = document.page_count
    first, last = 1, page_count

    workspace = BookWorkspace.for_book("per_la_liberta", BOOK_DIR.parent).ensure()
    run_params = {
        "pages": [first, last],
        "page_accept_rate": args.accept_rate,
        "atom_match_floor": args.atom_floor,
    }
    try:
        pages, dropped, engine_id, backend_params = _load_or_ocr_pages(
            workspace, pdf_path, scan_sha, first, last, args.refresh_boxes
        )
    except GeometryError as exc:
        # The backend's fail-loud fired mid-book (finished pages are banked in the cache).
        raise SystemExit(f"geometry backend fail-loud (exit 13): {exc}") from exc
    run_params.update({"engine_id": engine_id, "backend_params": backend_params})

    copy3 = load_stream(workspace, "copy3")
    calibration, calibration_ok = _calibrate_copy3_blind(copy3, pages, CALIBRATION_FLOOR)
    if not calibration_ok:
        # DT-3's failure route: hard-block, PERSIST the failure distribution, ruling to Ben.
        _write_stats("calibration_blocked", run=run_params, calibration_copy3_blind=calibration)
        print("calibration BELOW FLOOR — slice 1 hard-blocks (DT-3 failure route).")
        print(
            "  Ruling to Ben, the three named options: (i) ratify a page±1 tolerance tier with a "
            "re-derived floor; (ii) route the failing page-regions to the DT-10 worklist; "
            "(iii) reopen S2.1-alt."
        )
        raise SystemExit(13)

    copy1 = load_stream(workspace, "copy1")
    canonical = load_stream(workspace, "canonical")
    started = time.monotonic()
    outcome = match_stream(
        copy1, pages,
        page_accept_rate=args.accept_rate,
        atom_match_floor=args.atom_floor,
        dropped_boxes=dropped,
    )
    match_wall = time.monotonic() - started
    run_params["match_wall_seconds"] = match_wall

    sidecar = build_geom_sidecar(
        outcome,
        source_scan=SourceScan(
            kind="pdf", sha256=scan_sha, n_pages=page_count, n_bytes=pdf_path.stat().st_size
        ),
        backend_params=backend_params,
        engine_id=engine_id,
        canonical_stream=canonical,
    )

    page_status = Counter(record.status for record in sidecar.pages.values())
    rate_histogram = Counter()
    for record in sidecar.pages.values():
        if record.status == "matched":
            rate_histogram[_decade_bin(record.match_rate)] += 1
        elif record.stage == "match":
            rate_histogram[_decade_bin(record.value)] += 1
    atom_status = Counter(
        record.reason if record.status == "unmatched" else "matched"
        for record in sidecar.atoms.values()
    )
    pending = sum(
        1 for atom_id, window in sidecar.atom_pages.items()
        if atom_id not in sidecar.atoms and sidecar.pages[window.assigned].status == "routed"
    )
    sections = {
        "run": run_params,
        "calibration_copy3_blind": calibration,
        "pages": {
            "status_counts": dict(page_status),
            "rate_histogram": {k: rate_histogram[k] for k in sorted(rate_histogram)},
            "locate_failed": list(outcome.locate_failed_pages),
        },
        "atoms": {
            "records": len(sidecar.atoms),
            "status_counts": dict(atom_status),
            "pending": pending,
            "tokenless": sum(1 for c in outcome.token_counts.values() if c == 0),
            "straddler_windows": sum(1 for w in sidecar.atom_pages.values() if w.first != w.last),
        },
        "coverage": dict(sidecar.coverage),
        "hyphen_fragment_boxes": sum(1 for pg in pages for w in pg.words if w.text.endswith("-")),
    }

    try:
        tripwire = assert_auto_absent_tripwire(sidecar, outcome.token_counts)
    except GeometryError as exc:
        # P-5 fired: publish nothing, but PERSIST the evidence behind the trip.
        _write_stats("tripwire_blocked", **sections)
        raise SystemExit(f"auto-absent tripwire fired (exit 13): {exc}") from exc
    sections["tripwire"] = tripwire

    sidecar_path = save_geom_sidecar(workspace, sidecar)
    _write_stats("ok", **sections)

    print(f"\nsidecar -> {sidecar_path}")
    print(f"pages: {dict(page_status)}   atoms: {dict(atom_status)}   pending: {pending}")
    print(f"coverage: {dict(sidecar.coverage)}")
    print(f"tripwire: massA={tripwire['absent_token_mass_rate']:.4f} "
          f"proseB={tripwire['prose_absent_rate']:.4f} flags={len(tripwire['flags'])}")


if __name__ == "__main__":
    main()
