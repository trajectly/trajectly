from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from trajectly.sdk.adapters import (
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


class FakeQueryEngine:
    def __init__(self, result: Any) -> None:
        self.result = result
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def query(self, prompt: str, **kwargs: Any) -> Any:
        self.calls.append((prompt, kwargs))
        return self.result


class LlamaIndexResponse:
    def __init__(self, response: str, prompt_tokens: int, completion_tokens: int) -> None:
        self.response = response
        self.metadata = {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens}


class FakeCrewTaskExecute:
    def __init__(self, result: Any) -> None:
        self.result = result
        self.calls: list[dict[str, Any]] = []

    def execute(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return self.result


class FakeCrewTaskRun:
    def __init__(self, result: Any) -> None:
        self.result = result
        self.calls: list[dict[str, Any]] = []

    def run(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return self.result


class CrewTaskResponse:
    def __init__(self, output: str, total_tokens: int) -> None:
        self.output = output
        self.usage = {"total_tokens": total_tokens}


class FakeAutoGenRunner:
    def __init__(self, result: Any) -> None:
        self.result = result
        self.calls: list[tuple[list[dict[str, Any]], dict[str, Any]]] = []

    def run(self, messages: list[dict[str, Any]], **kwargs: Any) -> Any:
        self.calls.append((messages, kwargs))
        return self.result


class AutoGenResult:
    def __init__(self, content: str, total_tokens: int) -> None:
        self.response = content
        self.usage = {"total_tokens": total_tokens}


class FakeDSPYCallableProgram:
    def __init__(self, result: Any) -> None:
        self.result = result
        self.calls: list[tuple[Any, dict[str, Any]]] = []

    def __call__(self, input_value: Any, **kwargs: Any) -> Any:
        self.calls.append((input_value, kwargs))
        return self.result


class FakeDSPYForwardProgram:
    def __init__(self, result: Any) -> None:
        self.result = result
        self.calls: list[tuple[Any, dict[str, Any]]] = []

    def forward(self, input_value: Any, **kwargs: Any) -> Any:
        self.calls.append((input_value, kwargs))
        return self.result


class DSPYResult:
    def __init__(self, answer: str, total_tokens: int) -> None:
        self.answer = answer
        self.usage = {"total_tokens": total_tokens}


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


def test_llamaindex_adapter_from_mapping_response() -> None:
    context = FakeContext()
    query_engine = FakeQueryEngine(
        {
            "response": "llamaindex answer",
            "metadata": {"prompt_tokens": 4, "completion_tokens": 6},
        }
    )

    result = llamaindex_query(
        query_engine,
        "What is trajectly?",
        model="llamaindex-query-v1",
        provider="llamaindex",
        context=context,
        top_k=2,
    )

    assert result["response"] == "llamaindex answer"
    assert result["usage"] == {"prompt_tokens": 4, "completion_tokens": 6}
    assert query_engine.calls[0] == ("What is trajectly?", {"top_k": 2})
    assert context.calls[0]["provider"] == "llamaindex"
    assert context.calls[0]["model"] == "llamaindex-query-v1"


def test_llamaindex_adapter_from_object_response() -> None:
    context = FakeContext()
    query_engine = FakeQueryEngine(
        LlamaIndexResponse(response="object answer", prompt_tokens=3, completion_tokens=5)
    )

    result = llamaindex_query(query_engine, "prompt", context=context)

    assert result["response"] == "object answer"
    assert result["usage"] == {"completion_tokens": 5, "prompt_tokens": 3}


def test_llamaindex_adapter_validates_query_method() -> None:
    with pytest.raises(ValueError, match="query"):
        llamaindex_query(object(), "prompt")


def test_crewai_adapter_with_execute_method_and_mapping_result() -> None:
    context = FakeContext()
    task = FakeCrewTaskExecute(
        {
            "output": "crew output",
            "usage": {"total_tokens": 9},
        }
    )

    result = crewai_run_task(
        task,
        inputs={"topic": "ci reliability"},
        model="crew-task-v1",
        provider="crewai",
        context=context,
        temperature=0,
    )

    assert result["response"] == "crew output"
    assert result["usage"] == {"total_tokens": 9}
    assert task.calls[0] == {"topic": "ci reliability", "temperature": 0}
    assert context.calls[0]["provider"] == "crewai"
    assert context.calls[0]["model"] == "crew-task-v1"


def test_crewai_adapter_with_run_method_and_object_result() -> None:
    context = FakeContext()
    task = FakeCrewTaskRun(CrewTaskResponse(output="run output", total_tokens=12))

    result = crewai_run_task(task, inputs={"goal": "summarize"}, context=context)

    assert result["response"] == "run output"
    assert result["usage"] == {"total_tokens": 12}
    assert task.calls[0] == {"goal": "summarize"}


def test_crewai_adapter_validates_execute_or_run() -> None:
    with pytest.raises(ValueError, match="execute"):
        crewai_run_task(object())


def test_autogen_adapter_with_mapping_result() -> None:
    context = FakeContext()
    runner = FakeAutoGenRunner(
        {
            "response": "autogen reply",
            "usage": {"total_tokens": 14},
        }
    )
    messages = [{"role": "user", "content": "hello"}]

    result = autogen_chat_run(
        runner,
        messages,
        model="autogen-model",
        provider="autogen",
        context=context,
        temperature=0,
    )

    assert result["response"] == "autogen reply"
    assert result["usage"] == {"total_tokens": 14}
    assert runner.calls[0] == (messages, {"temperature": 0})
    assert context.calls[0]["provider"] == "autogen"
    assert context.calls[0]["model"] == "autogen-model"


def test_autogen_adapter_with_object_result() -> None:
    context = FakeContext()
    runner = FakeAutoGenRunner(AutoGenResult(content="object reply", total_tokens=10))

    result = autogen_chat_run(runner, [{"role": "user", "content": "question"}], context=context)

    assert result["response"] == "object reply"
    assert result["usage"] == {"total_tokens": 10}


def test_autogen_adapter_validates_runner_shape() -> None:
    with pytest.raises(ValueError, match="run"):
        autogen_chat_run(object(), [])


def test_dspy_adapter_with_callable_program() -> None:
    context = FakeContext()
    program = FakeDSPYCallableProgram(
        {
            "answer": "dspy answer",
            "usage": {"total_tokens": 8},
        }
    )

    result = dspy_call(
        program,
        "What is trajectly?",
        model="dspy-program-v1",
        provider="dspy",
        context=context,
        max_depth=2,
    )

    assert result["response"] == "dspy answer"
    assert result["usage"] == {"total_tokens": 8}
    assert program.calls[0] == ("What is trajectly?", {"max_depth": 2})
    assert context.calls[0]["provider"] == "dspy"
    assert context.calls[0]["model"] == "dspy-program-v1"


def test_dspy_adapter_with_forward_program_object_result() -> None:
    context = FakeContext()
    program = FakeDSPYForwardProgram(DSPYResult(answer="forward answer", total_tokens=11))

    result = dspy_call(program, {"question": "hi"}, context=context)

    assert result["response"] == "forward answer"
    assert result["usage"] == {"total_tokens": 11}
    assert program.calls[0] == ({"question": "hi"}, {})


def test_dspy_adapter_validates_program_shape() -> None:
    with pytest.raises(ValueError, match="forward"):
        dspy_call(object(), "prompt")
