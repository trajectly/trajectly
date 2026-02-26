# Trajectly Examples

Two real-world examples demonstrating deterministic regression testing for AI agents.

## Examples

| Example | Provider | Tools | What it tests |
|---------|----------|-------|---------------|
| **Ticket Classifier** | OpenAI (gpt-4o-mini) | `fetch_ticket`, `store_triage` | Tool allow/deny contracts, budget thresholds |
| **Code Review Bot** | Gemini (gemini-2.5-flash) | `fetch_pr`, `lint_code`, `post_review` | Sequence contracts, budget thresholds, tool deny, behavioral refinement |

Each example has a **baseline** (correct behavior) and a **regression** (intentionally broken).

## Quick Start

Pre-recorded baselines and fixtures are included -- **no API keys needed**.

```bash
# From the repo root
pip install -e ".[examples]"
cd examples
```

### Try it now (Ticket Classifier)

```bash
# Run the regression variant (replays from pre-recorded fixtures)
trajectly run specs/trt-support-triage-regression.agent.yaml
# Exit code 1: regression detected

# See what broke
trajectly report
# Shows: FAIL at witness index, REFINEMENT_BASELINE_CALL_MISSING

# Reproduce the failure
trajectly repro

# Minimize to shortest failing trace
trajectly shrink

# If the change was intentional, update the baseline
trajectly baseline update specs/trt-support-triage-baseline.agent.yaml
```

### Code Review Bot (multi-contract)

```bash
# Run regression (skips lint_code, calls unsafe_export)
trajectly run specs/trt-code-review-bot-regression.agent.yaml

# See multiple violations: sequence + tool deny + refinement
trajectly report
```

### Recording your own baselines

To re-record baselines from scratch (requires live LLM provider):

```bash
export OPENAI_API_KEY="sk-..."   # for ticket classifier
export GEMINI_API_KEY="..."       # for code review bot
trajectly init
trajectly record specs/trt-support-triage-baseline.agent.yaml
trajectly record specs/trt-code-review-bot-baseline.agent.yaml
```

## What each regression demonstrates

**Ticket Classifier regression**: The agent calls `unsafe_export` instead of `store_triage`. Trajectly detects this as `CONTRACT_TOOL_DENIED` -- the tool is on the deny list.

**Code Review Bot regression**: The agent skips the `lint_code` step and calls `unsafe_export`. Trajectly detects three violations:
- `CONTRACT_TOOL_DENIED` -- `unsafe_export` is denied
- `REFINEMENT_BASELINE_CALL_MISSING` -- the baseline called `lint_code` but the regression didn't
- `SEQUENCE_REQUIRE_BEFORE` -- `lint_code` must run before `post_review` (but it never ran)

## Directory Structure

```
examples/
├── specs/                          # Agent spec YAML files
│   ├── trt-support-triage-baseline.agent.yaml
│   ├── trt-support-triage-regression.agent.yaml
│   ├── trt-code-review-bot-baseline.agent.yaml
│   └── trt-code-review-bot-regression.agent.yaml
├── examples/
│   ├── support_triage/             # Ticket classifier entrypoints
│   │   ├── main.py                 # baseline
│   │   └── main_regression.py      # regression
│   ├── code_review_bot/            # Code review bot entrypoints
│   │   ├── main.py                 # baseline
│   │   └── main_regression.py      # regression
│   └── real_llm_ci/
│       └── runner.py               # Shared scenario logic + tools
└── README.md

```

## Tutorials

- [Ticket Classifier tutorial](../docs/tutorial-support-triage.md) -- step-by-step walkthrough
- [Code Review Bot tutorial](../docs/tutorial-code-review-bot.md) -- multi-tool sequence example
