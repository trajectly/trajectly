from __future__ import annotations

from trajectly.constants import FAILURE_CLASS_CONTRACT, FAILURE_CLASS_REFINEMENT
from trajectly.trt.types import TRTViolation
from trajectly.trt.witness import resolve_witness


def test_resolve_witness_prefers_earliest_index_then_refinement_then_lexical_code() -> None:
    violations = [
        TRTViolation(
            code="CONTRACT_Z",
            message="contract issue",
            failure_class=FAILURE_CLASS_CONTRACT,
            event_index=3,
        ),
        TRTViolation(
            code="REFINEMENT_B",
            message="refinement issue b",
            failure_class=FAILURE_CLASS_REFINEMENT,
            event_index=3,
        ),
        TRTViolation(
            code="REFINEMENT_A",
            message="refinement issue a",
            failure_class=FAILURE_CLASS_REFINEMENT,
            event_index=3,
        ),
        TRTViolation(
            code="CONTRACT_EARLY",
            message="early contract issue",
            failure_class=FAILURE_CLASS_CONTRACT,
            event_index=1,
        ),
    ]

    witness = resolve_witness(violations)
    assert witness is not None
    assert witness.witness_index == 1
    assert witness.primary_violation.code == "CONTRACT_EARLY"


def test_resolve_witness_refinement_wins_tie_at_same_index() -> None:
    violations = [
        TRTViolation(
            code="CONTRACT_A",
            message="contract issue",
            failure_class=FAILURE_CLASS_CONTRACT,
            event_index=5,
        ),
        TRTViolation(
            code="REFINEMENT_B",
            message="refinement issue b",
            failure_class=FAILURE_CLASS_REFINEMENT,
            event_index=5,
        ),
        TRTViolation(
            code="REFINEMENT_A",
            message="refinement issue a",
            failure_class=FAILURE_CLASS_REFINEMENT,
            event_index=5,
        ),
    ]

    witness = resolve_witness(violations)
    assert witness is not None
    assert witness.primary_violation.code == "REFINEMENT_A"
    assert [item.code for item in witness.all_violations_at_witness] == [
        "REFINEMENT_A",
        "REFINEMENT_B",
        "CONTRACT_A",
    ]
