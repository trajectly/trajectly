from __future__ import annotations

import json
import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypeVar

from trajectly.fixtures import FixtureLookupError, FixtureMatcher, FixtureStore

T = TypeVar("T")


class SDKRuntimeError(RuntimeError):
    pass


@dataclass(slots=True)
class _RuntimeSettings:
    mode: str
    events_path: Path | None
    fixtures_path: Path | None
    fixture_policy: str
    strict: bool
    contracts: _RuntimeContracts = field(default_factory=lambda: _RuntimeContracts())


@dataclass(slots=True)
class _RuntimeContracts:
    tools_allow: set[str] = field(default_factory=set)
    tools_deny: set[str] = field(default_factory=set)
    max_calls_total: int | None = None
    deny_write_tools: bool = False


_WRITE_TOOL_HINTS = (
    "write",
    "delete",
    "remove",
    "rm",
    "update",
    "patch",
    "save",
    "create",
    "insert",
    "upsert",
)


def _looks_like_write_tool(tool_name: str) -> bool:
    normalized = tool_name.strip().lower()
    return any(token in normalized for token in _WRITE_TOOL_HINTS)


def _parse_runtime_contracts(raw: str | None) -> _RuntimeContracts:
    if not raw:
        return _RuntimeContracts()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return _RuntimeContracts()
    if not isinstance(payload, dict):
        return _RuntimeContracts()

    tools = payload.get("tools") or {}
    side_effects = payload.get("side_effects") or {}
    if not isinstance(tools, dict):
        tools = {}
    if not isinstance(side_effects, dict):
        side_effects = {}

    allow_raw = tools.get("allow")
    deny_raw = tools.get("deny")
    max_calls_raw = tools.get("max_calls_total")
    deny_write_raw = side_effects.get("deny_write_tools", False)

    allow = set()
    if isinstance(allow_raw, list):
        allow = {str(item) for item in allow_raw}

    deny = set()
    if isinstance(deny_raw, list):
        deny = {str(item) for item in deny_raw}

    max_calls_total: int | None = None
    if max_calls_raw is not None:
        try:
            parsed_max = int(max_calls_raw)
            if parsed_max >= 0:
                max_calls_total = parsed_max
        except (TypeError, ValueError):
            max_calls_total = None

    deny_write_tools = bool(deny_write_raw)
    return _RuntimeContracts(
        tools_allow=allow,
        tools_deny=deny,
        max_calls_total=max_calls_total,
        deny_write_tools=deny_write_tools,
    )


class SDKContext:
    def __init__(self, settings: _RuntimeSettings) -> None:
        self._settings = settings
        self._start = time.monotonic()
        self._lock = threading.Lock()
        self._matcher: FixtureMatcher | None = None
        self._tool_calls_total = 0

        if settings.mode == "replay" and settings.fixtures_path and settings.fixtures_path.exists():
            store = FixtureStore.load(settings.fixtures_path)
            self._matcher = FixtureMatcher(
                store=store,
                policy=settings.fixture_policy,
                strict=settings.strict,
            )

    @staticmethod
    def from_env() -> SDKContext:
        mode = os.getenv("TRAJECTLY_MODE", "record").strip().lower()
        events_file = os.getenv("TRAJECTLY_EVENTS_FILE")
        fixtures_file = os.getenv("TRAJECTLY_FIXTURES_FILE")
        policy = os.getenv("TRAJECTLY_FIXTURE_POLICY", "by_index")
        strict = os.getenv("TRAJECTLY_STRICT", "0") == "1"
        contracts = _parse_runtime_contracts(os.getenv("TRAJECTLY_CONTRACTS_JSON"))
        settings = _RuntimeSettings(
            mode=mode,
            events_path=Path(events_file) if events_file else None,
            fixtures_path=Path(fixtures_file) if fixtures_file else None,
            fixture_policy=policy,
            strict=strict,
            contracts=contracts,
        )
        return SDKContext(settings=settings)

    @property
    def mode(self) -> str:
        return self._settings.mode

    def agent_step(self, name: str, details: dict[str, Any] | None = None) -> None:
        payload = {"name": name, "details": details or {}}
        self._emit("agent_step", payload)

    def invoke_tool(
        self,
        name: str,
        fn: Callable[..., T],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> T:
        input_payload = {"args": self._safe(args), "kwargs": self._safe(kwargs)}
        self._emit("tool_called", {"tool_name": name, "input": input_payload})

        contract_error = self._check_tool_contracts(name)
        if contract_error:
            self._emit("tool_returned", {"tool_name": name, "error": contract_error, "output": None})
            raise SDKRuntimeError(contract_error)

        if self.mode == "replay" and self._matcher is not None:
            try:
                fixture = self._matcher.match("tool", name, input_payload)
            except FixtureLookupError as exc:
                self._emit("tool_returned", {"tool_name": name, "error": str(exc), "output": None})
                raise SDKRuntimeError(str(exc)) from exc

            if fixture is not None:
                output_payload = fixture.output_payload.get("output")
                error = fixture.output_payload.get("error")
                self._emit(
                    "tool_returned",
                    {"tool_name": name, "output": self._safe(output_payload), "error": error},
                    meta={"replayed": True},
                )
                if error:
                    raise SDKRuntimeError(str(error))
                return output_payload  # type: ignore[return-value]

            if self._settings.strict:
                message = f"Missing fixture for tool call: {name}"
                self._emit("tool_returned", {"tool_name": name, "output": None, "error": message})
                raise SDKRuntimeError(message)

        try:
            output = fn(*args, **kwargs)
        except Exception as exc:
            self._emit("tool_returned", {"tool_name": name, "output": None, "error": str(exc)})
            raise

        self._emit("tool_returned", {"tool_name": name, "output": self._safe(output), "error": None})
        return output

    def _check_tool_contracts(self, tool_name: str) -> str | None:
        contracts = self._settings.contracts

        self._tool_calls_total += 1
        if contracts.max_calls_total is not None and self._tool_calls_total > contracts.max_calls_total:
            return (
                "CONTRACT_MAX_CALLS_TOTAL_EXCEEDED: "
                f"limit={contracts.max_calls_total}, actual={self._tool_calls_total}"
            )

        if tool_name in contracts.tools_deny:
            return f"CONTRACT_TOOL_DENIED: {tool_name}"

        if contracts.tools_allow and tool_name not in contracts.tools_allow:
            return f"CONTRACT_TOOL_NOT_ALLOWED: {tool_name}"

        if contracts.deny_write_tools and _looks_like_write_tool(tool_name):
            return f"CONTRACT_WRITE_TOOL_DENIED: {tool_name}"

        return None

    def invoke_llm(
        self,
        provider: str,
        model: str,
        fn: Callable[..., T],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> T:
        request_payload = {"args": self._safe(args), "kwargs": self._safe(kwargs)}
        name = f"{provider}:{model}"
        self._emit(
            "llm_called",
            {
                "provider": provider,
                "model": model,
                "request": request_payload,
            },
        )

        if self.mode == "replay" and self._matcher is not None:
            try:
                fixture = self._matcher.match("llm", name, request_payload)
            except FixtureLookupError as exc:
                self._emit(
                    "llm_returned",
                    {
                        "provider": provider,
                        "model": model,
                        "response": None,
                        "usage": {},
                        "error": str(exc),
                    },
                )
                raise SDKRuntimeError(str(exc)) from exc

            if fixture is not None:
                response_payload = fixture.output_payload.get("response")
                usage = fixture.output_payload.get("usage", {})
                error = fixture.output_payload.get("error")
                result_payload = fixture.output_payload.get("result")
                replay_result = result_payload
                if replay_result is None:
                    replay_result = {
                        "response": response_payload,
                        "usage": usage if isinstance(usage, dict) else {},
                    }
                self._emit(
                    "llm_returned",
                    {
                        "provider": provider,
                        "model": model,
                        "response": self._safe(response_payload),
                        "usage": self._safe(usage),
                        "result": self._safe(replay_result),
                        "error": error,
                    },
                    meta={"replayed": True},
                )
                if error:
                    raise SDKRuntimeError(str(error))
                return replay_result  # type: ignore[return-value]

            if self._settings.strict:
                message = f"Missing fixture for llm call: {name}"
                self._emit(
                    "llm_returned",
                    {
                        "provider": provider,
                        "model": model,
                        "response": None,
                        "usage": {},
                        "error": message,
                    },
                )
                raise SDKRuntimeError(message)

        try:
            result = fn(*args, **kwargs)
        except Exception as exc:
            self._emit(
                "llm_returned",
                {
                    "provider": provider,
                    "model": model,
                    "response": None,
                    "usage": {},
                    "error": str(exc),
                },
            )
            raise

        response, usage = self._normalize_llm_result(result)
        self._emit(
            "llm_returned",
            {
                "provider": provider,
                "model": model,
                "response": self._safe(response),
                "usage": self._safe(usage),
                "result": self._safe(result),
                "error": None,
            },
        )
        return result

    def _normalize_llm_result(self, result: Any) -> tuple[Any, dict[str, Any]]:
        if isinstance(result, dict):
            usage = result.get("usage", {})
            response = result.get("response", result)
            if isinstance(usage, dict):
                return response, usage
            return response, {}
        return result, {}

    def _emit(self, event_type: str, payload: dict[str, Any], meta: dict[str, Any] | None = None) -> None:
        if self._settings.events_path is None:
            return
        record = {
            "event_type": event_type,
            "rel_ms": int((time.monotonic() - self._start) * 1000),
            "payload": self._safe(payload),
            "meta": meta or {},
        }
        line = json.dumps(record, sort_keys=True, separators=(",", ":"))
        with self._lock:
            self._settings.events_path.parent.mkdir(parents=True, exist_ok=True)
            with self._settings.events_path.open("a", encoding="utf-8") as handle:
                handle.write(line)
                handle.write("\n")

    def _safe(self, value: Any) -> Any:
        try:
            json.dumps(value)
            return value
        except TypeError:
            if isinstance(value, dict):
                return {str(k): self._safe(v) for k, v in value.items()}
            if isinstance(value, (list, tuple)):
                return [self._safe(item) for item in value]
            return str(value)


_CONTEXT: SDKContext | None = None


def get_context() -> SDKContext:
    global _CONTEXT
    if _CONTEXT is None:
        _CONTEXT = SDKContext.from_env()
    return _CONTEXT
