from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class TRTViolation:
    code: str
    message: str
    failure_class: str
    event_index: int
    expected: Any | None = None
    observed: Any | None = None
    hint: str | None = None


__all__ = ["TRTViolation"]
