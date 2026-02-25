from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from trajectly.cli import app

runner = CliRunner()


def test_cli_report_prints_json_and_source(tmp_path: Path) -> None:
    reports_dir = tmp_path / ".trajectly" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_json = reports_dir / "latest.json"
    report_json.write_text(
        json.dumps(
            {
                "schema_version": "v1",
                "processed_specs": 1,
                "regressions": 0,
                "errors": [],
                "reports": [],
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["report", "--project-root", str(tmp_path), "--json"])

    assert result.exit_code == 0
    assert '"processed_specs": 1' in result.stdout
    assert "Source:" in result.stdout


def test_cli_report_missing_latest_file_returns_error(tmp_path: Path) -> None:
    result = runner.invoke(app, ["report", "--project-root", str(tmp_path), "--json"])

    assert result.exit_code == 2
    assert "Latest report not found" in result.output


def test_cli_report_pr_comment_output(tmp_path: Path) -> None:
    reports_dir = tmp_path / ".trajectly" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "latest.json").write_text(
        json.dumps(
            {
                "schema_version": "v1",
                "processed_specs": 1,
                "regressions": 1,
                "errors": [],
                "reports": [
                    {
                        "spec": "demo",
                        "regression": True,
                        "repro_command": "trajectly run demo.agent.yaml --project-root .",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["report", "--project-root", str(tmp_path), "--pr-comment"])
    assert result.exit_code == 0
    assert "Trajectly Regression Report" in result.stdout
    assert "`demo`" in result.stdout


def test_cli_report_rejects_json_with_pr_comment(tmp_path: Path) -> None:
    result = runner.invoke(app, ["report", "--project-root", str(tmp_path), "--json", "--pr-comment"])
    assert result.exit_code == 2
    assert "--json and --pr-comment cannot be used together" in result.output
