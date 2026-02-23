from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from trajectly.trace.models import TraceEventV03, TraceMetaV03
from trajectly.trace.validate import validate_trace_event_v03, validate_trace_meta_v03


def append_trace_event(path: Path, event: TraceEventV03 | dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = event.to_dict() if isinstance(event, TraceEventV03) else event
    validated = validate_trace_event_v03(raw)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(validated, sort_keys=True, separators=(",", ":"), ensure_ascii=True))
        handle.write("\n")


def write_trace_events(path: Path, events: list[TraceEventV03 | dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for event in events:
            raw = event.to_dict() if isinstance(event, TraceEventV03) else event
            validated = validate_trace_event_v03(raw)
            handle.write(json.dumps(validated, sort_keys=True, separators=(",", ":"), ensure_ascii=True))
            handle.write("\n")


def read_trace_events(path: Path) -> list[TraceEventV03]:
    rows: list[TraceEventV03] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            validated = validate_trace_event_v03(json.loads(stripped))
            rows.append(TraceEventV03(**validated))
    return rows


def write_trace_meta(path: Path, meta: TraceMetaV03 | dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = meta.to_dict() if isinstance(meta, TraceMetaV03) else meta
    validated = validate_trace_meta_v03(raw)
    path.write_text(json.dumps(validated, sort_keys=True, indent=2), encoding="utf-8")


def read_trace_meta(path: Path) -> TraceMetaV03:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Trace meta payload must be an object")
    validated = validate_trace_meta_v03(raw)
    return TraceMetaV03(
        schema_version=str(validated["schema_version"]),
        normalizer_version=str(validated["normalizer_version"]),
        spec_name=validated.get("spec_name"),
        run_id=validated.get("run_id"),
        mode=validated.get("mode"),
        metadata=dict(validated.get("metadata", {})),
    )


__all__ = [
    "append_trace_event",
    "read_trace_events",
    "read_trace_meta",
    "write_trace_events",
    "write_trace_meta",
]
