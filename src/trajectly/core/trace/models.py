from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

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
    event_index: int
    kind: EventKindV03
    payload: dict[str, Any]
    stable_hash: str
    schema_version: str = TRT_TRACE_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "event_index": self.event_index,
            "kind": self.kind,
            "payload": self.payload,
            "stable_hash": self.stable_hash,
        }


@dataclass(slots=True)
class TraceMetaV03:
    schema_version: str = TRT_TRACE_SCHEMA_VERSION
    normalizer_version: str = TRT_NORMALIZER_VERSION
    spec_name: str | None = None
    run_id: str | None = None
    mode: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
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


__all__ = [
    "TRACE_EVENT_KINDS_V03",
    "EventKindV03",
    "TraceEventV03",
    "TraceMetaV03",
]
