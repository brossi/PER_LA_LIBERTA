"""reconcile's contract/property + separability tiers (fast — no spaCy, no network).

The golden (``test_reconcile_golden``) proves the *whole* engine step reproduces live output on
PLL's frozen copies. These tests pin the *pieces* the golden exercises only incidentally:

  - **property** — each pure mechanic (``score_word`` ordering, ``align_paragraphs`` opcodes,
    the 2-way/3-way word reconcilers' majority + flag branches, near-dup, page-marker stripping,
    paragraph splitting) responds to its inputs as specified, including branches PLL's all-clean
    happy path never reaches;
  - **separability** — ``split_raw_chapters`` segments by the plugin's *structural markers*
    (PREFAZIONE / PARTE SECONDA / FINE / running head), not a baked PLL chapter count, and
    ``reconcile.run`` completes end-to-end on a synthetic non-PLL book;
  - **contract** — that synthetic run's ``reconciled_chapters.json`` satisfies ``validate``'s
    word-count input contract, closing the M2 inversion (a consumer shipped before its producer).

Determinism: ``_is_near_duplicate`` uses rapidfuzz, pinned by the lockfile; everything else is
SequenceMatcher / pure string work.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from engine.config.loader import load_book
from engine.errors import MissingInputError
from engine.lang.italian import ItalianLanguagePlugin
from engine.lang.registry import get_language_plugin
from engine.paths import BookWorkspace
from engine.steps import reconcile, validate

# The exact live score_word accent set (LanguageProfile.word_score_accents) — the one language
# seam threaded into the scorer. Pinned here so a profile edit that drops/adds an accent is a
# visible property change, not a silent golden shift.
ACCENTS = "àèìòùéÀÈÌÒÙ"

ENGINE_ROOT = Path(__file__).resolve().parents[2]
SYNTH_INPUTS = ENGINE_ROOT / "books" / "synthetic" / "inputs"
RECON_INPUTS = ("copy1_raw.txt", "copy2_raw.txt", "copy3_raw.txt", "copy3_flash_page_map.json")


# --- score_word: ordering + exact values (the OCR-confidence heuristic) ----------------- #

def test_score_word_exact_values_are_faithful_to_live():
    # Hand-computed against the live algorithm — pins each rule's contribution.
    assert reconcile.score_word("più", ACCENTS) == 7      # accent +5, clean +2
    assert reconcile.score_word("casa", ACCENTS) == 2     # clean +2 only
    assert reconcile.score_word("piii", ACCENTS) == -1    # "ii" -3, clean +2
    assert reconcile.score_word("voM", ACCENTS) == -2     # mid-word cap -4, clean +2
    assert reconcile.score_word("ca*sa", ACCENTS) == -15  # "*" -10, non-letter inner -5
    assert reconcile.score_word("(casa)", ACCENTS) == -13 # bracket -8, non-letter inner -5


def test_score_word_prefers_the_cleaner_witness():
    # The property the reconcilers rely on: a clean/accented form outranks its OCR-mangled twin.
    assert reconcile.score_word("più", ACCENTS) > reconcile.score_word("piii", ACCENTS)
    assert reconcile.score_word("casa", ACCENTS) > reconcile.score_word("ca*sa", ACCENTS)
    assert reconcile.score_word("libertà", ACCENTS) > reconcile.score_word("liberta", ACCENTS)


def test_score_word_accent_set_is_the_seam():
    # Under an accent set that omits ù, "più" loses its accent reward AND its clean-word bonus,
    # and ù now reads as a non-letter (−5) — the same string scores far lower, proving the set
    # drives the scorer. (The set is non-empty: an empty class is an invalid regex, and the
    # profile schema forbids it via minLength.)
    assert reconcile.score_word("più", "èé") < reconcile.score_word("più", ACCENTS)


# --- align_paragraphs: every SequenceMatcher opcode branch ------------------------------ #

def test_align_paragraphs_covers_equal_replace_insert_delete():
    # equal(alpha), delete(beta), replace(gamma→delta), insert(epsilon).
    paras1 = ["alpha uno", "beta due", "gamma tre"]
    paras2 = ["alpha uno", "delta quattro", "epsilon cinque"]
    aligned = reconcile.align_paragraphs(paras1, paras2)
    # alpha aligns; then beta/gamma vs delta/epsilon is a 2x2 replace → paired by position.
    assert aligned[0] == ("alpha uno", "alpha uno")
    assert ("gamma tre", None) not in aligned  # nothing is dropped silently
    # Every left and right paragraph appears exactly once across the alignment.
    lefts = [a for a, _ in aligned if a is not None]
    rights = [b for _, b in aligned if b is not None]
    assert lefts == paras1 and rights == paras2


def test_align_paragraphs_insert_and_delete_yield_none_pads():
    deleted = reconcile.align_paragraphs(["a b c", "x y z", "p q r"], ["a b c", "p q r"])
    assert (None, "x y z") not in deleted and ("x y z", None) in deleted

    inserted = reconcile.align_paragraphs(["a b c", "p q r"], ["a b c", "x y z", "p q r"])
    assert (None, "x y z") in inserted


# --- reconcile_words (2-way): merge + the score-tie flag branch ------------------------- #

def test_reconcile_words_2way_merges_and_flags_close_calls():
    merged, flagged = reconcile.reconcile_words(
        "la più bella casa", "la piii bella easa", "p1_ch01", 0, ACCENTS
    )
    assert merged == "la più bella casa"  # più beats piii (Δ8, no flag); casa beats easa (tie)
    assert len(flagged) == 1
    f = flagged[0]
    assert (f["word_copy1"], f["word_copy2"], f["chosen"]) == ("casa", "easa", "casa")
    assert f["resolution_method"] == "score_heuristic"
    assert f["chapter"] == "p1_ch01" and f["paragraph"] == 0


def test_reconcile_words_first_witness_spine_rejects_unmatched_second_extent():
    merged, _ = reconcile.reconcile_words(
        "una frase completa",
        "una frase completa testo estraneo aggiunto",
        "chapter",
        0,
        ACCENTS,
        first_witness_spine=True,
    )
    assert merged == "una frase completa"


# --- reconcile_words_3way: the four majority/score branches ----------------------------- #

def test_3way_unanimous_keeps_text_and_flags_nothing():
    merged, flagged = reconcile.reconcile_words_3way(
        "la casa bella", "la casa bella", "la casa bella", "c", 0, ACCENTS
    )
    assert merged == "la casa bella" and flagged == []


def test_3way_two_of_three_majority_auto_accepts():
    # copy2 == copy3 against a copy1 outlier → take the agreeing pair, no flag.
    merged, flagged = reconcile.reconcile_words_3way(
        "la xasa", "la casa", "la casa", "c", 0, ACCENTS
    )
    assert merged == "la casa" and flagged == []


def test_3way_copy1_copy3_agreement_keeps_copy1():
    merged, flagged = reconcile.reconcile_words_3way(
        "la casa", "la easa", "la casa", "c", 0, ACCENTS
    )
    assert merged == "la casa" and flagged == []


def test_3way_all_differ_scores_and_flags_with_context():
    merged, flagged = reconcile.reconcile_words_3way(
        "la xasa bella", "la yasa bella", "la zasa bella", "c", 2, ACCENTS
    )
    assert merged == "la xasa bella"  # all score 2 → first wins
    assert len(flagged) == 1
    f = flagged[0]
    assert f["resolution_method"] == "all_differ"
    assert (f["word_copy1"], f["word_copy2"], f["word_copy3"]) == ("xasa", "yasa", "zasa")
    assert f["context"] == "la xasa bella" and f["paragraph"] == 2


# --- _is_near_duplicate: short-circuit, identity, distinctness -------------------------- #

def test_is_near_duplicate_short_strings_are_always_dupes():
    assert reconcile._is_near_duplicate("breve", []) is True  # < 20 chars → skip


def test_is_near_duplicate_identical_and_distinct():
    a = "nelprimocapitolosiparladellalibertaedellagiustizia"
    assert reconcile._is_near_duplicate(a, [a]) is True
    b = "unafrasecompletamentediversasenzaalcunarelazionecolresto"
    assert reconcile._is_near_duplicate(b, [a]) is False


def test_is_near_duplicate_catches_a_window_merged_paragraph():
    # The concatenated-window branch (reconcile.py:126-134): a long paragraph one witness merged is
    # caught against several shorter prior norms that, concatenated, reconstruct it — even though no
    # single prior norm matches. If this branch silently breaks, a page-boundary dittography survives
    # into the text (false) or a real paragraph is dropped (false-positive) — both silent fidelity
    # errors. The per-inc checks above cannot fire here (norm is longer than every fragment and no
    # single fragment is similar), so only the window branch can return True.
    norm = "abcdefghij" * 22  # 220 chars (>= the 200-char window gate)
    fragments = [norm[:74], norm[74:148], norm[148:]]  # 3 contiguous pieces; concatenation == norm
    assert reconcile._is_near_duplicate(norm, fragments) is True
    # a genuinely distinct long paragraph against the same fragments is NOT a duplicate
    assert reconcile._is_near_duplicate("z" * 220, fragments) is False


# --- _strip_page_markers: removal + clean-offset → page map ----------------------------- #

def test_strip_page_markers_removes_and_maps():
    clean, page_breaks = reconcile._strip_page_markers("⟨PAGE:1⟩\nciao\n⟨PAGE:2⟩\nmondo")
    assert clean == "ciao\nmondo"
    assert page_breaks == {0: 1, 5: 2}  # "ciao\n" is 5 chars → page 2 begins at clean offset 5


# --- split_paragraphs: dehyphenation + blank-line separation ---------------------------- #

def test_split_paragraphs_heals_breaks_and_splits_on_blank_lines():
    text = "Questa è una\nfrase spez-\nzata in righe.\n\nSecondo paragrafo."
    assert reconcile.split_paragraphs(text) == [
        "Questa è una frase spezzata in righe.",
        "Secondo paragrafo.",
    ]


# --- _split_merged_chapters: recover a chapter Copy2 absorbed ---------------------------- #

def test_split_merged_chapters_recovers_an_absorbed_chapter():
    # Copy2 is missing p1_ch02; its content was merged into Copy2's p1_ch01. With Copy1's
    # boundaries as a guide, the host is split back at the paragraph break. (Golden-covered only
    # if PLL triggers it; pinned here so the recovery branch is never born untested.)
    alpha = ("alpha parola numero uno. " * 5).strip()
    beta = ("beta parola numero due. " * 5).strip()
    ch_map1 = {
        "p1_ch01": {"id": "p1_ch01", "title": "Capitolo Primo", "part": 1, "text": alpha},
        "p1_ch02": {"id": "p1_ch02", "title": "Capitolo Secondo", "part": 1, "text": beta},
    }
    ch_map2 = {  # Copy2 lacks p1_ch02; p1_ch01 holds both, joined by a blank line.
        "p1_ch01": {"id": "p1_ch01", "title": "Capitolo Primo", "part": 1,
                    "text": alpha + "\n\n" + beta},
    }

    reconcile._split_merged_chapters(ch_map1, ch_map2, sorted(ch_map1))

    assert set(ch_map2) == {"p1_ch01", "p1_ch02"}
    assert ch_map2["p1_ch01"]["text"] == alpha
    assert ch_map2["p1_ch02"]["text"] == beta
    assert ch_map2["p1_ch02"]["title"] == "Capitolo Secondo"  # title comes from Copy1


# --- separability: structural-marker segmentation (no PLL chapter count baked in) -------- #

_RAW_WITH_RUNNING_HEAD = (
    "PREFAZIONE\n"
    "testo della prefazione.\n"
    "Capitolo Primo\n"
    "testo del primo capitolo.\n"
    "FINE DELLA PRIMA PARTE\n"
    "PER LA LIBERTÀ!\n"
    "PARTE SECONDA\n"
    "Capitolo Secondo\n"
    "testo del secondo capitolo.\n"
)


def test_split_raw_chapters_follows_structural_markers_not_a_count():
    plugin = ItalianLanguagePlugin()
    chapters = plugin.split_raw_chapters(
        _RAW_WITH_RUNNING_HEAD, running_heads=("PER\\s+LA\\s+LIBERT[AÀ]!?",)
    )
    assert [c["id"] for c in chapters] == ["prefazione", "p1_ch01", "p2_ch02"]
    assert [c["part"] for c in chapters] == [0, 1, 2]  # PARTE SECONDA flipped the part
    # FINE (Italian, plugin-owned) and the running head (book-level, supplied) are both dropped.
    bodies = "\n".join(c["text"] for c in chapters)
    assert "FINE DELLA PRIMA PARTE" not in bodies
    assert "PER LA LIBERTÀ" not in bodies


def test_running_head_drop_is_book_config_not_plugin_baked():
    # The title is no longer hardcoded in the language plugin (BR-004): with no running_heads
    # supplied, "PER LA LIBERTÀ!" survives as content; it is dropped only when the book declares
    # it. The Italian structural words (PREFAZIONE/PARTE/FINE) are dropped either way.
    plugin = ItalianLanguagePlugin()
    bodies = "\n".join(c["text"] for c in plugin.split_raw_chapters(_RAW_WITH_RUNNING_HEAD))
    assert "PER LA LIBERTÀ" in bodies          # not plugin-baked → kept without book config
    assert "FINE DELLA PRIMA PARTE" not in bodies  # Italian structural word → still dropped


def test_declared_flat_sections_ignore_toc_repeats_and_trailing_index():
    cfg = load_book("ninnoli")
    spec = cfg.structure.raw_segmentation
    assert spec is not None

    body = "parole narrative sufficient per superare il limite minimo della sezione " * 2
    text = "\n".join(
        [
            "NINNOLI",
            "Storiella vecchia",
            "Era matto o aveva fame?",
            "Cavalleria assassina - Scellerata! - Quintino e Marco",
            "GIUSEPPE FRACCAROLI",
            "STORIELLA VECCHIA",
            "STORIELLA VECCHIA",  # duplicate opening / running title
            body + "uno",
            "12 NINNOLI",
            "Storiella vecchia 13",
            "ERA MATTO 0 AVEVA FAME?...",
            body + "due",
            "CAVALLERIA ASSASSINA",
            body + "tre",
            "SCELLERATA!...",
            body + "quattro",
            "QUINTINO E MARCO",
            body + "cinque",
            "INDICE",
            "pubblicità che non appartiene al quinto racconto",
        ]
    )

    chapters = reconcile.split_declared_raw_sections(
        text, spec, running_heads=cfg.structure.running_heads
    )

    assert [chapter["id"] for chapter in chapters] == [
        "storiella_vecchia",
        "era_matto_o_aveva_fame",
        "cavalleria_assassina",
        "scellerata",
        "quintino_e_marco",
    ]
    assert [chapter["title"] for chapter in chapters] == [
        section.title for section in spec.sections
    ]
    assert all(chapter["part"] == 0 for chapter in chapters)
    joined = "\n".join(chapter["text"] for chapter in chapters)
    assert "pubblicità" not in joined
    assert "NINNOLI" not in joined
    assert "Storiella vecchia 13" not in joined
    for sentinel in ("uno", "due", "tre", "quattro", "cinque"):
        assert joined.count(sentinel) == 1


def test_declared_flat_sections_fail_loud_on_missing_or_reordered_boundary():
    cfg = load_book("ninnoli")
    spec = cfg.structure.raw_segmentation
    text = "\n".join(
        [
            "GIUSEPPE FRACCAROLI",
            "STORIELLA VECCHIA",
            "testo abbastanza lungo " * 5,
            "CAVALLERIA ASSASSINA",  # expected Era matto first
            "testo abbastanza lungo " * 5,
        ]
    )

    with pytest.raises(MissingInputError, match="before expected"):
        reconcile.split_declared_raw_sections(
            text, spec, running_heads=cfg.structure.running_heads
        )


# --- separability: full reconcile.run on a synthetic, non-PLL book ---------------------- #

def _seed_synthetic(tmp_path: Path) -> BookWorkspace:
    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()
    for name in RECON_INPUTS:
        (ws.data / name).write_text(
            (SYNTH_INPUTS / name).read_text(encoding="utf-8"), encoding="utf-8"
        )
    return ws


def test_reconcile_runs_end_to_end_on_synthetic_book(tmp_path):
    cfg = load_book("synthetic")
    lang = get_language_plugin(cfg.language_id)
    ws = _seed_synthetic(tmp_path)

    summary = reconcile.run(workspace=ws, cfg=cfg, lang=lang)

    # 3 content units (prefazione + 2 chapters), not PLL's 58 — nothing assumes PLL's structure.
    assert summary["mode"] == "3-way"
    assert summary["chapters"] == 3

    chapters = json.loads((ws.data / reconcile.RECONCILED_FILE).read_text(encoding="utf-8"))
    # Output order is the live alphabetical id sort — "p1…" precedes "pr…", so prefazione is
    # last (faithful to reconcile.py's `sorted(all_ids)`), not a structural assumption.
    assert [c["id"] for c in chapters] == ["p1_ch01", "p1_ch02", "prefazione"]
    for c in chapters:
        assert isinstance(c["text"], str) and c["text"].strip()

    # The Copy-3 page map populated chapter_pages (the page→chapter mapping branch ran). The
    # synthetic page map uses two deliberately wide-spanning entries so they overlap every chapter
    # and clear the 500-char low-content skip — a *mechanism* fixture, not realistic geometry
    # (rationale: books/synthetic/inputs/README.md). Hence every chapter maps to [1, 2].
    pages = json.loads((ws.data / reconcile.CHAPTER_PAGES_FILE).read_text(encoding="utf-8"))
    assert pages, "expected the page map to map at least one chapter"
    for v in pages.values():
        assert v == sorted(set(v)) and all(isinstance(p, int) for p in v)


# --- 2-way mode: the --skip-ocr fallback (no Copy 3) -------------------------------------- #

def test_reconcile_two_way_mode_without_copy3(tmp_path):
    # PLL's golden and the separability fixture both carry a third witness, so this is the only
    # thing that exercises reconcile.run's 2-way orchestration branch (mode "2-way", the
    # ch1-and-ch2 path) — a real, documented --skip-ocr fallback. Also pins that chapter_pages is
    # not written without a page-bearing Copy 3.
    cfg = load_book("synthetic")
    lang = get_language_plugin(cfg.language_id)
    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()
    for name in ("copy1_raw.txt", "copy2_raw.txt"):  # deliberately no copy3
        (ws.data / name).write_text(
            (SYNTH_INPUTS / name).read_text(encoding="utf-8"), encoding="utf-8"
        )

    summary = reconcile.run(workspace=ws, cfg=cfg, lang=lang)

    assert summary["mode"] == "2-way"
    assert summary["chapters"] == 3
    chapters = json.loads((ws.data / reconcile.RECONCILED_FILE).read_text(encoding="utf-8"))
    assert [c["id"] for c in chapters] == ["p1_ch01", "p1_ch02", "prefazione"]
    assert not (ws.data / reconcile.CHAPTER_PAGES_FILE).exists()  # no Copy 3 → no page map


def test_reconcile_two_way_copy1_and_copy3_ignores_undeclared_stale_copy2(tmp_path):
    cfg = load_book("synthetic")
    cfg = replace(
        cfg,
        manifest=replace(
            cfg.manifest,
            sources=tuple(
                replace(source, role="comparison") if source.role == "copy2" else source
                for source in cfg.manifest.sources
            ),
        ),
    )
    lang = get_language_plugin(cfg.language_id)
    ws = _seed_synthetic(tmp_path)
    # _seed_synthetic includes a copy2_raw file. Once its manifest role is diagnostic, that stale
    # filename must not make it back into the voting set.
    summary = reconcile.run(workspace=ws, cfg=cfg, lang=lang)

    assert summary["mode"] == "2-way"
    source_chapters = {
        chapter["id"]: chapter["text"]
        for chapter in ItalianLanguagePlugin().split_raw_chapters(
            reconcile.collapse_spaces(
                ItalianLanguagePlugin().strip_boilerplate(
                    (ws.data / reconcile.COPY1_FILE).read_text(encoding="utf-8")
                )
            ),
            running_heads=cfg.structure.running_heads,
        )
    }
    chapters = json.loads((ws.data / reconcile.RECONCILED_FILE).read_text(encoding="utf-8"))
    # Copy 3 may correct words but cannot inject unmatched paragraph extent into Copy 1's spine.
    for chapter in chapters:
        assert len(chapter["text"]) <= len(source_chapters[chapter["id"]]) * 1.05
    flagged = json.loads((ws.data / reconcile.FLAGGED_FILE).read_text(encoding="utf-8"))
    assert all("word_copy2" not in item for item in flagged)
    assert all("word_copy3" in item for item in flagged)


# --- contract: reconcile output satisfies validate's word-count input (closes inversion) - #

def test_reconcile_output_satisfies_validate_word_count_contract(tmp_path):
    cfg = load_book("synthetic")
    lang = get_language_plugin(cfg.language_id)
    ws = _seed_synthetic(tmp_path)
    reconcile.run(workspace=ws, cfg=cfg, lang=lang)

    # validate's word_count_preservation reads reconciled_chapters.json as its denominator.
    # Feeding it the engine-produced file proves the producer→consumer contract holds on real
    # engine output — the inversion M2 left open (validate shipped before reconcile existed).
    reconciled = ws.data / reconcile.RECONCILED_FILE
    cleaned = "\n\n".join(
        c["text"] for c in json.loads(reconciled.read_text(encoding="utf-8"))
    )
    result = validate.check_word_count_preservation(
        cleaned, reconciled, retention_min=cfg.structure.retention_min
    )
    assert result["passed"] is True  # cleaned == reconciled text → 100% retention
    assert result["retention_pct"] == 100.0
