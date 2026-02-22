from __future__ import annotations

from pathlib import Path

import pytest

from trajectly.events import make_event, read_events_jsonl, write_events_jsonl


def test_make_event_id_ignores_rel_ms_and_meta() -> None:
    first = make_event(
        event_type="tool_called",
        seq=1,
        run_id="run-a",
        rel_ms=10,
        payload={"tool_name": "add", "input": {"args": [1, 2], "kwargs": {}}},
        meta={"source": "a"},
    )
    second = make_event(
        event_type="tool_called",
        seq=1,
        run_id="run-a",
        rel_ms=999,
        payload={"tool_name": "add", "input": {"args": [1, 2], "kwargs": {}}},
        meta={"source": "b"},
    )

    assert first.event_id == second.event_id


def test_events_jsonl_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "trace.jsonl"
    events = [
        make_event(
            event_type="run_started",
            seq=1,
            run_id="run-1",
            rel_ms=0,
            payload={"spec": "demo"},
        ),
        make_event(
            event_type="run_finished",
            seq=2,
            run_id="run-1",
            rel_ms=12,
            payload={"returncode": 0, "duration_ms": 12},
        ),
    ]

    write_events_jsonl(path, events)
    loaded = read_events_jsonl(path)

    assert len(loaded) == 2
    assert loaded[0].event_type == "run_started"
    assert loaded[1].payload["duration_ms"] == 12
    assert loaded[0].event_id == events[0].event_id


def test_make_event_rejects_unknown_type() -> None:
    with pytest.raises(ValueError, match="Unsupported event type"):
        make_event(
            event_type="unknown",
            seq=1,
            run_id="run-1",
            rel_ms=0,
            payload={},
        )
