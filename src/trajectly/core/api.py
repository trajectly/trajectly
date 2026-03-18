"""Stable public evaluation API for non-CLI callers.

This module gives platform and server integrations a small import-safe surface
over the existing TRT engine. Phase 1 callers can evaluate execution traces
without shelling out through the CLI, while still using the same deterministic
contract and witness logic.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from trajectly.core.errors import FailureClass
from trajectly.core.events import TraceEvent
from trajectly.core.report.schema import TRTStatus
from trajectly.core.specs import AgentSpec, load_spec
from trajectly.core.trt.runner import TRTResult, evaluate_trt
from trajectly.core.trt.types import TRTViolation


@dataclass(slots=True)
class Trajectory:
    """Programmatic trajectory input for the stable evaluation API."""

    events: list[TraceEvent]
    baseline_events: list[TraceEvent] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.events = _coerce_trace_events(self.events, field_name="trajectory.events")
        if self.baseline_events is not None:
            self.baseline_events = _coerce_trace_events(
                self.baseline_events,
                field_name="trajectory.baseline_events",
            )
        self.metadata = dict(self.metadata)

    @classmethod
    def from_events(
        cls,
        events: Sequence[TraceEvent],
        *,
        baseline_events: Sequence[TraceEvent] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Trajectory:
        """Build a stable API trajectory from raw event sequences."""

        return cls(
            events=list(events),
            baseline_events=list(baseline_events) if baseline_events is not None else None,
            metadata=dict(metadata or {}),
        )


@dataclass(slots=True, frozen=True)
class Violation:
    """Stable violation payload returned by :func:`evaluate`."""

    code: str
    message: str
    failure_class: FailureClass
    event_index: int
    expected: Any | None = None
    observed: Any | None = None
    hint: str | None = None

    @classmethod
    def from_trt(cls, violation: TRTViolation) -> Violation:
        """Project an internal TRT violation onto the stable public surface."""

        return cls(
            code=violation.code,
            message=violation.message,
            failure_class=cast(FailureClass, violation.failure_class),
            event_index=violation.event_index,
            expected=violation.expected,
            observed=violation.observed,
            hint=violation.hint,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize this violation to a JSON-ready mapping."""

        payload: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
            "failure_class": self.failure_class,
            "event_index": self.event_index,
        }
        if self.expected is not None:
            payload["expected"] = self.expected
        if self.observed is not None:
            payload["observed"] = self.observed
        if self.hint is not None:
            payload["hint"] = self.hint
        return payload


@dataclass(slots=True, frozen=True)
class Verdict:
    """Stable evaluation result returned by :func:`evaluate`."""

    status: TRTStatus
    violations: tuple[Violation, ...] = ()
    witness_index: int | None = None
    failure_class: FailureClass | None = None
    primary_violation: Violation | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        """Return ``True`` when the evaluated trajectory passed all checks."""

        return self.status == "PASS"

    @classmethod
    def from_trt(cls, result: TRTResult) -> Verdict:
        """Project an internal TRT result onto the stable public surface."""

        report = result.report
        return cls(
            status=result.status,
            violations=tuple(Violation.from_trt(violation) for violation in result.all_violations),
            witness_index=report.witness_index,
            failure_class=report.failure_class,
            primary_violation=(
                Violation(
                    code=report.primary_violation.code,
                    message=report.primary_violation.message,
                    failure_class=report.primary_violation.failure_class,
                    event_index=report.primary_violation.event_index,
                    expected=report.primary_violation.expected,
                    observed=report.primary_violation.observed,
                    hint=report.primary_violation.hint,
                )
                if report.primary_violation is not None
                else None
            ),
            metadata=report.metadata.to_dict(),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize this verdict to a JSON-ready mapping."""

        payload: dict[str, Any] = {
            "status": self.status,
            "passed": self.passed,
            "violations": [violation.to_dict() for violation in self.violations],
            "metadata": dict(self.metadata),
        }
        if self.witness_index is not None:
            payload["witness_index"] = self.witness_index
        if self.failure_class is not None:
            payload["failure_class"] = self.failure_class
        if self.primary_violation is not None:
            payload["primary_violation"] = self.primary_violation.to_dict()
        return payload


def _coerce_trace_events(raw: object, *, field_name: str) -> list[TraceEvent]:
    if isinstance(raw, str | bytes):
        raise TypeError(f"{field_name} must be a sequence of TraceEvent instances, not {type(raw).__name__}")
    if not isinstance(raw, Sequence):
        raise TypeError(f"{field_name} must be a sequence of TraceEvent instances")
    events = list(raw)
    for index, event in enumerate(events):
        if not isinstance(event, TraceEvent):
            raise TypeError(
                f"{field_name}[{index}] must be a trajectly.events.TraceEvent, "
                f"got {type(event).__name__}"
            )
    return events


def _coerce_trajectory(raw: object) -> Trajectory:
    if isinstance(raw, Trajectory):
        return raw
    if not isinstance(raw, str | bytes) and isinstance(raw, Sequence):
        return Trajectory.from_events(raw)
    raise TypeError(
        "trajectory must be a trajectly.core.Trajectory or a sequence of trajectly.events.TraceEvent instances"
    )


def _coerce_spec(raw: AgentSpec | str | Path) -> AgentSpec:
    if isinstance(raw, AgentSpec):
        return raw
    if isinstance(raw, str | Path):
        return load_spec(Path(raw))
    raise TypeError("spec must be an AgentSpec or a path to an .agent.yaml file")


def evaluate(trajectory: Trajectory | Sequence[TraceEvent], spec: AgentSpec | str | Path) -> Verdict:
    """Evaluate a trajectory against a spec without using the CLI.

    When ``baseline_events`` are omitted, evaluation falls back to contract-only
    checks by reusing the current trajectory as the refinement baseline.
    """

    normalized_trajectory = _coerce_trajectory(trajectory)
    normalized_spec = _coerce_spec(spec)
    baseline_events = (
        normalized_trajectory.baseline_events
        if normalized_trajectory.baseline_events is not None
        else normalized_trajectory.events
    )
    result = evaluate_trt(
        baseline_events=baseline_events,
        current_events=normalized_trajectory.events,
        spec=normalized_spec,
    )
    return Verdict.from_trt(result)


__all__ = [
    "Trajectory",
    "Verdict",
    "Violation",
    "evaluate",
]
