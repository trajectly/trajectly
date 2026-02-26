from __future__ import annotations

from typing import Any

from trajectly.core.constants import TRT_NORMALIZER_VERSION, TRT_TRACE_SCHEMA_VERSION
from trajectly.core.trace.models import TRACE_EVENT_KINDS_V03


class TraceValidationError(ValueError):
    pass


def validate_trace_event_v03(data: dict[str, Any]) -> dict[str, Any]:
    schema_version = data.get("schema_version")
    if schema_version != TRT_TRACE_SCHEMA_VERSION:
        raise TraceValidationError(
            f"Unsupported trace schema_version '{schema_version}'. Expected '{TRT_TRACE_SCHEMA_VERSION}'."
        )

    event_index = data.get("event_index")
    if not isinstance(event_index, int) or event_index < 0:
        raise TraceValidationError("Trace event requires non-negative integer `event_index`")

    kind = data.get("kind")
    if not isinstance(kind, str) or kind not in TRACE_EVENT_KINDS_V03:
        raise TraceValidationError(f"Trace event requires supported `kind`, got: {kind!r}")

    payload = data.get("payload")
    if not isinstance(payload, dict):
        raise TraceValidationError("Trace event requires object field `payload`")

    stable_hash = data.get("stable_hash")
    if not isinstance(stable_hash, str) or not stable_hash:
        raise TraceValidationError("Trace event requires non-empty string field `stable_hash`")

    return {
        "schema_version": schema_version,
        "event_index": event_index,
        "kind": kind,
        "payload": payload,
        "stable_hash": stable_hash,
    }


def validate_trace_meta_v03(data: dict[str, Any]) -> dict[str, Any]:
    schema_version = data.get("schema_version")
    if schema_version != TRT_TRACE_SCHEMA_VERSION:
        raise TraceValidationError(
            f"Unsupported trace meta schema_version '{schema_version}'. Expected '{TRT_TRACE_SCHEMA_VERSION}'."
        )

    normalizer_version = data.get("normalizer_version")
    if normalizer_version != TRT_NORMALIZER_VERSION:
        raise TraceValidationError(
            "Unsupported normalizer_version "
            f"'{normalizer_version}'. Expected '{TRT_NORMALIZER_VERSION}'."
        )

    metadata = data.get("metadata", {})
    if not isinstance(metadata, dict):
        raise TraceValidationError("Trace metadata field `metadata` must be an object")

    normalized = {
        "schema_version": schema_version,
        "normalizer_version": normalizer_version,
        "metadata": metadata,
    }
    for key in ("spec_name", "run_id", "mode"):
        value = data.get(key)
        if value is not None and not isinstance(value, str):
            raise TraceValidationError(f"Trace metadata field `{key}` must be a string when provided")
        if isinstance(value, str):
            normalized[key] = value
    return normalized


__all__ = [
    "TraceValidationError",
    "validate_trace_event_v03",
    "validate_trace_meta_v03",
]
