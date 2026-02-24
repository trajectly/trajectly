# Start Here: Trajectly in 10 Minutes

This is the shortest path to validate Trajectly with real LLM calls.

## 1) Understand the core

- TRT semantics and guarantees: [trt_theory.md](trt_theory.md)
- Why it is valuable in CI: [how_trt_provides_value.md](how_trt_provides_value.md)
- Supported real adapters: [platform_adapters.md](platform_adapters.md)

## 2) Run one PASS and one FAIL flow

```bash
cd trajectly-examples
trajectly init
trajectly record specs/trt-support-triage-baseline.agent.yaml
trajectly run specs/trt-support-triage-baseline.agent.yaml
trajectly run specs/trt-support-triage-regression.agent.yaml
TRAJECTLY_CI=1 trajectly repro --latest
```

Expected:
- baseline exits `0`
- regression exits `1`
- latest report includes witness index, primary violation, and repro command

## 3) 8 real scenarios (simple to complex)

The examples are real-provider scenarios across:
- OpenAI
- Gemini
- LangGraph (with OpenAI backend)
- LlamaIndex (with OpenAI backend)

Canonical pairs:
- `trt-support-triage` (ticket classifier)
- `trt-search-buy` (web search agent)
- `trt-code-review-bot`
- `trt-travel-planner`
- `trt-rag-agent`
- `trt-sql-agent` (document QA)
- `trt-payments-agent` (multi-step workflow)
- `trt-support-agent` (support escalation)

## 4) Reference pages

- [cli_reference.md](cli_reference.md)
- [agent_spec_reference.md](agent_spec_reference.md)
- [trace_schema_reference.md](trace_schema_reference.md)
