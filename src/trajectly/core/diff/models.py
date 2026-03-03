"""Core implementation module: trajectly/core/diff/models.py."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(slots=True)
class Finding:
    """Represent `Finding`."""
    classification: str
    message: str
    severity: str = "error"
    path: str | None = None
    baseline: Any = None
    current: Any = None

    def to_dict(self) -> dict[str, Any]:
        """Execute `to_dict`."""
        return asdict(self)


@dataclass(slots=True)
class DiffResult:
    """Represent `DiffResult`."""
    summary: dict[str, Any]
    findings: list[Finding]

    def to_dict(self) -> dict[str, Any]:
        """Execute `to_dict`."""
        return {
            "summary": self.summary,
            "findings": [finding.to_dict() for finding in self.findings],
        }
