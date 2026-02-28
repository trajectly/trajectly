from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from trajectly.cli import app

runner = CliRunner()


def test_smoke_prompt_command_sequence(tmp_path: Path) -> None:
    project_root = tmp_path / "workspace"
    project_root.mkdir(parents=True, exist_ok=True)
    agent = project_root / "agent.py"
    agent.write_text("print('ok')\n", encoding="utf-8")
    spec = project_root / "smoke.agent.yaml"
    spec.write_text(
        (
            'schema_version: "0.4"\n'
            "name: smoke\n"
            "command: python agent.py\n"
            "workdir: .\n"
            "strict: true\n"
        ),
        encoding="utf-8",
    )
    targets = str(spec)

    init_result = runner.invoke(app, ["init", str(project_root)])
    assert init_result.exit_code == 0

    record_result = runner.invoke(app, ["record", targets, "--project-root", str(project_root)])
    assert record_result.exit_code == 0

    run_result = runner.invoke(app, ["run", targets, "--project-root", str(project_root)])
    assert run_result.exit_code == 0
