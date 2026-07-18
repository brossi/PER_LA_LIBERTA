"""Prompt-templating machinery: namespaced context, StrictUndefined, and the separability tier.

The OCR template is the first consumer. The separability/leakage tier (the decided design, BR-008)
is a **single** render of the synthetic book's *own loaded context* asserting **no PLL string leaks
at all** — book identity (`Per la libertà`, `Crespi`, `1913`) *and* language facts (the name
`Italian`, the accent list `à è ì ò ù é`). For the language-fact half to bite while the synthetic
book keeps the Italian *plugin* (it must — only `it` is registered, BR-002), the synthetic manifest
**overrides** its prompt-facing language facts (`display_name`, `accent_inventory`) to non-Italian
values; `language_id` stays `it`, so reconcile/validate's Italian word-scoring is untouched. A baked
Italian name or accent then surfaces here as a leak. Full non-Italian *book* separability (the
language-axis seams cleanup consumes) remains BR-002.
"""

from __future__ import annotations

import pytest
from jinja2 import UndefinedError

from engine.config.loader import load_book
from engine.contracts.markers import SENTINEL_BLANK
from engine.prompts.templating import PROMPTS_DIR, PromptTemplate, build_prompt_context


def _render_ocr(book_id: str) -> str:
    tmpl = PromptTemplate.load("ocr")
    ctx = build_prompt_context(load_book(book_id))
    return tmpl.render(**ctx, blank_sentinel=SENTINEL_BLANK)


def test_template_file_is_profile_resident_and_loadable():
    # validate-bindings: the machinery resolves templates from the shared profiles/ tree, and the
    # OCR template actually exists there (not shape-asserted — load() reads the file).
    assert PROMPTS_DIR.name == "prompts" and PROMPTS_DIR.parent.name == "profiles"
    assert (PROMPTS_DIR / "ocr.txt.j2").is_file()
    assert PromptTemplate.load("ocr").name == "ocr"


def test_load_missing_template_is_a_clean_error():
    with pytest.raises(FileNotFoundError, match="prompt template not found"):
        PromptTemplate.load("no_such_template")


def test_build_prompt_context_is_namespaced():
    ctx = build_prompt_context(load_book("per_la_liberta"))
    assert set(ctx) == {"book", "language"}
    # book namespace = the manifest's free prompt_context verbatim (no language_name)
    assert ctx["book"]["book_title"] == "Per la libertà!"
    assert "language_name" not in ctx["book"]
    # language namespace = cross-title facts from the profile
    assert ctx["language"]["display_name"] == "Italian"
    assert ctx["language"]["accent_inventory"] == ["à", "è", "ì", "ò", "ù", "é"]


def test_strict_undefined_raises_on_missing_context_key():
    tmpl = PromptTemplate.load("ocr")
    # language present, but book missing every key it references → hard render error, not blanks.
    with pytest.raises(UndefinedError):
        tmpl.render(
            book={}, language={"display_name": "X", "accent_inventory": ["ñ"]},
            blank_sentinel=SENTINEL_BLANK,
        )


def test_synthetic_fixture_carries_non_pll_language_facts_for_separability():
    # The override that makes the single leakage render bite: distinct prompt-facing language facts,
    # while language_id stays 'it' (so the Italian plugin / reconcile word-scoring are unchanged).
    lp = load_book("synthetic").language
    assert lp.language_id == "it"
    assert lp.display_name == "Sintetico"
    assert lp.accent_inventory == ("ñ", "ç", "ø")
    assert not (set("àèìòùéÀÈÌÒÙÉ") & set("".join(lp.accent_inventory))), (
        "synthetic accent inventory must share no Italian accent, or the leak test can't bite"
    )


def test_no_pll_string_leaks_under_synthetic_render():
    # The decided separability tier (BR-008): one render of the synthetic book's own context leaks
    # NO PLL string — book identity AND language facts. A baked Italian name or accent shows here.
    rendered = _render_ocr("synthetic")
    for leaked in (
        "Per la libertà", "Crespi", "1913", "Italian", "à", "è", "ì", "ò", "ù", "é",
    ):
        assert leaked not in rendered, f"PLL/Italian string {leaked!r} leaked from the template"
    # ...and the synthetic book's own identity + language facts ARE present (interpolation works).
    for present in ("Libro di Prova", "Autore Sintetico", "1901", "Sintetico", "ñ"):
        assert present in rendered
