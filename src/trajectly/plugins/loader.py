from __future__ import annotations

from importlib.metadata import entry_points
from pathlib import Path
from typing import Any

from trajectly.diff.models import Finding
from trajectly.events import TraceEvent
from trajectly.plugins.interfaces import RunHookPlugin, SemanticDiffPlugin


def _load_group(group: str) -> list[Any]:
    loaded: list[Any] = []
    for entry in entry_points().select(group=group):
        loaded.append(entry.load())
    return loaded


def run_semantic_plugins(
    baseline: list[TraceEvent],
    current: list[TraceEvent],
) -> list[Finding]:
    findings: list[Finding] = []
    for plugin in _load_group("trajectly.semantic_diff_plugins"):
        instance: SemanticDiffPlugin
        instance = plugin() if callable(plugin) else plugin
        findings.extend(instance.compare(baseline, current))
    return findings


def run_run_hooks(context: dict[str, Any], report_paths: dict[str, Path]) -> None:
    for plugin in _load_group("trajectly.run_hook_plugins"):
        instance: RunHookPlugin
        instance = plugin() if callable(plugin) else plugin
        instance.on_run_finished(context=context, report_paths=report_paths)
