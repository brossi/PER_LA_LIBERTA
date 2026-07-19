"""S4.7 INV-3 move oracle and INV-5 six-row geometry interaction matrix."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from engine.structure.geom_regate import MODE_PRIMARY, MODE_TIE_BREAK

from harness.materialize import (
    AtomSeed,
    DriftConfig,
    DriftOperation,
    FixtureSpec,
    NodeSeed,
    RebindFixtureBundle,
    SLOT_BODY,
    component0_fixture_spec,
    materialize_fixture,
)
from harness.oracle import SlotRef, planted_tuples

FAIL_LOUD_REASONS = frozenset(
    {
        "zero-candidate",
        "ambiguous",
        "below-threshold",
        "missing-anchor",
        "stale-decision",
        "global-conflict",
    }
)


@dataclass(frozen=True, slots=True)
class MoveCase:
    name: str
    bundle: RebindFixtureBundle
    affected: tuple[SlotRef, ...]


@dataclass(frozen=True, slots=True)
class MoveObservation:
    slot: SlotRef
    bound: bool
    reason: str | None
    fresh_atom_ids: tuple[str, ...]
    map_globally_valid: bool


@dataclass(frozen=True, slots=True)
class GeometryInteractionRow:
    drift: str
    mode: str
    bundle: RebindFixtureBundle
    companion: RebindFixtureBundle | None
    expected: str


@lru_cache(maxsize=1)
def priority3_move_cases() -> tuple[MoveCase, ...]:
    spec = component0_fixture_spec()
    within = materialize_fixture(
        spec,
        DriftConfig(
            "inv3-within-slot-move",
            3101,
            (DriftOperation("move", ("a0",), position=4),),
        ),
    )
    cross = materialize_fixture(
        spec,
        DriftConfig(
            "inv3-cross-container-move",
            3102,
            (DriftOperation("move", ("b0", "b1"), position=8),),
        ),
    )
    return (
        MoveCase("within-container", within, (SlotRef("l0", SLOT_BODY),)),
        MoveCase("cross-container", cross, (SlotRef("l1", SLOT_BODY),)),
    )


def assert_move_observations(
    case: MoveCase, observations: tuple[MoveObservation, ...]
) -> None:
    by_slot = {observation.slot: observation for observation in observations}
    if len(by_slot) != len(observations):
        raise AssertionError("INV-3 duplicate observation for one affected slot")
    if set(by_slot) != set(case.affected):
        raise AssertionError(
            f"INV-3 affected-slot mismatch: expected={case.affected}, observed={tuple(by_slot)}"
        )
    for slot in case.affected:
        observation = by_slot[slot]
        if not observation.bound:
            if observation.reason not in FAIL_LOUD_REASONS:
                raise AssertionError(
                    f"INV-3 unresolved move lacks a closed fail-loud reason: {observation}"
                )
            continue
        planted = planted_tuples(case.bundle, slot)
        if observation.fresh_atom_ids not in planted:
            raise AssertionError(
                f"INV-3 moved slot bound away from planted destination: got="
                f"{observation.fresh_atom_ids}, planted={planted}"
            )
        if not observation.map_globally_valid:
            raise AssertionError(
                "INV-3 destination-correct atom bind produced a globally invalid structure map"
            )


def _word(index: int) -> str:
    return f"repeat{chr(ord('a') + index // 26)}{chr(ord('a') + index % 26)}"


def _repeated_geometry_spec(*, distinct_pages: bool) -> FixtureSpec:
    passage = tuple(_word(index) for index in range(100))
    atoms: list[AtomSeed] = []
    nodes: list[NodeSeed] = [NodeSeed("root", "volume", "container")]
    children: list[str] = []
    for copy in range(2):
        page = copy + 1 if distinct_pages else 1
        for half, words in (("left", passage[:50]), ("right", passage[50:])):
            node_id = f"leaf-{copy}-{half}"
            key = f"atom-{copy}-{half}"
            children.append(node_id)
            nodes.append(NodeSeed(node_id, "block", "leaf", body=(key,)))
            atoms.append(AtomSeed(key, " ".join(words), node_id, SLOT_BODY, page=page))
    nodes[0] = NodeSeed("root", "volume", "container", children=tuple(children))
    return FixtureSpec(
        root_id="root",
        nodes=tuple(nodes),
        atoms=tuple(atoms),
        require_tokenless_cases=False,
    )


def _repeated_bundle(mode: str, *, distinct_pages: bool) -> RebindFixtureBundle:
    return materialize_fixture(
        _repeated_geometry_spec(distinct_pages=distinct_pages),
        DriftConfig(
            f"inv5-repeated-{mode}-{'distinct' if distinct_pages else 'same'}-page",
            3200
            + (100 if mode == MODE_PRIMARY else 200)
            + (1 if distinct_pages else 0),
            (),
            geometry_mode=mode,
        ),
    )


def _boundary_bundle(mode: str) -> RebindFixtureBundle:
    return materialize_fixture(
        component0_fixture_spec(),
        DriftConfig(
            f"inv5-boundary-insert-{mode}",
            3300 + (100 if mode == MODE_PRIMARY else 200),
            (
                DriftOperation(
                    "insert",
                    outputs=("boundary-insert",),
                    texts=("boundary addition",),
                    position=5,
                ),
            ),
            geometry_mode=mode,
        ),
    )


def _move_bundle(mode: str) -> RebindFixtureBundle:
    return materialize_fixture(
        component0_fixture_spec(),
        DriftConfig(
            f"inv5-move-{mode}",
            3400 + (100 if mode == MODE_PRIMARY else 200),
            (DriftOperation("move", ("a0",), position=4),),
            geometry_mode=mode,
        ),
    )


@lru_cache(maxsize=1)
def tie_break_only_bundle() -> RebindFixtureBundle:
    spec = FixtureSpec(
        root_id="root",
        nodes=(
            NodeSeed("root", "volume", "container", children=("l0", "l1")),
            NodeSeed("l0", "block", "leaf", body=("x0",)),
            NodeSeed("l1", "block", "leaf", body=("x1",)),
        ),
        atoms=(
            AtomSeed("x0", "same same same", "l0", SLOT_BODY, page=1),
            AtomSeed("x1", "same same same", "l1", SLOT_BODY, page=1),
        ),
        require_tokenless_cases=False,
    )
    return materialize_fixture(
        spec,
        DriftConfig(
            "inv5-tie-break-only",
            3501,
            (
                DriftOperation(
                    "duplicate",
                    ("x0",),
                    ("x0-copy",),
                    output_pages=(2,),
                ),
            ),
            geometry_mode=MODE_TIE_BREAK,
        ),
    )


@lru_cache(maxsize=1)
def geometry_interaction_matrix() -> tuple[GeometryInteractionRow, ...]:
    rows: list[GeometryInteractionRow] = []
    for mode in (MODE_PRIMARY, MODE_TIE_BREAK):
        rows.extend(
            (
                GeometryInteractionRow(
                    "repeated-content",
                    mode,
                    _repeated_bundle(mode, distinct_pages=False),
                    _repeated_bundle(mode, distinct_pages=True),
                    "same-page ambiguous; distinct-page geometry may disambiguate",
                ),
                GeometryInteractionRow(
                    "boundary-edit",
                    mode,
                    _boundary_bundle(mode),
                    None,
                    "fail loud without independent confirmation",
                ),
                GeometryInteractionRow(
                    "move",
                    mode,
                    _move_bundle(mode),
                    None,
                    "fail loud or exact planted destination with valid map",
                ),
            )
        )
    return tuple(rows)
