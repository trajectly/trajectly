# `.agent.yaml` Reference (v0.3)

Trajectly specs define how to execute an agent run and how TRT should evaluate it.

---

## Minimal Spec

Use this when you only need the essentials:

```yaml
schema_version: "0.3"
name: trt-support-triage
command: python -m examples.support_triage.main
contracts:
  tools:
    allow: [fetch_ticket, store_triage]
    deny: [unsafe_export]
```

Required fields:

- `schema_version` (`"0.3"` or `"v0.3"`)
- `name`
- `command`

---

## Complete Annotated Spec

```yaml
schema_version: "0.3"
name: trt-code-review-bot
command: python -m examples.code_review_bot.main

# Optional command runtime settings
workdir: ..
env:
  APP_ENV: ci
  FEATURE_FLAG_REVIEW: "1"

# Replay and fixture behavior
fixture_policy: by_hash
strict: true
replay:
  mode: offline
  strict_sequence: true
  llm_match_mode: signature_match
  tool_match_mode: args_signature_match
  fixture_policy: by_hash

# Refinement behavior
refinement:
  mode: skeleton
  allow_extra_llm_steps: true
  allow_extra_tools: [log_event]
  allow_extra_side_effect_tools: []
  allow_new_tool_names: false
  ignore_call_tools: [log_event]

# Contract checks
contracts:
  tools:
    allow: [fetch_pr, lint_code, post_review]
    deny: [unsafe_export]
  sequence:
    require: [fetch_pr, lint_code, post_review]
  data_leak:
    deny_pii_outbound: true
    outbound_kinds: [TOOL_CALL, LLM_REQUEST]

# Optional controls
redact:
  - "(?i)authorization:\\s*bearer\\s+[A-Za-z0-9._-]+"
budget_thresholds:
  max_latency_ms: 10000
  max_tool_calls: 8
  max_tokens: 800
mode_profile: ci_safe
artifacts:
  dir: .trajectly/artifacts
```

---

## Field Reference

### Core

- `schema_version`: spec schema version (`0.3` / `v0.3`)
- `name`: stable spec identifier used in reporting
- `command`: executable command for the run

### Runtime

- `workdir`: command working directory (relative or absolute)
- `env`: environment variables injected into command process

### Replay

- `fixture_policy`: `by_hash` or `by_index`
- `strict`: strict replay toggle
- `replay.mode`: `offline` (default) or `online`
- `replay.strict_sequence`: strict event sequence matching
- `replay.llm_match_mode`: `signature_match` or `sequence_match`
- `replay.tool_match_mode`: `args_signature_match` or `sequence_match`

### Refinement

- `refinement.mode`: `none`, `skeleton`, or `strict`
- `allow_extra_llm_steps`: allow extra model steps
- `allow_extra_tools`: allow extra read-only tool calls
- `allow_extra_side_effect_tools`: allow extra side-effect tool calls
- `allow_new_tool_names`: permit unseen tool names
- `ignore_call_tools`: ignore tools for skeleton extraction

### Contracts

Common contract families:

- `tools` (allow/deny, call budgets)
- `sequence` (ordering constraints)
- `side_effects` (write guards)
- `network` (allowlist/deny policy)
- `data_leak` (PII/secret checks)
- `args` (argument schema and regex checks)

You may also use `contracts.config` to load policy from a separate file.

### Other

- `redact`: regex patterns applied to payload/meta redaction
- `budget_thresholds`: latency/tool/token budget checks
- `mode_profile`: `ci_safe`, `permissive`, or `strict`
- `artifacts.dir`: output directory for artifacts

---

## Practical Tips

- Keep spec `name` stable across baseline and regression variants.
- Use `python -m` commands for reliable module resolution.
- Start with strict contracts and relax only with explicit intent.
- Update baselines only for intentional behavior changes.
