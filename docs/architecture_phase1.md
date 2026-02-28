# Phase 1 Architecture — Trajectly

> This document describes the **current** (completed) architecture after the Phase 1 refactor.

## Package Layout

```
src/trajectly/
├── __init__.py              # __version__ = "0.4.0"
├── __main__.py              # python -m trajectly
├── core/
│   ├── __init__.py
│   ├── abstraction/         # Trace abstraction pipeline + predicates
│   ├── canonical.py         # Canonical JSON normalization (re-export)
│   ├── constants.py         # Schema versions, failure classes, exit codes, state dirs
│   ├── contracts.py         # Contract monitor evaluation engine
│   ├── diff/                # Trace comparison (LCS, structural diff, models)
│   ├── errors.py            # Error types, FailureClass
│   ├── events.py            # TraceEvent model, JSONL I/O
│   ├── fixtures.py          # FixtureStore / FixtureMatcher for replay
│   ├── normalize/           # Canonical normalizer + version constant
│   ├── redaction.py         # Regex-based PII/secret redaction
│   ├── refinement/          # Skeleton extraction + subsequence checker
│   ├── replay_guard.py      # Socket/requests monkey-patch for offline replay
│   ├── report/
│   │   └── schema.py        # Report data models (ViolationV03, TRTReportV03)
│   ├── runtime.py           # Subprocess execution of agent commands
│   ├── schema.py            # Trace/report JSON schema validation
│   ├── shrink/              # Delta-debugging trace minimization
│   ├── specs/               # Spec parser (v0.4, v0.2 compat, migration, extends)
│   ├── stores/
│   │   ├── artifacts.py     # ArtifactStore protocol + LocalArtifactStore
│   │   └── baselines.py     # BaselineStore protocol + LocalBaselineStore
│   ├── trace/               # Trace I/O, metadata, models, validation
│   └── trt/                 # TRT runner, violation types, witness resolution
├── cli/
│   ├── __init__.py          # Lazy re-export of `app` via __getattr__
│   ├── commands.py          # Typer app + all CLI commands
│   ├── engine.py            # Orchestration: record_specs, run_specs, shrink_repro
│   ├── engine_common.py     # Shared state paths, CommandOutcome
│   ├── benchmark.py         # Performance benchmark harness
│   └── report/
│       └── renderers.py     # Markdown / PR-comment / JSON report rendering
├── sdk/
│   ├── __init__.py
│   ├── adapters.py          # Framework adapters (OpenAI, Gemini, etc.)
│   └── context.py           # SDKContext: event emission + fixture replay
├── plugins/                 # Cross-cutting (stays at top level)
│   ├── cloud_exporter.py
│   ├── interfaces.py
│   └── loader.py
├── *.py (shims)             # Thin re-export shims at old import paths
└── github-action/
    └── action.yml           # Composite GitHub Action wrapper
```

## Layer Rules

| Layer | May import | Must NOT import |
|-------|-----------|-----------------|
| `core` | stdlib, PyYAML | typer, rich, click, cli, sdk, plugins |
| `cli` | core, sdk, plugins, typer, rich | — |
| `sdk` | core | typer, rich, click, cli, plugins |
| `plugins` | core, sdk | typer, rich, click, cli |

Boundary enforcement is tested in `tests/unit/test_boundary_enforcement.py` using AST analysis.

## Entrypoint

`pyproject.toml` scripts entrypoint: `trajectly = "trajectly.cli.commands:app"`

`cli/__init__.py` uses `__getattr__` to lazily re-export `app` from `cli/commands.py`, breaking circular imports when other modules do `from trajectly.cli import app`.

## Compatibility Shims

Every module that moved to `core/` or `cli/` has a thin re-export shim at its original path:

```python
# src/trajectly/contracts.py (shim)
from trajectly.core.contracts import *  # noqa: F403
```

Package shims (directories like `abstraction/`, `trace/`, etc.) have per-submodule shim files that explicitly re-export from `trajectly.core.*`. This ensures `isinstance` checks work correctly across both import paths.

`replay_guard.py` uses `sys.modules` aliasing so that `monkeypatch` in tests affects both the shim and core module:

```python
import trajectly.core.replay_guard as _mod
sys.modules[__name__] = _mod
```

Shims will be retained for one release cycle.

## Store Interfaces

`core/stores/artifacts.py`:
- `ArtifactStore` protocol: `put_bytes`, `put_file`, `get_bytes`, `list_keys`
- `LocalArtifactStore`: wraps `.trajectly/{reports,repros}/` filesystem layout

`core/stores/baselines.py`:
- `BaselineStore` protocol: `resolve`, `write`, `list_baselines`
- `LocalBaselineStore`: wraps `.trajectly/baselines/` + `fixtures/` layout

## Spec `extends`

Specs can inherit from a base spec using deterministic deep-merge:

```yaml
extends: ./base.agent.yaml
name: my-variant
contracts:
  tools:
    deny: [unsafe_tool]
```

Merge rules: dicts merge recursively (keys iterated in `sorted()` order), lists override, scalars override. Max chain depth: 10 (circular reference detection). Schema version stays `0.4`.

## GitHub Action Wrapper

`github-action/action.yml` is a composite action with no TRT logic:

1. `actions/setup-python` -- install Python
2. `python -m pip install` -- editable or PyPI
3. `python -m trajectly run` -- run specs
4. `python -m trajectly report --pr-comment` -- generate markdown
5. `actions/github-script` -- post/update PR comment
6. `actions/upload-artifact` -- upload `.trajectly/**`
7. Propagate exit code from step 3
