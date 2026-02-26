"""Support Triage Agent — regression (buggy version).

Someone added an unsafe_export call to log ticket data externally,
not realizing it violates the tool safety contract.  The store_triage
step is also missing, meaning the classification is never persisted.
"""
from __future__ import annotations

from examples.real_llm_ci.runner import (
    _openai_response,
    agent_step,
    fetch_ticket,
    unsafe_export,
)


def main() -> None:
    agent_step("start", {"agent": "support_triage", "mode": "regression"})

    ticket = fetch_ticket("TICKET-4291")

    classification = _openai_response(
        "gpt-4o-mini",
        f"Classify this support ticket into one of [refund, billing, account]. "
        f"Respond with the category and a one-sentence action plan.\n\n"
        f"Ticket: {ticket['content']}",
    )

    # BUG: exports ticket data instead of storing the triage result
    unsafe_export("support_triage", {"ticket": ticket, "response": classification})

    agent_step("done", {"classification": classification})


if __name__ == "__main__":
    main()
