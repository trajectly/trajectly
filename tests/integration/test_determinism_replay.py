from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from typer.testing import CliRunner

from trajectly.cli import app

runner = CliRunner()


def _write_script(path: Path, script: str) -> None:
    path.write_text(script, encoding="utf-8")


def _write_spec(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")


def _report_payload_for_latest_row(project_root: Path) -> dict[str, object]:
    latest_path = project_root / ".trajectly" / "reports" / "latest.json"
    latest = json.loads(latest_path.read_text(encoding="utf-8"))
    row = latest["reports"][0]
    report_json = project_root / ".trajectly" / row["report_json"]
    return cast(dict[str, object], json.loads(report_json.read_text(encoding="utf-8")))


def test_replay_trt_payload_is_deterministic_across_runs(tmp_path: Path) -> None:
    script = tmp_path / "agent.py"
    _write_script(
        script,
        """
from trajectly.sdk import llm_call, tool

@tool("add")
def add(a, b):
    return a + b

@llm_call(provider="mock", model="v1")
def mock_llm(text):
    return {"response": f"ok:{text}", "usage": {"total_tokens": 1}}

value = add(1, 2)
mock_llm(str(value))
""".strip(),
    )
    spec = tmp_path / "determinism.agent.yaml"
    _write_spec(
        spec,
        """
schema_version: "0.4"
name: determinism-demo
command: python agent.py
workdir: .
strict: true
""".strip(),
    )

    assert runner.invoke(app, ["init", str(tmp_path)]).exit_code == 0
    assert runner.invoke(app, ["record", str(spec), "--project-root", str(tmp_path)]).exit_code == 0

    first_run = runner.invoke(app, ["run", str(spec), "--project-root", str(tmp_path)])
    assert first_run.exit_code == 0
    first_report = _report_payload_for_latest_row(tmp_path)

    second_run = runner.invoke(app, ["run", str(spec), "--project-root", str(tmp_path)])
    assert second_run.exit_code == 0
    second_report = _report_payload_for_latest_row(tmp_path)

    first_trt = cast(dict[str, Any], first_report["trt_v03"])
    second_trt = cast(dict[str, Any], second_report["trt_v03"])
    assert first_trt == second_trt
    assert first_trt.get("witness_index") == second_trt.get("witness_index")
    assert first_trt.get("replay_mode") == "offline"
    assert isinstance(first_trt.get("fixture_usage"), dict)
    assert isinstance(first_trt["fixture_usage"]["fixtures"], list)
    assert isinstance(first_trt.get("determinism_diagnostics"), list)


def test_replay_blocks_live_network_in_ci_safe_mode(tmp_path: Path) -> None:
    script = tmp_path / "agent.py"
    _write_script(
        script,
        """
import os
import urllib.request

from trajectly.sdk import tool

@tool("echo")
def echo(text):
    return text

echo("ok")
if os.getenv("TRAJECTLY_MODE") == "replay":
    urllib.request.urlopen("https://example.com", timeout=1)
""".strip(),
    )
    spec = tmp_path / "network-block.agent.yaml"
    _write_spec(
        spec,
        """
schema_version: "0.4"
name: network-block
command: python agent.py
workdir: .
strict: true
""".strip(),
    )

    assert runner.invoke(app, ["init", str(tmp_path)]).exit_code == 0
    assert runner.invoke(app, ["record", str(spec), "--project-root", str(tmp_path)]).exit_code == 0

    run_result = runner.invoke(app, ["run", str(spec), "--project-root", str(tmp_path)])
    assert run_result.exit_code == 1

    latest = json.loads((tmp_path / ".trajectly" / "reports" / "latest.json").read_text(encoding="utf-8"))
    row = latest["reports"][0]
    current_trace = Path(row["current"])
    if not current_trace.is_absolute():
        current_trace = (tmp_path / current_trace).resolve()
    assert current_trace.exists()
    assert "Trajectly replay mode blocks network access" in current_trace.read_text(encoding="utf-8")
