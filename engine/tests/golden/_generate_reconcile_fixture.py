"""Dev-time generator for the reconcile golden fixture. NOT a test (leading underscore) and
NOT run at test time.

It imports the live top-level ``reconcile.py`` and runs it over the frozen PLL OCR copies in a
temp dir, then freezes the four outputs as the *expected* golden — so the golden's values come
from the independent live implementation, and ``test_reconcile_golden`` (which imports only
``engine.steps.reconcile``) proves the port reproduces them.

Per ENGINE_M3_PLAN.md D1 / F1: the reference is **generated from live code**, never diffed
against the hand-edited ``data/reconciled_chapters.json`` (which carries out-of-band OCR fixes
from commit c66cfe3 and is *not* a clean reconcile output). This generator logs that drift so it
is documented, not hidden.

Single-owner: this generator owns freezing reconcile's *inputs* (copy{1,2,3}_raw.txt + the two
page maps) into books/.../inputs/. It does **not** touch inputs/reconciled_chapters.json — that
is the hand-edited witness frozen by _generate_validate_fixture.py and is deliberately a
different value from reconcile's clean output.

Run from the REPO ROOT (the live env has ``rapidfuzz``, which the engine env does not):

    uv run python engine/tests/golden/_generate_reconcile_fixture.py

Asserts the live tree is reachable; writes only into engine/books/.../inputs and tests/golden/data.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

GOLDEN_DIR = Path(__file__).resolve().parent
# golden -> tests -> engine -> repo root
REPO_ROOT = GOLDEN_DIR.parents[2]
INPUTS_DIR = REPO_ROOT / "engine" / "books" / "per_la_liberta" / "inputs"
DATA_DIR = GOLDEN_DIR / "data"
LIVE_DATA = REPO_ROOT / "data"

# reconcile's inputs this generator owns (single-owner). copy3_raw.txt is the Pro witness; both
# page maps are frozen because live reconcile prefers flash, falling back to pro.
FROZEN_INPUTS = [
    "copy1_raw.txt",
    "copy2_raw.txt",
    "copy3_raw.txt",
    "copy3_flash_page_map.json",
    "copy3_pro_page_map.json",
]
# reconcile's outputs -> golden (D4: reconciled_raw.txt is asserted too).
OUTPUTS = [
    "reconciled_chapters.json",
    "flagged_segments.json",
    "chapter_pages.json",
    "reconciled_raw.txt",
]


def _freeze_inputs() -> None:
    for name in FROZEN_INPUTS:
        src = LIVE_DATA / name
        if not src.is_file():
            raise SystemExit(f"Live input missing: {src}")
        shutil.copyfile(src, INPUTS_DIR / name)


def _build_expected() -> dict[str, str]:
    sys.path.insert(0, str(REPO_ROOT))
    import reconcile as live  # the top-level live script (needs rapidfuzz: run in the live env)

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        for name in FROZEN_INPUTS:
            shutil.copyfile(INPUTS_DIR / name, tmp / name)
        live.reconcile(tmp)  # reads copies + page maps from tmp, writes OUTPUTS into tmp
        out: dict[str, str] = {}
        for name in OUTPUTS:
            p = tmp / name
            if not p.is_file():
                raise SystemExit(f"live reconcile did not produce {name}")
            out[name] = p.read_text(encoding="utf-8")
    return out


def _drift_report(generated_chapters_json: str) -> str:
    """Quantify the F1 drift: clean reconcile output vs. the hand-edited live data/ file."""
    live_path = LIVE_DATA / "reconciled_chapters.json"
    if not live_path.is_file():
        return "  (live data/reconciled_chapters.json absent — no drift comparison)"
    gen = {c["id"]: c["text"] for c in json.loads(generated_chapters_json)}
    liv = {c["id"]: c["text"] for c in json.loads(live_path.read_text(encoding="utf-8"))}
    differing = sorted(cid for cid in gen if cid in liv and gen[cid] != liv[cid])
    only_gen = sorted(set(gen) - set(liv))
    only_liv = sorted(set(liv) - set(gen))
    char_delta = sum(len(liv[c]) - len(gen[c]) for c in gen if c in liv)
    lines = [
        f"  chapters: generated={len(gen)} live={len(liv)} "
        f"differing-text={len(differing)} char_delta(live-gen)={char_delta:+d}",
    ]
    if differing:
        lines.append(f"  differing ids: {', '.join(differing)}")
    if only_gen:
        lines.append(f"  only in generated: {', '.join(only_gen)}")
    if only_liv:
        lines.append(f"  only in live: {', '.join(only_liv)}")
    return "\n".join(lines)


def main() -> int:
    if not (LIVE_DATA / "copy1_raw.txt").is_file():
        print(f"Live tree not reachable at {LIVE_DATA}", file=sys.stderr)
        return 1
    INPUTS_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    _freeze_inputs()
    out = _build_expected()

    for name in OUTPUTS:
        stem, ext = name.rsplit(".", 1)
        dest = DATA_DIR / f"{stem}_expected.{ext}"
        dest.write_text(out[name], encoding="utf-8")
        print(f"  wrote {dest.relative_to(REPO_ROOT)}")

    print("\nFroze reconcile inputs →", INPUTS_DIR.relative_to(REPO_ROOT))
    print("F1 drift (clean reconcile output vs. hand-edited live data/):")
    print(_drift_report(out["reconciled_chapters.json"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
