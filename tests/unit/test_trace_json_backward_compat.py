"""Backward-compatibility coverage for portable trajectory JSON."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from trajectly.schema import SchemaValidationError
from trajectly.trace.io import read_legacy_trajectory, read_trajectory_json, write_trace_events, write_trace_meta
from trajectly.trace.models import TraceEventV03, TraceMetaV03, TrajectoryV03


def test_legacy_trace_artifacts_can_be_lifted_into_portable_json(tmp_path: Path) -> None:
    trace_path = tmp_path / "demo.trace.jsonl"
    meta_path = tmp_path / "demo.trace.meta.json"
    write_trace_meta(meta_path, TraceMetaV03(spec_name="legacy-demo", mode="record"))
    write_trace_events(
        trace_path,
        [
            TraceEventV03(
                event_index=0,
                kind="TOOL_CALL",
                payload={"tool_name": "search", "args": {"q": "laptop"}},
                stable_hash="abc123",
            ),
            TraceEventV03(
                event_index=1,
                kind="TOOL_RESULT",
                payload={"tool_name": "search", "result": ["r1"]},
                stable_hash="def456",
            ),
        ],
    )

    trajectory = read_legacy_trajectory(trace_path)
    restored = TrajectoryV03.from_json(trajectory.to_json())

    assert trajectory.meta.spec_name == "legacy-demo"
    assert [event.kind for event in trajectory.events] == ["TOOL_CALL", "TOOL_RESULT"]
    assert restored.to_dict() == trajectory.to_dict()


def test_trajectory_json_reader_rejects_invalid_event_payloads(tmp_path: Path) -> None:
    path = tmp_path / "bad-trajectory.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "0.4",
                "meta": {"schema_version": "0.4", "normalizer_version": "1", "metadata": {}},
                "events": [
                    {
                        "schema_version": "0.4",
                        "event_index": -1,
                        "kind": "TOOL_CALL",
                        "payload": {},
                        "stable_hash": "abc123",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(SchemaValidationError, match="Trace event requires non-negative integer `event_index`"):
        read_trajectory_json(path)
