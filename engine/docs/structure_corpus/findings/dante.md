# Structural close read — La Divina Commedia (Dante; IT #1012 + Cary EN #8800)

> Specimen files: `engine/docs/structure_corpus/dante_commedia_it_1012.txt` (complete
> Italian, all three cantiche) and `engine/docs/structure_corpus/dante_commedia_en_cary_8800.txt`
> (H. F. Cary blank-verse English). All line anchors below are from `grep -n` / `sed -n` /
> `awk` over these two files in this session. Counts are reported from commands, not memory.
> This is a **paired witness** read: the cross-witness diff (§6) is the point.

## 0. Identification

- **Work**: *La Divina Commedia* / *The Divine Comedy* — the three-cantica poem (Inferno, Purgatorio, Paradiso).
- **Author**: Dante Alighieri (both files: `Author: Dante Alighieri`, IT L13 / EN L13).
- **IT edition**: Project Gutenberg eBook **#1012** (`Title: La Divina Commedia di Dante`, L11; release 1997-08-01, updated 2024-10-29). **20,004 lines / 626,095 bytes** (`wc`). Language: Italian. Original terza rima.
- **EN edition**: Project Gutenberg eBook **#8800** (`Title: The divine comedy`, L11), **Translator: Henry Francis Cary** (L17), **Illustrator: Gustave Doré** (L15). **16,000 lines / 656,728 bytes**. Cary's translation is **Miltonic blank verse**, not terza rima — this is the load-bearing fact for §6.
- **Work proper — IT**: PG START `*** START OF THE PROJECT GUTENBERG EBOOK LA DIVINA COMMEDIA DI DANTE ***` (**L28**); title block `LA DIVINA COMMEDIA / di Dante Alighieri` (L30–31); first cantica header `INFERNO` (**L37**); first verse line `Nel mezzo del cammin di nostra vita` (L45). Verse ends at `l'amor che move il sole e l'altre stelle.` (**L19596**). Back matter: a `TABLE OF SPECIAL CHARACTERS` transcriber glyph table (L19602–19638). PG END at **L19654**. Skip L1–L27 and L19640+.
- **Work proper — EN**: PG START (**L31**); title block `THE DIVINE COMEDY` (L36) / `THE VISION` (L38) / `HELL, PURGATORY, AND PARADISE` (L40) / `BY DANTE ALIGHIERI` (L42) / `TRANSLATED BY` / `THE REV. H. F. CARY, M.A.` (L45–46) / `Illustrated by M. Gustave Doré` (L48); front-matter TOC `LIST OF CANTOS` (**L53**); body begins `HELL / OR THE INFERNO` (**L164–165**), first verse line `In the midway of this our mortal life,` (L172). Verse ends `That moves the sun in heav'n and all the stars.` (**L15645**). PG END at **L15650**. Skip L1–L30 and L15648+.
- **How sampled**: `grep -n` for cantica + canto markers in both files (full counts in §1); `awk` run-length analysis of blank-line-delimited verse groups for Inferno I and Paradiso XXXIII in both; verbatim `sed -n` reads of every level boundary and both matter blocks.

## 1. Container hierarchy

**Named levels (top to bottom), with the IT/EN divergence made explicit:**

| Level | IT name in text | EN name in text | Count | Notes |
|-------|-----------------|-----------------|-------|-------|
| 0 — book | `LA DIVINA COMMEDIA` (L30) | `THE DIVINE COMEDY` (L36) | 1 | the whole work |
| 1 — cantica | `INFERNO` / `PURGATORIO` / `PARADISO` | `HELL` / `PURGATORY` / `PARADISE` | **3** | proper-name designation (§2) |
| 2 — canto | `Inferno • Canto I` … | `CANTO I` … | **100** | Roman designation, restarts per cantica |
| 3 — stanza group | **tercet** (uniform 3-line) | **verse-paragraph** (irregular) | — | **THIS LEVEL DIVERGES — see §6** |
| leaf — line | verse line | verse line | — | no printed line numbers in either file |

**Depth is FIXED, not variable; children are HOMOGENEOUS, not heterogeneous.** This is a clean
4–5 level tree. `grep -nE "^PART|^BOOK|^Part"` finds no grouping level between book and cantica.
Every cantica's children are cantos only; every canto's children are stanza-groups/lines only.
So this witness **does not exercise** working-hypotheses (a) recursion/variable-depth or
(f) heterogeneous children — and that absence is itself evidence (see §9).

**Asymmetric child counts per cantica — verbatim from the commands (CONFIRMED 34 / 33 / 33 = 100):**

IT — `grep -cnE '^\s*(Inferno|Purgatorio|Paradiso) • Canto '`:
- Inferno = **34** (first `Inferno • Canto I` L42; last `Inferno • Canto XXXIV` **L6337**)
- Purgatorio = **33** (first `Purgatorio • Canto I` L6535; last L12863)
- Paradiso = **33** (first `Paradiso • Canto I` L13069; last `Paradiso • Canto XXXIII` **L19401**)

EN — `awk '/^CANTO /'` partitioned at the cantica body headers:
- Hell = **34** (first `CANTO I` L170; last `CANTO XXXIV` **L5308**)
- Purgatory = **33** (last L10455)
- Paradise = **33** (last `CANTO XXXIII` **L15503**)

Both files independently total exactly **100** `CANTO` body headers. The 34/33/33 asymmetry is invariant across the witnesses.

**Boundary example — book → cantica (IT L37 / EN L164):**
```
IT:  INFERNO            (L37, standalone)
EN:  HELL               (L164)
     OR THE INFERNO     (L165)
```
Note the EN cantica header is **two lines for Hell** (`HELL` + `OR THE INFERNO`) but **single-word**
for the others (`PURGATORY` L5456, `PARADISE` L10612). The IT is uniformly single-word.

**Boundary example — cantica → canto:**
```
IT (L42):  Inferno • Canto I
EN (L170): CANTO I
```

**Boundary example — canto → tercet/line (Inferno Canto I, first tercet):**
```
IT (L45–47):
  Nel mezzo del cammin di nostra vita
  mi ritrovai per una selva oscura,
  ché la diritta via era smarrita.

EN (L172–174):
In the midway of this our mortal life,
I found me in a gloomy wood, astray
Gone from the path direct: and e'en to tell ...   ← runs ON past 3 lines (see §6)
```

## 2. Designation system

**TWO coexisting designation kinds at DIFFERENT depths — CONFIRMS working-hypothesis (c):**

1. **Cantica = proper-name designation** (not a number). `INFERNO` / `PURGATORIO` / `PARADISO`
   (IT) ; `HELL` / `PURGATORY` / `PARADISE` (EN). The name *is* the label; there is no
   "Cantica 1." A name-reader plugin must map name→ordinal (Inferno=1) for position, and the
   names **differ by language** (Inferno≠Hell), so the reader is language-specific.

2. **Canto = Roman-numeral designation.** `I … XXXIV`. **Restarts at I in each cantica** — verified:
   `Inferno • Canto I` (L42), `Purgatorio • Canto I` (L6535), `Paradiso • Canto I` (L13069) all exist.
   So a canto's Roman number is **unique only within its parent cantica**, never globally. "Canto I"
   alone is ambiguous across the book; it is parent-dependent.

3. **Line = no printed designation in either file.** There are *no* line-number markers in the text
   (`grep` for numbered line markers finds none in the verse). The line's only identity is its
   Arabic position within the canto — supplied by the reader/citation convention, not the source.

**Surface-form divergence of the same designation across THREE renderings** (a key tracking lesson):
- IT canto header: `Inferno • Canto I` — **self-contained** (repeats cantica name + Roman), globally unambiguous on its own line.
- EN body canto header: `CANTO I` — **parent-dependent** (Roman only; relies on the enclosing `HELL`/`PURGATORY`/`PARADISE` header).
- EN front-matter TOC: `Canto 1` (Arabic! L56 ff.) under `HELL` (L55) — same canto, **Arabic** here, **Roman** in the body.

So a single canto bears designation surfaces `Inferno • Canto I` / `CANTO I` / `Canto 1` across two
files and two locations in one file. **Designation does not encode a stable identity; position does.**

## 3. Descriptive titles

**No descriptive canto titles in either witness — cantos carry a number ONLY.** The IT canto header is
exactly `Inferno • Canto I` with nothing following before the verse; the EN is exactly `CANTO I`. There
is no "Canto I — The Dark Wood" gloss line. (Cary's *print* editions famously carry prose **arguments**
before each canto, but PG #8800 omits them — see §4/§5.) Cantica headers likewise carry no descriptive
subtitle except the EN `OR THE INFERNO` apposition on Hell (L165), which names the same cantica rather
than describing the canto. Conclusion: designation = number; title node is **absent** at the canto level.

## 4. Body block vocabulary

**Verse is the ONLY body block — CONFIRMS working-hypothesis (d), verse-primary.** No prose body exists
in either file: `grep -cE 'ARGUMENT'` = **0** in EN, and `grep -cE '^\s*NOTES?\s*$|FOOTNOTE|\[[0-9]+\]'`
= **0** in EN. There are no canto arguments, no footnotes, no editorial notes interleaved with the verse.
The body block vocabulary is two typed blocks: the **stanza-group** (grouping block) and the **line** (leaf).

**The stanza-group block is where IT and EN structurally diverge:**

- **IT = tercet** — a uniform 3-line block separated by a single blank line. `awk` run-length of
  non-blank lines in Inferno Canto I returns `3 3 3 3 3 3 3 3 …` (every group is exactly 3). The canto
  is **136 verse lines / 50 blank separators** = 45 tercets + 1 closing line (terza rima).
  Verbatim (IT L49–51, the second tercet):
  ```
  Ahi quanto a dir qual era è cosa dura
  esta selva selvaggia e aspra e forte
  che nel pensier rinova la paura!
  ```

- **EN = irregular verse-paragraph** — blank-line groups of *varying* length. `awk` run-length of the
  same canto (Cary Inferno I) returns `17 11 6 9 13 6 23 46 …` — sense-paragraphs, **not** tercets.
  The canto is **132 verse lines / 14 blank separators**. Verbatim (EN L172–177, the opening paragraph
  runs straight past three lines):
  ```
  In the midway of this our mortal life,
  I found me in a gloomy wood, astray
  Gone from the path direct: and e'en to tell
  It were no easy task, how savage wild
  That forest, how robust and rough its growth,
  Which to remember only, my dismay
  ```

So the leaf type (verse line) is invariant, but the grouping block above it (**tercet → verse-paragraph**)
is **witness-specific**, with different cardinality and different boundaries.

## 5. Matter (front / body / back)

Both witnesses treat matter as **book-level siblings of the cantica sequence — CONFIRMS hypothesis (e)**,
but the two files carry *different* matter, and one of the two blocks is a transcriber artifact, not authorial:

- **EN front matter** — `LIST OF CANTOS` (L53), a table of contents: cantica sub-headers `HELL` (L55) /
  `PURGATORY` (L91) / `PARADISE` (L126), each followed by `Canto 1 … Canto 34` (Arabic). This is an
  **editorial TOC**, a sibling preceding the first cantica body. **The IT file has no TOC.**
- **EN translator preface** — **none.** L159–163 (between TOC end and `HELL` body) are blank; Cary's
  prose preface is not in this PG file.
- **IT back matter** — a transcriber's `TABLE OF SPECIAL CHARACTERS` (bilingual header
  `TAVOLA DEI CARATTERI SPECIALI / TABLE OF SPECIAL CHARACTERS`, L19602–19603), set off by a dashed
  rule `- - - - - …` (L19601), listing glyph conventions (`à = a grave` … `• = middot` … `. . . = ellipsis`,
  to L19638). This is a **Project Gutenberg transcriber note**, not part of Dante's work — an extraction
  trap (§8). **The EN file has no such table.**
- **Arguments / notes** — absent in both (see §4).

Net: front/back matter are genuine siblings, but they are **non-parallel across witnesses** (EN has a
front TOC; IT has a back glyph table) and partly **non-authorial** (the IT table is transcription scaffolding).

## 6. Identity & cross-witness behavior

**Canonical citation in practice**: `cantica · canto · line` — e.g. *Inf.* I.1, *Par.* XXXIII.145. This
is the scholarly standard and both files independently support the cantica and canto coordinates.

**The IT-vs-EN structural diff — what is INVARIANT and what SHIFTS:**

INVARIANT across the two witnesses:
- **3 cantiche**, same order (Inferno/Hell → Purgatorio/Purgatory → Paradiso/Paradise).
- **Canto count per cantica: 34 / 33 / 33 = 100**, identical and identically asymmetric (verified by
  independent `grep`/`awk` counts in both files, §1).
- **Canto order and boundaries** correspond 1:1 — Inferno Canto I (IT) ↔ Hell CANTO I (EN), etc.
- **The closing line corresponds semantically** across the whole poem: IT `l'amor che move il sole e
  l'altre stelle.` (L19596) ↔ EN `That moves the sun in heav'n and all the stars.` (L15645).

SHIFTS across the two witnesses:
- **Stanza grouping**: uniform IT tercets → irregular EN verse-paragraphs (§4). The tercet level
  **does not survive translation**; Cary's blank verse has no terza-rima grouping.
- **Line counts differ — there is NO 1:1 line correspondence:**
  - Inferno Canto I: **IT 136 lines / EN 132 lines**.
  - Paradiso Canto XXXIII: **IT 145 lines / EN 135 lines** (`awk` non-blank counts, header-to-last-verse).
- **Designation surface** differs (proper names Inferno≠Hell; `Inferno • Canto I` vs `CANTO I` vs `Canto 1`).

**What this proves about identity:** translation invariance is **depth-bounded**. The position-path is
cross-witness stable **down to the canto** (`cantica[i].canto[j]`), and **breaks below it** — the line
index `[k]` is a *per-witness* coordinate (136≠132), and the tercet grouping exists in only one witness.
So:
- Working-hypothesis (b) — *position-path is canonical identity, designation is a read field* — is
  **CONFIRMED at the cantica/canto levels and is the only thing that could work there**: the canto's
  Roman designation isn't globally unique (restarts per cantica, §2), the cantica's designation is a
  language-specific proper name, and line numbers aren't even printed — so **only position survives**,
  and the citation string is a derived display rendering of `(cantica-name, canto-Roman, line-Arabic)`.
- **But (b) must be qualified at the line level**: a position-path that includes the line index is **not**
  a cross-witness identity. Aligning *Inf.* I.1 (IT) to its Cary line is an approximate text-alignment
  problem, not a positional lookup. The model must treat **line-level cross-witness identity as
  alignment, not equality** — exactly the IT→EN problem the live pipeline faces.

## 7. Authorship

**Single book-level author, with a distinct translator role — partial test of hypothesis (g).** Both files
declare `Author: Dante Alighieri`. The EN additionally declares `Translator: Henry Francis Cary` (L17) and
`Illustrator: Gustave Doré` (L15) as **separate book-level roles** (title block L42 `BY DANTE ALIGHIERI` vs
L45–46 `TRANSLATED BY / THE REV. H. F. CARY, M.A.`). There is **no per-node (per-canto, per-line)
authorship** — hypothesis (g) is *not* exercised by this witness. What it *does* force is a **role
distinction at book level**: `author` (Dante, language-invariant) vs `translator` (Cary, witness-specific)
vs `illustrator` (Doré). The translator is the axis along which the §6 line/tercet shifts occur, so the
role is load-bearing for cross-witness reasoning even though authorship itself is not per-node.

## 8. Extraction cues

**Markers a parser keys on (quoted from the raw text):**

- **Cantica boundary (IT)**: a standalone all-caps line matching `^\s*(INFERNO|PURGATORIO|PARADISO)\s*$`
  (L37, L6530, L13064).
- **Cantica boundary (EN body)**: standalone `^(HELL|PURGATORY|PARADISE)$` (L164, L5456, L10612) — but
  `HELL` is followed by an apposition line `OR THE INFERNO`, and the **same three words also appear in the
  title block** (`HELL, PURGATORY, AND PARADISE`, L40) and as **TOC sub-headers** (L55/91/126). Anchor on
  position (after the TOC, standalone) not on the word alone.
- **Canto boundary (IT)**: `^\s*(Inferno|Purgatorio|Paradiso) • Canto [IVXL]+\s*$` — note the **middot
  `•` separator** and that the cantica name is repeated. Do **not** match the bare word `canto`: it occurs
  mid-verse as the common noun ("song"), e.g. IT L739 `di quel segnor de l'altissimo canto` — a false
  positive the `•`-anchored pattern excludes.
- **Canto boundary (EN body)**: `^CANTO [IVXL]+$` (Roman, all-caps, standalone). The **TOC uses a
  different form** `Canto \d+` (mixed-case, Arabic) — `Canto 1` (L56). A parser that keys on `Canto`
  loosely will pull all 100 TOC entries as false canto starts; restrict to the all-caps Roman form and to
  the post-TOC region.
- **Line grouping**: blank-line-delimited groups. In IT every group is a 3-line tercet (reliable);
  in EN the group is a variable-length verse-paragraph (do **not** assume 3).

**Traps:**
- **Gutenberg boilerplate**: skip L1–L27 (IT) / L1–L30 (EN) header and the post-END license footer.
- **IT back-matter glyph table** (L19601–19638): the dashed rule `- - - - …` + `TABLE OF SPECIAL
  CHARACTERS` is a transcriber note, not verse — stop the body at the last verse line (`l'amor che move…`
  L19596), not at PG END.
- **EN front-matter TOC** (`LIST OF CANTOS` L53–158): 3 cantica words + 100 `Canto N` lines that mimic
  real headers in the wrong number system. Treat the whole block as front matter.
- **No printed line numbers**: a parser cannot read a line's citation index from the text; it must assign
  Arabic position by counting non-blank verse lines within the canto.
- **CR line endings**: both files are CRLF (`\r$`), so anchor patterns on `\s*$` not `$`-after-text.

## 9. What this witness uniquely forces in the model

1. **Verse-primary body** — the body block vocabulary must include a **stanza-group** and a **verse line**
   as first-class typed blocks, not just "paragraph." A prose-only body model cannot represent this work at
   all. (Other witnesses force prose/tables; this one forces verse.)
2. **Two designation kinds at different depths in one tree** — a **proper-name** reader at the cantica
   level *and* a **Roman-numeral** reader at the canto level must coexist as independent plugins on the
   same document. A single global designation scheme cannot describe Dante. This is the cleanest positive
   case for hypothesis (c).
3. **Parent-dependent, non-unique designation** — `Canto I` recurs 3× (once per cantica). Any identity
   that leans on the canto designation alone collides. This forces designation to be demoted to a
   *read field* and position (`cantica-index, canto-index`) to be the key — the core tracking thesis,
   here proven by a designation that is *structurally* non-unique rather than merely renumbered.
4. **Depth-bounded translation invariance** — structure survives IT→EN **down to the canto** (34/33/33
   boundaries identical) and **breaks below it** (tercets vanish; line counts 136≠132, 145≠135). The model
   must let position-path identity be **witness-stable at upper levels and alignment-only at the line
   level**. If the model assumes line `[k]` is the same node across witnesses, every IT→EN line citation
   silently mis-points — directly relevant to the live edition's IT-source / EN-translation pairing.
5. **What this witness does NOT force (and that is informative)**: no variable depth (a), no heterogeneous
   children (f), no per-node authorship (g). Dante is a *regular fixed-depth homogeneous* tree. A model
   tuned only on Dante would under-build; a model built for the ragged witnesses must still degrade
   gracefully to this clean case. Use Dante as the **regularity baseline**, not the capability driver,
   for those three axes.

**What breaks if ignored:** (i) modeling the body as prose loses verse entirely; (ii) one designation
reader mis-parses either the cantica names or the canto numerals; (iii) keying identity on the canto
number collides across cantiche; (iv) assuming line-level cross-witness equality mis-aligns every IT→EN
citation; (v) a loose `Canto`/`HELL` matcher ingests the EN TOC and the IT glyph table as body.

## 10. Open questions / contradictions

- **Tercet level is real but witness-asymmetric.** Should the canonical tree carry a `tercet`/stanza-group
  node at all, given Cary's witness has no tercets? Options: (a) model the stanza-group as a witness-local
  block that may be absent, or (b) anchor the tree at canto and treat all sub-canto grouping as
  presentation. The data supports (a): IT tercets are a genuine, uniform structural level; EN
  verse-paragraphs are a genuine, irregular one. **Needs a human ruling on whether a level that exists in
  only one witness is part of the shared identity or a per-witness annotation.**
- **No 1:1 line identity across witnesses** (136 vs 132; 145 vs 135). Confirmed contradiction of any
  "position-path includes line index, stable across witnesses" reading. The line index is intra-witness
  only; cross-witness line correspondence is an **alignment artifact**, not an identity. Flagged as the
  single most consequential cross-witness finding.
- **Matter is non-parallel and partly non-authorial.** EN has a front TOC; IT has a back glyph table (a
  transcriber note). Does the model represent the IT glyph table as back matter, or exclude it as
  transcription scaffolding? It is *in* the file but not *of* the work.
- **EN cantica header is irregular** (`HELL / OR THE INFERNO` two lines vs single-word `PURGATORY` /
  `PARADISE`). Minor, but a parser that assumes a single-line cantica header mis-reads Hell.
- **Doré illustrations** are declared (`Illustrator: Gustave Doré`) but **no image blocks** appear in this
  plain-text witness — a figure node present in metadata but absent from the body. Not a contradiction for
  these files, but a reminder that declared roles need not produce body nodes.
