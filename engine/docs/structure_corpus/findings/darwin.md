# Structural close read — On the Origin of Species (Darwin; 1859 #1228 + 1872 #2009)

> Witness role: **cross-edition renumbering** — the proof that *position ≠ designation*.
> Two editions of the same work read side-by-side; the diff is the centerpiece (§6).

## 0. Identification — work; both editions + PG#; sizes; how sampled.

- **Work:** Charles Darwin, *On the Origin of Species by Means of Natural Selection, or
  the Preservation of Favoured Races in the Struggle for Life.*
- **Edition A — 1st (1859):** `darwin_origin_1859.txt`, **PG #1228**, ~971 KB / 16 574
  lines. Title page: "John Murray, Albemarle Street. 1859." (file ~ln 38–55).
- **Edition B — 6th (1872):** `darwin_origin_1872.txt`, **PG #2009** ("considered the
  definitive edition"), ~1.30 MB / 21 957 lines. Title page: "Sixth London Edition,
  with all Additions and Corrections."
- **Both transcribed by** Sue Asscher and David Widger; both list the same three PG
  filenumbers (1228 / 22764 / 2009) in a selector header.
- **Work bounds (where the work proper begins / ends):**
  - 1859: PG `*** START ***` marker at **ln 27**; work proper (title page) begins
    **ln ~38** ("On / the Origin of Species"); back matter ends with the INDEX, which
    runs to **ln ~16 000**; PG `*** END ***` at **ln 16 224**.
  - 1872: `*** START ***` at **ln 27**; title page **ln ~38**; INDEX ends **ln ~21 540**;
    `*** END ***` at **ln 21 607**.
- **How sampled:** `grep -n` over `^CHAPTER`, the matter keywords
  (`INTRODUCTION|HISTORICAL SKETCH|GLOSSARY|INDEX|CONTENTS|RECAPITULATION`), bracket
  footnote markers `\[[0-9]+\]`, and whole-line italic side-headings `^_[A-Z][^_]*\._$`;
  targeted `sed -n` reads of every boundary quoted below. Counts/lists reported here are
  from those commands, not memory.

---

## 1. Container hierarchy — named levels; depth; child counts; verbatim boundary examples.

**Named levels (shallow tree, max depth 3 incl. block leaves):**

```
WORK
 ├─ front matter      (Contents; Detailed/Analytical Contents; Introduction; 1872-only Historical Sketch)
 ├─ CHAPTER  (×14 in 1859, ×15 in 1872)      ← the one grouping level
 │    └─ §sub-section  (italic run-in side-heading)   ← BODY-LEVEL ONLY IN 1872 (see §4)
 │         └─ prose paragraphs / footnotes (leaf blocks)
 └─ back matter       (Glossary [1872-only]; Index)
```

This is a **flat chapter spine**, *not* a recursive part/book tree. There is no
"Part"/"Book" grouping above chapters in either edition (contrast PLL's Parte
Prima/Seconda or Dante's cantiche). Depth is **2 structural levels** (chapter ›
sub-section) in 1872 and **1 structural level** (chapter only) in 1859, where the
sub-section topics live solely in the front-matter Detailed Contents and never surface
in the body.

**Child counts (asymmetric):** chapters are the only repeated container. The work has
1 chapter list; each chapter has a ragged number of body sub-sections (1872: ~52 italic
headings over 15 chapters ≈ 3–4 each, but unevenly — e.g. Ch. I has 5, others 1–2).

**Verbatim boundary example — chapter level (the header is TWO lines: designation, then title):**

1859, ln 482–484:
```
CHAPTER I.
VARIATION UNDER DOMESTICATION.
```
1872, ln 862–864:
```
CHAPTER I.
VARIATION UNDER DOMESTICATION.
```

**Verbatim boundary example — §sub-section level (1872 only), ln 877:**
```
_Causes of Variability._
```
(immediately followed by the prose paragraph "When we compare the individuals…").

---

## 2. Designation system — number + title; unique-within-edition but UNSTABLE across editions.

- **Kind:** **Roman-numeral chapter designation**, fused to the header token
  `CHAPTER <ROMAN>.` in the body of BOTH editions (`CHAPTER VII.`). Globally unique
  *within one edition*, only-within-the-work (resets per edition), self-contained
  (you can cite "Chapter VII" without a parent).
- **Encodes position?** Yes — the Roman numeral *is* the 1-based ordinal of the chapter
  in its edition. That is exactly why it is **not stable across editions**: when a
  chapter is inserted, every downstream numeral re-encodes a *new* position (§6).
- **A transcription wrinkle in the 1859 short Contents:** the designations are written
  inconsistently there — chapter 1 as Roman `CHAPTER I.` (ln 105) but chapters 2–14 as
  **Arabic** `CHAPTER 2.` … `CHAPTER 14.` (ln 120–297). The *body* and *Detailed
  Contents* use Roman throughout (`CHAPTER 2.` body header is at ln 1589 as `CHAPTER
  II.`). So even *within one edition* the designation's surface form is not uniform
  across the TOC vs. the body — an extraction trap, and evidence the numeral is a
  rendering of an ordinal, not a stable key.
- **The key point (developed in §6):** `CHAPTER VII` resolves to **different content**
  in the two editions:
  - 1859 ln 200 / body ln 6370: `CHAPTER VII. INSTINCT.`
  - 1872 ln 505 / body ln 7793: `CHAPTER VII. MISCELLANEOUS OBJECTIONS TO THE THEORY OF
    NATURAL SELECTION.`
  Same designation string → different node. The designation is therefore a **read
  field**, not an identity.

---

## 3. Descriptive titles — chapter titles; §sub-section titles; examples.

- **Chapter title:** present, and it is a **separate node/line from the designation**
  (designation on one line, ALL-CAPS title on the next — see §1). In the Contents the
  two are run together on one line (`CHAPTER I. VARIATION UNDER DOMESTICATION`); in the
  body they are split across two lines. So designation and title are *fused in the TOC,
  split in the body* — the model should treat them as two fields of one header, however
  rendered.
- **Chapter title examples (1872 Contents, ln 499–513):** "VARIATION UNDER
  DOMESTICATION", "NATURAL SELECTION; OR THE SURVIVAL OF THE FITTEST", "MISCELLANEOUS
  OBJECTIONS TO THE THEORY OF NATURAL SELECTION", "RECAPITULATION AND CONCLUSION".
- **§sub-section titles (1872 body, italic):** "_Causes of Variability._" (ln 877),
  "_Doubtful Species._" (ln 2180), "_Summary._" (ln 2634), "_Geometrical Ratio of
  Increase._" (ln 2777). These are the same topic strings that the Detailed Contents
  lists as run-in em-dash phrases.
- **Title fidelity across editions is imperfect** (titles are themselves edited — see
  the rename rows in §6): 1859 Ch. IV "NATURAL SELECTION." → 1872 Ch. IV "NATURAL
  SELECTION; OR THE SURVIVAL OF THE FITTEST"; 1859 Ch. VI "DIFFICULTIES ON THEORY." →
  1872 Ch. VI "DIFFICULTIES OF THE THEORY"; 1859 Ch. XIII "MUTUAL AFFINITIES OF ORGANIC
  BEINGS: MORPHOLOGY: EMBRYOLOGY: RUDIMENTARY ORGANS." (body ln 12302–12303) → 1872
  Ch. XIV "MUTUAL AFFINITIES OF ORGANIC BEINGS" (shortened).

---

## 4. Body block vocabulary — prose; §sub-section heading; footnote; verbatim examples.

Observed leaf/heading block types:

1. **Prose paragraph** (the default body block, both editions). 1859 body ln 495:
   ```
   When we look to the individuals of the same variety or sub-variety of
   our older cultivated plants and animals, one of the first points which
   strikes us, is, that they generally differ much more from each other,
   ```

2. **§sub-section heading — whole-line italic, `_..._` (1872 ONLY).** Verbatim, 1872
   ln 877:
   ```
   _Causes of Variability._
   ```
   **`grep -cE "^_[A-Z][^_]*\._$"` returns 52 in 1872 and 0 in 1859.** This is a
   first-class structural difference between the editions, not noise (see §10 / §9):
   the 6th edition promoted the analytical topics into run-in italic body headings; the
   1st edition kept them only in the front-matter Detailed Contents.

3. **Footnote — bracketed marker `[N]` inline + an indented `[N] …` note block. CONFINED
   TO THE HISTORICAL SKETCH in 1872; ABSENT ENTIRELY IN 1859.** `grep -cE "\[[0-9]+\]"`
   returns **0 in 1859** and **6 in 1872** (all at ln ≤ 403, i.e. inside the Historical
   Sketch). Verbatim marker + note, 1872 ln 97 + ln 103:
   ```
   allusions to the subject in the classical writers,[1] the first author
   ...
    [1] Aristotle, in his "Physicæ Auscultationes" (lib.2, cap.8, s.2),
    after remarking that rain does not fall in order to make the corn
   ```
   A second footnote idiom is the **`*` attribution note** on the Glossary header
   (1872 ln 18921 `GLOSSARY … VOLUME.*` → ln 18923 `   * I am indebted to … Mr. W.S.
   Dallas …`). The chapter bodies themselves carry **no** footnotes in either edition.

4. **Analytical-contents topic block** (front matter): a chapter's sub-topics rendered
   as a list — **format differs by edition**: 1859 = one period-terminated line each,
   indented (ln 107–118: `  Causes of Variability.` / `  Effects of Habit.` …); 1872 =
   a single em-dash-joined run-in paragraph (ln 526–532: `Causes of Variability—Effects
   of Habit and the use or disuse of Parts—Correlated Variation—…`).

5. **Back-matter entry blocks** — glossary entries and index entries (see §5).

Blocks carrying their own attributes: the footnote note carries an attribution/source;
the glossary header carries a **different author** (Dallas; §7).

---

## 5. Matter (front / body / back) — siblings or special-cased? edition differences.

Matter elements found, in **file order** (which is itself a finding — see the 1872 trap):

**1859 front matter:**
- `Contents` (ln 79) — short chapter list.
- `DETEAILED CONTENTS.` (ln 98, *sic* — OCR/transcription typo) — analytical contents.
- `INTRODUCTION.` body (ln 313): "When on board H.M.S. 'Beagle,' as naturalist, I was
  much struck …".
- **No Historical Sketch, no Glossary.**

**1859 back matter:**
- `INDEX.` (ln 14618) — the only back matter. Entry form `Headword, page.` with a
  **colon + indented sub-entries** idiom: ln 14630 `Affinities:` then `of extinct
  species, 329.` / `of organic beings, 411.`

**1872 front matter (NOTE THE FILE ORDER):**
- Three epigraphs (Whewell / Butler / Bacon, ln 57–80).
- **`AN HISTORICAL SKETCH OF THE PROGRESS OF OPINION ON THE ORIGIN OF SPECIES…`** — body
  at **ln 85**, i.e. it physically **precedes** the Contents in this file. This is the
  6th-edition addition (absent in 1859). It is the only section carrying footnotes.
- `Contents` (ln 493) — short list: Historical Sketch, Introduction, Chapters I–XV,
  Glossary, Index.
- `DETAILED CONTENTS.` (ln 517).
- `INTRODUCTION.` body (ln 702): "When on board H.M.S. Beagle, as naturalist…".

**1872 back matter:**
- **`GLOSSARY OF THE PRINCIPAL SCIENTIFIC TERMS USED IN THE PRESENT VOLUME.`** (ln 18921)
  — 6th-edition addition, absent in 1859. Entry form `HEADWORD.—Definition.` (ALL-CAPS
  headword, em-dash). ln 18929 `ABERRANT.—Forms or groups of animals or plants which
  deviate…`.
- `INDEX.` (ln 19702) — entry form `Headword, page.` with **em-dash continuation** for
  sub-entries (ln 19710 `Affinities of extinct species, 301.` then `—, of organic
  beings, 378.`), a *different* sub-entry idiom from 1859's colon-list.

**Siblings or special-cased?** Structurally these matter sections behave as **siblings
of the chapter spine** at the work level (they sit in the same flat sequence and appear
in the Contents alongside the chapters). But they are **typed differently** — the
Glossary and Index are lookup/locator structures, not prose chapters — so the model
needs heterogeneous siblings (front/body/back matter co-resident with chapters). The
**set of matter siblings differs by edition**: 1872 adds a Historical Sketch (front) and
a Glossary (back) that 1859 lacks.

---

## 6. Identity & cross-witness behavior — THE CENTERPIECE: the 1859↔1872 chapter diff.

**Full ordered chapter list, 1859 (14 chapters)** — from `grep -n "^CHAPTER" … | body`:

| # | 1859 designation | title (body) |
|---|---|---|
| 1 | CHAPTER I | VARIATION UNDER DOMESTICATION |
| 2 | CHAPTER II | VARIATION UNDER NATURE |
| 3 | CHAPTER III | STRUGGLE FOR EXISTENCE |
| 4 | CHAPTER IV | NATURAL SELECTION |
| 5 | CHAPTER V | LAWS OF VARIATION |
| 6 | CHAPTER VI | DIFFICULTIES ON THEORY |
| 7 | CHAPTER VII | **INSTINCT** |
| 8 | CHAPTER VIII | HYBRIDISM |
| 9 | CHAPTER IX | ON THE IMPERFECTION OF THE GEOLOGICAL RECORD |
| 10 | CHAPTER X | ON THE GEOLOGICAL SUCCESSION OF ORGANIC BEINGS |
| 11 | CHAPTER XI | GEOGRAPHICAL DISTRIBUTION |
| 12 | CHAPTER XII | GEOGRAPHICAL DISTRIBUTION—_continued_ |
| 13 | CHAPTER XIII | MUTUAL AFFINITIES OF ORGANIC BEINGS: MORPHOLOGY: EMBRYOLOGY: RUDIMENTARY ORGANS |
| 14 | CHAPTER XIV | RECAPITULATION AND CONCLUSION |

**Full ordered chapter list, 1872 (15 chapters):**

| # | 1872 designation | title (Contents ln 499–513) |
|---|---|---|
| 1 | CHAPTER I | VARIATION UNDER DOMESTICATION |
| 2 | CHAPTER II | VARIATION UNDER NATURE |
| 3 | CHAPTER III | STRUGGLE FOR EXISTENCE |
| 4 | CHAPTER IV | NATURAL SELECTION; OR THE SURVIVAL OF THE FITTEST |
| 5 | CHAPTER V | LAWS OF VARIATION |
| 6 | CHAPTER VI | DIFFICULTIES OF THE THEORY |
| 7 | CHAPTER VII | **MISCELLANEOUS OBJECTIONS TO THE THEORY OF NATURAL SELECTION** |
| 8 | CHAPTER VIII | INSTINCT |
| 9 | CHAPTER IX | HYBRIDISM |
| 10 | CHAPTER X | ON THE IMPERFECTION OF THE GEOLOGICAL RECORD |
| 11 | CHAPTER XI | ON THE GEOLOGICAL SUCCESSION OF ORGANIC BEINGS |
| 12 | CHAPTER XII | GEOGRAPHICAL DISTRIBUTION |
| 13 | CHAPTER XIII | GEOGRAPHICAL DISTRIBUTION—continued |
| 14 | CHAPTER XIV | MUTUAL AFFINITIES OF ORGANIC BEINGS |
| 15 | CHAPTER XV | RECAPITULATION AND CONCLUSION |

**Explicit content-aligned diff (align on title/content, not on numeral):**

| content | 1859 # | 1872 # | relation |
|---|---|---|---|
| Variation under Domestication | I | I | **identical** (designation + title) |
| Variation under Nature | II | II | identical |
| Struggle for Existence | III | III | identical |
| Natural Selection | IV | IV | **renamed** (title extended `; or the Survival of the Fittest`) |
| Laws of Variation | V | V | identical |
| Difficulties on/of (the) Theory | VI | VI | **renamed** (minor: "ON THEORY"→"OF THE THEORY") |
| **Miscellaneous Objections** | — | **VII** | **INSERTED — new chapter, no 1859 counterpart** |
| Instinct | VII | VIII | **renumbered +1** |
| Hybridism | VIII | IX | renumbered +1 |
| Imperfection of the Geological Record | IX | X | renumbered +1 |
| Geological Succession of Organic Beings | X | XI | renumbered +1 |
| Geographical Distribution | XI | XII | renumbered +1 |
| Geographical Distribution—continued | XII | XIII | renumbered +1 |
| Mutual Affinities of Organic Beings | XIII | XIV | renumbered +1 **and renamed** (title shortened) |
| Recapitulation and Conclusion | XIV | XV | renumbered +1 |

**Where renumbering starts:** at the **insertion point = new Chapter VII
("Miscellaneous Objections")**. Chapters 1–6 keep their numerals; everything from
**INSTINCT onward shifts +1** (1859 VII → 1872 VIII, …, 1859 XIV → 1872 XV).

**What it proves about identity:**
- The **designation is not a stable cross-edition key.** `CHAPTER VII` names *Instinct*
  in 1859 and *Miscellaneous Objections* in 1872; `CHAPTER XIV` names *Mutual
  Affinities…* in 1859 but *Recapitulation* in 1872. Keying identity on the numeral
  would silently mis-align 8 of the work's chapters.
- **Position-alignment survives** — but *position* here must mean *content-anchored
  ordinal* (alignment by title/content), not the printed numeral. A naive
  "nth-chapter-by-its-own-numeral" alignment also fails after the insertion. So the
  witness refines hypothesis (b): a **position-path is the right identity only if the
  alignment that produces it is content-aware (an insert/delete-tolerant alignment),
  not numeral arithmetic.** The numeral and the title are both *read fields*; the
  durable cross-edition link is the alignment edge between two position-paths.
- **The index makes the same point at the leaf level:** the same headword resolves to
  *different page numbers* across editions ("Aberrant groups, 429." 1859 ln 14620 vs.
  "Aberrant groups, 379." 1872 ln 19704; "Recapitulation, general, 459." 1859 ln 15826
  vs. "…, 404." 1872 ln 21125). The page locator is an edition-bound read field exactly
  like the chapter numeral.

---

## 7. Authorship — single author; per-node?

- **Book-level author:** Charles Darwin (both title pages).
- **Per-node authorship is REAL here and confirms hypothesis (g):** the **Glossary is
  authored by W. S. Dallas, not Darwin**, and the text says so in the header's
  attribution footnote — 1872 ln 18923:
  ```
     * I am indebted to the kindness of Mr. W.S. Dallas for this
     Glossary, which has been given because several readers have
     complained to me that some of the terms used were unintelligible…
  ```
  So a single work has a **per-node author override** on one back-matter sibling. The
  Historical Sketch (front matter) remains Darwin's but quotes/credits dozens of prior
  naturalists in its footnotes — surveyed attribution, not a node-author change.
- No per-chapter signatures; chapters inherit the book-level author.

---

## 8. Extraction cues — header/sub-section/footnote formats; traps.

**Cues a parser keys on in THIS raw text:**
- **Chapter header:** a line `^CHAPTER <ROMAN>\.` (body) — and the **descriptive title
  is the NEXT non-blank line, ALL-CAPS** (the header is two physical lines). In the
  Contents the same is one line `CHAPTER <ROMAN>. <TITLE>`.
- **§sub-section heading (1872):** a whole line wrapped in PG italic underscores and
  ending in a period: `^_[A-Z].*\._$` (e.g. `_Causes of Variability._`).
- **Footnote (1872 sketch only):** inline marker `[\d]` glued to the preceding word; the
  note body is a separate **leading-space-indented** line `^ \[\d\] …`.
- **Glossary entry (1872):** `^[A-ZÆ ()]+\.—` (ALL-CAPS headword, period, em-dash).
- **Index entry:** `^Headword, \d+\.`; sub-entries via `^—, …` (1872) or an
  indented list under a `Headword:` line (1859).

**Traps:**
1. **The renumbering itself** (§6) — the single most important trap. A pipeline that
   diffs two editions by chapter numeral mis-aligns 8 chapters; alignment must be
   content/title-aware and insert-tolerant.
2. **Edition-specific matter** — Historical Sketch (front) and Glossary (back) exist in
   1872 only; footnotes exist in 1872 only (and only in the Sketch). A schema that
   assumes a fixed matter set, or that footnotes appear in chapter bodies, is wrong for
   one of the two witnesses.
3. **Body sub-headings exist in 1872 but NOT 1859** — the same logical sub-sections are
   front-matter-only (Detailed Contents) in 1859 and promoted to body italic headings in
   1872. A parser must not assume body sub-headings are present in every edition.
4. **`CHAPTER` token appears 3× per chapter region** — once in the short Contents, once
   in the Detailed/Analytical Contents, once in the body. Body grep must be range-gated
   (chapters begin after the Detailed Contents block: 1859 body from ln 482; 1872 body
   from ln 863). The Contents/Detailed-Contents copies are *front matter*, not chapter
   starts.
5. **Designation surface inconsistency** — 1859's short Contents writes ch. 1 in Roman
   (`CHAPTER I.`) but ch. 2–14 in **Arabic** (`CHAPTER 2.`…); body/Detailed Contents are
   Roman. Don't assume one numeral system.
6. **"`—continued`" is part of a title**, not a separate block (1859 Ch. XII / 1872
   Ch. XIII "GEOGRAPHICAL DISTRIBUTION—continued").
7. **Transcription order ≠ logical order** in 1872: the Historical Sketch body (ln 85)
   physically precedes the Contents (ln 493) in this PG file. File order alone does not
   give the canonical front-matter sequence.
8. **OCR/transcription noise:** 1859 Contents reads `DETEAILED CONTENTS.` (ln 98, *sic*).

---

## 9. What this witness uniquely forces in the model.

- **Cross-edition tree alignment as a first-class operation.** This is the only paired
  prose witness in the corpus where the *same work* yields two structurally different
  trees. The model must support aligning two position-trees of one work where the
  alignment contains **inserts** (new Ch. VII), **renames** (Ch. IV, VI, XIII titles),
  and **a +1 renumber cascade** — i.e. an edit-distance alignment over children, not a
  zip-by-index and not a join-by-designation.
- **Designation must be demoted to a read field — and so must the index page-locator.**
  Both are edition-bound. If identity keys on `CHAPTER <ROMAN>`, then a citation, a
  translation memory, a revision link, or a cross-edition concordance attaches to the
  *wrong content* for every chapter at/after the insertion. The numeral is for
  *display/citation within one edition only*.
- **But "position-path = identity" needs the alignment to be content-aware.** This
  witness refutes the *naive* form of hypothesis (b) (numeral = position = identity) and
  the equally naive "nth child" form — after an insert, the nth child by raw order also
  diverges. What survives is a position-path **plus an explicit alignment edge** between
  the two editions' paths, computed from content, not from the numeral. The position-path
  is the per-edition identity; the cross-edition identity is the alignment relation.
- **Heterogeneous, edition-varying sibling set.** The model must let the front/back
  matter membership differ per witness (Sketch + Glossary present in B, absent in A)
  without treating the missing ones as deletions of *content* the other edition had.
- **Per-node author override** (Glossary = Dallas) must be representable on a single node
  inside an otherwise single-author work.

**What breaks if the model ignores this witness:** any feature that joins editions by
chapter number (concordance, "show me how Chapter VII changed", revision tracking,
shared translation of "Chapter VII") silently pairs *Instinct* with *Miscellaneous
Objections* and shifts every later chapter — a corruption that passes type-checking and
looks plausible because both editions legitimately *have* a "Chapter VII."

---

## 10. Open questions / contradictions.

- **Contradiction to starting hypothesis (uniform body sub-headings):** the manifest
  expected "italic §sub-section headings within chapters." True for **1872 only** (52
  found); **1859 has zero** in the body (`grep` = 0). The §sub-section level is *not a
  stable structural feature of the work* — it is an edition-level body convention. The
  union model must make sub-sections optional per edition.
- **Contradiction (footnotes):** hypothesis (d) "authorial footnotes" in the body holds
  **nowhere** — 1859 has none at all; 1872's footnotes are confined to the **Historical
  Sketch** front matter (6 total) plus one Glossary attribution `*`. The chapter bodies
  are footnote-free in both editions. "Authorial footnotes" is a front-matter feature
  here, not a body-block feature.
- **Refinement to hypothesis (b):** confirmed in spirit (designation is unstable;
  position survives) but the literal "position = the chapter numeral" is **false**, and
  even "position = raw child ordinal" fails across the insert. The witness forces the
  stronger claim: cross-edition identity = a **content-aware alignment between two
  per-edition position-paths**, not either edition's standalone path.
- **Front-matter ordering ambiguity (1872):** the Historical Sketch body precedes the
  Contents in the source file, but the Contents lists it *after* itself. Which order is
  canonical for the tree — file order or Contents order? Needs a human ruling on whether
  the extractor trusts physical order or the declared Contents order.
- **Is the inserted Ch. VII purely an insert, or partly a split?** The diff treats 1872
  Ch. VII "Miscellaneous Objections" as a clean insertion (no 1859 counterpart). Some of
  its material was in fact drawn from revisions to the old "Difficulties" chapter; a
  finer-grained (paragraph-level) alignment might show it as a *partial split of Ch. VI*
  rather than a pure insert. At chapter granularity it is an insert; flagged in case the
  model later needs sub-chapter move/split detection.
- **Index sub-entry idiom differs by edition** (1859 colon-list vs. 1872 em-dash
  continuation) — a parser for the back-matter index needs two grammars, or one tolerant
  one, across editions of the *same* work.
