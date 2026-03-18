"""Unit tests for the stable core evaluation API."""

from __future__ import annotations

from pathlib import Path

import pytest

from trajectly.core import Trajectory, Verdict, Violation, evaluate
from trajectly.events import TraceEvent, make_event
from trajectly.specs import AgentSpec, ToolContracts


def _event(tool_name: str, *, seq: int = 1, run_id: str = "run") -> TraceEvent:
    return make_event(
        event_type="tool_called",
        seq=seq,
        run_id=run_id,
        rel_ms=seq,
        payload={"tool_name": tool_name, "input": {"args": [], "kwargs": {}}},
    )


def _spec() -> AgentSpec:
    return AgentSpec(
        name="demo",
        command="python agent.py",
        source_path=Path("demo.agent.yaml"),
    )


def test_evaluate_returns_pass_verdict_for_allowed_trajectory() -> None:
    spec = _spec()
    spec.contracts.tools = ToolContracts(allow=["search"])

    verdict = evaluate(Trajectory(events=[_event("search")]), spec)

    assert isinstance(verdict, Verdict)
    assert verdict.passed is True
    assert verdict.status == "PASS"
    assert verdict.violations == ()
    assert verdict.primary_violation is None
    assert verdict.to_dict()["passed"] is True


def test_evaluate_returns_fail_verdict_with_stable_violation_payload() -> None:
    spec = _spec()
    spec.contracts.tools = ToolContracts(deny=["delete_account"])

    verdict = evaluate([_event("delete_account")], spec)

    assert verdict.status == "FAIL"
    assert verdict.witness_index == 0
    assert verdict.primary_violation is not None
    assert isinstance(verdict.primary_violation, Violation)
    assert verdict.primary_violation.code == "CONTRACT_TOOL_DENIED"
    assert verdict.primary_violation.failure_class == "CONTRACT"
    assert verdict.violations[0].to_dict()["code"] == "CONTRACT_TOOL_DENIED"


def test_evaluate_signature_and_validation_errors_are_stable() -> None:
    spec = _spec()

    with pytest.raises(TypeError, match="trajectory must be"):
        evaluate(trajectory={"events": []}, spec=spec)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="spec must be"):
        evaluate(trajectory=[_event("search")], spec=object())  # type: ignore[arg-type]


def test_trajectory_rejects_non_trace_event_items() -> None:
    with pytest.raises(TypeError, match=r"trajectory.events\[0\]"):
        Trajectory(events=["not-an-event"])  # type: ignore[list-item]
