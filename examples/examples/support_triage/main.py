"""Support Triage Agent — baseline (correct behavior).

A realistic agent that classifies incoming support tickets and stores
the triage result.  Uses OpenAI for classification.

Workflow:  fetch_ticket -> LLM classification -> store_triage
"""
from __future__ import annotations

from examples.real_llm_ci.runner import (
    fetch_ticket,
    store_triage,
    _openai_response,
    agent_step,
)


def main() -> None:
    agent_step("start", {"agent": "support_triage", "mode": "baseline"})

    ticket = fetch_ticket("TICKET-4291")

    classification = _openai_response(
        "gpt-4o-mini",
        f"Classify this support ticket into one of [refund, billing, account]. "
        f"Respond with the category and a one-sentence action plan.\n\n"
        f"Ticket: {ticket['content']}",
    )

    result = store_triage(classification, "billing")

    agent_step("done", {"classification": classification, "result": result})


if __name__ == "__main__":
    main()
