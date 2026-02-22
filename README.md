# Trajectly

Deterministic regression testing for AI agent trajectories.

Trajectly is the "Playwright for AI agents": record tool-using agent runs, replay them deterministically offline, and fail CI on meaningful trajectory regressions.

## Quickstart

### Recommended (`uv`)

```bash
uv venv
source .venv/bin/activate
uv sync --extra dev
trajectly enable
trajectly record --auto
trajectly run tests/*.agent.yaml
```

Starter template option:

```bash
trajectly enable --template openai
```

### Pip Editable Install (Supported)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
trajectly enable
trajectly record --auto
trajectly run tests/*.agent.yaml
```

## Baseline Update Workflow

Baselines are updated explicitly. Re-record only when a behavior change is intended:

```bash
trajectly baseline update tests/*.agent.yaml
# or
trajectly baseline update --auto
```

## Reproduce A Failure

```bash
trajectly repro
# or pick a specific spec from latest report
trajectly repro example-contract-tool-denied
```

Each run writes repro artifacts to `.trajectly/repros/`, including minimized baseline/current traces.

For CI comment output:

```bash
trajectly report --pr-comment
```

## Contracts Schema (v1 Draft)

```yaml
contracts:
  tools:
    allow: []
    deny: []
    max_calls_total: 5
    schema: {}
  sequence:
    require: []
    forbid: []
  side_effects:
    deny_write_tools: true
  network:
    allowlist: []
```

Contract checks in replay emit stable codes in tool errors/findings, including:

- `CONTRACT_TOOL_DENIED`
- `CONTRACT_TOOL_NOT_ALLOWED`
- `CONTRACT_MAX_CALLS_TOTAL_EXCEEDED`
- `CONTRACT_WRITE_TOOL_DENIED`

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

## Open-Core Model

OSS (MIT) contains the CLI, replay engine, diff engine, local reporting, and plugin hooks.
Future SaaS adds hosted history, team dashboards, flakiness detection, semantic diff services, and alerting.

## Roadmap

- v0.1: deterministic record/replay/diff, GitHub Action, examples
- v0.2: richer adapters, stronger schema validation, plugin ecosystem
- v0.3: hosted ingestion API, historical trend surfacing

## Release Process

- Checklist and policy: `RELEASING.md`
- Release history: `CHANGELOG.md`

## License

MIT
