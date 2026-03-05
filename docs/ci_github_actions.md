# CI: GitHub Actions

Trajectly ships a thin composite action at `github-action/action.yml`.

It wraps CLI commands and CI plumbing only. TRT evaluation remains in Python code.

## Minimal workflow

```yaml
name: Agent Regression Tests
on: [push, pull_request]

jobs:
  trajectly:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: ./github-action
```

## Use from another repository

If you are not vendoring the action locally:

```yaml
- uses: trajectly/trajectly/github-action@main
  with:
    spec_glob: "specs/*.agent.yaml"
    project_root: "."
```

Recommendation:
- use a pinned ref (`@vX.Y.Z` or a commit SHA) for stable CI behavior
- use `@main` only when you intentionally want latest action changes

## Action inputs

| Input | Default | Meaning |
|---|---|---|
| `spec_glob` | `specs/*.agent.yaml` | Spec files/glob passed to `trajectly run` |
| `project_root` | `.` | Working directory for run/report steps |
| `python_version` | `3.11` | Python version installed via `actions/setup-python@v5` |
| `install` | `editable` | `editable` => `pip install -e <project_root>`; `pypi` => `pip install trajectly` |
| `comment_pr` | `true` | Post/update PR comment with report markdown (PR events only) |
| `upload_artifacts` | `true` | Upload `${project_root}/.trajectly/**` artifact |

## What the action executes

In order:

1. **Set up Python**
2. **Install Trajectly**
   - `install: pypi` -> `pip install trajectly`
   - otherwise -> `pip install -e "${project_root}"`
3. **Run specs** (continue-on-error enabled)
   - `trajectly run <spec_glob> --project-root .`
   - captures exit code into `${{ steps.run.outputs.exit_code }}`
4. **Generate PR comment markdown**
   - `trajectly report --pr-comment > trajectly_pr_comment.md 2>/dev/null || true`
5. **Post PR comment** (if `comment_pr == true` and event is `pull_request`)
6. **Upload artifacts** (if `upload_artifacts == true`)
7. **Propagate exit code**
   - final step exits with run step exit code

Observed run-step output cues from a fresh validation run (March 5, 2026):

```text
# passing run
- `trt-procurement-agent`: clean
  - trt: `PASS`

# failing run
- `trt-procurement-agent`: regression
  - trt: `FAIL` (witness=10)
Tip: run `python -m trajectly repro` to reproduce, or `python -m trajectly shrink` to minimize.
```

Observed PR comment markdown produced by `trajectly report --pr-comment`:

```text
### Trajectly Regression Report

- Specs processed: **1**
- Regressions: **1**
- Errors: **0**
```

## Exit codes

| Code | Meaning |
|---|---|
| `0` | All specs passed |
| `1` | Regression(s) detected |
| `2` | Config or tooling error |

## Equivalent shell flow (any CI)

```bash
python -m pip install trajectly
python -m trajectly run specs/*.agent.yaml --project-root .
python -m trajectly report --pr-comment > trajectly_pr_comment.md
```

Expected behavior:
- `run` exits `0` for clean runs, `1` for regressions, `2` for config/tooling errors.
- `trajectly_pr_comment.md` contains a markdown summary table for PR comments.

Upload `.trajectly/**` as artifacts with your CI provider.

Common artifact files to expect:
- `${project_root}/.trajectly/reports/latest.md`
- `${project_root}/.trajectly/reports/latest.json`
- `${project_root}/.trajectly/repros/*.json`

## Optional cache

Caching `.trajectly/` can speed repeated CI runs:

```yaml
- uses: actions/cache@v4
  with:
    path: .trajectly
    key: trajectly-${{ hashFiles('specs/**') }}
    restore-keys: trajectly-
```

## Standalone examples

- Support demo workflow:
  <https://github.com/trajectly/support-escalation-demo/blob/main/.github/workflows/trajectly.yml>
- Procurement demo workflow:
  <https://github.com/trajectly/procurement-approval-demo/blob/main/.github/workflows/trajectly.yml>
