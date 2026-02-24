# Trace Schema Reference

## Event Envelope

Each JSONL line is a trace event object:

- `schema_version`: current `v1`
- `event_type`: one of supported event kinds
- `seq`: positive integer sequence number
- `run_id`: run identifier
- `rel_ms`: non-negative relative timestamp in milliseconds
- `payload`: object payload
- `meta`: object metadata
- `event_id` (optional in input, always present after normalization)

## Event Types

- `run_started`
- `agent_step`
- `llm_called`
- `llm_returned`
- `tool_called`
- `tool_returned`
- `run_finished`

## Compatibility

- Missing `schema_version` is treated as `v1`.
- Unsupported versions fail with migration guidance.
