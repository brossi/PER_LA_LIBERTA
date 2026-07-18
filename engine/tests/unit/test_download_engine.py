"""download property/contract tier (non-deterministic step → no equivalence golden, F1).

Network is the one seam, injected; these pin the language-neutral mechanics: byte-faithful
writes, the IA djvu-text URL-derivation fallback (the non-default config axis a sibling book
without explicit URLs would hit), idempotent skip-if-exists, and the typed failure mode.
"""

from __future__ import annotations

import pytest

from engine.config.loader import load_book
from engine.config.models import Source
from engine.errors import AcquisitionError
from engine.lang.registry import get_language_plugin
from engine.paths import BookWorkspace
from engine.steps import download


def _cfg_lang():
    cfg = load_book("synthetic")
    return cfg, get_language_plugin(cfg.language_id)


def test_url_derivation_fallback_matches_convention():
    # copy1 declares an explicit URL (it wins); copy2 declares only an ia_item_id → the IA
    # djvu-text convention is derived. The synthetic manifest is built to exercise both.
    cfg, _ = _cfg_lang()
    by_role = {s.role: s for s in cfg.manifest.sources}

    assert download.source_url(by_role["copy1"]) == by_role["copy1"].url
    assert (
        download.source_url(by_role["copy2"])
        == "https://archive.org/download/synthetic_copy2/synthetic_copy2_djvu.txt"
    )
    # The derivation equals the explicit URL for a source that *omits* it — i.e. an explicit URL
    # written out by hand would be redundant with the convention.
    derived_equiv = Source(role="copy2", label="x", ia_item_id="synthetic_copy2", url=None)
    explicit_equiv = Source(
        role="copy2", label="x", ia_item_id="synthetic_copy2",
        url="https://archive.org/download/synthetic_copy2/synthetic_copy2_djvu.txt",
    )
    assert download.source_url(derived_equiv) == download.source_url(explicit_equiv)


def test_target_name_keyed_off_role():
    assert download.target_name(Source("copy1", "l", "i")) == "copy1_raw.txt"
    assert download.target_name(Source("copy2", "l", "i")) == "copy2_raw.txt"


def test_writes_exactly_the_fetched_bytes(tmp_path, acq):
    cfg, lang = _cfg_lang()
    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()

    # Non-empty guard: the byte-faithfulness assertions live inside the `for s in sources` loop
    # below. An empty manifest would run it zero times — green while verifying nothing. Fail loud.
    assert cfg.manifest.sources, "synthetic manifest must declare sources"
    canned = {
        download.source_url(s): f"CANNED-{s.role}-µ-à\n"  # non-ASCII to prove utf-8 round-trip
        for s in cfg.manifest.sources
    }
    summary = download.run(workspace=ws, cfg=cfg, lang=lang, fetcher=acq.Fetcher(canned))

    for s in cfg.manifest.sources:
        written = (ws.data / download.target_name(s)).read_text(encoding="utf-8")
        assert written == canned[download.source_url(s)]
        assert summary[s.role]["skipped"] is False
        assert summary[s.role]["chars"] == len(written)


def test_idempotent_skip_if_exists(tmp_path, acq):
    cfg, lang = _cfg_lang()
    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()
    assert cfg.manifest.sources, "synthetic manifest must declare sources"  # else the loop is vacuous
    canned = {download.source_url(s): f"v1-{s.role}" for s in cfg.manifest.sources}
    download.run(workspace=ws, cfg=cfg, lang=lang, fetcher=acq.Fetcher(canned))

    # A second run with a fetcher that would raise if called proves skip-if-exists never refetches.
    class _Boom:
        def fetch(self, url):
            raise AssertionError(f"refetched {url} despite an existing file")

    summary = download.run(workspace=ws, cfg=cfg, lang=lang, fetcher=_Boom())
    for s in cfg.manifest.sources:
        assert summary[s.role]["skipped"] is True
        assert (ws.data / download.target_name(s)).read_text(encoding="utf-8") == f"v1-{s.role}"


def test_network_failure_becomes_typed_acquisition_error(tmp_path):
    cfg, lang = _cfg_lang()
    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()

    class _Failing:
        def fetch(self, url):
            raise ConnectionError("boom")

    with pytest.raises(AcquisitionError) as ei:
        download.run(workspace=ws, cfg=cfg, lang=lang, fetcher=_Failing())
    assert ei.value.exit_code == 4
    assert "boom" in str(ei.value)
