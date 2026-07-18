"""adjudicate is a classification spec, pinned by branch tests (no equivalence golden — F2/D3).

Three layers:
  1. **Classification branches** (fast, a fake in-memory oracle): each verdict — noise / ner /
     compound / corrected / unknown — is reached on a controlled flag, including the branches
     PLL's lost paired input could never replay. The fake oracle is the BR-001 seam in action:
     the classifier sees only its ``(found, matches)`` contract, never a real dictionary.
  2. **The real ``DictionaryOracle``** over a tiny temp chunk dir — chunk loading, word-boundary
     search, the <3-char floor, and the accent-insensitive retry, with no 13 MB asset.
  3. **Config bindings** (hard, not skipif): the boundary table comes from the source-noise
     profile (a different table changes a correction), and ``_build_oracle`` resolves the real
     monolingual period dictionary; plus a real-asset end-to-end ``run`` (integration).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.config.loader import load_book
from engine.lang.registry import get_language_plugin
from engine.paths import BookWorkspace
from engine.steps import adjudicate

ENGINE_ROOT = Path(__file__).resolve().parents[2]
SYNTH_INPUTS = ENGINE_ROOT / "books" / "synthetic" / "inputs"
LIVE_SUBS = {"i": ["r", "e"]}  # the live Bodoni boundary table


class FakeOracle:
    """Membership oracle backed by an in-memory ``word -> match_count`` map. Mirrors the real
    oracle's contract: ``__call__`` returns ``(found, matches)``; words shorter than 3 chars are
    rejected (so the classifier's short-word handling is exercised faithfully)."""

    name = "FakeDict"

    def __init__(self, known: dict[str, int]) -> None:
        self._known = known

    def __call__(self, word: str) -> tuple[bool, list[str]]:
        if not word or len(word) < 3:
            return False, []
        n = self._known.get(word)
        if n:
            return True, [f"{word} — gloss"] * n
        return False, []


def _classify(flags, *, known=None, subs=LIVE_SUBS):
    oracle = FakeOracle(known or {})
    results, stats = adjudicate.classify_flags(flags, oracle=oracle, boundary_subs=subs)
    return results, stats


def _only(results) -> dict:
    """The single classified entry across a one-token result set."""
    (items,) = results.values()
    assert len(items) == 1
    return items[0]


# --- the five classification branches --------------------------------------------------- #

def test_noise_branch():
    flags = {"ch": [{"token": "##", "left": "#", "right": "#", "reason": "dehyphenation"}]}
    results, stats = _classify(flags)
    assert _only(results)["resolution"] == "noise"
    assert stats["noise"] == 1


def test_ner_branch_when_neither_part_is_a_word():
    flags = {"ch": [{"token": "Lombardo-Veneto", "left": "Lombardo",
                     "right": "Veneto", "reason": "ner_candidate"}]}
    entry = _only(_classify(flags)[0])
    assert entry["resolution"] == "ner"
    assert "neither part in FakeDict" in entry["detail"]


def test_ner_branch_when_both_caps_even_if_one_is_a_word():
    # 'Lombardo' is also a common adjective → still NER because both parts are capitalised.
    flags = {"ch": [{"token": "Lombardo-Veneto", "left": "Lombardo",
                     "right": "Veneto", "reason": "ner_candidate"}]}
    entry = _only(_classify(flags, known={"Lombardo": 2})[0])
    assert entry["resolution"] == "ner"
    assert "'Lombardo' is also a dictionary word" in entry["detail"]


def test_compound_branch_requires_both_parts_long_and_confident():
    flags = {"ch": [{"token": "buon-giorno", "left": "buon",
                     "right": "giorno", "reason": "dehyphenation"}]}
    # buon is ≤5 chars → needs ≥2 hits; giorno is ≥6 → 1 hit suffices.
    entry = _only(_classify(flags, known={"buon": 2, "giorno": 1})[0])
    assert entry["resolution"] == "compound"
    assert "Both parts in FakeDict" in entry["detail"]


def test_compound_rejected_when_a_short_part_has_one_hit():
    # Same token, but 'buon' (≤5) with a single hit is not confident → not a compound.
    flags = {"ch": [{"token": "buon-giorno", "left": "buon",
                     "right": "giorno", "reason": "dehyphenation"}]}
    entry = _only(_classify(flags, known={"buon": 1, "giorno": 1})[0])
    assert entry["resolution"] != "compound"


def test_corrected_branch_via_simple_join():
    flags = {"ch": [{"token": "ben-essere", "left": "ben",
                     "right": "essere", "reason": "dehyphenation"}]}
    entry = _only(_classify(flags, known={"benessere": 1})[0])
    assert entry["resolution"] == "corrected"
    assert entry["suggestion"] == "benessere"


def test_unknown_branch_partial_then_neither():
    partial = {"ch": [{"token": "giustizi-aaa", "left": "giustizi",
                       "right": "aaa", "reason": "dehyphenation"}]}
    entry = _only(_classify(partial, known={"giustizi": 1})[0])
    assert entry["resolution"] == "unknown"
    assert "Left part 'giustizi' in FakeDict" in entry["detail"]

    neither = {"ch": [{"token": "zzz-qqq", "left": "zzz",
                       "right": "qqq", "reason": "dehyphenation"}]}
    entry = _only(_classify(neither)[0])
    assert entry["resolution"] == "unknown"
    assert entry["detail"] == "Neither part in FakeDict"


# --- the boundary table is read from config, not hardcoded ------------------------------ #

def test_boundary_substitutions_drive_corrections():
    # 'seri' + 'o': the only known target ('serro') is reachable *only* by the i→r boundary sub.
    flags = {"ch": [{"token": "seri-o", "left": "seri", "right": "o", "reason": "dehyphenation"}]}
    with_subs = _only(_classify(flags, known={"serro": 1}, subs={"i": ["r"]})[0])
    assert with_subs["resolution"] == "corrected" and with_subs["suggestion"] == "serro"

    # Same flag, empty boundary table → the correction is unreachable → unknown.
    without = _only(_classify(flags, known={"serro": 1}, subs={})[0])
    assert without["resolution"] == "unknown"


def test_try_corrections_covers_each_pass():
    join = adjudicate._try_corrections("ben", "essere", FakeOracle({"benessere": 1}), LIVE_SUBS)
    assert join == "benessere"

    boundary = adjudicate._try_corrections("seri", "o", FakeOracle({"serro": 1}), {"i": ["r"]})
    assert boundary == "serro"  # pass 2: boundary sub at the END of the left fragment

    # pass 3: boundary sub at the START of the right fragment — reachable only here (join "bene" is
    # unknown; left "be" has no substitutable boundary char, so pass 2 can't fire).
    boundary_right = adjudicate._try_corrections("be", "ne", FakeOracle({"bere": 1}), {"n": ["r"]})
    assert boundary_right == "bere"

    drop_i = adjudicate._try_corrections("ali", "ato", FakeOracle({"alato": 1}), {"i": ["r", "e"]})
    assert drop_i == "alato"  # pass 4a: drop the boundary 'i'

    drop_dup = adjudicate._try_corrections("sotto", "osta", FakeOracle({"sottosta": 1}), {})
    assert drop_dup == "sottosta"  # pass 4b: drop the duplicated boundary char


# --- the real DictionaryOracle over a tiny temp chunk dir ------------------------------- #

_FOLD = str.maketrans("àáâèéêìíîòóôùúûÀÁÂÈÉÊÌÍÎÒÓÔÙÚÛ", "aaaeeeiiiooouuuAAAEEEIIIOOOUUU")


def _temp_dict(tmp_path: Path) -> adjudicate.DictionaryOracle:
    (tmp_path / "c.txt").write_text(
        "casa, s. f. house, home.\ncaro, a. dear, expensive.\ncosi, av. thus, so.\n",
        encoding="utf-8",
    )
    return adjudicate.DictionaryOracle("Test Dict", tmp_path, "a-zA-ZÀ-ÿ", _FOLD)


def test_dictionary_oracle_membership_and_floor(tmp_path):
    oracle = _temp_dict(tmp_path)
    found, matches = oracle("casa")
    assert found and matches and "casa" in matches[0]
    assert oracle("zucchero") == (False, [])  # absent
    assert oracle("ca") == (False, [])        # < 3 chars → rejected before any search


def test_dictionary_oracle_accent_insensitive_retry(tmp_path):
    # 'così' is absent verbatim but its accent-stripped form 'cosi' is present → found on retry.
    oracle = _temp_dict(tmp_path)
    found, _ = oracle("così")
    assert found


def test_dictionary_oracle_lookup_and_context(tmp_path):
    oracle = _temp_dict(tmp_path)
    assert "house" in oracle.lookup("casa")
    assert oracle.lookup("zucchero") is None
    ctx = adjudicate.dictionary_context_for_flags(
        [{"token": "casa-caro", "left": "casa", "right": "caro"}], oracle
    )
    assert "Test Dict Dictionary Reference" in ctx and "casa" in ctx


def test_search_chunk_respects_word_boundaries(tmp_path):
    # 'cas' must not match inside 'casa' — the boundary anchors are why 'fl' won't hit 'ffle'.
    chunk = "casa, s. f. house.\n"
    assert adjudicate._search_chunk("casa", chunk, "a-zA-ZÀ-ÿ")
    assert not adjudicate._search_chunk("cas", chunk, "a-zA-ZÀ-ÿ")


# --- config binding: _build_oracle resolves the real monolingual dictionary ------------- #

def test_build_oracle_selects_the_monolingual_period_dictionary():
    cfg = load_book("per_la_liberta")
    oracle = adjudicate._build_oracle(cfg)
    assert oracle.name == "Zingarelli 1922"     # the monolingual member, not Edgren/Hoare
    assert oracle._dir.name == "zingarelli_1922"
    assert oracle._dir.is_dir()                  # the asset symlink resolves (hard, not skipif)


# --- run(): degradation, injected oracle, and a real-asset end-to-end ------------------- #

def test_run_without_flags_declares_no_input(tmp_path):
    # No review_flags.json → an *explicit* no-input envelope is written (not absent, not bare {}),
    # so a downstream consumer can tell "no input" apart from "zero results"/an upstream failure.
    cfg = load_book("synthetic")
    lang = get_language_plugin(cfg.language_id)
    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()

    envelope = adjudicate.run(workspace=ws, cfg=cfg, lang=lang)

    assert envelope["input_present"] is False
    assert envelope["tokens"] == 0 and envelope["results"] == {}
    written = ws.data / adjudicate.RESULTS_FILE
    assert written.is_file()
    assert json.loads(written.read_text(encoding="utf-8")) == envelope


def _seed_flags(tmp_path: Path) -> BookWorkspace:
    cfg_ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()
    (cfg_ws.data / adjudicate.REVIEW_FLAGS_FILE).write_text(
        (SYNTH_INPUTS / "review_flags.json").read_text(encoding="utf-8"), encoding="utf-8"
    )
    return cfg_ws


def test_run_with_injected_oracle_classifies_synthetic_flags(tmp_path):
    cfg = load_book("synthetic")
    lang = get_language_plugin(cfg.language_id)
    ws = _seed_flags(tmp_path)

    # An oracle that knows nothing → deterministic verdicts independent of any real dictionary.
    envelope = adjudicate.run(workspace=ws, cfg=cfg, lang=lang, oracle=FakeOracle({}))

    assert envelope["input_present"] is True and envelope["tokens"] == 4
    written = json.loads((ws.data / adjudicate.RESULTS_FILE).read_text(encoding="utf-8"))
    assert written == envelope
    verdicts = {e["resolution"] for items in envelope["results"].values() for e in items}
    assert verdicts <= {"noise", "ner", "compound", "corrected", "unknown"}
    assert envelope["stats"]["noise"] == 1   # '##'
    assert envelope["stats"]["ner"] == 1     # 'Lombardo-Veneto' (ner_candidate, unknown parts)


@pytest.mark.integration
def test_run_with_real_zingarelli_oracle(tmp_path):
    # The default path: _build_oracle loads the real monolingual dictionary chunks. Asserts the
    # end-to-end binding works; classifications depend on the 13 MB asset so are not pinned here.
    cfg = load_book("synthetic")
    lang = get_language_plugin(cfg.language_id)
    ws = _seed_flags(tmp_path)

    envelope = adjudicate.run(workspace=ws, cfg=cfg, lang=lang)

    assert envelope["input_present"] is True and envelope["tokens"] == 4
    for items in envelope["results"].values():
        for entry in items:
            assert entry["resolution"] in {"noise", "ner", "compound", "corrected", "unknown"}
