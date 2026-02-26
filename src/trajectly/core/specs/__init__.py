from __future__ import annotations

import glob
from pathlib import Path
from typing import Any

from trajectly.core.specs.compat_v02 import (
    AgentContracts,
    BudgetThresholds,
    DataLeakContracts,
    FixturePolicy,
    NetworkContracts,
    SequenceContracts,
    SideEffectContracts,
    ToolContracts,
)
from trajectly.core.specs.v03 import AgentSpec, parse_spec_with_compat

_MAX_EXTENDS_DEPTH = 10


def _load_yaml(path: Path) -> dict[str, Any]:
    import yaml

    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise ValueError(f"Spec file must be a mapping: {path}")
    return loaded


def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Deterministic deep-merge: dicts merge recursively, lists/scalars override."""
    merged = dict(base)
    for key in sorted(overlay):
        val = overlay[key]
        if key in merged and isinstance(merged[key], dict) and isinstance(val, dict):
            merged[key] = deep_merge(merged[key], val)
        else:
            merged[key] = val
    return merged


def _resolve_extends(data: dict[str, Any], source_path: Path, depth: int = 0) -> dict[str, Any]:
    """Recursively resolve `extends` chains with cycle detection."""
    extends_raw = data.pop("extends", None)
    if extends_raw is None:
        return data
    if depth >= _MAX_EXTENDS_DEPTH:
        raise ValueError(f"Spec extends depth exceeded {_MAX_EXTENDS_DEPTH}: circular reference?")

    extends_path = Path(extends_raw)
    if not extends_path.is_absolute():
        extends_path = (source_path.parent / extends_path).resolve()
    if not extends_path.exists():
        raise ValueError(f"extends target not found: {extends_path}")

    base_data = _load_yaml(extends_path)
    base_data = _resolve_extends(base_data, extends_path, depth + 1)
    return deep_merge(base_data, data)


def load_spec(path: Path) -> AgentSpec:
    data = _load_yaml(path)
    data = _resolve_extends(data, path.resolve())
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
    "deep_merge",
    "load_spec",
    "load_specs",
]
