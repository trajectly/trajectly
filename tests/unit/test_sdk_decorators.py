from __future__ import annotations

import asyncio
import inspect
from typing import Any

from trajectly.sdk import llm_call, tool


class FakeDecoratorContext:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def invoke_tool(self, name: str, fn: Any, args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any:
        self.calls.append({"kind": "tool", "name": name, "args": args, "kwargs": kwargs})
        return fn(*args, **kwargs)

    async def invoke_tool_async(self, name: str, fn: Any, args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any:
        self.calls.append({"kind": "tool_async", "name": name, "args": args, "kwargs": kwargs})
        result = fn(*args, **kwargs)
        if inspect.isawaitable(result):
            return await result
        return result

    def invoke_llm(
        self,
        provider: str,
        model: str,
        fn: Any,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> Any:
        self.calls.append(
            {
                "kind": "llm",
                "provider": provider,
                "model": model,
                "args": args,
                "kwargs": kwargs,
            }
        )
        return fn(*args, **kwargs)

    async def invoke_llm_async(
        self,
        provider: str,
        model: str,
        fn: Any,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> Any:
        self.calls.append(
            {
                "kind": "llm_async",
                "provider": provider,
                "model": model,
                "args": args,
                "kwargs": kwargs,
            }
        )
        result = fn(*args, **kwargs)
        if inspect.isawaitable(result):
            return await result
        return result


def test_tool_decorator_supports_async_callable(monkeypatch: Any) -> None:
    context = FakeDecoratorContext()
    monkeypatch.setattr("trajectly.sdk.get_context", lambda: context)

    @tool("add")
    async def add(left: int, right: int) -> int:
        return left + right

    result = asyncio.run(add(2, 3))

    assert result == 5
    assert context.calls == [
        {
            "kind": "tool_async",
            "name": "add",
            "args": (2, 3),
            "kwargs": {},
        }
    ]


def test_llm_call_decorator_supports_async_callable(monkeypatch: Any) -> None:
    context = FakeDecoratorContext()
    monkeypatch.setattr("trajectly.sdk.get_context", lambda: context)

    @llm_call(provider="mock", model="unit")
    async def generate(prompt: str) -> dict[str, Any]:
        return {"response": prompt.upper(), "usage": {"total_tokens": 4}}

    result = asyncio.run(generate("hello"))

    assert result == {"response": "HELLO", "usage": {"total_tokens": 4}}
    assert context.calls == [
        {
            "kind": "llm_async",
            "provider": "mock",
            "model": "unit",
            "args": ("hello",),
            "kwargs": {},
        }
    ]
