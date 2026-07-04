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

- **DT-1 Homes.** Detector in `structure/twins.py` (core, book-agnostic); persisted
  report `work/data/stream_qa/twin_report.json`; human worklist mirroring the
  geometry-review pattern (`s2_1_plan.md` DT-10: candidates under `work/state/`,
  verdicts tracked under `books/<id>/review/`); twin relations recorded with the L3
  relation machinery, verdict enum `{intentional, accidental_merged,
  accidental_authoritative}` plus `pending`.
- **DT-2 Position.** Detector runs post-freeze, pre-seeder; read-only over the
  frozen streams; deterministic (double-run byte-identical).
- **DT-3 Abstention.** Mid-band candidates route to the worklist; the tool never
  auto-verdicts. Verdicts are human-only — the flagger/decider boundary is the
  charter, not an implementation detail.
- **DT-4 Merge path.** An `accidental` cross-witness twin is reconciliation input:
  word-level 2-way reconciliation of the pair yields one authoritative span whose
  provenance records both twins. Merge is a human-triggered action with a recorded
  verdict; never automatic.
- **DT-5 Seeder consumption.** The seeder reads the twin report: duplicate-heading
  flags cite twin ids instead of guessing ("duplicate copy segment, running head,
  or index entry?" becomes "twin t-3, verdict pending"); a verdict-carrying twin
  region cannot double-seed.
- **DT-6 Numbers ride a ruling ledger.** `L` (length floor), the similarity band,
  and shingle size are *measured on the PLL streams first* (the s2_1 §8 pattern:
  proposals with measured bases, ruled per-item, never bundled).

## §4 Red-first matrix (sketch — rows firm up at ratification)

| Invariant | RED (named violation) |
|-----------|----------------------|
| planted long twin (≥ L, in-band) flags | remove the plant's flag → red |
| running-head series must NOT flag | planted page-periodic short repeats stay silent; mutant that drops the length floor → reds the must-NOT fixture |
| index-entry cluster must NOT flag | end-matter title cluster fixture stays silent |
| same-witness dittography classifies differently from cross-witness twin | signature mutant conflating the two → red |
| S-3 adjudicator: one box never binds twice | double-bind mutant → red (extends G-24's consumption discipline) |
| mid-band routes, never verdicts | mutant auto-verdicting the mid-band → red |
| report loader joins the shared loader taxonomy | absent → `MissingInputError`; malformed/stale → `StaleArtifactError` |
| determinism | double-run byte-identical; emission-order shuffle invariant |

## §5 Slices

1. **Slice A — detector + report + worklist** (S-1 + S-2). No dependencies;
   buildable now. PLL acceptance: finds the P1-ch22 canonical twin; does not flag
   the running heads, folios, or the end-matter index.
2. **Slice B — geometry adjudicator** (S-3). Gated on S2.1 slice 1 (#37's sidecar).
   Another named consumer of the slice-1 run artifacts.
3. **Slice C — verdicts + merge + seeder consumption.** Verdict CLI (home to be
   ruled: extend the authoring CLI vs own entry point), DT-4 merge path, DT-5
   seeder integration.

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
