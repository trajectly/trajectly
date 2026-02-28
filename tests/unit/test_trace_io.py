from __future__ import annotations

import json
from pathlib import Path

import pytest

from trajectly.trace.io import append_trace_event, read_trace_events, read_trace_meta, write_trace_meta
from trajectly.trace.models import TraceEventV03, TraceMetaV03
from trajectly.trace.validate import TraceValidationError


def test_trace_io_round_trip_for_events_and_meta(tmp_path: Path) -> None:
    trace_path = tmp_path / "demo.trace.jsonl"
    meta_path = tmp_path / "demo.trace.meta.json"

    write_trace_meta(meta_path, TraceMetaV03(spec_name="demo", mode="record"))
    append_trace_event(
        trace_path,
        TraceEventV03(
            event_index=0,
            kind="TOOL_CALL",
            payload={"tool_name": "search", "args": {"q": "laptop"}},
            stable_hash="abc",
        ),
    )
    append_trace_event(
        trace_path,
        TraceEventV03(
            event_index=1,
            kind="TOOL_RESULT",
            payload={"tool_name": "search", "result": ["r1"]},
            stable_hash="def",
        ),
    )

    loaded_meta = read_trace_meta(meta_path)
    loaded_events = read_trace_events(trace_path)

    assert loaded_meta.normalizer_version == "1"
    assert loaded_meta.schema_version == "0.4"
    assert len(loaded_events) == 2
    assert loaded_events[0].event_index == 0
    assert loaded_events[1].kind == "TOOL_RESULT"


def test_trace_meta_reader_rejects_wrong_normalizer_version(tmp_path: Path) -> None:
    meta_path = tmp_path / "bad.trace.meta.json"
    meta_path.write_text(
        json.dumps(
            {
                "schema_version": "0.4",
                "normalizer_version": "999",
                "metadata": {},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(TraceValidationError, match="Unsupported normalizer_version"):
        read_trace_meta(meta_path)
