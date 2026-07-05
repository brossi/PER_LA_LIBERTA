"""S2.1.3 probe — the band-drift evidence behind the P-2 supersession (3x -> 16x, ruled
2026-07-05). Findings doc: ``engine/docs/probes/s2_1_band_drift.md``.

Three read-only analyses over the banked box cache + copy3's ground-truth page map:

  drift    - blind locate under a chosen band; delta (assigned - truth) by truth-page bucket,
             worst failing atoms with their truth-page vs assigned-page bag overlap.
  ceiling  - same, wide band (the remedy): delta distribution, <=5-token slice, per-bucket table.
  centers  - the band-center PRIOR's error curve (linear cumulative-ratio map vs truth) plus
             per-block bag-token density — the mechanism (end-matter token deserts).

Usage (from ``engine/``):
  uv run python books/per_la_liberta/probes/s2_1_band_drift_probe.py centers
  uv run python books/per_la_liberta/probes/s2_1_band_drift_probe.py drift          # ruled band
  uv run python books/per_la_liberta/probes/s2_1_band_drift_probe.py drift 3762     # the old 3x
  uv run python books/per_la_liberta/probes/s2_1_band_drift_probe.py ceiling        # 20k band

Requires the complete box cache (``work/data/geometry/_boxes_dpi300.json``); run the slice-1
runner first if absent. Note the centers analysis approximates the live ``_bands`` center
formula (cumulative BAG-mass ratio) with the page-count-linear map — on this scan the two agree
because bag mass per page is near-uniform (441-521 tokens/page); the drift analysis uses the
real code path.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

BOOK_DIR = Path(__file__).resolve().parents[1]
ENGINE_ROOT = BOOK_DIR.parents[1]
sys.path.insert(0, str(BOOK_DIR))

from engine.paths import BookWorkspace  # noqa: E402
from engine.structure import load_stream, match_stream, normalize_tokens  # noqa: E402

from run_s2_1_slice1 import _pages_from_cache  # noqa: E402

CACHE = BOOK_DIR / "work" / "data" / "geometry" / "_boxes_dpi300.json"


def _load():
    cached = json.loads(CACHE.read_text(encoding="utf-8"))
    if not cached.get("complete"):
        raise SystemExit(f"box cache incomplete: {CACHE} — run the slice-1 runner first")
    pages = _pages_from_cache(cached["pages"])
    workspace = BookWorkspace.for_book("per_la_liberta", BOOK_DIR.parent)
    copy3 = load_stream(workspace, "copy3")
    single = [
        a
        for a in copy3.atoms
        if a.processing_scope == "included"
        and a.page_range[0] == a.page_range[1]
        and a.page_range[0] >= 0
    ]
    return pages, copy3, single


def drift(band: int | None) -> None:
    pages, copy3, single = _load()
    kwargs = {"page_accept_rate": 0.0, "atom_match_floor": 0.0}
    if band is not None:
        kwargs["band_tokens"] = band
    outcome = match_stream(copy3, pages, **kwargs)
    bags = {
        pg.page: Counter(t for wb in pg.words for t in normalize_tokens(wb.text)) for pg in pages
    }
    deltas = Counter()
    bucket = defaultdict(list)
    rows = []
    for a in single:
        truth = a.page_range[0]
        d = outcome.atom_pages[a.atom_id].assigned - truth
        deltas[d] += 1
        bucket[truth // 20 * 20].append(d)
        rows.append((a, truth, d))
    n = len(single)
    print(f"band={'ruled default' if band is None else band}: exact {deltas[0]}/{n} = {deltas[0] / n:.4f}")
    print(f"deltas: {dict(sorted(deltas.items()))}")
    small = [a for a, _, _ in rows if len(normalize_tokens(a.text)) <= 5]
    se = sum(
        1 for a in small if outcome.atom_pages[a.atom_id].assigned == a.page_range[0]
    )
    print(f"<=5-token slice: {se}/{len(small)}")
    print("truth bucket : n   exact%   mean-delta")
    for b in sorted(bucket):
        ds = bucket[b]
        print(
            f"  {b:>3}-{b + 19:>3}  : {len(ds):>3}  "
            f"{100 * sum(1 for x in ds if x == 0) / len(ds):5.1f}%   {sum(ds) / len(ds):+6.2f}"
        )
    fails = sorted(
        (r for r in rows if r[2] != 0), key=lambda r: -len(normalize_tokens(r[0].text))
    )
    print("\nworst 5 failing atoms (largest first): truth-page vs assigned-page bag overlap")
    for a, truth, d in fails[:5]:
        toks = Counter(normalize_tokens(a.text))
        total = sum(toks.values())
        assigned = outcome.atom_pages[a.atom_id].assigned
        hit_t = sum(min(c, bags.get(truth, Counter())[t]) for t, c in toks.items())
        hit_a = sum(min(c, bags.get(assigned, Counter())[t]) for t, c in toks.items())
        print(
            f"  {a.atom_id}: {total} tokens, truth p{truth} ({hit_t}/{total}) vs "
            f"assigned p{assigned} ({hit_a}/{total}), delta {d:+d}"
        )


def centers() -> None:
    pages, copy3, _ = _load()
    k = len(pages)
    atoms = [a for a in copy3.atoms if a.processing_scope == "included"]
    counts = [len(normalize_tokens(a.text)) for a in atoms]
    total = sum(counts)
    cum = 0
    bucket = defaultdict(list)
    for a, n in zip(atoms, counts):
        mid = (cum + n / 2) / total
        cum += n
        if a.page_range[0] != a.page_range[1] or a.page_range[0] < 0:
            continue
        bucket[a.page_range[0] // 20 * 20].append(1 + mid * (k - 1) - a.page_range[0])
    print(f"pages={k} stream tokens={total}")
    print("prior error (estimated - true page) by truth bucket:")
    for b in sorted(bucket):
        ds = bucket[b]
        print(f"  {b:>3}-{b + 19:>3}: mean {sum(ds) / len(ds):+6.2f}   ({min(ds):+.1f}..{max(ds):+.1f})")
    bag = [sum(len(normalize_tokens(wb.text)) for wb in pg.words) for pg in pages]
    print("\nbag-token density per 20-page block (uniform => the distortion is stream-side):")
    for i in range(0, k, 20):
        blk = bag[i : i + 20]
        print(f"  pages {i + 1:>3}-{min(i + 20, k):>3}: mean/page {sum(blk) / len(blk):6.0f}")


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "centers"
    if mode == "centers":
        centers()
    elif mode == "drift":
        drift(int(sys.argv[2]) if len(sys.argv) > 2 else None)
    elif mode == "ceiling":
        drift(20_000)
    else:
        raise SystemExit(f"unknown mode {mode!r} (centers | drift [band] | ceiling)")


if __name__ == "__main__":
    main()
