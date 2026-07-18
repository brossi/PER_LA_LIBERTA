from __future__ import annotations

import hashlib

import pytest

from engine.paths import BookWorkspace
from engine.structure import page_evidence_presence_shadow as presence
from engine.util.jsonio import atomic_write_json, read_json

pytest.importorskip("book_layout_sidecar")


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _ledger(tmp_path):
    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()
    ledger_path = ws.resolve("data", "page_evidence", "copy1", "ledger.json")
    ledger_path.parent.mkdir(parents=True)
    pairs = ((12, True), (0, False), (0, True), (12, False))
    atomic_write_json(
        ledger_path,
        {
            "schema_version": 1,
            "stale_class": "page-evidence-ledger",
            "book_id": "synthetic",
            "witness_id": "copy1",
            "ocr_model": "flash",
            "source": {
                "path": "scans/synthetic.pdf",
                "sha256": "a" * 64,
                "pages": 4,
            },
            "pages": [
                {
                    "page": page,
                    "signals": {
                        "baseline_geometry_boxes": boxes,
                        "effective_geometry_boxes": boxes,
                        "ocr_has_text": has_text,
                        "ocr_fallback": False,
                        "retry_status": "not_applicable",
                        "retry_selected_path": "geometry_baseline",
                    },
                }
                for page, (boxes, has_text) in enumerate(pairs, start=1)
            ],
        },
    )
    return ws, ledger_path


def test_presence_shadow_consumes_request_v4_without_routing_policy(tmp_path):
    ws, ledger_path = _ledger(tmp_path)

    result = presence.observe_page_evidence_presence(
        workspace=ws,
        ledger_path=ledger_path,
        witness_id="copy1",
    )

    assert result["status"] == "complete"
    assert result["counts"] == {"supported": 2, "unsupported": 2}
    assert result["contradiction_pages"] == [3, 4]
    assert result["unavailable_pages"] == []
    assert result["ledger"] == {
        "ref": "page-evidence:synthetic/copy1",
        "path": "data/page_evidence/copy1/ledger.json",
        "sha256": _sha(ledger_path),
    }

    page = read_json(
        presence.page_observation_path(ws, witness_id="copy1", page=3)
    )
    assert page["request"]["request_version"] == 4
    assert page["request"]["input_artifacts"] == [
        {
            "kind": "page_evidence_ledger",
            "ref": "page-evidence:synthetic/copy1",
            "sha256": _sha(ledger_path),
            "version": "page-evidence-v1",
        }
    ]
    feature = page["request"]["evidence"]["geometry_ocr_text_presence"]["payload"]
    assert feature["geometry_source_selector"] == (
        "$.pages[2].signals.effective_geometry_boxes"
    )
    assert feature["ocr_text_source_selector"] == "$.pages[2].signals.ocr_has_text"
    assert page["bundle"]["results"][0]["assessment"] == "unsupported"


def test_presence_shadow_revalidates_cache_and_provider_identity(tmp_path):
    from book_layout_sidecar.core import CoreAssessmentProvider, ProviderIdentity

    ws, ledger_path = _ledger(tmp_path)
    previous = CoreAssessmentProvider(
        identity=ProviderIdentity("book_layout_sidecar", "0.1.2")
    )
    presence.observe_page_evidence_presence(
        workspace=ws,
        ledger_path=ledger_path,
        witness_id="copy1",
        provider_factory=lambda: previous,
        refresh=True,
    )
    current = CoreAssessmentProvider()

    class CountingProvider:
        identity = current.identity

        def __init__(self):
            self.calls = 0

        def assess(self, request):
            self.calls += 1
            return current.assess(request)

    provider = CountingProvider()
    result = presence.observe_page_evidence_presence(
        workspace=ws,
        ledger_path=ledger_path,
        witness_id="copy1",
        provider_factory=lambda: provider,
    )

    assert provider.calls == 4
    assert result["cached_pages"] == 0
    assert result["provider"]["provider_version"] == "0.1.3"

    class ExplodingProvider:
        identity = current.identity

        def assess(self, request):
            raise AssertionError("fully revalidated cache should avoid provider calls")

    cached = presence.observe_page_evidence_presence(
        workspace=ws,
        ledger_path=ledger_path,
        witness_id="copy1",
        provider_factory=ExplodingProvider,
    )
    assert cached["cached_pages"] == 4
    assert cached["counts"] == result["counts"]


def test_presence_shadow_records_provider_failure_as_unavailable(tmp_path):
    from book_layout_sidecar.core import CoreAssessmentProvider

    ws, ledger_path = _ledger(tmp_path)
    current = CoreAssessmentProvider()

    class FailingProvider:
        identity = current.identity

        def assess(self, request):
            raise RuntimeError("provider unavailable")

    result = presence.observe_page_evidence_presence(
        workspace=ws,
        ledger_path=ledger_path,
        witness_id="copy1",
        provider_factory=FailingProvider,
    )

    assert result["status"] == "complete_with_unavailable"
    assert result["counts"] == {"unavailable": 4}
    assert result["unavailable_pages"] == [1, 2, 3, 4]
    page = read_json(
        presence.page_observation_path(ws, witness_id="copy1", page=1)
    )
    assert page["status"] == "unavailable"
    assert page["failure"]["type"] == "RuntimeError"
