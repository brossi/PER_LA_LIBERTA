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


def _noise_page(page: int = 1) -> PageGeometry:
    words = tuple(
        WordBox(
            text="x",
            bbox=(10.0 + (index % 10) * 45.0, 10.0 + (index // 10) * 45.0,
                  20.0 + (index % 10) * 45.0, 20.0 + (index // 10) * 45.0),
        )
        for index in range(140)
    )
    return PageGeometry(page=page, width=500.0, height=700.0, words=words)


def _raster(page: int = 1, *, ink_fraction: float, sha256: str = "b" * 64):
    return shadow.PageRasterEvidence(
        page=page,
        artifact_ref=f"scan:synthetic/source.pdf#page={page}:raster=test:dpi=300",
        sha256=sha256,
        source_selector=f"page={page}",
        producer="test-raster-v1",
        dpi=300,
        width_px=2000,
        height_px=3000,
        ink_fraction=ink_fraction,
    )


def _density(
    page: int = 1,
    *,
    label: str,
    box_count: int = 0,
    token_yield: float = 0.0,
    mean_token_length: float = 0.0,
    policy_applied: bool = True,
):
    return shadow.PageDensityEvidence(
        page=page,
        box_count=box_count,
        token_yield=token_yield,
        mean_token_length=mean_token_length,
        label=label,
        confidence=0.5,
        hint=label,
        producer="test-density-v1",
        policy_applied=policy_applied,
    )


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
        "provider_version": "0.1.5",
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
        identity=ProviderIdentity("book_layout_sidecar", "0.1.4")
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

    assert first.bundle.provider.provider_version == "0.1.4"
    assert second.status == shadow.STATUS_AVAILABLE
    assert second.cached is False
    assert provider.calls == 1
    assert second.bundle.provider.provider_version == "0.1.5"
    assert read_json(second.path)["provider"]["provider_version"] == "0.1.5"


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
def test_zero_boxes_with_calibrated_content_density_support_content(tmp_path):
    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()
    raster = _raster(ink_fraction=0.08)
    result = _observe(
        ws,
        page_geometry=_empty_page(),
        raster_evidence=raster,
        density_evidence=_density(label="content"),
    )
    near_blank = next(
        item for item in result.bundle.results if item.module_id == "near_blank_hallucinated_boxes"
    )
    request = read_json(result.path)["request"]

    assert near_blank.assessment == "supported"
    assert "density_supports_ocr_relevant_content" in near_blank.reasons
    raster_artifact = next(
        item for item in request["input_artifacts"] if item["kind"] == "source_raster"
    )
    assert raster_artifact["sha256"] == raster.sha256


@requires_sidecar
def test_clean_body_with_calibrated_content_density_is_supported(tmp_path):
    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()
    result = _observe(
        ws,
        page_geometry=_page(),
        raster_evidence=_raster(ink_fraction=0.08),
        density_evidence=_density(
            label="content",
            box_count=30,
            token_yield=1.0,
            mean_token_length=7.5,
        ),
    )
    near_blank = next(
        item for item in result.bundle.results if item.module_id == "near_blank_hallucinated_boxes"
    )

    assert near_blank.assessment == "supported"
    assert near_blank.metrics["density_label"] == "content"


@requires_sidecar
def test_zero_boxes_with_calibrated_near_blank_density_are_unsupported(tmp_path):
    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()
    result = _observe(
        ws,
        page_geometry=_empty_page(),
        raster_evidence=_raster(ink_fraction=0.001),
        density_evidence=_density(label="near_blank"),
    )
    near_blank = next(
        item for item in result.bundle.results if item.module_id == "near_blank_hallucinated_boxes"
    )

    assert near_blank.assessment == "unsupported"
    assert "near_blank_empty_low_ocr_activity" in near_blank.reasons


@requires_sidecar
def test_raw_raster_without_policy_does_not_become_positive_density_evidence(tmp_path):
    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()
    result = _observe(
        ws,
        page_geometry=_empty_page(),
        raster_evidence=_raster(ink_fraction=0.08),
    )
    near_blank = next(
        item for item in result.bundle.results if item.module_id == "near_blank_hallucinated_boxes"
    )
    request = read_json(result.path)["request"]

    assert near_blank.execution_status == "not_applicable"
    assert "density" not in request["evidence"]
    assert any(item["kind"] == "source_raster" for item in request["input_artifacts"])


@requires_sidecar
def test_zero_boxes_with_uncalibrated_visual_activity_abstain(tmp_path):
    """The same raw signal can be readable faint text or mirrored show-through."""
    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()
    result = _observe(
        ws,
        page_geometry=_empty_page(),
        raster_evidence=_raster(ink_fraction=0.08),
        density_evidence=_density(
            label="abstain",
            policy_applied=False,
        ),
    )
    near_blank = next(
        item for item in result.bundle.results if item.module_id == "near_blank_hallucinated_boxes"
    )

    assert near_blank.execution_status == "not_applicable"
    assert near_blank.assessment is None


@requires_sidecar
def test_high_box_blank_with_nondecisive_raw_density_remains_uncertain(tmp_path):
    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()
    result = _observe(
        ws,
        page_geometry=_noise_page(),
        raster_evidence=_raster(ink_fraction=0.01),
        density_evidence=_density(
            label="abstain",
            box_count=140,
            token_yield=0.0,
            mean_token_length=1.0,
            policy_applied=False,
        ),
    )
    near_blank = next(
        item for item in result.bundle.results if item.module_id == "near_blank_hallucinated_boxes"
    )

    assert near_blank.assessment == "uncertain"
    assert near_blank.confidence == 1.0
    assert near_blank.metrics["hallucination_score"] == 0.75


@requires_sidecar
def test_high_box_blank_with_near_zero_raw_density_is_unsupported(tmp_path):
    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()
    result = _observe(
        ws,
        page_geometry=_noise_page(),
        raster_evidence=_raster(ink_fraction=0.001),
        density_evidence=_density(
            label="abstain",
            box_count=140,
            token_yield=0.0,
            mean_token_length=1.0,
            policy_applied=False,
        ),
    )
    near_blank = next(
        item for item in result.bundle.results if item.module_id == "near_blank_hallucinated_boxes"
    )

    assert near_blank.assessment == "unsupported"
    assert "near_blank_hallucinated_boxes_likely" in near_blank.reasons
    assert "very_low_ink_fraction" in near_blank.reasons


@requires_sidecar
def test_changed_raster_hash_invalidates_cached_assessment(tmp_path):
    from book_layout_sidecar.core import CoreAssessmentProvider

    ws = BookWorkspace.for_book("synthetic", tmp_path).ensure()
    _observe(ws, raster_evidence=_raster(ink_fraction=0.08))
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
        raster_evidence=_raster(ink_fraction=0.08, sha256="c" * 64),
        provider_factory=lambda: provider,
    )

    assert result.cached is False
    assert provider.calls == 1


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
        "matrix_version": 4,
        "cases": 58,
        "boundary_valid": 29,
        "boundary_unavailable": 29,
        "status": "ok",
    }


@requires_sidecar
def test_installed_spatial_contract_requires_explicit_bound_box_input(tmp_path):
    from book_layout_sidecar.core import (
        AssessmentEvidence,
        AssessmentInputArtifact,
        AssessmentSubject,
        BoundingBox,
        CoreAssessmentProvider,
        GeometryOcrBoxSet,
        build_assessment_request,
        build_geometry_ocr_spatial_input,
    )
    from book_layout_sidecar.core.assessment import (
        CAPABILITY_EFFECTIVE_GEOMETRY_BOXES_HAVE_OCR_SPATIAL_SUPPORT,
    )
    from book_layout_sidecar.core.modules import (
        INPUT_KIND_EFFECTIVE_GEOMETRY_BOXES,
        INPUT_KIND_OCR_BOXES,
        EffectiveGeometryOcrSpatialSupportModule,
    )

    boxes = (
        BoundingBox(0, 0, 10, 10),
        BoundingBox(20, 0, 30, 10),
        BoundingBox(40, 0, 50, 10),
    )
    geometry = GeometryOcrBoxSet(
        page=1,
        width=100,
        height=100,
        boxes=boxes,
        source_ref="geometry:consumer-fixture/page-1",
        source_sha256="b" * 64,
        source_selector="$.effective_geometry.boxes",
        coordinate_space_id="source:consumer-fixture#page=1:full",
    )
    ocr = GeometryOcrBoxSet(
        page=1,
        width=100,
        height=100,
        boxes=boxes,
        source_ref="ocr:consumer-fixture/page-1",
        source_sha256="c" * 64,
        source_selector="$.ocr_geometry.boxes",
        coordinate_space_id="source:consumer-fixture#page=1:full",
    )
    evidence = AssessmentEvidence(
        subject=AssessmentSubject(
            book_id="consumer_fixture",
            source_ref="source:consumer-fixture",
            source_sha256="a" * 64,
            page=1,
        ),
        input_artifacts=(
            AssessmentInputArtifact(
                INPUT_KIND_EFFECTIVE_GEOMETRY_BOXES,
                geometry.source_ref,
                geometry.source_sha256,
            ),
            AssessmentInputArtifact(
                INPUT_KIND_OCR_BOXES,
                ocr.source_ref,
                ocr.source_sha256,
            ),
        ),
        geometry_ocr_spatial_input=build_geometry_ocr_spatial_input(
            geometry=geometry,
            ocr=ocr,
            geometry_detector_producer="tesseract@consumer-fixture",
            geometry_detector_family="tesseract",
            ocr_detector_producer="abbyy@consumer-fixture",
            ocr_detector_family="abbyy",
        ),
    )
    request = build_assessment_request(
        evidence=evidence,
        modules=(EffectiveGeometryOcrSpatialSupportModule(),),
    )
    result = CoreAssessmentProvider().assess(request).results[0]

    assert request.request_version == 5
    assert result.capability == (
        CAPABILITY_EFFECTIVE_GEOMETRY_BOXES_HAVE_OCR_SPATIAL_SUPPORT
    )
    assert result.assessment == "supported"
    assert result.metrics["support_class"] == "sufficient"

    workspace = BookWorkspace.for_book("synthetic", tmp_path).ensure()
    ordinary_observation = _observe(workspace)
    assert CAPABILITY_EFFECTIVE_GEOMETRY_BOXES_HAVE_OCR_SPATIAL_SUPPORT not in {
        item.capability for item in ordinary_observation.bundle.results
    }


@requires_sidecar
def test_installed_ocr_null_gate_distinguishes_active_abstention_from_blank():
    from book_layout_sidecar.core import should_run_perturbation_probe
    from book_layout_sidecar.core.density import DensityFeature
    from book_layout_sidecar.core.near_blank import score_near_blank_hallucinated_boxes
    from book_layout_sidecar.core.ocr import OcrPage
    from book_layout_sidecar.core.ocr_stats import compute_ocr_page_stats

    page = OcrPage(
        page=1,
        width=500.0,
        height=700.0,
        boxes=(),
        source_format="engine-consumer-fixture",
        source_ref="fixture/page.png",
        source_selector="page=1",
    )
    stats = compute_ocr_page_stats(page)
    score = score_near_blank_hallucinated_boxes(stats)

    def density(ink_fraction: float) -> DensityFeature:
        return DensityFeature(
            page=1,
            hint="density_policy_absent",
            ink_fraction=ink_fraction,
            box_count=0,
            token_yield=0.0,
            mean_token_length=0.0,
            label="abstain",
            confidence=0.0,
            source_ref="fixture/page.png",
            source_selector="page=1",
            producer="engine-consumer-fixture",
        )

    active = should_run_perturbation_probe(score, stats=stats, density=density(0.08))
    blank = should_run_perturbation_probe(score, stats=stats, density=density(0.001))

    assert active.should_probe is True
    assert active.reason == "ocr_null_with_unresolved_visual_activity"
    assert blank.should_probe is False
    assert blank.reason == "ocr_null_with_decisive_near_blank_evidence"
