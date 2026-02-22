from __future__ import annotations

from trajectly.sdk import agent_step, llm_call, tool


@tool("add")
def add(left: int, right: int) -> int:
    return left + right


@llm_call(provider="mock", model="deterministic-v1")
def summarize(text: str) -> dict[str, object]:
    return {
        "response": f"summary:{text}",
        "usage": {"total_tokens": 12},
    }


def main() -> None:
    agent_step("start", {"secret": "secret_12345"})
    total = add(2, 3)
    summary = summarize(f"total={total}")
    agent_step("done", {"total": total, "summary": summary["response"]})


if __name__ == "__main__":
    main()
