"""S4.0 / B-1 — the closed structure-map validation code set (``EC.*``) and its §4.1 partition.

``engine.structure.errors`` is the single home of the S4 §4.0 validation-code vocabulary: a change
to the set has exactly one edit site (invariant I5, single-sourcing), and governance (S8.1) routes
remediation on the code *value*. These tests pin the set exhaustively — the exact codes §4.0
enumerates, no more, no fewer — and its §4.1 partition into
``{validator-collected: Tier-2a ⊎ Tier-2b} ⊎ {writer} ⊎ {born-gate}``.

Invariants (each proven red on violation — red-first, ENGINE_STRUCTURE_PLAN §9):
  - **inv 12c** — the ``EC`` set equals the closed §4.0 set; adding or removing a code without
    updating ``EXPECTED_CODES`` below goes red (``test_ec_set_is_exactly_the_closed_s4_set``). This
    literal *is* the pin — there is no "non-exhaustive" hedge (M2).
  - the four buckets partition ``EC`` (pairwise-disjoint, union == ``EC``), and the three *special*
    buckets — the Tier-2a short-circuit preconditions, the writer code, the born-gate code — match
    §4.1 exactly; a mis-bucketed special code goes red (``test_special_buckets_*`` /
    ``test_the_four_buckets_partition_*``).
  - each member's ``value`` equals its ``name`` and the member IS its wire string, so a code routed
    by S8.1 and the source symbol cannot drift (``test_ec_values_equal_their_names``).
"""

from __future__ import annotations

import json
from itertools import combinations

from engine.structure import errors
from engine.structure.errors import EC

# The closed set §4.0 enumerates. This literal is the exhaustiveness pin: changing ``errors.EC`` in
# *either* direction without changing this set reddens ``test_ec_set_is_exactly_the_closed_s4_set``.
EXPECTED_CODES = {
    # ownership / coverage / atom-reference (validator, Tier-2b)
    "DUP_OWNERSHIP",
    "UNOWNED_INCLUDED_ATOM",
    "OWNED_EXCLUDED_ATOM",
    "DANGLING_ATOM_REF",
    # node identity (DUPLICATE_NODE_ID is Tier-2a) + child-reference integrity
    "DUPLICATE_NODE_ID",
    "DANGLING_REF",
    "ORPHAN_NODE",
    "MULTI_PARENT",
    "DUPLICATE_CHILD_REF",
    # root topology (ROOT_ID_DANGLING is Tier-2a)
    "ROOT_ID_DANGLING",
    "NO_ROOT",
    "MULTIPLE_ROOTS",
    "EMPTY_CONTAINER",
    # traversal
    "CYCLE",
    "UNREACHABLE_NODE",
    # body ordering
    "BODY_ATOMS_UNORDERED",
    # aliases
    "ALIAS_COLLISION",
    "ALIAS_DANGLING_TARGET",
    "ALIAS_INTERVAL_INVALID",
    "ALIAS_TEMPORAL_INCOMPLETE",
    # identity minting / class-kind
    "NODE_ID_DERIVED",
    "MINTED_BY_SPLIT",
    "CLASS_KIND_MISMATCH",
    # handle policy
    "POLICY_NOT_IN_VOCAB",
    "POLICY_UNRESOLVED",
    # vocab hygiene
    "VOCAB_UNKNOWN_COLLISION",
    "VOCAB_EMPTY",
    "VOCAB_DUPLICATE",
    "VOCAB_UNUSED",
    # non-validator producers
    "MAP_OVERWRITE_BLOCKED",  # writer (write_structure_map)
    "SCHEMA_NOT_BORN",  # born-gate (assert_schema_born)
}


def test_ec_set_is_exactly_the_closed_s4_set():
    # inv 12c: the code module equals the §4.0 closed set — exhaustive, no hedge (M2).
    assert {c.name for c in EC} == EXPECTED_CODES


def test_ec_values_equal_their_names():
    # S8.1 routes on the code value; a str-valued code whose value == name means the routed token
    # and the source symbol never drift, and it JSON-serializes as itself.
    for c in EC:
        assert c.value == c.name
        assert c == c.name  # StrEnum: the member IS its wire string


def test_ec_member_is_its_wire_token_in_every_position():
    # The module contract is "a member IS its wire token". A plain (str, Enum) mixin honours that for
    # == and json.dumps but NOT for str()/f-strings (which yield "EC.CYCLE" and do not round-trip
    # through EC(...)) — the exact trap enum.StrEnum removes. Pin every emission position so a
    # regression back to (str, Enum) reddens here, not in a downstream log line.
    for c in EC:
        assert str(c) == c.name  # str() emits the bare token, not "EC.<name>"
        assert f"{c}" == c.name  # f-string / __format__ likewise
        assert "%s" % c == c.name  # %-formatting (routes through __str__) likewise
        assert json.dumps(c) == f'"{c.name}"'  # serializes as itself
        assert EC(str(c)) is c  # and round-trips: str() output resolves back to the member


def test_no_duplicate_value_aliases():
    # Every member is a distinct code — a hand-edit giving two members the same value would make the
    # second a silent alias, hidden from iteration (and thus from the exhaustiveness/value tests,
    # which iterate canonical members only). __members__ counts aliases; list(EC) does not.
    assert len(list(EC)) == len(EC.__members__)


def test_special_buckets_match_the_s4_1_partition():
    # The three *special* buckets are pinned by explicit membership (§4.1). Tier-2b is the default
    # (everything else validator-owned), so pinning the specials pins the whole split.
    assert errors.TIER_2A_CODES == {EC.DUPLICATE_NODE_ID, EC.ROOT_ID_DANGLING}
    assert errors.WRITER_CODES == {EC.MAP_OVERWRITE_BLOCKED}
    assert errors.BORN_GATE_CODES == {EC.SCHEMA_NOT_BORN}


def test_the_four_buckets_partition_the_code_set():
    # Because TIER_2B_CODES is an EXPLICIT literal (not a complement), the union clause is a real
    # forcing function: a code added to EC but left out of every bucket makes union != EC and reddens
    # here, forcing a conscious Tier-2a-vs-Tier-2b classification. (With TIER_2B as a complement this
    # union would be tautological — the audit finding this closes.)
    buckets = (
        errors.TIER_2A_CODES,
        errors.TIER_2B_CODES,
        errors.WRITER_CODES,
        errors.BORN_GATE_CODES,
    )
    # union covers the whole set — an unclassified new code (in EC, in no bucket) fails here
    assert set().union(*buckets) == set(EC)
    # pairwise-disjoint — no code lands in two buckets
    for a, b in combinations(buckets, 2):
        assert not (set(a) & set(b)), f"code(s) in two buckets: {set(a) & set(b)}"
    # each part non-empty
    for bucket in buckets:
        assert bucket


def test_tier_2b_is_the_explicit_complement_of_the_special_buckets():
    # Cross-check the hand-enumerated TIER_2B_CODES against the derived complement, so a typo in the
    # explicit list (a dropped or extra Tier-2b code) is caught here even if the union still balances.
    assert errors.TIER_2B_CODES == set(EC) - errors.TIER_2A_CODES - errors.WRITER_CODES - errors.BORN_GATE_CODES


def test_validator_codes_are_exactly_tier_2a_plus_tier_2b():
    # VALIDATOR_CODES is derived UPWARD from the two explicit validator buckets; this pins it against
    # the complement so the writer guard and born-gate are provably excluded from the validator set.
    assert errors.VALIDATOR_CODES == errors.TIER_2A_CODES | errors.TIER_2B_CODES
    assert errors.VALIDATOR_CODES == set(EC) - errors.WRITER_CODES - errors.BORN_GATE_CODES
