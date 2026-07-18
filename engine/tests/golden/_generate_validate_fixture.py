"""Dev-time generator for the validate golden fixture. NOT a test (leading underscore) and
NOT run at test time.

It imports the live top-level ``validate.py`` and runs it over the frozen PLL inputs to
freeze the *expected* report — so the golden's values come from the independent live
implementation, and ``test_validate_golden`` (which imports only ``engine.steps.validate``)
proves the port reproduces it. The reconciled witness is frozen here; the cleaned text is
frozen by ``_generate_chapterids_fixture.py`` (single owner) and read from ``inputs/``.

One label is generalised: the live check ``italian_char_coverage`` → ``char_coverage`` (the
engine carries no language opinion in its output). Its data is reproduced verbatim.

Refresh (rare; only after a deliberate live-tree change to the cleaned/reconciled text):

    uv run python tests/golden/_generate_validate_fixture.py

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

LIVE_RECONCILED = REPO_ROOT / "data" / "reconciled_chapters.json"
FROZEN_CLEAN = INPUTS_DIR / "clean.md"  # frozen by the chapter-id fixture generator


def build_expected() -> dict:
    sys.path.insert(0, str(REPO_ROOT))
    import validate as live  # the top-level live script

    # Freeze the reconciled witness the engine's word_count check reads.
    shutil.copyfile(LIVE_RECONCILED, INPUTS_DIR / "reconciled_chapters.json")

    # Run the live validator: it reads <output>/italian_clean.md + <data>/reconciled.json and
    # writes <data>/validation_report.json. The live script hardcodes the name
    # ``italian_clean.md``, so stage the engine's generic ``clean.md`` under that name in a temp
    # dir (which also keeps the report write out of inputs/).
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        shutil.copyfile(FROZEN_CLEAN, tmp / "italian_clean.md")
        shutil.copyfile(INPUTS_DIR / "reconciled_chapters.json", tmp / "reconciled_chapters.json")
        report = live.validate(tmp, tmp)

    # Transform the live report to the engine's contract: (1) generalise the one language
    # label italian_char_coverage -> char_coverage; (2) uniform schema {overall, issues,
    # checks} with a top-level report-level ``issues`` channel (empty on this passing run).
    for check in report["checks"]:
        if check["name"] == "italian_char_coverage":
            check["name"] = "char_coverage"
    return {
        "overall": report["overall"],
        "issues": report.get("issues", []),
        "checks": report["checks"],
    }


def main() -> int:
    if not FROZEN_CLEAN.exists():
        print(f"Frozen clean text missing: {FROZEN_CLEAN}\n"
              f"Run _generate_chapterids_fixture.py first.", file=sys.stderr)
        return 1
    if not LIVE_RECONCILED.exists():
        print(f"Live reconciled missing: {LIVE_RECONCILED}", file=sys.stderr)
        return 1
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    report = build_expected()
    out = DATA_DIR / "validation_report_expected.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nWrote golden report ({report['overall']}) → {out.relative_to(REPO_ROOT)}")
    print(f"Froze reconciled witness → "
          f"{(INPUTS_DIR / 'reconciled_chapters.json').relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
