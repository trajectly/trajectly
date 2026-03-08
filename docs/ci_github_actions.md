# CI: GitHub Actions

The canonical Trajectly GitHub Action is:
`trajectly/trajectly-action@v1.0.1`

It wraps CLI commands and CI plumbing only. TRT evaluation remains in Python code.
The in-repo action path `./github-action` is kept as a temporary compatibility wrapper and is planned for removal in `v0.4.3` (one release cycle after `v0.4.2`).

## Minimal workflow

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

## Use from another repository

If your workflow runs on pull requests and you want comment updates:

```yaml
- uses: trajectly/trajectly-action@v1.0.1
  with:
    spec_glob: "specs/challenges/*.agent.yaml"
    project_root: "."
    comment_pr: "true"
```

Recommendation:
- use a pinned ref (`@vX.Y.Z` or a commit SHA) for stable CI behavior
- use `@v1` if you prefer stable major-line updates (`v1 -> latest v1.x.y`)

## Action inputs

| Input | Default | Meaning |
|---|---|---|
| `spec_glob` | `specs/*.agent.yaml` | Spec files/glob passed to `trajectly run` |
| `project_root` | `.` | Working directory for run/report steps |
| `python_version` | `3.11` | Python version installed via `actions/setup-python` |
| `trajectly_version` | `0.4.2` | Trajectly package version used when `install: pypi` |
| `install` | `pypi` | `editable` => `pip install -e <project_root>`; `pypi` => `pip install trajectly==<trajectly_version>` |
| `comment_pr` | `false` | Post/update PR comment with report markdown (PR events only) |
| `upload_artifacts` | `true` | Upload `${project_root}/.trajectly/**` artifact |

Compatibility note:
- The deprecated wrapper `./github-action` keeps older defaults (`install=editable`, `comment_pr=true`) to avoid breaking existing workflows.

## What the action executes

In order:

1. **Set up Python**
2. **Install Trajectly**
   - `install: pypi` -> `pip install trajectly==<trajectly_version>`
   - otherwise -> `pip install -e "${project_root}"`
3. **Run specs** (continue-on-error enabled)
   - `trajectly run <spec_glob> --project-root .`
   - captures exit code into `${{ steps.run.outputs.exit_code }}`
4. **Generate PR comment markdown**
   - `trajectly report --pr-comment > trajectly_pr_comment.md 2>/dev/null || true`
5. **Post PR comment** (if `comment_pr == true` and event is `pull_request`)
   - Requires workflow permission: `pull-requests: write`
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
python -m trajectly run specs/challenges/*.agent.yaml --project-root .
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

Replace `specs/challenges/*.agent.yaml` with your repository's spec path/glob.

## Optional cache

Caching `.trajectly/` can speed repeated CI runs:

```yaml
- uses: actions/cache@v4
  with:
    path: .trajectly
    key: trajectly-${{ hashFiles('specs/**') }}
    restore-keys: trajectly-
```

## Examples

- Arena CI workflows:
  <https://github.com/trajectly/trajectly-survival-arena/tree/main/.github/workflows>
- Action fixture workflows:
  <https://github.com/trajectly/trajectly-action-fixture/tree/main/.github/workflows>

For CLI/spec details, use [Trajectly Reference](trajectly_reference.md).
