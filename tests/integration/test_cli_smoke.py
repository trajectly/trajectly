"""CLI smoke tests: init, record, run, report on a fixture-only example."""
from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from trajectly.cli import app

runner = CliRunner()


def _write_file(path: Path, content: str) -> None:
    path.write_text(content.strip() + "\n", encoding="utf-8")


def _setup_fixture_agent(tmp_path: Path) -> Path:
    """Create a minimal agent + spec that runs without API keys."""
    _write_file(
        tmp_path / "agent.py",
        """
from trajectly.sdk import tool, llm_call, agent_step

@tool("multiply")
def multiply(a, b):
    return a * b

@llm_call(provider="mock", model="v1")
def mock_llm(text):
    return {"response": f"result:{text}", "usage": {"total_tokens": 2}}

agent_step("start")
val = multiply(3, 7)
mock_llm(str(val))
agent_step("done", {"value": val})
""",
    )
    spec = tmp_path / "smoke.agent.yaml"
    _write_file(
        spec,
        """
schema_version: "0.3"
name: smoke-test
command: python agent.py
workdir: .
strict: true
budget_thresholds:
  max_tool_calls: 10
  max_tokens: 50
""",
    )
    return spec


class TestCliSmoke:
    def test_init_creates_workspace(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["init", str(tmp_path)])
        assert result.exit_code == 0
        assert (tmp_path / ".trajectly").is_dir()
        assert (tmp_path / ".trajectly" / "baselines").is_dir()

    def test_record_then_run_pass(self, tmp_path: Path) -> None:
        spec = _setup_fixture_agent(tmp_path)
        assert runner.invoke(app, ["init", str(tmp_path)]).exit_code == 0
        assert runner.invoke(app, ["record", str(spec), "--project-root", str(tmp_path)]).exit_code == 0

        result = runner.invoke(app, ["run", str(spec), "--project-root", str(tmp_path)])
        assert result.exit_code == 0

    def test_report_json_output(self, tmp_path: Path) -> None:
        spec = _setup_fixture_agent(tmp_path)
        assert runner.invoke(app, ["init", str(tmp_path)]).exit_code == 0
        assert runner.invoke(app, ["record", str(spec), "--project-root", str(tmp_path)]).exit_code == 0
        assert runner.invoke(app, ["run", str(spec), "--project-root", str(tmp_path)]).exit_code == 0

        report_result = runner.invoke(app, ["report", "--json", "--project-root", str(tmp_path)])
        assert report_result.exit_code == 0
        json_text = report_result.output.split("\n}")
        payload = json.loads(json_text[0] + "\n}")
        assert "reports" in payload

    def test_report_pr_comment_output(self, tmp_path: Path) -> None:
        spec = _setup_fixture_agent(tmp_path)
        assert runner.invoke(app, ["init", str(tmp_path)]).exit_code == 0
        assert runner.invoke(app, ["record", str(spec), "--project-root", str(tmp_path)]).exit_code == 0
        assert runner.invoke(app, ["run", str(spec), "--project-root", str(tmp_path)]).exit_code == 0

        report_result = runner.invoke(app, ["report", "--pr-comment", "--project-root", str(tmp_path)])
        assert report_result.exit_code == 0
        assert "smoke-test" in report_result.output

    def test_help_works(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "init" in result.output
        assert "record" in result.output
        assert "run" in result.output
        assert "report" in result.output

    def test_exit_codes_preserved(self, tmp_path: Path) -> None:
        """init=0, record=0, run with no regression=0."""
        spec = _setup_fixture_agent(tmp_path)
        init = runner.invoke(app, ["init", str(tmp_path)])
        assert init.exit_code == 0

        record = runner.invoke(app, ["record", str(spec), "--project-root", str(tmp_path)])
        assert record.exit_code == 0

        run = runner.invoke(app, ["run", str(spec), "--project-root", str(tmp_path)])
        assert run.exit_code == 0

    def test_version_flag(self) -> None:
        from trajectly import __version__

        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.output
        assert result.output.strip().startswith("trajectly ")

    def test_spec_discovery_ordering_deterministic(self, tmp_path: Path) -> None:
        """discover_spec_files returns sorted paths regardless of creation order."""
        from trajectly.cli.engine import discover_spec_files

        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()
        for name in ["zebra.agent.yaml", "alpha.agent.yaml", "middle.agent.yaml"]:
            _write_file(
                specs_dir / name,
                'schema_version: "0.3"\nname: ' + name.replace(".agent.yaml", "") + "\ncommand: echo ok",
            )

        result = discover_spec_files(tmp_path)
        paths_as_str = [str(p) for p in result]
        assert paths_as_str == sorted(paths_as_str), f"Discovery order not deterministic: {paths_as_str}"

        result2 = discover_spec_files(tmp_path)
        assert result == result2, "Repeated discovery gave different order"
