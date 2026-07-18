# Structural close read — The Book of Household Management (Beeton, 1861)

## 0. Identification — work/author/date; source file + PG#; size; HOW SAMPLED (explicit).

- **Work / author / date.** *The Book of Household Management*, by Mrs. Isabella Beeton. Project Gutenberg eBook #10136 (release 2003, most recently updated 2024); the underlying printed work is the 1861 first book edition. Header block, lines 11–28:
  - L11 `Title: The Book of Household Management`
  - L13 `Author: Mrs. Beeton`
  - L51 `BY MRS. ISABELLA BEETON.`
- **Source file.** `/Users/ben_mpa/LLM/PER_LA_LIBERTA/engine/docs/structure_corpus/beeton_household_mgmt_10136.txt`
- **Size.** 3,115,955 bytes (3.1 MB); **66,953 lines** (`wc -l`).
- **PG envelope.** START marker L28 `*** START OF THE PROJECT GUTENBERG EBOOK ... ***`; END marker **L66603** `*** END OF THE PROJECT GUTENBERG EBOOK ... ***`. Everything after L66603 is PG license boilerplate.
- **HOW SAMPLED (explicit).** Did NOT read whole. Procedure: (1) `head -60` for the PG header/title block; (2) `grep -n '^CHAPTER'` → all 44 chapter offsets + count; (3) `grep -c` for each recipe field label (INGREDIENTS / Mode / Seasonable / Sufficient / Average cost / Time); (4) `grep -nE '^[0-9]+\.\s'` for the running-number designation, plus `sort -n` for its range; (5) targeted `Read` at: a chapter head (L4363), two complete recipe records (L7440–7464 ALMOND SOUP, L25322–25341 TO BAKE A HAM), a data table (L4706–4760 wages table), illustration captions (L5722, L7466), the front-matter ANALYTICAL INDEX (L245–289), and the file tail. Counts/formats below come from those commands, not memory.

## 1. Container hierarchy — named levels; depth; child counts; verbatim boundary examples.

The tree is **shallow (effective depth 2–3)**, NOT deeply recursive:

```
Book
├── Front matter      (Preface; Analytical Index)        — siblings
├── Chapter  I … XLIV (44 of them)                       — the one body container level
│   └── ordered list of NUMBERED UNITS + un-numbered blocks   (flat — no sub-chapter container)
│       ├── prose paragraph        (a numbered unit)
│       ├── RECIPE RECORD          (a numbered unit, field-bearing)   ← centerpiece
│       ├── recipe NAME header     (un-numbered caps line)
│       ├── data table             (un-numbered, layout-only)
│       ├── illustration / figure  (un-numbered [Illustration] block)
│       └── natural-history / anecdote note  (un-numbered indented prose)
└── Back matter        (PG license only — no editorial back matter)
```

- **Chapter level.** 44 chapters, `grep -c '^CHAPTER'` = **44**, `CHAPTER I.` (L4363) … `CHAPTER XLIV.` (L65828). Boundary, verbatim (L4363–4366):
  ```
  CHAPTER I.


  THE MISTRESS.
  ```
- **No recipe-as-container sub-level.** The recipe is NOT a child container under the chapter — it is one *type* of body block in the same flat ordered list as prose paragraphs, and crucially **shares the chapter's running number sequence** (see §2). A recipe boundary is just a caps NAME line followed by the next numbered unit. Verbatim recipe boundary inside Chapter on Soups (L7440–7442):
  ```
  ALMOND SOUP.

  110. INGREDIENTS.--4 lbs. of lean beef or veal, 1/2 a scrag of mutton, 1
  ```
- **Child counts.** ~1,300 recipe records book-wide (`^[0-9]+\. INGREDIENTS` = **1300**); 567 illustration blocks (`[Illustration` = **567**); plus an unbounded number of prose paragraphs sharing the same number line. Per-chapter counts vary widely (chapter offsets are 80–4000 lines apart).

## 2. Designation system — chapter numbers; recipe numbers; kinds; unique/parent-dependent.

Two designation systems, and the second is the load-bearing one:

1. **Chapter number** — Roman numeral, format `CHAPTER {ROMAN}.`: `CHAPTER I.` … `CHAPTER XLIV.`. Parent-dependent only in the trivial sense of ordinal position; unique within the book.

2. **Running paragraph/recipe number — a SINGLE continuous arabic sequence spanning the WHOLE book**, shared by *every* numbered unit regardless of type. This is the canonical handle.
   - Prose paragraphs carry it: `2. PURSUING THIS PICTURE …` (L4391), `3. EARLY RISING …` (L4401) — the very first unit prints as Roman `I.` (L4374) then arabic `2.` onward.
   - Recipes carry it from the *same* sequence: `110. INGREDIENTS.--…` (L7442), `810. INGREDIENTS.--…` (L25324), `811. INGREDIENTS.--…` (L25348).
   - It continues monotonically into the non-recipe back chapters: `2694. Humorists tell us …` (L65831, Chapter XLIV, legal memoranda).
   - **Unique across the entire book, NOT parent-dependent** — there is no "recipe 5 of chapter 12"; there is just "recipe/paragraph 110." Range observed: min `1`, recipe/section numbers climb through the 2600–2750 band by the final chapters.
   - **TRAP:** `^[0-9]+\.` is not always a designation. Line 63648 prints `4548. As we have already observed, measles are always characterized by …` — an anomalous value far above its neighbours (the surrounding medical paragraphs are in the ~2570s, e.g. `2578.` at L64006), i.e. an OCR/typesetting corruption of the running number, not a true 4548th unit.

**Kinds:** chapter (Roman, container) and unit-number (arabic, leaf — covers both prose paragraphs and recipe records identically). The unit-number is the citation primitive; the recipe "number" is not a separate namespace.

## 3. Descriptive titles — chapter titles; recipe names.

- **Chapter titles** = an all-caps descriptive line two blank lines below the `CHAPTER {roman}.` line. Verbatim samples:
  - L4366 `THE MISTRESS.`
  - L7293 `FRUIT AND VEGETABLE SOUPS.`
  - L14612 `SAUCES, PICKLES, GRAVIES, AND FORCEMEATS.`
  - L32994 (Ch XXIII region) `GENERAL OBSERVATIONS ON MILK, BUTTER, CHEESE, AND EGGS.`
  - **Title is OPTIONAL:** `CHAPTER XLIV.` (L65828) has NO descriptive title — it goes straight from the header to paragraph `2694.` (L65831). So a chapter title cannot be assumed present.
- **Recipe names** = a standalone all-caps line immediately *above* the numbered `INGREDIENTS` line; two surface forms: an imperative (`TO BAKE A HAM.` L25322, `TO BOIL A HAM.` L25344) or a noun phrase (`ALMOND SOUP.` L7440, `APPLE SOUP.` L7491). The name is descriptive display text; the number is the identity.

## 4. Body block vocabulary — THE CENTERPIECE.

The body is emphatically **NOT prose-only**. At least five block types coexist in one ordered list:

### (a) Prose paragraph (numbered)
`62. "THE DISTRIBUTION OF A KITCHEN," says Count Rumford … ` (L5699) — opening words small-capped, body running prose.

### (b) STRUCTURED RECIPE RECORD — a field-bearing unit (the centerpiece)

One **complete record, verbatim** — recipe **110, ALMOND SOUP** (L7440–7464), showing every field:

```
ALMOND SOUP.

110. INGREDIENTS.--4 lbs. of lean beef or veal, 1/2 a scrag of mutton, 1
oz. of vermicelli, 4 blades of mace, 6 cloves, 1/2 lb. of sweet almonds,
the yolks of 6 eggs, 1 gill of thick cream, rather more than 2 quarts of
water.

_Mode_.--Boil the beef, or veal, and the mutton, gently in water that
will cover them, till the gravy is very strong, and the meat very
tender; then strain off the gravy, and set it on the fire with the
specified quantities of vermicelli, mace, and cloves, to 2 quarts. Let
it boil till it has the flavour of the spices. Have ready the almonds,
blanched and pounded very fine; the yolks of the eggs boiled hard;
mixing the almonds, whilst pounding, with a little of the soup, lest the
latter should grow oily. Pound them till they are a mere pulp, and keep
adding to them, by degrees, a little soup until they are thoroughly
mixed together. Let the soup be cool when mixing, and do it perfectly
smooth. Strain it through a sieve, set it on the fire, stir frequently,
and serve hot. Just before taking it up, add the cream.

_Time_.--3 hours. _Average cost_ per quart, 2s. 3d.

_Seasonable_ all the year.

_Sufficient_ for 8 persons.
```

**Recipe field schema (labelled fields, verbatim label forms):**

| Field | Label form on the page | Role | Book-wide count |
|---|---|---|---|
| (name) | caps line above, e.g. `ALMOND SOUP.` | display title | — |
| (number) | `110.` leading the INGREDIENTS line | identity | ~1300 records |
| INGREDIENTS | `{n}. INGREDIENTS.--` | quantified item list | `INGREDIENTS` = **1309** |
| Mode | `_Mode_.--` (also plain `Mode.--`, L25326) | method prose | `_Mode_.--`/`Mode.--` = **1299** |
| Time | `_Time_.--` | duration attribute | (shares line with cost) |
| Average cost | `_Average cost_,` | money attribute | `Average cost` = **1044** |
| Seasonable | `_Seasonable_ …` | seasonality attribute | `Seasonable` = **1074** |
| Sufficient | `_Sufficient_ for N persons.` | yield attribute | `Sufficient` = **849** |

Notes that matter for a schema model:
- **Fields are OPTIONAL and order-stable but not all-present.** Recipe 810 (TO BAKE A HAM, L25322–25341) has INGREDIENTS / Mode / Time / Average cost / Seasonable but **no Sufficient**. The counts above confirm asymmetry: ~1300 INGREDIENTS vs 849 Sufficient vs 1044 Average cost. A record is a sparse field set, not a fixed tuple.
- **Two fields can share one physical line:** `_Time_.--3 hours. _Average cost_ per quart, 2s. 3d.` (L7460). So field extraction cannot be line-anchored; it must scan for the italic label tokens.
- **Label markup is the PG italic convention** (`_label_`), but plain forms also occur (`Mode.--` L25326, `INGREDIENTS.--` always plain after the number). Label detection must tolerate both `_X_` and `X`.
- **The record carries its own attributes:** cost (`2s. 3d.`), time (`3 hours`), seasonality (`all the year` / `from September to December`, L7503), yield (`for 8 persons`). These are per-block structured data, not chapter-level metadata.

### (c) DATA TABLE — whitespace-aligned columns, no markup

Verbatim fragment of the servants'-wages table (L4711–4725), introduced by numbered paragraph `21.` (L4706):

```
                      When not found in          When found in
                          Livery.                   Livery.

  The House Steward   From £10 to £80               --
  The Valet             "  25 to 50             From £20 to £30
  The Butler            "  25 to 50                 --
  The Cook              "  20 to 40                 --
  The Gardener          "  20 to 40                 --
  The Footman           "  20 to 40              "  15 to 25
  The Under Butler      "  15 to 30              "  15 to 25
  The Coachman              --                   "  20 to 35
  The Groom             "  15 to 30              "  12 to 20
  The Under Footman          --                  "  12 to 20
  The Page or Footboy   "  8 to 18               "  6 to  14
  The Stableboy         "  6 to 12                  --
```

The table is recognizable **only by space-aligned columns and ditto-marks (`"`)** — there is no `<table>`, no `TABLE` caption tag (`TABLE` as a literal token = 47 hits, almost all prose like "TABLE BEER", L10098). This is a pure layout artifact in the OCR/e-text.

### (d) CAPTIONED FIGURE / illustration

`[Illustration …]` blocks, 567 total, in three caption styles — verbatim:
- Bare: `[Illustration]` (L5689)
- Figure-numbered: `[Illustration: _Fig_. 1.]` (L5722), `[Illustration: _Fig_. 9. Modern.]` (L5910)
- Named subject caption: `[Illustration: ALMOND & BLOSSOM.]` (L7466), `[Illustration: BOILED HAM.]` (L25346)

The figure caption lives *inside* the bracket, not as a separate line.

### (e) Natural-history / anecdote note — un-numbered indented prose

After many recipes/illustrations sits a 4-space-indented prose block (no number, often a caps lead-in `SUBJECT.--`): e.g. `THE ALMOND-TREE.--This tree is indigenous to the northern parts of Asia and Africa …` (L7468), and the Lord-Bacon anecdote `HOG NOT BACON. ANECDOTE OF LORD BACON.--` (L25298). It is a distinct block type — neither a numbered unit nor a recipe field.

**Blocks carrying own attributes?** Yes, decisively — the recipe record carries cost / time / seasonality / yield as internal fields (see (b)). This is the witness's defining feature.

## 5. Matter (front/body/back) — siblings or special-cased?

- **Front matter:** `PREFACE.` (L77) then `ANALYTICAL INDEX.` (L245). The analytical index is placed at the **front** here (runs L245 → ~L4360, ending just before `CHAPTER I.` at L4363).
- **Body:** Chapters I–XLIV (L4363–end of editorial text).
- **Back matter:** none editorial — after the last chapter the file goes straight to the PG END marker (L66603) and license. There is no separate rear index or glossary; the analytical index does back-matter duty from the front.
- **Sibling vs special-cased:** they read naturally as **siblings of the chapter sequence** (Preface, Index, then Chapters), supporting hypothesis (e). But the index is functionally special — it is a navigation apparatus that *references* the body by number (see §6), so a model that treats it as just-another-sibling-block loses its cross-reference role.

## 6. Identity & cross-witness behavior — how a recipe is canonically referenced.

**By its running number — confirmed from the book's own apparatus.** The ANALYTICAL INDEX states its referencing rule verbatim (L247–248):

```
NOTE.--Where a "_p_" occurs before the number for reference, the
_page_, and not the paragraph, is to be sought.
```

i.e. **the default referent is the paragraph/recipe NUMBER**, and page is the marked exception. Index entries resolve to numbers, e.g. (L266, L285):

```
  Soup 110
...
Apple, the 111
```

`Soup 110` → recipe 110 (ALMOND SOUP, L7442); `Apple, the 111` → recipe 111 (APPLE SOUP, L7493). Ranges appear too: `Agreements 2705-7` (L251), `Apoplexy 2634-6` (L284).

Design read-through: this is **exactly the "designation = stable citation handle" hypothesis (b/c)**, but with a twist — here the number is *also* the most stable identity the book itself ships, more stable than position-path for a reader, because the index hard-codes it. Position-path (chapter-N → k-th block) is a fine *internal* identity, but the canonical *external* reference is the number. Name is the least stable handle (many "TO BOIL …" recipes share words). A designation-reader plugin (hypothesis c) is the right shape: it parses the leading `{n}.` token off a unit.

## 7. Authorship — single book-level or per-node?

**Single, book-level.** One author, `BY MRS. ISABELLA BEETON.` (L51); no per-chapter or per-recipe bylines, no contributor attribution on any block. (Beeton famously compiled/adapted from correspondents, but the *text as printed* asserts no per-node authorship.) So hypothesis (g) — per-node authorship — is **not exercised by this witness**; the model must *allow* it but this book would populate a single book-level author. This is a useful negative datapoint: the schema should default author at the book node and leave per-node author absent rather than required.

## 8. Extraction cues — markers; field-label vocabulary; traps.

**Cues (reliable):**
- Chapter: `^CHAPTER {ROMAN}\.$` (44 hits, exact).
- Chapter title: caps line ~2 lines below the chapter header — **but optional** (XLIV has none).
- Numbered unit: `^[0-9]+\.\s` at column 0 (prose paragraph OR recipe).
- Recipe record: a caps name line, then `^[0-9]+\. INGREDIENTS` (1300 hits) — INGREDIENTS is the most reliable recipe anchor.
- Recipe fields: italic-or-plain labels `_Mode_`/`Mode`, `_Time_`, `_Average cost_`, `_Seasonable_`, `_Sufficient_`, each typically followed by `.--` (em-dash) or a comma/space.
- Figure: `\[Illustration(: …)?\]` (567 hits).

**Traps:**
- **Field labels appear in prose.** `Mode`, `Time`, `Sufficient`, `Seasonable` occur as ordinary words: e.g. `4. Sufficiently remote from the principal apartments` (L5715) is prose, not a recipe `Sufficient` field. Label detection must require the field *position* (line-leading, post-record) + the `_label_`/`.--` punctuation frame, not the bare word. (This is why `grep -c Seasonable` = 1074 over-counts true fields, and why `^\s*Mode` under-counts at 10 — most real Mode fields are `_Mode_`.)
- **Tables are layout-only.** No table markup; reconstruction depends on preserved column whitespace and ditto marks (`"`). Any de-spacing/reflow destroys the table. OCR of multi-column tabular layout is the classic failure mode.
- **Illustration captions are inside the brackets**, sometimes empty (`[Illustration]`), sometimes `_Fig_. N.`, sometimes a subject — three sub-formats to parse.
- **Running number ≠ always a designation.** The anomalous `4548.` (L63648) shows a corrupted/implausible number; a parser must sanity-check monotonicity, not trust every `^\d+\.`.
- **First unit is Roman (`I.`) then arabic** — the numbering namespace mixes one Roman token at each chapter's first paragraph with arabic thereafter (`I.` L4374 vs `2.` L4391).

## 9. What this witness uniquely forces in the model.

1. **Typed non-prose body blocks with internal FIELDS.** The body cannot be an ordered list of *prose* blocks. A recipe is a body block whose payload is a **record / field-map** (`ingredients`, `mode`, `time`, `average_cost`, `seasonable`, `sufficient`), with fields **optional and sparsely present**. This is the strongest possible confirmation of hypothesis (d): the body-block vocabulary must be OPEN and the block payload polymorphic (prose string | field-record | table grid | figure-with-caption).
2. **A record schema as a first-class body block.** ~1,300 such records. If you model recipes as prose paragraphs, you lose: per-recipe cost/time/seasonality/yield as queryable data; the INGREDIENTS list as a list; and the ability to render the field structure. Everything downstream (search "recipes under 1s. average cost", "recipes seasonable in December") breaks.
3. **Heterogeneous children confirmed (hypothesis f).** One chapter holds prose paragraphs, recipe records, tables, figures, and indented notes in a single ordered sequence. Children are not homogeneous.
4. **Designation is a flat, book-wide, cross-type number (refines hypothesis b/c).** The identity hypothesis "position-path is canonical" holds internally, but the witness adds: the *citation* designation is a single continuous sequence that does **not** reset per chapter and is shared across block *types* (prose ↔ recipe ↔ medical note). A designation-reader plugin must read one global integer, independent of container path, and the book's own index proves this is the canonical external reference — so designation here is more than a display field; it is the index key.
5. **Front-loaded analytical index as a reference apparatus** — argues for treating index/TOC as a typed apparatus node that *holds references to* body nodes (by designation), not merely a sibling prose block.

**What breaks if body is modeled as prose-only:** recipe fields collapse into an undifferentiated paragraph; cost/time/yield/seasonality become unqueryable text; ingredient lists lose list structure; tables lose their grid; figure captions lose their figure binding. The entire value of *this* book — a structured reference cookbook — is destroyed.

## 10. Open questions / contradictions.

- **Contradiction to "recipe is a container level":** the recipe is NOT a sub-chapter container — it is a leaf body block sharing the chapter's flat number sequence. Depth is shallower than a "chapter › recipe-section › recipe" reading would assume.
- **Contradiction to "designation is merely a display/citation field":** the book's own analytical index keys on the number (L247–248), making the designation the **canonical external identity**, arguably more authoritative than position-path. Position-path remains the right *internal* identity, but the model must carry the number as an indexed, not cosmetic, field.
- **Hypothesis (g) per-node authorship — not exercised:** single book-level author only; the schema should permit per-node author but default it absent.
- **Field optionality:** is the field *order* invariant (INGREDIENTS → Mode → Time → Average cost → Seasonable → Sufficient) across all ~1,300 recipes, or only usually? Two records sampled both follow it but differ in which fields are present; not exhaustively verified. «unverified» — would need a scan of every record's label sequence to confirm order-invariance.
- **Table boundaries:** there is no machine marker delimiting where a table starts/ends — only whitespace. Robust table extraction from this e-text is heuristic; an authoritative source (original page images) would be needed to settle ambiguous column runs.
- **The `4548.` anomaly (L63648):** a single corrupted running number; how many other such corruptions exist was not counted — a designation parser needs a monotonicity guard regardless.
- **Chapter title optionality:** confirmed absent for XLIV; not audited for all 44 — a title-extraction step must treat the title as nullable.
