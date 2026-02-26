from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

import yaml

from trajectly.core.constants import TRT_SPEC_SCHEMA_VERSION
from trajectly.core.specs import load_spec
from trajectly.core.specs.v03 import AgentSpec


def _omit_none(value: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in value.items() if v is not None}


def spec_to_v03_payload(spec: AgentSpec) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": TRT_SPEC_SCHEMA_VERSION,
        "name": spec.name,
        "command": spec.command,
        "workdir": spec.workdir,
        "env": dict(spec.env),
        "fixture_policy": spec.fixture_policy,
        "strict": spec.strict,
        "redact": list(spec.redact),
        "budget_thresholds": _omit_none(asdict(spec.budget_thresholds)),
        "contracts": asdict(spec.contracts),
        "mode_profile": spec.mode_profile,
        "replay": {
            "mode": spec.replay.mode,
            "strict_sequence": spec.replay.strict_sequence,
            "llm_match_mode": spec.replay.llm_match_mode,
            "tool_match_mode": spec.replay.tool_match_mode,
            "fixture_policy": spec.replay.fixture_policy,
        },
        "refinement": {
            "mode": spec.refinement.mode,
            "allow_extra_llm_steps": spec.refinement.allow_extra_llm_steps,
            "allow_extra_tools": list(spec.refinement.allow_extra_tools),
            "allow_extra_side_effect_tools": list(spec.refinement.allow_extra_side_effect_tools),
            "allow_new_tool_names": spec.refinement.allow_new_tool_names,
            "ignore_call_tools": list(spec.refinement.ignore_call_tools),
        },
        "artifacts": {
            "dir": spec.artifacts_dir,
        },
    }

    if spec.baseline_trace:
        payload["baseline"] = {"trace": spec.baseline_trace}
    if spec.abstraction_config:
        payload["abstraction"] = {"config": spec.abstraction_config}
    if spec.contracts_config:
        payload["contracts"] = {
            **payload["contracts"],
            "config": spec.contracts_config,
        }

    if not payload["budget_thresholds"]:
        payload.pop("budget_thresholds")
    if not payload["env"]:
        payload.pop("env")
    if not payload["redact"]:
        payload.pop("redact")
    if payload.get("workdir") is None:
        payload.pop("workdir")

    return payload


def migrate_spec_file(
    *,
    spec_path: Path,
    output_path: Path | None,
    in_place: bool,
) -> Path:
    if in_place and output_path is not None:
        raise ValueError("--in-place and --output are mutually exclusive")

    source = spec_path.resolve()
    if not source.exists():
        raise FileNotFoundError(f"Spec file not found: {source}")

    spec = load_spec(source)
    payload = spec_to_v03_payload(spec)
    rendered = yaml.safe_dump(payload, sort_keys=False, default_flow_style=False)

    if in_place:
        destination = source
    elif output_path is not None:
        destination = output_path.resolve()
    else:
        destination = source.with_name(f"{source.stem}.v03{source.suffix}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(rendered, encoding="utf-8")
    return destination


__all__ = ["migrate_spec_file", "spec_to_v03_payload"]
