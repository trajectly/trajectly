# Trajectly

[![CI](https://github.com/trajectly/trajectly/actions/workflows/ci.yml/badge.svg)](https://github.com/trajectly/trajectly/actions/workflows/ci.yml)
[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/trajectly/trajectly/badge)](https://securityscorecards.dev/viewer/?uri=github.com/trajectly/trajectly)
[![PyPI version](https://img.shields.io/pypi/v/trajectly.svg)](https://pypi.org/project/trajectly/)

Trajectly is deterministic regression testing for AI agents.

It catches behavior regressions that output-only checks often miss:
- missing required tool calls
- wrong call order
- denied network/tool usage
- argument and budget-policy violations

Trajectly reports a deterministic witness index and a reproducible failing command.

## Install

```bash
python -m pip install trajectly
python -m trajectly --version
```

## 30-Second Quickstart

Use arena scenarios with committed fixtures (no API keys required):

```bash
git clone https://github.com/trajectly/trajectly-survival-arena.git
cd trajectly-survival-arena
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m trajectly init

# baseline behavior (expected PASS)
python -m trajectly run specs/challenges/procurement-chaos.agent.yaml --project-root .

# intentional regression behavior (expected FAIL)
python -m trajectly run specs/examples/procurement-chaos-regression.agent.yaml --project-root .
python -m trajectly report
python -m trajectly repro
python -m trajectly shrink
```

Expected exits for this flow:
- safe `run` -> `0`
- regression `run` -> `1`
- `report` -> `0`
- `repro` -> `1`
- `shrink` -> `0`

Stable output cues:

```text
# safe run
- `procurement-chaos`: clean
  - trt: `PASS`

# regression run
- `procurement-chaos`: regression
  - trt: `FAIL` (witness=...)

# report
Source: $PROJECT_ROOT/.trajectly/reports/latest.md
```

The canonical onboarding flow lives in [docs/trajectly_guide.md](docs/trajectly_guide.md).

## What Trajectly Checks

1. Contracts: tools, sequence, network, data leak, args, budgets.
2. Refinement: baseline tool-call skeleton remains a subsequence of current behavior.
3. Witness resolution: earliest failing trace event index.

## Use This In Your Project

Minimal migration recipe:

1. Make your agent command deterministic enough to replay.
2. Add one `.agent.yaml` spec.
3. Add one contract policy.
4. Record baseline.
5. Gate with `run`.
6. Debug with `report`, `repro`, `shrink`.

Starter files:

```yaml
# specs/my-agent.agent.yaml
schema_version: "0.4"
name: "my-agent"
command: "python -m my_agent.runner"
workdir: .
strict: true
fixture_policy: by_hash
contracts:
  config: contracts/my-agent.contracts.yaml
```

```yaml
# contracts/my-agent.contracts.yaml
tools:
  allow: [fetch_context, create_reply]
sequence:
  require: [fetch_context, create_reply]
```

Baseline and gate commands:

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
python -m pip install trajectly
python -m trajectly run specs/challenges/*.agent.yaml --project-root .
python -m trajectly report --pr-comment > trajectly_pr_comment.md
```

GitHub Actions:

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
          spec_glob: "specs/challenges/*.agent.yaml"
          project_root: "."
```

Replace `specs/challenges/*.agent.yaml` with your own spec glob/path in your project.

## Documentation

- [Guide](docs/trajectly_guide.md)
- [Reference](docs/trajectly_reference.md)
- [CI: GitHub Actions](docs/ci_github_actions.md)
- [Architecture (maintainers)](docs/architecture_phase1.md)
- [Security policy](SECURITY.md)
- [Contributing guide](CONTRIBUTING.md)
- [Merge or Die Arena](https://github.com/trajectly/trajectly-survival-arena)

## Contributing

For contribution flow and local checks, see [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Apache 2.0 -- see [LICENSE](LICENSE).

## Community

- Questions/discussions: <https://github.com/trajectly/trajectly/discussions>
- Security reports (private): <https://github.com/trajectly/trajectly/security/advisories/new>
