from __future__ import annotations

from pathlib import Path

SCHEMA_VERSION = "v1"
STATE_DIR = Path(".trajectly")
BASELINES_DIR = STATE_DIR / "baselines"
CURRENT_DIR = STATE_DIR / "current"
FIXTURES_DIR = STATE_DIR / "fixtures"
REPORTS_DIR = STATE_DIR / "reports"
TMP_DIR = STATE_DIR / "tmp"

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
