from __future__ import annotations

import json
from pathlib import Path

import pytest

from trajectly.fixtures import FixtureEntry, FixtureStore
from trajectly.sdk.context import SDKContext, SDKRuntimeError, _RuntimeContracts, _RuntimeSettings


def _read_events(path: Path) -> list[dict[str, object]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def test_sdk_context_record_mode_emits_events(tmp_path: Path) -> None:
    events_path = tmp_path / "events.jsonl"
    settings = _RuntimeSettings(
        mode="record",
        events_path=events_path,
        fixtures_path=None,
        fixture_policy="by_index",
        strict=False,
    )
    ctx = SDKContext(settings)

    tool_result = ctx.invoke_tool("add", lambda a, b: a + b, (2, 3), {})
    llm_result = ctx.invoke_llm(
        "mock",
        "v1",
        lambda text: {"response": f"ok:{text}", "usage": {"total_tokens": 7}},
        ("hello",),
        {},
    )

    events = _read_events(events_path)
    event_types = [event["event_type"] for event in events]

    assert tool_result == 5
    assert llm_result["response"] == "ok:hello"
    assert event_types == ["tool_called", "tool_returned", "llm_called", "llm_returned"]


def test_sdk_context_replay_mode_uses_fixtures_without_calling_function(tmp_path: Path) -> None:
    fixtures_path = tmp_path / "fixtures.json"
    events_path = tmp_path / "events.jsonl"

    store = FixtureStore(
        entries=[
            FixtureEntry(
                kind="tool",
                name="add",
                input_payload={"args": [2, 3], "kwargs": {}},
                input_hash="",
                output_payload={"output": 5, "error": None},
            ),
            FixtureEntry(
                kind="llm",
                name="mock:v1",
                input_payload={"args": ["hello"], "kwargs": {}},
                input_hash="",
                output_payload={
                    "response": "ok:hello",
                    "usage": {"total_tokens": 7},
                    "result": {"response": "ok:hello", "usage": {"total_tokens": 7}},
                    "error": None,
                },
            ),
        ]
    )

    # Recompute hashes through save/load path.
    normalized = FixtureStore.from_dict(store.to_dict())
    for entry in normalized.entries:
        from trajectly.canonical import sha256_of_data

        entry.input_hash = sha256_of_data(entry.input_payload)
    normalized.save(fixtures_path)

    settings = _RuntimeSettings(
        mode="replay",
        events_path=events_path,
        fixtures_path=fixtures_path,
        fixture_policy="by_hash",
        strict=True,
    )
    ctx = SDKContext(settings)

    def _should_not_run(*_args, **_kwargs):
        raise AssertionError("should not execute underlying function in replay mode")

    tool_result = ctx.invoke_tool("add", _should_not_run, (2, 3), {})
    llm_result = ctx.invoke_llm("mock", "v1", _should_not_run, ("hello",), {})

    events = _read_events(events_path)
    returned_events = [e for e in events if e["event_type"] in {"tool_returned", "llm_returned"}]

    assert tool_result == 5
    assert llm_result["response"] == "ok:hello"
    assert all(event["meta"].get("replayed") is True for event in returned_events)


def test_sdk_context_replay_strict_missing_fixture_raises(tmp_path: Path) -> None:
    fixtures_path = tmp_path / "fixtures.json"
    FixtureStore(entries=[]).save(fixtures_path)

    settings = _RuntimeSettings(
        mode="replay",
        events_path=tmp_path / "events.jsonl",
        fixtures_path=fixtures_path,
        fixture_policy="by_hash",
        strict=True,
    )
    ctx = SDKContext(settings)

    with pytest.raises(SDKRuntimeError, match="Missing fixture for tool call"):
        ctx.invoke_tool("missing", lambda: "nope", (), {})


def test_sdk_context_replay_fixture_exhausted_raises_stable_error(tmp_path: Path) -> None:
    fixtures_path = tmp_path / "fixtures.json"
    events_path = tmp_path / "events.jsonl"

    store = FixtureStore(
        entries=[
            FixtureEntry(
                kind="tool",
                name="add",
                input_payload={"args": [2, 3], "kwargs": {}},
                input_hash="",
                output_payload={"output": 5, "error": None},
            )
        ]
    )
    normalized = FixtureStore.from_dict(store.to_dict())
    for entry in normalized.entries:
        from trajectly.canonical import sha256_of_data

        entry.input_hash = sha256_of_data(entry.input_payload)
    normalized.save(fixtures_path)

    settings = _RuntimeSettings(
        mode="replay",
        events_path=events_path,
        fixtures_path=fixtures_path,
        fixture_policy="by_hash",
        strict=True,
    )
    ctx = SDKContext(settings)

    assert ctx.invoke_tool("add", lambda _a, _b: 99, (2, 3), {}) == 5
    with pytest.raises(SDKRuntimeError, match="FIXTURE_EXHAUSTED"):
        ctx.invoke_tool("add", lambda _a, _b: 99, (2, 3), {})

    events = _read_events(events_path)
    exhausted = [
        event
        for event in events
        if event["event_type"] == "tool_returned"
        and "FIXTURE_EXHAUSTED" in str(event["payload"].get("error", ""))
    ]
    assert exhausted
    payload = exhausted[-1]["payload"]
    assert payload["error_code"] == "FIXTURE_EXHAUSTED"
    assert payload["error_details"]["failure_class"] == "CONTRACT"


def test_sdk_context_contract_deny_raises_with_stable_error_code(tmp_path: Path) -> None:
    settings = _RuntimeSettings(
        mode="record",
        events_path=tmp_path / "events.jsonl",
        fixtures_path=None,
        fixture_policy="by_index",
        strict=False,
        contracts=_RuntimeContracts(tools_deny={"delete_account"}),
    )
    ctx = SDKContext(settings)

    with pytest.raises(SDKRuntimeError, match="CONTRACT_TOOL_DENIED"):
        ctx.invoke_tool("delete_account", lambda: "ok", (), {})


def test_sdk_context_contract_max_calls_total_raises(tmp_path: Path) -> None:
    settings = _RuntimeSettings(
        mode="record",
        events_path=tmp_path / "events.jsonl",
        fixtures_path=None,
        fixture_policy="by_index",
        strict=False,
        contracts=_RuntimeContracts(max_calls_total=1),
    )
    ctx = SDKContext(settings)

    assert ctx.invoke_tool("first", lambda: "ok", (), {}) == "ok"
    with pytest.raises(SDKRuntimeError, match="CONTRACT_MAX_CALLS_TOTAL_EXCEEDED"):
        ctx.invoke_tool("second", lambda: "boom", (), {})


def test_sdk_context_emits_v03_trace_when_trace_paths_provided(tmp_path: Path) -> None:
    events_path = tmp_path / "events.jsonl"
    trace_path = tmp_path / "events.trace.jsonl"
    trace_meta_path = tmp_path / "events.trace.meta.json"
    settings = _RuntimeSettings(
        mode="record",
        events_path=events_path,
        fixtures_path=None,
        fixture_policy="by_index",
        strict=False,
        trace_path=trace_path,
        trace_meta_path=trace_meta_path,
        spec_name="demo-spec",
    )
    ctx = SDKContext(settings)

    ctx.agent_step("start")
    _ = ctx.invoke_tool("add", lambda a, b: a + b, (1, 2), {})

    raw_meta = json.loads(trace_meta_path.read_text(encoding="utf-8"))
    trace_lines = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    assert raw_meta["schema_version"] == "0.3"
    assert raw_meta["normalizer_version"] == "1"
    assert trace_lines[0]["kind"] == "MESSAGE"
    assert trace_lines[1]["kind"] == "TOOL_CALL"
    assert trace_lines[2]["kind"] == "TOOL_RESULT"
