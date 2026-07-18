"""S2.1.5 column / reading-order detector run report (issue #39; DT-7 checkpoint).

Produces the evidence Ben ratifies the DT-7 column-decision policy against — the ``col2_score``
(valley-depth x column-balance) distribution over every text-bearing PLL page, from which the
``decision_threshold`` and ``hysteresis_margin`` are proposed. The values are PROPOSED here, NOT
ratified: the DT-7 rulings belong to Ben at this run report (like the DT-8 thresholds at the
slice-1 report), so the probe prints a proposal + rationale and writes them nowhere authoritative
(no manifest write). Once ratified, the column-detector params land in ``manifest.json``
``segmentation.column_detector`` and the labeled evidence in ``review/``.

Two views:
  1. col2_score distribution (box cache only — layout is a pure function of box coordinates): the
     histogram + the two-column detection rate at the proposed threshold + the count landing in the
     proposed hysteresis band (the pages the cross-page prior / worklist would arbitrate).
  2. Full front-end (PDF present): the density gate (#38 ratified bands) -> the cross-page prior
     (resolve_reading_columns) -> the per-outcome counts (evidence-2col / evidence-1col / prior /
     abstain), i.e. how often the prior actually decides and how often the book routes.

Run (box cache present locally; PDF optional for view 2):
    cd engine && uv run python books/per_la_liberta/probes/s2_1_column_probe.py
"""
from __future__ import annotations

import json
import os
import statistics
from pathlib import Path
from types import SimpleNamespace

from engine.structure import (
    COLUMN_DETECTOR_VERSION,
    ColumnDetector,
    DensityClassifier,
    PageColumnInput,
    detect_columns,
    resolve_reading_columns,
)

BOOK = Path(__file__).resolve().parents[1]
MANIFEST = BOOK / "manifest.json"
BOX_CACHE = BOOK / "work" / "data" / "geometry" / "_boxes_dpi300.json"
PDF = Path(os.environ.get(
    "PLL_LOC_PDF",
    BOOK.parents[2] / "public-gdcmassbookdig-perlalibertdal00cres-perlalibertdal00cres.pdf",
))
INK_DPI = int(os.environ.get("PLL_DENSITY_DPI", "150"))

# PROPOSED column-decision policy (NOT ratified — Ben's DT-7 checkpoint). Rationale: a clean
# two-column body page scores near 1.0 and a single-column / sparse page scores 0.0, so the score is
# strongly bimodal; the threshold sits in the empty valley between the clusters and the margin covers
# the thin ambiguous band (partial columns, footnote splits) that the cross-page prior should
# arbitrate rather than the detector guess. The distribution below is the evidence for these.
PROPOSED_DECISION_THRESHOLD = 0.5
PROPOSED_HYSTERESIS_MARGIN = 0.15


def _boxes_by_page() -> tuple[dict[int, list], dict]:
    cache = json.loads(BOX_CACHE.read_text())
    out: dict[int, list] = {}
    for pg in cache["pages"]:
        out[pg["page"]] = [
            SimpleNamespace(text=w[0], bbox=(w[1], w[2], w[3], w[4])) for w in pg["words"]
        ]
    widths = {pg["page"]: pg["width"] for pg in cache["pages"]}
    return out, {"last": cache["last"], "engine_id": cache.get("engine_id"), "widths": widths}


def _histogram(scores: list[float]) -> None:
    edges = [0.0, 0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 1.0001]
    for lo, hi in zip(edges, edges[1:]):
        n = sum(1 for s in scores if lo <= s < hi)
        bar = "#" * n
        print(f"  [{lo:.2f},{hi:.2f})  {n:4d}  {bar}")


def run() -> None:
    boxes_by_page, meta = _boxes_by_page()
    widths = meta["widths"]
    det = ColumnDetector(
        decision_threshold=PROPOSED_DECISION_THRESHOLD, hysteresis_margin=PROPOSED_HYSTERESIS_MARGIN
    )
    print(f"# S2.1.5 column detector run report  {COLUMN_DETECTOR_VERSION}  "
          f"pages={len(boxes_by_page)}  engine={meta['engine_id']}\n")

    # --- view 1: col2_score distribution (box cache only) ---
    scores = {p: detect_columns(bs, widths[p]).col2_score for p, bs in boxes_by_page.items()}
    vals = sorted(scores.values())
    t, mgn = PROPOSED_DECISION_THRESHOLD, PROPOSED_HYSTERESIS_MARGIN
    two_col = [p for p, s in scores.items() if s >= t]
    in_margin = [p for p, s in scores.items() if abs(s - t) < mgn]
    print("## col2_score distribution (valley-depth x column-balance) over all pages")
    _histogram(vals)
    print(f"\n  proposed decision_threshold = {t}   hysteresis_margin = {mgn}")
    print(f"  two-column (score >= {t}): {len(two_col)}/{len(scores)}   "
          f"(S2.0 prior: 30/37 sweep pages two-col)")
    print(f"  in hysteresis band |score - {t}| < {mgn} (prior/worklist arbitrates): {len(in_margin)}")
    if vals:
        print(f"  score min/median/max = {min(vals):.3f} / {statistics.median(vals):.3f} / {max(vals):.3f}")
    print(f"  sample in-margin pages: {sorted(in_margin)[:20]}")

    # --- view 2: full front-end (needs the PDF for the density gate) ---
    if not PDF.exists():
        print(f"\n## full front-end skipped — PDF not found at {PDF} (set PLL_LOC_PDF)")
        return
    import fitz  # PyMuPDF — lazy; only view 2 renders pixmaps

    from engine.structure import ink_fraction_from_pixmap, page_density_features

    bands = json.loads(MANIFEST.read_text())["segmentation"]["density_bands"]
    clf = DensityClassifier(**bands)
    n_leaves = meta["last"]
    doc = fitz.open(PDF)
    inputs: list[PageColumnInput] = []
    for p in sorted(boxes_by_page):
        bs = boxes_by_page[p]
        pm = doc[p - 1].get_pixmap(dpi=INK_DPI)
        feats = page_density_features(ink_fraction=ink_fraction_from_pixmap(pm), boxes=bs)
        density = clf.classify(feats, leaf_index=p, n_leaves=n_leaves)
        inputs.append(PageColumnInput(density=density, evidence=detect_columns(bs, widths[p])))
    verdicts = resolve_reading_columns(inputs, det)

    def _count(pred) -> int:
        return sum(1 for v in verdicts if pred(v))

    print("\n## full front-end: density gate (#38 bands) -> cross-page prior (R8)")
    print(f"  evidence 2-col : {_count(lambda v: v.n_cols == 2 and v.n_cols_source == 'evidence')}")
    print(f"  evidence 1-col : {_count(lambda v: v.n_cols == 1 and v.n_cols_source == 'evidence')}")
    print(f"  prior-inherited: {_count(lambda v: v.n_cols_source == 'prior')}")
    print(f"  routed/abstain : {_count(lambda v: v.routed)}")
    print(f"  boxes-untrusted: {_count(lambda v: v.signal == 'boxes-untrusted')}")
    print("\n(PROPOSED policy — Ben ratifies decision_threshold + hysteresis_margin from this report.)")


if __name__ == "__main__":
    run()
