# CI: GitHub Actions

Trajectly ships a thin composite GitHub Action in `github-action/action.yml`. It installs Trajectly, runs the CLI, and optionally posts a PR comment and uploads artifacts. No TRT algorithm logic lives in the action.

## Minimal Workflow

```yaml
# .github/workflows/trajectly.yml
name: Agent Regression Tests
on: [push, pull_request]

jobs:
  trajectly:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: ./github-action
```

This uses all defaults: Python 3.11, editable install, specs from `specs/*.agent.yaml`, PR comment enabled, artifacts uploaded.

## Customized Workflow

```yaml
name: Agent Regression Tests
on:
  pull_request:
    branches: [main]

jobs:
  trajectly:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: ./github-action
        with:
          spec_glob: "tests/specs/*.agent.yaml"
          project_root: "."
          python_version: "3.12"
          install: "pypi"
          comment_pr: "true"
          upload_artifacts: "true"
```

## Action Inputs

| Input | Default | Description |
|-------|---------|-------------|
| `spec_glob` | `specs/*.agent.yaml` | Glob pattern for agent spec files |
| `project_root` | `.` | Root directory of the project |
| `python_version` | `3.11` | Python version to install |
| `install` | `editable` | `editable` (pip install -e .) or `pypi` (pip install trajectly) |
| `comment_pr` | `true` | Post a PR comment with the report summary |
| `upload_artifacts` | `true` | Upload `.trajectly/**` as build artifacts |

## What the Action Does

1. **Setup Python** via `actions/setup-python@v5`.
2. **Install Trajectly**: editable from the repo or from PyPI.
3. **Run specs**: `trajectly run <spec_glob> --project-root <project_root>`. Continues on error so the report step always runs.
4. **Generate report**: `trajectly report --pr-comment > trajectly_pr_comment.md`.
5. **Post PR comment** (if `comment_pr` is `true` and the event is a pull request): uses `actions/github-script@v7` to create or update a comment with a `<!-- trajectly-report -->` marker.
6. **Upload artifacts** (if `upload_artifacts` is `true`): uploads `.trajectly/**` via `actions/upload-artifact@v4`.
7. **Propagate exit code**: the workflow fails with the exit code from step 3 (0 = pass, 1 = regression, 2 = error).

## Generic CI (Any Provider)

If you are not using GitHub Actions, the equivalent shell commands are:

```bash
pip install trajectly
trajectly run specs/*.agent.yaml --project-root .
trajectly report --pr-comment > comment.md
# upload .trajectly/** as build artifacts per your CI provider
```

## Caching `.trajectly/`

The `.trajectly/` directory contains baselines, fixtures, and reports. You can cache it between runs to speed up repeated workflows:

```yaml
- uses: actions/cache@v4
  with:
    path: .trajectly
    key: trajectly-${{ hashFiles('specs/**') }}
    restore-keys: trajectly-
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | All specs passed |
| 1 | At least one regression detected |
| 2 | Configuration or tooling error |
