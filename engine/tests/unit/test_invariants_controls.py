"""Two invariant controls folded into M4b (``docs/invariants.md`` §9 / §6).

  - **I9 — determinism / idempotency.** A run-twice-under-different-``PYTHONHASHSEED`` check: the M4b
    deterministic surfaces (triage's pure resolution passes + cleanup's text/flag generation) produce
    byte-identical output across hash seeds. Catches a future set/dict iteration order leaking into
    written output — which a single golden run can miss (it matches once, then a regeneration flips).
  - **I6 — governance ↔ code consistency (the mechanizable sliver).** Every ``test_*`` name cited in
    the standing decision record (``docs/`` + ``docs/decisions/``) resolves to a real test module or
    function — no dangling reference left by a rename/removal.
"""

from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parents[2]
TESTS_DIR = ENGINE_ROOT / "tests"
DOCS_DIR = ENGINE_ROOT / "docs"
DRIVER = TESTS_DIR / "_idempotency_driver.py"


# --- I9 — determinism / idempotency ------------------------------------------------------ #

def test_m4b_deterministic_surfaces_are_hashseed_independent():
    """Run the idempotency driver twice under different PYTHONHASHSEED; the digests must match."""
    digests = []
    for seed in ("0", "917"):
        proc = subprocess.run(
            [sys.executable, str(DRIVER)],
            env={**os.environ, "PYTHONHASHSEED": seed},
            capture_output=True, text=True,
        )
        assert proc.returncode == 0, f"driver failed under PYTHONHASHSEED={seed}:\n{proc.stderr}"
        digests.append(proc.stdout.strip())

    assert digests[0], "the idempotency driver produced no output"
    assert digests[0] == digests[1], (
        "M4b deterministic output changed with PYTHONHASHSEED — a set/dict iteration order leaked "
        "into written output (triage resolution or cleanup flag generation)"
    )


# --- I6 — doc-cited test names resolve --------------------------------------------------- #

def _actual_test_names() -> set[str]:
    """Every resolvable test identity: each ``test_*.py`` file stem + every ``test*`` function."""
    names: set[str] = set()
    for path in TESTS_DIR.rglob("test_*.py"):
        names.add(path.stem)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
                names.add(node.name)
    return names


def _resolves(cited: str, actual: set[str]) -> bool:
    """A cited token resolves if it names a test exactly, or is the prefix of one (a parametrised /
    family citation, e.g. the docs' ``test_require_asset_missing_*``)."""
    base = cited.rstrip("_")
    return base in actual or any(name.startswith(base + "_") for name in actual)


def test_governance_docs_cite_only_resolvable_test_names():
    actual = _actual_test_names()
    assert "test_cleanup_golden" in actual, "self-check: the new cleanup tests are discoverable"

    # I6's scope (docs/invariants.md) is the *decision record* — the divergence ledger, branch
    # register, invariants.md, port_discipline.md, decisions/, and the standing plan/tracker.
    # Point-in-time probe/audit reports under docs/probes/ are dated snapshots, not the decision
    # record: an audit that documents a test *removal* legitimately names the removed test, so holding
    # those reports to "every cited name still resolves" would forbid recording what was cut. Excluded.
    probes_dir = DOCS_DIR / "probes"
    cited: dict[str, list[str]] = {}
    for doc in sorted(DOCS_DIR.rglob("*.md")):
        if probes_dir in doc.parents:
            continue
        for m in re.finditer(r"\btest_[A-Za-z0-9_]+", doc.read_text(encoding="utf-8")):
            cited.setdefault(m.group(0), []).append(str(doc.relative_to(DOCS_DIR)))

    assert cited, "no test names cited in the governance docs — the scan is hollow"
    unresolved = {name: srcs for name, srcs in cited.items() if not _resolves(name, actual)}
    assert not unresolved, (
        "governance docs cite test names that no longer resolve (rename/removal left a dangling "
        f"reference):\n{unresolved}"
    )
