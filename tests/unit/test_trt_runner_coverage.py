"""Expanded TRT runner tests: FIXTURE_EXHAUSTED, _event_index_from_finding
branches, vacuous refinement, combined multi-witness."""

from __future__ import annotations

from pathlib import Path

from trajectly.events import make_event
from trajectly.specs import AgentContracts, AgentSpec, SequenceContracts, ToolContracts
from trajectly.trt.runner import _event_index_from_finding, evaluate_trt


def _spec(**overrides: object) -> AgentSpec:
    defaults: dict = {
        "name": "demo",
        "command": "python agent.py",
        "source_path": Path("demo.agent.yaml"),
    }
    defaults.update(overrides)
    return AgentSpec(**defaults)


# ---------------------------------------------------------------------------
# FIXTURE_EXHAUSTED handling
# ---------------------------------------------------------------------------

def test_fixture_exhausted_in_tool_returned() -> None:
    spec = _spec()
    baseline = [
        make_event(event_type="tool_called", seq=1, run_id="r1", rel_ms=1,
                   payload={"tool_name": "search", "input": {"args": [], "kwargs": {}}}),
    ]
    current = [
        make_event(event_type="tool_called", seq=1, run_id="r2", rel_ms=1,
                   payload={"tool_name": "search", "input": {"args": [], "kwargs": {}}}),
        make_event(event_type="tool_returned", seq=2, run_id="r2", rel_ms=2,
                   payload={
                       "tool_name": "search",
                       "error_code": "FIXTURE_EXHAUSTED",
                       "error": "No more fixtures for search",
                       "error_details": {
                           "expected_signature": "abc123",
                           "available_count": 1,
                           "consumed_count": 2,
                           "tool_name": "search",
                       },
                   }),
    ]
    result = evaluate_trt(baseline_events=baseline, current_events=current, spec=spec)
    assert result.status == "FAIL"
    fixture_violations = [v for v in result.contract_violations if v.code == "FIXTURE_EXHAUSTED"]
    assert len(fixture_violations) == 1
    assert fixture_violations[0].event_index == 1
    assert fixture_violations[0].expected["expected_signature"] == "abc123"
    assert fixture_violations[0].observed["consumed_count"] == 2


def test_fixture_exhausted_in_llm_returned() -> None:
    spec = _spec()
    baseline = [
        make_event(event_type="llm_called", seq=1, run_id="r1", rel_ms=1,
                   payload={"provider": "openai", "model": "gpt-4"}),
    ]
    current = [
        make_event(event_type="llm_called", seq=1, run_id="r2", rel_ms=1,
                   payload={"provider": "openai", "model": "gpt-4"}),
        make_event(event_type="llm_returned", seq=2, run_id="r2", rel_ms=2,
                   payload={
                       "error_code": "FIXTURE_EXHAUSTED",
                       "error": "No more LLM fixtures",
                       "error_details": {
                           "llm_signature": "openai/gpt-4",
                           "available_count": 0,
                           "consumed_count": 1,
                       },
                   }),
    ]
    result = evaluate_trt(baseline_events=baseline, current_events=current, spec=spec)
    fixture_violations = [v for v in result.contract_violations if v.code == "FIXTURE_EXHAUSTED"]
    assert len(fixture_violations) == 1
    assert fixture_violations[0].observed["llm_signature"] == "openai/gpt-4"


# ---------------------------------------------------------------------------
# _event_index_from_finding branches
# ---------------------------------------------------------------------------

def test_event_index_from_finding_no_path() -> None:
    idx = _event_index_from_finding(
        path=None,
        baseline=None,
        call_tokens=[],
        operations=[],
        fallback_index=99,
    )
    assert idx == 99


def test_event_index_from_finding_tool_calls_index() -> None:
    call_tokens = [(10, "search"), (20, "checkout")]
    idx = _event_index_from_finding(
        path="$.tool_calls[1]",
        baseline=None,
        call_tokens=call_tokens,
        operations=[],
        fallback_index=0,
    )
    assert idx == 20


def test_event_index_from_finding_tool_calls_index_oob() -> None:
    call_tokens = [(10, "search")]
    idx = _event_index_from_finding(
        path="$.tool_calls[5]",
        baseline=None,
        call_tokens=call_tokens,
        operations=[],
        fallback_index=99,
    )
    assert idx == 99


def test_event_index_from_finding_operations_index() -> None:
    operations = [(5, "tool:search"), (10, "llm:openai:gpt-4"), (15, "step:done")]
    idx = _event_index_from_finding(
        path="$.operations[2]",
        baseline=None,
        call_tokens=[],
        operations=operations,
        fallback_index=0,
    )
    assert idx == 15


def test_event_index_from_finding_operations_oob() -> None:
    operations = [(5, "tool:search")]
    idx = _event_index_from_finding(
        path="$.operations[10]",
        baseline=None,
        call_tokens=operations,
        operations=operations,
        fallback_index=42,
    )
    assert idx == 42


def test_event_index_from_finding_tool_call_name() -> None:
    call_tokens = [(10, "search"), (20, "checkout")]
    idx = _event_index_from_finding(
        path="$.tool_call.checkout.fields.price",
        baseline=None,
        call_tokens=call_tokens,
        operations=[],
        fallback_index=0,
    )
    assert idx == 20


def test_event_index_from_finding_tool_call_name_not_found() -> None:
    call_tokens = [(10, "search")]
    idx = _event_index_from_finding(
        path="$.tool_call.missing_tool.fields.x",
        baseline=None,
        call_tokens=call_tokens,
        operations=[],
        fallback_index=77,
    )
    assert idx == 77


def test_event_index_from_finding_per_tool_match() -> None:
    call_tokens = [(5, "refund"), (10, "refund"), (15, "refund")]
    idx = _event_index_from_finding(
        path="$.tool_calls.refund",
        baseline=1,
        call_tokens=call_tokens,
        operations=[],
        fallback_index=0,
    )
    assert idx == 10


def test_event_index_from_finding_per_tool_no_baseline_index() -> None:
    call_tokens = [(5, "refund"), (10, "refund")]
    idx = _event_index_from_finding(
        path="$.tool_calls.refund",
        baseline="not-an-int",
        call_tokens=call_tokens,
        operations=[],
        fallback_index=0,
    )
    assert idx == 10


def test_event_index_from_finding_per_tool_not_found() -> None:
    call_tokens = [(5, "search")]
    idx = _event_index_from_finding(
        path="$.tool_calls.missing",
        baseline=0,
        call_tokens=call_tokens,
        operations=[],
        fallback_index=88,
    )
    assert idx == 88


# ---------------------------------------------------------------------------
# Vacuous refinement (empty baseline)
# ---------------------------------------------------------------------------

def test_vacuous_refinement_metadata() -> None:
    spec = _spec()
    baseline: list = []
    current = [
        make_event(event_type="tool_called", seq=1, run_id="r2", rel_ms=1,
                   payload={"tool_name": "anything", "input": {"args": [], "kwargs": {}}}),
    ]
    result = evaluate_trt(baseline_events=baseline, current_events=current, spec=spec)
    assert result.status == "PASS"
    assert result.report.metadata.metadata["refinement_skeleton_vacuous"] is True


# ---------------------------------------------------------------------------
# Combined contract + refinement multi-witness
# ---------------------------------------------------------------------------

def test_multi_witness_contract_and_refinement() -> None:
    spec = _spec()
    spec.contracts = AgentContracts(
        tools=ToolContracts(deny=["forbidden_tool"]),
        sequence=SequenceContracts(never=["tool:forbidden_tool"]),
    )
    baseline = [
        make_event(event_type="tool_called", seq=1, run_id="r1", rel_ms=1,
                   payload={"tool_name": "search", "input": {"args": [], "kwargs": {}}}),
    ]
    current = [
        make_event(event_type="tool_called", seq=1, run_id="r2", rel_ms=1,
                   payload={"tool_name": "search", "input": {"args": [], "kwargs": {}}}),
        make_event(event_type="tool_called", seq=2, run_id="r2", rel_ms=2,
                   payload={"tool_name": "forbidden_tool", "input": {"args": [], "kwargs": {}}}),
    ]
    result = evaluate_trt(baseline_events=baseline, current_events=current, spec=spec)
    assert result.status == "FAIL"
    assert result.witness is not None
    assert len(result.all_violations) >= 3
    assert result.witness.primary_violation.failure_class == "REFINEMENT"
