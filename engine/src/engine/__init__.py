"""book-engine — a book/language-agnostic OCR → reconcile → clean → translate →
typeset framework.

Forked (deliberately, one-way) from the source translation pipeline at the parent
repo root. Every book/language/scan-specific constant leaves the core and lives in
a per-book manifest + shared profiles; the core reads ``cfg`` (ResolvedConfig) and
the active ``LanguagePlugin`` only. See ENGINE_FRAMEWORK_PLAN.md for the staged
build (M0–M7). Steps are ported milestone by milestone; an unported step module is a
scaffold stub whose ``run`` raises ``NotImplementedError`` naming the milestone that
ports it.
"""

from __future__ import annotations

__version__ = "0.0.2"

# The ordered build subset the framework reproduces (through typeset). `refine` is
# manual-only and never part of `--step all`; `companion` is intentionally excluded
# as situational hand-authored content (see plan "Decisions").
STEPS = (
    "download",
    "ocr",
    "reconcile",
    "triage",
    "cleanup",
    "adjudicate",
    "validate",
    "translate",
    "multi_translate",
    "refine",
    "typeset",
)

# Explicitly selectable observation/preflight stages. They are not part of ``--step all`` because
# their providers are optional and they do not produce the canonical build subset above.
OPTIONAL_STEPS = ("layout_shadow", "ingest_gate")

__all__ = ["__version__", "OPTIONAL_STEPS", "STEPS"]
