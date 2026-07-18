"""S1.2 — the model-level raw round-trip floor (ENGINE_STRUCTURE_PLAN §3.0/§9; D22).

An L1 atom's address (``raw_span`` + ``raw_source_hash``) only earns the word *durable* if the
raw witness text it points at can be recovered byte-for-byte and proven unchanged. This module is
that proof, in two tiers (§9):

- **(a) raw — byte-exact.** :func:`reconstruct_raw` slices ``source_text[start:end]`` and asserts
  the slice hashes to the atom's ``raw_source_hash``. This is the floor a ``norm_layer`` *label*
  cannot fake: the recovered bytes are checked against the captured hash, never against the label.
  A drifted source, or a wrong span, fails loud (:class:`~engine.errors.RoundTripError`).
- **(b) normalized — reversible.** A normalized atom's ``text`` may differ from its raw bytes, but
  *only by declared, reversible transforms*. A :class:`ReversibleTransform` carries a ``name`` (the
  human label) **plus** a real ``inverse``; reversibility is a property checked per input
  (:func:`is_reversible`), not asserted by the name. :func:`verify_atom_roundtrip` ties the tiers
  together: it recovers the raw (tier a), confirms the declared transforms *produce* the stored
  ``text``, and confirms their inverses *recover* the raw (tier b).

Why a label is never the guarantee (D30): the live pipeline's ``collapse_spaces`` / ``rejoin_lines``
are **not** reversible — they destroy run-length and line structure — so naming a ``norm_layer``
``"collapse_spaces"`` proves nothing. Tier (a)'s hash is the binding floor; tier (b) admits a
transform into the normalized guarantee only by exhibiting a working inverse. Recovering the *spaces*
those lossy ops removed is a separate, geometry/segmentation problem (D30, S2/S3), not an inversion.

This is the **model** floor: it operates on an in-memory ``source_text``. The real-input floor —
the same round-trip run against the committed PLL raw witnesses through the public read path — is
S1.4 (W2). Pure core: no language or book-structure opinion (the S0.2 neutrality guard scans here).
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from engine.errors import RoundTripError
from engine.structure.atoms import Atom

_HASH_PREFIX = "sha256:"


def hash_raw(raw_text: str) -> str:
    """The canonical hash of the raw text an atom's span addresses, as stored in ``raw_source_hash``.

    ``sha256:<hex>`` over the UTF-8 bytes. This is the single producer of the value the round-trip
    checks against, so an atom is well-formed precisely when
    ``atom.raw_source_hash == hash_raw(source_text[start:end])``. Hashing the *addressed slice*
    (not the whole artifact) is deliberate: it makes each atom's address verifiable on its own and
    localizes a drift to the atoms whose spans actually overlap it (§3.0 — "the raw text the span
    addresses").
    """
    return _HASH_PREFIX + hashlib.sha256(raw_text.encode("utf-8")).hexdigest()


def reconstruct_raw(atom: Atom, source_text: str) -> str:
    """Tier (a): recover the raw witness text ``atom`` addresses, byte-exact, or fail loud.

    Slices ``source_text`` at the atom's codepoint ``raw_span`` and verifies the slice hashes to
    ``raw_source_hash``. Raises :class:`~engine.errors.RoundTripError` if the span is out of bounds
    (a malformed address) or the hash mismatches (the source artifact drifted, or the span is
    wrong) — the byte-exact floor a ``norm_layer`` label cannot fake (§9; D22 negative case).
    """
    start, end = atom.raw_span
    if not 0 <= start <= end <= len(source_text):
        raise RoundTripError(
            f"raw_span {atom.raw_span} is out of bounds for a source of length "
            f"{len(source_text)} (atom {atom.atom_id!r})"
        )
    raw = source_text[start:end]
    actual = hash_raw(raw)
    if actual != atom.raw_source_hash:
        raise RoundTripError(
            f"raw round-trip failed for atom {atom.atom_id!r}: source text at {atom.raw_span} "
            f"hashes to {actual}, but the atom pins {atom.raw_source_hash} — the source artifact "
            f"drifted or the span is wrong (a norm_layer label cannot fake this)"
        )
    return raw


@dataclass(frozen=True, slots=True)
class ReversibleTransform:
    """One declared, reversible normalization step: a ``name`` label plus a real ``inverse``.

    ``name`` is the human-readable ``norm_layer`` token; it is *not* the guarantee. The guarantee is
    that ``inverse(forward(x)) == x`` for the inputs the layer is applied to — a property checked by
    :func:`is_reversible`, never inferred from ``name``. A lossy step (e.g. collapsing space runs)
    can be *named* but cannot satisfy that check on an input it loses information about, which is
    exactly how tier (b) keeps a label from standing in for the floor.
    """

    name: str
    forward: Callable[[str], str]
    inverse: Callable[[str], str]


def apply_forward(transforms: Iterable[ReversibleTransform], text: str) -> str:
    """Fold the transforms over ``text`` in declaration order (raw → normalized)."""
    for t in transforms:
        text = t.forward(text)
    return text


def apply_inverse(transforms: Iterable[ReversibleTransform], text: str) -> str:
    """Fold the inverses over ``text`` in *reverse* declaration order (normalized → raw).

    Reverse order is required: undoing a composition ``g∘f`` is ``f⁻¹∘g⁻¹``. A forward-order inverse
    would silently mis-recover whenever two steps don't commute.
    """
    for t in reversed(tuple(transforms)):
        text = t.inverse(text)
    return text


def is_reversible(transforms: Iterable[ReversibleTransform], raw: str) -> bool:
    """Whether the declared transforms round-trip ``raw``: ``inverse(forward(raw)) == raw``.

    Reversibility is a property of the transforms *for this input* — a space-collapsing step is
    reversible on text with no space runs and lossy on text that has them — so the input is part of
    the question (D22's negative case turns on exactly such an input).
    """
    transforms = tuple(transforms)
    return apply_inverse(transforms, apply_forward(transforms, raw)) == raw


def verify_atom_roundtrip(
    atom: Atom,
    source_text: str,
    transforms: Iterable[ReversibleTransform] = (),
) -> str:
    """The full floor for one atom: recover its raw (tier a) and bind its ``text`` to that raw by
    declared reversible transforms (tier b). Returns the recovered raw; raises on any failure.

    1. tier (a) — :func:`reconstruct_raw` recovers the raw bytes (hash-checked).
    2. the declared transforms must *produce* the stored ``text``: ``forward(raw) == atom.text``.
    3. and *reverse* it: ``inverse(atom.text) == raw``.

    With no transforms (the raw-only atom), steps 2–3 require ``text == raw``. A ``norm_layer`` that
    is merely a label — transforms that don't reproduce ``text``, or whose inverses don't recover
    the raw (a lossy op) — fails step 2 or 3 loud, never passes on the label alone.
    """
    raw = reconstruct_raw(atom, source_text)
    transforms = tuple(transforms)
    produced = apply_forward(transforms, raw)
    if produced != atom.text:
        raise RoundTripError(
            f"declared transforms for atom {atom.atom_id!r} (norm_layer={atom.norm_layer!r}) do "
            f"not produce its stored text: forward(raw)={produced!r} != text={atom.text!r}"
        )
    recovered = apply_inverse(transforms, atom.text)
    if recovered != raw:
        raise RoundTripError(
            f"normalized round-trip failed for atom {atom.atom_id!r} "
            f"(norm_layer={atom.norm_layer!r}): the declared transforms are not reversible — "
            f"inverse(text)={recovered!r} != raw={raw!r}. norm_layer is a label, not the guarantee"
        )
    return raw
