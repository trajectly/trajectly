"""Skeleton refinement checker (Definitions 4-5 in trt_theory.md).

Implements ``check_skeleton_refinement``, which verifies the skeleton
refinement preorder: baseline call names must embed as a subsequence in the
current call names, and any extra calls must be permitted by policy.

**Algorithm:** Greedy left-to-right subsequence scan in O(|S_b| + |S_c|).
The greedy match is optimal because every matched element consumes the
earliest possible position, maximizing room for subsequent matches.

**Determinism:** The scan is single-pass, index-ordered, and appends
violations in traversal order — no randomness or hash iteration.

**Vacuity:** Empty baseline skeleton is always satisfied (contracts remain
the only active obligations).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from trajectly.core.constants import FAILURE_CLASS_REFINEMENT
from trajectly.core.refinement.skeleton import SkeletonStep
from trajectly.core.trt.types import TRTViolation


@dataclass(slots=True)
class RefinementPolicy:
    mode: str = "skeleton"
    allow_extra_tools: list[str] = field(default_factory=list)
    allow_extra_side_effect_tools: list[str] = field(default_factory=list)
    allow_new_tool_names: bool = False


@dataclass(slots=True)
class RefinementCheckResult:
    violations: list[TRTViolation]
    refinement_skeleton_vacuous: bool = False


def _is_subsequence_with_matches(
    baseline_names: list[str],
    current_names: list[str],
) -> tuple[bool, list[int], str | None]:
    """Greedy O(|baseline| + |current|) subsequence check.

    Returns (matched, match_indices, first_missing_name).
    If matched is True, first_missing_name is None.
    """
    matches: list[int] = []
    baseline_idx = 0
    current_idx = 0

    while baseline_idx < len(baseline_names) and current_idx < len(current_names):
        if baseline_names[baseline_idx] == current_names[current_idx]:
            matches.append(current_idx)
            baseline_idx += 1
            current_idx += 1
            continue
        current_idx += 1

    if baseline_idx == len(baseline_names):
        return True, matches, None

    return False, matches, baseline_names[baseline_idx]


def check_skeleton_refinement(
    *,
    baseline_steps: list[SkeletonStep],
    current_steps: list[SkeletonStep],
    policy: RefinementPolicy,
    side_effect_tools: set[str],
) -> RefinementCheckResult:
    if policy.mode == "none":
        return RefinementCheckResult(violations=[], refinement_skeleton_vacuous=False)

    baseline_names = [step.tool_name for step in baseline_steps]
    current_names = [step.tool_name for step in current_steps]

    if not baseline_names:
        # v0.3 rule: empty baseline skeleton is vacuous for refinement and
        # contracts remain the only active obligations.
        return RefinementCheckResult(violations=[], refinement_skeleton_vacuous=True)

    violations: list[TRTViolation] = []
    matched, matched_indices, first_missing = _is_subsequence_with_matches(baseline_names, current_names)
    if not matched:
        event_index = current_steps[-1].event_index if current_steps else 0
        violations.append(
            TRTViolation(
                code="REFINEMENT_BASELINE_CALL_MISSING",
                message=f"Baseline skeleton call missing in current run: {first_missing or 'unknown'}",
                failure_class=FAILURE_CLASS_REFINEMENT,
                event_index=event_index,
                expected=first_missing,
                observed=current_names,
                hint="Ensure baseline-required tool protocol remains a subsequence.",
            )
        )

    matched_set = set(matched_indices)
    baseline_tool_set = set(baseline_names)
    allowed_extra_tools = set(policy.allow_extra_tools)
    allowed_extra_side_effect = set(policy.allow_extra_side_effect_tools)

    for index, step in enumerate(current_steps):
        # Extra calls are evaluated against both generic allow-lists and
        # side-effect-specific policy to preserve baseline safety.
        if index in matched_set:
            continue

        tool_name = step.tool_name
        if tool_name not in allowed_extra_tools:
            violations.append(
                TRTViolation(
                    code="REFINEMENT_EXTRA_TOOL_CALL",
                    message=f"Extra tool call not allowed by refinement policy: {tool_name}",
                    failure_class=FAILURE_CLASS_REFINEMENT,
                    event_index=step.event_index,
                    expected=sorted(allowed_extra_tools),
                    observed=tool_name,
                    hint="Add tool to refinement.allow_extra_tools or remove the extra call.",
                )
            )

        if tool_name in side_effect_tools and tool_name not in allowed_extra_side_effect:
            violations.append(
                TRTViolation(
                    code="REFINEMENT_EXTRA_SIDE_EFFECT_CALL",
                    message=f"Extra side-effect tool call not allowed: {tool_name}",
                    failure_class=FAILURE_CLASS_REFINEMENT,
                    event_index=step.event_index,
                    expected=sorted(allowed_extra_side_effect),
                    observed=tool_name,
                    hint="Allow explicitly via refinement.allow_extra_side_effect_tools.",
                )
            )

        if (
            not policy.allow_new_tool_names
            and tool_name not in baseline_tool_set
            and tool_name not in allowed_extra_tools
        ):
            violations.append(
                TRTViolation(
                    code="REFINEMENT_NEW_TOOL_NAME_FORBIDDEN",
                    message=f"New tool name not permitted by refinement policy: {tool_name}",
                    failure_class=FAILURE_CLASS_REFINEMENT,
                    event_index=step.event_index,
                    expected=sorted(baseline_tool_set.union(allowed_extra_tools)),
                    observed=tool_name,
                    hint="Set refinement.allow_new_tool_names=true or update allow_extra_tools.",
                )
            )

    return RefinementCheckResult(
        violations=violations,
        refinement_skeleton_vacuous=False,
    )


__all__ = [
    "RefinementCheckResult",
    "RefinementPolicy",
    "check_skeleton_refinement",
]
