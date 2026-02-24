# Platform Adapters

Trajectly currently focuses on four real adapter paths:

1. OpenAI
2. Gemini
3. LangGraph (with OpenAI backend)
4. LlamaIndex (with OpenAI backend)

---

## How adapter integration works

Trajectly does not require framework-specific checker logic. Adapters integrate through a shared event model:

1. agent executes framework/provider call
2. SDK emits trace events (`llm_called`, `tool_called`, etc.)
3. Trajectly records baseline and fixture artifacts
4. TRT replays and evaluates contracts/refinement deterministically

This means adapter differences stay in execution code, while verification stays uniform.

---

## Adapter Matrix (Real Examples)

| Adapter | Provider path | Example pairs | Example entrypoints |
| --- | --- | --- | --- |
| OpenAI | Direct OpenAI chat completion | `trt-support-triage`, `trt-search-buy` | `examples/support_triage/main.py`, `examples/search_buy/main.py` |
| Gemini | Direct Gemini REST path | `trt-code-review-bot`, `trt-travel-planner` | `examples/code_review_bot/main.py`, `examples/travel_planner/main.py` |
| LlamaIndex | LlamaIndex OpenAI integration | `trt-rag-agent`, `trt-sql-agent` | `examples/rag_agent/main.py`, `examples/sql_agent/main.py` |
| LangGraph | LangGraph workflow with OpenAI backend | `trt-payments-agent`, `trt-support-agent` | `examples/payments_agent/main.py`, `examples/support_agent/main.py` |

All eight are baseline/regression pairs with deterministic repro output.

---

## Example Specs by Adapter

### OpenAI

- `specs/trt-support-triage-baseline.agent.yaml`
- `specs/trt-support-triage-regression.agent.yaml`
- `specs/trt-search-buy-baseline.agent.yaml`
- `specs/trt-search-buy-regression.agent.yaml`

### Gemini

- `specs/trt-code-review-bot-baseline.agent.yaml`
- `specs/trt-code-review-bot-regression.agent.yaml`
- `specs/trt-travel-planner-baseline.agent.yaml`
- `specs/trt-travel-planner-regression.agent.yaml`

### LlamaIndex

- `specs/trt-rag-agent-baseline.agent.yaml`
- `specs/trt-rag-agent-regression.agent.yaml`
- `specs/trt-sql-agent-baseline.agent.yaml`
- `specs/trt-sql-agent-regression.agent.yaml`

### LangGraph

- `specs/trt-payments-agent-baseline.agent.yaml`
- `specs/trt-payments-agent-regression.agent.yaml`
- `specs/trt-support-agent-baseline.agent.yaml`
- `specs/trt-support-agent-regression.agent.yaml`

---

## Run the Full 8-Example Matrix

```bash
cd examples
trajectly init
```

Record baselines:

```bash
trajectly record \
  specs/trt-support-triage-baseline.agent.yaml \
  specs/trt-search-buy-baseline.agent.yaml \
  specs/trt-code-review-bot-baseline.agent.yaml \
  specs/trt-travel-planner-baseline.agent.yaml \
  specs/trt-rag-agent-baseline.agent.yaml \
  specs/trt-sql-agent-baseline.agent.yaml \
  specs/trt-payments-agent-baseline.agent.yaml \
  specs/trt-support-agent-baseline.agent.yaml
```

Run baseline checks:

```bash
trajectly run \
  specs/trt-support-triage-baseline.agent.yaml \
  specs/trt-search-buy-baseline.agent.yaml \
  specs/trt-code-review-bot-baseline.agent.yaml \
  specs/trt-travel-planner-baseline.agent.yaml \
  specs/trt-rag-agent-baseline.agent.yaml \
  specs/trt-sql-agent-baseline.agent.yaml \
  specs/trt-payments-agent-baseline.agent.yaml \
  specs/trt-support-agent-baseline.agent.yaml
```

Run regression checks:

```bash
trajectly run \
  specs/trt-support-triage-regression.agent.yaml \
  specs/trt-search-buy-regression.agent.yaml \
  specs/trt-code-review-bot-regression.agent.yaml \
  specs/trt-travel-planner-regression.agent.yaml \
  specs/trt-rag-agent-regression.agent.yaml \
  specs/trt-sql-agent-regression.agent.yaml \
  specs/trt-payments-agent-regression.agent.yaml \
  specs/trt-support-agent-regression.agent.yaml
```

Reproduce latest failure:

```bash
trajectly repro
```

---

## Picking an Adapter for First Validation

- Start with **OpenAI + Ticket Classifier** for fastest onboarding.
- Add **Gemini + Code Review Bot** to validate medium-complex workflows and policy enforcement.
- Expand to LangGraph/LlamaIndex once your team has a stable CI gate.
