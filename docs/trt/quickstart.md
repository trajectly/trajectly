# Quickstart (10-20 Minutes)

## 1) Install

```bash
uv venv
source .venv/bin/activate
uv sync --extra dev
```

## 2) Enable Workspace

```bash
trajectly enable
```

`enable` initializes `.trajectly/`, creates starter spec scaffolding, and writes workflow templates.

## 3) Record Baseline

```bash
trajectly record --auto
```

This captures baseline traces and fixtures.

## 4) Run TRT Check

```bash
trajectly run tests/*.agent.yaml
```

Exit codes:

- `0` pass
- `1` TRT failure
- `2` config/tooling error

## 5) Reproduce Offline

```bash
TRAJECTLY_CI=1 trajectly repro --latest
```

## 6) Optional: Shrink Counterexample

```bash
trajectly shrink --max-seconds 10 --max-iterations 200
```

Shrinker v1 accepts reduced traces when:

- TRT still fails
- failure class remains unchanged

## 7) Optional: Migrate Legacy Spec

```bash
trajectly migrate spec tests/legacy.agent.yaml
```
