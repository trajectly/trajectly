from __future__ import annotations

import json
import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
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


class SDKContext:
    def __init__(self, settings: _RuntimeSettings) -> None:
        self._settings = settings
        self._start = time.monotonic()
        self._lock = threading.Lock()
        self._matcher: FixtureMatcher | None = None

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
        settings = _RuntimeSettings(
            mode=mode,
            events_path=Path(events_file) if events_file else None,
            fixtures_path=Path(fixtures_file) if fixtures_file else None,
            fixture_policy=policy,
            strict=strict,
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
