from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any
from urllib.parse import urlparse

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_RE = re.compile(r"\b(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}\b")
URL_RE = re.compile(r"https?://[^\s)]+")


def _walk_strings(value: Any) -> Iterable[str]:
    # Predicate extraction intentionally walks only serializable payload-like
    # shapes to keep abstraction deterministic and side-effect free.
    if isinstance(value, str):
        yield value
        return
    if isinstance(value, dict):
        for item in value.values():
            yield from _walk_strings(item)
        return
    if isinstance(value, list | tuple):
        for item in value:
            yield from _walk_strings(item)


def contains_email(value: Any) -> bool:
    return any(EMAIL_RE.search(text) for text in _walk_strings(value))


def contains_phone(value: Any) -> bool:
    return any(PHONE_RE.search(text) for text in _walk_strings(value))


def extract_domains(value: Any) -> list[str]:
    domains: set[str] = set()
    for text in _walk_strings(value):
        candidates = [text, *URL_RE.findall(text)]
        for candidate in candidates:
            parsed = urlparse(candidate)
            host = parsed.hostname
            if host:
                domains.add(host.lower())
    return sorted(domains)


def extract_numeric_values(value: Any) -> list[float]:
    numbers: list[float] = []
    if isinstance(value, int | float):
        return [float(value)]
    if isinstance(value, dict):
        for item in value.values():
            numbers.extend(extract_numeric_values(item))
        return numbers
    if isinstance(value, list | tuple):
        for item in value:
            numbers.extend(extract_numeric_values(item))
        return numbers
    return numbers


__all__ = [
    "contains_email",
    "contains_phone",
    "extract_domains",
    "extract_numeric_values",
]
