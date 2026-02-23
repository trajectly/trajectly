from __future__ import annotations

import pytest

from trajectly.events import TraceEvent
from trajectly.shrink import ddmin_shrink


def _event(event_type: str, seq: int) -> TraceEvent:
    return TraceEvent(
        event_type=event_type,
        seq=seq,
        run_id="r1",
        rel_ms=seq,
        payload={},
    )


def test_ddmin_shrink_reduces_while_preserving_failure_predicate() -> None:
    events = [
        _event("run_started", 1),
        _event("agent_step", 2),
        _event("tool_called", 3),
        _event("tool_returned", 4),
        _event("agent_step", 5),
        _event("run_finished", 6),
    ]

    def failure_predicate(candidate: list[TraceEvent]) -> bool:
        return any(event.event_type == "tool_called" for event in candidate)

    result = ddmin_shrink(
        events=events,
        failure_predicate=failure_predicate,
        max_seconds=2.0,
        max_iterations=100,
    )

    assert result.original_len == len(events)
    assert result.reduced_len < len(events)
    assert any(event.event_type == "tool_called" for event in result.reduced_events)
    assert result.iterations > 0


def test_ddmin_shrink_rejects_non_failing_input() -> None:
    events = [_event("run_started", 1), _event("run_finished", 2)]

    with pytest.raises(ValueError, match="failure_predicate must hold"):
        ddmin_shrink(
            events=events,
            failure_predicate=lambda _candidate: False,
            max_seconds=1.0,
            max_iterations=10,
        )
