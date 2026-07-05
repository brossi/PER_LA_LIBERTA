"""S2.1.3 probe — how widespread are Tesseract's off-page (out-of-rect) boxes on the PLL scan?

Evidence for the #37 off-page ruling: the #36 backend fails loud on any box outside the page rect
(G-8, ratified), and the real slice-1 run tripped it on page 4 — a scan-target/library noise page
where Tesseract emitted 4 hallucinated wide boxes (garbage text, x1 ~1.7x the page width). This
probe OCRs every page OUTSIDE the backend (raw pymupdf) and records, per page: box count,
off-page box count, and each off-page box's text + bbox — so the ruling (drop-and-count isolated
artifacts vs keep hard fail-loud) can be sized against the whole book instead of one page.

Checkpointing: appends one JSON line per page to ``work/data/geometry/_oob_probe.jsonl`` and skips
already-probed pages on restart, so the ~40-minute pass survives interruption. Read-only against
the scan; writes nothing the pipeline consumes.

Population caveat (recorded for the ruling): this probe tests RAW ``get_text("words")`` output,
before the backend's DT-2 drop of empty-text/degenerate boxes and before its non-finite guard —
so an empty-text off-page box would count here but never trip the backend, and a NaN-coordinate
box is invisible here (NaN compares False) but raises there. On the 2026-07-05 whole-book run
every observed off-page box carried text and a non-degenerate bbox, i.e. all 20 are genuine
backend-trippers; a NaN class, if any exists, is not sized by this probe and stays fail-loud
under any ruling.

Usage (from ``engine/``):  uv run python books/per_la_liberta/probes/s2_1_oob_probe.py
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import fitz

BOOK_DIR = Path(__file__).resolve().parents[1]
ENGINE_ROOT = BOOK_DIR.parents[1]
MANIFEST = json.loads((BOOK_DIR / "manifest.json").read_text(encoding="utf-8"))
OUT = BOOK_DIR / "work" / "data" / "geometry" / "_oob_probe.jsonl"

TOLERANCE_PT = 1.0  # the backend's _RECT_TOLERANCE_PT


def main() -> None:
    pdf_path = ENGINE_ROOT.parent / MANIFEST["scan"]["pdf"]
    if not pdf_path.is_file():
        raise SystemExit(f"scan PDF not found: {pdf_path} (local-only)")
    done: set[int] = set()
    if OUT.is_file():
        for line in OUT.read_text(encoding="utf-8").splitlines():
            if line.strip():
                done.add(json.loads(line)["page"])
    OUT.parent.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(pdf_path)
    started = time.monotonic()
    with OUT.open("a", encoding="utf-8") as sink:
        for num in range(1, doc.page_count + 1):
            if num in done:
                continue
            page = doc[num - 1]
            rect = page.rect
            textpage = page.get_textpage_ocr(flags=0, language="ita", dpi=300, full=True)
            words = page.get_text("words", textpage=textpage)
            oob = [
                w for w in words
                if w[0] < rect.x0 - TOLERANCE_PT or w[1] < rect.y0 - TOLERANCE_PT
                or w[2] > rect.x1 + TOLERANCE_PT or w[3] > rect.y1 + TOLERANCE_PT
            ]
            record = {
                "page": num,
                "boxes": len(words),
                "oob": len(oob),
                "oob_detail": [
                    {"text": w[4], "bbox": [round(c, 2) for c in w[:4]]} for w in oob[:20]
                ],
            }
            sink.write(json.dumps(record, ensure_ascii=False) + "\n")
            sink.flush()
            if num % 10 == 0 or oob:
                elapsed = time.monotonic() - started
                print(f"page {num}/{doc.page_count}  boxes={len(words)} oob={len(oob)}  ({elapsed:.0f}s)")
    print("probe complete")


if __name__ == "__main__":
    main()
