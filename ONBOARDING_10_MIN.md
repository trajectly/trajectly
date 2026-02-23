# Trajectly 10-Minute Onboarding

This guide is the fastest path to prove Trajectly value in a fresh repo.

## Goal

In under 20 minutes, you will:

1. Enable Trajectly in your workspace.
2. Record a deterministic baseline.
3. Replay the same spec in offline mode.
4. Intentionally trigger a regression and see CI-style failure output.
5. Reproduce the failure with one command.

## Prerequisites

- Python 3.11+ installed.
- `uv` installed (`pipx install uv` or `brew install uv`).
- At least one `*.agent.yaml` spec in your repo, or use an auto template.

## Stopwatch Runbook

### Minute 0-2: Install and prepare

```bash
uv venv
source .venv/bin/activate
uv sync --extra dev
```

Success check:

- `trajectly --help` prints the CLI help.

### Minute 2-4: Enable workspace and scaffold starter files

```bash
trajectly enable --template openai
```

Success check:

- `.trajectly/` directories created.
- A starter `tests/sample.agent.yaml` is generated if no specs existed.

### Minute 4-6: Record baseline

```bash
trajectly record --auto
```

Success check:

- Exit code `0`.
- Baseline traces and fixtures written under `.trajectly/`.

### Minute 6-8: Replay deterministically

```bash
trajectly run tests/*.agent.yaml
```

Success check:

- Exit code `0` for unchanged behavior.
- Replay uses stored fixtures and offline network guard.

### Minute 8-12: Trigger regression and verify failure signal

Change agent behavior (tool output/order/arguments), then:

```bash
trajectly run tests/*.agent.yaml
```

Success check:

- Exit code `1`.
- Report generated under `.trajectly/reports/` with findings and first divergence.

### Minute 12-14: Reproduce with one command

```bash
trajectly repro
```

Success check:

- Repro command executes the latest failed spec.
- Repro artifacts exist under `.trajectly/repros/`.

### Minute 14-16: Review CI-friendly output

```bash
trajectly report --pr-comment
```

Success check:

- Markdown summary suitable for PR comments is printed.

## Definition of Done

Onboarding is complete when all conditions are true:

1. `enable` succeeded.
2. `record --auto` produced baseline artifacts.
3. `run` passed once with exit `0`.
4. `run` failed after intentional change with exit `1`.
5. `repro` reran the failing spec from generated artifacts.

## Common Fixes

- `No spec files matched targets`
  - Add a spec file such as `tests/sample.agent.yaml`, or run `trajectly enable --template openai`.
- `Cloud exporter` errors during local runs
  - Unset cloud env vars while onboarding locally:
    - `unset TRAJECTLY_CLOUD_API_BASE_URL TRAJECTLY_CLOUD_API_KEY`
- `run` stays clean after your intentional change
  - Ensure the changed behavior affects emitted tool/LLM events or contract checks.
