from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from trajectly.cli import app

runner = CliRunner()


def test_smoke_prompt_command_sequence(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    targets = str(repo_root / "tests" / "*.agent.yaml")

    init_result = runner.invoke(app, ["init", str(repo_root)])
    assert init_result.exit_code == 0

    record_result = runner.invoke(app, ["record", targets, "--project-root", str(repo_root)])
    assert record_result.exit_code == 0

    run_result = runner.invoke(app, ["run", targets, "--project-root", str(repo_root)])
    assert run_result.exit_code == 0
