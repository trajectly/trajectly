"""Smoke tests for the platform-facing API in a subprocess-style environment."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _pythonpath_env() -> dict[str, str]:
    env = os.environ.copy()
    src_path = str(_repo_root() / "src")
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = src_path if not existing else os.pathsep.join([src_path, existing])
    return env


def _write_spec(path: Path) -> None:
    path.write_text(
        (
            'schema_version: "0.4"\n'
            "name: platform-smoke\n"
            "command: python agent.py\n"
            "contracts:\n"
            "  tools:\n"
            "    deny: [delete_account]\n"
        ),
        encoding="utf-8",
    )


def test_platform_api_smoke_subprocess_evaluate_path(tmp_path: Path) -> None:
    spec_path = tmp_path / "platform.agent.yaml"
    _write_spec(spec_path)
    script = """
import json
import sys
from trajectly.core import Trajectory, evaluate
from trajectly.events import make_event

trajectory = Trajectory(
    events=[
        make_event(
            event_type="tool_called",
            seq=1,
            run_id="smoke-run",
            rel_ms=1,
            payload={"tool_name": "delete_account", "input": {"args": [], "kwargs": {}}},
        )
    ]
)
verdict = evaluate(trajectory, sys.argv[1])
print(json.dumps(verdict.to_dict(), sort_keys=True))
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(spec_path)],
        capture_output=True,
        text=True,
        check=False,
        env=_pythonpath_env(),
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "FAIL"
    assert payload["primary_violation"]["code"] == "CONTRACT_TOOL_DENIED"


def test_platform_api_smoke_subprocess_trace_json_path(tmp_path: Path) -> None:
    bundle_path = tmp_path / "trajectory.json"
    script = """
import json
import sys
from pathlib import Path
from trajectly.core.trace import TraceEventV03, TraceMetaV03, TrajectoryV03, read_trajectory_json, write_trajectory_json

trajectory = TrajectoryV03(
    meta=TraceMetaV03(spec_name="platform-smoke", run_id="run-1", mode="record"),
    events=[
        TraceEventV03(
            event_index=0,
            kind="TOOL_CALL",
            payload={"tool_name": "search"},
            stable_hash="hash-1",
        )
    ],
)
path = Path(sys.argv[1])
write_trajectory_json(path, trajectory)
restored = read_trajectory_json(path)
print(json.dumps(restored.to_dict(), sort_keys=True))
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(bundle_path)],
        capture_output=True,
        text=True,
        check=False,
        env=_pythonpath_env(),
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "0.4"
    assert payload["events"][0]["kind"] == "TOOL_CALL"
