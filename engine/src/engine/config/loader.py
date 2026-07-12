"""Config loading: manifest + referenced profiles → validated ``ResolvedConfig``.

Flow: read ``books/<id>/manifest.json``, resolve its ``profiles`` refs against the shared
``profiles/`` tree, apply any manifest ``overrides``, JSON-schema-validate each document,
then build the typed dataclasses in ``models.py``.

**Override semantics (deliberately minimal).** A manifest may carry an ``overrides`` block
that *replaces* named top-level fields of a referenced profile (shallow per-field replace).
The plan sketches a richer per-field deep-merge with declared append/replace strategies; that
is intentionally **not** built here. With one book and no override case in real use, designing
merge strategies would be modelling without a consumer — added when a real second book gives a
concrete merge to design against. Shallow replace covers the one realistic case (a sibling book
swapping a profile field, e.g. the dictionary set) and is exercised by ``test_config_loader``.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from .models import (
    BookManifest,
    ColumnDetectorPolicy,
    CoverageSpec,
    DensityBands,
    Edition,
    LanguageProfile,
    OcrConfig,
    PartStructure,
    RawSection,
    RawSegmentation,
    PeriodDictionary,
    ResolvedConfig,
    ScanFacts,
    Segmentation,
    SourceNoiseProfile,
    Source,
    Structure,
    TypefaceProfile,
)

# loader.py -> config -> engine(pkg) -> src -> engine/ (project root)
ENGINE_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_DIR = Path(__file__).resolve().parent / "schema"
DEFAULT_BOOKS_DIR = ENGINE_ROOT / "books"
DEFAULT_PROFILES_DIR = ENGINE_ROOT / "profiles"


class ConfigError(Exception):
    """A manifest/profile is missing, malformed, or fails schema validation."""


def _read_json(path: Path) -> dict:
    if not path.is_file():
        raise ConfigError(f"config file not found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"invalid JSON in {path}: {exc}") from exc


def _validate(data: dict, schema_name: str, *, what: str) -> None:
    schema = _read_json(SCHEMA_DIR / schema_name)
    try:
        jsonschema.validate(data, schema)
    except jsonschema.ValidationError as exc:
        loc = "/".join(str(p) for p in exc.absolute_path) or "<root>"
        raise ConfigError(f"{what} failed schema validation at {loc}: {exc.message}") from exc


# --- dataclass builders (dict → typed) ------------------------------------- #

def _build_segmentation(data: dict) -> Segmentation | None:
    """Build the optional geometry front-end config (``manifest.segmentation``; S2.1, DT-5/DT-6).
    Absent for most books -> ``None``. When present the schema has already guaranteed all seven bands
    + a valid ``order_source``, so this is a straight transcription."""
    seg = data.get("segmentation")
    if seg is None:
        return None
    bands = seg["density_bands"]
    cols = seg["column_detector"]
    return Segmentation(
        order_source=seg["order_source"],
        density_bands=DensityBands(
            yield_content_min=bands["yield_content_min"],
            box_content_min=bands["box_content_min"],
            ink_blank_max=bands["ink_blank_max"],
            ink_dark_min=bands["ink_dark_min"],
            confidence_margin=bands["confidence_margin"],
            cover_edge_leaves=bands["cover_edge_leaves"],
            ink_saturation_min=bands["ink_saturation_min"],
        ),
        column_detector=ColumnDetectorPolicy(
            decision_threshold=cols["decision_threshold"],
            hysteresis_margin=cols["hysteresis_margin"],
        ),
        review_fraction_max=seg.get("review_fraction_max"),  # optional (DT-10/P-6, #40)
        geometry_mode=seg.get("geometry_mode"),  # optional (S2.2 re-gate output, #30)
    )


def _build_manifest(data: dict) -> BookManifest:
    structure = data["structure"]
    edition = data["edition"]
    return BookManifest(
        schema_version=data["schema_version"],
        id=data["id"],
        title=data["title"],
        language_id=data["language"],
        profile_refs=dict(data["profiles"]),
        sources=tuple(
            Source(
                role=s["role"],
                label=s["label"],
                ia_item_id=s["ia_item_id"],
                url=s.get("url"),
            )
            for s in data["sources"]
        ),
        scan=ScanFacts(
            pdf=data["scan"]["pdf"],
            page_image_template=data["scan"]["page_image_template"],
            leaf_offset=data["scan"]["leaf_offset"],
            last_scan_page_default=data["scan"]["last_scan_page_default"],
        ),
        ocr=OcrConfig(models=dict(data["ocr"]["models"])),
        structure=Structure(
            h2_min=structure["h2_min"],
            h3_count=structure["h3_count"],
            parts=tuple(
                PartStructure(name=p["name"], chapters=p["chapters"])
                for p in structure["parts"]
            ),
            content_units=structure["content_units"],
            retention_min=structure["retention_min"],
            foreign_char_max=structure["foreign_char_max"],
            word_quality_high_severity_max=structure["word_quality_high_severity_max"],
            running_heads=tuple(structure["running_heads"]),
            raw_segmentation=(
                RawSegmentation(
                    kind=structure["raw_segmentation"]["kind"],
                    body_start_after_pattern=structure["raw_segmentation"][
                        "body_start_after_pattern"
                    ],
                    body_end_patterns=tuple(
                        structure["raw_segmentation"].get("body_end_patterns", [])
                    ),
                    sections=tuple(
                        RawSection(
                            id=section["id"],
                            title=section["title"],
                            heading_pattern=section["heading_pattern"],
                        )
                        for section in structure["raw_segmentation"]["sections"]
                    ),
                )
                if "raw_segmentation" in structure
                else None
            ),
        ),
        edition=Edition(
            title_it=edition["title_it"],
            title_en=edition["title_en"],
            subtitle_it=edition["subtitle_it"],
            subtitle_en=edition["subtitle_en"],
            author=edition["author"],
            year=edition["year"],
            colophon=edition["colophon"],
            ia_item_id=edition["ia_item_id"],
            site_base=edition["site_base"],
        ),
        prompt_context=dict(data["prompt_context"]),
        segmentation=_build_segmentation(data),
    )


def _build_language(data: dict) -> LanguageProfile:
    return LanguageProfile(
        language_id=data["language_id"],
        display_name=data["display_name"],
        spacy_model=data["spacy_model"],
        frequency_dictionary=data["frequency_dictionary"],
        english_markers=tuple(data["english_markers"]),
        skip_words=tuple(data["skip_words"]),
        consonant_alphabet=data["consonant_alphabet"],
        word_score_accents=data["word_score_accents"],
        accent_inventory=tuple(data["accent_inventory"]),
        coverage=CoverageSpec(
            ascii_letters=data["coverage"]["ascii_letters"],
            digits=data["coverage"]["digits"],
            letters=data["coverage"]["letters"],
            punctuation=data["coverage"]["punctuation"],
        ),
        accent_optional=data["accent_optional"],
        case_fold=data["case_fold"],
        accent_fold={"from": data["accent_fold"]["from"], "to": data["accent_fold"]["to"]},
        accented_letters=data["accented_letters"],
        word_letter_class=data["word_letter_class"],
        period_dictionaries=tuple(
            PeriodDictionary(name=d["name"], kind=d["kind"], dir=d["dir"])
            for d in data["period_dictionaries"]
        ),
        oracle_min=data["oracle_min"],
    )


def _build_source_noise(data: dict) -> SourceNoiseProfile:
    return SourceNoiseProfile(
        name=data["name"],
        substitution_rules=tuple((r[0], r[1]) for r in data["substitution_rules"]),
        boundary_substitutions={k: list(v) for k, v in data["boundary_substitutions"].items()},
        ligature_substitutions=tuple((r[0], r[1]) for r in data["ligature_substitutions"]),
        noise_line_patterns=tuple(data["noise_line_patterns"]),
        page_marker_line_pattern=data["page_marker_line_pattern"],
        char_substitutions=tuple((r[0], r[1]) for r in data["char_substitutions"]),
        inline_page_marker_patterns=tuple(data["inline_page_marker_patterns"]),
        page_marker_artifact_pattern=data["page_marker_artifact_pattern"],
        page_marker_format=data["page_marker_format"],
    )


def _build_typeface(data: dict) -> TypefaceProfile:
    return TypefaceProfile(
        name=data["name"],
        display_family=data["display_family"],
        body_family=data["body_family"],
        css_filename=data["css_filename"],
    )


def _load_profile(
    profiles_dir: Path, kind: str, ref: str, overrides: dict
) -> dict:
    """Read ``profiles/<subdir>/<ref>.json`` and apply the manifest override (if any)."""
    subdir = {"language": "languages", "source_noise": "source_noise", "typeface": "typefaces"}[kind]
    data = _read_json(profiles_dir / subdir / f"{ref}.json")
    override = overrides.get(kind)
    if override:
        data = {**data, **override}  # shallow per-field replace
    return data


#: Bibliographic facts that legitimately appear in BOTH ``edition`` (typeset metadata) and
#: ``prompt_context`` (LLM-prompt identity). The two namespaces are kept separate by design
#: (BR-008: book identity for prompts vs typed display metadata), so the same fact is declared
#: in each — and must agree. Pairs are ``(edition_key, prompt_context_key)``.
#:
#: ``author``/``year`` are hard invariants (one fact, no reason to differ). ``title_it``/
#: ``book_title`` is the softest pair: a future book could legitimately want a different
#: prompt-facing title than its typeset title (e.g. a simplified or transliterated form for the
#: model). If that need ever arises, drop the title pair here — consciously, not by silent drift.
_BIBLIOGRAPHIC_PAIRS = (("title_it", "book_title"), ("author", "author"), ("year", "year"))


def _check_bibliographic_consistency(book_id: str, manifest_data: dict) -> None:
    """Guard against drift between the two views of the shared bibliographic facts.

    ``edition`` and ``prompt_context`` each carry the title/author/year (one for typeset, one for
    the prompts). They are duplicated on purpose but must stay identical — a hand-edit to one and
    not the other would otherwise ship silently (e.g. an ``author`` with a fused year, or a title
    that disagrees case-for-case). This turns that drift into a load-time ``ConfigError``.
    """
    edition = manifest_data["edition"]
    prompt_context = manifest_data["prompt_context"]
    mismatches = [
        f"edition.{ek}={edition[ek]!r} != prompt_context.{pk}={prompt_context[pk]!r}"
        for ek, pk in _BIBLIOGRAPHIC_PAIRS
        if edition[ek] != prompt_context[pk]
    ]
    if mismatches:
        raise ConfigError(
            f"bibliographic facts disagree across edition and prompt_context in {book_id!r} "
            f"(they must be identical): " + "; ".join(mismatches)
        )


# --- public API ------------------------------------------------------------ #

def load_book(
    book_id: str,
    *,
    books_dir: Path | None = None,
    profiles_dir: Path | None = None,
) -> ResolvedConfig:
    """Resolve ``book_id`` to a validated ``ResolvedConfig``."""
    books_dir = books_dir or DEFAULT_BOOKS_DIR
    profiles_dir = profiles_dir or DEFAULT_PROFILES_DIR

    manifest_data = _read_json(books_dir / book_id / "manifest.json")
    _validate(manifest_data, "manifest.schema.json", what=f"manifest for {book_id!r}")

    refs = manifest_data["profiles"]
    overrides = manifest_data.get("overrides", {})

    lang_data = _load_profile(profiles_dir, "language", refs["language"], overrides)
    _validate(lang_data, "language_profile.schema.json", what=f"language profile {refs['language']!r}")

    noise_data = _load_profile(profiles_dir, "source_noise", refs["source_noise"], overrides)
    _validate(noise_data, "source_noise.schema.json", what=f"source-noise profile {refs['source_noise']!r}")

    type_data = _load_profile(profiles_dir, "typeface", refs["typeface"], overrides)
    _validate(type_data, "typeface_profile.schema.json", what=f"typeface profile {refs['typeface']!r}")

    # A profile declares its own language_id; it must match the manifest's.
    if lang_data["language_id"] != manifest_data["language"]:
        raise ConfigError(
            f"language mismatch: manifest {book_id!r} declares language "
            f"{manifest_data['language']!r} but profile {refs['language']!r} is "
            f"{lang_data['language_id']!r}"
        )

    _check_bibliographic_consistency(book_id, manifest_data)

    return ResolvedConfig(
        book_id=book_id,
        manifest=_build_manifest(manifest_data),
        language=_build_language(lang_data),
        source_noise=_build_source_noise(noise_data),
        typeface=_build_typeface(type_data),
    )
