"""Support Escalation Agent — regression after prompt upgrade.

PR context:
The prompt was changed to optimize for "fast auto-resolution". The new
flow now closes a case that policy requires escalating to a human.
"""
from __future__ import annotations

from examples.real_llm_ci.runner import (
    _openai_response,
    agent_step,
    check_entitlements,
    fetch_ticket,
    unsafe_auto_close,
)


def main() -> None:
    agent_step("start", {"agent": "support_escalation_agent", "mode": "regression"})

    ticket = fetch_ticket("TICKET-8801")
    policy = check_entitlements(ticket["account_tier"], ticket["issue_type"])

    closure_reason = _openai_response(
        "gpt-4o-mini",
        "Write a one-sentence escalation note for a human billing specialist. "
        "Do not propose direct auto-closure for enterprise duplicate-charge cases.\n\n"
        f"Ticket: {ticket['content']}",
    )

    # BUG: bypasses mandatory human escalation path.
    result = unsafe_auto_close(ticket["ticket_id"], closure_reason)

    agent_step("done", {"policy": policy, "closure_reason": closure_reason, "result": result})


if __name__ == "__main__":
    main()
