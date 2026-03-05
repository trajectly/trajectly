# Trajectly

Deterministic regression testing for AI agents, powered by **Trajectory Refinement Testing (TRT)**.

Trajectly records a known-good baseline, replays against deterministic fixtures, and tells you exactly where behavior diverged.

## Install

```bash
python -m pip install trajectly
python -m trajectly --version
```

Expected output cue:

```text
trajectly, version X.Y.Z
```

## 30-Second Quickstart

Use the standalone procurement demo with pre-recorded fixtures (no API keys required):

```bash
git clone https://github.com/trajectly/procurement-approval-demo.git
cd procurement-approval-demo
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

python -m trajectly run specs/trt-procurement-agent-regression.agent.yaml --project-root .
python -m trajectly report
python -m trajectly repro
python -m trajectly shrink
```

Expected exits for this intentional regression flow:
- `run ...regression...` -> `1` (`FAIL`)
- `report` -> `0`
- `repro` -> `1` (replays same failing run)
- `shrink` -> `0`

Observed output excerpts from a fresh run (March 5, 2026):

```text
# run ...regression...
- `trt-procurement-agent`: regression
  - trt: `FAIL` (witness=10)

# report
Source: $PROJECT_ROOT/.trajectly/reports/latest.md

# repro
Repro command: python -m trajectly run "$PROJECT_ROOT/specs/trt-procurement-agent-regression.agent.yaml" --project-root "$PROJECT_ROOT"

# shrink
Shrink completed and report updated with shrink stats.
```

Artifacts to expect after running the flow:
- `$PROJECT_ROOT/.trajectly/reports/latest.md`
- `$PROJECT_ROOT/.trajectly/reports/latest.json`
- `$PROJECT_ROOT/.trajectly/repros/<spec>.json`
- `$PROJECT_ROOT/.trajectly/repros/<spec>.counterexample.reduced.trace.jsonl`

For full step-by-step command/output walkthroughs, use [docs/trajectly.md](docs/trajectly.md).

## What Trajectly Checks

TRT evaluates behavior, not just output text:
1. **Contract compliance**: allow/deny rules, sequence constraints, budgets, network, data leak, args.
2. **Refinement**: baseline tool-call skeleton must remain a subsequence of the new run.
3. **Witness resolution**: report the earliest failing event index (0-based trace index).

Result: stable PASS/FAIL in CI with deterministic repro.

## Typical Workflow

```bash
python -m trajectly init
python -m trajectly record specs/*.agent.yaml --project-root .
python -m trajectly run specs/*.agent.yaml --project-root .
python -m trajectly report
```

Typical clean-run cue:

```text
- `my-agent`: clean
  - trt: `PASS`
Latest report: $PROJECT_ROOT/.trajectly/reports/latest.md
```

Failure triage loop:

```bash
python -m trajectly repro
python -m trajectly shrink
```

Typical failing-run cue:

```text
Repro command: python -m trajectly run "$PROJECT_ROOT/specs/my-agent.agent.yaml" --project-root "$PROJECT_ROOT"
Shrink completed and report updated with shrink stats.
```

## SDK Options

Trajectly supports two instrumentation styles.

### Option A: Decorators and adapters

```python
from trajectly.sdk import tool, llm_call

@tool("fetch_ticket")
def fetch_ticket(ticket_id: str) -> dict:
    return {"id": ticket_id, "status": "open"}

@llm_call(provider="openai", model="gpt-4o")
def classify_ticket(text: str) -> str:
    ...
```

You can also use framework adapters like `openai_chat_completion`, `gemini_generate_content`, and `langchain_invoke`.

### Option B: Declarative graph API (`trajectly.App`)

```python
import trajectly

app = trajectly.App(name="research-agent")

@app.node(id="search_engine", type="tool")
def search(query: str) -> dict:
    ...

@app.node(id="summarizer", type="llm", depends_on=["search_engine"], provider="openai", model="gpt-4o")
def summarize(search_engine: dict) -> str:
    ...

@app.node(id="format_response", type="transform", depends_on=["summarizer"])
def format_response(summarizer: str) -> dict:
    return {"answer": summarizer}

if __name__ == "__main__":
    outputs = app.run(input_data={"query": "Why is the sky blue?"})
    print(outputs["format_response"])
```

The graph layer uses the same SDKContext instrumentation path and trace event types (`tool_called`, `tool_returned`, `llm_called`, `llm_returned`, `agent_step`). No CLI changes are required.

## CI Integration

### Any CI

```bash
python -m pip install trajectly
python -m trajectly run specs/*.agent.yaml --project-root .
python -m trajectly report --pr-comment > comment.md
```

What to expect:

```text
run exit code:
- 0 when all specs are clean
- 1 when regressions are detected
```

### GitHub Actions

Trajectly ships a thin wrapper action in `github-action/action.yml`:

```yaml
name: Agent Regression Tests
on: [push, pull_request]

jobs:
  trajectly:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: ./github-action
```

See [docs/ci_github_actions.md](docs/ci_github_actions.md) for input options and full behavior.

## Architecture at a Glance

| Layer | Purpose | Key modules |
|---|---|---|
| `core` | TRT evaluation, traces, fixtures, contracts | `core/trt`, `core/contracts.py`, `core/refinement` |
| `cli` | Command orchestration and reporting | `cli/commands.py`, `cli/engine.py` |
| `sdk` | Runtime instrumentation + graph API | `sdk/context.py`, `sdk/adapters.py`, `sdk/graph.py` |

## Documentation

- [Full reference](docs/trajectly.md)
- [Architecture](docs/architecture_phase1.md)
- [CI: GitHub Actions](docs/ci_github_actions.md)
- [Contributing guide](CONTRIBUTING.md)
- [Support Escalation Demo (standalone)](https://github.com/trajectly/support-escalation-demo)
- [Procurement Approval Demo (standalone)](https://github.com/trajectly/procurement-approval-demo)

## Contributing

For a friendly step-by-step contribution guide, see [CONTRIBUTING.md](CONTRIBUTING.md).

```bash
git clone https://github.com/trajectly/trajectly.git
cd trajectly
python -m pip install -e ".[dev]"
pytest tests/
ruff check .
mypy src
```

## License

Apache 2.0 -- see [LICENSE](LICENSE).

## Support Trajectly

If Trajectly is useful to your work, please give the repository a star ⭐:
<https://github.com/trajectly/trajectly/stargazers>
