# Guarantees

This page states what Trajectly guarantees, why those guarantees hold, and where their limits are.

---

## 1) Scope of Guarantees

TRT guarantees are **observed-run** and **checker-relative**:

- observed-run: they apply to the concrete run being checked
- checker-relative: they are relative to configured abstraction `alpha`, contracts `Phi`, and refinement policy

TRT does not claim universal correctness over all unseen executions.

---

## 2) Soundness (Checker-Relative)

### Statement

If Trajectly returns `PASS`, then:

```text
alpha(T_n) satisfies Phi
and
S(T_b) <= S(T_n) under configured refinement policy
```

Equivalent implication:

```text
PASS => (V_c is empty) and (V_r is empty)
```

Where:

- `V_c`: contract violations
- `V_r`: refinement violations

### Proof sketch

1. TRT computes `V = V_c union V_r`.
2. TRT returns `PASS` iff `V` is empty.
3. If `V` is empty, then both `V_c` and `V_r` are empty.
4. `V_c` empty means all configured contract checks passed on `T_n`.
5. `V_r` empty means the configured refinement relation holds.
6. Therefore `PASS` implies contract compliance and refinement compliance for the observed run.

---

## 3) Determinism

### Statement

Given identical inputs (trace events, spec/config, fixtures, and runtime flags), Trajectly returns identical:

- verdict (`PASS`/`FAIL`)
- witness index
- primary violation code
- report payload fields

### Proof sketch

1. **Deterministic normalization and abstraction:** canonicalization and `alpha` are pure and deterministic.
2. **Deterministic contract evaluation:** checks execute in a fixed order with deterministic predicates.
3. **Deterministic refinement check:** skeleton extraction and subsequence checks are deterministic.
4. **Deterministic witness selection:** witness ordering is fixed by:
   - minimum event index
   - class precedence
   - lexical code order
5. Therefore the final verdict and metadata are deterministic for identical inputs.

---

## 4) Witness Guarantee

If Trajectly returns `FAIL`, it returns:

- earliest violating event index (`witness_index`)
- all violations at that index
- deterministic primary violation

This gives a stable failure anchor for CI triage and local debugging.

---

## 5) Completeness Caveat (What TRT Does Not Prove)

TRT does **not** prove:

- semantic correctness outside configured `alpha` and `Phi`
- correctness for all unseen future executions
- absence of all possible agent bugs

In other words, TRT gives deterministic compliance checks on observed/replayed behavior, not full program verification.

---

## 6) Worked Example (Code Review Bot, Example C)

Given:

- baseline skeleton `S(T_b) = [fetch_pr, lint_code, post_review]`
- regression skeleton `S(T_n) = [fetch_pr, lint_code, unsafe_export]`
- contract rule `deny: [unsafe_export]`

Then:

1. Contract monitor sees `unsafe_export` in `T_n` and emits `contract_tool_denied`.
2. Refinement check sees missing baseline call `post_review` and emits refinement violation.
3. Violation union is non-empty.
4. TRT returns `FAIL` with deterministic witness and primary violation.

This illustrates the model end-to-end:

- policy failure is explicit
- behavior drift is explicit
- reproduction is deterministic

---

## 7) Complexity (v1)

- abstraction: `O(n)`
- contract monitor pass: `O(n)` for core checks
- skeleton refinement: `O(n)`
- shrinker (`ddmin`): bounded best-effort, often `O(n log n)` style iterations under configured limits

---

## 8) Practical Summary

Trajectly provides rigorous, deterministic, run-level verification for agent CI:

- if it passes, configured checks passed
- if it fails, failure location and reason are reproducible
- guarantees are formal within the configured checker scope
