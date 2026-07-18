# Structure-study reference corpus

Verified full-text copies of real document structures used to design the engine's
book-agnostic **document-structure** model on the `spike/document-structure` branch.

Every work here is an **equal structural witness**. There is no privileged reference,
no "core vs. extra," no baseline set — privileging any subset would re-introduce the
single-book bias (PLL-as-spec) this branch exists to escape. The model must
accommodate the **union** of the structures these works exhibit; each contributes
whatever distinctive structural features it has, on equal footing. They were gathered
to span structural variety deliberately: numbered, named, and dated divisions; flat,
deep, and recursive hierarchies; prose, verse, tabular, and dramatic bodies; linear
and lookup-keyed identity; single- and multi-author collections.

The raw `*.txt` / `*.tex` / `*.pdf` files here are **gitignored** (large,
public-domain, regenerable from the URLs below); only this manifest and `.gitignore`
are tracked. Texts are Project Gutenberg transcriptions (public domain). PLL itself
is the live repository text and is not duplicated here.

## Works

| Work | Edition | Lang | Source | Local file | Bytes |
|------|---------|------|--------|-----------|------:|
| The Atlantic Monthly, Vol. 18 No. 106 | Aug 1866 | EN | PG 23040 | `atlantic_monthly_1866_no106_23040.txt` | 513,846 |
| The Book of Household Management | Beeton, 1861 | EN | PG 10136 | `beeton_household_mgmt_10136.txt` | 3,115,955 |
| The Diary of Samuel Pepys — Complete | Wheatley, 1893 | EN | PG 4200 | `pepys_diary_complete_4200.txt` | 6,800,848 |
| La Divina Commedia | Dante, complete (3 cantiche) | IT | PG 1012 | `dante_commedia_it_1012.txt` | 626,095 |
| The Divine Comedy | Dante, Cary translation | EN | PG 8800 | `dante_commedia_en_cary_8800.txt` | 656,728 |
| Encyclopædia Britannica 1911 ("England"–"English Finance") | 11th ed. | EN | PG 32940 | `britannica_1911_england_32940.txt` | 623,083 |
| Hamlet | Shakespeare | EN | PG 1524 | `shakespeare_hamlet_1524.txt` | 206,895 |
| The Kybalion | Three Initiates, 1908 | EN | PG 14209 | `kybalion_14209.txt` | 223,890 |
| On the Origin of Species | Darwin, 1st ed. 1859 | EN | PG 1228 | `darwin_origin_1859.txt` | 970,612 |
| The Origin of Species | Darwin, 6th ed. 1872 | EN | PG 2009 | `darwin_origin_1872.txt` | 1,303,005 |
| Per la Libertà! | Crespi, 1913 (PLL — live book) | IT | live repo | `output/italian_clean.md`, `output/english_translation.md` | — |
| Tractatus Logico-Philosophicus | Wittgenstein, Ogden 1922 | EN | PG 5740 | `wittgenstein_tractatus_5740.tex` | 380,896 |

## Structure each exhibits

- **Atlantic Monthly** — Issue › Article; heterogeneous content under one issue (essays, serialized fiction, poems, reviews); TOC-as-index; early issues run unsigned.
- **Beeton, Household Management** — structured records (recipes as field-bearing units) + data tables + captioned figures: non-prose body blocks.
- **Dante, Commedia** (IT original + Cary EN) — book › *named* cantica (Inferno/Purgatorio/Paradiso) › Roman-numeral canto › tercet › line; verse is the primary body; asymmetric child counts (34/33/33); citation by cantica·canto·line.
- **Encyclopædia Britannica 1911** — alphabetical entries keyed by *headword string* (reached by lookup, not linear reading); cross-references form a graph; *signed* per-article authorship; long articles carry sub-sections.
- **Hamlet** — Act › Scene; *speaker-attributed* dialogue; stage directions; a dramatis personae roster; a play-within-a-play (recursive containment).
- **The Kybalion** — flat chapters, no parts; a Roman-numeral designation *separate from* the descriptive title; set-off, attributed aphorism blocks.
- **Darwin, Origin of Species** (1859 + 1872) — flat chapters › italic §sub-sections; both a number designation *and* a descriptive title; authorial footnotes; glossary + index back matter; the skeleton *differs between editions* (a chapter inserted → renumbering).
- **Per la Libertà! (PLL)** — book › part › chapter; the chapter designation is a spelled-out Italian *ordinal word* ("Capitolo Primo"); prose body; set-off verse.
- **Pepys, Diary** — book › volume › year › month › *dated day-entry*; the designation is a *date*, often partial ("2nd." resolving only against its month/year heading); entries have no titles; Old/New-Style calendar irregularity.
- **Tractatus** — arbitrary-depth *recursive dotted-decimal* numbering (1, 1.1, 1.11, 2, 2.01 …); stored as TeX source (PG #5740 ships only TeX/PDF; the LaTeX exposes the numbering directly).

## Regenerating a copy

```bash
# Modern Gutenberg ebooks (plain text, UTF-8):
curl -sL -o <local-file> https://www.gutenberg.org/cache/epub/<PG#>/pg<PG#>.txt

# Older ebooks with legacy filenames (e.g. Tractatus #5740, which has no cache/epub
# plain text) — use the ebook landing page and take the offered format:
#   https://www.gutenberg.org/ebooks/5740   (TeX / PDF)
```

Downloaded 2026-06-23. Editions are pinned by Project Gutenberg number; a future
re-download may differ in whitespace/boilerplate, not in structure. Standalone
single-cantica Italian Dante editions (#1010 Purgatorio, #1011 Paradiso) were pruned
as redundant with the complete #1012.
