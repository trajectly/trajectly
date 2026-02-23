from __future__ import annotations

import json
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from trajectly.canonical import sha256_of_data
from trajectly.events import TraceEvent


class FixtureLookupError(RuntimeError):
    pass


@dataclass(slots=True)
class FixtureExhaustedError(FixtureLookupError):
    kind: str
    name: str
    expected_signature: str
    consumed_count: int
    available_count: int

    def to_payload(self) -> dict[str, object]:
        context_key = "tool_name" if self.kind == "tool" else "llm_signature"
        return {
            "code": "FIXTURE_EXHAUSTED",
            "failure_class": "CONTRACT",
            "expected_signature": self.expected_signature,
            "consumed_count": self.consumed_count,
            "available_count": self.available_count,
            context_key: self.name,
        }

    def __str__(self) -> str:
        context_key = "tool_name" if self.kind == "tool" else "llm_signature"
        return (
            "FIXTURE_EXHAUSTED: "
            f"{context_key}={self.name} expected_signature={self.expected_signature} "
            f"consumed_count={self.consumed_count} available_count={self.available_count}"
        )


@dataclass(slots=True)
class FixtureEntry:
    kind: str
    name: str
    input_payload: dict[str, Any]
    input_hash: str
    output_payload: dict[str, Any]
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "name": self.name,
            "input_payload": self.input_payload,
            "input_hash": self.input_hash,
            "output_payload": self.output_payload,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FixtureEntry:
        return cls(
            kind=str(data["kind"]),
            name=str(data["name"]),
            input_payload=dict(data.get("input_payload", {})),
            input_hash=str(data.get("input_hash", "")),
            output_payload=dict(data.get("output_payload", {})),
            error=data.get("error"),
        )


@dataclass(slots=True)
class FixtureStore:
    entries: list[FixtureEntry]

    def to_dict(self) -> dict[str, Any]:
        return {"entries": [entry.to_dict() for entry in self.entries]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FixtureStore:
        rows = data.get("entries", [])
        entries = [FixtureEntry.from_dict(row) for row in rows]
        return cls(entries=entries)

    @classmethod
    def from_events(cls, events: list[TraceEvent]) -> FixtureStore:
        pending_tool: deque[dict[str, Any]] = deque()
        pending_llm: deque[dict[str, Any]] = deque()
        entries: list[FixtureEntry] = []

        for event in events:
            payload = event.payload
            if event.event_type == "tool_called":
                tool_name = str(payload.get("tool_name", "unknown"))
                input_payload = dict(payload.get("input", {}))
                pending_tool.append({
                    "name": tool_name,
                    "input": input_payload,
                    "hash": sha256_of_data(input_payload),
                })
            elif event.event_type == "tool_returned" and pending_tool:
                prior = pending_tool.popleft()
                output_payload = {
                    "output": payload.get("output"),
                    "error": payload.get("error"),
                }
                entries.append(
                    FixtureEntry(
                        kind="tool",
                        name=str(prior["name"]),
                        input_payload=dict(prior["input"]),
                        input_hash=str(prior["hash"]),
                        output_payload=output_payload,
                        error=payload.get("error"),
                    )
                )
            elif event.event_type == "llm_called":
                provider = str(payload.get("provider", "unknown"))
                model = str(payload.get("model", "unknown"))
                name = f"{provider}:{model}"
                request_payload = dict(payload.get("request", {}))
                pending_llm.append({
                    "name": name,
                    "input": request_payload,
                    "hash": sha256_of_data(request_payload),
                })
            elif event.event_type == "llm_returned" and pending_llm:
                prior = pending_llm.popleft()
                output_payload = {
                    "response": payload.get("response"),
                    "usage": payload.get("usage", {}),
                    "result": payload.get("result"),
                    "error": payload.get("error"),
                }
                entries.append(
                    FixtureEntry(
                        kind="llm",
                        name=str(prior["name"]),
                        input_payload=dict(prior["input"]),
                        input_hash=str(prior["hash"]),
                        output_payload=output_payload,
                        error=payload.get("error"),
                    )
                )

        return cls(entries=entries)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), sort_keys=True, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> FixtureStore:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        return cls.from_dict(loaded)


class FixtureMatcher:
    def __init__(self, store: FixtureStore, policy: str, strict: bool) -> None:
        self._policy = policy
        self._strict = strict
        self._entries: dict[tuple[str, str], list[FixtureEntry]] = defaultdict(list)
        for entry in store.entries:
            self._entries[(entry.kind, entry.name)].append(entry)
        self._index: dict[tuple[str, str], int] = defaultdict(int)
        self._used_hash_slots: set[tuple[tuple[str, str], int]] = set()

    def match(self, kind: str, name: str, input_payload: dict[str, Any]) -> FixtureEntry | None:
        key = (kind, name)
        entries = self._entries.get(key, [])
        request_hash = sha256_of_data(input_payload)

        if self._policy == "by_index":
            idx = self._index[key]
            if idx >= len(entries):
                if entries:
                    raise FixtureExhaustedError(
                        kind=kind,
                        name=name,
                        expected_signature=request_hash,
                        consumed_count=idx,
                        available_count=len(entries),
                    )
                return None
            candidate = entries[idx]
            self._index[key] += 1
            if self._strict and candidate.input_hash != request_hash:
                raise FixtureLookupError(
                    f"by_index mismatch for {kind}:{name}; expected hash {candidate.input_hash}, got {request_hash}"
                )
            return candidate

        matching_indices: list[int] = []
        for idx, candidate in enumerate(entries):
            if candidate.input_hash != request_hash:
                continue
            matching_indices.append(idx)
            slot = (key, idx)
            if slot in self._used_hash_slots:
                continue
            self._used_hash_slots.add(slot)
            return candidate
        if matching_indices:
            consumed_count = sum(1 for idx in matching_indices if (key, idx) in self._used_hash_slots)
            raise FixtureExhaustedError(
                kind=kind,
                name=name,
                expected_signature=request_hash,
                consumed_count=consumed_count,
                available_count=len(matching_indices),
            )
        return None
