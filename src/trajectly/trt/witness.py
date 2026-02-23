"""Witness resolution (Definitions 6-7 in trt_theory.md).

Implements ``resolve_witness``, which selects the earliest violation event
(Theorem 3: witness minimality) and applies deterministic tie-breaking:

1. Failure class rank: REFINEMENT < CONTRACT < TOOLING.
2. Lexicographic violation code order within the same class.

This yields a total order on violations at the witness index, guaranteeing a
unique and stable primary violation across invocations (Theorem 2).
"""

from __future__ import annotations

from dataclasses import dataclass

from trajectly.constants import WITNESS_FAILURE_CLASS_ORDER
from trajectly.trt.types import TRTViolation


@dataclass(slots=True)
class WitnessResolution:
    witness_index: int
    primary_violation: TRTViolation
    all_violations_at_witness: list[TRTViolation]


def _class_rank(failure_class: str) -> int:
    for idx, value in enumerate(WITNESS_FAILURE_CLASS_ORDER):
        if value == failure_class:
            return idx
    return len(WITNESS_FAILURE_CLASS_ORDER)


def resolve_witness(violations: list[TRTViolation]) -> WitnessResolution | None:
    if not violations:
        return None

    witness_index = min(violation.event_index for violation in violations)
    at_witness = [violation for violation in violations if violation.event_index == witness_index]
    # Deterministic tie-break policy is contractually stable: class rank first,
    # then lexical code order within class.
    at_witness.sort(key=lambda item: (_class_rank(item.failure_class), item.code))
    return WitnessResolution(
        witness_index=witness_index,
        primary_violation=at_witness[0],
        all_violations_at_witness=at_witness,
    )


__all__ = [
    "WitnessResolution",
    "resolve_witness",
]
