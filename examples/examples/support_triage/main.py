from __future__ import annotations

from examples.real_llm_ci.runner import run_example


def main() -> None:
    run_example(
        scenario="ticket_classifier",
        provider="openai",
        mode="baseline",
        model="gpt-4o-mini",
    )


if __name__ == "__main__":
    main()
