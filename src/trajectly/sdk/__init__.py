from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any, TypeVar, cast

from trajectly.sdk.adapters import (
    SDKContextLike,
    anthropic_messages_create,
    autogen_chat_run,
    crewai_run_task,
    dspy_call,
    gemini_generate_content,
    invoke_llm_call,
    invoke_llm_call_async,
    invoke_tool_call,
    invoke_tool_call_async,
    langchain_invoke,
    llamaindex_query,
    openai_chat_completion,
)
from trajectly.sdk.context import SDKContext, get_context

T = TypeVar("T")


def tool(
    name: str | None = None,
) -> Callable[[Callable[..., T] | Callable[..., Awaitable[T]]], Callable[..., T] | Callable[..., Awaitable[T]]]:
    def decorator(
        fn: Callable[..., T] | Callable[..., Awaitable[T]],
    ) -> Callable[..., T] | Callable[..., Awaitable[T]]:
        tool_name = name or fn.__name__

        if inspect.iscoroutinefunction(fn):
            async_fn = cast(Callable[..., Awaitable[T]], fn)

            @wraps(async_fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> T:
                return await get_context().invoke_tool_async(tool_name, async_fn, args, kwargs)

            return async_wrapper

        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            sync_fn = cast(Callable[..., T], fn)
            return get_context().invoke_tool(tool_name, sync_fn, args, kwargs)

        return wrapper

    return decorator


def llm_call(
    provider: str = "mock",
    model: str = "default",
) -> Callable[[Callable[..., T] | Callable[..., Awaitable[T]]], Callable[..., T] | Callable[..., Awaitable[T]]]:
    def decorator(
        fn: Callable[..., T] | Callable[..., Awaitable[T]],
    ) -> Callable[..., T] | Callable[..., Awaitable[T]]:
        if inspect.iscoroutinefunction(fn):
            async_fn = cast(Callable[..., Awaitable[T]], fn)

            @wraps(async_fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> T:
                return await get_context().invoke_llm_async(
                    provider=provider,
                    model=model,
                    fn=async_fn,
                    args=args,
                    kwargs=kwargs,
                )

            return async_wrapper

        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            sync_fn = cast(Callable[..., T], fn)
            return get_context().invoke_llm(provider=provider, model=model, fn=sync_fn, args=args, kwargs=kwargs)

        return wrapper

    return decorator


def agent_step(name: str, details: dict[str, Any] | None = None) -> None:
    get_context().agent_step(name=name, details=details)


__all__ = [
    "SDKContext",
    "SDKContextLike",
    "agent_step",
    "anthropic_messages_create",
    "autogen_chat_run",
    "crewai_run_task",
    "dspy_call",
    "gemini_generate_content",
    "get_context",
    "invoke_llm_call",
    "invoke_llm_call_async",
    "invoke_tool_call",
    "invoke_tool_call_async",
    "langchain_invoke",
    "llamaindex_query",
    "llm_call",
    "openai_chat_completion",
    "tool",
]
