from __future__ import annotations

from trajectly.refinement import RefinementPolicy, SkeletonStep, check_skeleton_refinement


def test_refinement_allows_configured_extra_tool() -> None:
    baseline = [SkeletonStep(event_index=0, tool_name="search"), SkeletonStep(event_index=2, tool_name="checkout")]
    current = [
        SkeletonStep(event_index=0, tool_name="search"),
        SkeletonStep(event_index=1, tool_name="log_event"),
        SkeletonStep(event_index=2, tool_name="checkout"),
    ]
    result = check_skeleton_refinement(
        baseline_steps=baseline,
        current_steps=current,
        policy=RefinementPolicy(allow_extra_tools=["log_event"]),
        side_effect_tools={"checkout", "create_refund"},
    )
    assert result.violations == []
    assert result.refinement_skeleton_vacuous is False


def test_refinement_flags_extra_side_effect_and_new_tool() -> None:
    baseline = [SkeletonStep(event_index=0, tool_name="search")]
    current = [
        SkeletonStep(event_index=0, tool_name="search"),
        SkeletonStep(event_index=1, tool_name="create_refund"),
    ]

    result = check_skeleton_refinement(
        baseline_steps=baseline,
        current_steps=current,
        policy=RefinementPolicy(),
        side_effect_tools={"checkout", "create_refund"},
    )
    codes = [violation.code for violation in result.violations]
    assert "REFINEMENT_EXTRA_TOOL_CALL" in codes
    assert "REFINEMENT_EXTRA_SIDE_EFFECT_CALL" in codes
    assert "REFINEMENT_NEW_TOOL_NAME_FORBIDDEN" in codes


def test_refinement_vacuous_when_baseline_has_no_calls() -> None:
    result = check_skeleton_refinement(
        baseline_steps=[],
        current_steps=[SkeletonStep(event_index=0, tool_name="search")],
        policy=RefinementPolicy(),
        side_effect_tools=set(),
    )
    assert result.violations == []
    assert result.refinement_skeleton_vacuous is True
