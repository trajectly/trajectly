from __future__ import annotations

from trajectly.contracts import evaluate_contracts
from trajectly.events import make_event
from trajectly.specs import (
    AgentContracts,
    DataLeakContracts,
    NetworkContracts,
    SequenceContracts,
    SideEffectContracts,
    ToolContracts,
)


def test_evaluate_contracts_reports_tool_contract_violations() -> None:
    events = [
        make_event(
            event_type="tool_called",
            seq=1,
            run_id="r1",
            rel_ms=1,
            payload={"tool_name": "add", "input": {"args": [1, 2], "kwargs": {}}},
        ),
        make_event(
            event_type="tool_called",
            seq=2,
            run_id="r1",
            rel_ms=2,
            payload={"tool_name": "delete_account", "input": {"args": [], "kwargs": {}}},
        ),
        make_event(
            event_type="run_finished",
            seq=3,
            run_id="r1",
            rel_ms=3,
            payload={"duration_ms": 3, "returncode": 0},
        ),
    ]
    contracts = AgentContracts(
        tools=ToolContracts(allow=["add"], deny=["delete_account"], max_calls_total=1),
        side_effects=SideEffectContracts(deny_write_tools=True),
    )

    findings = evaluate_contracts(current=events, contracts=contracts)
    classifications = [finding.classification for finding in findings]

    assert "contract_tool_denied" in classifications
    assert "contract_tool_not_allowed" in classifications
    assert "contract_side_effect_write_tool_denied" in classifications
    assert "contract_max_calls_total_exceeded" in classifications


def test_evaluate_contracts_reports_sequence_require_and_forbid() -> None:
    events = [
        make_event(
            event_type="tool_called",
            seq=1,
            run_id="r1",
            rel_ms=1,
            payload={"tool_name": "add", "input": {"args": [1, 2], "kwargs": {}}},
        ),
        make_event(
            event_type="agent_step",
            seq=2,
            run_id="r1",
            rel_ms=2,
            payload={"name": "done", "details": {}},
        ),
        make_event(
            event_type="run_finished",
            seq=3,
            run_id="r1",
            rel_ms=3,
            payload={"duration_ms": 3, "returncode": 0},
        ),
    ]
    contracts = AgentContracts(
        sequence=SequenceContracts(
            require=["tool:add", "tool:search"],
            forbid=["tool:add"],
        )
    )

    findings = evaluate_contracts(current=events, contracts=contracts)
    classifications = [finding.classification for finding in findings]

    assert "contract_sequence_required_missing" in classifications
    assert "contract_sequence_forbidden_seen" in classifications


def test_evaluate_contracts_network_allowlist_blocked_signal() -> None:
    events = [
        make_event(
            event_type="run_finished",
            seq=1,
            run_id="r1",
            rel_ms=1,
            payload={
                "duration_ms": 1,
                "returncode": 1,
                "stderr_tail": (
                    "Trajectly replay mode blocks network access. "
                    "Use recorded fixtures or disable replay mode."
                ),
            },
        )
    ]
    contracts = AgentContracts(network=NetworkContracts(allowlist=["api.example.com"]))

    findings = evaluate_contracts(current=events, contracts=contracts)
    classifications = [finding.classification for finding in findings]

    assert "contract_network_allowlist_blocked" in classifications


def test_evaluate_contracts_supports_args_and_per_tool_limits_and_pii() -> None:
    events = [
        make_event(
            event_type="tool_called",
            seq=1,
            run_id="r1",
            rel_ms=1,
            payload={
                "tool_name": "checkout",
                "input": {
                    "args": [],
                    "kwargs": {"product_id": "p-1", "price": 42, "currency": "USD"},
                },
            },
        ),
        make_event(
            event_type="tool_called",
            seq=2,
            run_id="r1",
            rel_ms=2,
            payload={
                "tool_name": "refund",
                "input": {
                    "args": [],
                    "kwargs": {"invoice_id": "i-1", "amount": 10, "reason": "duplicate"},
                },
            },
        ),
        make_event(
            event_type="tool_called",
            seq=3,
            run_id="r1",
            rel_ms=3,
            payload={
                "tool_name": "refund",
                "input": {
                    "args": [],
                    "kwargs": {"invoice_id": "i-1", "amount": 10, "reason": "duplicate"},
                },
            },
        ),
        make_event(
            event_type="tool_called",
            seq=4,
            run_id="r1",
            rel_ms=4,
            payload={
                "tool_name": "web_search",
                "input": {"args": ["contact customer@example.com"], "kwargs": {}},
            },
        ),
    ]
    contracts = AgentContracts(
        tools=ToolContracts(
            deny=["web_search"],
            max_calls_per_tool={"refund": 1},
            schema={
                "checkout": {
                    "required_keys": ["product_id", "price", "currency"],
                    "fields": {
                        "price": {"type": "number", "max": 30},
                        "currency": {"type": "string", "enum": ["USD", "EUR"]},
                    },
                }
            },
        ),
        data_leak=DataLeakContracts(
            deny_pii_outbound=True,
            outbound_kinds=["TOOL_CALL"],
        ),
    )

    findings = evaluate_contracts(current=events, contracts=contracts)
    classifications = {finding.classification for finding in findings}

    assert "contract_args_max_violation" in classifications
    assert "contract_max_calls_per_tool_exceeded" in classifications
    assert "contract_tool_denied" in classifications
    assert "contract_data_leak_pii_outbound" in classifications


def test_evaluate_contracts_reports_network_domain_denied() -> None:
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
    contracts = AgentContracts(network=NetworkContracts(default="deny", allow_domains=["api.example.com"]))

    findings = evaluate_contracts(current=events, contracts=contracts)
    classifications = {finding.classification for finding in findings}

    assert "contract_network_domain_denied" in classifications


def test_evaluate_contracts_reports_secret_pattern_leak() -> None:
    events = [
        make_event(
            event_type="tool_called",
            seq=1,
            run_id="r1",
            rel_ms=1,
            payload={
                "tool_name": "post_comment",
                "input": {"args": [], "kwargs": {"body": "token=sk_live_ABCD1234"}},
            },
        ),
    ]
    contracts = AgentContracts(
        data_leak=DataLeakContracts(
            deny_pii_outbound=False,
            outbound_kinds=["TOOL_CALL"],
            secret_patterns=[r"sk_live_[A-Za-z0-9]+"],
        )
    )

    findings = evaluate_contracts(current=events, contracts=contracts)
    classifications = {finding.classification for finding in findings}

    assert "contract_data_leak_secret_pattern" in classifications
