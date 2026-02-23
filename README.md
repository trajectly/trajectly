# Trajectly

Deterministic contract testing and replay for AI agent trajectories.

Trajectly is TRT-first: it records baseline runs, replays deterministically offline, and returns witness-driven failures with counterexample artifacts.

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

Docs-first onboarding:

- `HANDOFF.md` (new engineer entrypoint with DONE/TODO/PENDING/NEEDS_FIX status)
- `ONBOARDING_10_MIN.md` (timed setup and first regression workflow)
- `CONTRACTS_VERSION_POLICY.md` (stable contracts version policy and migration rules)
- `docs/legacy_compat_policy.md` (what remains as shim in v0.3.x and v0.4 removal target)
- `docs/trt/what-is-trt.md`
- `docs/trt/guarantees.md`
- `docs/trt/quickstart.md`
- `docs/trt/contracts-reference.md`
- `docs/trt/abstraction-reference.md`
- `docs/trt/troubleshooting.md`

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
TRT-enriched reports also include:
- `trt_v03.status`
- `trt_v03.witness_index`
- `trt_v03.primary_violation`
- `trt_v03.all_violations_at_witness`
- `trt_v03.counterexample_paths.prefix`

Optional shrink for reduced failing traces:

```bash
trajectly shrink --max-seconds 10 --max-iterations 200
```

For CI comment output:

```bash
trajectly report --pr-comment
```

Legacy spec migration:

```bash
trajectly migrate spec tests/legacy.agent.yaml
```

## CI Baseline Immutability

When `TRAJECTLY_CI=1`, baseline writes are blocked by default.

```bash
trajectly record tests/*.agent.yaml
# fails in CI mode unless explicit override is provided

trajectly record tests/*.agent.yaml --allow-ci-write
# explicit override for controlled baseline updates
```

## Contracts Schema (v1, TRT-aligned)

```yaml
contracts:
  version: v1
  tools:
    allow: []
    deny: []
    max_calls_total: 5
    max_calls_per_tool: {}
    schema: {}
  sequence:
    require: []
    forbid: []
    require_before: []
    eventually: []
    never: []
    at_most_once: []
  side_effects:
    deny_write_tools: true
  network:
    allowlist: []
    default: deny
    allow_domains: []
  data_leak:
    deny_pii_outbound: true
    outbound_kinds: [TOOL_CALL, LLM_REQUEST]
```

Contract checks in replay emit stable codes in tool errors/findings, including:

- `CONTRACT_TOOL_DENIED`
- `CONTRACT_TOOL_NOT_ALLOWED`
- `CONTRACT_MAX_CALLS_TOTAL_EXCEEDED`
- `CONTRACT_WRITE_TOOL_DENIED`

`contracts.version` currently supports only `v1`. See `CONTRACTS_VERSION_POLICY.md` for compatibility and upgrade rules.

## Example TRT Output

```text
TRT FAIL: spec=trt-support-triage
- witness_index: 2
- primary_violation: REFINEMENT_EXTRA_TOOL_CALL
- all_violations_at_witness:
  - REFINEMENT_NEW_TOOL_NAME_FORBIDDEN
  - CONTRACT_TOOL_DENIED
  - CONTRACT_SEQUENCE_NEVER_SEEN
- counterexample: .trajectly/repros/trt-support-triage.counterexample.prefix.jsonl
```

## ASCII Architecture

```text
Agent Spec (.agent.yaml) -> CLI Orchestrator -> Runtime Shim (record|replay)
Runtime Shim -> Adapter SDK hooks (tool_called/tool_returned, llm_called/returned)
Record mode -> Baseline Trace + Fixture Store
Replay mode -> Deterministic Matcher + Offline Guard
Replay trace -> Abstraction (alpha) + Contracts (Phi) + Skeleton Refinement
TRT verdict -> witness + counterexample + report (md/json)
Plugin Bus -> semantic hooks + optional cloud export
```

## Open-Core Model

OSS (MIT) contains the CLI, replay engine, diff engine, local reporting, and plugin hooks.
Future SaaS adds hosted history, team dashboards, flakiness detection, semantic diff services, and alerting.

## Roadmap

- v0.3: TRT core (abstraction + contracts + refinement), witness/counterexample artifacts, deterministic replay
- v0.3.x: shrinker improvements and migration hardening
- v0.4: broader adapters and optional cloud amplification

## Release Process

- Checklist and policy: `RELEASING.md`
- Release history: `CHANGELOG.md`

## License

MIT
