# Structural close read — The Kybalion (Three Initiates, 1908)

> Specimen file: `engine/docs/structure_corpus/kybalion_14209.txt`. All line anchors
> below are from `grep -n` / `sed -n` over that file in this session. Counts are
> reported from commands, not memory.

## 0. Identification

- **Work**: *The Kybalion — A Study of The Hermetic Philosophy of Ancient Egypt and Greece*.
- **Author**: "Three Initiates" (a single collective pseudonym; see §7). Title page L29–L38:
  `THE KYBALION` (L29) … `BY` (L37) / `THREE INITIATES` (L38).
- **Date**: text dates itself `1912` / `COPYRIGHT 1912` (L46–48); the manifest/README label it 1908 (first edition). The file itself only asserts 1912.
- **Source**: Project Gutenberg eBook **#14209** (release 2004-11-29, updated 2024-10-28; L17–L21).
- **Size**: 3834 lines / 223,890 bytes (`wc`).
- **Work proper**: begins after the PG header at the START marker `*** START OF THE PROJECT GUTENBERG EBOOK THE KYBALION ***` (**L27**); the title-page block follows immediately (L29). The work ends at `FINIS` (**L3475**), then `*** END OF THE PROJECT GUTENBERG EBOOK THE KYBALION ***` (**L3484**). Skip L1–L26 (PG boilerplate header) and L3477+ (FINIS whitespace + PG license footer).

## 1. Container hierarchy

**Named levels (top to bottom):**

| Level | Name in text | Count | Depth |
|-------|--------------|-------|-------|
| 0 — grouping above chapter | *(none — no PART/BOOK/SECTION)* | 0 | — |
| 1 — chapter | `CHAPTER I` … `CHAPTER XV` | **15** | 1 |
| 1 — front-matter sibling | `INTRODUCTION` | 1 | 1 |
| 2 — intra-chapter subsection | numbered `Principle` subsections (Ch II only) | 7 | 2 |
| leaf — body block | aphorism / prose / list (see §4) | many | — |

**Max depth = 2, and the tree is RAGGED, not uniformly flat.** There is **no** part/book grouping above the chapter — `grep -nE "^PART|^BOOK|^SECTION|^Part "` returns nothing. That confirms the manifest's "0 grouping levels above the chapter." But "flat" holds only on the *grouping* axis: Chapter II nests a sub-level of 7 numbered Principle subsections (L405, L439, L463, L494, L554, L594, L621), each TOC-listed (L86–L92) and each with its own heading + aphorism + commentary. The other 14 chapters are depth-1 (chapter → blocks). So the chapter is **not** a uniform leaf; one chapter recurses.

**Chapter count, verbatim from the command** — `grep -n "CHAPTER"` returns exactly 15 lines:
L225, L382, L656, L794, L991, L1185, L1462, L1717, L2093, L2270, L2432, L2628, L2823, L2989, L3290. Roman numerals I–XV, strictly monotonic.

**Boundary example — chapter level** (L382–L386):
```
CHAPTER II

THE SEVEN HERMETIC PRINCIPLES

    "The Principles of Truth are Seven; ...
```
The prior chapter's last body line abuts it (L378 `and book in company. So mote it be!`) with only blank lines between — there is no rule, page number, or separator glyph at the boundary.

**Boundary example — intra-chapter subsection** (L405–L407):
```
1.  The Principle of Mentalism

    "THE ALL IS MIND; The Universe is Mental."--The Kybalion.
```

## 2. Designation system

- **Kind: Roman numeral**, one per chapter, on its own line: `CHAPTER I` (L225) … `CHAPTER XV` (L3290). Verbatim sample (L656, L991, L1462): `CHAPTER III`, `CHAPTER V`, `CHAPTER VII`.
- **Only-within-parent / sequential**: numerals run I→XV with no gaps and no reset; the designation is a pure ordinal of position.
- **Encodes position? Yes, fully.** Roman *N* = the *N*-th chapter. The designation is **derivable from the position-path** and carries no information the path lacks — the strongest possible support for demoting it to a read-only field (hypothesis b): here the designation is literally a rendering of the index.
- **A second, colliding designation axis exists**: the 7 Principles are designated by **Arabic 1–7**, and those same `1.`–`7.` numerals appear in THREE different structural roles — TOC sub-entries (L86–92), a plain in-body enumerated list (L411–L417), and the 7 subsection *headings* (L405–L621). Same designations, different node kinds (see §8 trap).
- A reader for this book needs a **Roman-numeral plugin** (chapter axis) **and** an **Arabic-ordinal plugin** (subsection axis) — distinct from PLL's ordinal-word reader and Pepys' date reader. Supports hypothesis (c).

## 3. Descriptive titles — designation ≠ title (KEY WITNESS)

**Confirmed and unambiguous.** Every chapter prints the Roman designation and the descriptive title as **two physically separate lines**, blank-line-separated:

```
CHAPTER I            (L225)
                     (L226 blank)
THE HERMETIC PHILOSOPHY   (L227)
```
Same shape at all 15 chapters (verified by printing L*n*..L*n+2* for every CHAPTER anchor): `CHAPTER IV` / `THE ALL` (L794/L796); `CHAPTER VII` / `"THE ALL" IN ALL` (L1462/L1464); `CHAPTER XV` / `HERMETIC AXIOMS` (L3290/L3292).

The Table of Contents (L75–L100) **also** carries both fields, designation + title together:
```
  I.    The Hermetic Philosophy        (L77)
  VII.  "The All" in All               (L94)
  XV.   Hermetic Axioms                (L100)
```
This is the cleanest witness in the corpus that **designation and title are separate fields, not a fused heading string**. A model that stores one heading line per node cannot (a) cite "Chapter I" independently of its title, nor (b) reconstruct the TOC, which prints the pair. Titles are ALL-CAPS at the chapter head but Title-Case in the TOC — i.e. a presentational variant of the *same* title datum, not two different strings.

## 4. Body block vocabulary

Observed typed blocks (ordered list within each chapter — hypothesis d):

1. **designation heading** — `CHAPTER VII` (L1462).
2. **title heading** — `"THE ALL" IN ALL` (L1464).
3. **attributed aphorism block** *(the distinctive type)* — set off by ~4-space indent, a quoted sentence, terminated by `--The Kybalion.`. Carries its **own attribute**: a citation to the source text.
4. **prose paragraph** — flush-left running text (e.g. L232+).
5. **enumerated list** — the seven Principles as a plain list (L411–L417): `    1. The Principle of Mentalism.` …
6. **node signature** — `THE THREE INITIATES.` closing the Introduction (L222).

**Verbatim attributed-aphorism block, with attribution (L407)** — Chapter II's opening axiom:
```
    "THE ALL IS MIND; The Universe is Mental."--The Kybalion.
```
A second, multi-line instance (Ch IX, L2098 region; here L465–L466) showing the attribution wraps:
```
    "Nothing rests; everything moves; everything vibrates."--The
    Kybalion.
```

**Count of attributed blocks**: whitespace-normalized `grep -oE '"--The Kybalion'` returns **39**. Every set-off attribution in the book points to the same source — `grep` for any `…"--<Capital>` attribution *other than* "The Kybalion" returns nothing; there are **no** Hermes/Trismegistus-attributed set-off blocks. So the attribution axis here has a single value, but it is a genuine per-block attribute (the aphorisms are the primary-source text the surrounding prose glosses). **Chapter XV ("Hermetic Axioms", L3290) is aphorism-dense**: its body is a run of aphorism + commentary pairs (e.g. L3292 opening axiom, then L3316 `"To change your mood or mental state--change your / vibration."--The Kybalion.`) rather than continuous prose — a body-vocabulary variation, not a structural one.

**Key extension to hypothesis (d)/(g):** the per-block datum here is a **citation/attribution to a quoted source**, which is a *different axis* from authorship of the node. The model needs an optional `attribution` (or `cites`) slot on a body block, separate from any `author` field.

## 5. Matter (front / body / back)

- **Front matter (rich)**, all between L29 and L224:
  - title-page block — `THE KYBALION` / subtitle / `BY` / `THREE INITIATES` (L29–L38);
  - epigraph — `"THE LIPS OF WISDOM ARE CLOSED, EXCEPT TO THE / EARS OF UNDERSTANDING"` (L41–L42);
  - copyright/publisher block (L46–L52);
  - **dedication** — `TO / HERMES TRISMEGISTUS … THIS LITTLE VOLUME … IS REVERENTLY DEDICATED` (L59–L72);
  - **Table of Contents** — heading `Table of Contents` (L75), entries L77–L100;
  - **Introduction** — heading `INTRODUCTION` (L102), body L104–L219, signed `THE THREE INITIATES.` (L222).
- **Body**: 15 chapters (L225–L3474).
- **Back matter: effectively none** — only `FINIS` (L3475); everything after is the PG license footer (boilerplate, not the work).

**Sibling-with-role-tag (hypothesis e): supported.** `INTRODUCTION` (L102) and `CHAPTER I` (L225) sit in the **same heading register** (bare ALL-CAPS line, blank-line-separated, no enclosing bracket). The source gives no structural marker that one is "matter" and the other "body" — only the *name* distinguishes them. So the natural model is: top-level body is an ordered list of heterogeneous siblings, each carrying a `role` tag (`front`/`chapter`), exactly as hypothesis (e) proposes. The Introduction is, structurally, the 0th sibling of the chapter run.

## 6. Identity & cross-witness behavior

- This is a **single-witness** specimen (one edition, no parallel text), so it cannot independently *prove* designation ≠ identity the way a cross-edition witness (Darwin) does. What it proves instead: the designation is a **pure function of position** (Roman *N* ↔ index *N*), so storing it as canonical identity would be redundant and fragile — position-path `body/<i>` is the obvious canonical key, designation a derived display field.
- **In-practice reference is by descriptive title, not Roman numeral**: the body prose refers to teachings by name ("the Principle of Rhythm", "the Chapter on Vibration"), and the aphorisms are cited as "The Kybalion", never as "Chapter IX, axiom 2". So neither the Roman designation nor a position-path is the *human* citation handle — the **title** and the **attribution** are. This nuances hypothesis (b): position-path is the right *internal* identity, but the citation field the model exposes should be the title/attribution, not the bare designation.

## 7. Authorship

- **Single book-level author**: "Three Initiates" (L38), a collective pseudonym. No chapter is individually attributed.
- **Node-level signature mechanism is present but non-divergent**: the Introduction closes with `THE THREE INITIATES.` (L222) — a signed front-matter node. It demonstrates the *shape* of per-node authorship (a node can carry its own signature) without demonstrating *divergence* (it is the same author). So hypothesis (g) is **mechanism-supported, not stress-tested** here — a signed-but-uniform case. The genuinely per-node datum in this book is the aphorism **attribution** ("The Kybalion"), which is a citation, not an author (see §4).

## 8. Extraction cues

**Markers a parser keys on (quoted from the raw text):**
- chapter start — a line matching `^CHAPTER [IVXLC]+$` (L225 `CHAPTER I` … L3290 `CHAPTER XV`).
- chapter title — the **next non-blank line** after the designation, ALL-CAPS (L227 `THE HERMETIC PHILOSOPHY`).
- aphorism block — an indented run ending in `--The Kybalion.` (regex `"--The Kybalion`), 39 occurrences.
- subsection (Ch II only) — `^[0-9]\.[[:space:]]+The Principle of` (7 hits, L405–L621).
- front-matter section — bare ALL-CAPS heading lines `Table of Contents` (L75, Title-Case here), `INTRODUCTION` (L102).
- node signature — `THE THREE INITIATES.` (L222).
- work bounds — `*** START OF THE PROJECT GUTENBERG EBOOK …` (L27) / `FINIS` (L3475) / `*** END …` (L3484).

**Traps:**
- **Designation reuse across roles** — `1.`–`7.` appear as TOC sub-entries (L86–92), as a plain in-body list (L411–417), AND as subsection headings (L405–621). A naive "numbered line = heading" rule will over-segment Chapter II. The headings are distinguished only by lacking a trailing period and being followed by a blank line + aphorism.
- **Wrapped attributions** — `--The Kybalion.` is often split across two lines (`…vibrates."--The` / `Kybalion.`, L465–466). A line-anchored regex misses ~3 of the 39 (single-line `grep -c` = 36 vs whitespace-normalized 39); the attribution detector must span line breaks.
- **No page numbers / no separators** — PG strips pagination; chapter boundaries have *only* blank lines + the ALL-CAPS heading, no rule glyph. There is no page-citation axis here (unlike PLL).
- **Title-case ↔ ALL-CAPS** — the same title is ALL-CAPS at the chapter head (L227) but Title-Case in the TOC (L77); a string-equality join of TOC↔heading fails without case folding.
- **`INTRODUCTION` looks like a chapter** — same register as `CHAPTER N`, but un-numbered. Role must be inferred from the name, not the typography.
- **PG boilerplate** — L1–26 header and L3477+ license must be excluded; the START/END sentinels and `FINIS` are the reliable cut points.

## 9. What this witness uniquely forces in the model

1. **Depth-can-be-zero *above* the chapter.** No part/book level exists. If the container model hard-codes a fixed `part → chapter` ladder, this book has an empty slot to invent or a level to fake. The grouping level must be **optional** — the chapter can be a direct child of the work. *(This is the manifest's headline role for this witness, and it holds.)*
2. **Ragged depth — recursion allowed but not required.** Chapter II nests 7 subsections; the other 14 don't. The model must permit a node to have child containers *or* be a block-leaf, decided per node, not per level. A uniform-depth schema breaks on Chapter II.
3. **Designation is a separate field from the title.** `CHAPTER I` and `THE HERMETIC PHILOSOPHY` are two lines and two TOC columns. Fusing them into one heading string loses the ability to cite the numeral alone and to render the TOC. This is the corpus's cleanest designation≠title case.
4. **Body blocks carry their own attribution.** The 39 aphorisms are typed blocks with a `cites = "The Kybalion"` attribute. Drop the attribute and they collapse into generic indented blockquotes, erasing the book's central distinction between primary-source axiom and editorial gloss.

**What breaks if ignored:** a fixed-depth, part-first tree can't place these flat chapters; a fused-heading model can't reproduce the TOC or cite a chapter by numeral; an attribution-blind block model loses the aphorism/commentary distinction that *is* the book.

## 10. Open questions / contradictions

- **"Flat chapters" is true only on the grouping axis.** The starting hypothesis ("FLAT chapters, no parts, the depth-can-be-zero witness") is **confirmed for levels above the chapter** but **contradicted as a claim that the chapter is a leaf**: Chapter II carries a TOC-listed sub-level (7 Principle subsections, L405–L628). The correct framing is *zero grouping levels above, ragged 0–1 levels below* — the witness simultaneously demonstrates "depth can be zero" (above) and "depth is per-node, not uniform" (below).
- **Is the Introduction body or front matter?** The source gives no bracket — only its name (`INTRODUCTION` vs `CHAPTER I`) and the absence of a Roman numeral distinguish it. This is exactly the role-tagged-sibling question (hypothesis e); the text supports "sibling with `role=front`" but cannot adjudicate whether the source author considered it *matter* vs *chapter 0*.
- **Single-value attribution axis.** All 39 set-off blocks cite "The Kybalion". This proves the *block carries an attribution slot*, but does not stress-test multi-source attribution (no rival "—Hermes" blocks). A model that conflates `attribution` with `author` would pass on this witness and fail elsewhere; flagging so the slot is kept distinct.
- **Per-node authorship is mechanism-only here.** The signed Introduction (L222) shows node-level signature with no author divergence — uniform, so (g) is supported but untested for the divergent case.
- **Date discrepancy**: file says 1912 (L46); manifest/README say 1908. Not a structural issue, but the identification field should cite what the text asserts (1912) and note 1908 as the bibliographic first-edition date.
