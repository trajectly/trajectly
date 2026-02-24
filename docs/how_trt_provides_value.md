# How TRT Provides Value

Trajectory Refinement Testing (TRT) gives you **deterministic agent contract checks** and **one-command offline repro** when a run regresses. This is how it adds value in practice.

## Value in one sentence

**Same code + same config + same fixtures ⇒ same verdict.** If something changes (prompt, tool order, model behavior, or contract), TRT fails with a concrete witness and a single repro command—no “works on my machine” or manual trace diffing.

## Where it helps

1. **CI** – Block merges when a trace regresses (extra call, wrong order, contract violation).
2. **Offline debugging** – `trajectly repro --latest` replays the failing trace without re-running the agent or hitting live APIs.
3. **Baseline discipline** – You explicitly record “good” behavior; any drift is a failure with a clear report.
4. **Multi-framework** – One workflow (record → run → repro) across OpenAI, Gemini, LangGraph, and LlamaIndex.

## Simulated CI flow (one example)

A minimal “simulated CI” using the examples repo:

1. **Record baselines** (once, or when you intend to change them):

   ```bash
   cd trajectly-examples
   trajectly init
   trajectly record specs/trt-support-triage-baseline.agent.yaml specs/trt-search-buy-baseline.agent.yaml
   ```

2. **Run TRT in CI** (e.g. on every push):

   ```bash
   trajectly run specs/trt-support-triage-baseline.agent.yaml specs/trt-search-buy-baseline.agent.yaml
   ```

   - If traces match the recorded baselines → **exit 0**.
   - If not (e.g. regression script or changed behavior) → **exit 1** and a report with witness index, primary violation, and counterexample.

3. **Reproduce the failure offline** (no live LLM/tools):

   ```bash
   TRAJECTLY_CI=1 trajectly repro --latest
   ```

   This replays the failing trace and writes artifacts (counterexample prefix, repro spec) so anyone can debug without re-running the agent.

4. **(Optional) Shrink** the counterexample to a minimal trace:

   ```bash
   trajectly shrink --latest
   ```

## What you get on failure

- **Earliest witness** – Event index where the trace first diverges or violates a contract.
- **Primary violation** – Refinement mismatch, contract denial, sequence error, etc.
- **One-command repro** – `trajectly repro --latest` (or the printed command) for offline replay.
- **Optional shrink** – Shorter trace that still fails, for faster debugging.

## Links

- [TRT theory](trt_theory.md) – Semantics and refinement relation.
- [Platform adapters](platform_adapters.md) – Supported stacks and example specs.
- [trajectly-examples](https://github.com/trajectly/trajectly-examples) – Runnable specs and `.github/workflows/regression-demo.yml` for a full CI example.
- [CLI reference](cli_reference.md) – `init`, `record`, `run`, `repro`, `shrink`.
