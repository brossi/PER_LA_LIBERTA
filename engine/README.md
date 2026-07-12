# book-engine

A book/language-agnostic OCR → reconcile → clean → translate → typeset framework,
**forked one-way** from the *Per la Libertà!* pipeline at the parent-repo root.

The parent pipeline is built for one book (1913 Italian); dozens of constants encode
facts about that single book/language/scan. This package lifts every such constant out
of the core into a **per-book manifest** + **shared profiles**, so the same machinery
can build future books in other languages without touching — or risking — the live
*Per la Libertà!* edition.

> **Status:** the single-model path through translation is executable; multi-translation,
> refinement, and typesetting remain scaffolded. See `../ENGINE_FRAMEWORK_PLAN.md` for the staged
> build and `books/ninnoli/SPIKE_REPORT.md` for the first full specimen result.

## Governance

This is a **deliberate forward fork, not a maintained mirror.** The live parent tree
remains the source of truth until *Per la Libertà!* is frozen. Fixes in the live tree
are **not** backported here unless they correct generic-engine behavior. There is no
bidirectional sync; the only sanctioned cross-flow is refreshing the frozen golden
fixtures under `books/per_la_liberta/inputs/` from live (read-only).

## Layout

```
src/engine/        importable package (true src layout) — names no book; reads cfg + LanguagePlugin
  cli.py           orchestrator (replaces pipeline.py)
  paths.py         BookWorkspace — all artifacts under books/<id>/work/ only
  config/          BookManifest / LanguageProfile / SourceNoiseProfile / TypefaceProfile + JSON-schema validation
  prompts/         Jinja2 StrictUndefined templating
  lang/            LanguagePlugin ABC + Italian impl (ordinals, headings, ChapterIdentity)
  steps/           the ported pipeline steps
  dictionaries/    chunked period-dict loader + >=2-of-N membership oracle (reusable)
  review/          native-resolution scan re-read layer (reusable review primitive)
  util/            generic helpers ported from utils.py, split by concern
  contracts/       versioned sidecar schemas + id/path-shape assertions
profiles/          SHARED reusable knowledge (languages / typefaces / prompt templates)
books/<id>/        per-book config + fixtures + runtime workspace:
  manifest.json    profile refs, structure contract, edition metadata, scan facts
  inputs/          frozen upstream artifacts (clean text, reconciled, sidecars) — committed
                   test fixtures, refreshed read-only from live by tests/golden/_generate_*
  work/            runtime workspace, gitignored; {data,output,state} — steps write only here
assets/            dev-time symlinks to read-only heavy assets (real copies at extraction)
tests/{unit,golden,fixtures}
```

A step reads its inputs from, and writes its outputs to, `work/` — never `inputs/`. `inputs/`
holds *frozen* copies of what upstream steps would produce, used to drive golden tests; a step
run consumes whatever the *previous* step left in `work/`. So on a fresh checkout `work/` is
empty and running a step in isolation (e.g. `validate`) reports an error until its predecessors
have populated the workspace (the golden tests seed `work/` from `inputs/` to bridge this).

## Develop

```bash
cd engine
uv sync --extra it          # installs the engine + Italian spaCy model
uv run pytest tests/unit    # focused unit checks
uv run pytest tests/golden  # golden reproduction checks

# Optional observation-only scan geometry/layout preflight (not part of --step all)
uv sync --extra it --extra assessment
uv run engine --book ninnoli --step layout_shadow \
  --tesseract-language ita --dpi 300 --witness-id copy1

# One-shot or live pipeline progress for a book
uv run engine --book ninnoli --status
uv run engine --book ninnoli --status --watch 2
```

The framework **never writes outside `books/<id>/work/`**. `paths.BookWorkspace`
asserts workspace containment, and `tests/unit/test_isolation.py` hashes the protected
parent roots (`data/`, `output/`, `state/`, `docs/`, `static/`) before/after each step
and fails on any mutation. Read-only heavy assets are symlinked under `assets/` during
development; real copies land only at extraction (`git subtree split --prefix=engine`).
