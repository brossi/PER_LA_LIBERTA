# Synthetic book — test fixtures

These are **hand-authored fixtures for a deliberately non-PLL book**, used to prove the engine
steps are config-driven and not hardcoded to *Per la Libertà!*'s structure (the separability
tier — see `engine/docs/port_discipline.md` §6). The "book" is three short Italian chapters
(`PREFAZIONE` + `Capitolo Primo` + `Capitolo Secondo`), nothing more. Consumed by
`tests/unit/test_validate_engine.py`, `test_reconcile_engine.py`, `test_adjudicate_engine.py`,
and `test_isolation.py`.

| File | Purpose |
|---|---|
| `clean.md` | Cleaned markdown — `validate`'s input (3 content units, not PLL's 58). |
| `reconciled_chapters.json` | `validate`'s word-count witness. |
| `copy1_raw.txt`, `copy2_raw.txt` | Two OCR "copies" for `reconcile` (identical here → deterministic, zero word-level disagreements; the flag branches are pinned by `test_reconcile_engine` property tests, not this fixture). |
| `copy3_raw.txt` | Third witness — `copy1` plus `⟨PAGE:N⟩` markers, so the 3-way path and `_strip_page_markers` run end-to-end. |
| `copy3_flash_page_map.json` | Copy-3 page map. **The two entries deliberately span `char_start: 0 … char_end: 100000`** — far wider than the ~1 KB text — purely so they overlap every chapter and exceed reconcile's 500-char low-content skip. This is a **mechanism** fixture: it exists to *exercise the page→chapter mapping branch* in `reconcile.run`, not to model realistic page geometry. Both pages overlap all chapters, so each chapter maps to `[1, 2]`. Do not read real pagination into it. |
| `review_flags.json` | `adjudicate`'s input — a few hyphen tokens covering the shapes (noise `##`, an `ner_candidate`, plain dehyphenation). Classifications in tests are driven by a *fake* oracle, so verdicts don't depend on the 13 MB Zingarelli asset. |

If you regenerate or extend these, keep them **small, Italian-but-not-PLL, and deterministic** —
their whole value is being a second fixture that differs from PLL on the axes a port generalizes
(structure, not language; see BR-002 for the still-missing non-Italian axis).
