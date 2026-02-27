# Trajectly Examples

Two PR-upgrade regression scenarios that mirror real CI usage:
record a baseline once, then let `trajectly run` catch behavioral drift on every change.

## Examples

| Example | Provider | Tools | What it tests |
|---------|----------|-------|---------------|
| **Support Escalation Agent** | OpenAI (`gpt-4o-mini`) | `fetch_ticket`, `check_entitlements`, `escalate_to_human` | Prompt-upgrade regression that auto-closes instead of escalating |
| **Procurement Approval Agent** | LangChain adapter (`langchain_invoke`) | `fetch_requisition`, `fetch_vendor_quotes`, `route_for_approval`, `create_purchase_order` | Code/prompt-upgrade regression that bypasses required approval |

Each scenario includes a **baseline** (expected behavior) and a **regression** (intentionally broken PR branch behavior).

## Quick Start

Pre-recorded baselines and fixtures are included -- **no API keys needed**.

```bash
# From repo root
pip install -e ".[examples]"
cd examples

# Support regression (expected FAIL with witness + violations)
trajectly run specs/trt-support-escalation-agent-regression.agent.yaml
trajectly report

# Procurement regression (expected FAIL with approval-sequence violations)
trajectly run specs/trt-procurement-approval-agent-regression.agent.yaml
trajectly report

# Reproduce and minimize latest failure
trajectly repro
trajectly shrink
```

## Recording Baselines (when intentionally updating behavior)

```bash
export OPENAI_API_KEY="sk-..."   # needed for support escalation baseline recording
trajectly init
trajectly record specs/trt-support-escalation-agent-baseline.agent.yaml
trajectly record specs/trt-procurement-approval-agent-baseline.agent.yaml
```

## Regression Signals Demonstrated

- **Support Escalation regression:** calls `unsafe_auto_close` and skips `escalate_to_human`; Trajectly reports tool deny + missing required sequence.
- **Procurement Approval regression:** calls `unsafe_direct_award` and skips approval/PO flow; Trajectly reports tool deny + sequence/refinement violations.

## Directory Structure

```text
examples/
├── specs/
│   ├── trt-support-escalation-agent-baseline.agent.yaml
│   ├── trt-support-escalation-agent-regression.agent.yaml
│   ├── trt-procurement-approval-agent-baseline.agent.yaml
│   └── trt-procurement-approval-agent-regression.agent.yaml
├── examples/
│   ├── support_escalation_agent/
│   │   ├── main.py
│   │   └── main_regression.py
│   ├── procurement_approval_agent/
│   │   ├── main.py
│   │   └── main_regression.py
│   └── real_llm_ci/
│       └── runner.py
└── README.md
```

## Tutorials

- [Support Escalation Agent tutorial](../docs/tutorial-support-escalation-agent.md)
- [Procurement Approval Agent tutorial](../docs/tutorial-procurement-approval-agent.md)
