# `.agent.yaml` Reference

## Required Fields

- `name`: human-readable spec name
- `command`: command to execute (example: `python path/to/agent.py`)

## Optional Fields

- `workdir`: working directory for command execution (relative to spec file or absolute)
- `env`: map of environment variables injected into process
- `fixture_policy`: `by_index` or `by_hash` (default: `by_index`)
- `strict`: strict replay behavior (default: `false`)
- `redact`: list of regex patterns for payload/meta redaction
- `budget_thresholds`:
  - `max_latency_ms`
  - `max_tool_calls`
  - `max_tokens`

## Example

```yaml
name: example-simple
command: python python-simple/agent.py
workdir: ..
fixture_policy: by_hash
strict: true
budget_thresholds:
  max_latency_ms: 10000
  max_tool_calls: 6
  max_tokens: 200
```
