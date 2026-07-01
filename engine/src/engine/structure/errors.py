"""Closed structure-map validation-code vocabulary (S4 §4.0) + its §4.1 partition.

Every reason a structure map can fail Tier-2 semantic validation — plus the writer's overwrite
guard and the schema born-gate — is one member of :class:`EC`, defined here and nowhere else
(invariant I5, single-sourcing): the per-module validators (``projection.py``, ``handles.py``) *will*
raise these codes, the aggregate ``validate_structure_map`` *will* collect them, and lineage
governance (S8.1) routes remediation on the code *value*. Those consumers arrive at B-2..B-5; B-1
ships only the vocabulary + partition. The set is **closed**: ``test_structure_errors.py`` pins it to
exactly the §4.0 codes, so a new failure mode is a deliberate edit here plus a matching test line —
never an ad hoc string, and never a "non-exhaustive" hedge (M2).

Partition (§4.1) — the set splits disjointly into four **explicitly-enumerated** buckets. Making each
bucket an explicit literal (rather than deriving the collect-all set as a complement) is deliberate:
a code added to :class:`EC` but left out of every bucket makes the four-bucket union ``!= EC``, so the
partition test goes red and *forces* a conscious Tier-2a-vs-Tier-2b decision at the point of addition
(without it, an unclassified new precondition would silently default into collect-all — the P3A-3 /
P3A-5 co-fire defect §4.1's two-phase design exists to prevent). The buckets:

- **Tier-2a preconditions** (:data:`TIER_2A_CODES`) — ``DUPLICATE_NODE_ID`` / ``ROOT_ID_DANGLING``:
  the two checks that must pass *before* the ``node_id``-keyed table and the root-anchored traversal
  can be built. They **short-circuit** (the first failure raises immediately) rather than joining the
  collect-all set — the only reason they cannot co-fire a second root/identity code (P3A-3/P3A-5).
- **Tier-2b** (:data:`TIER_2B_CODES`) — every other validator code, collected in one pass and raised
  together as a payload.
- the **writer** code (:data:`WRITER_CODES`) — ``MAP_OVERWRITE_BLOCKED``, raised by
  ``write_structure_map``, not the validator.
- the **born-gate** code (:data:`BORN_GATE_CODES`) — ``SCHEMA_NOT_BORN``, raised only by
  ``assert_schema_born`` (never the validator, never the born-agnostic loader).

Carries no language/book/typeface literal (invariant I4; the S0.2 neutrality scan covers this module
by dynamic glob). **No exception type lives here yet** (YAGNI): the first raiser is B-2's projection
validator, which will own the exception that carries a collected code payload; it is added when that
raiser exists, not pre-populated here.
"""

from __future__ import annotations

import enum


class EC(enum.StrEnum):
    """A structure-map error code (§4.0) — a Tier-2 validation-failure reason, or a non-validator
    producer code (the writer overwrite guard / the schema born-gate); see the four buckets below.

    A :class:`enum.StrEnum` so a member *is* its wire token in every position: it compares equal to
    its name, and ``str()`` / f-strings / ``%s`` / ``json.dumps`` all emit the bare token (``"CYCLE"``,
    not ``"EC.CYCLE"``) — so a code interpolated into an error message or log line round-trips through
    ``EC(...)`` and matches what S8.1 routes on. (A plain ``str, Enum`` mixin would emit ``"EC.CYCLE"``
    from ``str()``/f-strings — the trap this class avoids.) ``repr`` still shows ``<EC.CYCLE: 'CYCLE'>``
    so debugging keeps the class name. Each value is written explicitly equal to the member name — the
    redundancy is the point (one obvious source of truth; ``StrEnum.auto()`` would lowercase the name
    and break ``value == name``).
    """

    # -- ownership / coverage / atom-reference (validator, Tier-2b) --
    DUP_OWNERSHIP = "DUP_OWNERSHIP"
    UNOWNED_INCLUDED_ATOM = "UNOWNED_INCLUDED_ATOM"
    OWNED_EXCLUDED_ATOM = "OWNED_EXCLUDED_ATOM"
    DANGLING_ATOM_REF = "DANGLING_ATOM_REF"
    # -- node identity (DUPLICATE_NODE_ID is a Tier-2a precondition) + child-reference integrity --
    DUPLICATE_NODE_ID = "DUPLICATE_NODE_ID"
    DANGLING_REF = "DANGLING_REF"
    ORPHAN_NODE = "ORPHAN_NODE"
    MULTI_PARENT = "MULTI_PARENT"
    DUPLICATE_CHILD_REF = "DUPLICATE_CHILD_REF"
    # -- root topology (ROOT_ID_DANGLING is a Tier-2a precondition) --
    ROOT_ID_DANGLING = "ROOT_ID_DANGLING"
    NO_ROOT = "NO_ROOT"
    MULTIPLE_ROOTS = "MULTIPLE_ROOTS"
    EMPTY_CONTAINER = "EMPTY_CONTAINER"
    # -- traversal --
    CYCLE = "CYCLE"
    UNREACHABLE_NODE = "UNREACHABLE_NODE"
    # -- body ordering --
    BODY_ATOMS_UNORDERED = "BODY_ATOMS_UNORDERED"
    # -- aliases --
    ALIAS_COLLISION = "ALIAS_COLLISION"
    ALIAS_DANGLING_TARGET = "ALIAS_DANGLING_TARGET"
    ALIAS_INTERVAL_INVALID = "ALIAS_INTERVAL_INVALID"
    ALIAS_TEMPORAL_INCOMPLETE = "ALIAS_TEMPORAL_INCOMPLETE"
    # -- identity minting / class-kind --
    NODE_ID_DERIVED = "NODE_ID_DERIVED"
    MINTED_BY_SPLIT = "MINTED_BY_SPLIT"
    CLASS_KIND_MISMATCH = "CLASS_KIND_MISMATCH"
    # -- handle policy --
    POLICY_NOT_IN_VOCAB = "POLICY_NOT_IN_VOCAB"
    POLICY_UNRESOLVED = "POLICY_UNRESOLVED"
    # -- vocab hygiene --
    VOCAB_UNKNOWN_COLLISION = "VOCAB_UNKNOWN_COLLISION"
    VOCAB_EMPTY = "VOCAB_EMPTY"
    VOCAB_DUPLICATE = "VOCAB_DUPLICATE"
    VOCAB_UNUSED = "VOCAB_UNUSED"
    # -- non-validator producers --
    MAP_OVERWRITE_BLOCKED = "MAP_OVERWRITE_BLOCKED"  # writer (write_structure_map)
    SCHEMA_NOT_BORN = "SCHEMA_NOT_BORN"  # born-gate (assert_schema_born)


#: §4.1 Tier-2a — structural preconditions that short-circuit (raise on the first failure) so they
#: cannot co-fire a second root/identity code. Explicit membership (P3A-3/P3A-5).
TIER_2A_CODES = frozenset({EC.DUPLICATE_NODE_ID, EC.ROOT_ID_DANGLING})
#: §4.1 Tier-2b — the collect-all validator codes, enumerated **explicitly** (not derived as a
#: complement) so that an unclassified new code fails the four-bucket partition test rather than
#: silently defaulting here. Every validator code that is not a Tier-2a precondition.
TIER_2B_CODES = frozenset(
    {
        EC.DUP_OWNERSHIP,
        EC.UNOWNED_INCLUDED_ATOM,
        EC.OWNED_EXCLUDED_ATOM,
        EC.DANGLING_ATOM_REF,
        EC.DANGLING_REF,
        EC.ORPHAN_NODE,
        EC.MULTI_PARENT,
        EC.DUPLICATE_CHILD_REF,
        EC.NO_ROOT,
        EC.MULTIPLE_ROOTS,
        EC.EMPTY_CONTAINER,
        EC.CYCLE,
        EC.UNREACHABLE_NODE,
        EC.BODY_ATOMS_UNORDERED,
        EC.ALIAS_COLLISION,
        EC.ALIAS_DANGLING_TARGET,
        EC.ALIAS_INTERVAL_INVALID,
        EC.ALIAS_TEMPORAL_INCOMPLETE,
        EC.NODE_ID_DERIVED,
        EC.MINTED_BY_SPLIT,
        EC.CLASS_KIND_MISMATCH,
        EC.POLICY_NOT_IN_VOCAB,
        EC.POLICY_UNRESOLVED,
        EC.VOCAB_UNKNOWN_COLLISION,
        EC.VOCAB_EMPTY,
        EC.VOCAB_DUPLICATE,
        EC.VOCAB_UNUSED,
    }
)
#: §4.1 — the writer-owned guard, raised by ``write_structure_map`` (not a validator code).
WRITER_CODES = frozenset({EC.MAP_OVERWRITE_BLOCKED})
#: §4.1 — the born-gate code, raised only by ``assert_schema_born`` (not the validator/loader).
BORN_GATE_CODES = frozenset({EC.SCHEMA_NOT_BORN})
#: Everything the semantic validator can raise = Tier-2a preconditions ⊎ Tier-2b collect-all. Derived
#: **upward** from the two explicit validator buckets; the test cross-checks it against the
#: complement ``EC - WRITER - BORN_GATE`` so a mis-enumerated ``TIER_2B_CODES`` is caught.
VALIDATOR_CODES = TIER_2A_CODES | TIER_2B_CODES
