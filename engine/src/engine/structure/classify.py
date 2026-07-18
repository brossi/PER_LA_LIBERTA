"""The ``BlockClassifier`` seam (concern A's typing step) + its degenerate stub.

Concern A emits a *typed* atom stream (PLAN §2-A, R3): each captured block carries a class
(heading / body / verse / … — the vocabulary is the **book's**, declared in the structure
profile §7.1, never named here in core). The typing is book-specific and **correctable**: B may
re-type a block (R3/D5), so every classification records *who* typed it (``typed_by``) and a
``confidence`` B weighs against. This module fixes only the seam — the ``Protocol`` S1.3b's typed
projection binds against — plus a degenerate stub that stands in until the real S9 recognizer
exists.

The stub classifies **every** atom ``UNKNOWN``: it is *incomplete by construction*, never a
plausible-looking green. ``UNKNOWN`` is the engine-level "not yet classified" sentinel — a
first-class *incomplete* state (S1.3b's completeness check FAILS on an all-``UNKNOWN``
projection), distinct from any real class a profile declares. Core names only ``UNKNOWN``; every
other label is profile data (``feedback_engine_agnostic``).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

#: The engine-level "not yet classified" block class — a first-class *incomplete* state, never a
#: real class. The structure profile declares all real classes (§7.1); core knows only this one.
UNKNOWN = "unknown"

#: ``typed_by`` provenance the degenerate stub stamps. It names itself so an all-``UNKNOWN``
#: projection is attributable to the placeholder, never silently passed off as a real typing.
DEGENERATE_CLASSIFIER_NAME = "degenerate-all-unknown"


@dataclass(frozen=True, slots=True)
class BlockClassification:
    """One atom's class + the provenance B needs to override it (R3/D5).

    ``block_class`` is a profile-declared label or ``UNKNOWN``. ``typed_by`` names the classifier
    (so a re-type by B stays attributable, never anonymous); ``confidence`` is what B weighs — the
    degenerate stub reports ``0.0`` (it asserts no knowledge), so its output can never be mistaken
    for a real classification. Frozen: a classification is a record, re-typing produces a new one.
    """

    block_class: str
    typed_by: str
    confidence: float

    def __post_init__(self) -> None:
        # ``typed_by`` is the attribution B relies on to override a typing (R3/D5); an empty one is
        # an anonymous classification, which the "never an anonymous label" guarantee above forbids.
        if not self.typed_by:
            raise ValueError(
                "BlockClassification.typed_by must name the classifier (never anonymous) — a "
                "re-type by B stays attributable only if every classification records who typed it."
            )


class BlockClassifier(Protocol):
    """Concern A's typing seam: map a source-ordered atom stream to one ``BlockClassification``
    per atom, in order (PLAN §2-A, R3). Injectable so S1.3b — and tests — bind to the seam, not
    the real S9 recognizer. The result is **positionally aligned** with the input (same length,
    same order), so a caller can ``zip`` atoms with their classes.

    The atom element type is intentionally unconstrained here: this seam is defined *before* the
    concrete L1 ``Atom`` (S1.1) exists, so a backend reads whatever shape it needs and S9 binds
    the real type. The stub ignores element content entirely.
    """

    def classify(self, atoms: Sequence[object]) -> Sequence[BlockClassification]: ...


# --- degenerate stub (all-UNKNOWN; the real backend is S9) ------------------------------ #

class DegenerateBlockClassifier:
    """The S0.4 placeholder ``BlockClassifier``: classifies **every** atom ``UNKNOWN`` with
    ``confidence=0.0``. Incomplete by construction — S1.3b's completeness check fails on its
    output rather than treating an all-``UNKNOWN`` projection as done. It exists only to give
    S1.3b a nameable seam to wire against before S9 lands, and is built so it can never pass as a
    real classifier.
    """

    def classify(self, atoms: Sequence[object]) -> list[BlockClassification]:
        return [
            BlockClassification(
                block_class=UNKNOWN,
                typed_by=DEGENERATE_CLASSIFIER_NAME,
                confidence=0.0,
            )
            for _ in atoms
        ]
