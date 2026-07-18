# Structural close read — Hamlet (Shakespeare)

> Grounding note: every count and quote below comes from `grep -n` / `sed -n` /
> `Read` run against the file this session. Line anchors are 1-based file lines
> (the same numbers `grep -n` emits), **not** the play's own verse line numbering.

## 0. Identification

- **Work / author:** *The Tragedy of Hamlet, Prince of Denmark* — William Shakespeare.
- **Source file:** `engine/docs/structure_corpus/shakespeare_hamlet_1524.txt`, **207 KB**, **7082 lines**.
- **Provenance:** Project Gutenberg **eBook #1524** (`www.gutenberg.org/ebooks/1524`), credit "Dianne Bean"; release 1998-11-01, "Most recently updated: September 19, 2025".
- **Boilerplate vs. play proper:**
  - PG header occupies lines 1–27, ending at `27:*** START OF THE PROJECT GUTENBERG EBOOK HAMLET ***`.
  - The **work title** appears at `32:THE TRAGEDY OF HAMLET, PRINCE OF DENMARK`; a `Contents` table at 39–69; `Dramatis Personæ` at 74–100; a global setting line `102:SCENE. Elsinore.`
  - The **play proper** (dialogue/action) begins at `107:ACT I` → `109:SCENE I.` and runs through the final stage direction at lines 6727–6728 (`[_Exeunt, bearing off the bodies, after which a peal of ordnance is shot off._]`).
  - PG license tail begins at `6732:*** END OF THE PROJECT GUTENBERG EBOOK HAMLET ***` and runs to EOF.

## 1. Container hierarchy

Named levels, in containment order:

```
WORK (the play)
└── ACT            5 instances, Roman-numbered (I–V)
    └── SCENE      20 instances total, Roman-numbered, restart per act
        └── (body: dialogue turns + stage directions)
            └── PLAY-WITHIN-A-PLAY   1 instance, nested inside Act III Scene II
                └── (inner body: its own dialogue turns + stage directions)
```

So the maximum container depth is **4** (Work › Act › Scene › inner play), and it is **variable**: only one scene (III.ii) descends to depth 4; every other scene bottoms out at depth 3.

**Child counts (verified by grep on `^[[:space:]]*ACT [IVX]+` and `^[[:space:]]*SCENE [IVX]+\.`):**

| Act | header line | scenes | scene header lines |
|-----|-------------|--------|--------------------|
| I   | 107 | **5** | 109, 440, 885, 1090, 1270 |
| II  | 1617 | **2** | 1619, 1833 |
| III | 2767 | **4** | 2769, 3067, 3766, 3904 |
| IV  | 4277 | **7** | 4279, 4355, 4421, 4563, 4680, 5076, 5130 |
| V   | 5443 | **2** | 5445, 5972 |

**5 acts, 20 scenes** (5+2+4+7+2). The hypothesis "5 acts" is **confirmed**; the manifest gave no scene total — recorded here as **20**.

> Note: child count is **heterogeneous across the same level** — acts hold anywhere from 2 to 7 scenes. The model cannot assume a fixed fan-out.

**Verbatim boundary example per level:**

- ACT level — `107:ACT I`
- SCENE level — `109:SCENE I. Elsinore. A platform before the Castle.`
- Inner-play level (boundary) — opening at `3292:Trumpets sound. The dumb show enters.` and the explicit start of the spoken inner play at `3316:Enter Prologue.` / `3332:PROLOGUE.`; broken off at `3514:The King rises.` → `3525:KING.` / `3526:Give me some light. Away.` (see §1.x below).

### 1.x The recursive play-within-a-play (hypothesis confirmed, with nuance)

The inner play ("The Murder of Gonzago", nicknamed `3468:_The Mousetrap._`) is nested **inside Act III, Scene II** (scene spans file lines 3067–3765, i.e. up to `3766:SCENE III.`). It is genuinely recursive: the inner play has the **same block grammar** as an outer scene — its own stage directions and its own speaker-attributed dialogue turns — and the **outer** characters (HAMLET, OPHELIA, KING) interleave commentary between the inner turns.

Structure of the nested unit:
- A wordless **dumb show**: `3292:Trumpets sound. The dumb show enters.` followed by an italic prose stage-direction block at 3294–3303 and `3305:[_Exeunt._]`.
- The spoken inner play: `3316:Enter Prologue.`, `3332:PROLOGUE.`, then `3346:Enter a King and a Queen.`, with inner speakers **PLAYER KING** (3348), **PLAYER QUEEN** (3356), and **LUCIANUS** (3498).
- Aborted, not closed cleanly: at `3506:[_Pours the poison into the sleeper's ears._]` Claudius reacts; `3513:OPHELIA. / 3514:The King rises.`, `3525:KING. / 3526:Give me some light. Away.`, then `3531:[_Exeunt all but Hamlet and Horatio._]`.

Design consequence: the inner play is **not** a distinct typed level requiring its own schema — it is a **scene-shaped subtree recursively embedded in a body block**. Critically, it has **disambiguating speaker aliases**: inner `3356:PLAYER QUEEN.` and `3348:PLAYER KING.` coexist in the same scene with the outer-frame `3519:QUEEN.` and `3525:KING.`. Speaker identity is therefore **scoped to the containing (sub)tree**, not globally unique by name.

## 2. Designation system

- **Acts:** Roman numerals, format `ACT I` … `ACT V`. Verbatim: `107:ACT I`, `5443:ACT V`.
- **Scenes:** Roman numerals with a trailing period, format `SCENE I.` … `SCENE VII.`. Verbatim: `109:SCENE I. Elsinore. A platform before the Castle.`, `5130: SCENE VII. Another room in the Castle.`
- **Uniqueness:** Act designations are unique within the work. Scene designations are **parent-dependent** — they restart at `I` inside every act (there are five distinct `SCENE I.` lines: 109, 1619, 2769, 4279, 5445). A scene is only identified by the **pair** (act, scene). This directly supports demoting the designation to a display/citation field and using a position-path (`act#/scene#`) as canonical identity.
- **Indentation as a designation tell:** the first scene of each act is flush-left (`109:SCENE I...`), later scenes are leading-space-indented (`440: SCENE II...`). Indentation is cosmetic, not semantic.

## 3. Descriptive titles

Yes. **Every scene header carries a descriptive setting line** appended after the designation, not a separate title node:

- `109:SCENE I. Elsinore. A platform before the Castle.`
- `885: SCENE III. A room in Polonius's house.`
- `5445:SCENE I. A churchyard.`

Acts have **no** descriptive title (bare `ACT I`). There is also a single **work-level** setting line `102:SCENE. Elsinore.` (no number) in the front matter — a global locale, distinct from the per-scene settings. The Contents table (39–69) restates each scene's setting, so the descriptive title appears in **two** places (TOC and in-situ header) — a cross-reference the extractor should treat as a citation of the in-situ header, not a second node.

## 4. Body block vocabulary — the centerpiece

A scene body is an **ordered, heterogeneous list of typed blocks**. THIS witness forces (at least) these block types:

### (a) Speaker-attributed DIALOGUE TURN — speaker is an attribute, not a heading

A turn = a **speaker label line** (caps name + period) immediately followed by one or more content lines, terminated by a blank line. The speaker is metadata **on** the block, not a container.

```
114:BARNARDO.
115:Who's there?
```
```
117:FRANCISCO.
118:Nay, answer me. Stand and unfold yourself.
```

Count: **1123** all-caps speaker labels match `^[A-Z][A-Z'’ ]*\.$`. Speaker labels are **not** strictly single-token — `3348:PLAYER KING.`, `3356:PLAYER QUEEN.` are multi-word.

### (b) STAGE DIRECTION — a sibling block, two surface forms

1. **Plain entrance/exit lines** at block scope (68 lines match `^(Enter|Exit|Exeunt|Re-enter|Flourish|Trumpets|A flourish)`):
   ```
   112:Enter Francisco and Barnardo, two sentinels.
   ```
   ```
   3346:Enter a King and a Queen.
   ```
2. **Bracketed-italic directions** wrapped in `[_…_]` (137 lines match `^\[_.*_\]$`), used for action and exeunt:
   ```
   3506:[_Pours the poison into the sleeper's ears._]
   ```
   ```
   3531:[_Exeunt all but Hamlet and Horatio._]
   ```
   There is also a multi-line **italic prose** stage block (no brackets), the dumb show 3294–3303, opened/closed by underscores.

Stage directions occur **both** between turns (siblings of dialogue) **and inside a speech** (children of a turn — see §8 traps), e.g. `529:[_Aside._] A little more than kin, and less than kind.`

### (c) Verse vs. prose lines (a property of the turn's content, not a separate block)

The same DIALOGUE-TURN block carries either metered verse or running prose:

- **Verse** (capitalized, line-broken, metrical):
  ```
  3349:Full thirty times hath Phoebus' cart gone round
  3350:Neptune's salt wash and Tellus' orbed ground,
  ```
- **Prose** (wrapped, sentence-flowing):
  ```
  3509:He poisons him i' th'garden for's estate. His name's Gonzago. The story
  3510:is extant, and written in very choice Italian. You shall see anon how
  3511:the murderer gets the love of Gonzago's wife.
  ```

Verse/prose is best modeled as a **mode attribute on the content lines**, not a distinct sibling block — a single speaker can switch modes within a scene (Hamlet does throughout III.ii).

## 5. Matter (front / body / back)

- **Front matter** is present and is a **sibling** of the acts, not special-cased into the act tree:
  - `Contents` TOC (39–69) — a generated index of the act/scene tree.
  - `Dramatis Personæ` roster (74–100): a **list of character entries**, each `NAME, role` —
    ```
    76:HAMLET, Prince of Denmark
    77:CLAUDIUS, King of Denmark, Hamlet's uncle
    ```
    Entries include collective/anonymous rows (`94:Players`, `97:Two Clowns, Grave-diggers`, `100:Lords, Ladies, Officers, Soldiers, Sailors, Messengers, and Attendants`). This roster is exactly the per-block speaker vocabulary referenced by the dialogue turns — a front-matter **roster node** whose entries are cross-referenced by body blocks.
  - Global setting `102:SCENE. Elsinore.`
- **Back matter:** none authored by the work — the play ends on its final stage direction (6727–6728); everything after `6732` is PG license, not part of the document model.

So: front matter (Contents, Dramatis Personae, global SCENE) and body (the 5 acts) are **siblings under the work root**. The roster confirms hypothesis (e): a "Dramatis Personae" is a sibling block, not an act.

## 6. Identity & cross-witness behavior

- **Canonical citation** is positional and hierarchical: `act.scene.line` (e.g. "III.ii.247"), where act and scene are the designation pair from §2 and the third term is the play's own verse-line index (a per-scene running count, **not** the file line). This is exactly a **position-path**; the Roman/Arabic designation is a display rendering of the same path. Hypothesis (b) — position-path as canonical identity — **holds**, and the designation→display demotion is well-supported.
- **Speaker as per-block attribute:** every dialogue turn carries a `speaker` field (the label line). Speakers are drawn from the roster but are **not globally unique** — the inner play introduces `PLAYER KING`/`PLAYER QUEEN` alongside the frame's `KING`/`QUEEN` (§1.x), so the speaker attribute must resolve **within the block's containing subtree**, and the roster must tolerate aliases/role-doubles.
- **Collective speakers** (`3528:All.`, `793:Both.`, `4880:Danes.`) are valid speaker values too — the attribute's value space is roster-names ∪ collective labels, not a closed enum of named persons.

## 7. Authorship

Single author: **William Shakespeare** (`34:by William Shakespeare`). No per-node authorship variation in the text itself. Hypothesis (g) "authorship may be per-node" finds **no positive evidence here** — the inner play is *diegetically* authored by a different (fictional) hand and *performed* by the Players, but the witness encodes no per-node author field; it is one author throughout. This witness neither confirms nor refutes (g); it is simply silent, and a model that makes author a per-node *optional* field loses nothing here.

## 8. Extraction cues

- **ACT header:** line matches `^[[:space:]]*ACT [IVX]+\s*$` (leading space tolerated). Bare designation, no title.
- **SCENE header:** line matches `^[[:space:]]*SCENE [IVX]+\.` followed by a free-text setting; first-in-act flush-left, others indented one space.
- **Speaker label:** a line that is **only** a name + terminal period, typically all-caps `^[A-Z][A-Z'’ ]*\.$` (1123 matches), **but also Title-case** for collective speakers (`All.`, `Both.`, `Danes.`, `Ladies.`). The label is immediately followed by ≥1 content line and preceded by a blank line.
- **Stage direction:** either a bracketed-italic line `^\[_.*_\]$`, an unbracketed `Enter/Exit/Exeunt/Re-enter/Flourish/Trumpets…` line, or an unbracketed italic prose block (`_…_`) like the dumb show.

**Traps (each verified):**

1. **Mid-line / mid-speech stage directions.** A `[_…_]` direction can sit **inside** a speech rather than between turns: `2156:How say you by that? [_Aside._] Still harping on my daughter. Yet he`. A line-anchored "stage directions are siblings" rule will mis-segment these; directions must be allowed **inside** a dialogue-turn block as inline children.
2. **One-word lines that look like speaker labels.** `127:He.`, `1756:Farewell.`, `3265:Nothing.` match the Title-case-label regex but are **dialogue content** (a one-word reply), not labels. They are distinguished from real collective-speaker labels (`793:Both.`, `3528:All.`) **only by position**: a label is *preceded* by a blank line and *followed* by content; a one-word reply is *preceded* by a speaker label. 14 mixed-case lines match `^[A-Z][a-z]+\.$`, mixing both kinds — name-shape alone cannot classify them.
3. **The inner play's own dialogue** carries inner-scoped speakers (`PLAYER KING`, `PLAYER QUEEN`, `LUCIANUS`, `PROLOGUE`) that are **absent from the top-level Dramatis Personae roster** (the roster lists only generic `94:Players`). An extractor that validates speakers against the roster will reject legitimate inner speakers unless speaker scope is per-subtree.
4. **Speaker-name collision across nesting** — frame `KING`/`QUEEN` vs inner `PLAYER KING`/`PLAYER QUEEN` in the *same* scene (§1.x). Global speaker dedup by string is wrong.
5. **Setting text duplicated** between the Contents TOC (39–69) and each in-situ scene header; only the in-situ header is the structural node.

## 9. What this witness uniquely forces in the model

THIS is the key dramatic witness; it forces, beyond the prose-document baseline:

1. **Speaker-attributed dialogue turn as a first-class typed block with a `speaker` attribute.** The speaker is metadata on an ordered body block, not a heading/container. The open body vocabulary (hypothesis d) must admit at least `{dialogue_turn, stage_direction}` for dramatic texts — and the speaker value space is `roster-name ∪ collective-label`.
2. **Stage directions as sibling blocks AND inline children.** They appear both between turns (siblings) and inside speeches (children) — so the body grammar cannot be "alternating speaker/non-speaker lines"; it is a true ordered list with optional inline annotations.
3. **Recursive containment via the body, not via a new level.** The play-within-a-play (Act III.ii) is a scene-shaped subtree embedded *inside a body block*. The container model must be recursive (hypothesis a) and must allow a body block to *contain another (sub)tree of the same block grammar*. A flat "act › scene › blocks" schema with no recursion **cannot represent III.ii** without either losing the nesting or inventing a bespoke "inner play" level.
4. **Subtree-scoped speaker identity.** Because `KING` and `PLAYER KING` (and `QUEEN`/`PLAYER QUEEN`) coexist in one scene, the speaker attribute resolves relative to the containing subtree; identity/citation must therefore be position-path-anchored (hypothesis b), with designation/name purely for display.
5. **Heterogeneous, variable child counts** at the same level (acts hold 2–7 scenes; a scene body mixes turns, directions, and a nested play) — confirms hypotheses (a) and (f).

**What breaks if ignored:**
- No `dialogue_turn` block type → the entire play degrades to undifferentiated paragraphs; the speaker (the single most-cited attribute) is lost and `act.scene.line` citation becomes impossible.
- No recursion in the body → Act III Scene II's inner play is unrepresentable (or forces a hard-coded special case), and inner-vs-frame speaker disambiguation collapses.
- Global (non-scoped) speaker identity → `KING` and `PLAYER KING` merge, corrupting attribution exactly where the plot turns.
- Treating stage directions as strictly between-turn siblings → mid-speech `[_Aside._]` directions mis-split speeches.

## 10. Open questions / contradictions

- **Designation vs. identity (supports the hypothesis).** Scene numbers are parent-dependent (five `SCENE I.`), confirming designation must be demoted to display and identity must be the (act, scene) position-path. No contradiction — strong support for hypothesis (b)/(c).
- **Speaker label is not a closed lexical class.** Contradiction to a naive "speaker = ALL-CAPS token" reading: collective speakers are Title-case (`All.`, `Both.`, `Danes.`) and one-word **dialogue** lines share the same shape. Classification needs position/context, not a name regex (§8 traps 1–2). This is the sharpest contradiction to a line-pattern-only extractor.
- **Per-node authorship (g) is unwitnessed here.** The inner play is fictionally a different author/performance but carries no encoded author field; this witness is silent on (g) rather than confirming it. A different witness (e.g. an anthology, or annotated/edited text with editor vs. author layers) is needed to exercise per-node authorship.
- **Where does the inner play formally "end"?** It is **aborted**, not closed — Claudius's `KING. Give me some light. Away.` interrupts mid-performance, and `[_Exeunt all but Hamlet and Horatio._]` (3531) clears the stage. The inner subtree therefore has a fuzzy lower boundary (no closing "exeunt the Players" of its own). The model should not assume nested subtrees are always cleanly terminated.
- **Verse vs. prose modeling.** Left as a content attribute (mode) on the turn rather than a block type, because a single speaker alternates modes within one scene. Flagged for the model owner to ratify: is mode a line/segment property or a sub-block? This witness shows it must at least be *representable per content-span*, not per-scene.
- **TOC / in-situ duplication.** The Contents table and per-scene headers restate the same setting strings; the extractor must pick the in-situ header as the node and treat the TOC as a generated cross-reference (not double-counted as scenes — naive `Scene`-line counting over the whole file would otherwise yield ~40, double the real 20).
