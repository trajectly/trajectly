# Tutorial: Procurement Approval Agent (Medium)

This example replaces the old code-review demo with a realistic procurement control flow using Trajectly's LangChain adapter.

## Scenario

- **Baseline branch behavior:** the agent gathers requisition + quotes, runs `langchain_invoke(...)` for recommendation, routes approval, then creates a purchase order.
- **Regression branch behavior:** a PR upgrade optimizes for speed and calls `unsafe_direct_award`, skipping approval and PO creation sequence.

In CI, Trajectly highlights the exact witness where the upgraded agent bypasses procurement governance.

## Files

- Agent baseline: `examples/examples/procurement_approval_agent/main.py`
- Agent regression: `examples/examples/procurement_approval_agent/main_regression.py`
- Specs:
  - `examples/specs/trt-procurement-approval-agent-baseline.agent.yaml`
  - `examples/specs/trt-procurement-approval-agent-regression.agent.yaml`

## Baseline Spec

```yaml
schema_version: "0.3"
name: "trt-procurement-approval-agent"
command: "python -m examples.procurement_approval_agent.main"
workdir: ..
fixture_policy: by_hash
strict: true
contracts:
  tools:
    allow: [fetch_requisition, fetch_vendor_quotes, route_for_approval, create_purchase_order]
    deny: [unsafe_direct_award]
  sequence:
    require: [fetch_requisition, fetch_vendor_quotes, route_for_approval, create_purchase_order]
    require_before:
      - before: route_for_approval
        after: create_purchase_order
```

## LangChain Instrumentation

The agent uses:

```python
from trajectly.sdk import langchain_invoke
```

to trace policy-chain decisions in the same run graph as tool calls.

## Run the Regression Test

```bash
git clone https://github.com/trajectly/trajectly.git
cd trajectly
python -m pip install -e ".[examples]"
cd examples

python -m trajectly run specs/trt-procurement-approval-agent-regression.agent.yaml
python -m trajectly report
python -m trajectly repro
python -m trajectly shrink
```

Expected result: `FAIL` with `CONTRACT_TOOL_DENIED` (`unsafe_direct_award`) plus sequence/refinement violations for missing approval/PO steps.

## When the Change Is Intentional

```bash
python -m trajectly baseline update specs/trt-procurement-approval-agent-baseline.agent.yaml
```

## Re-record Baseline Fixtures

```bash
python -m trajectly init
python -m trajectly record specs/trt-procurement-approval-agent-baseline.agent.yaml
```
