"""Integration tests for the stable platform-facing evaluate import surface."""

from __future__ import annotations

import inspect
from pathlib import Path

from trajectly import Trajectory as TopLevelTrajectory
from trajectly import Verdict as TopLevelVerdict
from trajectly import Violation as TopLevelViolation
from trajectly import evaluate as top_level_evaluate
from trajectly.core import Trajectory, Verdict, Violation, evaluate
from trajectly.events import make_event


def _write_spec(path: Path) -> None:
    path.write_text(
        (
            'schema_version: "0.4"\n'
            "name: platform-demo\n"
            "command: python agent.py\n"
            "contracts:\n"
            "  tools:\n"
            "    deny: [delete_account]\n"
        ),
        encoding="utf-8",
    )


def test_platform_imports_expose_a_stable_shared_surface() -> None:
    signature = inspect.signature(evaluate)

    assert top_level_evaluate is evaluate
    assert TopLevelTrajectory is Trajectory
    assert TopLevelVerdict is Verdict
    assert TopLevelViolation is Violation
    assert list(signature.parameters) == ["trajectory", "spec"]


def test_platform_evaluate_acceptance_path_works_end_to_end(tmp_path: Path) -> None:
    spec_path = tmp_path / "platform.agent.yaml"
    _write_spec(spec_path)
    trajectory = Trajectory(
        events=[
            make_event(
                event_type="tool_called",
                seq=1,
                run_id="platform-run",
                rel_ms=1,
                payload={"tool_name": "delete_account", "input": {"args": [], "kwargs": {}}},
            )
        ]
    )

    verdict = evaluate(trajectory, spec_path)

    assert verdict.status == "FAIL"
    assert verdict.passed is False
    assert verdict.primary_violation is not None
    assert verdict.primary_violation.code == "CONTRACT_TOOL_DENIED"
    assert verdict.to_dict()["primary_violation"]["failure_class"] == "CONTRACT"
