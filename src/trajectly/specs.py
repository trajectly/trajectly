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
class ToolContracts:
    allow: list[str] = field(default_factory=list)
    deny: list[str] = field(default_factory=list)
    max_calls_total: int | None = None
    schema: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SequenceContracts:
    require: list[str] = field(default_factory=list)
    forbid: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SideEffectContracts:
    deny_write_tools: bool = False


@dataclass(slots=True)
class NetworkContracts:
    allowlist: list[str] = field(default_factory=list)


@dataclass(slots=True)
class AgentContracts:
    version: str = "v1"
    tools: ToolContracts = field(default_factory=ToolContracts)
    sequence: SequenceContracts = field(default_factory=SequenceContracts)
    side_effects: SideEffectContracts = field(default_factory=SideEffectContracts)
    network: NetworkContracts = field(default_factory=NetworkContracts)


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
    contracts: AgentContracts = field(default_factory=AgentContracts)

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


def _parse_string_list(raw: Any, *, field_name: str) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError(f"{field_name} must be a list")
    return [str(item) for item in raw]


def _parse_contracts(raw: Any) -> AgentContracts:
    if raw is None:
        return AgentContracts()
    if not isinstance(raw, dict):
        raise ValueError("contracts must be a mapping")

    version_raw = raw.get("version", "v1")
    if not isinstance(version_raw, str):
        raise ValueError("contracts.version must be a string")
    version = version_raw.strip()
    if version != "v1":
        raise ValueError(f"Unsupported contracts.version: {version}. Supported: v1")

    tools_raw = raw.get("tools") or {}
    if not isinstance(tools_raw, dict):
        raise ValueError("contracts.tools must be a mapping")
    tools_allow = _parse_string_list(tools_raw.get("allow"), field_name="contracts.tools.allow")
    tools_deny = _parse_string_list(tools_raw.get("deny"), field_name="contracts.tools.deny")
    tools_overlap = sorted(set(tools_allow).intersection(tools_deny))
    if tools_overlap:
        joined = ", ".join(tools_overlap)
        raise ValueError(f"contracts.tools allow/deny overlap: {joined}")

    tools_max_calls_total_raw = tools_raw.get("max_calls_total")
    if tools_max_calls_total_raw is None:
        tools_max_calls_total: int | None = None
    else:
        tools_max_calls_total = int(tools_max_calls_total_raw)
        if tools_max_calls_total < 0:
            raise ValueError("contracts.tools.max_calls_total must be >= 0")

    tools_schema_raw = tools_raw.get("schema") or {}
    if not isinstance(tools_schema_raw, dict):
        raise ValueError("contracts.tools.schema must be a mapping")

    sequence_raw = raw.get("sequence") or {}
    if not isinstance(sequence_raw, dict):
        raise ValueError("contracts.sequence must be a mapping")

    side_effects_raw = raw.get("side_effects") or {}
    if not isinstance(side_effects_raw, dict):
        raise ValueError("contracts.side_effects must be a mapping")

    network_raw = raw.get("network") or {}
    if not isinstance(network_raw, dict):
        raise ValueError("contracts.network must be a mapping")

    deny_write_tools_raw = side_effects_raw.get("deny_write_tools", False)
    if not isinstance(deny_write_tools_raw, bool):
        raise ValueError("contracts.side_effects.deny_write_tools must be a boolean")

    return AgentContracts(
        version=version,
        tools=ToolContracts(
            allow=tools_allow,
            deny=tools_deny,
            max_calls_total=tools_max_calls_total,
            schema={str(k): v for k, v in tools_schema_raw.items()},
        ),
        sequence=SequenceContracts(
            require=_parse_string_list(sequence_raw.get("require"), field_name="contracts.sequence.require"),
            forbid=_parse_string_list(sequence_raw.get("forbid"), field_name="contracts.sequence.forbid"),
        ),
        side_effects=SideEffectContracts(deny_write_tools=deny_write_tools_raw),
        network=NetworkContracts(
            allowlist=_parse_string_list(network_raw.get("allowlist"), field_name="contracts.network.allowlist")
        ),
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
        contracts=_parse_contracts(data.get("contracts")),
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
