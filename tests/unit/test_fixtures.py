from __future__ import annotations

from trajectly.events import make_event
from trajectly.fixtures import FixtureMatcher, FixtureStore


def _sample_events() -> list:
    run_id = "run-1"
    return [
        make_event(
            event_type="tool_called",
            seq=1,
            run_id=run_id,
            rel_ms=1,
            payload={"tool_name": "add", "input": {"args": [1, 2], "kwargs": {}}},
        ),
        make_event(
            event_type="tool_returned",
            seq=2,
            run_id=run_id,
            rel_ms=2,
            payload={"tool_name": "add", "output": 3, "error": None},
        ),
        make_event(
            event_type="tool_called",
            seq=3,
            run_id=run_id,
            rel_ms=3,
            payload={"tool_name": "add", "input": {"args": [4, 5], "kwargs": {}}},
        ),
        make_event(
            event_type="tool_returned",
            seq=4,
            run_id=run_id,
            rel_ms=4,
            payload={"tool_name": "add", "output": 9, "error": None},
        ),
    ]


def test_fixture_matcher_by_index() -> None:
    store = FixtureStore.from_events(_sample_events())
    matcher = FixtureMatcher(store=store, policy="by_index", strict=False)
    first = matcher.match("tool", "add", {"args": [1, 2], "kwargs": {}})
    second = matcher.match("tool", "add", {"args": [4, 5], "kwargs": {}})
    assert first is not None
    assert second is not None
    assert first.output_payload["output"] == 3
    assert second.output_payload["output"] == 9


def test_fixture_matcher_by_hash() -> None:
    store = FixtureStore.from_events(_sample_events())
    matcher = FixtureMatcher(store=store, policy="by_hash", strict=False)
    second = matcher.match("tool", "add", {"args": [4, 5], "kwargs": {}})
    first = matcher.match("tool", "add", {"args": [1, 2], "kwargs": {}})
    assert first is not None
    assert second is not None
    assert first.output_payload["output"] == 3
    assert second.output_payload["output"] == 9
