"""The L1 ``Atom`` model — immutable, addressed capture units (ENGINE_STRUCTURE_PLAN §3.0/§3.2).

An atom is one captured unit of source text carrying a *durable address*: a raw codepoint span +
the hash of the raw witness text it addresses, a page/scan range, an optional word-box geometry,
and a normalization-layer label. Nothing downstream recomputes these from mutated text, so an atom
stays addressable across every later stage. Identity is ``atom_id`` (text evidence + coordinates),
deliberately distinct from the structural ``node_id`` minted at L2.

Two stream flavours share this one type (§11.1): a **per-witness** atom names its ``witness`` and
carries that witness's own geometry; a **canonical** (reconciled) atom has no single witness and
instead back-links through ``derived_from`` to the per-witness atoms it was reconciled from.

``geom`` (D30) is the part S1.1 *freezes the shape of*: the primary re-binding signal and the base
layer for space reconstruction. Its slot is Optional, and **absence is a first-class state — never
invented coordinates.** One witness flavour (Gemini-vision text) has no word-box layer at all, and
because the boxes come from a *different* OCR pass than the witness text, a box is not a fact about
that text until a matcher proves it — so every present box records its match-provenance
(``geometry_engine`` / ``matched_witness_id`` / ``match_method`` / ``match_confidence``). The
matcher (S2.1) writes into this slot and S4.4's schema reads it, so the field *set* is locked here.

Pure core: no language, ordinal, or book-structure opinion lives here — capture classes and witness
names are caller-supplied strings (the S0.2 neutrality guard scans this module).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

# ``processing_scope`` vocabulary (S1.3a; §3.0/§3.3). Capture-time inclusion of an atom's bytes in
# downstream processing — the field that makes *captured-but-excluded* distinct from *never-captured*
# (the distinction the no-loss round-trip checks against, §9). ``included`` is the body default;
# furniture/wrapper atoms (page markers, running heads) are captured with ``excluded``. These are
# neutral process labels, not the derived behavioral flags (translatable/alignable/…) policy computes
# at S6 — those switch on this plus L2 content provenance.
PROCESSING_SCOPE_INCLUDED = "included"
PROCESSING_SCOPE_EXCLUDED = "excluded"


@dataclass(frozen=True, slots=True)
class Geom:
    """Optional word-box geometry for an atom, with match-provenance (D30; PLAN §3.0/§11.1).

    ``present`` is the ``{present | absent}`` state. When **absent**, every coordinate/provenance
    field is ``None`` — an absent geom that carried coordinates would be *invented geometry*, which
    construction forbids. When **present**, all six fields are required (a half-built box fails
    loud, never silently half-present) and ``bbox`` is exactly four floats ``[x0, y0, x1, y1]``.
    Use the :meth:`absent` / :meth:`matched` factories; the field set is frozen because S2's matcher
    writes it and S4.4's schema consumes it.
    """

    present: bool
    page: int | None = None
    bbox: tuple[float, float, float, float] | None = None
    geometry_engine: str | None = None
    matched_witness_id: str | None = None
    match_method: str | None = None
    match_confidence: float | None = None

    def __post_init__(self) -> None:
        coords = (
            self.page,
            self.bbox,
            self.geometry_engine,
            self.matched_witness_id,
            self.match_method,
            self.match_confidence,
        )
        if self.present:
            if any(v is None for v in coords):
                raise ValueError(
                    "a present geom must carry full match-provenance (page, bbox, geometry_engine, "
                    "matched_witness_id, match_method, match_confidence)"
                )
            object.__setattr__(self, "bbox", tuple(self.bbox))
            if len(self.bbox) != 4:
                raise ValueError(f"bbox must be four floats [x0, y0, x1, y1], got {len(self.bbox)}")
        elif any(v is not None for v in coords):
            raise ValueError(
                "an absent geom must not carry coordinates — absence is a first-class state, never "
                "invented geometry"
            )

    @classmethod
    def absent(cls) -> "Geom":
        """A geom with no geometry: the witness has no word-box layer, or no box matched its text."""
        return cls(present=False)

    @classmethod
    def matched(
        cls,
        *,
        page: int,
        bbox: tuple[float, float, float, float],
        geometry_engine: str,
        matched_witness_id: str,
        match_method: str,
        match_confidence: float,
    ) -> "Geom":
        """A matched word-box union with its full provenance (what S2.1's matcher writes).

        Named ``matched`` rather than ``present`` because ``present`` is the state *field* — a
        present geom is precisely a box a matcher aligned to the witness text.
        """
        return cls(
            present=True,
            page=page,
            bbox=bbox,
            geometry_engine=geometry_engine,
            matched_witness_id=matched_witness_id,
            match_method=match_method,
            match_confidence=match_confidence,
        )


@dataclass(frozen=True, slots=True)
class AtomDerivation:
    """One back-link from a canonical atom to a per-witness atom it was reconciled from (§11.1)."""

    witness: str
    atom_id: str


@dataclass(frozen=True, slots=True)
class Atom:
    """An immutable, addressed L1 capture unit (§3.0/§3.2/§11.1).

    Required address: ``atom_id`` (L1 identity), ``text``, ``raw_span`` (codepoint ``[start, end]``
    into the raw witness), ``raw_source_hash`` (pins the raw text that span addresses — the binding
    guarantee behind the byte-exact round-trip tier, S1.2), ``page_range`` (``[first, last]``),
    ``norm_layer`` (a human-readable normalization label, *never* the loss guarantee), ``geom``, and
    ``capture_provenance_class`` (the L1 *capture* provenance — how/whence the bytes were captured;
    a field deliberately distinct from L2's content/editorial provenance, S6.1). ``witness`` and
    ``derived_from`` are the per-witness vs canonical discriminators (§11.1) and default to the
    canonical-less / un-derived case. ``processing_scope`` (S1.3a) is the capture-time inclusion
    label — ``"included"`` body default, ``"excluded"`` for captured-but-not-processed furniture
    (§3.0; ``PROCESSING_SCOPE_*``). Sequence fields are normalized to tuples so the frozen guarantee
    cannot be undermined by a retained mutable handle.
    """

    atom_id: str
    text: str
    raw_span: tuple[int, int]
    raw_source_hash: str
    page_range: tuple[int, int]
    norm_layer: str
    geom: Geom
    capture_provenance_class: str
    witness: str | None = None
    derived_from: tuple[AtomDerivation, ...] = ()
    processing_scope: str = PROCESSING_SCOPE_INCLUDED

    def __post_init__(self) -> None:
        object.__setattr__(self, "raw_span", tuple(self.raw_span))
        object.__setattr__(self, "page_range", tuple(self.page_range))
        object.__setattr__(self, "derived_from", tuple(self.derived_from))
        if len(self.raw_span) != 2:
            raise ValueError("raw_span must be [start, end] codepoint offsets")
        if len(self.page_range) != 2:
            raise ValueError("page_range must be [first_page, last_page]")
        if self.processing_scope not in (PROCESSING_SCOPE_INCLUDED, PROCESSING_SCOPE_EXCLUDED):
            # Closed vocabulary: an out-of-vocab value (a typo, a stray label) must fail at
            # construction, not silently slip past downstream filters keyed on these two states
            # (e.g. the S1.3b completeness scope) and vanish from a check that should have seen it.
            raise ValueError(
                f"processing_scope must be {PROCESSING_SCOPE_INCLUDED!r} or "
                f"{PROCESSING_SCOPE_EXCLUDED!r}, got {self.processing_scope!r}"
            )


def duplicate_atom_ids(atoms: Iterable[Atom]) -> list[str]:
    """The ``atom_id``s appearing more than once in ``atoms`` (empty = all unique), each reported
    once in first-collision order.

    ``atom_id`` is L1 identity, so a stream with a repeated id is malformed. This is the reusable
    uniqueness primitive the atom store (S1.5) and raw capture (S1.3a) enforce against; the model
    itself does not police cross-atom uniqueness, it makes uniqueness *checkable*.
    """
    seen: set[str] = set()
    dups: list[str] = []
    for atom in atoms:
        if atom.atom_id in seen:
            if atom.atom_id not in dups:
                dups.append(atom.atom_id)
        else:
            seen.add(atom.atom_id)
    return dups
