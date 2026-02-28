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

### Changed

- Version aligned: `pyproject.toml` and `__init__.py` both `0.3.0rc3`.
- CLI entrypoint changed from `trajectly.cli:app` to `trajectly.cli.commands:app`.
- `cli.py` renamed to `cli/commands.py`.
- `docs/architecture_phase1.md` rewritten to describe completed architecture.

### Fixed

- `_repo_src_path()` in `runtime.py` adjusted for new file depth after move to `core/`.
- Shim for `replay_guard.py` uses `sys.modules` aliasing for monkeypatch compatibility.
- Shim for `engine_common.py` explicitly re-exports underscore-prefixed names.

### Internal

- 281+ tests pass. ruff + mypy clean on CI.
- No user-facing CLI behavior changes (all commands, flags, exit codes preserved).

---

- Deterministic replay hardening tests:
  - `tests/integration/test_determinism_replay.py` validates repeat-run TRT payload stability.
  - replay network-block integration assertion for CI-safe offline mode.
- Tiered Makefile quality targets:
  - `make check`
  - `make test-fast`
  - `make test-determinism`
  - `make test-cov`
- M12 compatibility policy doc: `docs/legacy_compat_policy.md`.

### Changed

- CI now runs dedicated determinism replay tests and coverage output in addition to lint/type/unit suites.
- Focused explanatory comments added in canonical normalization, abstraction predicate extraction, refinement subsequence logic, and witness tie-break ordering.

## v0.3.0-rc1 - 2026-02-23

### Added

- TRT-first CLI coverage:
  - `trajectly shrink` for bounded ddmin counterexample reduction
  - v0.2/v1 to v0.3 spec migration support
- Shrinker module (`src/trajectly/shrink/ddmin.py`) with class-preserving failure predicate support.
- TRT docs set under `docs/trt/`:
  - What Is TRT
  - Guarantees + proof sketch wording
  - Quickstart
  - Contracts reference
  - Abstraction reference
  - Troubleshooting
- `Makefile` targets:
  - `make test`
  - `make demo`

### Changed

- Core package version bumped to `0.3.0rc1`.
- `README.md` updated with TRT docs links, shrink command, and migration command.
- `trajectly-action` contract updated for TRT:
  - PR-comment-ready summary artifact output
  - repro artifact uploads (`.trajectly/repros/*.json`, `.jsonl`)

### Fixed

- Deterministic replay analysis loop hardening with additional repeat-run stability test for TRT witness/verdict output.

### Added

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
- `ONBOARDING_10_MIN.md` docs-first walkthrough and `CONTRACTS_VERSION_POLICY.md` compatibility policy.

### Changed

- Expanded deterministic replay coverage and integration smoke scenarios.
- Quickstart docs now use `enable` + `record --auto` flow.

### Fixed

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
