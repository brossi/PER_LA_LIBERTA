# S2.0 geometry gate — 5-lens adversarial audit (2026-06-29)

Record of the multi-agent adversarial pass over the S2.0 geometry probe (`s2_0_geometry_alignment.md`,
`books/per_la_liberta/probes/s2_0_geometry_probe.py`) and its remediation. Anti-patterned by design
(divergent stances + heterogeneous briefings + inverted frame + concrete-repro requirement) so the
harness would refute rather than confirm. Five agents, reaching by different methods:

1. **Replication** — re-ran the probe + re-derived the numbers with independent code.
2. **Methodology / confound** — attacked the verdict (witness target, median, BoW ceiling, threshold).
3. **Two-column finding** — inspected page images; tried to break the two-column claim.
4. **S2.1 design inputs** — full-book density check; symmetry logic; human-in-loop spec.
5. **Completeness** — spec-vs-deliverable strata coverage and unbacked claims.

All numbers reproduced exactly and deterministically (replication). The findings were **claims built on
the numbers**, not arithmetic errors. The agents self-corrected: Agent 5's strongest finding (witness
substitution) was *defused* by Agent 2 measuring the thing Agent 5 only reasoned about.

## Findings and disposition

| # | Finding | Severity | Disposition |
|---|---|---|---|
| A | "Settled PRIMARY" overclaims: pre-registered *naive* metric = 0.49 (no-geometry band); PRIMARY recovered only via a col-aware **prototype of the S2.1 detector**, reported as a **median** hiding mean 0.82 / ~30% per-page fail. | MED-HIGH | **Accepted.** Verdict (b) → **conditional-primary, re-gate after S2.1**, measured by mean + per-page pass-rate. Probe now reports mean + pass@0.85. |
| B | Density "clean separation" claim **empirically false** on all 278 pages: ink-fraction is a continuum and **non-monotone** (dark endpaper 0.97 > densest prose; 22 content pages below the floor). | HIGH | **Accepted / retracted.** Report §"S2.1 design inputs" replaces fixed-threshold with a two-sided/band + dark-page-class requirement. |
| C | "37/37 two-column" is a detector artifact: `min(single central bin)` returns the two-column signal on *every* page (incl. single-column prefazione). "in-bounds 0.999" near-tautological. | MAJOR | **Accepted / fixed.** New detector = contiguous central gutter + centrality + column-balance (30/37 on the sweep; calls single-column pages correctly). in-bounds relabeled a smoke test; box/witness ratio added as a hallucination flag. |
| D | Witness substitution: every number is vs copy3 (word-level adjudicator), never the structural copy1/2; copy1 «unverified». | HIGH (A5) → LOW (A2) | **Defused by measurement.** Agent 2 located copy1 spans (overlap-windowing) and measured copy1 reads its columns at 0.98 — column-ordered, representative. Recorded; copy1 page-map still absent (windowed, not native). |
| E | Human-in-loop gate unimplementable as written (no confidence metric / threshold / human-output schema / volume bound). | HIGH | **Accepted.** Report now requires those four to be specified in S2.1; framed as the safety net for both order-sourcing branches. |
| F | Strata mislabels: "bad-OCR region" never sampled (269 is a clean TOC); embedded_letter (189/193) is narrative prose (no set-off letters in the book); page_furniture degenerate (n=0 coverage); footnotes sampled call-out not note-body. | MED | **Accepted.** Stratified labels corrected; footnote-body pages added; report states the bad-OCR and set-off-letter strata were not located rather than mislabeling. |
| G | BoW "ceiling" inflated ~1.5 pts by 53% stopwords; content-token anchorability ~0.92. | LOW | **Accepted.** Probe computes content-token BoW; report credits re-bind the content-token ~0.92. |
| H | Symmetry "corroborator" redundant with the valley; "reject if not mirror-balanced" mis-handles asymmetric multi-column. | LOW | **Accepted.** Symmetry rule dropped; valley (RXYC) is the discriminator. |
| I | Threshold inconsistency (sweep counts two-column at gutter<0.12, reorder splits at <0.06); negative-bin histogram wrap; `line_h … or 10` falsy-zero (same class as a prior fix); sweep computed BoW only. | MINOR | **Accepted / fixed.** Single detector (one threshold); both histogram ends clamped; explicit `line_h` guard; sweep now computes ordered coverage. |

## Net

The gate's **direction holds** (geometry viable, not S2.1-alt) and is *better supported* after the fix:
on the two-column body pages geometry is *for*, col-aware ordered **mean 0.92 / 87% pass@0.85** (n=30).
But the gate's earlier **confidence** did not hold — the PRIMARY rating, one density claim, the
two-column *count*, and two supporting metrics were defective. Post-remediation the verdict is
**conditional-primary** with honest mean/pass-rate evidence, the density claim retracted, the detector
fixed, and the strata relabeled. The reading-order architecture was also clarified (audit + user review):
order comes from a column-correct text witness when one exists (geometry cross-checks), and from the
geometric detector + human-in-loop when none does — so the engine must not presume a prior witness.
