# Layout assessment shadow boundary

The engine consumes `book-layout-sidecar` only through its versioned `core` provider API. The
dependency is optional and pinned to `v0.1.2`; install it with:

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
`ColumnAssessmentPolicy`. Geometry-match, marginal-text, and bleed-through mappings remain
unavailable until the engine can supply their separately hashed evidence families.

Every reusable observation is re-parsed and revalidated against a freshly rebuilt request and the
current provider identity. Source hash, normalized OCR boxes, adapter version, provider version,
module configuration, or evidence-binding drift invalidates reuse. Provider/import/response
failures are persisted as `unavailable`; they are never interpreted as a blank-page finding.

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
