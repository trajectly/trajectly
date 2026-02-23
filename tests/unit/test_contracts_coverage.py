"""Tests for uncovered contract paths: require_before, eventually, never,
at_most_once, network default=allow, data-leak outbound_kinds filtering,
tool schema edge cases."""

from __future__ import annotations

from trajectly.contracts import evaluate_contracts
from trajectly.events import make_event
from trajectly.specs import (
    AgentContracts,
    DataLeakContracts,
    NetworkContracts,
    SequenceContracts,
    ToolContracts,
)


def _tool_event(tool_name: str, seq: int, **kwargs: object) -> object:
    return make_event(
        event_type="tool_called",
        seq=seq,
        run_id="r1",
        rel_ms=seq,
        payload={"tool_name": tool_name, "input": {"args": [], "kwargs": dict(kwargs)}},
    )


def _step_event(name: str, seq: int) -> object:
    return make_event(
        event_type="agent_step",
        seq=seq,
        run_id="r1",
        rel_ms=seq,
        payload={"name": name, "details": {}},
    )


# ---------------------------------------------------------------------------
# Sequence: require_before
# ---------------------------------------------------------------------------

def test_require_before_order_satisfied() -> None:
    events = [
        _tool_event("lookup", 1),
        _tool_event("send_email", 2),
    ]
    contracts = AgentContracts(
        sequence=SequenceContracts(require_before=[("tool:lookup", "tool:send_email")])
    )
    findings = evaluate_contracts(current=events, contracts=contracts)
    codes = [f.classification for f in findings]
    assert "contract_sequence_require_before_violated" not in codes


def test_require_before_order_violated() -> None:
    events = [
        _tool_event("send_email", 1),
        _tool_event("lookup", 2),
    ]
    contracts = AgentContracts(
        sequence=SequenceContracts(require_before=[("tool:lookup", "tool:send_email")])
    )
    findings = evaluate_contracts(current=events, contracts=contracts)
    codes = [f.classification for f in findings]
    assert "contract_sequence_require_before_violated" in codes


def test_require_before_missing_first_element() -> None:
    events = [_tool_event("send_email", 1)]
    contracts = AgentContracts(
        sequence=SequenceContracts(require_before=[("tool:lookup", "tool:send_email")])
    )
    findings = evaluate_contracts(current=events, contracts=contracts)
    codes = [f.classification for f in findings]
    assert "contract_sequence_require_before_violated" in codes


# ---------------------------------------------------------------------------
# Sequence: eventually
# ---------------------------------------------------------------------------

def test_eventually_satisfied() -> None:
    events = [_tool_event("finalize", 1)]
    contracts = AgentContracts(
        sequence=SequenceContracts(eventually=["tool:finalize"])
    )
    findings = evaluate_contracts(current=events, contracts=contracts)
    codes = [f.classification for f in findings]
    assert "contract_sequence_eventually_missing" not in codes


def test_eventually_missing() -> None:
    events = [_tool_event("other", 1)]
    contracts = AgentContracts(
        sequence=SequenceContracts(eventually=["tool:finalize"])
    )
    findings = evaluate_contracts(current=events, contracts=contracts)
    codes = [f.classification for f in findings]
    assert "contract_sequence_eventually_missing" in codes


# ---------------------------------------------------------------------------
# Sequence: never
# ---------------------------------------------------------------------------

def test_never_not_seen() -> None:
    events = [_tool_event("safe_op", 1)]
    contracts = AgentContracts(
        sequence=SequenceContracts(never=["tool:dangerous"])
    )
    findings = evaluate_contracts(current=events, contracts=contracts)
    codes = [f.classification for f in findings]
    assert "contract_sequence_never_seen" not in codes


def test_never_seen() -> None:
    events = [_tool_event("dangerous", 1)]
    contracts = AgentContracts(
        sequence=SequenceContracts(never=["tool:dangerous"])
    )
    findings = evaluate_contracts(current=events, contracts=contracts)
    codes = [f.classification for f in findings]
    assert "contract_sequence_never_seen" in codes


# ---------------------------------------------------------------------------
# Sequence: at_most_once
# ---------------------------------------------------------------------------

def test_at_most_once_satisfied() -> None:
    events = [_tool_event("charge", 1)]
    contracts = AgentContracts(
        sequence=SequenceContracts(at_most_once=["tool:charge"])
    )
    findings = evaluate_contracts(current=events, contracts=contracts)
    codes = [f.classification for f in findings]
    assert "contract_sequence_at_most_once_exceeded" not in codes


def test_at_most_once_exceeded() -> None:
    events = [_tool_event("charge", 1), _tool_event("charge", 2)]
    contracts = AgentContracts(
        sequence=SequenceContracts(at_most_once=["tool:charge"])
    )
    findings = evaluate_contracts(current=events, contracts=contracts)
    codes = [f.classification for f in findings]
    assert "contract_sequence_at_most_once_exceeded" in codes


# ---------------------------------------------------------------------------
# Network: default = allow, but domain not in allowlist
# ---------------------------------------------------------------------------

def test_network_default_allow_domain_not_in_allowlist() -> None:
    events = [
        make_event(
            event_type="tool_called",
            seq=1,
            run_id="r1",
            rel_ms=1,
            payload={
                "tool_name": "http_request",
                "input": {"args": [], "kwargs": {"url": "https://evil.example/path"}},
            },
        ),
    ]
    contracts = AgentContracts(
        network=NetworkContracts(
            default="allow",
            allow_domains=["safe.example.com"],
        )
    )
    findings = evaluate_contracts(current=events, contracts=contracts)
    codes = [f.classification for f in findings]
    assert "contract_network_domain_denied" in codes


def test_network_default_allow_domain_in_allowlist() -> None:
    events = [
        make_event(
            event_type="tool_called",
            seq=1,
            run_id="r1",
            rel_ms=1,
            payload={
                "tool_name": "http_request",
                "input": {"args": [], "kwargs": {"url": "https://safe.example.com/api"}},
            },
        ),
    ]
    contracts = AgentContracts(
        network=NetworkContracts(
            default="allow",
            allow_domains=["safe.example.com"],
        )
    )
    findings = evaluate_contracts(current=events, contracts=contracts)
    codes = [f.classification for f in findings]
    assert "contract_network_domain_denied" not in codes


def test_network_default_allow_no_allowlist() -> None:
    """When default=allow and no allowlist, no violation."""
    events = [
        make_event(
            event_type="tool_called",
            seq=1,
            run_id="r1",
            rel_ms=1,
            payload={
                "tool_name": "http_request",
                "input": {"args": [], "kwargs": {"url": "https://anything.com/x"}},
            },
        ),
    ]
    contracts = AgentContracts(
        network=NetworkContracts(default="allow", allow_domains=[])
    )
    findings = evaluate_contracts(current=events, contracts=contracts)
    codes = [f.classification for f in findings]
    assert "contract_network_domain_denied" not in codes


# ---------------------------------------------------------------------------
# Data-leak: outbound_kinds filtering
# ---------------------------------------------------------------------------

def test_pii_not_detected_in_non_eligible_kind() -> None:
    """PII in an llm_called event is not flagged when outbound_kinds=TOOL_CALL only."""
    events = [
        make_event(
            event_type="llm_called",
            seq=1,
            run_id="r1",
            rel_ms=1,
            payload={"provider": "openai", "model": "gpt-4", "messages": [{"content": "email: user@test.com"}]},
        ),
    ]
    contracts = AgentContracts(
        data_leak=DataLeakContracts(
            deny_pii_outbound=True,
            outbound_kinds=["TOOL_CALL"],
        )
    )
    findings = evaluate_contracts(current=events, contracts=contracts)
    codes = [f.classification for f in findings]
    assert "contract_data_leak_pii_outbound" not in codes


def test_pii_detected_in_llm_kind() -> None:
    """PII in an llm_called event IS flagged when outbound_kinds=LLM_REQUEST."""
    events = [
        make_event(
            event_type="llm_called",
            seq=1,
            run_id="r1",
            rel_ms=1,
            payload={"provider": "openai", "model": "gpt-4", "messages": [{"content": "email: user@test.com"}]},
        ),
    ]
    contracts = AgentContracts(
        data_leak=DataLeakContracts(
            deny_pii_outbound=True,
            outbound_kinds=["LLM_REQUEST"],
        )
    )
    findings = evaluate_contracts(current=events, contracts=contracts)
    codes = [f.classification for f in findings]
    assert "contract_data_leak_pii_outbound" in codes


def test_secret_pattern_outbound_kinds_filtering() -> None:
    """Secret pattern only checked in eligible outbound_kinds."""
    events = [
        make_event(
            event_type="tool_called",
            seq=1,
            run_id="r1",
            rel_ms=1,
            payload={"tool_name": "log", "input": {"args": ["sk_live_ABC"], "kwargs": {}}},
        ),
    ]
    contracts = AgentContracts(
        data_leak=DataLeakContracts(
            outbound_kinds=["LLM_REQUEST"],
            secret_patterns=[r"sk_live_[A-Za-z0-9]+"],
        )
    )
    findings = evaluate_contracts(current=events, contracts=contracts)
    codes = [f.classification for f in findings]
    assert "contract_data_leak_secret_pattern" not in codes


# ---------------------------------------------------------------------------
# Tool schema edge cases
# ---------------------------------------------------------------------------

def test_schema_min_violation() -> None:
    events = [
        make_event(
            event_type="tool_called",
            seq=1,
            run_id="r1",
            rel_ms=1,
            payload={
                "tool_name": "bid",
                "input": {"args": [], "kwargs": {"amount": 3}},
            },
        ),
    ]
    contracts = AgentContracts(
        tools=ToolContracts(
            schema={
                "bid": {
                    "fields": {
                        "amount": {"type": "number", "min": 10},
                    },
                },
            }
        )
    )
    findings = evaluate_contracts(current=events, contracts=contracts)
    codes = [f.classification for f in findings]
    assert "contract_args_min_violation" in codes


def test_schema_type_violation_not_numeric() -> None:
    events = [
        make_event(
            event_type="tool_called",
            seq=1,
            run_id="r1",
            rel_ms=1,
            payload={
                "tool_name": "bid",
                "input": {"args": [], "kwargs": {"amount": "not-a-number"}},
            },
        ),
    ]
    contracts = AgentContracts(
        tools=ToolContracts(
            schema={
                "bid": {
                    "fields": {
                        "amount": {"type": "number"},
                    },
                },
            }
        )
    )
    findings = evaluate_contracts(current=events, contracts=contracts)
    codes = [f.classification for f in findings]
    assert "contract_args_type_violation" in codes


def test_schema_enum_violation() -> None:
    events = [
        make_event(
            event_type="tool_called",
            seq=1,
            run_id="r1",
            rel_ms=1,
            payload={
                "tool_name": "pay",
                "input": {"args": [], "kwargs": {"currency": "GBP"}},
            },
        ),
    ]
    contracts = AgentContracts(
        tools=ToolContracts(
            schema={
                "pay": {
                    "fields": {
                        "currency": {"type": "string", "enum": ["USD", "EUR"]},
                    },
                },
            }
        )
    )
    findings = evaluate_contracts(current=events, contracts=contracts)
    codes = [f.classification for f in findings]
    assert "contract_args_enum_violation" in codes


def test_schema_regex_violation() -> None:
    events = [
        make_event(
            event_type="tool_called",
            seq=1,
            run_id="r1",
            rel_ms=1,
            payload={
                "tool_name": "tag",
                "input": {"args": [], "kwargs": {"label": "INVALID!!"}},
            },
        ),
    ]
    contracts = AgentContracts(
        tools=ToolContracts(
            schema={
                "tag": {
                    "fields": {
                        "label": {"type": "string", "regex": r"^[a-z-]+$"},
                    },
                },
            }
        )
    )
    findings = evaluate_contracts(current=events, contracts=contracts)
    codes = [f.classification for f in findings]
    assert "contract_args_regex_violation" in codes


def test_schema_required_key_missing() -> None:
    events = [
        make_event(
            event_type="tool_called",
            seq=1,
            run_id="r1",
            rel_ms=1,
            payload={
                "tool_name": "pay",
                "input": {"args": [], "kwargs": {"amount": 50}},
            },
        ),
    ]
    contracts = AgentContracts(
        tools=ToolContracts(
            schema={
                "pay": {
                    "required_keys": ["amount", "currency"],
                },
            }
        )
    )
    findings = evaluate_contracts(current=events, contracts=contracts)
    codes = [f.classification for f in findings]
    assert "contract_args_required_key_missing" in codes


# ---------------------------------------------------------------------------
# Network deny: no domain (blocked)
# ---------------------------------------------------------------------------

def test_network_deny_no_domain_in_url() -> None:
    events = [
        make_event(
            event_type="tool_called",
            seq=1,
            run_id="r1",
            rel_ms=1,
            payload={
                "tool_name": "http_request",
                "input": {"args": [], "kwargs": {"url": "not-a-url"}},
            },
        ),
    ]
    contracts = AgentContracts(
        network=NetworkContracts(default="deny", allow_domains=["safe.com"])
    )
    findings = evaluate_contracts(current=events, contracts=contracts)
    codes = [f.classification for f in findings]
    assert "contract_network_domain_denied" in codes
