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
- :class:`DensityBand` — the output ``{content, near_blank, non_text_dark, cover, abstain}``.
  ``abstain`` is a **first-class** result routing to the human worklist (#40), never a class forced
  onto an ambiguous page (G-9). ``near_blank`` (low ink, low yield), ``non_text_dark`` (high ink),
  and ``cover`` (near-saturated at the document extremes) all mean *boxes untrusted* (G-11).
  ``cover`` was added as a fifth class (Ben, 2026-07-06) — see :class:`DensityBand`.
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
import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher
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
    """The density verdict (DT-6, extended). ``ABSTAIN`` is first-class — it routes to the worklist,
    it is never a fallback synonym for one of the trusted/untrusted classes.

    ``COVER`` was added as a fifth class (RULED by Ben 2026-07-06, at the S2.1.4 calibration
    checkpoint, amending DT-6's original four): a near-saturated leaf at the document extremes is
    binding material (front/back cover or pastedown endpaper), confidently untrusted and
    auto-declinable — distinct from ``NON_TEXT_DARK``, which is any other high-ink page whose
    handling (route vs auto-decline) is the worklist's. The distinction is positional × saturation:
    an interior saturated page is *not* a cover (it is an anomaly classed ``NON_TEXT_DARK``)."""

    CONTENT = "content"
    NEAR_BLANK = "near_blank"
    NON_TEXT_DARK = "non_text_dark"
    COVER = "cover"
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
        """True only for ``CONTENT``. ``near_blank`` / ``non_text_dark`` / ``cover`` all mean boxes
        untrusted (G-11); ``abstain`` is undecided, not trusted."""
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

    Decision order: a near-saturated leaf at the document extremes is a ``COVER`` (position ×
    saturation, Ben 2026-07-06); else a high-ink page is ``NON_TEXT_DARK`` — checked *before*
    content, so ``ink >= ink_dark_min`` gates content out (a saturated page can never be content on
    hallucinated yield); else ``token_yield`` (the trust axis) + ``box_content_min`` (a hard
    eligibility gate — a two-box divider is not content however clean its tokens) decide ``CONTENT``,
    with ``ink_fraction`` splitting the remaining untrusted low-yield pages into ``NEAR_BLANK`` (low
    ink) vs the ink mid-band. ``confidence`` is the margin to the nearest edge that would change the
    class; a page inside ``confidence_margin`` of an edge, or in the low-yield ink mid-band,
    **abstains** — the never-guess posture (G-9).
    """

    def __init__(
        self,
        *,
        yield_content_min: float,
        box_content_min: int,
        ink_blank_max: float,
        ink_dark_min: float,
        confidence_margin: float,
        cover_edge_leaves: int,
        ink_saturation_min: float,
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
        if not (type(cover_edge_leaves) is int and cover_edge_leaves >= 0):
            raise ValueError(f"cover_edge_leaves must be a non-negative integer, got {cover_edge_leaves!r}")
        # A cover is *near-saturated*, strictly darker than the ordinary high-ink (non_text_dark) band —
        # else "cover" would collapse into "any dark leaf at the extremes" and lose the saturation
        # signal that separates binding material from a merely-dark endpaper.
        if not (math.isfinite(ink_saturation_min) and ink_dark_min < ink_saturation_min <= 1.0):
            raise ValueError(
                f"ink_saturation_min must be in (ink_dark_min={ink_dark_min!r}, 1], got {ink_saturation_min!r}"
            )
        self._yield_content_min = yield_content_min
        self._box_content_min = box_content_min
        self._ink_blank_max = ink_blank_max
        self._ink_dark_min = ink_dark_min
        self._confidence_margin = confidence_margin
        self._cover_edge_leaves = cover_edge_leaves
        self._ink_saturation_min = ink_saturation_min

    @classmethod
    def from_config(cls, bands) -> DensityClassifier:
        """Build a classifier from a config ``DensityBands`` model (the DT-5 wiring seam, #39). Read
        duck-typed on the seven band attributes so neutral ``structure/`` needs no import of
        ``config/``; the constructor above still enforces every value range."""
        return cls(
            yield_content_min=bands.yield_content_min,
            box_content_min=bands.box_content_min,
            ink_blank_max=bands.ink_blank_max,
            ink_dark_min=bands.ink_dark_min,
            confidence_margin=bands.confidence_margin,
            cover_edge_leaves=bands.cover_edge_leaves,
            ink_saturation_min=bands.ink_saturation_min,
        )

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
            "cover_edge_leaves": self._cover_edge_leaves,
            "ink_saturation_min": self._ink_saturation_min,
        }

    def classify(self, features: PageDensityFeatures, *, leaf_index: int, n_leaves: int) -> DensityVerdict:
        """Classify one page. Pure function of ``(band values, features, position)`` — deterministic.

        ``leaf_index`` is the page's 1-based scan-leaf number and ``n_leaves`` the document leaf count
        (RULED by Ben 2026-07-06 — position is a classifier input): a near-saturated leaf within
        ``cover_edge_leaves`` of either end is a ``COVER``.
        """
        if not (type(n_leaves) is int and n_leaves >= 1):
            raise ValueError(f"n_leaves must be a positive integer leaf count, got {n_leaves!r}")
        if not (type(leaf_index) is int and 1 <= leaf_index <= n_leaves):
            raise ValueError(f"leaf_index must be an integer in [1, {n_leaves}], got {leaf_index!r}")

        yield_ok = features.token_yield >= self._yield_content_min
        boxes_ok = features.box_count >= self._box_content_min
        at_extreme = leaf_index <= self._cover_edge_leaves or leaf_index > n_leaves - self._cover_edge_leaves

        if at_extreme and features.ink_fraction >= self._ink_saturation_min:
            # Position × saturation: binding material at the extremes. Untrusted, auto-declinable.
            raw = DensityBand.COVER
            margin = features.ink_fraction - self._ink_saturation_min
        elif features.ink_fraction >= self._ink_dark_min:
            # A high-ink page's boxes are untrusted regardless of yield (Finding-B); this is also the
            # ink gate on content (RULED by Ben 2026-07-06) — checked BEFORE content, so a saturated
            # page can never be mislabeled content on hallucinated yield (calibration page 278).
            raw = DensityBand.NON_TEXT_DARK
            margin = features.ink_fraction - self._ink_dark_min  # distance down to the ink mid-band
        elif yield_ok and boxes_ok:
            raw = DensityBand.CONTENT
            # Content flips to NON_TEXT_DARK if ink rises to ink_dark_min and to ABSTAIN if yield
            # drops to the floor — the margin is the distance to the nearer of those two edges.
            margin = min(features.token_yield - self._yield_content_min,
                         self._ink_dark_min - features.ink_fraction)
        elif features.ink_fraction <= self._ink_blank_max:
            raw = DensityBand.NEAR_BLANK
            margin = self._ink_blank_max - features.ink_fraction  # distance up to the ink mid-band
            if boxes_ok:
                # Only yield keeps it out of content (boxes already clear the gate), so yield is also
                # a live edge; when boxes are short too, more boxes are needed to reach content, so
                # the yield axis alone cannot flip it and is not a near edge.
                margin = min(margin, self._yield_content_min - features.token_yield)
        else:
            # Low yield/boxes with ink in the mid-band: cannot tell near-blank from dark. Inherently
            # undecidable — route, do not guess (G-9). Confidence 0.0: maximally uncertain.
            return DensityVerdict(DensityBand.ABSTAIN, confidence=0.0, signal="ink-ambiguous")

        if margin < self._confidence_margin:
            # Inside the band-edge margin: too close to call, route rather than commit (G-9). Applies
            # to COVER too — a leaf whose ink barely clears saturation routes rather than auto-declines.
            return DensityVerdict(DensityBand.ABSTAIN, confidence=margin, signal="band-margin")
        return DensityVerdict(raw, confidence=margin, signal=raw.value)

    def classify_page(
        self, *, pixmap: fitz.Pixmap, boxes: Sequence, leaf_index: int, n_leaves: int
    ) -> tuple[PageDensityFeatures, DensityVerdict]:
        """Extract features from a page pixmap + its boxes, then classify at its leaf position. The
        calibration probe (#38) and the two-branch wiring (#39) enter here; returns both so the
        features can be recorded."""
        features = page_density_features(ink_fraction=ink_fraction_from_pixmap(pixmap), boxes=boxes)
        return features, self.classify(features, leaf_index=leaf_index, n_leaves=n_leaves)


# ================================================================================================ #
# Column / reading-order detector (S2.1.5, #39; DT-7)
#
# Promotes the S2.0 probe's ``detect_columns``/``reading_order`` into core with the adversarial
# audit's rulings baked in: a contiguous central valley (>= 3 bins) that splits the page into two
# genuinely-populated halves is a real gutter; the audit-killed ``min(single-bin)`` detector (every
# page two-column) and the redundant mirror-symmetry rule are BOTH gone. Detection is pure geometry
# — box x-centers only, no witness text, no language — so it lives in neutral core beside the density
# classifier. Like the density feature constants, the projection-profile geometry is fixed and
# versioned (``COLUMN_DETECTOR_VERSION``); the calibrated *decision* (threshold + hysteresis margin)
# is book config, defaultless (the G-1 numberless-core posture), because how deep/balanced a gutter
# must be to count is a scan-profile opinion, not a universal.
# ================================================================================================ #

# A separate version string from SEGMENTATION_VERSION: a column verdict and a density verdict have
# independent staleness (DT-9/G-22 — the sidecar fingerprints each), so an algorithm change to one
# must not silently invalidate the other. The projection-profile constants below are this string's
# contract; changing any of them bumps it.
COLUMN_DETECTOR_VERSION = "columns-v1"

# Projection-profile geometry — versioned structural constants, NOT book config (a bin count / a
# central-search window / a populated-halves band carry no source-language or typeface opinion, so
# the neutrality budget does not reach them; they define what the col2 signal MEANS, so they join
# COLUMN_DETECTOR_VERSION).
_COLUMN_MIN_BOXES = 25            # below this the profile is too sparse to assert a gutter -> 1 column
_PROJECTION_BINS = 100            # x-axis histogram resolution (page width -> this many bins)
_CENTRAL_BAND = (33, 67)         # a gutter is searched in the central third of the page only
_GUTTER_EMPTY_FRACTION = 0.15    # a bin counts as "empty" at <= this fraction of the peak bin
_MIN_GUTTER_BINS = 3             # a real gutter is a contiguous run of >= this many empty central bins
_GUTTER_CENTER_RANGE = (0.40, 0.60)     # the gutter midpoint must sit near page center
_POPULATED_HALVES_RANGE = (0.28, 0.72)  # both columns must be genuinely populated (fraction on the left)
_LINE_HEIGHT_FRACTION = 0.6      # a reading line is this fraction of the median box height (row binning)


def _box_x_center(box) -> float:
    """The x-midpoint of a box, in page-point space (``box.bbox = (x0, y0, x1, y1)``)."""
    x0, _, x1, _ = box.bbox
    return (x0 + x1) / 2.0


@dataclass(frozen=True, slots=True)
class ColumnEvidence:
    """Projection-profile evidence for one page's column layout (DT-7). Pure geometry, no config.

    ``col2_score`` = valley depth x column balance in ``[0, 1]`` — how strongly the box coordinates
    support a two-column reading. It is ``0.0`` when no structural gutter exists (a confidently
    single-column page: too few boxes, no >= 3-bin central valley, an off-center valley, or an
    unbalanced split). ``split_x`` is the gutter's page-point x when a gutter exists, else the page
    width (the whole page is one column). The *decision* (how high a score counts as two-column) is
    the :class:`ColumnDetector`'s, not this record's.
    """

    col2_score: float
    split_x: float

    def __post_init__(self) -> None:
        if not (math.isfinite(self.col2_score) and 0.0 <= self.col2_score <= 1.0):
            raise ValueError(f"ColumnEvidence.col2_score must be a fraction in [0, 1], got {self.col2_score!r}")
        if not (math.isfinite(self.split_x) and self.split_x > 0.0):
            raise ValueError(f"ColumnEvidence.split_x must be a positive page-point x, got {self.split_x!r}")


@dataclass(frozen=True, slots=True)
class ColumnVerdict:
    """A page's column decision under a calibrated :class:`ColumnDetector`.

    ``n_cols`` is the leaning column count (1 or 2) by the decision threshold; ``confidence`` is the
    margin ``|col2_score - decision_threshold|`` (distance from the decision boundary, never the raw
    score — the same edge-margin discipline the density classifier uses); ``confident`` is
    ``confidence >= hysteresis_margin`` — only a confident page's own evidence stands alone, an
    in-margin page defers to the cross-page prior (DT-7/R8). ``signal`` names the basis.
    """

    n_cols: int
    confidence: float
    confident: bool
    signal: str

    def __post_init__(self) -> None:
        if self.n_cols not in (1, 2):
            raise ValueError(f"ColumnVerdict.n_cols must be 1 or 2 (S2.1 scope), got {self.n_cols!r}")
        if not (math.isfinite(self.confidence) and self.confidence >= 0.0):
            raise ValueError(f"ColumnVerdict.confidence must be a non-negative margin, got {self.confidence!r}")
        if not self.signal:
            raise ValueError("ColumnVerdict.signal must name the deciding basis")


def detect_columns(boxes: Sequence, width: float) -> ColumnEvidence:
    """Projection-profile column evidence for one page (DT-7). Reads only box x-centers — no witness
    text, no language.

    A two-column page is one whose box x-centers form two populated clusters separated by a
    contiguous central low-density gutter. Every ``>= _MIN_GUTTER_BINS`` central empty run is a
    candidate gutter; each is scored ``col2_score = valley_depth x column_balance`` where
    ``valley_depth`` = ``1 - mean(gutter-run bin counts) / peak bin`` (how empty the gutter is
    relative to the columns) and ``column_balance`` = ``min(left, right) / max(left, right)`` over
    the fraction of boxes each side (1.0 at an even 50/50 split, lower as it lopsides). The best-
    scoring candidate whose midpoint is near page center AND whose split leaves both halves populated
    wins. Considering *all* runs — not only the single longest — is what stops a longer OFF-center run
    (e.g. a centered running head / folio splitting the gutter band) from shadowing a valid centered
    gutter. The four single-column rejections (too few boxes, no >= 3-bin run, no run both centered
    and balanced) all return ``col2_score = 0.0`` and ``split_x = width``.
    """
    if len(boxes) < _COLUMN_MIN_BOXES:
        return ColumnEvidence(col2_score=0.0, split_x=width)
    if not (math.isfinite(width) and width > 0.0):
        raise ValueError(f"detect_columns width must be a positive page dimension, got {width!r}")

    bins = [0] * _PROJECTION_BINS
    for box in boxes:
        idx = int(_box_x_center(box) / width * _PROJECTION_BINS)
        bins[max(0, min(_PROJECTION_BINS - 1, idx))] += 1  # clamp both ends (a box on the far edge)
    peak = max(bins) or 1
    empty_at = _GUTTER_EMPTY_FRACTION * peak

    # Collect every contiguous central empty run of >= _MIN_GUTTER_BINS (G-10's real-gutter floor).
    lo, hi = _CENTRAL_BAND
    runs: list[tuple[int, int]] = []
    run = 0
    run_start = lo
    for b in range(lo, hi):
        if bins[b] <= empty_at:
            if run == 0:
                run_start = b
            run += 1
        else:
            if run >= _MIN_GUTTER_BINS:
                runs.append((run_start, run))
            run = 0
    if run >= _MIN_GUTTER_BINS:  # a run flush against the central-band edge
        runs.append((run_start, run))

    center_lo, center_hi = _GUTTER_CENTER_RANGE
    halves_lo, halves_hi = _POPULATED_HALVES_RANGE
    best = ColumnEvidence(col2_score=0.0, split_x=width)
    for start, length in runs:
        split = (start + length / 2.0) / _PROJECTION_BINS * width
        if not (center_lo * width <= split <= center_hi * width):  # gutter must sit near page center
            continue
        left_fraction = sum(1 for box in boxes if _box_x_center(box) < split) / len(boxes)
        if not (halves_lo <= left_fraction <= halves_hi):  # both columns genuinely populated (G-10)
            continue
        gutter_mean = statistics.mean(bins[start:start + length])
        valley_depth = 1.0 - gutter_mean / peak
        right_fraction = 1.0 - left_fraction
        column_balance = min(left_fraction, right_fraction) / max(left_fraction, right_fraction)
        score = valley_depth * column_balance
        if score > best.col2_score:  # keep the strongest valid two-column interpretation
            best = ColumnEvidence(col2_score=score, split_x=split)
    return best


class ColumnDetector:
    """Applies a book's calibrated column-decision policy to :class:`ColumnEvidence`.

    Two required, defaultless keyword params (the G-1 numberless-core posture): ``decision_threshold``
    — the ``col2_score`` at/above which a page leans two-column — and ``hysteresis_margin`` — the
    distance from that threshold within which the evidence is too weak to stand alone, so the
    cross-page prior decides (DT-7). Both are proposed in-code and ratified against the run-report
    valley/balance distribution (the DT-7 checkpoint); the core carries no default.
    """

    def __init__(self, *, decision_threshold: float, hysteresis_margin: float) -> None:
        if not (math.isfinite(decision_threshold) and 0.0 < decision_threshold < 1.0):
            raise ValueError(f"decision_threshold must be in (0, 1), got {decision_threshold!r}")
        if not (math.isfinite(hysteresis_margin) and 0.0 < hysteresis_margin <= 1.0):
            raise ValueError(f"hysteresis_margin must be in (0, 1], got {hysteresis_margin!r}")
        self._decision_threshold = decision_threshold
        self._hysteresis_margin = hysteresis_margin

    @property
    def version(self) -> str:
        return COLUMN_DETECTOR_VERSION

    @property
    def params(self) -> dict[str, float]:
        """The decision values, for the sidecar fingerprint (DT-9). Ordered for a stable fingerprint."""
        return {"decision_threshold": self._decision_threshold, "hysteresis_margin": self._hysteresis_margin}

    def classify(self, evidence: ColumnEvidence) -> ColumnVerdict:
        """Map column evidence to a leaning count + confidence. Pure, deterministic."""
        score = evidence.col2_score
        n_cols = 2 if score >= self._decision_threshold else 1
        confidence = abs(score - self._decision_threshold)
        confident = confidence >= self._hysteresis_margin
        return ColumnVerdict(
            n_cols=n_cols,
            confidence=confidence,
            confident=confident,
            signal="evidence" if confident else "weak-evidence",
        )


def reading_order(boxes: Sequence, *, split_x: float | None) -> tuple[str, ...]:
    """Recover reading order from box coordinates (DT-7): columns left-to-right, each top-to-bottom,
    line-binned by median box height. Returns the box texts in order.

    ``split_x`` is the gutter x when the page is two-column (boxes left of it read before boxes right
    of it), or ``None`` for a single column (a plain top-to-bottom, left-to-right line sort). The
    caller supplies the column decision (the :class:`ColumnDetector`'s), so this stays a mechanical
    consequence of geometry.
    """
    if not boxes:
        return ()
    heights = [box.bbox[3] - box.bbox[1] for box in boxes]
    median_height = statistics.median(heights)
    line_height = (median_height if median_height > 0 else 10.0) * _LINE_HEIGHT_FRACTION

    def _key(box):
        y_center = (box.bbox[1] + box.bbox[3]) / 2.0
        return (round(y_center / line_height), box.bbox[0])

    if split_x is None:
        ordered = sorted(boxes, key=_key)
    else:
        left = sorted((box for box in boxes if _box_x_center(box) < split_x), key=_key)
        right = sorted((box for box in boxes if _box_x_center(box) >= split_x), key=_key)
        ordered = [*left, *right]
    return tuple(box.text for box in ordered)


def ordered_coverage(expected: Sequence[str], actual: Sequence[str]) -> float:
    """Fraction of ``expected`` tokens recovered IN ORDER by ``actual`` — the order-coverage metric
    the detector's QA cross-check emits (DT-5 ``order_qa``; the G-16 no-witness pin).

    Order-sensitive by construction: the summed size of ``difflib.SequenceMatcher``'s matching blocks
    over ``len(expected)`` (``autojunk`` off so nothing is silently ignored on long inputs). Those are
    Ratcliff/Obershelp longest-*contiguous*-matching blocks, so the total is a CONSERVATIVE lower
    bound on the true longest-common-subsequence length (equal for the cases here; it can under-report
    on adversarially interleaved inputs — a note for #40 if it needs exact LCS for the book-wide
    ``order_qa``). ``1.0`` iff every expected token appears in ``actual`` in order; a column-
    interleaved order scores below ``1.0``. Empty ``expected`` -> ``0.0`` (coverage is undefined
    there; 0.0 refuses a vacuous perfect score, never 1.0/NaN).
    """
    if not expected:
        return 0.0
    matcher = SequenceMatcher(a=list(expected), b=list(actual), autojunk=False)
    matched = sum(block.size for block in matcher.get_matching_blocks())
    return matched / len(expected)


# --- Cross-page prior (DT-7 / R8): layout is locally constant ----------------------------------- #


@dataclass(frozen=True, slots=True)
class PageColumnInput:
    """One page's inputs to the cross-page prior: its density verdict (the trust gate) and its column
    evidence. The density verdict runs first — a routed page routes, a non-content page has untrusted
    boxes — so the prior only ever chains ``content``-band pages (R8 clause 1)."""

    density: DensityVerdict
    evidence: ColumnEvidence


@dataclass(frozen=True, slots=True)
class PageColumnVerdict:
    """The resolved column decision for one page under the prior.

    ``n_cols`` is 1/2 for a decided content page, ``None`` for a routed or boxes-untrusted page.
    ``n_cols_source`` is ``"evidence"`` (the page's own confident detector verdict) or ``"prior"``
    (inherited from an agreeing content neighbor), and ``None`` when there is no column decision —
    the S2.2 re-gate reads this to measure how often the prior decided (R8 clause 4). ``routed`` sends
    the page to the human worklist; ``signal`` names the basis.
    """

    n_cols: int | None
    n_cols_source: str | None
    routed: bool
    signal: str

    def __post_init__(self) -> None:
        if self.n_cols is not None and self.n_cols not in (1, 2):
            raise ValueError(f"PageColumnVerdict.n_cols must be 1, 2, or None, got {self.n_cols!r}")
        if self.n_cols_source not in (None, "evidence", "prior"):
            raise ValueError(f"PageColumnVerdict.n_cols_source must be evidence/prior/None, got {self.n_cols_source!r}")
        if not self.signal:
            raise ValueError("PageColumnVerdict.signal must name the deciding basis")


# A page's own-evidence classification for the prior pass — the three kinds the density gate + the
# detector produce, tagged so pass 2 can chain them without re-deriving. (kind, own n_cols, confident).
_ROUTED, _UNTRUSTED, _CONTENT = "routed", "untrusted", "content"


def _next_confident_neighbor(own: list[tuple], i: int) -> int | None:
    """The immediately-next page's own confident column count, iff that next page is a confident
    content page — the forward neighbor for the prior. One step only: a non-content/routed page or an
    in-margin page is not a class to inherit, so the neighbor is ``None`` there (no tunneling across a
    reset or a second undecided page — R8 clause 1)."""
    if i + 1 >= len(own):
        return None
    kind, lean, confident = own[i + 1]
    return lean if (kind == _CONTENT and confident) else None


def resolve_reading_columns(
    page_inputs: Sequence[PageColumnInput], detector: ColumnDetector
) -> list[PageColumnVerdict]:
    """Resolve each page's column count with the cross-page prior (DT-7 / R8).

    Two passes. Pass 1 classifies every page by the density gate: a density-routed page routes, a
    non-content page is boxes-untrusted, and a content page gets its own detector verdict (confident
    or in-margin). Pass 2 walks the book carrying ``prior`` — the last *confident* content column
    count within the unbroken content chain — and:

    - a routed or non-content page routes/records untrusted and **resets** ``prior`` (clause 1: the
      prior never tunnels an endpaper or a routed page);
    - a confident content page keeps its own evidence and becomes the new ``prior`` (clause 2: own
      evidence outside the margin always wins);
    - an in-margin content page inherits the class shared by its available confident content
      neighbors (the previous ``prior`` and the immediate next confident page); if those neighbors
      **disagree**, or none exists, it abstains to the worklist (clause 3). An inherited page does
      not overwrite ``prior`` — a weak inheritance never becomes new confident evidence.

    Every decided page records ``n_cols_source`` (clause 4).
    """
    own: list[tuple] = []
    for page in page_inputs:
        if page.density.routed:
            own.append((_ROUTED, None, None))
        elif not page.density.boxes_trusted:
            own.append((_UNTRUSTED, None, None))
        else:
            verdict = detector.classify(page.evidence)
            own.append((_CONTENT, verdict.n_cols, verdict.confident))

    verdicts: list[PageColumnVerdict] = []
    prior: int | None = None
    for i, (kind, lean, confident) in enumerate(own):
        if kind == _ROUTED:
            verdicts.append(PageColumnVerdict(None, None, routed=True, signal="density-routed"))
            prior = None
        elif kind == _UNTRUSTED:
            verdicts.append(PageColumnVerdict(None, None, routed=False, signal="boxes-untrusted"))
            prior = None
        elif confident:
            verdicts.append(PageColumnVerdict(lean, "evidence", routed=False, signal="evidence"))
            prior = lean
        else:
            neighbors = [c for c in (prior, _next_confident_neighbor(own, i)) if c is not None]
            if neighbors and all(c == neighbors[0] for c in neighbors):
                verdicts.append(PageColumnVerdict(neighbors[0], "prior", routed=False, signal="prior-inherit"))
                # prior UNCHANGED: an inherited page is not confident own-evidence (do not propagate).
            else:
                verdicts.append(PageColumnVerdict(None, None, routed=True, signal="prior-ambiguous"))
                prior = None  # an abstaining content page is worklist-routed -> resets the chain.
    return verdicts
