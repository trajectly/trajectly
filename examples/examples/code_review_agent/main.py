"""Code Review Agent — baseline (correct behavior).

A realistic agent that reviews pull requests: fetches the diff,
runs lint checks, generates a review with Gemini, and posts it.

Workflow:  fetch_pr -> lint_code -> LLM review -> post_review
"""
from __future__ import annotations

from examples.real_llm_ci.runner import (
    fetch_pr,
    lint_code,
    post_review,
    _gemini_response,
    _stable_json,
    agent_step,
)


def main() -> None:
    agent_step("start", {"agent": "code_review_agent", "mode": "baseline"})

    pr = fetch_pr("PR-2048")
    lint = lint_code(pr["diff"])

    review = _gemini_response(
        "gemini-2.5-flash",
        f"Review this pull request diff and lint results. "
        f"Summarize issues and approve or request changes.\n\n"
        f"Diff:\n{pr['diff']}\n\nLint:\n{_stable_json(lint)}",
    )

    result = post_review(pr["pr_id"], review)

    agent_step("done", {"review": review, "result": result})


if __name__ == "__main__":
    main()
