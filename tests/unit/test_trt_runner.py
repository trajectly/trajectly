from __future__ import annotations

from pathlib import Path

from trajectly.events import make_event
from trajectly.specs import AgentSpec, ToolContracts
from trajectly.trt.runner import evaluate_trt


def _spec() -> AgentSpec:
    return AgentSpec(
        name="demo",
        command="python agent.py",
        source_path=Path("demo.agent.yaml"),
    )


def test_trt_runner_passes_when_contracts_and_refinement_hold() -> None:
    spec = _spec()
    spec.contracts.tools = ToolContracts(allow=["search", "checkout"])

    baseline = [
        make_event(
            event_type="tool_called",
            seq=1,
            run_id="r1",
            rel_ms=1,
            payload={"tool_name": "search", "input": {"args": [], "kwargs": {}}},
        ),
        make_event(
            event_type="tool_called",
            seq=2,
            run_id="r1",
            rel_ms=2,
            payload={"tool_name": "checkout", "input": {"args": [], "kwargs": {}}},
        ),
    ]
    current = [
        make_event(
            event_type="tool_called",
            seq=1,
            run_id="r2",
            rel_ms=1,
            payload={"tool_name": "search", "input": {"args": [], "kwargs": {}}},
        ),
        make_event(
            event_type="tool_called",
            seq=2,
            run_id="r2",
            rel_ms=2,
            payload={"tool_name": "checkout", "input": {"args": [], "kwargs": {}}},
        ),
    ]

    result = evaluate_trt(baseline_events=baseline, current_events=current, spec=spec)
    assert result.status == "PASS"
    assert result.report.status == "PASS"
    assert result.report.primary_violation is None


def test_trt_runner_prefers_refinement_primary_on_tied_witness() -> None:
    spec = _spec()
    spec.contracts.tools = ToolContracts(deny=["delete_account"])

    baseline = [
        make_event(
            event_type="tool_called",
            seq=1,
            run_id="r1",
            rel_ms=1,
            payload={"tool_name": "search", "input": {"args": [], "kwargs": {}}},
        ),
    ]
    current = [
        make_event(
            event_type="tool_called",
            seq=1,
            run_id="r2",
            rel_ms=1,
            payload={"tool_name": "search", "input": {"args": [], "kwargs": {}}},
        ),
        make_event(
            event_type="tool_called",
            seq=2,
            run_id="r2",
            rel_ms=2,
            payload={"tool_name": "delete_account", "input": {"args": [], "kwargs": {}}},
        ),
    ]

    result = evaluate_trt(
        baseline_events=baseline,
        current_events=current,
        spec=spec,
        repro_command="trajectly repro demo",
        counterexample_paths={"prefix": ".trajectly/repros/demo.prefix.trace.jsonl"},
    )

    assert result.status == "FAIL"
    assert result.report.witness_index == 1
    assert result.report.primary_violation is not None
    assert result.report.primary_violation.failure_class == "REFINEMENT"
    assert any(v.failure_class == "CONTRACT" for v in result.report.all_violations_at_witness)
    assert result.report.repro_command == "trajectly repro demo"
