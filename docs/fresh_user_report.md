# Fresh User Validation Report

Audit performed from the perspective of a developer discovering Trajectly for the first time, with a clean Python 3.11 environment, no prior `.trajectly/` directory, and no API keys.

## Summary

| Area | Status | Issues found | Fixed |
|------|--------|-------------|-------|
| Install | Pass | 0 | - |
| Quickstart | Fixed | 2 critical | Yes |
| Examples | Fixed | 1 critical | Yes |
| CLI UX | Improved | 3 improvements | Yes |
| Local UI | Fixed | 4 issues | Yes |
| CI integration | Improved | 2 improvements | Yes |
| Homepage | Created | Landing page missing | Yes |
| Terminology | Fixed | 3 stale references | Yes |

## Part 1: Installation

**What worked:**
- `pip install trajectly` installs cleanly
- `trajectly --version` prints `trajectly 0.3.0rc3`
- `trajectly --help` lists all commands with clear descriptions

**No issues found.** Python 3.11+ requirement is correctly specified in `pyproject.toml`.

## Part 2: Quickstart

**Critical issue: examples required API keys from a fresh clone.**

The `.gitignore` excluded `.trajectly/` globally, meaning pre-recorded fixtures and baselines were not committed. A fresh clone had zero fixtures, making `trajectly run` (replay mode) impossible without first running `trajectly record` with live API keys (`OPENAI_API_KEY` or `GEMINI_API_KEY`).

This directly contradicted the product's core value proposition: deterministic offline testing.

**Fixes applied:**
1. Added `.gitignore` override to track `examples/.trajectly/baselines/` and `examples/.trajectly/fixtures/`
2. Committed pre-recorded fixtures for both examples
3. Rewrote README quickstart to skip `record` step -- users can immediately run `trajectly run` with zero setup
4. Moved API key instructions to a separate "Recording your own baselines" section

**Second issue: README quickstart led with `export OPENAI_API_KEY`.**

Even if fixtures were present, the first visible command was an API key export, creating an impression that API keys are required. This is a significant UX friction point for evaluation.

**Fix:** API key export removed from quickstart. New quickstart is 5 commands, zero prerequisites.

## Part 3: Example Validation

**Both examples now work from a fresh clone:**
- Ticket Classifier (OpenAI): `trajectly run specs/trt-support-triage-regression.agent.yaml` produces `FAIL` at witness=2 with `REFINEMENT_BASELINE_CALL_MISSING`
- Code Review Bot (Gemini): `trajectly run specs/trt-code-review-bot-regression.agent.yaml` produces `FAIL` at witness=4 with `REFINEMENT_BASELINE_CALL_MISSING`

**Fixed: `require_before` YAML syntax error in Code Review Bot specs.** The specs used array syntax `[lint_code, post_review]` instead of the required mapping syntax `{before: lint_code, after: post_review}`, causing a parse error.

**Verified full loop for both examples:**
1. `trajectly run` -- regression detected (exit code 1)
2. `trajectly report` -- clear markdown output showing which spec failed and where
3. `trajectly repro` -- reproduces the failure deterministically
4. `trajectly shrink` -- minimizes the trace

## Part 4: CLI Experience

**Improvements made:**

1. **Missing baseline hint:** `trajectly run` with missing baseline now says: `"missing baseline trace at {path}. Run 'trajectly record' first to capture a baseline."`

2. **Missing fixtures hint:** `trajectly run` with missing fixtures now says: `"missing fixtures at {path}. Run 'trajectly record' first to capture fixtures."`

3. **Missing report hint:** `trajectly report` with no prior run now says: `"Latest report not found: {path}. Run 'trajectly run' first to generate a report."`

4. **Regression next-step hint:** After detecting a regression, CLI now shows: `"Tip: run 'trajectly repro' to reproduce, or 'trajectly shrink' to minimize."`

**Verified no stack traces leak:** All error scenarios produce clean, user-friendly messages.

**Exit codes verified:**
- 0: all specs pass
- 1: regression detected
- 2: internal error (missing files, bad arguments)

## Part 5: Local UI

**Issues found and fixed:**

1. **README was stale.** Listed routes that don't exist (`/runs`, `/theory`, `/settings`, `/help`), referenced old example names (`trt-search-buy`, `trt-travel-planner`), and described features that were removed (Demo Dataset button, TRT Demo Reports button). **Fixed:** Complete rewrite reflecting actual routes (`/`, `/dashboard`, `/runs/:runId`) and current functionality.

2. **`index.html` title was `"trajectly-cloud-web"`.** **Fixed:** Updated to `"Trajectly - Deterministic Regression Testing for AI Agents"` with proper meta description, OG tags, and favicon.

3. **No documentation on when to use UI vs CLI.** **Fixed:** Added "Dashboard (optional)" section to core README, plus a comparison table in the web UI README.

4. **Old example slugs in test files.** `theory.test.ts` and `parsers.test.ts` used `trt-search-buy` slug. **Fixed:** Updated to `trt-code-review-bot`.

## Part 6: CI Integration

**Improvements:**

1. **Action path clarification:** README CI section now explains three usage modes: `./github-action` (internal), `trajectly/trajectly/github-action@main` (external), and raw `pip install` (any CI).

2. **Caching added to example workflow:** `examples/.github/workflows/agent-tests.yml` now includes `actions/cache@v4` for `.trajectly/` directory, keyed on spec file hashes.

3. **Simplified workflow comments:** Removed outdated prerequisite comments about recording baselines manually; fixtures are now pre-committed.

## Part 7: Homepage (trajectly.dev)

**Issue: No landing page existed.** The site immediately showed a dashboard with auto-loaded data, which is confusing for first-time visitors who don't know what Trajectly is.

**Fix: Created LandingPage.tsx** with these sections:
1. Hero with tagline, logo, and CTA buttons
2. Problem statement (silent regressions, flaky diffs, no root cause)
3. Solution (behavioral refinement, contracts, exact witness)
4. How it works (4-step flow: Record, Run, Compare, Verdict)
5. 30-second quickstart code block
6. CI integration snippet
7. Comparison table (output diff testing vs Trajectly)
8. Open source positioning (MIT, minimal deps, extensible)

**Routing updated:** `/` is landing page, `/dashboard` is the data dashboard. TopBar shows contextual navigation.

## Part 8: Terminology Audit

**Stale references found and fixed:**
- Old example slugs in web UI tests (`trt-search-buy` → `trt-code-review-bot`)
- App test routing (`/` → `/dashboard` for dashboard tests, `/theory` → `/nonexistent` for redirect test)

**No issues found for:**
- "triage console" -- not present anywhere
- "cloud" in user-facing text -- only appears correctly (e.g., "No cloud services")
- "theory" in UI strings -- only in internal code identifiers, not user-facing
- Old example slugs in production code -- already cleaned up

## Alignment Verification

All changes reinforce the Phase 1 positioning:

| Principle | Status |
|-----------|--------|
| CLI-first | README quickstart is pure CLI, no UI required |
| CI-native | GitHub Action is thin wrapper, any-CI snippet prominent |
| Deterministic | Fixture replay enables zero-API-key testing |
| Offline repro | `trajectly repro` + `trajectly shrink` documented in all tutorials |
| No cloud dependency | Local data mode default, auth disabled, no external services |
