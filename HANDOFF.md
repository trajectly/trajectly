# Trajectly Core Handoff

Last updated: 2026-02-23

## Repo Scope
`trajectly` is the TRT core engine and CLI:
- deterministic replay/runtime hooks
- contracts (`Phi`) monitor
- skeleton refinement checker
- witness/counterexample report generation
- shrink + migrate tooling

## Setup
```bash
uv sync --extra dev
```

## Validation (Required)
```bash
uv run ruff check .
uv run mypy src
uv run pytest -q
```

## Key Paths
- `src/trajectly/trt/`: TRT verdict orchestration and witness resolution
- `src/trajectly/contracts.py`: contracts monitor + findings
- `src/trajectly/refinement/`: skeleton extraction/checker
- `src/trajectly/abstraction/`: token/predicate abstraction pass
- `src/trajectly/replay_guard.py`: offline replay network/process guard
- `src/trajectly/specs/`: v0.3 schema + v0.2 compatibility + migration

## Status Snapshot
### DONE
- TRT v0.3 core architecture merged to `main`.
- Stable witness/counterexample contracts integrated in report payload.
- Deterministic replay guard and shrinker flow shipped.

### PENDING
- `QA-T004`: dead-code staged cleanup.
- `QA-T006`: `engine.py` hot-path refactor.
- `QA-T007`: benchmark harness for TRT performance.

### TODO
- Sync with founder UX findings from `TRT-T022` once sessions complete.

### NEEDS_FIX
- None blocking local development.
- Deployment authority/permissions are external to this repo and tracked as `QA-T016`.

## Onboarding Notes
1. Start with `ONBOARDING_10_MIN.md`.
2. Then read TRT docs in `docs/trt/`.
3. Use `trajectly-examples` for deterministic end-to-end regression checks.
