from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from trajectly.normalize.version import NORMALIZER_VERSION

DEFAULT_VOLATILE_KEYS = (
    "timestamp",
    "run_id",
    "request_id",
    "event_id",
    "rel_ms",
    "created_at",
    "updated_at",
)


@dataclass(slots=True, frozen=True)
class CanonicalNormalizer:
    version: str = NORMALIZER_VERSION
    volatile_keys: tuple[str, ...] = DEFAULT_VOLATILE_KEYS
    float_precision: int = 12

    def _normalize_float(self, value: float) -> float | str:
        if math.isnan(value):
            return "NaN"
        if math.isinf(value):
            return "Infinity" if value > 0 else "-Infinity"
        return round(value, self.float_precision)

    def strip_volatile(self, value: Any) -> Any:
        # Canonical ordering is required so hashing/signatures stay stable across
        # Python versions and mapping insertion order differences.
        if isinstance(value, Mapping):
            stripped: dict[str, Any] = {}
            for key in sorted(value.keys(), key=str):
                key_text = str(key)
                if key_text in self.volatile_keys:
                    continue
                stripped[key_text] = self.strip_volatile(value[key])
            return stripped
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            return [self.strip_volatile(item) for item in value]
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        if isinstance(value, float):
            return self._normalize_float(value)
        if value is None or isinstance(value, (str, int, bool)):
            return value
        return str(value)

    def normalize(self, value: Any, *, strip_volatile: bool = True) -> Any:
        if strip_volatile:
            return self.strip_volatile(value)
        if isinstance(value, Mapping):
            return {str(k): self.normalize(value[k], strip_volatile=False) for k in sorted(value.keys(), key=str)}
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            return [self.normalize(item, strip_volatile=False) for item in value]
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        if isinstance(value, float):
            return self._normalize_float(value)
        if value is None or isinstance(value, (str, int, bool)):
            return value
        return str(value)

    def canonical_dumps(self, value: Any, *, strip_volatile: bool = True) -> str:
        normalized = self.normalize(value, strip_volatile=strip_volatile)
        return json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

    def sha256(self, value: Any, *, strip_volatile: bool = True) -> str:
        digest = hashlib.sha256(self.canonical_dumps(value, strip_volatile=strip_volatile).encode("utf-8"))
        return digest.hexdigest()

    def sha256_subset(self, value: Mapping[str, Any], ignored_keys: set[str] | None = None) -> str:
        ignored = ignored_keys or set()
        # Subset hashing is used by legacy event-id paths; keys are filtered
        # before canonicalization so callers can exclude volatile envelope fields.
        subset = {str(k): value[k] for k in value.keys() if str(k) not in ignored}
        return self.sha256(subset, strip_volatile=False)


DEFAULT_CANONICAL_NORMALIZER = CanonicalNormalizer()


def normalize_for_json(value: Any) -> Any:
    return DEFAULT_CANONICAL_NORMALIZER.normalize(value, strip_volatile=False)


def canonical_dumps(value: Any) -> str:
    return DEFAULT_CANONICAL_NORMALIZER.canonical_dumps(value, strip_volatile=False)


def sha256_of_data(value: Any) -> str:
    return DEFAULT_CANONICAL_NORMALIZER.sha256(value, strip_volatile=False)


def sha256_of_subset(value: Mapping[str, Any], ignored_keys: set[str] | None = None) -> str:
    return DEFAULT_CANONICAL_NORMALIZER.sha256_subset(value, ignored_keys=ignored_keys)


__all__ = [
    "DEFAULT_CANONICAL_NORMALIZER",
    "DEFAULT_VOLATILE_KEYS",
    "CanonicalNormalizer",
    "canonical_dumps",
    "normalize_for_json",
    "sha256_of_data",
    "sha256_of_subset",
]
