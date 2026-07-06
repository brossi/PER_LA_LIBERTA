"""Config loader: resolution of the real PLL manifest, schema enforcement, override.

These prove the three things the loader exists to do — (1) wire manifest + profiles into a
typed ``ResolvedConfig`` carrying the real constants M2 ``validate`` will read, (2) reject
malformed hand-edited config with a clear error, (3) apply the one supported override mode.
No live PLL artifacts are touched; the inputs are the committed engine config files.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from engine.config import loader
from engine.config.loader import ConfigError, load_book
from engine.lang.registry import UnknownLanguageError, get_language_plugin

REAL_BOOKS = loader.DEFAULT_BOOKS_DIR
REAL_PROFILES = loader.DEFAULT_PROFILES_DIR


def test_resolves_real_pll_constants():
    cfg = load_book("per_la_liberta")

    # structure (the M2 validate contract)
    s = cfg.structure
    assert (s.h2_min, s.h3_count, s.content_units) == (3, 57, 58)
    assert s.retention_min == 0.60
    assert s.foreign_char_max == 0.005
    assert s.word_quality_high_severity_max == 0
    assert tuple((p.name, p.chapters) for p in s.parts) == (
        ("Parte Prima", 24),
        ("Parte Seconda", 33),
    )

    # language profile (validate + later oracle)
    lp = cfg.language
    assert cfg.language_id == "it" == lp.language_id
    assert lp.spacy_model == "it_core_news_lg"
    assert "the" in lp.english_markers and "correct" in lp.english_markers
    assert "il" in lp.skip_words
    assert lp.consonant_alphabet == "bcdfghjklmnpqrstvwxyz"
    # coverage is a structured literal-character allowlist (no regex).
    assert lp.coverage.ascii_letters is True and lp.coverage.digits is True
    assert "à" in lp.coverage.letters and "É" in lp.coverage.letters
    assert "«" in lp.coverage.punctuation and "…" in lp.coverage.punctuation
    assert lp.accent_optional is True
    # S3.0: the pre-lookup fold's case axis, sourced from the profile (was a baked `.lower()`).
    assert lp.case_fold == "lower"
    assert lp.oracle_min == 2
    assert {d.name for d in lp.period_dictionaries} == {
        "Zingarelli 1922", "Edgren 1901", "Hoare 1915"
    }

    # scan profile (page-marker pattern read by M2; subs by M3/M4)
    assert cfg.source_noise.page_marker_artifact_pattern == r"\d+\s+[35][EI]:?"
    assert ("cbe", "che") in cfg.source_noise.substitution_rules
    assert cfg.source_noise.boundary_substitutions == {"i": ["r", "e"]}

    # edition + typeface (M3). author + year are separate fields (year not fused into author).
    assert cfg.manifest.edition.author == "Cesare Crespi"
    assert cfg.manifest.edition.year == 1913
    assert cfg.manifest.edition.site_base.endswith("/PER_LA_LIBERTA")
    assert cfg.typeface.display_family == "Spectral"
    assert cfg.typeface.body_family == "Fraunces"


def test_cleanup_accented_letters_is_the_full_canonical_set():
    """Config-contract guard complementing the cleanup equivalence golden (Audit 1).

    ``cfg.language.accented_letters`` is the enumerated set cleanup interpolates into its two
    is_noise "real word" classes (``real_word_short_re`` / ``real_word_3_re``, ``build_rules``). A
    single-letter deletion is a plausible hand-edit of the language profile — and the equivalence
    golden (``test_cleanup_golden``) only *individually* binds 3 of the 12 letters on the frozen
    corpus (``ì``, ``é``, ``Ì`` flip a line's noise classification there; the other nine never land
    in a ≤4-char / page-marker line that changes output, so dropping one slips past the golden,
    confirmed by the Audit-1 per-letter mutation sweep). This asserts the whole canonical set
    directly — corpus-independent — so a dropped letter fails *here* instead of shipping silently.

    The set is the Italian accented-vowel inventory: grave ``à è ì ò ù`` + acute ``é``, each in both
    cases. It is a strict superset of the live restrictive class (``cleanup.py`` :231/:244,
    ``àèìòùéÀÈÌÒÙ``) by exactly ``É`` — the deliberate M4b-D1 superset, proven inert on the corpus.
    """
    lp = load_book("per_la_liberta").language
    canonical = set("àèìòùéÀÈÌÒÙÉ")
    assert set(lp.accented_letters) == canonical, (
        "accented_letters drifted from the canonical Italian set "
        f"(symmetric diff: {set(lp.accented_letters) ^ canonical})"
    )
    assert len(lp.accented_letters) == len(canonical), "duplicate letter in accented_letters"
    # Tie to Audit 1: the live restrictive subset plus exactly the proven-inert +É extension.
    assert set(lp.accented_letters) - set("àèìòùéÀÈÌÒÙ") == {"É"}
    # Deliberately no parallel guard for the sibling word_letter_class (the permissive a-zA-ZÀ-ÿ
    # range): unlike enumerated accented_letters (9/12 letters golden-silent → it needs this guard),
    # the range is strongly golden-bound (narrowing it diverges 10 chapters) and a single-codepoint
    # boundary typo is not a realistic edit — a contract assertion there would be belt-and-suspenders.


def _write_book(tmp_path, name, manifest: dict):
    book_dir = tmp_path / "books" / name
    book_dir.mkdir(parents=True)
    (book_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return tmp_path / "books"


def test_schema_rejects_missing_required_field(tmp_path):
    bad = json.loads((REAL_BOOKS / "per_la_liberta" / "manifest.json").read_text())
    del bad["structure"]
    books = _write_book(tmp_path, "bad", bad)
    with pytest.raises(ConfigError, match="schema validation"):
        load_book("bad", books_dir=books, profiles_dir=REAL_PROFILES)


def test_schema_rejects_wrong_type(tmp_path):
    bad = json.loads((REAL_BOOKS / "per_la_liberta" / "manifest.json").read_text())
    bad["structure"]["h3_count"] = "fifty-seven"
    books = _write_book(tmp_path, "bad", bad)
    with pytest.raises(ConfigError, match="schema validation"):
        load_book("bad", books_dir=books, profiles_dir=REAL_PROFILES)


@pytest.mark.parametrize("missing", ["book_title", "author", "year"])
def test_prompt_context_requires_the_ocr_template_keys(tmp_path, missing):
    # The OCR template (profiles/prompts/ocr.txt.j2) hard-references book.book_title/author/year
    # under StrictUndefined. Pinning them in the manifest schema turns a forgotten key into a
    # clean ConfigError at *load* — not a late jinja2.UndefinedError at render time, which escapes
    # the CLI exception taxonomy as a raw traceback (the gap this closes).
    m = _real_manifest()
    m["id"] = "pc"
    del m["prompt_context"][missing]
    books = _write_book(tmp_path, "pc", m)
    with pytest.raises(ConfigError, match="schema validation"):
        load_book("pc", books_dir=books, profiles_dir=REAL_PROFILES)


def test_prompt_context_stays_extensible_beyond_the_required_three(tmp_path):
    # Only the three keys the OCR template consumes are required; prompt_context stays open for
    # the later prompts (subject/entities feed triage/translate, pinned when they land). Dropping
    # a non-OCR key still loads — proving the requirement is exactly the three, not over-tightened.
    m = _real_manifest()
    m["id"] = "pcx"
    del m["prompt_context"]["subject"]
    books = _write_book(tmp_path, "pcx", m)
    cfg = load_book("pcx", books_dir=books, profiles_dir=REAL_PROFILES)
    assert "subject" not in cfg.manifest.prompt_context
    assert cfg.manifest.prompt_context["book_title"] == "Per la libertà!"


def test_override_replaces_profile_field(tmp_path):
    # A sibling book reusing the Italian profile but swapping the oracle threshold —
    # the one realistic override case the shallow-replace mode is built for.
    m = json.loads((REAL_BOOKS / "per_la_liberta" / "manifest.json").read_text())
    m["id"] = "ovr"
    m["overrides"] = {"language": {"oracle_min": 3}}
    books = _write_book(tmp_path, "ovr", m)

    base = load_book("per_la_liberta")
    overridden = load_book("ovr", books_dir=books, profiles_dir=REAL_PROFILES)
    assert base.language.oracle_min == 2
    assert overridden.language.oracle_min == 3


def test_missing_book_is_a_clean_error(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_book("nonexistent", books_dir=tmp_path, profiles_dir=REAL_PROFILES)


def _real_manifest() -> dict:
    return json.loads((REAL_BOOKS / "per_la_liberta" / "manifest.json").read_text())


def test_language_id_mismatch_is_rejected(tmp_path):
    # Manifest declares 'fr' but the referenced profile is 'it' — the loader guard fires.
    m = _real_manifest()
    m["language"] = "fr"
    books = _write_book(tmp_path, "mm", m)
    with pytest.raises(ConfigError, match="language mismatch"):
        load_book("mm", books_dir=books, profiles_dir=REAL_PROFILES)


@pytest.mark.parametrize(
    "ed_key, drifted",
    [("title_it", "Per la Libertà!"), ("author", "Cesare Crespi (1913)"), ("year", 1914)],
)
def test_bibliographic_drift_across_namespaces_is_rejected(tmp_path, ed_key, drifted):
    # title/author/year live in BOTH edition and prompt_context (two consumers, BR-008). The loader
    # guard requires them identical, so a hand-edit to one view and not the other — e.g. re-fusing
    # the year into author, or a case-only title drift like libertà→Libertà — fails at load instead
    # of shipping silently. Exercises each guarded field's failure branch.
    m = _real_manifest()
    m["id"] = "bibdrift"
    m["edition"][ed_key] = drifted  # diverge edition's view; prompt_context keeps the real value
    books = _write_book(tmp_path, "bibdrift", m)
    with pytest.raises(ConfigError, match="bibliographic facts disagree"):
        load_book("bibdrift", books_dir=books, profiles_dir=REAL_PROFILES)


def test_missing_edition_year_is_a_schema_error_before_the_consistency_check(tmp_path):
    # year is now a required edition field; dropping it is a schema error (a clean ConfigError),
    # raised before the consistency check — proving the schema gates the new field, not a KeyError
    # in _check_bibliographic_consistency.
    m = _real_manifest()
    m["id"] = "noyear"
    del m["edition"]["year"]
    books = _write_book(tmp_path, "noyear", m)
    with pytest.raises(ConfigError, match="schema validation"):
        load_book("noyear", books_dir=books, profiles_dir=REAL_PROFILES)


def test_missing_profile_ref_is_a_clean_error(tmp_path):
    m = _real_manifest()
    m["profiles"]["language"] = "no_such_profile"
    books = _write_book(tmp_path, "mp", m)
    with pytest.raises(ConfigError, match="not found"):
        load_book("mp", books_dir=books, profiles_dir=REAL_PROFILES)


@pytest.mark.parametrize(
    "profile, field_path",
    [
        ("languages/italian_1900_1922.json", ("oracle_min",)),          # profile-level schema path (else KeyError in the builder)
        ("languages/italian_1900_1922.json", ("case_fold",)),           # S3.0 normalization field, schema-first (no baked default)
        ("languages/italian_1900_1922.json", ("coverage", "letters")),  # a nested required sub-field
        ("source_noise/bodoni_didone.json", ("substitution_rules",)),   # the source-noise profile is validated too
        ("typefaces/spectral_fraunces.json", ("display_family",)),      # ...and the typeface profile (the third _validate call)
    ],
)
def test_profile_schema_rejects_a_missing_required_field(tmp_path, profile, field_path):
    # A malformed *profile* (not just the manifest) fails validation cleanly (ConfigError) rather than
    # KeyError-ing later in a builder. Parametrized across every validated profile so each _validate
    # call — language / source-noise / typeface — is exercised, including a nested sub-field. Adding a
    # newly-required profile field is a one-line param here.
    prof = _stage_profiles(tmp_path)
    p = prof.joinpath(*profile.split("/"))
    data = json.loads(p.read_text())
    target = data
    for key in field_path[:-1]:
        target = target[key]
    del target[field_path[-1]]
    p.write_text(json.dumps(data), encoding="utf-8")
    books = _write_book(tmp_path, "bad", _real_manifest())
    with pytest.raises(ConfigError, match="schema validation"):
        load_book("bad", books_dir=books, profiles_dir=prof)


def test_override_is_validated_after_merge(tmp_path):
    # An override that violates the schema is caught — proving override happens before,
    # not after, validation.
    m = _real_manifest()
    m["id"] = "ovrbad"
    m["overrides"] = {"language": {"oracle_min": "two"}}  # wrong type
    books = _write_book(tmp_path, "ovrbad", m)
    with pytest.raises(ConfigError, match="schema validation"):
        load_book("ovrbad", books_dir=books, profiles_dir=REAL_PROFILES)


def test_override_replaces_list_field_wholesale(tmp_path):
    # The documented shallow-replace semantics: overriding a list swaps it whole, it does
    # not append. (This is the tradeoff vs the deferred per-field deep merge.)
    m = _real_manifest()
    m["id"] = "ovrlist"
    m["overrides"] = {
        "language": {
            "period_dictionaries": [
                {"name": "Only One", "kind": "monolingual", "dir": "dictionary/only_one"}
            ]
        }
    }
    books = _write_book(tmp_path, "ovrlist", m)
    cfg = load_book("ovrlist", books_dir=books, profiles_dir=REAL_PROFILES)
    assert [d.name for d in cfg.language.period_dictionaries] == ["Only One"]


def _stage_profiles(tmp_path) -> Path:
    """Copy the real profile tree into tmp so a single profile can be corrupted in place."""
    dst = tmp_path / "profiles"
    for sub in ("languages", "source_noise", "typefaces"):
        (dst / sub).mkdir(parents=True)
        for f in (REAL_PROFILES / sub).glob("*.json"):
            shutil.copy(f, dst / sub / f.name)
    return dst


def test_language_profile_requires_a_monolingual_period_dictionary(tmp_path):
    # adjudicate._build_oracle binds its membership oracle to a *monolingual* period dictionary
    # and raises if none — a bare ValueError that escapes the CLI exception taxonomy as a raw
    # traceback. The schema now enforces ≥1 monolingual member, so a profile declaring only
    # bilingual dicts fails at LOAD (ConfigError) instead. (Same defect class as the prompt_context
    # fix: a consumer requirement the contract didn't guarantee, failing late.) This also empirically
    # confirms the installed jsonschema enforces draft-2020-12 `contains`.
    prof = _stage_profiles(tmp_path)
    lp = prof / "languages" / "italian_1900_1922.json"
    data = json.loads(lp.read_text())
    data["period_dictionaries"] = [
        d for d in data["period_dictionaries"] if d["kind"] != "monolingual"
    ]
    assert data["period_dictionaries"], "fixture must keep bilingual dicts — testing 'no monolingual', not 'empty'"
    lp.write_text(json.dumps(data), encoding="utf-8")
    books = _write_book(tmp_path, "nomono", _real_manifest())
    with pytest.raises(ConfigError, match="schema validation"):
        load_book("nomono", books_dir=books, profiles_dir=prof)


def test_case_fold_enum_rejects_an_unknown_value(tmp_path):
    # case_fold is enum-constrained to the fold modes the normalization policy implements
    # ("lower"|"casefold"|"none"); a typo'd/unsupported mode fails at LOAD, not later as a value the
    # fold path would silently mis-apply or crash on. Exercises the enum failure branch.
    prof = _stage_profiles(tmp_path)
    lp = prof / "languages" / "italian_1900_1922.json"
    data = json.loads(lp.read_text())
    data["case_fold"] = "uppercase"  # not one of the supported modes
    lp.write_text(json.dumps(data), encoding="utf-8")
    books = _write_book(tmp_path, "badcf", _real_manifest())
    with pytest.raises(ConfigError, match="schema validation"):
        load_book("badcf", books_dir=books, profiles_dir=prof)


@pytest.mark.parametrize("mode", ["lower", "casefold", "none"])
def test_case_fold_enum_accepts_every_supported_mode(tmp_path, mode):
    # Positive acceptance for ALL three fold modes — not just the "lower" the real Italian profile
    # ships (single-fixture blind spot: the non-default config value is otherwise born untested). A
    # non-default mode loads and round-trips to the model. This pins the enum at the config tier,
    # independent of #25's behavioural fold test: NARROWING the schema enum (dropping/typo'ing
    # "casefold"/"none") fails HERE, not only when the synthetic-profile battery later runs. Pairs
    # with test_case_fold_enum_rejects_an_unknown_value (which guards WIDENING) to fix the set exactly.
    prof = _stage_profiles(tmp_path)
    lp = prof / "languages" / "italian_1900_1922.json"
    data = json.loads(lp.read_text())
    data["case_fold"] = mode
    lp.write_text(json.dumps(data), encoding="utf-8")
    books = _write_book(tmp_path, f"cf_{mode}", _real_manifest())
    cfg = load_book(f"cf_{mode}", books_dir=books, profiles_dir=prof)
    assert cfg.language.case_fold == mode


def test_unimplemented_but_consistent_language_reaches_unknown_language_error(tmp_path):
    # The real joined path (not the monkeypatched CLI half): the loader is plugin-agnostic,
    # so a manifest+profile both declaring 'xx' load cleanly; the missing plugin only
    # surfaces at get_language_plugin.
    prof = _stage_profiles(tmp_path)
    lp = prof / "languages" / "italian_1900_1922.json"
    data = json.loads(lp.read_text())
    data["language_id"] = "xx"
    lp.write_text(json.dumps(data), encoding="utf-8")
    m = _real_manifest()
    m["language"] = "xx"
    books = _write_book(tmp_path, "xx", m)

    cfg = load_book("xx", books_dir=books, profiles_dir=prof)
    assert cfg.language_id == "xx"
    with pytest.raises(UnknownLanguageError):
        get_language_plugin(cfg.language_id)


# --- S2.1.5 (#39) — segmentation front-end config: DT-5 order_source + DT-6 density bands -------- #


def test_segmentation_config_resolves_for_pll():
    # The manifest->typed-model wiring deferred from #38: manifest.segmentation carries the DT-5
    # order_source (PLL = witness: copy1 is the column-ordered reading-order oracle) and the DT-6
    # density bands ratified by Ben 2026-07-06.
    seg = load_book("per_la_liberta").manifest.segmentation
    assert seg is not None
    assert seg.order_source == "witness"
    b = seg.density_bands
    assert (b.yield_content_min, b.box_content_min, b.ink_blank_max) == (0.70, 40, 0.15)
    assert (b.ink_dark_min, b.confidence_margin) == (0.60, 0.05)
    assert (b.cover_edge_leaves, b.ink_saturation_min) == (7, 0.90)


def test_density_classifier_constructs_from_config():
    # The construction seam #39 owns: the typed band model -> a live DensityClassifier, its params
    # exactly the manifest values, and it classifies (proves the round-trip is a working classifier,
    # not just a data copy).
    from engine.structure import DensityBand, DensityClassifier, PageDensityFeatures

    seg = load_book("per_la_liberta").manifest.segmentation
    clf = DensityClassifier.from_config(seg.density_bands)
    assert clf.params == {
        "yield_content_min": 0.70, "box_content_min": 40, "ink_blank_max": 0.15,
        "ink_dark_min": 0.60, "confidence_margin": 0.05, "cover_edge_leaves": 7,
        "ink_saturation_min": 0.90,
    }
    feats = PageDensityFeatures(ink_fraction=0.10, box_count=400, token_yield=0.95, mean_token_length=5.0)
    assert clf.classify(feats, leaf_index=100, n_leaves=278).band is DensityBand.CONTENT


def test_book_without_segmentation_is_valid_and_has_none():
    # Segmentation is OPTIONAL top-level config — only a book routed through the geometry front-end
    # carries it. The synthetic fixture book has none: it loads, and manifest.segmentation is None.
    assert load_book("synthetic").manifest.segmentation is None


def test_schema_rejects_unknown_order_source(tmp_path):
    m = _real_manifest()
    m["id"] = "os"
    m["segmentation"]["order_source"] = "sideways"   # not witness|geometry
    books = _write_book(tmp_path, "os", m)
    with pytest.raises(ConfigError, match="schema validation"):
        load_book("os", books_dir=books, profiles_dir=REAL_PROFILES)


def test_schema_requires_order_source_when_segmentation_present(tmp_path):
    m = _real_manifest()
    m["id"] = "noos"
    del m["segmentation"]["order_source"]
    books = _write_book(tmp_path, "noos", m)
    with pytest.raises(ConfigError, match="schema validation"):
        load_book("noos", books_dir=books, profiles_dir=REAL_PROFILES)


def test_schema_rejects_incomplete_density_bands(tmp_path):
    # The band block is all-or-nothing: a missing band would leave the defaultless DensityClassifier
    # unconstructible, so the schema rejects it at load rather than deep in from_config.
    m = _real_manifest()
    m["id"] = "nb"
    del m["segmentation"]["density_bands"]["ink_dark_min"]
    books = _write_book(tmp_path, "nb", m)
    with pytest.raises(ConfigError, match="schema validation"):
        load_book("nb", books_dir=books, profiles_dir=REAL_PROFILES)
