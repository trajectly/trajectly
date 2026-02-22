from __future__ import annotations

import json
from pathlib import Path

import pytest

from trajectly.constants import SCHEMA_VERSION
from trajectly.events import read_events_jsonl
from trajectly.schema import (
    SchemaValidationError,
    validate_diff_report_dict,
    validate_latest_report_dict,
    validate_trace_event_dict,
)


def test_validate_trace_event_defaults_missing_schema_version() -> None:
    normalized = validate_trace_event_dict(
        {
            "event_type": "run_started",
            "seq": 1,
            "run_id": "run-1",
            "rel_ms": 0,
            "payload": {"spec_name": "demo"},
            "meta": {},
        }
    )

    assert normalized["schema_version"] == SCHEMA_VERSION


def test_validate_trace_event_rejects_unsupported_schema_version() -> None:
    with pytest.raises(SchemaValidationError, match="Unsupported trace schema_version"):
        validate_trace_event_dict(
            {
                "schema_version": "v999",
                "event_type": "run_started",
                "seq": 1,
                "run_id": "run-1",
                "rel_ms": 0,
                "payload": {},
                "meta": {},
            }
        )


def test_read_events_jsonl_rejects_unsupported_schema_version(tmp_path: Path) -> None:
    path = tmp_path / "bad-trace.jsonl"
    path.write_text(
        json.dumps(
            {
                "schema_version": "v999",
                "event_type": "run_started",
                "seq": 1,
                "run_id": "run-1",
                "rel_ms": 0,
                "payload": {},
                "meta": {},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(SchemaValidationError, match="Migration required"):
        read_events_jsonl(path)


def test_validate_diff_report_defaults_schema_version() -> None:
    normalized = validate_diff_report_dict(
        {
            "summary": {"regression": False, "finding_count": 0},
            "findings": [],
        }
    )

    assert normalized["schema_version"] == SCHEMA_VERSION


def test_validate_diff_report_rejects_unsupported_schema_version() -> None:
    with pytest.raises(SchemaValidationError, match="Unsupported report schema_version"):
        validate_diff_report_dict(
            {
                "schema_version": "v999",
                "summary": {"regression": False, "finding_count": 0},
                "findings": [],
            }
        )


def test_validate_latest_report_defaults_schema_version() -> None:
    normalized = validate_latest_report_dict(
        {
            "processed_specs": 1,
            "regressions": 0,
            "errors": [],
            "reports": [],
        }
    )

    assert normalized["schema_version"] == SCHEMA_VERSION


def test_validate_latest_report_rejects_unsupported_schema_version() -> None:
    with pytest.raises(SchemaValidationError, match="Unsupported report schema_version"):
        validate_latest_report_dict(
            {
                "schema_version": "v999",
                "processed_specs": 1,
                "regressions": 0,
                "errors": [],
                "reports": [],
            }
        )
