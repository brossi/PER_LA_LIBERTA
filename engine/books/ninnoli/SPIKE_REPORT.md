# Ninnoli specimen spike — first complete run

Date: 2026-07-12  
Baseline: `3d37189`  
Accepted blind Italian SHA-256: `f4da70a9646f7c2cee7db918163d313275da5eaf00831c230a986be90f30c305`  
Accepted blind English SHA-256: `97d7701fd2fc639ea1efb2bb423599308dcd2788d61bc09e4ff698f3675be331`

## Outcome

The real 110-page book completed scan geometry, layout-assessment shadowing, OCR, reconciliation,
triage, cleanup, validation, and single-model translation. The canonical artifacts are Markdown.
Refinement, multi-model synthesis, and typesetting were intentionally excluded from this spike.

The run proves that a real specimen is useful now, but it does **not** prove the engine is ready for
unattended production. The post-seal human reference found a 2.13% token edit distance in the
accepted Italian text, including low-complexity semantic errors that all internal gates missed and
that the English translation faithfully propagated.

## What the run forced us to fix

1. **Flat collections had no segmentation path.** The language plugin recognized the structure of
   the original project, not Ninnoli's five named stories. Ordered manifest-declared raw sections now
   fail loudly on missing or reordered boundaries and ignore repeated running heads.
2. **Adjacent editions cannot be equal OCR voters.** Treating the 1883 scan as Copy 2 inflated one
   story by roughly 19%. It is now a diagnostic `comparison` role and cannot enter reconciliation.
3. **Paragraph-list alignment inflated same-scan OCR.** Naive two-way alignment produced 998 flags
   and a 9–21% section expansion. Copy 1 now owns extent while Copy 3 may correct only anchored text;
   the accepted reconciliation produced 348 provenance-preserving disagreements.
4. **Provider refusal was not an OCR error.** Gemini returned `RECITATION` with no text on pages 11,
   39, and 91. The engine now reports the finish reason; an explicit, provenance-bearing local
   Tesseract fallback repaired only those failed checkpoints before the completeness gate published
   Copy 3.
5. **Triage was opaque and non-restartable.** Its 348 items became 70 silent sequential batches and
   took about sixteen minutes. It auto-accepted 91 decisions, changed 41 occurrences, and retained
   255 for human review. This run completed, but checkpointing and per-batch progress remain owed.
6. **Deterministic cleanup was insufficient.** It passed structure and retention but initially left
   seven high-severity ornament/garble tokens. The optional chapter correction pass reduced this to
   zero high-severity flags; final retention was 97.2%, with 60 dictionary-only advisories.
7. **Translation was still a scaffold.** A minimal single-model step now consumes only hash-bound,
   validation-passed `clean.md`; binds rendered sections to stable reconciliation ids; fingerprints
   source, prompt, model, and settings; checkpoints each story; and refuses partial publication.

## Geometry and layout assessment

- Scan pin: `a8ab798c9d9aed9f07626cff6f2795d6968f754e3458bcfcf160146d3e4ac8ad`
- Pages: 110
- Tesseract word boxes: 25,319
- Dropped boxes: 0; out-of-bounds boxes: 1
- Layout assessments available: 110/110
- Near-blank capability: 107 supported, 3 uncertain
- OCR text-likeness: 96 supported, 7 uncertain, 7 not applicable
- Density/column judgments: deliberately not applicable because the spike supplied no policy

The sidecar was useful as observation and provenance, not as a decision-maker. It did not catch the
semantic OCR errors described below, which is consistent with its current capability scope.

## Accepted translation diagnostics

| Story | Source chars | English chars | Ratio | Source paragraphs | English paragraphs |
|---|---:|---:|---:|---:|---:|
| Storiella vecchia | 36,748 | 38,347 | 1.044 | 156 | 154 |
| Era matto o aveva fame? | 37,439 | 39,117 | 1.045 | 155 | 155 |
| Cavalleria assassina | 12,902 | 13,219 | 1.025 | 26 | 26 |
| Scellerata! | 27,773 | 28,959 | 1.043 | 216 | 216 |
| Quintino e Marco | 28,567 | 28,794 | 1.008 | 66 | 66 |

All five calls ended normally, no preamble was emitted, and every story and exact source-page list
was present in the aggregate. The two-paragraph contraction in the first story is diagnostic and
deserves editorial review; the current completeness gate records it but does not threshold it.

## Post-seal evaluation

The Gutenberg reference remained unread until the blind Italian and English outputs were complete
and hashed. Gutenberg #28231 identifies itself as a human-produced transcription of the same 1884
third edition. Token alignment yielded:

| Story | Token edit distance | Reference tokens | WER |
|---|---:|---:|---:|
| Storiella vecchia | 52 | 6,017 | 0.86% |
| Era matto o aveva fame? | 77 | 6,001 | 1.28% |
| Cavalleria assassina | 59 | 2,075 | 2.84% |
| Scellerata! | 117 | 4,414 | 2.65% |
| Quintino e Marco | 187 | 4,643 | 4.03% |
| **Whole book** | **492** | **23,150** | **2.13%** |

The WER includes typographic and tokenization differences, so it is not a pure semantic-error rate.
However, the sample contains unmistakable missed OCR errors:

- `E Domenico` → reference `Se Domenico`; translated as “And Domenico,” changing the opening logic.
- `un di quei tali` → `un di quei buli`.
- `vino di Gussago` → `vinetto di Gussago`.
- `cartaccia` → `partaccia`.
- `Uella mattina` → `Quella mattina`.
- `contrappeso` → `contrappelo`.
- `terraiolo` → `ferraiolo`.
- `accarezzandole` → `accarezzandolo`.
- The running head `PORTA VECCHIA` entered the accepted Italian body; the translator silently
  omitted it, demonstrating an untracked source-to-target deletion even though it was furniture.

These are the decisive result of the spike: structural completeness, dictionary membership, quote
balance, character coverage, and LLM cleanup can all be green while locally plausible wrong words
survive. The engine therefore needs a source-grounded deviation/sampling gate before a green Italian
artifact is treated as production-ready. A frozen oracle is not the pipeline test; a sealed reference
is valuable **after** the run as an honest measuring instrument.

## Recommended next move

Run more specimens now, but treat them as adversarial calibration, not production. Before the next
book, add only three controls:

1. restartable triage batches with visible progress;
2. a sampled scan-grounded review artifact keyed to the accepted source hash;
3. a post-cleanup cross-witness residual pass that targets plausible in-dictionary substitutions and
   surviving furniture, not only garble patterns.

Do not port multi-model synthesis or typesetting yet. The current bottleneck is source truth, not
English presentation.
