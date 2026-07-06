"""S2.1.4 density-band calibration probe (issue #38; DT-6 human checkpoint).

Extracts the four DT-6 density features — ink fraction (binarized pixmap), box count, token yield
(alpha-token count / box count), mean token length — for the calibration page set (the S2.0
stratified strata + the run-report's boundary/routed pages). OCR boxes are reused from the #37
slice-1 box cache (no re-OCR); ink fraction is rendered from the local LOC PDF (a ratio, so
dpi-robust — this probe renders at 150 dpi for speed).

Output: a features table (stdout) + a PROPOSED labeled calibration set + proposed band values to
``books/per_la_liberta/review/density_calibration.proposed.json`` — the artifact handed to Ben for
confirmation. It is NOT ground truth until Ben ratifies (the DT-6 human checkpoint); the ratified
labels land in ``density_calibration.json`` and the band values in ``manifest.json``.

Run (PDF + box cache present locally):
    cd engine && uv run python books/per_la_liberta/probes/s2_1_density_probe.py
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

import fitz  # PyMuPDF — declared engine dependency

from engine.structure.segmentation import (
    SEGMENTATION_VERSION,
    DensityClassifier,
    ink_fraction_from_pixmap,
    page_density_features,
)

# PROPOSED band values (Ben ratified the 5 density bands at the 2026-07-06 checkpoint; the two cover
# params are proposed from this calibration — covers observed at leaves 1/272/278, all ink >= 0.97,
# leaf 272 sits 6 from the end; content tops out at ink 0.115). NOT ground truth until Ben rules the
# two cover numbers; the labels this produces are the handoff for that ruling.
PROPOSED_BANDS = dict(
    yield_content_min=0.70,
    box_content_min=40,
    ink_blank_max=0.50,
    ink_dark_min=0.60,
    confidence_margin=0.05,
    cover_edge_leaves=7,
    ink_saturation_min=0.90,
)

BOOK = Path(__file__).resolve().parents[1]
PDF = Path(os.environ.get(
    "PLL_LOC_PDF",
    BOOK.parents[2] / "public-gdcmassbookdig-perlalibertdal00cres-perlalibertdal00cres.pdf",
))
BOX_CACHE = BOOK / "work" / "data" / "geometry" / "_boxes_dpi300.json"
OUT = BOOK / "review" / "density_calibration.proposed.json"
INK_DPI = int(os.environ.get("PLL_DENSITY_DPI", "150"))

# Calibration pages: (scan_page, semantic hint from S2.0 strata + the #37 run report). The hint is
# context for labelling, NOT the label — the features decide, Ben confirms.
CALIBRATION = [
    (1, "cover"), (2, "front_matter"), (3, "front_matter"), (4, "scan_target_noise"),
    (5, "front_matter_1col"), (6, "ghost_verso_658boxes"),
    (7, "chapter_open_1col"), (9, "chapter_open_2col"), (127, "chapter_open_2col"),
    (21, "dense_prose"), (28, "dense_prose"), (50, "dense_prose"), (57, "dense_prose"),
    (100, "dense_prose"), (140, "dense_prose"), (150, "dense_prose"), (204, "dense_prose"),
    (72, "footnote_callout"), (73, "footnote_body"), (82, "footnote_body"),
    (125, "part_divider"), (126, "part_divider"),
    (168, "low_coverage_routed"), (231, "low_coverage_routed"),
    (117, "blotchy_prose_routed"), (139, "blotchy_prose_routed"),
    (75, "routed"), (192, "near_bar_routed"), (206, "routed"), (220, "routed"),
    (253, "near_bar_routed"), (265, "near_bar_routed"),
    (189, "orsini_prose"), (193, "orsini_prose"), (269, "toc_smalltype"),
    (272, "back_matter"), (273, "back_matter_noise"), (274, "back_matter_noise"),
    (275, "back_matter"), (276, "back_matter_noise"), (277, "back_matter"), (278, "back_matter"),
]


def _boxes_by_page() -> dict[int, list]:
    cache = json.loads(BOX_CACHE.read_text())
    out: dict[int, list] = {}
    for pg in cache["pages"]:
        # words are [text, x0, y0, x1, y1]; the feature seam reads only .text
        out[pg["page"]] = [SimpleNamespace(text=w[0]) for w in pg["words"]]
    return out


def run() -> None:
    boxes_by_page = _boxes_by_page()
    n_leaves = json.loads(BOX_CACHE.read_text())["last"]
    clf = DensityClassifier(**PROPOSED_BANDS)
    doc = fitz.open(PDF)
    rows = []
    print(f"# S2.1.4 density calibration  pdf={PDF.name}  ink_dpi={INK_DPI}  {SEGMENTATION_VERSION}\n")
    hdr = f"{'scan':>4} {'hint':<22} {'ink':>6} {'boxes':>6} {'yield':>6} {'meanlen':>7} {'label':<14} {'conf':>6}"
    print(hdr)
    for scan, hint in CALIBRATION:
        boxes = boxes_by_page.get(scan, [])
        pm = doc[scan - 1].get_pixmap(dpi=INK_DPI)
        feats = page_density_features(ink_fraction=ink_fraction_from_pixmap(pm), boxes=boxes)
        verdict = clf.classify(feats, leaf_index=scan, n_leaves=n_leaves)
        rows.append({"scan": scan, "hint": hint, "ink_fraction": round(feats.ink_fraction, 4),
                     "box_count": feats.box_count, "token_yield": round(feats.token_yield, 4),
                     "mean_token_length": round(feats.mean_token_length, 3),
                     "proposed_label": verdict.band.value, "confidence": round(verdict.confidence, 4)})
        print(f"{scan:>4} {hint:<22} {feats.ink_fraction:6.4f} {feats.box_count:6d} "
              f"{feats.token_yield:6.4f} {feats.mean_token_length:7.3f} {verdict.band.value:<14} "
              f"{verdict.confidence:6.4f}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "note": "PROPOSED labels + bands — not ground truth until Ben ratifies the two cover numbers "
                "(cover_edge_leaves, ink_saturation_min) at the DT-6 human checkpoint.",
        "segmentation_version": SEGMENTATION_VERSION,
        "ink_dpi": INK_DPI,
        "n_leaves": n_leaves,
        "box_cache_engine": json.loads(BOX_CACHE.read_text())["engine_id"],
        "proposed_bands": clf.params,
        "features": rows,
    }, indent=2))
    print(f"\nwrote {OUT.relative_to(BOOK.parents[2])}")


if __name__ == "__main__":
    run()
