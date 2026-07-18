# Structural close read — The Diary of Samuel Pepys (Wheatley ed., complete)

> Specimen for the book-agnostic document-structure model. All structural claims
> below are anchored to `grep`/`sed` output run this session against the file; line
> numbers are 1-indexed into `pepys_diary_complete_4200.txt`. The file was **sampled,
> not read whole** (see §0).

## 0. Identification

- **Work:** *The Diary of Samuel Pepys — Complete* (single combined file assembling the whole diary, 1660–1669).
- **Author / diarist:** Samuel Pepys (title-page line 7; metadata line 13 of head).
- **Transcriber:** Rev. Mynors Bright (from the Pepysian shorthand MS) — head lines 11–13, 46–53.
- **Editors:** Lord Braybrooke (notes) + Henry B. Wheatley F.S.A. ("Edited With Additions By", head lines 17, 64–66). Wheatley signs the front matter "H. B. W." (lines 203, 1695).
- **Edition:** George Bell & Sons, London, **1893** (title page lines 68–72); editorial back-matter dates the issue "First issue of this edition June, 1896. Reprinted 1897." (line 101662).
- **Source file + PG#:** Project Gutenberg **eBook #4200** (line 22), release Oct 31 2004, "Most recently updated: August 9, 2016". Single PG envelope: `*** START ***` line 32, `*** END ***` line 102985.
- **Size:** 6,800,848 bytes (6.8 MB), **103,335 lines**.
- **How sampled (explicit):**
  - Read the head (lines 1–120) — PG header, title page, start of Wheatley's PREFACE.
  - `grep -n` for: PG seams; `VOLUME|PART|BOOK`; bare-year lines `^16\d\d$`; ALL-CAPS month headings `^(JANUARY…DECEMBER) 16…`; bare-ordinal day lines `^\d{1,2}(st|nd|rd|th|d)\.`; month-named first-of-month lines; `--[` inline footnote splices; indented `^\s+\[` footnote blocks; `INDEX|CONTENTS|APPENDIX`.
  - `sed -n` reads at the **first** month (APRIL 1660 region, 4681–4760; JANUARY 1659-1660 at 1701), a **middle** month (JULY–NOVEMBER 1664, 44051–47267), and the **last** month (MAY 1669, 101012–101035; final entry + sign-off 101600–101655).
  - Read the front-matter heading list (40–1701) and the end matter (101652–101662).
  - I did **not** read the ~100k lines of diary body; counts below are from `grep -c`.

## 1. Container hierarchy

**The manifest hypothesis `book › volume › year › month › DATED day-entry` is REFUTED for this witness at two levels.** What is physically *marked* in this combined file is only **three** levels:

```
book (the whole diary)
└─ month-heading  ← carries the year; the only mid-level container that is marked
   └─ day-entry   ← prose, designated by a (often partial) date
```

**Max *marked* depth = 3, not 4/5.** Two predicted levels have **no marker** in this file:

- **VOLUME — absent.** `grep -nE "VOLUME|^PART |^BOOK |FIRST VOLUME"` → **0 hits**. This "Complete" edition flattened the multi-volume seams; the diary runs continuously, one PG envelope, no per-volume front matter or PG re-headers inside.
- **YEAR — not a marked container; it is *embedded in the month heading* and otherwise only inferable.** `grep -nE "^16[0-9][0-9]$"` → **0 hits** (no standalone year heading line). The year exists only as a field inside each month heading (`APRIL 1660`) and must be *derived* to bucket months into calendar years.

So `volume` and `year` are **logical / derived** levels a parser would have to *synthesize*, not parse — `volume` is unrecoverable from this file at all, and `year` is recoverable only from the month-heading's embedded year (and is complicated by Old-Style rollover, §2/§8).

**Ragged?** Yes within each marked level: months hold a variable number of day-entries; day-entries hold a variable number of editorial footnote blocks (0..n); the day-entry's date designation has variable shape (§2).

**Verbatim boundary example per level:**

- **book (open):** line 7 `THE DIARY OF SAMUEL PEPYS M.A. F.R.S.` ; (close) line 101652 `END OF THE DIARY.`
- **month — first:** line 1701 `JANUARY 1659-1660` ; **middle:** line 44051 `JULY 1664` ; **last:** line 101012 `MAY 1669`. (113 month headings total — §8.)
- **day — first under APRIL 1660:** line 4683 `April 1st (Lord’s day). Mr. Ibbott preached very well.…` ; **next:** line 4696 `2d. Up very early, and to get all my things and my boy’s packed up.` ; **last entry of the diary:** line ~101630 `31st. Up very betimes, and so continued all the morning with W. Hewer,…`

## 2. Designation system

**Kind = DATE.** Every day-entry is designated by a calendar date and nothing else (no title — §3).

**Two surface forms (verbatim):**

1. **First entry of a month** carries the month name:
   - `April 1st (Lord’s day).` (4683) — month + ordinal + optional weekday parenthetical
   - `May 1st.` (101014) — month + ordinal only
   - `April 1st, 1661.` (13070), `July 1st, 1665.` (52729), `October 1st, 1666.` (66846), `May 1st, 1668.` (91620) — **4 cases** that also repeat the **year** inline.
2. **Every subsequent entry** is a **bare ordinal** (this is the bulk — 2,784 entries, §8):
   - `2d. Up very early,` (4696) · `3d. Late to bed.` (≈4716) · `4th. This morning I dispatch many letters` (4751) · `31st. Up very betimes,` (last entry).

**PARTIAL date — the key witness.** Line 4696:

```
2d. Up very early, and to get all my things and my boy’s packed up.
```

`2d.` is meaningless on its own. It resolves **only** against its parent heading two lines above, line 4681:

```
APRIL 1660
```

→ the entry's true date is *2 April 1660*, but neither the month nor the year is in the designation. The designation is **not self-contained; it needs parent context to mean anything.**

**Globally unique? NO.** The same designation recurs once per month across ten years:
- `2d.`/`2nd.` occurs **98×** (14 + 84, §8); `15th.` **96×**; the bare ordinal repeats in every month it appears.
- Even the month-named `April 1st…` recurs every April. A designation is unique **only within its parent month**, never globally.

**Self-contained? NO** for the 2,784-entry majority (bare ordinals); **partially** for the 113 first-of-month entries (they name the month but usually not the year). The diary's closing sign-off is the one fully self-contained date: `May 31, 1669.` (line ≈101648), written as a signature, not as an entry head.

**Encodes position?** Only *within-month order* (the ordinal). It does **not** encode the year or any volume position — and, critically, the **year grouping is recoverable only by reading the DATE** (there is no year container, §1). So here the designation is **load-bearing for reconstructing a logical level**, not purely decorative (see §6 / §9 — this nuances hypothesis (b)).

## 3. Descriptive titles

**None.** Day-entries have a date designation and immediately a prose body; there is no title slot. The front/back-matter sections do have titles (`PREFACE`, `PREVIOUS EDITIONS OF THE DIARY.`) but those are editorial matter (§5), not diary entries. Confirms the hypothesis that this corpus's body nodes are title-less and designation-only.

## 4. Body block vocabulary

| Block type | How marked | Count / anchor | Author |
|---|---|---|---|
| **prose day-entry** | date token at line start, then prose paragraph(s) | 2,784 bare-ordinal + 114 month-named line-starts | Pepys |
| **editorial footnote — standalone** | indented bracketed block `^\s+[ … ]` | **784** opening lines | editor (Braybrooke/Wheatley) |
| **editorial footnote — inline splice** | `--[ … ]--` injected mid-sentence | **233** | editor |
| **front/back matter prose** | titled ALL-CAPS heading + prose | §5 | Wheatley |
| **closing sign-off** | full date line `May 31, 1669.` | 1×, ≈101648 | Pepys |

**Verbatim — standalone footnote** (inside the April 4th entry, lines 4727–4742, abridged):

```
     [This is the first mention in the Diary of Admiral (afterwards Sir
     William) Penn, with whom Pepys was subsequently so particularly
     intimate.  At this time admirals were sometimes styled generals.
     …dying there, September 16th, 1670, aged forty-nine, was buried in
     the church of St. Mary Redcliffe, in Bristol…]
```

**Verbatim — inline splice** (lines 1995–1997):

```
4th. Early came Mr. Vanly--[Mr Vanley appears to have been Pepys’s
landlord; he is mentioned again in the Diary on September 20th,
1660.]--to me for his half-year’s rent…
```

**Blocks carrying their own attributes:** the **day-entry** carries the date as a leading attribute token (its designation). **Footnotes carry no date** — they attach to a *point inside* a day-entry (an inline anchor or an immediately-following bracket), so they are *child blocks of an entry*, not dated siblings. This is a second, editor-authored block class interleaved into the diarist's prose — a strong argument for a typed-block body list where block type and authorship are per-node (§7).

## 5. Matter (front / body / back)

- **Front matter (editor, Wheatley):**
  - `PREFACE` (line 39) → signed `H. B. W.` (line 203).
  - Introduction / Life-of-Pepys prose, including the subsection `PREVIOUS EDITIONS OF THE DIARY.` (line 211), running to a second `H. B. W.` signature (line 1695), immediately before the first month heading (1701).
- **Body:** the dated diary, `JANUARY 1659-1660` (1701) → `MAY 1669` (101012), ending `END OF THE DIARY.` (101652).
- **Back matter (editor):** a closing `PREFACE` *moved to the end*, flagged with an editor's note (lines 101657–101660):

  ```
  PREFACE

                [This moved, by the editor, to the end
                where it seems to fit more comfortably.]

  First issue of this edition June, 1896. Reprinted 1897.
  ```

  then the PROJECT GUTENBERG license (102999+).
- **Index / contents:** `grep -nE "^(INDEX|CONTENTS|TABLE OF CONTENTS|APPENDIX)"` → **0 hits**. This combined file has **no index or TOC** (printed multi-volume Wheatley sets do; this concatenation drops them).
- **Siblings or special-cased?** Front and back matter sit at the **book level as siblings of the body**, but they are a **different matter-class and different author** (editor, not diarist) — and the back matter is explicitly *relocated* editorial content, not a chronological tail. So: siblings of the body in tree position, but flagged as non-body matter. The hypothesis "front/back matter are siblings" holds *with* an added requirement that nodes carry a matter-class (front/body/back) and an author distinct from position.

## 6. Identity & cross-witness behavior

- **How an entry is canonically *referenced* in scholarship and in the text's own cross-links:** by **date** — e.g., the footnote at 1995–1997 points the reader to "the Diary on September 20th, 1660." A reader cites "Pepys, 2 April 1660," never "book›month 4›entry 2."
- **Why date is a poor *identity key* (supports hypothesis (b), with a caveat):**
  1. **Not globally unique** — `2nd.`/`2d.` resolves to 98 distinct entries (§2); even `April 1st` recurs yearly.
  2. **Partial / parent-dependent** — 2,784 of ~2,900 entries are bare ordinals that don't even name their month (§2).
  3. **Surface-unstable** — the *same* date is written `2d.` early and `2nd.` later (§8); dual-dated years appear as `1659-1660`, `1660-1661`, *and* abbreviated `1660-61` (§8). The string is not a stable key.
  4. **Old-Style ambiguity** — `JANUARY 1659-1660` is *one* month with *two* year numbers; a naive `(year, month, day)` key has to choose which year.
  → A **position-path** (`body / month[idx] / entry[idx]`, or `… / footnote[idx]`) is stable across all of these and is the right canonical identity.
- **Caveat / extension (this is the contradiction for hypothesis (b)):** the date is **not** purely a read-only display field here. Because there is **no year container** (§1), the **only** signal that buckets months into calendar years is the year embedded in the DATE designation. A pure positional path (`book›month[i]›day[j]`) **loses the calendar-year grouping** unless the DATE reader supplies it. So the designation is demoted for *identity* but remains **load-bearing for deriving a logical level** the markup never encodes. The model must let a designation-reader *contribute structure* (year buckets), not merely render a citation.

## 7. Authorship

Two authors interleaved at the block level, not the document level:
- **Diarist — Samuel Pepys:** all day-entry prose and the closing sign-off `May 31, 1669.`
- **Editor — Wheatley (with Braybrooke's notes):** all 784 standalone + 233 inline footnotes (§4), the front-matter PREFACE/Introduction (signed `H. B. W.`, lines 203/1695), and the relocated back-matter PREFACE with its bracketed editorial directive (101659). Authorship is therefore **per-node** and even **per-sub-span** (an inline `--[…]--` splice is editor-authored *inside* a diarist sentence). Confirms hypothesis (g) strongly, and pushes it further than "per-node" — to *per-span within a node*.

## 8. Extraction cues

**Markers a parser keys on:**
- **Month/year heading:** a line matching `^(JANUARY|FEBRUARY|…|DECEMBER) 16\d\d([-/]\d{2,4})?$`, ALL-CAPS, isolated. **113** such lines.
- **Day-entry, first-of-month:** line starting `^(January|…|December) \d{1,2}(st|nd|rd|th|d)\b` (optionally `… , 16\d\d` or `(… day)`). **114** line-starts.
- **Day-entry, subsequent:** line starting `^\d{1,2}(st|nd|rd|th|d)\.\s`. **2,784** lines.
- **Standalone footnote:** indented bracket block `^\s+\[ … \]` (multi-line). **784** openings.
- **Inline footnote:** `--\[ … \]--` mid-sentence. **233**.

**Traps (verified this session):**
1. **Partial dates** — 2,784 entries (≈96%) are bare ordinals (`2d.`, `31st.`) carrying neither month nor year; they inherit both from the nearest preceding month heading. A parser MUST resolve them against parent context.
2. **Ordinal-abbreviation drift** — early volumes use the `-d` form, later switch to `-nd/-rd`: `2d.`=14 vs `2nd.`=84; `3d.`=10 vs `3rd.`=86; `22d.`=6 vs `22nd.`=92. Accept **both**. (`^1st\.` = **0** — the 1st of a month is *always* written month-named, never as a bare `1st.`; useful invariant.)
3. **Dual-dated (Old-Style) years, inconsistent format** — heading years appear as `1659-1660`, `1660-1661`, **and** abbreviated `1660-61` (`FEBRUARY 1660-61`, line 12145). Jan/Feb/early-March of a year carry the dual form; April onward carry a single year (OS year began 25 March). Normalising to a single calendar year requires knowing this.
4. **Year repeated inline on 4 first-of-month entries** (`April 1st, 1661.`, etc.) — these inflate naive first-of-month counts and must not be mistaken for a different block type.
5. **No year or volume heading** — do **not** expect a level marker for either; year must be lifted from the heading string, volume is simply gone.
6. **Footnotes interrupt entries** — an inline `--[…]--` can split a sentence (1995–1997); a standalone `[…]` block sits *between* paragraphs of one entry (4727–4742). Naive paragraph-splitting will mis-attribute footnote text to the diarist and break date-run detection.
7. **No per-volume PG seam** — unlike multi-file Gutenberg concatenations, there is exactly one `*** START ***`/`*** END ***` pair (32 / 102985); no internal PG re-headers to split on.
8. **Run-together entries** — entries are separated only by the date token at a paragraph start, not by blank-line counts or rules; the date line *is* the only boundary.
9. **Editorial back-matter masquerades as front-matter** — a second `PREFACE` appears *after* `END OF THE DIARY.` with a bracketed "[This moved, by the editor, to the end…]" directive (101657–101660); matter-class can't be inferred from heading text alone.

## 9. What this witness uniquely forces in the model

- **Marked depth here is 3, but the *logical* model needs more — and two levels are unmarked.** The model cannot assume every container level is recognizable from a marker. It needs (a) **derived/virtual containers** (year — synthesized from the designation; volume — absent here, present in volume-split siblings of this same work) and (b) tolerance for a witness that *flattens* a level the manifest expected. **If ignored:** a parser that hard-codes `book›volume›year›month›day` finds no volume and no year markers and either fails or mis-nests every entry.
- **A genuinely parent-dependent designation.** 96% of nodes carry a designation (`2d.`) that is unresolvable without walking to the parent heading. **If ignored:** entries get duplicate/partial keys and cross-references like "the Diary on September 20th, 1660" can't be resolved.
- **Date-as-designation that is also structure-bearing.** The DATE is the right thing to *demote from identity* (non-unique, partial, surface-unstable) — but it is the *only* source of the year grouping (no year container). So the designation-reader plugin (a DATE reader) must be able to **emit a derived grouping key**, not just a citation string. **If ignored:** the model loses the calendar-year layer entirely, or wrongly assumes position-path encodes everything the designation does.
- **Per-span heterogeneous authorship inside one node.** Editor footnotes interleave with — and even splice mid-sentence into — diarist prose. **If ignored:** authorship attribution and any "diarist-only" extraction (e.g., word counts, translation) silently ingest editorial text.
- **Old-Style calendar irregularity as first-class.** `JANUARY 1659-1660` is one month with two year numbers; the year begins in March. **If ignored:** chronological sorting and year-bucketing are wrong for every Jan–Mar entry.

## 10. Open questions / contradictions

1. **Hypothesis (b) is too strong here.** "Designation is just a read field" holds for *identity* but **not** for *structure*: in this file the date is the sole carrier of the (unmarked) year level. Recommend: designation-readers may *contribute derived grouping keys*, kept separate from canonical identity.
2. **Manifest hypothesis refuted at two levels** (`volume`, `year`): the "Complete" file has **no volume seams** and **no year headings** — depth is 3 marked, not 4/5. The deepest-witness expectation should come from the *volume-split* editions of this same work, not this combined file. (Flagged for the manifest.)
3. **113 month headings vs 114 month-named day line-starts** — the +1 is explained by the 4 inline-year first entries plus normal first-of-month entries; the exact reconciliation (whether any month's first entry is *not* on the 1st, or a stray line-start full date) was not exhaustively walked. Minor; affects first-of-month heuristics only.
4. **Index/TOC absent in this file** — printed Wheatley volumes carry a substantial index; whether the model should treat "index" as an expected-but-optional back-matter sibling (present in volume editions, dropped in the combined file) is a cross-witness question best settled against a volume-split specimen.
5. **OS dual-year normalization policy** — `1659-1660` / `1660-61` / `1660-1661`: which integer the canonical year-bucket uses (OS vs NS) is a model decision the data does not settle on its own.
