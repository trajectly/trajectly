from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any, Protocol, TypeVar, cast

from trajectly.sdk.context import get_context

T = TypeVar("T")


class SDKContextLike(Protocol):
    def invoke_tool(
        self,
        name: str,
        fn: Callable[..., T],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> T: ...

    def invoke_llm(
        self,
        provider: str,
        model: str,
        fn: Callable[..., T],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> T: ...


def _resolve_context(context: SDKContextLike | None) -> SDKContextLike:
    if context is not None:
        return context
    return get_context()


def _as_mapping(value: Any) -> Mapping[str, Any] | None:
    if isinstance(value, Mapping):
        return cast(Mapping[str, Any], value)
    if hasattr(value, "__dict__"):
        raw = cast(dict[str, Any], vars(value))
        return raw
    return None


def _as_usage_dict(value: Any) -> dict[str, Any]:
    mapping = _as_mapping(value)
    if mapping is None:
        return {}
    return {str(key): mapping[key] for key in mapping}


def _lookup(value: Any, key: str, default: Any = None) -> Any:
    mapping = _as_mapping(value)
    if mapping is not None:
        return mapping.get(key, default)
    return getattr(value, key, default)


def _resolve_nested_attribute(root: Any, segments: tuple[str, ...], label: str) -> Any:
    current = root
    for segment in segments:
        if not hasattr(current, segment):
            joined = ".".join(segments)
            raise ValueError(f"{label} client must expose `{joined}`")
        current = getattr(current, segment)
    return current


def _extract_openai_response(result: Any) -> tuple[Any, dict[str, Any]]:
    usage = _as_usage_dict(_lookup(result, "usage", {}))
    choices = _lookup(result, "choices", [])

    if isinstance(choices, Sequence) and not isinstance(choices, (str, bytes)) and choices:
        first = choices[0]
        message = _lookup(first, "message")
        if message is not None:
            content = _lookup(message, "content")
            if content is not None:
                return content, usage
        text = _lookup(first, "text")
        if text is not None:
            return text, usage

    response = _lookup(result, "response", result)
    return response, usage


def _extract_anthropic_response(result: Any) -> tuple[Any, dict[str, Any]]:
    usage = _as_usage_dict(_lookup(result, "usage", {}))
    content_blocks = _lookup(result, "content", [])
    if isinstance(content_blocks, Sequence) and not isinstance(content_blocks, (str, bytes)):
        texts = []
        for block in content_blocks:
            text = _lookup(block, "text")
            if text is None:
                continue
            texts.append(str(text))
        if texts:
            return "\n".join(texts), usage

    response = _lookup(result, "response", result)
    return response, usage


def invoke_tool_call(
    name: str,
    fn: Callable[..., T],
    *args: Any,
    context: SDKContextLike | None = None,
    **kwargs: Any,
) -> T:
    ctx = _resolve_context(context)
    return ctx.invoke_tool(name, fn, args, kwargs)


def invoke_llm_call(
    provider: str,
    model: str,
    fn: Callable[..., T],
    *args: Any,
    context: SDKContextLike | None = None,
    **kwargs: Any,
) -> T:
    ctx = _resolve_context(context)
    return ctx.invoke_llm(provider=provider, model=model, fn=fn, args=args, kwargs=kwargs)


def openai_chat_completion(
    client: Any,
    *,
    model: str,
    messages: list[dict[str, Any]],
    context: SDKContextLike | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    create_fn = _resolve_nested_attribute(client, ("chat", "completions", "create"), label="openai")
    request = {"model": model, "messages": messages, **kwargs}
    ctx = _resolve_context(context)
    raw_result = ctx.invoke_llm(provider="openai", model=model, fn=create_fn, args=(), kwargs=request)
    response, usage = _extract_openai_response(raw_result)
    return {"response": response, "usage": usage, "result": raw_result}


def anthropic_messages_create(
    client: Any,
    *,
    model: str,
    messages: list[dict[str, Any]],
    context: SDKContextLike | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    create_fn = _resolve_nested_attribute(client, ("messages", "create"), label="anthropic")
    request = {"model": model, "messages": messages, **kwargs}
    ctx = _resolve_context(context)
    raw_result = ctx.invoke_llm(provider="anthropic", model=model, fn=create_fn, args=(), kwargs=request)
    response, usage = _extract_anthropic_response(raw_result)
    return {"response": response, "usage": usage, "result": raw_result}


def langchain_invoke(
    runnable: Any,
    input_value: Any,
    *,
    model: str = "langchain-runnable",
    provider: str = "langchain",
    context: SDKContextLike | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    if not hasattr(runnable, "invoke"):
        raise ValueError("langchain runnable must expose `invoke`")
    invoke_fn = runnable.invoke
    raw_result = invoke_llm_call(provider, model, invoke_fn, input_value, context=context, **kwargs)

    usage = {}
    response: Any = raw_result
    mapping = _as_mapping(raw_result)
    if mapping is not None:
        usage = _as_usage_dict(mapping.get("usage", {}))
        if "response" in mapping:
            response = mapping["response"]
        elif "text" in mapping:
            response = mapping["text"]

    return {"response": response, "usage": usage, "result": raw_result}


__all__ = [
    "SDKContextLike",
    "anthropic_messages_create",
    "invoke_llm_call",
    "invoke_tool_call",
    "langchain_invoke",
    "openai_chat_completion",
]
