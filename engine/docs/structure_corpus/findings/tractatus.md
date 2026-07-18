# Structural close read — Tractatus Logico-Philosophicus (Wittgenstein, Ogden 1922; TeX source)

> Evidence base for `ENGINE_STRUCTURE_PLAN.md`. Every line anchor and count below
> comes from commands run this session against the file named in §0, not from memory.

## 0. Identification

- **Work / author / translator / introducer.** *Tractatus Logico-Philosophicus* by Ludwig Wittgenstein; English translation by C. K. Ogden (1922 Kegan Paul edition); introduction by Bertrand Russell. The PG header records all three roles verbatim (lines 15–21):
  - L15 `% Author: Ludwig Wittgenstein`
  - L19 `% Contributor: Bertrand Russell`
  - L21 `% Translator: C. K. Ogden`
- **Source file.** `/Users/ben_mpa/LLM/PER_LA_LIBERTA/engine/docs/structure_corpus/wittgenstein_tractatus_5740.tex` — **Project Gutenberg #5740** (`\def\ebook{5740}`, L32; release "October 22, 2010", L23).
- **Format.** LaTeX/TeX source (`\documentclass[12pt,oneside]{book}`, L114), encoded ISO-8859-1 (L25). PG #5740 ships only TeX + PDF — there is no plain-text cache edition — so structure is carried in **TeX macros**, not headings.
- **Size.** 380,896 bytes (SOURCES.md row, confirmed on disk) / **11,738 lines**.
- **Language.** This file is a **bilingual edition**: the full English (Ogden) text *and* the full German original (`Logisch-philosophische Abhandlung`) are both present, English first (body L1318–6250), German second (body L6330–11372). The PG header's `% Language: German` (L27) describes the original; both languages are fully typeset here.
- **How sampled.** `grep -c`/`grep -n`/`grep -oE` over the proposition macros; extracted all 526 English number tokens to a temp file and analysed the dotted-decimal tree in Python (depth distribution, parent/ancestor connectivity, duplicates, per-top-node child counts); read the macro definitions (L191–300) and ~10 proposition spans in context for verbatim quotes.

## 1. Container hierarchy — the recursive proposition tree

The body is **not** a nested container tree in the document source. It is a **single flat LaTeX list** whose items each carry a hand-written dotted-decimal label; the recursive tree is encoded **entirely in the decimal string**, never in `\begin`/`\end` nesting:

```
361  % define new list type for propositions
362  \newlist{propositions}{enumerate}{1}
363  \setlist[propositions,1]{label=5.47321, leftmargin=*, align=left, itemsep=4pt, ...}
```

`{enumerate}{1}` declares a list with **max nesting depth 1** — i.e. the propositions environment is intentionally flat. (The `label=5.47321` is a width-template placeholder so every item's hanging label reserves the same horizontal space; it is *not* a real proposition number.)

**The tree is therefore implied, derived by parsing each label.** Reading "each appended digit = one level deeper" (Wittgenstein's own convention, §2), the 526 English propositions distribute by digit-count depth as:

| depth (digits) | count |
|---|---|
| 1 | 7 |
| 2 | 25 |
| 3 | 124 |
| 4 | 245 |
| 5 | 118 |
| 6 | 7 |

- **Max depth observed: 6.** The longest decimals (5 fractional digits) are exactly seven nodes: `2.01231`, `2.02331`, `2.15121`, `4.12721`, `5.47321`, `6.36111`, `6.36311`. Deepest in context (L5973): `\PropositionE{6.36311}` "That the sun will rise to-morrow, is an hypothesis…".
- **Top level is clean: exactly 1–7**, no more, no less (`grep -v '\.'` over the labels → `1 2 3 4 5 6 7`). These are Wittgenstein's seven cardinal propositions.
- **Branching is wildly ragged.** Descendant counts under each top node (`grep -c '\PropositionE{N\.'`): 1→6, 2→78, 3→73, 4→108, 5→150, 6→104, **7→0**. Proposition **7 is a childless leaf at depth 1** (the famous closer, L6247–6249, "Whereof one cannot speak, thereof one must be silent."), while proposition 5 spawns 150 descendants. No level has a fixed or even approximately-uniform child count.

**Verbatim nesting example** (L1319–1336) — a depth-1 root, its depth-2 comment, its depth-3 comment, and a sibling, all consecutive flat `\item`s:

```
1319  \PropositionE{1}
1320  {The world is everything that is the case.\footnote{...}}
1326  \PropositionE{1.1}
1327  {The world is the totality of facts, not of things.}
1331  \PropositionE{1.11}
1332  {The world is determined by the facts, and by these being \emph{all} the facts.}
1345  \PropositionE{1.2}
1346  {The world divides into facts.}
```

**Is the tree clean/complete or ragged? Ragged on two independent axes** (see §2 and §10): (a) asymmetric, unbounded branching; (b) **leading-zero "virtual" intermediate nodes** that have no proposition of their own.

## 2. Designation system — DOTTED-DECIMAL

- **Kind:** dotted-decimal (a single integer `1–7`, then a run of fractional digits). The first argument of every `\PropositionE`/`\PropositionG` is the designation.
- **Verbatim examples at several depths:**
  - depth 1 — L1354 `\PropositionE{2}`
  - depth 2 — L1359 `\PropositionE{2.01}`  *(see leading-zero note below)*
  - depth 3 — L1364 `\PropositionE{2.011}`
  - depth 5 — L1420 `\PropositionE{2.01231}`
  - depth 6 — L5973 `\PropositionE{6.36311}`
- **Does it ENCODE the position-path? Yes — explicitly, by the author's design.** Proposition 1 carries a footnote (L1320–1323) in which Wittgenstein states the numbering convention in his own words:

  > "The decimal figures as numbers of the separate propositions indicate the logical importance of the propositions, the emphasis laid upon them in my exposition. The propositions *n*.1, *n*.2, *n*.3, etc., are comments on proposition No.\ *n*; the propositions *n*.*m*1, *n*.*m*2, etc., are comments on the proposition No.\ *n*.*m*; and so on."

  So `1.1` is a child (comment) of `1`; `1.11` a child of `1.1`. The dotted-decimal **literally spells the path from root to node, one digit per level.** This is the witness's defining feature: designation == position-path.
- **Globally unique? Yes.** All 526 English labels are distinct (Python `Counter` → 0 duplicates), and the German label set is **identical** to the English (`diff` of the two sorted lists → no difference). The number is a global key, not a within-parent ordinal.

**Caveat to "encodes the path" — leading zeros create virtual levels.** The digit run is *not* a plain base-10 path because Wittgenstein uses leading zeros as an ordering device: `2.01` sorts before `2.1`, and its digits imply parent `2.0` — but **no proposition `2.0` exists**. Across the 526 nodes, **45 have a missing immediate parent** under the strict "drop the last digit" rule (e.g. `2.01→2.0`, `3.001→3.00→3.0`, `5.5301→5.530`). Under the alternative rule "parent = the longest existing digit-prefix," **0 nodes are orphaned** (the tree is fully connected) but those same **45 nodes skip 1–2 levels** to reach their nearest real ancestor (`3.001`'s nearest existing ancestor is `3`, a 3-level jump). The decimal still gives a **deterministic absolute depth** (digit count); what it does *not* guarantee is a materialised parent at depth−1.

## 3. Descriptive titles — none

Propositions have **numbers, not titles.** Each `\PropositionE{NUM}{BODY}` has exactly two arguments: the dotted-decimal designation and the prose body. There is no title slot, no run-in heading, no caption. (The only titles in the file are the work/part titles passed to `\Preface` and `\MainMatter`, e.g. L1316 `\MainMatter{Tractatus logico-philosophicus}` — these label *matter divisions*, not propositions.)

## 4. Body block vocabulary

The body has essentially **one block type: the numbered proposition** (prose). Logical formulae and truth-tables are **not** separate sibling blocks — they appear as **inline LaTeX inside the proposition's second (body) argument.**

- **Numbered proposition (prose)** — the universal unit:
  ```
  1746  \PropositionE{2.18}
  1747  {What every picture, of whatever form, must
  1748  have in common with reality ... the form of reality.}
  ```
- **Logical formula embedded in a proposition body** (display math + `array`), L3062–3078 — note it lives *between* the `{…}` braces of proposition `4.1252`, not as its own item:
  ```
  3062  \PropositionE{4.1252}
  3063  {Series which are ordered by \emph{internal} relations I call formal series.
  ...
  3069  Similarly the series of propositions ``$aRb$'',
  3070  \[
  3071  \begin{array}{l}
  3072  ``(\exists x) : aRx \DotOp xRb\text{'',}\\
  3073  ``(\exists x,y) : aRx \DotOp aRy \DotOp yRb\text{'', etc.}
  3074  \end{array}
  3075  \]
  3077  (If $b$ stands in one of these relations to $a$, ...)}
  ```
- **Truth-table** (`tabular`) — likewise inline within a proposition body, e.g. the schema tables around L3362/L3384/L3398 (the T/F matrices) and L2430. Custom operator macros support them: `\Not`, `\DotOp`, `\BarOp`, `\Implies` (L282–285), `\Wahr`/`\False` (W/F cells, L337–338).
- **Illustration** — `\Illustration[..]{file}` (defined L272) pulls the original's 14 diagrams from `images/*.pdf`; again inline content, not a standalone numbered block.
- **Attributes carried by a block:** the proposition's only intrinsic attribute is its dotted-decimal number. Body footnotes exist but are rare — only **3 `\footnote{` in the whole file**, the most important being Wittgenstein's numbering-convention note on proposition 1 (§2).

## 5. Matter (front / body / back) — siblings, special-cased by distinct macros

The matter divisions are **siblings at the document level**, each introduced by its own dedicated macro (defined L191–256), and **none of the front/back matter uses the proposition scheme** (the Introduction region L518–1256 contains **0** `\Proposition*` calls and **0** `\section`/`\chapter` commands — it is plain prose paragraphs):

| Order | Line | Macro | Content |
|---|---|---|---|
| front | L372 | `\Boilerplate` | PG legal boilerplate |
| front | L488 | `\Note` | transcriber's note |
| front | L518 | `\Introduction` | **Russell's introduction** — macro hardcodes `\textsc{By BERTRAND RUSSELL}` (L215) |
| front | L1257 | `\Preface{Tractatus Logico-Philosophicus}{Preface}` | **Wittgenstein's own preface** (Ogden's English) |
| body | L1316 | `\MainMatter{Tractatus logico-philosophicus}` → `\begin{propositions}` (L1318) … `\end{propositions}` (L6250) | the 526 English propositions |
| body | L6257 | `\Preface{Logisch-Philosophische Abhandlung}{Vorwort}` | Wittgenstein's preface (German) |
| body | L6328 | `\MainMatter{Logisch-philosophische Abhandlung}` → `\begin{propositions}` (L6330) … `\end{propositions}` (L11372) | the 526 German propositions |
| back | L11385 | `\Licence` | PG licence (`\pdfbookmark[-1]{Back Matter}`, L253) |

So **Russell's introduction and Wittgenstein's preface are front-matter siblings of the body, not propositions** — they sit *outside* `\begin{propositions}` and follow no numbering scheme. The PDF-bookmark hierarchy in the macros (`\pdfbookmark[-1]{Main Matter}`, `[0]{Introduction}`, etc., L198–256) is the only explicit "tree" the source ships, and it groups *matter*, not propositions.

## 6. Identity & cross-witness behavior — designation == identity (a coincidence of this work)

- **Canonical reference in practice:** a proposition is cited by its dotted-decimal number ("TLP 5.6", "proposition 7"). The file's own cross-reference macros prove this: `\PropERef`/`\PropGRef` (L263/269) resolve a reference by the *number string* (`\hyperref[PropE:#1]{#1}`), and each proposition plants a label keyed on that same number (`\label{PropE:#1}`, L260). The number is simultaneously the display citation **and** the hyperlink anchor.
- **This is the one witness where designation == position-path == identity.** Because Wittgenstein engineered the decimal to spell the tree path (§2), the citation string and the canonical position-path are byte-for-byte the same token. The bilingual edition reinforces it: English `2.01` and German `2.01` are the *same node in two languages* and carry the *same* number — the number, not the language or the prose, is the identity.
- **Why that's a coincidence, not a general rule.** The model must **not** generalise "designation is identity" from this witness. Here the author chose a designation that happens to encode position; in the sibling witnesses the two come apart (e.g. Darwin's cross-edition renumbering, where the *same* paragraph gets a different number across editions; Pepys' date designations that repeat/partial; Per la Libertà!'s ordinal-word chapter names that say nothing about order). The correct reading is the inverse: **identity = position-path always; designation is a per-node display/citation field that, in the Tractatus alone, is a faithful serialization of that path.** A dotted-decimal *reader* (a designation plugin) can recover the path from the string *for this work*, but the tracking layer must keep its own position-path so that a re-typeset, a translation, or an edition revision that renumbers does not break identity.

## 7. Authorship — book-level roles, not per-node

Authorship is **per role at the work level, not per proposition.** Three distinct roles, all declared once in the PG header (§0) and surfaced structurally:
- **Author:** Wittgenstein — owns every proposition and the preface(s). No proposition is individually signed; there is no per-node author attribute.
- **Translator:** C. K. Ogden — owns the English column; the German column is Wittgenstein's original. The split is structural (two `\MainMatter` blocks), not annotated on each node.
- **Introducer:** Bertrand Russell — owns *only* the introduction, and the `\Introduction` macro bakes his name in (`\textsc{By BERTRAND RUSSELL}`, L215). This is the one place authorship attaches to a specific matter-node rather than the whole work.

So authorship here is **matter-level** (intro = Russell, body = Wittgenstein/Ogden), a coarser granularity than Britannica's per-article signatures or Hamlet's per-line speakers.

## 8. Extraction cues — the TeX macros

- **Proposition markers (name them):** `\PropositionE{NUM}{BODY}` (English) and `\PropositionG{NUM}{BODY}` (German), defined L259–267. Both expand to a list `\item` with a `\label`/`\phantomsection` and a cross-link to the parallel-language twin:
  ```
  259  \newcommand{\PropositionE}[2]{%
  260    \item[\phantomsection\label{PropE:#1}\PropGRef{#1}] #2%
  261  }
  265  \newcommand{\PropositionG}[2]{%
  266    \item[\phantomsection\label{PropG:#1}\PropERef{#1}] #2%
  267  }
  ```
  A parser keys on the literal control sequences `\PropositionE{` / `\PropositionG{`: **526 of each** (`grep -c`). **Arg 1 = the dotted-decimal number; arg 2 = the body** (which may span many lines and contain blank-line paragraph breaks, inline math, `\footnote`, `\emph`, `\Illustration`).
- **Body envelope:** propositions live strictly between `\begin{propositions}` and `\end{propositions}` (L1318/6250 English, L6330/11372 German). The list type is declared once at L362 (`\newlist{propositions}{enumerate}{1}`).
- **Deriving depth from the decimal:** strip the dot, count digits → absolute depth (1–6). Parent = longest existing digit-prefix (re-inserting the dot after digit 1). **Do not assume parent = depth−1:** §2/§10 — 45 nodes skip levels because of leading-zero virtual nodes.
- **Traps:**
  1. **Flat list ≠ flat tree.** The source nesting is depth-1; the real tree lives only in the label string. A parser that reads container nesting sees no hierarchy at all.
  2. **Leading-zero virtual parents** (`2.01`'s parent `2.0` does not exist; 45 such cases) — naive "drop last digit → parent" produces dangling references.
  3. **`label=5.47321` in `\setlist` (L363) is a decoy** — a width template, not a proposition. Extract numbers from `\Proposition*` first args only, never from `\setlist`.
  4. **Bilingual duplication:** every number appears **twice** (E and G). De-duplicate by `(language, number)`, or the node set looks like 1052, not 526.
  5. **Front/back matter follow a different scheme** — `\Introduction`, `\Preface`, `\Note`, `\Boilerplate`, `\Licence` (L191–256) are prose, no numbers; do not feed them to the dotted-decimal reader.
  6. **TeX noise inside bodies:** `\emph{}`, `\footnote{}`, display math `\[ … \]`, `array`/`tabular` truth-tables, `\DPtypo{wrong}{right}` (L279, a transcriber typo-correction macro — take arg 2), page markers `% -----File: NNN.png---`. Brace-balance the body argument; don't split on the first `}`.

## 9. What this witness uniquely forces in the model

- **Arbitrary-depth recursion (the key case).** Observed depth runs 1→6 with no structural ceiling; the depth is whatever the decimal says. A model with fixed level slots (book/part/chapter/section) **cannot represent** this — depth-6 propositions would have nowhere to go. The container tree must be **recursive and depth-agnostic.**
- **A designation that *encodes* the position-path.** This is the witness that justifies keeping designation and identity as *separate* fields whose contents *may coincide*: identity = position-path; designation = display string; a **dotted-decimal designation-reader plugin** can parse the path *out of* the string here, but the model must not collapse the two fields just because one work makes them equal.
- **Depth derived from the designation, not from container nesting.** Extraction must compute tree depth by parsing the decimal (count digits), because the source carries the propositions as a *flat* list. This is the inverse of heading-based witnesses where depth = number of enclosing `##`/`###` levels.
- **Tolerance for ragged / gap-bearing trees.** Branching is asymmetric (a childless top-level leaf `7` beside a 150-descendant `5`) **and** intermediate nodes can be *virtual* (no `2.0` though `2.01` exists). The tree model must allow (a) any child count incl. zero at any depth, and (b) a node whose materialised parent is more than one level up. A "complete n-ary tree" assumption breaks on both.
- **What breaks if depth is assumed fixed:** every proposition deeper than the assumed ceiling is either dropped, truncated to the ceiling (collapsing distinct nodes like `6.36`, `6.363`, `6.3631`, `6.36311` into one), or mis-parented. And a position-path built from container nesting would be **uniformly depth-1** for all 526 nodes — losing the entire hierarchy the work is *about*.

## 10. Open questions / contradictions

- **Two defensible parent rules give two different trees.** "Drop last digit" leaves 45 nodes parent-less (dangling at `2.0`, `3.00`, …); "longest existing prefix" connects all 526 but introduces 45 level-skips. **Which is canonical for the position-path?** Needs a ruling. (Recommended: depth = digit count for the *path*, parent = nearest existing prefix for *tree edges*; record the skipped virtual levels explicitly rather than silently re-parenting.)
- **Leading zeros are semantically load-bearing ordering, not pure path.** `2.01` precedes `2.1` and is "lower importance," per Wittgenstein's footnote — the decimal is partly an *ordinal/priority* signal, not a clean radix path. A digit-per-level reader captures depth but **loses the sibling ordering nuance** unless it sorts decimals as real numbers (`2.01 < 2.011 < 2.02 < 2.1`), which it must.
- **Bilingual pairing is structural but only weakly machine-marked.** English↔German twins are linked solely by *identical number strings* (`\PropERef`/`\PropGRef` cross-links, L263/269). If a future plain-text edition drops the macros, the language pairing survives only because the numbers match — fragile if either side renumbers.
- **`\setlist` label template `5.47321` (L363)** is a real proposition number reused as a width sample. Harmless to compilation, but a naive regex for "a dotted-decimal token" would pick it up as a 527th, phantom node. Confirmed excluded by keying on `\Proposition*` first-args only.
- **Illustrations / truth-tables have no independent identity.** The 14 diagrams and the T/F matrices live *inside* proposition bodies with no number of their own. If the model wants to cite "the truth-table in 4.31," there is no node to point at below the proposition — open question whether sub-proposition figure/table blocks need their own positional ids.
