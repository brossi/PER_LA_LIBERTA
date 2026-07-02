"""S0.3 — the structure axis's test-tier spine (ENGINE_STRUCTURE_TASKS).

Per the house tiers, expressed by naming + docstring, not markers (ENGINE_STRUCTURE_PLAN §9;
only ``golden``/``integration`` are registered markers, and ``golden`` is reserved for
live-parity targets — the net-new substrate has no live referent, so its synthetic artifact is a
**fixture**, never a golden). This file is the first inhabitant of four tiers the structure
done-whens lean on; S1+ join it with per-concern tier tests:

- **fixture / round-trip** — the generator-produced CONFORMING artifact (evolved trivial →
  conforming at S4.4/B-5, s4_plan §1.5 M-S4.4) survives a write→read cycle through the real
  ``structure_map`` location accessor. Its full two-tier load is exercised in
  ``test_structure_map.py``; here it drives the location/binding spine only.
- **reference-integrity (binding)** — the fixture's declared ``schema_version`` resolves to the
  live ``STRUCTURE_MAP_SCHEMA_VERSION`` constant (``feedback_validate_bindings``).
- **property** — an invariant over synthetic book ids, not one fixture.
- **negative (fail-loud)** — the binding's failure branch raises, no skip-masking
  (``feedback_no_cheating_results``).

The fixture is produced by ``tests/fixtures/_generate_structure_fixture.py`` (dev-time,
imported here only to bind the committed bytes to the generator's current output).

Each tier's binding is proven red on violation (red-first, §9): the committed↔generator match goes
red on any drift, content *or* bytes; the version binding raises on a bumped/missing constant
(positive + negative share one ``_assert_version_binds`` chokepoint, so neither can pass while the
other regresses); the property fails on a location collision; the location test fails if the bytes
don't survive the accessor. It deliberately does *not* assert a ``json.loads(json.dumps(x)) == x``
round-trip — that exercises stdlib, never structure code.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

import engine.structure as structure
from engine.paths import BookWorkspace

FIXTURES_ROOT = Path(__file__).resolve().parents[1] / "fixtures"
FIXTURE = FIXTURES_ROOT / "structure" / "conforming_structure_map.json"
GENERATOR = FIXTURES_ROOT / "_generate_structure_fixture.py"


def _load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _load_generator():
    """Import the dev-time fixture generator by path (it is a `_`-prefixed script, not a package
    module) so a test can bind the committed fixture to the generator's current output. Exec is
    side-effect-free — ``main()`` runs only under ``__main__``, never on import."""
    spec = importlib.util.spec_from_file_location("_generate_structure_fixture", GENERATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _assert_version_binds(fixture: dict) -> None:
    """The reference-integrity binding as a single chokepoint both the positive and negative
    tiers exercise: the fixture's declared ``schema_version`` must equal the live constant.

    Lives in the test (not ``src/``) — S0.3 is test-spine only; the persisted store's real
    validator is S1.5/S4.4, not anticipated here.
    """
    actual = fixture.get("schema_version")
    if actual != structure.STRUCTURE_MAP_SCHEMA_VERSION:
        raise ValueError(
            f"fixture schema_version {actual!r} != live STRUCTURE_MAP_SCHEMA_VERSION "
            f"{structure.STRUCTURE_MAP_SCHEMA_VERSION!r} — regenerate the fixture"
        )


# --- fixture / round-trip tier ---------------------------------------------------------- #

def test_fixture_writes_back_byte_exact_through_the_structure_map_location(tmp_path):
    # The location half of the fixture tier: structure_map_path is a real, writable path at the
    # §11.2 work root, and the bytes written through it survive verbatim. (Deliberately NOT a
    # json.loads(json.dumps(x))==x round-trip — that only exercises stdlib json, never the
    # structure code; the generator↔fixture round-trip is the test below.)
    ws = BookWorkspace.for_book("demo", tmp_path).ensure()
    dest = structure.structure_map_path(ws)
    payload = FIXTURE.read_text(encoding="utf-8")

    dest.write_text(payload, encoding="utf-8")

    assert dest == ws.root / "structure_map.json"          # the §11.2 location, via the accessor
    assert dest.read_text(encoding="utf-8") == payload      # exact bytes survive at that location


def test_committed_fixture_is_byte_exact_to_the_generator_output():
    # The done-when's "a generator round-trips a trivial fixture", read literally: regenerating
    # reproduces the committed fixture *exactly*. Two bindings: content (dict) AND byte format —
    # so a hand-edit to one without the other, a constant bump without a refresh, OR a reformat of
    # the committed file all fail here. Without the byte check, format-only drift slips through.
    gen = _load_generator()
    assert _load_fixture() == gen.build_fixture()                    # content binding
    assert FIXTURE.read_text(encoding="utf-8") == gen.render()       # byte-exact: no format drift


# --- reference-integrity tier (binding) ------------------------------------------------- #

def test_fixture_schema_version_binds_to_the_live_constant():
    # A real binding, not a shape check: bumping the constant without refreshing the fixture
    # fails here. This is the tier's reason to exist (feedback_validate_bindings).
    _assert_version_binds(_load_fixture())


# --- property tier ---------------------------------------------------------------------- #

@pytest.mark.parametrize("book_id", ["a", "demo", "per_la_liberta", "x_9"])
def test_artifact_locations_are_always_distinct_and_contained(book_id, tmp_path):
    # An invariant over synthetic book ids: the three artifact locations never collide and never
    # escape the work tree, whatever the book.
    ws = BookWorkspace.for_book(book_id, tmp_path)
    locations = [
        structure.atoms_dir(ws),
        structure.structure_map_path(ws),
        structure.relations_path(ws),
    ]
    assert len(set(locations)) == 3
    assert all(p.is_relative_to(ws.root) for p in locations)


# --- negative tier (fail-loud, no skip-masking) ----------------------------------------- #

def test_negative_a_drifted_fixture_version_fails_the_binding():
    # The failure branch of the reference-integrity binding, asserted hard via the same chokepoint
    # the positive tier uses — so the two can never silently diverge.
    tampered = _load_fixture()
    tampered["schema_version"] = structure.STRUCTURE_MAP_SCHEMA_VERSION + 1
    with pytest.raises(ValueError, match="!= live STRUCTURE_MAP_SCHEMA_VERSION"):
        _assert_version_binds(tampered)
