"""download step — fetch the OCR text witnesses from Internet Archive (djvu text).

Faithful port of the top-level ``download.py``: idempotent skip-if-exists; one file per source
written into ``ws.data`` as ``{role}_raw.txt`` — the names ``reconcile`` reads. The two
book-specific URLs leave the code and come from ``manifest.sources[]``; the IA djvu-text URL
convention is the code-default fallback for a source that declares only an ``ia_item_id``. The
network call is the one injectable seam (D1/BR-009), defaulting to ``requests``; tests inject
canned bytes so the property/separability tiers run offline.

``copy3`` is *produced by ``ocr``*, not downloaded — the manifest's ``sources[]`` lists only the
djvu-text witnesses, so the step iterates exactly those.
"""

from __future__ import annotations

from typing import Protocol

from ..config.models import ResolvedConfig, Source
from ..errors import AcquisitionError
from ..lang.base import LanguagePlugin
from ..paths import BookWorkspace
from ..util.jsonio import atomic_write_text


class Fetcher(Protocol):
    """Fetch a URL's text. The seam that makes ``download`` testable offline."""

    def fetch(self, url: str) -> str: ...


class RequestsFetcher:
    """Default ``Fetcher`` — ``requests.get`` with the live 60s timeout, raising on HTTP error."""

    def fetch(self, url: str) -> str:
        import requests

        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        return resp.text


def source_url(source: Source) -> str:
    """The source's explicit ``manifest`` URL if present, else the IA djvu-text convention
    (``{id}/{id}_djvu.txt``) derived from its ``ia_item_id``. The explicit URL always wins."""
    if source.url:
        return source.url
    return (
        f"https://archive.org/download/{source.ia_item_id}/"
        f"{source.ia_item_id}_djvu.txt"
    )


def target_name(source: Source) -> str:
    """Output filename for a source, keyed off its role: ``copy1`` → ``copy1_raw.txt``."""
    return f"{source.role}_raw.txt"


def run(
    *,
    workspace: BookWorkspace,
    cfg: ResolvedConfig,
    lang: LanguagePlugin,
    fetcher: Fetcher | None = None,
) -> dict:
    """Download each ``manifest.sources[]`` witness into ``ws.data`` (idempotent).

    Returns ``{role: {"path", "chars", "skipped"}}``. A network/HTTP failure becomes a clean
    ``AcquisitionError`` (CLI exit 4), not a bare ``requests`` traceback. ``lang`` is unused —
    ``download`` is language-neutral — but kept for the uniform step signature.
    """
    ws = workspace
    fetcher = fetcher or RequestsFetcher()
    ws.ensure()

    summary: dict[str, dict] = {}
    for source in cfg.manifest.sources:
        target = ws.resolve("data", target_name(source))
        if target.exists():
            print(f"  {source.label}: already downloaded ({target.stat().st_size:,} bytes)")
            summary[source.role] = {"path": str(target), "chars": None, "skipped": True}
            continue

        url = source_url(source)
        print(f"  {source.label}: downloading {url}")
        try:
            text = fetcher.fetch(url)
        except AcquisitionError:
            raise
        except Exception as exc:  # any backend failure → one typed engine error
            raise AcquisitionError(
                f"failed to fetch {source.role} ({source.label}) from {url}: {exc}"
            ) from exc

        atomic_write_text(target, text)
        print(f"  {source.label}: saved ({len(text):,} chars)")
        summary[source.role] = {"path": str(target), "chars": len(text), "skipped": False}

    return summary
