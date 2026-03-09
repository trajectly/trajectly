# Trajectly

[![CI](https://github.com/trajectly/trajectly/actions/workflows/ci.yml/badge.svg)](https://github.com/trajectly/trajectly/actions/workflows/ci.yml)
[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/trajectly/trajectly/badge)](https://securityscorecards.dev/viewer/?uri=github.com/trajectly/trajectly)
[![PyPI version](https://img.shields.io/pypi/v/trajectly.svg)](https://pypi.org/project/trajectly/)

Deterministic regression testing for AI agents.

The answer looked fine. The behavior wasn't. An agent that skips approval, leaks a secret, or calls a forbidden domain can still produce a perfectly worded final answer. Trajectly catches the behavioral regression and tells you *exactly where it broke*.

## Install

```bash
pip install trajectly
```

## 30-Second Quickstart

Uses committed fixtures -- no API keys required.

```bash
git clone https://github.com/trajectly/trajectly-survival-arena.git
cd trajectly-survival-arena
python3.11 -m venv .venv && source .venv/bin/activate
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

### Missing steps

An agent skips a required step but the answer reads fine. Trajectly extracts a tool-call skeleton from the baseline and verifies it appears as a subsequence in the current trace. Missing calls break the skeleton.

```text
REFINEMENT_BASELINE_CALL_MISSING — missing_call=route_for_approval — witness=6
```

### Wrong order

The right tools called in the wrong sequence. `require_before` says "A must happen before B" without locking exact positions, so the agent can evolve without breaking the ordering rule.

```text
CONTRACT_SEQUENCE_REQUIRE_BEFORE_VIOLATED — expected=reserve_room before send_invite — witness=4
```

### Leaked secrets

The summary looks clean but the outbound tool-call payload contains a secret pattern. Trajectly scans outbound arguments against regex patterns declared in the contract.

```text
DATA_LEAK_SECRET_PATTERN — pattern=sk_live_[A-Za-z0-9]+ — witness=4
```

### Forbidden network access

The agent reports success but contacted a domain outside the allowlist. The network contract defaults to deny-all and whitelists specific domains.

```text
NETWORK_DOMAIN_DENIED — witness=2
```

### Invalid arguments

A tool call completes but an argument violates its format. Argument contracts validate required keys, types, numeric bounds, regex patterns, and enum values on every call.

```text
CONTRACT_ARGS_REGEX_VIOLATION — witness=6
```

### Budget overruns

Identical output, but twice the tool calls or tokens. Budget thresholds gate execution cost at the spec level.

```text
budget_breach — max_tool_calls exceeded
```

## How You Debug Failures

Every failure comes with three tools:

| Tool | What it does | Command |
|---|---|---|
| **Witness** | Pinpoints the exact trace event where behavior diverged | Included in every report |
| **Repro** | Replays the exact failure deterministically | `python -m trajectly repro` |
| **Shrink** | Reduces the trace to the shortest proof (14 events -> 3) | `python -m trajectly shrink` |

No log hunting. No guesswork. No LLM calls for evaluation.

## Use This In Your Project

1. Add one `.agent.yaml` spec:

```yaml
schema_version: "0.4"
name: "my-agent"
command: "python -m my_agent.runner"
workdir: .
strict: true
fixture_policy: by_hash
contracts:
  config: contracts/my-agent.contracts.yaml
```

2. Add one `.contracts.yaml` policy:

```yaml
version: v1
tools:
  allow: [fetch_context, create_reply]
sequence:
  require: [fetch_context, create_reply]
```

3. Record, gate, debug:

```bash
python -m trajectly init
python -m trajectly record specs/my-agent.agent.yaml --project-root .
python -m trajectly run specs/my-agent.agent.yaml --project-root .
python -m trajectly report
python -m trajectly repro
python -m trajectly shrink
```

## CI Integration

Any CI:

```bash
pip install trajectly
python -m trajectly run specs/*.agent.yaml --project-root .
python -m trajectly report --pr-comment > trajectly_pr_comment.md
```

GitHub Actions:

```yaml
- uses: trajectly/trajectly-action@v1.0.1
  with:
    spec_glob: "specs/*.agent.yaml"
    project_root: "."
    comment_pr: "true"
```

When a spec fails, the PR gets a death report: witness index, violated contract, repro command, and shrink result.

See [trajectly-action](https://github.com/trajectly/trajectly-action) for full CI documentation.

## Try Merge or Die

Eight arena scenarios covering all six failure categories. Run them, break them, debug them.

[trajectly-survival-arena](https://github.com/trajectly/trajectly-survival-arena) | [trajectly.dev/merge-or-die](https://www.trajectly.dev/merge-or-die)

## Documentation

- [Guide](docs/trajectly_guide.md) -- onboarding, core concepts, TRT algorithm
- [What Trajectly Catches](docs/what_trajectly_catches.md) -- six failure categories with full examples
- [Contract Catalog](docs/contract_catalog.md) -- reference for all six contract dimensions
- [Reference](docs/trajectly_reference.md) -- CLI, spec schema, SDK, trace schema
- [CI: GitHub Actions](docs/ci_github_actions.md) -- action inputs, execution order, artifacts
- [Architecture (maintainers)](docs/architecture_phase1.md)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Apache 2.0 -- see [LICENSE](LICENSE).

## Community

- Questions/discussions: <https://github.com/trajectly/trajectly/discussions>
- Security reports (private): <https://github.com/trajectly/trajectly/security/advisories/new>
