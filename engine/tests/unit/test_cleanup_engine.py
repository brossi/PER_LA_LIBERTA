"""cleanup port — property, separability, leakage, and regen-guard tiers.

The deterministic core's equivalence is the detcore golden (``tests/golden/test_cleanup_golden``);
its no-Italian-literal neutrality is ``test_cleanup_neutrality``. Here:

  - **property** — the config-driven markdown wrapper, the part-stable chapter sort, the LLM-path
    pure helpers (user-message + preamble + diff-extract + correction-apply + batch-request build),
    ``reconcile_flags``, and the rules-are-built-from-config binding;
  - **regen-guard** — refuses to clobber an existing ``clean.md`` without the kwarg/env override;
  - **leakage** — the cleanup-correct prompt under the synthetic book leaks no PLL/Italian string;
  - **separability** (``integration``, real spaCy+symspell) — the synthetic book runs end-to-end
    deterministically, and the LLM path drives the injected ``Chat`` seam + full-text cache.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.config.loader import load_book
from engine.errors import MissingInputError, RegenerationGuardError
from engine.lang.registry import get_language_plugin
from engine.paths import BookWorkspace
from engine.steps import cleanup
from engine.util.jsonio import read_json

ENGINE_ROOT = Path(__file__).resolve().parents[2]
SYNTHETIC_INPUTS = ENGINE_ROOT / "books" / "synthetic" / "inputs"


# --- test doubles ------------------------------------------------------------------------ #

class _FakeOracle:
    """No-knowledge membership oracle — for batch-request building, where containment/structure
    matters, not the dictionary. Satisfies ``dictionary_context_for_flags`` (``name`` + ``lookup``)."""

    name = "FakeDict"

    def __call__(self, word):
        return False, []

    def lookup(self, word, context_lines=3):
        return None


class _FakeCorrectChat:
    """``cleanup.Chat`` double — returns a fixed corrected text and records what it was handed."""

    def __init__(self, reply: str = "TESTO CORRETTO") -> None:
        self._reply = reply
        self.calls: list[tuple[str, str]] = []

    def correct(self, *, system: str, user: str) -> str:
        self.calls.append((system, user))
        return self._reply


# --- property: config-driven markdown wrapper -------------------------------------------- #

def test_render_markdown_is_config_driven():
    cfg = load_book("synthetic")
    rendered = [
        ({"id": "prefazione", "part": 0, "title": "Prefazione"}, "corpo pref"),
        ({"id": "p1_capitolo_primo", "part": 1, "title": "Capitolo Primo"}, "corpo uno"),
        ({"id": "p1_capitolo_secondo", "part": 1, "title": "Capitolo Secondo"}, "corpo due"),
    ]
    md = cleanup.render_markdown(rendered, cfg, chapter_pages={"p1_capitolo_primo": [3, 4]})

    assert md.startswith("# Libro di Prova")                       # edition.title_it
    assert "*Edizione sintetica per i test del motore*" in md      # edition.subtitle_it
    assert "**Autore Sintetico** (1901)" in md                     # byline: author bold, year outside
    assert "## Prefazione" in md                                   # part 0 → H2, title from data
    assert "## Parte Prima" in md                                  # part header from structure.parts
    assert "### Capitolo Primo" in md                              # part ≥ 1 → H3
    assert "<!-- pages:3-4 -->" in md                              # page provenance from chapter_pages
    assert "### Capitolo Secondo" in md and "corpo due" in md


def test_render_markdown_rule_separates_only_subsequent_parts():
    cfg = load_book("per_la_liberta")  # two parts
    rendered = [
        ({"id": "prefazione", "part": 0, "title": "PREFAZIONE"}, "p"),
        ({"id": "p1_ch01", "part": 1, "title": "Capitolo Primo"}, "a"),
        ({"id": "p2_ch01", "part": 2, "title": "Capitolo Primo"}, "b"),
    ]
    md = cleanup.render_markdown(rendered, cfg, {})
    assert "## Parte Prima" in md and "## Parte Seconda" in md
    # A '---' rule precedes the second part; the first part has none directly before its header.
    pre_seconda = md[:md.index("## Parte Seconda")]
    assert pre_seconda.rstrip().endswith("---")
    pre_prima = md[:md.index("## Parte Prima")]
    # the only '---' before Parte Prima is the title-block rule, not a part separator right above it
    assert not pre_prima.rstrip().endswith("---") or "**" in pre_prima.rstrip().splitlines()[-2]


def test_sort_chapters_is_stable_by_part_and_handles_long_ids():
    chapters = [
        {"id": "p1_capitolo_primo", "part": 1},
        {"id": "p2_capitolo_primo", "part": 2},
        {"id": "prefazione", "part": 0},
        {"id": "p1_capitolo_secondo", "part": 1},
    ]
    assert [c["id"] for c in cleanup._sort_chapters(chapters)] == [
        "prefazione", "p1_capitolo_primo", "p1_capitolo_secondo", "p2_capitolo_primo",
    ]


# --- property: rules are built from config (binding, not baked) -------------------------- #

def test_rules_are_built_from_config_not_baked():
    cfg = load_book("per_la_liberta")
    rules = cleanup.build_rules(cfg)
    assert cfg.language.word_letter_class in rules.hyphen_token_re.pattern
    assert cfg.language.accented_letters in rules.real_word_short_re.pattern
    assert len(rules.noise_line_patterns) == len(cfg.source_noise.noise_line_patterns)
    assert len(rules.char_substitutions) == len(cfg.source_noise.char_substitutions)
    # the source-noise char-sub *replacement* (£→E) comes from config, not a hardcoded "E".
    assert rules.char_substitutions[0][1] == cfg.source_noise.char_substitutions[0][1]


# --- property: LLM-path pure helpers ----------------------------------------------------- #

def test_build_user_content_appends_reference_only_when_context_given():
    plain = cleanup.build_user_content("testo", "Capitolo Primo")
    assert "Capitolo Primo" in plain and "REFERENCE" not in plain
    withref = cleanup.build_user_content("testo", "Capitolo Primo", "DICT EVIDENCE")
    assert "REFERENCE" in withref and "DICT EVIDENCE" in withref


def test_strip_preamble_removes_known_lead_only():
    assert cleanup.strip_preamble("Ecco il testo corretto:\n\nVero corpo") == "Vero corpo"
    assert cleanup.strip_preamble("I'll correct this.\n\nCorpo") == "Corpo"
    # a real corrected text with no preamble is untouched
    assert cleanup.strip_preamble("Nel mezzo del cammin") == "Nel mezzo del cammin"


def test_build_batch_requests_skips_cached_and_builds_params():
    chapters = [{"id": "a", "title": "A"}, {"id": "b", "title": "B"}]
    reqs = cleanup.build_batch_requests(
        chapters, {"a": "testo a", "b": "testo b"}, {}, skip_ids={"a"},
        system="SYS", oracle=_FakeOracle(),
    )
    assert [r["custom_id"] for r in reqs] == ["b"]
    params = reqs[0]["params"]
    assert params["system"] == "SYS"
    assert params["model"] == cleanup._LLM_CORRECT_MODEL
    assert "testo b" in params["messages"][0]["content"]


def test_build_batch_requests_appends_dictionary_context_when_flagged():
    reqs = cleanup.build_batch_requests(
        [{"id": "a", "title": "A"}], {"a": "x"},
        {"a": [{"token": "co-mune", "left": "co", "right": "mune"}]},
        set(), "SYS", _FakeOracle(),
    )
    assert "REFERENCE" in reqs[0]["params"]["messages"][0]["content"]


# --- property: post-LLM flag bookkeeping ------------------------------------------------- #

def test_reconcile_flags_keeps_surviving_and_preserves_original(tmp_path):
    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()
    (ws.output / cleanup.CLEAN_FILE).write_text("il gatto bianco corre", encoding="utf-8")
    (ws.data / cleanup.REVIEW_FLAGS_FILE).write_text(json.dumps({
        "ch1": [
            {"token": "corre", "context": "bianco corre"},  # survives
            {"token": "nero", "context": "gatto nero"},      # gone
        ]
    }), encoding="utf-8")

    summary = cleanup.reconcile_flags(ws)
    assert summary == {"original": 2, "remaining": 1, "resolved": 1}
    remaining = read_json(ws.data / cleanup.REVIEW_FLAGS_REMAINING_FILE)
    assert remaining == {"ch1": [{"token": "corre", "context": "bianco corre"}]}
    assert (ws.data / cleanup.REVIEW_FLAGS_FILE).is_file()  # original preserved intact


def test_reconcile_flags_skips_when_inputs_missing(tmp_path):
    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()
    assert cleanup.reconcile_flags(ws) == {"original": 0, "remaining": 0, "resolved": 0}


# --- regen-guard (BR-012 / M4b-D2) ------------------------------------------------------- #

def test_regen_guard_blocks_existing_without_override(tmp_path):
    out = tmp_path / "clean.md"
    out.write_text("hand-tuned", encoding="utf-8")
    with pytest.raises(RegenerationGuardError) as ei:
        cleanup._check_regen_guard(out, allow_regen=False)
    assert ei.value.exit_code == 6
    assert cleanup.ENGINE_ALLOW_REGEN_ENV in str(ei.value)


def test_regen_guard_allows_with_kwarg_or_env(tmp_path, monkeypatch):
    out = tmp_path / "clean.md"
    out.write_text("x", encoding="utf-8")
    cleanup._check_regen_guard(out, allow_regen=True)            # kwarg override
    monkeypatch.setenv(cleanup.ENGINE_ALLOW_REGEN_ENV, "1")
    cleanup._check_regen_guard(out, allow_regen=False)           # env override


def test_regen_guard_is_inert_without_existing_output(tmp_path):
    cleanup._check_regen_guard(tmp_path / "absent.md", allow_regen=False)  # no raise


def test_run_refuses_to_clobber_existing_clean_md(tmp_path):
    cfg = load_book("synthetic")
    lang = get_language_plugin(cfg.language_id)
    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()
    (ws.output / cleanup.CLEAN_FILE).write_text("hand-tuned", encoding="utf-8")
    with pytest.raises(RegenerationGuardError):  # raised before any model load
        cleanup.run(workspace=ws, cfg=cfg, lang=lang)


def test_run_without_reconciled_is_typed_missing_input(tmp_path):
    cfg = load_book("synthetic")
    lang = get_language_plugin(cfg.language_id)
    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()  # guard passes (no clean.md)
    with pytest.raises(MissingInputError) as ei:
        cleanup.run(workspace=ws, cfg=cfg, lang=lang)
    assert ei.value.exit_code == 3 and cleanup.RECONCILED_FILE in str(ei.value)


# --- leakage: cleanup-correct prompt under the synthetic book ---------------------------- #

def test_no_pll_string_leaks_in_correct_prompt():
    rendered = cleanup.render_correct_prompt(load_book("synthetic"))
    for leaked in ("Per la libertà", "Crespi", "1913", "Italian", "à", "è", "ì", "ò", "ù", "é"):
        assert leaked not in rendered, f"PLL/Italian string {leaked!r} leaked from the template"
    for present in ("Libro di Prova", "Autore Sintetico", "1901", "Sintetico"):
        assert present in rendered, f"synthetic fact {present!r} did not interpolate"


def test_correct_prompt_carries_real_book_identity():
    rendered = cleanup.render_correct_prompt(load_book("per_la_liberta"))
    assert "Per la libertà!" in rendered and "Cesare Crespi" in rendered and "Italian" in rendered


# --- separability: synthetic book end-to-end (real spaCy + symspell) --------------------- #

def _seed_reconciled(ws: BookWorkspace) -> None:
    (ws.data / cleanup.RECONCILED_FILE).write_text(
        (SYNTHETIC_INPUTS / "reconciled_chapters.json").read_text(encoding="utf-8"), encoding="utf-8"
    )


@pytest.mark.integration
def test_cleanup_runs_deterministically_on_synthetic_book(tmp_path):
    cfg = load_book("synthetic")
    lang = get_language_plugin(cfg.language_id)
    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()
    _seed_reconciled(ws)

    result = cleanup.run(workspace=ws, cfg=cfg, lang=lang)

    assert result["chapters"] == 3 and result["used_llm"] is False
    out = (ws.output / cleanup.CLEAN_FILE).read_text(encoding="utf-8")
    assert out.startswith("# Libro di Prova") and "## Parte Prima" in out
    assert ws.output in (ws.output / cleanup.CLEAN_FILE).parents


@pytest.mark.integration
def test_cleanup_llm_path_drives_chat_seam_and_caches(tmp_path):
    cfg = load_book("synthetic")
    lang = get_language_plugin(cfg.language_id)
    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()
    _seed_reconciled(ws)

    chat = _FakeCorrectChat("TESTO CORRETTO")
    result = cleanup.run(
        workspace=ws, cfg=cfg, lang=lang, use_llm=True, chat=chat, oracle=_FakeOracle()
    )

    assert result["used_llm"] is True
    assert len(chat.calls) == 3                          # one per uncached chapter
    # the system prompt the seam saw is the synthetic-rendered correct prompt (no PLL identity)
    assert "Libro di Prova" in chat.calls[0][0] and "Per la libertà" not in chat.calls[0][0]
    cached = (ws.state / "llm_cleaned" / "p1_capitolo_primo.txt").read_text(encoding="utf-8")
    assert cached == "TESTO CORRETTO"
    assert "TESTO CORRETTO" in (ws.output / cleanup.CLEAN_FILE).read_text(encoding="utf-8")


@pytest.mark.integration
def test_cleanup_llm_failure_degrades_to_deterministic_text(tmp_path):
    # The LLM per-chapter failure branch (cleanup.py:951): a chat.correct() exception must degrade to
    # the deterministic clean_text output — not crash, not poison the cache. The happy-path LLM test
    # never raises, so this branch was untested; a regression that let the exception propagate, or
    # wrote a sentinel/empty cache, would ship green.
    cfg = load_book("synthetic")
    lang = get_language_plugin(cfg.language_id)

    class _BoomChat:
        def __init__(self) -> None:
            self.calls = 0

        def correct(self, *, system: str, user: str) -> str:
            self.calls += 1
            raise RuntimeError("model-unavailable")

    # run 1: use_llm=True but every chat.correct() raises → degradation
    ws1 = BookWorkspace.for_book("synthetic", tmp_path / "a").ensure()
    _seed_reconciled(ws1)
    chat = _BoomChat()
    result = cleanup.run(
        workspace=ws1, cfg=cfg, lang=lang, use_llm=True, chat=chat, oracle=_FakeOracle()
    )
    assert result["used_llm"] is True
    assert chat.calls == 3  # every uncached chapter was attempted, none silently skipped
    cache = ws1.state / "llm_cleaned"
    assert not cache.exists() or not list(cache.glob("*.txt"))  # failure must not poison the cache

    # run 2: the no-LLM deterministic baseline
    ws2 = BookWorkspace.for_book("synthetic", tmp_path / "b").ensure()
    _seed_reconciled(ws2)
    cleanup.run(workspace=ws2, cfg=cfg, lang=lang)

    # the degraded output is byte-identical to the deterministic baseline — the branch falls back
    # cleanly to clean_text, adding nothing and dropping nothing.
    assert (ws1.output / cleanup.CLEAN_FILE).read_text(encoding="utf-8") == (
        ws2.output / cleanup.CLEAN_FILE
    ).read_text(encoding="utf-8")


@pytest.mark.integration
def test_cleanup_cache_wins_over_fresh_clean(tmp_path):
    cfg = load_book("synthetic")
    lang = get_language_plugin(cfg.language_id)
    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()
    _seed_reconciled(ws)
    cache_dir = ws.state / "llm_cleaned"
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "prefazione.txt").write_text("CACHED PREFAZIONE BODY", encoding="utf-8")

    # use_llm=False, but a chapter cache exists → the cache wins for that chapter (live precedence).
    cleanup.run(workspace=ws, cfg=cfg, lang=lang)

    assert "CACHED PREFAZIONE BODY" in (ws.output / cleanup.CLEAN_FILE).read_text(encoding="utf-8")
