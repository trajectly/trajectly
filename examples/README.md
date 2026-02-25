# Trajectly Examples

Two real-world examples demonstrating Trajectly regression testing with actual LLM calls.

## Examples

| Example | Provider | Model | Tools | Complexity |
|---------|----------|-------|-------|------------|
| **Ticket Classifier** | OpenAI | gpt-4o-mini | `fetch_ticket`, `store_triage` | Simple |
| **Code Review Bot** | Gemini | gemini-2.5-flash | `fetch_pr`, `lint_code`, `post_review` | Medium |

Each example has a **baseline** (correct behavior) and a **regression** (introduces `unsafe_export`, which is denied by contract).

## Quick Start

```bash
# Install dependencies
pip install -e ".[dev]"
pip install openai  # for ticket classifier

# Set API keys
export OPENAI_API_KEY="sk-..."
export GEMINI_API_KEY="..."

# Run the simple example
cd examples
trajectly record specs/trt-support-triage-baseline.agent.yaml
trajectly run specs/trt-support-triage-regression.agent.yaml
trajectly report
```

## Directory Structure

```
examples/
├── specs/                          # YAML spec files
│   ├── trt-support-triage-baseline.agent.yaml
│   ├── trt-support-triage-regression.agent.yaml
│   ├── trt-code-review-bot-baseline.agent.yaml
│   └── trt-code-review-bot-regression.agent.yaml
├── examples/
│   ├── support_triage/             # Ticket classifier entrypoints
│   │   ├── main.py                 # baseline
│   │   └── main_regression.py      # regression
│   ├── code_review_bot/            # Code review bot entrypoints
│   │   ├── main.py
│   │   └── main_regression.py
│   └── real_llm_ci/
│       └── runner.py               # Shared scenario logic + tools
└── README.md
```

## Tutorials

- [Ticket Classifier tutorial](../docs/tutorial-support-triage.md)
- [Code Review Bot tutorial](../docs/tutorial-code-review-bot.md)
