from __future__ import annotations

import json
from pathlib import Path

import typer

from trajectly.constants import EXIT_INTERNAL_ERROR, EXIT_REGRESSION, EXIT_SUCCESS
from trajectly.engine import (
    SUPPORTED_ENABLE_TEMPLATES,
    CommandOutcome,
    apply_enable_template,
    build_repro_command,
    discover_spec_files,
    enable_workspace,
    initialize_workspace,
    latest_report_path,
    read_latest_report,
    record_specs,
    resolve_repro_spec,
    run_specs,
    shrink_repro,
)
from trajectly.report import render_pr_comment
from trajectly.specs.migrate import migrate_spec_file


def _version_callback(value: bool) -> None:
    if value:
        from trajectly import __version__

        typer.echo(f"trajectly {__version__}")
        raise typer.Exit()


app = typer.Typer(add_completion=False, help="Regression testing for AI agents")


@app.callback(invoke_without_command=True)
def _main(
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True, help="Print version and exit."
    ),
) -> None:
    pass
baseline_app = typer.Typer(add_completion=False, help="Manage baseline update workflows")
migrate_app = typer.Typer(add_completion=False, help="Migration helpers")
app.add_typer(baseline_app, name="baseline")
app.add_typer(migrate_app, name="migrate")


def _emit_outcome(outcome: CommandOutcome) -> None:
    if outcome.errors:
        for error in outcome.errors:
            typer.echo(f"ERROR: {error}", err=True)

    if outcome.latest_report_md and outcome.latest_report_md.exists():
        typer.echo(f"Latest report: {outcome.latest_report_md}")

    if outcome.exit_code == EXIT_REGRESSION:
        typer.echo("Tip: run `trajectly repro` to reproduce, or `trajectly shrink` to minimize.", err=True)

    raise typer.Exit(outcome.exit_code)


def _resolve_targets_for_command(
    *,
    project_root: Path,
    targets: list[str] | None,
    auto: bool,
) -> list[str]:
    resolved_targets = list(targets or [])
    if auto:
        discovered = [str(path) for path in discover_spec_files(project_root.resolve())]
        resolved_targets = sorted(set([*resolved_targets, *discovered]))
        if not resolved_targets:
            raise ValueError(
                f"No .agent.yaml specs discovered under {project_root.resolve()}. "
                "Add a spec or pass explicit targets."
            )
        return resolved_targets

    if not resolved_targets:
        raise ValueError("No targets provided. Pass spec/glob targets or use --auto.")
    return resolved_targets


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
def enable(
    project_root: Path = typer.Argument(Path("."), help="Project root to enable"),
    template: str | None = typer.Option(
        None,
        "--template",
        help="Starter template: openai | langchain | autogen",
    ),
) -> None:
    """Set up Trajectly in an existing project with scaffolding and auto-discovery."""
    _enable(project_root=project_root, template=template)


def _enable(project_root: Path, template: str | None) -> None:
    """Set up Trajectly in an existing project with scaffolding and auto-discovery."""
    try:
        discovered = enable_workspace(project_root.resolve())
        created_template_files: list[Path] = []
        if template is not None:
            created_template_files = apply_enable_template(project_root.resolve(), template)
    except Exception as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(EXIT_INTERNAL_ERROR) from exc

    typer.echo(f"Enabled Trajectly workspace at {project_root.resolve()}")
    if template is not None:
        typer.echo(f"Applied template: {template}")
        if created_template_files:
            typer.echo("Template files created:")
            for path in created_template_files:
                typer.echo(f"- {path}")
        else:
            supported = ", ".join(sorted(SUPPORTED_ENABLE_TEMPLATES))
            typer.echo("Template files already existed; no files written.")
            typer.echo(f"Supported templates: {supported}")

    typer.echo("Next step: trajectly record --auto")
    if discovered:
        typer.echo("Discovered specs:")
        for spec_path in discovered:
            typer.echo(f"- {spec_path}")
    raise typer.Exit(EXIT_SUCCESS)


@app.command()
def record(
    targets: list[str] | None = typer.Argument(None, help="Spec files or glob patterns"),
    project_root: Path = typer.Option(Path("."), "--project-root", help="Project root"),
    auto: bool = typer.Option(False, "--auto", help="Auto-discover .agent.yaml specs"),
    allow_ci_write: bool = typer.Option(
        False,
        "--allow-ci-write",
        help="Allow baseline writes when TRAJECTLY_CI=1 (explicit override).",
    ),
) -> None:
    """Record baseline agent runs and fixtures for replay."""
    try:
        resolved_targets = _resolve_targets_for_command(project_root=project_root, targets=targets, auto=auto)
    except ValueError as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(EXIT_INTERNAL_ERROR) from exc

    outcome = record_specs(
        targets=resolved_targets,
        project_root=project_root.resolve(),
        allow_ci_write=allow_ci_write,
    )
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
    """Run agent specs against recorded baselines and report regressions."""
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
def repro(
    selector: str = typer.Argument("latest", help="Spec name/slug from latest report, or explicit spec path"),
    project_root: Path = typer.Option(Path("."), "--project-root", help="Project root"),
    strict: bool | None = typer.Option(None, "--strict/--no-strict", help="Override strict mode"),
    print_only: bool = typer.Option(False, "--print-only", help="Print repro command without executing"),
) -> None:
    """Reproduce the latest regression (or selected spec) with one command."""
    project_root = project_root.resolve()

    explicit_path = Path(selector)
    if selector != "latest" and explicit_path.exists():
        spec_path = explicit_path.resolve()
    else:
        resolved_selector = None if selector == "latest" else selector
        try:
            _, spec_path = resolve_repro_spec(project_root, resolved_selector)
        except (FileNotFoundError, ValueError) as exc:
            typer.echo(f"ERROR: {exc}", err=True)
            raise typer.Exit(EXIT_INTERNAL_ERROR) from exc

    command = build_repro_command(spec_path=spec_path, project_root=project_root, strict_override=strict)
    typer.echo(f"Repro command: {command}")
    if print_only:
        raise typer.Exit(EXIT_SUCCESS)

    outcome = run_specs(
        targets=[str(spec_path)],
        project_root=project_root,
        strict_override=strict,
    )
    if outcome.latest_report_md and outcome.latest_report_md.exists():
        typer.echo(outcome.latest_report_md.read_text(encoding="utf-8"))
    _emit_outcome(outcome)


@app.command()
def shrink(
    selector: str = typer.Argument("latest", help="Spec name/slug from latest report, or explicit selector"),
    project_root: Path = typer.Option(Path("."), "--project-root", help="Project root"),
    max_seconds: float = typer.Option(10.0, "--max-seconds", min=0.1, help="Maximum shrink time budget"),
    max_iterations: int = typer.Option(200, "--max-iterations", min=1, help="Maximum ddmin iterations"),
) -> None:
    """Minimize a failing trace to the smallest reproducing example."""
    resolved_selector = None if selector == "latest" else selector
    outcome = shrink_repro(
        project_root=project_root.resolve(),
        selector=resolved_selector,
        max_seconds=max_seconds,
        max_iterations=max_iterations,
    )
    if outcome.exit_code == EXIT_SUCCESS:
        typer.echo("Shrink completed and report updated with shrink stats.")
    _emit_outcome(outcome)


@baseline_app.command("update")
def baseline_update(
    targets: list[str] | None = typer.Argument(None, help="Spec files or glob patterns"),
    project_root: Path = typer.Option(Path("."), "--project-root", help="Project root"),
    auto: bool = typer.Option(False, "--auto", help="Auto-discover .agent.yaml specs"),
    allow_ci_write: bool = typer.Option(
        False,
        "--allow-ci-write",
        help="Allow baseline writes when TRAJECTLY_CI=1 (explicit override).",
    ),
) -> None:
    """Explicitly update baselines by re-recording selected specs."""
    try:
        resolved_targets = _resolve_targets_for_command(project_root=project_root, targets=targets, auto=auto)
    except ValueError as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(EXIT_INTERNAL_ERROR) from exc

    outcome = record_specs(
        targets=resolved_targets,
        project_root=project_root.resolve(),
        allow_ci_write=allow_ci_write,
    )
    if outcome.exit_code == EXIT_SUCCESS:
        typer.echo(f"Updated baseline for {outcome.processed_specs} spec(s)")
    _emit_outcome(outcome)


@app.command()
def report(
    project_root: Path = typer.Option(Path("."), "--project-root", help="Project root"),
    as_json: bool = typer.Option(False, "--json", help="Print JSON instead of Markdown"),
    pr_comment: bool = typer.Option(False, "--pr-comment", help="Render PR-comment-ready markdown"),
) -> None:
    """Print the latest aggregate report."""
    if as_json and pr_comment:
        typer.echo("ERROR: --json and --pr-comment cannot be used together", err=True)
        raise typer.Exit(EXIT_INTERNAL_ERROR)

    if pr_comment:
        try:
            raw_json = read_latest_report(project_root.resolve(), as_json=True)
        except FileNotFoundError as exc:
            typer.echo(f"ERROR: {exc}. Run `trajectly run` first to generate a report.", err=True)
            raise typer.Exit(EXIT_INTERNAL_ERROR) from exc
        parsed = json.loads(raw_json)
        typer.echo(render_pr_comment(parsed))
        typer.echo(f"Source: {latest_report_path(project_root.resolve(), as_json=True)}")
    else:
        try:
            content = read_latest_report(project_root.resolve(), as_json=as_json)
        except FileNotFoundError as exc:
            typer.echo(f"ERROR: {exc}. Run `trajectly run` first to generate a report.", err=True)
            raise typer.Exit(EXIT_INTERNAL_ERROR) from exc

        if as_json:
            parsed = json.loads(content)
            typer.echo(json.dumps(parsed, indent=2, sort_keys=True))
            typer.echo(f"Source: {latest_report_path(project_root.resolve(), as_json=True)}")
        else:
            typer.echo(content)
            typer.echo(f"Source: {latest_report_path(project_root.resolve(), as_json=False)}")
    raise typer.Exit(EXIT_SUCCESS)


@migrate_app.command("spec")
def migrate_spec_command(
    spec_path: Path = typer.Argument(..., exists=True, file_okay=True, dir_okay=False, help="Spec file to convert"),
    output: Path | None = typer.Option(None, "--output", help="Output file path for converted v0.3 spec"),
    in_place: bool = typer.Option(False, "--in-place", help="Rewrite the input file in place"),
) -> None:
    """Convert a legacy Trajectly spec to v0.3 format."""
    try:
        destination = migrate_spec_file(
            spec_path=spec_path.resolve(),
            output_path=output.resolve() if output is not None else None,
            in_place=in_place,
        )
    except Exception as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(EXIT_INTERNAL_ERROR) from exc

    typer.echo(f"Migrated spec written to: {destination}")
    raise typer.Exit(EXIT_SUCCESS)
