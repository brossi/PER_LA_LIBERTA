"""Config dataclasses — the typed surface the orchestrator threads into steps.

These are *dumb data holders*: a faithful 1:1 transcription of the book/scan/language
constants the live pipeline hardcodes, reorganised per ``engine/docs/constant_inventory.md``
(the M1 acceptance checklist). They carry no behaviour and no field without an inventory
destination. ``loader.py`` builds them; steps read them.

``ResolvedConfig`` = ``BookManifest`` ⊕ ``LanguageProfile`` ⊕ ``SourceNoiseProfile`` ⊕
``TypefaceProfile`` (plan §"Config model"). Fields with an imminent consumer (``Structure``
and the validate-relevant ``LanguageProfile``/``SourceNoiseProfile`` fields feed M2's ``validate``)
are typed precisely; ``prompt_context`` stays a free dict because its keys are defined by the
prompt templates ported in M4, not knowable now.
"""

from __future__ import annotations

from dataclasses import dataclass


# --- manifest sub-objects -------------------------------------------------- #

@dataclass(frozen=True, slots=True)
class Source:
    """One OCR/scan witness (``manifest.sources[]``; consumed by download in M4a)."""

    role: str
    label: str
    ia_item_id: str
    url: str | None = None


@dataclass(frozen=True, slots=True)
class ScanFacts:
    """Book-specific scan facts (``manifest.scan``; consumed by ocr/typeset in M3–M4a)."""

    pdf: str
    page_image_template: str
    leaf_offset: int
    last_scan_page_default: int


@dataclass(frozen=True, slots=True)
class OcrConfig:
    """Per-book OCR provenance (``manifest.ocr``; consumed by ocr in M4a, BR-010).

    ``models`` maps the model *role* (``"flash"``/``"pro"``) to the concrete backend model
    id. Model ids live in per-book config — not a baked engine default — because frontier ids
    change on a reasonable cadence and a declared id is provenance for which model produced
    ``copy3`` (D3/BR-010). ``dpi``/render tuning stay code defaults until a book needs them.
    """

    models: dict  # {"flash": <id>, "pro": <id>}


@dataclass(frozen=True, slots=True)
class PartStructure:
    name: str
    chapters: int


@dataclass(frozen=True, slots=True)
class RawSection:
    """One manifest-declared flat content boundary in raw OCR.

    ``heading_pattern`` is a full-line regular expression. It carries book/edition typography and
    OCR variation; the generic reconciler owns only ordered boundary mechanics.
    """

    id: str
    title: str
    heading_pattern: str
    boundary_line_role: str = "heading"


@dataclass(frozen=True, slots=True)
class RawSegmentation:
    """Manifest-selected raw-OCR segmentation for ordered edition sections.

    Each section supplies its own full-line heading shape.  This is the book/edition seam for
    typography such as named essays, bare numerals plus synopses, or other forms that do not use
    a language plugin's conventional heading grammar.
    """

    kind: str
    body_start_after_pattern: str
    body_end_patterns: tuple[str, ...]
    sections: tuple[RawSection, ...]
    heading_span: str = "line"
    section_marker_patterns: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Structure:
    """Header-count contract + validation thresholds (``manifest.structure``; M2 ``validate``),
    plus the book's raw-OCR ``running_heads`` (M3 ``reconcile``).

    ``running_heads`` are regex bodies for page-furniture lines (e.g. the repeated book title)
    that segmentation must drop — **book-level** data, deliberately *not* in the cross-title
    language plugin (BR-004). Each body is anchored by the plugin as ``\\s*(?:<body>)\\s*$``.

    It is a **required** manifest field with no default (an empty ``[]`` means "this book has no
    running heads", explicitly — distinct from a forgotten field). The rationale: segmentation
    behavior stays visible in the manifest and is never implicit, matching the other ``structure``
    fields, which are all required. Full decision record in BR-004.
    """

    h2_min: int
    h3_count: int
    parts: tuple[PartStructure, ...]
    content_units: int
    retention_min: float
    foreign_char_max: float
    word_quality_high_severity_max: int
    running_heads: tuple[str, ...]
    raw_segmentation: RawSegmentation | None = None


@dataclass(frozen=True, slots=True)
class Edition:
    """Bibliographic metadata + deploy base (``manifest.edition``; consumed by typeset in M3).

    ``author`` and ``year`` are distinct fields: the publication year is a first-class fact (it
    also feeds the prompts as ``prompt_context.year``), so it is *not* fused into the ``author``
    display string. ``render_markdown`` composes the title-block byline as ``**{author}** ({year})``.
    The loader cross-checks ``title_it``/``author``/``year`` against ``prompt_context`` so the two
    views of these shared facts cannot silently drift apart.
    """

    title_it: str
    title_en: str
    subtitle_it: str
    subtitle_en: str
    author: str
    year: int
    colophon: str
    ia_item_id: str
    site_base: str


@dataclass(frozen=True, slots=True)
class DensityBands:
    """The DT-6 density-band thresholds (``manifest.segmentation.density_bands``; S2.1.4 #38).

    A faithful 1:1 transcription of the seven calibrated band values (ratified by Ben 2026-07-06);
    :meth:`DensityClassifier.from_config` reads them to build the classifier. They live in book
    config — not a core default — because a band is a scan-profile opinion (the G-1 numberless-core
    posture); the classifier's constructor is where the value *ranges* are enforced, this is just
    the typed carrier.
    """

    yield_content_min: float
    box_content_min: int
    ink_blank_max: float
    ink_dark_min: float
    confidence_margin: float
    cover_edge_leaves: int
    ink_saturation_min: float


@dataclass(frozen=True, slots=True)
class ColumnDetectorPolicy:
    """The DT-7 column-decision policy (``manifest.segmentation.column_detector``; S2.1.5 #39).

    ``decision_threshold`` — the ``col2_score`` at/above which a page leans two-column;
    ``hysteresis_margin`` — the distance from it within which the cross-page prior decides. Ruled by
    Ben 2026-07-06 at the #39 run-report checkpoint. Per-book config, not a core default (the G-1
    numberless-core posture); ``ColumnDetector.from_config`` reads it, the constructor enforces the
    ``(0, 1)`` ranges. This is just the typed carrier.
    """

    decision_threshold: float
    hysteresis_margin: float


@dataclass(frozen=True, slots=True)
class Segmentation:
    """The geometry/segmentation front-end config (``manifest.segmentation``; S2.1, DT-5/DT-6/DT-7).

    ``order_source`` selects the two-branch reading-order policy (DT-5): ``"witness"`` — a
    column-ordered text witness supplies reading order and the detector is only a QA cross-check
    (PLL, copy1); ``"geometry"`` — the geometric detector is the authoritative order source
    (image-only sources). ``density_bands`` is the DT-6 pre-check calibration; ``column_detector`` is
    the DT-7 column-decision policy. Optional book-wide: only a book routed through the geometry
    front-end carries a ``segmentation`` block, and the block runs the whole front-end (density +
    column), so both sub-configs are present.
    """

    order_source: str
    density_bands: DensityBands
    column_detector: ColumnDetectorPolicy
    #: The per-stage human-review volume bound (DT-10 / P-6; S2.1.6 #40). Optional — ``None`` lets
    #: the run reach for the ruled default (``geom_review.REVIEW_FRACTION_MAX_DEFAULT`` = 0.15); a
    #: book carries it only to tune its own budget.
    review_fraction_max: float | None = None
    #: The S5 geometry operating mode ruled by the S2.2 re-gate (#30; ``geom_regate.MODE_*``).
    #: Optional — ``None`` until the re-gate has run (S5 falls back to conditional-primary); PLL
    #: carries ``"geometry-tie-break"`` (``docs/probes/s2_2_regate.md``). Consumed by S5.1's rebind.
    geometry_mode: str | None = None


@dataclass(frozen=True, slots=True)
class BookManifest:
    schema_version: int
    id: str
    title: str
    language_id: str
    profile_refs: dict  # {"language": <id>, "source_noise": <id>, "typeface": <id>}
    sources: tuple[Source, ...]
    scan: ScanFacts
    ocr: OcrConfig
    structure: Structure
    edition: Edition
    prompt_context: dict  # free-form; keys defined by the M4 prompt templates
    segmentation: Segmentation | None = None  # geometry front-end config (S2.1); absent for most books


# --- shared profiles ------------------------------------------------------- #

@dataclass(frozen=True, slots=True)
class PeriodDictionary:
    """One period dictionary for the ≥N-of-M membership oracle (M6 consumer)."""

    name: str
    kind: str  # "monolingual" | "bilingual"
    dir: str   # assets-relative chunk dir


@dataclass(frozen=True, slots=True)
class CoverageSpec:
    """What counts as *in-script* for validate's char-coverage check — a literal-character
    allowlist, deliberately **not** a regex. ``ascii_letters``/``digits`` toggle the a–zA–Z /
    0–9 ranges (a non-Latin script turns ASCII off); ``letters`` and ``punctuation`` are
    verbatim character lists (the script's letters beyond ASCII, and the tolerated typographic
    punctuation). The check turns this into a ``frozenset`` and tests membership, so there is no
    regex syntax, escaping, or accidental-range surface for a book author to get wrong.
    Whitespace is always in-script (the check filters it before testing)."""

    ascii_letters: bool
    digits: bool
    letters: str
    punctuation: str


@dataclass(frozen=True, slots=True)
class LanguageProfile:
    """Language knowledge shared across books in the same language/era.

    The word-quality fields (``english_markers``, ``skip_words``, ``consonant_alphabet``),
    ``coverage`` (char-coverage), and ``spacy_model``/``frequency_dictionary`` are read by M2
    ``validate``; ``word_score_accents`` feeds M3 reconcile's OCR word scorer; the period
    dictionaries + ``oracle_min`` feed the M6 membership oracle.

    ``display_name`` (the human-readable language name, e.g. ``"Italian"``) and
    ``accent_inventory`` (the accented characters a prompt asks the model to preserve) are the
    cross-title language facts the M4 prompt templates render as ``{{ language.* }}`` — distinct
    from book identity (``{{ book.* }}`` from ``manifest.prompt_context``). ``display_name``
    replaces the per-book ``prompt_context.language_name`` the live OCR prompt baked in, so a
    language fact can no longer vary book-to-book (BR-008). ``accent_inventory`` is a
    prompt-display set, deliberately separate from ``word_score_accents`` (the scorer's set,
    which mixes case) and ``coverage.letters`` (char-coverage's set).

    The three M4b-D1 fields keep cleanup's *step code* free of any Italian character literal —
    every accent/letter set it parameterises on is sourced here, not baked (the BR-002 code-
    neutrality half; proven by ``test_cleanup_neutrality``):
      - ``accent_fold`` — the fixed accent→base translation cleanup folds with (``{"from","to"}``
        parallel strings → ``str.maketrans``). Deliberately the verbatim live ``_ACCENT_MAP``, NOT
        ``util.text.strip_accents`` (NFKD): the two diverge on non-Italian glyphs (``ç``/``ñ``) a
        foreign name could surface, which would move the detcore golden.
      - ``accented_letters`` — the presumed-canonical superset of the language's accented letters,
        used wherever cleanup's regexes enumerate "a real accented letter" (the live code spelled a
        slightly different restrictive subset at each site; the superset is golden-validated, so any
        site where it changes output turns the golden red rather than passing silently).
      - ``word_letter_class`` — the permissive "any word letter" regex char-class fragment
        (``a-zA-ZÀ-ÿ``) cleanup's tokenisation regexes use. A *script* fact (a non-Latin book needs
        a different class), so config not code — the one documented exception to ``CoverageSpec``'s
        no-regex rule, because its consumer is a compiled regex, not a membership set.

    ``case_fold`` (S3.0) is the case axis of the pre-lookup fold — ``"lower"`` | ``"casefold"`` |
    ``"none"`` — the literal previously baked as ``.lower()`` in the dictionary-oracle path. A
    non-Latin or case-sensitive book needs ``"none"``/``"casefold"``, so it is a profile fact, not
    code (the case sibling to ``accent_fold``; the S3.0 normalization policy reads exactly these two).
    """

    language_id: str
    display_name: str
    spacy_model: str
    frequency_dictionary: str
    english_markers: tuple[str, ...]
    skip_words: tuple[str, ...]
    consonant_alphabet: str
    word_score_accents: str
    accent_inventory: tuple[str, ...]
    coverage: CoverageSpec
    accent_optional: bool
    case_fold: str              # case axis of the pre-lookup fold: "lower"|"casefold"|"none" (S3.0)
    accent_fold: dict           # {"from": "àá…", "to": "aa…"} — fixed fold table (M4b-D1)
    accented_letters: str       # canonical superset of accented letters (M4b-D1)
    word_letter_class: str      # "any word letter" regex class fragment (M4b-D1)
    period_dictionaries: tuple[PeriodDictionary, ...]
    oracle_min: int


@dataclass(frozen=True, slots=True)
class SourceNoiseProfile:
    """How the *source scan* degrades — the OCR-noise fingerprint of the typeface the
    original book was printed in (e.g. a face that blurs ``c`` and ``e``).

    This is an **input** concern: it drives cleanup's correction of OCR errors, and has
    nothing to do with how the *edition* is rendered (that is ``TypefaceProfile``). The
    engine ships no opinion here — a book supplies the noise profile matching its own scan.

    ``page_marker_artifact_pattern`` is read by M2 ``validate``; the substitution tables,
    ``noise_line_patterns``, ``ligature_substitutions`` and ``page_marker_format`` are consumed
    by reconcile/cleanup in M3–M4b.

    The five fields cleanup reads keep its *step code* free of any source-noise literal — every
    OCR-noise pattern it parameterises on is sourced here, not baked (the BR-002/refinement-#4
    relocation; proven by ``test_cleanup_neutrality``):
      - ``noise_line_patterns`` — full-line OCR-decoration regexes; a line matching ANY is dropped
        (``is_noise_line`` :234/:248/:251). The M4b singular ``noise_line_pattern`` folded into this
        list, joined by the separator + ``Disp.``-furniture patterns; per-pattern flags ride inline
        (e.g. ``(?i)``).
      - ``page_marker_line_pattern`` — the compound page-marker noise class (``is_noise_line`` :241);
        the surrounding len/real-word/has-digit guard stays in code.
      - ``char_substitutions`` — ``[regex, replacement]`` confusions whose *replacement* is
        typeface/language opinion (``£→E``, a source-scan misread of a capital E). Distinct from
        the next field, which deletes noise (a neutral space, decided in code).
      - ``inline_page_marker_patterns`` — mid-text page-marker artifact regexes cleanup removes
        (cleanup.py :601-603).

    Note (BR-007): the substitution fields are three different *kinds*. ``boundary_substitutions``
    is a language-neutral *character-confusion* model (``i→r/e``), applied generatively and
    dictionary-validated. ``ligature_substitutions`` is likewise a generative, dictionary-validated
    char-confusion (``fi``→``u``/``n``/``ri`` etc.) but for the typeface's ligatures. ``substitution_rules``
    are *literal* garble→word pairs that bake a character confusion together with a specific Italian
    word (``eolla→colla``) — so they are language-bound, not pure typeface. Factoring the
    char-confusion part into a layered {general + per-typeface} model is deferred (BR-007) until a
    2nd typeface/language exists.
    """

    name: str
    substitution_rules: tuple[tuple[str, str], ...]
    boundary_substitutions: dict  # {"i": ["r", "e"]}
    ligature_substitutions: tuple[tuple[str, str], ...]  # [("u", "fi"), ...] (D3)
    noise_line_patterns: tuple[str, ...]                 # full-line OCR-decoration regexes (M4b)
    page_marker_line_pattern: str                        # compound page-marker noise class (M4b)
    char_substitutions: tuple[tuple[str, str], ...]      # [("£(?!\\d)", "E"), ...] (M4b)
    inline_page_marker_patterns: tuple[str, ...]         # mid-text page-marker artifacts (M4b)
    page_marker_artifact_pattern: str
    page_marker_format: str


@dataclass(frozen=True, slots=True)
class TypefaceProfile:
    """Output-edition typeface facts (consumed by typeset in M3).

    Deliberately thin: asset resolution / CSS version-hashing semantics are M3's to
    define, so M1 carries only the irreducible facts (the two families + the stylesheet
    filename). M3 extends this rather than reshaping a speculative model.
    """

    name: str
    display_family: str
    body_family: str
    css_filename: str


# --- the threaded object --------------------------------------------------- #

@dataclass(frozen=True, slots=True)
class ResolvedConfig:
    book_id: str
    manifest: BookManifest
    language: LanguageProfile
    source_noise: SourceNoiseProfile
    typeface: TypefaceProfile

    @property
    def language_id(self) -> str:
        return self.manifest.language_id

    @property
    def structure(self) -> Structure:
        return self.manifest.structure
