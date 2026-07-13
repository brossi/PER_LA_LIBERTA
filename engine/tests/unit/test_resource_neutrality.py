"""S3.0.6 (#28) — resource/normalizer neutrality guard (invariant 11).

The two S3.0 modules that turn the language profile's resources + fold policy into versions —
``dictionaries/normalization.py`` (the fold ops) and ``structure/lineage.py`` (the digest +
``ResourceLineage``) — are engine **core**: they read every dictionary path, frequency-file name, and
accent table from ``cfg.language``, baking none of them (``docs/s3_0_plan.md`` D-A/D-F, invariant 11).

The real protection is **behavioural** — ``test_resource_lineage`` invariant 10
(``test_synthetic_profile_breaks_on_any_bake``: a non-Latin, case-sensitive, non-Italian-accent
profile) and the ``fake_assets`` binding tests fail the moment a path/table is baked, regardless of
its spelling. This literal scan is **belt-and-suspenders** for the specific reintroduction the #27
pre-commit audit surfaced: the existing neutrality tiers glob these files but their denylists do not
cover *resource* identity. ``test_structure_neutrality`` forbids source-language **headings /
guillemets / part-counts** (and globs ``structure/lineage.py``); ``test_core_neutrality`` forbids the
book's **entities / typeface** (across all of core). **Neither** would catch a baked dictionary dir
(``zingarelli_1922``), the frequency filename (``it_combined.txt``), the source-language name, or an
Italian accent-fold literal in these two modules — so this scan adds that orthogonal axis. (The plan's
§11 named only ``normalization.py``; the #27 audit widened it to ``lineage.py`` too, since the same
gap applies there.)

Scope note: unlike the *language plugin* (which legitimately carries Italian-language opinion — its
job), these two modules are language-**neutral** core, so even a prose mention of the source language
is a leak here; the fix is to say "the source language", not name it. The denylist is the known-leak
set, not a completeness proof — a semantic bake with no literal (an Italian-only fold assumption
spelled neutrally) is caught by invariant 10, not this scan. A naive ``.lower()`` / ``[a-z]`` scan is
deliberately **excluded**: it false-positives on neutral code, and the case axis is already pinned
behaviourally (invariant 10) + by ``test_chunk_key_*`` in the battery.

Red-first (§9): ``test_no_resource_literal_in_the_s3_0_modules`` is green on the clean modules;
``test_guard_catches_a_planted_literal`` is the non-vacuity proof — it plants each forbidden term and
asserts the *same* scan flags it, so the guard is known to go red on a real reintroduction.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src" / "engine"
# Exactly the two S3.0 resource/normalizer modules — NOT a glob: the scan's claim is about these
# two specific neutral-core files, and a broad glob would re-cover ground the sibling scans already
# hold (and risk false-positives on files allowed to name the language).
RESOURCE_MODULES = [
    SRC / "dictionaries" / "normalization.py",
    SRC / "structure" / "lineage.py",
]

# Source-language *resource* identity that must live in the language profile, never baked in these
# two modules. Four categories, matching the #27-audit-named gap:
FORBIDDEN = [
    # the profile's period-dictionary `dir` stems (cfg.language.period_dictionaries) — engine core
    # resolves them through require_asset, never names them
    "zingarelli", "edgren", "hoare",
    # the profile's frequency_dictionary filename stem
    "it_combined",
    # the source-language name — these modules are neutral core, not the language plugin, so even a
    # docstring mention leaks ("the source language" is the neutral phrasing)
    "italian", "italiano",
    # a baked accent-fold table: the Italian accent inventory (profile `accent_inventory`). IGNORECASE
    # also covers the upper-case forms (À/È/…). The behavioural guard (invariant 10) is the real
    # protection; this catches a literal `_ACCENT_MAP` / fold string reappearing in core.
    "à", "è", "ì", "ò", "ù", "é",
]


def _hits(term: str, files: list[Path]) -> list[str]:
    """Every ``file:lineno: line`` where ``term`` appears (case-insensitive) — the leak report. The
    real-scan test and the planted-literal proof share this one function, so the proof exercises the
    *same* path the guard does (not a re-implemented copy that could drift)."""
    pat = re.compile(re.escape(term), re.IGNORECASE)
    hits: list[str] = []
    for f in files:
        for lineno, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if pat.search(line):
                hits.append(f"{f.name}:{lineno}: {line.strip()}")
    return hits


def test_s3_0_modules_exist():
    # Guard against a vacuous green: a renamed/removed module would make every scan below pass by
    # examining nothing (the single-fixture-blind-spot trap).
    missing = [str(m) for m in RESOURCE_MODULES if not m.is_file()]
    assert not missing, f"S3.0 module(s) not found, scan would pass vacuously: {missing}"


@pytest.mark.parametrize("term", FORBIDDEN)
def test_no_resource_literal_in_the_s3_0_modules(term):
    hits = _hits(term, RESOURCE_MODULES)
    assert not hits, (
        f"source-language resource literal {term!r} leaked into a neutral S3.0 module — read it "
        f"from cfg.language instead:\n" + "\n".join(hits)
    )


@pytest.mark.parametrize("term", ["zingarelli", "à"])
def test_guard_catches_a_planted_literal(tmp_path, term):
    # The non-vacuity proof: plant a forbidden term in a throwaway file and assert the SAME scan
    # flags it. Without this, an over-narrow regex could silently stop catching reintroductions.
    # Two representatives, one per input axis ``_hits`` actually distinguishes (#56): a plain-ASCII
    # stem, and an accented char (Unicode case-insensitive matching is a distinct failure mode —
    # IGNORECASE must also catch À). The full per-term sweep re-proved one code path 12 times.
    planted = tmp_path / "leak.py"
    planted.write_text(f'RESOURCE_DIR = "{term} ..."\n', encoding="utf-8")
    assert _hits(term, [planted]), f"the guard failed to catch a planted {term!r} — scan is vacuous"
