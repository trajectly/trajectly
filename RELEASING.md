# Releasing Trajectly

This document defines the release checklist and changelog policy for the Trajectly OSS repos.

## Release Checklist

1. Confirm CI green in all repos:
   - `trajectly`
   - `trajectly-action`
   - `trajectly-examples`
   - `trajectly-docs`
2. Run private file policy checks and ensure no internal files are tracked.
3. Run pre-release smoke:
   - Core smoke (`init`, `record`, `run`)
   - Examples clean specs and intentional regression specs
   - Action smoke checks
   - Docs quality checks
4. Verify schema compatibility tests pass in `trajectly`:
   - trace schema validation
   - report schema validation
   - unsupported version behavior
5. Update changelog entries (see policy below) for each impacted repo.
6. Create and push version tags:
   - `trajectly`: `vX.Y.Z` (SemVer)
   - `trajectly-action`: `v1.Y.Z` and move floating `v1`
   - `trajectly-examples`: update compatibility pin if needed
7. Verify release workflows complete successfully and artifacts are published.
8. Post-release smoke run from a clean clone.

## Changelog Policy

1. Every behavior or contract change must be listed in `CHANGELOG.md`.
2. Keep entries in these categories:
   - `Added`
   - `Changed`
   - `Fixed`
   - `Security`
3. Use a top-level `Unreleased` section until a tag is cut.
4. At release, move `Unreleased` items into a versioned section with date (`YYYY-MM-DD`).
5. Include breaking-change notes explicitly and provide migration guidance.
6. Changelog content must reference affected public contracts when relevant:
   - CLI/exit codes
   - `.agent.yaml` schema
   - trace/report schema version handling
   - plugin interfaces

## Versioning Rules

- `trajectly`: SemVer (`v0.x` until stable `v1`)
- `trajectly-action`: independent SemVer with moving major tag (`v1`)
- `trajectly-examples`: documents minimum supported `trajectly` version and validates pin in CI
