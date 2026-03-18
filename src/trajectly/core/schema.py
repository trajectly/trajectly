"""Core implementation module: trajectly/core/schema.py."""

from __future__ import annotations

from typing import Any

from trajectly.core.constants import (
    SCHEMA_VERSION,
    TRACE_EVENT_TYPES,
    TRT_NORMALIZER_VERSION,
    TRT_TRACE_SCHEMA_VERSION,
)
from trajectly.core.trace.validate import TraceValidationError, validate_trace_event_v03, validate_trace_meta_v03

SUPPORTED_TRACE_SCHEMA_VERSIONS = {SCHEMA_VERSION}
SUPPORTED_REPORT_SCHEMA_VERSIONS = {SCHEMA_VERSION}
SUPPORTED_TRAJECTORY_JSON_SCHEMA_VERSIONS = {TRT_TRACE_SCHEMA_VERSION}


class SchemaValidationError(ValueError):
    """Represent `SchemaValidationError`."""
    pass


def _unsupported_version_message(kind: str, version: str, supported: set[str]) -> str:
    """Execute `_unsupported_version_message`."""
    supported_text = ", ".join(sorted(supported))
    return (
        f"Unsupported {kind} schema_version '{version}'. Supported versions: {supported_text}. "
        "Migration required: regenerate artifacts with current Trajectly version."
    )


def _normalize_schema_version(
    value: Any,
    *,
    kind: str,
    supported: set[str],
    allow_missing: bool,
) -> str:
    """Execute `_normalize_schema_version`."""
    if value is None:
        if allow_missing:
            return SCHEMA_VERSION
        raise SchemaValidationError(f"Missing required {kind} schema_version")

    version = str(value)
    if version not in supported:
        raise SchemaValidationError(_unsupported_version_message(kind, version, supported))
    return version


def validate_trace_event_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Execute `validate_trace_event_dict`."""
    if not isinstance(data, dict):
        raise SchemaValidationError("Trace event must be an object")

    schema_version = _normalize_schema_version(
        data.get("schema_version"),
        kind="trace",
        supported=SUPPORTED_TRACE_SCHEMA_VERSIONS,
        allow_missing=True,
    )

    event_type = data.get("event_type")
    if not isinstance(event_type, str) or not event_type:
        raise SchemaValidationError("Trace event requires non-empty string field `event_type`")
    if event_type not in TRACE_EVENT_TYPES:
        raise SchemaValidationError(f"Unsupported event type: {event_type}")

    seq = data.get("seq")
    if not isinstance(seq, int) or seq <= 0:
        raise SchemaValidationError("Trace event requires positive integer field `seq`")

    run_id = data.get("run_id")
    if not isinstance(run_id, str) or not run_id.strip():
        raise SchemaValidationError("Trace event requires non-empty string field `run_id`")

    rel_ms = data.get("rel_ms")
    if not isinstance(rel_ms, int) or rel_ms < 0:
        raise SchemaValidationError("Trace event requires non-negative integer field `rel_ms`")

    payload = data.get("payload")
    if not isinstance(payload, dict):
        raise SchemaValidationError("Trace event requires object field `payload`")

    meta = data.get("meta", {})
    if not isinstance(meta, dict):
        raise SchemaValidationError("Trace event field `meta` must be an object")

    normalized: dict[str, Any] = {
        "schema_version": schema_version,
        "event_type": event_type,
        "seq": seq,
        "run_id": run_id,
        "rel_ms": rel_ms,
        "payload": payload,
        "meta": meta,
    }
    if "event_id" in data and data["event_id"] is not None:
        normalized["event_id"] = str(data["event_id"])
    return normalized


def validate_diff_report_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Execute `validate_diff_report_dict`."""
    if not isinstance(data, dict):
        raise SchemaValidationError("Diff report must be an object")

    schema_version = _normalize_schema_version(
        data.get("schema_version"),
        kind="report",
        supported=SUPPORTED_REPORT_SCHEMA_VERSIONS,
        allow_missing=True,
    )

    summary = data.get("summary")
    if not isinstance(summary, dict):
        raise SchemaValidationError("Diff report requires object field `summary`")

    findings = data.get("findings")
    if not isinstance(findings, list):
        raise SchemaValidationError("Diff report requires list field `findings`")

    normalized_findings: list[dict[str, Any]] = []
    for finding in findings:
        if not isinstance(finding, dict):
            raise SchemaValidationError("Each finding must be an object")
        classification = finding.get("classification")
        message = finding.get("message")
        if not isinstance(classification, str) or not classification:
            raise SchemaValidationError("Each finding requires non-empty string `classification`")
        if not isinstance(message, str) or not message:
            raise SchemaValidationError("Each finding requires non-empty string `message`")
        normalized_findings.append(dict(finding))

    return {
        "schema_version": schema_version,
        "summary": summary,
        "findings": normalized_findings,
    }


def validate_latest_report_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Execute `validate_latest_report_dict`."""
    if not isinstance(data, dict):
        raise SchemaValidationError("Latest report must be an object")

    schema_version = _normalize_schema_version(
        data.get("schema_version"),
        kind="report",
        supported=SUPPORTED_REPORT_SCHEMA_VERSIONS,
        allow_missing=True,
    )

    processed_specs = data.get("processed_specs")
    regressions = data.get("regressions")
    errors = data.get("errors")
    reports = data.get("reports")

    if not isinstance(processed_specs, int) or processed_specs < 0:
        raise SchemaValidationError("Latest report requires non-negative integer `processed_specs`")
    if not isinstance(regressions, int) or regressions < 0:
        raise SchemaValidationError("Latest report requires non-negative integer `regressions`")
    if not isinstance(errors, list):
        raise SchemaValidationError("Latest report requires list field `errors`")
    if not isinstance(reports, list):
        raise SchemaValidationError("Latest report requires list field `reports`")

    return {
        "schema_version": schema_version,
        "processed_specs": processed_specs,
        "regressions": regressions,
        "errors": errors,
        "reports": reports,
    }


def validate_trajectory_json_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Validate a portable execution trajectory JSON payload."""

    if not isinstance(data, dict):
        raise SchemaValidationError("Trajectory JSON payload must be an object")

    schema_version = _normalize_schema_version(
        data.get("schema_version", TRT_TRACE_SCHEMA_VERSION),
        kind="trajectory JSON",
        supported=SUPPORTED_TRAJECTORY_JSON_SCHEMA_VERSIONS,
        allow_missing=True,
    )

    meta_raw = data.get("meta", {})
    if not isinstance(meta_raw, dict):
        raise SchemaValidationError("Trajectory JSON requires object field `meta`")

    events_raw = data.get("events", [])
    if not isinstance(events_raw, list):
        raise SchemaValidationError("Trajectory JSON requires list field `events`")

    meta_candidate = {
        "schema_version": meta_raw.get("schema_version", TRT_TRACE_SCHEMA_VERSION),
        "normalizer_version": meta_raw.get("normalizer_version", TRT_NORMALIZER_VERSION),
        "metadata": meta_raw.get("metadata", {}),
        **{
            key: value
            for key, value in meta_raw.items()
            if key not in {"schema_version", "normalizer_version", "metadata"}
        },
    }

    try:
        normalized_meta = validate_trace_meta_v03(meta_candidate)
        normalized_events = [
            validate_trace_event_v03(
                {
                    "schema_version": event.get("schema_version", TRT_TRACE_SCHEMA_VERSION)
                    if isinstance(event, dict)
                    else None,
                    **(event if isinstance(event, dict) else {}),
                }
            )
            for event in events_raw
        ]
    except TraceValidationError as exc:
        raise SchemaValidationError(str(exc)) from exc

    return {
        "schema_version": schema_version,
        "meta": normalized_meta,
        "events": normalized_events,
    }


__all__ = [
    "SUPPORTED_REPORT_SCHEMA_VERSIONS",
    "SUPPORTED_TRACE_SCHEMA_VERSIONS",
    "SUPPORTED_TRAJECTORY_JSON_SCHEMA_VERSIONS",
    "SchemaValidationError",
    "validate_diff_report_dict",
    "validate_latest_report_dict",
    "validate_trace_event_dict",
    "validate_trajectory_json_dict",
]
