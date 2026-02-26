"""TRT decision procedure (Definition 8 in trt_theory.md).

Implements ``evaluate_trt``, the top-level verdict function that composes
abstraction, contract evaluation, skeleton refinement, and witness resolution
into a single deterministic pipeline.

**Soundness guarantee (Theorem 1):** If ``evaluate_trt`` returns PASS, every
configured contract obligation is satisfied and skeleton refinement holds for
the observed traces.

**Determinism guarantee (Theorem 2):** For fixed inputs ``(T_b, T_n, spec)``,
the output (verdict, witness index, violation list) is identical across
invocations — no randomness, no hash-map iteration order dependency, no
parallelism.

**Runtime invariants enforced by assertions:**
- PASS ↔ zero violations (soundness check).
- Witness index == min(event_index) over all violations (minimality check).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal, cast

from trajectly.core.abstraction.pipeline import AbstractionConfig, AbstractTrace, build_abstract_trace
from trajectly.core.constants import FAILURE_CLASS_CONTRACT, SIDE_EFFECT_TOOL_REGISTRY_V1
from trajectly.core.contracts import evaluate_contracts
from trajectly.core.errors import FailureClass
from trajectly.core.events import TraceEvent
from trajectly.core.refinement.checker import RefinementPolicy, check_skeleton_refinement
from trajectly.core.refinement.skeleton import extract_call_skeleton
from trajectly.core.report.schema import TRTReportMetadataV03, TRTReportV03, ViolationV03
from trajectly.core.specs import AgentSpec
from trajectly.core.trt.types import TRTViolation
from trajectly.core.trt.witness import WitnessResolution, resolve_witness

TRTStatus = Literal["PASS", "FAIL", "ERROR"]

_VALID_FAILURE_CLASSES = {"REFINEMENT", "CONTRACT", "TOOLING"}


@dataclass(slots=True)
class TRTResult:
    status: TRTStatus
    report: TRTReportV03
    witness: WitnessResolution | None = None
    contract_violations: list[TRTViolation] = field(default_factory=list)
    refinement_violations: list[TRTViolation] = field(default_factory=list)
    abstraction_current: AbstractTrace | None = None
    abstraction_baseline: AbstractTrace | None = None

    @property
    def all_violations(self) -> list[TRTViolation]:
        return [*self.contract_violations, *self.refinement_violations]


def _token_signature(token_kind: str, token_name: str) -> str:
    if token_kind == "CALL":
        return f"tool:{token_name}"
    if token_kind == "LLM_REQUEST":
        return f"llm:{token_name}"
    if token_kind == "MESSAGE":
        return f"step:{token_name}"
    return f"other:{token_kind}:{token_name}"


def _code_from_classification(classification: str) -> str:
    overrides = {
        "contract_network_domain_denied": "NETWORK_DOMAIN_DENIED",
        "contract_data_leak_secret_pattern": "DATA_LEAK_SECRET_PATTERN",
    }
    override = overrides.get(classification)
    if override is not None:
        return override
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", classification.strip()).strip("_")
    return normalized.upper() if normalized else "CONTRACT_VIOLATION"


def _event_index_from_finding(
    *,
    path: str | None,
    baseline: Any,
    call_tokens: list[tuple[int, str]],
    operations: list[tuple[int, str]],
    fallback_index: int,
) -> int:
    # Map contract finding paths back to concrete trace indices so witness
    # resolution remains actionable for repro workflows.
    if not path:
        return fallback_index

    tool_call_index_match = re.search(r"\$\.tool_calls\[(\d+)\]", path)
    if tool_call_index_match:
        idx = int(tool_call_index_match.group(1))
        if 0 <= idx < len(call_tokens):
            return call_tokens[idx][0]
        return fallback_index

    operation_index_match = re.search(r"\$\.operations\[(\d+)\]", path)
    if operation_index_match:
        idx = int(operation_index_match.group(1))
        if 0 <= idx < len(operations):
            return operations[idx][0]
        return fallback_index

    tool_name_match = re.search(r"\$\.tool_call\.([^.]+)\.", path)
    if tool_name_match:
        tool_name = tool_name_match.group(1)
        for event_index, name in call_tokens:
            if name == tool_name:
                return event_index
        return fallback_index

    per_tool_match = re.search(r"\$\.tool_calls\.([^.]+)$", path)
    if per_tool_match:
        tool_name = per_tool_match.group(1)
        matching_indices = [event_index for event_index, name in call_tokens if name == tool_name]
        if matching_indices:
            if isinstance(baseline, int) and baseline >= 0 and baseline < len(matching_indices):
                return matching_indices[baseline]
            return matching_indices[-1]
    return fallback_index


def _build_contract_violations(
    *,
    current_events: list[TraceEvent],
    current_abstract: AbstractTrace,
    spec: AgentSpec,
) -> list[TRTViolation]:
    violations: list[TRTViolation] = []

    call_tokens = [
        (token.event_index, token.name)
        for token in current_abstract.tokens
        if token.kind == "CALL"
    ]
    operations = [
        (token.event_index, _token_signature(token.kind, token.name))
        for token in current_abstract.tokens
    ]
    fallback_index = operations[-1][0] if operations else 0

    base_findings = evaluate_contracts(current=current_events, contracts=spec.contracts)
    for finding in base_findings:
        event_index = _event_index_from_finding(
            path=finding.path,
            baseline=finding.baseline,
            call_tokens=call_tokens,
            operations=operations,
            fallback_index=fallback_index,
        )
        violations.append(
            TRTViolation(
                code=_code_from_classification(finding.classification),
                message=finding.message,
                failure_class=FAILURE_CLASS_CONTRACT,
                event_index=event_index,
                expected=finding.baseline,
                observed=finding.current,
            )
        )

    for event_index, event in enumerate(current_events):
        if event.event_type not in {"tool_returned", "llm_returned"}:
            continue
        payload = event.payload
        raw_code = payload.get("error_code")
        if raw_code != "FIXTURE_EXHAUSTED":
            continue
        details = payload.get("error_details")
        details_map = details if isinstance(details, dict) else {}
        violations.append(
            TRTViolation(
                code="FIXTURE_EXHAUSTED",
                message=str(payload.get("error") or "Replay fixture exhausted"),
                failure_class=FAILURE_CLASS_CONTRACT,
                event_index=event_index,
                expected={
                    "expected_signature": details_map.get("expected_signature"),
                    "available_count": details_map.get("available_count"),
                },
                observed={
                    "consumed_count": details_map.get("consumed_count"),
                    "tool_name": details_map.get("tool_name"),
                    "llm_signature": details_map.get("llm_signature"),
                },
                hint="Record new fixtures or adjust deterministic replay policy.",
            )
        )

    return violations


def _to_report(
    *,
    status: TRTStatus,
    witness: WitnessResolution | None,
    repro_command: str | None,
    counterexample_paths: dict[str, str],
    metadata: dict[str, Any] | None = None,
) -> TRTReportV03:
    report = TRTReportV03(
        status=status,
        metadata=TRTReportMetadataV03(metadata=metadata or {}),
        repro_command=repro_command,
        counterexample_paths=counterexample_paths,
    )
    if witness is not None:
        primary_failure_class = (
            witness.primary_violation.failure_class
            if witness.primary_violation.failure_class in _VALID_FAILURE_CLASSES
            else "TOOLING"
        )
        report.witness_index = witness.witness_index
        report.failure_class = cast(FailureClass, primary_failure_class)
        report.primary_violation = ViolationV03(
            code=witness.primary_violation.code,
            message=witness.primary_violation.message,
            failure_class=cast(FailureClass, primary_failure_class),
            event_index=witness.primary_violation.event_index,
            expected=witness.primary_violation.expected,
            observed=witness.primary_violation.observed,
            hint=witness.primary_violation.hint,
        )
        report.all_violations_at_witness = [
            ViolationV03(
                code=violation.code,
                message=violation.message,
                failure_class=cast(
                    FailureClass,
                    violation.failure_class if violation.failure_class in _VALID_FAILURE_CLASSES else "TOOLING",
                ),
                event_index=violation.event_index,
                expected=violation.expected,
                observed=violation.observed,
                hint=violation.hint,
            )
            for violation in witness.all_violations_at_witness
        ]
    return report


def evaluate_trt(
    *,
    baseline_events: list[TraceEvent],
    current_events: list[TraceEvent],
    spec: AgentSpec,
    repro_command: str | None = None,
    counterexample_paths: dict[str, str] | None = None,
) -> TRTResult:
    abstraction_cfg = AbstractionConfig(ignore_call_tools=spec.refinement.ignore_call_tools)
    baseline_abs = build_abstract_trace(baseline_events, config=abstraction_cfg)
    current_abs = build_abstract_trace(current_events, config=abstraction_cfg)

    contract_violations = _build_contract_violations(
        current_events=current_events,
        current_abstract=current_abs,
        spec=spec,
    )
    side_effect_tools = set(SIDE_EFFECT_TOOL_REGISTRY_V1)
    refinement_policy = RefinementPolicy(
        mode=spec.refinement.mode,
        allow_extra_tools=spec.refinement.allow_extra_tools,
        allow_extra_side_effect_tools=spec.refinement.allow_extra_side_effect_tools,
        allow_new_tool_names=spec.refinement.allow_new_tool_names,
    )
    baseline_steps = extract_call_skeleton(baseline_abs, ignore_call_tools=set(spec.refinement.ignore_call_tools))
    current_steps = extract_call_skeleton(current_abs, ignore_call_tools=set(spec.refinement.ignore_call_tools))
    refinement_result = check_skeleton_refinement(
        baseline_steps=baseline_steps,
        current_steps=current_steps,
        policy=refinement_policy,
        side_effect_tools=side_effect_tools,
    )

    all_violations = [*refinement_result.violations, *contract_violations]
    witness = resolve_witness(all_violations)
    status: TRTStatus = "FAIL" if all_violations else "PASS"

    assert (status == "PASS") == (len(all_violations) == 0), (
        "Soundness: PASS iff zero violations"
    )
    if witness is not None:
        assert status == "FAIL", "Witness exists only when FAIL"
        assert witness.witness_index == min(v.event_index for v in all_violations), (
            "Witness minimality: witness_index == min(event_index)"
        )
    report = _to_report(
        status=status,
        witness=witness,
        repro_command=repro_command,
        counterexample_paths=counterexample_paths or {},
        metadata={
            "refinement_skeleton_vacuous": refinement_result.refinement_skeleton_vacuous,
            "baseline_legacy_compat": spec.legacy_compat,
        },
    )

    return TRTResult(
        status=status,
        report=report,
        witness=witness,
        contract_violations=contract_violations,
        refinement_violations=refinement_result.violations,
        abstraction_current=current_abs,
        abstraction_baseline=baseline_abs,
    )


__all__ = [
    "TRTResult",
    "evaluate_trt",
]
