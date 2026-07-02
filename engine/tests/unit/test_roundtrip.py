"""S1.2 — the model-level raw round-trip floor (ENGINE_STRUCTURE_TASKS / PLAN §3.0/§9; D22).

The floor that makes an L1 atom's address *durable*: the raw witness text a ``raw_span`` +
``raw_source_hash`` point at must be recoverable byte-for-byte and provably unchanged, and a
normalized ``text`` may differ from that raw only by declared, reversible transforms. ``norm_layer``
is a label, never the guarantee — these tests pin exactly that.

Two tiers (§9), each proven red on violation (red-first, PLAN §9):
  - **(a) raw — byte-exact.** ``reconstruct_raw`` recovers ``source[start:end]`` byte-exact incl.
    multi-byte codepoints (``test_reconstruct_raw_*``); it raises on a hash mismatch (drifted
    source) or an out-of-bounds span — the negative cases a label cannot fake (D22). Red-inputs:
    drop the hash check → a wrong slice returns silently; drop the bounds check → an IndexError-free
    bad slice.
  - **(b) normalized — reversible.** ``apply_forward``/``apply_inverse`` compose transforms (inverse
    in *reverse* order — ``test_apply_inverse_reverses_order``, red-input: fold forward); a genuinely
    reversible transform round-trips and a *lossy* one does not (``test_is_reversible_*``); and
    ``verify_atom_roundtrip`` ties the tiers together — it recovers the raw, confirms the declared
    transforms produce the stored ``text``, and confirms their inverses recover the raw, failing
    loud otherwise (``test_verify_atom_roundtrip_*``).

The headline (``test_norm_layer_label_does_not_fake_the_floor``): an atom whose ``norm_layer`` claims
the text is verbatim, but whose stored ``text`` is not the raw, still fails — the floor checks bytes,
not the label. This is the model floor (in-memory ``source_text``); the real-input floor against the
committed PLL witnesses is S1.4.
"""

from __future__ import annotations

import hashlib
import re

import pytest

from engine.errors import RoundTripError
from engine.structure import (
    Atom,
    Geom,
    ReversibleTransform,
    apply_forward,
    apply_inverse,
    hash_raw,
    is_reversible,
    reconstruct_raw,
    verify_atom_roundtrip,
)


def _raw_atom(source: str, start: int, end: int, *, atom_id: str = "ac_0001", **over) -> Atom:
    """An atom addressing ``source[start:end]``, well-formed by construction: its ``raw_source_hash``
    is the hash of that slice, and ``text`` defaults to the slice (a raw-only atom). Overrides let a
    test introduce a *normalized* text or a deliberate lie."""
    slice_ = source[start:end]
    base = dict(
        atom_id=atom_id,
        text=slice_,
        raw_span=(start, end),
        raw_source_hash=hash_raw(slice_),
        page_range=(1, 1),
        norm_layer="raw",
        geom=Geom.absent(),
        capture_provenance_class="authorial",
    )
    base.update(over)
    return Atom(**base)


# --- hash_raw: the canonical, contract-pinned hash ---------------------------------------- #

def test_hash_raw_is_sha256_utf8_with_prefix():
    # Pin the contract (algorithm + encoding + prefix), not just "returns a string": an independent
    # hashlib computation must agree. Changing the algorithm, the encoding, or the prefix reds this.
    text = "città perché — Èè"
    expected = "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert hash_raw(text) == expected
    assert hash_raw(text).startswith("sha256:")
    assert len(hash_raw(text)) == len("sha256:") + 64  # sha256 hex digest is 64 chars


def test_hash_raw_distinguishes_and_is_deterministic():
    assert hash_raw("alpha") == hash_raw("alpha")            # deterministic
    assert hash_raw("alpha") != hash_raw("alphb")            # one-char drift → different digest


# --- tier (a): raw byte-exact reconstruction ---------------------------------------------- #

def test_reconstruct_raw_recovers_the_slice_byte_exact():
    source = "the quick brown fox"
    a = _raw_atom(source, 4, 9)            # "quick"
    assert reconstruct_raw(a, source) == "quick"


def test_reconstruct_raw_is_byte_exact_over_nonascii_codepoints():
    # raw_span is in *codepoints*. A combining mark + accented vowels guard a byte-vs-codepoint
    # confusion: a byte-offset slice of this source would split a multi-byte char and never hash-match.
    source = "abc à è ́ perché xyz"      # ́ = combining acute, a standalone codepoint
    start = source.index("à")
    end = source.index("perché") + len("perché")
    a = _raw_atom(source, start, end)
    recovered = reconstruct_raw(a, source)
    assert recovered == source[start:end]
    # byte-exact: the recovered text and the source slice encode to identical UTF-8 bytes
    assert recovered.encode("utf-8") == source[start:end].encode("utf-8")


def test_reconstruct_raw_empty_slice_round_trips():
    # An empty addressed span (start == end) is degenerate but valid: it recovers "" and hashes to
    # the hash of "" — the bounds and hash logic must not special-case it away.
    source = "anything"
    a = _raw_atom(source, 3, 3)
    assert reconstruct_raw(a, source) == ""


def test_reconstruct_raw_raises_on_hash_mismatch():
    # The byte-exact floor: a source that drifted within the span no longer hashes to raw_source_hash.
    # Drop the hash check in reconstruct_raw and this returns the (wrong) slice silently — the exact
    # silent corruption the floor exists to stop.
    source = "the quick brown fox"
    a = _raw_atom(source, 4, 9)                       # pinned to "quick"
    drifted = "the QUICK brown fox"                   # same length, different bytes in the span
    with pytest.raises(RoundTripError, match="drifted or the span is wrong"):
        reconstruct_raw(a, drifted)


def test_reconstruct_raw_raises_on_out_of_bounds_span():
    source = "short"
    a = _raw_atom("short and then some longer source", 6, 30)   # span valid for the long source...
    with pytest.raises(RoundTripError, match="out of bounds"):
        reconstruct_raw(a, source)                              # ...but not for this short one


def test_reconstruct_raw_bounds_guard_catches_what_the_hash_cannot():
    # An empty-slice atom (span start == end, hash of "") with an absurd offset: Python slicing
    # source[100:100] yields "" with no IndexError, and "" hashes to the atom's stored hash — so the
    # hash check alone would PASS this malformed address. Only the bounds guard rejects it. This is
    # why the bounds check is load-bearing, not dead behind the hash.
    source = "anything"
    a = _raw_atom(source, 100, 100)                  # slice "", raw_source_hash == hash_raw("")
    with pytest.raises(RoundTripError, match="out of bounds"):
        reconstruct_raw(a, source)


# --- tier (b): declared reversible transforms --------------------------------------------- #

# Genuinely reversible: escaping newlines is reversible on text with no literal backslash-n.
_ESCAPE_NL = ReversibleTransform(
    "escape-newlines", lambda s: s.replace("\n", "\\n"), lambda s: s.replace("\\n", "\n")
)
# Lossy: collapsing space runs cannot restore the run lengths it removed — its honest inverse is
# identity, so it round-trips only on text with no space runs (the D22 negative case).
_COLLAPSE = ReversibleTransform(
    "collapse-spaces", lambda s: re.sub(r" +", " ", s), lambda s: s
)
# A non-commuting pair, to prove apply_inverse reverses ORDER (append, then whole-string reverse).
_APPEND = ReversibleTransform("append-x", lambda s: s + "X", lambda s: s[:-1])
_REVERSE = ReversibleTransform("reverse", lambda s: s[::-1], lambda s: s[::-1])


def test_apply_forward_folds_in_declaration_order():
    assert apply_forward([_APPEND, _REVERSE], "abc") == ("abc" + "X")[::-1]   # "Xcba"


def test_apply_inverse_reverses_order():
    # The composition g∘f inverts as f⁻¹∘g⁻¹. With this non-commuting pair, folding the inverses in
    # forward order yields the wrong string — so the reverse-order fold is the thing under test.
    forwarded = apply_forward([_APPEND, _REVERSE], "abc")   # "Xcba"
    assert apply_inverse([_APPEND, _REVERSE], forwarded) == "abc"


def test_is_reversible_true_for_a_reversible_transform():
    assert is_reversible([_ESCAPE_NL], "line one\nline two") is True


def test_is_reversible_false_for_a_lossy_transform():
    # The label says "transform"; the floor says otherwise. Collapsing the double space loses
    # information no inverse can restore — norm_layer is a label, never the guarantee (D22).
    assert is_reversible([_COLLAPSE], "a  b") is False
    # ...yet the SAME transform is reversible on an input it does not lose anything on — proving the
    # check is about the (transform, input) pair, not the transform's name.
    assert is_reversible([_COLLAPSE], "a b") is True


# --- the floor applied to an atom: verify_atom_roundtrip ---------------------------------- #

def test_verify_atom_roundtrip_raw_only_atom():
    source = "verbatim capture here"
    a = _raw_atom(source, 0, 8)                 # text == raw == "verbatim", no transforms
    assert verify_atom_roundtrip(a, source) == "verbatim"


def test_verify_atom_roundtrip_with_reversible_transform():
    # A normalized atom: raw has a newline, text is the escaped form. The declared transform both
    # produces text from raw and recovers raw from text — the (a)+(b) success path.
    source = "head\ntail end"
    raw = source[0:9]                            # "head\ntail"
    a = _raw_atom(source, 0, 9, text=_ESCAPE_NL.forward(raw), norm_layer="escape-newlines")
    assert a.text == "head\\ntail"               # the stored text is the escaped form, not the raw
    assert verify_atom_roundtrip(a, source, [_ESCAPE_NL]) == raw


def test_verify_atom_roundtrip_raises_when_transforms_do_not_produce_text():
    # Step 2: the declared transforms must actually produce the stored text. Here they don't.
    source = "hello world"
    a = _raw_atom(source, 0, 5, text="HELLO")    # raw is "hello"; no transform makes "HELLO"
    with pytest.raises(RoundTripError, match="do not produce its stored text"):
        verify_atom_roundtrip(a, source, [])     # forward([], raw) == "hello" != "HELLO"


def test_verify_atom_roundtrip_raises_on_lossy_transform():
    # Step 3 — the D22 headline at atom level: a lossy collapse produces the stored text (forward
    # matches) but cannot recover the raw, so the normalized tier fails loud. The norm_layer label
    # "collapse-spaces" does not make it reversible.
    source = "a  b trailing"
    raw = source[0:4]                            # "a  b" (two spaces)
    a = _raw_atom(source, 0, 4, text=_COLLAPSE.forward(raw), norm_layer="collapse-spaces")
    assert a.text == "a b"                       # forward collapsed the run...
    with pytest.raises(RoundTripError, match="not the guarantee"):
        verify_atom_roundtrip(a, source, [_COLLAPSE])   # ...inverse cannot restore it


def test_verify_atom_roundtrip_gates_on_the_raw_tier_first():
    # The raw floor (a) precedes (b): a drifted source fails at reconstruct_raw, before any
    # transform check — so a broken address can never reach the normalized tier.
    source = "head\ntail end"
    a = _raw_atom(source, 0, 9, text=_ESCAPE_NL.forward(source[0:9]), norm_layer="escape-newlines")
    with pytest.raises(RoundTripError, match="drifted or the span is wrong"):
        verify_atom_roundtrip(a, "HEAD\ntail end", [_ESCAPE_NL])


def test_norm_layer_label_does_not_fake_the_floor():
    # The whole point of S1.2 in one test: an atom *claims* its text is verbatim (norm_layer="raw",
    # no transforms), but the stored text is not the raw bytes. The floor checks the bytes via the
    # hash + transform identity, not the label, so it fails loud.
    source = "the real raw bytes"
    a = _raw_atom(source, 0, 8, text="THE REAL", norm_layer="raw")   # claims verbatim, lies
    with pytest.raises(RoundTripError):
        verify_atom_roundtrip(a, source)                            # transforms default to ()
