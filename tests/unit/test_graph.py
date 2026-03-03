"""Unit tests for sdk graph execution."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from trajectly.sdk.graph import App, GraphError, scan_module


class FakeGraphContext:
    def __init__(self) -> None:
        self.tool_calls: list[dict[str, Any]] = []
        self.llm_calls: list[dict[str, Any]] = []
        self.agent_steps: list[dict[str, Any]] = []

    def invoke_tool(self, name: str, fn: Any, args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any:
        self.tool_calls.append({"name": name, "args": args, "kwargs": kwargs})
        return fn(*args, **kwargs)

    def invoke_llm(
        self,
        provider: str,
        model: str,
        fn: Any,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> Any:
        self.llm_calls.append({"provider": provider, "model": model, "args": args, "kwargs": kwargs})
        return fn(*args, **kwargs)

    def agent_step(self, name: str, details: dict[str, Any] | None = None) -> None:
        self.agent_steps.append({"name": name, "details": details or {}})


def test_graph_builds_with_stable_topological_order() -> None:
    app = App(name="topology")

    @app.node("a", type="input")
    def a(seed: int) -> int:
        return seed

    @app.node("b", type="input")
    def b(extra: int) -> int:
        return extra

    @app.node("c", depends_on=["a", "b"])
    def c(left: int, right: int) -> int:
        return left + right

    spec = app.graph()

    assert spec.topo_order == ("a", "b", "c")
    assert spec.input_keys == ("extra", "seed")


def test_graph_cycle_detection_raises_graph_error() -> None:
    app = App()

    @app.node("a", depends_on=["b"])
    def a(value: int) -> int:
        return value

    @app.node("b", depends_on=["a"])
    def b(value: int) -> int:
        return value

    with pytest.raises(GraphError, match="Cycle detected"):
        app.graph()


def test_graph_missing_dependency_raises_graph_error() -> None:
    app = App()

    @app.node("a", depends_on=["b"])
    def a(value: int) -> int:
        return value

    with pytest.raises(GraphError, match="missing node"):
        app.graph()


def test_dependency_resolution_for_list_and_dict_forms() -> None:
    app = App()

    @app.node("search")
    def search(query: str) -> str:
        return query

    @app.node("summarize", depends_on=["search"])
    def summarize(search_payload: str, tone: str) -> str:
        return f"{tone}:{search_payload}"

    @app.node("merge", depends_on={"left": "search", "right": "summarize"})
    def merge(left: str, right: str) -> str:
        return f"{left}|{right}"

    spec = app.graph()
    assert spec.nodes["summarize"].input_mapping == {"search_payload": "search"}
    assert spec.nodes["merge"].input_mapping == {"left": "search", "right": "summarize"}


def test_dependency_resolution_rejects_invalid_mappings() -> None:
    app = App()

    with pytest.raises(GraphError, match="maps unknown parameter"):

        @app.node("bad", depends_on={"missing": "upstream"})
        def bad(value: int) -> int:
            return value

    with pytest.raises(GraphError, match="declares 2 dependencies but only 1 parameters"):

        @app.node("too_many", depends_on=["a", "b"])
        def too_many(one: str) -> str:
            return one


def test_run_executes_nodes_in_topological_order(monkeypatch: Any) -> None:
    context = FakeGraphContext()
    monkeypatch.setattr("trajectly.sdk.graph.get_context", lambda: context)
    call_order: list[str] = []
    app = App(name="execution")

    @app.node("input_node", type="input")
    def input_node(query: str) -> str:
        call_order.append("input_node")
        return query.strip()

    @app.node("middle", depends_on=["input_node"])
    def middle(input_node: str) -> str:
        call_order.append("middle")
        return input_node.upper()

    @app.node("final", depends_on=["middle"])
    def final(middle: str) -> dict[str, str]:
        call_order.append("final")
        return {"answer": middle}

    results = app.run({"query": " sky "})

    assert results == {
        "input_node": "sky",
        "middle": "SKY",
        "final": {"answer": "SKY"},
    }
    assert call_order == ["input_node", "middle", "final"]


def test_tool_nodes_route_through_sdk_context(monkeypatch: Any) -> None:
    context = FakeGraphContext()
    monkeypatch.setattr("trajectly.sdk.graph.get_context", lambda: context)
    app = App()

    @app.node("adder", type="tool")
    def adder(left: int, right: int) -> int:
        return left + right

    result = app.run({"left": 2, "right": 3})

    assert result["adder"] == 5
    assert context.tool_calls == [{"name": "adder", "args": (), "kwargs": {"left": 2, "right": 3}}]


def test_llm_nodes_route_through_sdk_context(monkeypatch: Any) -> None:
    context = FakeGraphContext()
    monkeypatch.setattr("trajectly.sdk.graph.get_context", lambda: context)
    app = App()

    @app.node("draft", type="llm")
    def draft(prompt: str) -> str:
        return prompt.upper()

    @app.node("polish", type="llm", depends_on=["draft"], provider="openai", model="gpt-4o")
    def polish(draft: str) -> str:
        return f"{draft}!"

    result = app.run({"prompt": "hello"})

    assert result["polish"] == "HELLO!"
    assert context.llm_calls == [
        {
            "provider": "openai",
            "model": "default",
            "args": (),
            "kwargs": {"prompt": "hello"},
        },
        {
            "provider": "openai",
            "model": "gpt-4o",
            "args": (),
            "kwargs": {"draft": "HELLO"},
        },
    ]


def test_transform_nodes_emit_agent_step_events(monkeypatch: Any) -> None:
    context = FakeGraphContext()
    monkeypatch.setattr("trajectly.sdk.graph.get_context", lambda: context)
    app = App(name="steps")

    @app.node("normalize", type="transform")
    def normalize(query: str) -> str:
        return query.lower()

    app.run({"query": "HELLO"})

    names = [entry["name"] for entry in context.agent_steps]
    assert names == ["graph_start", "transform:normalize", "graph_done"]
    assert context.agent_steps[1]["details"] == {"input_keys": ["query"]}


def test_generate_spec_returns_expected_contracts() -> None:
    app = App(name="research-agent")

    @app.node("prepare", type="input")
    def prepare(query: str) -> str:
        return query

    @app.node("search_engine", type="tool", depends_on=["prepare"])
    def search_engine(prepare: str) -> str:
        return prepare

    @app.node("summarizer", type="tool", depends_on=["search_engine"])
    def summarizer(search_engine: str) -> str:
        return search_engine

    @app.node("format_response", type="transform", depends_on=["summarizer"])
    def format_response(summarizer: str) -> dict[str, str]:
        return {"answer": summarizer}

    generated = app.generate_spec(
        command="python -m research_agent.main",
        contracts={"sequence": {"eventually": ["summarizer"]}},
    )

    assert generated["schema_version"] == "0.4"
    assert generated["name"] == "research-agent"
    assert generated["command"] == "python -m research_agent.main"
    assert generated["contracts"]["tool_call_allowlist"] == ["search_engine", "summarizer"]
    assert generated["contracts"]["tools"]["allow"] == ["search_engine", "summarizer"]
    assert generated["contracts"]["sequence"]["require"] == ["search_engine", "summarizer"]
    assert generated["contracts"]["sequence"]["eventually"] == ["summarizer"]


def test_scan_module_discovers_registered_nodes() -> None:
    app = App()

    @app.node("zeta")
    def zeta() -> int:
        return 1

    @app.node("alpha")
    def alpha() -> int:
        return 2

    module = SimpleNamespace(alpha_fn=alpha, zeta_fn=zeta, unrelated=42)
    discovered = scan_module(module)

    assert [node.id for node in discovered] == ["alpha", "zeta"]
