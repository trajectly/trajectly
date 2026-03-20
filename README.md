# Trajectly

[![CI](https://github.com/trajectly/trajectly/actions/workflows/ci.yml/badge.svg)](https://github.com/trajectly/trajectly/actions/workflows/ci.yml)
[![CodeQL](https://github.com/trajectly/trajectly/actions/workflows/codeql.yml/badge.svg)](https://github.com/trajectly/trajectly/actions/workflows/codeql.yml)
[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/trajectly/trajectly/badge)](https://securityscorecards.dev/viewer/?uri=github.com/trajectly/trajectly)
[![PyPI version](https://img.shields.io/pypi/v/trajectly.svg)](https://pypi.org/project/trajectly/)

Deterministic regression testing for AI agents.

The answer looked fine. The behavior wasn't. An agent that skips approval, leaks a secret, or calls a forbidden domain can still produce a perfectly worded final answer. Trajectly catches the behavioral regression and tells you *exactly where it broke*.
Record once against live behavior, then replay committed fixtures deterministically in CI with no API key.

## 30-Second Quickstart

Uses committed fixtures -- no API keys required.

```bash
git clone https://github.com/trajectly/trajectly-survival-arena.git
cd trajectly-survival-arena
python3.11 -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m trajectly init

# baseline behavior (expected PASS)
python -m trajectly run specs/challenges/procurement-chaos.agent.yaml --project-root .

# intentional regression (expected FAIL -- approval was skipped)
python -m trajectly run specs/examples/procurement-chaos-regression.agent.yaml --project-root .
python -m trajectly report
python -m trajectly repro
python -m trajectly shrink
```

## What Trajectly Catches

Six categories of silent failure that correct-looking output can hide.
Trajectly checks execution-path behavior, not final-answer quality: which tools ran, with what arguments, in what order, and across which data boundaries.
The examples below are simplified report snippets with labeled fields.

### Missing steps

An agent skips a required step but the answer reads fine. Trajectly extracts a tool-call skeleton from the baseline and verifies it appears as a subsequence in the current trace. Missing calls break the skeleton.

```text
violation: REFINEMENT_BASELINE_CALL_MISSING
detail: missing_call=route_for_approval
witness: 6
```

### Wrong order

The right tools called in the wrong sequence. `require_before` says "A must happen before B" without locking exact positions, so the agent can evolve without breaking the ordering rule.

```text
violation: CONTRACT_SEQUENCE_REQUIRE_BEFORE_VIOLATED
detail: expected=reserve_room before send_invite
witness: 4
```

### Leaked secrets

The summary looks clean but the outbound tool-call payload contains a secret pattern. Trajectly scans outbound arguments against regex patterns declared in the contract.

```text
violation: DATA_LEAK_SECRET_PATTERN
detail: pattern=sk_live_[A-Za-z0-9_]+
witness: 4
```

### Forbidden network access

The agent reports success but contacted a domain outside the allowlist. The network contract defaults to deny-all and whitelists specific domains.

```text
violation: NETWORK_DOMAIN_DENIED
witness: 2
```

### Invalid arguments

A tool call completes but an argument violates its format. Argument contracts validate required keys, types, numeric bounds, regex patterns, and enum values on every call.

```text
violation: CONTRACT_ARGS_REGEX_VIOLATION
witness: 6
```

### Budget overruns

Identical output, but twice the tool calls or tokens. Budget thresholds gate execution cost at the spec level.

```text
classification: budget_breach
detail: max_tool_calls exceeded
```

## Common Use Cases

Trajectly is a good fit for agents that can look correct while doing the wrong thing at runtime.

- **Support agents** -- keep read-only lookups read-only, require approval for MFA resets, ensure audit trails, and prevent PII leakage. See the [support agent case study](https://www.trajectly.dev/case-study/testing-the-support-agent).
- **Approval-driven workflows** -- procurement, finance, HR, and IT operations agents where required steps, ordering, and one-time approvals matter.
- **Tool-using copilots and RAG agents** -- validate tool arguments after model or prompt changes, block forbidden tools or domains, and catch hidden cost regressions.

## Default Workflow

For most teams, Trajectly is a CLI-first loop:

1. `record` captures a known-good baseline plus the fixtures needed for deterministic replay.
2. `run` replays the committed fixtures and checks refinement plus contracts.
3. `report` explains failures with the witness index and violated contract.
4. `repro` and `shrink` replay the exact failure and minimize it to the shortest proof.
5. The same `run` command becomes your fast deterministic CI gate.

Initialize once, then the day-to-day flow looks like this:

```bash
python -m trajectly init
python -m trajectly record specs/my-agent.agent.yaml --project-root .
python -m trajectly run specs/my-agent.agent.yaml --project-root .
python -m trajectly report
python -m trajectly repro
python -m trajectly shrink
```

When something fails, `report` tells you why, `repro` reruns the exact failure deterministically, and `shrink` reduces the trace to the smallest counterexample. No log hunting. No LLM calls for evaluation.

See [Guide](docs/trajectly_guide.md) for the full onboarding flow, [Reference](docs/trajectly_reference.md) for CLI and schema details, and [What Trajectly Catches](docs/what_trajectly_catches.md) for deeper examples.

## Add Trajectly to Your Project

Start with one critical workflow. This example stays generic on purpose: swap in your own command, tool names, identifiers, and thresholds.

1. Add one `.agent.yaml` spec (save as `specs/my-agent.agent.yaml`):

```yaml
schema_version: "0.4"
name: "my-agent"
command: "python -m my_agent.runner"
workdir: .
strict: true
fixture_policy: by_hash
budget_thresholds:
  max_tool_calls: 6
  max_tokens: 800
contracts:
  config: contracts/my-agent.contracts.yaml
```

2. Add one `.contracts.yaml` policy (save as `contracts/my-agent.contracts.yaml`):

```yaml
version: v1
tools:
  allow: [fetch_context, prepare_action, request_approval, log_audit_event]
  deny: [delete_records, disable_guardrails]
args:
  prepare_action:
    required_keys: [resource_id]
    fields:
      resource_id:
        type: string
        regex: "^RES-"
sequence:
  require: [tool:fetch_context, tool:prepare_action, tool:request_approval]
  at_most_once: [tool:request_approval]
  eventually: [tool:log_audit_event]
data_leak:
  deny_pii_outbound: true
```

3. Initialize once, then use the three core commands:

```bash
python -m trajectly init
python -m trajectly record specs/my-agent.agent.yaml --project-root .
python -m trajectly run specs/my-agent.agent.yaml --project-root .
python -m trajectly report
```

## CI Integration

Trajectly is the fast deterministic gate on every pull request. Record baselines locally against live behavior, commit them, then let CI replay the fixtures offline on every run. Broader live evals can run later on `main`, release branches, or scheduled jobs.

Any CI:

```bash
pip install trajectly
python -m trajectly run specs/*.agent.yaml --project-root .
python -m trajectly report --pr-comment > trajectly_pr_comment.md
```

GitHub Actions:

```yaml
- uses: trajectly/trajectly-action@v1.0.2
  with:
    spec_glob: "specs/*.agent.yaml"
    project_root: "."
    comment_pr: "true"
```

When a spec fails, the PR gets a death report: witness index, violated contract, repro command, and shrink result.

See [trajectly-action](https://github.com/trajectly/trajectly-action) for full CI documentation.

If you need platform ingestion, `python -m trajectly sync` uploads the latest run report plus portable execution trajectories to a Trajectly-compatible server endpoint. The request contract is documented in [docs/platform_sync_protocol.md](docs/platform_sync_protocol.md).

See [CI: GitHub Actions](docs/ci_github_actions.md) for action inputs, execution order, and artifacts.

## Other Integration Paths

### CLI

The CLI is the default path already shown above. Use it to record baselines, run checks, inspect reports, reproduce failures, and shrink traces.

### SDK

Use the SDK when you want Trajectly to instrument agent code directly:

```python
from trajectly.sdk import agent_step, tool

@tool
def fetch_context(resource_id: str) -> dict:
    return {"resource_id": resource_id}

def run() -> None:
    agent_step("workflow:start", {"name": "my-agent"})
    fetch_context("RES-123")
```

Two SDK styles are supported: decorators like `tool`, `llm_call`, and `agent_step`, plus the declarative graph style `trajectly.App`. See [Reference](docs/trajectly_reference.md) for both.

### Programmatic Evaluation API

For platform, backend, or advanced integrations, use the stable import-safe evaluation API when you already have trajectory events and want to evaluate them inside your own Python service:

```python
from pathlib import Path

from trajectly.core import Trajectory, evaluate
from trajectly.events import make_event

trajectory = Trajectory(
    events=[
        make_event(
            event_type="tool_called",
            seq=1,
            run_id="platform-run",
            rel_ms=1,
            payload={"tool_name": "search", "input": {"args": [], "kwargs": {}}},
        )
    ]
)

verdict = evaluate(trajectory, Path("specs/my-agent.agent.yaml"))
if not verdict.passed:
    print(verdict.primary_violation)
```

If you omit `baseline_events`, Trajectly evaluates execution contracts without requiring CLI baseline orchestration. Provide `baseline_events` when you want refinement checks to participate in the verdict.

The supported Phase 1 import boundary for platform/server code is documented in [docs/platform_api_surface.md](docs/platform_api_surface.md).

## Try Merge or Die

Eight arena scenarios covering all six failure categories. Run them, break them, debug them.

[trajectly-survival-arena](https://github.com/trajectly/trajectly-survival-arena) | [trajectly.dev/merge-or-die](https://www.trajectly.dev/merge-or-die)

## Documentation

- [Guide](docs/trajectly_guide.md) -- onboarding, core concepts, TRT algorithm
- [Reference](docs/trajectly_reference.md) -- CLI, spec schema, SDK, programmatic evaluation API, trace schema
- [CI: GitHub Actions](docs/ci_github_actions.md) -- action inputs, execution order, artifacts
- [What Trajectly Catches](docs/what_trajectly_catches.md) -- six failure categories with full examples
- [Contract Catalog](docs/contract_catalog.md) -- reference for all six contract dimensions
- [Platform API Surface](docs/platform_api_surface.md) -- stable import boundary for platform/server integrations
- [Platform Sync Protocol](docs/platform_sync_protocol.md) -- HTTP contract for `trajectly sync`
- [Architecture (maintainers)](docs/architecture.md)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Apache 2.0 -- see [LICENSE](LICENSE).

## Community

- Questions/discussions: <https://github.com/trajectly/trajectly/discussions>
- Security reports (private): <https://github.com/trajectly/trajectly/security/advisories/new>
