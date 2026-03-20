# Trajectly

[![CI](https://github.com/trajectly/trajectly/actions/workflows/ci.yml/badge.svg)](https://github.com/trajectly/trajectly/actions/workflows/ci.yml)
[![CodeQL](https://github.com/trajectly/trajectly/actions/workflows/codeql.yml/badge.svg)](https://github.com/trajectly/trajectly/actions/workflows/codeql.yml)
[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/trajectly/trajectly/badge)](https://securityscorecards.dev/viewer/?uri=github.com/trajectly/trajectly)
[![PyPI version](https://img.shields.io/pypi/v/trajectly.svg)](https://pypi.org/project/trajectly/)

Deterministic regression testing for AI agents.

The answer looked fine. The behavior wasn't. An agent that skips approval, leaks a secret, or calls a forbidden domain can still produce a perfectly worded final answer. Trajectly catches the behavioral regression and tells you *exactly where it broke*.
Record once against live behavior, then replay committed fixtures deterministically in CI with no API key.

## Install

```bash
pip install trajectly
```

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

## How You Use Trajectly

Trajectly exposes three public surfaces:

### CLI

The default workflow for most users. Use the CLI to record baselines, run checks, inspect reports, reproduce failures, and shrink traces.

### SDK

Use the SDK when you want Trajectly to instrument your agent code directly.

Two SDK styles are supported:
- Decorators: `tool`, `llm_call`, `agent_step`
- Declarative graph: `trajectly.App`

### Programmatic Evaluation API

Use this when you already have trajectory events and want to evaluate them inside your own Python service, backend, or platform integration without shelling out to the CLI.

Most users should start with the CLI and, when needed, the SDK. The programmatic evaluation API is mainly for embedding Trajectly into other systems.

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

## How You Debug Failures

Every failure comes with three tools:

| Tool | What it does | Command |
|---|---|---|
| **Witness** | Pinpoints the exact trace event where behavior diverged | Included in every report |
| **Repro** | Replays the exact failure deterministically | `python -m trajectly repro` |
| **Shrink** | Reduces the trace to the shortest proof (14 events -> 3) | `python -m trajectly shrink` |

No log hunting. No guesswork. No LLM calls for evaluation.

## Use This In Your Project

1. Add one `.agent.yaml` spec (save as `specs/support-agent-mfa-reset.agent.yaml`):

```yaml
schema_version: "0.4"
name: "support-agent-mfa-reset"
command: "python -m support_agent.runner"
workdir: .
strict: true
fixture_policy: by_hash
budget_thresholds:
  max_tool_calls: 6
  max_tokens: 800
contracts:
  config: contracts/support-agent.contracts.yaml
```

2. Add one `.contracts.yaml` policy (save as `contracts/support-agent.contracts.yaml`):

```yaml
version: v1
tools:
  allow: [draft_mfa_reset_request, request_human_approval, log_audit_event]
  deny: [delete_user, disable_guardrails]
args:
  draft_mfa_reset_request:
    required_keys: [account_id]
    fields:
      account_id:
        type: string
        regex: "^ACME-"
sequence:
  require: [tool:draft_mfa_reset_request, tool:request_human_approval]
  at_most_once: [tool:request_human_approval]
  eventually: [tool:log_audit_event]
data_leak:
  deny_pii_outbound: true
```

3. Record, gate, debug:

```bash
python -m trajectly init
python -m trajectly record specs/support-agent-mfa-reset.agent.yaml --project-root .
python -m trajectly run specs/support-agent-mfa-reset.agent.yaml --project-root .
python -m trajectly report
python -m trajectly repro
python -m trajectly shrink
```

## CI Integration

Trajectly is the fast deterministic gate on every pull request. Record baselines locally against live behavior, commit them, then let CI replay the fixtures offline on every run. Broader live evals can run later on `main`, release branches, or scheduled jobs.

Any CI:

```bash
pip install trajectly
python -m trajectly run specs/*.agent.yaml --project-root .
python -m trajectly report --pr-comment > trajectly_pr_comment.md
python -m trajectly sync --project-root . --endpoint https://platform.example/api/v1/sync
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

For platform ingestion, `python -m trajectly sync` uploads the latest run report plus portable execution trajectories to a Trajectly-compatible server endpoint. The request contract is documented in [docs/platform_sync_protocol.md](docs/platform_sync_protocol.md).

## Programmatic Evaluation API

For platform, backend, or advanced integrations, use the stable import-safe evaluation API. This is the programmatic evaluation surface, not the SDK instrumentation layer:

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

The supported Phase 1 import boundary for platform/server code is documented in
[docs/platform_api_surface.md](docs/platform_api_surface.md).

## Try Merge or Die

Eight arena scenarios covering all six failure categories. Run them, break them, debug them.

[trajectly-survival-arena](https://github.com/trajectly/trajectly-survival-arena) | [trajectly.dev/merge-or-die](https://www.trajectly.dev/merge-or-die)

## Documentation

- [Guide](docs/trajectly_guide.md) -- onboarding, core concepts, TRT algorithm
- [What Trajectly Catches](docs/what_trajectly_catches.md) -- six failure categories with full examples
- [Contract Catalog](docs/contract_catalog.md) -- reference for all six contract dimensions
- [Reference](docs/trajectly_reference.md) -- CLI, spec schema, SDK, programmatic evaluation API, trace schema
- [CI: GitHub Actions](docs/ci_github_actions.md) -- action inputs, execution order, artifacts
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
