# Tutorial: Code Review Bot (Medium)

A Gemini-powered agent that reviews pull requests. This example shows multi-tool sequence enforcement and how Trajectly catches unauthorized tool usage in a more complex flow.

## What this agent does

The agent uses three tools:

1. **`fetch_pr`** -- retrieves a pull request diff and description
2. **`lint_code`** -- runs a linter on the diff
3. **`post_review`** -- posts the review comment back

The baseline flow is: fetch PR -> lint the diff -> call LLM to write review -> post review.

The regression intentionally calls **`unsafe_export`** instead of `post_review`, which violates the tool contract.

## Files

### Agent code: `examples/examples/code_review_bot/main.py`

```python
from examples.real_llm_ci.runner import run_example

def main() -> None:
    run_example(
        scenario="code_review_bot",
        provider="gemini",
        mode="baseline",
        model="gemini-2.5-flash",
    )
```

The regression variant (`main_regression.py`) uses `mode="regression"`, causing the agent to call `unsafe_export` instead of `post_review`.

### Spec file: `examples/specs/trt-code-review-bot-baseline.agent.yaml`

```yaml
schema_version: "0.3"
name: "trt-code-review-bot"
command: "python -m examples.code_review_bot.main"
workdir: ..
fixture_policy: by_hash
strict: true
contracts:
  tools:
    allow: [fetch_pr, lint_code, post_review]
    deny: [unsafe_export]
```

The `allow` list enforces that the agent can only use `fetch_pr`, `lint_code`, and `post_review`. The `deny` list explicitly blocks `unsafe_export`. This means Trajectly enforces both:

- **What tools can be used** (allow list)
- **What tools must never be used** (deny list)

## Running it

### Prerequisites

```bash
pip install trajectly
export GEMINI_API_KEY="your-gemini-key"
```

### Step 1: Record the baseline

```bash
cd examples
trajectly record specs/trt-code-review-bot-baseline.agent.yaml
```

### Step 2: Run the regression

```bash
trajectly run specs/trt-code-review-bot-regression.agent.yaml
```

### Step 3: Check the report

```bash
trajectly report
```

### Step 4: Reproduce

```bash
trajectly repro --latest
```

## What Trajectly detected

The regression calls `unsafe_export` after `lint_code`, which violates the tool contract:

**Baseline call sequence:**
```
fetch_pr -> lint_code -> [LLM call] -> post_review
```

**Regression call sequence:**
```
fetch_pr -> lint_code -> [LLM call] -> unsafe_export  <-- DENIED
```

Trajectly reports:

- **Failure step**: the event index where `unsafe_export` was called
- **Violation code**: `CONTRACT_TOOL_DENIED`
- **Repro command**: `trajectly repro --latest`

## Why this matters

In production, a code review bot calling `unsafe_export` could leak proprietary code, credentials, or customer data. Trajectly catches this regression deterministically -- no flaky tests, no "it works on my machine." The exact failing trace is reproducible with a single command.
