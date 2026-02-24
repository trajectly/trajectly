# Contracts Reference (Phi v1)

`phi.yaml` contains policy only. Do not put `refinement` in `phi.yaml`.

```yaml
schema_version: "0.3"
contracts:
  version: v1
  tools:
    allow: []
    deny: []
    max_calls_total: 10
    max_calls_per_tool: {}
  sequence:
    require: []
    forbid: []
    require_before: []
    eventually: []
    never: []
    at_most_once: []
  side_effects:
    deny_write_tools: true
  network:
    default: deny
    allowlist: []
    allow_domains: []
  data_leak:
    deny_pii_outbound: true
    outbound_kinds: [TOOL_CALL, LLM_REQUEST]
  args:
    tool_name:
      required_keys: []
      fields: {}
```

## Supported Obligation Families

- tool allow/deny
- max call budgets (global + per-tool)
- sequence constraints (`require_before`, `eventually`, `never`, `at_most_once`)
- side-effect guard (`deny_write_tools`)
- network policy
- outbound PII checks (regex-based v1)
- argument checks (`required_keys`, `type`, `min`, `max`, `enum`, `regex`)

## Stable Codes

Core stable codes include:

- `FIXTURE_EXHAUSTED`
- `NORMALIZER_VERSION_MISMATCH` (tooling/config path, exit code `2`)
