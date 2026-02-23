from __future__ import annotations

import re
from collections import Counter
from typing import Any
from urllib.parse import urlparse

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


def _safe_find_operation_index(operations: list[str], target: str) -> int | None:
    try:
        return operations.index(target)
    except ValueError:
        return None


def _extract_tool_input(event: TraceEvent) -> dict[str, Any]:
    payload = event.payload
    input_payload = payload.get("input")
    if isinstance(input_payload, dict):
        return input_payload
    return {}


def _extract_tool_kwargs(event: TraceEvent) -> dict[str, Any]:
    input_payload = _extract_tool_input(event)
    kwargs = input_payload.get("kwargs")
    if isinstance(kwargs, dict):
        return kwargs
    return {}


def _extract_tool_args(event: TraceEvent) -> list[Any]:
    input_payload = _extract_tool_input(event)
    args = input_payload.get("args")
    if isinstance(args, list):
        return args
    return []


def _coerce_number(value: Any) -> float | None:
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _contains_pii(value: Any) -> bool:
    if isinstance(value, str):
        email_match = re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", value)
        phone_match = re.search(r"\b(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}\b", value)
        return email_match is not None or phone_match is not None
    if isinstance(value, dict):
        return any(_contains_pii(v) for v in value.values())
    if isinstance(value, list):
        return any(_contains_pii(v) for v in value)
    return False


def _contains_regex(value: Any, pattern: str) -> bool:
    if isinstance(value, str):
        return re.search(pattern, value) is not None
    if isinstance(value, dict):
        return any(_contains_regex(v, pattern) for v in value.values())
    if isinstance(value, list):
        return any(_contains_regex(v, pattern) for v in value)
    return False


def _extract_url_from_event(event: TraceEvent) -> str | None:
    kwargs = _extract_tool_kwargs(event)
    for key in ("url", "uri", "endpoint"):
        value = kwargs.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    args = _extract_tool_args(event)
    if args:
        first = args[0]
        if isinstance(first, str) and first.strip():
            return first.strip()
    return None


def _extract_domain(value: str) -> str | None:
    parsed = urlparse(value)
    host = parsed.hostname
    if host:
        return host.lower()
    if "://" not in value and "/" not in value and "." in value:
        return value.lower()
    return None


def _validate_tool_schema(tool_name: str, event: TraceEvent, schema: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    if not schema:
        return findings

    required_keys_raw = schema.get("required_keys")
    if isinstance(required_keys_raw, list):
        required_keys = [str(key) for key in required_keys_raw]
    else:
        required_keys = []

    fields_raw = schema.get("fields")
    fields = fields_raw if isinstance(fields_raw, dict) else {}
    kwargs = _extract_tool_kwargs(event)
    args = _extract_tool_args(event)

    merged_values: dict[str, Any] = dict(kwargs)
    if args:
        for index, value in enumerate(args):
            merged_values[f"arg_{index}"] = value

    for required_key in required_keys:
        if required_key not in merged_values:
            findings.append(
                Finding(
                    classification="contract_args_required_key_missing",
                    message=f"Required argument missing for tool {tool_name}: {required_key}",
                    path=f"$.tool_call.{tool_name}.required_keys",
                    current=required_key,
                )
            )

    for field_name, field_rules_raw in fields.items():
        if not isinstance(field_rules_raw, dict):
            continue
        field_rules = field_rules_raw
        if field_name not in merged_values:
            continue
        value = merged_values[field_name]

        expected_type = field_rules.get("type")
        if expected_type == "number":
            numeric = _coerce_number(value)
            if numeric is None:
                findings.append(
                    Finding(
                        classification="contract_args_type_violation",
                        message=f"Field {tool_name}.{field_name} must be numeric",
                        path=f"$.tool_call.{tool_name}.fields.{field_name}",
                        current=value,
                    )
                )
                continue
            max_value = field_rules.get("max")
            if isinstance(max_value, int | float) and numeric > float(max_value):
                findings.append(
                    Finding(
                        classification="contract_args_max_violation",
                        message=f"Field {tool_name}.{field_name} exceeds max ({numeric} > {max_value})",
                        path=f"$.tool_call.{tool_name}.fields.{field_name}",
                        baseline=max_value,
                        current=numeric,
                    )
                )
            min_value = field_rules.get("min")
            if isinstance(min_value, int | float) and numeric < float(min_value):
                findings.append(
                    Finding(
                        classification="contract_args_min_violation",
                        message=f"Field {tool_name}.{field_name} below min ({numeric} < {min_value})",
                        path=f"$.tool_call.{tool_name}.fields.{field_name}",
                        baseline=min_value,
                        current=numeric,
                    )
                )
        if expected_type == "string":
            text = str(value)
            enum_raw = field_rules.get("enum")
            if isinstance(enum_raw, list):
                allowed = [str(item) for item in enum_raw]
                if text not in allowed:
                    findings.append(
                        Finding(
                            classification="contract_args_enum_violation",
                            message=f"Field {tool_name}.{field_name} not in enum",
                            path=f"$.tool_call.{tool_name}.fields.{field_name}",
                            baseline=allowed,
                            current=text,
                        )
                    )
            regex_raw = field_rules.get("regex")
            if isinstance(regex_raw, str):
                if re.search(regex_raw, text) is None:
                    findings.append(
                        Finding(
                            classification="contract_args_regex_violation",
                            message=f"Field {tool_name}.{field_name} does not match regex",
                            path=f"$.tool_call.{tool_name}.fields.{field_name}",
                            baseline=regex_raw,
                            current=text,
                        )
                    )
    return findings


def evaluate_contracts(current: list[TraceEvent], contracts: AgentContracts) -> list[Finding]:
    findings: list[Finding] = []

    tool_events = [event for event in current if event.event_type == "tool_called"]
    tool_names = [name for event in tool_events if (name := _tool_name_from_event(event))]
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

    if contracts.tools.max_calls_per_tool:
        counts = Counter(tool_names)
        for tool_name, limit in contracts.tools.max_calls_per_tool.items():
            actual = counts.get(tool_name, 0)
            if actual > limit:
                findings.append(
                    Finding(
                        classification="contract_max_calls_per_tool_exceeded",
                        message=(
                            "contracts.tools.max_calls_per_tool exceeded "
                            f"for {tool_name} (limit={limit}, actual={actual})"
                        ),
                        path=f"$.tool_calls.{tool_name}",
                        baseline=limit,
                        current=actual,
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

    for required_before, required_after in contracts.sequence.require_before:
        before_idx = _safe_find_operation_index(operations, required_before)
        after_idx = _safe_find_operation_index(operations, required_after)
        if before_idx is None or after_idx is None or before_idx > after_idx:
            findings.append(
                Finding(
                    classification="contract_sequence_require_before_violated",
                    message=f"Required order violated: {required_before} before {required_after}",
                    path="$.operations",
                    current=operations,
                )
            )

    for required in contracts.sequence.eventually:
        if required not in operations:
            findings.append(
                Finding(
                    classification="contract_sequence_eventually_missing",
                    message=f"Expected operation missing: {required}",
                    path="$.operations",
                    current=operations,
                )
            )

    never_set = set(contracts.sequence.never)
    if never_set:
        for position, operation in enumerate(operations):
            if operation in never_set:
                findings.append(
                    Finding(
                        classification="contract_sequence_never_seen",
                        message=f"Operation forbidden by `never`: {operation}",
                        path=f"$.operations[{position}]",
                        current=operation,
                    )
                )

    for target in contracts.sequence.at_most_once:
        count = operations.count(target)
        if count > 1:
            findings.append(
                Finding(
                    classification="contract_sequence_at_most_once_exceeded",
                    message=f"Operation appears more than once: {target}",
                    path="$.operations",
                    baseline=1,
                    current=count,
                )
            )

    schema_map = contracts.tools.schema
    for event in tool_events:
        event_tool_name = _tool_name_from_event(event)
        if event_tool_name is None:
            continue
        tool_schema_raw = schema_map.get(event_tool_name)
        if not isinstance(tool_schema_raw, dict):
            continue
        findings.extend(_validate_tool_schema(event_tool_name, event, tool_schema_raw))

    network_allowlist = contracts.network.allowlist or contracts.network.allow_domains
    network_default = (contracts.network.default or "deny").strip().lower()
    network_events = [
        (position, event)
        for position, event in enumerate(tool_events)
        if _tool_name_from_event(event) in {"http_request", "web_search"}
    ]
    if network_events:
        allow_domains = {domain.strip().lower() for domain in network_allowlist if domain.strip()}
        for position, event in network_events:
            tool_name = _tool_name_from_event(event) or "unknown"
            url = _extract_url_from_event(event)
            domain = _extract_domain(url) if isinstance(url, str) else None
            if network_default == "deny":
                if not domain:
                    findings.append(
                        Finding(
                            classification="contract_network_domain_denied",
                            message=f"Outbound network call blocked (no domain): {tool_name}",
                            path=f"$.tool_calls[{position}]",
                            baseline=sorted(allow_domains),
                            current=url,
                        )
                    )
                    continue
                if domain not in allow_domains:
                    findings.append(
                        Finding(
                            classification="contract_network_domain_denied",
                            message=f"Network domain denied by contracts.network.allow_domains: {domain}",
                            path=f"$.tool_calls[{position}]",
                            baseline=sorted(allow_domains),
                            current=domain,
                        )
                    )
                    continue
            elif allow_domains and domain and domain not in allow_domains:
                findings.append(
                    Finding(
                        classification="contract_network_domain_denied",
                        message=f"Network domain not in allowlist: {domain}",
                        path=f"$.tool_calls[{position}]",
                        baseline=sorted(allow_domains),
                        current=domain,
                    )
                )

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

    outbound_kinds = set(contracts.data_leak.outbound_kinds)
    event_kind_map = {
        "TOOL_CALL": "tool_called",
        "LLM_REQUEST": "llm_called",
    }
    eligible_events: list[TraceEvent] = []
    for kind in outbound_kinds:
        event_type = event_kind_map.get(kind)
        if event_type is None:
            continue
        eligible_events.extend(event for event in current if event.event_type == event_type)

    if contracts.data_leak.deny_pii_outbound:
        for event in eligible_events:
            if _contains_pii(event.payload):
                findings.append(
                    Finding(
                        classification="contract_data_leak_pii_outbound",
                        message=f"PII detected in outbound payload for {event.event_type}",
                        path="$.payload",
                        current=event.payload,
                    )
                )
                break

    for pattern in contracts.data_leak.secret_patterns:
        for event in eligible_events:
            if _contains_regex(event.payload, pattern):
                findings.append(
                    Finding(
                        classification="contract_data_leak_secret_pattern",
                        message=f"Secret pattern detected in outbound payload for {event.event_type}",
                        path="$.payload",
                        baseline=pattern,
                        current=event.payload,
                    )
                )
                break
        else:
            continue
        break

    return findings
