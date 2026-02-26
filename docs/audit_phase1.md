# Phase 1 Audit Report

**Date**: 2026-02-26
**Scope**: Full repo-wide inspection of the Phase 1 architecture refactor.
**Verdict**: **MATCHES PHASE 1** (minor documentation/CLI polish items fixed in the same commit series).

---

## A1. Repository Structure

### `src/trajectly/core/` (deterministic engine)

| Module | Purpose |
|--------|---------|
| `abstraction/` | Trace abstraction pipeline, PII/domain predicates |
| `canonical.py` | Re-exports canonical normalization |
| `constants.py` | Schema versions, failure classes, exit codes, state dirs |
| `contracts.py` | Contract monitor evaluation |
| `diff/` | Trace comparison engine (LCS, structural diff, models) |
| `errors.py` | Error types and codes |
| `events.py` | TraceEvent model, JSONL I/O |
| `fixtures.py` | FixtureStore / FixtureMatcher for replay |
| `normalize/` | Canonical normalizer, version constant |
| `redaction.py` | Regex-based PII redaction |
| `refinement/` | Skeleton extraction, subsequence refinement checker |
| `replay_guard.py` | Socket/requests monkey-patch for offline replay |
| `report/schema.py` | TRT report v0.3 data models (ViolationV03, TRTReportV03) |
| `runtime.py` | Subprocess execution of agent commands |
| `schema.py` | Trace/report schema validation |
| `shrink/` | Delta-debugging minimization |
| `specs/` | Spec parser (v0.3, v0.2 compat, migration, `extends`) |
| `stores/` | ArtifactStore + BaselineStore protocols and local implementations |
| `trace/` | Trace I/O, metadata, models, validation |
| `trt/` | TRT runner, violation types, witness resolution |

### `src/trajectly/cli/` (Typer commands + orchestration)

| Module | Purpose |
|--------|---------|
| `commands.py` | Typer app: init, enable, record, run, repro, shrink, report, baseline update, migrate spec |
| `engine.py` | Orchestration: record_specs, run_specs, shrink_repro |
| `engine_common.py` | Shared state paths, CommandOutcome |
| `benchmark.py` | Performance benchmark harness |
| `report/renderers.py` | Markdown / PR-comment / JSON report rendering |

### `src/trajectly/sdk/` (instrumentation)

| Module | Purpose |
|--------|---------|
| `adapters.py` | Framework adapters (OpenAI, Gemini, etc.) |
| `context.py` | SDKContext for event emission and fixture replay |

### `src/trajectly/plugins/` (cross-cutting, top-level)

| Module | Purpose |
|--------|---------|
| `cloud_exporter.py` | Cloud run hook exporter |
| `interfaces.py` | Plugin protocol definitions |
| `loader.py` | Entry-point based plugin loading |

### Compatibility shims (`src/trajectly/*.py`)

All top-level `.py` files outside `core/`, `cli/`, `sdk/`, and `plugins/` are thin re-export shims that forward to `trajectly.core.*` or `trajectly.cli.*`. These preserve old import paths for one release cycle.

---

## A2. Boundary Checks

### core: forbidden imports

```
grep pattern: typer|rich|click|github|requests
scope:        src/trajectly/core/**/*.py
result:       ZERO violations
```

Note: `core/replay_guard.py` uses `importlib.import_module("requests")` for dynamic patching at runtime, not a static import. Acceptable.

### sdk: forbidden imports

```
grep pattern: typer|rich|click|trajectly\.cli
scope:        src/trajectly/sdk/**/*.py
result:       ZERO violations
```

### Verdict: PASS

---

## A3. CLI Surface

Commands enumerated from `src/trajectly/cli/commands.py`:

| Command | Key flags |
|---------|-----------|
| `init` | `project_root` |
| `enable` | `--template {openai,langchain,autogen}` |
| `record` | `--project-root`, `--auto`, `--allow-ci-write` |
| `run` | `--project-root`, `--baseline-dir`, `--fixtures-dir`, `--strict/--no-strict` |
| `repro` | `--project-root`, `--strict/--no-strict`, `--print-only` |
| `shrink` | `--project-root`, `--max-seconds`, `--max-iterations` |
| `report` | `--project-root`, `--json`, `--pr-comment` |
| `baseline update` | `--project-root`, `--auto`, `--allow-ci-write` |
| `migrate spec` | `--output`, `--in-place` |

Exit codes: `EXIT_SUCCESS=0`, `EXIT_REGRESSION=1`, `EXIT_INTERNAL_ERROR=2` (in `core/constants.py`).

**Gap found**: `--version` flag was missing. Fixed in this commit series.

### Verdict: PASS (after fix)

---

## A4. Spec + Workspace Compatibility

- **Schema v0.3**: Supported. Parser accepts `"0.3"` and `"v0.3"`. Unknown keys ignored via `.get()`.
- **Spec `extends`**: Implemented in `core/specs/__init__.py` with deterministic deep-merge (`sorted(overlay)` iteration). Max chain depth = 10 (cycle detection).
- **`.trajectly/` layout**: Unchanged. Subdirectories: `baselines/`, `current/`, `fixtures/`, `reports/`, `repros/`, `tmp/`.
- **Store interfaces**: `ArtifactStore` and `BaselineStore` protocols in `core/stores/` with `LocalArtifactStore` and `LocalBaselineStore` implementations wrapping existing filesystem layout.

### Verdict: PASS

---

## A5. Determinism Checks

### Canonical JSON

`core/normalize/canonical.py` line 74:
```python
json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
```
Keys also pre-sorted during normalization via `sorted(value.keys(), key=str)`.

### Witness resolution

`core/trt/witness.py`:
- Witness index: `min(violation.event_index for violation in violations)`
- Tie-break: `sort(key=lambda v: (_class_rank(v.failure_class), v.code))`
- Class rank order: REFINEMENT < CONTRACT < TOOLING (defined in `core/constants.py`)

### Set / dict iteration

All `set()` uses in `core/` are either membership-only checks or sorted before iteration. No nondeterministic ordering found. Examples:
- `core/abstraction/pipeline.py`: `predicates["domains"] = sorted(domains)`
- `core/specs/compat_v02.py`: `sorted(set(tools_allow).intersection(tools_deny))`
- `core/diff/structural.py`: `keys = sorted(set(...) | set(...))`
- `core/specs/__init__.py`: `deep_merge` iterates `sorted(overlay)`

### Verdict: PASS

---

## A6. GitHub Action

Location: `github-action/action.yml`

| Input | Default |
|-------|---------|
| `spec_glob` | `specs/*.agent.yaml` |
| `project_root` | `.` |
| `python_version` | `3.11` |
| `install` | `editable` |
| `comment_pr` | `true` |
| `upload_artifacts` | `true` |

Steps: setup-python, install, `trajectly run`, `trajectly report --pr-comment`, post PR comment (actions/github-script), upload artifacts (actions/upload-artifact), propagate exit code.

No TRT/algorithm logic in the action.

### Verdict: PASS

---

## A7. Test Coverage

281 tests pass across 44 test files.

### Determinism tests

| Test file | What it covers |
|-----------|---------------|
| `test_determinism_witness.py` | Witness selection: single, earliest, tie-break stability, repeated calls |
| `test_canonical_stability.py` | Sorted keys, nested sort, hash stability, no whitespace variance |
| `test_determinism_replay.py` | Repeat-run TRT payload identity, network blocking |
| `test_canonical.py` | Canonical serialization stability, sha256 subset |
| `test_normalize_canonical.py` | Normalizer determinism across repeated runs |

### Architecture tests

| Test file | What it covers |
|-----------|---------------|
| `test_boundary_enforcement.py` | Core has no typer/rich/click; SDK has no CLI imports |
| `test_spec_extends.py` | Single/chained extends, circular detection, deep-merge determinism |
| `test_cli_smoke.py` | init, record, run, report (json + pr-comment), help, exit codes |

### Gaps fixed in this series

- `--version` flag smoke test added
- Spec discovery ordering determinism test added

### Verdict: PASS

---

## Final Verdict

**MATCHES PHASE 1.** All architectural boundaries, determinism properties, CLI surface, GitHub Action wrapper, and compatibility guarantees are in place. Documentation and minor CLI polish gaps fixed in the accompanying commits.
