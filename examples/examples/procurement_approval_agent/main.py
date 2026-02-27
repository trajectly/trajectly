"""Procurement Approval Agent — baseline (LangChain policy flow).

PR context:
A prompt update changed how supplier recommendations are generated. This
baseline is the expected behavior in CI: recommendations are advisory,
then routed through mandatory approval before creating a PO.
"""
from __future__ import annotations

from typing import Any

from examples.real_llm_ci.runner import (
    agent_step,
    create_purchase_order,
    fetch_requisition,
    fetch_vendor_quotes,
    route_for_approval,
)

from trajectly.sdk import langchain_invoke


class ProcurementPolicyRunnable:
    """Minimal runnable compatible with `langchain_invoke`."""

    def __init__(self, prompt_version: str) -> None:
        self.prompt_version = prompt_version

    def invoke(self, input_data: dict[str, Any]) -> dict[str, Any]:
        quotes = input_data["quotes"]
        risk_rank = {"low": 0, "medium": 1, "high": 2}
        safest_quote = min(quotes, key=lambda quote: risk_rank[quote["risk_score"]])
        return {
            "response": {
                "selected_vendor": safest_quote["vendor_id"],
                "approval_reason": (
                    f"Prompt {self.prompt_version}: select lowest-risk vendor and require finance approval."
                ),
                "requires_manual_approval": True,
            },
            "usage": {"input_tokens": 152, "output_tokens": 81},
        }


def main() -> None:
    agent_step("start", {"agent": "procurement_approval_agent", "mode": "baseline"})

    requisition = fetch_requisition("REQ-8842")
    quotes = fetch_vendor_quotes(requisition["request_id"])

    policy_chain = ProcurementPolicyRunnable(prompt_version="v1-approved")
    policy_result = langchain_invoke(
        policy_chain,
        {
            "requisition": requisition,
            "quotes": quotes,
            "instruction": "Recommend a vendor but never bypass approval controls.",
        },
        model="procurement-policy-chain-v1",
        provider="langchain",
    )
    recommendation = policy_result["response"]

    approval = route_for_approval(
        requisition["request_id"],
        recommendation["selected_vendor"],
        recommendation["approval_reason"],
    )
    po = create_purchase_order(
        requisition["request_id"],
        recommendation["selected_vendor"],
        approval["approved_by"],
    )

    agent_step(
        "done",
        {
            "recommendation": recommendation,
            "approval": approval,
            "purchase_order": po,
        },
    )


if __name__ == "__main__":
    main()
