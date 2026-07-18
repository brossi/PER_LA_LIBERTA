# Structural close read — The Atlantic Monthly, Vol. 18 No. 106 (Aug 1866)

> Method note: every structural claim below is anchored to a `grep -n`/`sed -n` reading
> of the file run this session. Line numbers are from
> `atlantic_monthly_1866_no106_23040.txt` as committed. Quotes are verbatim.

## 0. Identification

- **Periodical / issue / date:** *The Atlantic Monthly*, "_A Magazine of Literature,
  Science, Art, and Politics._" (line 53), **Vol. XVIII — August 1866 — No. CVI**
  (i.e. Vol. 18, No. 106). Publisher Ticknor and Fields, Boston.
- **Masthead boundary (verbatim):**
  ```
  50:ATLANTIC MONTHLY.
  53:_A Magazine of Literature, Science, Art, and Politics._
  55:VOL. XVIII.--AUGUST, 1866.--NO. CVI.
  57:Entered according to Act of Congress, in the year 1866, by TICKNOR AND
  ```
- **Source file:** `engine/docs/structure_corpus/atlantic_monthly_1866_no106_23040.txt`
  — **Project Gutenberg eBook #23040** (release 2007-10-16), produced from Cornell
  University Digital Collections images. "Author: Various" (line 12).
- **Size:** 514 KB, **9174 lines**.
- **How sampled:** Whole file scanned. PG boilerplate (lines 1–46 header, 8852–9174
  license) skipped per instruction. Body read in full at the structural level; each
  article opening, every serialized installment header, both poems, a footnote block,
  and the entire Reviews department were read verbatim. Article inventory and counts
  are taken from the grep/sed output reproduced below, not from memory.

## 1. Container hierarchy

Observed shape — **ragged, variable depth** (NOT a uniform two-level list):

```
Issue (Vol.18 No.106, Aug 1866)
├─ front matter: masthead block (lines 49–62)          [no TOC — see §5]
├─ Article  (leaf — prose essay, poem, or single-part narrative)      ×8
├─ Article  (sub-container — serialized installment with internal chapters)  ×1
├─ Article  (serialized installment carrying an installment ordinal)  ×3
├─ Department: REVIEWS AND LITERARY NOTICES (sub-container of book-notices)   ×1
└─ back matter: PG license (skip)
```

So the tree is **recursive with non-uniform depth**: most articles are leaves; one
article (the novel) nests `Chapter` children; one article (Reviews) nests `Notice`
children. Depth is 2 for a plain essay (Issue › Article) and 3 for the novel
(Issue › Article › Chapter) and the reviews (Issue › Department › Notice).

**Top-level article inventory (13 nodes), from `grep -nE '^[A-Z][A-Z0-9 ...]+\.?$'`:**

| # | Line | Title (verbatim) | Kind |
|---|------|------------------|------|
| 1 | 67 | `HOW MY NEW ACQUAINTANCES SPIN.` | prose essay (natural history) |
| 2 | 1058 | `WHAT DID SHE SEE WITH?` | prose narrative / short story |
| 3 | 1942 | `THE MINER.` | **verse poem** |
| 4 | 1988 | `PHYSICAL HISTORY OF THE VALLEY OF THE AMAZONS.` | prose essay (science) + footnotes |
| 5 | 2657 | `A MANIAC'S CONFESSION.` | prose sketch/essay + footnotes |
| 6 | 2917 | `THE GREAT DOCTOR.` (`A STORY IN TWO PARTS.` / `II.`) | **serialized fiction, part II** |
| 7 | 3831 | `MY FARM: A FABLE.` | **verse poem** |
| 8 | 3901 | `PASSAGES FROM HAWTHORNE'S NOTE-BOOKS.` (`VIII.`) | **serialized journal extracts, installment VIII** |
| 9 | 4393 | `THE CHIMNEY-CORNER FOR 1866.` (`VIII.` / `HOW SHALL WE ENTERTAIN OUR COMPANY?`) | **serialized topical essay, installment VIII** |
| 10 | 4839 | `GRIFFITH GAUNT; OR, JEALOUSY.` (`CHAPTER XXXII`–`XXXVIII`) | **serialized novel installment** |
| 11 | 6610 | `LONDON FORTY YEARS AGO.` (`FROM THE MEMORANDA OF A TRAVELLER.`) | prose memoir/essay |
| 12 | 7392 | `A YEAR IN MONTANA.` | prose essay (travel) |
| 13 | 8280 | `REVIEWS AND LITERARY NOTICES.` | **department / sub-container of 11 notices** |

**Child count:** 13 top-level articles (12 individual + 1 reviews department). The
novel article (10) has **7 chapter children** (XXXII–XXXVIII). The reviews department
(13) has **11 notice children** (see §4/§5).

**Verbatim boundary example per level:**

- *Issue → first Article* (lines 62–67):
  ```
  62:to the end of the article.
  …
  67:HOW MY NEW ACQUAINTANCES SPIN.
  ```
- *Article → Chapter* inside the novel (lines 4839–4842):
  ```
  4839:GRIFFITH GAUNT; OR, JEALOUSY.
  4842:CHAPTER XXXII.
  ```
- *Department → Notice* inside Reviews (lines 8280–8283):
  ```
  8280:REVIEWS AND LITERARY NOTICES.
  8283:_The Poems of_ THOMAS BAILEY ALDRICH. Boston: Ticknor and Fields.
  ```

## 2. Designation system

**Articles themselves carry NO number and NO page number — title only.** There is no
"Article 1 / Article 2" numbering and the PG transcription preserves no physical page
numbers or running heads (probe for `^\s*\d{1,3}\s*$`, `p. N`, `page N` over the body
returned nothing but a single in-footnote citation `p. 134` at line 2613). So an
article's only designation is its descriptive title (§3).

Designation appears only **inside** the serialized articles, and in **three different
conventions in this one issue**:

- **Chapter Roman numerals** (the novel): `CHAPTER XXXII.` … `CHAPTER XXXVIII.`
  (lines 4842, 5520, 5809, 6081, 6148, 6345, 6463).
- **Installment Roman numeral, open-ended series:** `VIII.` standing alone under the
  title — Hawthorne note-books (line 3904) and The Chimney-Corner (line 4396).
- **Part-of-N ordinal:** `THE GREAT DOCTOR.` / `A STORY IN TWO PARTS.` / `II.`
  (lines 2917–2923) — part 2 of a fixed 2.

These designations are **parent-dependent and cross-issue**: `CHAPTER XXXII` is unique
only within the novel *Griffith Gaunt* (which spans issues), not within this issue;
`VIII.` is meaningless except relative to its serial. They do **not** encode the
article's position in this issue.

Reviews notices are "designated" by their book-citation header line (italic title +
author + city/publisher), e.g. line 8500 `_The United States during the War._ By
AUGUST LAUGEL. New York:`.

## 3. Descriptive titles

The **title is the primary (and usually only) handle** for an article. Titles are
descriptive, free-form ALL-CAPS lines flanked by blank lines, terminated by a period
(or `?`):

```
67:HOW MY NEW ACQUAINTANCES SPIN.
1058:WHAT DID SHE SEE WITH?
7392:A YEAR IN MONTANA.
```

Several articles add a **secondary title / genre tag** on the next non-blank line —
structurally a sub-title node fused to the title, not a separate designation:

```
2917:THE GREAT DOCTOR.
2919:A STORY IN TWO PARTS.
```
```
6610:LONDON FORTY YEARS AGO.
6612:FROM THE MEMORANDA OF A TRAVELLER.
```
```
4393:THE CHIMNEY-CORNER FOR 1866.
4396:VIII.
4398:HOW SHALL WE ENTERTAIN OUR COMPANY?      ← installment's own descriptive title
```

There is no separate numeric designation node anywhere at article level; title *is*
the identity surface a reader cites.

## 4. Body block vocabulary

Four+ distinct body-block kinds appear as **siblings under one issue**:

- **Prose essay** (running paragraphs) — e.g. the spider essay:
  ```
  69:The strictly professional man may have overcome his natural aversion to
  70:some of the most interesting objects of his study, such as snakes, and
  ```
- **Verse poem** (indented, line-broken, stanza-separated) — `THE MINER.`:
  ```
  1945:    Down 'mid the tangled roots of things
  1946:    That coil about the central fire,
  1947:    I seek for that which giveth wings,
  1948:    To stoop, not soar, to my desire.
  ```
  and `MY FARM: A FABLE.`:
  ```
  3833:    Within a green and pleasant land
  3834:      I own a favorite plantation,
  ```
- **Serialized-fiction prose** (narrative with chapter headers / dialogue) — the novel:
  ```
  4844:He went straight to the stable, and saddled Black Dick.
  …
  4849:He went back to her room, and came so suddenly that he caught her
  ```
- **Review / literary notice** (book citation header, then critical prose, often
  quoting verse from the reviewed book):
  ```
  8283:_The Poems of_ THOMAS BAILEY ALDRICH. Boston: Ticknor and Fields.
  8285:The things which please in these poems are so obvious, that we feel it
  ```
- **Footnote block** (article-internal apparatus; the transcriber moved footnotes to
  article end, lettered `[A]`):
  ```
  2611:FOOTNOTES:
  2613:[A] Bohn's edition of Humboldt's Personal Narrative, p. 134. Humboldt
  ```

Note a recursive subtlety: a *prose review block* itself **embeds verse** (it quotes
the reviewed poet at lines 8297–8302, 8332+). So a "review" node is not purely prose.

## 5. Matter (front / body / back)

- **Front matter = a masthead block, NOT a table of contents.** Probe for
  `CONTENTS`/`Table of Contents` returned **0 hits**, and every article title occurs
  **exactly once** in the file (TOC would duplicate them). The front matter is only the
  magazine name, subtitle, volume/date/number, the copyright line, and the
  transcriber's note (lines 49–62, quoted in §0). **There is no index node in this
  witness** — a direct contradiction of the "front matter is a TOC" hypothesis (see §10).
- **Body = the 13 articles** (§1), in reading order, no wrapping group node between
  issue and article.
- **Back matter = Project Gutenberg license** (lines 8852+), i.e. transcription
  apparatus, not part of the periodical. Special-cased / skipped.

The Reviews department (article 13) is the closest thing to back matter *within* the
periodical, but it is structurally a **sibling article**, set off by the same ALL-CAPS
title convention as every other article (`8280:REVIEWS AND LITERARY NOTICES.`) — it is
not special-cased; it simply has notice children. Its 11 notices:

```
8283:_The Poems of_ THOMAS BAILEY ALDRICH. Boston: Ticknor and Fields.
8500:_The United States during the War._ By AUGUST LAUGEL. New York:
8503:_The Civil War in America._ An Address read at the last Meeting of the
8578:_Hospital Life in the Army of the Potomac._ By WILLIAM HOWELL REED.
8635:_A History of the Gypsies: with Specimens of the Gypsy Language._ By
8673:_Eros. A Series of connected Poems._ By LORENZO SOMERVILLE, London:
8676:_Patriotic Poems._ By FRANCIS DE HAES JANVIER. Philadelphia: J. B.
8679:_The Contest: a Poem._ By G. P. CARR. Chicago: P. L. Hanscom.
8681:_Poems._ By ANNIE E. CLARK. Philadelphia: J. B. Lippincott & Co.
8737:_Thirty Years of Army Life on the Border._ By COLONEL R. B. MARCY, U. S.
8786:_Memoirs of a Good-for-Nothing._ From the German of JOSEPH VON
```

(Notices 8673–8681 are short, grouped together as a cluster of poetry notices; the
others are full single-book reviews. So even the department's children are ragged.)

## 6. Identity & cross-witness behavior

- **Canonical reference in practice = title + issue.** An article has no number and no
  page in this transcription, so it is cited as "*A Year in Montana*, Atlantic Monthly,
  Aug. 1866." Position-in-issue (article #12) is a derivable index, not how anyone
  refers to it.
- **The serialized fiction is the headline identity case.** Four articles in this one
  issue are *slices of works that span multiple issues*:
  - `GRIFFITH GAUNT; OR, JEALOUSY.` opens at **`CHAPTER XXXII.`** (line 4842) — chapters
    I–XXXI ran in earlier issues; later chapters run in later issues. The novel's
    identity (and its chapter numbering, XXXII–XXXVIII here) is **continuous across
    issues**, while this issue holds only one contiguous window of it.
  - `PASSAGES FROM HAWTHORNE'S NOTE-BOOKS.` / `VIII.` and `THE CHIMNEY-CORNER FOR 1866.`
    / `VIII.` are installment 8 of open-ended series; `THE GREAT DOCTOR.` / `II.` is
    part 2 of 2.
  - The **work** identity (Griffith Gaunt) is orthogonal to its **position** in *this*
    issue (article #10): position-path `(issue=Aug1866, article=10)` is local; the
    cross-issue thread is the **chapter/installment designation**. Here the designation
    carries identity information the issue-local position-path **cannot** express. This
    qualifies hypothesis (b): position-path is canonical *within a container*, but the
    serial's cross-issue continuity lives in the designation, not the path.

## 7. Authorship — PER-NODE, predominantly UNSIGNED

- **No bylines on any of the 12 individual articles.** A probe for `^By [A-Z]`,
  `^\s+By [A-Z]`, ` BY [A-Z]` across the body **before** the Reviews section (line
  <8280) returned **nothing**. Article ends carry no signature either — e.g. the spider
  essay closes straight into the next title (lines 1053→1058), and *A Year in Montana*
  ends with prose then immediately `REVIEWS AND LITERARY NOTICES.` (lines 8275→8280),
  with no author name between. This matches the period: Atlantic ran unsigned.
- **Where a name appears, it is in the title, not a byline field** — Hawthorne is named
  only inside the article title `PASSAGES FROM HAWTHORNE'S NOTE-BOOKS.` (line 3901),
  i.e. attribution fused into the title node, not a separate author attribute.
- **The only `By NAME` tokens belong to the *reviewed* books, not the reviewer.** E.g.
  `8500:_The United States during the War._ By AUGUST LAUGEL.` names Laugel as author of
  the *book under review*; the Atlantic reviewer who wrote the notice is **unsigned**.
  A naive byline parser would mis-attribute the review to Laugel.

So authorship is a **per-node, optional, frequently-null** field; and even where a name
is present it may be the *subject's* author, not the *node's* author.

## 8. Extraction cues

**Article-title cue:** an ALL-CAPS line, flanked by blank lines, ending in `.` or `?`:
```
67:HOW MY NEW ACQUAINTANCES SPIN.
1058:WHAT DID SHE SEE WITH?
```
**Sub-title cue:** the next non-blank ALL-CAPS or descriptive line (`A STORY IN TWO
PARTS.`, `FROM THE MEMORANDA OF A TRAVELLER.`).
**Installment cue:** a standalone Roman-numeral line `VIII.` / `II.` directly under the
title (lines 3904, 4396, 2923).
**Chapter cue:** `CHAPTER XXXII.` … (lines 4842 ff).
**Poem cue:** body lines uniformly indented (≥4 spaces), short, line-broken, with blank
lines between stanzas (lines 1945–1948).
**Review-notice cue:** a line opening with an italic-markup title `_..._` followed by
`By NAME` and `City: Publisher.` (lines 8283, 8500, 8578…).
**Footnote cue:** literal `FOOTNOTES:` then lettered `[A]`, `[B]` markers at article end
(lines 2611–2613).

**Traps:**
- **ALL-CAPS over-captures.** The same all-caps-line rule that finds titles also hits
  *internal* headings (`CHAPTER XXXII.`, `VIII.`, `A STORY IN TWO PARTS.`), the
  **masthead** (`ATLANTIC MONTHLY.`, `VOL. XVIII.--AUGUST, 1866.--NO. CVI.`, lines
  50/55), and the **license boilerplate** (all-caps legal lines 9039–9062). Title
  detection must exclude masthead, internal headers, and back-matter.
- **`FOOTNOTES:` is also all-caps** (lines 2611, 2910) and would be mistaken for a title.
- **Unsigned articles** mean authorship cannot anchor or delimit nodes.
- **`By NAME` inside Reviews is the reviewed book's author**, not a contributor byline —
  do not promote it to the notice's author.
- **No page numbers / running heads** survive in this PG text, so page-based segmentation
  is unavailable.
- Reviews has **two granularities** mixed: long single-book reviews and short grouped
  poetry notices (8673–8681) under one heading.

## 9. What this witness uniquely forces in the model

- **HETEROGENEOUS children are mandatory.** `Issue.children` is a list of articles of
  *different kinds* as siblings — prose essay, verse poem, serialized fiction (novel +
  short story), serialized non-fiction journal, serialized topical essay, and a
  reviews/notices department. The container **cannot type its children uniformly**;
  node-kind must be a **per-node attribute**, not inherited from the parent. (This
  repeats one level down inside the Reviews department, whose children are again ragged
  — long reviews vs. grouped short notices.) If the model assumes homogeneous children
  ("an issue is a list of essays", or any single child type), the poems, the novel
  installment, and the reviews department all mis-parse, and a single block-vocabulary
  for the whole container is impossible.
- **Variable-depth recursion.** Most articles are leaves (depth 2), but the novel adds
  a `Chapter` level and Reviews adds a `Notice` level (depth 3). The tree is ragged; a
  fixed-depth schema fails.
- **Cross-issue serialized identity.** A node's identity can **span containers**:
  *Griffith Gaunt* chapter XXXII here continues a work whose chapters I–XXXI and beyond
  live in *other issues*. Issue-local position-path identifies the *slice*; the
  **designation (chapter/installment ordinal)** is the thread that re-assembles the work
  across issues. The model needs a way to express "this article is installment N of an
  external serial" — position-path alone can't.
- **Per-node, optional, mostly-null authorship.** A model requiring a book-level author,
  or any author per node, breaks: nearly every node here is unsigned, and the one named
  contributor (Hawthorne) is named only inside the title string.
- **TOC is optional.** Front matter may be a bare masthead with **no index node** at
  all; the model must not assume a TOC sibling exists.

## 10. Open questions / contradictions

- **Contradicts hypothesis (e) (front/back are a TOC):** this witness has **no table of
  contents** (0 `CONTENTS` hits; each title appears once). Front matter is a masthead
  block only. *Open ruling:* should the extractor synthesize a TOC node from the
  detected articles, or model front matter purely as an opaque masthead block? (The
  print original likely had a cover/wrapper TOC that PG dropped — unverifiable from this
  file.)
- **Heterogeneity at two levels** (issue, and the Reviews department) — does the model
  treat "Reviews" as just another `Article` with notice children, or as a distinct
  `Department` kind? This file gives it the same title syntax as every other article,
  arguing for "just an article that happens to nest."
- **Sub-title vs. child node:** is `A STORY IN TWO PARTS.` / `FROM THE MEMORANDA OF A
  TRAVELLER.` an attribute of the parent title or a separate node? Designer's call;
  the text only shows it as a second title-styled line.
- **Three installment-numbering conventions in one issue** (`CHAPTER XXXII`, `VIII.`,
  `II.`) — the model's installment designation must be free-form, not a single scheme.
- **Reviewer anonymity vs. reviewed-author naming:** the only author names in the issue
  are the *reviewed* books' authors. Any author-extraction must distinguish "author of
  the node" from "author named within the node."
- **`THE MINER` / `MY FARM` poem authorship:** both verse pieces are unsigned here;
  whether the original printed an attribution is not recoverable from this transcription.
