from __future__ import annotations

from trajectly.contracts import evaluate_contracts
from trajectly.events import make_event
from trajectly.specs import (
    AgentContracts,
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
