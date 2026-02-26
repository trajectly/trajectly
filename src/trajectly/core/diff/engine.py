from __future__ import annotations

from collections import Counter
from typing import Any

from trajectly.core.diff.lcs import lcs_pairs
from trajectly.core.diff.models import DiffResult, Finding
from trajectly.core.diff.structural import structural_diff
from trajectly.core.events import TraceEvent
from trajectly.core.specs import BudgetThresholds

_TRACKED_EVENT_TYPES = {"tool_called", "tool_returned", "llm_called", "llm_returned"}


def _signature(event: TraceEvent) -> str:
    payload = event.payload
    if event.event_type == "tool_called":
        return f"tool_called:{payload.get('tool_name', 'unknown')}"
    if event.event_type == "tool_returned":
        return f"tool_returned:{payload.get('tool_name', 'unknown')}"
    if event.event_type == "llm_called":
        provider = payload.get("provider", "unknown")
        model = payload.get("model", "unknown")
        return f"llm_called:{provider}:{model}"
    if event.event_type == "llm_returned":
        provider = payload.get("provider", "unknown")
        model = payload.get("model", "unknown")
        return f"llm_returned:{provider}:{model}"
    return f"other:{event.event_type}"


def _tracked(events: list[TraceEvent]) -> list[TraceEvent]:
    return [event for event in events if event.event_type in _TRACKED_EVENT_TYPES]


def _sum_tokens(events: list[TraceEvent]) -> int:
    total = 0
    for event in events:
        if event.event_type != "llm_returned":
            continue
        usage = event.payload.get("usage", {})
        if isinstance(usage, dict):
            tokens = usage.get("total_tokens", 0)
            if isinstance(tokens, int):
                total += tokens
    return total


def _duration_ms(events: list[TraceEvent]) -> int:
    finished = [event for event in events if event.event_type == "run_finished"]
    if not finished:
        return 0
    payload = finished[-1].payload
    value = payload.get("duration_ms", 0)
    return int(value) if isinstance(value, int | float | str) else 0


def _tool_calls(events: list[TraceEvent]) -> int:
    return sum(1 for event in events if event.event_type == "tool_called")


def _first_divergence(baseline_ops: list[TraceEvent], current_ops: list[TraceEvent]) -> dict[str, Any] | None:
    limit = max(len(baseline_ops), len(current_ops))
    for index in range(limit):
        baseline_event = baseline_ops[index] if index < len(baseline_ops) else None
        current_event = current_ops[index] if index < len(current_ops) else None

        baseline_signature = _signature(baseline_event) if baseline_event else None
        current_signature = _signature(current_event) if current_event else None

        if baseline_signature != current_signature:
            return {
                "kind": "sequence",
                "index": index,
                "baseline": baseline_signature,
                "current": current_signature,
            }

        if baseline_event is None or current_event is None:
            continue
        changes = structural_diff(baseline_event.payload, current_event.payload, path="$.payload")
        if changes:
            first_change = changes[0]
            return {
                "kind": "payload",
                "index": index,
                "signature": baseline_signature,
                "path": first_change.path,
                "baseline": first_change.baseline,
                "current": first_change.current,
            }
    return None


def compare_traces(
    baseline: list[TraceEvent],
    current: list[TraceEvent],
    budgets: BudgetThresholds | None = None,
) -> DiffResult:
    findings: list[Finding] = []
    baseline_ops = _tracked(baseline)
    current_ops = _tracked(current)

    base_signatures = [_signature(event) for event in baseline_ops]
    curr_signatures = [_signature(event) for event in current_ops]
    pairs = lcs_pairs(base_signatures, curr_signatures)

    matched_left = {left for left, _ in pairs}
    matched_right = {right for _, right in pairs}

    for idx, signature in enumerate(base_signatures):
        if idx not in matched_left:
            findings.append(
                Finding(
                    classification="sequence_mismatch",
                    message=f"Missing event from current trace: {signature} at index {idx}",
                    baseline=signature,
                    current=None,
                )
            )

    for idx, signature in enumerate(curr_signatures):
        if idx not in matched_right:
            findings.append(
                Finding(
                    classification="sequence_mismatch",
                    message=f"Unexpected event in current trace: {signature} at index {idx}",
                    baseline=None,
                    current=signature,
                )
            )

    for left_idx, right_idx in pairs:
        left_event = baseline_ops[left_idx]
        right_event = current_ops[right_idx]
        if _signature(left_event) != _signature(right_event):
            continue
        changes = structural_diff(left_event.payload, right_event.payload, path="$.payload")
        for change in changes:
            findings.append(
                Finding(
                    classification="structural_mismatch",
                    message=f"Payload mismatch at {change.path}",
                    path=change.path,
                    baseline=change.baseline,
                    current=change.current,
                )
            )

    budgets = budgets or BudgetThresholds()
    duration_baseline = _duration_ms(baseline)
    duration_current = _duration_ms(current)
    tool_calls_baseline = _tool_calls(baseline)
    tool_calls_current = _tool_calls(current)
    tokens_baseline = _sum_tokens(baseline)
    tokens_current = _sum_tokens(current)

    if budgets.max_latency_ms is not None and duration_current > budgets.max_latency_ms:
        findings.append(
            Finding(
                classification="budget_breach",
                message=(
                    "Latency budget exceeded "
                    f"(current={duration_current}ms limit={budgets.max_latency_ms}ms)"
                ),
                baseline=duration_baseline,
                current=duration_current,
            )
        )

    if budgets.max_tool_calls is not None and tool_calls_current > budgets.max_tool_calls:
        findings.append(
            Finding(
                classification="budget_breach",
                message=(
                    "Tool call budget exceeded "
                    f"(current={tool_calls_current} limit={budgets.max_tool_calls})"
                ),
                baseline=tool_calls_baseline,
                current=tool_calls_current,
            )
        )

    if budgets.max_tokens is not None and tokens_current > budgets.max_tokens:
        findings.append(
            Finding(
                classification="budget_breach",
                message=f"Token budget exceeded (current={tokens_current} limit={budgets.max_tokens})",
                baseline=tokens_baseline,
                current=tokens_current,
            )
        )

    classification_counts = Counter(finding.classification for finding in findings)
    summary: dict[str, Any] = {
        "regression": bool(findings),
        "finding_count": len(findings),
        "classifications": dict(classification_counts),
        "first_divergence": _first_divergence(baseline_ops, current_ops),
        "baseline": {
            "duration_ms": duration_baseline,
            "tool_calls": tool_calls_baseline,
            "tokens": tokens_baseline,
        },
        "current": {
            "duration_ms": duration_current,
            "tool_calls": tool_calls_current,
            "tokens": tokens_current,
        },
    }

    return DiffResult(summary=summary, findings=findings)
