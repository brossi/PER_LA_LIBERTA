"""Build the total page-evidence ledger consumed by reconciliation."""

from __future__ import annotations

from engine.config.models import ResolvedConfig
from engine.errors import ReconciliationAdmissionError
from engine.lang.base import LanguagePlugin
from engine.paths import BookWorkspace
from engine.structure.page_evidence import DEFAULT_REVIEW_BOUND, build_page_evidence
from engine.structure.page_evidence_presence_shadow import (
    begin_presence_observation,
    observe_page_evidence_presence,
    record_presence_unavailable,
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
    ledger_path = workspace.resolve("data", "page_evidence", witness_id, "ledger.json")
    begin_presence_observation(
        workspace=workspace,
        book_id=cfg.book_id,
        witness_id=witness_id,
    )
    try:
        summary = build_page_evidence(
            workspace=workspace,
            cfg=cfg,
            witness_id=witness_id,
            model=model,
            max_review_pages=max_review_pages,
            enforce_review_bound=False,
        )
    except Exception as exc:
        record_presence_unavailable(
            workspace=workspace,
            book_id=cfg.book_id,
            witness_id=witness_id,
            ledger_path=None,
            failure=exc,
        )
        raise
    try:
        presence = presence_observer(
            workspace=workspace,
            ledger_path=ledger_path,
            book_id=cfg.book_id,
            witness_id=witness_id,
            refresh=refresh_shadow,
        )
        if not isinstance(presence, dict) or presence.get("status") not in {
            "complete",
            "complete_with_unavailable",
            "unavailable",
        }:
            raise TypeError("presence observer returned an invalid summary")
    except Exception as exc:
        # The consumer is deliberately shadow-only. Its inability to observe a valid, already
        # written ledger cannot revise or revoke the engine-owned admission decision.
        presence = record_presence_unavailable(
            workspace=workspace,
            book_id=cfg.book_id,
            witness_id=witness_id,
            ledger_path=ledger_path,
            failure=exc,
        )
    print(
        f"  page evidence: {summary['pages']} pages, "
        f"{summary['review_pages']} require review; {summary['status']}"
    )
    print(f"  presence shadow: {presence['status']}")
    if summary["review_pages"] > max_review_pages:
        raise ReconciliationAdmissionError(
            f"page-evidence review volume {summary['review_pages']} exceeds bound "
            f"{max_review_pages}; see {summary['review']}"
        )
    return {**summary, "presence_shadow": presence}
