# Trajectly

Regression testing for AI agents.

Record a known-good agent run, then catch regressions when you change prompts, tools, or models. Get a deterministic `PASS` or `FAIL` with the exact step where behavior diverged.

## Install

```bash
pip install trajectly
```

## 30-Second Example

```bash
cd examples
trajectly init
trajectly record specs/trt-support-triage-baseline.agent.yaml
trajectly run specs/trt-support-triage-regression.agent.yaml   # FAIL -- regression detected
trajectly repro                                                 # Reproduce offline
```

## What You Get

- **PASS or FAIL** -- deterministic, not flaky
- **Failure step** -- the exact event where behavior diverged
- **One-command repro** -- `trajectly repro` replays from saved fixtures, no live API calls
- **CI-ready** -- `trajectly run specs/*.agent.yaml` as a pipeline gate

## Documentation

- [Full docs](docs/trajectly.md) -- quickstart, concepts, CLI reference, spec reference, SDK reference
- [Tutorial: Support Triage (OpenAI)](docs/tutorial-support-triage.md) -- simple single-tool example
- [Tutorial: Payments Agent (LangGraph)](docs/tutorial-payments-agent.md) -- multi-step workflow example

## Supported Frameworks

OpenAI, Anthropic, Gemini, LangChain, LangGraph, LlamaIndex, AutoGen, CrewAI, DSPy.

## License

MIT
