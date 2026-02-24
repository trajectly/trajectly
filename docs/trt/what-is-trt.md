# What Is TRT?

Trajectory Refinement Testing (TRT) is Trajectly’s core verification primitive for agent CI.

Given:

- baseline trace `T_b`
- new trace `T_n`
- abstraction map `alpha`
- obligations `Phi`
- refinement relation `<=_skeleton`

TRT returns `PASS` iff:

1. `alpha(T_n)` satisfies all obligations in `Phi`
2. `alpha(T_n) <=_skeleton alpha(T_b)`

If TRT fails, Trajectly emits:

- earliest witness event index
- primary violation
- all violations at witness
- counterexample prefix trace
- one-command offline repro

## Formal Objects

- Concrete trace `T`: ordered events `e_0..e_n`
- Abstraction `alpha`: deterministic mapping from concrete events to abstract tokens + predicates
- Obligations `Phi`: machine-checkable safety/protocol properties
- Refinement `<=_skeleton`: baseline-relative behavioral constraint over `TOOL_CALL` skeletons

## Refinement Scope (v1)

Skeleton refinement is computed from `TOOL_CALL` events only.
`TOOL_RESULT` events are excluded from refinement checks in v1.

Baseline skeleton `S_b` is extracted from baseline `TOOL_CALL` names after `ignore_call_tools` filtering.
New skeleton `S_n` is extracted the same way.

`T_n <=_skeleton T_b` iff:

1. `S_b` is an ordered subsequence of `S_n` (multiplicity-aware)
2. extra calls in `S_n` are in `allow_extra_tools`
3. extra side-effect calls are in `allow_extra_side_effect_tools`
4. if `allow_new_tool_names=false`, no tool name may appear outside `tools(S_b) union allow_extra_tools`

If baseline has no `TOOL_CALL` events, skeleton refinement is vacuous (`refinement_skeleton_vacuous=true` in report metadata).
