# Engine Structure Plan — Document-Structure Axis

Branch: `spike/document-structure`. Originating item: **BR-021** (position-based
chapter identity) in `docs/decisions/branch_register.md`.

## How to read / audit this

This is the **reconciled design spec** for the document-structure axis. The body is the
contract and is kept consistent with the decisions log (§10); read this file for sign-off
and for decomposing the work into tasks.

The two-round adversarial review that produced it — 17 red-team points + 17 follow-ups,
each answered with a code-verified response — is archived verbatim in
**`ENGINE_STRUCTURE_PLAN_DISCUSSION.md`** (the immutable `@@@@@@`/`======` threads). That
archive is provenance; this file is authoritative. Findings about the live tree or the
existing engine port are cited `file · symbol`.

Future audits: drop `@@@@@@` blocks into this file; once a point resolves, fold the
outcome into the body **and** the decisions log, then move the thread to the archive — so
the body never drifts from the decisions again (the failure this split repaired).

## Status — design ratified (2026-06-26); only deliberate deferrals remain

- **Decided by the user (rulings D28–D35):** the engine is the production pipeline for a
  re-translated PLL **v2** (D28); structure assignment runs **before** cleanup/triage
  (D29); space/fragment reconstruction is geometry + Zipf-DP segmentation (D30);
  build-enough-of-spec scope (D31); overlapping hierarchy parked behind a reserved hook
  (D32); the identity keystone **O1 = Option A "store-and-rebind" (D33)**, which entails
  the identity model D11/D12/D20/D24; cross-language alignment is general source↔target,
  not bespoke IT↔EN (D34); the model is designed for a reasonably unbounded unit count
  (D35).
- **Agreed earlier (D1):** the two-layer framing — extraction → durable structural model.
- **Ratified (2026-06-26):** all formerly-*Proposed* design decisions (D2, D4–D10,
  D13–D19, D21–D23, D25–D27) are now **Decided (user)** — the spotlight items (D16/D26
  sequencing, D18 fixture gate, D10/D14/D19 substrate complexity) were considered and
  approved. The body and §10 reflect this.
- **No open architectural items.** The only non-decided items are **O2** (recognition
  packaging) and **O3** (HITL scale ceiling), both **deferred by choice and recorded**
  (§8): O2 settles at §7.1 implementation; O3 is a resource/cost question, not an
  architectural one, given D35.
- PLL is the **build target**, not merely a reference (D28). The ten other corpus
  witnesses are co-equal conformance validators (`structure_corpus/findings/*.md`); the
  artifacts are evidence to re-check, not gospel.

## Scope

- **In scope:** redesign the document-structure axis as *extraction → durable structural
  model → relations*; define the seams; specify what the PLL v2 target needs built.
- **Build target:** PLL v2 (D28). Per **D31**, build the general *mechanism* for each
  capability so no single book's shape is baked in, instantiate concretely what PLL needs,
  and defer only the genuinely-unsolved (overlapping hierarchy). This supersedes any
  "build only what PLL exercises" framing.
- **Out of scope:** the M4c translate/refine port (paused behind this exploration); the
  live edition's deploy state — the deploy-hold governs the live PLL push, not this
  clean-room design (orthogonal; see `feedback_existing_path_failures_as_evidence`).

---

## 0. Why this exists (the problem)

BR-021 flagged chapter identity as "arbitrary / position-based." Reading the corpus plus
the existing port shows the deeper shape: the engine **fuses three separable concerns and
hardcodes one book's skeleton** (F1–F4 below).

This is not a study exercise. Per **D28**, the engine becomes the production pipeline for a
**re-translated PLL (v2)** — the first translation has known fidelity issues a second pass
can improve. The redesign, including the B/C governance and the human-in-the-loop
structure map, is therefore justified by a real build target, not speculative generality.
The corpus exists to stop that target from re-importing the single-book bias: the model
answers to the **union** of what eleven real document structures exhibit.

---

## 1. Current state in the engine (what we are changing)

Four findings, each a thing this plan redesigns; all present in the port today.

- **F1 — Structure recognition lives entirely in `LanguagePlugin`.** `lang/base.py`
  declares `is_chapter_heading`, `parse_chapter_number`, `structural_part`,
  `strip_boilerplate`, `split_raw_chapters` as abstract; `lang/italian.py` (`ORDINALS`,
  `_HEADING_RE`, `_PARTS`, `_PREFAZIONE_RE`, `_PARTE_SECONDA_RE`) carries all of it. There
  is no core structure model and no structure seam — structure is a per-*language* concern
  today. The corpus shows block vocabulary (Hamlet dialogue, Beeton recipe-record) and
  some designation kinds (Tractatus dotted-decimal) are per-*book*, not per-language, so
  this fusion is the wrong cut.

- **F2 — `BookManifest.structure` is a fixed-shape validator, not a model.**
  `config/models.py · Structure` carries `h2_min`, `h3_count`, `parts`, `content_units`,
  `running_heads` — PLL's skeleton ("≥3 H2, exactly 57 H3 = 24+33"). A book with zero
  grouping levels (Kybalion), four (Pepys), or recursion (Tractatus) cannot be described.

- **F3 — `ChapterIdentity` derives every handle from the designation.**
  `util/chapterids.py · ChapterIdentity` holds `short` (`p1_ch01`), `parse_md`, `html_slug`,
  plus `part`, `number`, `title`, all descending from the Italian ordinal parse. Identity
  rides on the designation reader — the BR-021 fragility; the long id drifts with the
  source's spelling (`Capitolo Decimo Ottavo` P1 vs `Capitolo Decimottavo` P2).

- **F4 — The chapter representation is untyped; blocks do not exist.**
  `steps/reconcile.py` emits `reconciled_chapters.json` as `{id, title, part, text}`, where
  `text` is paragraphs joined by `\n\n`. No `Block`/`Paragraph`/`Span` type, no block
  identity, no place for verse, footnotes, dialogue, or inline spans.

- **Multi-witness fact behind F4.** `reconcile.run` segments Copy 1/2/3 independently
  (`reconcile.py:553–562`), reconciles at word level, and persists only one merged stream
  (`reconciled_chapters.json :630–673`) plus word-level disagreements (`flagged_segments.json
  :716`, keyed by `(ch_id, para_idx)`); page provenance attaches to the merged clean-char
  offsets (`_strip_page_markers :485`). The per-witness *structural* streams are discarded,
  so a Copy-1-only segmentation failure has nowhere to live and disagreement flags hang off
  a fragile position pair. The new model fixes this (§2-A, §3.2).

---

## 2. Architecture — three concerns, non-linear

The user's two layers map onto three concerns: **layer 1 = A**; **layer 2 = B + C** (the
durable catalogue is B; its relations are C).

```
        ┌─────────────────────────────────────────────────────────────┐
  raw   │  A. BLOCK EXTRACTION        flat, source-ordered typed atoms  │
  text ─┼─►  faithful capture + L1 geometry + space reconstruction      │
        │                                          │                    │
        │  B. STRUCTURAL ASSIGNMENT    ◄────────────┘   the durable      │
        │     group blocks into a ragged container tree;   "structure   │
        │     assign designation / title / role / matter;   map" sidecar│
        │     mint + persist node_ids   (runs BEFORE cleanup/triage)     │
        │                                          │                    │
        │  C. RELATIONS                ◄────────────┘                    │
        │     cross-ref edges + cross-edition / cross-witness alignment  │
        │     (proposes governed corrections back to A/B — the loop)     │
        └─────────────────────────────────────────────────────────────┘
```

- **A — Block extraction.** Source → a flat, source-ordered list of typed atoms. As
  faithful as the source allows; restoration of degraded typography (the `typography.json`
  class of thing) is a *separate attributed overlay*, never folded into capture. A is
  book-specific where it must be (block typing) and **correctable** by B (§4 R3) — not a
  universal-dumb pass. **A emits both** per-witness atom streams (each addressable, so
  copy-specific failures and OCR disagreements keep an attachment point) **and one
  canonical reconciled projection** that downstream consumes. **A captures word-box
  geometry at L1** (D30; PyMuPDF/Fitz — the PLL PDF is an image scan, so geometry comes
  from the OCR textpage/bbox layer, not native `get_text`) and reconstructs split/merged
  spaces and fragments via **Zipf-cost DP word-segmentation** over the frequency dictionary
  (`data/dictionaries/it_combined.txt`), oracle-gated by the ≥2-of-3 period dictionaries —
  *not* by inverting `collapse_spaces`/`rejoin_lines`. Coordinate space and capture
  completeness: §3.0.

- **B — Structural assignment.** Group the flat blocks into a ragged container tree, attach
  the read-fields (designation, title, role, matter), and **mint + persist `node_id`s**
  (§3.4). This is the durable catalogue — a human-in-the-loop structure-map sidecar (the
  `typography.json` precedent, §3.5). **B runs before cleanup/triage (D29):** layout and
  content-block structure are *geometric* base-truth, available pre-translation, so `node_id`
  is minted early, before any text mutation.

- **C — Relations.** Cross-reference edges (a graph orthogonal to containment) and
  cross-edition / cross-witness alignment. **Non-linear:** C can prove A or B wrong (a
  cross-edition alignment can reveal a missegmentation) and feed a *governed* correction
  back — a reviewer-approved patch to the map, never a silent rewrite of L1 (§3.6).

---

## 3. The model

### 3.0 Coordinate space & capture completeness

- **Every L1 atom carries a durable address:** `{witness_id, raw_codepoint_span,
  page/scan_range, geom (optional word-box bbox + match-provenance), normalization_layer_id}`,
  plus a `raw_source_hash` pinning the raw witness text the span addresses. Atoms remain
  addressable across all downstream stages because nothing recomputes these from mutated text.
- The existing port's only coordinate seed is `_strip_page_markers`'s `{clean_offset → page}`
  map (`reconcile.py:485`) — built *after* normalization, page-granular, witness-untagged.
  It becomes one projection over this address space, not the only one. `collapse_spaces`
  (`util/text.py:39`), `rejoin_lines` (`util/text.py:55`, which heals hyphen line-breaks and
  destroys line structure), and `strip_boilerplate` (`lang/italian.py`) are string→string
  with no offset map today; the address space is what replaces that loss.
- **"Everything is brought in" = captured-with-role.** Gutenberg wrappers, running heads
  (`Structure.running_heads`, BR-004), and scan furniture are captured atoms carrying an L1
  **capture-provenance** class ∈ {`source-wrapper`, `page-furniture`, …} (the L1 field of the
  L1/L2 split in §3.3) and a `processing_scope` that excludes them downstream (§3.3) —
  **captured-but-excluded is distinct from never-captured**, and that distinction is what
  makes the no-loss round-trip checkable (§9).
- `normalization_layer_id` (`norm_layer`) is a human-readable label, **never** the loss
  guarantee. The binding guarantee is `raw_source_hash` + the byte-exact raw round-trip tier
  (§9) and a reversible transform map for normalized text.
- **Geometry (`geom`, D30)** is a physical fact of the witness scan: D30's **intended primary
  re-binding signal** (§3.4) — *conditionally confirmed* by S2.0 (outcome below, not settled) — and
  the base layer for space/fragment reconstruction. It is
  available when a scan exists (PLL has the LOC PDF); the portability floor for text-only
  sources is content + structural-path. **The slot is `Optional`, and absence is a
  first-class state — never invented coordinates:** one of PLL's three witnesses (copy3,
  Gemini-vision text) has no word-box layer at all, before any failed OCR-box match. And
  because the boxes come from a *different* OCR pass (PyMuPDF) than the witness text
  (IA-Tesseract / Gemini), `geom` is not a fact *about the witness text* until a matcher
  proves it: each value therefore carries match-provenance — `{geometry_engine,
  matched_witness_id, match_method, match_confidence}` and a `{present | absent}` state — and
  an **unmatched box is unusable as a primary re-bind anchor**. The probe that measures this
  text↔box alignment quality, and the demotion path when it misses threshold, are the
  build-now gate of the geometry pole (task tracker S2.0/S2.1).
  **S2.0 outcome (2026-06-29, `docs/probes/s2_0_geometry_alignment.md` + `…_adversarial_audit.md`):**
  geometry is **viable** (token anchorability ~0.92 content-token; column reading-order recoverable
  from box coords, mean 0.92 / 87% pass on two-column body pages) but rated **conditional-primary,
  not settled** — the order-extraction half is **re-gated at S2.2** on the as-built detector (mean +
  per-page pass-rate over a breadth sample), not asserted now. Reading order is sourced two ways:
  from a column-correct **text witness** when one exists (geometry cross-checks), from the
  **geometric detector + human-in-loop** when none does (the engine must not presume a witness).
  So "primary re-binding signal" above is the design intent this gate conditionally confirmed, not a
  proven property.

### 3.1 Container tree

- A **recursive container node** with ragged, *discovered* depth — 0 levels (Kybalion) to 4
  (Pepys), recursive (Tractatus). Depth is **not** a schema constant (replaces F2's fixed
  shape).
- **Matter is a role attribute** (`front | body | back`), not a special case; the three are
  siblings in one ordered child list (replaces PLL's special-cased prefazione).
- A container's **children may be heterogeneous** (Atlantic: essay / poem / serialized
  fiction / review as siblings).
- **Contiguous embedding** (a sub-document inside the body) is a **container node** with
  `role=embedded` and an authorship override — the Mazzini letter, build-now. It is distinct
  from **overlapping hierarchy** (§4 R4), which the tree cannot natively express and which is
  parked (D32).

### 3.2 Three-layer body: atoms / projections / annotations (replaces F4)

- **L1 atoms** — immutable, addressed capture units (§3.0); identity is `atom_id` (text
  evidence + coordinates), distinct from the structural `node_id` of §3.4.
- **L2 projections** — group/split/type atoms into the **open, per-book** block vocabulary:
  paragraph, verse-line, tercet, aphorism, footnote-body, table, figure-caption,
  structured-record, dialogue-turn, stage-direction, dated-entry, … Identity is `node_id`.
  Versioned and correctable (R3). A **leaf projection owns body atoms; a container owns its
  children plus any heading/signature atoms** — no atom is owned twice.
- **L3 annotations** — spans, fields, attributes (speaker, date, author, citation, recipe
  cost/time), and relations. Inline stage directions, emphasis runs, and footnote
  call-sites are L3 **spans**, not blocks; a footnote = an L2 note-body projection + an L3
  call-site span linked by a `note-of` relation.
- **`SpanRef` is the first-class L3 endpoint primitive:** `{atom_id, start, end}` (with
  optional `node_id`). L3 relation endpoints are a typed union — `atom_range |
  projection_node | span_ref` — so OCR flags, partial alignment, and the reserved overlap
  hook can address sub-block ranges without regressing to paragraph granularity.
- **PLL build-now:** L2 `paragraph` + `verse`, the embedded-letter container, and
  `SpanRef`-typed endpoints. The richer block types are mechanism-admitted now,
  instantiated as books need them (§6).

### 3.3 Read-fields: designation, title, matter, authorship

- **Designation ≠ descriptive title**; both are optional, source-read display fields.
  Designation kinds observed: ordinal-word, Roman, global-Arabic, proper-name, date,
  headword-string, dotted-decimal.
- **Three orthogonal status axes**, never one bag:
  - **role** — `front | body | back`, *structural matter only* (never `excluded`).
  - **authorship** — who, at scope `work | witness | translation | span`; overridable, not a
    book-level constant (Pepys editor splices mid-sentence; EB per-sub-section signatures).
  - **content provenance** — editorial status: `authorial | editorial | translator-note |
    transcriber | generated-TOC | scan-OCR-furniture | source-wrapper | renderer-added`.
- **L1 and L2 provenance are distinct semantic fields.** L1 records **capture / source
  provenance** for atoms (§3.0 — how/whence the bytes were captured); L2 records **content /
  editorial status** for projections (the axis above). Implementations **must use distinct
  identifiers or otherwise enforce the distinction by schema** — they are not one shared
  `provenance_class` reused at both layers — so a consumer cannot grab the convenient field
  and bypass the rollup. *(Provisional names: L1 `capture_provenance_class`, L2
  `content_provenance_class`; final names are an implementation choice, the binding
  requirement is the distinctness.)*
- **Pipeline participation is *derived*, not a `role` value.** Policy computes behavioral
  flags `translatable` / `alignable` / `counts_for_retention` / `rendered`, and validators
  switch on *those* — so the content-provenance vocabulary can grow without hardcoding
  `translator-note` into every step. **Derived flags read the L2 content status *plus* an
  explicit L1 rollup rule:** a node mixing authorial-body atoms with furniture/wrapper atoms
  must either split the projection (preferred) or carry an explicit, tested mixed-rollup —
  silent rollup of a mixed node is the failure mode. `validate.check_word_count_preservation`
  keys on `counts_for_retention`, not on a raw provenance literal.

### 3.4 Identity — durable `node_id` + handle policy (keystone — DECIDED, Option A / D33)

- **Internal identity is an opaque, durable `node_id`** — assigned once (at B-time),
  persisted in the structure map, never re-derived from position, designation, or content.
  It is the root every overlay, relation, and revision key pins to. (Atom-level evidence
  pins to a distinct L1 `atom_id`.) **Minting split:** humans author/approve the *container*
  tree (~61 nodes for PLL, the §3.5 HITL-tractable scale); the extractor *machine-mints*
  leaf `node_id`s (counter/ULID) and persists them in the same map — humans spot-check,
  never hand-key thousands. No `node_id` carries a positional component; the readable
  `p1_ch01.p3`-style string is a handle (below), not the id.
- **Designation / position / headword are handle policies and citation semantics, not
  identity.** Each node-class carries a `handle_policy` (`position-path` |
  `designation-string` | `title` | …), inherited down the tree unless overridden, declared
  in the structure map — a policy per node class, not one book-wide enum. The visible handle
  (F3's `short` / `parse_md` / `html_slug`, the provenance key, the revision key) is a
  **rendering** of `(node_id, handle_policy)` — one source of truth, not parallel schemes.
- A handle that changes (a missed node is inserted, `p2_ch18` shifts) leaves `node_id`
  fixed; the old handle survives as an **alias record** (§3.6) so existing citations and
  caches resolve.
- Tractatus and EB make designation-string **handles** first-class (as cross-reference
  anchors) but do **not** force designation-string *internal* identity. `content-key` is
  dropped as a basis (no forcing witness); if a book ever needs content-derived handles,
  that is a future handle policy with collision/migration behavior defined then.
- Identity is **depth-varying in the stability of its handle**, not in whether identity
  exists: container handles are reliable; block-granularity correspondence is
  alignment-mediated (§4 R5).
- **Re-binding (the residual hard part).** Each node stores `rebind_anchors` —
  *checkpoints, not identity* (R2): a **geometry** anchor (page + bbox region, from D30's
  word-boxes — the signal most invariant to OCR re-tokenization, hence primary), a
  **fuzzy/fail-loud content fingerprint** (never the exact-substring the live tree
  tombstoned), and a **structural-path** tie-break. On re-extraction a node re-attaches to
  the fresh atoms occupying its stored region, verified by fingerprint; unique + confident →
  bind; ambiguous or below threshold → **fail loud → human re-approval** (§3.6). Geometry is
  a strength where a scan exists; the text-only floor is content + structural-path.

> **D33 — Option A "store-and-rebind."** `node_id` is an opaque label *stored* in B's map
> (not computed from raw) — stable (stored), reproducible *as committed/versioned data*, and
> derived from neither position nor content (R2-clean). The rejected alternative was a
> hash/derivation (Option B): from-scratch recomputability at the cost of the mutable-basis
> churn R1/R2 killed. **Acknowledged one-way gate:** the structure map is therefore a
> hand-tuned, *irreproducible* artifact and **joins the regeneration-guard family**
> (translations, `typography.json`) — never blown away and regenerated; deleting and
> re-authoring it mints *different* ids by design. Accepted as a one-way gate, revisitable
> only after the initial build-out shows how it behaves.

### 3.5 The structure map (B's output) — HITL authoring; O3 scale ceiling deferred (D35)

The durable catalogue is a hand-authorable sidecar — the **`typography.json` precedent**: a
scan-verified, human-curated artifact that is the sole source of truth, applied at defined
sites, **fail-loud on anything that matches nowhere**. The premise — human-in-the-loop
tagging as the first-pass authoring path — is **decided for PLL** (D28/D29): it dissolves
the "extraction cannot build the tree neutrally" problem by moving tree-building out of A
and into B. The map header is a lineage manifest and its staleness rules are governance
(§3.6).

**Scale ceiling (O3, deferred — D35):** HITL container-authoring is tractable for *targets*
(PLL ≈ 61 containers), and leaf nodes are machine-minted (§3.4), so the human surface does
not grow with body size. The model is therefore **designed for a reasonably unbounded unit
count** (target order ~100k units, D35): node identity is machine-minted, node storage is a
flat addressable list, and no structure operation is super-linear in unit count. Under that
constraint the "ceiling above which inference must lead authoring" reduces to a
resource/cost question, not an architectural limit — so O3 is **deferred by choice**,
revisited only if a real corpus stresses the HITL container surface.

### 3.6 Lifecycle & governance

- **Lineage manifest** in the map header (not one hash): raw witness ids+hashes, atom-stream
  ids+hashes, canonical projection id+hash, structure-profile/schema version, and
  recognizer/extractor version. This is the minimum needed to answer *why* a sidecar is
  stale → *which* migration to run: raw OCR changed (re-capture) vs normalization changed
  (re-derive offsets) vs only a projection changed (re-attach L2/L3) are different repairs.
- **Stale = fail-loud.** Load fails when a hashed input has changed since authoring;
  refresh-or-migrate is required, never silent best-effort. A misrouted structure map is a
  *silent* failure (mis-translation, mis-alignment), worse than a dropped italic — so it
  gets a stronger fail-loud than `typography.json`'s unmatched-fragment log.
- **Decision provenance per entry:** `human-approved | plugin-suggested | inherited`.
  Re-suggestion never overwrites a human ruling.
- **C-corrections are reviewer-approved patches** to the map (L2/L3), never auto-rewrites of
  L1. L1 is immutable *in place* but may be **superseded by a new stream version**
  (re-capture, D25) when a capture atom is genuinely missing/malformed; old `atom_id`s stay
  addressable, and L2/L3 refs migrate forward or are tombstoned (kept-marked-invalid — the
  `corrections.json` post-mortem in `feedback_existing_path_failures_as_evidence` is why we
  keep rather than delete).
- **Alias records:** `{handle_type, value, scope, locale_or_witness, target_node_id,
  valid_from, valid_to, status}` — so `p2_ch18`, an HTML slug, a parse-md key, and a retired
  revision-cache key coexist without sharing a namespace. Integrity = every `status:active`
  alias resolves to exactly one node within its declared scope.
- All of the above is enforced by §9 (reference integrity, two-tier round-trip, fail-loud
  negatives).

---

## 4. The rulings (R1–R5)

Each cites the witness that forced it and what it changes in code. **R1 is decided (D33);
R2–R5 are firm proposals pending sign-off.**

- **R1 — Internal identity is a durable `node_id`; designation/position/headword are handle
  policies.** *Decided (D33).* *Forced by:* Tractatus (dotted-decimal is the cross-ref
  **handle**; `findings/tractatus.md` §6) and EB (headword is the citation **handle**;
  dangling cross-refs key on the designation string; `findings/britannica_1911.md`). Both
  falsified "designation = display, position = identity" *and* its successor "identity is a
  per-book basis"; after D11/D12, identity is *neither* position nor designation nor content
  but an opaque `node_id`, and those three are handle policies rendered from it. *Changes:*
  `ChapterIdentity` (F3) → opaque `node_id` + rendered handles + alias records (§3.4); the
  designation reader leaves the identity path, surviving as a handle-policy renderer and
  cross-ref anchor.

- **R2 — Content fragments *checkpoint* identity; they do not *define* it.** *Forced by:*
  Pepys (419/2901 day-entries non-unique at a 40-char anchor; `findings/pepys.md`) and PLL's
  own history — `cleanup.py` built a 40-char content anchor (exact-substring `if find not in
  text: continue`), watched re-extraction silently invalidate it, and migrated to a
  full-text cache. *Changes:* a *fuzzy, fail-loud* content anchor is a re-attachment aid only
  (§3.4 rebind), never the exact-substring primitive the live tree tombstoned.

- **R3 — Stage A is book-specific and correctable, not universal-dumb.** *Forced by:* Hamlet
  (`findings/hamlet.md`) — atomization needs the turn parse (`[_Reads._]` with no surrounding
  blanks must split; `[_Writing._]` with blanks must not), and typing is ambiguous (`He.` /
  `Dead.` are byte-identical to speaker labels `Both.` / `Danes.`, separable only by
  turn-state). A mis-*typed* atom cannot be fixed by a B that only groups. *Changes:* A emits
  a *typed* stream via the book's block-classifier; **B can re-atomize and re-type, not
  merely re-group.**

- **R4 — Contiguous embedding (build-now) is separated from overlapping hierarchy (parked,
  D32).** *Forced by:* Hamlet's play-within-a-play is *interleaved* (the frame audience
  comments turn-by-turn), so the inner play's blocks are a discontiguous subsequence — the
  overlapping-hierarchy / TEI-milestone problem a tree of nested source-order intervals
  cannot natively express. *Decision:* PLL's contiguous embedded letter is build-now; the
  **containment tree stays strictly non-overlapping**, and overlapping/interleaved cases use
  a **reserved L3 `participates-in` relation** (`contiguous: false`, typed `members` over the
  endpoint union) — no PLL instance, Hamlet-conformance-checked (D15). Parked by D32.

- **R5 — Block-level, span-capable cross-language alignment is in scope for the target.**
  *(Renamed from "paragraph-level.")* The relation is **general source↔target
  (LANG_A↔LANG_B), not bespoke IT↔EN** (D34, `feedback_engine_agnostic`): core carries no
  language pair, and IT↔EN is merely PLL's instance. *Forced by:* the live edition already
  ships a facing-page provenance feature (1,118 `data-prov` cross-column links) that depends
  on source↔target correspondence and is *already broken* — `typeset.py` reuses the English
  paragraph *index* on the Italian column (`it_paras[para_num-1]`); 23/58 chapters have
  divergent paragraph counts → 14 provable mispoints. The position-index-as-key failure, shipped.
  *Changes:* alignment is an **L3 relation** — many-to-many over stable `node_id`s/`SpanRef`s,
  each edge carrying `method` (`by-index | by-content | human`) + `confidence`, with an
  `alignment_set` version. A paragraph index is one *method* that produces edges, never the
  durable key; endpoints admit whole nodes *or* spans, so a later human edit can align half a
  paragraph with no schema change. (The live `typeset.py` fix is a separate live-PLL matter,
  cited here only as evidence.)

---

## 5. Settled foundations (do not relitigate)

Five independent adversarial passes (archived) each conceded these; they are settled unless
a new audit block reopens them:

- The **A/B/C decomposition** itself.
- **A's flat, source-ordered, no-meaning-imputed-to-order capture** (vindicated by EB, where
  reading order is meaningless). The breaks were on the "decision-free" overclaim (→ R3) and
  anchor-as-identity (→ R2), not the flat-list idea.
- The **ragged recursive container tree** (§3.1).
- **HITL for targets** — tractable at PLL scale; the scale ceiling (O3) is the open part, not
  the premise.
- **Depth-varying handle stability** (§3.4).
- **Container-level cross-language alignment** — `typeset.py · _align_chapters` already pairs
  IT/EN chapters positionally; the "part header invisible in EN" attack confirmed the model.

---

## 6. Scope — build for v2 (per D31)

**D31 discipline:** build the general *mechanism* for every capability so no single book's
shape is baked in; instantiate concretely what PLL v2 needs; the **only** deferral is the
genuinely-unsolved. Each named witness is the conformance check that the mechanism is
coherent. (This supersedes the earlier "build only what PLL exercises" framing.)

| Capability | Witness(es) | For v2 | Note |
|---|---|---|---|
| Ragged container tree, discovered depth 0–4 / recursive | PLL, Kybalion, Pepys, Tractatus | Mechanism + PLL instance | depth discovered, never schema-baked (F2) |
| Open typed-block vocabulary (admits table/figure/recipe-record/dialogue/stage-direction) | PLL, Dante, Beeton, Hamlet | Mechanism now; PLL instantiates `paragraph` + `verse` | typing must be open + correctable (R3) |
| Contiguous embedded sub-document | PLL | Yes | the Mazzini letter (container, `role=embedded`) |
| L1 geometry capture + Zipf-DP space/fragment reconstruction | PLL | **Yes** | D30; primary re-bind signal + raw-tier floor |
| Opaque `node_id` identity + `rebind_anchors` + alias records | PLL | **Yes** | R1/R2/D33 |
| Per-node-class handle policies (admits designation-string, headword, date, dotted-decimal) | PLL, Tractatus, EB, Pepys | Mechanism now; PLL uses `position-path` + `ordinal-word` | designation-string is a cross-ref *handle*, not internal identity |
| Block-level, span-capable cross-language (source↔target) alignment relation | PLL, Dante | **Yes** | R5/D34; general LANG_A↔LANG_B, PLL instance is IT↔EN |
| Depth-deriver seam (depth from designation) | Tractatus | Seam now, unpopulated for PLL | dotted-decimal computes depth 0–6 |
| Graph cross-ref edge type (may dangle / resolve externally) | EB | Mechanism now | concern-C edges, external/unresolved semantics |
| Heterogeneous children | Atlantic | Yes | tree must not assume homogeneity |
| Per-node / per-span authorship attribute | EB, Pepys, Atlantic | Mechanism now; PLL has a few overrides | Mazzini-letter override |
| Three status axes + derived behavioral flags | all | Yes | role / authorship / provenance (L1 capture + L2 content, §3.3) |
| Lineage manifest + stale-fail governance | all | Yes | §3.6 |
| **Overlapping / interleaved hierarchy** | Hamlet | **Deferred (genuinely unsolved)** | reserved `participates-in` hook only (D15/D32) — the one deferral line |
| Second-structure synthetic fixture (depth-0 + designation-string handle) | — | **Build-now GATE** | schema + adapter only; the schema is not "born" until it passes (D18) |

---

## 7. Integration with the existing engine

This redesigns the four findings of §1.

- **7.1 — Split structure recognition out of `LanguagePlugin` (resolves BR-021).**
  Recognition is per-*book*, not per-language (F1). **Profile-first + code-escape (D17/D27):**
  a **declarative structure profile** (heading regexes, running heads, matter labels,
  designation grammar, numbering scope, block-split rules — *data primitives only*, no DSL,
  no control flow in JSON) covers the common case, so new books are *authored*; a **narrow
  code escape hatch** (a thin reader) handles irreducibly procedural recognition (Hamlet's
  turn-state). The structural *model* (tree, three-layer substrate, identity protocol) is
  book-agnostic **core** (`feedback_engine_agnostic`); only recognition is plugged. PLL = the
  profile + the existing Italian ordinal reader relocated. *(The packaging choice — a profile
  read by core vs a thin per-book `StructurePlugin` class — is O2, **deferred by choice** and
  settled at this section's implementation.)*

- **7.2 — Replace `Structure` (F2) with a general model + per-book structure map.** The
  fixed-shape validator becomes (a) a general tree/blocks model in core and (b) the book's
  structure-map sidecar (§3.5). `validate.py`'s shape checks become assertions over the
  structure map, not hardcoded H2/H3 counts.

- **7.3 — Rework `ChapterIdentity` (F3) → opaque `node_id` + per-node-class handle policies.**
  `short` / `parse_md` / `html_slug`, the provenance key, and the revision key become
  deterministic *renderings* of `(node_id, handle_policy)`, not parallel sources; shifted
  handles are recorded as aliases (§3.6). *(Not "one basis per book" — identity is the opaque
  `node_id`, D11/D33.)*

- **7.4 — Rework `reconciled_chapters.json` (F4) → a typed block stream.** B (running
  structure-first, D29) emits typed blocks with `node_id`, not a `\n\n` string. **Sequencing
  is resolved (D16 / O5):** land the block model **behind reconcile** with a **read-only
  adapter** projecting L2 → the legacy `{id, title, part, text}` dict (`text = "\n\n".join(
  paragraph projections)`), so consumers keep working; they then migrate one BR at a time.
  Consumers of the legacy shape: `triage.py:286–327` (rewrites in place), `cleanup.py:882`
  (reads `text`), `validate.py:432–465` (word count); downstream `translate`/`refine`/`typeset`
  read `clean.md` + the translations and are insulated. **`triage` migrates first** — it
  rewrites in place, so a post-adapter triage run could diverge from the block artifact; the
  adapter is never a write-back path (D26).

---

## 8. Decision status & remaining open items

As of 2026-06-26 the design is **fully ratified** — every formerly-*Proposed* decision is
Decided (user) — and the original five rulings (O1–O5) are resolved, parked, or
deferred-by-choice. Nothing architectural is open.

- **O1 — DECIDED (D33, Option A "store-and-rebind").** Identity = opaque, stored `node_id`,
  re-bound on re-extraction via geometry + fuzzy content checkpoints; the map joins the
  regen-guard family (one-way gate, revisitable post-build-out). Entails D11/D12/D20/D24.
- **O2 — DEFERRED (recorded).** Profile-first + code-escape is settled (D17/D27); the only
  residual is where the profile/reader lives, deferred by choice to §7.1 implementation.
- **O3 — DEFERRED (recorded); premise decided.** HITL structural tagging *is* built for PLL
  (D28/D29). Per **D35** the model is designed for a reasonably unbounded unit count, so the
  "ceiling above which inference must lead authoring" is a resource/cost question, not an
  architectural limit; revisited only if a real corpus stresses the HITL container surface.
- **O4 — PARKED (D32).** Overlapping/interleaved hierarchy is future work; reserved
  `participates-in` hook only (D15/D19). Triggers: discontiguous interleaving (Hamlet),
  geometrically-parallel marginalia. No identified target need.
- **O5 — RESOLVED (D16).** Block model lands behind reconcile via the read-only adapter;
  structure-first (D29).

**Ratified at sign-off (2026-06-26), with the spotlight items considered and approved:**
D16+D26 (sequencing & migration as described — *not* the rejected big-bang cutover); D18
(the build-now second-structure fixture gate); D10+D14+D19 (substrate + governance
complexity — accepted with eyes open, justified by D28's real v2 target and the live PLL
flat model having already shipped the bugs it prevents). Two refinements were added at
sign-off: **D34** (alignment is general source↔target, not bespoke IT↔EN) and **D35**
(design for a reasonably unbounded unit count). The next step is task decomposition, not
further sign-off.

---

## 9. Test strategy

**Red-first, invariant-driven — the method over every tier below.** A test that has never been
red is a claim, not a check. (1) **Enumerate** invariants from the done-when *before* writing
tests, in the module docstring (an `Invariants (proven red below)` block). (2) For each, **see it
red on violation** before trusting green: TDD for new code (the test fails with the code absent); a
**permanent** negative / planted-violation control for a guard over existing code (mutate the
input / monkeypatch the mechanism / drop the binding) — never a throwaway probe. (3) Name the input
that turns each assertion red; if it is "edit the test's own literal" or "a stdlib bug," it is a
tautology — rewrite it against the code under test. Enumeration-first catches the
*missing-invariant* class (the symlink-canonicalization vector was implied by "live tree
unreachable" yet had no test); the red-proof catches the *weak-test* class (tautologies, tests that
exercise stdlib not the code). The mechanical form of (2) is **mutation testing** — a surviving
mutant is a line no test discriminates; adopt scoped where cost permits. Worked examples:
the S0.1–S0.3 module docstrings (`test_workspace`, `test_structure_artifacts`,
`test_structure_neutrality`; the S0.3 tiers spine was folded into `test_structure_map`, #56).

**Adversarial-audit gate — the review method, sibling to red-first.** Red-first governs the *tests*;
this governs the *review* a `BUILD`/`GATE` task passes before commit. Run a pre-commit adversarial
pass: the mechanical **mutation hunt** (the narrow form of red-first, above) plus several
**overlapping read-only reviewers** at two complementary apertures — **wide** (seam / consumer /
cross-artifact plan↔code / boundary) and **narrow** (exact branch / exception class / per-line mutant
/ single-fixture coupling). Two rules, because a pass certifies only the bytes it saw: (A) re-audit
any *behavior-changing* remediation it produces — a new branch, error path, or contract is itself
unaudited — and **iterate to a fixpoint**: stop when a pass yields no behavior-changing change (a
clean pass, or remediation that is docs/comments/test-only). (B) re-aim the apertures at the delta — a
narrow delta wants the microscope, a wide delta the telescope; weight by aperture agreement
(convergence → act, lone-lens → verify-first). **Proportionality** bounds it: depth scales with
surface — a substantial behavioral task warrants several lenses, a one-line mechanical or doc-only
change a single proportional check, never a fleet (signal, not ceremony; the cost is real).
Self-applied, like red-first — a DoD discipline, **not** a mechanical hook; forward-only. Worked
example: S3.0.5 (#27) — the first pass caught a wrong-identity digest (wide); the *re-audit of its
own fix* caught a `UnicodeDecodeError` escaping the new `except` (narrow).
`feedback_adversarial_audit_cadence`.

Per the house tiers (`tests/unit` property/separability/isolation/neutrality; `tests/golden`):

- **Golden** — reproduce PLL's current chapter boundaries and identities through the new
  model (no regression on the live target). **Reserved for live-parity assertions only**
  (I3 anti-cheat: expected values come from the live implementation), so it applies *only*
  where a live referent exists — the chapter-identity rework, the legacy adapter, the PLL
  identity golden. The net-new substrate (atoms, geometry, projections, relations) has **no
  live referent**; a hand-authored synthetic artifact is a **fixture** or a
  reference-integrity test, **never** a "golden" — calling it golden would invite invented
  expected outputs wearing a parity badge (`feedback_no_cheating_results`).
- **Property** — structure operations over synthetic trees (ragged depth, heterogeneous
  children, recursion-in-body).
- **Neutrality** — no language/structure literals in core (the model carries no
  Italian/ordinal opinion; recognition lives in the profile/plugin).
- **Second-structure fixture (build-now GATE, D18)** — a **hand-authored structure fixture**
  (schema + adapter only, *not* an OCR/reconcile integration target) built to **differ** from
  PLL: depth-0 body, designation-string handle policy, alias uniqueness within scope, stale
  lineage-manifest failure, relation-endpoint resolution. A passing PLL golden alone verifies
  one point only (`feedback_single_fixture_blind_spots`).
- **Reference integrity (binding)** — every structure-map ref resolves to an existing
  `atom_id`/`node_id`; every L3 relation endpoint resolves; every `status:active` alias
  resolves to exactly one node within its declared scope.
- **Two-tier no-loss round-trip** — (a) **raw**: byte-exact reconstruction from `raw_span` +
  `raw_source_hash` against the source artifact, for every captured atom; (b) **normalized**:
  reconstruction differs from raw only by declared, reversible transform operations. Tier (a)
  is the floor a `norm_layer` label cannot fake.
- **Re-binding (D33)** — geometry + fingerprint re-attach binds fresh atoms to the right
  `node_id`; a regenerated atom stream re-binds the stored `node_id`s given unchanged
  geometry; an ambiguous/below-threshold re-bind **fails loud** into governance (assert the
  raise), never silently mis-binds.
- **Space reconstruction (D30)** — Zipf-DP segmentation recovers known split/fragmented PLL
  spans, oracle-gated; a period-form the ≥2-of-3 oracle accepts is **not** "corrected" away
  (the `project_cleanup_corruption` risk).
- **Negative tests (fail-loud, no skip-masking)** — alias collision within a scope,
  unresolved relation endpoint, stale lineage manifest, and ambiguous re-bind each assert the
  raise; a mutated source fails until the sidecar is refreshed or migrated.

---

## 10. Decisions log

| # | Decision | State |
|---|---|---|
| D1 | Two-layer framing: extraction → durable structural model | Agreed (user) |
| D2 | Three-concern decomposition A/B/C, non-linear | Decided (user) |
| D3 | Identity per-book basis; designation off the identity path (R1, original form) | Superseded by D11/D12/D33 — Decided (user) |
| D4 | Content anchor checkpoints, never defines, identity (R2) | Decided (user) |
| D5 | Stage A typed + correctable by B (R3) | Decided (user) |
| D6 | Contiguous embedding build-now; overlapping hierarchy parked (R4) | Decided (user) — overlap parked by D32 |
| D7 | Block-level, span-capable cross-language (source↔target) alignment relation (R5) | Decided (user) — general LANG_A↔LANG_B per D34 |
| D8 | Structure recognition split out of `LanguagePlugin` | Decided (user); packaging deferred (O2) |
| D9 | HITL structural tagging as first-pass authoring | Decided (user); scale ceiling deferred (O3/D35) |
| D10 | Three-layer substrate: immutable addressed L1 atoms → versioned L2 projections → L3 annotations/spans/fields/relations | Decided (user) |
| D11 | Durable opaque `node_id` is internal identity; F3 handles + provenance/revision keys are renderings of `(node_id, handle policy)` with an alias table | Decided (user) — via D33/O1 |
| D12 | "Basis" demotes to a per-node-class handle policy with inheritance; `content-key` dropped (no forcing witness) | Decided (user) — via D33/O1 |
| D13 | Orthogonal provenance axis, separate from role and authorship; capture-with-role for excluded matter. **L1 capture-provenance and L2 content/editorial provenance are distinct semantic fields** (distinct identifiers or schema-enforced), and derived flags read L2 status + an explicit L1 rollup rule (§3.3) | Decided (user) |
| D14 | Lifecycle/governance spine: lineage manifest; stale = fail-loud; C-corrections are reviewer-approved patches, never auto-rewrite of L1; reference-integrity + round-trip tests | Decided (user) |
| D15 | Overlapping hierarchy stays unsolved (no tree overlap) but a `participates-in` relation hook (`contiguous:false`, typed members) is reserved now | Decided (user) — confirmed by D32 |
| D16 | Block model lands behind reconcile with a read-only `blocks → reconciled_chapters.json` adapter; consumers migrate one BR at a time | Decided (user) — resolves O5 |
| D17 | O2 reframed: declarative structure profile first, narrow code escape hatch only (Hamlet); PLL = profile + relocated ordinal reader | Decided (user); packaging deferred (O2) |
| D18 | Second-structure synthetic fixture (depth-0 + designation-string node) is a build-now gate, not a §9 add-on | Decided (user) |
| D19 | `SpanRef = {atom_id,start,end}` is a first-class L3 endpoint; relation endpoints are a typed union `atom_range \| projection_node \| span_ref` | Decided (user) |
| D20 | L1 identity is `atom_id`; structural identity is `node_id` (L2/L3) — kept distinct; overlays pin by evidence type | Decided (user) — via D33/O1 |
| D21 | Structure-map header is a lineage manifest (raw + atom-stream + canonical-projection hashes, profile + recognizer versions), referencing one `canonical_stream_id` | Decided (user) |
| D22 | No-loss round-trip is two-tier: raw (byte-exact) + normalized (reversible transform map); plus negative tests | Decided (user) |
| D23 | `role` = `front\|body\|back` only; pipeline participation is derived behavioral flags; validators switch on flags, not on a raw provenance class (either layer — L1 capture or L2 content, D13/§3.3) | Decided (user) |
| D24 | Aliases are records `{handle_type,value,scope,locale_or_witness,target_node_id,valid_from,valid_to,status}`; integrity = every active alias resolves to one node in its scope | Decided (user) — via D33/O1 |
| D25 | L1 is never mutated in place, but may be superseded by a new stream version (re-capture); old ids stay addressable, refs migrate/tombstone | Decided (user) |
| D26 | The legacy adapter is read-only; `triage` (in-place rewriter) migrates first off it, its edits becoming governed L2/L3 patches | Decided (user) |
| D27 | Declarative profile holds data primitives only; stateful parsing crosses a hard line into the code escape hatch — no control flow in JSON, no structure DSL | Decided (user) |
| **D28** | **Engine purpose: the production pipeline for a re-translated PLL (v2).** PLL is a real build target, not a study object — so B/C governance is not premature | **Decided (user)** |
| **D29** | **Structure assignment (B) runs BEFORE cleanup/triage** — i.e. before any *linguistic mutation*, **not** before raw capture or before the L1 substrate exists (A still precedes B in build order). Layout/content-block structure is geometric base-truth before linguistic truth; `node_id` minted early, before text mutation | **Decided (user)** |
| **D30** | Space/fragment reconstruction = geometry at L1 (word bboxes; PyMuPDF/Fitz) + Zipf-cost DP word-segmentation over the frequency dictionary, oracle-gated — not by inverting `collapse_spaces`/`rejoin_lines`; raw tier stays the byte-exact floor | **Decided (user)** |
| **D31** | Build enough of the spec to avoid PLL-shaped lock-in — build the general mechanism for each capability, instantiate what PLL needs; the deferral line is the genuinely-unsolved (overlap), not "untouched by PLL" | **Decided (user)** |
| **D32** | Overlapping/interleaved hierarchy parked for future support (reserved hook only, D15/D19) | **Decided (user)** |
| **D33** | **O1 resolved — Option A "store-and-rebind."** `node_id` is an opaque label stored in B's map (not derived); humans mint containers, extractor mints leaves; re-extraction re-binds via geometry + fuzzy fingerprint + struct-path, fail-loud. Rejected Option B (hash-derived → churn). One-way gate (regen-guard family), revisitable after build-out. Entails D11/D12/D20/D24 | **Decided (user)** |
| **D34** | **Cross-language alignment is general source↔target (LANG_A↔LANG_B); IT↔EN is PLL's instance, not the design.** Core carries no language pair (`feedback_engine_agnostic`); refines D7/R5 | **Decided (user)** |
| **D35** | **The structural model is designed for a reasonably unbounded unit count (target order ~100k units):** machine-minted leaf identity, flat addressable node storage, no super-linear structure ops. The O3 HITL scale ceiling is therefore a resource/cost question, not an architectural limit | **Decided (user)** |
| **D36** | **Adversarial-audit gate (§9):** a `BUILD`/`GATE` task is not DONE until a pre-commit adversarial pass (mutation hunt + overlapping wide/narrow reviewers) is clean; re-audit any behavior-changing remediation **to a fixpoint** (docs/test-only terminates), re-aiming apertures at the delta; proportional to surface, self-applied (not a hook), **forward-only (does not reopen DONE tasks)**. Codifies the de-facto 5-lens practice in the S1.3b/S1.4/S1.5 rows + `feedback_adversarial_audit_cadence` | **Decided (user)** |

---

## 11. Worked example — PLL slice

The schema on a few concrete PLL units: an ordinary chapter (`Capitolo Primo`), the
`prefazione`, an embedded letter, one page-provenance span, and the derived handle set.
**Schematic** — field names are proposals, not frozen; ids are neutral and
content-independent (`a*_` = atom, `n_` = node); `geom`/`bbox` values are illustrative. The
embedded-letter *placement* is illustrative — its real container is **«unverified»** (would
need a read of `output/italian_clean.md`); only the existence of an embedded letter is from
`findings/pll.md`.

### 11.1 Artifact A — L1 atom streams (immutable, addressed)

Per-witness streams **plus** one canonical reconciled stream. The structure map (§11.2)
references **only** the canonical stream; per-witness atoms relate to it through C alignment.

```jsonc
// data/atoms/copy1.json  — one stream per witness; copy2/copy3 parallel
[
  { "atom_id": "a1_0007", "witness": "copy1", "text": "Capitolo Primo",
    "raw_span": [10432, 10446], "raw_source_hash": "sha256:…copy1",
    "page_range": [12, 12], "norm_layer": "rejoin+collapse",
    "geom": { "present": true, "page": 12, "bbox": [72.0, 118.4, 523.1, 134.8],   // D30: Fitz/OCR word-box
              "geometry_engine": "pymupdf-ocr", "matched_witness_id": "copy1",     //   union, matched to
              "match_method": "token-bbox", "match_confidence": 0.97 },            //   THIS witness text
    "capture_provenance_class": "authorial" }
  // a1_0008 (body), a1_0042 (letter body), … parallel.
  // copy3 (Gemini-vision text, no word-box layer) carries  "geom": { "present": false }  — never invented.
]

// data/atoms/canonical.json  — the reconciled projection the structure map keys on
[
  { "atom_id": "ac_0007", "text": "Capitolo Primo", "page_range": [12, 12],
    "norm_layer": "rejoin+collapse", "capture_provenance_class": "authorial",
    "geom": { "present": true, "page": 12, "bbox": [72.0, 118.4, 523.1, 134.8],   // primary-witness box
              "geometry_engine": "pymupdf-ocr", "matched_witness_id": "copy1",     //   (matched), for
              "match_method": "token-bbox", "match_confidence": 0.97 },            //   re-bind
    "derived_from": [ { "witness": "copy1", "atom_id": "a1_0007" },
                      { "witness": "copy2", "atom_id": "a2_0007" } ] },
  { "atom_id": "ac_0008", "text": "Carlo di Rudio nacque a Belluno…", "page_range": [12, 13],
    "capture_provenance_class": "authorial", "derived_from": [ /* … */ ] },
  { "atom_id": "ac_0042", "text": "Fratelli, l'ora è giunta…", "page_range": [19, 20],
    "capture_provenance_class": "authorial", "derived_from": [ /* … */ ] }
]
```

`atom_id` is **L1 identity** (text evidence + coordinates), distinct from the structural
`node_id` of §11.2. `raw_span` + `raw_source_hash` make the **raw** round-trip tier
byte-exact; `norm_layer` is human-readable provenance only, never the loss guarantee. `geom`
(D30) is the **optional** word-box geometry, the **primary re-binding signal** (§3.4) and the
base layer for space/fragment reconstruction; it is a physical fact of the witness scan, so
the canonical atom carries its primary witness's box **where a matcher confidently aligns the
box to that witness's text** — otherwise `geom.present` is `false` (copy3 has no box layer at
all), never invented. Each present box records its `geometry_engine` / `matched_witness_id` /
`match_method` / `match_confidence`, and an unmatched box is unusable as a primary re-bind
anchor (§3.0). Page furniture and source
wrappers are captured atoms too, with `capture_provenance_class: "page-furniture"` /
`"source-wrapper"` (the L1 capture field; L2 content/editorial provenance is a *distinct*
field, §3.3) and a `processing_scope` that excludes them from translate/retention —
captured-but-excluded, never dropped.

### 11.2 Artifact B — structure map (B's output, the durable catalogue)

```jsonc
// books/pll/work/structure_map.json
{
  "lineage": {                                  // a manifest, not one hash (§3.6)
    "source_artifacts": [ { "witness": "copy1", "hash": "sha256:…" },
                          { "witness": "copy2", "hash": "sha256:…" } ],
    "atom_streams":     [ { "id": "copy1", "hash": "sha256:…" },
                          { "id": "canonical", "hash": "sha256:…" } ],
    "canonical_stream_id": "canonical",         // the one stream nodes key on
    "projection_id": "proj-…",
    "profile_version": "pll-structure-1",
    "recognizer_version": "italian-ordinal-1"
  },
  "handle_policies": {                          // a policy, NOT identity (§3.4)
    "chapter": "position-path", "front-matter": "designation-string",
    "embedded-letter": "position-path" },
  "nodes": [
    { "node_id": "n_pref", "class": "front-matter", "role": "front", "minted_by": "human",
      "designation": null, "title": "Prefazione", "handle": "prefazione",
      "aliases": [ { "handle_type": "html_slug", "value": "prefazione",
                     "scope": "edition", "status": "active", "target_node_id": "n_pref" } ],
      "children": ["n_pref_p1", "n_pref_p2"] },

    { "node_id": "n_chap", "class": "chapter", "role": "body", "minted_by": "human",   // D33
      "designation": { "kind": "ordinal-word", "raw": "Capitolo Primo", "value": 1 },
      "title": null, "handle": "p1_ch01",       // rendered from node_id + policy
      "aliases": [ { "handle_type": "html_slug", "value": "parte-prima-capitolo-primo",
                     "scope": "edition", "status": "active", "target_node_id": "n_chap" } ],
      "rebind_anchors": { "geom": { "page": 12, "bbox_region": [70, 110, 525, 140] },   // checkpoints,
                          "content_fp": "fnv1a:…", "struct_path": "body/0" },           //   not identity (R2)
      "heading_atoms": ["ac_0007"],             // container owns the heading atom only
      "children": ["n_chap_p1", "n_letter"] },

    { "node_id": "n_chap_p1", "class": "paragraph", "parent": "n_chap", "minted_by": "machine",  // D33
      "rebind_anchors": { "geom": { "page": 12, "bbox_region": [70, 145, 525, 360] },
                          "content_fp": "fnv1a:…", "struct_path": "body/0/0" },
      "body_atoms": ["ac_0008"] },              // leaf projection owns body atoms

    { "node_id": "n_letter", "class": "embedded-letter", "role": "embedded", "minted_by": "human",
      "parent": "n_chap",                       // schematic placement — real container «unverified»
      "authorship": "Mazzini",                  // authorship override, not book-level
      "heading_atoms": [], "children": ["n_letter_v1"] },   // NO body_atoms on the container

    { "node_id": "n_letter_v1", "class": "verse", "parent": "n_letter", "minted_by": "machine",
      "body_atoms": ["ac_0042"], "decision": "human-approved" }
  ]
}
```

No atom is owned twice: a container owns its child nodes plus any heading/signature atoms; a
leaf projection owns body atoms. `n_letter` is a **container node** (contiguous, so the tree
expresses it natively — no relation). Each node carries `minted_by` (`human` for the
container tree, `machine` for leaves — D33) and `rebind_anchors` (geometry + fuzzy content
fingerprint + structural path) that re-attach the stored `node_id` to fresh atoms on
re-extraction; the `node_id` itself is opaque and never recomputed, and a failed/ambiguous
re-bind fails loud into the §3.6 governance path. Queries: "all letter text" = subtree of
`n_letter`; "all chapter paragraphs" = `paragraph`-class descendants of `n_chap` (letter
included); "source order, letter once" = in-order walk of canonical atoms (`ac_0042` once).

### 11.3 Artifact C — relations (graph + alignment), typed endpoints

Endpoints are a typed union — `atom_range | projection_node | span_ref` — so a relation can
target a whole node *or* half a sentence.

```jsonc
// books/pll/work/relations.json
{
  "alignment_set": "align-…",                   // versioned edge set
  "relations": [
    // page-provenance: node ⇒ scan pages, from canonical atom page_range (not (ch_id,para_idx))
    { "type": "page-span", "endpoint": { "kind": "projection_node", "node_id": "n_chap_p1" },
      "pages": [12, 13], "method": "atom-page-range" },

    // IT↔EN alignment: per-edge method + confidence; endpoints may be node or span
    { "type": "align",
      "src": { "kind": "projection_node", "node_id": "n_chap_p1" },
      "tgt": { "kind": "projection_node", "node_id": "en:n_chap_p1" },
      "confidence": 0.98, "method": "by-content" }

    // a later partial correction needs NO schema change:
    // ,{ "type": "align",
    //    "src": { "kind": "span_ref", "atom_id": "ac_0008", "start": 220, "end": 540 },
    //    "tgt": { "kind": "projection_node", "node_id": "en:n_chap_p1b" },
    //    "confidence": 0.91, "method": "human" }

    // reserved hook — typed members, discontiguous, no PLL instance (D15/D32):
    // ,{ "type": "participates-in", "contiguous": false,
    //    "members": [ { "kind": "projection_node", "node_id": "…" } /* , … */ ] }
  ]
}
```

Every endpoint binds to `node_id` / `atom_id`, never to a positional index — the live
`typeset.py` mispoint (EN index reused on the IT column) is structurally impossible here. The
alias records (§11.2) carry any handle that moved, and §9's integrity test fails loud on any
unresolved endpoint.

---

## Appendix — corpus evidence index

Ten close-reads under `structure_corpus/findings/` (`README.md` carries the shared template);
treat as evidence to re-check, not gospel — e.g. `findings/hamlet.md` over-claims the
interleaved inner play as a clean "subtree" (it is the overlapping case, R4/D32). Witnesses
and the rulings they drive: PLL (R1/R5), Kybalion (depth-0), Dante (R5, verse), Pepys (R2),
Darwin (R1 cross-edition), Britannica (R1, C edges), Beeton (block vocab), Hamlet (R3/R4),
Tractatus (R1, depth-from-designation), Atlantic (heterogeneous children).
