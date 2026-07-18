"""OCR wire-protocol constants — emitted by ``ocr``, consumed by ``reconcile`` and the OCR
prompt template. Single-sourced so emitter and parser cannot silently drift (plan F6).

Two protocols cross a producer↔consumer boundary here:

  - **The ``⟨PAGE:N⟩`` page marker** — ``ocr`` emits it once per page; ``reconcile`` strips it and
    reads the page number back. A ``.format`` emit-string and a compiled parse-regex are not one
    interchangeable object, so the marker grammar is written *once* (``PAGE_MARKER_TEMPLATE``) and
    the regex is *derived* from it — there is no second literal to forget to update. A property
    test pins the round-trip (``PAGE_MARKER_RE`` matches what ``PAGE_MARKER_TEMPLATE.format`` emits).
  - **The ``[BLANK]`` / ``[OCR_ERROR]`` page sentinels** — ``[BLANK]`` crosses the template↔stitcher
    boundary: the OCR prompt template instructs the model to emit it (rendered from
    ``SENTINEL_BLANK``) and ``ocr._stitch_pages`` matches it (the same constant), so a change in one
    place cannot diverge from the other. ``[OCR_ERROR`` is emitted in code on a transcription
    failure and prefix-matched by the stitcher.

These are internal tag protocols, not book/language facts, so they are code defaults (not config)
— matching ``reconcile``'s original local ``PAGE_MARKER_RE`` and the framework plan's "internal tag
protocols stay code defaults".
"""

from __future__ import annotations

import re

#: The page-marker grammar — the single literal both the emit-format and the parse-regex derive
#: from. ``ocr`` calls ``PAGE_MARKER_TEMPLATE.format(n)``; ``reconcile`` uses ``PAGE_MARKER_RE``.
PAGE_MARKER_TEMPLATE = "⟨PAGE:{}⟩"  # ⟨PAGE:N⟩

#: Derived from ``PAGE_MARKER_TEMPLATE`` so the literal exists in exactly one place: escape the
#: template, then swap the (escaped) ``{}`` placeholder for a captured integer group.
PAGE_MARKER_RE = re.compile(
    re.escape(PAGE_MARKER_TEMPLATE).replace(re.escape("{}"), r"(\d+)")
)

#: Per-page sentinel the OCR model is instructed to return for a blank/decorative page. Rendered
#: into the prompt template as ``{{ blank_sentinel }}`` and matched verbatim by ``_stitch_pages``.
SENTINEL_BLANK = "[BLANK]"

#: Prefix of the sentinel ``ocr`` writes in code when a page's transcription fails after retries
#: (``[OCR_ERROR: <exc>]``); the stitcher prefix-matches it to drop the page body.
SENTINEL_OCR_ERROR_PREFIX = "[OCR_ERROR"
