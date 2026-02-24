# Platform Adapters

Trajectly is currently focused on four real adapter paths:

1. OpenAI
2. Gemini
3. LangGraph (with OpenAI backend)
4. LlamaIndex (with OpenAI backend)

## Adapter table

| Adapter | How it is used in examples | Example pairs |
|---|---|---|
| OpenAI | Direct `openai_chat_completion` calls | `trt-support-triage`, `trt-search-buy` |
| Gemini | Direct Gemini REST calls | `trt-code-review-bot`, `trt-travel-planner` |
| LlamaIndex | Real LlamaIndex LLM calls over OpenAI | `trt-rag-agent`, `trt-sql-agent` |
| LangGraph | Real LangGraph workflow over OpenAI | `trt-payments-agent`, `trt-support-agent` |

All examples are baseline/regression pairs with tools and deterministic repro output.

## Run the full 8-example matrix

```bash
cd trajectly-examples
trajectly init
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

```bash
TRAJECTLY_CI=1 trajectly repro --latest
```
