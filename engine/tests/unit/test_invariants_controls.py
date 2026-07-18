"""Two invariant controls folded into M4b (``docs/invariants.md`` §9 / §6).

  - **I9 — determinism / idempotency.** A run-twice-under-different-``PYTHONHASHSEED`` check: the M4b
    deterministic surfaces (triage's pure resolution passes + cleanup's text/flag generation) produce
    byte-identical output across hash seeds. Catches a future set/dict iteration order leaking into
    written output — which a single golden run can miss (it matches once, then a regeneration flips).
  - **I6 — governance ↔ code consistency (the mechanizable sliver).** Every ``test_*`` name cited in
    the standing decision record (``docs/`` + ``docs/decisions/``) resolves to a real test module or
    function — no dangling reference left by a rename/removal. Scoped (S2.1/#35): frozen
    point-in-time snapshots (``docs/probes/``, ``*discussion*`` plan-dialogue archives) are outside
    the scan. A ratified plan's not-yet-built test homes and exact non-test schema identifiers use
    separate self-cleaning registries below.
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


# Forward references from a RATIFIED plan, not dangling renames: s2_1_plan.md's G-matrix Home
# column cites the test homes of children not yet built. Each entry names the child that births
# the file; the test asserts an entry does NOT yet resolve, so the moment a child lands its entry
# turns into a failure and must be deleted here — self-cleaning ON RESOLUTION. Two honest
# residuals the mechanism cannot close: an entry excuses its name in ANY doc (name-scoped, not
# doc-scoped), and a child that ships its tests under a *different* name never resolves the entry,
# leaving the plan citation dangling behind it — pruning that case belongs to the child-close
# review (the issue tags below exist for that review, not for this test).
PENDING_TEST_HOMES: dict[str, str] = {
    # (empty) — test_geometry_e2e landed with #39 (S2.1.5); its entry was deleted on resolution.
}

# Exact data/schema identifiers whose ``test_*`` spelling is not a test citation. This is separate
# from PENDING_TEST_HOMES: these names are not expected to become tests. The governance control
# below requires each exemption to remain present and unresolved, so removed or newly colliding
# entries clean themselves rather than becoming a permanent blanket allowlist.
NON_TEST_IDENTIFIERS: dict[str, str] = {
    "test_cmd": "mutation-run artifact JSON field naming the invoked test command",
}


def _unresolved_citations(
    cited: dict[str, list[str]], actual: set[str]
) -> dict[str, list[str]]:
    return {
        name: srcs
        for name, srcs in cited.items()
        if not _resolves(name, actual)
        and name not in PENDING_TEST_HOMES
        and name not in NON_TEST_IDENTIFIERS
    }


def test_governance_docs_cite_only_resolvable_test_names():
    actual = _actual_test_names()
    assert "test_cleanup_golden" in actual, "self-check: the new cleanup tests are discoverable"

    # I6's scope (docs/invariants.md) is the *decision record* — the divergence ledger, branch
    # register, invariants.md, port_discipline.md, decisions/, and the standing plan/tracker.
    # Point-in-time probe/audit reports under docs/probes/ are dated snapshots, not the decision
    # record: an audit that documents a test *removal* legitimately names the removed test, so holding
    # those reports to "every cited name still resolves" would forbid recording what was cut. Excluded.
    # Same class, by naming convention: any ``*discussion*`` doc — a plan's verbatim audit-dialogue
    # snapshot, frozen once its plan is distilled/ratified (never edited after), so it cannot chase
    # renames either. The repo holds three spellings of the convention (``-discussion.md``,
    # ``_discussion.md``, ``_DISCUSSION.md``), hence the case-folded substring match.
    probes_dir = DOCS_DIR / "probes"
    cited: dict[str, list[str]] = {}
    for doc in sorted(DOCS_DIR.rglob("*.md")):
        if probes_dir in doc.parents or "discussion" in doc.name.lower():
            continue
        for m in re.finditer(r"\btest_[A-Za-z0-9_]+", doc.read_text(encoding="utf-8")):
            cited.setdefault(m.group(0), []).append(str(doc.relative_to(DOCS_DIR)))

    assert cited, "no test names cited in the governance docs — the scan is hollow"

    stale_pending = {name: issue for name, issue in PENDING_TEST_HOMES.items() if _resolves(name, actual)}
    assert not stale_pending, (
        f"PENDING_TEST_HOMES entries now resolve — the child landed; delete them: {stale_pending}"
    )

    stale_non_test = {
        name: reason for name, reason in NON_TEST_IDENTIFIERS.items() if name not in cited
    }
    assert not stale_non_test, (
        "NON_TEST_IDENTIFIERS entries no longer occur in governed docs; delete them: "
        f"{stale_non_test}"
    )
    colliding_non_test = {
        name: reason for name, reason in NON_TEST_IDENTIFIERS.items() if _resolves(name, actual)
    }
    assert not colliding_non_test, (
        "NON_TEST_IDENTIFIERS entries now resolve as tests; delete the exemptions: "
        f"{colliding_non_test}"
    )

    unresolved = _unresolved_citations(cited, actual)
    assert not unresolved, (
        "governance docs cite test names that no longer resolve (rename/removal left a dangling "
        f"reference):\n{unresolved}"
    )


def test_governance_citation_filter_ignores_only_registered_non_test_identifiers():
    cited = {
        "test_real": ["plan.md"],
        "test_cmd": ["plan.md"],
        "test_removed": ["plan.md"],
    }

    assert _unresolved_citations(cited, {"test_real"}) == {
        "test_removed": ["plan.md"]
    }
