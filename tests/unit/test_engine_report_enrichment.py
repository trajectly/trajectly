from __future__ import annotations

from pathlib import Path

from trajectly.cli.engine import _build_determinism_diagnostics, _build_fixture_usage
from trajectly.core.canonical import sha256_of_data
from trajectly.core.events import TraceEvent, make_event
from trajectly.diff.models import DiffResult, Finding
from trajectly.fixtures import FixtureEntry, FixtureStore
from trajectly.specs import AgentSpec


def _event(seq: int, event_type: str, payload: dict[str, object]) -> TraceEvent:
    return make_event(
        event_type=event_type,
        seq=seq,
        run_id="run-1",
        rel_ms=seq,
        payload=payload,
    )


def test_build_fixture_usage_reports_consumed_and_exhausted(tmp_path: Path) -> None:
    tool_request = {"args": [1, 2], "kwargs": {}}
    llm_request = {"args": ["3"], "kwargs": {}}

    fixture_store = FixtureStore(
        entries=[
            FixtureEntry(
                kind="tool",
                name="add",
                input_payload=tool_request,
                input_hash=sha256_of_data(tool_request),
                output_payload={"output": 3, "error": None},
            ),
            FixtureEntry(
                kind="llm",
                name="mock:v1",
                input_payload=llm_request,
                input_hash=sha256_of_data(llm_request),
                output_payload={"response": "ok", "usage": {"total_tokens": 1}, "error": None},
            ),
        ]
    )

    fixture_path = tmp_path / "fixtures.json"
    fixture_store.save(fixture_path)

    events = [
        _event(1, "tool_called", {"tool_name": "add", "input": tool_request}),
        _event(2, "tool_returned", {"tool_name": "add", "output": 3, "error": None}),
        # Repeated call exceeds available fixture signatures.
        _event(3, "tool_called", {"tool_name": "add", "input": tool_request}),
        _event(4, "tool_returned", {"tool_name": "add", "output": 3, "error": None}),
        _event(
            5,
            "llm_called",
            {"provider": "mock", "model": "v1", "request": llm_request},
        ),
        _event(
            6,
            "llm_returned",
            {"provider": "mock", "model": "v1", "response": "ok", "usage": {"total_tokens": 1}, "error": None},
        ),
    ]

    usage = _build_fixture_usage(events, fixture_path)

    assert usage["summary"] == {"total": 2, "consumed": 2, "misses": 1, "exhausted": 1}
    assert len(usage["fixtures"]) == 3
    assert usage["fixtures"][0]["matched"] is True
    assert usage["fixtures"][1]["matched"] is False


def test_build_determinism_diagnostics_merges_runtime_and_config_signals(tmp_path: Path) -> None:
    spec = AgentSpec(
        name="diagnostics",
        command="python agent.py",
        source_path=tmp_path / "diagnostics.agent.yaml",
    )
    spec.determinism.clock.mode = "disabled"
    spec.determinism.random.mode = "disabled"
    spec.determinism.filesystem.mode = "permissive"
    spec.replay.mode = "online"

    warnings = [
        {
            "code": "NONDETERMINISM_RANDOM_DETECTED",
            "message": "NONDETERMINISM_RANDOM_DETECTED random module access detected",
        }
    ]

    diff_result = DiffResult(
        summary={
            "regression": True,
            "finding_count": 1,
            "classifications": {"network_runtime_error": 1},
            "baseline": {"duration_ms": 1, "tool_calls": 1, "tokens": 1},
            "current": {"duration_ms": 1, "tool_calls": 1, "tokens": 1},
        },
        findings=[Finding(classification="runtime_error", message="Network call observed during replay")],
    )

    diagnostics = _build_determinism_diagnostics(
        spec=spec,
        determinism_warnings=warnings,
        diff_result=diff_result,
    )

    assert any(row["category"] == "random" and row["detected"] is True for row in diagnostics)
    assert any(row["category"] == "network" and row["detected"] is True for row in diagnostics)
    # Config-only rows are still surfaced to explain replay guarantees.
    assert any(row["category"] == "time" and row["detected"] is False for row in diagnostics)
    assert any(row["category"] == "filesystem" and row["detected"] is False for row in diagnostics)
