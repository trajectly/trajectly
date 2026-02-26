from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

REDACTION_TOKEN = "[REDACTED]"


def _redact_string(value: str, patterns: Sequence[re.Pattern[str]]) -> str:
    redacted = value
    for pattern in patterns:
        redacted = pattern.sub(REDACTION_TOKEN, redacted)
    return redacted


def apply_redactions(value: Any, regex_patterns: Sequence[str]) -> Any:
    if not regex_patterns:
        return value
    compiled = [re.compile(pattern) for pattern in regex_patterns]

    def walk(node: Any) -> Any:
        if isinstance(node, str):
            return _redact_string(node, compiled)
        if isinstance(node, Mapping):
            return {str(key): walk(v) for key, v in node.items()}
        if isinstance(node, Sequence) and not isinstance(node, (str, bytes, bytearray)):
            return [walk(item) for item in node]
        return node

    return walk(value)
