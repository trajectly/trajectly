# Trajectly

Deterministic regression testing for AI agents. Record a baseline, enforce contracts, catch regressions before they ship.

## Install

```bash
pip install trajectly
```

## 30-Second Example

Trajectly works in three steps: **record** a known-good baseline, **run** against it later, and **get a verdict**.

```bash
# Clone the repo to get the examples
git clone https://github.com/trajectly/trajectly.git
cd trajectly

# Install trajectly with example dependencies (openai, gemini)
pip install -e ".[examples]"

# Set your OpenAI key (the example calls gpt-4o-mini)
export OPENAI_API_KEY="sk-..."

# 1. Record the baseline
cd examples
trajectly init
trajectly record specs/trt-support-triage-baseline.agent.yaml

# 2. Run the regression variant against it
trajectly run specs/trt-support-triage-regression.agent.yaml

# 3. See what broke
trajectly report
```

The report shows exactly **which step** failed, **why** (the regression calls `unsafe_export`, which is denied by policy), and gives you a **deterministic repro command**.

## How It Works

1. **Record** -- run your agent normally. Trajectly captures every tool call and LLM response as a trace.
2. **Replay** -- re-run the agent. Trajectly replays recorded LLM responses from fixtures so results are deterministic.
3. **Compare** -- Trajectly checks the new trace against the baseline:
   - **Contracts**: are only allowed tools called? Are denied tools blocked?
   - **Refinement**: does the new call sequence preserve the baseline sequence?
4. **Verdict** -- PASS or FAIL with the exact failure step (witness index), violation code, and a copy-paste repro command.

## Examples

| Example | Provider | Tools | What it tests |
|---------|----------|-------|---------------|
| [Ticket Classifier](docs/tutorial-support-triage.md) | OpenAI | `fetch_ticket`, `store_triage` | Simple 2-tool agent with contract enforcement |
| [Code Review Bot](docs/tutorial-code-review-bot.md) | Gemini | `fetch_pr`, `lint_code`, `post_review` | Multi-tool sequence with policy guardrails |

## Documentation

- [Full documentation](docs/trajectly.md) -- concepts, CLI reference, spec format, SDK reference
- [Tutorial: Ticket Classifier](docs/tutorial-support-triage.md) -- step-by-step simple example
- [Tutorial: Code Review Bot](docs/tutorial-code-review-bot.md) -- step-by-step medium example

## License

MIT
