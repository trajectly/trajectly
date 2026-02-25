# Trajectly Examples

Real, deterministic validation scenarios that demonstrate TRT on practical agent workflows.

This directory is intentionally focused on **8 example pairs** (baseline + regression) across:

- OpenAI
- Gemini
- LangGraph (OpenAI backend)
- LlamaIndex (OpenAI backend)

Each regression path intentionally introduces a denied tool call (`unsafe_export`) so TRT returns a reproducible `FAIL` with
clear witness data.

## Prerequisites

- Trajectly installed from this repo root: `pip install -e ".[dev]"`
- Provider keys:
  - `OPENAI_API_KEY` (OpenAI, LangGraph, LlamaIndex examples)
  - `GEMINI_API_KEY` (Gemini examples)
- Optional runtime packages when exercising all adapters:
  - `openai`
  - `langgraph`
  - `langchain-openai`
  - `llama-index-llms-openai`

## Example Anatomy (How Code + Specs Connect)

```text
examples/
  examples/
    <scenario>/
      main.py
      main_regression.py
    real_llm_ci/
      runner.py
  specs/
    trt-<scenario>-baseline.agent.yaml
    trt-<scenario>-regression.agent.yaml
```

How to read this structure:

- `main.py` / `main_regression.py` are thin entrypoints that call `run_example(...)`.
- `examples/real_llm_ci/runner.py` contains tool definitions, provider adapters, and scenario functions.
- `specs/*.agent.yaml` defines command, replay policy, and tool contracts.
- `trajectly run` evaluates observed behavior against those contracts and refinement checks.

For the full internal walkthrough, see [`../docs/examples-developer-guide.md`](../docs/examples-developer-guide.md).

## 8 Example Pairs (Simple -> Complex)

1. `trt-support-triage` - Ticket classifier (OpenAI)
2. `trt-search-buy` - Web search and recommendation (OpenAI)
3. `trt-code-review-bot` - PR fetch/lint/review posting (Gemini)
4. `trt-travel-planner` - Search and booking flow (Gemini)
5. `trt-rag-agent` - Retrieval + rerank + answer formatting (LlamaIndex)
6. `trt-sql-agent` - Document QA with citations (LlamaIndex)
7. `trt-payments-agent` - Multi-step routing workflow (LangGraph)
8. `trt-support-agent` - Escalation and outcome logging (LangGraph)

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

Run baseline checks (expected `PASS`):

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

Run regression checks (expected `FAIL`):

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

## Create a New Example Pair

1. Add scenario behavior in `examples/real_llm_ci/runner.py`:
   - define or reuse `@tool(...)` functions
   - add scenario function with baseline and regression branches
   - register scenario in `SCENARIOS`
2. Add entrypoints in `examples/<new_example>/`:
   - `main.py` with `mode="baseline"`
   - `main_regression.py` with `mode="regression"`
3. Add spec pair in `specs/`:
   - baseline spec command -> `...main`
   - regression spec command -> `...main_regression`
   - include `contracts.tools.allow` and `deny`
4. Validate:
   - `trajectly record specs/trt-<new>-baseline.agent.yaml`
   - `trajectly run specs/trt-<new>-baseline.agent.yaml` (expect `PASS`)
   - `trajectly run specs/trt-<new>-regression.agent.yaml` (expect `FAIL`)

## Common Mistakes and Debugging

- Tool name mismatch:
  - symptom: expected tool allowed but TRT reports denied/sequence drift
  - fix: align spec tool names exactly with `@tool("...")` names
- Wrong `workdir` in spec:
  - symptom: module import/command resolution errors
  - fix: use `workdir: ..` for packaged examples
- Baseline drift after behavior change:
  - symptom: failures in baseline spec
  - fix: intentionally re-record baseline for approved behavior updates
- Fixture mismatch/exhaustion:
  - symptom: replay matching failures
  - fix: re-record baseline and confirm deterministic arguments/tool order

## Tutorials and Next Reading

Per-example tutorials:

- [`../docs/tutorial-support-triage.md`](../docs/tutorial-support-triage.md)
- [`../docs/tutorial-search-buy.md`](../docs/tutorial-search-buy.md)
- [`../docs/tutorial-code-review-bot.md`](../docs/tutorial-code-review-bot.md)
- [`../docs/tutorial-travel-planner.md`](../docs/tutorial-travel-planner.md)
- [`../docs/tutorial-rag-agent.md`](../docs/tutorial-rag-agent.md)
- [`../docs/tutorial-sql-agent.md`](../docs/tutorial-sql-agent.md)
- [`../docs/tutorial-payments-agent.md`](../docs/tutorial-payments-agent.md)
- [`../docs/tutorial-support-agent.md`](../docs/tutorial-support-agent.md)

Developer deep dive:

- [`../docs/examples-developer-guide.md`](../docs/examples-developer-guide.md)

## Validation

```bash
./scripts/check_blocked_paths.sh
```
