# Guarantees

## Soundness (Observed-Run, Checker-Relative)

Soundness with respect to this checker:

If Trajectly returns `PASS`, then no contract monitor or refinement rule was violated on the observed run.

Formally:

`PASS => (alpha(T_n) satisfies Phi) and (alpha(T_n) <=_skeleton alpha(T_b))`

This is run-level compliance, not universal correctness over all possible executions.

## Counterexample Witness

If Trajectly returns `FAIL`, Trajectly returns the earliest violating event index (`witness_index`) and all violations at that index.

Witness ordering is deterministic:

1. minimum event index
2. refinement class before contract class
3. lexical code order within class

## Determinism Contract

Given identical inputs (trace, configs, fixtures, runtime flags), Trajectly returns identical:

- verdict (`PASS`/`FAIL`)
- witness index
- primary violation code
- report payload fields

## Complexity (v1)

- abstraction: `O(n)`
- contract monitor pass: `O(n)` for core checks
- skeleton refinement: `O(n)`
- shrinker (`ddmin`): bounded best-effort, worst-case `O(n log n)` style iterations under configured limits

## Honest Limits

Trajectly does not prove:

- semantic correctness outside configured `alpha` and `Phi`
- correctness for unseen executions
- absence of all agent bugs

Trajectly does provide deterministic behavioral checks for observed and replayed runs in CI.
