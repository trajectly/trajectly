"""Core implementation module: trajectly/core/trace/models.py."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal, cast

from trajectly.core.constants import TRT_NORMALIZER_VERSION, TRT_TRACE_SCHEMA_VERSION

EventKindV03 = Literal[
    "LLM_REQUEST",
    "LLM_RESPONSE",
    "TOOL_CALL",
    "TOOL_RESULT",
    "MESSAGE",
    "OBSERVATION",
    "ERROR",
]

TRACE_EVENT_KINDS_V03 = {
    "LLM_REQUEST",
    "LLM_RESPONSE",
    "TOOL_CALL",
    "TOOL_RESULT",
    "MESSAGE",
    "OBSERVATION",
    "ERROR",
}


@dataclass(slots=True)
class TraceEventV03:
    """Represent `TraceEventV03`."""
    event_index: int
    kind: EventKindV03
    payload: dict[str, Any]
    stable_hash: str
    schema_version: str = TRT_TRACE_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        """Execute `to_dict`."""
        return {
            "schema_version": self.schema_version,
            "event_index": self.event_index,
            "kind": self.kind,
            "payload": self.payload,
            "stable_hash": self.stable_hash,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TraceEventV03:
        """Construct a trace event from validated dictionary data."""
        schema_version = str(data.get("schema_version", TRT_TRACE_SCHEMA_VERSION))
        if schema_version != TRT_TRACE_SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported trace schema_version '{schema_version}'. Expected '{TRT_TRACE_SCHEMA_VERSION}'."
            )

        event_index = data.get("event_index")
        if not isinstance(event_index, int) or event_index < 0:
            raise ValueError("Trace event requires non-negative integer `event_index`")

        kind = data.get("kind")
        if not isinstance(kind, str) or kind not in TRACE_EVENT_KINDS_V03:
            raise ValueError(f"Trace event requires supported `kind`, got: {kind!r}")

        payload = data.get("payload")
        if not isinstance(payload, dict):
            raise ValueError("Trace event requires object field `payload`")

        stable_hash = data.get("stable_hash")
        if not isinstance(stable_hash, str) or not stable_hash:
            raise ValueError("Trace event requires non-empty string field `stable_hash`")

        return cls(
            schema_version=schema_version,
            event_index=event_index,
            kind=cast(EventKindV03, kind),
            payload=payload,
            stable_hash=stable_hash,
        )


@dataclass(slots=True)
class TraceMetaV03:
    """Represent `TraceMetaV03`."""
    schema_version: str = TRT_TRACE_SCHEMA_VERSION
    normalizer_version: str = TRT_NORMALIZER_VERSION
    spec_name: str | None = None
    run_id: str | None = None
    mode: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Execute `to_dict`."""
        payload: dict[str, Any] = {
            "schema_version": self.schema_version,
            "normalizer_version": self.normalizer_version,
            "metadata": self.metadata,
        }
        if self.spec_name is not None:
            payload["spec_name"] = self.spec_name
        if self.run_id is not None:
            payload["run_id"] = self.run_id
        if self.mode is not None:
            payload["mode"] = self.mode
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TraceMetaV03:
        """Construct trace metadata from dictionary data."""
        schema_version = str(data.get("schema_version", TRT_TRACE_SCHEMA_VERSION))
        if schema_version != TRT_TRACE_SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported trace meta schema_version '{schema_version}'. Expected '{TRT_TRACE_SCHEMA_VERSION}'."
            )

        normalizer_version = str(data.get("normalizer_version", TRT_NORMALIZER_VERSION))
        if normalizer_version != TRT_NORMALIZER_VERSION:
            raise ValueError(
                "Unsupported normalizer_version "
                f"'{normalizer_version}'. Expected '{TRT_NORMALIZER_VERSION}'."
            )

        metadata = data.get("metadata", {})
        if not isinstance(metadata, dict):
            raise ValueError("Trace metadata field `metadata` must be an object")

        spec_name = data.get("spec_name")
        run_id = data.get("run_id")
        mode = data.get("mode")
        for key, value in {"spec_name": spec_name, "run_id": run_id, "mode": mode}.items():
            if value is not None and not isinstance(value, str):
                raise ValueError(f"Trace metadata field `{key}` must be a string when provided")

        return cls(
            schema_version=schema_version,
            normalizer_version=normalizer_version,
            spec_name=spec_name,
            run_id=run_id,
            mode=mode,
            metadata=metadata,
        )


@dataclass(slots=True)
class TrajectoryV03:
    """Portable execution trajectory bundle for Phase 1 platform ingestion."""

    meta: TraceMetaV03 = field(default_factory=TraceMetaV03)
    events: list[TraceEventV03] = field(default_factory=list)
    schema_version: str = TRT_TRACE_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        """Convert the trajectory bundle to a JSON-ready mapping."""

        return {
            "events": [event.to_dict() for event in self.events],
            "meta": self.meta.to_dict(),
            "schema_version": self.schema_version,
        }

    def to_json(self, *, indent: int | None = 2) -> str:
        """Serialize the trajectory bundle with deterministic key ordering."""

        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            ensure_ascii=True,
            indent=indent,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TrajectoryV03:
        """Construct a trajectory bundle from dictionary data."""

        schema_version = str(data.get("schema_version", TRT_TRACE_SCHEMA_VERSION))
        if schema_version != TRT_TRACE_SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported trajectory schema_version '{schema_version}'. Expected '{TRT_TRACE_SCHEMA_VERSION}'."
            )

        raw_meta = data.get("meta", {})
        if not isinstance(raw_meta, dict):
            raise ValueError("Trajectory JSON requires object field `meta`")

        raw_events = data.get("events", [])
        if not isinstance(raw_events, list):
            raise ValueError("Trajectory JSON requires list field `events`")

        return cls(
            schema_version=schema_version,
            meta=TraceMetaV03.from_dict(raw_meta),
            events=[TraceEventV03.from_dict(event) for event in raw_events],
        )

    @classmethod
    def from_json(cls, payload: str | bytes) -> TrajectoryV03:
        """Deserialize a trajectory bundle from a JSON string or bytes payload."""

        raw = json.loads(payload)
        if not isinstance(raw, dict):
            raise ValueError("Trajectory JSON payload must be an object")
        return cls.from_dict(raw)


__all__ = [
    "TRACE_EVENT_KINDS_V03",
    "EventKindV03",
    "TraceEventV03",
    "TraceMetaV03",
    "TrajectoryV03",
]
