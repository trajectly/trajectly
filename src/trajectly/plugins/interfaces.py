from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from trajectly.diff.models import Finding
from trajectly.events import TraceEvent


class SemanticDiffPlugin(Protocol):
    def compare(
        self,
        baseline_trace: list[TraceEvent],
        current_trace: list[TraceEvent],
    ) -> list[Finding]:
        ...


class RunHookPlugin(Protocol):
    def on_run_finished(self, context: dict[str, Any], report_paths: dict[str, Path]) -> None:
        ...
