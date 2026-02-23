"""Expanded refinement checker tests: subsequence failure path, allow_new_tool_names,
side-effect tools, empty current skeleton, mode=none bypass."""

from __future__ import annotations

from trajectly.refinement import RefinementPolicy, SkeletonStep, check_skeleton_refinement


def test_subsequence_failure_reports_first_missing_tool() -> None:
    baseline = [
        SkeletonStep(event_index=0, tool_name="search"),
        SkeletonStep(event_index=1, tool_name="checkout"),
        SkeletonStep(event_index=2, tool_name="confirm"),
    ]
    current = [
        SkeletonStep(event_index=0, tool_name="search"),
        SkeletonStep(event_index=1, tool_name="confirm"),
    ]
    result = check_skeleton_refinement(
        baseline_steps=baseline,
        current_steps=current,
        policy=RefinementPolicy(),
        side_effect_tools=set(),
    )
    missing_violations = [v for v in result.violations if v.code == "REFINEMENT_BASELINE_CALL_MISSING"]
    assert len(missing_violations) == 1
    assert missing_violations[0].expected == "checkout"


def test_subsequence_failure_with_empty_current() -> None:
    baseline = [SkeletonStep(event_index=0, tool_name="search")]
    current: list[SkeletonStep] = []
    result = check_skeleton_refinement(
        baseline_steps=baseline,
        current_steps=current,
        policy=RefinementPolicy(),
        side_effect_tools=set(),
    )
    missing_violations = [v for v in result.violations if v.code == "REFINEMENT_BASELINE_CALL_MISSING"]
    assert len(missing_violations) == 1
    assert missing_violations[0].event_index == 0
    assert missing_violations[0].expected == "search"


def test_allow_new_tool_names_suppresses_new_name_violation() -> None:
    baseline = [SkeletonStep(event_index=0, tool_name="search")]
    current = [
        SkeletonStep(event_index=0, tool_name="search"),
        SkeletonStep(event_index=1, tool_name="brand_new_tool"),
    ]
    result = check_skeleton_refinement(
        baseline_steps=baseline,
        current_steps=current,
        policy=RefinementPolicy(allow_new_tool_names=True),
        side_effect_tools=set(),
    )
    codes = [v.code for v in result.violations]
    assert "REFINEMENT_NEW_TOOL_NAME_FORBIDDEN" not in codes
    assert "REFINEMENT_EXTRA_TOOL_CALL" in codes


def test_allow_new_tool_names_false_emits_violation() -> None:
    baseline = [SkeletonStep(event_index=0, tool_name="search")]
    current = [
        SkeletonStep(event_index=0, tool_name="search"),
        SkeletonStep(event_index=1, tool_name="brand_new_tool"),
    ]
    result = check_skeleton_refinement(
        baseline_steps=baseline,
        current_steps=current,
        policy=RefinementPolicy(allow_new_tool_names=False),
        side_effect_tools=set(),
    )
    codes = [v.code for v in result.violations]
    assert "REFINEMENT_NEW_TOOL_NAME_FORBIDDEN" in codes


def test_extra_side_effect_allowed_explicitly() -> None:
    baseline = [SkeletonStep(event_index=0, tool_name="search")]
    current = [
        SkeletonStep(event_index=0, tool_name="search"),
        SkeletonStep(event_index=1, tool_name="db_write"),
    ]
    result = check_skeleton_refinement(
        baseline_steps=baseline,
        current_steps=current,
        policy=RefinementPolicy(
            allow_extra_tools=["db_write"],
            allow_extra_side_effect_tools=["db_write"],
        ),
        side_effect_tools={"db_write"},
    )
    assert result.violations == []


def test_side_effect_not_in_extra_side_effect_list() -> None:
    baseline = [SkeletonStep(event_index=0, tool_name="search")]
    current = [
        SkeletonStep(event_index=0, tool_name="search"),
        SkeletonStep(event_index=1, tool_name="db_write"),
    ]
    result = check_skeleton_refinement(
        baseline_steps=baseline,
        current_steps=current,
        policy=RefinementPolicy(allow_extra_tools=["db_write"]),
        side_effect_tools={"db_write"},
    )
    codes = [v.code for v in result.violations]
    assert "REFINEMENT_EXTRA_TOOL_CALL" not in codes
    assert "REFINEMENT_EXTRA_SIDE_EFFECT_CALL" in codes


def test_mode_none_skips_refinement() -> None:
    baseline = [SkeletonStep(event_index=0, tool_name="search")]
    current: list[SkeletonStep] = []
    result = check_skeleton_refinement(
        baseline_steps=baseline,
        current_steps=current,
        policy=RefinementPolicy(mode="none"),
        side_effect_tools=set(),
    )
    assert result.violations == []
    assert result.refinement_skeleton_vacuous is False


def test_perfect_match_no_violations() -> None:
    baseline = [
        SkeletonStep(event_index=0, tool_name="search"),
        SkeletonStep(event_index=1, tool_name="checkout"),
    ]
    current = [
        SkeletonStep(event_index=0, tool_name="search"),
        SkeletonStep(event_index=1, tool_name="checkout"),
    ]
    result = check_skeleton_refinement(
        baseline_steps=baseline,
        current_steps=current,
        policy=RefinementPolicy(),
        side_effect_tools=set(),
    )
    assert result.violations == []


def test_existing_tool_as_extra_not_new_name() -> None:
    """If the extra tool appears in the baseline set, NEW_TOOL_NAME is not emitted."""
    baseline = [
        SkeletonStep(event_index=0, tool_name="search"),
        SkeletonStep(event_index=1, tool_name="checkout"),
    ]
    current = [
        SkeletonStep(event_index=0, tool_name="search"),
        SkeletonStep(event_index=1, tool_name="checkout"),
        SkeletonStep(event_index=2, tool_name="search"),
    ]
    result = check_skeleton_refinement(
        baseline_steps=baseline,
        current_steps=current,
        policy=RefinementPolicy(allow_new_tool_names=False),
        side_effect_tools=set(),
    )
    codes = [v.code for v in result.violations]
    assert "REFINEMENT_EXTRA_TOOL_CALL" in codes
    assert "REFINEMENT_NEW_TOOL_NAME_FORBIDDEN" not in codes
