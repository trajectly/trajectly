# Changelog

All notable changes to this project are documented in this file.

## Unreleased

### Added

- Release automation workflow for SemVer tags.
- Pre-release smoke workflow covering core and cross-repo checks.
- Strict trace/report schema validation with compatibility tests.
- Adapter helpers and examples for LlamaIndex, CrewAI, AutoGen, and DSPy.

### Changed

- Expanded deterministic replay coverage and integration smoke scenarios.

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
