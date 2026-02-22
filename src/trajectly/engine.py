from __future__ import annotations

import json
import os
import re
import uuid
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from trajectly.constants import (
    BASELINES_DIR,
    CURRENT_DIR,
    EXIT_INTERNAL_ERROR,
    EXIT_REGRESSION,
    EXIT_SUCCESS,
    FIXTURES_DIR,
    REPORTS_DIR,
    SCHEMA_VERSION,
    STATE_DIR,
    TMP_DIR,
    TRACE_EVENT_TYPES,
)
from trajectly.contracts import evaluate_contracts
from trajectly.diff import compare_traces
from trajectly.diff.models import DiffResult, Finding
from trajectly.events import (
    TraceEvent,
    compute_event_id,
    make_event,
    read_events_jsonl,
    write_events_jsonl,
)
from trajectly.fixtures import FixtureStore
from trajectly.plugins import run_run_hooks, run_semantic_plugins
from trajectly.redaction import apply_redactions
from trajectly.report import write_reports
from trajectly.runtime import ExecutionResult, execute_spec
from trajectly.schema import validate_latest_report_dict
from trajectly.specs import AgentSpec, BudgetThresholds, load_specs


@dataclass(slots=True)
class CommandOutcome:
    exit_code: int
    processed_specs: int
    regressions: int = 0
    errors: list[str] = field(default_factory=list)
    latest_report_json: Path | None = None
    latest_report_md: Path | None = None


@dataclass(slots=True)
class _StatePaths:
    root: Path
    state: Path
    baselines: Path
    current: Path
    fixtures: Path
    reports: Path
    tmp: Path


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower())
    slug = slug.strip("-")
    return slug or "spec"


def _state_paths(project_root: Path) -> _StatePaths:
    state = project_root / STATE_DIR
    return _StatePaths(
        root=project_root,
        state=state,
        baselines=project_root / BASELINES_DIR,
        current=project_root / CURRENT_DIR,
        fixtures=project_root / FIXTURES_DIR,
        reports=project_root / REPORTS_DIR,
        tmp=project_root / TMP_DIR,
    )


def _ensure_state_dirs(paths: _StatePaths) -> None:
    for directory in [paths.state, paths.baselines, paths.current, paths.fixtures, paths.reports, paths.tmp]:
        directory.mkdir(parents=True, exist_ok=True)


def initialize_workspace(project_root: Path) -> None:
    paths = _state_paths(project_root)
    _ensure_state_dirs(paths)

    config_path = paths.state / "config.yaml"
    if not config_path.exists():
        config_path.write_text(
            "schema_version: v1\ndefault_fixture_policy: by_index\ndefault_strict: false\n",
            encoding="utf-8",
        )

    sample_spec_dir = project_root / "tests"
    sample_spec_dir.mkdir(parents=True, exist_ok=True)
    sample_spec = sample_spec_dir / "sample.agent.yaml"
    if not sample_spec.exists():
        sample_spec.write_text(
            "name: sample\ncommand: python agents/simple_agent.py\nfixture_policy: by_index\nstrict: true\n",
            encoding="utf-8",
        )


_AUTO_SPEC_EXCLUDED_DIRS = {
    ".git",
    ".github",
    ".trajectly",
    ".venv",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
}


def discover_spec_files(project_root: Path) -> list[Path]:
    """Discover agent specs for auto-mode commands in deterministic order."""
    root = project_root.resolve()
    discovered: list[Path] = []
    for walk_root, dirs, files in os.walk(root):
        dirs[:] = sorted(
            directory
            for directory in dirs
            if directory not in _AUTO_SPEC_EXCLUDED_DIRS and not directory.startswith(".")
        )
        for filename in sorted(files):
            if filename.endswith(".agent.yaml"):
                discovered.append((Path(walk_root) / filename).resolve())
    return sorted(discovered, key=lambda path: str(path))


def enable_workspace(project_root: Path) -> list[Path]:
    """Initialize workspace and return discovered specs for onboarding output."""
    initialize_workspace(project_root.resolve())
    return discover_spec_files(project_root.resolve())


def _build_trace(spec: AgentSpec, result: ExecutionResult, run_id: str) -> list[TraceEvent]:
    events: list[TraceEvent] = []
    seq = 1
    events.append(
        make_event(
            event_type="run_started",
            seq=seq,
            run_id=run_id,
            rel_ms=0,
            payload={"spec_name": spec.name, "spec_path": str(spec.source_path)},
            meta={"mode": "record_or_replay"},
        )
    )

    last_rel = 0
    for raw in result.raw_events:
        raw_type = str(raw.get("event_type", "")).strip()
        if raw_type not in TRACE_EVENT_TYPES:
            continue
        payload = raw.get("payload", {})
        payload_map = payload if isinstance(payload, dict) else {"value": payload}

        meta = raw.get("meta", {})
        meta_map = meta if isinstance(meta, dict) else {}

        rel_value = raw.get("rel_ms", last_rel)
        if isinstance(rel_value, (int, float, str)):
            try:
                rel_ms = int(rel_value)
            except ValueError:
                rel_ms = last_rel
        else:
            rel_ms = last_rel
        rel_ms = max(rel_ms, last_rel)
        last_rel = rel_ms

        seq += 1
        events.append(
            make_event(
                event_type=raw_type,
                seq=seq,
                run_id=run_id,
                rel_ms=rel_ms,
                payload=payload_map,
                meta=meta_map,
            )
        )

    seq += 1
    events.append(
        make_event(
            event_type="run_finished",
            seq=seq,
            run_id=run_id,
            rel_ms=max(last_rel, result.duration_ms),
            payload={
                "returncode": result.returncode,
                "duration_ms": result.duration_ms,
                "stdout_tail": result.stdout[-2000:],
                "stderr_tail": result.stderr[-2000:],
                "internal_error": result.internal_error,
            },
            meta={},
        )
    )

    if spec.redact:
        for event in events:
            event.payload = apply_redactions(event.payload, spec.redact)
            event.meta = apply_redactions(event.meta, spec.redact)
            event.event_id = compute_event_id(event)

    return events


def _write_latest_report(paths: _StatePaths, aggregate: dict[str, Any], markdown: str) -> tuple[Path, Path]:
    latest_json = paths.reports / "latest.json"
    latest_md = paths.reports / "latest.md"
    latest_json.write_text(json.dumps(aggregate, indent=2, sort_keys=True), encoding="utf-8")
    latest_md.write_text(markdown, encoding="utf-8")
    return latest_json, latest_md


def _refresh_summary(result: DiffResult) -> None:
    counts = Counter(f.classification for f in result.findings)
    result.summary["regression"] = bool(result.findings)
    result.summary["finding_count"] = len(result.findings)
    result.summary["classifications"] = dict(counts)


def _aggregate_markdown(rows: list[dict[str, Any]], errors: list[str]) -> str:
    lines: list[str] = []
    lines.append("# Trajectly Latest Run")
    lines.append("")
    if errors:
        lines.append("## Errors")
        lines.append("")
        for error in errors:
            lines.append(f"- {error}")
        lines.append("")

    lines.append("## Specs")
    lines.append("")
    if not rows:
        lines.append("No specs processed.")
    else:
        for row in rows:
            status = "regression" if row["regression"] else "clean"
            lines.append(f"- `{row['spec']}`: {status}")
            lines.append(f"  - json: `{row['report_json']}`")
            lines.append(f"  - md: `{row['report_md']}`")
    lines.append("")
    return "\n".join(lines)


def record_specs(targets: list[str], project_root: Path) -> CommandOutcome:
    paths = _state_paths(project_root)
    _ensure_state_dirs(paths)

    try:
        specs = load_specs(targets, cwd=project_root)
    except Exception as exc:
        return CommandOutcome(exit_code=EXIT_INTERNAL_ERROR, processed_specs=0, errors=[str(exc)])

    errors: list[str] = []
    for spec in specs:
        slug = _slugify(spec.name)
        run_id = f"{slug}-{uuid.uuid4().hex[:8]}"
        raw_events_path = paths.tmp / f"{slug}.record.events.jsonl"

        result = execute_spec(
            spec=spec,
            mode="record",
            events_path=raw_events_path,
            fixtures_path=None,
            strict=spec.strict,
        )
        events = _build_trace(spec=spec, result=result, run_id=run_id)

        baseline_path = paths.baselines / f"{slug}.jsonl"
        write_events_jsonl(baseline_path, events)

        fixture_store = FixtureStore.from_events(events)
        fixture_store.save(paths.fixtures / f"{slug}.json")

        if result.internal_error:
            errors.append(f"{spec.name}: internal error: {result.internal_error}")
        elif result.returncode != 0:
            errors.append(f"{spec.name}: command failed during record with exit code {result.returncode}")

    exit_code = EXIT_INTERNAL_ERROR if errors else EXIT_SUCCESS
    return CommandOutcome(exit_code=exit_code, processed_specs=len(specs), errors=errors)


def run_specs(
    targets: list[str],
    project_root: Path,
    baseline_dir: Path | None = None,
    fixtures_dir: Path | None = None,
    strict_override: bool | None = None,
) -> CommandOutcome:
    paths = _state_paths(project_root)
    _ensure_state_dirs(paths)

    try:
        specs = load_specs(targets, cwd=project_root)
    except Exception as exc:
        return CommandOutcome(exit_code=EXIT_INTERNAL_ERROR, processed_specs=0, errors=[str(exc)])

    baseline_root = baseline_dir.resolve() if baseline_dir else paths.baselines
    fixtures_root = fixtures_dir.resolve() if fixtures_dir else paths.fixtures

    errors: list[str] = []
    regressions = 0
    rows: list[dict[str, Any]] = []

    for spec in specs:
        slug = _slugify(spec.name)
        baseline_path = baseline_root / f"{slug}.jsonl"
        fixture_path = fixtures_root / f"{slug}.json"

        if not baseline_path.exists():
            errors.append(f"{spec.name}: missing baseline trace at {baseline_path}")
            continue
        if not fixture_path.exists():
            errors.append(f"{spec.name}: missing fixtures at {fixture_path}")
            continue

        strict = strict_override if strict_override is not None else spec.strict
        run_id = f"{slug}-{uuid.uuid4().hex[:8]}"
        raw_events_path = paths.tmp / f"{slug}.run.events.jsonl"

        result = execute_spec(
            spec=spec,
            mode="replay",
            events_path=raw_events_path,
            fixtures_path=fixture_path,
            strict=strict,
        )

        current_events = _build_trace(spec=spec, result=result, run_id=run_id)
        current_path = paths.current / f"{slug}.jsonl"
        write_events_jsonl(current_path, current_events)

        baseline_events = read_events_jsonl(baseline_path)
        diff_result = compare_traces(
            baseline=baseline_events,
            current=current_events,
            budgets=spec.budget_thresholds,
        )

        if result.internal_error:
            diff_result.findings.append(
                Finding(
                    classification="runtime_error",
                    message=f"Internal runtime error: {result.internal_error}",
                )
            )

        if result.returncode != 0:
            diff_result.findings.append(
                Finding(
                    classification="runtime_error",
                    message=f"Replay command exited non-zero ({result.returncode})",
                    baseline=0,
                    current=result.returncode,
                )
            )

        plugin_findings = run_semantic_plugins(baseline=baseline_events, current=current_events)
        diff_result.findings.extend(plugin_findings)
        contract_findings = evaluate_contracts(current=current_events, contracts=spec.contracts)
        diff_result.findings.extend(contract_findings)
        _refresh_summary(diff_result)

        report_json = paths.reports / f"{slug}.json"
        report_md = paths.reports / f"{slug}.md"
        write_reports(spec_name=spec.name, result=diff_result, json_path=report_json, md_path=report_md)

        run_run_hooks(
            context={
                "schema_version": SCHEMA_VERSION,
                "spec": spec.name,
                "slug": slug,
                "run_id": run_id,
                "regression": diff_result.summary.get("regression", False),
            },
            report_paths={
                "json": report_json,
                "markdown": report_md,
                "baseline": baseline_path,
                "current": current_path,
            },
        )

        if diff_result.summary.get("regression", False):
            regressions += 1

        rows.append(
            {
                "spec": spec.name,
                "slug": slug,
                "regression": diff_result.summary.get("regression", False),
                "report_json": str(report_json),
                "report_md": str(report_md),
                "baseline": str(baseline_path),
                "current": str(current_path),
            }
        )

    aggregate = {
        "schema_version": SCHEMA_VERSION,
        "processed_specs": len(rows),
        "regressions": regressions,
        "errors": errors,
        "reports": rows,
    }
    latest_md_text = _aggregate_markdown(rows=rows, errors=errors)
    latest_json_path, latest_md_path = _write_latest_report(paths=paths, aggregate=aggregate, markdown=latest_md_text)

    if errors:
        exit_code = EXIT_INTERNAL_ERROR
    elif regressions > 0:
        exit_code = EXIT_REGRESSION
    else:
        exit_code = EXIT_SUCCESS

    return CommandOutcome(
        exit_code=exit_code,
        processed_specs=len(rows),
        regressions=regressions,
        errors=errors,
        latest_report_json=latest_json_path,
        latest_report_md=latest_md_path,
    )


def diff_traces(
    baseline_path: Path,
    current_path: Path,
    budgets: BudgetThresholds | None = None,
) -> DiffResult:
    baseline_events = read_events_jsonl(baseline_path)
    current_events = read_events_jsonl(current_path)
    return compare_traces(baseline_events, current_events, budgets=budgets)


def write_diff_report(
    spec_name: str,
    result: DiffResult,
    json_output: Path,
    markdown_output: Path,
) -> None:
    write_reports(spec_name=spec_name, result=result, json_path=json_output, md_path=markdown_output)


def read_latest_report(project_root: Path, as_json: bool) -> str:
    paths = _state_paths(project_root)
    if as_json:
        path = paths.reports / "latest.json"
    else:
        path = paths.reports / "latest.md"
    if not path.exists():
        raise FileNotFoundError(f"Latest report not found: {path}")
    content = path.read_text(encoding="utf-8")
    if as_json:
        parsed = json.loads(content)
        validate_latest_report_dict(parsed)
    return content


def latest_report_path(project_root: Path, as_json: bool) -> Path:
    paths = _state_paths(project_root)
    return paths.reports / ("latest.json" if as_json else "latest.md")
