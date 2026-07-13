"""Build the total page-evidence ledger consumed by reconciliation."""

from __future__ import annotations

from engine.config.models import ResolvedConfig
from engine.lang.base import LanguagePlugin
from engine.paths import BookWorkspace
from engine.structure.page_evidence import DEFAULT_REVIEW_BOUND, build_page_evidence


def run(
    *,
    workspace: BookWorkspace,
    cfg: ResolvedConfig,
    lang: LanguagePlugin,
    witness_id: str = "copy1",
    model: str = "flash",
    max_review_pages: int = DEFAULT_REVIEW_BOUND,
) -> dict:
    """Derive dispositions without changing OCR text or canonical output."""
    del lang
    summary = build_page_evidence(
        workspace=workspace,
        cfg=cfg,
        witness_id=witness_id,
        model=model,
        max_review_pages=max_review_pages,
    )
    print(
        f"  page evidence: {summary['pages']} pages, "
        f"{summary['review_pages']} require review; {summary['status']}"
    )
    return summary
