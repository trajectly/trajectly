# Trajectly Examples

This directory contains the in-repo CI regression example for procurement approval.

For the full real-world support escalation workflow (baseline, regression PR, dashboard,
CI gate, repro, and shrink), use the dedicated demo repo:
https://github.com/trajectly/support-escalation-demo

## In-repo Example

| Example | Provider | Tools | What it tests |
|---------|----------|-------|---------------|
| **Procurement Approval Agent** | LangChain adapter (`langchain_invoke`) | `fetch_requisition`, `fetch_vendor_quotes`, `route_for_approval`, `create_purchase_order` | Code/prompt-upgrade regression that bypasses required approval |

The procurement scenario includes a **baseline** (expected behavior) and a
**regression** (intentionally broken PR-branch behavior).

## Quick Start

Pre-recorded baselines and fixtures are included -- **no API keys needed**.

```bash
# From repo root
python -m pip install -e ".[examples]"
cd examples

# Procurement regression (expected FAIL with approval-sequence violations)
python -m trajectly run specs/trt-procurement-approval-agent-regression.agent.yaml
python -m trajectly report

# Reproduce and minimize latest failure
python -m trajectly repro
python -m trajectly shrink
```

## Recording Baselines (when intentionally updating behavior)

```bash
python -m trajectly init
python -m trajectly record specs/trt-procurement-approval-agent-baseline.agent.yaml
```

## Regression Signal Demonstrated

- **Procurement Approval regression:** calls `unsafe_direct_award` and skips
  approval/PO flow; Trajectly reports tool deny + sequence/refinement violations.

## Directory Structure

```text
examples/
├── specs/
│   ├── trt-procurement-approval-agent-baseline.agent.yaml
│   └── trt-procurement-approval-agent-regression.agent.yaml
├── examples/
│   ├── procurement_approval_agent/
│   │   ├── main.py
│   │   └── main_regression.py
│   └── real_llm_ci/
│       └── runner.py
└── README.md
```

## Tutorials

- [Procurement Approval Agent tutorial](../docs/tutorial-procurement-approval-agent.md)
- [Support Escalation Demo (standalone repo)](https://github.com/trajectly/support-escalation-demo)
