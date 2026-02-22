from __future__ import annotations

import glob
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, cast

import yaml

FixturePolicy = Literal["by_index", "by_hash"]


@dataclass(slots=True)
class BudgetThresholds:
    max_latency_ms: int | None = None
    max_tool_calls: int | None = None
    max_tokens: int | None = None


@dataclass(slots=True)
class AgentSpec:
    name: str
    command: str
    source_path: Path
    workdir: str | None = None
    env: dict[str, str] = field(default_factory=dict)
    fixture_policy: FixturePolicy = "by_index"
    strict: bool = False
    redact: list[str] = field(default_factory=list)
    budget_thresholds: BudgetThresholds = field(default_factory=BudgetThresholds)

    def resolved_workdir(self) -> Path:
        if self.workdir is None:
            return self.source_path.parent
        candidate = Path(self.workdir)
        if candidate.is_absolute():
            return candidate
        return (self.source_path.parent / candidate).resolve()


def _load_yaml(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise ValueError(f"Spec file must be a mapping: {path}")
    return loaded


def _parse_budget_thresholds(raw: Any) -> BudgetThresholds:
    if raw is None:
        return BudgetThresholds()
    if not isinstance(raw, dict):
        raise ValueError("budget_thresholds must be a mapping")
    max_latency_ms = raw.get("max_latency_ms")
    max_tool_calls = raw.get("max_tool_calls")
    max_tokens = raw.get("max_tokens")
    return BudgetThresholds(
        max_latency_ms=int(max_latency_ms) if max_latency_ms is not None else None,
        max_tool_calls=int(max_tool_calls) if max_tool_calls is not None else None,
        max_tokens=int(max_tokens) if max_tokens is not None else None,
    )


def load_spec(path: Path) -> AgentSpec:
    data = _load_yaml(path)
    name = str(data.get("name") or path.stem)
    command = data.get("command")
    if not isinstance(command, str) or not command.strip():
        raise ValueError(f"Spec {path} is missing required non-empty field: command")

    fixture_policy = str(data.get("fixture_policy", "by_index"))
    if fixture_policy not in {"by_index", "by_hash"}:
        raise ValueError(f"Spec {path} has invalid fixture_policy: {fixture_policy}")

    raw_env = data.get("env") or {}
    if not isinstance(raw_env, dict):
        raise ValueError(f"Spec {path} field env must be a mapping")

    raw_redact = data.get("redact") or []
    if not isinstance(raw_redact, list):
        raise ValueError(f"Spec {path} field redact must be a list")

    parsed_policy = cast(FixturePolicy, fixture_policy)

    return AgentSpec(
        name=name,
        command=command,
        source_path=path.resolve(),
        workdir=data.get("workdir"),
        env={str(k): str(v) for k, v in raw_env.items()},
        fixture_policy=parsed_policy,
        strict=bool(data.get("strict", False)),
        redact=[str(pattern) for pattern in raw_redact],
        budget_thresholds=_parse_budget_thresholds(data.get("budget_thresholds")),
    )


def _resolve_targets(targets: list[str], cwd: Path) -> list[Path]:
    resolved: list[Path] = []
    for target in targets:
        candidate = Path(target)
        if candidate.exists():
            resolved.append(candidate.resolve())
            continue
        matches = [Path(path).resolve() for path in glob.glob(target)]
        resolved.extend(matches)
    deduped = sorted(set(resolved), key=lambda value: str(value))
    if not deduped:
        joined = ", ".join(targets)
        raise ValueError(f"No spec files matched targets: {joined}")
    return deduped


def load_specs(targets: list[str], cwd: Path | None = None) -> list[AgentSpec]:
    root = cwd or Path.cwd()
    paths = _resolve_targets(targets, root)
    specs: list[AgentSpec] = []
    for path in paths:
        specs.append(load_spec(path))
    return specs
