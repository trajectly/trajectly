from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, cast

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
    max_calls_per_tool: dict[str, int] = field(default_factory=dict)
    schema: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SequenceContracts:
    require: list[str] = field(default_factory=list)
    forbid: list[str] = field(default_factory=list)
    require_before: list[tuple[str, str]] = field(default_factory=list)
    eventually: list[str] = field(default_factory=list)
    never: list[str] = field(default_factory=list)
    at_most_once: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SideEffectContracts:
    deny_write_tools: bool = False


@dataclass(slots=True)
class NetworkContracts:
    allowlist: list[str] = field(default_factory=list)
    default: str = "deny"
    allow_domains: list[str] = field(default_factory=list)


@dataclass(slots=True)
class DataLeakContracts:
    deny_pii_outbound: bool = False
    outbound_kinds: list[str] = field(default_factory=list)
    secret_patterns: list[str] = field(default_factory=list)


@dataclass(slots=True)
class AgentContracts:
    version: str = "v1"
    tools: ToolContracts = field(default_factory=ToolContracts)
    sequence: SequenceContracts = field(default_factory=SequenceContracts)
    side_effects: SideEffectContracts = field(default_factory=SideEffectContracts)
    network: NetworkContracts = field(default_factory=NetworkContracts)
    data_leak: DataLeakContracts = field(default_factory=DataLeakContracts)


@dataclass(slots=True)
class ReplayConfig:
    mode: str = "offline"
    strict_sequence: bool = False
    llm_match_mode: str = "signature_match"
    tool_match_mode: str = "args_signature_match"
    fixture_policy: FixturePolicy = "by_hash"


@dataclass(slots=True)
class RefinementConfig:
    mode: str = "skeleton"
    allow_extra_llm_steps: bool = True
    allow_extra_tools: list[str] = field(default_factory=list)
    allow_extra_side_effect_tools: list[str] = field(default_factory=list)
    allow_new_tool_names: bool = False
    ignore_call_tools: list[str] = field(default_factory=list)


@dataclass(slots=True)
class AgentSpecV02Compat:
    schema_version: str
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
    baseline_trace: str | None = None
    abstraction_config: str | None = None
    contracts_config: str | None = None
    replay: ReplayConfig = field(default_factory=ReplayConfig)
    refinement: RefinementConfig = field(default_factory=RefinementConfig)
    artifacts_dir: str = ".trajectly/artifacts"
    mode_profile: str = "ci_safe"
    legacy_compat: bool = True

    def resolved_workdir(self) -> Path:
        if self.workdir is None:
            return self.source_path.parent
        candidate = Path(self.workdir)
        if candidate.is_absolute():
            return candidate
        return (self.source_path.parent / candidate).resolve()


def _parse_string_list(raw: Any, *, field_name: str) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError(f"{field_name} must be a list")
    return [str(item) for item in raw]


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


def parse_contracts_v1(raw: Any) -> AgentContracts:
    if raw is None:
        return AgentContracts()
    if not isinstance(raw, dict):
        raise ValueError("contracts must be a mapping")

    if "refinement" in raw:
        raise ValueError("refinement must be defined in .agent.yaml, not contracts policy")

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
    max_calls_per_tool_raw = tools_raw.get("max_calls_per_tool") or {}
    if not isinstance(max_calls_per_tool_raw, dict):
        raise ValueError("contracts.tools.max_calls_per_tool must be a mapping")
    max_calls_per_tool: dict[str, int] = {}
    for key, value in max_calls_per_tool_raw.items():
        parsed = int(value)
        if parsed < 0:
            raise ValueError("contracts.tools.max_calls_per_tool values must be >= 0")
        max_calls_per_tool[str(key)] = parsed

    tools_schema_raw = tools_raw.get("schema") or {}
    if not isinstance(tools_schema_raw, dict):
        raise ValueError("contracts.tools.schema must be a mapping")
    args_raw = raw.get("args") or {}
    if not isinstance(args_raw, dict):
        raise ValueError("contracts.args must be a mapping")
    normalized_tools_schema = {str(k): v for k, v in tools_schema_raw.items()}
    for tool_name, tool_schema in args_raw.items():
        if not isinstance(tool_schema, dict):
            raise ValueError("contracts.args entries must be mappings")
        existing = normalized_tools_schema.get(str(tool_name))
        if isinstance(existing, dict):
            merged = dict(existing)
            merged.update(tool_schema)
            normalized_tools_schema[str(tool_name)] = merged
        else:
            normalized_tools_schema[str(tool_name)] = dict(tool_schema)

    sequence_raw = raw.get("sequence") or {}
    if not isinstance(sequence_raw, dict):
        raise ValueError("contracts.sequence must be a mapping")
    require_before_raw = sequence_raw.get("require_before") or []
    if not isinstance(require_before_raw, list):
        raise ValueError("contracts.sequence.require_before must be a list")
    require_before: list[tuple[str, str]] = []
    for item in require_before_raw:
        if not isinstance(item, dict):
            raise ValueError("contracts.sequence.require_before entries must be mappings")
        before = item.get("before")
        after = item.get("after")
        if not isinstance(before, str) or not isinstance(after, str):
            raise ValueError("contracts.sequence.require_before entries need string before/after")
        require_before.append((before, after))

    side_effects_raw = raw.get("side_effects") or {}
    if not isinstance(side_effects_raw, dict):
        raise ValueError("contracts.side_effects must be a mapping")

    network_raw = raw.get("network") or {}
    if not isinstance(network_raw, dict):
        raise ValueError("contracts.network must be a mapping")
    network_default_raw = network_raw.get("default", "deny")
    if not isinstance(network_default_raw, str):
        raise ValueError("contracts.network.default must be a string")
    network_default = network_default_raw.strip().lower()
    if network_default not in {"deny", "allow"}:
        raise ValueError("contracts.network.default must be deny|allow")

    deny_write_tools_raw = side_effects_raw.get("deny_write_tools", False)
    if not isinstance(deny_write_tools_raw, bool):
        raise ValueError("contracts.side_effects.deny_write_tools must be a boolean")

    data_leak_raw = raw.get("data_leak") or {}
    if not isinstance(data_leak_raw, dict):
        raise ValueError("contracts.data_leak must be a mapping")
    deny_pii_outbound_raw = data_leak_raw.get("deny_pii_outbound", False)
    if not isinstance(deny_pii_outbound_raw, bool):
        raise ValueError("contracts.data_leak.deny_pii_outbound must be a boolean")

    return AgentContracts(
        version=version,
        tools=ToolContracts(
            allow=tools_allow,
            deny=tools_deny,
            max_calls_total=tools_max_calls_total,
            max_calls_per_tool=max_calls_per_tool,
            schema=normalized_tools_schema,
        ),
        sequence=SequenceContracts(
            require=_parse_string_list(sequence_raw.get("require"), field_name="contracts.sequence.require"),
            forbid=_parse_string_list(sequence_raw.get("forbid"), field_name="contracts.sequence.forbid"),
            require_before=require_before,
            eventually=_parse_string_list(sequence_raw.get("eventually"), field_name="contracts.sequence.eventually"),
            never=_parse_string_list(sequence_raw.get("never"), field_name="contracts.sequence.never"),
            at_most_once=_parse_string_list(
                sequence_raw.get("at_most_once"),
                field_name="contracts.sequence.at_most_once",
            ),
        ),
        side_effects=SideEffectContracts(deny_write_tools=deny_write_tools_raw),
        network=NetworkContracts(
            allowlist=_parse_string_list(network_raw.get("allowlist"), field_name="contracts.network.allowlist"),
            default=network_default,
            allow_domains=_parse_string_list(
                network_raw.get("allow_domains"),
                field_name="contracts.network.allow_domains",
            ),
        ),
        data_leak=DataLeakContracts(
            deny_pii_outbound=deny_pii_outbound_raw,
            outbound_kinds=_parse_string_list(
                data_leak_raw.get("outbound_kinds"),
                field_name="contracts.data_leak.outbound_kinds",
            ),
            secret_patterns=_parse_string_list(
                data_leak_raw.get("secret_patterns"),
                field_name="contracts.data_leak.secret_patterns",
            ),
        ),
    )


def parse_v02_spec(data: dict[str, Any], *, source_path: Path, schema_version: str) -> AgentSpecV02Compat:
    name = str(data.get("name") or source_path.stem)
    command = data.get("command")
    if not isinstance(command, str) or not command.strip():
        raise ValueError(f"Spec {source_path} is missing required non-empty field: command")

    fixture_policy = str(data.get("fixture_policy", "by_index"))
    if fixture_policy not in {"by_index", "by_hash"}:
        raise ValueError(f"Spec {source_path} has invalid fixture_policy: {fixture_policy}")

    raw_env = data.get("env") or {}
    if not isinstance(raw_env, dict):
        raise ValueError(f"Spec {source_path} field env must be a mapping")

    raw_redact = data.get("redact") or []
    if not isinstance(raw_redact, list):
        raise ValueError(f"Spec {source_path} field redact must be a list")

    parsed_policy = cast(FixturePolicy, fixture_policy)

    return AgentSpecV02Compat(
        schema_version=schema_version,
        name=name,
        command=command,
        source_path=source_path.resolve(),
        workdir=data.get("workdir"),
        env={str(k): str(v) for k, v in raw_env.items()},
        fixture_policy=parsed_policy,
        strict=bool(data.get("strict", False)),
        redact=[str(pattern) for pattern in raw_redact],
        budget_thresholds=_parse_budget_thresholds(data.get("budget_thresholds")),
        contracts=parse_contracts_v1(data.get("contracts")),
        replay=ReplayConfig(fixture_policy=parsed_policy, strict_sequence=bool(data.get("strict", False))),
    )
