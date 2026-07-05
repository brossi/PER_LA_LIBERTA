"""Segmentation front-end — the density band pre-check (S2.1.4, #38; ``s2_1_plan.md`` DT-6).

Before the witness↔geometry matcher (#37) trusts a page's OCR boxes, this classifier answers a
prior question: **can the boxes be trusted at all, or is the page a near-blank / dark leaf whose
boxes are OCR hallucination?** The S2.0 adversarial audit's Finding B killed the single fixed ink
threshold (ink fraction is a non-monotone continuum — a dark endpaper reads 0.97, a real
chapter-end reads < 0.038), so the pre-check is a **two-sided band classifier** over four per-page
features, calibrated to *abstain* rather than guess.

- :class:`PageDensityFeatures` — the per-page feature vector: ``ink_fraction`` (binarized pixmap),
  ``box_count``, ``token_yield`` (alpha-token count / box count — the discriminator: PLL's ghost
  leaf p6 is 658 boxes / ~7 real tokens, yield ≈ 0.01), and ``mean_token_length``. Validity is
  enforced at construction.
- :class:`DensityBand` — the four-class output ``{content, near_blank, non_text_dark, abstain}``.
  ``abstain`` is a **first-class** result routing to the human worklist (#40), never a class forced
  onto an ambiguous page (G-9). ``near_blank`` (low ink, low yield) and ``non_text_dark`` (high ink,
  low yield) are distinct classes but both mean *boxes untrusted* (G-11).
- :class:`DensityClassifier` — maps features → a :class:`DensityVerdict`. Its band thresholds are
  **required constructor parameters with no defaults** (the G-1 numberless-core posture — a baked
  default band is a scan-profile opinion in core; PLL's calibrated values live in ``manifest.json``,
  DT-6/R7). Confidence is the **margin to the nearest band edge**, never the raw ink fraction
  (Finding B's trap: ink-confidence is maximal on exactly the hallucination-prone dark pages).

Pure-core discipline: no language, no book literal, no witness text — the classifier operates on
boxes and pixmaps only (DT-1; the S0.2 neutrality guard scans this module). The **feature
definitions** (the 2-char alpha-token floor, the luma binarization cutoff) are fixed, versioned
constants under :data:`SEGMENTATION_VERSION` — a definition change bumps the version; the **band
values** are book config. That split lets the sidecar (DT-9) distinguish "classifier changed" from
"input changed" mechanically (G-22).
"""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # annotation-only: resolves ``fitz.Pixmap`` for type-checkers without a runtime import
    import fitz

# NB: ``fitz`` (PyMuPDF) is imported lazily inside :func:`ink_fraction_from_pixmap`, not at module
# top level, so ``import engine.structure`` stays fitz-free — the classifier and its records are pure
# and are what the sidecar/#39/#40 consumers load; only the pixmap-extraction helper touches PyMuPDF,
# matching the core/backend isolation where the fitz OCR backend (``geometry_pymupdf``) is likewise
# not imported by the package ``__init__``. Type annotations name ``fitz.Pixmap`` but never evaluate
# it (``from __future__ import annotations``). Precedent: ``engine/steps/ocr.py``.

# Feature-definition constants — part of the SEGMENTATION_VERSION contract, NOT book config.
# Language-neutral by construction (a codepoint-class rule and a luminance cutoff carry no
# source-language or typeface opinion — the neutrality budget governs literals, DT-6). A change to
# either changes what the features *mean*, so it bumps the version string below.
SEGMENTATION_VERSION = "density-bands-v1"

# An "alpha token" (a real word for the token-yield signal) is an edge-stripped box text of at least
# this many characters that carries at least one letter. The floor drops the single-character bleed /
# pencil-mark boxes that dominate a hallucinated leaf (p6) while costing only the rare 1-char function
# word on a real page (whose hundreds of longer tokens keep yield high anyway).
_MIN_ALPHA_TOKEN_LEN = 2

# A grayscale pixel darker than this (0 = black, 255 = white) counts as ink. A mid-gray cutoff keeps
# only clearly-dark marks — scanned paper (~200-240) never counts, text/bleed/endpaper does.
_INK_LUMA_THRESHOLD = 128

# ``\W`` is Unicode-aware (any non-alphanumeric, non-underscore) — a neutral edge strip, no Latin
# bias. A digit-only box ("35" folio) survives the strip but fails the has-a-letter test below.
_EDGE = re.compile(r"^\W+|\W+$")

# 256-entry map: dark luma -> 1, light -> 0, so a page's ink count is one C-speed ``bytes.translate``
# + ``.count(1)`` rather than a per-pixel Python loop (an 8 MP page at 300 dpi is otherwise ruinous).
_INK_TABLE = bytes(1 if v < _INK_LUMA_THRESHOLD else 0 for v in range(256))


class DensityBand(Enum):
    """The four-class density verdict (DT-6). ``ABSTAIN`` is first-class — it routes to the worklist,
    it is never a fallback synonym for one of the trusted/untrusted classes."""

    CONTENT = "content"
    NEAR_BLANK = "near_blank"
    NON_TEXT_DARK = "non_text_dark"
    ABSTAIN = "abstain"


@dataclass(frozen=True, slots=True)
class PageDensityFeatures:
    """One page's density feature vector (DT-6), the input the classifier maps to a band.

    ``ink_fraction`` and ``token_yield`` are fractions in ``[0, 1]``; ``box_count`` is a non-negative
    count; ``mean_token_length`` is a non-negative mean over the page's box texts. Validity is
    enforced at construction — a non-finite or out-of-range feature is an extractor bug, made
    unconstructible here rather than silently classified. A genuinely blank page (``box_count == 0``,
    ``token_yield == 0.0``) is valid, not an error.
    """

    ink_fraction: float
    box_count: int
    token_yield: float
    mean_token_length: float

    def __post_init__(self) -> None:
        for name in ("ink_fraction", "token_yield"):
            v = getattr(self, name)
            if not (math.isfinite(v) and 0.0 <= v <= 1.0):
                raise ValueError(f"PageDensityFeatures.{name} must be a fraction in [0, 1], got {v!r}")
        # Exact-int (not ``>= 0``): a bool is an int subclass but not a box count, and ``nan``/float
        # would slip a numeric bound — the same trap PageGeometry.page closes.
        if not (type(self.box_count) is int and self.box_count >= 0):
            raise ValueError(
                f"PageDensityFeatures.box_count must be a non-negative integer, got {self.box_count!r}"
            )
        if not (math.isfinite(self.mean_token_length) and self.mean_token_length >= 0.0):
            raise ValueError(
                f"PageDensityFeatures.mean_token_length must be a non-negative number, "
                f"got {self.mean_token_length!r}"
            )


@dataclass(frozen=True, slots=True)
class DensityVerdict:
    """A classified page: its :class:`DensityBand`, the ``confidence`` margin that placed it there,
    and the routing ``signal`` (the worklist's ``signal`` field for a routed page, DT-10).

    ``confidence`` is the margin to the nearest band edge (never the raw ink fraction) — for a
    trusted/untrusted class it is ``>= confidence_margin``; for a routed page it is the sub-margin
    distance that tripped the route (``0.0`` when the page is in the inherently-undecidable
    ink-ambiguous mid-band).
    """

    band: DensityBand
    confidence: float
    signal: str

    def __post_init__(self) -> None:
        if not (math.isfinite(self.confidence) and self.confidence >= 0.0):
            raise ValueError(
                f"DensityVerdict.confidence must be a non-negative margin, got {self.confidence!r}"
            )
        if not self.signal:
            raise ValueError("DensityVerdict.signal must name the deciding/routing basis")

    @property
    def routed(self) -> bool:
        """True iff the page abstained — it goes to the human worklist, no automatic trust decision."""
        return self.band is DensityBand.ABSTAIN

    @property
    def boxes_trusted(self) -> bool:
        """True only for ``CONTENT``. ``near_blank`` and ``non_text_dark`` both mean boxes untrusted
        (G-11); ``abstain`` is undecided, not trusted."""
        return self.band is DensityBand.CONTENT


def edge_strip(text: str) -> str:
    """Strip leading/trailing non-word characters (Unicode-aware, neutral). Public for the calibration
    probe and tests, which reproduce the alpha-token definition."""
    return _EDGE.sub("", text)


def is_alpha_token(text: str) -> bool:
    """True iff ``text`` is a real word token for the yield signal: ``>= _MIN_ALPHA_TOKEN_LEN`` chars
    after the edge strip and carrying at least one letter (a digit-only folio fails)."""
    stripped = edge_strip(text)
    return len(stripped) >= _MIN_ALPHA_TOKEN_LEN and any(c.isalpha() for c in stripped)


def ink_fraction_from_pixmap(pixmap: fitz.Pixmap) -> float:
    """Fraction of a page pixmap that is ink (dark) — the binarized-ink density feature (DT-6).

    Normalizes any colorspace/alpha to plain grayscale, then counts pixels below
    :data:`_INK_LUMA_THRESHOLD`. A zero-area pixmap yields ``0.0`` (no ink), never a divide error.
    """
    import fitz  # PyMuPDF — lazy so the package import stays fitz-free (see module note).

    pm = pixmap
    if pm.colorspace is None or pm.colorspace.n != 1:
        pm = fitz.Pixmap(fitz.csGRAY, pm)  # convert to single-channel luminance
    if pm.alpha:
        pm = fitz.Pixmap(pm, 0)  # drop the alpha channel so samples are one byte per pixel
    luma = pm.samples
    if not luma:
        return 0.0
    return luma.translate(_INK_TABLE).count(1) / len(luma)


def page_density_features(*, ink_fraction: float, boxes: Sequence) -> PageDensityFeatures:
    """Assemble a :class:`PageDensityFeatures` from a page's ink fraction and its OCR boxes.

    ``boxes`` is any sequence of records carrying a ``.text`` token (a :class:`~engine.structure.
    geometry.WordBox` in production; a fake in tests — the seam takes no witness and no language).
    ``token_yield`` = alpha-token count / box count; ``mean_token_length`` = mean edge-stripped
    length over **all** boxes (so a leaf of single-char fragments reads short, the hallucination
    tell). A page with zero boxes yields zero yield and zero mean, not a divide error.
    """
    box_count = len(boxes)
    stripped = [edge_strip(b.text) for b in boxes]
    alpha_count = sum(1 for s in stripped if len(s) >= _MIN_ALPHA_TOKEN_LEN and any(c.isalpha() for c in s))
    token_yield = alpha_count / box_count if box_count else 0.0
    mean_token_length = sum(len(s) for s in stripped) / box_count if box_count else 0.0
    return PageDensityFeatures(
        ink_fraction=ink_fraction,
        box_count=box_count,
        token_yield=token_yield,
        mean_token_length=mean_token_length,
    )


class DensityClassifier:
    """Maps :class:`PageDensityFeatures` to a :class:`DensityVerdict` against calibrated band edges.

    Constructor band thresholds are **keyword-only and required — no defaults** (DT-6 / G-1): a
    default band would bake a scan-profile opinion into neutral core. PLL's values come from
    ``manifest.json`` (book config), the labeled calibration set from
    ``books/<id>/review/density_calibration.json`` (DT-6/R7).

    The decision plane is two-sided: ``token_yield`` is the trust axis (real words vs hallucinated
    boxes) and ``ink_fraction`` splits an untrusted page into ``near_blank`` (low ink) vs
    ``non_text_dark`` (high ink); ``box_content_min`` is a hard eligibility gate (a two-box divider
    is not content however clean its two tokens). ``confidence`` is the margin to the nearest edge
    that would change the class; a page inside ``confidence_margin`` of an edge, or in the
    low-yield ink mid-band, **abstains** — the never-guess posture (G-9).
    """

    def __init__(
        self,
        *,
        yield_content_min: float,
        box_content_min: int,
        ink_blank_max: float,
        ink_dark_min: float,
        confidence_margin: float,
    ) -> None:
        if not (math.isfinite(yield_content_min) and 0.0 < yield_content_min <= 1.0):
            raise ValueError(f"yield_content_min must be in (0, 1], got {yield_content_min!r}")
        if not (type(box_content_min) is int and box_content_min >= 0):
            raise ValueError(f"box_content_min must be a non-negative integer, got {box_content_min!r}")
        if not (math.isfinite(ink_blank_max) and 0.0 <= ink_blank_max < 1.0):
            raise ValueError(f"ink_blank_max must be in [0, 1), got {ink_blank_max!r}")
        if not (math.isfinite(ink_dark_min) and 0.0 < ink_dark_min <= 1.0):
            raise ValueError(f"ink_dark_min must be in (0, 1], got {ink_dark_min!r}")
        # The two ink edges must leave a real mid-band — else a low-yield page could never land in
        # the inherently-ambiguous ink zone the two-sided design needs (and the classes would overlap).
        if not (ink_blank_max < ink_dark_min):
            raise ValueError(
                f"ink_blank_max ({ink_blank_max!r}) must be strictly below ink_dark_min ({ink_dark_min!r})"
            )
        if not (math.isfinite(confidence_margin) and 0.0 < confidence_margin <= 1.0):
            raise ValueError(f"confidence_margin must be in (0, 1], got {confidence_margin!r}")
        self._yield_content_min = yield_content_min
        self._box_content_min = box_content_min
        self._ink_blank_max = ink_blank_max
        self._ink_dark_min = ink_dark_min
        self._confidence_margin = confidence_margin

    @property
    def version(self) -> str:
        return SEGMENTATION_VERSION

    @property
    def params(self) -> dict[str, float | int]:
        """The band values, for the sidecar ``classifier_params`` (DT-9) and the DT-10 input
        fingerprint. Ordered so the fingerprint is stable."""
        return {
            "yield_content_min": self._yield_content_min,
            "box_content_min": self._box_content_min,
            "ink_blank_max": self._ink_blank_max,
            "ink_dark_min": self._ink_dark_min,
            "confidence_margin": self._confidence_margin,
        }

    def classify(self, features: PageDensityFeatures) -> DensityVerdict:
        """Classify one page. Pure function of ``(band values, features)`` — deterministic."""
        yield_ok = features.token_yield >= self._yield_content_min
        boxes_ok = features.box_count >= self._box_content_min

        if yield_ok and boxes_ok:
            raw = DensityBand.CONTENT
            # The nearest flip out of content is losing yield_ok; box_content_min is a hard gate, not
            # a confidence axis (a content page sits far above it — DT-6's axes are yield and ink).
            margin = features.token_yield - self._yield_content_min
        elif features.ink_fraction <= self._ink_blank_max:
            raw = DensityBand.NEAR_BLANK
            margin = self._ink_blank_max - features.ink_fraction  # distance up to the ink mid-band
            if boxes_ok:
                # Only yield keeps it out of content (boxes already clear the gate), so yield is also
                # a live edge; when boxes are short too, more boxes are needed to reach content, so
                # the yield axis alone cannot flip it and is not a near edge.
                margin = min(margin, self._yield_content_min - features.token_yield)
        elif features.ink_fraction >= self._ink_dark_min:
            raw = DensityBand.NON_TEXT_DARK
            margin = features.ink_fraction - self._ink_dark_min  # distance down to the ink mid-band
            if boxes_ok:
                margin = min(margin, self._yield_content_min - features.token_yield)
        else:
            # Low yield/boxes with ink in the mid-band: cannot tell near-blank from dark. Inherently
            # undecidable — route, do not guess (G-9). Confidence 0.0: maximally uncertain.
            return DensityVerdict(DensityBand.ABSTAIN, confidence=0.0, signal="ink-ambiguous")

        if margin < self._confidence_margin:
            # Inside the band-edge margin: too close to call, route rather than commit (G-9).
            return DensityVerdict(DensityBand.ABSTAIN, confidence=margin, signal="band-margin")
        return DensityVerdict(raw, confidence=margin, signal=raw.value)

    def classify_page(self, *, pixmap: fitz.Pixmap, boxes: Sequence) -> tuple[PageDensityFeatures, DensityVerdict]:
        """Extract features from a page pixmap + its boxes, then classify. The calibration probe (#38)
        and the two-branch wiring (#39) enter here; returns both so the features can be recorded."""
        features = page_density_features(ink_fraction=ink_fraction_from_pixmap(pixmap), boxes=boxes)
        return features, self.classify(features)
