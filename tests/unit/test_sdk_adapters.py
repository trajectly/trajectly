from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from trajectly.sdk.adapters import (
    anthropic_messages_create,
    invoke_llm_call,
    invoke_tool_call,
    langchain_invoke,
    openai_chat_completion,
)


class FakeContext:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def invoke_tool(
        self,
        name: str,
        fn: Any,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> Any:
        self.calls.append({"kind": "tool", "name": name, "args": args, "kwargs": kwargs})
        return fn(*args, **kwargs)

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


class FakeCallable:
    def __init__(self, result: Any) -> None:
        self.result = result
        self.requests: list[dict[str, Any]] = []

    def __call__(self, **kwargs: Any) -> Any:
        self.requests.append(kwargs)
        return self.result


class FakeOpenAIClient:
    def __init__(self, result: Any) -> None:
        self.create = FakeCallable(result)
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))


class FakeAnthropicClient:
    def __init__(self, result: Any) -> None:
        self.create = FakeCallable(result)
        self.messages = SimpleNamespace(create=self.create)


class OpenAIUsage:
    def __init__(self, total_tokens: int) -> None:
        self.total_tokens = total_tokens


class OpenAIMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class OpenAIChoice:
    def __init__(self, content: str) -> None:
        self.message = OpenAIMessage(content)


class OpenAIResponse:
    def __init__(self, content: str, total_tokens: int) -> None:
        self.choices = [OpenAIChoice(content)]
        self.usage = OpenAIUsage(total_tokens)


class AnthropicUsage:
    def __init__(self, input_tokens: int, output_tokens: int) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class AnthropicBlock:
    def __init__(self, text: str) -> None:
        self.text = text


class AnthropicResponse:
    def __init__(self, lines: list[str], input_tokens: int, output_tokens: int) -> None:
        self.content = [AnthropicBlock(line) for line in lines]
        self.usage = AnthropicUsage(input_tokens, output_tokens)


class FakeRunnable:
    def __init__(self, result: Any) -> None:
        self.result = result
        self.calls: list[tuple[Any, dict[str, Any]]] = []

    def invoke(self, input_value: Any, **kwargs: Any) -> Any:
        self.calls.append((input_value, kwargs))
        return self.result


def test_invoke_tool_call_uses_context() -> None:
    context = FakeContext()

    def add(left: int, right: int) -> int:
        return left + right

    result = invoke_tool_call("add", add, 2, 5, context=context)

    assert result == 7
    assert context.calls == [
        {
            "kind": "tool",
            "name": "add",
            "args": (2, 5),
            "kwargs": {},
        }
    ]


def test_invoke_llm_call_uses_context() -> None:
    context = FakeContext()

    def fake_llm(*, prompt: str) -> dict[str, Any]:
        return {"response": prompt.upper(), "usage": {"total_tokens": 3}}

    result = invoke_llm_call("mock", "deterministic", fake_llm, context=context, prompt="hello")

    assert result == {"response": "HELLO", "usage": {"total_tokens": 3}}
    assert context.calls[0]["provider"] == "mock"
    assert context.calls[0]["model"] == "deterministic"
    assert context.calls[0]["kwargs"] == {"prompt": "hello"}


def test_openai_adapter_from_mapping_response() -> None:
    context = FakeContext()
    client = FakeOpenAIClient(
        {
            "choices": [{"message": {"content": "openai mapping"}}],
            "usage": {"total_tokens": 11},
        }
    )

    result = openai_chat_completion(
        client,
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "hi"}],
        temperature=0,
        context=context,
    )

    assert result["response"] == "openai mapping"
    assert result["usage"] == {"total_tokens": 11}
    assert client.create.requests[0]["model"] == "gpt-4o-mini"
    assert context.calls[0]["provider"] == "openai"


def test_openai_adapter_from_object_response() -> None:
    context = FakeContext()
    client = FakeOpenAIClient(OpenAIResponse(content="openai object", total_tokens=7))

    result = openai_chat_completion(
        client,
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": "hello"}],
        context=context,
    )

    assert result["response"] == "openai object"
    assert result["usage"] == {"total_tokens": 7}


def test_openai_adapter_validates_client_shape() -> None:
    with pytest.raises(ValueError, match=r"chat\.completions\.create"):
        openai_chat_completion(object(), model="gpt", messages=[])


def test_anthropic_adapter_from_mapping_response() -> None:
    context = FakeContext()
    client = FakeAnthropicClient(
        {
            "content": [{"text": "line one"}, {"text": "line two"}],
            "usage": {"input_tokens": 9, "output_tokens": 5},
        }
    )

    result = anthropic_messages_create(
        client,
        model="claude-sonnet",
        messages=[{"role": "user", "content": "summarize"}],
        max_tokens=64,
        context=context,
    )

    assert result["response"] == "line one\nline two"
    assert result["usage"] == {"input_tokens": 9, "output_tokens": 5}
    assert client.create.requests[0]["max_tokens"] == 64
    assert context.calls[0]["provider"] == "anthropic"


def test_anthropic_adapter_from_object_response() -> None:
    context = FakeContext()
    client = FakeAnthropicClient(AnthropicResponse(lines=["A", "B"], input_tokens=3, output_tokens=4))

    result = anthropic_messages_create(
        client,
        model="claude-haiku",
        messages=[{"role": "user", "content": "prompt"}],
        context=context,
    )

    assert result["response"] == "A\nB"
    assert result["usage"] == {"input_tokens": 3, "output_tokens": 4}


def test_anthropic_adapter_validates_client_shape() -> None:
    with pytest.raises(ValueError, match=r"messages\.create"):
        anthropic_messages_create(object(), model="claude", messages=[])


def test_langchain_adapter_with_dict_result() -> None:
    context = FakeContext()
    runnable = FakeRunnable({"text": "langchain text", "usage": {"total_tokens": 6}})

    result = langchain_invoke(
        runnable,
        {"question": "what is trajectly?"},
        model="langchain-fake",
        provider="langchain",
        context=context,
        config={"temperature": 0},
    )

    assert result["response"] == "langchain text"
    assert result["usage"] == {"total_tokens": 6}
    assert runnable.calls[0][0] == {"question": "what is trajectly?"}
    assert runnable.calls[0][1] == {"config": {"temperature": 0}}


def test_langchain_adapter_with_string_result() -> None:
    context = FakeContext()
    runnable = FakeRunnable("direct string output")

    result = langchain_invoke(runnable, "prompt", context=context)

    assert result["response"] == "direct string output"
    assert result["usage"] == {}


def test_langchain_adapter_validates_invoke() -> None:
    with pytest.raises(ValueError, match="invoke"):
        langchain_invoke(object(), "prompt")
