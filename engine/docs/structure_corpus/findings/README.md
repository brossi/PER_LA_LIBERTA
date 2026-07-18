# Structural close-read findings

Durable per-specimen structural reads for the `spike/document-structure` branch.
One artifact per work; every work is a **co-equal structural witness** (no
privileged baseline — see `../SOURCES.md`). Each file documents what the text
*actually exhibits*, including anything that contradicts the working union model.

These artifacts are the evidence base for `ENGINE_STRUCTURE_PLAN.md`. They feed two
separable design concerns:

- **Extraction** — raw text → a tree of typed blocks (recognition; noisy; plugin-heavy).
- **Tracking** — a stable identity per node that survives downstream stages and
  re-runs (deterministic; book-agnostic). Working hypothesis: identity = the
  **position-path**; the **designation** (Chapter VII / Capitolo Primo / a date /
  a headword) is demoted to a read-only display/citation field.

## Index

| Artifact | Work | Witness role (distinctive feature) |
|----------|------|------------------------------------|
| `pll.md` | Per la Libertà! (Crespi 1913) | the live target; ordinal-word designation; 3 competing id schemes (the tracking anti-pattern) |
| `kybalion.md` | The Kybalion (1908) | flat tree (0 grouping levels); Roman designation *separate from* title; attributed aphorism blocks |
| `dante.md` | Divina Commedia (IT + Cary EN) | named cantica › Roman canto › tercet › line; verse-primary; cross-language structural fidelity |
| `pepys.md` | Pepys Diary (complete) | deepest tree (4); **date** designation, often partial/parent-dependent |
| `darwin.md` | Origin of Species (1859 + 1872) | **cross-edition renumbering** — the proof that position ≠ designation |
| `britannica_1911.md` | EB 1911 (England slice) | **non-positional** headword/lookup/graph identity; per-article signed authorship |
| `beeton.md` | Beeton, Household Management (1861) | non-prose body: structured records, tables, captioned figures |
| `hamlet.md` | Hamlet | Act › Scene; speaker-attributed dialogue; stage directions; play-within-a-play (recursion) |
| `tractatus.md` | Tractatus (TeX) | **recursive dotted-decimal** depth; designation *encodes* the position-path |
| `atlantic.md` | Atlantic Monthly (Aug 1866) | **heterogeneous** collection: Issue › Article of mixed kinds; unsigned |

## Shared template

Every artifact follows these sections so the witnesses stay comparable:

0. **Identification** — work / author / date / edition(s) / source file + PG# / slice / size / how sampled.
1. **Container hierarchy** — named levels (e.g. book › part › chapter); max depth; uniform or ragged; child counts (asymmetric?); verbatim boundary example per level with line anchors.
2. **Designation system** — kind (ordinal-word / Roman / Arabic / proper-name / date / headword / dotted-decimal / none / mixed); verbatim examples; globally unique or only-within-parent; self-contained or parent-dependent; does it *encode* position?
3. **Descriptive titles** — present? separate node from the designation or fused? examples.
4. **Body block vocabulary** — the typed blocks observed; verbatim example of each non-prose type with anchor; blocks carrying own attributes (speaker / date / author / citation)?
5. **Matter** — front (TOC, preface, dramatis personae…) and back (glossary, index, notes…); siblings of body or special-cased in the source?
6. **Identity & cross-witness behavior** — how a unit is canonically referenced in practice; for paired works, the structural diff between witnesses (what's invariant, what shifts) and what it proves about identity.
7. **Authorship** — single book-level author or per-node (signed)?
8. **Extraction cues** — the concrete textual markers a parser keys on for each boundary in THIS raw text (quote them); the traps (false boundaries, transcription noise, inconsistent markers, run-in headings).
9. **What this witness uniquely forces in the model** — the design capability it mandates; what breaks if the model ignores it.
10. **Open questions / contradictions** — anything that didn't fit, contradicted the union model, or needs a human ruling.
