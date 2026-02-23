from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from trajectly.constants import (
    TRT_NORMALIZER_VERSION,
    TRT_REPORT_SCHEMA_VERSION,
    TRT_SIDE_EFFECT_REGISTRY_VERSION,
)
from trajectly.errors import FailureClass

TRTStatus = Literal["PASS", "FAIL", "ERROR"]


@dataclass(slots=True)
class ViolationV03:
    code: str
    message: str
    failure_class: FailureClass
    event_index: int
    expected: Any | None = None
    observed: Any | None = None
    hint: str | None = None

    def to_dict(self) -> dict[str, Any]:
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


@dataclass(slots=True)
class ShrinkStatsV03:
    original_len: int
    reduced_len: int
    iterations: int
    seconds: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "original_len": self.original_len,
            "reduced_len": self.reduced_len,
            "iterations": self.iterations,
            "seconds": self.seconds,
        }


@dataclass(slots=True)
class TRTReportMetadataV03:
    report_schema_version: str = TRT_REPORT_SCHEMA_VERSION
    normalizer_version: str = TRT_NORMALIZER_VERSION
    side_effect_registry_version: str = TRT_SIDE_EFFECT_REGISTRY_VERSION
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_schema_version": self.report_schema_version,
            "normalizer_version": self.normalizer_version,
            "side_effect_registry_version": self.side_effect_registry_version,
            "metadata": self.metadata,
        }


@dataclass(slots=True)
class TRTReportV03:
    status: TRTStatus
    metadata: TRTReportMetadataV03 = field(default_factory=TRTReportMetadataV03)
    failure_class: FailureClass | None = None
    witness_index: int | None = None
    primary_violation: ViolationV03 | None = None
    all_violations_at_witness: list[ViolationV03] = field(default_factory=list)
    repro_command: str | None = None
    counterexample_paths: dict[str, str] = field(default_factory=dict)
    shrink_stats: ShrinkStatsV03 | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "metadata": self.metadata.to_dict(),
            "status": self.status,
            "all_violations_at_witness": [violation.to_dict() for violation in self.all_violations_at_witness],
            "counterexample_paths": self.counterexample_paths,
        }
        if self.failure_class is not None:
            payload["failure_class"] = self.failure_class
        if self.witness_index is not None:
            payload["witness_index"] = self.witness_index
        if self.primary_violation is not None:
            payload["primary_violation"] = self.primary_violation.to_dict()
        if self.repro_command is not None:
            payload["repro_command"] = self.repro_command
        if self.shrink_stats is not None:
            payload["shrink_stats"] = self.shrink_stats.to_dict()
        return payload


__all__ = [
    "ShrinkStatsV03",
    "TRTReportMetadataV03",
    "TRTReportV03",
    "TRTStatus",
    "ViolationV03",
]
