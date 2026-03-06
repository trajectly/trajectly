# Phase 1 Architecture - Trajectly

This document describes the current architecture on `main`.

Use this document when you need to:
1. understand module boundaries before changing code,
2. add a new CLI/runtime capability without crossing layers,
3. confirm where a behavior belongs (`core`, `cli`, `sdk`, or `plugins`).

## Package Layout

```text
src/trajectly/
|-- __init__.py              # public exports: __version__, App
|-- __main__.py              # python -m trajectly entrypoint
|-- core/
|   |-- abstraction/         # trace abstraction pipeline
|   |-- canonical.py         # canonical JSON hashing/normalization helpers
|   |-- constants.py         # schema versions, event types, exit codes, state dirs
|   |-- contracts.py         # contract evaluation engine
|   |-- diff/                # trace diff models/algorithms
|   |-- errors.py            # typed failures and failure classes
|   |-- events.py            # trace event model + JSONL I/O
|   |-- fixtures.py          # fixture store/matcher for replay
|   |-- normalize/           # canonical normalizer
|   |-- redaction.py         # payload redaction
|   |-- refinement/          # skeleton extraction and refinement checks
|   |-- replay_guard.py      # replay-mode network guard
|   |-- report/schema.py     # report models
|   |-- runtime.py           # subprocess execution model for specs
|   |-- schema.py            # trace/report schema validators
|   |-- shrink/              # ddmin counterexample shrinking
|   |-- specs/               # spec parsing, migration, extends deep-merge
|   |-- stores/              # baseline and artifact store protocols/impls
|   |-- trace/               # trace io/meta/models
|   \-- trt/                # TRT runner + witness resolution
|-- cli/
|   |-- commands.py          # Typer command surface
|   |-- engine.py            # orchestration for record/run/repro/shrink/baselines
|   |-- engine_common.py     # shared command helpers and paths
|   |-- benchmark.py         # benchmark harness
|   \-- report/renderers.py  # markdown/pr-comment/json output
|-- sdk/
|   |-- __init__.py          # decorators + graph exports
|   |-- context.py           # SDKContext event emission + fixture replay
|   |-- adapters.py          # OpenAI/Gemini/LangChain/etc wrappers
|   \-- graph.py             # declarative App DAG registration/execution
|-- plugins/
|   |-- interfaces.py
|   \-- loader.py
\-- github-action/
    \-- action.yml          # deprecated compatibility wrapper -> trajectly/trajectly-action@v1 (planned removal in v0.4.3)
```

## Layer Boundaries

| Layer | Allowed imports | Not allowed |
|---|---|---|
| `core` | stdlib, PyYAML | `cli`, `sdk`, Typer, Rich |
| `cli` | `core`, `sdk`, `plugins`, Typer, Rich | n/a |
| `sdk` | `core` | `cli`, Typer, Rich |
| `plugins` | `core`, `sdk` | `cli`, Typer, Rich |

Boundary checks are enforced by tests (AST-based import rules).

## Execution Flow

### CLI-driven execution

1. `python -m trajectly run ...` loads specs and resolves project paths.
2. `core/runtime.py` executes each spec command in a subprocess with `TRAJECTLY_*` env wiring.
3. Agent code emits events through SDK instrumentation.
4. TRT compares baseline vs current traces and computes a deterministic verdict.
5. CLI renders reports and exits with `0` (pass), `1` (regression), or `2` (internal/config error).

### Declarative graph SDK flow

`App.run()` (in `sdk/graph.py`) executes a validated DAG in deterministic topological order and routes instrumentation through `SDKContext`:

`App.run -> SDKContext.invoke_tool/invoke_llm/agent_step -> trace events -> existing core TRT pipeline`

This means graph-based agents and decorator-based agents share the same replay, fixture, and report semantics.

## SDK Instrumentation Model

`SDKContext` is the single runtime instrumentation boundary:

1. Emits `tool_called` / `tool_returned`.
2. Emits `llm_called` / `llm_returned`.
3. Emits `agent_step` markers.
4. Replays from fixtures in replay mode (strict behavior enforced by runtime settings).

No separate event schema exists for graph mode.

## Compatibility Shims

Legacy import-path shims remain for modules moved under `core/` and `cli/`.

Example:

```python
from trajectly.core.contracts import *  # noqa: F403
```

Shims are retained for compatibility while imports migrate to canonical paths.

## Spec Inheritance (`extends`)

Specs support deterministic deep-merge inheritance:

- dicts merge recursively
- lists and scalars override
- max chain depth protects against cycles

This enables a shared base policy with per-agent overrides.

## Storage Interfaces

`core/stores` defines protocol boundaries:

- `ArtifactStore` / `LocalArtifactStore`
- `BaselineStore` / `LocalBaselineStore`

These isolate filesystem layout concerns from higher-level orchestration.

## GitHub Action Boundary

Canonical action behavior lives in `trajectly/trajectly-action`.

`github-action/action.yml` in this repository is a compatibility wrapper that delegates to that canonical action.

The action boundary remains intentionally thin:

1. setup Python
2. install Trajectly (`editable` or `pypi`)
3. run specs
4. generate PR comment markdown
5. optionally post comment
6. optionally upload `.trajectly/**`
7. propagate run exit code

All TRT logic remains in Python packages, not in workflow YAML.

## Where to extend

Common change types and their primary edit locations:

1. New CLI command or flag:
   - `cli/commands.py` for Typer surface
   - `cli/engine.py` for orchestration
   - `cli/report/renderers.py` only if output format changes
2. New contract rule or TRT check:
   - `core/contracts.py` or `core/trt/`
   - add/adjust report schema in `core/report/schema.py` if new fields are emitted
3. New instrumentation adapter:
   - `sdk/adapters.py`
   - ensure events still map to existing trace event types via `sdk/context.py`
4. New storage backend:
   - implement protocols in `core/stores/`
   - wire selection in CLI/engine layer without importing CLI into `core`
