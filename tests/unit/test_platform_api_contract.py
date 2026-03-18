"""Contract tests for the documented platform-facing API surface."""

from __future__ import annotations

import inspect
from dataclasses import fields

import trajectly
import trajectly.core as core
import trajectly.core.trace as trace
from trajectly.core import Trajectory, Verdict, Violation, evaluate
from trajectly.core.trace import (
    TraceEventV03,
    TraceMetaV03,
    TrajectoryV03,
    read_legacy_trajectory,
    read_trajectory_json,
    write_trajectory_json,
)


def test_platform_core_public_surface_matches_documented_contract() -> None:
    assert core.__all__ == ["Trajectory", "Verdict", "Violation", "evaluate"]
    assert trajectly.Trajectory is Trajectory
    assert trajectly.Verdict is Verdict
    assert trajectly.Violation is Violation
    assert trajectly.evaluate is evaluate
    assert list(inspect.signature(evaluate).parameters) == ["trajectory", "spec"]


def test_platform_value_objects_keep_documented_fields_and_helpers() -> None:
    assert [field.name for field in fields(Trajectory)] == ["events", "baseline_events", "metadata"]
    assert [field.name for field in fields(Verdict)] == [
        "status",
        "violations",
        "witness_index",
        "failure_class",
        "primary_violation",
        "metadata",
    ]
    assert [field.name for field in fields(Violation)] == [
        "code",
        "message",
        "failure_class",
        "event_index",
        "expected",
        "observed",
        "hint",
    ]
    assert isinstance(Verdict.passed, property)
    assert hasattr(Trajectory, "from_events")
    assert hasattr(Verdict, "to_dict")
    assert hasattr(Violation, "to_dict")


def test_platform_trace_surface_matches_documented_contract() -> None:
    documented_exports = {
        "TraceEventV03",
        "TraceMetaV03",
        "TrajectoryV03",
        "read_legacy_trajectory",
        "read_trajectory_json",
        "write_trajectory_json",
    }

    assert documented_exports.issubset(set(trace.__all__))
    assert TraceEventV03.__name__ == "TraceEventV03"
    assert TraceMetaV03.__name__ == "TraceMetaV03"
    assert [field.name for field in fields(TrajectoryV03)] == ["meta", "events", "schema_version"]
    assert callable(read_legacy_trajectory)
    assert callable(read_trajectory_json)
    assert callable(write_trajectory_json)
