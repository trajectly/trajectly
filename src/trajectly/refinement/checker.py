from __future__ import annotations

from dataclasses import dataclass, field

from trajectly.constants import FAILURE_CLASS_REFINEMENT
from trajectly.refinement.skeleton import SkeletonStep
from trajectly.trt.types import TRTViolation


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
) -> tuple[bool, list[int]]:
    # Multiplicity-aware subsequence check used by skeleton refinement:
    # each baseline call must match a distinct current call in order.
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

    return baseline_idx == len(baseline_names), matches


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
    matched, matched_indices = _is_subsequence_with_matches(baseline_names, current_names)
    if not matched:
        missing_tool = None
        current_cursor = 0
        for baseline_tool in baseline_names:
            found = False
            while current_cursor < len(current_names):
                if current_names[current_cursor] == baseline_tool:
                    found = True
                    current_cursor += 1
                    break
                current_cursor += 1
            if not found:
                missing_tool = baseline_tool
                break

        event_index = current_steps[-1].event_index if current_steps else 0
        violations.append(
            TRTViolation(
                code="REFINEMENT_BASELINE_CALL_MISSING",
                message=f"Baseline skeleton call missing in current run: {missing_tool or 'unknown'}",
                failure_class=FAILURE_CLASS_REFINEMENT,
                event_index=event_index,
                expected=missing_tool,
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
