"""triage port — property, separability, and prompt-leakage tiers (no equivalence golden: LLM).

The pure mechanics (plausibility check, the three resolution passes, the occurrence-safe apply) are
unit-tested directly. Separability runs the synthetic book's flagged segments through an injected
chat and asserts the outputs land + the chapters mutate. The leakage tier renders the triage system
prompt under the synthetic book's own (non-Italian-overridden) context and asserts no PLL/Italian
string leaks — the engine-agnostic invariant, mirroring the OCR template's leakage test.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.config.loader import load_book
from engine.lang.registry import get_language_plugin
from engine.paths import BookWorkspace
from engine.steps import triage
from engine.util.jsonio import read_json

ENGINE_ROOT = Path(__file__).resolve().parents[2]
SYNTHETIC_INPUTS = ENGINE_ROOT / "books" / "synthetic" / "inputs"


# --- test double ------------------------------------------------------------------------- #

class _FakeChat:
    """``triage.Chat`` double: returns canned ``classify_disagreement`` inputs in order, and records
    the system/user it was handed (so a test can assert what was rendered)."""

    def __init__(self, results: list[dict]) -> None:
        self._results = results
        self.calls: list[tuple[str, str]] = []

    def classify(self, *, system: str, tool: dict, user: str) -> list[dict]:
        self.calls.append((system, user))
        return self._results


def _verdict(category, proposed, confidence, needs_human):
    return {
        "category": category,
        "proposed_reading": proposed,
        "confidence": confidence,
        "reasoning": "test",
        "needs_human": needs_human,
    }


def _reviewed(chosen, verdict, *, chapter="c", paragraph=0):
    return {"chapter": chapter, "paragraph": paragraph, "chosen": chosen, "triage": verdict}


# --- property: plausibility ------------------------------------------------------------- #

def test_plausibility_requires_both_strings():
    assert triage._is_plausible_correction("", "x") is False
    assert triage._is_plausible_correction("x", "") is False


def test_plausibility_accepts_near_match_rejects_drift():
    assert triage._is_plausible_correction("comuni", "comune") is True   # ratio ~0.83
    assert triage._is_plausible_correction("abc", "abc") is True         # identical
    assert triage._is_plausible_correction("foo", "completelydifferentword") is False


# --- property: the three resolution passes ----------------------------------------------- #

def test_resolution_passes_map_every_branch():
    reviewed = [
        _reviewed("comuni", _verdict("ocr_confusion", "comune", "high", False)),       # accept
        _reviewed("foo", _verdict("alignment_drift", "completelydifferentword", "high", False)),  # reject
        _reviewed("bar", _verdict("unknown", "bar", "high", True)),                     # needs_human
        _reviewed("baz", _verdict("ocr_corruption", "baz2", "low", False)),             # low_conf
    ]
    resolved, stats = triage.apply_resolution_passes(reviewed)

    assert [(r["resolution_source"], r["resolved"]) for r in resolved] == [
        ("llm_triage", "comune"),
        ("plausibility_rejected", "foo"),
        ("needs_human", "bar"),
        ("low_confidence", "baz"),
    ]
    assert stats["auto_accepted"] == 1
    assert stats["needs_human"] == 3
    assert stats["by_category"] == {
        "ocr_confusion": 1, "alignment_drift": 1, "unknown": 1, "ocr_corruption": 1,
    }
    # purity: the input list is not mutated (resolution fields land only on the returned copies).
    assert all("resolved" not in item for item in reviewed)


def test_medium_confidence_is_also_auto_accepted():
    resolved, stats = triage.apply_resolution_passes(
        [_reviewed("comuni", _verdict("ocr_confusion", "comune", "medium", False))]
    )
    assert resolved[0]["resolution_source"] == "llm_triage"
    assert stats["auto_accepted"] == 1


# --- property: witnesses + user-message building ----------------------------------------- #

def test_build_witnesses_lists_sources_then_copy3():
    witnesses = triage.build_witnesses(load_book("synthetic"))
    assert witnesses == [
        "Copy 1: synthetic copy 1",
        "Copy 2: synthetic copy 2",
        "Copy 3: vision-model OCR of the source scan",
    ]


def test_build_witnesses_excludes_diagnostic_comparison_sources():
    cfg = load_book("ninnoli")
    witnesses = triage.build_witnesses(cfg)
    assert witnesses == [
        "Copy 1: 1884 third edition / University of Toronto scan / Internet Archive OCR",
        "Copy 3: vision-model OCR of the source scan",
    ]


def test_user_message_blocks_every_item():
    batch = [
        {"chapter": "ch", "paragraph": 2, "word_copy1": "a", "word_copy2": "b",
         "word_copy3": "c", "context": "x a b", "chosen": "a"},
        {"chapter": "ch", "paragraph": 3, "word_copy1": "d", "word_copy2": "e", "chosen": "d"},
    ]
    msg = triage.build_user_message(batch)
    assert "Classify each of these 2 OCR disagreements" in msg
    assert "Item 1:" in msg and "Item 2:" in msg
    assert 'Copy 3: "c"' in msg          # copy3 + context only when present
    assert "Context: ...x a b..." in msg
    assert "Copy 3" not in msg.split("Item 2:")[1]  # item 2 had no copy3


# --- property: apply is occurrence-safe and idempotent ----------------------------------- #

def _seed(ws):
    (ws.data / "reconciled_chapters.json").write_text(
        (SYNTHETIC_INPUTS / "reconciled_chapters.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )


def test_apply_resolutions_is_idempotent(tmp_path):
    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()
    _seed(ws)
    resolved = [{"chapter": "p1_capitolo_primo", "paragraph": 0,
                 "chosen": "comuni", "resolved": "comune"}]

    first = triage.apply_resolutions(ws, resolved)
    text = read_json(ws.data / "reconciled_chapters.json")[1]["text"]
    assert "sono comune e ben note" in text and "sono comuni e ben note" not in text

    second = triage.apply_resolutions(ws, resolved)  # word already gone → no-op
    assert (first, second) == (1, 0)


def test_apply_resolutions_is_occurrence_safe(tmp_path):
    # The apply path's headline invariant (triage.py:314-321), which the idempotency test cannot see
    # (its word occurs once): a correction replaces only the FIRST uncorrected occurrence of a
    # recurring word, and N same-word corrections land on N DISTINCT positions — never replace-all,
    # never both on index 0.
    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()
    chapter = {"id": "p1_capitolo_primo", "title": "X", "part": 1,
               "text": "alfa comuni beta comuni gamma comuni"}

    def seed():
        (ws.data / "reconciled_chapters.json").write_text(json.dumps([chapter]), encoding="utf-8")

    one = {"chapter": "p1_capitolo_primo", "paragraph": 0, "chosen": "comuni", "resolved": "comune"}

    # one correction → only the first "comuni" changes (a replace-all regression is caught here)
    seed()
    n1 = triage.apply_resolutions(ws, [one])
    text1 = read_json(ws.data / "reconciled_chapters.json")[0]["text"]
    assert (n1, text1) == (1, "alfa comune beta comuni gamma comuni")

    # two same-word corrections → first two occurrences, distinct positions (dropping the
    # corrected_positions guard makes the second a no-op on index 0, leaving position 3 unchanged)
    seed()
    n2 = triage.apply_resolutions(ws, [one, dict(one)])
    text2 = read_json(ws.data / "reconciled_chapters.json")[0]["text"]
    assert (n2, text2) == (2, "alfa comune beta comune gamma comuni")


# --- separability: synthetic flagged segments through an injected chat -------------------- #

def test_synthetic_triage_resolves_and_mutates(tmp_path, monkeypatch):
    monkeypatch.setattr(triage, "_BATCH_DELAY", 0)
    cfg = load_book("synthetic")
    lang = get_language_plugin(cfg.language_id)
    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()
    _seed(ws)
    (ws.data / "flagged_segments.json").write_text(
        (SYNTHETIC_INPUTS / "flagged_segments.json").read_text(encoding="utf-8"), encoding="utf-8"
    )

    # Two items need triage (the majority_vote one is filtered out); fake returns them in order.
    chat = _FakeChat([
        _verdict("ocr_confusion", "comune", "high", False),   # comuni -> comune (applied)
        _verdict("ocr_corruption", "ordinato", "low", True),  # needs human (not applied)
    ])
    result = triage.run(workspace=ws, cfg=cfg, lang=lang, chat=chat)

    assert result["flagged"] == 3 and result["triaged"] == 2
    assert result["auto_accepted"] == 1 and result["applied"] == 1
    assert (ws.data / "triage_review.json").is_file()
    assert (ws.data / "triage_resolved.json").is_file()

    chapters = read_json(ws.data / "reconciled_chapters.json")
    primo = next(c for c in chapters if c["id"] == "p1_capitolo_primo")["text"]
    assert "sono comune e ben note" in primo
    # the rendered system the seam saw carries synthetic identity, not PLL.
    assert "Libro di Prova" in chat.calls[0][0]


def test_triage_with_no_needs_items_is_a_clean_noop(tmp_path, monkeypatch):
    monkeypatch.setattr(triage, "_BATCH_DELAY", 0)
    cfg = load_book("synthetic")
    lang = get_language_plugin(cfg.language_id)
    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()
    _seed(ws)
    # Only a majority_vote item — nothing needs triage, so no chat is built (None is fine).
    (ws.data / "flagged_segments.json").write_text(
        '[{"chapter": "prefazione", "paragraph": 0, "chosen": "breve", '
        '"resolution_method": "majority_vote"}]', encoding="utf-8"
    )
    result = triage.run(workspace=ws, cfg=cfg, lang=lang, chat=None)
    assert result == {"flagged": 1, "triaged": 0, "auto_accepted": 0, "applied": 0}


def test_triage_without_flagged_segments_is_typed_missing_input(tmp_path):
    from engine.errors import MissingInputError

    cfg = load_book("synthetic")
    lang = get_language_plugin(cfg.language_id)
    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()
    with pytest.raises(MissingInputError) as ei:
        triage.run(workspace=ws, cfg=cfg, lang=lang, chat=_FakeChat([]))
    assert ei.value.exit_code == 3
    assert "flagged_segments.json" in str(ei.value)


# --- leakage: no PLL/Italian string in the synthetic render ------------------------------- #

def test_no_pll_string_leaks_under_synthetic_render():
    rendered = triage.render_system_prompt(load_book("synthetic"))
    for leaked in ("Per la libertà", "Crespi", "1913", "Italian", "à", "è", "ì", "ò", "ù", "é"):
        assert leaked not in rendered, f"PLL/Italian string {leaked!r} leaked from the template"
    for present in ("Libro di Prova", "Autore Sintetico", "1901", "Sintetico", "ñ"):
        assert present in rendered, f"synthetic fact {present!r} did not interpolate"


def test_real_book_render_carries_its_identity():
    # The positive control: the same template interpolates the real book's identity + language.
    rendered = triage.render_system_prompt(load_book("per_la_liberta"))
    assert "Per la libertà!" in rendered and "Cesare Crespi" in rendered
    assert "Italian" in rendered
