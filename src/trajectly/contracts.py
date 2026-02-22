from __future__ import annotations

from typing import Any

from trajectly.diff.models import Finding
from trajectly.events import TraceEvent
from trajectly.specs import AgentContracts

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


def _tool_name_from_event(event: TraceEvent) -> str | None:
    if event.event_type != "tool_called":
        return None
    tool_name = event.payload.get("tool_name")
    if not isinstance(tool_name, str):
        return None
    return tool_name


def _operation_signature(event: TraceEvent) -> str | None:
    if event.event_type == "tool_called":
        tool_name = event.payload.get("tool_name")
        if isinstance(tool_name, str):
            return f"tool:{tool_name}"
        return None
    if event.event_type == "llm_called":
        provider = event.payload.get("provider")
        model = event.payload.get("model")
        if isinstance(provider, str) and isinstance(model, str):
            return f"llm:{provider}:{model}"
        return None
    if event.event_type == "agent_step":
        name = event.payload.get("name")
        if isinstance(name, str):
            return f"step:{name}"
    return None


def _looks_like_write_tool(tool_name: str) -> bool:
    normalized = tool_name.strip().lower()
    return any(token in normalized for token in _WRITE_TOOL_HINTS)


def _find_required_sequence_missing(requirements: list[str], operations: list[str]) -> list[str]:
    if not requirements:
        return []
    missing: list[str] = []
    cursor = 0
    for required in requirements:
        try:
            index = operations.index(required, cursor)
        except ValueError:
            missing.append(required)
            continue
        cursor = index + 1
    return missing


def evaluate_contracts(current: list[TraceEvent], contracts: AgentContracts) -> list[Finding]:
    findings: list[Finding] = []

    tool_names = [name for event in current if (name := _tool_name_from_event(event))]
    operations = [signature for event in current if (signature := _operation_signature(event))]

    deny_tools = set(contracts.tools.deny)
    allow_tools = set(contracts.tools.allow)

    for position, tool_name in enumerate(tool_names):
        if tool_name in deny_tools:
            findings.append(
                Finding(
                    classification="contract_tool_denied",
                    message=f"Contract denied tool call: {tool_name}",
                    path=f"$.tool_calls[{position}]",
                    current=tool_name,
                )
            )

        if allow_tools and tool_name not in allow_tools:
            findings.append(
                Finding(
                    classification="contract_tool_not_allowed",
                    message=f"Tool call not in contracts.tools.allow: {tool_name}",
                    path=f"$.tool_calls[{position}]",
                    current=tool_name,
                )
            )

        if contracts.side_effects.deny_write_tools and _looks_like_write_tool(tool_name):
            findings.append(
                Finding(
                    classification="contract_side_effect_write_tool_denied",
                    message=f"Write-like tool blocked by contracts.side_effects.deny_write_tools: {tool_name}",
                    path=f"$.tool_calls[{position}]",
                    current=tool_name,
                )
            )

    max_calls_total = contracts.tools.max_calls_total
    if max_calls_total is not None and len(tool_names) > max_calls_total:
        findings.append(
            Finding(
                classification="contract_max_calls_total_exceeded",
                message=(
                    "contracts.tools.max_calls_total exceeded "
                    f"(limit={max_calls_total}, actual={len(tool_names)})"
                ),
                path="$.tool_calls",
                baseline=max_calls_total,
                current=len(tool_names),
            )
        )

    missing_required = _find_required_sequence_missing(contracts.sequence.require, operations)
    for required in missing_required:
        findings.append(
            Finding(
                classification="contract_sequence_required_missing",
                message=f"Required sequence operation missing: {required}",
                path="$.operations",
                current=operations,
            )
        )

    forbid_set = set(contracts.sequence.forbid)
    if forbid_set:
        for position, operation in enumerate(operations):
            if operation in forbid_set:
                findings.append(
                    Finding(
                        classification="contract_sequence_forbidden_seen",
                        message=f"Forbidden sequence operation observed: {operation}",
                        path=f"$.operations[{position}]",
                        current=operation,
                    )
                )

    network_allowlist = contracts.network.allowlist
    if network_allowlist:
        run_finished = [event for event in current if event.event_type == "run_finished"]
        if run_finished:
            payload: dict[str, Any] = run_finished[-1].payload
            stderr_tail = payload.get("stderr_tail")
            if isinstance(stderr_tail, str) and "Trajectly replay mode blocks network access" in stderr_tail:
                findings.append(
                    Finding(
                        classification="contract_network_allowlist_blocked",
                        message=(
                            "Network call was blocked during replay and did not match contracts.network.allowlist"
                        ),
                        path="$.run_finished.stderr_tail",
                        current=stderr_tail,
                    )
                )

    return findings
