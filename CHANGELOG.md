# Changelog

All notable changes to this project are documented in this file.

## Unreleased

### Added

- **Phase 1 architecture refactor**: `core/`, `cli/`, `sdk/` package boundaries.
  - `src/trajectly/core/` contains all deterministic engine modules.
  - `src/trajectly/cli/` contains Typer commands, orchestration, and report rendering.
  - `src/trajectly/sdk/` contains instrumentation adapters (unchanged).
  - Compatibility shims at old import paths for one release cycle.
  - Boundary enforcement test (`test_boundary_enforcement.py`): core must not import typer/rich/click.
- `ArtifactStore` and `BaselineStore` protocols in `core/stores/` with local filesystem implementations.
- Spec `extends` field for file-based spec inheritance with deterministic deep-merge.
- `github-action/action.yml`: thin composite GitHub Action wrapper (no TRT logic).
- `--version` flag on the CLI (`trajectly --version`).
- Deterministic witness selection tests (`test_determinism_witness.py`).
- Canonical JSON stability tests (`test_canonical_stability.py`).
- CLI smoke tests (`test_cli_smoke.py`): init, record, run, report, exit codes.
- Spec extends tests (`test_spec_extends.py`): single/chained extends, cycle detection.
- Phase 1 architecture audit report.
- CI GitHub Actions guide (`docs/ci_github_actions.md`).
- Deterministic replay hardening tests:
  - `tests/integration/test_determinism_replay.py` validates repeat-run TRT payload stability.
  - Replay network-block integration assertion for CI-safe offline mode.
- Tiered Makefile quality targets: `make check`, `make test-fast`, `make test-determinism`, `make test-cov`.
- Stable Python evaluation API for platform integrations:
  - `trajectly.core.evaluate(trajectory, spec) -> Verdict`
  - stable `Trajectory`, `Verdict`, and `Violation` exports from `trajectly.core` and top-level `trajectly`
  - import-contract coverage for non-CLI callers
- Portable execution trajectory JSON for platform ingestion:
  - `TrajectoryV03.to_json()` / `TrajectoryV03.from_json()`
  - `write_trajectory_json(...)` / `read_trajectory_json(...)`
  - `read_legacy_trajectory(...)` to lift existing `trace.jsonl` + `trace.meta.json` artifacts
- First-party workspace sync client for platform ingestion:
  - `python -m trajectly sync --endpoint ...`
  - deterministic sync payloads with `Idempotency-Key`
  - `.trajectly/sync/latest.json` metadata for the last successful upload
  - sync protocol reference in `docs/platform_sync_protocol.md`

### Changed

- Version aligned: `pyproject.toml` and `__init__.py` both `0.3.0rc3`.
- CLI entrypoint changed from `trajectly.cli:app` to `trajectly.cli.commands:app`.
- `cli.py` renamed to `cli/commands.py`.
- `docs/architecture.md` rewritten to describe completed architecture.
- GitHub Action canonical source is now `trajectly/trajectly-action@v1`.
- In-repo `github-action/action.yml` is now a compatibility wrapper that delegates to `trajectly/trajectly-action@v1` and is planned for removal in `v0.4.3`.
- CI now runs dedicated determinism replay tests and coverage output in addition to lint/type/unit suites.

### Fixed

- `_repo_src_path()` in `runtime.py` adjusted for new file depth after move to `core/`.
- Shim for `replay_guard.py` uses `sys.modules` aliasing for monkeypatch compatibility.
- Shim for `engine_common.py` explicitly re-exports underscore-prefixed names.
- Portable trajectory JSON now defaults a missing top-level `schema_version` to `0.4` during validation.
- `trajectly sync` now derives `Idempotency-Key` from stable artifact content so repeated identical uploads reuse the same key.

### Internal

- 281+ tests pass. ruff + mypy clean on CI.
- No user-facing CLI behavior changes (all commands, flags, exit codes preserved).

## v0.4.2 - 2026-03-06

### Changed

- Removed the optional cloud run-hook exporter path from the core package:
  - deleted `src/trajectly/plugins/cloud_exporter.py`
  - removed built-in cloud exporter wiring from `plugins/loader.py`
  - removed cloud exporter exports/tests and architecture doc references
- Maintained plugin extension support via entry points (`trajectly.run_hook_plugins` and `trajectly.semantic_diff_plugins`).

## v0.3.0-rc1 - 2026-02-23

### Added

- TRT-first CLI coverage:
  - `trajectly shrink` for bounded ddmin counterexample reduction
  - v0.2/v1 to v0.3 spec migration support
- Shrinker module (`src/trajectly/shrink/ddmin.py`) with class-preserving failure predicate support.
- `Makefile` targets: `make test`, `make demo`.
- Release automation workflow for SemVer tags.
- Pre-release smoke workflow covering core and cross-repo checks.
- Strict trace/report schema validation with compatibility tests.
- Adapter helpers and examples for LlamaIndex, CrewAI, AutoGen, and DSPy.
- `trajectly enable` command for onboarding workspace scaffolding and spec discovery hints.
- `record --auto` for deterministic spec auto-discovery.
- `baseline update` command for explicit baseline refresh workflow.
- `.agent.yaml` contracts schema parsing/validation for tools, sequence, side effects, and network sections.
- `.agent.yaml` contracts now support explicit `contracts.version` with fail-fast validation (currently `v1` only).
- Replay-time contract enforcement engine with stable tool error codes.
- Replay network allowlist support via `contracts.network.allowlist`.
- First-divergence summary in diff outputs and reports.
- Repro artifacts in `.trajectly/repros/` plus `trajectly repro` command for one-command local reproduction.
- Basic trace minimization in repro artifacts (`*.baseline.min.jsonl`, `*.current.min.jsonl`).
- PR-comment-ready markdown output via `trajectly report --pr-comment`.
- `trajectly enable --template {openai,langchain,autogen}` starter template scaffolds.

### Changed

- Core package version bumped to `0.3.0rc1`.
- `README.md` updated with TRT docs links, shrink command, and migration command.
- `trajectly-action` contract updated for TRT:
  - PR-comment-ready summary artifact output
  - repro artifact uploads (`.trajectly/repros/*.json`, `.jsonl`)
- Expanded deterministic replay coverage and integration smoke scenarios.

### Fixed

- Deterministic replay analysis loop hardening with additional repeat-run stability test for TRT witness/verdict output.
- Private-repo CI behavior for cross-repo checks by using token-gated flows.

## v0.1.0 - 2026-02-22

### Added

- Initial OSS MVP:
  - CLI (`init`, `record`, `run`, `diff`, `report`)
  - deterministic recorder/replayer
  - fixture store and matcher
  - trajectory diff engine and report renderers
  - plugin interfaces
  - adapter SDK foundation
