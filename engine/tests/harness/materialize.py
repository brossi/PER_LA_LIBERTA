"""Component 0(b) — deterministic S4.7 drift-fixture materialization.

This module owns test substrate, not re-bind behavior.  It deliberately does not import
``engine.structure.rebind`` or any future alignment/projection implementation.  The mutation
engine maintains provenance incrementally while it edits a regenerated working stream; the
independent event interpreter in :mod:`harness.relation` recomputes the closure afterward.

The old map is always built and fingerprinted before drift.  The fresh generation begins with a
``remint`` transition for every old atom, so unchanged content still receives new atom ids and the
harness cannot accidentally test an identity-preserving shortcut.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from itertools import combinations
from types import MappingProxyType
from typing import Mapping

import jsonschema

from engine.errors import CaptureError, RoundTripError
from engine.structure.atom_store import (
    AtomStream,
    assert_atom_hashes,
    assert_reference_integrity,
    assert_stream_roundtrip,
)
from engine.structure.atoms import Atom, AtomDerivation, Geom
from engine.structure.artifacts import NORMALIZER_STALE_CLASS, RESOURCE_STALE_CLASS
from engine.structure.boundary_anchor import (
    DeterministicBoundaryAnchorFamily,
    derive_boundary_anchor,
)
from engine.structure.geom_match import normalize_tokens
from engine.structure.geom_regate import MODE_NO_GEOMETRY, MODE_PRIMARY, MODE_TIE_BREAK
from engine.structure.lineage import ResourceLineage
from engine.structure.errors import StructureValidationError
from engine.structure.roundtrip import hash_raw
from engine.structure.structure_map import (
    STRUCTURE_MAP_SCHEMA_VERSION,
    StreamAtomReader,
    StructureMap,
    build_manifest,
    canonical_content_hash,
    canonical_geometry_hash,
    load_schema,
    structure_map_from_json,
    validate_structure_map,
)

from harness.relation import (
    LineageEvent,
    ProvenanceRelation,
    check_relation_laws,
)

SLOT_BODY = "body"
SLOT_HEADING = "heading"
SLOT_SIGNATURE = "signature"
SLOTS = frozenset({SLOT_BODY, SLOT_HEADING, SLOT_SIGNATURE})
PERTURBATION_OPS = frozenset(
    {"char_sub", "drop", "insert", "duplicate", "split", "merge", "move"}
)
REQUIRED_COMPOSITION_TAGS = frozenset(
    {"merge×repeat", "split×boundary", "move×container-edge"}
)
_TAG_REQUIRED_OPS = {
    "merge×repeat": frozenset({"merge", "duplicate"}),
    "split×boundary": frozenset({"split", "insert"}),
    "move×container-edge": frozenset({"move"}),
}
_OCR_CONFUSIONS = {
    "a": "o",
    "c": "e",
    "e": "c",
    "i": "l",
    "l": "i",
    "m": "rn",
    "n": "ri",
    "o": "a",
}


class FixtureBuildError(ValueError):
    """A fixture/configuration contract failed; malformed test truth never reaches an invariant."""


@dataclass(frozen=True, slots=True)
class AtomSeed:
    key: str
    text: str
    owner_node_id: str
    slot: str
    page: int = 1

    def __post_init__(self) -> None:
        if not self.key:
            raise ValueError("AtomSeed.key must be non-empty")
        if self.slot not in SLOTS:
            raise ValueError(
                f"AtomSeed.slot must be one of {sorted(SLOTS)}, got {self.slot!r}"
            )
        if (
            isinstance(self.page, bool)
            or not isinstance(self.page, int)
            or self.page < 1
        ):
            raise ValueError(f"AtomSeed.page must be an int >= 1, got {self.page!r}")


@dataclass(frozen=True, slots=True)
class NodeSeed:
    node_id: str
    node_class: str
    kind: str  # container | leaf
    children: tuple[str, ...] = ()
    body: tuple[str, ...] = ()
    heading: tuple[str, ...] = ()
    signature: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("children", "body", "heading", "signature"):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        if not self.node_id or not self.node_class:
            raise ValueError("NodeSeed node_id and node_class must be non-empty")
        if self.kind not in {"container", "leaf"}:
            raise ValueError(
                f"NodeSeed.kind must be 'container' or 'leaf', got {self.kind!r}"
            )
        if self.kind == "leaf" and (self.children or self.heading or self.signature):
            raise ValueError("a leaf seed owns only body atoms")
        if self.kind == "container" and self.body:
            raise ValueError("a container seed cannot own body atoms")


@dataclass(frozen=True, slots=True)
class FixtureSpec:
    root_id: str
    nodes: tuple[NodeSeed, ...]
    atoms: tuple[AtomSeed, ...]  # canonical order
    require_tokenless_cases: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "nodes", tuple(self.nodes))
        object.__setattr__(self, "atoms", tuple(self.atoms))
        _validate_spec(self)


@dataclass(frozen=True, slots=True)
class DriftOperation:
    op: str
    targets: tuple[str, ...] = ()  # stable fixture labels, resolved at application time
    outputs: tuple[str, ...] = ()
    texts: tuple[str, ...] = ()
    output_pages: tuple[int | None, ...] = ()
    position: int | None = (
        None  # post-removal coordinate for move; current coordinate for insert
    )

    def __post_init__(self) -> None:
        for name in ("targets", "outputs", "texts", "output_pages"):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        if self.op not in PERTURBATION_OPS:
            raise ValueError(
                f"unknown perturbation {self.op!r}; valid: {sorted(PERTURBATION_OPS)}"
            )
        shape = {
            "char_sub": (1, 1, 1),
            "drop": (1, 0, 0),
            "insert": (0, 1, 1),
            "duplicate": (1, None, 0),
            "split": (1, None, None),
            "merge": (None, 1, 0),
            "move": (None, 0, 0),
        }[self.op]
        for label, values, expected in zip(
            ("targets", "outputs", "texts"),
            (self.targets, self.outputs, self.texts),
            shape,
        ):
            if expected is not None and len(values) != expected:
                raise ValueError(
                    f"{self.op}: expected {expected} {label}, got {len(values)}"
                )
        if self.op in {"duplicate", "split"} and len(self.outputs) < (
            1 if self.op == "duplicate" else 2
        ):
            raise ValueError(f"{self.op}: too few output labels")
        if self.op == "split" and len(self.texts) != len(self.outputs):
            raise ValueError("split: texts and outputs must have equal cardinality")
        if self.output_pages and len(self.output_pages) != len(self.outputs):
            raise ValueError(f"{self.op}: output_pages cardinality must match outputs")
        if any(
            page is not None
            and (isinstance(page, bool) or not isinstance(page, int) or page < 1)
            for page in self.output_pages
        ):
            raise ValueError(
                f"{self.op}: every output page must be None or an int >= 1"
            )
        if self.output_pages and self.op != "duplicate":
            raise ValueError(f"{self.op}: output_pages is admitted only for duplicate")
        if self.op in {"merge", "move"} and len(self.targets) < (
            2 if self.op == "merge" else 1
        ):
            raise ValueError(f"{self.op}: too few target labels")
        if self.op in {"insert", "move"} and self.position is None:
            raise ValueError(f"{self.op}: position is required")
        if self.position is not None and (
            isinstance(self.position, bool) or not isinstance(self.position, int)
        ):
            raise ValueError(f"{self.op}: position must be an int")
        if len(set(self.targets)) != len(self.targets) or len(set(self.outputs)) != len(
            self.outputs
        ):
            raise ValueError(
                f"{self.op}: target/output labels must be unique within the operation"
            )


@dataclass(frozen=True, slots=True)
class DriftConfig:
    name: str
    seed: int
    operations: tuple[DriftOperation, ...]
    geometry_mode: str = MODE_NO_GEOMETRY
    composition_tags: frozenset[str] = frozenset()
    permitted_compositions: frozenset[tuple[str, str]] = frozenset()

    def __post_init__(self) -> None:
        object.__setattr__(self, "operations", tuple(self.operations))
        object.__setattr__(self, "composition_tags", frozenset(self.composition_tags))
        normalized_pairs = frozenset(
            tuple(sorted(pair)) for pair in self.permitted_compositions
        )
        if any(len(pair) != 2 or pair[0] == pair[1] for pair in normalized_pairs):
            raise ValueError("permitted compositions must be distinct two-op pairs")
        object.__setattr__(self, "permitted_compositions", normalized_pairs)
        if not self.name:
            raise ValueError("DriftConfig.name must be non-empty")
        if (
            isinstance(self.seed, bool)
            or not isinstance(self.seed, int)
            or self.seed < 0
        ):
            raise ValueError(
                f"DriftConfig.seed must be a non-negative int, got {self.seed!r}"
            )
        if self.geometry_mode not in {MODE_NO_GEOMETRY, MODE_PRIMARY, MODE_TIE_BREAK}:
            raise ValueError(f"unknown geometry mode {self.geometry_mode!r}")
        actual_ops = sorted({operation.op for operation in self.operations})
        unknown_tags = self.composition_tags - REQUIRED_COMPOSITION_TAGS
        if unknown_tags:
            raise ValueError(f"unknown composition tags: {sorted(unknown_tags)}")
        for tag in self.composition_tags:
            required_ops = _TAG_REQUIRED_OPS[tag]
            if not required_ops <= set(actual_ops):
                raise ValueError(
                    f"{self.name}: composition tag {tag!r} requires ops {sorted(required_ops)}"
                )
        actual_pairs = frozenset(combinations(actual_ops, 2))
        undeclared = actual_pairs - normalized_pairs
        if undeclared:
            raise ValueError(
                f"{self.name}: composed operation pairs must be explicitly permitted; "
                f"undeclared={sorted(undeclared)}"
            )


@dataclass(frozen=True, slots=True)
class DriftSuiteConfig:
    cases: tuple[DriftConfig, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "cases", tuple(self.cases))
        names = [case.name for case in self.cases]
        if len(set(names)) != len(names):
            raise ValueError(f"drift case names must be unique, got {names}")
        covered = {op.op for case in self.cases for op in case.operations}
        missing_ops = PERTURBATION_OPS - covered
        tags = frozenset(tag for case in self.cases for tag in case.composition_tags)
        missing_tags = REQUIRED_COMPOSITION_TAGS - tags
        if missing_ops or missing_tags:
            raise ValueError(
                f"drift suite is incomplete: missing ops={sorted(missing_ops)}, "
                f"missing composition tags={sorted(missing_tags)}"
            )


SlotOwner = tuple[str, str]


@dataclass(frozen=True, slots=True)
class FixtureStats:
    generated_counts: Mapping[str, int]
    realized_counts: Mapping[str, int]
    resegmented_old_ids: frozenset[str]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "generated_counts", MappingProxyType(dict(self.generated_counts))
        )
        object.__setattr__(
            self, "realized_counts", MappingProxyType(dict(self.realized_counts))
        )
        object.__setattr__(
            self, "resegmented_old_ids", frozenset(self.resegmented_old_ids)
        )

    def count(self, op: str) -> int:
        return self.realized_counts.get(op, 0)

    def generated_count(self, op: str) -> int:
        return self.generated_counts.get(op, 0)


@dataclass(frozen=True, slots=True)
class RebindFixtureBundle:
    spec: FixtureSpec
    config: DriftConfig
    old_map: StructureMap
    old_canonical: AtomStream
    fresh_canonical: AtomStream
    geometry_mode: str
    relation: ProvenanceRelation
    events: tuple[LineageEvent, ...]
    stats: FixtureStats
    insertion_ownership: Mapping[str, frozenset[SlotOwner | None]]
    old_witnesses: tuple[AtomStream, ...] = ()
    fresh_witnesses: tuple[AtomStream, ...] = ()
    old_evidence: object | None = None
    policy: object | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "events", tuple(self.events))
        object.__setattr__(self, "old_witnesses", tuple(self.old_witnesses))
        object.__setattr__(self, "fresh_witnesses", tuple(self.fresh_witnesses))
        object.__setattr__(
            self,
            "insertion_ownership",
            MappingProxyType(
                {
                    key: frozenset(value)
                    for key, value in self.insertion_ownership.items()
                }
            ),
        )

    @property
    def old_streams(self) -> dict[str, AtomStream]:
        return {
            self.old_canonical.stream_id: self.old_canonical,
            **{w.stream_id: w for w in self.old_witnesses},
        }

    @property
    def fresh_streams(self) -> dict[str, AtomStream]:
        return {
            self.fresh_canonical.stream_id: self.fresh_canonical,
            **{w.stream_id: w for w in self.fresh_witnesses},
        }


@dataclass(slots=True)
class _WorkingAtom:
    label: str
    atom_id: str
    text: str
    ancestors: frozenset[str]
    page: int
    geom: Geom
    legal_owners: frozenset[SlotOwner | None]


def component0_fixture_spec() -> FixtureSpec:
    """The shared deterministic corpus: all three slot kinds plus tokenless interior/final atoms."""
    atoms = (
        AtomSeed("h0", "Opening heading", "n-sec", SLOT_HEADING),
        AtomSeed("a0", "alpha beta ", "l0", SLOT_BODY),
        AtomSeed("p0", "—", "l0", SLOT_BODY),  # tokenless, slot-interior
        AtomSeed("a1", "gamma delta ", "l0", SLOT_BODY),
        AtomSeed("p1", "…", "l0", SLOT_BODY),  # tokenless, slot-final/seam
        AtomSeed("b0", "epsilon zeta ", "l1", SLOT_BODY),
        AtomSeed("b1", "eta theta ", "l1", SLOT_BODY),
        AtomSeed("s0", "closing signature", "n-sec", SLOT_SIGNATURE),
        AtomSeed("c0", "iota kappa ", "l2", SLOT_BODY),
        AtomSeed("c1", "lambda mu", "l2", SLOT_BODY),
    )
    nodes = (
        NodeSeed("n-root", "volume", "container", children=("n-sec", "l2")),
        NodeSeed(
            "n-sec",
            "section",
            "container",
            children=("l0", "l1"),
            heading=("h0",),
            signature=("s0",),
        ),
        NodeSeed("l0", "block", "leaf", body=("a0", "p0", "a1", "p1")),
        NodeSeed("l1", "block", "leaf", body=("b0", "b1")),
        NodeSeed("l2", "block", "leaf", body=("c0", "c1")),
    )
    return FixtureSpec(root_id="n-root", nodes=nodes, atoms=atoms)


def component0_case_matrix() -> DriftSuiteConfig:
    """The mandatory deterministic matrix consumed before randomized supplemental cases."""
    return DriftSuiteConfig(
        cases=(
            DriftConfig(
                "char-sub",
                101,
                (DriftOperation("char_sub", ("a0",), ("a0-edit",), ("alpha beto ",)),),
            ),
            DriftConfig(
                "drop-insert",
                102,
                (
                    DriftOperation("drop", ("c1",)),
                    DriftOperation(
                        "insert", outputs=("new0",), texts=("nu xi",), position=9
                    ),
                ),
                permitted_compositions=frozenset({("drop", "insert")}),
            ),
            DriftConfig(
                "duplicate",
                103,
                (DriftOperation("duplicate", ("b0",), ("b0-copy",)),),
            ),
            DriftConfig(
                "split-token-boundary",
                104,
                (
                    DriftOperation(
                        "split", ("a1",), ("a1-left", "a1-right"), ("gamma ", "delta ")
                    ),
                ),
            ),
            DriftConfig(
                "merge-repeat",
                105,
                (
                    DriftOperation("merge", ("b0", "b1"), ("b-merge",)),
                    DriftOperation("duplicate", ("b-merge",), ("b-merge-copy",)),
                ),
                composition_tags=frozenset({"merge×repeat"}),
                permitted_compositions=frozenset({("duplicate", "merge")}),
            ),
            DriftConfig(
                "split-boundary",
                106,
                (
                    DriftOperation(
                        "split", ("a1",), ("a1-left", "a1-right"), ("gamma ", "delta ")
                    ),
                    DriftOperation(
                        "insert",
                        outputs=("seam-new",),
                        texts=("boundary addition",),
                        position=6,
                    ),
                ),
                composition_tags=frozenset({"split×boundary"}),
                permitted_compositions=frozenset({("insert", "split")}),
            ),
            DriftConfig(
                "move-container-edge",
                107,
                (DriftOperation("move", ("b0", "b1"), position=8),),
                composition_tags=frozenset({"move×container-edge"}),
            ),
            DriftConfig(
                "merge-cross-slot-seam",
                108,
                (DriftOperation("merge", ("p1", "b0"), ("seam-merge",)),),
            ),
            DriftConfig(
                "heavy-resegmentation",
                109,
                (
                    DriftOperation(
                        "split",
                        ("a0",),
                        ("a0-left", "a0-right"),
                        ("alpha ", "beta "),
                    ),
                    DriftOperation("merge", ("b0", "b1"), ("b-heavy-merge",)),
                ),
                permitted_compositions=frozenset({("merge", "split")}),
            ),
        )
    )


def seeded_supplemental_config(
    spec: FixtureSpec,
    *,
    seed: int,
    enabled_ops: frozenset[str] = PERTURBATION_OPS,
    geometry_mode: str = MODE_NO_GEOMETRY,
) -> DriftConfig:
    """Generate a deterministic randomized supplement over independently toggled perturbations.

    The deterministic case matrix remains the gate.  This helper varies targets/positions and
    composition order without becoming an oracle: :func:`materialize_fixture` still builds truth
    incrementally and :func:`harness.relation.compose_events` still verifies it independently.
    """
    unknown = enabled_ops - PERTURBATION_OPS
    if unknown:
        raise ValueError(f"unknown enabled perturbations: {sorted(unknown)}")
    rng = random.Random(seed)
    # Mutable draft rows: [label, text, owner, page].  This is config planning only; it carries no
    # provenance and shares no relation-fold code with the materializer or reference interpreter.
    live: list[list[object]] = [
        [atom.key, atom.text, (atom.owner_node_id, atom.slot), atom.page]
        for atom in spec.atoms
    ]
    operations: list[DriftOperation] = []

    if "char_sub" in enabled_ops:
        candidates = [
            row for row in live if any(char.isalpha() for char in str(row[1]))
        ]
        row = rng.choice(candidates)
        old_label, old_text = str(row[0]), str(row[1])
        new_label = f"rnd-char-{seed}-{old_label}"
        new_text = _ocr_substitution(old_text)
        operations.append(
            DriftOperation("char_sub", (old_label,), (new_label,), (new_text,))
        )
        row[0], row[1] = new_label, new_text

    if "split" in enabled_ops:
        candidates = [
            row for row in live if 0 < str(row[1]).find(" ") < len(str(row[1])) - 1
        ]
        if not candidates:
            raise FixtureBuildError(
                "seeded supplement: no atom has a legal exact split point"
            )
        row = rng.choice(candidates)
        index = live.index(row)
        label, text = str(row[0]), str(row[1])
        cut = text.find(" ") + 1
        labels = (f"rnd-split-{seed}-{label}-0", f"rnd-split-{seed}-{label}-1")
        texts = (text[:cut], text[cut:])
        operations.append(DriftOperation("split", (label,), labels, texts))
        live[index : index + 1] = [
            [labels[0], texts[0], row[2], row[3]],
            [labels[1], texts[1], row[2], row[3]],
        ]

    if "merge" in enabled_ops:
        candidates = [
            index
            for index in range(len(live) - 1)
            if live[index][2] == live[index + 1][2]
            and live[index][3] == live[index + 1][3]
            and not (
                str(live[index][0]).startswith(f"rnd-split-{seed}-")
                and str(live[index + 1][0]).startswith(f"rnd-split-{seed}-")
                and str(live[index][0]).rsplit("-", 1)[0]
                == str(live[index + 1][0]).rsplit("-", 1)[0]
            )
        ]
        if not candidates:
            raise FixtureBuildError(
                "seeded supplement: no adjacent same-owner merge pair"
            )
        index = rng.choice(candidates)
        left, right = live[index], live[index + 1]
        label = f"rnd-merge-{seed}-{left[0]}-{right[0]}"
        operations.append(
            DriftOperation("merge", (str(left[0]), str(right[0])), (label,))
        )
        live[index : index + 2] = [
            [label, str(left[1]) + str(right[1]), left[2], left[3]]
        ]

    if "duplicate" in enabled_ops:
        index = rng.randrange(len(live))
        row = live[index]
        label = f"rnd-dup-{seed}-{row[0]}"
        operations.append(DriftOperation("duplicate", (str(row[0]),), (label,)))
        live.insert(index + 1, [label, row[1], row[2], row[3]])

    if "drop" in enabled_ops:
        candidates = [
            index
            for index, row in enumerate(live)
            if not str(row[0]).startswith((f"rnd-split-{seed}-", f"rnd-merge-{seed}-"))
        ]
        if not candidates:
            raise FixtureBuildError(
                "seeded supplement: no drop target remains outside realized re-segmentation"
            )
        index = rng.choice(candidates)
        row = live.pop(index)
        operations.append(DriftOperation("drop", (str(row[0]),)))

    if "insert" in enabled_ops:
        position = rng.randrange(len(live) + 1)
        label = f"rnd-insert-{seed}"
        text = f"supplemental insertion {seed}"
        operations.append(
            DriftOperation("insert", outputs=(label,), texts=(text,), position=position)
        )
        if live:
            neighbor = live[position - 1] if position > 0 else live[0]
            owner, page = neighbor[2], neighbor[3]
        else:
            owner, page = None, 1
        live.insert(position, [label, text, owner, page])

    if "move" in enabled_ops:
        if len(live) < 2:
            raise FixtureBuildError(
                "seeded supplement: move needs at least two live atoms"
            )
        old_index = rng.randrange(len(live))
        row = live.pop(old_index)
        destinations = [
            position for position in range(len(live) + 1) if position != old_index
        ]
        position = rng.choice(destinations)
        operations.append(DriftOperation("move", (str(row[0]),), position=position))
        live.insert(position, row)

    op_names = sorted({operation.op for operation in operations})
    permitted = frozenset(combinations(op_names, 2))
    return DriftConfig(
        name=f"random-seed-{seed}",
        seed=seed,
        operations=tuple(operations),
        geometry_mode=geometry_mode,
        permitted_compositions=permitted,
    )


def materialize_fixture(spec: FixtureSpec, config: DriftConfig) -> RebindFixtureBundle:
    """Build one old-map/fresh-stream pair and its independently checkable provenance truth."""
    with_geometry = config.geometry_mode != MODE_NO_GEOMETRY
    old_atoms: list[Atom] = []
    working: list[_WorkingAtom] = []
    old_content: dict[str, str] = {}
    for index, seed in enumerate(spec.atoms):
        old_id = f"old-{seed.key}"
        geom = _initial_geom(index, seed.page) if with_geometry else Geom.absent()
        old_atoms.append(
            _atom(old_id, seed.text, geom, page=seed.page, witness_id="w-old")
        )
        old_content[old_id] = seed.text
        working.append(
            _WorkingAtom(
                label=seed.key,
                atom_id=old_id,
                text=seed.text,
                ancestors=frozenset({old_id}),
                page=seed.page,
                geom=geom,
                legal_owners=frozenset({(seed.owner_node_id, seed.slot)}),
            )
        )

    old_canonical = AtomStream.canonical(old_atoms, stream_id="canonical")
    old_witness = _witness_stream(old_canonical, "w-old")
    old_map = _build_old_map(
        spec,
        old_canonical,
        {old_canonical.stream_id: old_canonical, old_witness.stream_id: old_witness},
    )
    events: list[LineageEvent] = []
    used_ids = {atom.atom_id for atom in working}

    # Regeneration gives every atom a new id before drift; this is a materialization transition,
    # not a perturbation and therefore excluded from realized-operation counts.
    for index, atom in enumerate(working):
        fresh_id = _mint_id(config.seed, 0, index, atom.label)
        _claim_id(fresh_id, used_ids)
        events.append(
            LineageEvent(
                "remint",
                (atom.atom_id,),
                (fresh_id,),
                position=index,
                old_position=index,
                old_texts=(atom.text,),
                fresh_texts=(atom.text,),
            )
        )
        atom.atom_id = fresh_id

    generated_counts = {op: 0 for op in sorted(PERTURBATION_OPS)}
    deleted: set[str] = set()
    movement_events: list[frozenset[str]] = []
    resegmentation_events: list[tuple[str, frozenset[str]]] = []
    for op_index, operation in enumerate(config.operations, start=1):
        _apply_operation(
            working,
            operation,
            config.seed,
            op_index,
            events,
            used_ids,
            deleted,
            movement_events,
            resegmentation_events,
        )
        generated_counts[operation.op] += 1

    realized_counts = dict(generated_counts)

    pairs = frozenset(
        (old_id, atom.atom_id) for atom in working for old_id in atom.ancestors
    )
    surviving_old = {old_id for old_id, _ in pairs}
    movement_candidates = frozenset(
        old_id for participants in movement_events for old_id in participants
    )
    realized_moved = _materialized_final_moved_old_ids(
        tuple(atom.atom_id for atom in old_atoms), working, pairs, movement_candidates
    )
    relation = ProvenanceRelation(
        old_order=tuple(atom.atom_id for atom in old_atoms),
        fresh_order=tuple(atom.atom_id for atom in working),
        pairs=pairs,
        inserted=frozenset(atom.atom_id for atom in working if not atom.ancestors),
        deleted=frozenset(old_id for old_id in deleted if old_id not in surviving_old),
        moved=realized_moved,
        old_content=old_content,
        fresh_content={atom.atom_id: atom.text for atom in working},
    )
    resegmentation_candidates = frozenset(
        old_id for _, participants in resegmentation_events for old_id in participants
    )
    realized_resegmented = _realized_resegmented_old_ids(
        relation, resegmentation_candidates
    )
    for op_name in ("split", "merge"):
        realized_counts[op_name] = sum(
            bool(participants & realized_resegmented)
            for event_op, participants in resegmentation_events
            if event_op == op_name
        )
    realized_counts["move"] = sum(
        bool(participants & realized_moved) for participants in movement_events
    )
    fresh_canonical = AtomStream.canonical(
        [
            _atom(
                atom.atom_id,
                atom.text,
                atom.geom,
                page=atom.page,
                witness_id="w-fresh",
            )
            for atom in working
        ],
        stream_id="canonical",
    )
    fresh_witness = _witness_stream(fresh_canonical, "w-fresh")
    bundle = RebindFixtureBundle(
        spec=spec,
        config=config,
        old_map=old_map,
        old_canonical=old_canonical,
        fresh_canonical=fresh_canonical,
        geometry_mode=config.geometry_mode,
        relation=relation,
        events=tuple(events),
        stats=FixtureStats(generated_counts, realized_counts, realized_resegmented),
        insertion_ownership={
            atom.atom_id: atom.legal_owners for atom in working if not atom.ancestors
        },
        old_witnesses=(old_witness,),
        fresh_witnesses=(fresh_witness,),
    )
    validate_fixture_bundle(bundle)
    return bundle


def validate_fixture_bundle(bundle: RebindFixtureBundle) -> None:
    """The explicit bundle validator required by §1.1; all findings are reported together."""
    problems: list[str] = []
    manifest = bundle.old_map.doc.get("manifest", {})
    if manifest.get("canonical_stream_id") != bundle.old_canonical.stream_id:
        problems.append(
            "old map canonical_stream_id does not name the supplied old canonical"
        )
    content_hash = canonical_content_hash(bundle.old_canonical)
    if manifest.get("canonical_content_hash") != content_hash:
        problems.append(
            "old map canonical_content_hash does not bind the supplied old canonical"
        )
    if bundle.geometry_mode != MODE_NO_GEOMETRY:
        geom_hash = canonical_geometry_hash(bundle.old_canonical)
        if manifest.get("canonical_geometry_hash") != geom_hash:
            problems.append(
                "old map canonical_geometry_hash does not bind the supplied old canonical"
            )

    old_ids = tuple(atom.atom_id for atom in bundle.old_canonical.atoms)
    fresh_ids = tuple(atom.atom_id for atom in bundle.fresh_canonical.atoms)
    if old_ids != bundle.relation.old_order:
        problems.append("old canonical order diverges from provenance old_order")
    if fresh_ids != bundle.relation.fresh_order:
        problems.append("fresh canonical order diverges from provenance fresh_order")
    overlap = set(old_ids) & set(fresh_ids)
    if overlap:
        problems.append(f"fresh generation reused old atom ids: {sorted(overlap)}")
    if bundle.geometry_mode != bundle.config.geometry_mode:
        problems.append("bundle geometry_mode diverges from its config")

    relation_findings = check_relation_laws(bundle.relation, list(bundle.events))
    problems.extend(
        f"relation {finding.law}: {finding.detail}" for finding in relation_findings
    )
    try:
        jsonschema.validate(bundle.old_map.doc, load_schema())
    except jsonschema.ValidationError as exc:
        location = "/".join(str(part) for part in exc.absolute_path) or "<root>"
        problems.append(
            f"old structure map is not Tier-1 valid at {location}: {exc.message}"
        )
    try:
        validate_structure_map(
            bundle.old_map,
            StreamAtomReader(bundle.old_streams, bundle.old_canonical.stream_id),
        )
    except StructureValidationError as exc:
        problems.append(f"old structure map is not globally valid: {exc}")
    for which, canonical, witnesses in (
        ("old", bundle.old_canonical, bundle.old_witnesses),
        ("fresh", bundle.fresh_canonical, bundle.fresh_witnesses),
    ):
        try:
            assert_atom_hashes(canonical.atoms)
            assert_reference_integrity(
                canonical, {witness.stream_id: witness for witness in witnesses}
            )
            for witness in witnesses:
                assert_stream_roundtrip(witness)
                assert_atom_hashes(witness.atoms)
        except (CaptureError, RoundTripError) as exc:
            problems.append(f"{which} stream integrity failed: {exc}")

    old_content = {atom.atom_id: atom.text for atom in bundle.old_canonical.atoms}
    fresh_content = {atom.atom_id: atom.text for atom in bundle.fresh_canonical.atoms}
    if dict(bundle.relation.old_content) != old_content:
        problems.append("relation old_content does not equal the old canonical")
    if dict(bundle.relation.fresh_content) != fresh_content:
        problems.append("relation fresh_content does not equal the fresh canonical")
    if set(bundle.insertion_ownership) != set(bundle.relation.inserted):
        problems.append(
            "insert ownership table does not cover exactly the final inserted atoms"
        )
    expected_generated = {op: 0 for op in sorted(PERTURBATION_OPS)}
    for operation in bundle.config.operations:
        expected_generated[operation.op] += 1
    if dict(bundle.stats.generated_counts) != expected_generated:
        problems.append("generated operation counts diverge from the fixture config")
    if set(bundle.stats.realized_counts) != set(expected_generated) or any(
        bundle.stats.count(op) > bundle.stats.generated_count(op)
        for op in expected_generated
    ):
        problems.append(
            "realized operation counts are malformed or exceed generated counts"
        )

    by_node = {node["node_id"]: node for node in bundle.old_map.doc["nodes"]}
    expected_node_ids = {node.node_id for node in bundle.spec.nodes}
    if set(by_node) != expected_node_ids:
        problems.append(
            "old map node ids diverge from fixture spec: "
            f"missing={sorted(expected_node_ids - set(by_node))}, "
            f"extra={sorted(set(by_node) - expected_node_ids)}"
        )
    seed_by_key = {seed.key: seed for seed in bundle.spec.atoms}
    for node in bundle.spec.nodes:
        raw = by_node.get(node.node_id)
        if raw is None:
            continue
        slot_keys = (
            (SLOT_BODY, node.body),
            (SLOT_HEADING, node.heading),
            (SLOT_SIGNATURE, node.signature),
        )
        for slot, keys in slot_keys:
            if not keys:
                continue
            expected = _fingerprint_payload([seed_by_key[key].text for key in keys])
            stored = (
                raw.get("rebind_anchors", {}).get("content_fingerprint", {}).get(slot)
            )
            if expected is None:
                if stored is not None:
                    problems.append(
                        f"{node.node_id}/{slot}: tokenless slot unexpectedly has a fingerprint"
                    )
            elif stored != expected:
                problems.append(
                    f"{node.node_id}/{slot}: stored anchor was not derived from old-map content"
                )

    if problems:
        raise FixtureBuildError(
            "invalid rebind fixture bundle:\n  - " + "\n  - ".join(problems)
        )


def _validate_spec(spec: FixtureSpec) -> None:
    problems: list[str] = []
    node_ids = [node.node_id for node in spec.nodes]
    atom_keys = [atom.key for atom in spec.atoms]
    atom_positions = {key: index for index, key in enumerate(atom_keys)}
    if len(set(node_ids)) != len(node_ids):
        problems.append("duplicate node ids")
    if len(set(atom_keys)) != len(atom_keys):
        problems.append("duplicate atom keys")
    nodes = {node.node_id: node for node in spec.nodes}
    atoms = {atom.key: atom for atom in spec.atoms}
    class_kinds: dict[str, str] = {}
    for node in spec.nodes:
        prior = class_kinds.setdefault(node.node_class, node.kind)
        if prior != node.kind:
            problems.append(
                f"node_class {node.node_class!r} is used as both {prior!r} and {node.kind!r}"
            )
    if spec.root_id not in nodes:
        problems.append(f"missing root {spec.root_id!r}")

    claims: list[str] = []
    parents: dict[str, str] = {}
    for node in spec.nodes:
        for child in node.children:
            if child not in nodes:
                problems.append(f"{node.node_id}: unknown child {child!r}")
            if child in parents:
                problems.append(f"{child!r} has multiple parents")
            parents[child] = node.node_id
        for slot, keys in (
            (SLOT_BODY, node.body),
            (SLOT_HEADING, node.heading),
            (SLOT_SIGNATURE, node.signature),
        ):
            indices: list[int] = []
            for key in keys:
                claims.append(key)
                seed = atoms.get(key)
                if seed is None:
                    problems.append(f"{node.node_id}/{slot}: unknown atom {key!r}")
                    continue
                if (seed.owner_node_id, seed.slot) != (node.node_id, slot):
                    problems.append(f"{key!r}: AtomSeed owner disagrees with node slot")
                indices.append(atom_positions[key])
            if indices != sorted(indices):
                problems.append(
                    f"{node.node_id}/{slot}: atom keys are not in canonical order"
                )
    if sorted(claims) != sorted(atom_keys):
        problems.append("node slots must claim every atom exactly once")
    if set(parents) != set(nodes) - {spec.root_id}:
        problems.append("tree must have exactly one root and reach every non-root node")

    # Cycle/reachability check independent of the production structure validator.  This is an
    # explicit enter/exit stack so the registered D=2,500 fixture is not bounded by Python's call
    # stack. ``active`` is the iterative equivalent of the prior recursive gray set.
    seen: set[str] = set()
    active: set[str] = set()
    work: list[tuple[str, bool]] = []
    if spec.root_id in nodes:
        work.append((spec.root_id, False))
    while work:
        node_id, exiting = work.pop()
        if exiting:
            active.remove(node_id)
            seen.add(node_id)
            continue
        if node_id in active:
            problems.append(f"cycle at {node_id!r}")
            continue
        if node_id in seen or node_id not in nodes:
            continue
        active.add(node_id)
        work.append((node_id, True))
        work.extend(
            (child, False) for child in reversed(nodes[node_id].children)
        )
    if seen != set(nodes):
        problems.append(f"unreachable nodes: {sorted(set(nodes) - seen)}")

    if spec.require_tokenless_cases:
        tokenless = {atom.key for atom in spec.atoms if not normalize_tokens(atom.text)}
        interior = False
        final = False
        for node in spec.nodes:
            for keys in (node.body, node.heading, node.signature):
                for index, key in enumerate(keys):
                    if key in tokenless:
                        interior |= index < len(keys) - 1
                        final |= index == len(keys) - 1
        if not interior or not final:
            problems.append(
                "fixture must contain tokenless included atoms both slot-interior and slot-final"
            )
    if problems:
        raise FixtureBuildError("invalid fixture spec:\n  - " + "\n  - ".join(problems))


def _build_old_map(
    spec: FixtureSpec, canonical: AtomStream, streams: Mapping[str, AtomStream]
) -> StructureMap:
    seed_by_key = {seed.key: seed for seed in spec.atoms}
    atom_by_key = {seed.key: atom for seed, atom in zip(spec.atoms, canonical.atoms)}
    stream_tokens: list[str] = []
    token_ranges: dict[str, tuple[int, int]] = {}
    for seed in spec.atoms:
        start = len(stream_tokens)
        stream_tokens.extend(normalize_tokens(seed.text))
        token_ranges[seed.key] = (start, len(stream_tokens))
    anchor_family = DeterministicBoundaryAnchorFamily()

    def anchor_payload(anchor) -> dict[str, list[str]]:
        return {
            "prefix": list(anchor.prefix),
            "exact": list(anchor.exact),
            "suffix": list(anchor.suffix),
        }

    nodes: list[dict] = []
    for seed in spec.nodes:
        raw: dict[str, object] = {
            "node_id": seed.node_id,
            "node_class": seed.node_class,
            "minted_by": "human" if seed.kind == "container" else "machine",
        }
        if seed.kind == "container":
            raw["children"] = list(seed.children)
            if seed.heading:
                raw["heading_atoms"] = [
                    atom_by_key[key].atom_id for key in seed.heading
                ]
            if seed.signature:
                raw["signature_atoms"] = [
                    atom_by_key[key].atom_id for key in seed.signature
                ]
        else:
            raw["body_atoms"] = [atom_by_key[key].atom_id for key in seed.body]

        content_fingerprint: dict[str, dict] = {}
        boundary_anchors: dict[str, dict] = {}
        own_keys = (
            (SLOT_BODY, seed.body),
            (SLOT_HEADING, seed.heading),
            (SLOT_SIGNATURE, seed.signature),
        )
        first_geom: Geom | None = None
        for slot, keys in own_keys:
            if not keys:
                continue
            fp = _fingerprint_payload([seed_by_key[key].text for key in keys])
            if fp is not None:
                content_fingerprint[slot] = fp
                tokened_keys = [key for key in keys if token_ranges[key][0] != token_ranges[key][1]]
                start_boundary = token_ranges[tokened_keys[0]][0]
                end_boundary = token_ranges[tokened_keys[-1]][1]
                boundary_anchors[slot] = {
                    "start": anchor_payload(
                        derive_boundary_anchor(
                            anchor_family,
                            stream_tokens,
                            start_boundary,
                            side="start",
                        )
                    ),
                    "end": anchor_payload(
                        derive_boundary_anchor(
                            anchor_family,
                            stream_tokens,
                            end_boundary,
                            side="end",
                        )
                    ),
                }
            if first_geom is None:
                first_geom = next(
                    (
                        atom_by_key[key].geom
                        for key in keys
                        if atom_by_key[key].geom.present
                    ),
                    None,
                )
        anchors: dict[str, object] = {}
        if content_fingerprint:
            anchors["content_fingerprint"] = content_fingerprint
            anchors["boundary_anchors"] = boundary_anchors
        if first_geom is not None:
            anchors["region"] = {
                "page": first_geom.page,
                "bbox_region": list(first_geom.bbox),
            }
        if anchors:
            raw["rebind_anchors"] = anchors
        nodes.append(raw)

    classes = {node.node_class: node.kind for node in spec.nodes}
    doc = {
        "schema_version": STRUCTURE_MAP_SCHEMA_VERSION,
        "root_id": spec.root_id,
        "map_revision": 1,
        "block_vocabulary": [
            {"name": name, "kind": kind, "status": "active"}
            for name, kind in sorted(classes.items())
        ],
        "handle_policies": {name: "position-path" for name in sorted(classes)},
        "furniture_atoms": [],
        "aliases": [],
        "manifest": build_manifest(
            streams=streams,
            canonical_stream_id=canonical.stream_id,
            resource_lineage=ResourceLineage(
                resource_version="synthetic-resource-v1",
                resource_descriptor='{"fixture":"s4.7-component0"}',
                resource_stale_class=RESOURCE_STALE_CLASS,
                normalizer_version="synthetic-normalizer-v1",
                normalizer_descriptor='{"case_fold":true,"accent_fold":false}',
                normalizer_stale_class=NORMALIZER_STALE_CLASS,
            ),
            profile_version="synthetic-profile-v1",
            recognizer_version="synthetic-recognizer-v1",
        ),
        "nodes": nodes,
    }
    # ``materialize_fixture`` immediately validates the completed bundle, including this exact
    # Tier-1 document.  Keeping a second full-document schema walk here doubled large-fixture
    # construction cost without adding an independent check.
    return structure_map_from_json(doc)


def _fingerprint_payload(texts: list[str], *, k: int = 3) -> dict | None:
    tokens = [token for text in texts for token in normalize_tokens(text)]
    if not tokens:
        return None
    effective = min(k, len(tokens))
    shingles = sorted(
        {
            " ".join(tokens[index : index + effective])
            for index in range(len(tokens) - effective + 1)
        }
    )
    return {
        "algo_id": "shingle-jaccard@v1",
        "normalizer_id": "geom_match.normalize_tokens@v1",
        "k": effective,
        "token_count": len(tokens),
        "shingles": shingles,
    }


def _apply_operation(
    working: list[_WorkingAtom],
    op: DriftOperation,
    seed: int,
    op_index: int,
    events: list[LineageEvent],
    used_ids: set[str],
    deleted: set[str],
    movement_events: list[frozenset[str]],
    resegmentation_events: list[tuple[str, frozenset[str]]],
) -> None:
    label_collisions = set(op.outputs) & {atom.label for atom in working}
    if label_collisions:
        raise FixtureBuildError(
            f"{op.op}: output label(s) already active: {sorted(label_collisions)}"
        )
    indices = [_label_index(working, label, op.op) for label in op.targets]
    if op.op in {"merge", "move"} and indices != list(
        range(indices[0], indices[0] + len(indices))
    ):
        raise FixtureBuildError(
            f"{op.op}: targets must be a contiguous working-stream block"
        )

    old_atoms = [working[index] for index in indices]
    old_ids = tuple(atom.atom_id for atom in old_atoms)
    old_texts = tuple(atom.text for atom in old_atoms)
    old_position = indices[0] if indices else None

    if op.op == "drop":
        atom = old_atoms[0]
        del working[indices[0]]
        deleted.update(atom.ancestors)
        events.append(
            LineageEvent(
                "drop", old_ids, (), old_position=old_position, old_texts=old_texts
            )
        )
        return

    if op.op == "insert":
        position = _checked_position(op.position, len(working), op.op)
        output_id = _mint_id(seed, op_index, 0, op.outputs[0])
        _claim_id(output_id, used_ids)
        page = _insert_page(working, position, op="insert")
        geom = _insert_geom(working, position)
        owners = _insert_owners(working, position)
        atom = _WorkingAtom(
            op.outputs[0], output_id, op.texts[0], frozenset(), page, geom, owners
        )
        working.insert(position, atom)
        events.append(
            LineageEvent(
                "insert", (), (output_id,), position=position, fresh_texts=(atom.text,)
            )
        )
        return

    if op.op == "char_sub":
        source = old_atoms[0]
        if op.texts[0] == source.text:
            raise FixtureBuildError(
                "char_sub: replacement is byte-identical (generated no-op)"
            )
        if not _is_ocr_class_substitution(source.text, op.texts[0]):
            raise FixtureBuildError(
                "char_sub: replacement must be one registered in-token OCR-class substitution"
            )
        output_id = _mint_id(seed, op_index, 0, op.outputs[0])
        _claim_id(output_id, used_ids)
        replacement = _WorkingAtom(
            op.outputs[0],
            output_id,
            op.texts[0],
            source.ancestors,
            source.page,
            source.geom,
            source.legal_owners,
        )
        working[indices[0]] = replacement
        events.append(
            LineageEvent(
                "char_sub",
                old_ids,
                (output_id,),
                position=indices[0],
                old_position=indices[0],
                old_texts=old_texts,
                fresh_texts=(replacement.text,),
            )
        )
        return

    if op.op == "duplicate":
        source = old_atoms[0]
        copies: list[_WorkingAtom] = []
        staged = list(working)
        for offset, label in enumerate(op.outputs):
            output_id = _mint_id(seed, op_index, offset, label)
            _claim_id(output_id, used_ids)
            position = indices[0] + 1 + offset
            geom = _insert_geom(staged, position)
            page = (
                op.output_pages[offset]
                if op.output_pages and op.output_pages[offset] is not None
                else source.page
            )
            if op.output_pages and op.output_pages[offset] is not None and geom.present:
                geom = _repage_geom(geom, op.output_pages[offset])
            copy_atom = _WorkingAtom(
                label,
                output_id,
                source.text,
                source.ancestors,
                page,
                geom,
                source.legal_owners,
            )
            copies.append(copy_atom)
            staged.insert(position, copy_atom)
        working[:] = staged
        events.append(
            LineageEvent(
                "duplicate",
                old_ids,
                tuple(atom.atom_id for atom in copies),
                position=indices[0] + 1,
                old_position=indices[0],
                old_texts=old_texts,
                fresh_texts=tuple(atom.text for atom in copies),
            )
        )
        return

    if op.op == "split":
        source = old_atoms[0]
        if "".join(op.texts) != source.text:
            raise FixtureBuildError(
                "split: output texts must concatenate byte-exactly to the source"
            )
        geoms = _split_geom(source.geom, op.texts)
        products: list[_WorkingAtom] = []
        for offset, (label, text, geom) in enumerate(zip(op.outputs, op.texts, geoms)):
            output_id = _mint_id(seed, op_index, offset, label)
            _claim_id(output_id, used_ids)
            products.append(
                _WorkingAtom(
                    label,
                    output_id,
                    text,
                    source.ancestors,
                    source.page,
                    geom,
                    source.legal_owners,
                )
            )
        working[indices[0] : indices[0] + 1] = products
        resegmentation_events.append(("split", source.ancestors))
        events.append(
            LineageEvent(
                "split",
                old_ids,
                tuple(atom.atom_id for atom in products),
                position=indices[0],
                old_position=indices[0],
                old_texts=old_texts,
                fresh_texts=tuple(atom.text for atom in products),
            )
        )
        return

    if op.op == "merge":
        pages = {atom.page for atom in old_atoms}
        if len(pages) > 1:
            raise FixtureBuildError(
                "merge: cross-page sources are an excluded composition"
            )
        output_id = _mint_id(seed, op_index, 0, op.outputs[0])
        _claim_id(output_id, used_ids)
        merged = _WorkingAtom(
            op.outputs[0],
            output_id,
            "".join(old_texts),
            frozenset(old for atom in old_atoms for old in atom.ancestors),
            old_atoms[0].page,
            _merge_geom([atom.geom for atom in old_atoms]),
            frozenset(owner for atom in old_atoms for owner in atom.legal_owners),
        )
        working[indices[0] : indices[-1] + 1] = [merged]
        resegmentation_events.append(("merge", merged.ancestors))
        events.append(
            LineageEvent(
                "merge",
                old_ids,
                (output_id,),
                position=indices[0],
                old_position=indices[0],
                old_texts=old_texts,
                fresh_texts=(merged.text,),
            )
        )
        return

    if op.op == "move":
        block = working[indices[0] : indices[-1] + 1]
        before = tuple(atom.atom_id for atom in working)
        del working[indices[0] : indices[-1] + 1]
        position = _checked_position(op.position, len(working), op.op)
        destination_page = _insert_page(working, position, op="move")
        destination_geoms = _moved_block_geoms(
            _insert_geom(working, position), len(block), destination_page
        )
        working[position:position] = block
        if tuple(atom.atom_id for atom in working) == before:
            raise FixtureBuildError(
                "move: destination leaves the working order unchanged"
            )
        for atom, geom in zip(block, destination_geoms):
            atom.page = destination_page
            atom.geom = geom
        movement_events.append(
            frozenset(old_id for atom in block for old_id in atom.ancestors)
        )
        events.append(
            LineageEvent(
                "move",
                old_ids,
                old_ids,
                position=position,
                old_position=old_position,
                old_texts=old_texts,
                fresh_texts=old_texts,
            )
        )
        return

    raise AssertionError(f"unhandled perturbation {op.op}")


def _label_index(working: list[_WorkingAtom], label: str, op: str) -> int:
    matches = [index for index, atom in enumerate(working) if atom.label == label]
    if len(matches) != 1:
        raise FixtureBuildError(
            f"{op}: target label {label!r} resolves {len(matches)} times"
        )
    return matches[0]


def _realized_resegmented_old_ids(
    relation: ProvenanceRelation, candidates: frozenset[str]
) -> frozenset[str]:
    """Candidates whose FINAL relation is not one-old↔one-fresh.

    A split followed by a merge back to one atom (or a merge later undone without retaining the
    original separation) is not counted merely because events were emitted.  This final-relation
    definition is independent of operation count and makes the ≥30% floor resistant to net-zero
    event padding.
    """
    descendants: dict[str, set[str]] = {old_id: set() for old_id in candidates}
    ancestors: dict[str, set[str]] = {}
    for old_id, fresh_id in relation.pairs:
        if old_id in descendants:
            descendants[old_id].add(fresh_id)
        ancestors.setdefault(fresh_id, set()).add(old_id)
    return frozenset(
        old_id
        for old_id, fresh_ids in descendants.items()
        if fresh_ids
        and (
            len(fresh_ids) != 1
            or any(len(ancestors.get(fresh_id, set())) != 1 for fresh_id in fresh_ids)
        )
    )


def _materialized_final_moved_old_ids(
    old_order: tuple[str, ...],
    working: list[_WorkingAtom],
    pairs: frozenset[tuple[str, str]],
    candidates: frozenset[str],
) -> frozenset[str]:
    """Incremental engine's final move truth, computed without the reference interpreter."""
    old_rank = {old_id: index for index, old_id in enumerate(old_order)}
    fresh_rank = {atom.atom_id: index for index, atom in enumerate(working)}
    ranks_by_old: dict[str, list[int]] = {}
    for old_id, fresh_id in pairs:
        ranks_by_old.setdefault(old_id, []).append(fresh_rank[fresh_id])
    final_rank = {old_id: min(ranks) for old_id, ranks in ranks_by_old.items()}
    return frozenset(
        old_id
        for old_id in candidates
        if old_id in final_rank
        and any(
            other != old_id
            and (
                final_rank[old_id] == final_rank[other]
                or (old_rank[old_id] - old_rank[other])
                * (final_rank[old_id] - final_rank[other])
                < 0
            )
            for other in final_rank
        )
    )


def _checked_position(position: int | None, maximum: int, op: str) -> int:
    if position is None or not 0 <= position <= maximum:
        raise FixtureBuildError(f"{op}: position {position!r} outside [0, {maximum}]")
    return position


def _claim_id(atom_id: str, used: set[str]) -> None:
    if atom_id in used:
        raise FixtureBuildError(f"mutation engine attempted atom-id reuse: {atom_id!r}")
    used.add(atom_id)


def _mint_id(seed: int, op_index: int, output_index: int, label: str) -> str:
    safe = "".join(char if char.isalnum() or char in "._-" else "-" for char in label)
    return f"fresh-{seed:08x}-{op_index:03d}-{output_index:03d}-{safe}"


def _ocr_substitution(text: str) -> str:
    for index, char in enumerate(text):
        replacement = _OCR_CONFUSIONS.get(char.casefold())
        if replacement is None:
            continue
        if char.isupper():
            replacement = replacement.upper()
        return text[:index] + replacement + text[index + 1 :]
    raise FixtureBuildError(
        "seeded supplement: selected text has no registered OCR-class substitution"
    )


def _is_ocr_class_substitution(old: str, fresh: str) -> bool:
    for index, char in enumerate(old):
        replacement = _OCR_CONFUSIONS.get(char.casefold())
        if replacement is None:
            continue
        if char.isupper():
            replacement = replacement.upper()
        if old[:index] + replacement + old[index + 1 :] == fresh:
            # ``char`` itself is alphabetic by membership in the confusion table; requiring a
            # letter on at least one side keeps the change inside a token rather than punctuation.
            return (index > 0 and old[index - 1].isalpha()) or (
                index + 1 < len(old) and old[index + 1].isalpha()
            )
    return False


def _atom(
    atom_id: str,
    text: str,
    geom: Geom,
    *,
    page: int,
    witness_id: str | None = None,
) -> Atom:
    return Atom(
        atom_id=atom_id,
        text=text,
        raw_span=(0, len(text)),
        raw_source_hash=hash_raw(text),
        page_range=(page, page),
        norm_layer="synthetic-drift",
        geom=geom,
        capture_provenance_class="synthetic",
        witness=None,
        derived_from=(
            (AtomDerivation(witness=witness_id, atom_id=f"{witness_id}-{atom_id}"),)
            if witness_id is not None
            else ()
        ),
        processing_scope="included",
    )


def _witness_stream(canonical: AtomStream, witness_id: str) -> AtomStream:
    source = "".join(atom.text for atom in canonical.atoms)
    cursor = 0
    atoms: list[Atom] = []
    for canonical_atom in canonical.atoms:
        start = cursor
        cursor += len(canonical_atom.text)
        atoms.append(
            Atom(
                atom_id=f"{witness_id}-{canonical_atom.atom_id}",
                text=canonical_atom.text,
                raw_span=(start, cursor),
                raw_source_hash=hash_raw(canonical_atom.text),
                page_range=canonical_atom.page_range,
                norm_layer="synthetic-drift",
                geom=Geom.absent(),
                capture_provenance_class="synthetic",
                witness=witness_id,
                derived_from=(),
                processing_scope="included",
            )
        )
    return AtomStream.witness(witness_id, atoms, (), source)


def _initial_geom(index: int, page: int) -> Geom:
    top = 10.0 + index * 12.0
    return _matched_geom(page, (10.0, top, 110.0, top + 8.0))


def _matched_geom(page: int, bbox: tuple[float, float, float, float]) -> Geom:
    return Geom.matched(
        page=page,
        bbox=bbox,
        geometry_engine="synthetic-v1",
        matched_witness_id="synthetic",
        match_method="constructed",
        match_confidence=1.0,
    )


def _repage_geom(geom: Geom, page: int) -> Geom:
    if not geom.present:
        return geom
    assert geom.bbox is not None
    return _matched_geom(page, geom.bbox)


def _insert_geom(working: list[_WorkingAtom], position: int) -> Geom:
    present = [atom for atom in working if atom.geom.present]
    if not present:
        return Geom.absent()
    left = next(
        (
            working[index]
            for index in range(position - 1, -1, -1)
            if working[index].geom.present
        ),
        None,
    )
    right = next(
        (
            working[index]
            for index in range(position, len(working))
            if working[index].geom.present
        ),
        None,
    )
    if left is not None and right is not None and left.geom.page != right.geom.page:
        raise FixtureBuildError(
            "insert: neighbors cross pages (excluded geometry composition)"
        )
    reference = left or right
    assert (
        reference is not None
        and reference.geom.bbox is not None
        and reference.geom.page is not None
    )
    if left is not None and right is not None:
        y = (left.geom.bbox[3] + right.geom.bbox[1]) / 2.0
    elif left is not None:
        y = left.geom.bbox[3] + 1.0
    else:
        assert right is not None
        y = right.geom.bbox[1] - 2.0
    return _matched_geom(reference.geom.page, (10.0, y, 110.0, y + 1.0))


def _insert_page(working: list[_WorkingAtom], position: int, *, op: str) -> int:
    if not working:
        return 1
    left = working[position - 1].page if position > 0 else None
    right = working[position].page if position < len(working) else None
    if left is not None and right is not None and left != right:
        raise FixtureBuildError(
            f"{op}: neighbors cross pages (excluded geometry composition)"
        )
    return left if left is not None else right


def _moved_block_geoms(base: Geom, count: int, page: int) -> tuple[Geom, ...]:
    if not base.present:
        return tuple(Geom.absent() for _ in range(count))
    assert base.bbox is not None
    x0, y0, x1, y1 = base.bbox
    height = max(0.25, y1 - y0)
    return tuple(
        _matched_geom(page, (x0, y0 + offset * height, x1, y1 + offset * height))
        for offset in range(count)
    )


def _insert_owners(
    working: list[_WorkingAtom], position: int
) -> frozenset[SlotOwner | None]:
    left = working[position - 1].legal_owners if position > 0 else frozenset()
    right = working[position].legal_owners if position < len(working) else frozenset()
    concrete_left = frozenset(owner for owner in left if owner is not None)
    concrete_right = frozenset(owner for owner in right if owner is not None)
    if concrete_left and not concrete_right:
        return concrete_left
    if concrete_right and not concrete_left:
        return concrete_right
    if concrete_left and concrete_left == concrete_right:
        return concrete_left
    if concrete_left or concrete_right:
        return frozenset(set(concrete_left | concrete_right) | {None})
    return frozenset({None})


def _split_geom(geom: Geom, texts: tuple[str, ...]) -> tuple[Geom, ...]:
    if not geom.present:
        return tuple(Geom.absent() for _ in texts)
    assert geom.bbox is not None and geom.page is not None
    x0, y0, x1, y1 = geom.bbox
    weights = [max(1, len(normalize_tokens(text))) for text in texts]
    total = sum(weights)
    cursor = x0
    out: list[Geom] = []
    for index, weight in enumerate(weights):
        end = x1 if index == len(weights) - 1 else cursor + (x1 - x0) * weight / total
        out.append(_matched_geom(geom.page, (cursor, y0, end, y1)))
        cursor = end
    return tuple(out)


def _merge_geom(geoms: list[Geom]) -> Geom:
    present = [geom for geom in geoms if geom.present]
    if not present:
        return Geom.absent()
    pages = {geom.page for geom in present}
    if len(pages) != 1:
        raise FixtureBuildError("merge: present geometry spans pages")
    boxes = [geom.bbox for geom in present]
    assert all(box is not None for box in boxes)
    return _matched_geom(
        present[0].page,
        (
            min(box[0] for box in boxes),
            min(box[1] for box in boxes),
            max(box[2] for box in boxes),
            max(box[3] for box in boxes),
        ),
    )
