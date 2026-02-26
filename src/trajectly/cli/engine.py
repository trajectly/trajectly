from __future__ import annotations

import json
import os
import uuid
from collections import Counter
from pathlib import Path
from typing import Any

from trajectly.constants import (
    EXIT_INTERNAL_ERROR,
    EXIT_REGRESSION,
    EXIT_SUCCESS,
    SCHEMA_VERSION,
    TRACE_EVENT_TYPES,
    TRT_NORMALIZER_VERSION,
    TRT_SPEC_SCHEMA_VERSION,
)
from trajectly.contracts import evaluate_contracts
from trajectly.diff import compare_traces
from trajectly.diff.models import DiffResult, Finding
from trajectly.engine_common import (
    CommandOutcome,
    _baseline_meta_path,
    _ensure_state_dirs,
    _slugify,
    _state_paths,
    _StatePaths,
)
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
from trajectly.report.schema import ShrinkStatsV03
from trajectly.runtime import ExecutionResult, execute_spec
from trajectly.schema import validate_latest_report_dict
from trajectly.shrink import ddmin_shrink
from trajectly.specs import AgentSpec, load_specs
from trajectly.trace.io import read_trace_meta, write_trace_meta
from trajectly.trace.models import TraceMetaV03
from trajectly.trt.runner import TRTResult, evaluate_trt
from trajectly.trt.types import TRTViolation

__all__ = [
    "SUPPORTED_ENABLE_TEMPLATES",
    "CommandOutcome",
    "apply_enable_template",
    "build_repro_command",
    "discover_spec_files",
    "enable_workspace",
    "initialize_workspace",
    "latest_report_path",
    "read_latest_report",
    "record_specs",
    "resolve_repro_spec",
    "run_specs",
    "shrink_repro",
]


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

SUPPORTED_ENABLE_TEMPLATES = {"openai", "langchain", "autogen"}


def _template_assets(template: str) -> dict[Path, str]:
    if template == "openai":
        return {
            Path("templates/openai_agent.py"): (
                "from trajectly.sdk import agent_step, openai_chat_completion\n\n"
                "class _Completions:\n"
                "    def create(self, **_kwargs):\n"
                "        return {\n"
                "            'choices': [{'message': {'content': 'openai-template-ok'}}],\n"
                "            'usage': {'total_tokens': 4},\n"
                "        }\n\n"
                "class _Chat:\n"
                "    completions = _Completions()\n\n"
                "class MockOpenAIClient:\n"
                "    chat = _Chat()\n\n"
                "agent_step('start')\n"
                "result = openai_chat_completion(\n"
                "    MockOpenAIClient(),\n"
                "    model='gpt-mock',\n"
                "    messages=[{'role': 'user', 'content': 'hello'}],\n"
                ")\n"
                "agent_step('done', {'response': result['response']})\n"
            ),
            Path("openai.agent.yaml"): (
                "name: template-openai\n"
                "command: python templates/openai_agent.py\n"
                "fixture_policy: by_hash\n"
                "strict: true\n"
            ),
        }
    if template == "langchain":
        return {
            Path("templates/langchain_agent.py"): (
                "from trajectly.sdk import agent_step, langchain_invoke\n\n"
                "class MockRunnable:\n"
                "    def invoke(self, _input_value):\n"
                "        return {'response': 'langchain-template-ok', 'usage': {'total_tokens': 3}}\n\n"
                "agent_step('start')\n"
                "result = langchain_invoke(MockRunnable(), {'prompt': 'hello'})\n"
                "agent_step('done', {'response': result['response']})\n"
            ),
            Path("langchain.agent.yaml"): (
                "name: template-langchain\n"
                "command: python templates/langchain_agent.py\n"
                "fixture_policy: by_hash\n"
                "strict: true\n"
            ),
        }
    if template == "autogen":
        return {
            Path("templates/autogen_agent.py"): (
                "from trajectly.sdk import agent_step, autogen_chat_run\n\n"
                "class MockChatRunner:\n"
                "    def run(self, messages):\n"
                "        return {\n"
                "            'response': f\"autogen-template-ok:{len(messages)}\",\n"
                "            'usage': {'total_tokens': 2},\n"
                "        }\n\n"
                "agent_step('start')\n"
                "result = autogen_chat_run(MockChatRunner(), [{'role': 'user', 'content': 'hello'}])\n"
                "agent_step('done', {'response': result['response']})\n"
            ),
            Path("autogen.agent.yaml"): (
                "name: template-autogen\n"
                "command: python templates/autogen_agent.py\n"
                "fixture_policy: by_hash\n"
                "strict: true\n"
            ),
        }
    raise ValueError(f"Unsupported template: {template}")


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


def apply_enable_template(project_root: Path, template: str) -> list[Path]:
    normalized = template.strip().lower()
    if normalized not in SUPPORTED_ENABLE_TEMPLATES:
        supported = ", ".join(sorted(SUPPORTED_ENABLE_TEMPLATES))
        raise ValueError(f"Unsupported template: {template}. Supported templates: {supported}")

    created: list[Path] = []
    assets = _template_assets(normalized)
    for rel_path, content in assets.items():
        path = (project_root.resolve() / rel_path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            continue
        path.write_text(content, encoding="utf-8")
        created.append(path)
    return created


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


def _trt_violation_to_finding(violation: TRTViolation) -> Finding:
    path = f"$.trt.event[{violation.event_index}]"
    classification = violation.code.strip().lower()
    return Finding(
        classification=classification,
        message=violation.message,
        path=path,
        baseline=violation.expected,
        current=violation.observed,
    )


def _merge_trt_findings(diff_result: DiffResult, trt_result: TRTResult) -> None:
    existing_keys = {
        (finding.classification, finding.message, finding.path)
        for finding in diff_result.findings
    }
    for violation in trt_result.all_violations:
        finding = _trt_violation_to_finding(violation)
        key = (finding.classification, finding.message, finding.path)
        if key in existing_keys:
            continue
        diff_result.findings.append(finding)
        existing_keys.add(key)


def _write_counterexample_prefix(
    *,
    paths: _StatePaths,
    slug: str,
    current_events: list[TraceEvent],
    witness_index: int,
) -> Path:
    cutoff = max(witness_index, 0)
    prefix_events = current_events[: cutoff + 1]
    prefix_path = paths.repros / f"{slug}.counterexample.prefix.jsonl"
    write_events_jsonl(prefix_path, prefix_events)
    return prefix_path


def _augment_report_with_trt(report_json: Path, trt_result: TRTResult) -> None:
    raw = json.loads(report_json.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return
    raw["trt_v03"] = trt_result.report.to_dict()
    report_json.write_text(json.dumps(raw, indent=2, sort_keys=True), encoding="utf-8")


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
            if row.get("trt_status"):
                trt_status = str(row["trt_status"])
                witness = row.get("trt_witness_index")
                if witness is None:
                    lines.append(f"  - trt: `{trt_status}`")
                else:
                    lines.append(f"  - trt: `{trt_status}` (witness={witness})")
            if row.get("repro_command"):
                lines.append(f"  - repro: `{row['repro_command']}`")
            if row.get("trt_counterexample_reduced"):
                lines.append(f"  - trt reduced: `{row['trt_counterexample_reduced']}`")
    lines.append("")
    return "\n".join(lines)


def _build_repro_command(spec_path: Path, project_root: Path, strict_override: bool | None = None) -> str:
    command = f'trajectly run "{spec_path}" --project-root "{project_root}"'
    if strict_override is True:
        command += " --strict"
    if strict_override is False:
        command += " --no-strict"
    return command


def _write_repro_artifact(
    *,
    paths: _StatePaths,
    spec: AgentSpec,
    slug: str,
    diff_result: DiffResult,
    baseline_events: list[TraceEvent],
    current_events: list[TraceEvent],
    report_json: Path,
    report_md: Path,
    trt_status: str | None = None,
    trt_failure_class: str | None = None,
    trt_witness_index: int | None = None,
    trt_counterexample_prefix: Path | None = None,
) -> Path:
    first_divergence = diff_result.summary.get("first_divergence")
    cutoff_index: int | None = None
    if isinstance(first_divergence, dict):
        raw_index = first_divergence.get("index")
        if isinstance(raw_index, int) and raw_index >= 0:
            cutoff_index = raw_index

    baseline_min_path, current_min_path = _write_minimized_repro_traces(
        paths=paths,
        slug=slug,
        baseline_events=baseline_events,
        current_events=current_events,
        cutoff_index=cutoff_index,
    )

    repro_path = paths.repros / f"{slug}.json"
    payload = {
        "schema_version": SCHEMA_VERSION,
        "spec": spec.name,
        "slug": slug,
        "spec_path": str(spec.source_path),
        "first_divergence": first_divergence,
        "finding_count": diff_result.summary.get("finding_count", 0),
        "regression": diff_result.summary.get("regression", False),
        "report_json": str(report_json),
        "report_md": str(report_md),
        "repro_command": _build_repro_command(spec_path=spec.source_path, project_root=paths.root),
        "baseline_min_trace": str(baseline_min_path),
        "current_min_trace": str(current_min_path),
    }
    if trt_status is not None:
        payload["trt_status"] = trt_status
    if trt_failure_class is not None:
        payload["trt_failure_class"] = trt_failure_class
    if trt_witness_index is not None:
        payload["trt_witness_index"] = trt_witness_index
    if trt_counterexample_prefix is not None:
        payload["trt_counterexample_prefix"] = str(trt_counterexample_prefix)
    repro_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return repro_path


def _minimize_trace(events: list[TraceEvent], cutoff_index: int | None) -> list[TraceEvent]:
    op_types = {"tool_called", "tool_returned", "llm_called", "llm_returned"}
    minimized: list[TraceEvent] = []
    op_index = 0

    for event in events:
        if event.event_type == "run_started":
            minimized.append(event)
            continue

        if event.event_type in op_types:
            should_include = cutoff_index is None or op_index <= cutoff_index
            if should_include:
                minimized.append(event)
            op_index += 1
            continue

        if event.event_type == "agent_step":
            if cutoff_index is None or op_index <= cutoff_index + 1:
                minimized.append(event)
            continue

    finished = [event for event in events if event.event_type == "run_finished"]
    if finished:
        minimized.append(finished[-1])

    deduped: list[TraceEvent] = []
    seen: set[tuple[str, int, str]] = set()
    for event in minimized:
        key = (event.event_type, event.seq, event.event_id)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(event)
    return deduped


def _write_minimized_repro_traces(
    *,
    paths: _StatePaths,
    slug: str,
    baseline_events: list[TraceEvent],
    current_events: list[TraceEvent],
    cutoff_index: int | None,
) -> tuple[Path, Path]:
    baseline_min_path = paths.repros / f"{slug}.baseline.min.jsonl"
    current_min_path = paths.repros / f"{slug}.current.min.jsonl"
    write_events_jsonl(baseline_min_path, _minimize_trace(baseline_events, cutoff_index=cutoff_index))
    write_events_jsonl(current_min_path, _minimize_trace(current_events, cutoff_index=cutoff_index))
    return baseline_min_path, current_min_path


def _read_latest_report_dict(project_root: Path) -> dict[str, Any]:
    report_path = latest_report_path(project_root, as_json=True)
    if not report_path.exists():
        raise FileNotFoundError(f"Latest report not found: {report_path}. Run `trajectly run` first")
    data = json.loads(report_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Latest report must be JSON object: {report_path}")
    return validate_latest_report_dict(data)


def _resolve_latest_report_row(project_root: Path, selector: str | None = None) -> dict[str, Any]:
    report = _read_latest_report_dict(project_root)
    rows = report.get("reports", [])
    if not isinstance(rows, list) or not rows:
        raise ValueError("Latest report contains no specs to reproduce")

    chosen: dict[str, Any] | None = None
    if selector and selector != "latest":
        for row in rows:
            if not isinstance(row, dict):
                continue
            if row.get("spec") == selector or row.get("slug") == selector:
                chosen = row
                break
        if chosen is None:
            raise ValueError(f"Spec not found in latest report: {selector}")
    else:
        for row in rows:
            if isinstance(row, dict) and row.get("regression"):
                chosen = row
                break
        if chosen is None:
            first = rows[0]
            if isinstance(first, dict):
                chosen = first

    if chosen is None:
        raise ValueError("Unable to resolve repro target from latest report")

    return chosen


def resolve_repro_spec(project_root: Path, selector: str | None = None) -> tuple[str, Path]:
    chosen = _resolve_latest_report_row(project_root, selector)
    spec_path_raw = chosen.get("spec_path")
    if not isinstance(spec_path_raw, str) or not spec_path_raw.strip():
        raise ValueError(
            "Latest report is missing `spec_path`. Re-run `trajectly run` with this version to generate repro metadata."
        )
    return str(chosen.get("spec", "unknown")), Path(spec_path_raw).resolve()


def record_specs(
    targets: list[str],
    project_root: Path,
    *,
    allow_ci_write: bool = False,
) -> CommandOutcome:
    paths = _state_paths(project_root)
    _ensure_state_dirs(paths)

    try:
        specs = load_specs(targets, cwd=project_root)
    except Exception as exc:
        return CommandOutcome(exit_code=EXIT_INTERNAL_ERROR, processed_specs=0, errors=[str(exc)])

    if os.getenv("TRAJECTLY_CI") == "1" and not allow_ci_write:
        return CommandOutcome(
            exit_code=EXIT_INTERNAL_ERROR,
            processed_specs=0,
            errors=[
                "Baseline writes are blocked when TRAJECTLY_CI=1. "
                "Re-run `trajectly record ... --allow-ci-write` only for explicit baseline updates."
            ],
        )

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
        write_trace_meta(
            _baseline_meta_path(baseline_path),
            TraceMetaV03(
                spec_name=spec.name,
                run_id=run_id,
                mode="record",
                metadata={
                    "legacy_event_schema_version": SCHEMA_VERSION,
                    "spec_schema_version": spec.schema_version,
                },
            ),
        )

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
            errors.append(
                f"{spec.name}: missing baseline trace at {baseline_path}. "
                "Run `trajectly record` first to capture a baseline."
            )
            continue
        if spec.schema_version == TRT_SPEC_SCHEMA_VERSION:
            baseline_meta_path = _baseline_meta_path(baseline_path)
            if not baseline_meta_path.exists():
                errors.append(
                    f"{spec.name}: NORMALIZER_VERSION_MISMATCH: missing baseline meta at {baseline_meta_path}. "
                    "Re-run `trajectly record` to regenerate baseline artifacts."
                )
                continue
            try:
                baseline_meta = read_trace_meta(baseline_meta_path)
            except Exception as exc:
                errors.append(
                    f"{spec.name}: NORMALIZER_VERSION_MISMATCH: invalid baseline meta at {baseline_meta_path}: {exc}"
                )
                continue
            if baseline_meta.normalizer_version != TRT_NORMALIZER_VERSION:
                errors.append(
                    f"{spec.name}: NORMALIZER_VERSION_MISMATCH: baseline={baseline_meta.normalizer_version} "
                    f"runtime={TRT_NORMALIZER_VERSION}. Re-record baselines."
                )
                continue
        if not fixture_path.exists():
            errors.append(
                f"{spec.name}: missing fixtures at {fixture_path}. "
                "Run `trajectly record` first to capture fixtures."
            )
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

        repro_command = _build_repro_command(spec_path=spec.source_path, project_root=paths.root)
        trt_result = evaluate_trt(
            baseline_events=baseline_events,
            current_events=current_events,
            spec=spec,
            repro_command=repro_command,
            counterexample_paths={},
        )
        counterexample_prefix: Path | None = None
        if trt_result.witness is not None:
            counterexample_prefix = _write_counterexample_prefix(
                paths=paths,
                slug=slug,
                current_events=current_events,
                witness_index=trt_result.witness.witness_index,
            )
            trt_result.report.counterexample_paths["prefix"] = str(counterexample_prefix)

        if trt_result.status == "FAIL":
            _merge_trt_findings(diff_result, trt_result)

        _refresh_summary(diff_result)

        report_json = paths.reports / f"{slug}.json"
        report_md = paths.reports / f"{slug}.md"
        write_reports(spec_name=spec.name, result=diff_result, json_path=report_json, md_path=report_md)
        _augment_report_with_trt(report_json, trt_result)
        repro_artifact = _write_repro_artifact(
            paths=paths,
            spec=spec,
            slug=slug,
            diff_result=diff_result,
            baseline_events=baseline_events,
            current_events=current_events,
            report_json=report_json,
            report_md=report_md,
            trt_status=trt_result.status,
            trt_failure_class=trt_result.report.failure_class,
            trt_witness_index=trt_result.report.witness_index,
            trt_counterexample_prefix=counterexample_prefix,
        )

        run_run_hooks(
            context={
                "schema_version": SCHEMA_VERSION,
                "spec": spec.name,
                "slug": slug,
                "run_id": run_id,
                "regression": diff_result.summary.get("regression", False),
                "trt_status": trt_result.status,
                "trt_failure_class": trt_result.report.failure_class,
                "trt_witness_index": trt_result.report.witness_index,
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
                "spec_path": str(spec.source_path),
                "repro_artifact": str(repro_artifact),
                "repro_command": repro_command,
                "trt_status": trt_result.status,
                "trt_failure_class": trt_result.report.failure_class,
                "trt_witness_index": trt_result.report.witness_index,
                "trt_primary_violation": (
                    trt_result.report.primary_violation.to_dict() if trt_result.report.primary_violation else None
                ),
                "trt_counterexample_prefix": str(counterexample_prefix) if counterexample_prefix else None,
            }
        )

    aggregate = {
        "schema_version": SCHEMA_VERSION,
        "trt_mode": True,
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


def _refresh_latest_report_row(
    *,
    paths: _StatePaths,
    slug: str,
    row_updates: dict[str, Any],
) -> tuple[Path, Path]:
    latest_json = paths.reports / "latest.json"
    if not latest_json.exists():
        raise FileNotFoundError(f"Latest report not found: {latest_json}")

    aggregate = _read_latest_report_dict(paths.root)
    rows = aggregate.get("reports", [])
    if not isinstance(rows, list):
        raise ValueError("Latest report payload is invalid: reports must be a list")

    updated = False
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("slug") != slug:
            continue
        row.update(row_updates)
        updated = True
        break
    if not updated:
        raise ValueError(f"Spec slug not found in latest report: {slug}")

    aggregate["reports"] = rows
    markdown = _aggregate_markdown(rows=rows, errors=[str(item) for item in aggregate.get("errors", [])])
    return _write_latest_report(paths=paths, aggregate=aggregate, markdown=markdown)


def shrink_repro(
    *,
    project_root: Path,
    selector: str | None = None,
    max_seconds: float = 10.0,
    max_iterations: int = 200,
) -> CommandOutcome:
    paths = _state_paths(project_root.resolve())
    _ensure_state_dirs(paths)

    try:
        selected = _resolve_latest_report_row(paths.root, selector)
    except Exception as exc:
        return CommandOutcome(exit_code=EXIT_INTERNAL_ERROR, processed_specs=0, errors=[str(exc)])

    slug = str(selected.get("slug", "")).strip()
    spec_name = str(selected.get("spec", slug or "unknown"))
    if not slug:
        return CommandOutcome(
            exit_code=EXIT_INTERNAL_ERROR,
            processed_specs=0,
            errors=["Latest report row is missing slug for shrink target"],
        )

    spec_path_raw = selected.get("spec_path")
    baseline_path_raw = selected.get("baseline")
    current_path_raw = selected.get("current")
    report_json_raw = selected.get("report_json")

    missing_fields: list[str] = []
    if not isinstance(spec_path_raw, str) or not spec_path_raw.strip():
        missing_fields.append("spec_path")
    if not isinstance(baseline_path_raw, str) or not baseline_path_raw.strip():
        missing_fields.append("baseline")
    if not isinstance(current_path_raw, str) or not current_path_raw.strip():
        missing_fields.append("current")
    if not isinstance(report_json_raw, str) or not report_json_raw.strip():
        missing_fields.append("report_json")
    if missing_fields:
        joined = ", ".join(sorted(missing_fields))
        return CommandOutcome(
            exit_code=EXIT_INTERNAL_ERROR,
            processed_specs=0,
            errors=[
                f"Latest report row for `{spec_name}` missing required fields: {joined}. Re-run `trajectly run` first."
            ],
        )

    spec_path = Path(str(spec_path_raw)).resolve()
    baseline_path = Path(str(baseline_path_raw)).resolve()
    current_path = Path(str(current_path_raw)).resolve()
    report_json_path = Path(str(report_json_raw)).resolve()

    try:
        spec = load_specs([str(spec_path)], cwd=paths.root)[0]
    except Exception as exc:
        return CommandOutcome(exit_code=EXIT_INTERNAL_ERROR, processed_specs=0, errors=[str(exc)])

    if not baseline_path.exists() or not current_path.exists():
        return CommandOutcome(
            exit_code=EXIT_INTERNAL_ERROR,
            processed_specs=0,
            errors=[f"Missing baseline/current traces for shrink target `{spec_name}`"],
        )

    baseline_events = read_events_jsonl(baseline_path)
    source_counterexample = selected.get("trt_counterexample_prefix")
    if isinstance(source_counterexample, str) and source_counterexample:
        source_path = Path(source_counterexample).resolve()
        current_events = read_events_jsonl(source_path) if source_path.exists() else read_events_jsonl(current_path)
        prefix_path = source_path if source_path.exists() else None
    else:
        current_events = read_events_jsonl(current_path)
        prefix_path = None

    repro_command = str(selected.get("repro_command", "")).strip() or _build_repro_command(
        spec_path=spec.source_path, project_root=paths.root
    )
    original_result = evaluate_trt(
        baseline_events=baseline_events,
        current_events=current_events,
        spec=spec,
        repro_command=repro_command,
        counterexample_paths={},
    )
    if original_result.status != "FAIL" or original_result.report.failure_class is None:
        return CommandOutcome(
            exit_code=EXIT_INTERNAL_ERROR,
            processed_specs=0,
            errors=[f"Shrink requires a failing TRT trace for `{spec_name}`"],
        )

    if prefix_path is None and original_result.witness is not None:
        prefix_path = _write_counterexample_prefix(
            paths=paths,
            slug=slug,
            current_events=current_events,
            witness_index=original_result.witness.witness_index,
        )

    original_failure_class = original_result.report.failure_class

    def _preserves_failure_class(candidate: list[TraceEvent]) -> bool:
        candidate_result = evaluate_trt(
            baseline_events=baseline_events,
            current_events=candidate,
            spec=spec,
            repro_command=repro_command,
            counterexample_paths={},
        )
        return (
            candidate_result.status == "FAIL"
            and candidate_result.report.failure_class == original_failure_class
        )

    try:
        shrink_result = ddmin_shrink(
            events=current_events,
            failure_predicate=_preserves_failure_class,
            max_seconds=max_seconds,
            max_iterations=max_iterations,
        )
    except Exception as exc:
        return CommandOutcome(exit_code=EXIT_INTERNAL_ERROR, processed_specs=0, errors=[str(exc)])

    reduced_path: Path | None = None
    if shrink_result.reduced:
        reduced_path = paths.repros / f"{slug}.counterexample.reduced.trace.jsonl"
        write_events_jsonl(reduced_path, shrink_result.reduced_events)

    final_counterexample_paths: dict[str, str] = {}
    if prefix_path is not None:
        final_counterexample_paths["prefix"] = str(prefix_path)
    if reduced_path is not None:
        final_counterexample_paths["reduced"] = str(reduced_path)

    final_result = evaluate_trt(
        baseline_events=baseline_events,
        current_events=shrink_result.reduced_events,
        spec=spec,
        repro_command=repro_command,
        counterexample_paths=final_counterexample_paths,
    )
    final_result.report.shrink_stats = ShrinkStatsV03(
        original_len=shrink_result.original_len,
        reduced_len=shrink_result.reduced_len,
        iterations=shrink_result.iterations,
        seconds=shrink_result.seconds,
    )

    _augment_report_with_trt(report_json_path, final_result)

    repro_artifact_raw = selected.get("repro_artifact")
    if isinstance(repro_artifact_raw, str) and repro_artifact_raw.strip():
        repro_artifact_path = Path(repro_artifact_raw).resolve()
        if repro_artifact_path.exists():
            payload = json.loads(repro_artifact_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                if prefix_path is not None:
                    payload["trt_counterexample_prefix"] = str(prefix_path)
                if reduced_path is not None:
                    payload["trt_counterexample_reduced"] = str(reduced_path)
                payload["trt_failure_class"] = final_result.report.failure_class
                payload["trt_witness_index"] = final_result.report.witness_index
                payload["trt_shrink_stats"] = final_result.report.shrink_stats.to_dict()
                repro_artifact_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    row_updates: dict[str, Any] = {
        "trt_status": final_result.status,
        "trt_failure_class": final_result.report.failure_class,
        "trt_witness_index": final_result.report.witness_index,
        "trt_primary_violation": (
            final_result.report.primary_violation.to_dict() if final_result.report.primary_violation else None
        ),
        "trt_shrink_stats": final_result.report.shrink_stats.to_dict() if final_result.report.shrink_stats else None,
    }
    if prefix_path is not None:
        row_updates["trt_counterexample_prefix"] = str(prefix_path)
    if reduced_path is not None:
        row_updates["trt_counterexample_reduced"] = str(reduced_path)

    try:
        latest_json_path, latest_md_path = _refresh_latest_report_row(paths=paths, slug=slug, row_updates=row_updates)
    except Exception as exc:
        return CommandOutcome(exit_code=EXIT_INTERNAL_ERROR, processed_specs=0, errors=[str(exc)])

    return CommandOutcome(
        exit_code=EXIT_SUCCESS,
        processed_specs=1,
        latest_report_json=latest_json_path,
        latest_report_md=latest_md_path,
    )


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


def build_repro_command(spec_path: Path, project_root: Path, strict_override: bool | None = None) -> str:
    return _build_repro_command(spec_path=spec_path, project_root=project_root, strict_override=strict_override)
