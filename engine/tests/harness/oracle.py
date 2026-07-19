"""Independent S4.7 INV-1/INV-2 oracle and their shared seeded corpus.

This module intentionally does not import :mod:`engine.structure.rebind`.  Fixture provenance
supplies the planted destination; a bounded edit-grid reference model contributes feasibility and
alternative-boundary facts; independent shingle arithmetic and representation-agnostic boundary
sentinels contribute confidence.  None of those decisions read the mechanism's report.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from itertools import product
from types import MappingProxyType
from typing import Iterable, Mapping

from engine.structure.boundary_anchor import BOUNDARY_ANCHOR_FOOTPRINT_W
from engine.structure.geom_match import normalize_tokens
from engine.structure.geom_regate import MODE_NO_GEOMETRY, MODE_PRIMARY, MODE_TIE_BREAK

from harness.materialize import (
    AtomSeed,
    DriftConfig,
    DriftOperation,
    FixtureSpec,
    NodeSeed,
    RebindFixtureBundle,
    SLOT_BODY,
    component0_case_matrix,
    component0_fixture_spec,
    materialize_fixture,
    seeded_supplemental_config,
)

# Independent copy of the item-2 policy values.  A contract test binds these to the shipped
# RebindPolicy defaults; the oracle never calls production threshold or scoring code.
ORACLE_TAU_BY_MODE = MappingProxyType(
    {MODE_PRIMARY: 0.70, MODE_TIE_BREAK: 0.75, MODE_NO_GEOMETRY: 0.80}
)
REFERENCE_MAX_TOKENS = 512
REFERENCE_MAX_OPTIONAL_INSERTS = 8
PRIORITY2_RANDOM_SEEDS = tuple(range(2700, 2716))


@dataclass(frozen=True, slots=True, order=True)
class SlotRef:
    node_id: str
    slot_name: str


@dataclass(frozen=True, slots=True)
class AllowedBind:
    slot: SlotRef
    fresh_atom_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ObservedBind:
    slot: SlotRef
    fresh_atom_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ObservedCase:
    binds: tuple[ObservedBind, ...]
    unresolved_slots: frozenset[SlotRef]


@dataclass(frozen=True, slots=True)
class AlignmentFacts:
    edit_distance: int
    optimal_paths: int  # saturated at 2
    old_start: int
    old_end: int
    fresh_start: int
    fresh_end: int
    start_mappings: tuple[int, ...]
    end_mappings: tuple[int, ...]

    @property
    def planted_feasible(self) -> bool:
        return (
            self.fresh_start in self.start_mappings
            and self.fresh_end in self.end_mappings
        )

    @property
    def has_boundary_alternative(self) -> bool:
        return len(self.start_mappings) != 1 or len(self.end_mappings) != 1


@dataclass(frozen=True, slots=True)
class SlotOracle:
    slot: SlotRef
    old_atom_ids: tuple[str, ...]
    planted_tuples: tuple[tuple[str, ...], ...]
    allowed: frozenset[AllowedBind]
    blocked_reasons: tuple[str, ...]
    alignment: tuple[AlignmentFacts, ...]


@dataclass(frozen=True, slots=True)
class CaseDiagnostic:
    case_name: str
    bound_correct: int
    abstained: int
    wrong: int


@dataclass(frozen=True, slots=True)
class CorpusCase:
    name: str
    bundle: RebindFixtureBundle
    required_inv2: tuple[SlotRef, ...] = ()


@dataclass(frozen=True, slots=True)
class SharedInvariantCorpus:
    cases: tuple[CorpusCase, ...]
    random_seeds: tuple[int, ...]

    @property
    def case_names(self) -> tuple[str, ...]:
        return tuple(case.name for case in self.cases)


@dataclass(frozen=True, slots=True)
class AnchorDensityKnob:
    """Item-2's deterministic sentinel knob; the six-point v3 sweep remains item 4's."""

    repeat_copies: int

    def __post_init__(self) -> None:
        if (
            isinstance(self.repeat_copies, bool)
            or not isinstance(self.repeat_copies, int)
            or not 1 <= self.repeat_copies <= 4
        ):
            raise ValueError("repeat_copies must be an int in [1, 4]")


ANCHOR_RICH_SENTINEL = AnchorDensityKnob(repeat_copies=1)
ANCHOR_POOR_SENTINEL = AnchorDensityKnob(repeat_copies=2)


def _alpha_suffix(index: int) -> str:
    """A lower-alpha base-26 suffix (the normalizer keeps it as one distinctive token)."""
    chars: list[str] = []
    value = index
    while True:
        value, remainder = divmod(value, 26)
        chars.append(chr(ord("a") + remainder))
        if value == 0:
            return "".join(reversed(chars))
        value -= 1


def _tokens(prefix: str, count: int) -> str:
    return " ".join(f"{prefix}{_alpha_suffix(index)}" for index in range(count)) + " "


def priority2_fixture_spec() -> FixtureSpec:
    """A confidence-positive companion to Component 0's deliberately tiny structural fixture."""
    atoms = (
        AtomSeed("h0", _tokens("heading", 8), "n-sec", "heading"),
        AtomSeed("a0", _tokens("first", 24), "l0", SLOT_BODY),
        AtomSeed("a1", _tokens("second", 24), "l0", SLOT_BODY),
        AtomSeed("a2", _tokens("third", 24), "l0", SLOT_BODY),
        AtomSeed("b0", _tokens("fourth", 36), "l1", SLOT_BODY),
        AtomSeed("b1", _tokens("source", 36), "l1", SLOT_BODY),
        AtomSeed("s0", _tokens("signature", 8), "n-sec", "signature"),
        AtomSeed("c0", _tokens("sixth", 36), "l2", SLOT_BODY),
        AtomSeed("c1", _tokens("seventh", 36), "l2", SLOT_BODY),
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
        NodeSeed("l0", "block", "leaf", body=("a0", "a1", "a2")),
        NodeSeed("l1", "block", "leaf", body=("b0", "b1")),
        NodeSeed("l2", "block", "leaf", body=("c0", "c1")),
    )
    return FixtureSpec(
        root_id="n-root", nodes=nodes, atoms=atoms, require_tokenless_cases=False
    )


def _interior_char_config(spec: FixtureSpec) -> DriftConfig:
    old = next(atom.text for atom in spec.atoms if atom.key == "b1")
    # source... -> saurce... is one registered OCR-class o→a substitution, well inside l1.
    fresh = old.replace("o", "a", 1)
    return DriftConfig(
        "inv2-interior-char-sub",
        2601,
        (DriftOperation("char_sub", ("b1",), ("b1-edit",), (fresh,)),),
    )


@lru_cache(maxsize=1)
def priority2_shared_corpus() -> SharedInvariantCorpus:
    """The exact corpus/config consumed by both INV-1 and INV-2."""
    base = component0_fixture_spec()
    cases = [
        CorpusCase(
            case.name,
            materialize_fixture(base, case),
            required_inv2=(SlotRef("l0", SLOT_BODY),)
            if case.name == "split-token-boundary"
            else (),
        )
        for case in component0_case_matrix().cases
    ]
    rich = priority2_fixture_spec()
    char_config = _interior_char_config(rich)
    cases.append(
        CorpusCase(
            char_config.name,
            materialize_fixture(rich, char_config),
            required_inv2=(SlotRef("l1", SLOT_BODY),),
        )
    )
    merge_config = DriftConfig(
        "inv2-atom-merge",
        2602,
        (DriftOperation("merge", ("b0", "b1"), ("b-merge",)),),
    )
    cases.append(
        CorpusCase(
            merge_config.name,
            materialize_fixture(base, merge_config),
            required_inv2=(SlotRef("l1", SLOT_BODY),),
        )
    )
    cases.extend(
        (
            CorpusCase(
                "anchor-poor-within-container",
                anchor_density_fixture(ANCHOR_POOR_SENTINEL),
            ),
            CorpusCase(
                "anchor-poor-cross-container",
                anchor_density_fixture(ANCHOR_POOR_SENTINEL, cross_container=True),
            ),
        )
    )
    cases.extend(
        CorpusCase(f"shared-{config.name}", materialize_fixture(base, config))
        for config in (
            seeded_supplemental_config(base, seed=seed)
            for seed in PRIORITY2_RANDOM_SEEDS
        )
    )
    return SharedInvariantCorpus(tuple(cases), PRIORITY2_RANDOM_SEEDS)


def anchor_density_fixture(
    knob: AnchorDensityKnob, *, cross_container: bool = False
) -> RebindFixtureBundle:
    """Materialize a rich (one copy) or analytically anchor-poor (repeated) sentinel."""
    repeat_width = 4 * BOUNDARY_ANCHOR_FOOTPRINT_W + 2
    passage = tuple(f"repeat{_alpha_suffix(index)}" for index in range(repeat_width))
    midpoint = repeat_width // 2
    atoms: list[AtomSeed] = []
    nodes: list[NodeSeed] = [NodeSeed("root", "volume", "container")]
    children: list[str] = []
    for copy_index in range(knob.repeat_copies):
        copy_children: list[str] = []
        for half, words in (
            ("left", passage[:midpoint]),
            ("right", passage[midpoint:]),
        ):
            node_id = f"leaf-{copy_index}-{half}"
            atom_key = f"atom-{copy_index}-{half}"
            copy_children.append(node_id)
            nodes.append(NodeSeed(node_id, "block", "leaf", body=(atom_key,)))
            atoms.append(AtomSeed(atom_key, " ".join(words), node_id, SLOT_BODY))
        if cross_container:
            container_id = f"container-{copy_index}"
            children.append(container_id)
            nodes.append(
                NodeSeed(
                    container_id,
                    "section",
                    "container",
                    children=tuple(copy_children),
                )
            )
        else:
            children.extend(copy_children)
        if copy_index + 1 < knob.repeat_copies:
            node_id = f"separator-{copy_index}"
            atom_key = f"separator-atom-{copy_index}"
            children.append(node_id)
            nodes.append(NodeSeed(node_id, "block", "leaf", body=(atom_key,)))
            atoms.append(
                AtomSeed(
                    atom_key,
                    _tokens(f"separator{_alpha_suffix(copy_index)}", 3),
                    node_id,
                    SLOT_BODY,
                )
            )
    nodes[0] = NodeSeed("root", "volume", "container", children=tuple(children))
    spec = FixtureSpec(
        root_id="root",
        nodes=tuple(nodes),
        atoms=tuple(atoms),
        require_tokenless_cases=False,
    )
    return materialize_fixture(
        spec,
        DriftConfig(
            f"anchor-density-{'cross' if cross_container else 'within'}-copies-"
            f"{knob.repeat_copies}",
            2850 + knob.repeat_copies if cross_container else 2800 + knob.repeat_copies,
            (),
        ),
    )


def _node_slot_keys(spec: FixtureSpec) -> dict[SlotRef, tuple[str, ...]]:
    slots: dict[SlotRef, tuple[str, ...]] = {}
    for node in spec.nodes:
        for slot_name, keys in (
            (SLOT_BODY, node.body),
            ("heading", node.heading),
            ("signature", node.signature),
        ):
            if keys:
                slots[SlotRef(node.node_id, slot_name)] = keys
    return slots


def _atom_token_intervals(
    bundle: RebindFixtureBundle, *, fresh: bool
) -> dict[str, tuple[int, int]]:
    stream = bundle.fresh_canonical if fresh else bundle.old_canonical
    intervals: dict[str, tuple[int, int]] = {}
    cursor = 0
    for atom in stream.atoms:
        start = cursor
        cursor += len(normalize_tokens(atom.text))
        intervals[atom.atom_id] = (start, cursor)
    return intervals


def _stream_tokens(bundle: RebindFixtureBundle, *, fresh: bool) -> tuple[str, ...]:
    stream = bundle.fresh_canonical if fresh else bundle.old_canonical
    return tuple(
        token for atom in stream.atoms for token in normalize_tokens(atom.text)
    )


def _slot_old_ids(bundle: RebindFixtureBundle, slot: SlotRef) -> tuple[str, ...]:
    keys = _node_slot_keys(bundle.spec)[slot]
    old_by_key = {
        seed.key: atom.atom_id
        for seed, atom in zip(bundle.spec.atoms, bundle.old_canonical.atoms)
    }
    return tuple(old_by_key[key] for key in keys)


def planted_tuples(
    bundle: RebindFixtureBundle, slot: SlotRef
) -> tuple[tuple[str, ...], ...]:
    """Return relation-derived legal atom tuples, including explicit seam-insert alternatives."""
    old_ids = frozenset(_slot_old_ids(bundle, slot))
    ancestry: dict[str, frozenset[str]] = {}
    for old_id, fresh_id in bundle.relation.pairs:
        ancestry[fresh_id] = ancestry.get(fresh_id, frozenset()) | frozenset({old_id})

    # A many-to-one atom crossing a slot seam cannot be represented by whole-atom ownership.
    if any(
        bool(parents & old_ids) and not parents <= old_ids
        for parents in ancestry.values()
    ):
        return ()

    base = {
        fresh_id
        for fresh_id, parents in ancestry.items()
        if parents and parents <= old_ids
    }
    mandatory: set[str] = set()
    optional: list[str] = []
    for fresh_id, owners in bundle.insertion_ownership.items():
        if owners == frozenset({(slot.node_id, slot.slot_name)}):
            mandatory.add(fresh_id)
        elif (slot.node_id, slot.slot_name) in owners:
            optional.append(fresh_id)
    if len(optional) > REFERENCE_MAX_OPTIONAL_INSERTS:
        raise ValueError(
            f"reference insertion-attribution bound exceeded: optional={len(optional)}, "
            f"max={REFERENCE_MAX_OPTIONAL_INSERTS}"
        )

    order = {
        atom_id: index for index, atom_id in enumerate(bundle.relation.fresh_order)
    }
    candidates: set[tuple[str, ...]] = set()
    for choices in product((False, True), repeat=len(optional)):
        selected = (
            base
            | mandatory
            | {atom_id for atom_id, include in zip(optional, choices) if include}
        )
        if selected:
            candidates.add(tuple(sorted(selected, key=order.__getitem__)))
    return tuple(sorted(candidates))


def _edit_reference(
    old_tokens: tuple[str, ...], fresh_tokens: tuple[str, ...]
) -> tuple[list[list[int]], list[list[int]], int, int]:
    """Enumerate the bounded edit grid with no production pruning; path count saturates at two."""
    n, m = len(old_tokens), len(fresh_tokens)
    if n > REFERENCE_MAX_TOKENS or m > REFERENCE_MAX_TOKENS:
        raise ValueError(
            f"reference alignment bound exceeded: old={n}, fresh={m}, max={REFERENCE_MAX_TOKENS}"
        )
    forward = [[0] * (m + 1) for _ in range(n + 1)]
    counts = [[0] * (m + 1) for _ in range(n + 1)]
    counts[0][0] = 1
    for i in range(n + 1):
        for j in range(m + 1):
            if i == j == 0:
                continue
            choices: list[tuple[int, int]] = []
            if i:
                choices.append((forward[i - 1][j] + 1, counts[i - 1][j]))
            if j:
                choices.append((forward[i][j - 1] + 1, counts[i][j - 1]))
            if i and j:
                choices.append(
                    (
                        forward[i - 1][j - 1]
                        + (old_tokens[i - 1] != fresh_tokens[j - 1]),
                        counts[i - 1][j - 1],
                    )
                )
            best = min(cost for cost, _ in choices)
            forward[i][j] = best
            counts[i][j] = min(2, sum(count for cost, count in choices if cost == best))

    backward = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n, -1, -1):
        for j in range(m, -1, -1):
            if i == n and j == m:
                continue
            choices = []
            if i < n:
                choices.append(backward[i + 1][j] + 1)
            if j < m:
                choices.append(backward[i][j + 1] + 1)
            if i < n and j < m:
                choices.append(
                    backward[i + 1][j + 1] + (old_tokens[i] != fresh_tokens[j])
                )
            backward[i][j] = min(choices)
    return forward, backward, forward[n][m], counts[n][m]


def _boundary_mappings(
    old_boundary: int,
    forward: list[list[int]],
    backward: list[list[int]],
    distance: int,
) -> tuple[int, ...]:
    return tuple(
        fresh_boundary
        for fresh_boundary in range(len(forward[0]))
        if forward[old_boundary][fresh_boundary]
        + backward[old_boundary][fresh_boundary]
        == distance
    )


def _is_contiguous_tuple(
    bundle: RebindFixtureBundle, atom_ids: tuple[str, ...]
) -> bool:
    positions = [bundle.relation.fresh_order.index(atom_id) for atom_id in atom_ids]
    return positions == list(range(positions[0], positions[-1] + 1))


def _tuple_token_span(
    atom_ids: tuple[str, ...], intervals: Mapping[str, tuple[int, int]]
) -> tuple[int, int]:
    return intervals[atom_ids[0]][0], intervals[atom_ids[-1]][1]


def _shingles(tokens: tuple[str, ...], k: int) -> frozenset[str]:
    if not tokens:
        return frozenset()
    effective = min(k, len(tokens)) if k >= 1 else 1
    return frozenset(
        " ".join(tokens[index : index + effective])
        for index in range(len(tokens) - effective + 1)
    )


def _independent_score(
    old_tokens: tuple[str, ...], fresh_tokens: tuple[str, ...], k: int
) -> float:
    old, fresh = _shingles(old_tokens, k), _shingles(fresh_tokens, k)
    union = old | fresh
    return len(old & fresh) / len(union) if union else 0.0


def _stored_k(bundle: RebindFixtureBundle, slot: SlotRef) -> int | None:
    raw = next(
        node for node in bundle.old_map.doc["nodes"] if node["node_id"] == slot.node_id
    )
    fingerprint = (
        raw.get("rebind_anchors", {}).get("content_fingerprint", {}).get(slot.slot_name)
    )
    return fingerprint.get("k") if fingerprint else None


def _boundary_is_uniquely_content_anchored(
    old_tokens: tuple[str, ...],
    fresh_tokens: tuple[str, ...],
    old_span: tuple[int, int],
    fresh_span: tuple[int, int],
) -> bool:
    """A strict representation-agnostic item-2 sentinel.

    Each inside-adjacent boundary token must be unchanged and whole-stream unique in both streams.
    Any non-empty content anchor touching that boundary token is therefore unique regardless of how
    #48 allocates prefix/exact/suffix within W.  Repeated-passage sentinels fail this analytically.
    """
    old_start, old_end = old_span
    fresh_start, fresh_end = fresh_span
    if old_start == old_end or fresh_start == fresh_end:
        return False
    pairs = (
        (old_tokens[old_start], fresh_tokens[fresh_start]),
        (old_tokens[old_end - 1], fresh_tokens[fresh_end - 1]),
    )
    old_counts, fresh_counts = Counter(old_tokens), Counter(fresh_tokens)
    return all(
        old_token == fresh_token
        and old_counts[old_token] == 1
        and fresh_counts[fresh_token] == 1
        for old_token, fresh_token in pairs
    )


def slot_oracle(bundle: RebindFixtureBundle, slot: SlotRef) -> SlotOracle:
    old_ids = _slot_old_ids(bundle, slot)
    candidates = planted_tuples(bundle, slot)
    if not candidates:
        return SlotOracle(
            slot, old_ids, (), frozenset(), ("unrepresentable-destination",), ()
        )

    old_tokens = _stream_tokens(bundle, fresh=False)
    fresh_tokens = _stream_tokens(bundle, fresh=True)
    old_intervals = _atom_token_intervals(bundle, fresh=False)
    fresh_intervals = _atom_token_intervals(bundle, fresh=True)
    old_span = _tuple_token_span(old_ids, old_intervals)
    forward, backward, distance, path_count = _edit_reference(old_tokens, fresh_tokens)
    old_slot_tokens = old_tokens[old_span[0] : old_span[1]]
    k = _stored_k(bundle, slot)
    tau = ORACLE_TAU_BY_MODE[bundle.geometry_mode]
    allowed: set[AllowedBind] = set()
    facts: list[AlignmentFacts] = []
    reasons: set[str] = set()
    for candidate in candidates:
        if not _is_contiguous_tuple(bundle, candidate):
            reasons.add("noncontiguous-planted-destination")
            continue
        fresh_span = _tuple_token_span(candidate, fresh_intervals)
        start_mappings = _boundary_mappings(old_span[0], forward, backward, distance)
        end_mappings = _boundary_mappings(old_span[1], forward, backward, distance)
        alignment = AlignmentFacts(
            distance,
            path_count,
            old_span[0],
            old_span[1],
            fresh_span[0],
            fresh_span[1],
            start_mappings,
            end_mappings,
        )
        facts.append(alignment)
        fresh_slot_tokens = fresh_tokens[fresh_span[0] : fresh_span[1]]
        if not alignment.planted_feasible:
            reasons.add("planted-destination-infeasible")
            continue
        if alignment.has_boundary_alternative:
            reasons.add("multiple-optimal-boundary-projections")
            continue
        if k is None or _independent_score(old_slot_tokens, fresh_slot_tokens, k) < tau:
            reasons.add("content-below-tau")
            continue
        if not _boundary_is_uniquely_content_anchored(
            old_tokens, fresh_tokens, old_span, fresh_span
        ):
            reasons.add("boundary-not-unique-in-both")
            continue
        # Positional confirmation is not inferred from uniqueness: the unique located boundaries
        # must be exactly the independently projected planted boundaries.
        if start_mappings != (fresh_span[0],) or end_mappings != (fresh_span[1],):
            reasons.add("located-boundary-maps-far")
            continue
        allowed.add(AllowedBind(slot, candidate))
    return SlotOracle(
        slot,
        old_ids,
        candidates,
        frozenset(allowed),
        tuple(sorted(reasons)),
        tuple(facts),
    )


def case_oracle(bundle: RebindFixtureBundle) -> dict[SlotRef, SlotOracle]:
    return {
        slot: slot_oracle(bundle, slot) for slot in sorted(_node_slot_keys(bundle.spec))
    }


def allowed_bind_set(bundle: RebindFixtureBundle) -> frozenset[AllowedBind]:
    return frozenset(
        allowed
        for slot_truth in case_oracle(bundle).values()
        for allowed in slot_truth.allowed
    )


def assert_bound_subset_and_disjoint(
    observed: Iterable[ObservedBind], allowed: frozenset[AllowedBind]
) -> None:
    """INV-1's pairwise ceiling plus always-on fresh-atom disjointness conjunct."""
    observed_tuple = tuple(observed)
    observed_slots = [bind.slot for bind in observed_tuple]
    if len(observed_slots) != len(set(observed_slots)):
        raise AssertionError(
            "INV-1 mechanism reported more than one bind for the same slot"
        )
    observed_as_allowed = {
        AllowedBind(bind.slot, tuple(bind.fresh_atom_ids)) for bind in observed_tuple
    }
    unexpected = observed_as_allowed - allowed
    if unexpected:
        rendered = sorted(
            (bind.slot.node_id, bind.slot.slot_name, bind.fresh_atom_ids)
            for bind in unexpected
        )
        raise AssertionError(
            f"INV-1 false bind(s) outside provenance/reference oracle: {rendered}"
        )

    claims: dict[str, set[SlotRef]] = {}
    for bind in observed_tuple:
        if len(bind.fresh_atom_ids) != len(set(bind.fresh_atom_ids)):
            raise AssertionError(f"INV-1 duplicate atom inside one slot bind: {bind}")
        for atom_id in bind.fresh_atom_ids:
            claims.setdefault(atom_id, set()).add(bind.slot)
    contested = {
        atom_id: sorted(owners) for atom_id, owners in claims.items() if len(owners) > 1
    }
    if contested:
        raise AssertionError(
            f"INV-1 fresh atoms claimed by multiple slots: {contested}"
        )


def assert_insert_coverage_not_silent(
    bundle: RebindFixtureBundle, observed: ObservedCase
) -> None:
    """An unclaimed insert is legal only while at least one legal owner fails loud.

    Once every legal owner has auto-bound, leaving the atom out of every tuple silently violates
    full included-atom coverage.  ``None`` in fixture truth represents the explicit abstention
    alternative; it does not authorize a clean all-bound report with missing coverage.
    """
    claimed = {atom_id for bind in observed.binds for atom_id in bind.fresh_atom_ids}
    for atom_id, legal in bundle.insertion_ownership.items():
        if atom_id in claimed:
            continue
        legal_slots = frozenset(
            SlotRef(owner[0], owner[1]) for owner in legal if owner is not None
        )
        if legal_slots and legal_slots.isdisjoint(observed.unresolved_slots):
            raise AssertionError(
                f"INV-1 inserted atom {atom_id!r} silently dropped although all legal owners bound"
            )


def diagnose_case(
    case_name: str,
    slots: Iterable[SlotRef],
    observed: Iterable[ObservedBind],
    allowed: frozenset[AllowedBind],
) -> CaseDiagnostic:
    """Per-case diagnostic counts only; callers must not turn these into an acceptance rate."""
    observed_by_slot: dict[SlotRef, list[ObservedBind]] = {}
    for bind in observed:
        observed_by_slot.setdefault(bind.slot, []).append(bind)
    correct = wrong = abstained = 0
    for slot in slots:
        binds = observed_by_slot.get(slot, [])
        if not binds:
            abstained += 1
        elif (
            len(binds) != 1 or AllowedBind(slot, binds[0].fresh_atom_ids) not in allowed
        ):
            wrong += 1
        else:
            correct += 1
    return CaseDiagnostic(case_name, correct, abstained, wrong)


def required_inv2_binds(
    corpus: SharedInvariantCorpus,
) -> dict[str, tuple[AllowedBind, ...]]:
    """The by-construction INV-2 positive matrix; every named row must have one exact pair."""
    required: dict[str, tuple[AllowedBind, ...]] = {}
    for case in corpus.cases:
        pairs: list[AllowedBind] = []
        truths = case_oracle(case.bundle)
        for slot in case.required_inv2:
            allowed = sorted(
                truths[slot].allowed,
                key=lambda bind: bind.fresh_atom_ids,
            )
            if len(allowed) != 1:
                raise AssertionError(
                    f"INV-2 fixture {case.name}/{slot} must admit exactly one bind; "
                    f"allowed={allowed}, reasons={truths[slot].blocked_reasons}"
                )
            pairs.extend(allowed)
        if pairs:
            required[case.name] = tuple(pairs)
    return required
