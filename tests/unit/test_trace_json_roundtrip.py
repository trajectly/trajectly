"""Roundtrip coverage for portable trajectory JSON artifacts."""

from __future__ import annotations

from pathlib import Path

from trajectly.trace.io import read_trajectory_json, write_trajectory_json
from trajectly.trace.models import TraceEventV03, TraceMetaV03, TrajectoryV03


def _trajectory() -> TrajectoryV03:
    return TrajectoryV03(
        meta=TraceMetaV03(spec_name="demo", run_id="run-123", mode="record", metadata={"source": "sdk"}),
        events=[
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


def test_trajectory_json_roundtrip_preserves_meta_events_and_order(tmp_path: Path) -> None:
    trajectory = _trajectory()
    payload = trajectory.to_json()
    path = tmp_path / "trajectory.json"

    assert payload.index('{\n  "events"') == 0
    assert payload.index('\n  "meta"') > payload.index('\n  "events"')
    assert payload.rindex('\n  "schema_version"') > payload.index('\n  "meta"')

    restored = TrajectoryV03.from_json(payload)
    write_trajectory_json(path, trajectory)
    loaded = read_trajectory_json(path)

    assert restored.to_dict() == trajectory.to_dict()
    assert loaded.to_dict() == trajectory.to_dict()
    assert path.read_text(encoding="utf-8") == trajectory.to_json()


def test_trajectory_json_roundtrip_accepts_empty_events_with_default_meta() -> None:
    trajectory = TrajectoryV03.from_json('{"events": []}')

    assert trajectory.schema_version == "0.4"
    assert trajectory.meta.normalizer_version == "1"
    assert trajectory.events == []
