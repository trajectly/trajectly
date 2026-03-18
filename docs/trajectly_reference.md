# Trajectly Reference

This is the canonical lookup reference for:
- CLI commands
- spec schema
- SDK interfaces
- trace schema
- contracts

For onboarding and troubleshooting, use [Guide](trajectly_guide.md).

## Table of contents

- [1) CLI reference](#1-cli-reference)
- [2) Spec reference](#2-spec-reference)
- [3) SDK reference](#3-sdk-reference)
- [4) Trace schema reference](#4-trace-schema-reference)
- [5) Contracts reference](#5-contracts-reference)

---

## 1) CLI reference

The command surface below reflects current `python -m trajectly --help` workflow.

### Top-level commands

| Command | Purpose |
|---|---|
| `python -m trajectly --version` | Print version |
| `python -m trajectly init [PROJECT_ROOT]` | Initialize `.trajectly/` workspace |
| `python -m trajectly enable [PROJECT_ROOT] [--template ...]` | Scaffold and auto-discover setup |
| `python -m trajectly record [TARGETS]... [--auto] [--project-root ...] [--allow-ci-write]` | Record baselines and fixtures |
| `python -m trajectly run TARGETS... [--project-root ...] [--baseline ...] [--strict/--no-strict]` | Run TRT checks |
| `python -m trajectly repro [SELECTOR] [--project-root ...] [--strict/--no-strict] [--print-only]` | Reproduce latest/selected regression |
| `python -m trajectly shrink [SELECTOR] [--project-root ...] [--max-seconds ...] [--max-iterations ...]` | Minimize failing trace |
| `python -m trajectly sync [--project-root ...] --endpoint ... [--project-slug ...] [--dry-run]` | Push latest run artifacts to a platform endpoint |
| `python -m trajectly report [--project-root ...] [--json] [--pr-comment]` | Print latest aggregate report |
| `python -m trajectly baseline ...` | Baseline lifecycle commands |

### `init`

```bash
python -m trajectly init
python -m trajectly init ./my-project
```

### `enable`

```bash
python -m trajectly enable
python -m trajectly enable . --template openai
```

Supported templates include `openai`, `langchain`, and `autogen`.

### `record`

Signature:

```text
python -m trajectly record [TARGETS]... [--project-root PATH] [--auto] [--allow-ci-write]
```

Examples:

```bash
python -m trajectly record specs/my-agent.agent.yaml --project-root .
python -m trajectly record --auto --project-root .
```

### `run`

Signature:

```text
python -m trajectly run TARGETS... [--project-root PATH] [--baseline-dir PATH] [--fixtures-dir PATH] [--baseline VERSION] [--strict/--no-strict]
```

Examples:

```bash
python -m trajectly run specs/my-agent.agent.yaml --project-root .
python -m trajectly run specs/*.agent.yaml --project-root . --baseline v2
```

Exit codes:
- `0` = all passing
- `1` = one or more regressions
- `2` = config/internal/tooling error

### `repro`

Signature:

```text
python -m trajectly repro [SELECTOR] [--project-root PATH] [--strict/--no-strict] [--print-only]
```

Examples:

```bash
python -m trajectly repro
python -m trajectly repro my-agent
python -m trajectly repro --print-only
```

### `shrink`

Signature:

```text
python -m trajectly shrink [SELECTOR] [--project-root PATH] [--max-seconds FLOAT] [--max-iterations INT]
```

Examples:

```bash
python -m trajectly shrink
python -m trajectly shrink my-agent --max-seconds 20 --max-iterations 500
```

### `sync`

Signature:

```text
python -m trajectly sync [--project-root PATH] --endpoint URL [--api-key TOKEN] [--project-slug SLUG] [--dry-run] [--retries INT] [--timeout-seconds FLOAT]
```

Examples:

```bash
python -m trajectly sync --project-root . --endpoint https://platform.example/api/v1/sync
python -m trajectly sync --project-root . --endpoint https://platform.example/api/v1/sync --dry-run
```

Protocol details:
- Request/response contract: [Platform Sync Protocol](platform_sync_protocol.md)
- Successful runs persist `.trajectly/sync/latest.json`
- Dry runs build the payload and idempotency key without sending the request

### `report`

```bash
python -m trajectly report
python -m trajectly report --json
python -m trajectly report --pr-comment
```

### Baseline commands

#### `baseline list`

```text
python -m trajectly baseline list [TARGETS]... [--project-root PATH]
```

```bash
python -m trajectly baseline list
python -m trajectly baseline list specs/my-agent.agent.yaml
```

#### `baseline create`

```text
python -m trajectly baseline create --name VERSION TARGETS... [--project-root PATH] [--allow-ci-write]
```

```bash
python -m trajectly baseline create --name v2 specs/my-agent.agent.yaml --project-root .
```

#### `baseline promote`

```text
python -m trajectly baseline promote VERSION [TARGETS]... [--project-root PATH]
```

```bash
python -m trajectly baseline promote v2 specs/my-agent.agent.yaml --project-root .
```

#### `baseline diff`

```text
python -m trajectly baseline diff SPEC_SLUG LEFT RIGHT [--project-root PATH] [--json]
```

```bash
python -m trajectly baseline diff my-agent v1 v2 --project-root .
python -m trajectly baseline diff my-agent v1 v2 --json
```

#### `baseline update`

```text
python -m trajectly baseline update [TARGETS]... [--project-root PATH] [--auto] [--allow-ci-write]
```

```bash
python -m trajectly baseline update specs/my-agent.agent.yaml --project-root .
python -m trajectly baseline update --auto --project-root .
```

---

## 2) Spec reference

Trajectly specs are `.agent.yaml` files.

### Minimal example

```yaml
schema_version: "0.4"
name: my-agent
command: python -m agents.my_agent
contracts:
  tools:
    allow: [fetch_data, summarize]
```

Required fields:
- `schema_version`
- `name`
- `command`

### Annotated example

```yaml
schema_version: "0.4"
name: procurement-chaos
command: python -m arena.cli run --scenario procurement-chaos
workdir: ../..
strict: true
fixture_policy: by_hash
budget_thresholds:
  max_tool_calls: 8
  max_tokens: 800
contracts:
  config: ../../contracts/procurement-chaos.contracts.yaml
```

### Common fields

| Field | Purpose |
|---|---|
| `schema_version` | Spec schema version (`0.4`) |
| `name` | Human-readable spec name |
| `command` | Command used by runtime subprocess |
| `workdir` | Optional run working directory |
| `env` | Env overrides |
| `contracts` | Policy constraints |
| `replay` | Replay matching configuration |
| `refinement` | Refinement behavior controls |
| `determinism` | Determinism-related runtime controls |
| `redact` | Regex redaction patterns |
| `budget_thresholds` | Max latency/tool calls/tokens |
| `artifacts_dir` | Artifact output directory |

### Spec inheritance (`extends`)

```yaml
# child.agent.yaml
extends: ./base.agent.yaml
name: my-agent-variant
contracts:
  tools:
    deny: [unsafe_export]
```

Merge semantics:
- dicts merge recursively
- lists and scalars override parent values

---

## 3) SDK reference

Trajectly supports two SDK styles that share the same runtime instrumentation path.

### Choosing an SDK style

1. Use decorators when you already have plain Python functions and want minimal integration work.
2. Use `trajectly.App` when you want explicit DAG structure, node dependencies, and generated spec scaffolding.
3. Both styles emit the same trace event types and use the same CLI/report pipeline.

### A) Decorators

```python
from trajectly.sdk import agent_step, tool
from trajectly.sdk.adapters import openai_chat_completion

@tool("fetch_ticket")
def fetch_ticket(ticket_id: str) -> dict[str, str]:
    return {
        "ticket_id": ticket_id,
        "plan": "enterprise",
        "issue_type": "duplicate_charge",
    }

@tool("escalate_to_human")
def escalate_to_human(incident_id: str, reason_code: str) -> dict[str, str]:
    return {
        "incident_id": incident_id,
        "reason_code": reason_code,
        "queue": "billing-escalations",
    }

def run_support_flow(client) -> None:
    agent_step("scenario:start", {"scenario": "support-apocalypse"})
    ticket = fetch_ticket("TCK-1001")
    model = openai_chat_completion(
        client,
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Return the escalation reason code only."},
            {"role": "user", "content": f"issue_type={ticket['issue_type']}"},
        ],
    )
    reason_code = str(model["response"]).strip() or "duplicate_charge"
    escalate_to_human(incident_id="INC-230001", reason_code=reason_code)
    agent_step("scenario:done", {"path": "escalated"})
```

### B) Declarative graph (`trajectly.App`)

```python
import trajectly

app = trajectly.App(name="graph-chain-reaction")

@app.node(id="fetch_incident", type="tool")
def fetch_incident(incident_id: str) -> dict[str, str]:
    return {"incident_id": incident_id, "severity": "sev1"}

@app.node(id="choose_dispatch_token", type="transform", depends_on={"incident": "fetch_incident"})
def choose_dispatch_token(incident: dict[str, str]) -> str:
    return "WR-12345" if incident["severity"] == "sev1" else "WR-99999"

@app.node(id="dispatch_war_room", type="tool", depends_on={"dispatch_token": "choose_dispatch_token"})
def dispatch_war_room(dispatch_token: str) -> dict[str, str]:
    return {"dispatch_token": dispatch_token, "status": "sent"}

if __name__ == "__main__":
    outputs = app.run({"incident_id": "INC-777001"})
    print(outputs["dispatch_war_room"])
```

### Graph API objects

- `trajectly.App`: graph registration and execution
- `trajectly.sdk.graph.NodeSpec`: immutable node definition
- `trajectly.sdk.graph.GraphSpec`: validated graph snapshot (nodes, topological order, input keys)
- `trajectly.sdk.graph.GraphError`: static graph validation errors
- `trajectly.sdk.graph.scan_module(module)`: discover decorated node specs

### `App.node(...)` semantics

Node types:
- `tool`
- `llm`
- `input`
- `transform`

Dependencies:
- `depends_on=["a", "b"]` -> positional parameter mapping
- `depends_on={"param": "source_node"}` -> explicit mapping
- `depends_on=None` -> parameters resolve from `input_data` or previous node ids

### Deterministic order

Graph execution uses deterministic topological ordering (lexicographic tie-break for same indegree).

### Event mapping

Graph execution emits the same event types used everywhere else:
- `tool_called` / `tool_returned` via `ctx.invoke_tool`
- `llm_called` / `llm_returned` via `ctx.invoke_llm`
- `agent_step` markers for graph lifecycle and transform stages

### `generate_spec(...)`

`App.generate_spec()` returns a `.agent.yaml`-compatible template:
- fills `schema_version`, `name`, placeholder `command`
- derives tool allowlist and sequence requirements from graph tool nodes
- allows deep-merged overrides

### Framework adapters

Framework adapters in `trajectly.sdk.adapters` include:
- `openai_chat_completion`
- `gemini_generate_content`
- `langchain_invoke`
- `anthropic_messages_create`
- `llamaindex_query`

---

## 4) Trace schema reference

Trajectly stores traces as JSONL (one event per line).

### Event envelope

| Field | Meaning |
|---|---|
| `schema_version` | Trace event schema version (`"v1"`) |
| `event_type` | Event kind |
| `seq` | Emission sequence number |
| `run_id` | Run identifier |
| `rel_ms` | Milliseconds since run start |
| `payload` | Event-specific payload |
| `meta` | Optional metadata |
| `event_id` | Deterministic event hash (if present) |

### Event types

| Event type | Meaning |
|---|---|
| `run_started` | Runtime start marker |
| `agent_step` | Logical step marker |
| `tool_called` | Tool invocation started |
| `tool_returned` | Tool invocation finished |
| `llm_called` | LLM invocation started |
| `llm_returned` | LLM invocation finished |
| `run_finished` | Runtime completion marker |

Example:

```json
{
  "schema_version": "v1",
  "event_type": "tool_called",
  "seq": 6,
  "run_id": "run-01H...",
  "rel_ms": 124,
  "payload": {
    "tool_name": "fetch_data",
    "input": {"args": ["q-123"], "kwargs": {}}
  },
  "meta": {}
}
```

Note: spec schema version (`0.4`) and trace schema version (`v1`) are intentionally separate version namespaces.

### Portable trajectory JSON

For platform ingestion and storage, Trajectly also supports a bundled normalized trace payload:

```json
{
  "events": [
    {
      "event_index": 0,
      "kind": "TOOL_CALL",
      "payload": {"tool_name": "search"},
      "schema_version": "0.4",
      "stable_hash": "abc123"
    }
  ],
  "meta": {
    "metadata": {},
    "mode": "record",
    "normalizer_version": "1",
    "schema_version": "0.4",
    "spec_name": "demo"
  },
  "schema_version": "0.4"
}
```

Portable JSON helpers:
- `trajectly.trace.models.TrajectoryV03.to_json()`
- `trajectly.trace.models.TrajectoryV03.from_json(...)`
- `trajectly.trace.io.write_trajectory_json(...)`
- `trajectly.trace.io.read_trajectory_json(...)`
- `trajectly.trace.io.read_legacy_trajectory(...)` to lift `trace.jsonl` + `trace.meta.json`

---

## 5) Contracts reference

Contracts are under `contracts:` in spec YAML.

### Tools

```yaml
contracts:
  tools:
    allow: [fetch_data, save_result]
    deny: [unsafe_export]
    max_calls_total: 10
    max_calls_per_tool:
      fetch_data: 3
```

### Sequence

```yaml
contracts:
  sequence:
    require: [fetch_data, process, save_result]
    forbid: [unsafe_export]
    require_before:
      - before: fetch_data
        after: save_result
    eventually: [save_result]
    never: [unsafe_export]
    at_most_once: [initialize]
```

### Side effects

```yaml
contracts:
  side_effects:
    deny_write_tools: true
```

### Network

```yaml
contracts:
  network:
    default: deny
    allow_domains: [api.example.com]
```

### Data leak

```yaml
contracts:
  data_leak:
    deny_pii_outbound: true
    outbound_kinds: [TOOL_CALL, LLM_REQUEST]
    secret_patterns: ["(?i)api[_-]?key"]
```

### Arguments

```yaml
contracts:
  args:
    fetch_data:
      required_keys: [query]
      fields:
        query:
          type: string
          regex: "^[a-zA-Z0-9-]+$"
```

---

For troubleshooting and failure-recovery workflow, use [Guide: 5) Troubleshooting](trajectly_guide.md#5-troubleshooting).
