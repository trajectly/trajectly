from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from trajectly.cli import app

runner = CliRunner()


def _write_script(path: Path, script: str) -> None:
    path.write_text(script, encoding="utf-8")


def _write_spec(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")


def test_record_then_run_clean(tmp_path: Path) -> None:
    script = tmp_path / "agent.py"
    _write_script(
        script,
        """
from trajectly.sdk import tool, llm_call, agent_step

@tool("add")
def add(a, b):
    return a + b

@llm_call(provider="mock", model="v1")
def mock_llm(text):
    return {"response": f"ok:{text}", "usage": {"total_tokens": 3}}

agent_step("start")
value = add(2, 3)
mock_llm(str(value))
agent_step("done", {"value": value})
""".strip(),
    )

    spec = tmp_path / "demo.agent.yaml"
    _write_spec(
        spec,
        """
name: demo
command: python agent.py
workdir: .
fixture_policy: by_hash
strict: true
budget_thresholds:
  max_latency_ms: 5000
  max_tool_calls: 5
  max_tokens: 20
""".strip(),
    )

    init_result = runner.invoke(app, ["init", str(tmp_path)])
    assert init_result.exit_code == 0

    record_result = runner.invoke(
        app,
        ["record", str(spec), "--project-root", str(tmp_path)],
    )
    assert record_result.exit_code == 0

    run_result = runner.invoke(
        app,
        ["run", str(spec), "--project-root", str(tmp_path)],
    )
    assert run_result.exit_code == 0
    assert (tmp_path / ".trajectly" / "reports" / "latest.json").exists()


def test_run_detects_regression_with_strict_replay(tmp_path: Path) -> None:
    script = tmp_path / "agent.py"
    _write_script(
        script,
        """
import os
from trajectly.sdk import tool

@tool("add")
def add(a, b):
    return a + b

if os.getenv("TRAJECTLY_MODE") == "replay":
    add(9, 9)
else:
    add(1, 2)
""".strip(),
    )

    spec = tmp_path / "regression.agent.yaml"
    _write_spec(
        spec,
        """
name: regression
command: python agent.py
workdir: .
fixture_policy: by_hash
strict: true
""".strip(),
    )

    runner.invoke(app, ["init", str(tmp_path)])
    record_result = runner.invoke(app, ["record", str(spec), "--project-root", str(tmp_path)])
    assert record_result.exit_code == 0

    run_result = runner.invoke(app, ["run", str(spec), "--project-root", str(tmp_path)])
    assert run_result.exit_code == 1
