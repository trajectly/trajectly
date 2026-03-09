# Contract Catalog

Trajectly contracts are declarative YAML policies that enforce behavioral invariants on agent traces. A single `.contracts.yaml` file can combine any or all of the six dimensions below.

All examples reference real scenarios from the [Merge or Die arena](https://github.com/trajectly/trajectly-survival-arena).

---

## 1. Tools (allow / deny)

Controls which tool calls are permitted during execution.

```yaml
tools:
  allow:
    - fetch_requisition
    - fetch_vendor_quotes
    - route_for_approval
    - create_purchase_order
  deny:
    - unsafe_direct_award
```

**What it enforces**: Only listed tools may be called. Any call to a denied tool is an immediate violation.

**Violation code**: `CONTRACT_TOOL_DENIED`

**Without this**: An agent can silently switch to a disallowed tool path and still produce correct-looking output. You discover the wrong tool was used only when a side effect surfaces in production.

---

## 2. Sequence

Controls the order in which tools must be called.

```yaml
sequence:
  require:
    - tool:fetch_requisition
    - tool:fetch_vendor_quotes
    - tool:route_for_approval
    - tool:create_purchase_order
  require_before:
    - before: tool:route_for_approval
      after: tool:create_purchase_order
  at_most_once:
    - tool:send_invite
  never:
    - tool:run_dangerous_command
```

**Directives**:

| Directive | Meaning |
|---|---|
| `require` | These tools must appear in this order (as a subsequence -- other calls can be interleaved) |
| `require_before` | Tool A must appear before tool B, without requiring exact positions |
| `at_most_once` | Tool may be called at most one time |
| `never` | Tool must never appear in the trace |

**Violation codes**: `CONTRACT_SEQUENCE_REQUIRE_BEFORE_VIOLATED`, `CONTRACT_SEQUENCE_AT_MOST_ONCE_VIOLATED`, `CONTRACT_SEQUENCE_NEVER_VIOLATED`

**Without this**: An agent that sends invites before reserving a room, or calls a forbidden command while still reporting "audit complete", passes any output-only check.

---

## 3. Network

Controls which external domains the agent may contact.

```yaml
network:
  default: deny
  allow_domains:
    - status.internal.example
```

**What it enforces**: All outbound network requests are checked against the domain allowlist. The default policy is deny-all, so only explicitly listed domains are reachable.

**Violation code**: `NETWORK_DOMAIN_DENIED`

**Without this**: An agent can exfiltrate data to an unauthorized domain or fetch from an untrusted source while its final answer looks perfectly normal.

---

## 4. Data Leak

Scans outbound tool-call payloads for secret-like patterns.

```yaml
data_leak:
  outbound_kinds:
    - TOOL_CALL
  secret_patterns:
    - "sk_live_[A-Za-z0-9_]+"
```

**What it enforces**: Every outbound tool-call argument is matched against the declared regex patterns. If a match is found, the trace fails at the exact event.

**Violation code**: `DATA_LEAK_SECRET_PATTERN`

**Without this**: A log summarizer can produce a clean, readable summary while the raw `post_summary` payload leaks API keys, tokens, or PII to an external system.

---

## 5. Arguments

Validates tool-call arguments against type, format, and value constraints.

```yaml
args:
  dispatch_war_room:
    required_keys:
      - dispatch_token
    fields:
      dispatch_token:
        type: string
        regex: "^WR-[0-9]{5}$"
  create_purchase_order:
    required_keys:
      - amount_usd
      - approval_token
    fields:
      amount_usd:
        type: number
        max: 50000
      approval_token:
        type: string
        regex: "^APR-[0-9]{6}$"
  escalate_to_human:
    required_keys:
      - incident_id
      - reason_code
    fields:
      incident_id:
        type: string
        regex: "^INC-[0-9]{6}$"
      reason_code:
        type: string
        enum:
          - duplicate_charge
          - account_takeover
          - data_loss
```

**Field validators**:

| Validator | Meaning |
|---|---|
| `type` | Expected type: `string`, `number`, `boolean` |
| `regex` | Value must match this pattern |
| `max` | Numeric upper bound |
| `enum` | Value must be one of the listed options |

**Violation code**: `CONTRACT_ARGS_REGEX_VIOLATION`, `CONTRACT_ARGS_TYPE_VIOLATION`, `CONTRACT_ARGS_MISSING_KEY`

**Without this**: A tool call can complete successfully with a malformed token, an out-of-range amount, or a missing required field -- and nothing downstream catches the silent corruption.

---

## 6. Budget Thresholds

Caps execution cost at the spec level.

```yaml
# Declared in the .agent.yaml spec, not the contracts file
budget_thresholds:
  max_tool_calls: 3
  max_tokens: 500
```

**What it enforces**: If the agent exceeds the declared tool-call or token limit, Trajectly flags the run as a budget breach regression.

**Classification**: `budget_breach`

**Without this**: Identical final output can mask a run that made twice the API calls or consumed twice the tokens. Cost regressions are invisible until the bill arrives.

---

## Combining dimensions

A single contracts file can use any combination of the above:

```yaml
version: v1
tools:
  allow: [fetch_requisition, fetch_vendor_quotes, route_for_approval, create_purchase_order]
  deny: [unsafe_direct_award]
sequence:
  require:
    - tool:fetch_requisition
    - tool:fetch_vendor_quotes
    - tool:route_for_approval
    - tool:create_purchase_order
  require_before:
    - before: tool:route_for_approval
      after: tool:create_purchase_order
args:
  create_purchase_order:
    required_keys: [amount_usd, approval_token]
    fields:
      amount_usd:
        type: number
        max: 50000
      approval_token:
        type: string
        regex: "^APR-[0-9]{6}$"
```

This single file enforces which tools can be called, in what order, and with what arguments -- all evaluated deterministically at CI time.

---

## See also

- [What Trajectly Catches](what_trajectly_catches.md) -- six failure categories with full walkthrough examples
- [Trajectly Reference](trajectly_reference.md) -- complete spec and contract schema
- [Merge or Die arena](https://github.com/trajectly/trajectly-survival-arena) -- 8 runnable scenarios using all contract dimensions
