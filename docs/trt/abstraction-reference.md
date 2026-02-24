# Abstraction Reference (alpha v1)

Abstraction maps concrete trace events into tokens and derived predicates.

## Default Tokens

- `TOOL_CALL -> CALL(tool_name)`
- `TOOL_RESULT -> RESULT(tool_name)`
- `LLM_REQUEST -> LLM_REQUEST(model)`
- `LLM_RESPONSE -> LLM_RESPONSE(model)`
- `MESSAGE -> MESSAGE`
- `OBSERVATION -> OBSERVATION`
- `ERROR -> ERROR`

## Predicate Extractors (v1)

- `pii`: email/phone regex detectors
- `price`: numeric extraction from configured paths
- `refund_count`: count of refund tool calls

## Determinism Rules

- abstraction is pure (no I/O, no randomness)
- normalization happens through one canonical pipeline
- volatile fields are stripped before hashing/signatures/predicate extraction

## Common Refinement Controls (`.agent.yaml`)

```yaml
refinement:
  mode: skeleton
  allow_extra_llm_steps: true
  allow_extra_tools: ["log_event"]
  allow_extra_side_effect_tools: []
  allow_new_tool_names: false
  ignore_call_tools: ["log_event"]
```
