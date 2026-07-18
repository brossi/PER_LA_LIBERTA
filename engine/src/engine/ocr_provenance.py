"""Closed vocabulary for OCR checkpoint provenance that changes selection semantics."""

from __future__ import annotations

from typing import Any


OCR_FALLBACK_PROVENANCE_KINDS = frozenset(
    {
        "provider_refusal_fallback",
        "explicit_recitation_fallback",
    }
)


def is_ocr_fallback_provenance(value: Any) -> bool:
    """Return true only for an explicitly selected OCR fallback record."""

    if not isinstance(value, dict):
        return False
    kind = value.get("kind")
    return isinstance(kind, str) and kind in OCR_FALLBACK_PROVENANCE_KINDS
