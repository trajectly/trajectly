from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from trajectly.canonical import sha256_of_subset
from trajectly.constants import SCHEMA_VERSION, TRACE_EVENT_TYPES


@dataclass(slots=True)
class TraceEvent:
    event_type: str
    seq: int
    run_id: str
    rel_ms: int
    payload: dict[str, Any]
    meta: dict[str, Any] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION
    event_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "schema_version": self.schema_version,
            "event_type": self.event_type,
            "seq": self.seq,
            "run_id": self.run_id,
            "rel_ms": self.rel_ms,
            "payload": self.payload,
            "meta": self.meta,
        }
        if self.event_id:
            data["event_id"] = self.event_id
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TraceEvent:
        event_id = str(data.get("event_id", ""))
        event = cls(
            schema_version=str(data.get("schema_version", SCHEMA_VERSION)),
            event_type=str(data["event_type"]),
            seq=int(data["seq"]),
            run_id=str(data["run_id"]),
            rel_ms=int(data["rel_ms"]),
            payload=dict(data.get("payload", {})),
            meta=dict(data.get("meta", {})),
            event_id=event_id,
        )
        if not event.event_id:
            event.event_id = compute_event_id(event)
        return event


def compute_event_id(event: TraceEvent) -> str:
    payload = event.to_dict()
    return sha256_of_subset(payload, ignored_keys={"event_id", "rel_ms", "meta"})


def make_event(
    event_type: str,
    seq: int,
    run_id: str,
    rel_ms: int,
    payload: dict[str, Any],
    meta: dict[str, Any] | None = None,
) -> TraceEvent:
    if event_type not in TRACE_EVENT_TYPES:
        raise ValueError(f"Unsupported event type: {event_type}")
    event = TraceEvent(
        event_type=event_type,
        seq=seq,
        run_id=run_id,
        rel_ms=rel_ms,
        payload=payload,
        meta=meta or {},
    )
    event.event_id = compute_event_id(event)
    return event


def write_events_jsonl(path: Path, events: list[TraceEvent]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event.to_dict(), sort_keys=True, separators=(",", ":")))
            handle.write("\n")


def read_events_jsonl(path: Path) -> list[TraceEvent]:
    events: list[TraceEvent] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            events.append(TraceEvent.from_dict(json.loads(stripped)))
    return events
