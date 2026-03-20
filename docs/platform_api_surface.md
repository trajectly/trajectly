# Platform API Surface

This document defines the Phase 1 engine surface that `trajectly/trajectly-platform`
is allowed to rely on. Everything listed here is treated as a compatibility
contract for the `0.4.x` line. Imports outside this document are considered
internal implementation details unless another document says otherwise.

Use this document when embedding Trajectly into backend, service, or platform
code. It describes the stable programmatic evaluation API, not the SDK
instrumentation layer. Most application developers should start with the CLI
and, when needed, the SDK.

## Supported Imports

Prefer the explicit core import path in server or platform code:

```python
from trajectly.core import Trajectory, Verdict, Violation, evaluate
```

The top-level mirror remains supported for the same symbols:

```python
from trajectly import Trajectory, Verdict, Violation, evaluate
```

Portable execution trajectory bundles are supported through the trace module:

```python
from trajectly.core.trace import (
    TraceEventV03,
    TraceMetaV03,
    TrajectoryV03,
    read_legacy_trajectory,
    read_trajectory_json,
    write_trajectory_json,
)
```

For process-to-process upload, the supported command surface is:

```bash
python -m trajectly sync --project-root . --endpoint https://platform.example/api/v1/sync
```

The wire contract for `trajectly sync` is documented in
[Platform Sync Protocol](platform_sync_protocol.md).

## Stability Expectations

- Trajectly is still pre-1.0, but the platform boundary above is pinned for the
  entire `0.4.x` patch line.
- Patch releases in `0.4.x` will not remove or rename the supported symbols in
  this document.
- Patch releases in `0.4.x` will not change the `evaluate(trajectory, spec)`
  parameter names or ordering.
- Patch releases in `0.4.x` will not remove fields from the documented
  dataclass-style result objects or from `TrajectoryV03`.
- Patch releases in `0.4.x` will not change the portable execution trajectory
  schema version from `0.4` without an explicit changelog entry and migration
  note.
- New optional metadata keys may be added to serialized payloads, but existing
  keys keep their meaning.
- Breaking changes to this contract must ship in the next minor release and be
  called out in `CHANGELOG.md`.

## Stable Object Shapes

### `Trajectory`

- Fields: `events`, `baseline_events`, `metadata`
- Supported constructor forms:
  - `Trajectory(events=[...])`
  - `Trajectory.from_events(events, baseline_events=..., metadata=...)`

### `Verdict`

- Fields: `status`, `violations`, `witness_index`, `failure_class`,
  `primary_violation`, `metadata`
- Supported helpers:
  - `passed`
  - `to_dict()`

### `Violation`

- Fields: `code`, `message`, `failure_class`, `event_index`, `expected`,
  `observed`, `hint`
- Supported helper:
  - `to_dict()`

### `TrajectoryV03`

- Fields: `meta`, `events`, `schema_version`
- Supported helpers:
  - `to_dict()`
  - `to_json()`
  - `from_dict(...)`
  - `from_json(...)`

## Supported `evaluate(...)` Inputs

- `trajectory` may be:
  - a `trajectly.core.Trajectory`
  - a sequence of `trajectly.events.TraceEvent`
- `spec` may be:
  - an `AgentSpec`
  - a string or `Path` pointing to an `.agent.yaml` file

If `Trajectory.baseline_events` is omitted, `evaluate(...)` performs
contract-only verification by reusing `events` as the refinement baseline.

## Explicitly Not Part Of The Stable Import Contract

The private platform should not import these modules directly:

- `trajectly.core.api`
- `trajectly.core.schema`
- `trajectly.core.sync`
- `trajectly.core.trt.*`
- `trajectly.core.report.*`
- `trajectly.cli.*`
- `trajectly.engine_common`

The private platform should also avoid:

- underscore-prefixed helpers
- modules not listed under **Supported Imports**
- depending on field ordering in `dict` payloads beyond the documented keys

## Upgrade Guidance

- Prefer `trajectly.core` over the top-level `trajectly` mirror in platform
  server code so the boundary stays explicit.
- When changing any supported symbol, update this document, the platform API
  contract tests, and the dedicated CI compatibility gate in the same pull
  request.
