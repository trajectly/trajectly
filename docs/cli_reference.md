# CLI Reference

This page documents the current Trajectly CLI used for record, replay, repro, and shrink workflows.

---

## Command Index

- `trajectly init`
- `trajectly enable`
- `trajectly record`
- `trajectly run`
- `trajectly repro`
- `trajectly shrink`
- `trajectly report`
- `trajectly baseline update`
- `trajectly migrate spec`

---

## `trajectly init [project_root]`

Initializes `.trajectly/` workspace directories and starter state.

Example:

```bash
trajectly init
```

---

## `trajectly enable [project_root] [--template TEMPLATE]`

Enables workspace scaffolding and spec discovery hints.

Supported templates:

- `openai`
- `langchain`
- `autogen`

Examples:

```bash
trajectly enable
trajectly enable . --template openai
```

---

## `trajectly record [targets...] [--project-root PATH] [--auto] [--allow-ci-write]`

Records baseline traces and fixture bundles.

Writes:

- `.trajectly/baselines/*.jsonl`
- `.trajectly/fixtures/*.json`

Examples:

```bash
trajectly record specs/trt-support-triage-baseline.agent.yaml
trajectly record --auto
trajectly record specs/trt-support-triage-baseline.agent.yaml --allow-ci-write
```

---

## `trajectly run <targets...> [--project-root PATH] [--baseline-dir PATH] [--fixtures-dir PATH] [--strict|--no-strict]`

Runs replay checks against recorded artifacts and emits reports.

Examples:

```bash
trajectly run specs/trt-support-triage-baseline.agent.yaml
trajectly run specs/trt-support-triage-regression.agent.yaml --strict
```

---

## `trajectly repro [selector] [--project-root PATH] [--strict|--no-strict] [--print-only]`

Reproduces the latest failing spec (or selected spec) with one deterministic command.

Selector options:

- `latest` (default)
- spec name/slug from latest report
- explicit spec path

Examples:

```bash
trajectly repro --print-only
trajectly repro
trajectly repro trt-code-review-bot
```

---

## `trajectly shrink [selector] [--project-root PATH] [--max-seconds N] [--max-iterations N]`

Attempts to minimize a failing counterexample while preserving failure class.

Examples:

```bash
trajectly shrink --latest
trajectly shrink trt-code-review-bot --max-seconds 20 --max-iterations 500
```

---

## `trajectly report [--project-root PATH] [--json] [--pr-comment]`

Prints latest aggregate report.

Examples:

```bash
trajectly report
trajectly report --json
trajectly report --pr-comment
```

---

## `trajectly baseline update [targets...] [--project-root PATH] [--auto] [--allow-ci-write]`

Explicitly updates baselines by re-recording selected specs.

Examples:

```bash
trajectly baseline update specs/trt-code-review-bot-baseline.agent.yaml
trajectly baseline update --auto
```

Use only when behavior changes are intentional and approved.

---

## `trajectly migrate spec <spec_path> [--output PATH] [--in-place]`

Converts legacy spec format to v0.3 format.

Examples:

```bash
trajectly migrate spec tests/legacy.agent.yaml --output tests/legacy.v03.agent.yaml
trajectly migrate spec tests/legacy.agent.yaml --in-place
```

---

## Exit Codes

- `0`: success / no regression
- `1`: regression detected
- `2`: internal, tooling, or spec error

---

## Common Workflows

### First-time setup

```bash
trajectly init
trajectly record specs/trt-support-triage-baseline.agent.yaml
trajectly run specs/trt-support-triage-baseline.agent.yaml
```

### CI regression gate

```bash
trajectly run specs/*.agent.yaml
```

### Failure triage

```bash
trajectly report
trajectly repro
trajectly shrink --latest
```

### Intentional behavior update

```bash
trajectly baseline update specs/trt-support-triage-baseline.agent.yaml
trajectly run specs/trt-support-triage-baseline.agent.yaml
```
