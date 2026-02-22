from __future__ import annotations

from typing import Any

from trajectly.constants import SCHEMA_VERSION, TRACE_EVENT_TYPES

SUPPORTED_TRACE_SCHEMA_VERSIONS = {SCHEMA_VERSION}
SUPPORTED_REPORT_SCHEMA_VERSIONS = {SCHEMA_VERSION}


class SchemaValidationError(ValueError):
    pass


def _unsupported_version_message(kind: str, version: str, supported: set[str]) -> str:
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
    if value is None:
        if allow_missing:
            return SCHEMA_VERSION
        raise SchemaValidationError(f"Missing required {kind} schema_version")

    version = str(value)
    if version not in supported:
        raise SchemaValidationError(_unsupported_version_message(kind, version, supported))
    return version


def validate_trace_event_dict(data: dict[str, Any]) -> dict[str, Any]:
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


__all__ = [
    "SUPPORTED_REPORT_SCHEMA_VERSIONS",
    "SUPPORTED_TRACE_SCHEMA_VERSIONS",
    "SchemaValidationError",
    "validate_diff_report_dict",
    "validate_latest_report_dict",
    "validate_trace_event_dict",
]
