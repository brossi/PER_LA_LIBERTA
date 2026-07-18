# Divergence Ledger

> Deliberate **behavioral** changes from PLL — never silent. Append-only. See
> `engine/docs/port_discipline.md` §2, §5.
>
> **No entries yet.** The ledger opens at the first behavioral divergence; M2–M4a porting closed
> with none. The deliberate forks that did arise (e.g. adjudicate's result-envelope, BR-005) are
> orchestration/contract decisions recorded in the branch register, not ground-truth-licensed
> algorithm changes — the only kind this ledger admits. The M4a ocr render-hardening (page-count
> failure → `BackendError`; per-page render failure → `[OCR_ERROR]` sentinel) was likewise
> evaluated for an entry and ruled **out** (2026-06-23): it is error-handling on malformed input
> with no golden to move, not a ground-truth-licensed algorithm change — so the proposed "DL-001"
> is declined. Until the first entry this file pins the format only.
>
> **The anti-cheat rule (§5).** A change to a `*_expected` golden that alters expected **values**
> through a ground-truth-licensed behavioral change must cite a `DL` entry here; a re-freeze of
> `books/<id>/inputs/` from the live tree (output changes, behavior does not) cites an `RF` entry.
> A pure report-envelope or format regeneration that leaves every classification/decision
> unchanged — verified **zero** behavioral diffs — is neither: it needs no entry, only a note in
> its own commit. (Narrowed 2026-06-23, post-M4a audit: the literal "any change to a golden"
> reading was already out of step with honest practice — commit `93b5aa7` regenerated the validate
> report envelope, adding `"issues": []`, with zero classification diffs and no entry. That is
> correct under this narrower rule, not a violation.)

---

## Entry format

```
## DL-NNN — <short title>  (<date>, <step>)
- PLL did:        …
- We now do:      …
- Why better:     … + the ground truth that licenses it (scans / period dictionaries / review
                  findings) — never "feels cleaner" (port_discipline.md §2)
- Property test:  tests/…::test_…
- Golden:         <fixture>  (was … → now …)
```

## Input-refresh entry format

```
## RF-NNN — refreshed <inputs>  (<date>)
- Source:   live commit <sha>
- Re-froze: books/<id>/inputs/<files>
- Goldens regenerated:  <fixtures>   (input refresh, not a behavioral divergence)
```
