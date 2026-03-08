# Trajectly

[![CI](https://github.com/trajectly/trajectly/actions/workflows/ci.yml/badge.svg)](https://github.com/trajectly/trajectly/actions/workflows/ci.yml)
[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/trajectly/trajectly/badge)](https://securityscorecards.dev/viewer/?uri=github.com/trajectly/trajectly)
[![PyPI version](https://img.shields.io/pypi/v/trajectly.svg)](https://pypi.org/project/trajectly/)

Trajectly is deterministic regression testing for AI agents.

It helps you catch behavioral regressions that text-only checks often miss:
- record a known-good run
- replay it with deterministic fixtures
- get an exact failing event index plus reproducible command

Under the hood, Trajectly uses **Trajectory Refinement Testing (TRT)**.

## Install

```bash
python -m pip install trajectly
python -m trajectly --version
```

## 30-Second Quickstart

Use the arena scenarios with pre-recorded fixtures (no API keys required):

```bash
git clone https://github.com/trajectly/trajectly-survival-arena.git
cd trajectly-survival-arena
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m trajectly init

python -m trajectly run specs/challenges/procurement-chaos.agent.yaml --project-root .
ARENA_AGENT_PATH=agents/contenders/unsafe_demo.py python -m trajectly run specs/challenges/procurement-chaos.agent.yaml --project-root .
python -m trajectly report
ARENA_AGENT_PATH=agents/contenders/unsafe_demo.py python -m trajectly repro
ARENA_AGENT_PATH=agents/contenders/unsafe_demo.py python -m trajectly shrink
```

Expected exits for this intentional regression flow:
- first `run` (safe contender) -> `0` (`PASS`)
- second `run` (unsafe contender) -> `1` (`FAIL`)
- `report` -> `0`
- `repro` -> `1` (replays the same failing scenario)
- `shrink` -> `0`

Observed output excerpts from a fresh run (March 8, 2026):

```text
# safe run
- `procurement-chaos`: clean
  - trt: `PASS`

# unsafe run
- `procurement-chaos`: regression
  - trt: `FAIL` (witness=6)

# report
Source: $PROJECT_ROOT/.trajectly/reports/latest.md

# repro
Repro command: python -m trajectly run "$PROJECT_ROOT/specs/challenges/procurement-chaos.agent.yaml" --project-root "$PROJECT_ROOT"

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

Arena example map:
- `procurement-chaos`, `support-apocalypse`, `calendar-thunderdome`: refinement/sequence regressions.
- `secret-karaoke`: outbound secret pattern detection.
- `graph-chain-reaction`: graph node argument contract enforcement.
- `network-no-fly-zone`: `contracts.network` domain policy.
- `budget-gauntlet`: `budget_thresholds` breaches with unchanged final text.

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

Arena example: `graph-chain-reaction` in `trajectly-survival-arena` runs the same contender contract through `trajectly.App` and demonstrates args-contract failure detection without changing final text.

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

The canonical action is published at `trajectly/trajectly-action`:

```yaml
name: Agent Regression Tests
on: [push, pull_request]

jobs:
  trajectly:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@v4
      - uses: trajectly/trajectly-action@v1.0.1
        with:
          spec_glob: "specs/*.agent.yaml"
          project_root: "."
```

Notes:
- `comment_pr` is off by default. Enable it only when you want PR comments and grant `pull-requests: write`.
- The in-repo path `./github-action` is a temporary compatibility wrapper and is planned for removal in `v0.4.3` (one release cycle after `v0.4.2`).

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
- [Security policy](SECURITY.md)
- [Contributing guide](CONTRIBUTING.md)
- [Support Escalation Demo (standalone)](https://github.com/trajectly/support-escalation-demo)
- [Procurement Approval Demo (standalone)](https://github.com/trajectly/procurement-approval-demo)
- [Merge or Die Arena (scenario tutorial)](https://github.com/trajectly/trajectly-survival-arena)

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

## Community

- Questions and use-case discussions: <https://github.com/trajectly/trajectly/discussions>
- Security reports (private): <https://github.com/trajectly/trajectly/security/advisories/new>

## Support Trajectly

If Trajectly is useful to your work, please give the repository a star ⭐
