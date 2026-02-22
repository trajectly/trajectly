from __future__ import annotations

from trajectly.diff.engine import compare_traces
from trajectly.events import make_event
from trajectly.specs import BudgetThresholds


def _event(event_type: str, seq: int, payload: dict[str, object], rel_ms: int = 0):
    return make_event(
        event_type=event_type,
        seq=seq,
        run_id="run",
        rel_ms=rel_ms,
        payload=payload,
    )


def test_compare_traces_detects_sequence_and_structural_mismatches() -> None:
    baseline = [
        _event("tool_called", 1, {"tool_name": "add", "input": {"args": [1, 2], "kwargs": {}}}),
        _event("tool_returned", 2, {"tool_name": "add", "output": 3, "error": None}),
        _event("run_finished", 3, {"duration_ms": 10, "returncode": 0}),
    ]
    current = [
        _event("tool_called", 1, {"tool_name": "add", "input": {"args": [1, 2], "kwargs": {}}}),
        _event("tool_returned", 2, {"tool_name": "add", "output": 4, "error": None}),
        _event("tool_called", 3, {"tool_name": "extra", "input": {"args": [], "kwargs": {}}}),
        _event("run_finished", 4, {"duration_ms": 12, "returncode": 0}),
    ]

    result = compare_traces(baseline, current)

    classes = [finding.classification for finding in result.findings]
    assert "sequence_mismatch" in classes
    assert "structural_mismatch" in classes
    assert result.summary["regression"] is True


def test_compare_traces_detects_budget_breaches() -> None:
    baseline = [
        _event("llm_returned", 1, {"usage": {"total_tokens": 5}, "provider": "mock", "model": "m"}),
        _event("run_finished", 2, {"duration_ms": 10, "returncode": 0}),
    ]
    current = [
        _event("tool_called", 1, {"tool_name": "a", "input": {"args": [], "kwargs": {}}}),
        _event("tool_called", 2, {"tool_name": "b", "input": {"args": [], "kwargs": {}}}),
        _event("llm_returned", 3, {"usage": {"total_tokens": 50}, "provider": "mock", "model": "m"}),
        _event("run_finished", 4, {"duration_ms": 500, "returncode": 0}),
    ]

    budgets = BudgetThresholds(max_latency_ms=20, max_tool_calls=1, max_tokens=10)
    result = compare_traces(baseline, current, budgets=budgets)

    budget_findings = [finding for finding in result.findings if finding.classification == "budget_breach"]
    assert len(budget_findings) == 3
    assert result.summary["current"]["duration_ms"] == 500
    assert result.summary["current"]["tool_calls"] == 2
    assert result.summary["current"]["tokens"] == 50
