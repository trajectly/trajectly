"""Declarative graph execution utilities built on top of the SDK context."""

from __future__ import annotations

import heapq
import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal, cast

from trajectly.sdk.context import get_context

NodeType = Literal["tool", "llm", "input", "transform"]


class GraphError(Exception):
    """Raised when a graph definition is invalid."""


@dataclass(slots=True, frozen=True)
class NodeSpec:
    """A registered graph node."""

    id: str
    fn: Callable[..., Any]
    node_type: NodeType
    depends_on: tuple[str, ...]
    input_mapping: dict[str, str]
    provider: str | None
    model: str | None


@dataclass(slots=True)
class GraphSpec:
    """A validated graph ready for execution."""

    nodes: dict[str, NodeSpec]
    topo_order: tuple[str, ...]
    input_keys: tuple[str, ...]


def _as_node_type(raw: str) -> NodeType:
    normalized = raw.strip().lower()
    allowed = {"tool", "llm", "input", "transform"}
    if normalized not in allowed:
        raise GraphError(f"Unsupported node type: {raw!r}. Expected one of {sorted(allowed)}")
    return cast(NodeType, normalized)


def _dedupe(values: list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return tuple(ordered)


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overlay.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            left = cast(dict[str, Any], merged[key])
            right = cast(dict[str, Any], value)
            merged[key] = _deep_merge(left, right)
        else:
            merged[key] = value
    return merged


def _resolve_dependencies(
    node_id: str,
    parameter_names: tuple[str, ...],
    depends_on: list[str] | dict[str, str] | None,
) -> tuple[tuple[str, ...], dict[str, str]]:
    if depends_on is None:
        return (), {}

    if isinstance(depends_on, list):
        for dep in depends_on:
            if not isinstance(dep, str) or not dep:
                raise GraphError(f"Node {node_id!r} has non-string dependency entry: {dep!r}")
        if len(depends_on) > len(parameter_names):
            raise GraphError(
                f"Node {node_id!r} declares {len(depends_on)} dependencies but only {len(parameter_names)} parameters"
            )
        mapping = {parameter_names[index]: dep for index, dep in enumerate(depends_on)}
        return _dedupe(depends_on), mapping

    if isinstance(depends_on, dict):
        explicit_mapping: dict[str, str] = {}
        deps: list[str] = []
        for parameter_name, source_name in depends_on.items():
            if parameter_name not in parameter_names:
                raise GraphError(f"Node {node_id!r} maps unknown parameter {parameter_name!r}")
            if not isinstance(source_name, str) or not source_name:
                raise GraphError(f"Node {node_id!r} has non-string mapping source: {source_name!r}")
            explicit_mapping[str(parameter_name)] = source_name
            deps.append(source_name)
        return _dedupe(deps), explicit_mapping

    raise GraphError(
        f"Node {node_id!r} depends_on must be None, list[str], or dict[str, str]; got {type(depends_on).__name__}"
    )


def _resolve_kwargs(
    node: NodeSpec,
    input_data: dict[str, Any],
    results: dict[str, Any],
) -> dict[str, Any]:
    signature = inspect.signature(node.fn)
    kwargs: dict[str, Any] = {}
    for parameter_name in signature.parameters:
        if parameter_name in node.input_mapping:
            source_name = node.input_mapping[parameter_name]
            if source_name in results:
                kwargs[parameter_name] = results[source_name]
            elif source_name in input_data:
                kwargs[parameter_name] = input_data[source_name]
            continue

        if parameter_name in input_data:
            kwargs[parameter_name] = input_data[parameter_name]
            continue

        if parameter_name in results:
            kwargs[parameter_name] = results[parameter_name]
            continue

    return kwargs


class App:
    """Declarative DAG application for deterministic agent execution."""

    def __init__(self, name: str = "agent") -> None:
        self._name = name
        self._nodes: dict[str, NodeSpec] = {}
        self._graph_cache: GraphSpec | None = None

    def node(
        self,
        id: str,
        type: str = "transform",
        depends_on: list[str] | dict[str, str] | None = None,
        provider: str | None = None,
        model: str | None = None,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Register a function as a graph node."""

        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            if not id:
                raise GraphError("Node id must be a non-empty string")
            if id in self._nodes:
                raise GraphError(f"Duplicate node id: {id!r}")

            node_type = _as_node_type(type)
            parameter_names = tuple(inspect.signature(fn).parameters.keys())
            declared_dependencies, input_mapping = _resolve_dependencies(id, parameter_names, depends_on)
            node_spec = NodeSpec(
                id=id,
                fn=fn,
                node_type=node_type,
                depends_on=declared_dependencies,
                input_mapping=input_mapping,
                provider=provider,
                model=model,
            )
            self._nodes[id] = node_spec
            fn._trajectly_node = node_spec  # type: ignore[attr-defined]
            self._graph_cache = None
            return fn

        return decorator

    def graph(self) -> GraphSpec:
        """Build and cache a validated graph specification."""
        if self._graph_cache is not None:
            return self._graph_cache

        for node in self._nodes.values():
            for dependency in node.depends_on:
                if dependency not in self._nodes:
                    raise GraphError(f"Node {node.id!r} depends on missing node {dependency!r}")

        indegree: dict[str, int] = {node_id: 0 for node_id in self._nodes}
        adjacency: dict[str, set[str]] = {node_id: set() for node_id in self._nodes}
        for node in self._nodes.values():
            for dependency in node.depends_on:
                if node.id in adjacency[dependency]:
                    continue
                adjacency[dependency].add(node.id)
                indegree[node.id] += 1

        heap: list[str] = [node_id for node_id, degree in indegree.items() if degree == 0]
        heapq.heapify(heap)

        topo_order: list[str] = []
        while heap:
            current = heapq.heappop(heap)
            topo_order.append(current)
            for child in sorted(adjacency[current]):
                indegree[child] -= 1
                if indegree[child] == 0:
                    heapq.heappush(heap, child)

        if len(topo_order) != len(self._nodes):
            unresolved = sorted(node_id for node_id, degree in indegree.items() if degree > 0)
            raise GraphError(f"Cycle detected involving nodes: {unresolved}")

        input_keys: set[str] = set()
        for node_id in topo_order:
            node = self._nodes[node_id]
            if node.depends_on:
                continue
            for parameter_name in inspect.signature(node.fn).parameters:
                input_keys.add(parameter_name)

        spec = GraphSpec(
            nodes=dict(self._nodes),
            topo_order=tuple(topo_order),
            input_keys=tuple(sorted(input_keys)),
        )
        self._graph_cache = spec
        return spec

    def run(self, input_data: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute the graph and return node outputs keyed by node id."""
        graph_spec = self.graph()
        ctx = get_context()
        payload = input_data or {}
        results: dict[str, Any] = {}

        ctx.agent_step("graph_start", {"name": self._name, "nodes": list(graph_spec.topo_order)})
        for node_id in graph_spec.topo_order:
            node = graph_spec.nodes[node_id]
            kwargs = _resolve_kwargs(node, payload, results)
            if node.node_type == "tool":
                result = ctx.invoke_tool(node.id, node.fn, (), kwargs)
            elif node.node_type == "llm":
                result = ctx.invoke_llm(node.provider or "openai", node.model or "default", node.fn, (), kwargs)
            elif node.node_type == "input":
                result = node.fn(**kwargs)
            else:
                ctx.agent_step(f"transform:{node.id}", {"input_keys": list(kwargs.keys())})
                result = node.fn(**kwargs)
            results[node.id] = result

        ctx.agent_step("graph_done", {"outputs": list(results.keys())})
        return results

    def generate_spec(self, schema_version: str = "0.4", **overrides: Any) -> dict[str, Any]:
        """Generate a `.agent.yaml` compatible spec mapping."""
        graph_spec = self.graph()
        ordered_tools = [
            node_id
            for node_id in graph_spec.topo_order
            if graph_spec.nodes[node_id].node_type == "tool"
        ]

        base_spec: dict[str, Any] = {
            "schema_version": schema_version,
            "name": self._name,
            "command": "python -m your_agent_module",
            "contracts": {
                "tool_call_allowlist": ordered_tools,
                "tools": {"allow": ordered_tools},
                "sequence": {"require": ordered_tools},
            },
        }
        if not overrides:
            return base_spec
        return _deep_merge(base_spec, overrides)


def scan_module(module: Any) -> list[NodeSpec]:
    """Discover registered node specs from a module object."""
    discovered: list[NodeSpec] = []
    for name in dir(module):
        candidate = getattr(module, name, None)
        spec = getattr(candidate, "_trajectly_node", None)
        if isinstance(spec, NodeSpec):
            discovered.append(spec)
    return sorted(discovered, key=lambda node_spec: node_spec.id)


__all__ = ["App", "GraphError", "GraphSpec", "NodeSpec", "NodeType", "scan_module"]
