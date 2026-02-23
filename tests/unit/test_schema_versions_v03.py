from __future__ import annotations

from trajectly.constants import (
    SIDE_EFFECT_TOOL_REGISTRY_V1,
    TRT_NORMALIZER_VERSION,
    TRT_REPORT_SCHEMA_VERSION,
    TRT_SIDE_EFFECT_REGISTRY_VERSION,
    TRT_SPEC_SCHEMA_VERSION,
    TRT_TRACE_SCHEMA_VERSION,
    WITNESS_FAILURE_CLASS_ORDER,
)
from trajectly.report.schema import TRTReportMetadataV03, TRTReportV03
from trajectly.trace.models import TraceEventV03, TraceMetaV03


def test_trt_v03_schema_constants_are_stable() -> None:
    assert TRT_SPEC_SCHEMA_VERSION == "0.3"
    assert TRT_TRACE_SCHEMA_VERSION == "0.3"
    assert TRT_REPORT_SCHEMA_VERSION == "0.3"
    assert TRT_NORMALIZER_VERSION == "1"
    assert TRT_SIDE_EFFECT_REGISTRY_VERSION == "1"


def test_side_effect_registry_v1_is_deterministic() -> None:
    assert SIDE_EFFECT_TOOL_REGISTRY_V1 == (
        "checkout",
        "create_refund",
        "send_email",
        "db_write",
        "filesystem_write",
        "http_request",
    )


def test_witness_class_order_is_refinement_then_contract_then_tooling() -> None:
    assert WITNESS_FAILURE_CLASS_ORDER == ("REFINEMENT", "CONTRACT", "TOOLING")


def test_trace_models_default_to_v03_and_normalizer_v1() -> None:
    event = TraceEventV03(
        event_index=0,
        kind="TOOL_CALL",
        payload={"tool_name": "search"},
        stable_hash="abc123",
    )
    meta = TraceMetaV03(spec_name="demo")

    assert event.schema_version == "0.3"
    assert meta.schema_version == "0.3"
    assert meta.normalizer_version == "1"


def test_report_schema_defaults_to_v03_with_metadata() -> None:
    report = TRTReportV03(status="PASS")
    metadata = TRTReportMetadataV03()
    report_payload = report.to_dict()

    assert metadata.report_schema_version == "0.3"
    assert metadata.normalizer_version == "1"
    assert metadata.side_effect_registry_version == "1"
    assert report_payload["metadata"]["report_schema_version"] == "0.3"
    assert report_payload["metadata"]["normalizer_version"] == "1"
