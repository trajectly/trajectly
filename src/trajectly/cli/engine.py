from __future__ import annotations

import datetime as datetime_module
import hashlib
import json
import os
import random
import re
import subprocess
import time as time_module
import uuid
from collections import Counter, defaultdict, deque
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

from trajectly import __version__ as trajectly_version
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
from trajectly.core.canonical import sha256_of_data
from trajectly.diff import compare_traces
from trajectly.diff.models import DiffResult, Finding
from trajectly.engine_common import (
    CommandOutcome,
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
from trajectly.specs import AgentSpec, BudgetThresholds, load_specs
from trajectly.trace.io import read_trace_meta, write_trace_meta
from trajectly.trace.models import TraceMetaV03
from trajectly.trt.runner import TRTResult, evaluate_trt
from trajectly.trt.types import TRTViolation

__all__ = [
    "SUPPORTED_ENABLE_TEMPLATES",
    "CommandOutcome",
    "apply_enable_template",
    "baseline_create",
    "baseline_diff",
    "baseline_list",
    "baseline_promote",
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
            (
                "schema_version: \"0.4\"\n"
                "name: sample\n"
                "command: python agents/simple_agent.py\n"
                "fixture_policy: by_index\n"
                "strict: true\n"
            ),
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

_BASELINE_VERSION_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_DETERMINISM_CODE_RE = re.compile(
    r"(NONDETERMINISM_CLOCK_DETECTED|NONDETERMINISM_RANDOM_DETECTED|NONDETERMINISM_UUID_DETECTED|NONDETERMINISM_FILESYSTEM_DETECTED)"
)


def _validate_baseline_version(version: str) -> str:
    normalized = version.strip()
    if not normalized:
        raise ValueError("Baseline version name cannot be empty")
    if not _BASELINE_VERSION_RE.match(normalized):
        raise ValueError(
            f"Invalid baseline version `{version}`. Use only letters, numbers, dot, underscore, or dash."
        )
    return normalized


def _baseline_spec_dir(paths: _StatePaths, slug: str) -> Path:
    return paths.baselines / slug


def _baseline_version_dir(paths: _StatePaths, slug: str, version: str) -> Path:
    return _baseline_spec_dir(paths, slug) / _validate_baseline_version(version)


def _baseline_trace_path(paths: _StatePaths, slug: str, version: str) -> Path:
    return _baseline_version_dir(paths, slug, version) / "trace.jsonl"


def _baseline_trace_meta_path(paths: _StatePaths, slug: str, version: str) -> Path:
    return _baseline_version_dir(paths, slug, version) / "trace.meta.json"


def _baseline_fixture_path(paths: _StatePaths, slug: str, version: str) -> Path:
    return _baseline_version_dir(paths, slug, version) / "fixtures.json"


def _baseline_runtime_meta_path(paths: _StatePaths, slug: str, version: str) -> Path:
    return _baseline_version_dir(paths, slug, version) / "baseline.meta.json"


def _legacy_baseline_trace_path(paths: _StatePaths, slug: str) -> Path:
    return paths.baselines / f"{slug}.jsonl"


def _legacy_fixture_path(paths: _StatePaths, slug: str) -> Path:
    return paths.fixtures / f"{slug}.json"


def _legacy_meta_path(paths: _StatePaths, slug: str) -> Path:
    return paths.baselines / f"{slug}.meta.json"


def _reject_legacy_baseline_layout(paths: _StatePaths, slug: str) -> str | None:
    legacy_paths = [
        _legacy_baseline_trace_path(paths, slug),
        _legacy_meta_path(paths, slug),
        _legacy_fixture_path(paths, slug),
    ]
    present = [path for path in legacy_paths if path.exists()]
    if not present:
        return None
    joined = ", ".join(str(path) for path in present)
    return (
        f"Hard cutover active: legacy baseline layout is no longer supported for `{slug}`. "
        f"Found: {joined}. "
        "Re-record using `python -m trajectly baseline create --name v1 <spec>`."
    )


def _promoted_pointer_path(paths: _StatePaths, slug: str) -> Path:
    return paths.current / f"{slug}.json"


def _read_promoted_version(paths: _StatePaths, slug: str) -> str | None:
    pointer = _promoted_pointer_path(paths, slug)
    if not pointer.exists():
        return None
    payload = json.loads(pointer.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return None
    version = payload.get("version")
    if not isinstance(version, str):
        return None
    return version.strip() or None


def _write_promoted_version(paths: _StatePaths, slug: str, version: str) -> Path:
    pointer = _promoted_pointer_path(paths, slug)
    pointer.parent.mkdir(parents=True, exist_ok=True)
    pointer.write_text(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "slug": slug,
                "version": _validate_baseline_version(version),
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return pointer


def _list_baseline_versions(paths: _StatePaths, slug: str) -> list[str]:
    directory = _baseline_spec_dir(paths, slug)
    if not directory.exists():
        return []
    versions: list[str] = []
    for child in sorted(directory.iterdir()):
        if not child.is_dir():
            continue
        trace_file = child / "trace.jsonl"
        if trace_file.exists():
            versions.append(child.name)
    return versions


def _default_record_version(paths: _StatePaths, slug: str) -> str:
    existing = _read_promoted_version(paths, slug)
    if existing:
        return existing
    return "v1"


def _current_run_trace_path(paths: _StatePaths, slug: str) -> Path:
    return paths.current / f"{slug}.run.jsonl"


def _spec_file_hash(spec: AgentSpec) -> str:
    return hashlib.sha256(spec.source_path.read_bytes()).hexdigest()


def _resolve_git_sha(project_root: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return "unknown"
    if completed.returncode != 0:
        return "unknown"
    return completed.stdout.strip() or "unknown"


def _make_runtime_baseline_meta(
    *,
    project_root: Path,
    spec: AgentSpec,
    clock_seed: float | None,
    random_seed: int | None,
) -> dict[str, Any]:
    return {
        "created_at": datetime_module.datetime.now(datetime_module.UTC).isoformat(),
        "git_sha": _resolve_git_sha(project_root),
        "trajectly_version": trajectly_version,
        "clock_seed": clock_seed,
        "random_seed": random_seed,
        "spec_hash": _spec_file_hash(spec),
    }


def _extract_determinism_warnings(result: ExecutionResult) -> list[dict[str, str]]:
    combined = f"{result.stdout}\n{result.stderr}"
    warnings: list[dict[str, str]] = []
    seen: set[str] = set()
    for match in _DETERMINISM_CODE_RE.finditer(combined):
        code = match.group(1)
        if code in seen:
            continue
        seen.add(code)
        line_start = combined.rfind("\n", 0, match.start()) + 1
        line_end = combined.find("\n", match.end())
        if line_end == -1:
            line_end = len(combined)
        snippet = combined[line_start:line_end].strip()
        warnings.append({"code": code, "message": snippet})
    return warnings


def _determinism_warning_messages(warnings: list[dict[str, str]]) -> list[str]:
    """Collapse structured determinism warnings to unique user-facing messages."""
    messages: list[str] = []
    seen: set[str] = set()
    for warning in warnings:
        raw_message = str(warning.get("message", "")).strip()
        code = str(warning.get("code", "")).strip()
        normalized = raw_message or code
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        messages.append(normalized)
    return messages


def _collect_available_baselines(paths: _StatePaths, slug: str) -> list[str]:
    """Return known baseline versions, placing promoted version first when present."""
    versions = _list_baseline_versions(paths, slug)
    if not versions:
        return []
    promoted = _read_promoted_version(paths, slug)
    if promoted and promoted in versions:
        return [promoted] + [version for version in versions if version != promoted]
    return versions


def _collect_baseline_metadata(paths: _StatePaths, slug: str, versions: list[str]) -> dict[str, dict[str, Any]]:
    """Load per-version runtime metadata and attach promotion flags."""
    promoted = _read_promoted_version(paths, slug)
    metadata: dict[str, dict[str, Any]] = {}
    for version in versions:
        runtime_meta_path = _baseline_runtime_meta_path(paths, slug, version)
        payload: dict[str, Any] = {}
        if runtime_meta_path.exists():
            try:
                loaded = _load_runtime_baseline_meta(runtime_meta_path)
                if isinstance(loaded, dict):
                    payload.update(loaded)
            except Exception:
                payload["load_error"] = f"invalid runtime metadata: {runtime_meta_path}"
        payload["version"] = version
        payload["promoted"] = promoted == version
        metadata[version] = payload
    return metadata


def _extract_fixture_observations(current_events: list[TraceEvent]) -> list[dict[str, Any]]:
    """Pair call/return trace events into normalized fixture-observation records."""
    observations: list[dict[str, Any]] = []
    pending_tools: deque[dict[str, Any]] = deque()
    pending_llms: deque[dict[str, Any]] = deque()

    for event in current_events:
        payload = event.payload
        if event.event_type == "tool_called":
            tool_name = str(payload.get("tool_name", "unknown"))
            request_payload = payload.get("input", {})
            request_map = request_payload if isinstance(request_payload, dict) else {"value": request_payload}
            pending_tools.append(
                {
                    "kind": "tool",
                    "name": tool_name,
                    "request": request_map,
                    "input_hash": sha256_of_data(request_map),
                }
            )
            continue

        if event.event_type == "tool_returned" and pending_tools:
            prior = pending_tools.popleft()
            observations.append(
                {
                    **prior,
                    "response": {
                        "output": payload.get("output"),
                        "error": payload.get("error"),
                        "error_code": payload.get("error_code"),
                    },
                }
            )
            continue

        if event.event_type == "llm_called":
            provider = str(payload.get("provider", "unknown"))
            model = str(payload.get("model", "unknown"))
            request_payload = payload.get("request", {})
            request_map = request_payload if isinstance(request_payload, dict) else {"value": request_payload}
            pending_llms.append(
                {
                    "kind": "llm",
                    "name": f"{provider}:{model}",
                    "request": request_map,
                    "input_hash": sha256_of_data(request_map),
                }
            )
            continue

        if event.event_type == "llm_returned" and pending_llms:
            prior = pending_llms.popleft()
            observations.append(
                {
                    **prior,
                    "response": {
                        "response": payload.get("response"),
                        "usage": payload.get("usage"),
                        "error": payload.get("error"),
                        "error_code": payload.get("error_code"),
                    },
                }
            )

    return observations


def _build_fixture_usage(current_events: list[TraceEvent], fixture_store_path: Path) -> dict[str, Any]:
    """Compute fixture consumption summary plus per-call match diagnostics."""
    if not fixture_store_path.exists():
        return {
            "summary": {"total": 0, "consumed": 0, "misses": 0, "exhausted": 0},
            "fixtures": [],
        }

    fixture_store = FixtureStore.load(fixture_store_path)
    available_by_signature: dict[tuple[str, str, str], int] = defaultdict(int)
    for entry in fixture_store.entries:
        available_by_signature[(entry.kind, entry.name, entry.input_hash)] += 1

    observed = _extract_fixture_observations(current_events)
    consumed_by_signature: dict[tuple[str, str, str], int] = defaultdict(int)

    consumed = 0
    misses = 0
    exhausted = 0
    fixtures: list[dict[str, Any]] = []

    for call in observed:
        signature = (str(call["kind"]), str(call["name"]), str(call["input_hash"]))
        available = available_by_signature.get(signature, 0)
        consumed_by_signature[signature] += 1
        signature_consumed = consumed_by_signature[signature]
        matched = available > 0 and signature_consumed <= available

        if matched:
            consumed += 1
        else:
            misses += 1
            if available > 0:
                exhausted += 1

        fixture_row: dict[str, Any] = {
            "type": call["kind"],
            "key": f"{signature[0]}:{signature[1]}:{signature[2][:12]}",
            "label": signature[1],
            "request": call["request"],
            "response": call["response"],
            "matched": matched,
        }
        if not matched:
            fixture_row["mismatch"] = {
                "expected": {"available": available, "signature": signature[2]},
                "actual": {"consumed": signature_consumed},
            }
        fixtures.append(fixture_row)

    return {
        "summary": {
            "total": len(fixture_store.entries),
            "consumed": consumed,
            "misses": misses,
            "exhausted": exhausted,
        },
        "fixtures": fixtures,
    }


_DETERMINISM_CATEGORY_BY_CODE = {
    "NONDETERMINISM_CLOCK_DETECTED": "time",
    "NONDETERMINISM_RANDOM_DETECTED": "random",
    "NONDETERMINISM_UUID_DETECTED": "uuid",
    "NONDETERMINISM_FILESYSTEM_DETECTED": "filesystem",
}


def _infer_determinism_category(text: str) -> str | None:
    """Map free-form warning/finding text into a determinism category."""
    normalized = text.lower()
    if "network" in normalized or "http" in normalized or "domain" in normalized:
        return "network"
    if "clock" in normalized or "utc" in normalized or "datetime" in normalized or "timestamp" in normalized:
        return "time"
    if "random" in normalized:
        return "random"
    if "uuid" in normalized:
        return "uuid"
    if "filesystem" in normalized or "file" in normalized or "path" in normalized:
        return "filesystem"
    return None


def _build_determinism_diagnostics(
    *,
    spec: AgentSpec,
    determinism_warnings: list[dict[str, str]],
    diff_result: DiffResult,
) -> list[dict[str, Any]]:
    """Build normalized determinism diagnostics from warnings, findings, and spec config."""
    diagnostics: list[dict[str, Any]] = []
    dedupe: set[tuple[str, str | None, str]] = set()

    def add(category: str, message: str, *, detected: bool, code: str | None = None) -> None:
        key = (category, code, message)
        if key in dedupe:
            return
        dedupe.add(key)
        row: dict[str, Any] = {
            "category": category,
            "message": message,
            "detected": detected,
        }
        if code:
            row["code"] = code
        diagnostics.append(row)

    for warning in determinism_warnings:
        code = str(warning.get("code", "")).strip() or None
        message = str(warning.get("message", "")).strip() or (code or "Determinism warning detected")
        category = _DETERMINISM_CATEGORY_BY_CODE.get(code or "")
        if category is None:
            category = _infer_determinism_category(message)
        if category is None:
            continue
        add(category, message, detected=True, code=code)

    for finding in diff_result.findings:
        merged_text = f"{finding.classification} {finding.message}"
        category = _infer_determinism_category(merged_text)
        if category is None:
            continue
        add(category, finding.message, detected=True, code=finding.classification.upper())

    # Config-only diagnostics help explain why a category may be empty during replay.
    if spec.determinism.clock.mode == "disabled":
        add("time", "Clock determinism mode is disabled for this spec.", detected=False)
    if spec.determinism.random.mode == "disabled":
        add("random", "Random determinism mode is disabled for this spec.", detected=False)
    if spec.determinism.filesystem.mode == "permissive":
        add("filesystem", "Filesystem determinism mode is permissive for this spec.", detected=False)
    if spec.replay.mode == "online":
        add("network", "Replay mode is online; network calls may execute.", detected=False)

    return diagnostics


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
                "schema_version: \"0.4\"\n"
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
                "schema_version: \"0.4\"\n"
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
                "schema_version: \"0.4\"\n"
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


def _augment_report_with_trt(
    report_json: Path,
    trt_result: TRTResult,
    *,
    baseline_version: str | None = None,
    determinism_warnings: list[dict[str, str]] | None = None,
    available_baselines: list[str] | None = None,
    baseline_metadata: dict[str, dict[str, Any]] | None = None,
    fixture_usage: dict[str, Any] | None = None,
    determinism_diagnostics: list[dict[str, Any]] | None = None,
    replay_mode: str | None = None,
) -> None:
    raw = json.loads(report_json.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return
    trt_payload = trt_result.report.to_dict()
    if baseline_version is not None:
        trt_payload["baseline_version"] = baseline_version
    if determinism_warnings:
        trt_payload["determinism_warnings"] = determinism_warnings
        trt_payload["determinism_warning_messages"] = _determinism_warning_messages(determinism_warnings)
    if available_baselines is not None:
        trt_payload["available_baselines"] = available_baselines
    if baseline_metadata is not None:
        trt_payload["baseline_metadata"] = baseline_metadata
    if fixture_usage is not None:
        trt_payload["fixture_usage"] = fixture_usage
    if determinism_diagnostics is not None:
        trt_payload["determinism_diagnostics"] = determinism_diagnostics
    if replay_mode is not None:
        trt_payload["replay_mode"] = replay_mode
    raw["trt_v03"] = trt_payload
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
    command = f'python -m trajectly run "{spec_path}" --project-root "{project_root}"'
    if strict_override is True:
        command += " --strict"
    if strict_override is False:
        command += " --no-strict"
    return command


def _determinism_payload(spec: AgentSpec) -> dict[str, object]:
    return cast(dict[str, object], asdict(spec.determinism))


def _seed_values_for_spec(spec: AgentSpec) -> tuple[float | None, int | None]:
    clock_mode = spec.determinism.clock.mode
    random_mode = spec.determinism.random.mode
    clock_seed = time_module.time() if clock_mode != "disabled" else None
    random_seed = random.randint(1, 2**31 - 1) if random_mode != "disabled" else None
    return clock_seed, random_seed


def _load_runtime_baseline_meta(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Invalid baseline runtime meta file: {path}")
    return raw


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
        raise FileNotFoundError(f"Latest report not found: {report_path}. Run `python -m trajectly run` first")
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
            "Latest report is missing `spec_path`. Re-run `python -m trajectly run` "
            "with this version to generate repro metadata."
        )
    return str(chosen.get("spec", "unknown")), Path(spec_path_raw).resolve()


def record_specs(
    targets: list[str],
    project_root: Path,
    *,
    allow_ci_write: bool = False,
    baseline_version: str | None = None,
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
                "Re-run `python -m trajectly record ... --allow-ci-write` only for explicit baseline updates."
            ],
        )

    errors: list[str] = []
    for spec in specs:
        slug = _slugify(spec.name)
        legacy_error = _reject_legacy_baseline_layout(paths, slug)
        if legacy_error is not None:
            errors.append(f"{spec.name}: {legacy_error}")
            continue

        version = _validate_baseline_version(baseline_version or _default_record_version(paths, slug))
        version_dir = _baseline_version_dir(paths, slug, version)
        version_dir.mkdir(parents=True, exist_ok=True)

        baseline_path = _baseline_trace_path(paths, slug, version)
        baseline_trace_meta_path = _baseline_trace_meta_path(paths, slug, version)
        fixture_path = _baseline_fixture_path(paths, slug, version)
        runtime_meta_path = _baseline_runtime_meta_path(paths, slug, version)

        clock_seed, random_seed = _seed_values_for_spec(spec)
        determinism_payload = _determinism_payload(spec)

        run_id = f"{slug}-{uuid.uuid4().hex[:8]}"
        raw_events_path = paths.tmp / f"{slug}.record.events.jsonl"

        result = execute_spec(
            spec=spec,
            mode="record",
            events_path=raw_events_path,
            fixtures_path=None,
            strict=spec.strict,
            determinism_config=determinism_payload,
            clock_seed=clock_seed,
            random_seed=random_seed,
            project_root=project_root,
        )
        events = _build_trace(spec=spec, result=result, run_id=run_id)

        write_events_jsonl(baseline_path, events)
        write_trace_meta(
            baseline_trace_meta_path,
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
        fixture_store.save(fixture_path)

        runtime_meta_path.write_text(
            json.dumps(
                _make_runtime_baseline_meta(
                    project_root=project_root,
                    spec=spec,
                    clock_seed=clock_seed,
                    random_seed=random_seed,
                ),
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        _write_promoted_version(paths, slug, version)

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
    baseline_version: str | None = None,
) -> CommandOutcome:
    paths = _state_paths(project_root)
    _ensure_state_dirs(paths)

    try:
        specs = load_specs(targets, cwd=project_root)
    except Exception as exc:
        return CommandOutcome(exit_code=EXIT_INTERNAL_ERROR, processed_specs=0, errors=[str(exc)])

    if fixtures_dir is not None:
        return CommandOutcome(
            exit_code=EXIT_INTERNAL_ERROR,
            processed_specs=0,
            errors=[
                "Hard cutover active: --fixtures-dir is not supported in v0.4. "
                "Use versioned baselines under .trajectly/baselines/<slug>/<version>/fixtures.json."
            ],
        )
    baseline_root = baseline_dir.resolve() if baseline_dir else paths.baselines

    errors: list[str] = []
    regressions = 0
    rows: list[dict[str, Any]] = []

    for spec in specs:
        slug = _slugify(spec.name)
        legacy_error = _reject_legacy_baseline_layout(paths, slug)
        if legacy_error is not None:
            errors.append(f"{spec.name}: {legacy_error}")
            continue

        resolved_version = baseline_version or _read_promoted_version(paths, slug)
        if resolved_version is None:
            errors.append(
                f"{spec.name}: no promoted baseline version found. "
                "Create one with `python -m trajectly baseline create --name v1 <spec>` and promote it."
            )
            continue
        resolved_version = _validate_baseline_version(resolved_version)

        version_dir = baseline_root / slug / resolved_version
        baseline_path = version_dir / "trace.jsonl"
        fixture_path = version_dir / "fixtures.json"
        runtime_meta_path = version_dir / "baseline.meta.json"

        if not baseline_path.exists():
            errors.append(
                f"{spec.name}: missing baseline trace at {baseline_path} for baseline version `{resolved_version}`. "
                "Create it with `python -m trajectly baseline create --name <version> <spec>`."
            )
            continue
        if spec.schema_version == TRT_SPEC_SCHEMA_VERSION:
            baseline_meta_path = version_dir / "trace.meta.json"
            if not baseline_meta_path.exists():
                errors.append(
                    f"{spec.name}: NORMALIZER_VERSION_MISMATCH: missing baseline meta at {baseline_meta_path}. "
                    "Re-run `python -m trajectly record` to regenerate baseline artifacts."
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
                f"{spec.name}: missing fixtures at {fixture_path} for baseline version `{resolved_version}`. "
                "Re-record this version."
            )
            continue
        if not runtime_meta_path.exists():
            errors.append(
                f"{spec.name}: missing baseline runtime metadata at {runtime_meta_path}. "
                "Re-record this baseline version."
            )
            continue
        try:
            runtime_meta = _load_runtime_baseline_meta(runtime_meta_path)
        except Exception as exc:
            errors.append(f"{spec.name}: invalid baseline runtime metadata at {runtime_meta_path}: {exc}")
            continue

        strict = strict_override if strict_override is not None else spec.strict
        run_id = f"{slug}-{uuid.uuid4().hex[:8]}"
        raw_events_path = paths.tmp / f"{slug}.run.events.jsonl"

        clock_seed_raw = runtime_meta.get("clock_seed")
        random_seed_raw = runtime_meta.get("random_seed")
        clock_seed_value = float(clock_seed_raw) if isinstance(clock_seed_raw, (int, float, str)) else None
        random_seed_value = int(random_seed_raw) if isinstance(random_seed_raw, (int, float, str)) else None

        result = execute_spec(
            spec=spec,
            mode="replay",
            events_path=raw_events_path,
            fixtures_path=fixture_path,
            strict=strict,
            determinism_config=_determinism_payload(spec),
            clock_seed=clock_seed_value,
            random_seed=random_seed_value,
            project_root=project_root,
        )

        current_events = _build_trace(spec=spec, result=result, run_id=run_id)
        current_path = _current_run_trace_path(paths, slug)
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
        determinism_warnings = _extract_determinism_warnings(result)
        for warning in determinism_warnings:
            diff_result.findings.append(
                Finding(
                    classification=warning["code"].lower(),
                    message=warning["message"],
                    path="$.runtime.determinism",
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

        available_baselines = _collect_available_baselines(paths, slug)
        baseline_metadata = _collect_baseline_metadata(paths, slug, available_baselines)
        fixture_usage = _build_fixture_usage(current_events, fixture_path)
        determinism_diagnostics = _build_determinism_diagnostics(
            spec=spec,
            determinism_warnings=determinism_warnings,
            diff_result=diff_result,
        )
        warning_messages = _determinism_warning_messages(determinism_warnings)

        report_json = paths.reports / f"{slug}.json"
        report_md = paths.reports / f"{slug}.md"
        write_reports(spec_name=spec.name, result=diff_result, json_path=report_json, md_path=report_md)
        _augment_report_with_trt(
            report_json,
            trt_result,
            baseline_version=resolved_version,
            determinism_warnings=determinism_warnings,
            available_baselines=available_baselines,
            baseline_metadata=baseline_metadata,
            fixture_usage=fixture_usage,
            determinism_diagnostics=determinism_diagnostics,
            replay_mode=spec.replay.mode,
        )
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
                "baseline_version": resolved_version,
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
                "baseline_version": resolved_version,
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
                "available_baselines": available_baselines,
                "baseline_metadata": baseline_metadata,
                "determinism_warnings": warning_messages,
                "determinism_warnings_structured": determinism_warnings,
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
                f"Latest report row for `{spec_name}` missing required fields: {joined}. "
                "Re-run `python -m trajectly run` first."
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


def _resolve_slug_filters_for_baseline_targets(paths: _StatePaths, targets: list[str] | None) -> list[str]:
    if not targets:
        return []
    slugs: list[str] = []
    for target in targets:
        candidate = Path(target)
        if candidate.exists():
            resolved_spec = load_specs([str(candidate.resolve())], cwd=paths.root)[0]
            slugs.append(_slugify(resolved_spec.name))
        else:
            slugs.append(_slugify(target))
    return sorted(set(slugs))


def baseline_list(project_root: Path, targets: list[str] | None = None) -> dict[str, Any]:
    paths = _state_paths(project_root.resolve())
    _ensure_state_dirs(paths)

    filter_slugs = _resolve_slug_filters_for_baseline_targets(paths, targets)
    if filter_slugs:
        candidate_slugs = filter_slugs
    else:
        candidate_slugs = sorted(
            entry.name
            for entry in paths.baselines.iterdir()
            if entry.is_dir()
        ) if paths.baselines.exists() else []

    specs: list[dict[str, Any]] = []
    for slug in candidate_slugs:
        versions = _list_baseline_versions(paths, slug)
        if not versions and filter_slugs:
            specs.append({"slug": slug, "versions": [], "promoted": None})
            continue
        if not versions:
            continue
        specs.append(
            {
                "slug": slug,
                "versions": versions,
                "promoted": _read_promoted_version(paths, slug),
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "specs": specs,
    }


def baseline_create(
    *,
    targets: list[str],
    project_root: Path,
    name: str,
    allow_ci_write: bool = False,
) -> CommandOutcome:
    version = _validate_baseline_version(name)
    return record_specs(
        targets=targets,
        project_root=project_root.resolve(),
        allow_ci_write=allow_ci_write,
        baseline_version=version,
    )


def baseline_promote(
    *,
    project_root: Path,
    version: str,
    targets: list[str] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    paths = _state_paths(project_root.resolve())
    _ensure_state_dirs(paths)

    normalized_version = _validate_baseline_version(version)
    filter_slugs = _resolve_slug_filters_for_baseline_targets(paths, targets)
    if filter_slugs:
        candidate_slugs = filter_slugs
    else:
        candidate_slugs = sorted(
            entry.name for entry in paths.baselines.iterdir() if entry.is_dir()
        ) if paths.baselines.exists() else []

    promoted: list[str] = []
    missing: list[str] = []
    for slug in candidate_slugs:
        versions = set(_list_baseline_versions(paths, slug))
        if normalized_version not in versions:
            missing.append(slug)
            continue
        _write_promoted_version(paths, slug, normalized_version)
        promoted.append(slug)

    payload = {
        "schema_version": SCHEMA_VERSION,
        "version": normalized_version,
        "promoted": promoted,
        "missing": missing,
    }
    return payload, missing


def baseline_diff(
    *,
    project_root: Path,
    spec_slug: str,
    left: str,
    right: str,
) -> dict[str, Any]:
    paths = _state_paths(project_root.resolve())
    _ensure_state_dirs(paths)
    slug = _slugify(spec_slug)
    left_version = _validate_baseline_version(left)
    right_version = _validate_baseline_version(right)

    left_trace = _baseline_trace_path(paths, slug, left_version)
    right_trace = _baseline_trace_path(paths, slug, right_version)
    if not left_trace.exists():
        raise FileNotFoundError(f"Left baseline trace missing: {left_trace}")
    if not right_trace.exists():
        raise FileNotFoundError(f"Right baseline trace missing: {right_trace}")

    left_events = read_events_jsonl(left_trace)
    right_events = read_events_jsonl(right_trace)
    diff_result = compare_traces(
        baseline=left_events,
        current=right_events,
        budgets=BudgetThresholds(),
    )
    _refresh_summary(diff_result)
    return {
        "schema_version": SCHEMA_VERSION,
        "slug": slug,
        "left": left_version,
        "right": right_version,
        "summary": diff_result.summary,
        "findings": [finding.to_dict() for finding in diff_result.findings],
    }


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
