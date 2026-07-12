# Ninnoli specimen run

Baseline: `3d37189`

## Fixed inputs

- Primary production scan: 1884 third edition, 110 pages, SHA-256
  `a8ab798c9d9aed9f07626cff6f2795d6968f754e3458bcfcf160146d3e4ac8ad`.
- Primary IA OCR: same 1884 scan.
- Secondary IA OCR: 1883 edition; diagnostic cross-edition witness only.
- Gutenberg reference: sealed until production output is complete and hashed.

The edition preflight found the same five ordered stories in both IA witnesses. Per-story
normalized text similarity was `0.9613`, `0.8922`, `0.9076`, `0.9073`, and `0.9867`; normalized
length ratios were `0.9839`, `0.9324`, `0.8916`, `0.8840`, and `0.9971`. This is sufficient for a
diagnostic adversarial reconciliation but not for treating every disagreement as ordinary OCR
error or certifying the 1883 witness as production-equivalent.

## Execution

1. Verify `resources.sha256`.
2. Split both IA witnesses through manifest-declared ordered flat sections. Require five nonempty
   stories in manifest order; front contents, repeated title heads, and back matter are furniture.
3. Run all 110 primary-scan pages through PyMuPDF/Tesseract with explicit `ita`, 300 DPI. Persist
   source-bound page geometry checkpoints and invoke `book-layout-sidecar` `v0.1.0` in shadow mode.
   No density or column policy is supplied.
4. Acquire/admit the two IA witnesses into the workspace.
5. OCR the primary scan with the configured Gemini flash role. Require every page complete before
   canonical publication.
6. Reconcile Copy 1 with same-scan Copy 3. Keep the 1883 edition as non-voting comparison evidence.
   Inspect disagreement volume, then triage serially.
7. Run deterministic cleanup and validation. Add LLM cleanup only if measured residuals justify it.
8. Continue into translation/typesetting until the next real blocker; repair, regress, and resume.
9. Hash production outputs before unsealing Gutenberg for evaluation.

Commands run from `engine/`:

```sh
shasum -a 256 -c books/ninnoli/resources.sha256
engine --book ninnoli --step layout_shadow \
  --tesseract-language ita --dpi 300 --witness-id copy1
engine --book ninnoli --step download
engine --book ninnoli --step ocr --model flash --workers 4 \
  --fallback-tesseract-language ita
engine --book ninnoli --step reconcile
engine --book ninnoli --step triage
engine --book ninnoli --step cleanup
engine --book ninnoli --step validate
engine --book ninnoli --step translate --workers 2

# In another terminal: persisted lifecycle + per-step checkpoint counts
engine --book ninnoli --status --watch 2
```

Provider credentials are loaded from the ignored root `.env` only for the relevant command; no
generic `--api-key` is used across providers.

The completed run, blind-output hashes, blockers, and post-seal evaluation are recorded in
`SPIKE_REPORT.md`. The accepted generated Markdown artifacts remain under the ignored `work/` tree.
