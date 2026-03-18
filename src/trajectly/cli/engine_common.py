"""Shared state and path helpers for engine commands (record, run, repro). QA-T006."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from trajectly.constants import (
    BASELINES_DIR,
    CURRENT_DIR,
    FIXTURES_DIR,
    REPORTS_DIR,
    REPROS_DIR,
    STATE_DIR,
    SYNC_DIR,
    TMP_DIR,
)


@dataclass(slots=True)
class CommandOutcome:
    """Represent `CommandOutcome`."""
    exit_code: int
    processed_specs: int
    regressions: int = 0
    errors: list[str] = field(default_factory=list)
    latest_report_json: Path | None = None
    latest_report_md: Path | None = None


@dataclass(slots=True)
class _StatePaths:
    """Represent `_StatePaths`."""
    root: Path
    state: Path
    baselines: Path
    current: Path
    fixtures: Path
    reports: Path
    repros: Path
    sync: Path
    tmp: Path


@dataclass(slots=True)
class SyncMetadata:
    """Persist the last successful workspace sync summary inside `.trajectly/`."""

    endpoint: str
    project_slug: str
    idempotency_key: str
    synced_at: str
    latest_report_path: str
    latest_report_sha256: str
    processed_specs: int
    report_count: int
    trajectory_count: int
    status: str
    sync_id: str | None = None
    message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize sync metadata to a deterministic JSON-ready mapping."""

        payload: dict[str, Any] = {
            "endpoint": self.endpoint,
            "project_slug": self.project_slug,
            "idempotency_key": self.idempotency_key,
            "synced_at": self.synced_at,
            "latest_report_path": self.latest_report_path,
            "latest_report_sha256": self.latest_report_sha256,
            "processed_specs": self.processed_specs,
            "report_count": self.report_count,
            "trajectory_count": self.trajectory_count,
            "status": self.status,
        }
        if self.sync_id is not None:
            payload["sync_id"] = self.sync_id
        if self.message is not None:
            payload["message"] = self.message
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SyncMetadata:
        """Load and validate persisted sync metadata."""

        required_string_fields = (
            "endpoint",
            "project_slug",
            "idempotency_key",
            "synced_at",
            "latest_report_path",
            "latest_report_sha256",
            "status",
        )
        for field_name in required_string_fields:
            value = data.get(field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Sync metadata requires non-empty string `{field_name}`")

        required_int_fields = ("processed_specs", "report_count", "trajectory_count")
        for field_name in required_int_fields:
            value = data.get(field_name)
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"Sync metadata requires non-negative integer `{field_name}`")

        sync_id = data.get("sync_id")
        if sync_id is not None and not isinstance(sync_id, str):
            raise ValueError("Sync metadata field `sync_id` must be a string when provided")
        message = data.get("message")
        if message is not None and not isinstance(message, str):
            raise ValueError("Sync metadata field `message` must be a string when provided")

        return cls(
            endpoint=str(data["endpoint"]),
            project_slug=str(data["project_slug"]),
            idempotency_key=str(data["idempotency_key"]),
            synced_at=str(data["synced_at"]),
            latest_report_path=str(data["latest_report_path"]),
            latest_report_sha256=str(data["latest_report_sha256"]),
            processed_specs=int(data["processed_specs"]),
            report_count=int(data["report_count"]),
            trajectory_count=int(data["trajectory_count"]),
            status=str(data["status"]),
            sync_id=sync_id,
            message=message,
        )


def _slugify(value: str) -> str:
    """Execute `_slugify`."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower())
    slug = slug.strip("-")
    return slug or "spec"


def _state_paths(project_root: Path) -> _StatePaths:
    """Execute `_state_paths`."""
    state = project_root / STATE_DIR
    return _StatePaths(
        root=project_root,
        state=state,
        baselines=project_root / BASELINES_DIR,
        current=project_root / CURRENT_DIR,
        fixtures=project_root / FIXTURES_DIR,
        reports=project_root / REPORTS_DIR,
        repros=project_root / REPROS_DIR,
        sync=project_root / SYNC_DIR,
        tmp=project_root / TMP_DIR,
    )


def _baseline_meta_path(baseline_trace_path: Path) -> Path:
    """Execute `_baseline_meta_path`."""
    return baseline_trace_path.with_name(f"{baseline_trace_path.stem}.meta.json")


def _ensure_state_dirs(paths: _StatePaths) -> None:
    """Execute `_ensure_state_dirs`."""
    directories = [
        paths.state,
        paths.baselines,
        paths.current,
        paths.fixtures,
        paths.reports,
        paths.repros,
        paths.sync,
        paths.tmp,
    ]
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)


def _sync_metadata_path(paths: _StatePaths) -> Path:
    """Return the canonical path for the latest workspace sync metadata file."""

    return paths.sync / "latest.json"


def _write_sync_metadata(paths: _StatePaths, metadata: SyncMetadata | dict[str, Any]) -> Path:
    """Persist validated sync metadata under `.trajectly/sync/latest.json`."""

    validated = metadata if isinstance(metadata, SyncMetadata) else SyncMetadata.from_dict(metadata)
    path = _sync_metadata_path(paths)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(validated.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return path


def _read_sync_metadata(paths: _StatePaths) -> SyncMetadata:
    """Read the latest workspace sync metadata file."""

    path = _sync_metadata_path(paths)
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Sync metadata payload must be an object")
    return SyncMetadata.from_dict(raw)
