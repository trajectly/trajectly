from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from trajectly.core.constants import (
    FAILURE_CLASS_CONTRACT,
    FAILURE_CLASS_REFINEMENT,
    FAILURE_CLASS_TOOLING,
)

FailureClass = Literal[
    "REFINEMENT",
    "CONTRACT",
    "TOOLING",
]

ERROR_CODE_FIXTURE_EXHAUSTED = "FIXTURE_EXHAUSTED"
ERROR_CODE_NORMALIZER_VERSION_MISMATCH = "NORMALIZER_VERSION_MISMATCH"
ERROR_CODE_NONDETERMINISM_CLOCK_DETECTED = "NONDETERMINISM_CLOCK_DETECTED"
ERROR_CODE_NONDETERMINISM_RANDOM_DETECTED = "NONDETERMINISM_RANDOM_DETECTED"
ERROR_CODE_NONDETERMINISM_UUID_DETECTED = "NONDETERMINISM_UUID_DETECTED"
ERROR_CODE_NONDETERMINISM_FILESYSTEM_DETECTED = "NONDETERMINISM_FILESYSTEM_DETECTED"


@dataclass(slots=True, frozen=True)
class TrajectlyError:
    code: str
    message: str
    failure_class: FailureClass | None = None
    event_index: int | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }
        if self.failure_class is not None:
            payload["failure_class"] = self.failure_class
        if self.event_index is not None:
            payload["event_index"] = self.event_index
        return payload


VALID_FAILURE_CLASSES = {
    FAILURE_CLASS_REFINEMENT,
    FAILURE_CLASS_CONTRACT,
    FAILURE_CLASS_TOOLING,
}


__all__ = [
    "ERROR_CODE_FIXTURE_EXHAUSTED",
    "ERROR_CODE_NONDETERMINISM_CLOCK_DETECTED",
    "ERROR_CODE_NONDETERMINISM_FILESYSTEM_DETECTED",
    "ERROR_CODE_NONDETERMINISM_RANDOM_DETECTED",
    "ERROR_CODE_NONDETERMINISM_UUID_DETECTED",
    "ERROR_CODE_NORMALIZER_VERSION_MISMATCH",
    "VALID_FAILURE_CLASSES",
    "FailureClass",
    "TrajectlyError",
]
