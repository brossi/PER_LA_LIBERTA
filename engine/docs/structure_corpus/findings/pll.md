# Structural close read — Per la Libertà! (Crespi 1913)

> Evidence base for `ENGINE_STRUCTURE_PLAN.md`. Every line anchor below was produced
> by `grep -n`, `grep -c`, `awk`, or a direct `Read` of the two source files *this
> session*; counts are reported from the commands, not from memory. This is the **live
> target** witness — the book the pipeline already ships — so its tracking pathologies
> are not hypothetical; they are in production.

## 0. Identification

- **Work:** *Per la Libertà! (Dalle mie conversazioni col Conte Carlo di Rudio, complice di Felice Orsini)* — EN: *For Freedom!*
- **Author:** Cesare Crespi, 1913 (Canessa Printing Co., San Francisco). `# Per la Libertà!` (IT line 1) / `**Cesare Crespi** (1913)` (IT line 5).
- **Edition / form read:** the pipeline's *cleaned/extracted* markdown output, **not** raw OCR. Two paired witnesses:
  - `/Users/ben_mpa/LLM/PER_LA_LIBERTA/output/italian_clean.md` — 4281 lines / 779 752 bytes
  - `/Users/ben_mpa/LLM/PER_LA_LIBERTA/output/english_translation.md` — 4427 lines / 813 378 bytes
  The original recognition read three OCR witnesses of the 1913 LOC/Harvard scans, keying chapter detection on **Italian-ordinal heading words** (`Capitolo` + spelled-out ordinal); what we read here is the post-recognition markdown surface, so designation noise visible below is *survivor* noise, already once-cleaned.
- **How sampled:** full header enumeration (`grep -n '^#'`) on both files; level counts (`grep -c '^## '`, `'^### '`); per-part chapter counts by `awk` split at the Parte-Seconda line; structural-marker greps (lists/blockquotes, footnote/sentinel/`---`, `<!-- pages: -->`); and direct reads of the title+preface+ch1 head (IT 1–140), both part-2 boundaries (IT 2024–2045 / EN 2110–2134), the two anomalous EN headings (EN 3113–3124), and both tails.

## 1. Container hierarchy

**Named levels (canonical, from IT):** `book(H1) › matter-group(H2) › chapter(H3) › block`.
Max grouping depth = **3** header levels above the block stream. The tree is **ragged**, not uniform, on two axes:

1. **Asymmetric child counts.** The two body parts are lopsided:
   - `## Parte Prima` (IT line 34) holds **24** chapters; `## Parte Seconda` (IT line 2036) holds **33**. Confirmed by `awk` split at line 2036: 24 before / 33 after. EN identical: 24 before line 2117 / 33 after. **Total 57 `###` (`grep -c` = 57 in both files).** The 24 / 33 / 57 manifest hypothesis is **CONFIRMED exactly.**
2. **Heterogeneous siblings at H2.** The three `## ` nodes are *not* the same kind: `## Prefazione` (front-matter prose, signed) sits at the **same markup level** as `## Parte Prima` / `## Parte Seconda` (chapter-bearing groups). One H2 carries paragraphs directly; the other two carry only `###` children. Confirms hypothesis (f): a level's siblings are heterogeneous.

**Verbatim boundary example per level:**
- book → IT line 1 `# Per la Libertà!`
- matter-group → IT line 34 `## Parte Prima`; IT line 2036 `## Parte Seconda`; IT line 9 `## Prefazione`
- chapter → IT line 36 `### Capitolo Primo`; IT line 2038 `### Capitolo Primo` (**the same designation, second occurrence** — see §2)
- block → IT line 40 `Los Angeles, una splendida mattina d'estate.` (first body paragraph of ch1)

Hypothesis (a) "recursive, variable depth" is **only weakly** supported here: the *container* nesting is a fixed 3-level skeleton, not arbitrary recursion. Recursion appears instead **inside blocks** — embedded quoted documents (a Mazzini letter, a Dante tercet, see §4/§7) are sub-documents with their own author and language nested in a paragraph. So the recursion this witness demands is *block-level embedding*, not deeper container nesting.

## 2. Designation system

- **Kind:** spelled-out **Italian ordinal word**, prefixed by the role noun: `Capitolo Primo … Capitolo Trentesimo Terzo`. Parts use the same scheme: `Parte Prima`, `Parte Seconda`. This is the corpus's distinctive designation kind (cf. Roman in Kybalion, date in Pepys, dotted-decimal in Tractatus).
- **Only-within-parent unique, NOT global.** `### Capitolo Primo` occurs at IT line 36 **and** IT line 2038; the ordinal sequence **resets to 1** at each part. A designation alone (`Capitolo Primo`) cannot name a node — it needs its parent part. Refutes any "designation = global key" reading.
- **Self-contained vs parent-dependent:** parent-dependent for uniqueness (above), and *individually* self-contained only in that the word names its own ordinal.
- **Does it encode position?** It encodes an **ordinal**, but the ordinal is **decorative, not load-bearing, and demonstrably unreliable as a key:**
  - **Same ordinal, two surface spellings across parts.** 17th: `Capitolo Decimo Settimo` (IT 1284, Part 1, spaced) vs `Capitolo Decimosettimo` (IT 3000, Part 2, fused). 18th: `Capitolo Decimo Ottavo` (IT 1369) vs `Capitolo Decimottavo` (IT 3067, elided). The inconsistency runs both ways — Part 1 *fuses* the 23rd/24th (`Ventesimoterzo` IT 1822, `Ventesimoquarto` IT 1939) while Part 2 *spaces* them (`Ventesimo Terzo` IT 3520, `Ventesimo Quarto` IT 3589).
  - **Mistranslated in EN.** Exactly two EN headings keep the raw Italian ordinal: `### Chapter Decimosettimo` (EN 3117) and `### Chapter Decimottavo` (EN 3184), where every other EN heading reads `Chapter One … Chapter Thirty-Three`. By **position** these are unambiguously Part 2 / ch 17 and ch 18; only the designation string is broken.

  This is the single cleanest demonstration in the corpus that **designation text is an unreliable identity** — it varies by part, by transcription, and by translation, while the node's *position* (P2 § 17) is invariant. Strongly confirms hypothesis (b): position-path is canonical, designation is a read-only field.

## 3. Descriptive titles

**Absent at chapter level.** No `### Capitolo Primo — <title>` form anywhere; the `###` line carries *only* the designation. So at chapter level designation and title are not "fused" — the title node simply **does not exist**; the bare ordinal is the whole head.

The one **descriptive** head is the work title itself, and there designation/title behavior is distinctive: the H1 is the title (`# Per la Libertà!`), with the **subtitle as a separate italic block** below it (`*Dalle mie conversazioni col Conte Carlo di Rudio…*`, IT line 3) and author/date as a separate bold block (`**Cesare Crespi** (1913)`, IT line 5). So the title-page node fans into title / subtitle / byline as **three sibling blocks**, not one fused string. The matter-group H2s (`Prefazione`, `Parte Prima/Seconda`) are role-labels, not descriptive titles.

## 4. Body block vocabulary (open, observed at the markdown surface)

The block grammar is deliberately thin and **open** (confirms (d)). `grep` for markdown lists/blockquotes (`^\s*(>|[-*+] |\d+\. )`) returns **0** in both files — there is **no** list or quote markup; everything below is either a header, a prose paragraph, or an inline-styled run. Observed types:

1. **prose paragraph** (default, the overwhelming majority) — IT line 40.
2. **page-provenance marker** — HTML comment carrying a page-range attribute: IT line 38 `<!-- pages:8-14 -->`. **One per chapter+preface in IT (`grep -c` = 58).** Carries its own attribute (the page span) → confirms "blocks carrying own attributes."
3. **thematic break** `---` — IT line 7 (after title page) and IT line 2034 (between Part 1 and Part 2).
4. **inline-styled span** — `*italic*` (subtitle IT 3; EN footnotes; EN-side embedded Italian letter) and `**bold**` (byline IT 5). NB: **verse/italic emphasis inside running prose is NOT represented at this surface** — the 1913 italics/small-caps/verse were flattened by OCR and are restored *only later*, at typeset, from the `data/typography.json` sidecar. So a parser of *this* file sees no verse block type at all (see trap §8).
5. **footnote** — a prose paragraph led by a `(1)` marker, parked at the **end of its chapter** (not page-anchored): IT 1120, 1281, 1936, 2029. Example IT line 2029 `(1) È il nome assunto da Felice Orsini per deludere la Polizia Svizzera.` Two sub-behaviors:
   - One footnote is a **flattened list of 15 names** (IT 1281 / EN 1343) — semantically a list, surfaced as one comma-joined paragraph (consistent with the 0-list-markup finding).
   - EN renders footnotes **in italic** (`*(1) …*`, EN 1343/2017/2112) while IT leaves them plain — a per-node style attribute that **differs across witnesses**.
6. **part-end / book-end sentinel** — plain prose, **not** a header: IT 2031 `FINE DELLA PRIMA PARTE`, IT 4280 `FINE`; EN 2114 `END OF PART ONE`, EN 4427 `THE END`. These mark container boundaries *in band as text*.
7. **embedded quoted document** — a sub-document with its own authorship/language, nested in the block stream. The book's final movement quotes Mazzini's letter of recommendation, signed `Giuseppe Mazzini`; in **EN it appears bilingually** — the untranslated Italian original (italic block) immediately followed by the English (EN tail, the `*"Mi fo lecito…"*` block then `"I take the liberty…"`). Also the Dante tercet fragment in the preface (IT 17 / EN 23, see §8).
8. **(EN-only) translator's note** — `*Translated from the Italian*` (EN line 7), with no IT counterpart: a body-of-the-title-page block that exists in one witness only.

## 5. Matter (front / body / back)

- **Front matter:** the **title page** (H1 + subtitle + byline + `---`, IT 1–7) is the *root*, not a sibling — it owns the whole tree. The **Prefazione** (`## Prefazione`, IT 9), signed `Cesare Crespi.` (IT 31), is a **sibling H2 of the two body parts** at the same markup level. So the preface confirms hypothesis (e): front matter is a same-level sibling carrying a role label, **not** a special-cased node — the only thing distinguishing it from `Parte Prima` is the role word `Prefazione` vs `Parte`. A pure position/role model handles this with one `role` tag and no schema branch.
- **Back matter:** **none as a separate container.** The book simply ends inside the last chapter (Part 2 / ch 33) at IT 4280 `FINE` / EN 4427 `THE END`. Footnotes are *not* collected into an end-notes section — they live at the foot of their own chapter (§4.5). No glossary, index, or appendix. So this witness shows front-matter-as-sibling but **no** back-matter node at all.

## 6. Identity & cross-witness behavior

**The tracking anti-pattern, concretely (the reason this witness exists).** A single chapter node is handled by **three competing id schemes** in the live pipeline, all derived from the unstable designation rather than from position:

| Scheme | Form for P2 ch18 | Built from |
|--------|------------------|-----------|
| short ordinal-counter | `p2_ch18` | part + integer index |
| long designation-slug | `p2_capitolo_decimottavo` | the *Italian ordinal words*, underscored |
| HTML-anchor slug | a hyphenated `_slug()` of the heading | the rendered heading text |

Because scheme 2 is built from the designation **string**, the §2 spelling drift propagates straight into the id: Part 1's 18th becomes `p1_capitolo_decimo_ottavo` (spaced→underscored) while Part 2's 18th becomes `p2_capitolo_decimottavo` (elided) — **the same logical "chapter 18" gets structurally different ids in the two parts**, and the EN side would additionally inherit `Decimosettimo`/`Decimottavo` from the mistranslated headings (EN 3117/3184). Three handles for one node, none of them stable, *all* downstream of designation. This is exactly what hypothesis (b) fixes: make identity `body/2/17` (part-index / chapter-index, position-path) and demote every one of `Capitolo Decimottavo` / `Chapter Eighteen` / `p2_ch18` to a read-only display/citation field.

**IT-vs-EN structural diff (translation-invariance test):**

| Signal | IT | EN | Invariant? |
|--------|----|----|-----------|
| chapter count / part split | 57 (24+33) | 57 (24+33) | **invariant** |
| chapter *order* | 1…33 | 1…33 | **invariant** |
| **part container header** | `## Parte Prima` / `## Parte Seconda` (IT 34 / 2036) | **absent** — `grep -c '^## '` = **1** (only `## Preface`); no `## Part …` at all | **SHIFTS** |
| part-divider `---` | present (IT 2034) | **absent** | **SHIFTS** |
| preface header | one clean `## Prefazione` (IT 9) | **defective**: `## Preface` (EN 11) *and* a stray `# Preface` H1 (EN 17) | **SHIFTS** |
| page-provenance markers | 58 (one each) | **92** — duplicated 2–3× (e.g. EN 13+15; EN 44+46+48) | **SHIFTS** |
| chapter designations | ordinal words, 2 spellings | word-ordinals + 2 untranslated Italian (EN 3117/3184) | **SHIFTS** |

**What it proves about identity:** the *positional skeleton* (how many chapters, in what order, grouped into two parts) is **perfectly translation-invariant**, while **every surface marker that designation/header-based extraction relies on is degraded or absent in one witness**. The strongest case: in EN the **part-level container is invisible to a header parser** — the only cues that Part 2 began are the prose sentinel `END OF PART ONE` (EN 2114) and the chapter number resetting from `Twenty-Four` to `One` (EN 2117). A naive header-driven extractor run on the EN file would recover a **flat 57-chapter book and lose the part grouping entirely.** Position-path identity survives this; designation/header identity does not. This is the decisive evidence for (b) and (c).

## 7. Authorship

**Layered / per-node — not a single book-level author.** Book-level attribution is Cesare Crespi (byline IT 5; preface signed IT 31 / EN 39). But the work is structurally a *frame*: Crespi narrates, then from Part 2 ch1 the **first-person voice is di Rudio's** ("Come introduzione a questa seconda parte…", IT 2042) — so the narrating author of a container differs from the book author. Embedded documents carry their **own** authorship: Mazzini's letter is signed `Giuseppe Mazzini` (IT tail); the preface's set-off line is Dante (Inferno V). And EN adds a **translator** node (`*Translated from the Italian*`, EN 7) that has no IT counterpart. So authorship is genuinely a **per-node attribute** (book → frame-narrator → embedded-document author → translator), confirming hypothesis (g). A book-level-only author field cannot represent the Mazzini letter or the translator.

## 8. Extraction cues (and traps), quoted

**Boundary cues a parser keys on in *this* surface:**
- book: a single leading `# ` (IT 1).
- matter-group: `## ` + role word — `## Prefazione`, `## Parte Prima`, `## Parte Seconda`. The *original* OCR recognizer keyed on Italian heading keywords (`Capitolo`/`Parte` + ordinal word), not on `#`.
- chapter: `### Capitolo <ordinal-word>` (IT) / `### Chapter <ordinal-word>` (EN).
- page provenance: `<!-- pages:N-M -->` HTML comment.
- container end: prose sentinels `FINE DELLA PRIMA PARTE` / `FINE` (IT) and `END OF PART ONE` / `THE END` (EN).

**Traps (each a reason recognition must be separable from tracking):**
1. **Missing part headers in EN.** No `## Part …`; part boundary survives only as the prose sentinel `END OF PART ONE` (EN 2114) + chapter renumber. A header parser silently flattens the tree.
2. **Stray duplicate H1 in EN front matter.** `## Preface` (EN 11) immediately followed by `# Preface` (EN 17) — an H1 at the *same level as the book title* (`# For Freedom!`, EN 1). A level-aware parser thinks a new top-level document began mid-preface.
3. **Duplicated provenance markers in EN.** 92 vs 58; e.g. ch1 carries the marker three times (EN 44/46/48). Anything that maps markers → pages 1:1 double-counts.
4. **Designation spelling drift** (§2): `Decimo Ottavo` vs `Decimottavo` — string-equality chapter matching across parts fails.
5. **Untranslated headings** `Chapter Decimosettimo/Decimottavo` (EN 3117/3184) — language-keyed heading detection mis-fires.
6. **Footnotes and sentinels are bare prose**, not markup (§4.5/§4.6). A "every non-header line is body prose" parser absorbs `(1) È il nome…` and `FINE DELLA PRIMA PARTE` into the preceding paragraph.
7. **Verse fragment split mid-sentence.** The preface's Dante quote is broken across a paragraph boundary in IT — line 15 ends `Come un Minosse che` and line 17 resumes `"Giudica e manda secondo che avvinghia"` — and rejoined as a clean standalone block only in EN (EN 23). The same logical verse line is one block in one witness and two in the other.

## 9. What this witness uniquely forces in the model

1. **Position-path identity is mandatory, not preferred.** This is the live target and it already exhibits *three* designation-derived ids for one node, two of which drift with the §2 ordinal spelling. Any model that lets designation leak into identity reproduces the bug it is meant to retire. Identity must be `role-index/role-index` (`body[1]/chapter[17]`); `Capitolo Decimottavo` / `Chapter Eighteen` / `p2_ch18` are all *display* fields hung off that path.
2. **Designation reading must be a plugin** (confirms (c)): the ordinal-word reader is Italian-specific (`Primo…Trentesimo Terzo`), tolerant of spaced/fused/elided variants, and must degrade gracefully when the string is mistranslated or absent. A hard-coded reader breaks on the EN file alone.
3. **A `role` tag on a same-level node** handles front matter with no schema branch: `Prefazione` and `Parte Prima` differ only by role. (e) confirmed.
4. **Per-node authorship + per-node language** are required (g): the Mazzini letter, the Dante line, the bilingual embedded quote, and the EN-only translator note cannot be expressed by book-level author/language fields.
5. **Extraction must tolerate witness-specific structural loss.** The EN witness *lacks the part container in its markup.* If tracking depends on extraction recovering identical trees from both witnesses, it breaks here. Identity must be assignable from the **invariant positional skeleton** (count + order + grouping), which both witnesses agree on, even when one witness's surface markers are gone.

**What breaks if ignored:** a header/designation-driven design produces a flat 57-chapter EN tree (part grouping lost), double-counts EN page citations, fails to align IT↔EN chapter 17/18 (string mismatch), and re-creates the three-id tangle this branch exists to remove.

## 10. Open questions / contradictions

- **Hypothesis (a) only partially holds.** Container nesting is a *fixed* 3-level skeleton (book › matter-group › chapter), not arbitrary-depth recursion. The recursion this book actually needs is **block-level embedding** (quoted sub-documents with their own author/language inside a paragraph), not deeper containers. The model should not over-fit "variable-depth container tree" on this witness; it should ensure a *block* can contain a sub-document.
- **Footnote ↔ reference linkage is unrepresented.** Footnotes sit at chapter end as `(1) …`, but the in-text `(1)` call-site was not located in this surface read; whether the extraction preserves the anchor pair is an open question for a parser (the markers may have been flattened).
- **Verse has no surface representation.** At the `.md` layer verse/italic/small-caps are *gone* (flattened by OCR, restored only at typeset from `data/typography.json`). So this witness, read alone, *understates* its own block vocabulary — the extraction surface and the rendered edition disagree on what block types exist. A model built only from `output/*.md` would miss verse entirely; the typography sidecar is a separate, slug-keyed identity scheme that is itself a *fourth* handle on the node and re-raises the identity-vs-designation problem at render time.
- **EN front-matter defect needs a human ruling** on whether `## Preface` + stray `# Preface` (EN 11/17) is a one-off transcription artifact or a systematic export bug; it changes whether a parser should hard-reject duplicate top-level heads or coalesce them.
- **Asymmetric parts are real, not noise.** 24 vs 33 is the actual structure (confirmed both witnesses), so any uniform-children assumption is wrong for this book; child counts must be free.
