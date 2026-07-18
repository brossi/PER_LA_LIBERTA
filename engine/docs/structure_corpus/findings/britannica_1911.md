# Structural close read — Encyclopædia Britannica 1911 (11th ed., "England"–"English Finance" slice)

> Witness role: **non-positional headword/lookup/graph identity; per-article (in fact
> per-sub-section) signed authorship.** This is the corpus's hardest test of the working
> hypothesis that *identity = position-path*. Verdict below: position-path is the wrong
> canonical identity here; the canonical handle is a **headword string drawn from a
> namespace larger than the document**, plus an explicit **cross-reference edge set** the
> position-path cannot express.

All counts and quotes below come from `grep`/`sed`/`awk` and `Read` run against the file
this session; line anchors are 1-based into the raw `.txt`.

---

## 0. Identification

- **Work / edition.** *The Encyclopaedia Britannica*, Eleventh Edition — a single
  printed *slice* of one volume, not a whole book. Internal banner (lines 60–70):
  - L60 `ENCYCLOPAEDIA BRITANNICA`
  - L62 `A DICTIONARY OF ARTS, SCIENCES, LITERATURE`
  - L65 `ELEVENTH EDITION`
  - L68 `VOLUME IX, SLICE IV`
  - L70 `England to English Finance`
- **Alphabetical slice covered.** Begins **mid-alphabet** at `ENGLAND` (not the start of
  letter E) and ends **mid-alphabet** at `ENGLISH FINANCE` (not the end of E). *Both*
  document boundaries fall inside the letter E; the slice is a contiguous window of the
  global A→Z headword sequence, defined **by its two endpoint headword strings**, not by
  any natural unit of the work. The seven contained articles are enumerated up front:
  - L75 `ARTICLES IN THIS SLICE:`
  - L78–81 two-column list: `ENGLAND`, `ENGLAND, THE CHURCH OF`, `ENGLEFIELD, SIR
    FRANCIS`, `ENGLEHEART, GEORGE`, `ENGLEWOOD`, `ENGLISH CHANNEL`, `ENGLISH FINANCE`.
- **Source file + PG#.** `britannica_1911_england_32940.txt`, Project Gutenberg eBook
  **#32940** (L17 `Release date: June 21, 2010 [eBook #32940]`; L13 `Author: Various`).
- **Size.** 623,083 bytes (≈623 KB); **9,964 lines**.
- **How sampled.** Whole file read structurally. PG boilerplate skipped: header L1–59;
  license/footer from the `*** END OF THE PROJECT GUTENBERG EBOOK … ***` marker at **L9614**
  to EOF. Encyclopedic content runs ~L60–L6353 (`ENGLAND`) and L6358–~L9610 (the rest).
  Two transcriber's notes (L44–55) are load-bearing for extraction (see §4, §8): side-notes
  were *relocated to function as paragraph titles*, and one typo was corrected.

---

## 1. Container hierarchy

The tree is **ragged** — depth is a function of article length, not a fixed schema. Two
regimes coexist within the same flat alphabetical sequence:

**A. Short-stub regime (flat, depth 0 below the article).** Biographical and gazetteer
stubs are a single article node containing only ordered prose paragraphs, optionally a
bibliographic `See …` line and a signature. Example — the whole of `ENGLEWOOD`:
- L8088 `ENGLEWOOD, a city of Bergen county, New Jersey, U.S.A., near the Hudson`
- … runs unbroken prose to L8106; no sub-sections, no table, **no signature.**

**B. Long-article regime (nested, depth up to ~3 below the article).** `ENGLAND`
(L86–L6353), `ENGLAND, THE CHURCH OF` (L6358–…), and `ENGLISH FINANCE` (L8483–L9610) carry
internal structure. `ENGLAND` exhibits the deepest tree:

- **Level 0 — article (headword entry).** Boundary:
  - L86 `ENGLAND. Geographical usage confines to the southern part of the island`
- **Level 1 — numbered sub-section** (Roman/Arabic ordinal + ALL-CAPS title on its own
  line). Ten of them, verbatim boundaries:
  - L94 `1. TOPOGRAPHY.`
  - L457 `II. PHYSICAL GEOGRAPHY`
  - L1300 `III. GEOLOGY`
  - L1488 `IV. CLIMATE`
  - L1630 `V. ENGLISH PLACE-NAMES`
  - L1777 `VI. Population`  *(note: mixed-case title, not ALL-CAPS — marker is inconsistent)*
  - L2398 `VII. COMMUNICATIONS`
  - L2758 `VIII. INDUSTRIES`
  - L3335 `IX. TERRITORIAL DIVISIONS, &C.`
  - L3478 `X. LOCAL GOVERNMENT`
- **Level 2 — italic run-in head** (`_Title._--`, italics flattened to underscores in PG
  plain text; head runs into the first sentence). 12 found; boundaries:
  - L175 `_Hills._--As an introduction to the discussion of the natural regions`
  - L313 `_Coast._--The coast-line of England is deeply indented by a succession`
  - L2113 `_Religion._--In attempting to give a concise account of the religious`
  - L3539 `_The Administrative County._--The administrative county includes all`
- **Level 2′ — relocated side-note paragraph title** (a parallel, *block*-form head; the
  transcriber's note L46–47 explains these were marginal side-notes moved inline). E.g.:
  - L2139 `  The Church of England.`
  - L2360 `  Roman Catholics.`
  - L3537 `  The county and the county council.`
  - L3821 `  Finance.`

So the maximum container depth is **article › numbered-sub-section › run-in/side-note head
› paragraph** (≈3 grouping levels under the article) for `ENGLAND`, collapsing to **article
› paragraph** (0 grouping levels) for the four stubs. **Child counts are wildly asymmetric:**
`ENGLAND` ≈ 6,267 lines and ten level-1 sub-sections; `ENGLEWOOD` ≈ 19 lines and none.

---

## 2. Designation system

- **Kind: HEADWORD STRING** (proper-name / lemma), not an ordinal of any kind. The
  designation is the ALL-CAPS phrase that opens the article at column 0 and runs *into* the
  first sentence:
  - L7982 `ENGLEFIELD, SIR FRANCIS (c. 1520-1596), English Roman Catholic`
  - L6358 `ENGLAND, THE CHURCH OF. The Church of England claims to be a branch of`
- **Globally unique, and the real handle?** Yes for top-level entries: the headword is the
  alphabetization key and the thing every cross-reference names (see §6). It is unique
  *within the global A→Z namespace of the whole encyclopedia* — a namespace **larger than
  this document**: cross-references routinely point at headwords that are not in this slice
  (`DOMESDAY BOOK`, `WALES`, `REGISTRATION`, `EXCHEQUER`). So the headword is the canonical
  handle, but its uniqueness scope is the work, not the file.
- **Does reading-order position carry meaning?** Only *derivatively*. The articles sit in
  alphabetical order, so an article's ordinal position is a *consequence* of its headword's
  collation, not an independent fact. Position tells you a node's alphabetical neighbours
  (`ENGLEWOOD` follows `ENGLEHEART`) and nothing else; it carries **no citation weight**.
  Inserting one new headword would renumber every following article's position while
  invalidating **zero** references — because references are keyed on the string. The
  designation here is *not* demoted display metadata (the union hypothesis); it is the
  identity, and **position is the derived field.**

---

## 3. Descriptive titles

The headword **is** the title — there is no separate descriptive-title node. The headword
phrase doubles as (a) the alphabetization key, (b) the human-readable title, and (c) the
first words of the body sentence (run-in). Compare Kybalion (Roman designation *separate
from* an English title) or PLL (ordinal-word designation + translated title): Britannica
fuses designation and title into one string. The only "subtitle"-like material is
parenthetical gloss appended to the headword, still on the same line:
- L8111 `ENGLISH CHANNEL (commonly called "The Channel"; Fr. _La Manche_, "the`

---

## 4. Body block vocabulary

Observed typed blocks (each with a verbatim anchor):

- **Prose paragraph** — the default block (e.g. L8088 ff.).
- **Numbered sub-section heading** — `^([0-9]+|[IVXL]+)\. TITLE` (L94, L457, …; see §1).
- **Italic run-in head** — `^_Title._--` continuing into prose (L175, L2113, …).
- **Relocated side-note title** — indented short standalone line (L2139, L3537; transcriber
  note L46).
- **Statistical table** — Britannica's hallmark. **35** ASCII rule lines forming multiple
  table blocks. The counties area/population table:
  - L117 `  +---------------------+-------------+-------------+`
  - L122 `  | Bedfordshire        |    298,494  |    171,240  |`
  - L163 `  |        Total        | 32,544,685  | 30,807,232  |`
  Further table blocks open at L369, L412, L1813, L1875, L1978, L2030, … (climate,
  population, occupations).
- **Footnote apparatus** — `[N]` definitions gathered at the article's end. 24 such
  definition lines in the content region; the `ENGLAND` block runs L6280–L6353:
  - L6300 `  [5] Partly belonging to Scotland.`
  - L6304 `    Trent (170 m.), qq.v. for their numerous important tributaries.`
- **Cross-reference (typed inline element).** Two surface forms (see §6 for the graph):
  - parenthetical `(q.v.)` / plural `(qq.v.)` after a term: L8509 `…the great institution of the exchequer (q.v.) with its judicial…`
  - parenthetical `(see HEADWORD)`: L8511 `…the Domesday Survey (see DOMESDAY BOOK)--now`
  - block `See also HEADWORD; HEADWORD; …`: L2301 `See also ENGLAND, CHURCH OF; ANGLICAN COMMUNION; ECCLESIASTICAL`
- **Bibliographic "Authorities" line** — `See <Author>, _Italic Title_ (place, year)`; a
  *source* reference, **not** an inter-entry edge — disambiguate from the cross-ref `See`:
  - L2725 `  See H. R. De Salis, _Bradshaw's Canals and Navigable Rivers of England`
  - L8042 `  See _Dict. of Nat. Biog._ xvii. 372-374; but additional light has been`
- **Author signature** — parenthesized initials, right-aligned, ending a node (see §7).

Blocks carrying their own attributes: tables (column schema), footnotes (a back-reference
id), the signed sub-sections (a contributor id). This already breaks "body = ordered prose
blocks under one author."

---

## 5. Matter (front / body / back)

**The slice has no global front or back matter** — by construction, because it is a *window*
into the middle of a multi-volume work. There is no title page, no preface, no index, and —
critically — **no contributor key.** The only front-matter-shaped elements are
transcription/printing artifacts:
- the volume/slice banner (L60–70);
- the `ARTICLES IN THIS SLICE:` manifest (L75–81) — a transcriber-supplied local TOC, not
  part of the original page;
- transcriber's notes (L44–55).

The consequence for the model: the **contributor-initials key that would expand `(O. J. R.
H.)` into a person lives in the work's front matter, which is outside this document.** A
single-file extraction sees signatures it *cannot resolve* — node-level authorship is a
foreign-key into a table this file does not contain (see §7, §9).

---

## 6. Identity & cross-witness behavior — THE CENTERPIECE

**Claim under test (hypothesis b):** *position-path is the canonical identity; the
designation is demoted to a display field.* **On this witness that is refuted, and the
correct generalization is stronger than "swap in the headword."**

### 6.1 The canonical handle is the headword string, not a position

Every reference inside the corpus names a **headword**, never an ordinal or a page:
- L8509 `…the exchequer (q.v.)…` → "go look up the article headed EXCHEQUER."
- L8511 `…(see DOMESDAY BOOK)…`
- L3475 `groups of registration counties (see REGISTRATION).     (O. J. R. H.)`
- L2301 `See also ENGLAND, CHURCH OF; ANGLICAN COMMUNION; ECCLESIASTICAL`

A reader reaches `ENGLISH FINANCE` by **lookup on the string**, not by reading the six
preceding articles. There is no scenario in which a unit is cited as "article 7 of slice
IV" — that ordinal is not a stable or meaningful name.

### 6.2 Position is actively *fragile* here

- The two **document boundaries are themselves headword strings** ("England to English
  Finance," L70) — the file's extent is defined by lookup keys, not by ordinal range.
- The same `ENGLISH FINANCE` article sits at a completely different ordinal in a differently
  cut volume; its **identity is invariant under re-slicing**, its position is not.
- Inserting/removing any headword renumbers all following positions while leaving every
  cross-reference edge intact — the diagnostic signature of *string identity, derived
  position* (cf. the Darwin witness, where cross-edition renumbering proves position ≠
  designation; here the same lesson arrives through alphabetical insertion).

### 6.3 The cross-reference GRAPH — edges the position-path cannot carry

Counts this session: **19** `q.v.` + **1** `qq.v.` inline pointers; **3** `See [also]
HEADWORD` block cross-refs; plus inline `(see HEADWORD)` forms. These are **typed directed
edges between entries**, a structure orthogonal to the containment tree. Crucially, **most
targets resolve outside the slice** (`DOMESDAY BOOK`, `WALES`, `FEUDALISM`, `EXCHEQUER`,
`POOR LAW`, `ROMAN CATHOLIC CHURCH`). The edge set is therefore (a) not expressible as a
parent/child path, and (b) not closed over the document — it points into the global
namespace.

### 6.4 The corrected identity model this forces

It is **not** "headword replaces position-path." It is:

1. **Canonical identity = a non-positional string key** (the headword) **drawn from a
   namespace larger than the document** (the whole encyclopedia's A→Z space).
2. **Position-path survives only as a *within-document container address*** — useful to
   locate `ENGLAND › II. PHYSICAL GEOGRAPHY › _Hills._`, useless as a citation handle and
   not stable across editions/slicings.
3. **A first-class edge set (graph)** must coexist with the tree; tracking that assumes a
   pure tree silently drops every `q.v.`.

The headword is not even a perfect *local* key (see the run-in sub-headword trap in §8), so
the model needs an explicit, possibly hierarchical **designation namespace** with edges —
not a single integer path.

---

## 7. Authorship — PER-NODE, and finer than per-article

Articles are **signed**, confirming hypothesis (g) — and the witness *extends* it: signing
is at the **sub-section** level, finer than the article, and is **sparse**.

- Signature format: parenthesized space-separated single-letter initials, right-aligned,
  terminating a node. **13** signatures total; **9** distinct contributors:

  | initials | count | example anchor |
  |---|---|---|
  | `(O. J. R. H.)` | 4 | L3475, L8232 |
  | `(H. R. M.)` | 2 | L1297, L1627 |
  | `(J. A. H.)` | 1 | L1485 |
  | `(W. A. P.)` | 1 | L2395 |
  | `(A. F. P.)` | 1 | L8046 |
  | `(G. C. W.)` | 1 | L8083 |
  | `(D. J. M.)` | 1 | L8294 |
  | `(H. M. R.)` | 1 | L8473 |
  | `(C. F. B.)` | 1 | L9602 |

- Verbatim signatures in context:
  - L1297 `  suggestive rather than determinative.     (H. R. M.)`  *(ends ENGLAND §III GEOLOGY)*
  - L2395 `  Manchester,--the Lutheran, and the Armenian churches.     (W. A. P.)`  *(ends ENGLAND’s Religion run-in head)*
  - L8083 `  (1902).     (G. C. W.)`  *(ends ENGLEHEART)*
- **Per-node, not per-book:** the single article `ENGLAND` carries *seven* signatures by
  *four* different contributors (L454 `(O. J. R. H.)`, L1297 `(H. R. M.)`, L1485 `(J. A.
  H.)`, L1627 `(H. R. M.)`, L2111 `(O. J. R. H.)`, L2395 `(W. A. P.)`, L3475 `(O. J. R.
  H.)`). Authorship attaches to the **sub-section** node.
- **Sparse:** the long `X. LOCAL GOVERNMENT` span (L3478–~6353) and the stub `ENGLEWOOD`
  carry **no** signature. Authorship is an *optional* node attribute, not a guaranteed one.
- **Many-to-many via a foreign key:** the same initials recur across different articles
  (`(O. J. R. H.)` signs both an `ENGLAND` sub-section and `ENGLISH CHANNEL`, L8232) — i.e.
  the signature is a key into a contributor table. **That table is not in this slice** (§5),
  so the initials are unresolvable from this file alone. (Externally these are 11th-edition
  contributors — e.g. O.J.R.H. = O. J. R. Howarth — but the file gives only the key.)

---

## 8. Extraction cues

| Element | Marker in THIS raw text | Anchor |
|---|---|---|
| Article headword | column-0 ALL-CAPS phrase, comma-separated inversions allowed, **run into the first sentence** by `. ` / `, ` / ` (` | L86, L6358, L7982 |
| Numbered sub-section | `^([0-9]+|[IVXL]+)\. ` + title line | L94, L457, L3478 |
| Italic run-in head | `^_Title._--` (PG underscores = italics) | L175, L3539 |
| Side-note title | indented short standalone line, blank-line delimited | L2139, L3537 |
| Inline cross-ref | `(q.v.)`, `(qq.v.)`, `(see HEADWORD)` | L8509, L6304, L8511 |
| Block cross-ref | `See also HEADWORD; HEADWORD; …` | L2301 |
| Authorities/biblio | `  See <Author>, _Title_ (place, year)` | L2725, L8042 |
| Signature | `(X. Y. Z.)` initials, right-aligned, node-terminal | L1297, L8083 |
| Table | `+---…---+` rule lines + `|`-delimited rows | L117–164 |
| Footnote def | `^  \[N\] ` block at article end | L6300 |

**Traps (real, observed):**

1. **Slice boundaries are mid-alphabet** — the file begins *and* ends inside letter E
   (`ENGLAND` … `ENGLISH FINANCE`). A parser must not assume the first article is the
   letter's first or the last is its last; there is no global front/back matter to anchor on.
2. **Run-in headword for a sub-biography that is NOT a top-level entry.** Inside `ENGLEHEART,
   GEORGE`, a nephew's mini-biography opens with a column-internal ALL-CAPS name:
   - L8073 `His nephew, JOHN COX DILLMAN ENGLEHEART (1784-1862), also a miniature`
   This looks exactly like a headword but is a *child* of the entry. The ALL-CAPS-name
   heuristic over-segments here.
3. **Wrapped ALL-CAPS cross-reference tails mimic headwords.** A `(see ALL CAPS HEADWORD)`
   that wraps puts an ALL-CAPS fragment at column 0, indistinguishable by shape from an
   article start:
   - L2378 `ROMAN CATHOLIC CHURCH).`
   - L3466 `POOR LAW).`
   - L7430 `QUEEN ANNE'S BOUNTY).`
   A naïve `^[A-Z]{2,}` rule yields false article boundaries here (verified: this regex
   produced 6+ false hits this session). Disambiguate by requiring run-in body text and a
   preceding blank-line gap, and by checking the manifest at L78–81.
4. **`See` is overloaded** — inter-entry cross-ref (L2301) vs bibliographic source (L2725).
   Only the former is a graph edge.
5. **Inconsistent sub-section markers** — Arabic `1.` (L94) then Roman `II.`…`X.`; one title
   is mixed-case (`VI. Population`, L1777) while the rest are ALL-CAPS.
6. **Regnal/enumeration ordinals run *into* sentences**, not as headings — `VIII.
   Elizabeth, again, presents…` (L8842) and `(1) The royal estates…` (L8551) are prose, not
   structural nodes; `ENGLISH FINANCE` is largely continuous prose, so it has *less* nesting
   than `ENGLAND` despite being long.

---

## 9. What this witness uniquely forces in the model

1. **Non-positional, namespaced string identity.** Identity must be a **designation key**
   (headword) whose uniqueness scope is the *work*, not the file — explicitly larger than
   the extracted document. A position-path is at best a within-document container address
   and at worst (across editions/slicings) actively misleading. *If the model hard-codes
   "identity = position-path,"* every cross-reference target silently becomes unaddressable
   and re-slicing the volume re-identifies every article.
2. **A cross-reference edge set as a first-class structure** alongside the containment tree,
   with edges that **point outside the document**. *If the model assumes a pure tree,* it
   drops all 20 `q.v.`/`qq.v.` pointers and both `See also` graphs, losing the encyclopedia's
   defining structure (an article *is* its lookup neighborhood, not its alphabetical
   neighbors).
3. **Per-node, optional, foreign-keyed authorship.** Author is a node attribute that (a)
   attaches below the article (sub-section), (b) is frequently absent, and (c) is a *key*
   (initials) into a contributor table that may not be in scope. *If the model assumes one
   book-level author,* it loses the seven-author internal structure of `ENGLAND` and cannot
   represent "this paragraph is by O.J.R.H., that one by W.A.P."
4. **Ragged depth within one flat sequence.** The same model must hold a depth-0 stub and a
   depth-3 compound article as siblings — extraction depth is data-driven, not schema-fixed.
5. **Non-prose body blocks as the norm, not the exception** — statistical tables and a
   footnote apparatus are core encyclopedic content; a prose-only body model loses the
   tables that *are* the article's payload.

---

## 10. Open questions / contradictions

- **Contradiction to the union hypothesis (b):** here the designation is the identity and
  position is the derived field — the inverse of the working model. Needs a ruling on
  whether the tracking layer admits a **designation-as-identity** mode (string key + edges)
  distinct from the position-path mode used by linear works (PLL, Pepys).
- **Namespace scope.** The headword key is unique only over the *whole* encyclopedia, and
  the file is a slice. Does the model identify nodes within a document, or within a larger
  *work* the document is a fragment of? This witness only makes sense at the work level.
- **Unresolvable foreign keys.** Signatures and most cross-ref targets resolve against
  tables/articles *not in this file*. How should extraction represent a *dangling*
  reference/attribution (initials with no key, `(see WALES)` with no WALES in scope)? Pure
  single-file extraction cannot resolve them; it can only record the raw key + mark it
  external.
- **Two parallel level-2 head styles** (`_italic run-in_` vs relocated block side-note) —
  are these one logical level rendered two ways, or two distinct node types? The transcriber
  *manufactured* the side-note form (note L46), so this distinction is partly an artifact of
  this transcription, not the 1911 page.
- **Sub-section vs entry continuity of authorship.** `ENGLAND`'s `X. LOCAL GOVERNMENT` is
  unsigned — is it unattributed, attributed in omitted matter, or covered by the article's
  general editor? Undecidable from the slice.
