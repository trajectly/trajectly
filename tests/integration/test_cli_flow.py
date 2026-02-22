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


def test_record_auto_returns_error_when_no_specs_discovered(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["record", "--auto", "--project-root", str(tmp_path)],
    )

    assert result.exit_code == 2
    assert "No .agent.yaml specs discovered" in result.output


def test_enable_scaffolds_workspace_and_record_auto(tmp_path: Path) -> None:
    script = tmp_path / "tests" / "agents" / "simple_agent.py"
    script.parent.mkdir(parents=True, exist_ok=True)
    _write_script(
        script,
        """
from trajectly.sdk import tool

@tool("echo")
def echo(text):
    return text

echo("hello")
""".strip(),
    )

    enable_result = runner.invoke(app, ["enable", str(tmp_path)])
    assert enable_result.exit_code == 0
    assert "Next step: trajectly record --auto" in enable_result.stdout
    assert (tmp_path / "tests" / "sample.agent.yaml").exists()

    record_result = runner.invoke(
        app,
        ["record", "--auto", "--project-root", str(tmp_path)],
    )
    assert record_result.exit_code == 0
    assert (tmp_path / ".trajectly" / "baselines" / "sample.jsonl").exists()
    assert (tmp_path / ".trajectly" / "fixtures" / "sample.json").exists()

    run_result = runner.invoke(
        app,
        ["run", str(tmp_path / "tests" / "sample.agent.yaml"), "--project-root", str(tmp_path)],
    )
    assert run_result.exit_code == 0


def test_baseline_update_command_re_records_expected_spec(tmp_path: Path) -> None:
    script = tmp_path / "agent.py"
    _write_script(
        script,
        """
import os
from trajectly.sdk import tool

@tool("add")
def add(a, b):
    return a + b

shift = int(os.getenv("SHIFT", "1"))
add(1, shift)
""".strip(),
    )

    spec = tmp_path / "update.agent.yaml"
    _write_spec(
        spec,
        """
name: update
command: python agent.py
workdir: .
fixture_policy: by_hash
strict: true
env:
  SHIFT: "1"
""".strip(),
    )

    init_result = runner.invoke(app, ["init", str(tmp_path)])
    assert init_result.exit_code == 0

    record_result = runner.invoke(app, ["record", str(spec), "--project-root", str(tmp_path)])
    assert record_result.exit_code == 0

    clean_run = runner.invoke(app, ["run", str(spec), "--project-root", str(tmp_path)])
    assert clean_run.exit_code == 0

    _write_spec(
        spec,
        """
name: update
command: python agent.py
workdir: .
fixture_policy: by_hash
strict: true
env:
  SHIFT: "2"
""".strip(),
    )
    regression_run = runner.invoke(app, ["run", str(spec), "--project-root", str(tmp_path)])
    assert regression_run.exit_code == 1

    update_result = runner.invoke(
        app,
        ["baseline", "update", str(spec), "--project-root", str(tmp_path)],
    )
    assert update_result.exit_code == 0

    clean_after_update = runner.invoke(app, ["run", str(spec), "--project-root", str(tmp_path)])
    assert clean_after_update.exit_code == 0
