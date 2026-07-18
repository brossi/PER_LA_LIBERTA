"""Golden reproduction (D4) — the engine ``cleanup.clean_text``, run per chapter on the frozen
reconciled witness, must reproduce the live ``cleanup.clean_text`` output (frozen by
``_generate_cleanup_fixture.py``) byte-for-byte: text, review flags, and punctuation-fix count.

This is the equivalence proof for the M4b-D1 / refinement-#4 relocations — the accent/letter-class
superset (``accented_letters`` adds ``É``; ``word_letter_class`` replaces the per-site ``À-ÿ``) and
the source-noise pattern moves (noise-line list, page-marker class, ``£→E``, inline page markers).
A relocation that changed output would surface as a divergent chapter here, not pass silently (I3).

Loads the real spaCy model + symspell index (``apply_dictionary_correction``) — asserted *hard*,
never skipped: a missing model is a real configuration error (``uv sync --extra it``), and a skip
here would hide a broken dictionary-correction port until it shipped.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.config.loader import load_book
from engine.dictionaries.frequency import load_word_set
from engine.dictionaries.symspell import load_symspell
from engine.lang.registry import get_language_plugin
from engine.paths import require_asset
from engine.steps import cleanup

GOLDEN_DIR = Path(__file__).resolve().parent
ENGINE_ROOT = GOLDEN_DIR.parents[1]
INPUTS = ENGINE_ROOT / "books" / "per_la_liberta" / "inputs"
EXPECTED = GOLDEN_DIR / "data" / "cleanup_detcore_expected.json"

pytestmark = pytest.mark.golden


def test_clean_text_reproduces_frozen_detcore():
    cfg = load_book("per_la_liberta")
    lang = get_language_plugin(cfg.language_id)

    chapters = json.loads((INPUTS / "reconciled_chapters.json").read_text(encoding="utf-8"))
    dict_path = require_asset(cfg.language.frequency_dictionary, kind="file")
    word_set = load_word_set(dict_path)
    sym = load_symspell(dict_path)
    nlp = lang.load_spacy(cfg.language.spacy_model, disable=["parser", "lemmatizer"])
    rules = cleanup.build_rules(cfg)

    expected = json.loads(EXPECTED.read_text(encoding="utf-8"))

    got: dict = {}
    for ch in chapters:
        text, flags, punct = cleanup.clean_text(ch["text"], word_set, rules, sym=sym, nlp=nlp)
        got[ch["id"]] = {"text": text, "flags": flags, "punct_fixes": punct}

    # Same chapter set, then per-chapter equality so a divergence names the offending chapter.
    assert set(got) == set(expected)
    for ch_id in expected:
        assert got[ch_id] == expected[ch_id], f"chapter {ch_id!r} diverged from the live clean_text"
