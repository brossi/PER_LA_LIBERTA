> **ARCHIVE — superseded as the working spec (2026-06-26).** This file preserves the
> full two-round adversarial review verbatim — the immutable `@@@@@@` (auditor) /
> `======` (response) threads — that produced the design. The reconciled, authoritative
> spec is **`ENGINE_STRUCTURE_PLAN.md`**; read that for sign-off and task decomposition.
> Nothing below is edited or resolved further; it is kept for provenance only. Where this
> archive and the spec disagree, the spec wins (the spec's decisions log §10 records the
> outcome of every thread here).

# Engine Structure Plan — Document-Structure Axis (DISCUSSION ARCHIVE)

Branch: `spike/document-structure`. Originating item: **BR-021** (position-based
chapter identity) in `docs/decisions/branch_register.md`.

## How to read / audit this

This is a **design plan to review before any code**, per `feedback_plan_review_workflow`.
Drop `@@@@@@` audit blocks anywhere; each expects a paired `======` response,
code-verified, per point. Sections are numbered and claims are kept atomic so an
audit block can target one line. Findings about the live tree are cited as
`file · symbol`; findings about the existing engine port are cited the same way.

## Status — keystone decided; not yet fully signed off

- **Agreed by the user (this session):** the *two-layer* framing — extraction
  ("everything is brought in") then a durable tracking/structural model ("how it is
  durably catalogued").
- **Decided by the user (rulings):** engine = PLL v2 production pipeline (D28); structure-first
  pipeline order (D29); geometry + Zipf-DP reconstruction (D30); build-enough-of-spec scope (D31);
  overlapping hierarchy parked (D32); **O1 identity keystone = Option A "store-and-rebind" (D33),
  with the identity cluster D11/D12/D20/D24 it entails.** HITL structural tagging is now *committed
  for PLL* (D28/D29) — only its scale-ceiling/inference-fallback for large non-PLL validators stays
  open (O3).
- **Still proposed (await a sign-off pass):** the three-concern decomposition (§2), R2–R5 (§4), the
  build-now vs joint-only scope (§6), the engine integration (§7), and D-rows D2, D4–D10, D13–D19,
  D21–D23, D25–D27. Editorial gaps remain: §3.0/§3.6 are referenced but unwritten, and §6/§7/§11
  partly lag the rulings (§6↔D31, §7↔D29).
- **PLL is a reference, not a spec.** The other ten corpus witnesses are co-equal
  structural witnesses used as conformance validators, not a build backlog.
- **Evidence base:** `structure_corpus/findings/*.md` (ten close-reads) +
  `structure_corpus/SOURCES.md`. The red-team pass caught some findings artifacts
  over-claiming (notably `findings/hamlet.md`); they are **evidence to re-check, not
  gospel**.

@@@@@@
**Red-team #1 — this plan still needs a concrete artifact slice before code.**

The abstraction is plausible, but it remains under-specified at the exact point where
ambiguity will become expensive: the on-disk contracts. Before implementation, require a
small worked example for PLL containing one ordinary chapter, the preface, the Mazzini
embedded document, one page-provenance span, and one derived handle set. That example should
show the raw/extracted block artifact, the structure-map artifact, and the relation/alignment
artifact. Without that, reviewers are approving vocabulary rather than a schema, and two
implementers could produce incompatible "correct" versions of A/B/C.
@@@@@@

======
**Accept — this is the highest-value point; the plan is approving vocabulary, not a schema.** Without a worked slice, "typed block," "structure map," and "relation" are nouns, and §3.2/§3.4 are exactly where two implementers diverge. Added **§11 — Worked example (PLL slice)** at the end: one ordinary chapter (`Capitolo Primo`), the `prefazione`, the embedded Mazzini letter, one page-provenance span, and the derived handle set, rendered as the three on-disk artifacts (atoms / structure-map / relations). It deliberately encodes the substrate revision the red team forces below (RT#4/7/13 three layers; RT#9/10 `node_id` + handle policy), so the schema and the rulings are reviewed together rather than in sequence. Treat §11 as the artifact under audit from here on — if the schema there is wrong, the rulings inherit the fix.
======

@@@@@@
**Codex follow-up #1 — agree, with one schema audit from §11.**

The worked slice is exactly the right move. The remaining risk is that §11 currently mixes
per-witness atoms with a structure map that looks canonical: `data/atoms/copy1.json` provides
`a_*`, while `structure_map.json` references those same `a_*` as if they were the durable body
substrate and says `source_hash` is for "this reconciled source." Before this hardens, the slice
needs to name the canonical projection explicitly: either the structure map is authored against a
reconciled atom stream, with per-witness streams related to it, or it is authored against one chosen
witness. The latter is probably wrong for the engine. Add `source_artifacts` / `projection_id` /
`canonical_stream_id` to the example so the three artifacts do not smuggle in different answers.
@@@@@@

======
**Response to Codex #1 — accept; real bug in §11, fixed.** The structure map referenced `copy1.json`'s
per-witness `a_*` as if canonical — exactly the smuggled answer you name. Corrected: the structure map
references **one canonical atom stream** (the reconciled projection); per-witness streams relate to it
through C alignment, never directly. §11 header now carries `source_artifacts` (raw witness ids+hashes),
`canonical_stream_id`, and `projection_id`, so all three artifacts point at the same substrate. This is
the same field set Codex #11 asks for as a lineage manifest — merged, not duplicated.
======

## Scope

- **In scope:** redesign the document-structure axis as *extraction → durable
  structural model → relations*; define the seams; specify what the **PLL target**
  needs built now.
- **Build-now target:** PLL. The ten other witnesses validate that the *joints* are
  coherently designable, not that they are implemented.
- **Out of scope:** implementing validator-only capabilities; the M4c translate/refine
  port (paused behind this exploration); the live edition's deploy state (the
  deploy-hold governs the live PLL push, not this clean-room design — orthogonal, see
  `feedback_existing_path_failures_as_evidence`).

---

## 0. Why this exists (the problem)

BR-021 flagged chapter identity as "arbitrary / position-based." Reading the corpus
plus the existing port shows the deeper shape: the engine fuses three separable
concerns and hardcodes one book's skeleton.

The corpus exists to break the single-book bias (PLL-as-spec). It did: the model below
is answerable to the **union** of what eleven real document structures exhibit, and the
red team confirmed which parts of an earlier draft survived contact with that union and
which did not (§5).

---

## 1. Current state in the engine (what we are changing)

Four findings, each a thing this plan redesigns. All are present in the port today.

- **F1 — Structure recognition lives entirely in `LanguagePlugin`.**
  `lang/base.py` declares `is_chapter_heading`, `parse_chapter_number`,
  `structural_part`, `strip_boilerplate`, `split_raw_chapters` as abstract; the Italian
  implementation (`lang/italian.py`: `ORDINALS`, `_HEADING_RE`, `_PARTS`,
  `_PREFAZIONE_RE`, `_PARTE_SECONDA_RE`) carries all of it. There is no core structure
  model and no structure seam. **Structure is a per-language concern today.** The corpus
  says block vocabulary (Hamlet dialogue, Beeton recipe-record) and some designation
  kinds (Tractatus dotted-decimal) are per-**book**, not per-**language** — so this
  fusion is the wrong cut.

- **F2 — `BookManifest.structure` is a fixed-shape validator, not a model.**
  `config/models.py · Structure` carries `h2_min`, `h3_count`, `parts`,
  `content_units`, `running_heads`. These encode "≥3 H2, exactly 57 H3 (24+33)" —
  PLL's specific skeleton. A book with zero grouping levels (Kybalion) or four
  (Pepys) or recursion (Tractatus) cannot be described by this schema.

- **F3 — `ChapterIdentity` derives every handle from the designation.**
  `util/chapterids.py · ChapterIdentity` holds `short` (`p1_ch01`), `parse_md`
  (`p1_capitolo_primo`), `html_slug` (`parte-prima-capitolo-primo`), plus `part`,
  `number`, `title`. The three id strings all descend from `number`/`part`, which come
  from the Italian ordinal parse. **Identity rides on the designation reader** — the
  precise BR-021 fragility, and (per the PLL close-read) the reason the long id drifts
  with the source's spelling (`Capitolo Decimo Ottavo` P1 vs `Capitolo Decimottavo` P2).

- **F4 — The chapter representation is untyped; blocks do not exist.**
  `steps/reconcile.py` emits `reconciled_chapters.json` as a list of plain dicts
  `{"id", "title", "part", "text"}`, where `text` is paragraphs joined by `\n\n`.
  There is no `Block`/`Paragraph`/`Span` type, no block identity, no place for verse,
  footnotes, dialogue, or inline spans. The body is an opaque string.

@@@@@@
**Red-team #2 — F1–F4 miss the multi-witness dependency that already exists.**

The current extraction path does not just segment "the source text"; `reconcile.run`
segments Copy 1, Copy 2, and optionally Copy 3 separately, then aligns/merges them. The new
model needs to say whether A emits per-witness block streams, a single reconciled stream, or
both. If it emits only the reconciled stream, page provenance, OCR disagreement flags, and
copy-specific structural failures lose their attachment point. If it emits only per-witness
streams, cleanup/translate still need a canonical stream. This is a contract-level issue,
not an implementation detail.
@@@@@@

======
**Accept — code-verified, and the current code already loses what you name.** `reconcile.run`
segments `ch_map1`/`ch_map2`/`ch_map3` independently (`steps/reconcile.py:553–562`), reconciles
paragraph-by-paragraph at word level, and persists exactly two things: one merged stream
(`reconciled_chapters.json`, `:630–673`) and word-level disagreements (`flagged_segments.json`,
`:716`) keyed by `(ch_id, para_idx)`. The per-witness *structural* streams are thrown away; page
provenance is then attached to the **merged** clean-char offsets (`_strip_page_markers` →
`{clean_offset: page}`, `:485`). So today's answer is "reconciled-only," and it already pays the
price you predict: a Copy-1-only segmentation failure has nowhere to live, and the disagreement
flags hang off a fragile `(ch_id, para_idx)` position pair (the same position-as-key fragility
R2/RT#10 indict). **Ruling: A emits both** — per-witness atom streams (each addressable, so
copy-specific failures and OCR disagreements keep an attachment point) **and** one designated
reconciled *projection* that cleanup/translate consume. Provenance and flags bind to atom/node
ids (RT#10), not to `(ch_id, para_idx)`. Folded into §2-A and §7.4; shown concretely in §11.
======

@@@@@@
**Codex follow-up #2 — agree, but flags need span-level anchors.**

The "both per-witness streams and one reconciled projection" ruling is correct. I would tighten
the attachment rule: OCR disagreement flags cannot bind only to `node_id`, and often not even to a
whole atom. They need `{witness_id, atom_id, span}` on each competing reading, plus a link to the
canonical projection node they affected. Otherwise word-level disagreements become paragraph-level
again under a new name. This also lets a single paragraph carry multiple independent OCR conflicts
without manufacturing extra structure nodes.
@@@@@@

======
**Response to Codex #2 — accept; flags are span-level L3 annotations.** An OCR disagreement flag binds
to `{witness_id, atom_id, span}` per competing reading, plus a link to the canonical projection node it
affects — not to a `node_id` alone, and not to a whole atom. That keeps a paragraph able to carry
several independent conflicts without inventing structure nodes, and stops word-level disagreements
regressing to paragraph granularity. This is the first consumer of the `SpanRef` primitive I accept
under Codex #7; the flag schema reuses it rather than defining its own.
======

---

## 2. Architecture — three concerns, non-linear

The user's two layers map onto three concerns: **layer 1 = A**; **layer 2 = B + C**
(the durable catalogue is B; its relations are C).

```
        ┌─────────────────────────────────────────────────────────────┐
  raw   │  A. BLOCK EXTRACTION        flat, source-ordered typed blocks │
  text ─┼─►  faithful capture     ──► (no container hierarchy inferred) │
        │                                          │                    │
        │  B. STRUCTURAL ASSIGNMENT    ◄────────────┘   the durable      │
        │     group blocks into a ragged container tree;   "structure   │
        │     assign designation / title / role / matter    map" sidecar│
        │                                          │                    │
        │  C. RELATIONS                ◄────────────┘                    │
        │     cross-ref edges + cross-edition / cross-witness alignment  │
        │     (may feed corrections back to A and B — the loop)          │
        └─────────────────────────────────────────────────────────────┘
```

- **A — Block extraction.** Source → a flat, source-ordered list of typed blocks. As
  faithful as the source allows; restoration of degraded typography (the
  `typography.json` class of thing) is a *separate attributed overlay*, never folded
  into capture. A is book-specific where it must be (block typing), and **correctable**
  by B (§4 R3) — it is not the universal-dumb pass an earlier draft claimed.

@@@@@@
**Red-team #3 — A needs a declared coordinate system and a losslessness invariant.**

The existing code calls `strip_boilerplate`, `collapse_spaces`, and paragraph rejoiners before
or during structural work; those operations destroy stable offsets unless an offset map is
created first. If B/C can later correct A, every block/span must be addressable in a durable
coordinate space: source witness id, raw byte or codepoint offsets, line/column, page/scan
range, and the normalization layer those offsets refer to. Also define what "everything is
brought in" means for Gutenberg wrappers, scan catalog matter, running heads, and page
furniture: captured-but-excluded is different from never captured.
@@@@@@

======
**Accept — code-verified, and one coordinate seed already exists to generalize.** `collapse_spaces`
(`util/text.py:39`), `rejoin_lines` (`util/text.py:55`, which *heals* hyphenated line-breaks and so
destroys line structure), and `strip_boilerplate` (`lang/italian.py:225`) are all string→string with
no offset map across the transform. The single coordinate system in the port is
`_strip_page_markers`'s `{clean_char_offset → page}` dict (`reconcile.py:485`) — built **after**
normalization, page-granular, witness-untagged. **Ruling:** every A-atom carries a durable address
`{witness_id, raw_codepoint_span, page/scan_range, normalization_layer_id}`, and the existing page
map becomes one projection over that address space rather than the only one. On "everything is
brought in": adopt **captured-with-role** — Gutenberg wrappers, running heads (`Structure.running_heads`
already enumerates these as manifest data, BR-004), and scan furniture are captured atoms with
`provenance_class` ∈ {source-wrapper, page-furniture, …} and `role=excluded` (RT#8), which is
distinct from never-captured. That distinction is also what makes RT#17's no-loss round-trip
checkable. New **§3.0 Coordinate space & capture completeness**.
======

@@@@@@
**Codex follow-up #3 — agree, but `norm_layer` cannot replace a reversible map.**

The coordinate ruling is right; the example still needs to be stricter. `raw_span` should always
address the raw witness text, and the atom's normalized `text` should be tied to a transform map,
not merely a `norm_layer` label. A label like `rejoin+collapse` is enough for provenance, but not
for no-loss reconstruction unless the raw bytes are recoverable from the source artifact and every
normalized character can be mapped back or declared generated/deleted. Add an explicit
`raw_source_hash` plus either `raw_text` in tests or a transform map. Otherwise "round-trip modulo
normalization" can accidentally bless lossy capture.
@@@@@@

======
**Response to Codex #3 — accept; `norm_layer` is a label, not the guarantee.** Right that a label can
bless lossy capture. Two changes: each atom gains a `raw_source_hash` pinning the raw witness text its
`raw_span` addresses; and the round-trip test (Codex #17) splits in two — **raw** reconstruction from
`raw_span` against the source artifact must be **exact** for every captured atom, while **normalized**
reconstruction may differ from raw only by declared transform operations carrying a reversible map (or
explicit generated/deleted markers). The label survives only as human-readable provenance; the binding
check is the map plus the raw-exact tier. Folded into §11 atoms and §9.
======

- **B — Structural assignment.** Group the flat blocks into a ragged container tree
  and attach the read-fields (designation, title, role, matter). This is the durable
  catalogue. Proposed authoring surface: human-in-the-loop, plugin/LLM pre-suggested
  (§3.5) — *open ruling O3*.

@@@@@@
**Red-team #4 — "B can re-atomize" blurs the A/B contract.**

R3 says B can re-atomize and re-type, not merely group. That is probably necessary, but then
A's typed blocks cannot also be the primitive durable substrate. The safer cut is: A emits
immutable low-level source atoms or ranges; B emits a projection that groups/splits/types those
atoms; corrections are versioned projection operations. Otherwise a B correction changes block
ids out from under review flags, typography overlays, page links, and later C relations.
@@@@@@

======
**Accept — this is the central revision, and it converges with RT#7 and RT#13.** The flaw is real:
if the "typed block" is simultaneously the faithful primitive *and* the re-typeable projection, then
R3's "B can re-atomize" mutates the thing every overlay is pinned to. Adopt your cut as the model's
spine — **a three-layer substrate**:
- **L1 source atoms** — immutable, addressed (§3.0), assigned a durable `node_id` once (RT#10),
  never re-atomized. This is the substrate everything pins to.
- **L2 block projections** — group/split/type L1 atoms into paragraphs, verse-lines, records,
  dialogue-turns. A *projection*, versioned; B's re-atomize/re-type and C's corrections are
  versioned ops over L1, never edits to L1 ids.
- **L3 annotations** — spans, fields, attributes, and relations (incl. alignment, RT#13) keyed to
  L1 `node_id`s.
Review flags, typography overlays, and page links bind to L1, so a B re-projection leaves them
intact (it changes which *projection* groups an atom, not the atom's id). This replaces the flat
"typed blocks + inline spans" of §3.2. The price — projections are now first-class versioned
artifacts needing the lifecycle of RT#5/11 — is real and accepted, not waved off.
======

@@@@@@
**Codex follow-up #4 — agree, but keep `atom_id` and `node_id` distinct.**

The three-layer substrate is the right correction. The wording "L1 source atoms ... assigned a
durable `node_id` once" is where I would push back. L1 should have durable `atom_id`s; structural
identity starts at L2/L3 as `node_id`s over atom ranges. Some systems make atoms nodes too, but §11
already separates `a_*` from `n_*`, and that separation is useful. It prevents review flags and OCR
coordinates from being confused with structural handles. So: overlays that care about text evidence
pin to `atom_id` + span; overlays that care about structural meaning pin to `node_id`; relations can
state which endpoint type they accept.
@@@@@@

======
**Response to Codex #4 — accept; my RT#4 wording was wrong, §11 was already right.** "L1 atoms assigned a
durable `node_id`" conflated the two layers. Correct rule: **L1 carries `atom_id`** (text evidence +
coordinates); **structural identity is `node_id`, and it begins at L2/L3** over atom ranges. §11 already
separated `a_*` from `n_*`; the prose now matches it. Overlay pinning splits by what the overlay is
about: OCR flags, raw coordinates, typography evidence → `atom_id` + span; structural meaning, handles,
revisions → `node_id`. Relation endpoints declare which they accept (Codex #7/#12). D10/D11 wording
corrected accordingly.
======

- **C — Relations.** Cross-reference edges (a graph orthogonal to containment) and
  cross-edition / cross-witness alignment. **Non-linear:** C can prove A or B wrong
  (a cross-edition alignment can reveal a missegmentation) and feed a correction back.

@@@@@@
**Red-team #5 — the feedback loop needs governance, or reproducibility gets vague.**

"C can prove A or B wrong" is right, but the plan does not say how that proof becomes a new
artifact. Is it an automatic rewrite, a proposed patch to the structure map, a reviewer-approved
override, or a new version of A? Given the project's branch/divergence discipline, corrections
from C should have an audit trail: source evidence, artifact version bumped, old ids/relations
migrated or explicitly invalidated, and tests that fail on stale references.
@@@@@@

======
**Accept — and pin the answer to "never auto-rewrite A."** A C-discovered missegmentation becomes a
**proposed patch to the structure map (L2/L3), human-approved**, never a silent rewrite of L1 atoms
— L1 is immutable by RT#4. The audit trail: the relation that exposed the conflict is the source
evidence; the structure-map version bumps; superseded L2 projections/L3 relations are either
migrated to new `node_id`s or explicitly tombstoned (kept, marked invalid — the corrections.json
post-mortem in `feedback_existing_path_failures_as_evidence` is exactly why we keep rather than
delete); and RT#17's reference-integrity tests fail on any stale ref. This is the same governance
spine RT#11 and RT#17 ask for from the map and the tests; consolidated in new **§3.6 Lifecycle &
governance**.
======

@@@@@@
**Codex follow-up #5 — agree, with one escape hatch: new L1 versions, not L1 rewrites.**

"Never auto-rewrite A" is the right default. The only nuance is that C may reveal not just a bad
projection but a genuinely missing or malformed capture atom. In that case the fix should be a new
L1 artifact version derived from the raw witness, not a mutation of the old L1 stream. The old atom
ids stay addressable for audit; the new stream gets a new source/projection hash; migrations map old
L2/L3 refs forward or tombstone them. This preserves reproducibility without pretending L1 can never
be superseded.
@@@@@@

======
**Response to Codex #5 — accept; "no rewrite" ≠ "no new version."** The nuance is right: when C exposes a
genuinely missing or malformed *capture* atom (not just a bad projection), the fix is a **new L1 stream
version** derived from the raw witness, with a new stream id+hash. Old `atom_id`s stay addressable for
audit; L2/L3 refs migrate forward or tombstone through the governance path. The invariant that survives
is "L1 is never mutated *in place*," not "L1 is frozen forever." Adding an L1-versioning clause to the
governance spine (D14) so re-capture is a first-class, audited event rather than an edit.
======

---

## 3. The model

### 3.1 Container tree

- A **recursive container node** with ragged, *discovered* depth — 0 levels (Kybalion)
  to 4 (Pepys), recursive (Tractatus). Depth is **not** a schema constant (replaces
  F2's fixed shape).
- **Matter is a role attribute** (`front` | `body` | `back`), not a special case;
  front/back/body are siblings in one ordered child list (replaces PLL's special-cased
  prefazione).
- A container's **children may be heterogeneous** (Atlantic: essay / poem / serialized
  fiction / review as siblings).
- **Recursion in the body** (a sub-document embedded inside a block) is real and
  build-now for PLL (the embedded Mazzini letter). It is distinct from **overlapping
  hierarchy** (§4 R4).

@@@@@@
**Red-team #6 — "container", "block", and "embedded document" need sharper boundaries.**

For PLL, is the Mazzini letter a block with child blocks, a container child of the chapter, or
a relation over a range of blocks? The choice affects rendering, authorship scope, language
scope, and alignment. The current text says recursion is "inside blocks", but §3.1 defines the
recursive thing as a container node. Pick one representation and show query semantics: how do I
ask for all paragraphs in the chapter, all text authored by Mazzini, and the source-order body
with the letter included exactly once?
@@@@@@

======
**Accept — and the decision is: the Mazzini letter is a container node, not a block and not a
relation.** I conflated the two in the prose; picking one. It is a **container node** with
`role=embedded` and an authorship override (`Mazzini`), holding its own ordered child paragraphs.
Rationale: it has internal paragraph structure (so not a bare block) and it is **contiguous** in the
source (so the tree expresses it natively — no relation needed; relations are reserved for the
*discontiguous/overlapping* case, R4/RT#12). Query semantics over the L1/L2/L3 substrate:
- *all paragraphs in the chapter* — all `paragraph` projections (L2) descending from the chapter
  node, embedded-letter paragraphs included (they are descendants).
- *all text authored by Mazzini* — the subtree under the node whose `authorship=Mazzini` (an
  attribute query, L3), independent of depth.
- *source-order body, letter once* — an in-order walk of L1 atoms; each atom appears once, the
  embedded node is simply the contiguous atom-span `[start_id … end_id]`. No double-count because
  the letter is *containment*, not a cross-cutting relation.
Shown in §11. §3.1 updated to name "contiguous embedded sub-document = container node with
`role=embedded`."
======

@@@@@@
**Codex follow-up #6 — agree on container, but §11 double-owns atoms and misplaces the example.**

The Mazzini letter as a contiguous embedded container is the right representation. Two details in
§11 should be corrected before it becomes the exemplar. First, containers should generally not own
the same body atom as their child leaf projection; `n_mazz` and `n_mazz_v1` both list `a_0042`,
which makes source-order walks depend on a convention not stated. Prefer: containers own child
nodes and optional heading/signature atoms; leaf projections own body atoms. Second, the example
places `n_mazz` under `n_p1c1`. If this is illustrative only, say so loudly; if it is meant as a PLL
slice, put the letter under its real chapter or use neutral ids. The whole point of the worked
example is to remove ambiguity, so false locality hurts.
@@@@@@

======
**Response to Codex #6 — accept both; §11 corrected.** (1) **Double-ownership fixed:** `n_mazz` (the
container) no longer lists `a_0042`; it owns its child node plus the optional heading/signature atoms,
and the body atom belongs solely to the leaf projection `n_mazz_v1`. Source-order walks now depend on
"leaf projections own body atoms," a stated rule, not a convention. (2) **False locality removed:** I had
not verified which chapter the Mazzini letter actually sits in — placing it under `n_p1c1` (Capitolo
Primo) asserted a locality I cannot confirm «unverified» (would need a read of `output/italian_clean.md`
for the letter's real container). §11 is now marked **schematic** and uses neutral container ids so it
demonstrates the shape without claiming a placement. The existence of an embedded letter is from
`findings/pll.md`; its exact chapter is deliberately left unasserted.
======

### 3.2 Three-layer body: atoms / projections / annotations (replaces F4)

*Revised post-round-1/2 — "typed block" split into three layers (D10; RT#7 / Codex #4/#7).*

- **L1 atoms** — immutable, addressed capture units (§11.1); identity is `atom_id` (text evidence +
  coordinates), distinct from structural `node_id` (Codex #4).
- **L2 projections** — group/split/type atoms into the **open, per-book** block vocabulary: paragraph,
  verse-line, tercet, aphorism, footnote-body, table, figure-caption, structured-record,
  dialogue-turn, stage-direction, dated-entry, … Identity is `node_id`. Versioned and correctable
  (R3); a leaf projection owns body atoms, a container owns children + heading/signature atoms
  (Codex #6).
- **L3 annotations** — spans, fields, attributes (speaker, date, author, citation, recipe cost/time),
  and relations. Inline stage directions, emphasis runs, and footnote call-sites are L3 **spans**, not
  blocks; a footnote = an L2 note-body projection + an L3 call-site span linked by a `note-of` relation.
- **`SpanRef` is the first-class L3 endpoint primitive** (Codex #7): `{atom_id, start, end}` (with
  optional `node_id`). L3 endpoints are a typed union — `atom_range | projection_node | span_ref` — so
  OCR flags (Codex #2), partial alignment (Codex #13), and the reserved overlap hook (Codex #12) address
  sub-block ranges without regressing to paragraph granularity.
- PLL build-now: L2 `paragraph` + `verse`, the embedded-letter container, and `SpanRef`-typed
  endpoints; the rich block types are validator-only (§6).

@@@@@@
**Red-team #7 — "typed block" is doing too much work.**

A `dialogue-turn` is a multi-line unit with speaker metadata; a `verse-line` may be a leaf; a
`structured-record` can have fields; an inline stage direction is a span; a footnote has both a
call-site and note-body. These are not the same abstraction. Define at least three layers:
source atoms, block projections, and annotations/spans/fields. If "block" remains the only word,
the model will either over-nest simple paragraphs or under-represent records, notes, and drama.
@@@@@@

======
**Accept — same three layers as RT#4; this is the half that fixes §3.2's vocabulary.** Map the
zoo onto the substrate so nothing is forced into one word:
- `paragraph`, `verse-line`, `aphorism` → **L2 leaf projections** (one or more L1 atoms, no children).
- `dialogue-turn` → **L2 projection with a `speaker` field** (L3) over its atoms.
- `structured-record` (Beeton recipe) → **L2 projection carrying typed fields** (L3:
  `ingredients`, `cost`, `time`).
- inline stage direction → **L3 span annotation** inside another projection's atom range (not its
  own block).
- footnote → **L2 projection** (the note body) **plus an L3 span** (the call-site) linked by an
  **L3 relation** (`note-of`). This is the only clean way to carry "both a call-site and a
  note-body" your point names.
So "block" stops being the only word: L1 atoms / L2 projections / L3 annotations-spans-fields-relations.
§3.2 rewritten to this; verse and the embedded-letter case in §11 use it.
======

@@@@@@
**Codex follow-up #7 — agree; make span refs a first-class endpoint type.**

The L1/L2/L3 mapping handles the block vocabulary cleanly. The main addition I would require is a
formal span-reference shape, e.g. `{atom_id, start, end}` or `{node_id, atom_id, start, end}`.
Footnote call-sites, inline stage directions, emphasis, OCR flags, and partial alignments all need
that same primitive. If L3 relations only accept `node_id`s, the design will recreate the paragraph
granularity problem when the first relation targets half a sentence.
@@@@@@

======
**Response to Codex #7 — accept; `SpanRef` is the unifying L3 primitive.** Defining it now:
`SpanRef = {atom_id, start, end}` (optionally `node_id` when the span is interpreted through a
projection). L3 endpoints are a typed union — **`atom_range` | `projection_node` | `span_ref`**. Every
sub-block referent uses it: footnote call-sites, inline stage directions, emphasis runs, OCR flags
(Codex #2), and partial alignment (Codex #13). Without it, the first relation that targets half a
sentence re-introduces the paragraph-granularity problem the whole substrate exists to kill. This is the
single largest addition this round; it lands in §3.2/§3 (relation contract) and is shown in §11.
======

### 3.3 Read-fields: designation, title, matter, authorship

- **Designation** ≠ **descriptive title**; both are optional, source-read display
  fields. Designation kinds observed: ordinal-word, Roman, global-Arabic, proper-name,
  date, headword-string, dotted-decimal.
- **Authorship/attribution is per-node and can go to the span** (Pepys editor splices
  mid-sentence; EB per-sub-section signatures). It is an overridable attribute, not a
  book-level constant; scope is `work | witness | translation | span`.
- **Three orthogonal status axes** (RT#8 / Codex #8), not one bag:
  - **role** — `front | body | back`, *structural matter only* (never `excluded`).
  - **authorship** — who, at the scope above.
  - **provenance_class** — editorial status: `authorial | editorial | translator-note | transcriber |
    generated-TOC | scan-OCR-furniture | source-wrapper | renderer-added`.
- **Pipeline participation is derived, not a `role` value** (Codex #8): policy computes behavioral
  flags `translatable` / `alignable` / `counts_for_retention` / `rendered`, and validators switch on
  *those* — so `provenance_class` can grow without hardcoding `translator-note` into every step.
  `validate.check_word_count_preservation` keys on `counts_for_retention`, not on a `provenance_class`
  literal.

@@@@@@
**Red-team #8 — role/matter/authorship need witness and editorial status, not just values.**

`front | body | back` is a useful structural role, but extraction also needs to distinguish
authorial text, editor/transcriber additions, translator notes, generated tables of contents,
scan/OCR furniture, source wrapper text, and renderer-added artifacts. Likewise authorship may
be work-level, witness-level, translation-level, or span-level. If those statuses are flattened
into generic attributes now, later validators will not know whether text should be translated,
rendered, aligned, or excluded from word-count preservation.
@@@@@@

======
**Accept — add a `provenance_class` axis orthogonal to structural role and to authorship.** Three
independent axes, not one flattened bag:
- **role** (`front | body | back`) — structural position.
- **authorship** (`work | witness | translation | span` scope) — who.
- **provenance_class** (`authorial | editorial | translator-note | transcriber | generated-TOC |
  scan-OCR-furniture | source-wrapper | renderer-added`) — editorial status, the new axis.
This is not speculative: the live `validate.check_word_count_preservation` (`steps/validate.py`)
already needs it implicitly — it compares clean vs reconciled word counts and would mis-count if a
Gutenberg wrapper or a generated TOC were folded into "body." `provenance_class` is what lets a
validator decide translatable / alignable / counted / excluded without guessing. Pairs with RT#3's
capture-with-role (furniture is captured with `provenance_class=…, role=excluded`, not dropped).
§3.3 gains this axis.
======

@@@@@@
**Codex follow-up #8 — agree on the axis; do not overload `role=excluded`.**

`provenance_class` is the missing concept, but `excluded` should not become a `role` value if
`role` means `front | body | back`. Exclusion is pipeline participation, not structural matter.
Use a separate field such as `inclusion`, `processing_scope`, or booleans derived from policy
(`translatable`, `alignable`, `counts_for_retention`, `rendered`). Even better, validators should
depend on those behavioral flags rather than switching directly on a growing
`provenance_class` enum. That keeps "translator-note" from becoming a hardcoded special case in
every later step.
@@@@@@

======
**Response to Codex #8 — accept; don't overload `role`, derive behavioral flags.** Correcting my own
RT#3/RT#8 wording: `role` stays strictly `front | body | back` (structural matter). Exclusion is
*pipeline participation*, a different axis — carried as `processing_scope` and surfaced as
policy-derived behavioral flags: `translatable`, `alignable`, `counts_for_retention`, `rendered`.
Validators switch on those flags, **not** on the `provenance_class` enum — so `provenance_class` can grow
(translator-note, transcriber, renderer-added) without becoming a hardcoded special case in every step.
`validate.check_word_count_preservation` keys on `counts_for_retention`, not on `provenance_class ==
"scan-OCR-furniture"`. §3.3 corrected (no `role=excluded`).
======

### 3.4 Identity — durable `node_id` + handle policy (keystone — DECIDED, Option A / D33)

*Revised post-round-2 (D11/D12; Codex #9): "basis" no longer means identity. O1 resolved by user
ruling D33 — Option A ("store-and-rebind"); see the decision note at the end of this section.*

- **Internal identity is an opaque, durable `node_id`** — assigned once (at B-time), persisted in the
  structure map, never re-derived from position, designation, or content. It is the root every overlay,
  relation, and revision key pins to. (Atom-level evidence pins to a distinct L1 `atom_id` — Codex #4.)
  **Minting split (D33):** humans author/approve the *container* tree (~61 nodes for PLL, the §3.5
  HITL-tractable scale); the extractor *machine-mints* leaf `node_id`s (counter/ULID) and persists them
  in the same map — humans spot-check, never hand-key thousands. No `node_id` carries a positional
  component; the readable `p1_ch01.p3`-style string is a handle (below), not the id.
- **Designation / position / headword are handle policies and citation semantics, not identity.** Each
  node-class carries a `handle_policy` (`position-path` | `designation-string` | `title` | …), inherited
  down the tree unless overridden, declared in the structure map — a **policy per node class** (RT#9),
  not one book-wide enum. The visible handle (F3's `short` / `parse_md` / `html_slug`, the provenance
  key, the revision key) is a **rendering** of `(node_id, handle_policy)` — one source of truth, not
  parallel schemes.
- A handle that changes (a missed node is inserted, `p2_ch18` shifts) leaves `node_id` fixed; the old
  handle survives as an **alias record** (§11.2: `{handle_type, value, scope, …, status}`) so existing
  citations and caches resolve.
- Tractatus and EB make designation-string **handles** first-class (especially as cross-reference
  anchors) but do **not** force designation-string *internal* identity — a stronger, cleaner model
  (Codex #9).
- **`content-key` is not an identity basis** — no forcing witness; dropped (D12). If a book ever needs
  content-derived handles, that is a future handle policy with collision/migration behavior defined then.
- Identity is **depth-varying in the stability of its handle**, not in whether identity exists: container
  handles are reliable; block-granularity correspondence is alignment-mediated (§4 R5).
- **Re-binding — the residual hard part (D33).** Each node stores `rebind_anchors` — *checkpoints, not
  identity* (R2): a **geometry** anchor (page + bbox region, from D30's Fitz word-boxes — the signal most
  invariant to OCR re-tokenization, hence primary), a **fuzzy/fail-loud content fingerprint** (never the
  exact-substring the live tree tombstoned), and a **structural-path** tie-break. On re-extraction a node
  re-attaches to the fresh atoms occupying its stored region, verified by fingerprint; unique + confident
  → bind; ambiguous or below threshold → **fail loud → human re-approval** (D14 governance). Geometry is a
  *strength when a scan exists* (PLL has the LOC PDF); the portability floor for text-only sources is
  content + structural-path.

> **O1 — DECIDED (user ruling D33): Option A, "store-and-rebind."** `node_id` is an opaque label
> *stored* in B's structure map (the `typography.json` precedent), not *computed* from raw — so it is
> stable (stored), reproducible *as committed/versioned data*, and derived from neither position nor
> content (R2-clean). The rejected alternative was a hash/derivation (Option B): from-scratch
> recomputability at the cost of the exact mutable-basis churn R1/R2 killed. **Acknowledged one-way
> gate:** the structure map is therefore a hand-tuned, *irreproducible* artifact and **joins the
> regeneration-guard family** (translations, `typography.json`) — never blown away and regenerated;
> deleting and re-authoring it mints *different* ids by design. The user accepts this as a one-way gate,
> revisitable ("tweak the door") only after the initial build-out shows how it behaves in practice.

@@@@@@
**Red-team #9 — a single per-book identity basis is too coarse.**

Real books can mix identity regimes: chapters by position, appendices by title, glossary
entries by headword, footnotes by call number within a chapter, figures by printed label, and
paragraphs by alignment checkpoint. The basis should probably be a policy per node class/depth
(with inheritance), not one enum for the whole book. `content-key` is also underspecified and
has no current forcing witness; either remove it until needed or define it as an opaque
plugin-provided key with collision and migration behavior.
@@@@@@

======
**Accept — this and RT#10 together rewrite the keystone O1; stated once here.** You are right twice:
the basis must be per-node-class, and `content-key` has no forcing witness. The revised O1:
- **Internal identity is a durable opaque `node_id`**, assigned once at L1/B-time and persisted in
  the structure map — *neither* position *nor* designation *nor* content. (This is RT#10; it is also
  R2 applied to identity itself: if content can't *define* identity, neither can position — both are
  renderings.)
- **"Basis" demotes to a per-node-class handle policy** with inheritance down the tree: PLL chapters
  render their citation handle by `position-path`, an appendix could render by `title`, a glossary
  entry by `headword`, Tractatus propositions by `designation-string`. Declared in the structure
  profile/map, inherited unless overridden — exactly your "policy per node class/depth," not one
  book-wide enum.
- **`content-key` is dropped from the enumerated bases.** No witness forces it, and an unpopulated
  enum slot violates seam-validator discipline (design the extensible *mechanism* — handle policies
  are open — not a named-empty value). If a book ever needs content-derived handles, it is added then
  as a policy, with the collision/migration behavior you ask for defined at that point.
Reframes §3.4 and O1; the firmest single change in this pass.
======

@@@@@@
**Codex follow-up #9 — agree; rewrite R1/O1 language so "basis" no longer means identity.**

This is a good correction and should propagate back into the plan text, not only the response
block. R1 still says "identity is per-book and captured" and §3.4 still begins with "An identity
has a basis." After D11/D12, the precise claim is: internal identity is opaque and durable;
designation/position/headword are handle policies and citation semantics. Tractatus and EB still
force designation-string *handles* to be first-class, especially for cross-refs, but they no longer
force designation-string internal identity. That is a stronger, cleaner model.
@@@@@@

======
**Response to Codex #9 — accept; propagated into the body, not just here.** Rewrote §3.4's opening: it no
longer says "An identity has a basis" — it states internal identity is an opaque durable `node_id`, and
designation/position/headword are **handle policies and citation semantics**, not identity. R1 reworded
the same way: it no longer claims "identity is per-book and captured." The precise residual force of
Tractatus and EB is preserved and sharpened: they make designation-string **handles** first-class
(especially as cross-reference anchors), but they do **not** force designation-string *internal*
identity. Leaving the correction only in response blocks would have left the body asserting the
falsified model — your point. Done in this pass; §3.4 + R1 edited.
======

@@@@@@
**Red-team #10 — derived handles should not all be derived from the same mutable public basis.**

Public HTML slugs, revision-cache keys, provenance ids, and internal node ids have different
stability requirements. If `position-path` changes because a missed node is inserted, every
downstream handle shifts unless there is a persistent internal id and an alias/migration table.
For PLL, `p2_ch18` is a good citation view, but making it the root of all revision/provenance
keys repeats a milder version of the current fragility. Consider `node_id` as durable internal
identity, with basis-derived handles as renderings plus recorded aliases.
@@@@@@

======
**Accept — `node_id` is the keystone answer; this is the other half of the O1 rewrite (see RT#9).**
This is the corrections.json lesson (`feedback_existing_path_failures_as_evidence`) generalized: PLL
built a position/content-derived handle as the *root* of identity, watched re-extraction shift it,
and paid for it. Making `position-path` the root of every revision/provenance key repeats that in a
milder key — you are right. So:
- **`node_id`** = durable internal identity (the root). The three F3 strings (`short`, `parse_md`,
  `html_slug`), the provenance key, and the revision key are all **renderings** of `(node_id, handle
  policy)`, not parallel sources — which still collapses F3's three schemes into one source of truth,
  just rooted on `node_id` instead of on the designation parse.
- A handle that changes (a missed node is inserted, `p2_ch18` shifts) leaves `node_id` fixed; the old
  handle is **recorded in an alias table** so existing citations/caches resolve. `p2_ch18` stays a
  fine *public citation view* — it is just no longer the thing identity is stored under.
Folded into §3.4/§7.3; the alias table is a named artifact in §3.6 and tested in §9 (RT#17).
======

@@@@@@
**Codex follow-up #10 — agree; aliases need scope, type, and validity.**

The alias table should not be just `aliases: []` on each node. A reused visible handle is plausible
across versions, languages, witnesses, or handle types. Make aliases records:
`{handle_type, value, scope, locale_or_witness, target_node_id, valid_from, valid_to, status}`.
Then `p2_ch18`, an HTML slug, a parse-md key, and an old revision-cache key can coexist without
pretending they are the same namespace. This also gives the stale-artifact tests something precise
to assert: every active alias resolves to exactly one node in its declared scope.
@@@@@@

======
**Response to Codex #10 — accept; aliases are records, not a bare list.** Replacing `aliases: []` with
records: `{handle_type, value, scope, locale_or_witness, target_node_id, valid_from, valid_to, status}`.
That lets `p2_ch18`, an HTML slug, a parse-md key, and a retired revision-cache key coexist without
pretending they share a namespace, and it spans versions/languages/witnesses. The §9 integrity test
gets its precise assertion from this: **every `status:active` alias resolves to exactly one node within
its declared `scope`** (collision across scopes is allowed; collision within a scope fails loud). §11
alias fields updated.
======

### 3.5 The structure map (B's output) — proposed, open ruling O3

The durable catalogue is a hand-authorable sidecar — the **`typography.json`
precedent**: a scan-verified, human-curated artifact that is the sole source of truth,
applied at one site. The user offered human-in-the-loop tagging as the first-pass
authoring path; it dissolves the "extraction cannot build the tree neutrally" problem by
moving tree-building out of A and into B. Caveat the red team established: HITL is
tractable for **targets** (PLL ≈ 61 containers) but not for large validators (Pepys
≈ 4,000 blocks); the inference plugins are the path at that scale. This plan does **not**
commit to building the tooling — that is **O3**.

@@@@@@
**Red-team #11 — the sidecar lifecycle is the real hard part.**

Calling the structure map the sole source of truth is dangerous unless stale-map detection is
first-class. The map needs to declare which raw/reconciled source version it was authored
against, how suggestions differ from approved human decisions, how changed OCR invalidates refs,
and how conflicts are reviewed. `typography.json` is a useful precedent, but structure is more
central: a stale structure map can silently misroute every later translation, cache, and
alignment.
@@@@@@

======
**Accept — "sole source of truth" without stale-detection is the trap, agreed.** The
`typography.json` precedent is honest only if I carry its *failure* too: it logs unmatched fragments
at typeset (`typeset` reports sidecar fragments that matched nowhere) — that fail-loud is the part
worth copying, and structure needs a stronger version because a misroute is silent, not a dropped
italic. The structure map header declares **the source artifact id + content hash it was authored
against**; load fails loud when the hashed L1/reconciled source has changed since authoring
(refresh-or-migrate required, never silent best-effort). Each entry records **decision provenance**
(`human-approved` vs `plugin-suggested` vs `inherited`) so review and re-suggestion don't overwrite
human rulings. Same spine as RT#5 (C-correction audit) and RT#17 (stale-fail tests); all three
consolidate into **§3.6 Lifecycle & governance**, and the hash/version field is what RT#17's
"declares the source it was authored against" test asserts.
======

@@@@@@
**Codex follow-up #11 — agree; one hash is not enough lineage.**

The fail-loud stale rule is right. The artifact header should be a small lineage manifest, not a
single `source_hash`: raw witness ids + hashes, atom-stream ids + hashes, canonical projection id +
hash, structure profile/schema version, and recognizer/extractor version where code was involved.
That is the minimum needed to explain why a sidecar is stale. A single hash against "the reconciled
source" hides whether the raw OCR changed, the normalization changed, or only a projection changed;
those cases need different migration behavior.
@@@@@@

======
**Response to Codex #11 — accept; the header is a lineage manifest.** One `source_hash` collapses three
distinct staleness causes. Replacing it with a manifest: **raw witness ids+hashes**, **atom-stream
ids+hashes**, **canonical projection id+hash**, **structure-profile/schema version**, and
**recognizer/extractor version** where code participated. That is the minimum to answer *why* a sidecar
is stale and therefore *which* migration to run — raw OCR changed (re-capture, Codex #5) vs normalization
changed (re-derive offsets) vs only a projection changed (re-attach L2/L3) are different repairs. Same
field set the canonical-stream fix in Codex #1 introduces — one manifest, referenced by both. §11 header
revised; §9 stale-lineage test (Codex #17) asserts against it.
======

---

## 4. The five rulings (revised post-red-team)

Each cites the witness that forced it and what it changes in code. R1–R3 are firm
proposals; R4–R5 carry open sub-questions (§8).

- **R1 — Internal identity is a durable `node_id`; designation/position/headword are handle policies.**
  *(Revised twice — see Codex #9.)* *Forced by:* Tractatus (dotted-decimal is the cross-ref **handle**;
  `findings/tractatus.md` §6) and EB (headword is the citation **handle**; dangling cross-refs key on
  the designation string; `findings/britannica_1911.md`). An earlier draft's "designation = display,
  position = identity" was falsified by both — and so was its successor, "identity is a per-book
  *basis*": after D11/D12, identity is *neither* position nor designation nor content, but an opaque
  `node_id`, and those three are **handle policies** rendered from it. Tractatus/EB force
  designation-string *handles* to be first-class, not designation-string internal identity. *Changes:*
  `ChapterIdentity` (F3) → opaque `node_id` + rendered handles + alias records (§3.4); the designation
  reader leaves the identity path entirely, surviving as a handle-policy renderer and cross-ref anchor.

- **R2 — Content fragments *checkpoint* identity; they do not *define* it.**
  *Forced by:* Pepys (419/2901 day-entries non-unique at a 40-char anchor;
  `findings/pepys.md`) and PLL's own history — `cleanup.py` already built a 40-char
  content anchor (`extract_corrections_from_diff` / `apply_corrections`, exact-substring
  `if find not in text: continue`), watched re-extraction silently invalidate it, and
  migrated to a full-text cache (recorded in the live `CLAUDE.md`). *Changes:* identity
  is the basis (R1); a *fuzzy, fail-loud* content anchor is a re-attachment aid only —
  never the exact-substring primitive the live tree tombstoned.

- **R3 — Stage A is book-specific and correctable, not universal-dumb.**
  *Forced by:* Hamlet (`findings/hamlet.md`) — atomization needs the turn parse
  (`[_Reads._]` with no surrounding blanks must split; `[_Writing._]` with blanks must
  not), and typing is ambiguous (`He.` / `Dead.` are byte-identical to speaker labels
  `Both.` / `Danes.`, separable only by turn-state). A mis-*typed* atom cannot be fixed
  by a B that only groups. *Changes:* A emits a *typed* stream via the book's
  block-classifier; **B can re-atomize and re-type, not merely re-group.**

- **R4 — Contiguous embedding (build-now) is separated from overlapping hierarchy
  (joint-only, named unsolved).**
  *Forced by:* Hamlet's play-within-a-play is *interleaved* (the frame audience comments
  turn-by-turn), so the inner play's blocks are a discontiguous subsequence — the
  overlapping-hierarchy / TEI-milestone problem, which a tree of nested source-order
  intervals cannot natively express. *Decision:* PLL's contiguous embedded letter is
  build-now; overlapping hierarchy is flagged **unsolved, joint-only** — not papered
  over as "embedded sub-document." *Open:* O4.

@@@@@@
**Red-team #12 — "unsolved" may be more expensive than a minimal relation now.**

You do not need full TEI milestones to avoid painting the model into a corner. A cheap joint
could be a relation whose target is an ordered set of block refs/ranges with
`contiguous: false`. That would let Hamlet say "these blocks participate in the inner play"
without forcing the main containment tree to overlap. Leaving no representational hook at all
means the first overlapping target may force a structural redesign instead of adding a relation
type.
@@@@@@

======
**Accept — this strengthens R4; the distinction it preserves is "reserve the hook ≠ solve the
problem."** Right that "unsolved" with *no representational hook* is the expensive failure: the
first overlapping target then forces a tree redesign. Take your cheap joint — an **L3 relation**
`participates-in` whose target is an ordered set of L1/L2 refs with `contiguous: false`. The
**containment tree stays strictly non-overlapping** (no nested-interval violation); Hamlet's inner
play is expressed as such a relation over the discontiguous turn-blocks, *not* as a tree subtree
(which is the over-claim the red team caught in `findings/hamlet.md`). This is precisely the §6
seam-validator discipline — design the joint, don't build the engine — so it is build-now only as a
**reserved relation type with no PLL instance**, conformance-checked against Hamlet. R4 revised:
overlapping *hierarchy* stays unsolved (no tree overlap), but the *relation hook* is reserved now.
O4 narrows accordingly.
======

@@@@@@
**Codex follow-up #12 — agree; reserve the hook with typed endpoints.**

The relation hook is the correct compromise. I would avoid "ordered set of L1/L2 refs" as an
untyped union, though. Define endpoint variants now: `atom_range`, `projection_node`, and
`span_ref`, with an ordered `members` list and optional per-member role labels. That keeps Hamlet's
inner-play relation from becoming a free-form bag while still avoiding tree overlap. The tree
remains non-overlapping; the relation can be discontiguous.
@@@@@@

======
**Response to Codex #12 — accept; typed endpoints, not an untyped bag.** "Ordered set of L1/L2 refs" was
too loose. The `participates-in` hook (and every L3 relation) takes a typed `members` list over the
`atom_range | projection_node | span_ref` union (Codex #7), ordered, with optional per-member role
labels. Hamlet's inner play is an ordered member list of discontiguous turn nodes; the containment tree
stays non-overlapping while the relation is discontiguous. No PLL instance is built — it remains the
reserved, Hamlet-conformance-checked hook of D15, now with a typed signature instead of a free-form
target.
======

- **R5 — A paragraph-level cross-language aligner is in scope for the target.**
  *Forced by:* the live edition already ships a facing-page provenance feature (1,118
  `data-prov` cross-column links) that depends on IT↔EN paragraph correspondence, and
  it is *already broken*: `typeset.py` reuses the English paragraph index on the Italian
  column (`it_paras[para_num-1]`); 23 of 58 chapters have divergent IT/EN paragraph
  counts → 14 provable cross-column mispoints + 82 unresolvable provenance entries.
  "Chapter mapping known by construction" holds (PLL translates per-chapter; Dante shows
  it degrades to count+order inference for an independent translation). *Changes:* the
  aligner is a concern-C component to build for PLL, not a deferred nicety. (The live
  bug is a separate live-PLL matter; see `feedback_existing_path_failures_as_evidence`.)

@@@@@@
**Red-team #13 — call this block alignment, not paragraph alignment, unless you mean it.**

Cleanup, translation, and human revision can split, merge, delete, or reorder paragraphs; verse
and embedded documents are not naturally paragraph-indexed. The target may start with PLL prose
paragraphs, but the relation should be many-to-many over stable source/target block ids with
confidence and method metadata. A paragraph index is acceptable as one alignment method, not as
the durable relation key.
@@@@@@

======
**Accept — and the live bug is the proof your point is right.** `typeset.py` mispoints precisely
because it used a **paragraph *index* as the key** — it reuses the EN index on the IT column
(`it_paras[para_num-1]`), and where IT/EN paragraph counts diverge (23/58 chapters) the index points
at the wrong block. That is the position-index-as-key failure you name, shipped. So alignment becomes
an **L3 relation**: many-to-many over stable `node_id`s, carrying `confidence` and `method`
(`by-index` / `by-content` / `human`). A paragraph index is one *method* that produces edges, never
the durable key. Renaming R5 from "paragraph-level aligner" to **block-level alignment relation**;
it moves under concern C as a relation type (consistent with RT#4/7's L3). The live `typeset.py` fix
stays a separate live-PLL matter (`feedback_existing_path_failures_as_evidence`), cited here only as
evidence, not pulled into engine scope.
======

@@@@@@
**Codex follow-up #13 — agree; partial alignment requires span endpoints too.**

Renaming this to block-level alignment is right, and the durable key must be `node_id` or span refs,
not paragraph index. One more constraint: many-to-many node edges are still too coarse for some
translation edits. Alignment endpoints should allow whole projection nodes *or spans within nodes*,
with method/confidence on each edge and an alignment-set version. PLL can start with paragraph-node
edges, but the relation contract should not prevent a future human correction from aligning only the
second half of a paragraph.
@@@@@@

======
**Response to Codex #13 — accept; alignment endpoints admit spans.** Closing the SpanRef trio
(Codex #2/#7/#12): alignment edges accept `projection_node` **or** `span_ref`, each edge carries
`method` + `confidence`, and the relation set carries an `alignment_set` version. PLL ships with
paragraph-node↔paragraph-node edges (the common case), but the contract does not forbid a later human
correction aligning only half a source paragraph to a target span — no schema change required when that
first partial edit arrives. R5/D7 reworded from "paragraph-level" to span-capable block alignment.
======

---

## 5. What survived the red team (do not relitigate)

Five independent witness-as-battering-ram passes each conceded the following; they are
settled unless an audit block reopens them.

- The **A/B/C decomposition** itself — every ram conceded the shape holds.
- **Concern A's flat, source-ordered, no-meaning-imputed-to-order capture** — vindicated,
  especially by EB (where reading order is meaningless and A is correct to refuse to read
  narrative into it). The break on A was the "decision-free" overclaim (→ R3) and the
  anchor-as-identity choice (→ R2), not the flat-list idea.
- The **ragged recursive container tree** (§3.1) — genuinely present across witnesses.
- **Human-in-the-loop for targets** — tractable at PLL scale; the scale ceiling (O3) is
  the open part, not the premise.
- **Depth-varying identity** (§3.4) — descriptively confirmed on live data.
- **Container-level cross-language alignment** — `typeset.py · _align_chapters` already
  pairs IT/EN chapters positionally; the "part header invisible in EN" attack *confirmed*
  the model rather than breaking it.

---

## 6. Scope — build-now vs joint-only

Seam-validator discipline: implement what PLL needs; design the joint for the rest, and
let the named witness be the conformance check that the joint is coherent.

| Capability | Witness(es) | Build now (PLL)? | Note |
|---|---|---|---|
| Ragged container tree, depth 0–3 | PLL, Kybalion | **Yes** | PLL is shallow + fixed; depth must not be schema-baked (F2) |
| Typed blocks: `paragraph`, `verse` | PLL, Dante | **Yes** | Verse is build-now (PLL set-off verse) |
| Embedded sub-document (contiguous) | PLL | **Yes** | The Mazzini letter |
| `position-path` identity basis + checkpoints | PLL | **Yes** | R1/R2 |
| Paragraph-level IT↔EN aligner | PLL, Dante | **Yes** | R5 (live feature already depends on it) |
| Ordinal-word designation reader | PLL | **Yes** | The existing Italian reader, demoted off the identity path |
| `designation-string` identity basis | Tractatus, EB | Joint only | Design the basis enum so it *can* hold this |
| Graph cross-ref edges (may dangle) | EB | Joint only | Concern-C edge type with external/unresolved semantics |
| `content-key` identity basis | — | Joint only | Enum slot; no current target |
| Depth-from-designation (dotted-decimal) | Tractatus | Joint only | Depth-deriver plugin seam, unpopulated for PLL |
| Rich block types (table, figure, recipe-record, dialogue-turn, stage-direction) | Beeton, Hamlet | Joint only | Open block vocabulary must *admit* them |
| Overlapping / interleaved hierarchy | Hamlet | **No** (unsolved) | R4 — named limit, not designed |
| Heterogeneous children | Atlantic | Joint only | Tree must not assume homogeneity |
| Per-node / per-span authorship | EB, Pepys, Atlantic | Joint only | Attribute slot; PLL is single-author with a few overrides |

@@@@@@
**Red-team #14 — build-now cannot be validated by PLL alone.**

The table says ragged depth 0-3 is build-now, but PLL exercises only one shallow shape. The test
strategy later mentions a second-structure fixture; make that fixture part of build-now, not a
nice-to-have. It can be tiny and synthetic, but it must exercise at least one non-PLL shape
(depth 0 or designation-string identity) before the schema is considered born. Otherwise
the "joint" is only reviewed in prose.
@@@@@@

======
**Accept — promote the second-structure fixture from §9 to a build-now gate.** Right that PLL
exercises one shallow shape, so "ragged depth 0–3 is build-now" is, today, prose. This is exactly
`feedback_single_fixture_blind_spots`: a single all-pass PLL fixture verifies one point; the axis a
port generalizes (depth-0, designation-string identity) is born untested. So the synthetic fixture —
tiny, hand-written, deliberately *built to differ* (a depth-0 Kybalion-shaped book **and** one
designation-string-identity node) — is a **precondition for the schema being "born,"** not a §9
nice-to-have. Moved into §6 as a build-now row and made a gate in §9. Caveat I will not paper over:
a synthetic fixture proves the *joint is exercised*, not that the real second book is *correct* —
that still waits on a real non-PLL target.
======

@@@@@@
**Codex follow-up #14 — agree; keep the fixture cheap and explicitly schema-focused.**

Promoting the second-structure fixture to a gate is correct. I would specify that it is a
hand-authored structure fixture, not a full OCR/reconcile integration target. It should exercise
schema and adapter behavior: depth-0 body, designation-string handle policy, alias uniqueness,
stale sidecar failure, and relation endpoint resolution. Making it a full pipeline fixture too
early would bury the structural signal under language/OCR dependencies and recreate the BR-002
problem under a new name.
@@@@@@

======
**Response to Codex #14 — accept; the fixture is structure-only.** Tightening D18: the build-now gate is a
**hand-authored structure fixture** exercising schema + adapter, not an OCR/reconcile integration target.
Its assertions: depth-0 body, designation-string handle policy, alias uniqueness within scope, stale
lineage-manifest failure, and relation-endpoint resolution. Making it a full-pipeline fixture this early
would bury the structural signal under language/OCR dependencies — the BR-002 failure mode under a new
name, as you say. The real non-PLL pipeline target stays a later, separate validation (my own RT#14
caveat).
======

---

## 7. Integration with the existing engine

This redesigns four existing things (F1–F4). Proposed shape:

- **7.1 — Split structure recognition out of `LanguagePlugin` (resolves BR-021).**
  Recognition is per-**book**, not per-language (F1). Proposed: a **`StructurePlugin`**
  seam (parallel to `LanguagePlugin`, selected per book) carrying the four narrow
  readers — boundary-segmenter, designation-reader, block-classifier, depth-deriver —
  each *optional* pre-suggesters behind B. The **structural model** (tree, typed blocks,
  identity protocol) is book-agnostic **core** (honoring `feedback_engine_agnostic`); only
  recognition is plugged. For PLL the plugin is thin (the existing Italian ordinal
  reader, relocated). *This is open ruling O2* — keep in `LanguagePlugin`, move to a new
  `StructurePlugin`, or core+narrow-seams.

@@@@@@
**Red-team #15 — a per-book `StructurePlugin` risks turning future books into Python projects.**

Some recognition needs code, but much of it is declarative: heading regexes, running heads,
matter labels, designation grammars, numbering scopes, and block split rules. Prefer a layered
surface: reusable structure profiles + manifest data for common cases, with a narrow code escape
hatch for books like Hamlet. If every new translation requires a custom plugin class, the engine
has moved hardcoding from core into per-book code without making authoring much easier.
@@@@@@

======
**Accept — this refines O2, and the codebase already leans this way.** A per-book `StructurePlugin`
class for every book would relocate hardcoding from core into per-book Python — a real regression.
The layered surface you describe is also the existing grain: `Structure.running_heads` is already
**declarative manifest data** anchored by the plugin (BR-004), not code. So O2's answer narrows to:
1. **Declarative structure profile** (heading regexes, running heads, matter labels, designation
   grammar, numbering scope, block-split rules) as data — covers the common case; new books are
   authored, not coded.
2. **Narrow code escape hatch** (a thin reader) only for irreducibly procedural recognition —
   Hamlet's turn-parse (R3), where typing depends on turn-state no regex captures.
PLL is **profile + the existing thin ordinal reader relocated**, not a bespoke class. This also keeps
`feedback_engine_agnostic` intact: core carries the *model*, the profile carries the *book's*
opinion, code is the exception. O2 reframed from "three-way pick" to "profile-first, code-escape."
======

@@@@@@
**Codex follow-up #15 — agree; avoid building a declarative mini-language.**

Profile-first is the right default, and BR-004 already proves the repo wants that shape. The trap
on this side is overcorrecting into a bespoke structure DSL that is harder than a plugin. Keep the
declarative profile to boring data primitives: regex lists, label vocabularies, numbering scopes,
handle policies, and simple block split rules. The moment a rule needs stateful parsing
(Hamlet-style turn state), use the code escape hatch rather than adding control flow to JSON.
@@@@@@

======
**Response to Codex #15 — accept; profile = data primitives, never a DSL.** The overcorrection you name
is real: a bespoke structure DSL is harder to author and maintain than a plugin, and it smuggles control
flow into config. Bounding D17: the declarative profile holds only **boring data primitives** — regex
lists, label vocabularies, numbering scopes, handle policies, simple block-split rules. The moment a rule
needs stateful parsing (Hamlet turn-state, where typing depends on prior turns), it crosses into the
**code escape hatch** — no conditionals, loops, or state machines expressed in JSON. "Profile-first,
code-escape" has a hard line between the two, not a gradient that slides toward a mini-language.
======

- **7.2 — Replace `Structure` (F2) with a general structural model + per-book structure
  map.** The fixed-shape validator becomes (a) a general tree/blocks model in core, and
  (b) the book's structure-map sidecar (§3.5). `validate.py`'s shape checks become
  assertions over the structure map, not hardcoded H2/H3 counts.

- **7.3 — Rework `ChapterIdentity` (F3) → identity basis + derived handles.** One basis
  per book (§3.4); `short` / `parse_md` / `html_slug` become deterministic *renderings*
  of the basis, not parallel sources.

- **7.4 — Rework `reconciled_chapters.json` (F4) → a typed block stream.** `reconcile`
  (or a new extraction step) emits typed blocks with block identity, not a `\n\n` string.
  This is the largest change and touches M3 (reconcile) and the deferred M7 (extraction
  readiness); **sequencing is an open question** — whether to land the block model first
  behind reconcile, or as the M7 axis.

@@@@@@
**Red-team #16 — the migration plan for existing consumers is missing.**

`cleanup.render_markdown`, `validate.check_word_count_preservation`, review flags,
chapter page maps, future translate/refine state, and typeset/provenance all assume chapter dicts
with opaque `text`. The plan should choose either a compatibility adapter
(`blocks -> reconciled_chapters.json` during transition) or a versioned cutover where every
consumer moves in one recorded branch decision. Without this, §7.4 becomes a big-bang step
contract change with unclear blast radius.
@@@@@@

======
**Accept — and the blast radius is small and now enumerated (engine tree).** Consumers of
`reconciled_chapters.json`'s `{id,title,part,text}` shape: `triage.py:286–327` (rewrites it in
place), `cleanup.py:882` (reads `text` as input), `validate.py:432–465` (word-count preservation).
Downstream `translate`/`refine`/`typeset` read `clean.md` and the translations, **not** the chapter
dicts — so they are insulated. **Ruling: compatibility adapter, not big-bang.** The block model
lands behind `reconcile`, and an adapter projects L2 → the legacy `{id,title,part,text}` dict
(`text = "\n\n".join(paragraph projections)`) so triage/cleanup/validate keep working unchanged;
each consumer then migrates to the block stream one at a time, each migration a recorded BR. This
**answers O5**: land behind reconcile with the adapter, *not* deferred to M7 as a big-bang axis. The
adapter is also the natural home for RT#17's round-trip test (legacy `text` must reconstruct from
L1 atoms). Added to §7.4; O5 resolved in §8.
======

@@@@@@
**Codex follow-up #16 — agree, with triage as the migration pressure point.**

The compatibility adapter is the right sequencing answer. The consumer list also shows the main
risk: `triage` mutates the legacy `reconciled_chapters.json` shape. Once the block stream is
authoritative, legacy mutation must not become an alternate source of truth. Either migrate triage
early, or make its legacy edits produce a patch back into L2/L3 through the same governance path.
Otherwise a post-adapter triage run can diverge from the block artifact while cleanup sees only the
legacy view. The adapter should be read-only projection unless a BR explicitly defines reverse
application.
@@@@@@

======
**Response to Codex #16 — accept; the adapter is read-only and triage migrates first.** The consumer that
makes this load-bearing is `triage` — it *rewrites* the legacy dict in place (`triage.py:286–327`), so a
post-adapter triage run could silently diverge from the block artifact while `cleanup` reads only the
legacy projection. Ruling: the adapter is a **read-only projection** (L2 → `{id,title,part,text}`),
never a write-back path. `triage` is therefore the **first** consumer migrated off the adapter (its
edits become a patch into L2/L3 through the governance path of D14), and no consumer gets
reverse-application through the adapter unless a specific BR defines it. Sharpens D16; the divergence risk
you name is exactly why triage goes first, not last.
======

---

## 8. Open rulings for your audit

- **O1 (keystone) — the identity-basis mechanism (§3.4).** Is `basis ∈ {position-path,
  designation-string, content-key}` the right enum? Is it **declared in the manifest**
  (config), **captured in Stage A** (read from the source), or both? Every other ruling
  leans on this — settle it first.
- **O2 — where structure recognition lives (§7.1):** new `StructurePlugin`, stay in
  `LanguagePlugin`, or core + four narrow seams.
- **O3 — human-in-the-loop tooling (§3.5):** build the tagging surface, and what is it?
  What is the corpus-size ceiling above which inference must lead?
- **O4 — overlapping hierarchy (R4):** is "named unsolved, joint-only" acceptable, or
  does a target need it (none identified)?
- **O5 — block-model sequencing (§7.4):** land the typed block stream behind reconcile
  now, or as the M7 extraction-readiness axis?

---

## 9. Test strategy

Per the house tiers (`tests/unit` property/separability/isolation/neutrality;
`tests/golden`):

- **Golden** — reproduce PLL's current chapter boundaries and identities through the new
  model (no regression on the live target).
- **Property** — structure operations over synthetic trees (ragged depth, heterogeneous
  children, recursion-in-body).
- **Neutrality** — no language/structure literals in core (the model must carry no
  Italian/ordinal opinion; recognition lives in the plugin).
- **Second-structure fixture (build-now gate, D18)** — per `feedback_single_fixture_blind_spots`, a
  **hand-authored structure fixture** (schema + adapter only, *not* an OCR/reconcile integration
  target — Codex #14) built to **differ** from PLL: depth-0 body, designation-string handle policy,
  alias uniqueness within scope, stale lineage-manifest failure, relation-endpoint resolution. A
  passing PLL golden alone verifies one point only.
- **Reference integrity (binding, RT#17)** — every structure-map ref resolves to an existing
  `atom_id`/`node_id`; every L3 relation endpoint resolves; every `status:active` alias resolves to
  exactly one node within its declared scope.
- **Two-tier no-loss round-trip (Codex #3/#17)** — (a) **raw**: byte-exact reconstruction from
  `raw_span` + `raw_source_hash` against the source artifact, for every captured atom; (b)
  **normalized**: reconstruction differs from raw only by declared, reversible transform operations.
  Tier (a) is the floor a `norm_layer` label cannot fake.
- **Negative tests (fail-loud, no skip-masking)** — alias collision within a scope, unresolved relation
  endpoint, and stale lineage manifest each assert the raise; a mutated source fails until the sidecar
  is refreshed or migrated.

@@@@@@
**Red-team #17 — add tests for reference integrity and stale artifact failure.**

The current test bullets cover shape, neutrality, and a second fixture, but the new model's
failure mode will be orphaned references. Add properties that every structure-map range points
to existing A atoms/blocks, every relation endpoint resolves, every derived handle is unique,
every approved sidecar declares the source artifact hash/version it was authored against, and a
changed source fails loudly until the sidecar is refreshed or migrated. Also test a no-loss
round trip: selected source text can be reconstructed from A plus overlays, modulo declared
normalizations.
@@@@@@

======
**Accept — these are the tests that match the model's actual failure mode.** Shape/neutrality tests
miss the real risk (orphaned references, silent misroute). Adding to §9 as **binding** properties
(no skip-masking, per `feedback_validate_bindings`):
- every structure-map ref resolves to an existing L1 atom / L2 projection (`node_id` exists);
- every L3 relation endpoint resolves;
- every rendered handle is unique within its scope, and every alias resolves to exactly one `node_id`;
- the sidecar declares the source hash it was authored against, and a mutated source **fails loud**
  (assert the raise, exercise the failure branch — not a happy-path fixture);
- **no-loss round-trip**: selected source reconstructs from L1 atoms + declared overlays modulo the
  recorded normalization layers (this is where RT#3's `normalization_layer_id` earns its place and
  RT#16's adapter is checked).
These are the same governance spine as RT#5/11, now with teeth. §9 expanded; the round-trip is the
acceptance gate for the §11 worked example.
======

@@@@@@
**Codex follow-up #17 — agree; split raw round-trip from normalized round-trip.**

These are the right tests. I would make the no-loss assertion two-tiered: raw reconstruction from
`raw_span` against the source artifact must be exact for captured atoms, and normalized
reconstruction may differ only by declared transform operations with a map. If the only test is
"modulo recorded normalization layers," the normalizer can hide loss. Also add explicit negative
tests for alias collision, unresolved relation endpoints, and stale lineage manifests; those are the
failure modes this design is trying to make impossible to miss.
@@@@@@

======
**Response to Codex #17 — accept; two-tier round-trip + explicit negative tests.** The no-loss assertion
splits: **(a) raw** — reconstruction from `raw_span` against the source artifact must be **byte-exact**
for every captured atom (this is the tier a label cannot fake, Codex #3); **(b) normalized** —
reconstruction may differ from raw **only** by declared transform operations carrying a reversible map.
"Modulo recorded normalization layers" alone lets the normalizer hide loss, so (a) is the binding floor.
Adding explicit **negative** tests: alias collision within a scope, unresolved relation endpoint, and
stale lineage manifest — each must fail loud, asserted on the raise, not skipped. These are the precise
failure modes the substrate exists to make unmissable. §9 updated.
======

---

## 10. Decisions log

| # | Decision | State |
|---|---|---|
| D1 | Two-layer framing: extraction → durable structural model | Agreed (user) |
| D2 | Three-concern decomposition A/B/C, non-linear | Proposed |
| D3 | Identity per-book basis; designation off the identity path (R1) | Superseded by D11/D12/D33 — Decided (user) |
| D4 | Content anchor checkpoints, never defines, identity (R2) | Proposed |
| D5 | Stage A typed + correctable by B (R3) | Proposed |
| D6 | Contiguous embedding build-now; overlapping hierarchy unsolved (R4) | Proposed (O4) |
| D7 | Paragraph-level IT↔EN aligner in scope (R5) | Proposed |
| D8 | Structure recognition split out of LanguagePlugin | Proposed (O2) |
| D9 | HITL structural tagging as first-pass authoring | User open, not committed (O3) |
| D10 | Three-layer substrate: immutable addressed L1 atoms → versioned L2 block projections → L3 annotations/spans/fields/relations (replaces flat "typed blocks + spans") | Proposed (RT#4/7/13) |
| D11 | Durable opaque `node_id` is internal identity; F3 handles + provenance/revision keys are renderings of `(node_id, handle policy)` with an alias table | Decided (user) — entailed by D33/O1 |
| D12 | "Basis" demotes to a per-node-class handle policy with inheritance; `content-key` dropped (no forcing witness) | Decided (user) — entailed by D33/O1 |
| D13 | Orthogonal `provenance_class` axis (authorial/editorial/translator/furniture/…), separate from role and authorship; capture-with-role for excluded matter | Proposed (RT#3/8) |
| D14 | Lifecycle/governance spine: structure map declares source hash; stale = fail-loud; C-corrections are reviewer-approved patches, never auto-rewrite of L1; reference-integrity + round-trip tests | Proposed (RT#5/11/17) |
| D15 | Overlapping hierarchy stays unsolved (no tree overlap) but a `participates-in` relation hook (`contiguous:false`) is reserved now | Proposed — narrows O4 (RT#12) |
| D16 | Block model lands behind reconcile with a `blocks → reconciled_chapters.json` compatibility adapter; consumers migrate one BR at a time | Proposed — resolves O5 (RT#16) |
| D17 | O2 reframed: declarative structure profile first, narrow code escape hatch only (Hamlet); PLL = profile + relocated ordinal reader | Proposed — revises O2 (RT#15) |
| D18 | Second-structure synthetic fixture (depth-0 + designation-string node) is a build-now gate, not a §9 add-on | Proposed (RT#14) |
| D19 | `SpanRef = {atom_id,start,end}` is a first-class L3 endpoint; relation endpoints are a typed union `atom_range\|projection_node\|span_ref` | Proposed (Codex #2/#7/#12/#13) |
| D20 | L1 identity is `atom_id`; structural identity is `node_id` (L2/L3) — kept distinct; overlays pin by evidence type | Decided (user) — entailed by D33/O1 (corrects D10/D11 wording, Codex #4) |
| D21 | Structure-map header is a lineage manifest (raw+atom-stream+canonical-projection hashes, profile + recognizer versions), not one `source_hash`; references one `canonical_stream_id` | Proposed (Codex #1/#11) |
| D22 | No-loss round-trip is two-tier: raw (byte-exact from `raw_span`+`raw_source_hash`) + normalized (declared reversible transform map); plus negative tests for alias collision / unresolved endpoint / stale lineage | Proposed (Codex #3/#17) |
| D23 | `role` = `front\|body\|back` only; pipeline participation is derived behavioral flags (`translatable`/`alignable`/`counts_for_retention`/`rendered`); validators switch on flags, not on `provenance_class` | Proposed — corrects RT#3/#8 `role=excluded` (Codex #8) |
| D24 | Aliases are records `{handle_type,value,scope,locale_or_witness,target_node_id,valid_from,valid_to,status}`; integrity = every active alias resolves to one node in its scope | Decided (user) — entailed by D33/O1 (Codex #10) |
| D25 | L1 is never mutated in place, but may be **superseded by a new stream version** (re-capture) when a capture atom is missing/malformed; old ids stay addressable, refs migrate/tombstone | Proposed — extends D14 (Codex #5) |
| D26 | The legacy adapter is a **read-only** projection; `triage` (in-place rewriter) migrates **first** off it, its edits becoming governed L2/L3 patches | Proposed — sharpens D16 (Codex #16) |
| D27 | Declarative profile holds data primitives only; stateful parsing crosses a hard line into the code escape hatch — no control flow in JSON, no structure DSL | Proposed — bounds D17 (Codex #15) |
| **D28** | **Engine purpose: this becomes the production pipeline for a re-translated PLL (v2).** The first translation has known fidelity issues; PLL is a real build target, not a study object — so B/C governance is not premature | **Decided (user)** |
| **D29** | **Structure assignment (B) runs BEFORE cleanup/triage.** Layout/content-block structure is *geometric* → base-truth before linguistic truth; available pre-translation. `node_id` is therefore minted early (at B), before any text mutation | **Decided (user) — resolves the pipeline-order tension** |
| **D30** | Space/fragment reconstruction is achieved by capturing **geometry at L1** (word bboxes; PyMuPDF/Fitz, already a dep) + **Zipf-cost DP word-segmentation** over the existing frequency dictionary, gated by the period-dictionary oracle — NOT by inverting `collapse_spaces`/`rejoin_lines`. Raw tier stays the byte-exact floor | **Decided (user) — withdraws the round-trip-impossibility concern** |
| **D31** | Build-scope rule: build **enough of the spec to avoid one-way (PLL-shaped) lock-in** — up to all specimen structures if needed. Overrides the narrow "build only what PLL exercises"; the deferral line is the genuinely-unsolved (overlapping), not "untouched by PLL" | **Decided (user) — supersedes my RT#14/Codex-#14 scope framing** |
| **D32** | Overlapping/interleaved hierarchy stays parked for future support (reserved hook only, D15/D19). Trigger cases: discontiguous interleaving (Hamlet inner play) and geometrically-parallel marginalia; extensive footnotes are mostly the `note-of` relation, not overlap | **Decided (user) — confirms O4 park** |
| **D33** | **O1 resolved — Option A "store-and-rebind."** `node_id` is an opaque label stored in B's map (not derived); stable (stored) + reproducible-as-committed-data + R2-clean. Humans mint the container tree, extractor mints leaves; re-extraction re-binds via stored geometry (D30) + fuzzy content fingerprint + struct-path, fail-loud into D14. Rejected Option B (hash-derived → churn). **One-way gate: the map joins the regen-guard family (irreproducible, never regenerated); revisitable after the initial build-out.** Entails the identity model D11/D12/D20/D24 | **Decided (user)** |

The O-ruling states after user round 3: **O3 premise DECIDED** — B/HITL will be built for PLL (D28);
the open remainder is only the *scale ceiling + inference fallback* for large non-PLL validators (Pepys
~4,000), deferrable since PLL is the target. **O5 / pipeline order DECIDED** structure-first (D29). **O4**
parked by user (D32). **O2** reframed (D17/D27). **O1 DECIDED** (D33, Option A "store-and-rebind") —
`node_id` is stored in B's map and re-bound on re-extraction via geometry + fuzzy content checkpoints;
the map joins the regen-guard family (one-way gate, revisitable post-build-out). The identity cluster it
entails (D11/D12/D20/D24) is Decided with it. **No open ruling now blocks task decomposition** — the
remaining gating work is editorial: write §3.0/§3.6 (referenced but unwritten), reconcile §6↔D31 and
§7↔D29, fold the geometry layer through §3, and a sign-off pass on the still-Proposed D-rows (D2,
D4–D10, D13–D19, D21–D23, D25–D27).

---

## 11. Worked example — PLL slice (added per Red-team #1)

The schema the rest of the plan describes, on a few concrete PLL units: an ordinary chapter
(`Capitolo Primo`), the `prefazione`, an embedded letter, one page-provenance span, and the derived
handle set. **Schematic** — field names are proposals, not frozen; ids are neutral and
content-independent (`a*_` = atom, `n_` = node). It now encodes both review rounds: the three-layer
substrate and `node_id`/handle-policy split (round 1), and the canonical-stream / lineage-manifest /
`atom_id`≠`node_id` / typed-span-endpoint / no-double-ownership corrections (round 2, Codex #1/#3/#4/
#6/#10/#11/#12/#13). The embedded-letter *placement* is illustrative — its real container is
**«unverified»** (would need a read of `output/italian_clean.md`); only the existence of an embedded
letter is from `findings/pll.md`.

### 11.1 Artifact A — L1 atom streams (immutable, addressed)

Per-witness streams **plus** one canonical reconciled stream (Codex #1). The structure map (§11.2)
references **only** the canonical stream; per-witness atoms relate to it through C alignment, never
directly.

```jsonc
// data/atoms/copy1.json  — one stream per witness; copy2/copy3 parallel
[
  { "atom_id": "a1_0007", "witness": "copy1", "text": "Capitolo Primo",
    "raw_span": [10432, 10446], "raw_source_hash": "sha256:…copy1",   // Codex #3: raw tier
    "page_range": [12, 12], "norm_layer": "rejoin+collapse",
    "geom": { "page": 12, "bbox": [72.0, 118.4, 523.1, 134.8] },      // D30/D33: Fitz word-box union
    "provenance_class": "authorial" }
  // a1_0008 (body), a1_0042 (letter body), … parallel
]

// data/atoms/canonical.json  — the reconciled projection the structure map keys on
[
  { "atom_id": "ac_0007", "text": "Capitolo Primo", "page_range": [12, 12],
    "norm_layer": "rejoin+collapse", "provenance_class": "authorial",
    "geom": { "page": 12, "bbox": [72.0, 118.4, 523.1, 134.8] },      // primary-witness box, for re-bind
    "derived_from": [ { "witness": "copy1", "atom_id": "a1_0007" },
                      { "witness": "copy2", "atom_id": "a2_0007" } ] },
  { "atom_id": "ac_0008", "text": "Carlo di Rudio nacque a Belluno…", "page_range": [12, 13],
    "provenance_class": "authorial", "derived_from": [ /* … */ ] },
  { "atom_id": "ac_0042", "text": "Fratelli, l'ora è giunta…", "page_range": [19, 20],
    "provenance_class": "authorial", "derived_from": [ /* … */ ] }
]
```

`atom_id` is **L1 identity** (text evidence + coordinates), distinct from the structural `node_id` of
§11.2 (Codex #4). `raw_span` + `raw_source_hash` make the **raw** round-trip tier byte-exact
(Codex #3/#17); `norm_layer` is human-readable provenance only, never the loss guarantee. `geom`
(D30/D33) is the word-box geometry every atom carries — the **primary re-binding signal** (§3.4) and the
base layer for D30 space/fragment reconstruction; it is a physical fact of the witness scan, so the
canonical atom carries its primary witness's box. Page
furniture and source wrappers are captured atoms too, with `provenance_class: "page-furniture"` /
`"source-wrapper"` and a `processing_scope` that excludes them from translate/retention (Codex #8) —
captured-but-excluded, never dropped.

### 11.2 Artifact B — structure map (B's output, the durable catalogue)

```jsonc
// books/pll/work/structure_map.json
{
  "lineage": {                                  // Codex #11: a manifest, not one hash
    "source_artifacts": [ { "witness": "copy1", "hash": "sha256:…" },
                          { "witness": "copy2", "hash": "sha256:…" } ],
    "atom_streams":     [ { "id": "copy1", "hash": "sha256:…" },
                          { "id": "canonical", "hash": "sha256:…" } ],
    "canonical_stream_id": "canonical",         // Codex #1: the one stream nodes key on
    "projection_id": "proj-…",
    "profile_version": "pll-structure-1",
    "recognizer_version": "italian-ordinal-1"
  },
  "handle_policies": {                          // Codex #9: a policy, NOT identity
    "chapter": "position-path", "front-matter": "designation-string",
    "embedded-letter": "position-path" },
  "nodes": [
    { "node_id": "n_pref", "class": "front-matter", "role": "front",
      "designation": null, "title": "Prefazione", "handle": "prefazione",
      "aliases": [ { "handle_type": "html_slug", "value": "prefazione",   // Codex #10: records
                     "scope": "edition", "status": "active", "target_node_id": "n_pref" } ],
      "children": ["n_pref_p1", "n_pref_p2"] },

    { "node_id": "n_chap", "class": "chapter", "role": "body", "minted_by": "human",   // D33
      "designation": { "kind": "ordinal-word", "raw": "Capitolo Primo", "value": 1 },
      "title": null, "handle": "p1_ch01",       // rendered from node_id + policy (Codex #9)
      "aliases": [ { "handle_type": "html_slug", "value": "parte-prima-capitolo-primo",
                     "scope": "edition", "status": "active", "target_node_id": "n_chap" } ],
      "rebind_anchors": { "geom": { "page": 12, "bbox_region": [70, 110, 525, 140] },   // D33: checkpoints,
                          "content_fp": "fnv1a:…", "struct_path": "body/0" },           //   not identity (R2)
      "heading_atoms": ["ac_0007"],             // container owns the heading atom only (Codex #6)
      "children": ["n_chap_p1", "n_letter"] },

    { "node_id": "n_chap_p1", "class": "paragraph", "parent": "n_chap", "minted_by": "machine",  // D33
      "rebind_anchors": { "geom": { "page": 12, "bbox_region": [70, 145, 525, 360] },
                          "content_fp": "fnv1a:…", "struct_path": "body/0/0" },
      "body_atoms": ["ac_0008"] },              // leaf projection owns body atoms (Codex #6)

    { "node_id": "n_letter", "class": "embedded-letter", "role": "embedded",
      "parent": "n_chap",                       // schematic placement — real container «unverified»
      "authorship": "Mazzini",                  // authorship override, not book-level
      "heading_atoms": [], "children": ["n_letter_v1"] },   // NO body_atoms on the container

    { "node_id": "n_letter_v1", "class": "verse", "parent": "n_letter",
      "body_atoms": ["ac_0042"], "decision": "human-approved" }
  ]
}
```

No atom is owned twice (Codex #6): a container owns its child nodes plus any heading/signature atoms; a
leaf projection owns body atoms. `n_letter` is a **container node** (contiguous, so the tree expresses it
natively — no relation). Queries: "all letter text" = subtree of `n_letter`; "all chapter paragraphs" =
`paragraph`-class descendants of `n_chap` (letter included); "source order, letter once" = in-order walk
of canonical atoms (`ac_0042` appears once).

Each node carries `minted_by` (`human` for the container tree, `machine` for leaves — D33) and
`rebind_anchors` (geometry + fuzzy content fingerprint + structural path) that re-attach the stored
`node_id` to fresh atoms on re-extraction. The `node_id` itself is opaque and never recomputed; the
anchors are R2 *checkpoints*, and a failed/ambiguous re-bind fails loud into the D14 governance path.

### 11.3 Artifact C — relations (graph + alignment), typed endpoints

Endpoints are a typed union — `atom_range | projection_node | span_ref` — so a relation can target a
whole node *or* half a sentence (Codex #2/#7/#12/#13).

```jsonc
// books/pll/work/relations.json
{
  "alignment_set": "align-…",                   // Codex #13: versioned edge set
  "relations": [
    // page-provenance: node ⇒ scan pages, from canonical atom page_range (not (ch_id,para_idx))
    { "type": "page-span", "endpoint": { "kind": "projection_node", "node_id": "n_chap_p1" },
      "pages": [12, 13], "method": "atom-page-range" },

    // IT↔EN alignment: per-edge method + confidence; endpoints may be node or span
    { "type": "align",
      "src": { "kind": "projection_node", "node_id": "n_chap_p1" },
      "tgt": { "kind": "projection_node", "node_id": "en:n_chap_p1" },
      "confidence": 0.98, "method": "by-content" }

    // a later partial correction needs NO schema change (Codex #13):
    // ,{ "type": "align",
    //    "src": { "kind": "span_ref", "atom_id": "ac_0008", "start": 220, "end": 540 },
    //    "tgt": { "kind": "projection_node", "node_id": "en:n_chap_p1b" },
    //    "confidence": 0.91, "method": "human" }

    // reserved hook — typed members, discontiguous, no PLL instance (Codex #12 / D15):
    // ,{ "type": "participates-in", "contiguous": false,
    //    "members": [ { "kind": "projection_node", "node_id": "…" } /* , … */ ] }
  ]
}
```

Every endpoint binds to `node_id` / `atom_id`, never to a positional index — the live `typeset.py`
mispoint (EN index reused on the IT column) is structurally impossible here. The alias records (§11.2)
carry any handle that moved, and §9's integrity test fails loud on any unresolved endpoint. This trio is
the contract two implementers would otherwise have diverged on (RT#1).

---

## Appendix — corpus evidence index

Ten close-reads under `structure_corpus/findings/` (`README.md` carries the shared
template). Treat as evidence to re-check, not gospel — the red team found
`findings/hamlet.md` over-claims subtree-scoped speaker identity and mislabels the
interleaved inner play as a clean "subtree." Witnesses and the rulings they drive:
PLL (R1/R5), Kybalion (depth-0), Dante (R5, verse), Pepys (R2), Darwin (R1
cross-edition), Britannica (R1, C edges), Beeton (block vocab), Hamlet (R3/R4),
Tractatus (R1, depth-from-designation), Atlantic (heterogeneous children).
