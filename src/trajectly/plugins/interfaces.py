"""Plugin module: trajectly/plugins/interfaces.py."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from trajectly.diff.models import Finding
from trajectly.events import TraceEvent


class SemanticDiffPlugin(Protocol):
    # v0.3.x compatibility surface:
    # Semantic plugins still receive legacy diff findings while TRT remains
    # authoritative for verdict semantics.
    """Represent `SemanticDiffPlugin`."""
    def compare(
        self,
        baseline_trace: list[TraceEvent],
        current_trace: list[TraceEvent],
    ) -> list[Finding]:
        """Execute `compare`."""
        ...


class RunHookPlugin(Protocol):
    """Represent `RunHookPlugin`."""
    def on_run_finished(self, context: dict[str, Any], report_paths: dict[str, Path]) -> None:
        """Execute `on_run_finished`."""
        ...
