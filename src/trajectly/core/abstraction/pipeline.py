"""Deterministic abstraction pipeline (Definition 2 in trt_theory.md).

Implements ``build_abstract_trace``, which maps a concrete event trace to an
abstract representation consisting of a token stream and a predicate bag.

**Determinism (Theorem 2 precondition):** The pipeline iterates events by
index, applies a fixed token-mapping function per event type, and accumulates
predicates in a single pass.  Output keys are sorted (``tool_calls_by_name``,
``domains``) so the abstract trace is identical for identical inputs regardless
of Python dict insertion order.

**Abstraction homomorphism:** ``alpha(T, c) = (Tokens, Predicates)`` where
each token preserves the event index and causal kind, and predicates aggregate
over the full trace.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from trajectly.core.abstraction.predicates import (
    contains_email,
    contains_phone,
    extract_domains,
    extract_numeric_values,
)
from trajectly.core.events import TraceEvent

TokenKind = Literal[
    "CALL",
    "RESULT",
    "LLM_REQUEST",
    "LLM_RESPONSE",
    "MESSAGE",
    "OBSERVATION",
    "ERROR",
]


@dataclass(slots=True)
class Token:
    event_index: int
    kind: TokenKind
    name: str
    payload: dict[str, Any]


@dataclass(slots=True)
class AbstractionConfig:
    ignore_call_tools: list[str] = field(default_factory=list)
    enable_pii_detection: bool = True
    enable_domain_extraction: bool = True
    enable_numeric_extraction: bool = True


@dataclass(slots=True)
class AbstractTrace:
    tokens: list[Token]
    predicates: dict[str, Any]


def _token_from_event(event: TraceEvent, event_index: int, ignore_call_tools: set[str]) -> Token | None:
    # Event-to-token mapping is intentionally conservative: only stable,
    # contract-relevant event types feed TRT abstraction.
    payload = dict(event.payload)
    if event.event_type == "tool_called":
        tool_name = str(payload.get("tool_name", "unknown"))
        if tool_name in ignore_call_tools:
            return None
        return Token(event_index=event_index, kind="CALL", name=tool_name, payload=payload)
    if event.event_type == "tool_returned":
        tool_name = str(payload.get("tool_name", "unknown"))
        return Token(event_index=event_index, kind="RESULT", name=tool_name, payload=payload)
    if event.event_type == "llm_called":
        provider = str(payload.get("provider", "unknown"))
        model = str(payload.get("model", "unknown"))
        return Token(event_index=event_index, kind="LLM_REQUEST", name=f"{provider}:{model}", payload=payload)
    if event.event_type == "llm_returned":
        provider = str(payload.get("provider", "unknown"))
        model = str(payload.get("model", "unknown"))
        return Token(event_index=event_index, kind="LLM_RESPONSE", name=f"{provider}:{model}", payload=payload)
    if event.event_type == "agent_step":
        name = str(payload.get("name", "step"))
        return Token(event_index=event_index, kind="MESSAGE", name=name, payload=payload)
    if event.event_type == "run_finished":
        return Token(event_index=event_index, kind="OBSERVATION", name="run_finished", payload=payload)
    return None


def build_abstract_trace(
    events: list[TraceEvent],
    *,
    config: AbstractionConfig | None = None,
) -> AbstractTrace:
    cfg = config or AbstractionConfig()
    ignore_call_tools = set(cfg.ignore_call_tools)
    tokens: list[Token] = []

    for index, event in enumerate(events):
        token = _token_from_event(event, index, ignore_call_tools)
        if token is not None:
            tokens.append(token)

    # Predicate bag shape is fixed for deterministic report payloads.
    predicates: dict[str, Any] = {
        "tool_calls_total": sum(1 for token in tokens if token.kind == "CALL"),
        "tool_calls_by_name": {},
        "domains": [],
        "pii": {"email": False, "phone": False},
        "max_numeric_value": None,
        "refund_count": 0,
    }

    tool_counts: dict[str, int] = {}
    domains: set[str] = set()
    numeric_values: list[float] = []
    has_email = False
    has_phone = False
    refund_count = 0

    for token in tokens:
        # Predicates are derived in a single deterministic pass so witness-level
        # checks can be reproduced exactly in CI replay.
        if token.kind == "CALL":
            tool_counts[token.name] = tool_counts.get(token.name, 0) + 1
            if "refund" in token.name.lower():
                refund_count += 1

        if cfg.enable_domain_extraction:
            domains.update(extract_domains(token.payload))
        if cfg.enable_numeric_extraction:
            numeric_values.extend(extract_numeric_values(token.payload))
        if cfg.enable_pii_detection:
            has_email = has_email or contains_email(token.payload)
            has_phone = has_phone or contains_phone(token.payload)

    predicates["tool_calls_by_name"] = dict(sorted(tool_counts.items()))
    predicates["refund_count"] = refund_count
    predicates["domains"] = sorted(domains)
    predicates["pii"] = {"email": has_email, "phone": has_phone}
    predicates["max_numeric_value"] = max(numeric_values) if numeric_values else None

    return AbstractTrace(tokens=tokens, predicates=predicates)


__all__ = [
    "AbstractTrace",
    "AbstractionConfig",
    "Token",
    "build_abstract_trace",
]
