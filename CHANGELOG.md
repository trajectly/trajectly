# Changelog

All notable changes to this project are documented in this file.

## Unreleased

### Added

- Release automation workflow for SemVer tags.
- Pre-release smoke workflow covering core and cross-repo checks.
- Strict trace/report schema validation with compatibility tests.
- Adapter helpers and examples for LlamaIndex, CrewAI, AutoGen, and DSPy.
- `trajectly enable` command for onboarding workspace scaffolding and spec discovery hints.
- `record --auto` for deterministic spec auto-discovery.
- `baseline update` command for explicit baseline refresh workflow.
- `.agent.yaml` contracts schema parsing/validation for tools, sequence, side effects, and network sections.
- Replay-time contract enforcement engine with stable tool error codes.
- Replay network allowlist support via `contracts.network.allowlist`.
- First-divergence summary in diff outputs and reports.
- Repro artifacts in `.trajectly/repros/` plus `trajectly repro` command for one-command local reproduction.
- Basic trace minimization in repro artifacts (`*.baseline.min.jsonl`, `*.current.min.jsonl`).
- PR-comment-ready markdown output via `trajectly report --pr-comment`.
- `trajectly enable --template {openai,langchain,autogen}` starter template scaffolds.

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
