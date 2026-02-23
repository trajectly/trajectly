from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, cast

import yaml

from trajectly.constants import TRT_SPEC_SCHEMA_VERSION
from trajectly.specs.compat_v02 import (
    AgentContracts,
    BudgetThresholds,
    FixturePolicy,
    parse_contracts_v1,
    parse_v02_spec,
)

ModeProfile = Literal["ci_safe", "permissive", "strict"]
ReplayMode = Literal["offline", "online"]
LLMMatchMode = Literal["signature_match", "sequence_match"]
ToolMatchMode = Literal["args_signature_match", "sequence_match"]
RefinementMode = Literal["none", "skeleton", "strict"]


@dataclass(slots=True)
class ReplayConfig:
    mode: ReplayMode = "offline"
    strict_sequence: bool = False
    llm_match_mode: LLMMatchMode = "signature_match"
    tool_match_mode: ToolMatchMode = "args_signature_match"
    fixture_policy: FixturePolicy = "by_hash"


@dataclass(slots=True)
class RefinementConfig:
    mode: RefinementMode = "skeleton"
    allow_extra_llm_steps: bool = True
    allow_extra_tools: list[str] = field(default_factory=list)
    allow_extra_side_effect_tools: list[str] = field(default_factory=list)
    allow_new_tool_names: bool = False
    ignore_call_tools: list[str] = field(default_factory=list)


@dataclass(slots=True)
class AgentSpec:
    name: str
    command: str
    source_path: Path
    schema_version: str = TRT_SPEC_SCHEMA_VERSION
    workdir: str | None = None
    env: dict[str, str] = field(default_factory=dict)
    fixture_policy: FixturePolicy = "by_hash"
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
    mode_profile: ModeProfile = "ci_safe"
    legacy_compat: bool = False

    def resolved_workdir(self) -> Path:
        if self.workdir is None:
            return self.source_path.parent
        candidate = Path(self.workdir)
        if candidate.is_absolute():
            return candidate
        return (self.source_path.parent / candidate).resolve()

    def resolve_path(self, raw: str | None) -> Path | None:
        if raw is None:
            return None
        path = Path(raw)
        if path.is_absolute():
            return path
        return (self.source_path.parent / path).resolve()


def _load_yaml(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise ValueError(f"Spec file must be a mapping: {path}")
    return loaded


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


def _ensure_mapping(raw: Any, *, field_name: str) -> dict[str, Any]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"{field_name} must be a mapping")
    return raw


def _parse_mode_profile(raw: Any) -> ModeProfile:
    profile = str(raw or "ci_safe").strip().lower()
    if profile not in {"ci_safe", "permissive", "strict"}:
        raise ValueError(f"mode_profile must be one of ci_safe|permissive|strict; got: {profile}")
    return cast(ModeProfile, profile)


def _parse_replay(raw: Any) -> ReplayConfig:
    block = _ensure_mapping(raw, field_name="replay")

    mode = str(block.get("mode", "offline")).strip().lower()
    if mode not in {"offline", "online"}:
        raise ValueError("replay.mode must be one of offline|online")
    replay_mode = cast(ReplayMode, mode)

    llm_match_mode = str(block.get("llm_match_mode", "signature_match")).strip().lower()
    if llm_match_mode not in {"signature_match", "sequence_match"}:
        raise ValueError("replay.llm_match_mode must be signature_match|sequence_match")
    parsed_llm_mode = cast(LLMMatchMode, llm_match_mode)

    tool_match_mode = str(block.get("tool_match_mode", "args_signature_match")).strip().lower()
    if tool_match_mode not in {"args_signature_match", "sequence_match"}:
        raise ValueError("replay.tool_match_mode must be args_signature_match|sequence_match")
    parsed_tool_mode = cast(ToolMatchMode, tool_match_mode)

    fixture_policy = str(block.get("fixture_policy", "by_hash"))
    if fixture_policy not in {"by_index", "by_hash"}:
        raise ValueError("replay.fixture_policy must be by_index|by_hash")
    parsed_policy = cast(FixturePolicy, fixture_policy)

    strict_sequence_raw = block.get("strict_sequence", False)
    if not isinstance(strict_sequence_raw, bool):
        raise ValueError("replay.strict_sequence must be a boolean")

    return ReplayConfig(
        mode=parsed_mode if (parsed_mode := replay_mode) else "offline",
        strict_sequence=strict_sequence_raw,
        llm_match_mode=parsed_llm_mode,
        tool_match_mode=parsed_tool_mode,
        fixture_policy=parsed_policy,
    )


def _parse_refinement(raw: Any) -> RefinementConfig:
    block = _ensure_mapping(raw, field_name="refinement")
    mode = str(block.get("mode", "skeleton")).strip().lower()
    if mode not in {"none", "skeleton", "strict"}:
        raise ValueError("refinement.mode must be none|skeleton|strict")
    parsed_mode = cast(RefinementMode, mode)

    allow_extra_llm_steps_raw = block.get("allow_extra_llm_steps", True)
    if not isinstance(allow_extra_llm_steps_raw, bool):
        raise ValueError("refinement.allow_extra_llm_steps must be a boolean")

    allow_new_tool_names_raw = block.get("allow_new_tool_names", False)
    if not isinstance(allow_new_tool_names_raw, bool):
        raise ValueError("refinement.allow_new_tool_names must be a boolean")

    return RefinementConfig(
        mode=parsed_mode,
        allow_extra_llm_steps=allow_extra_llm_steps_raw,
        allow_extra_tools=_parse_string_list(
            block.get("allow_extra_tools"), field_name="refinement.allow_extra_tools"
        ),
        allow_extra_side_effect_tools=_parse_string_list(
            block.get("allow_extra_side_effect_tools"),
            field_name="refinement.allow_extra_side_effect_tools",
        ),
        allow_new_tool_names=allow_new_tool_names_raw,
        ignore_call_tools=_parse_string_list(
            block.get("ignore_call_tools"), field_name="refinement.ignore_call_tools"
        ),
    )


def _load_contracts_from_config(source_path: Path, config_path: str) -> tuple[str, AgentContracts]:
    resolved = Path(config_path)
    if not resolved.is_absolute():
        resolved = (source_path.parent / resolved).resolve()
    if not resolved.exists():
        raise ValueError(f"contracts.config not found: {resolved}")

    payload = _load_yaml(resolved)
    if "contracts" in payload:
        contracts_raw = payload.get("contracts")
    else:
        contracts_raw = payload

    if not isinstance(contracts_raw, dict):
        raise ValueError(f"contracts policy file must contain mapping: {resolved}")
    if "refinement" in contracts_raw:
        raise ValueError("refinement must be defined in .agent.yaml, not contracts policy")

    return str(resolved), parse_contracts_v1(contracts_raw)


def _parse_command(data: dict[str, Any], source_path: Path) -> str:
    command = data.get("command")
    if isinstance(command, str) and command.strip():
        return command.strip()

    entrypoint = data.get("entrypoint")
    if isinstance(entrypoint, str) and entrypoint.strip():
        return f"python {shlex.quote(entrypoint.strip())}"

    raise ValueError(f"Spec {source_path} is missing required field: command or entrypoint")


def parse_v03_spec(data: dict[str, Any], *, source_path: Path) -> AgentSpec:
    schema_version_raw = data.get("schema_version")
    if schema_version_raw is None:
        raise ValueError("v0.3 spec requires schema_version")
    schema_version = str(schema_version_raw).strip()
    if schema_version not in {"0.3", "v0.3"}:
        raise ValueError(f"Unsupported schema_version for v0.3 parser: {schema_version}")

    name_raw = data.get("name")
    if not isinstance(name_raw, str) or not name_raw.strip():
        raise ValueError("v0.3 spec requires non-empty `name`")
    name = name_raw.strip()
    command = _parse_command(data, source_path)

    raw_env = data.get("env") or {}
    if not isinstance(raw_env, dict):
        raise ValueError(f"Spec {source_path} field env must be a mapping")

    raw_redact = data.get("redact") or []
    if not isinstance(raw_redact, list):
        raise ValueError(f"Spec {source_path} field redact must be a list")

    replay = _parse_replay(data.get("replay"))
    fixture_policy = str(data.get("fixture_policy", replay.fixture_policy))
    if fixture_policy not in {"by_index", "by_hash"}:
        raise ValueError(f"Spec {source_path} has invalid fixture_policy: {fixture_policy}")
    parsed_policy = cast(FixturePolicy, fixture_policy)

    strict_raw = data.get("strict", replay.strict_sequence)
    if not isinstance(strict_raw, bool):
        raise ValueError("strict must be a boolean")

    baseline_block = _ensure_mapping(data.get("baseline"), field_name="baseline")
    baseline_trace_raw = baseline_block.get("trace")
    if baseline_trace_raw is not None and not isinstance(baseline_trace_raw, str):
        raise ValueError("baseline.trace must be a string")

    abstraction_block = _ensure_mapping(data.get("abstraction"), field_name="abstraction")
    abstraction_config_raw = abstraction_block.get("config")
    if abstraction_config_raw is not None and not isinstance(abstraction_config_raw, str):
        raise ValueError("abstraction.config must be a string")

    contracts_config_path: str | None = None
    contracts_block = _ensure_mapping(data.get("contracts"), field_name="contracts")
    contracts_payload: Any = contracts_block if contracts_block else None
    if contracts_block:
        config_raw = contracts_block.get("config")
        if config_raw is not None:
            if not isinstance(config_raw, str):
                raise ValueError("contracts.config must be a string")
            contracts_config_path, loaded_contracts = _load_contracts_from_config(source_path, config_raw)
            overlay = {k: v for k, v in contracts_block.items() if k != "config"}
            if overlay:
                if "refinement" in overlay:
                    raise ValueError("refinement must be defined in .agent.yaml, not contracts policy")
                merged: dict[str, Any] = {}
                if loaded_contracts.version:
                    merged["version"] = loaded_contracts.version
                merged.update(overlay)
                contracts = parse_contracts_v1(merged)
            else:
                contracts = loaded_contracts
            contracts_payload = contracts
        else:
            contracts_payload = contracts_block

    if isinstance(contracts_payload, AgentContracts):
        contracts = contracts_payload
    else:
        contracts = parse_contracts_v1(contracts_payload)

    artifacts_block = _ensure_mapping(data.get("artifacts"), field_name="artifacts")
    artifacts_dir_raw = artifacts_block.get("dir", ".trajectly/artifacts")
    if not isinstance(artifacts_dir_raw, str) or not artifacts_dir_raw.strip():
        raise ValueError("artifacts.dir must be a non-empty string")

    spec = AgentSpec(
        schema_version=TRT_SPEC_SCHEMA_VERSION,
        name=name,
        command=command,
        source_path=source_path.resolve(),
        workdir=data.get("workdir"),
        env={str(k): str(v) for k, v in raw_env.items()},
        fixture_policy=parsed_policy,
        strict=strict_raw,
        redact=[str(pattern) for pattern in raw_redact],
        budget_thresholds=_parse_budget_thresholds(data.get("budget_thresholds")),
        contracts=contracts,
        baseline_trace=str(baseline_trace_raw) if baseline_trace_raw is not None else None,
        abstraction_config=str(abstraction_config_raw) if abstraction_config_raw is not None else None,
        contracts_config=contracts_config_path,
        replay=replay,
        refinement=_parse_refinement(data.get("refinement")),
        artifacts_dir=artifacts_dir_raw.strip(),
        mode_profile=_parse_mode_profile(data.get("mode_profile")),
        legacy_compat=False,
    )
    return spec


def parse_spec_with_compat(data: dict[str, Any], *, source_path: Path) -> AgentSpec:
    schema_version_raw = data.get("schema_version")
    if schema_version_raw is None:
        parsed_v02 = parse_v02_spec(data, source_path=source_path, schema_version=TRT_SPEC_SCHEMA_VERSION)
    else:
        schema_version = str(schema_version_raw).strip()
        if schema_version in {"0.3", "v0.3"}:
            return parse_v03_spec(data, source_path=source_path)
        if schema_version in {"0.2", "v0.2", "v1", "1"}:
            parsed_v02 = parse_v02_spec(data, source_path=source_path, schema_version=schema_version)
        else:
            raise ValueError(
                f"Unsupported schema_version: {schema_version}. "
                "Supported: 0.3 (native), 0.2/v1 (compat loader)."
            )

    return AgentSpec(
        schema_version=TRT_SPEC_SCHEMA_VERSION,
        name=parsed_v02.name,
        command=parsed_v02.command,
        source_path=parsed_v02.source_path,
        workdir=parsed_v02.workdir,
        env=parsed_v02.env,
        fixture_policy=parsed_v02.fixture_policy,
        strict=parsed_v02.strict,
        redact=parsed_v02.redact,
        budget_thresholds=parsed_v02.budget_thresholds,
        contracts=parsed_v02.contracts,
        baseline_trace=parsed_v02.baseline_trace,
        abstraction_config=parsed_v02.abstraction_config,
        contracts_config=parsed_v02.contracts_config,
        replay=ReplayConfig(
            mode=cast(
                ReplayMode,
                parsed_v02.replay.mode if parsed_v02.replay.mode in {"offline", "online"} else "offline",
            ),
            strict_sequence=parsed_v02.replay.strict_sequence,
            llm_match_mode=cast(
                LLMMatchMode,
                parsed_v02.replay.llm_match_mode
                if parsed_v02.replay.llm_match_mode in {"signature_match", "sequence_match"}
                else "signature_match",
            ),
            tool_match_mode=cast(
                ToolMatchMode,
                parsed_v02.replay.tool_match_mode
                if parsed_v02.replay.tool_match_mode in {"args_signature_match", "sequence_match"}
                else "args_signature_match",
            ),
            fixture_policy=parsed_v02.fixture_policy,
        ),
        refinement=RefinementConfig(),
        artifacts_dir=parsed_v02.artifacts_dir,
        mode_profile=cast(
            ModeProfile,
            parsed_v02.mode_profile if parsed_v02.mode_profile in {"ci_safe", "permissive", "strict"} else "ci_safe",
        ),
        legacy_compat=True,
    )


__all__ = [
    "AgentSpec",
    "LLMMatchMode",
    "ModeProfile",
    "RefinementConfig",
    "ReplayConfig",
    "ReplayMode",
    "ToolMatchMode",
    "parse_spec_with_compat",
]
