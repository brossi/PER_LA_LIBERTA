"""Build the total page-evidence ledger consumed by reconciliation."""

from __future__ import annotations

from engine.config.models import ResolvedConfig
from engine.lang.base import LanguagePlugin
from engine.paths import BookWorkspace
from engine.structure.page_evidence import DEFAULT_REVIEW_BOUND, build_page_evidence
from engine.structure.page_evidence_presence_shadow import (
    observe_page_evidence_presence,
)


def run(
    *,
    workspace: BookWorkspace,
    cfg: ResolvedConfig,
    lang: LanguagePlugin,
    witness_id: str = "copy1",
    model: str = "flash",
    max_review_pages: int = DEFAULT_REVIEW_BOUND,
    refresh_shadow: bool = False,
    presence_observer=observe_page_evidence_presence,
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
    try:
        presence = presence_observer(
            workspace=workspace,
            ledger_path=workspace.resolve(
                "data", "page_evidence", witness_id, "ledger.json"
            ),
            witness_id=witness_id,
            refresh=refresh_shadow,
        )
    except Exception as exc:
        # The consumer is deliberately shadow-only. Its inability to observe a valid, already
        # written ledger cannot revise or revoke the engine-owned admission decision.
        presence = {
            "status": "unavailable",
            "failure_type": type(exc).__name__,
            "failure_message": str(exc) or type(exc).__name__,
        }
    print(
        f"  page evidence: {summary['pages']} pages, "
        f"{summary['review_pages']} require review; {summary['status']}"
    )
    print(f"  presence shadow: {presence['status']}")
    return {**summary, "presence_shadow": presence}
