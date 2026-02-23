from __future__ import annotations

from trajectly.constants import (
    FAILURE_CLASS_CONTRACT,
    FAILURE_CLASS_REFINEMENT,
    FAILURE_CLASS_TOOLING,
)
from trajectly.errors import (
    ERROR_CODE_FIXTURE_EXHAUSTED,
    ERROR_CODE_NORMALIZER_VERSION_MISMATCH,
    VALID_FAILURE_CLASSES,
    TrajectlyError,
)


def test_normative_error_codes_are_stable() -> None:
    assert ERROR_CODE_FIXTURE_EXHAUSTED == "FIXTURE_EXHAUSTED"
    assert ERROR_CODE_NORMALIZER_VERSION_MISMATCH == "NORMALIZER_VERSION_MISMATCH"


def test_valid_failure_classes_cover_trt_contract() -> None:
    assert VALID_FAILURE_CLASSES == {
        FAILURE_CLASS_REFINEMENT,
        FAILURE_CLASS_CONTRACT,
        FAILURE_CLASS_TOOLING,
    }


def test_trajectly_error_to_dict_includes_required_fields() -> None:
    error = TrajectlyError(
        code=ERROR_CODE_FIXTURE_EXHAUSTED,
        message="Fixture was exhausted",
        failure_class=FAILURE_CLASS_CONTRACT,
        event_index=7,
        details={
            "expected_signature": "tool:add:abc",
            "consumed_count": 2,
            "available_count": 2,
            "tool_name": "add",
        },
    )

    payload = error.to_dict()
    assert payload["code"] == "FIXTURE_EXHAUSTED"
    assert payload["failure_class"] == "CONTRACT"
    assert payload["event_index"] == 7
    assert payload["details"]["tool_name"] == "add"
