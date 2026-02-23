"""Property-based invariant tests for TRT core theorems:
- Determinism: identical inputs → identical outputs
- Soundness: PASS ↔ zero violations
- Witness minimality: witness_index == min(event_index)
- Counterexample: prefix trace reproduces failure
"""

from __future__ import annotations

import random
from pathlib import Path

from trajectly.events import TraceEvent, make_event
from trajectly.specs import (
    AgentContracts,
    AgentSpec,
    SequenceContracts,
    ToolContracts,
)
from trajectly.trt.runner import evaluate_trt
from trajectly.trt.types import TRTViolation
from trajectly.trt.witness import resolve_witness

SEED = 42
NUM_TRIALS = 50


def _random_tool_events(rng: random.Random, n: int, tools: list[str]) -> list[TraceEvent]:
    events = []
    for i in range(n):
        events.append(
            make_event(
                event_type="tool_called",
                seq=i + 1,
                run_id="r1",
                rel_ms=i + 1,
                payload={
                    "tool_name": rng.choice(tools),
                    "input": {"args": [], "kwargs": {}},
                },
            )
        )
    return events


def _spec() -> AgentSpec:
    return AgentSpec(
        name="prop-test",
        command="python agent.py",
        source_path=Path("test.agent.yaml"),
    )


# ---------------------------------------------------------------------------
# Theorem 2: Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_evaluate_trt_deterministic_pass(self) -> None:
        spec = _spec()
        spec.contracts.tools = ToolContracts(allow=["search", "checkout"])
        baseline = _random_tool_events(random.Random(SEED), 5, ["search", "checkout"])
        current = _random_tool_events(random.Random(SEED), 5, ["search", "checkout"])

        r1 = evaluate_trt(baseline_events=baseline, current_events=current, spec=spec)
        r2 = evaluate_trt(baseline_events=baseline, current_events=current, spec=spec)

        assert r1.status == r2.status
        assert r1.report.status == r2.report.status
        assert len(r1.all_violations) == len(r2.all_violations)

    def test_evaluate_trt_deterministic_fail(self) -> None:
        spec = _spec()
        spec.contracts.tools = ToolContracts(deny=["dangerous"])
        baseline = _random_tool_events(random.Random(1), 3, ["search"])
        current = _random_tool_events(random.Random(2), 4, ["search", "dangerous"])

        results = [evaluate_trt(baseline_events=baseline, current_events=current, spec=spec) for _ in range(10)]
        statuses = {r.status for r in results}
        witness_indices = {r.witness.witness_index if r.witness else None for r in results}
        violation_counts = {len(r.all_violations) for r in results}

        assert len(statuses) == 1
        assert len(witness_indices) == 1
        assert len(violation_counts) == 1

    def test_many_random_inputs_deterministic(self) -> None:
        spec = _spec()
        spec.contracts = AgentContracts(
            tools=ToolContracts(deny=["evil"], max_calls_total=5),
            sequence=SequenceContracts(never=["tool:evil"]),
        )
        rng = random.Random(SEED)
        tools = ["search", "checkout", "evil", "log"]

        for trial in range(NUM_TRIALS):
            n_baseline = rng.randint(1, 6)
            n_current = rng.randint(1, 8)
            baseline = _random_tool_events(random.Random(trial), n_baseline, tools)
            current = _random_tool_events(random.Random(trial + 1000), n_current, tools)

            r1 = evaluate_trt(baseline_events=baseline, current_events=current, spec=spec)
            r2 = evaluate_trt(baseline_events=baseline, current_events=current, spec=spec)

            assert r1.status == r2.status, f"Trial {trial}: status mismatch"
            assert len(r1.all_violations) == len(r2.all_violations), f"Trial {trial}: violation count mismatch"
            if r1.witness and r2.witness:
                assert r1.witness.witness_index == r2.witness.witness_index, f"Trial {trial}: witness mismatch"


# ---------------------------------------------------------------------------
# Theorem 1: Soundness
# ---------------------------------------------------------------------------

class TestSoundness:
    def test_pass_implies_zero_violations(self) -> None:
        spec = _spec()
        spec.contracts.tools = ToolContracts(allow=["search", "checkout"])
        baseline = _random_tool_events(random.Random(SEED), 3, ["search", "checkout"])
        current = _random_tool_events(random.Random(SEED), 3, ["search", "checkout"])

        result = evaluate_trt(baseline_events=baseline, current_events=current, spec=spec)
        if result.status == "PASS":
            assert len(result.all_violations) == 0

    def test_fail_implies_nonzero_violations(self) -> None:
        spec = _spec()
        spec.contracts.tools = ToolContracts(deny=["dangerous"])
        baseline = [
            make_event(event_type="tool_called", seq=1, run_id="r1", rel_ms=1,
                       payload={"tool_name": "search", "input": {"args": [], "kwargs": {}}}),
        ]
        current = [
            make_event(event_type="tool_called", seq=1, run_id="r2", rel_ms=1,
                       payload={"tool_name": "dangerous", "input": {"args": [], "kwargs": {}}}),
        ]

        result = evaluate_trt(baseline_events=baseline, current_events=current, spec=spec)
        assert result.status == "FAIL"
        assert len(result.all_violations) > 0

    def test_soundness_many_random_traces(self) -> None:
        spec = _spec()
        spec.contracts = AgentContracts(
            tools=ToolContracts(deny=["evil"], max_calls_total=4),
        )
        rng = random.Random(SEED)
        tools = ["search", "checkout", "evil"]

        for trial in range(NUM_TRIALS):
            baseline = _random_tool_events(random.Random(trial), rng.randint(1, 5), tools)
            current = _random_tool_events(random.Random(trial + 500), rng.randint(1, 6), tools)
            result = evaluate_trt(baseline_events=baseline, current_events=current, spec=spec)

            if result.status == "PASS":
                assert len(result.all_violations) == 0, f"Trial {trial}: PASS with violations"
            else:
                assert len(result.all_violations) > 0, f"Trial {trial}: FAIL with zero violations"


# ---------------------------------------------------------------------------
# Theorem 3: Witness minimality
# ---------------------------------------------------------------------------

class TestWitnessMinimality:
    def test_witness_is_minimum_event_index(self) -> None:
        violations = [
            TRTViolation(code="A", message="", failure_class="CONTRACT", event_index=5),
            TRTViolation(code="B", message="", failure_class="REFINEMENT", event_index=2),
            TRTViolation(code="C", message="", failure_class="CONTRACT", event_index=8),
        ]
        witness = resolve_witness(violations)
        assert witness is not None
        assert witness.witness_index == 2

    def test_witness_minimality_random(self) -> None:
        rng = random.Random(SEED)
        for _ in range(NUM_TRIALS):
            n = rng.randint(1, 20)
            violations = [
                TRTViolation(
                    code=f"V{i}",
                    message="",
                    failure_class=rng.choice(["REFINEMENT", "CONTRACT", "TOOLING"]),
                    event_index=rng.randint(0, 100),
                )
                for i in range(n)
            ]
            witness = resolve_witness(violations)
            assert witness is not None
            expected_min = min(v.event_index for v in violations)
            assert witness.witness_index == expected_min

    def test_witness_tiebreak_deterministic(self) -> None:
        violations = [
            TRTViolation(code="CONTRACT_X", message="", failure_class="CONTRACT", event_index=3),
            TRTViolation(code="REFINEMENT_A", message="", failure_class="REFINEMENT", event_index=3),
            TRTViolation(code="CONTRACT_B", message="", failure_class="CONTRACT", event_index=3),
        ]
        w1 = resolve_witness(violations)
        w2 = resolve_witness(list(reversed(violations)))
        assert w1 is not None and w2 is not None
        assert w1.primary_violation.code == w2.primary_violation.code
        assert w1.primary_violation.failure_class == "REFINEMENT"

    def test_witness_empty_returns_none(self) -> None:
        assert resolve_witness([]) is None


# ---------------------------------------------------------------------------
# Theorem 4: Counterexample prefix sufficiency
# ---------------------------------------------------------------------------

class TestCounterexamplePrefix:
    def test_prefix_reproduces_failure(self) -> None:
        """Truncating the current trace to [0..witness_index] reproduces the primary violation."""
        spec = _spec()
        spec.contracts.tools = ToolContracts(deny=["evil"])
        baseline = [
            make_event(event_type="tool_called", seq=1, run_id="r1", rel_ms=1,
                       payload={"tool_name": "search", "input": {"args": [], "kwargs": {}}}),
        ]
        current = [
            make_event(event_type="tool_called", seq=1, run_id="r2", rel_ms=1,
                       payload={"tool_name": "search", "input": {"args": [], "kwargs": {}}}),
            make_event(event_type="tool_called", seq=2, run_id="r2", rel_ms=2,
                       payload={"tool_name": "evil", "input": {"args": [], "kwargs": {}}}),
            make_event(event_type="tool_called", seq=3, run_id="r2", rel_ms=3,
                       payload={"tool_name": "search", "input": {"args": [], "kwargs": {}}}),
        ]

        full_result = evaluate_trt(baseline_events=baseline, current_events=current, spec=spec)
        assert full_result.status == "FAIL"
        assert full_result.witness is not None

        k = full_result.witness.witness_index
        prefix = current[: k + 1]
        prefix_result = evaluate_trt(baseline_events=baseline, current_events=prefix, spec=spec)

        assert prefix_result.status == "FAIL"
        assert prefix_result.witness is not None
        assert any(
            v.code == full_result.witness.primary_violation.code
            for v in prefix_result.all_violations
        )

    def test_prefix_sufficiency_random(self) -> None:
        spec = _spec()
        spec.contracts = AgentContracts(
            tools=ToolContracts(deny=["evil"], max_calls_total=3),
        )
        rng = random.Random(SEED)
        tools = ["search", "evil", "checkout"]

        reproduced = 0
        for trial in range(NUM_TRIALS):
            baseline = _random_tool_events(random.Random(trial), rng.randint(1, 4), tools)
            current = _random_tool_events(random.Random(trial + 2000), rng.randint(2, 8), tools)

            full = evaluate_trt(baseline_events=baseline, current_events=current, spec=spec)
            if full.status != "FAIL" or full.witness is None:
                continue

            k = full.witness.witness_index
            prefix = current[: k + 1]
            prefix_result = evaluate_trt(baseline_events=baseline, current_events=prefix, spec=spec)

            assert prefix_result.status == "FAIL", f"Trial {trial}: prefix should still fail"
            reproduced += 1

        assert reproduced > 0, "Should have reproduced at least one failure"
