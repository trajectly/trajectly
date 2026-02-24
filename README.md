# Trajectly

Deterministic contract testing and replay for AI agent trajectories.

Trajectly (TRT) records baseline runs, replays deterministically offline, and returns **witness-driven failures** with
counterexample artifacts when behavior regresses.

## Why Trajectly

- **Deterministic verdicts**: same trace + same spec ⇒ same PASS/FAIL.
- **Witness-first debugging**: earliest failing event index and primary violation.
- **One-command repro**: replay the exact failure without calling live APIs.
- **Framework-agnostic**: works with OpenAI, Gemini, LangGraph, LlamaIndex, and custom tools.

## Install

### Recommended (uv)

```bash
uv venv
source .venv/bin/activate
uv sync --extra dev
```

### Pip (supported)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

## Quick Example (real pass/fail)

```bash
cd ../trajectly-examples
trajectly init
trajectly record specs/trt-support-triage-baseline.agent.yaml
trajectly run specs/trt-support-triage-baseline.agent.yaml
trajectly run specs/trt-support-triage-regression.agent.yaml
TRAJECTLY_CI=1 trajectly repro --latest
```

Expected:

- baseline exits `0`
- regression exits `1`
- latest report includes witness index + primary violation + repro command

## Documentation

All docs now live in this repo under `docs/`:

- `docs/start_here.md`
- `docs/trt_theory.md`
- `docs/how_trt_provides_value.md`
- `docs/platform_adapters.md`
- `docs/cli_reference.md`
- `docs/agent_spec_reference.md`
- `docs/trace_schema_reference.md`

## License

MIT
