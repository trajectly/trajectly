from __future__ import annotations

from pathlib import Path

# Legacy schema version used by pre-TRT modules. This remains until full v0.3 cutover.
SCHEMA_VERSION = "v1"

# TRT v0.4 contract versions.
TRT_SPEC_SCHEMA_VERSION = "0.4"
TRT_TRACE_SCHEMA_VERSION = "0.4"
TRT_REPORT_SCHEMA_VERSION = "0.4"
TRT_NORMALIZER_VERSION = "1"
TRT_SIDE_EFFECT_REGISTRY_VERSION = "1"

# Structured nondeterminism codes.
NONDETERMINISM_CLOCK_DETECTED = "NONDETERMINISM_CLOCK_DETECTED"
NONDETERMINISM_RANDOM_DETECTED = "NONDETERMINISM_RANDOM_DETECTED"
NONDETERMINISM_UUID_DETECTED = "NONDETERMINISM_UUID_DETECTED"
NONDETERMINISM_FILESYSTEM_DETECTED = "NONDETERMINISM_FILESYSTEM_DETECTED"

# TRT failure classes and deterministic witness ordering.
FAILURE_CLASS_REFINEMENT = "REFINEMENT"
FAILURE_CLASS_CONTRACT = "CONTRACT"
FAILURE_CLASS_TOOLING = "TOOLING"
WITNESS_FAILURE_CLASS_ORDER = (
    FAILURE_CLASS_REFINEMENT,
    FAILURE_CLASS_CONTRACT,
    FAILURE_CLASS_TOOLING,
)

# Built-in side-effect tool registry v1 (deterministic default policy seed).
SIDE_EFFECT_TOOL_REGISTRY_V1 = (
    "checkout",
    "create_refund",
    "send_email",
    "db_write",
    "filesystem_write",
    "http_request",
)

STATE_DIR = Path(".trajectly")
BASELINES_DIR = STATE_DIR / "baselines"
CURRENT_DIR = STATE_DIR / "current"
FIXTURES_DIR = STATE_DIR / "fixtures"
REPORTS_DIR = STATE_DIR / "reports"
TMP_DIR = STATE_DIR / "tmp"
REPROS_DIR = STATE_DIR / "repros"

TRACE_EVENT_TYPES = {
    "run_started",
    "agent_step",
    "llm_called",
    "llm_returned",
    "tool_called",
    "tool_returned",
    "run_finished",
}

EXIT_SUCCESS = 0
EXIT_REGRESSION = 1
EXIT_INTERNAL_ERROR = 2
