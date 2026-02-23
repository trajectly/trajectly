from __future__ import annotations

from dataclasses import dataclass

from trajectly.abstraction.pipeline import AbstractTrace


@dataclass(slots=True)
class SkeletonStep:
    event_index: int
    tool_name: str


def extract_call_skeleton(
    abstract_trace: AbstractTrace,
    *,
    ignore_call_tools: set[str] | None = None,
) -> list[SkeletonStep]:
    ignored = ignore_call_tools or set()
    steps: list[SkeletonStep] = []
    for token in abstract_trace.tokens:
        if token.kind != "CALL":
            continue
        if token.name in ignored:
            continue
        steps.append(SkeletonStep(event_index=token.event_index, tool_name=token.name))
    return steps


__all__ = [
    "SkeletonStep",
    "extract_call_skeleton",
]
