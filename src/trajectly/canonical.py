from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from typing import Any


def _normalize_float(value: float) -> float | str:
    if math.isnan(value):
        return "NaN"
    if math.isinf(value):
        return "Infinity" if value > 0 else "-Infinity"
    return round(value, 12)


def normalize_for_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): normalize_for_json(value[key]) for key in sorted(value.keys(), key=str)}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [normalize_for_json(item) for item in value]
    if isinstance(value, float):
        return _normalize_float(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if value is None or isinstance(value, (str, int, bool)):
        return value
    return str(value)


def canonical_dumps(value: Any) -> str:
    normalized = normalize_for_json(value)
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_of_data(value: Any) -> str:
    digest = hashlib.sha256(canonical_dumps(value).encode("utf-8"))
    return digest.hexdigest()


def sha256_of_subset(value: Mapping[str, Any], ignored_keys: set[str] | None = None) -> str:
    ignored = ignored_keys or set()
    subset = {k: v for k, v in value.items() if k not in ignored}
    return sha256_of_data(subset)
