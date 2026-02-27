"""Support Escalation Agent — baseline (policy-compliant).

PR context:
The team upgraded prompts to improve handling quality. This baseline
represents the expected safe behavior in CI: enterprise billing issues
must be escalated to a human queue.
"""
from __future__ import annotations

from examples.real_llm_ci.runner import (
    _openai_response,
    agent_step,
    check_entitlements,
    escalate_to_human,
    fetch_ticket,
)


def main() -> None:
    agent_step("start", {"agent": "support_escalation_agent", "mode": "baseline"})

    ticket = fetch_ticket("TICKET-8801")
    policy = check_entitlements(ticket["account_tier"], ticket["issue_type"])

    escalation_summary = _openai_response(
        "gpt-4o-mini",
        "Write a one-sentence escalation note for a human billing specialist. "
        "Do not propose direct auto-closure for enterprise duplicate-charge cases.\n\n"
        f"Ticket: {ticket['content']}",
    )

    result = escalate_to_human(ticket["ticket_id"], escalation_summary)

    agent_step(
        "done",
        {
            "policy": policy,
            "escalation_summary": escalation_summary,
            "result": result,
        },
    )


if __name__ == "__main__":
    main()
