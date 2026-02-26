"""Code Review Agent — regression (buggy version).

Someone removed the lint step to "speed up reviews" and added an
unsafe_export call, breaking three contracts simultaneously:
  1. lint_code is required before post_review (sequence violation)
  2. unsafe_export is on the deny list (tool policy violation)
  3. lint_code and post_review are missing (refinement violation)
"""
from __future__ import annotations

from examples.real_llm_ci.runner import (
    fetch_pr,
    unsafe_export,
    _gemini_response,
    agent_step,
)


def main() -> None:
    agent_step("start", {"agent": "code_review_agent", "mode": "regression"})

    pr = fetch_pr("PR-2048")

    # BUG: skips lint_code entirely and exports data instead of posting review
    review = _gemini_response(
        "gemini-2.5-flash",
        f"Review this pull request diff.\n\nDiff:\n{pr['diff']}",
    )

    unsafe_export("code_review_agent", {"pr": pr, "response": review})

    agent_step("done", {"review": review})


if __name__ == "__main__":
    main()
