from __future__ import annotations

import json
import sys
from pathlib import Path

from trajectly.runtime import execute_spec
from trajectly.specs import AgentContracts, AgentSpec, NetworkContracts


def _write(path: Path, body: str) -> None:
    path.write_text(body.strip() + "\n", encoding="utf-8")


def _spec(tmp_path: Path, command: str, workdir: str | None = ".") -> AgentSpec:
    spec_path = tmp_path / "demo.agent.yaml"
    _write(spec_path, f"command: {command}")
    return AgentSpec(name="demo", command=command, source_path=spec_path, workdir=workdir)


def test_execute_spec_collects_events_and_sets_replay_guard(tmp_path: Path) -> None:
    script_path = tmp_path / "agent.py"
    _write(
        script_path,
        """
import json
import os
from pathlib import Path

path = Path(os.environ["TRAJECTLY_EVENTS_FILE"])
record = {
    "event_type": "agent_step",
    "rel_ms": 1,
    "payload": {"mode": os.getenv("TRAJECTLY_MODE")},
    "meta": {},
}
with path.open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(record) + "\\n")
print("guard=" + os.getenv("TRAJECTLY_REPLAY_GUARD", "0"))
""",
    )

    spec = _spec(tmp_path, f"{sys.executable} {script_path.name}")
    events_path = tmp_path / "events.jsonl"

    record_result = execute_spec(spec=spec, mode="record", events_path=events_path, fixtures_path=None, strict=False)
    replay_result = execute_spec(spec=spec, mode="replay", events_path=events_path, fixtures_path=None, strict=True)

    assert record_result.returncode == 0
    assert replay_result.returncode == 0
    assert record_result.raw_events[0]["event_type"] == "agent_step"
    assert "guard=1" in replay_result.stdout


def test_execute_spec_returns_internal_error_on_invalid_workdir(tmp_path: Path) -> None:
    script_path = tmp_path / "agent.py"
    _write(script_path, "print('ok')")

    spec = _spec(tmp_path, f"{sys.executable} {script_path.name}", workdir="does-not-exist")
    events_path = tmp_path / "events.jsonl"

    result = execute_spec(spec=spec, mode="record", events_path=events_path, fixtures_path=None, strict=False)

    assert result.returncode == 1
    assert result.internal_error is not None
    assert isinstance(result.raw_events, list)


def test_execute_spec_includes_custom_env(tmp_path: Path) -> None:
    script_path = tmp_path / "agent.py"
    _write(
        script_path,
        """
import os
print(os.getenv("CUSTOM_ENV"))
""",
    )

    spec = AgentSpec(
        name="demo",
        command=f"{sys.executable} {script_path.name}",
        source_path=tmp_path / "demo.agent.yaml",
        workdir=".",
        env={"CUSTOM_ENV": "works"},
    )

    result = execute_spec(
        spec=spec,
        mode="record",
        events_path=tmp_path / "events.jsonl",
        fixtures_path=None,
        strict=False,
    )

    assert result.returncode == 0
    assert "works" in result.stdout


def test_execute_spec_sets_network_allowlist_env(tmp_path: Path) -> None:
    script_path = tmp_path / "agent.py"
    _write(
        script_path,
        """
import os
print(os.getenv("TRAJECTLY_NETWORK_ALLOWLIST", "missing"))
""",
    )

    spec = AgentSpec(
        name="demo",
        command=f"{sys.executable} {script_path.name}",
        source_path=tmp_path / "demo.agent.yaml",
        workdir=".",
        contracts=AgentContracts(network=NetworkContracts(allowlist=["api.example.com", "localhost"])),
    )

    result = execute_spec(
        spec=spec,
        mode="replay",
        events_path=tmp_path / "events.jsonl",
        fixtures_path=None,
        strict=True,
    )

    assert result.returncode == 0
    assert "api.example.com,localhost" in result.stdout


def test_execute_spec_sets_trace_env_and_writes_meta(tmp_path: Path) -> None:
    script_path = tmp_path / "agent.py"
    _write(
        script_path,
        """
import os
from trajectly.sdk import agent_step

agent_step("start")
print(os.getenv("TRAJECTLY_TRACE_FILE", "missing"))
print(os.getenv("TRAJECTLY_TRACE_META_FILE", "missing"))
print(os.getenv("TRAJECTLY_SPEC_NAME", "missing"))
""",
    )

    spec = AgentSpec(
        name="trace-demo",
        command=f"{sys.executable} {script_path.name}",
        source_path=tmp_path / "trace-demo.agent.yaml",
        workdir=".",
    )
    events_path = tmp_path / "trace.events.jsonl"

    result = execute_spec(
        spec=spec,
        mode="record",
        events_path=events_path,
        fixtures_path=None,
        strict=False,
    )

    assert result.returncode == 0
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    assert lines[0].endswith(".trace.jsonl")
    assert lines[1].endswith(".trace.meta.json")
    assert lines[2] == "trace-demo"
    meta_path = Path(lines[1])
    assert meta_path.exists()
    payload = json.loads(meta_path.read_text(encoding="utf-8"))
    assert payload["normalizer_version"] == "1"
