"""S2.1.3 — the PLL slice-1 geometry run (issue #37; ``s2_1_plan.md`` DT-3/DT-8/DT-9/DT-11 tier 3).

The LOCAL-ONLY real run (the scan PDF is gitignored and CI has no copy — DT-11's honest split):

1. OCR the LOC scan (copy1's physical copy) with the #36 backend — PLL's book profile:
   ``language="ita"``, ``dpi=300``. Boxes are cached **incrementally** in the disposable workspace
   (``work/data/geometry/_boxes_dpi300.json``, keyed on scan hash + engine id, checkpointed every
   20 pages and resumable), so neither a mid-pass fail-loud nor an interrupted ~40-minute pass
   discards completed pages, and matcher re-runs never repeat the OCR.
2. **Calibration gate (P-1, RULED 2026-07-03; SUPERSEDED by Ben 2026-07-05 — two complementary
   clauses, BOTH must hold):** page-locate runs on copy3 *blind* (its page map ignored) and the
   derived pages are compared to the map — the only ground truth we own. Clause A: exact (strict
   page equality) ≥ 95% over single-page-truth atoms with > 5 tokens — the discriminable
   population; exactness is what catches a systematic one-page offset. Clause B: within ±1 ≥ 98%
   over ALL single-page-truth atoms — bounds worst-case error for the tiny atoms clause A cannot
   see. Unmapped or multi-page-truth atoms are excluded AND counted (the map-coverage
   cross-check); floors and the token cutoff are CLI-tunable (ruled values as defaults). On any
   clause failure the run HARD-BLOCKS: no ``copy1_geom.json`` is published, the failure
   distribution is **persisted** to the stats file (status ``calibration_blocked``), and the
   ruling goes to Ben with DT-3's three named options.
3. copy1 page-locate + token-bow-v1 match -> ``build_geom_sidecar`` (canonical stream loaded for
   the DT-13 coverage counters) -> P-5 tripwire -> ``save_geom_sidecar``. A tripwire trip also
   persists its evidence (status ``tripwire_blocked``) before failing; the sidecar is not saved.
4. Run-report evidence -> ``docs/probes/s2_1_run_stats.json`` (the numbers behind
   ``docs/probes/s2_1_run_report.md``), ``status: "ok"`` only on a fully green run.

DT-8 thresholds (RATIFIED by Ben 2026-07-05, at the slice-1 run report): ``atom_match_floor``
0.60 is a ratified **constant** (it guards individual atoms, not review budgets).
``page_accept_rate`` is ratified as a **standing procedure**, not a constant: the cut is a
per-run review-budget decision, named by a human from the deterministic ``threshold_sweep``
this runner emits (ladder + advisory gap candidates + decision zone, persisted in the stats
file and printed at run end); the applied cut lands in ``run_params``, its rationale in the run
report. Run 1's cut: 0.80 (the pre-registered proposal, left standing after review of the
12-page worklist). The engine core still refuses to default either value — both arrive as
parameters.

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
from bisect import bisect_left
from collections import Counter
from pathlib import Path

import fitz

from engine.paths import BookWorkspace
from engine.structure import (
    ColumnDetector,
    DensityClassifier,
    GeometryError,
    PageColumnInput,
    PageGeometry,
    SourceScan,
    WordBox,
    assert_auto_absent_tripwire,
    build_geom_sidecar,
    detect_columns,
    ink_fraction_from_pixmap,
    load_stream,
    match_stream,
    normalize_tokens,
    page_density_features,
    resolve_reading_columns,
    save_geom_sidecar,
)
from engine.structure.column_calibration import propose_column_policy
from engine.structure.geom_review import (
    REVIEW_FRACTION_MAX_DEFAULT,
    RouteInput,
    build_worklist,
    input_fingerprint,
    overlay_path,
    page_order_qa,
    render_overlay,
    save_worklist,
    write_review_sheet,
)
from engine.structure.geom_sidecar import PAGE_MATCHED, PAGE_ROUTED, with_detector_fields
from engine.structure.geometry_pymupdf import PyMuPDFTesseractBackend
from engine.structure.segmentation import is_alpha_token
from engine.util.jsonio import atomic_write_json

BOOK_DIR = Path(__file__).resolve().parent
ENGINE_ROOT = BOOK_DIR.parents[1]
MANIFEST = json.loads((BOOK_DIR / "manifest.json").read_text(encoding="utf-8"))
STATS_PATH = ENGINE_ROOT / "docs" / "probes" / "s2_1_run_stats.json"

LANGUAGE = "ita"
DPI = 300
# P-1 (RULED 2026-07-03: 95% exact over all single-page atoms; SUPERSEDED by Ben 2026-07-05:
# two complementary clauses, both must hold — each covers the other's structural blind spot,
# see docs/probes/s2_1_band_drift.md and the P-1 row). Ruled values are the defaults; the CLI
# flags below exist so the floors and the population cutoff are tunable for sensitivity probes
# without code changes (same pattern as the DT-8 --accept-rate/--atom-floor proposals).
CALIBRATION_EXACT_FLOOR = 0.95  # clause A: exact, atoms with > SMALL_ATOM_MAX_TOKENS tokens
CALIBRATION_WINDOW_FLOOR = 0.98  # clause B: within +/-1 page, ALL single-page atoms
SMALL_ATOM_MAX_TOKENS = 5  # the discriminability cutoff between clause A's population and the reported slice
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
    """The cached OCR pass: PageGeometry list + dropped_boxes + oob_boxes + provenance strings.

    The cache is written incrementally (every CHECKPOINT_EVERY pages, and on a mid-pass
    fail-loud) with ``complete: false`` until the whole range is in, so an interrupted or
    backend-blocked pass resumes instead of repeating finished pages. A cache from before the
    2026-07-05 bounded drop-and-count amendment lacks ``oob_boxes`` and is treated as unusable
    (regenerated) rather than guessed at."""
    cache_path = workspace.resolve("data", "geometry", f"_boxes_dpi{DPI}.json")
    backend = PyMuPDFTesseractBackend(pdf_path, language=LANGUAGE, dpi=DPI)
    pages: list[PageGeometry] = []
    dropped: dict[int, int] = {}
    oob: dict[int, int] = {}
    if cache_path.is_file() and not refresh:
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            usable = (
                cached["scan_sha256"] == scan_sha
                and cached["engine_id"] == backend.engine_id
                and cached["first"] == first
                and cached["last"] == last
                and isinstance(cached["oob_boxes"], dict)
                and isinstance(cached["dropped_boxes"], dict)
                and len(cached["pages"]) == len({e["page"] for e in cached["pages"]})
            )
        except (json.JSONDecodeError, KeyError, TypeError, UnicodeDecodeError) as exc:
            print(f"box cache unusable ({exc!r}: corrupt or pre-P-7 schema) — regenerating")
            usable = False
        if usable:
            pages = _pages_from_cache(cached["pages"])
            dropped = {int(k): v for k, v in cached["dropped_boxes"].items()}
            oob = {int(k): v for k, v in cached["oob_boxes"].items()}
            if cached.get("complete") and len(pages) == last - first + 1:
                print(f"box cache hit: {len(pages)} pages from {cache_path.name}")
                return pages, dropped, oob, cached["engine_id"], cached["backend_params"]
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
                "oob_boxes": {str(k): v for k, v in oob.items()},
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
                oob[geometry.page] = backend.oob_boxes[geometry.page]
                if oob[geometry.page]:
                    print(
                        f"  page {geometry.page}: {oob[geometry.page]} isolated off-page "
                        f"box(es) dropped and counted (2026-07-05 ruling)"
                    )
                if geometry.page % CHECKPOINT_EVERY == 0 or geometry.page == last:
                    checkpoint(complete=(geometry.page == last))
                    elapsed = time.monotonic() - started
                    print(f"  page {geometry.page}/{last}  ({elapsed:.0f}s elapsed)")
        except GeometryError:
            # Bank the finished pages AND the failing page's backend counters (banked there
            # before its raise) so the systemic-failure evidence lands in the persisted cache;
            # a resume re-OCRs the failing page and overwrites these entries.
            dropped.update({p: c for p, c in backend.dropped_boxes.items() if p not in dropped})
            oob.update({p: c for p, c in backend.oob_boxes.items() if p not in oob})
            checkpoint(complete=False)
            raise
    else:
        checkpoint(complete=True)
    return pages, dropped, oob, backend.engine_id, backend.backend_params


def _calibrate_copy3_blind(copy3, pages, *, small_max_tokens):
    """P-1's measurement: page-locate copy3 blind, hold the derived pages against its map.

    Measurement only — the pass/block judgment lives in :func:`_gate_verdict` so the floors are
    tunable (CLI flags) without touching this pass. Two-clause populations (P-1 SUPERSEDED by Ben
    2026-07-05, two complementary gates): clause A = strict page equality over single-page-truth
    atoms with MORE than ``small_max_tokens`` tokens (the discriminable population — the plan's
    exactness claim must never silently loosen into window containment); clause B = within ±1
    over ALL single-page-truth atoms (bounds worst-case error for the tiny atoms clause A cannot
    see, and only exactness catches the systematic one-page offset clause B alone would pass).
    Unmapped / multi-page-truth atoms are excluded from both denominators and counted."""
    started = time.monotonic()
    outcome = match_stream(copy3, pages, page_accept_rate=0.0, atom_match_floor=0.0)
    wall = time.monotonic() - started
    in_range = {pg.page for pg in pages}
    excluded_unmapped = 0
    excluded_multi_page_truth = 0
    excluded_out_of_range = 0
    deltas = Counter()
    small_total = small_exact = 0
    big_total = big_exact = 0
    body_total = exact = within_one = 0
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
        delta = assigned - true_first
        hit = delta == 0
        body_total += 1
        exact += hit
        within_one += abs(delta) <= 1
        deltas[delta] += 1
        if outcome.token_counts[atom.atom_id] <= small_max_tokens:
            small_total += 1
            small_exact += hit
        else:
            big_total += 1
            big_exact += hit
    stats = {
        "body_atoms": body_total,
        "exact": exact,
        "exact_rate": (exact / body_total) if body_total else 0.0,
        "small_max_tokens": small_max_tokens,
        "clause_a": {
            "population": f"single-page-truth atoms with > {small_max_tokens} tokens",
            "n": big_total,
            "exact": big_exact,
            "rate": (big_exact / big_total) if big_total else 0.0,
        },
        "clause_b": {
            "population": "all single-page-truth atoms, within +/-1 page",
            "n": body_total,
            "within_one": within_one,
            "rate": (within_one / body_total) if body_total else 0.0,
        },
        "excluded_unmapped": excluded_unmapped,
        "excluded_multi_page_truth": excluded_multi_page_truth,
        "excluded_out_of_range": excluded_out_of_range,
        "delta_histogram": {str(k): v for k, v in sorted(deltas.items())},
        "small_atom_total": small_total,
        "small_atom_exact": small_exact,
        "small_atom_exact_rate": (small_exact / small_total) if small_total else None,
        "wall_seconds": wall,
    }
    return stats


def _gate_verdict(stats, *, exact_floor, window_floor):
    """The pure P-1 judgment over measured calibration stats: BOTH clauses must hold.

    An empty clause population fails its clause — a book that yields no discriminable atoms (or
    no mapped atoms at all) cannot be *certified*, only investigated; passing vacuously would
    publish a sidecar on zero evidence."""
    a, b = stats["clause_a"], stats["clause_b"]
    a_ok = a["n"] > 0 and a["rate"] >= exact_floor
    b_ok = b["n"] > 0 and b["rate"] >= window_floor
    reasons = []
    if not a_ok:
        reasons.append(
            f"clause A: exact {a['exact']}/{a['n']} = {a['rate']:.4f} < floor {exact_floor}"
            if a["n"]
            else "clause A: empty population — nothing discriminable to certify"
        )
    if not b_ok:
        reasons.append(
            f"clause B: within +/-1 {b['within_one']}/{b['n']} = {b['rate']:.4f} < floor {window_floor}"
            if b["n"]
            else "clause B: empty population — no mapped atoms to certify"
        )
    return a_ok and b_ok, reasons


def _decade_bin(rate: float) -> str:
    for i in range(10):
        if rate < (i + 1) / 10:
            return f"{i / 10:.1f}"
    return "0.9"


# DT-8 standing mechanism (RATIFIED by Ben 2026-07-05): the page-accept threshold is not a
# constant — it is a per-run REVIEW-BUDGET decision, named by a human from this deterministic
# sweep of the run's own persisted rate distribution (never an ad-hoc probe loop, never an
# auto-decided cut). The gap candidates are ADVISORY: they surface where the distribution has
# natural cuts; the human names the value; the applied cut lands in run_params and its rationale
# in the run report. Re-cutting = re-running with --accept-rate X (~3 min from the box cache).
SWEEP_LADDER = (0.70, 0.75, 0.78, 0.79, 0.80, 0.81, 0.85, 0.90)
SWEEP_GAP_RANGE = (0.50, 0.95)  # cuts outside this range are not review-budget territory
SWEEP_ZONE_HALF_WIDTH = 0.05  # pages within +/- this of the applied cut = the decision zone


def _threshold_sweep(sidecar, applied_cut):
    """The threshold-decision evidence: ladder counts, advisory gap candidates, decision zone.

    Pages routed at locate (``empty-window``) carry no rate and route under any cut; only
    match-stage rates participate. Pure and deterministic over the sidecar's persisted rates."""
    rated = sorted(
        (rec.match_rate if rec.status == "matched" else rec.value, n)
        for n, rec in sidecar.pages.items()
        if rec.status == "matched" or rec.stage == "match"
    )
    values = [v for v, _ in rated]
    rateless = len(sidecar.pages) - len(rated)

    def counts(cut):
        accepted = len(values) - bisect_left(values, cut)
        return {"accepted": accepted, "routed": len(values) - accepted + rateless}

    ladder = {f"{t:.2f}": counts(t) for t in sorted({*SWEEP_LADDER, round(applied_cut, 4)})}
    lo, hi = SWEEP_GAP_RANGE
    in_range = sorted({v for v in values if lo <= v <= hi})
    gaps = sorted(
        (
            {"below": a, "above": b, "width": b - a, "candidate_cut": (a + b) / 2,
             **counts((a + b) / 2)}
            for a, b in zip(in_range, in_range[1:])
        ),
        key=lambda g: -g["width"],
    )[:3]
    zone = {
        str(n): v for v, n in rated if abs(v - applied_cut) <= SWEEP_ZONE_HALF_WIDTH
    }
    return {
        "procedure": "DT-8 ratified 2026-07-05: human-named cut from this sweep; gaps advisory",
        "applied_cut": applied_cut,
        "pages_without_rate": rateless,
        "ladder": ladder,
        "gap_candidates": gaps,
        "decision_zone": dict(sorted(zone.items(), key=lambda kv: kv[1])),
    }


def _write_stats(status: str, **sections) -> None:
    STATS_PATH.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(STATS_PATH, {"status": status, **sections})
    print(f"run stats ({status}) -> {STATS_PATH}")


INK_DPI = 150  # density pre-check ink-fraction dpi (the #38 calibration resolution)
OVERLAY_DPI = 150  # review-overlay render dpi (#46) — legible on screen, page-bounded output


def _front_end_pass(pages, document, seg, copy1, boundaries, matched_pages):
    """The S2.1 segmentation front-end over the OCR'd book (DT-5/6/7/12; #38/#39 built the pieces,
    #40 wires them book-wide): density gate → column detector + cross-page prior → per-matched-page
    ``order_qa`` (the S2.2 feed) + the routed-page worklist inputs + the ``col2_score`` distribution
    (the DT-7 auto-propose evidence).

    ``pages`` are in scan order, aligned with ``boundaries`` (page-locate's per-page-index cuts) and
    the reconstructed copy1 witness stream — so ``stream_tokens[boundaries[i]:boundaries[i+1]]`` is
    the witness window of ``pages[i]``. Pure over its inputs except the density pixmap render (I/O).
    """
    bands, cols = seg["density_bands"], seg["column_detector"]
    clf = DensityClassifier(**bands)
    detector = ColumnDetector(**cols)
    n_leaves = pages[-1].page if pages else 0  # last scan page = leaf count for the COVER position gate
    # Rebuild the witness stream exactly as match_stream did (full stream, DT-3): normalize every
    # copy1 atom's text and concatenate — so the boundaries index this token list.
    stream_tokens = [tok for atom in copy1.atoms for tok in normalize_tokens(atom.text)]

    densities, evidences, feats = [], [], []
    for page in pages:
        pixmap = document[page.page - 1].get_pixmap(dpi=INK_DPI)
        ink = ink_fraction_from_pixmap(pixmap)
        density_features = page_density_features(ink_fraction=ink, boxes=page.words)
        densities.append(clf.classify(density_features, leaf_index=page.page, n_leaves=n_leaves))
        evidences.append(detect_columns(page.words, page.width))
        feats.append((ink, len(page.words), sum(1 for w in page.words if is_alpha_token(w.text))))
    verdicts = resolve_reading_columns(
        [PageColumnInput(density=d, evidence=e) for d, e in zip(densities, evidences)], detector
    )

    detector_fields: dict[int, dict] = {}
    order_qa_values: dict[int, float] = {}
    routes: list[RouteInput] = []
    col2_scores = [e.col2_score for e in evidences]
    for i, page in enumerate(pages):
        verdict = verdicts[i]
        if page.page in matched_pages:
            # A matched page has accepted geometry (the matcher's token evidence). The density gate
            # and the matcher are independent classifiers, so a page can be ink-ABSTAIN yet
            # token-matched; reconcile in the matcher's favour — emit its order_qa, no review route
            # (never publish a page as both accepted and needing review).
            split_x = evidences[i].split_x if verdict.n_cols == 2 else None
            window = stream_tokens[boundaries[i]:boundaries[i + 1]]
            oqa = page_order_qa(window, page.words, split_x)
            detector_fields[page.page] = {
                "n_cols": verdict.n_cols, "n_cols_source": verdict.n_cols_source, "order_qa": oqa,
            }
            order_qa_values[page.page] = oqa
            continue
        ink, box_count, token_count = feats[i]
        if verdict.routed and verdict.signal == "density-routed":
            routes.append(RouteInput(
                page=page.page, stage="density", signal=densities[i].signal,
                value=densities[i].confidence, threshold=bands["confidence_margin"],
                tentative={"box_count": box_count, "token_count": token_count,
                           "ink": ink, "band": densities[i].band.name},
            ))
        elif verdict.routed and verdict.signal == "prior-ambiguous":
            routes.append(RouteInput(
                page=page.page, stage="columns", signal="valley-confidence",
                value=evidences[i].col2_score, threshold=cols["decision_threshold"],
                tentative={"split_x": evidences[i].split_x, "col2_score": evidences[i].col2_score,
                           "n_cols_hint": detector.classify(evidences[i]).n_cols},
            ))
    return detector_fields, order_qa_values, routes, col2_scores


def _matcher_routes(sidecar, outcome, accept_rate):
    """The matcher-stage worklist inputs: the sidecar's already-routed pages (locate empty-window
    and sub-threshold match rate). The front-end (density/columns) routes are disjoint by stage, so
    a page routed at two gates surfaces as two candidates.

    #46: a match route carries the review evidence behind its bare rate — the ``matched``/``total``
    token denominator (the p6 tiny-window trap) and the ``unmatched_tokens`` chips — from the
    matcher's in-memory :attr:`MatchOutcome.page_match_evidence` (never persisted to the lean
    sidecar). The review sheet's denominator rule requires ``total`` for a match-rate entry."""
    routes = []
    for page, rec in sorted(sidecar.pages.items()):
        if rec.status != PAGE_ROUTED:
            continue
        if rec.stage == "match":
            ev = outcome.page_match_evidence[page]  # KeyError = a match route with no evidence: a bug
            threshold = accept_rate
            tentative = {"matched": ev.matched, "total": ev.total,
                         "unmatched_tokens": list(ev.unmatched_tokens)}
        else:
            threshold = 0.0
            tentative = {}
        routes.append(RouteInput(
            page=page, stage=rec.stage, signal=rec.signal, value=rec.value,
            threshold=threshold, tentative=tentative,
        ))
    return routes


def _render_worklist_overlays(worklist, pages_by_scan, pdf_path, workspace):
    """Render one review overlay per worklist **candidate** (#46): the routed page's scan with its
    OCR boxes drawn, plus the detected split + a pixel ruler on ``columns`` candidates (so
    ``redraw_split`` can be read off the image). Overlays are keyed by ``(page, stage)`` — a page
    routed at two gates gets two distinct files, so the plain match/locate overlay never overwrites
    the columns one that needs the ruler (#46 audit M1). On-demand and page-bounded — only the routed
    pages (≤ the P-6 review fraction), never the whole book. Returns the count rendered."""
    count = 0
    with fitz.open(pdf_path) as document:
        for c in worklist.candidates:
            page = pages_by_scan.get(c.page)
            if page is None:  # a candidate page outside the read range — should not happen
                continue
            split_x = c.tentative.get("split_x") if c.stage == "columns" else None
            background = document[c.page - 1].get_pixmap(dpi=OVERLAY_DPI)
            render_overlay(
                width=page.width, height=page.height, boxes=page.words, split_x=split_x,
                out_path=overlay_path(workspace, c.page, c.stage), background=background,
                dpi=OVERLAY_DPI, ruler=(c.stage == "columns"),
            )
            count += 1
    return count


def _order_qa_summary(order_qa_values):
    """The S2.2 measurement feed (DT-12): per-page order_qa distribution + mean + pass@0.85 (the
    re-gate's own metric, so #30 becomes a ruling over persisted numbers, not new machinery)."""
    vals = sorted(order_qa_values.values())
    n = len(vals)
    histogram = {}
    for i in range(10):
        lo, hi = i / 10, (i + 1) / 10
        histogram[f"{lo:.1f}"] = sum(1 for v in vals if (lo <= v < hi) or (i == 9 and v == 1.0))
    return {
        "n_pages": n,
        "mean": (sum(vals) / n) if n else None,
        "median": (vals[n // 2] if n else None),
        "pass_at_0_85": (sum(1 for v in vals if v >= 0.85) / n) if n else None,
        "histogram": histogram,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="PLL slice-1 geometry run (S2.1.3 #37)")
    parser.add_argument("--accept-rate", type=float, default=0.80,
                        help="DT-8 page-acceptance proposal (ratified at the run report)")
    parser.add_argument("--atom-floor", type=float, default=0.60,
                        help="DT-8 per-atom floor proposal (ratified at the run report)")
    parser.add_argument("--refresh-boxes", action="store_true")
    parser.add_argument("--calibration-exact-floor", type=float, default=CALIBRATION_EXACT_FLOOR,
                        help="P-1 clause A: exact-rate floor over > small-max-tokens atoms "
                             "(ruled 0.95; override for sensitivity probes)")
    parser.add_argument("--calibration-window-floor", type=float, default=CALIBRATION_WINDOW_FLOOR,
                        help="P-1 clause B: within-±1 floor over all single-page atoms "
                             "(ruled 0.98; override for sensitivity probes)")
    parser.add_argument("--small-max-tokens", type=int, default=SMALL_ATOM_MAX_TOKENS,
                        help="token cutoff splitting clause A's population from the reported "
                             "small-atom slice (ruled 5)")
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
        pages, dropped, oob, engine_id, backend_params = _load_or_ocr_pages(
            workspace, pdf_path, scan_sha, first, last, args.refresh_boxes
        )
    except GeometryError as exc:
        # The backend's fail-loud fired mid-book (finished pages are banked in the cache).
        raise SystemExit(f"geometry backend fail-loud (exit 13): {exc}") from exc
    run_params.update({"engine_id": engine_id, "backend_params": backend_params})

    copy3 = load_stream(workspace, "copy3")
    calibration = _calibrate_copy3_blind(copy3, pages, small_max_tokens=args.small_max_tokens)
    calibration["floors"] = {
        "clause_a_exact": args.calibration_exact_floor,
        "clause_b_within_one": args.calibration_window_floor,
    }
    a, b = calibration["clause_a"], calibration["clause_b"]
    print(
        f"calibration (copy3 blind): clause A exact {a['exact']}/{a['n']} = {a['rate']:.4f} "
        f"(floor {args.calibration_exact_floor}); clause B within ±1 {b['within_one']}/{b['n']} "
        f"= {b['rate']:.4f} (floor {args.calibration_window_floor}); "
        f"≤{args.small_max_tokens}-token slice {calibration['small_atom_exact']}"
        f"/{calibration['small_atom_total']}; {calibration['wall_seconds']:.1f}s"
    )
    calibration_ok, gate_reasons = _gate_verdict(
        calibration,
        exact_floor=args.calibration_exact_floor,
        window_floor=args.calibration_window_floor,
    )
    if not calibration_ok:
        # DT-3's failure route: hard-block, PERSIST the failure distribution, ruling to Ben.
        calibration["gate_failures"] = gate_reasons
        _write_stats("calibration_blocked", run=run_params, calibration_copy3_blind=calibration)
        for reason in gate_reasons:
            print(f"calibration BLOCKED — {reason}")
        print("slice 1 hard-blocks (DT-3 failure route); distribution persisted, ruling to Ben.")
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

    # --- S2.1.6 (#40): segmentation front-end — order_qa feed (DT-12) + worklist (DT-10) + DT-7 ---
    seg = MANIFEST["segmentation"]
    matched_pages = {p for p, rec in sidecar.pages.items() if rec.status == PAGE_MATCHED}
    fe_started = time.monotonic()
    with fitz.open(pdf_path) as document:
        detector_fields, order_qa_values, front_end_routes, col2_scores = _front_end_pass(
            pages, document, seg, copy1, outcome.boundaries, matched_pages
        )
    front_end_wall = time.monotonic() - fe_started
    sidecar = with_detector_fields(sidecar, detector_fields)  # order_qa onto the matched pages

    review_fraction_max = seg.get("review_fraction_max") or REVIEW_FRACTION_MAX_DEFAULT
    fingerprint = input_fingerprint(
        stream_source_hash=sidecar.stream_source_hash,
        source_scan_sha256=scan_sha,
        engine_id=engine_id,
        classifier_version=DensityClassifier(**seg["density_bands"]).version,
        policy_values={**seg["density_bands"], **seg["column_detector"],
                       "review_fraction_max": review_fraction_max},
    )
    all_routes = front_end_routes + _matcher_routes(sidecar, outcome, args.accept_rate)
    proposal = propose_column_policy(col2_scores)

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
        # Bounded drop-and-count evidence (P-7, ruled 2026-07-05): which pages shed isolated
        # off-page hallucinations, and how many — the run report's check that the drops stayed
        # confined to the probe's noise-page profile.
        "oob_boxes": {
            "total": sum(oob.values()),
            "pages_with_drops": {str(k): v for k, v in sorted(oob.items()) if v},
        },
        "threshold_sweep": _threshold_sweep(sidecar, args.accept_rate),
        # S2.1.6 (#40): the DT-12 S2.2 measurement feed — per-page order_qa over the as-built
        # detector, the exact metric #30 re-gates on (mean + pass@0.85).
        "order_qa": {**_order_qa_summary(order_qa_values), "front_end_wall_seconds": front_end_wall},
        # DT-7 amendment (auto-propose): the column policy this book's own col2_score distribution
        # suggests — a PROPOSAL Ben ratifies + freezes; the live run uses the manifest's frozen 0.50/0.15.
        "column_policy_auto_propose": {
            "bimodal": proposal.bimodal,
            "reason": proposal.reason,
            "decision_threshold": proposal.decision_threshold,
            "hysteresis_margin": proposal.hysteresis_margin,
            "valley": list(proposal.valley) if proposal.valley else None,
            "low_cluster_mass": proposal.low_cluster_mass,
            "high_cluster_mass": proposal.high_cluster_mass,
            "ratified_in_manifest": seg["column_detector"],
        },
    }

    try:
        tripwire = assert_auto_absent_tripwire(sidecar, outcome.token_counts)
    except GeometryError as exc:
        # P-5 fired: publish nothing, but PERSIST the evidence behind the trip.
        _write_stats("tripwire_blocked", **sections)
        raise SystemExit(f"auto-absent tripwire fired (exit 13): {exc}") from exc
    sections["tripwire"] = tripwire

    # The DT-10 human-review worklist — one candidate per routed page; the per-stage volume bound
    # (P-6/G-13) hard-fails the run if any gate floods the queue (re-design the classifier, never
    # lower the bar). Built AFTER the tripwire so a blocked run publishes no worklist either.
    try:
        worklist = build_worklist(
            all_routes, witness_id="copy1", n_pages=page_count,
            review_fraction_max=review_fraction_max, fingerprint=fingerprint,
        )
    except GeometryError as exc:
        sections["worklist_volume_breach"] = str(exc)
        _write_stats("review_volume_blocked", **sections)
        raise SystemExit(f"review volume bound breached (exit 13): {exc}") from exc
    stage_counts = Counter(c.stage for c in worklist.candidates)
    sections["worklist"] = {
        "candidates": len(worklist.candidates),
        "by_stage": dict(stage_counts),
        "review_fraction_max": review_fraction_max,
        "fingerprint": fingerprint,
    }

    sidecar_path = save_geom_sidecar(workspace, sidecar)
    worklist_out = save_worklist(workspace, worklist)
    # #46: render the per-candidate review overlays (page-bounded to the routed pages) + the
    # read-only HTML evidence sheet — the eyes-half of DT-10; verdicts still enter only via the CLI.
    pages_by_scan = {pg.page: pg for pg in pages}
    overlays_rendered = _render_worklist_overlays(worklist, pages_by_scan, pdf_path, workspace)
    sheet_path = write_review_sheet(workspace, "per_la_liberta", worklist, sweep=sections["threshold_sweep"])
    sections["worklist"]["overlays_rendered"] = overlays_rendered
    _write_stats("ok", **sections)

    print(f"\nsidecar -> {sidecar_path}")
    print(f"worklist -> {worklist_out}  ({len(worklist.candidates)} candidates: {dict(stage_counts)})")
    print(f"review sheet -> {sheet_path}  ({overlays_rendered} overlays)")
    print(f"pages: {dict(page_status)}   atoms: {dict(atom_status)}   pending: {pending}")
    print(f"coverage: {dict(sidecar.coverage)}")
    print(f"tripwire: massA={tripwire['absent_token_mass_rate']:.4f} "
          f"proseB={tripwire['prose_absent_rate']:.4f} flags={len(tripwire['flags'])}")
    oqa = sections["order_qa"]
    print(f"\norder_qa (S2.2 feed, DT-12): {oqa['n_pages']} matched pages, "
          f"mean {oqa['mean']:.4f}, pass@0.85 {oqa['pass_at_0_85']:.3f} "
          f"({front_end_wall:.0f}s front-end)" if oqa["n_pages"] else "\norder_qa: no matched pages")
    prop = sections["column_policy_auto_propose"]
    if prop["bimodal"]:
        print(f"column policy auto-propose (DT-7): threshold {prop['decision_threshold']:.3f} / "
              f"margin {prop['hysteresis_margin']:.3f} — a PROPOSAL; live run uses manifest "
              f"{prop['ratified_in_manifest']}")
    else:
        print(f"column policy auto-propose (DT-7): ABSTAIN — {prop['reason']}")
    sweep = sections["threshold_sweep"]
    print(f"\nthreshold sweep (DT-8 procedure — applied cut {sweep['applied_cut']}):")
    for t, c in sweep["ladder"].items():
        mark = " <- applied" if float(t) == round(sweep["applied_cut"], 4) else ""
        print(f"  >= {t}: {c['accepted']} accepted / {c['routed']} routed{mark}")
    for g in sweep["gap_candidates"]:
        print(
            f"  gap candidate: cut {g['candidate_cut']:.4f} (width {g['width']:.4f}, "
            f"{g['below']:.4f}..{g['above']:.4f}) -> {g['accepted']} accepted / {g['routed']} routed"
        )
    zone = ", ".join(f"p{n}={v:.4f}" for n, v in sweep["decision_zone"].items())
    print(f"  decision zone (±{SWEEP_ZONE_HALF_WIDTH}): {zone or 'empty'}")
    print("  to re-cut: re-run with --accept-rate X (~3 min from the box cache)")


if __name__ == "__main__":
    main()
