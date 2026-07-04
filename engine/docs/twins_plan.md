# Twins — duplicated-section flagging as stream QA (plan stub)

**Status: STUB for discussion — not ratified.** No tracker row, milestone number, or
issue is minted; those follow ratification (§7). The governing principle IS settled
(Ben, 2026-07-04, in discussion): **this is a flagger, never a deduplicator** — every
flag feeds an *intentioned decision by the human editor*; the pipeline never silently
merges, deletes, or picks a side. The machine's job is detection, classification
evidence, and a worklist; the verdict is human.

## §1 Charter and origin evidence

Detect near-identical spans (twins) in the frozen witness/canonical streams; classify
intentional repetition vs accidental duplication with calibrated abstention; record
human verdicts as durable relations; downstream consumers read verdicts, never
re-derive them.

Why we believe the determination is reliable — every signal below has already worked
in practice:

- **PLL #655** — the whole-P2-ch22 duplication in the live edition: 19K chars at
  similarity 0.977 (`autojunk=False`), traced to a reconcile chapter-split miss.
- **P1-ch22 canonical alignment twin** (found 2026-07-04): the chapter opening
  ("AFFERMANO gli storici…") present twice in `canonical.json`
  (`canonical_01817`/`canonical_01979`, each behind its own heading atom), with
  complementary single-witness derivations — copy1-only vs copy2-only — the
  mechanical signature of an alignment-failure twin. The seeder flagged the region
  ("duplicate copy segment") without being able to say why; ~14 sibling flags
  suggest more such regions.
- **The anti-pattern, lived:** PLL cleanup's *silent sentence dedup* was a
  corruption source; and #655's discarded-candidate twin carried **better readings**
  than the kept copy (`A DURANCE`/`Canarie` vs `La Durr`/`Carmarie`). An accidental
  cross-witness twin is a free passage-level 2-way witness alignment — merge
  material, not garbage.

## §2 The three signals (escalation order)

- **S-1 Text twins.** Shingle/similarity scan over the stream above a token-length
  floor `L`, flagging pairs in a similarity band `[hi_lo, 1.0)`. Length is the first
  intentional/accidental discriminator (running heads, folios, index entries,
  chapter titles are a line; accidental duplication is paragraph-to-chapter scale).
  The high-but-not-exact band is itself signal: two OCR passes over different
  physical instances never match exactly.
- **S-2 Provenance signature.** Per-atom derivations classify the twin's birth:
  *cross-witness complementary* (copy1-only vs copy2-only → alignment-failure twin),
  *within-witness* (→ dittography / source repetition), *both-witness at both
  positions* (→ intentional print repetition — each witness prints the index too).
- **S-3 Physical instance counting** (S2.1 sidecar, no new scan reads). The scan
  prints a passage once, so its word boxes exist once; DT-8's multiset consumption
  means twins *compete* for the same boxes — the loser surfaces as zero/low-match
  where its text visibly exists. Same-page-window competition ⇒ scan-confirmed
  accidental; disjoint printed instances ⇒ intentional. This upgrades S-1/S-2
  candidates to physical evidence mechanically.

## §3 Decisions to ratify (sketch)

- **DT-1 Homes** *(RATIFIED 2026-07-04)*. Detector in `structure/twins.py` (core,
  book-agnostic). Three-artifact split, mirroring the geometry-review design
  (`s2_1_plan.md` DT-10):
  1. `work/data/stream_qa/twin_report.json` — the detector's output (candidate
     pairs, scores, signature class); regenerable QA output in the ignored `work/`
     area, carrying the stream fingerprint it was computed against;
  2. `books/<id>/review/twin_verdicts.json` — **tracked** human verdicts with
     provenance (who/when/evidence cited), the sibling-of-`work/` posture of
     `geometry_verdicts.json`; the editor's intentioned decisions accumulate here,
     survive re-runs, and are replayable;
  3. the L3 relation store — only *applied* verdicts materialize as `twin-of`
     relations (durable, schema-versioned, loader-hardened); `relations.json` is
     ratified-truth only.
  Verdict enum `{intentional, accidental_merged, accidental_authoritative}` plus
  `pending`; `pending` lives in artifacts 1–2 only, never in 3. Applying a verdict
  is an explicit, idempotent, stale-guarded act (the DT-10 replay discipline).
- **DT-2 Position** *(RATIFIED 2026-07-04, with two clauses)*. Detector runs
  post-freeze, pre-seeder; read-only over the frozen streams (its only write is its
  own report under `work/` — inside the I7 containment boundary); deterministic
  (double-run byte-identical).
  - **Staleness semantics for consumers:** the report carries the stream
    fingerprint it was computed against. A consumer finding a
    fingerprint-mismatched report fails loud (`StaleArtifactError`, shared loader
    taxonomy) — evidence about streams that no longer exist is worse than none. An
    *absent* report degrades gracefully: the seeder runs and its flag report notes
    "no twin report present." Absent = a visible sequencing fact; stale = a
    correctness hazard.
  - **Step position is normative for future books:** `capture → freeze → twins →
    seed` is the named ingestion order. For PLL (already seeded, first-write
    guarded) the detector back-fills the report; the existing seeder flags gain
    twin citations only if a human ever chooses a re-seed.
- **DT-3 Abstention** *(RATIFIED 2026-07-04, tightened)*. **No confidence band ever
  verdicts.** Bands affect worklist *ordering and annotation only* — a 0.99
  cross-witness long twin arrives at the top of the worklist with its evidence
  attached, but it arrives `pending` like everything else. The only automatic
  outcome in the tool is *non-detection* below the length floor, and that is scope,
  not judgment (a line-length repeat is not a candidate, the same way a non-heading
  line is not a seeder candidate). Corollary, deliberately: a **long intentional
  repetition should flag** and receive a human `intentional` verdict — that is the
  system working, not noise; there is no "obviously intentional, suppress it"
  heuristic above the floor, because that heuristic would be the deduplicator
  returning through the side door. The must-NOT-flag red fixtures are strictly
  below-floor classes. The S-2 signature classifier abstains the same way: an
  ambiguous signature emits `unclassified`, never a guessed class. Verdicts are
  human-only — the flagger/decider boundary is the charter, not an implementation
  detail.
- **DT-4 Merge path** *(RATIFIED 2026-07-04, with two clauses)*. An `accidental`
  cross-witness twin is reconciliation input: word-level 2-way reconciliation of
  the pair yields one authoritative span whose provenance records both twins.
  Merge is a human-triggered action with a recorded verdict; never automatic.
  - **Materialization defers to S8.1 — the verdict record IS the merge.** An
    `accidental_merged` verdict carries the approved merged text plus per-word
    provenance (which twin supplied each reading) in the tracked verdict artifact.
    The twins stay physically in the frozen stream until an S8.1 supersession pass
    consumes ruled verdicts and mints the superseding stream revision. L1
    immutability holds; no shadow-stream (authoritative text never lives outside
    the stream store); S8.1 gains a concrete named input. (The S1.3a posture:
    derived data waits in a sidecar; the frozen artifact is never mutated.)
  - **The machine proposes, the human disposes.** At verdict time the CLI computes
    and presents the word-level reconciliation *proposal* (diff + merged
    candidate — mechanical, deterministic); the editor approves or hand-edits, and
    only approved text enters the verdict record. The flagger principle one level
    deeper: merge content is an intentioned editorial decision — `A DURANCE`/
    `Canarie` vs `La Durr`/`Carmarie` is a word-level judgment no similarity score
    may make.
- **DT-5 Seeder consumption** *(RATIFIED 2026-07-04, with the pending/ruled split)*.
  The seeder reads the twin report; the DT-3 no-auto-verdict rule draws the
  boundary of what it may do with it:
  - **Pending twins annotate, never suppress.** A heading inside a `pending` twin
    region participates in boundary matching exactly as without the report; the
    *flag* improves — "heading at `canonical_01978` sits inside twin t-3
    (`pending`, cross-witness signature) — likely the duplicate copy's heading;
    REVIEW" replaces the three-way guess ("duplicate copy segment, running head,
    or index entry?").
  - **Ruled verdicts bind.** Under an `accidental_*` verdict, the non-authoritative
    side's headings are excluded as boundary candidates outright; the flag states
    the exclusion and cites the verdict. Human decision in, machine consequence
    out.
  - **Inheritance and direction:** absent/stale report semantics per ratified DT-2
    (absent = noted and proceed; stale = fail loud). Flow is strictly
    one-directional, twins → seed — the detector never consumes seeder output; a
    seeding guess must not become twin evidence.
- **DT-6 Numbers ride a ruling ledger** *(RATIFIED 2026-07-04 as process, with
  three clauses; the numbers themselves stay open)*. Measured on the PLL streams,
  proposed with bases, ruled per-item, never bundled (the s2_1 §8 pattern).
  - **Decision point = slice A; the ledger gates slice-A-DONE, not build-start.**
    The detector is built with the numbers as parameters; its first PLL run
    produces the proposal sheet; the ledger is ruled; slice A's acceptance run
    executes with ruled values. No throwaway measurement script duplicating the
    detector. (The DT-13 shape: an open ruling gates the row's DONE, never the
    build.)
  - **The ledger, named in full:** P-1 length floor `L`; P-2 similarity band
    `[hi_lo, 1.0)`; P-3 shingle size `k`; P-4 position-class distance boundary
    (adjacent-displaced vs far, S-2). Implicit numbers are how thresholds escape
    their ledger — nothing ships unnamed.
  - **The measured basis places both poles:** the known twins (the P1-ch22
    canonical pair; the #655-scale event) AND the known intentional/short classes
    (running heads, folios, the end-matter index cluster) located in the
    length × similarity plane, with chosen values separating them by a stated
    margin. What the plane cannot separate belongs to the mid-band worklist *by
    design* (DT-3 working, not a calibration failure).

## §4 Red-first matrix (sketch — rows firm up at ratification)

| Invariant | RED (named violation) |
|-----------|----------------------|
| planted long twin (≥ L, in-band) flags | remove the plant's flag → red |
| running-head series must NOT flag | planted page-periodic short repeats stay silent; mutant that drops the length floor → reds the must-NOT fixture |
| index-entry cluster must NOT flag | end-matter title cluster fixture stays silent |
| same-witness dittography classifies differently from cross-witness twin | signature mutant conflating the two → red |
| S-3 adjudicator: one box never binds twice | double-bind mutant → red (extends G-24's consumption discipline) |
| no band ever verdicts — every above-floor candidate lands `pending` | mutant auto-verdicting any band (incl. a "suppress obviously-intentional" heuristic) → red; long-intentional-repeat fixture must FLAG (and stay `pending`) |
| report loader joins the shared loader taxonomy | absent → `MissingInputError`; malformed/stale → `StaleArtifactError` |
| determinism | double-run byte-identical; emission-order shuffle invariant |

## §5 Slices

1. **Slice A — detector + report + worklist** (S-1 + S-2). No dependencies;
   buildable now. PLL acceptance: finds the P1-ch22 canonical twin; does not flag
   the running heads, folios, or the end-matter index.
2. **Slice B — geometry adjudicator** (S-3). Gated on S2.1 slice 1 (#37's sidecar).
   Another named consumer of the slice-1 run artifacts.
3. **Slice C — verdicts + merge + seeder consumption.** Verdict CLI home *(RULED
   2026-07-04)*: **own entry point, `python -m engine.structure.twins`** (the
   module owns its CLI; `__main__.py` carries the import-inert guard from day
   one). Not bolted onto the authoring CLI — different artifact family, different
   lifecycle. A shared `review` front-door for all human worklists is **deferred
   to a named trigger**: when #40 lands the geometry verdict CLI, both consumers
   exist and the shared surface gets designed against real shapes
   (deferral-for-information — revisit at #40's close, owner: the #40 DoD).
   Plus DT-4 merge path, DT-5 seeder integration.

## §6 Non-goals

- **No auto-delete, no auto-merge, ever** — charter, restated.
- The **live edition** (`output/italian_clean.md`) — the P2-ch22 dup there belongs
  to the deviation-review track (#655, held for adjudication), not this tool. The
  engine's streams are frozen raw-witness captures; this tool reads those.
- **v2-extraction gating** — S11 consumes twin verdicts later; nothing here gates
  extraction yet.

## §7 Open for ratification

DT-1…DT-6 as written; the §3/DT-6 numeric values (measure first); verdict-CLI home;
whether twin relations live in `relations.json` or an own sidecar; tracker
row/milestone number + issue minting; slice-A-now vs after-S2.1-slice-1 sequencing.
