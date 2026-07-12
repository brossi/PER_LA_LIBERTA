from __future__ import annotations

import importlib.util

import pytest

from engine.paths import BookWorkspace
from engine.structure.geometry import PageGeometry, WordBox
from engine.structure import layout_assessment_shadow as shadow
from engine.util.jsonio import atomic_write_text, read_json


def _sidecar_installed() -> bool:
    return importlib.util.find_spec("book_layout_sidecar") is not None


requires_sidecar = pytest.mark.skipif(
    not _sidecar_installed(), reason="book-layout-sidecar assessment extra is not installed"
)


def _page(page: int = 1, *, two_columns: bool = False) -> PageGeometry:
    words = []
    for index in range(30):
        column_x = 40.0 if not two_columns or index < 15 else 330.0
        row = index if not two_columns else index % 15
        words.append(
            WordBox(
                text=f"parola{index}",
                bbox=(column_x, 40.0 + row * 20.0, column_x + 70.0, 52.0 + row * 20.0),
            )
        )
    return PageGeometry(page=page, width=500.0, height=700.0, words=tuple(words))


def _empty_page(page: int = 1) -> PageGeometry:
    return PageGeometry(page=page, width=500.0, height=700.0, words=())


def _observe(ws, **overrides):
    values = {
        "workspace": ws,
        "mode": shadow.MODE_SHADOW,
        "witness_id": "tesseract",
        "source_ref": "scan:synthetic/source.pdf",
        "source_sha256": "a" * 64,
        "page_geometry": _page(),
        "geometry_engine_id": "test-geometry-1",
    }
    values.update(overrides)
    return shadow.observe_page_geometry(**values)


def test_off_is_a_true_noop_without_optional_import_provider_or_artifact(tmp_path, monkeypatch):
    ws = BookWorkspace.for_book("synthetic", tmp_path)
    monkeypatch.setattr(
        shadow,
        "_load_sidecar_api",
        lambda: (_ for _ in ()).throw(AssertionError("optional package loaded")),
    )

    result = shadow.observe_page_geometry(
        workspace=ws,
        mode=shadow.MODE_OFF,
        witness_id="../not-even-validated-in-off-mode",
        source_ref="",
        source_sha256="not-a-hash",
        page_geometry=_page(),
        geometry_engine_id="",
        provider_factory=lambda: (_ for _ in ()).throw(AssertionError("provider constructed")),
    )

    assert result.status == shadow.STATUS_OFF
    assert result.path is None
    assert not ws.root.exists()


@requires_sidecar
def test_valid_shadow_observation_persists_and_revalidates_exact_request(tmp_path):
    from book_layout_sidecar.core import (
        assessment_bundle_from_dict,
        assessment_request_from_dict,
        validate_assessment_response,
    )

    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()
    result = _observe(ws)

    assert result.status == shadow.STATUS_AVAILABLE
    envelope = read_json(result.path)
    assert envelope["status"] == shadow.STATUS_AVAILABLE
    assert envelope["mode"] == shadow.MODE_SHADOW
    assert envelope["stale_class"] == shadow.OBSERVATION_STALE_CLASS
    assert envelope["request"]["subject"]["source_sha256"] == "a" * 64
    assert envelope["provider"] == {
        "provider_id": "book_layout_sidecar",
        "provider_version": "0.1.1",
    }

    request = assessment_request_from_dict(envelope["request"])
    bundle = assessment_bundle_from_dict(envelope["bundle"])
    validate_assessment_response(request, bundle, expected_provider=bundle.provider)
    assert len(bundle.results) == 3
    assert {item.execution_status for item in bundle.results} <= {
        "completed",
        "not_applicable",
    }


@requires_sidecar
def test_fresh_observation_is_reused_only_after_full_revalidation(tmp_path):
    from book_layout_sidecar.core import CoreAssessmentProvider

    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()
    first = _observe(ws)
    core = CoreAssessmentProvider()

    class _ExplodingProvider:
        identity = core.identity

        def assess(self, request):
            raise AssertionError("fresh cache should avoid a provider call")

    second = _observe(ws, provider_factory=_ExplodingProvider)

    assert first.status == second.status == shadow.STATUS_AVAILABLE
    assert second.cached is True
    assert first.bundle.to_dict() == second.bundle.to_dict()


@requires_sidecar
def test_previous_provider_version_invalidates_cache_without_refresh(tmp_path):
    from book_layout_sidecar.core import CoreAssessmentProvider, ProviderIdentity

    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()
    previous = CoreAssessmentProvider(
        identity=ProviderIdentity("book_layout_sidecar", "0.1.0")
    )
    first = _observe(ws, provider_factory=lambda: previous, refresh=True)
    current = CoreAssessmentProvider()

    class _CountingProvider:
        identity = current.identity

        def __init__(self):
            self.calls = 0

        def assess(self, request):
            self.calls += 1
            return current.assess(request)

    provider = _CountingProvider()
    second = _observe(ws, provider_factory=lambda: provider)

    assert first.bundle.provider.provider_version == "0.1.0"
    assert second.status == shadow.STATUS_AVAILABLE
    assert second.cached is False
    assert provider.calls == 1
    assert second.bundle.provider.provider_version == "0.1.1"
    assert read_json(second.path)["provider"]["provider_version"] == "0.1.1"


@requires_sidecar
def test_changed_source_hash_invalidates_cache_and_calls_provider(tmp_path):
    from book_layout_sidecar.core import CoreAssessmentProvider

    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()
    _observe(ws)
    core = CoreAssessmentProvider()

    class _CountingProvider:
        identity = core.identity

        def __init__(self):
            self.calls = 0

        def assess(self, request):
            self.calls += 1
            return core.assess(request)

    provider = _CountingProvider()
    result = _observe(
        ws,
        source_sha256="b" * 64,
        provider_factory=lambda: provider,
    )

    assert result.status == shadow.STATUS_AVAILABLE
    assert result.cached is False
    assert provider.calls == 1
    assert read_json(result.path)["request"]["subject"]["source_sha256"] == "b" * 64


@requires_sidecar
@pytest.mark.parametrize(
    ("provider_method", "error_type"),
    [
        (lambda request: object(), "ValueError"),
        (lambda request: (_ for _ in ()).throw(RuntimeError("provider down")), "RuntimeError"),
    ],
)
def test_malformed_response_or_provider_exception_is_explicitly_unavailable(
    tmp_path, provider_method, error_type
):
    from book_layout_sidecar.core import CoreAssessmentProvider

    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()
    authoritative = ws.resolve("data", "canonical.txt")
    atomic_write_text(authoritative, "unchanged pipeline truth")
    identity = CoreAssessmentProvider().identity

    class _Provider:
        def __init__(self):
            self.identity = identity

        def assess(self, request):
            return provider_method(request)

    result = _observe(ws, provider_factory=_Provider)

    assert result.status == shadow.STATUS_UNAVAILABLE
    assert result.failure_code == "provider_error"
    envelope = read_json(result.path)
    assert envelope["bundle"] is None
    assert envelope["failure"]["type"] == error_type
    assert authoritative.read_text(encoding="utf-8") == "unchanged pipeline truth"


@requires_sidecar
def test_column_capability_is_requested_only_with_ratified_policy(tmp_path):
    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()

    without = _observe(ws, page_geometry=_page(two_columns=True), refresh=True)
    with_policy = _observe(
        ws,
        page_geometry=_page(two_columns=True),
        column_policy=shadow.ColumnAssessmentPolicy(
            decision_threshold=0.5,
            hysteresis_margin=0.15,
        ),
        refresh=True,
    )

    assert len(without.bundle.results) == 3
    assert len(with_policy.bundle.results) == 4
    assert any(item.module_id == "column_hysteresis" for item in with_policy.bundle.results)


@requires_sidecar
def test_zero_boxes_without_pixel_evidence_never_support_content(tmp_path):
    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()

    result = _observe(ws, page_geometry=_empty_page())
    near_blank = next(
        item for item in result.bundle.results if item.module_id == "near_blank_hallucinated_boxes"
    )

    assert near_blank.execution_status == "not_applicable"
    assert near_blank.assessment is None
    assert near_blank.confidence is None
    assert near_blank.reasons == ("zero_ocr_boxes_without_affirmative_content_evidence",)
    assert near_blank.module_version == "2.1.0"


@requires_sidecar
def test_identical_refresh_is_byte_deterministic(tmp_path):
    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()

    first = _observe(ws, refresh=True)
    first_bytes = first.path.read_bytes()
    second = _observe(ws, refresh=True)

    assert second.path.read_bytes() == first_bytes
    assert second.bundle.to_dict() == first.bundle.to_dict()


@requires_sidecar
def test_installed_provider_conformance_packet_passes():
    from book_layout_sidecar.contracts.conformance import run_conformance_matrix

    assert run_conformance_matrix() == {
        "matrix_version": 2,
        "cases": 32,
        "boundary_valid": 17,
        "boundary_unavailable": 15,
        "status": "ok",
    }
