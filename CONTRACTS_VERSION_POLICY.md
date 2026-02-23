# Contracts Version Policy

This document defines versioning and compatibility for `.agent.yaml` `contracts`.

## Current Version

- Supported `contracts.version`: `v1`
- Default when omitted: `v1`

Example:

```yaml
contracts:
  version: v1
  tools:
    deny: [dangerous_tool]
```

## Compatibility Rules

1. Additive-only changes in a version.
2. Existing `v1` fields and behavior remain stable.
3. Existing contract error codes remain stable.
4. Unsupported versions fail fast with a clear message.

Parser behavior for unsupported versions:

- `Unsupported contracts.version: <value>. Supported: v1`

## What Counts as Additive

- New optional fields under existing sections.
- New optional sections with deterministic defaults.
- New non-breaking diagnostics/metadata.

## What Is Breaking

- Renaming/removing existing fields.
- Changing semantics of existing fields.
- Changing stable contract error code identifiers.

## Future Version Rollout (v2+)

When introducing `v2`:

1. Keep `v1` parser/enforcement intact.
2. Add explicit `v2` parser and schema docs.
3. Add migration notes with before/after examples.
4. Ship compatibility tests for both versions.
5. Update changelog with versioned contract behavior.

## Testing Requirements

Any contract version change must include:

1. Unit tests for valid + invalid payloads.
2. Integration tests for enforcement paths.
3. Regression tests for unchanged `v1` behavior.
4. Docs updates in `README.md` and this policy file.
