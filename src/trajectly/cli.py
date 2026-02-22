from __future__ import annotations

import json
from pathlib import Path

import typer

from trajectly.constants import EXIT_INTERNAL_ERROR, EXIT_REGRESSION, EXIT_SUCCESS
from trajectly.engine import (
    CommandOutcome,
    diff_traces,
    initialize_workspace,
    latest_report_path,
    read_latest_report,
    record_specs,
    run_specs,
    write_diff_report,
)
from trajectly.report import render_markdown
from trajectly.specs import BudgetThresholds

app = typer.Typer(add_completion=False, help="Deterministic regression testing for AI agent trajectories")


def _emit_outcome(outcome: CommandOutcome) -> None:
    if outcome.errors:
        for error in outcome.errors:
            typer.echo(f"ERROR: {error}", err=True)

    if outcome.latest_report_md and outcome.latest_report_md.exists():
        typer.echo(f"Latest report: {outcome.latest_report_md}")

    raise typer.Exit(outcome.exit_code)


@app.command()
def init(project_root: Path = typer.Argument(Path("."), help="Project root to initialize")) -> None:
    """Create Trajectly state directories and starter config."""
    try:
        initialize_workspace(project_root.resolve())
    except Exception as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(EXIT_INTERNAL_ERROR) from exc
    typer.echo(f"Initialized Trajectly workspace at {project_root.resolve()}")
    raise typer.Exit(EXIT_SUCCESS)


@app.command()
def record(
    targets: list[str] = typer.Argument(..., help="Spec files or glob patterns"),
    project_root: Path = typer.Option(Path("."), "--project-root", help="Project root"),
) -> None:
    """Record deterministic baseline trajectories and fixtures."""
    outcome = record_specs(targets=targets, project_root=project_root.resolve())
    if outcome.exit_code == EXIT_SUCCESS:
        typer.echo(f"Recorded {outcome.processed_specs} spec(s) successfully")
    _emit_outcome(outcome)


@app.command()
def run(
    targets: list[str] = typer.Argument(..., help="Spec files or glob patterns"),
    project_root: Path = typer.Option(Path("."), "--project-root", help="Project root"),
    baseline_dir: Path | None = typer.Option(None, "--baseline-dir", help="Custom baseline trace directory"),
    fixtures_dir: Path | None = typer.Option(None, "--fixtures-dir", help="Custom fixture directory"),
    strict: bool | None = typer.Option(None, "--strict/--no-strict", help="Override strict mode"),
) -> None:
    """Replay against fixtures, diff baseline vs current, and emit reports."""
    outcome = run_specs(
        targets=targets,
        project_root=project_root.resolve(),
        baseline_dir=baseline_dir,
        fixtures_dir=fixtures_dir,
        strict_override=strict,
    )

    if outcome.latest_report_md and outcome.latest_report_md.exists():
        typer.echo(outcome.latest_report_md.read_text(encoding="utf-8"))
    _emit_outcome(outcome)


@app.command()
def diff(
    baseline: Path = typer.Option(..., "--baseline", exists=True, file_okay=True, dir_okay=False),
    current: Path = typer.Option(..., "--current", exists=True, file_okay=True, dir_okay=False),
    spec_name: str = typer.Option("adhoc", "--spec-name", help="Spec label in report output"),
    json_output: Path | None = typer.Option(None, "--json-output", help="Write JSON report to this path"),
    markdown_output: Path | None = typer.Option(None, "--markdown-output", help="Write Markdown report path"),
    max_latency_ms: int | None = typer.Option(None, "--max-latency-ms"),
    max_tool_calls: int | None = typer.Option(None, "--max-tool-calls"),
    max_tokens: int | None = typer.Option(None, "--max-tokens"),
) -> None:
    """Diff two trace files directly."""
    budgets = BudgetThresholds(
        max_latency_ms=max_latency_ms,
        max_tool_calls=max_tool_calls,
        max_tokens=max_tokens,
    )
    result = diff_traces(
        baseline_path=baseline.resolve(),
        current_path=current.resolve(),
        budgets=budgets,
    )

    markdown = render_markdown(spec_name=spec_name, result=result)
    typer.echo(markdown)

    if json_output is not None and markdown_output is not None:
        write_diff_report(
            spec_name=spec_name,
            result=result,
            json_output=json_output.resolve(),
            markdown_output=markdown_output.resolve(),
        )

    if result.summary.get("regression", False):
        raise typer.Exit(EXIT_REGRESSION)
    raise typer.Exit(EXIT_SUCCESS)


@app.command()
def report(
    project_root: Path = typer.Option(Path("."), "--project-root", help="Project root"),
    as_json: bool = typer.Option(False, "--json", help="Print JSON instead of Markdown"),
) -> None:
    """Print the latest aggregate report."""
    try:
        content = read_latest_report(project_root.resolve(), as_json=as_json)
    except FileNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(EXIT_INTERNAL_ERROR) from exc

    if as_json:
        parsed = json.loads(content)
        typer.echo(json.dumps(parsed, indent=2, sort_keys=True))
        typer.echo(f"Source: {latest_report_path(project_root.resolve(), as_json=True)}")
    else:
        typer.echo(content)
        typer.echo(f"Source: {latest_report_path(project_root.resolve(), as_json=False)}")
    raise typer.Exit(EXIT_SUCCESS)
