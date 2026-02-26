# Phase 1 Architecture — Trajectly

## Current Structure (pre-Phase 1)

```
src/trajectly/
├── __init__.py              # __version__
├── __main__.py              # python -m trajectly
├── cli.py                   # Typer app + commands (init, record, run, repro, shrink, report, baseline update, migrate spec)
├── engine.py                # Orchestration: record_specs, run_specs, shrink_repro
├── engine_common.py         # Shared state paths, CommandOutcome
├── abstraction/             # Trace abstraction pipeline + predicates
├── canonical.py             # Canonical JSON normalization
├── constants.py             # Shared constants (dirs, exit codes, versions)
├── contracts.py             # Contract evaluation engine
├── diff/                    # Trace diffing (LCS, structural, models)
├── errors.py                # Error types, FailureClass
├── events.py                # TraceEvent model, JSONL I/O
├── fixtures.py              # Fixture capture/replay
├── normalize/               # Normalizer (canonical + version)
├── plugins/                 # Plugin system (cloud exporter, interfaces, loader)
├── redaction.py             # PII/secret redaction
├── refinement/              # Skeleton extraction + refinement checker
├── replay_guard.py          # Socket monkey-patch for deterministic replay
├── report/                  # Report schema (data models) + renderers (markdown/json)
├── runtime.py               # Subprocess execution of agent commands
├── schema.py                # Report JSON validation
├── sdk/                     # Developer SDK (adapters, context, decorators)
├── shrink/                  # Delta-debugging trace minimization
├── specs/                   # Agent spec parser (v0.3, migration, compat)
├── trace/                   # Trace I/O, metadata, models, validation
├── trt/                     # TRT runner, witness resolution, violation types
└── benchmark.py             # Benchmark utilities
```

55 Python modules. Flat layout with `sdk/` as only intentional sub-package.

### Problems

1. **No boundary enforcement** — `engine.py` mixes CLI orchestration with core
   algorithm imports. Nothing prevents core modules from importing `typer`/`rich`.
2. **Version mismatch** — `pyproject.toml` says `0.3.0rc2`, `__init__.py` says `0.3.0rc1`.
3. **No store abstraction** — baselines and artifacts are always local filesystem;
   hard to extend to remote storage.
4. **No spec inheritance** — every spec is standalone, no `extends` mechanism.
5. **Entrypoint coupling** — `trajectly.cli:app` points at a flat module, not a package.

---

## Target Structure (Phase 1)

```
src/trajectly/
├── __init__.py              # __version__ = "0.3.0rc3"
├── __main__.py              # python -m trajectly (unchanged)
├── core/
│   ├── __init__.py          # Re-exports key symbols
│   ├── abstraction/         # (moved from trajectly.abstraction)
│   ├── canonical.py         # (moved)
│   ├── constants.py         # (moved)
│   ├── contracts.py         # (moved)
│   ├── diff/                # (moved)
│   ├── errors.py            # (moved)
│   ├── events.py            # (moved)
│   ├── fixtures.py          # (moved)
│   ├── normalize/           # (moved)
│   ├── redaction.py         # (moved)
│   ├── refinement/          # (moved)
│   ├── replay_guard.py      # (moved)
│   ├── report/
│   │   ├── __init__.py
│   │   └── schema.py        # Report data models only (ViolationV03, TRTReportV03, etc.)
│   ├── runtime.py           # (moved)
│   ├── schema.py            # (moved)
│   ├── shrink/              # (moved)
│   ├── specs/               # (moved)
│   ├── stores/
│   │   ├── __init__.py
│   │   ├── artifacts.py     # ArtifactStore protocol + LocalArtifactStore
│   │   └── baselines.py     # BaselineStore protocol + LocalBaselineStore
│   ├── trace/               # (moved)
│   ├── trt/                 # (moved)
│   └── benchmark.py         # (moved)
├── cli/
│   ├── __init__.py          # Re-exports `app` for entrypoint
│   ├── app.py               # (moved from trajectly.cli — Typer commands)
│   ├── engine.py            # (moved from trajectly.engine — orchestration)
│   ├── engine_common.py     # (moved from trajectly.engine_common — state paths)
│   └── report/
│       ├── __init__.py
│       └── renderers.py     # (moved from trajectly.report.renderers)
├── sdk/                     # (unchanged)
│   ├── __init__.py
│   ├── adapters.py
│   └── context.py
└── plugins/                 # (unchanged — cross-cutting)
    ├── __init__.py
    ├── cloud_exporter.py
    ├── interfaces.py
    └── loader.py
```

### Layer rules

| Layer | May import | Must NOT import |
|-------|-----------|-----------------|
| `core` | stdlib, PyYAML | typer, rich, click, cli, sdk, plugins |
| `cli` | core, sdk, plugins, typer, PyYAML | — |
| `sdk` | core | typer, rich, click, cli, plugins |
| `plugins` | core, sdk | typer, rich, click, cli |

---

## Migration / Compatibility

### Shim strategy (one release cycle)

Every moved module keeps a **thin re-export shim** at its original path so that all
existing `from trajectly.X import Y` imports continue to work:

**File shims** (e.g. `contracts.py`):
```python
from trajectly.core.contracts import *  # noqa: F401,F403
```

**Package shims** (e.g. `abstraction/`):
```python
# abstraction/__init__.py
from trajectly.core.abstraction import *  # noqa: F401,F403
import trajectly.core.abstraction as _pkg  # noqa: F401
__path__ = _pkg.__path__
```

The `__path__` override ensures sub-module imports like
`from trajectly.abstraction.pipeline import X` still resolve correctly.

### Entrypoint

`pyproject.toml` entrypoint stays `trajectly.cli:app`. After the move,
`trajectly.cli` is a package whose `__init__.py` re-exports `app` from
`trajectly.cli.app`.

### What changes for users

**Nothing.** All CLI commands, flags, exit codes, spec formats, and on-disk
layouts remain identical. Internal import paths gain new `trajectly.core.*` /
`trajectly.cli.*` alternatives. Old paths work via shims for one release.

---

## New features in Phase 1

### Store interfaces (`core/stores/`)

- `ArtifactStore` protocol: `put_bytes`, `put_file`, `get_bytes`, `list_keys`
- `BaselineStore` protocol: `resolve`, `write`, `list_baselines`
- `LocalArtifactStore` / `LocalBaselineStore` implementations wrapping existing
  `.trajectly/` filesystem layout
- Wired into `cli/engine.py` orchestration

### Spec `extends` (file-based)

```yaml
extends: ./base.agent.yaml
name: my-variant
contracts:
  tool_policy:
    deny: [unsafe_tool]
```

Deterministic merge: dicts deep-merge recursively, lists override, scalars override.
Schema version stays `0.3`.

### GitHub Action wrapper (`github-action/action.yml`)

Thin composite action: setup Python, install trajectly, `trajectly run`, post PR
comment, upload artifacts. No TRT logic in the action.
