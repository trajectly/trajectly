"""Shared state and path helpers for engine commands (record, run, repro). QA-T006."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from trajectly.constants import (
    BASELINES_DIR,
    CURRENT_DIR,
    FIXTURES_DIR,
    REPORTS_DIR,
    REPROS_DIR,
    STATE_DIR,
    TMP_DIR,
)


@dataclass(slots=True)
class CommandOutcome:
    exit_code: int
    processed_specs: int
    regressions: int = 0
    errors: list[str] = field(default_factory=list)
    latest_report_json: Path | None = None
    latest_report_md: Path | None = None


@dataclass(slots=True)
class _StatePaths:
    root: Path
    state: Path
    baselines: Path
    current: Path
    fixtures: Path
    reports: Path
    repros: Path
    tmp: Path


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower())
    slug = slug.strip("-")
    return slug or "spec"


def _state_paths(project_root: Path) -> _StatePaths:
    state = project_root / STATE_DIR
    return _StatePaths(
        root=project_root,
        state=state,
        baselines=project_root / BASELINES_DIR,
        current=project_root / CURRENT_DIR,
        fixtures=project_root / FIXTURES_DIR,
        reports=project_root / REPORTS_DIR,
        repros=project_root / REPROS_DIR,
        tmp=project_root / TMP_DIR,
    )


def _baseline_meta_path(baseline_trace_path: Path) -> Path:
    return baseline_trace_path.with_name(f"{baseline_trace_path.stem}.meta.json")


def _ensure_state_dirs(paths: _StatePaths) -> None:
    directories = [
        paths.state,
        paths.baselines,
        paths.current,
        paths.fixtures,
        paths.reports,
        paths.repros,
        paths.tmp,
    ]
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
