from __future__ import annotations

from trajectly.abstraction import AbstractionConfig, build_abstract_trace
from trajectly.events import make_event


def test_abstraction_builds_tokens_and_predicates() -> None:
    events = [
        make_event(
            event_type="tool_called",
            seq=1,
            run_id="r1",
            rel_ms=1,
            payload={
                "tool_name": "web_search",
                "input": {"args": ["contact me at test@example.com via https://api.example.com"], "kwargs": {}},
            },
        ),
        make_event(
            event_type="tool_returned",
            seq=2,
            run_id="r1",
            rel_ms=2,
            payload={"tool_name": "web_search", "output": {"price": 19.99}, "error": None},
        ),
    ]

    abstract = build_abstract_trace(events, config=AbstractionConfig())

    assert len(abstract.tokens) == 2
    assert abstract.tokens[0].kind == "CALL"
    assert abstract.predicates["tool_calls_total"] == 1
    assert abstract.predicates["tool_calls_by_name"] == {"web_search": 1}
    assert abstract.predicates["pii"]["email"] is True
    assert "api.example.com" in abstract.predicates["domains"]
    assert abstract.predicates["max_numeric_value"] == 19.99


def test_abstraction_respects_ignore_call_tools() -> None:
    events = [
        make_event(
            event_type="tool_called",
            seq=1,
            run_id="r1",
            rel_ms=1,
            payload={"tool_name": "log_event", "input": {"args": [], "kwargs": {}}},
        ),
        make_event(
            event_type="tool_called",
            seq=2,
            run_id="r1",
            rel_ms=2,
            payload={"tool_name": "checkout", "input": {"args": [], "kwargs": {}}},
        ),
    ]

    abstract = build_abstract_trace(
        events,
        config=AbstractionConfig(ignore_call_tools=["log_event"]),
    )

    call_names = [token.name for token in abstract.tokens if token.kind == "CALL"]
    assert call_names == ["checkout"]
