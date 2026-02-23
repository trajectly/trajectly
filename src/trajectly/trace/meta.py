from __future__ import annotations

from pathlib import Path


def default_trace_path(events_path: Path) -> Path:
    return events_path.parent / f"{events_path.stem}.trace.jsonl"


def default_trace_meta_path(trace_path: Path) -> Path:
    if trace_path.name.endswith(".trace.jsonl"):
        base = trace_path.name.removesuffix(".jsonl")
        return trace_path.with_name(f"{base}.meta.json")
    return trace_path.with_name(f"{trace_path.stem}.meta.json")


__all__ = [
    "default_trace_meta_path",
    "default_trace_path",
]
