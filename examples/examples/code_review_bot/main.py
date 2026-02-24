from __future__ import annotations

from examples.real_llm_ci.runner import run_example


def main() -> None:
    run_example(
        scenario="code_review_bot",
        provider="gemini",
        mode="baseline",
        model="gemini-2.5-flash",
    )


if __name__ == "__main__":
    main()
