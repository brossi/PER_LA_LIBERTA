from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

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
            "review_bound": 2,
            "status": "review_required",
            "source": {
                "path": "scans/synthetic.pdf",
                "sha256": "a" * 64,
                "pages": 4,
            },
            "pages": [
                {
                    "page": page,
                    "disposition": "review_required",
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
        book_id="synthetic",
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
    projection = presence.projection_path(ws, witness_id="copy1")
    assert result["projection"] == {
        "ref": "page-evidence-presence:synthetic/copy1",
        "path": "data/layout_assessment/copy1/page_evidence_presence_projection.json",
        "sha256": _sha(projection),
    }
    assert result["projection"]["sha256"] != result["ledger"]["sha256"]

    page = read_json(
        presence.page_observation_path(ws, witness_id="copy1", page=3)
    )
    assert page["request"]["request_version"] == 4
    assert page["request"]["input_artifacts"] == [
        {
                "kind": "page_evidence_ledger",
                "ref": "page-evidence-presence:synthetic/copy1",
                "sha256": _sha(projection),
            "version": "page-evidence-v1",
        }
    ]
    feature = page["request"]["evidence"]["geometry_ocr_text_presence"]["payload"]
    assert feature["geometry_source_selector"] == (
        "$.pages[2].signals.effective_geometry_boxes"
    )
    assert feature["ocr_text_source_selector"] == "$.pages[2].signals.ocr_has_text"
    assert page["bundle"]["results"][0]["assessment"] == "unsupported"


def test_presence_shadow_binds_features_to_one_immutable_ledger_snapshot(
    tmp_path, monkeypatch
):
    ws, ledger_path = _ledger(tmp_path)
    original_sha = _sha(ledger_path)
    api = presence._load_sidecar_api()
    constructor = api["compute_effective_geometry_ocr_text_presence"]
    replaced = False

    def replace_live_ledger(**kwargs):
        nonlocal replaced
        if not replaced:
            replacement = read_json(ledger_path)
            replacement["pages"][0]["signals"]["baseline_geometry_boxes"] = 0
            replacement["pages"][0]["signals"]["effective_geometry_boxes"] = 0
            atomic_write_json(ledger_path, replacement)
            replaced = True
        return constructor(**kwargs)

    monkeypatch.setattr(
        presence,
        "_load_sidecar_api",
        lambda: {
            **api,
            "compute_effective_geometry_ocr_text_presence": replace_live_ledger,
        },
    )

    with pytest.raises(ValueError, match="ledger binding is stale"):
        presence.observe_page_evidence_presence(
            workspace=ws,
            ledger_path=ledger_path,
            book_id="synthetic",
            witness_id="copy1",
            refresh=True,
        )

    assert _sha(ledger_path) != original_sha
    report = read_json(presence.report_path(ws, witness_id="copy1"))
    assert report["status"] == "unavailable"
    assert report["ledger"]["sha256"] == _sha(ledger_path)
    page = read_json(
        presence.page_observation_path(ws, witness_id="copy1", page=1)
    )
    artifact = page["request"]["input_artifacts"][0]
    payload = page["request"]["evidence"]["geometry_ocr_text_presence"]["payload"]
    assert artifact["sha256"] == page["projection"]["sha256"]
    assert page["ledger"]["sha256"] == original_sha
    assert payload["effective_geometry_box_count"] == 12
    assert page["bundle"]["results"][0]["assessment"] == "supported"


def test_presence_shadow_revalidates_cache_and_provider_identity(tmp_path):
    from book_layout_sidecar.core import CoreAssessmentProvider, ProviderIdentity

    ws, ledger_path = _ledger(tmp_path)
    previous = CoreAssessmentProvider(
        identity=ProviderIdentity("book_layout_sidecar", "0.1.2")
    )
    presence.observe_page_evidence_presence(
        workspace=ws,
        ledger_path=ledger_path,
        book_id="synthetic",
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
        book_id="synthetic",
        witness_id="copy1",
        provider_factory=lambda: provider,
    )

    assert provider.calls == 4
    assert result["cached_pages"] == 0
    assert result["provider"]["provider_version"] == "0.1.4"

    class ExplodingProvider:
        identity = current.identity

        def assess(self, request):
            raise AssertionError("fully revalidated cache should avoid provider calls")

    cached = presence.observe_page_evidence_presence(
        workspace=ws,
        ledger_path=ledger_path,
        book_id="synthetic",
        witness_id="copy1",
        provider_factory=ExplodingProvider,
    )
    assert cached["cached_pages"] == 4
    assert cached["counts"] == result["counts"]


def test_presence_shadow_reuses_cache_after_policy_only_ledger_change(tmp_path):
    from book_layout_sidecar.core import CoreAssessmentProvider

    ws, ledger_path = _ledger(tmp_path)
    first = presence.observe_page_evidence_presence(
        workspace=ws,
        ledger_path=ledger_path,
        book_id="synthetic",
        witness_id="copy1",
    )
    first_projection_sha = first["projection"]["sha256"]
    ledger = read_json(ledger_path)
    ledger["review_bound"] = 3
    ledger["status"] = "admitted"
    for page in ledger["pages"]:
        page["disposition"] = "content"
    atomic_write_json(ledger_path, ledger)

    current = CoreAssessmentProvider()

    class CountingProvider:
        identity = current.identity

        def __init__(self):
            self.calls = 0

        def assess(self, request):
            self.calls += 1
            return current.assess(request)

    provider = CountingProvider()
    second = presence.observe_page_evidence_presence(
        workspace=ws,
        ledger_path=ledger_path,
        book_id="synthetic",
        witness_id="copy1",
        provider_factory=lambda: provider,
    )

    assert provider.calls == 0
    assert second["cached_pages"] == 4
    assert second["projection"]["sha256"] == first_projection_sha
    assert second["ledger"]["sha256"] == _sha(ledger_path)
    page = read_json(
        presence.page_observation_path(ws, witness_id="copy1", page=1)
    )
    assert page["ledger"] == second["ledger"]
    assert page["projection"] == second["projection"]


@pytest.mark.parametrize(
    ("target", "message"),
    (
        ("page", "observation page 1 changed"),
        ("manifest", "observation manifest is malformed"),
        ("projection", "projection binding is stale"),
        ("ledger", "ledger binding is stale"),
    ),
)
def test_presence_report_validation_detects_artifact_drift(
    tmp_path, target, message
):
    ws, ledger_path = _ledger(tmp_path)
    presence.observe_page_evidence_presence(
        workspace=ws,
        ledger_path=ledger_path,
        book_id="synthetic",
        witness_id="copy1",
    )
    presence.validate_presence_report(workspace=ws, witness_id="copy1")

    if target == "page":
        page_path = presence.page_observation_path(ws, witness_id="copy1", page=1)
        page = read_json(page_path)
        page["failure"] = {"code": "tampered"}
        atomic_write_json(page_path, page)
    elif target == "manifest":
        report_path = presence.report_path(ws, witness_id="copy1")
        report = read_json(report_path)
        report["observations"][0]["sha256"] = "0" * 64
        atomic_write_json(report_path, report)
    elif target == "projection":
        projection_path = presence.projection_path(ws, witness_id="copy1")
        projection = read_json(projection_path)
        projection["unexpected"] = True
        atomic_write_json(projection_path, projection)
    else:
        ledger = read_json(ledger_path)
        ledger["review_bound"] = 99
        atomic_write_json(ledger_path, ledger)

    with pytest.raises(ValueError, match=message):
        presence.validate_presence_report(workspace=ws, witness_id="copy1")


def test_presence_report_validation_rejects_coherently_rehashed_page_swap(tmp_path):
    ws, ledger_path = _ledger(tmp_path)
    presence.observe_page_evidence_presence(
        workspace=ws,
        ledger_path=ledger_path,
        book_id="synthetic",
        witness_id="copy1",
    )
    first_path = presence.page_observation_path(ws, witness_id="copy1", page=1)
    second_path = presence.page_observation_path(ws, witness_id="copy1", page=2)
    first = read_json(first_path)
    second = read_json(second_path)
    for key in ("request", "request_sha256", "bundle", "bundle_sha256"):
        first[key] = second[key]
    atomic_write_json(first_path, first)

    report_path = presence.report_path(ws, witness_id="copy1")
    report = read_json(report_path)
    report["observations"][0]["sha256"] = _sha(first_path)
    report["observations_sha256"] = presence._dict_sha256(report["observations"])
    atomic_write_json(report_path, report)

    with pytest.raises(ValueError, match="request page 1 differs from projection"):
        presence.validate_presence_report(workspace=ws, witness_id="copy1")


def test_presence_result_rejects_unsolicited_extra_capability():
    requested = SimpleNamespace(capability="presence")
    unsolicited = SimpleNamespace(capability="other")

    with pytest.raises(ValueError, match="exactly one requested result"):
        presence._presence_result(
            SimpleNamespace(results=(requested, unsolicited)),
            capability="presence",
        )


def test_presence_consumer_uses_only_the_supported_sidecar_core_surface():
    source = Path(presence.__file__).read_text(encoding="utf-8")

    assert "book_layout_sidecar.adapters" not in source
    assert "book_layout_sidecar.lab" not in source


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
        book_id="synthetic",
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


@pytest.mark.parametrize("failure_stage", ("api", "constructor", "provider"))
def test_presence_shadow_replaces_prior_success_for_preloop_failure(
    tmp_path, monkeypatch, failure_stage
):
    ws, ledger_path = _ledger(tmp_path)
    presence.observe_page_evidence_presence(
        workspace=ws,
        ledger_path=ledger_path,
        book_id="synthetic",
        witness_id="copy1",
    )
    api = presence._load_sidecar_api()

    def fail():
        raise RuntimeError(f"{failure_stage} unavailable")

    provider_factory = None
    if failure_stage == "api":
        monkeypatch.setattr(presence, "_load_sidecar_api", fail)
    elif failure_stage == "constructor":
        monkeypatch.setattr(
            presence,
            "_load_sidecar_api",
                lambda: {
                    **api,
                    "compute_effective_geometry_ocr_text_presence": (
                        lambda *args, **kwargs: fail()
                    ),
                },
        )
    else:
        provider_factory = fail

    with pytest.raises(RuntimeError, match=f"{failure_stage} unavailable"):
        presence.observe_page_evidence_presence(
            workspace=ws,
            ledger_path=ledger_path,
            book_id="synthetic",
            witness_id="copy1",
            provider_factory=provider_factory,
        )

    report = read_json(presence.report_path(ws, witness_id="copy1"))
    assert report["status"] == "unavailable"
    assert report["ledger"]["sha256"] == _sha(ledger_path)
    assert report["failure"] == {
        "code": "engine_error",
        "type": "RuntimeError",
        "message": f"{failure_stage} unavailable",
    }
    assert presence.validate_presence_report(
        workspace=ws, witness_id="copy1"
    )["status"] == "unavailable"
