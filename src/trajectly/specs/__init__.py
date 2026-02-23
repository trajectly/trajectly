from __future__ import annotations

import glob
from pathlib import Path
from typing import Any

from trajectly.specs.compat_v02 import (
    AgentContracts,
    BudgetThresholds,
    DataLeakContracts,
    FixturePolicy,
    NetworkContracts,
    SequenceContracts,
    SideEffectContracts,
    ToolContracts,
)
from trajectly.specs.v03 import AgentSpec, parse_spec_with_compat


def _load_yaml(path: Path) -> dict[str, Any]:
    import yaml

    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise ValueError(f"Spec file must be a mapping: {path}")
    return loaded


def load_spec(path: Path) -> AgentSpec:
    data = _load_yaml(path)
    return parse_spec_with_compat(data, source_path=path.resolve())


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
    return [load_spec(path) for path in paths]


__all__ = [
    "AgentContracts",
    "AgentSpec",
    "BudgetThresholds",
    "DataLeakContracts",
    "FixturePolicy",
    "NetworkContracts",
    "SequenceContracts",
    "SideEffectContracts",
    "ToolContracts",
    "load_spec",
    "load_specs",
]
