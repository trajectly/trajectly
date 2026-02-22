# Trajectly

Deterministic regression testing for AI agent trajectories.

Trajectly is the "Playwright for AI agents": record tool-using agent runs, replay them deterministically offline, and fail CI on meaningful trajectory regressions.

## Quickstart

### Recommended (`uv`)

```bash
uv venv
source .venv/bin/activate
uv sync --extra dev
trajectly init
trajectly record tests/*.agent.yaml
trajectly run tests/*.agent.yaml
```

### Pip Editable Install (Supported)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
trajectly init
trajectly record tests/*.agent.yaml
trajectly run tests/*.agent.yaml
```

## Example Diff Output

```text
Regression detected in spec simple
- sequence_mismatch: expected tool:add at position 2, got tool:multiply
- structural_mismatch at $.payload.output.total: baseline=5 current=6
- budget_breach: max_tool_calls exceeded (baseline=2 current=4 limit=3)
```

## ASCII Architecture

```text
Agent Spec (.agent.yaml) -> CLI Orchestrator -> Runtime Shim (record|replay)
Runtime Shim -> Adapter SDK hooks (tool_called/tool_returned, llm_called/returned)
Record mode -> Canonical JSONL Trace + Fixture Store
Replay mode -> Fixture Matcher (by_index|by_hash) + Network Blocker
Both traces -> Diff Engine (sequence + args + outputs + budgets) -> Reporters (md/json)
Plugin Bus -> semantic diff plugins + SaaS export hooks
```

## Why Trajectly vs Existing Tools

- LangSmith: excellent observability and tracing, but Trajectly is CI-first deterministic replay/diff for strict regression gating.
- Braintrust: strong eval workflows, while Trajectly focuses on trajectory determinism and fixture-backed replay semantics.
- Promptfoo: prompt/output evaluation centric; Trajectly diffs full tool/LLM call trajectories, arguments, outputs, and budgets.
- agent-ci.com: CI orchestration focused; Trajectly centers on canonical trace contracts and reproducible local+CI replay behavior.

## Open-Core Model

OSS (MIT) contains the CLI, replay engine, diff engine, local reporting, and plugin hooks.
Future SaaS adds hosted history, team dashboards, flakiness detection, semantic diff services, and alerting.

## Roadmap

- v0.1: deterministic record/replay/diff, GitHub Action, examples
- v0.2: richer adapters, stronger schema validation, plugin ecosystem
- v0.3: hosted ingestion API, historical trend surfacing

## License

MIT
