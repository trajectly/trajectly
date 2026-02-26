"""Deterministic witness selection: same inputs always produce the same witness_index + primary violation."""
from __future__ import annotations

from trajectly.core.trt.types import TRTViolation
from trajectly.core.trt.witness import resolve_witness


def _make_violation(
    code: str, event_index: int, failure_class: str = "CONTRACT", message: str = ""
) -> TRTViolation:
    return TRTViolation(
        code=code,
        message=message or f"{code} at {event_index}",
        failure_class=failure_class,
        event_index=event_index,
    )


class TestDeterministicWitnessSelection:
    def test_single_violation(self) -> None:
        violations = [_make_violation("CONTRACT_TOOL_DENIED", event_index=5)]
        result = resolve_witness(violations)
        assert result.witness_index == 5
        assert result.primary_violation.code == "CONTRACT_TOOL_DENIED"

    def test_multiple_violations_picks_earliest(self) -> None:
        violations = [
            _make_violation("REFINEMENT_EXTRA_TOOL_CALL", event_index=10),
            _make_violation("CONTRACT_TOOL_DENIED", event_index=3),
            _make_violation("CONTRACT_BUDGET_EXCEEDED", event_index=7),
        ]
        result = resolve_witness(violations)
        assert result.witness_index == 3
        assert result.primary_violation.code == "CONTRACT_TOOL_DENIED"

    def test_tie_break_is_stable_across_orderings(self) -> None:
        v_a = _make_violation("REFINEMENT_BASELINE_CALL_MISSING", event_index=5, failure_class="REFINEMENT")
        v_b = _make_violation("CONTRACT_TOOL_DENIED", event_index=5, failure_class="CONTRACT")

        result_ab = resolve_witness([v_a, v_b])
        result_ba = resolve_witness([v_b, v_a])

        assert result_ab.witness_index == result_ba.witness_index == 5
        assert result_ab.primary_violation.code == result_ba.primary_violation.code

    def test_repeated_calls_produce_identical_results(self) -> None:
        violations = [
            _make_violation("CONTRACT_TOOL_DENIED", event_index=2),
            _make_violation("REFINEMENT_EXTRA_TOOL_CALL", event_index=2, failure_class="REFINEMENT"),
            _make_violation("CONTRACT_BUDGET_EXCEEDED", event_index=8),
        ]
        results = [resolve_witness(violations) for _ in range(10)]
        assert all(r.witness_index == results[0].witness_index for r in results)
        assert all(r.primary_violation.code == results[0].primary_violation.code for r in results)

    def test_all_violations_at_witness_collected(self) -> None:
        violations = [
            _make_violation("CONTRACT_TOOL_DENIED", event_index=4),
            _make_violation("CONTRACT_BUDGET_EXCEEDED", event_index=4),
            _make_violation("REFINEMENT_EXTRA_TOOL_CALL", event_index=10, failure_class="REFINEMENT"),
        ]
        result = resolve_witness(violations)
        assert result.witness_index == 4
        assert len(result.all_violations_at_witness) == 2
        at_witness_codes = {v.code for v in result.all_violations_at_witness}
        assert at_witness_codes == {"CONTRACT_TOOL_DENIED", "CONTRACT_BUDGET_EXCEEDED"}
