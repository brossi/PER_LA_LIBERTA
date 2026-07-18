"""Dev-time generator for the chapter-id golden fixture. NOT a test (pytest ignores
the leading underscore) and NOT run at test time.

It is the only place that imports the live top-level pipeline (utils/translate/typeset).
It runs those functions over the committed live artifacts to freeze the *expected*
chapter identities, plus a frozen copy of the inputs the engine plugin will reproduce
from. The golden test then compares the engine plugin's output to this frozen expectation
without ever importing top-level code — so a divergence in the hardest refactor is caught.

Refresh (rare; only after a deliberate live-tree change to chapter structure):

    uv run python tests/golden/_generate_chapterids_fixture.py

Asserts the live tree is reachable; writes nothing into the live tree.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

GOLDEN_DIR = Path(__file__).resolve().parent
# golden -> tests -> engine -> repo root
REPO_ROOT = GOLDEN_DIR.parents[2]
INPUTS_DIR = REPO_ROOT / "engine" / "books" / "per_la_liberta" / "inputs"
DATA_DIR = GOLDEN_DIR / "data"

LIVE_CLEAN = REPO_ROOT / "output" / "italian_clean.md"
LIVE_START_PAGES = REPO_ROOT / "data" / "chapter_start_pages.json"


def _page_ranges(start_pages: dict) -> dict[str, tuple[int, int]]:
    """Reproduce typeset.py:732-735 — end = next.start_scan - 1, last from fallback."""
    chapters = start_pages.get("chapters", [])
    last_scan = start_pages.get("_last_scan_page", 278)
    ranges: dict[str, tuple[int, int]] = {}
    for idx, entry in enumerate(chapters):
        start = entry["start_scan"]
        end = chapters[idx + 1]["start_scan"] - 1 if idx + 1 < len(chapters) else last_scan
        ranges[entry["id"]] = (start, end)
    return ranges


def build_expected() -> list[dict]:
    sys.path.insert(0, str(REPO_ROOT))
    from translate import _italian_to_english_title, parse_italian_markdown
    from typeset import _slug

    text = LIVE_CLEAN.read_text(encoding="utf-8")
    start_pages = json.loads(LIVE_START_PAGES.read_text(encoding="utf-8"))
    ranges = _page_ranges(start_pages)

    parsed = parse_italian_markdown(text)
    content = [c for c in parsed if not c.get("is_structural")]

    # Track the active part by parse_md id prefix (document order) — collision-free,
    # unlike keying on title ("Capitolo Primo" appears in both parts). The short-id
    # counter resets at each part transition, matching utils.build_chapter_id_map.
    part_meta = {"p1": ("Parte Prima", 1), "p2": ("Parte Seconda", 2)}
    cur_part: str | None = None
    counter = 0

    expected = []
    for ch in content:
        title = ch["title"]
        parse_md = ch["id"]
        ps = "p1" if parse_md.startswith("p1_") else "p2" if parse_md.startswith("p2_") else None
        if ps != cur_part:
            cur_part = ps
            counter = 0
        if ps:
            pt, partno = part_meta[ps]
            counter += 1
            short = f"{ps}_ch{counter:02d}"
            html_slug = f"{_slug(pt)}-{_slug(title)}"
            part = partno
            number: int | None = counter
        else:
            short = _slug(title).replace("-", "_")  # prefazione; no part prefix
            html_slug = _slug(title)
            part = 0
            number = None
        rng = ranges.get(parse_md)
        expected.append(
            {
                "short": short,
                "parse_md": parse_md,
                "html_slug": html_slug,
                "english_title": _italian_to_english_title(title),
                "part": part,
                "number": number,
                "title": title,
                "page_range": list(rng) if rng else None,
            }
        )
    return expected


def main() -> int:
    if not LIVE_CLEAN.exists():
        print(f"Live input missing: {LIVE_CLEAN}", file=sys.stderr)
        return 1
    INPUTS_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Freeze the inputs the engine reproduces from (the live ``italian_clean.md`` becomes the
    # engine's generic ``clean.md``).
    shutil.copyfile(LIVE_CLEAN, INPUTS_DIR / "clean.md")
    shutil.copyfile(LIVE_START_PAGES, INPUTS_DIR / "chapter_start_pages.json")

    expected = build_expected()
    out = DATA_DIR / "chapterids_expected.json"
    out.write_text(json.dumps(expected, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(expected)} chapter identities → {out.relative_to(REPO_ROOT)}")
    print(f"Froze inputs → {INPUTS_DIR.relative_to(REPO_ROOT)}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
