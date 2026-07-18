"""Asset binding: every asset the resolved config references must actually resolve.

The config carries asset *paths* as strings; nothing in the schema proves they point at a
real file. These tests close that gap — they would have caught the frequency-dictionary
path pointing at a nonexistent location. They assert hard (no skipif): a bare ``uv sync``
without ``--extra it`` should fail loudly here, not skip silently, because the only book is
Italian and cannot be processed without its model + dictionaries.
"""

from __future__ import annotations

import importlib.util

import pytest

from engine import paths
from engine.config.loader import load_book
from engine.errors import MissingInputError
from engine.lang import base
from engine.lang.italian import ItalianLanguagePlugin


def test_frequency_dictionary_resolves_to_a_file():
    cfg = load_book("per_la_liberta")
    p = paths.asset_path(cfg.language.frequency_dictionary)
    assert p.is_file(), f"frequency dictionary not found at {p}"


def test_period_dictionaries_resolve_to_dirs():
    cfg = load_book("per_la_liberta")
    # Non-empty guard FIRST: without it, an emptied list makes the loop below cover nothing and pass
    # green — while the ≥2-of-3 period oracle silently loses every dictionary and misclassifies the
    # whole corpus as OCR garble. The vacuous-pass is more dangerous than a missing test.
    assert cfg.language.period_dictionaries, "no period dictionaries configured — oracle would be empty"
    for d in cfg.language.period_dictionaries:
        p = paths.asset_path(d.dir)
        assert p.is_dir(), f"period dictionary {d.name!r} not found at {p}"


# --- invariant I1 negative controls: a missing/typo'd asset is a *typed* failure, not a bare
# FileNotFoundError. The two tests above are positive controls (the real book's assets resolve);
# these exercise the failure branch require_asset closes (engine/docs/invariants.md, I1).

def test_require_asset_missing_file_is_typed_not_bare():
    with pytest.raises(MissingInputError) as exc:
        paths.require_asset("does/not/exist/freq.txt", kind="file")
    assert exc.value.exit_code == 3
    assert "does/not/exist/freq.txt" in str(exc.value)


def test_require_asset_missing_dir_is_typed_not_bare():
    with pytest.raises(MissingInputError) as exc:
        paths.require_asset("dictionary/no_such_dir", kind="dir")
    assert exc.value.exit_code == 3


def test_require_asset_kind_mismatch_does_not_pass_silently():
    # The real frequency dictionary is a file; requesting it as a dir must still fail typed,
    # not return a path that a downstream dir-walk would choke on.
    cfg = load_book("per_la_liberta")
    with pytest.raises(MissingInputError):
        paths.require_asset(cfg.language.frequency_dictionary, kind="dir")


def test_require_asset_returns_resolved_path_when_present():
    cfg = load_book("per_la_liberta")
    p = paths.require_asset(cfg.language.frequency_dictionary, kind="file")
    assert p.is_file() and p == paths.asset_path(cfg.language.frequency_dictionary)


def test_spacy_model_is_installed():
    cfg = load_book("per_la_liberta")
    model = cfg.language.spacy_model
    assert importlib.util.find_spec(model) is not None, (
        f"spaCy model {model!r} not installed; run `uv sync --extra it`"
    )


def test_load_spacy_caches_by_model_and_disable(monkeypatch):
    # Exercise the cache logic without the heavy model: a fresh cache + a fake spacy.load.
    monkeypatch.setattr(base, "_SPACY_PIPELINES", {})
    import spacy

    calls: list[tuple] = []

    def fake_load(model, disable=None):
        calls.append((model, tuple(disable or ())))
        return object()

    monkeypatch.setattr(spacy, "load", fake_load)
    plugin = ItalianLanguagePlugin()

    a = plugin.load_spacy("zz_fake_model")
    b = plugin.load_spacy("zz_fake_model")
    assert a is b and len(calls) == 1  # same (model, disable) → cached, loaded once

    c = plugin.load_spacy("zz_fake_model", disable=["ner"])
    assert c is not a and len(calls) == 2  # different disable → distinct pipeline


def test_load_spacy_missing_model_gives_actionable_error(monkeypatch):
    monkeypatch.setattr(base, "_SPACY_PIPELINES", {})
    import spacy

    def boom(model, disable=None):
        raise OSError("can't find model")

    monkeypatch.setattr(spacy, "load", boom)
    with pytest.raises(OSError, match="uv sync --extra"):
        ItalianLanguagePlugin().load_spacy("nope_model")


@pytest.mark.integration
def test_load_spacy_real_model_returns_pipeline():
    from spacy.language import Language

    cfg = load_book("per_la_liberta")
    nlp = ItalianLanguagePlugin().load_spacy(
        cfg.language.spacy_model, disable=["parser", "lemmatizer"]
    )
    assert isinstance(nlp, Language)
