# Layout assessment shadow boundary

The engine consumes `book-layout-sidecar` only through its versioned `core` provider API. The
dependency is optional and pinned to `v0.1.5`; install it with:

```sh
uv sync --extra assessment
```

`engine.structure.layout_assessment_shadow.observe_page_geometry` is the engine-owned boundary.
It accepts an already validated `PageGeometry` plus optional engine-owned raster/density records,
translates them to the provider's typed evidence, validates the response, and stores the exact
request and bundle under:

```text
books/<id>/work/data/layout_assessment/<witness>/page_NNNN.json
```

The only supported modes are:

- `off`: returns before importing the optional package, constructing a provider, or writing a file.
- `shadow`: records evidence but cannot change geometry, routing, worklists, structure, or output.

The scan step renders every page at the explicitly requested geometry DPI and checkpoints both the
PNG and a metadata record under `work/data/raster/shadow/<witness>/`. The record binds the source
PDF hash, page, DPI, raster SHA-256, dimensions, producer, and raw ink fraction. A changed source,
DPI, producer, record, or PNG hash invalidates reuse.

Raw density measurement does not imply a content decision. When a book has no
`manifest.segmentation.density_bands`, the engine emits a `DensityFeature` with `label=abstain`,
`confidence=0`, and `hint=density_policy_absent`. This exposes the measured ink fraction to the
provider while supplying no engine threshold. When the manifest carries calibrated bands, the
versioned engine classifier supplies the label and confidence; its full parameters and fingerprint
are persisted. The density producer also embeds the source-raster SHA-256, so equal-looking feature
values cannot detach from the pixels that produced them.

A column assessment is included only when the caller supplies an already-ratified
`ColumnAssessmentPolicy`. The v5 provider can independently recompute spatial support between two
exact, normalized box sets, but this boundary does not infer or synthesize that second evidence
family. Its spatial capability therefore remains absent from ordinary observations until a caller
supplies both separately hashed box sets and their detector lineage. Marginal-text and
bleed-through mappings likewise remain unavailable until the engine can supply their separately
hashed evidence families.

Every reusable observation is re-parsed and revalidated against a freshly rebuilt request and the
current provider identity. Source hash, normalized OCR boxes, adapter version, provider version,
module configuration, or evidence-binding drift invalidates reuse. Provider/import/response
failures are persisted as `unavailable`; they are never interpreted as a blank-page finding.

After `ingest_gate` writes the total page-evidence ledger, a second observation-only consumer asks
the v5 provider for `effective_geometry_ocr_text_presence_is_consistent` on every page. This is the
first point where finalized effective geometry and canonical OCR-text presence coexist. The engine
captures the ledger once, derives a minimal factual page-evidence projection containing only the
source identity and six presence signals, and binds both named roles to that projection with
distinct JSON selectors. Review bounds, verdicts, dispositions, and other policy fields do not
invalidate an unchanged presence request. It stores the projection, exact requests, and bundles
under:

```text
books/<id>/work/data/layout_assessment/<witness>/page_evidence_presence/page_NNNN.json
books/<id>/work/data/layout_assessment/<witness>/page_evidence_presence_projection.json
books/<id>/work/data/layout_assessment/<witness>/page_evidence_presence_report.json
```

The report binds the current full ledger and projection and manifests every page observation by
path and SHA-256. Loading it revalidates the projection against the ledger, every request and
bundle, the provider identity, page totals, contradiction/unavailable sets, and aggregate counts.
A new run first replaces any older success with an unavailable sentinel; pre-provider failures and
review-bound admission failures therefore cannot leave an apparently current older report.

The result is factual shadow evidence only: both axes present or absent is `supported`; one-axis
presence is `unsupported`; missing primitives are `not_applicable`. It cannot change a ledger
disposition, review worklist, or reconciliation admission. A provider/import/translation failure is
reported as unavailable after the engine-owned gate artifacts have already been written.

For pages with at most two PDF-geometry words, the engine also records a bounded geometry retry
under `work/data/geometry/retry/<witness>/`. It first runs Tesseract on the exact persisted raster,
because that surface is not interchangeable with the PDF OCR backend. If the released sidecar gate
finds zero OCR boxes with unresolved visual activity, the engine runs one `adaptive_bw` pass. The
engine selects either result only when sidecar text-likeness reports `trusted_text`; a larger box
count alone remains `unresolved`. Decisively near-blank pages are recorded without creating a
transformed raster. Reuse binds the source, raster and baseline geometry hashes, sidecar version,
Tesseract executable hash, language, PSM, transform, transformed raster hash, and normalized OCR
hashes. The run report distinguishes candidate, attempted, selected, and unresolved pages.

Example after a geometry backend has produced a page:

```python
from engine.structure.layout_assessment_shadow import MODE_SHADOW, observe_page_geometry

observation = observe_page_geometry(
    workspace=workspace,
    mode=MODE_SHADOW,
    witness_id="tesseract",
    source_ref="scan:ninnoli/ninnolir00roveuoft.pdf",
    source_sha256=scan_sha256,
    page_geometry=page_geometry,
    geometry_engine_id=geometry_backend.engine_id,
    raster_evidence=raster_evidence,
    density_evidence=density_evidence,
)
```

The first-class `layout_shadow` step owns scan hashing, raster rendering, calibrated classification,
and checkpointing. A direct adapter caller must supply those records explicitly. The adapter never
reads a manifest, opens the scan, shells out to the sidecar CLI, or imports
`book_layout_sidecar.adapters`/`book_layout_sidecar.lab`.

The assessment-enabled CI job fetches the private pinned dependency with the
`BOOK_LAYOUT_SIDECAR_DEPLOY_KEY` Actions secret. Its public half is a read-only deploy key on the
sidecar repository; the workflow pins GitHub's published Ed25519 host key and grants no sidecar
write access.
