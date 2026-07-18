"""Dev-time generator for the cleanup detcore golden. NOT a test (leading underscore); NOT run at
test time.

It imports the live top-level ``cleanup.py`` and runs its deterministic ``clean_text`` over the
frozen reconciled chapters — so the golden's *expected* values come from the independent live
implementation, and ``test_cleanup_golden`` (which imports only ``engine.steps.cleanup``) proves
the port reproduces them byte-for-byte. This is the equivalence proof for every M4b-D1/refinement-#4
relocation (the accent/letter-class superset + the source-noise pattern moves): a relocation that
changed output would surface here as a divergent chapter, not pass silently (I3 anti-cheat).

The golden isolates ``clean_text`` *per chapter* (``{id: {text, flags, punct_fixes}}``), NOT the
wrapped markdown — the wrapper bakes book identity (config in the engine) and would need a frozen
``chapter_pages.json``; the algorithm is what the equivalence check is about (refinement #1).

The reconciled witness is the one ``_generate_validate_fixture.py`` already froze into ``inputs/``
(read here, not re-frozen, so both goldens stay pinned to the same input). Loads the live spaCy
model + symspell — asserted reachable, never skipped (a missing model is a config error).

Refresh (rare; only after a deliberate live-tree change to ``cleanup.py`` or the reconciled text):

    uv run python tests/golden/_generate_cleanup_fixture.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

GOLDEN_DIR = Path(__file__).resolve().parent
# golden -> tests -> engine -> repo root
REPO_ROOT = GOLDEN_DIR.parents[2]
INPUTS_DIR = REPO_ROOT / "engine" / "books" / "per_la_liberta" / "inputs"
DATA_DIR = GOLDEN_DIR / "data"

FROZEN_RECONCILED = INPUTS_DIR / "reconciled_chapters.json"  # frozen by the validate fixture generator


def build_expected() -> dict:
    sys.path.insert(0, str(REPO_ROOT))
    import cleanup as live  # the top-level live script

    chapters = json.loads(FROZEN_RECONCILED.read_text(encoding="utf-8"))
    word_set = live._get_word_set()  # the live dictionary singleton (drives symspell + membership)

    expected: dict = {}
    for ch in chapters:
        text, flags, punct = live.clean_text(ch["text"], word_set)
        expected[ch["id"]] = {"text": text, "flags": flags, "punct_fixes": punct}
    return expected


def main() -> int:
    if not FROZEN_RECONCILED.exists():
        print(f"Frozen reconciled missing: {FROZEN_RECONCILED}\n"
              f"Run _generate_validate_fixture.py first.", file=sys.stderr)
        return 1
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    expected = build_expected()
    out = DATA_DIR / "cleanup_detcore_expected.json"
    out.write_text(json.dumps(expected, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    n_flags = sum(len(v["flags"]) for v in expected.values())
    print(f"\nWrote cleanup detcore golden: {len(expected)} chapters, {n_flags} flags "
          f"→ {out.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
