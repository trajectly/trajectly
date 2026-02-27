# Tutorial: Support Escalation Agent (Simple)

This example models a realistic PR prompt-upgrade regression in a support workflow.

## Scenario

- **Baseline branch behavior:** enterprise duplicate-charge tickets are fetched, policy is checked, then escalated to human billing ops.
- **Regression branch behavior:** a prompt/code tweak closes tickets directly with `unsafe_auto_close`, bypassing required escalation.

This mirrors the CI question teams actually care about: _"Did this agent upgrade violate support controls?"_

## Files

- Agent baseline: `examples/examples/support_escalation_agent/main.py`
- Agent regression: `examples/examples/support_escalation_agent/main_regression.py`
- Specs:
  - `examples/specs/trt-support-escalation-agent-baseline.agent.yaml`
  - `examples/specs/trt-support-escalation-agent-regression.agent.yaml`

## Baseline Spec

```yaml
schema_version: "0.3"
name: "trt-support-escalation-agent"
command: "python -m examples.support_escalation_agent.main"
workdir: ..
fixture_policy: by_hash
strict: true
contracts:
  tools:
    allow: [fetch_ticket, check_entitlements, escalate_to_human, send_resolution]
    deny: [unsafe_auto_close]
  sequence:
    require: [fetch_ticket, check_entitlements, escalate_to_human]
```

## Run the Regression Test

```bash
git clone https://github.com/trajectly/trajectly.git
cd trajectly
pip install -e ".[examples]"
cd examples

trajectly run specs/trt-support-escalation-agent-regression.agent.yaml
trajectly report
trajectly repro
trajectly shrink
```

Expected result: `FAIL` with violations including `CONTRACT_TOOL_DENIED` (`unsafe_auto_close`) and missing baseline sequence calls.

## When the Change Is Intentional

```bash
trajectly baseline update specs/trt-support-escalation-agent-baseline.agent.yaml
```

## Re-record Baseline Fixtures

```bash
export OPENAI_API_KEY="sk-..."
trajectly init
trajectly record specs/trt-support-escalation-agent-baseline.agent.yaml
```
