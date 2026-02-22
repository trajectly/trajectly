# Trajectly End-to-End Execution Plan

This document is the source-of-truth build plan from OSS MVP to production-ready open-core + SaaS.

## Current Status (as of 2026-02-22)

- Stage 1 Architecture Plan: complete in implementation docs and code structure.
- Stage 2 Repository Structure: complete for `trajectly`, `trajectly-action`, `trajectly-examples`.
- Stage 3 Core CLI/Runtime/Diff: complete for MVP and covered by unit/integration/e2e tests.
- Stage 4 GitHub Action: complete with smoke tests and artifact/summary handling.
- Stage 5 Examples: in progress with deterministic examples plus platform-style adapters.
- Stage 6 OSS Assets: in progress; core READMEs and contributing docs exist, doc depth is being expanded.
- Stage 7 Launch Plan Content: in progress; messaging/assets pipeline still needs execution.
- Stage 8 SaaS Boundary Design: in progress; API/plugin extension points are defined, hosted control plane still pending.

## Repo-by-Repo Scope

### `trajectly`

- Owns CLI contracts (`init`, `record`, `run`, `diff`, `report`) and exit code policy.
- Owns trace schema, fixture storage, diff engine, replay guard, and plugin interfaces.
- Owns SDK adapter surface for framework/platform integration.

### `trajectly-action`

- Owns CI action contract (inputs, outputs, artifact behavior, summary behavior).
- Owns action-level validation and smoke tests.

### `trajectly-examples`

- Owns runnable demo specs and regression examples.
- Owns compatibility demonstrations across adapter patterns.

## Stage Gates (Required Before v0.2.0)

1. Platform adapter maturity gate:
- Add integration tests for adapter wrappers against representative client shapes.
- Add strict replay tests proving deterministic behavior for each adapter example.

2. Schema/versioning gate:
- Add explicit `schema_version` validation in all report and trace entry points.
- Add compatibility tests for future schema migration behavior.

3. CI quality gate:
- Require private-file policy check in all repos.
- Require smoke replay pass and intentional regression pass in PR checks.

4. Documentation gate:
- Publish command reference, schema reference, plugin reference, and onboarding flow.
- Keep prompt/planning internals in `.private/` only.

## Next Build Stages

### Stage 9: Platform Expansion (v0.2.x)

- Native wrappers and examples for:
  - OpenAI-style clients
  - Anthropic-style clients
  - LangChain runnable/chain invocation
  - LlamaIndex query engine hooks
  - CrewAI task/tool wrappers
  - AutoGen agent message loops
- Add contract tests for each wrapper.

### Stage 10: Observability + Debugging (v0.3.x)

- Trace visualization CLI output improvements.
- Rich budget diagnostics with top offenders and drift timeline.
- Flaky-run detection heuristics in OSS plugin examples.

### Stage 11: SaaS Alpha (v0.4.x)

- Hosted ingestion API and workspace auth.
- Run history explorer and diff drilldowns.
- Alert routing + regression triage workflows.

## Definition of "Fully Functioning"

- Deterministic record/replay passes locally and in CI for all examples.
- Intentional regressions fail with actionable findings.
- Public contracts are documented and versioned.
- Private/prompts/planning docs are blocked from git tracking by policy checks.
