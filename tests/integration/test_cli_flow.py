from __future__ import annotations

import json
from pathlib import Path

import yaml
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


def test_record_blocks_baseline_write_in_ci_without_override(tmp_path: Path) -> None:
    script = tmp_path / "agent.py"
    _write_script(
        script,
        """
from trajectly.sdk import tool

@tool("echo")
def echo(text):
    return text

echo("ok")
""".strip(),
    )
    spec = tmp_path / "ci.agent.yaml"
    _write_spec(
        spec,
        """
name: ci-record
command: python agent.py
workdir: .
strict: true
""".strip(),
    )

    runner.invoke(app, ["init", str(tmp_path)])
    blocked = runner.invoke(
        app,
        ["record", str(spec), "--project-root", str(tmp_path)],
        env={"TRAJECTLY_CI": "1"},
    )
    assert blocked.exit_code == 2
    assert "Baseline writes are blocked when TRAJECTLY_CI=1" in blocked.output

    allowed = runner.invoke(
        app,
        ["record", str(spec), "--project-root", str(tmp_path), "--allow-ci-write"],
        env={"TRAJECTLY_CI": "1"},
    )
    assert allowed.exit_code == 0


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


def test_run_enforces_contract_tool_deny(tmp_path: Path) -> None:
    script = tmp_path / "agent.py"
    _write_script(
        script,
        """
from trajectly.sdk import tool

@tool("add")
def add(a, b):
    return a + b

add(1, 2)
""".strip(),
    )
    spec = tmp_path / "contracts.agent.yaml"
    _write_spec(
        spec,
        """
name: contracts
command: python agent.py
workdir: .
fixture_policy: by_hash
strict: true
""".strip(),
    )

    runner.invoke(app, ["init", str(tmp_path)])
    record_result = runner.invoke(app, ["record", str(spec), "--project-root", str(tmp_path)])
    assert record_result.exit_code == 0

    _write_spec(
        spec,
        """
name: contracts
command: python agent.py
workdir: .
fixture_policy: by_hash
strict: true
contracts:
  tools:
    deny: [add]
""".strip(),
    )

    run_result = runner.invoke(app, ["run", str(spec), "--project-root", str(tmp_path)])
    assert run_result.exit_code == 1

    latest_report = tmp_path / ".trajectly" / "reports" / "contracts.json"
    payload = json.loads(latest_report.read_text(encoding="utf-8"))
    classifications = {finding["classification"] for finding in payload["findings"]}
    assert "contract_tool_denied" in classifications


def test_run_contract_violation_fails_fast_before_followup_steps(tmp_path: Path) -> None:
    marker = tmp_path / "should_not_exist.txt"
    script = tmp_path / "agent.py"
    _write_script(
        script,
        f"""
from pathlib import Path
from trajectly.sdk import tool

@tool("delete_account")
def delete_account(user_id):
    return user_id

delete_account("u-1")
Path("{marker.name}").write_text("ran", encoding="utf-8")
""".strip(),
    )
    spec = tmp_path / "failfast.agent.yaml"
    _write_spec(
        spec,
        """
name: failfast
command: python agent.py
workdir: .
fixture_policy: by_hash
strict: true
""".strip(),
    )

    runner.invoke(app, ["init", str(tmp_path)])
    record_result = runner.invoke(app, ["record", str(spec), "--project-root", str(tmp_path)])
    assert record_result.exit_code == 0
    assert marker.exists()
    marker.unlink()

    _write_spec(
        spec,
        """
name: failfast
command: python agent.py
workdir: .
fixture_policy: by_hash
strict: true
contracts:
  tools:
    deny: [delete_account]
""".strip(),
    )

    run_result = runner.invoke(app, ["run", str(spec), "--project-root", str(tmp_path)])
    assert run_result.exit_code == 1
    assert not marker.exists()


def test_repro_command_uses_latest_regression_and_repro_artifact(tmp_path: Path) -> None:
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

    spec = tmp_path / "repro.agent.yaml"
    _write_spec(
        spec,
        """
name: repro
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

    repro_artifact = tmp_path / ".trajectly" / "repros" / "repro.json"
    assert repro_artifact.exists()
    repro_payload = json.loads(repro_artifact.read_text(encoding="utf-8"))
    assert repro_payload["spec"] == "repro"
    assert "repro_command" in repro_payload
    baseline_min = Path(repro_payload["baseline_min_trace"])
    current_min = Path(repro_payload["current_min_trace"])
    assert baseline_min.exists()
    assert current_min.exists()
    full_current = tmp_path / ".trajectly" / "current" / "repro.jsonl"
    min_lines = [line for line in current_min.read_text(encoding="utf-8").splitlines() if line.strip()]
    full_lines = [line for line in full_current.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert min_lines
    assert len(min_lines) <= len(full_lines)

    print_only_result = runner.invoke(app, ["repro", "--project-root", str(tmp_path), "--print-only"])
    assert print_only_result.exit_code == 0
    assert "Repro command:" in print_only_result.stdout
    assert str(spec.resolve()) in print_only_result.stdout

    execute_result = runner.invoke(app, ["repro", "--project-root", str(tmp_path)])
    assert execute_result.exit_code == 1


def test_enable_with_openai_template_creates_files_and_runs(tmp_path: Path) -> None:
    enable_result = runner.invoke(app, ["enable", str(tmp_path), "--template", "openai"])
    assert enable_result.exit_code == 0
    assert "Applied template: openai" in enable_result.stdout

    spec_path = tmp_path / "openai.agent.yaml"
    script_path = tmp_path / "templates" / "openai_agent.py"
    assert spec_path.exists()
    assert script_path.exists()

    record_result = runner.invoke(app, ["record", str(spec_path), "--project-root", str(tmp_path)])
    assert record_result.exit_code == 0

    run_result = runner.invoke(app, ["run", str(spec_path), "--project-root", str(tmp_path)])
    assert run_result.exit_code == 0


def test_enable_with_invalid_template_returns_error(tmp_path: Path) -> None:
    result = runner.invoke(app, ["enable", str(tmp_path), "--template", "unknown-template"])
    assert result.exit_code == 2
    assert "Unsupported template" in result.output


def test_shrink_command_reduces_counterexample_and_updates_report(tmp_path: Path) -> None:
    script = tmp_path / "agent.py"
    _write_script(
        script,
        """
from trajectly.sdk import tool

@tool("add")
def add(a, b):
    return a + b

add(1, 2)
""".strip(),
    )
    spec = tmp_path / "shrink.agent.yaml"
    _write_spec(
        spec,
        """
schema_version: "0.3"
name: shrink-demo
command: python agent.py
workdir: .
fixture_policy: by_hash
strict: true
""".strip(),
    )

    runner.invoke(app, ["init", str(tmp_path)])
    record_result = runner.invoke(
        app,
        ["record", str(spec), "--project-root", str(tmp_path), "--allow-ci-write"],
        env={"TRAJECTLY_CI": "1"},
    )
    assert record_result.exit_code == 0

    _write_spec(
        spec,
        """
schema_version: "0.3"
name: shrink-demo
command: python agent.py
workdir: .
fixture_policy: by_hash
strict: true
contracts:
  tools:
    deny: [add]
""".strip(),
    )

    run_result = runner.invoke(app, ["run", str(spec), "--project-root", str(tmp_path)])
    assert run_result.exit_code == 1

    shrink_result = runner.invoke(
        app,
        ["shrink", "latest", "--project-root", str(tmp_path), "--max-seconds", "5", "--max-iterations", "100"],
    )
    assert shrink_result.exit_code == 0

    report_json = tmp_path / ".trajectly" / "reports" / "shrink-demo.json"
    payload = json.loads(report_json.read_text(encoding="utf-8"))
    trt = payload["trt_v03"]
    assert trt["status"] == "FAIL"
    assert trt["failure_class"] == "CONTRACT"
    assert "shrink_stats" in trt
    assert trt["shrink_stats"]["reduced_len"] <= trt["shrink_stats"]["original_len"]


def test_repeated_runs_have_stable_trt_verdict_and_witness(tmp_path: Path) -> None:
    script = tmp_path / "agent.py"
    _write_script(
        script,
        """
from trajectly.sdk import tool

@tool("charge")
def charge(amount):
    return {"ok": True, "amount": amount}

charge(10)
""".strip(),
    )
    spec = tmp_path / "stable.agent.yaml"
    _write_spec(
        spec,
        """
schema_version: "0.3"
name: stable-trt
command: python agent.py
workdir: .
strict: true
""".strip(),
    )

    runner.invoke(app, ["init", str(tmp_path)])
    record_result = runner.invoke(app, ["record", str(spec), "--project-root", str(tmp_path)])
    assert record_result.exit_code == 0

    _write_spec(
        spec,
        """
schema_version: "0.3"
name: stable-trt
command: python agent.py
workdir: .
strict: true
contracts:
  tools:
    deny: [charge]
""".strip(),
    )

    run_one = runner.invoke(app, ["run", str(spec), "--project-root", str(tmp_path)])
    assert run_one.exit_code == 1
    report_path = tmp_path / ".trajectly" / "reports" / "stable-trt.json"
    first_payload = json.loads(report_path.read_text(encoding="utf-8"))
    first_trt = first_payload["trt_v03"]

    run_two = runner.invoke(app, ["run", str(spec), "--project-root", str(tmp_path)])
    assert run_two.exit_code == 1
    second_payload = json.loads(report_path.read_text(encoding="utf-8"))
    second_trt = second_payload["trt_v03"]

    assert second_trt == first_trt
