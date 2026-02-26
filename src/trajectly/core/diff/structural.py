from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class StructuralChange:
    path: str
    baseline: Any
    current: Any


def structural_diff(baseline: Any, current: Any, path: str = "$") -> list[StructuralChange]:
    changes: list[StructuralChange] = []

    if type(baseline) is not type(current):
        changes.append(StructuralChange(path=path, baseline=baseline, current=current))
        return changes

    if isinstance(baseline, Mapping):
        keys = sorted(set(baseline.keys()) | set(current.keys()), key=str)
        for key in keys:
            key_path = f"{path}.{key}"
            left_missing = key not in baseline
            right_missing = key not in current
            if left_missing or right_missing:
                changes.append(
                    StructuralChange(
                        path=key_path,
                        baseline=baseline.get(key),
                        current=current.get(key),
                    )
                )
                continue
            changes.extend(structural_diff(baseline[key], current[key], key_path))
        return changes

    if isinstance(baseline, Sequence) and not isinstance(baseline, (str, bytes, bytearray)):
        max_len = max(len(baseline), len(current))
        for idx in range(max_len):
            idx_path = f"{path}[{idx}]"
            if idx >= len(baseline) or idx >= len(current):
                left = baseline[idx] if idx < len(baseline) else None
                right = current[idx] if idx < len(current) else None
                changes.append(StructuralChange(path=idx_path, baseline=left, current=right))
                continue
            changes.extend(structural_diff(baseline[idx], current[idx], idx_path))
        return changes

    if baseline != current:
        changes.append(StructuralChange(path=path, baseline=baseline, current=current))

    return changes
