from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

from trajectly.sdk.adapters import (
    SDKContextLike,
    anthropic_messages_create,
    autogen_chat_run,
    crewai_run_task,
    dspy_call,
    invoke_llm_call,
    invoke_tool_call,
    langchain_invoke,
    llamaindex_query,
    openai_chat_completion,
)
from trajectly.sdk.context import SDKContext, get_context

T = TypeVar("T")


def tool(name: str | None = None) -> Callable[[Callable[..., T]], Callable[..., T]]:
    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        tool_name = name or fn.__name__

        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            return get_context().invoke_tool(tool_name, fn, args, kwargs)

        return wrapper

    return decorator


def llm_call(
    provider: str = "mock",
    model: str = "default",
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            return get_context().invoke_llm(provider=provider, model=model, fn=fn, args=args, kwargs=kwargs)

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
    "get_context",
    "invoke_llm_call",
    "invoke_tool_call",
    "langchain_invoke",
    "llamaindex_query",
    "llm_call",
    "openai_chat_completion",
    "tool",
]
