# Layout assessment shadow boundary

The engine consumes `book-layout-sidecar` only through its versioned `core` provider API. The
dependency is optional and pinned to `v0.1.1`; install it with:

```sh
uv sync --extra assessment
```

`engine.structure.layout_assessment_shadow.observe_page_geometry` is the engine-owned boundary.
It accepts an already validated `PageGeometry`, translates it to the provider's typed OCR-box
evidence, validates the response, and stores the exact request and bundle under:

```text
books/<id>/work/data/layout_assessment/<witness>/page_NNNN.json
```

The only supported modes are:

- `off`: returns before importing the optional package, constructing a provider, or writing a file.
- `shadow`: records evidence but cannot change geometry, routing, worklists, structure, or output.

The first slice assesses OCR text-likeness and conservative near-blank/OCR-relevance evidence. A
column assessment is included only when the caller supplies an already-ratified
`ColumnAssessmentPolicy`. No thresholds are inferred. Density, geometry-match, marginal-text, and
bleed-through mappings remain unavailable until the engine can supply their separately hashed
evidence families.

Every reusable observation is re-parsed and revalidated against a freshly rebuilt request and the
current provider identity. Source hash, normalized OCR boxes, adapter version, provider version,
module configuration, or evidence-binding drift invalidates reuse. Provider/import/response
failures are persisted as `unavailable`; they are never interpreted as a blank-page finding.

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
)
```

The caller owns scan hashing once per run and supplies the same bare lowercase SHA-256 for every
page. The adapter never reads a manifest, opens the scan, shells out to the sidecar CLI, or imports
`book_layout_sidecar.adapters`/`book_layout_sidecar.lab`.
