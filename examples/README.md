# Trajectly Examples

Real validation scenarios for Trajectly.

Minimum compatible core version: the same release as this core repository.

This directory is intentionally minimal and focused on **8 real examples** (baseline + regression) across:

- OpenAI
- Gemini
- LangGraph (OpenAI backend)
- LlamaIndex (OpenAI backend)

## Prerequisites

- `OPENAI_API_KEY` (OpenAI, LangGraph, LlamaIndex examples)
- `GEMINI_API_KEY` (Gemini examples)
- Optional runtime packages when running all examples:
  - `openai`
  - `langgraph`
  - `langchain-openai`
  - `llama-index-llms-openai`

## 8 example pairs (simple -> complex)

1. `trt-support-triage` — Ticket classifier (OpenAI)
2. `trt-search-buy` — Web search agent (OpenAI)
3. `trt-code-review-bot` — Code review bot (Gemini)
4. `trt-travel-planner` — Travel planner (Gemini)
5. `trt-rag-agent` — RAG pipeline (LlamaIndex)
6. `trt-sql-agent` — Document QA (LlamaIndex)
7. `trt-payments-agent` — Multi-step workflow (LangGraph)
8. `trt-support-agent` — Support escalation (LangGraph)

Each regression path intentionally calls `unsafe_export` so TRT produces a clear FAIL witness.

## Quickstart

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

Run baseline checks (expected PASS):

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

Run regression checks (expected FAIL):

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

Replay latest failure:

```bash
trajectly repro
```

## Validation

```bash
./scripts/check_blocked_paths.sh
```
