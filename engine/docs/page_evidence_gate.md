# Page-evidence reconciliation gate

`ingest_gate` runs after `layout_shadow` and OCR, before reconciliation. It writes a total,
ordered ledger for exactly the scan page range at:

```text
books/<id>/work/data/page_evidence/<witness>/ledger.json
```

Each page is `content`, `blank`, `non_text`, or `review_required`. Admission binds the source scan,
raster, baseline geometry, selected retry, provider assessment, OCR checkpoint, and OCR text hash.
A provider result may corroborate or contradict another signal, but no OCR backend is treated as a
truth oracle. In particular, OCR text with unresolved geometry and blank OCR with content-like
geometry both require review.

The companion `review.json` contains only unresolved pages, their exact review-specimen
fingerprint, raster reference, competing signal summary, and an OCR excerpt. The review fingerprint
binds the source raster and canonical OCR text: the page specimen that receives the human
content/blank/non-text ruling. Geometry overlays, transformed contrast aids, retry records, and
provider assessments remain separately hash-bound for admission, but detector or package churn
does not invalidate an unchanged human page judgment. The command fails loud if its review volume
exceeds `--max-review-pages`; it never relaxes disposition rules to fit the bound.

Human decisions live separately under:

```text
books/<id>/review/page_evidence/<witness>/verdicts.json
```

The document has this shape:

```json
{
  "schema_version": 1,
  "stale_class": "page-evidence-human-verdicts",
  "book_id": "ninnoli",
  "witness_id": "copy1",
  "verdicts": [
    {
      "page": 4,
      "disposition": "blank",
      "evidence_sha256": "<copy from review.json>",
      "reviewer": "<reviewer identity>",
      "decided_at": "2026-07-12T00:00:00-04:00",
      "note": "optional rationale"
    }
  ]
}
```

Only `content`, `blank`, and `non_text` are valid reviewed dispositions. The tracked `review/`
location is deliberately outside regenerable `work/`, matching the engine's other durable human
verdicts. Use the engine-owned verdict writer (directly or through a review frontend) rather than
editing generated ledger files. A verdict whose evidence fingerprint no longer matches is reported
as stale and returns to review automatically. Reconciliation checks the admitted ledger and every
live evidence hash before reading its voting witnesses; an absent, partial, unresolved, or drifted
ledger stops the step without creating canonical output.
