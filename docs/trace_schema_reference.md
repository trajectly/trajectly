# Trace Schema Reference

Trajectly stores trace data as JSONL events. Each line is one event object.

This page covers:

1. event envelope fields
2. event kinds and when they fire
3. annotated examples
4. compatibility behavior

---

## 1) Event Envelope

Each JSONL event includes:

- `schema_version`: current event schema (`v1` for runtime envelope)
- `event_type`: event kind
- `seq`: positive sequence number in emission order
- `run_id`: run identifier
- `rel_ms`: relative timestamp in milliseconds
- `payload`: event-specific body
- `meta`: optional metadata map
- `event_id`: deterministic event hash (may be absent in raw input, added after normalization)

Example envelope:

```json
{
  "schema_version": "v1",
  "event_type": "tool_called",
  "seq": 8,
  "run_id": "run-01JXYZ",
  "rel_ms": 124,
  "payload": {
    "tool_name": "fetch_pr",
    "input": {
      "args": ["PR-2026"],
      "kwargs": {}
    }
  },
  "meta": {
    "provider": "gemini"
  },
  "event_id": "77d15e..."
}
```

---

## 2) Event Types (Runtime Envelope)

Supported event types:

- `run_started`
- `agent_step`
- `llm_called`
- `llm_returned`
- `tool_called`
- `tool_returned`
- `run_finished`

When each type fires:

- `run_started`: at execution start for a spec
- `agent_step`: logical step markers emitted by agent instrumentation
- `llm_called`: before provider/model invocation
- `llm_returned`: after provider/model response
- `tool_called`: before tool invocation
- `tool_returned`: after tool result is produced
- `run_finished`: at run completion with final status

---

## 3) Annotated Event Examples

### `run_started`

```json
{
  "schema_version": "v1",
  "event_type": "run_started",
  "seq": 1,
  "run_id": "run-01JXYZ",
  "rel_ms": 0,
  "payload": {
    "spec_name": "trt-code-review-bot"
  },
  "meta": {}
}
```

### `llm_called`

```json
{
  "schema_version": "v1",
  "event_type": "llm_called",
  "seq": 6,
  "run_id": "run-01JXYZ",
  "rel_ms": 97,
  "payload": {
    "provider": "gemini",
    "model": "gemini-2.5-flash",
    "prompt": "Review this diff and lint summary..."
  },
  "meta": {}
}
```

### `tool_returned`

```json
{
  "schema_version": "v1",
  "event_type": "tool_returned",
  "seq": 9,
  "run_id": "run-01JXYZ",
  "rel_ms": 155,
  "payload": {
    "tool_name": "post_review",
    "output": {
      "status": "posted",
      "pr_id": "PR-2026"
    }
  },
  "meta": {}
}
```

---

## 4) Normalized TRT Event View (v0.3)

During TRT processing, events are normalized into TRT event objects (v0.3 style) with fields such as:

- `event_index`
- `kind` (`TOOL_CALL`, `TOOL_RESULT`, `LLM_REQUEST`, `LLM_RESPONSE`, etc.)
- `payload`
- `stable_hash`

This normalized representation is what abstraction and refinement consume.

---

## 5) Compatibility and Validation

- missing `schema_version` in runtime event input is treated as `v1`
- unsupported versions fail with migration guidance
- `event_id` is deterministically computed if absent
- invalid event shape fails schema validation

---

## 6) Practical Guidance

- Keep payloads structured and deterministic where possible.
- Avoid embedding secrets in trace payloads; use redaction patterns in specs.
- Use stable tool names since refinement and policy checks depend on them.
