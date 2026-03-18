"""Unit coverage for persisted workspace sync metadata artifacts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from trajectly.constants import SYNC_DIR
from trajectly.engine_common import (
    SyncMetadata,
    _ensure_state_dirs,
    _read_sync_metadata,
    _state_paths,
    _sync_metadata_path,
    _write_sync_metadata,
)


def test_persist_sync_metadata_in_workspace_artifacts_happy_path(tmp_path: Path) -> None:
    paths = _state_paths(tmp_path)
    _ensure_state_dirs(paths)

    metadata = SyncMetadata(
        endpoint="https://platform.example/api/v1/sync",
        project_slug="sync-demo",
        idempotency_key="idem-123",
        synced_at="2026-03-18T12:00:00+00:00",
        latest_report_path=".trajectly/reports/latest.json",
        latest_report_sha256="report-sha",
        processed_specs=2,
        report_count=2,
        trajectory_count=2,
        status="accepted",
        sync_id="sync-123",
        message="queued",
    )

    written_path = _write_sync_metadata(paths, metadata)
    loaded = _read_sync_metadata(paths)
    raw = json.loads(written_path.read_text(encoding="utf-8"))

    assert written_path == tmp_path / SYNC_DIR / "latest.json"
    assert _sync_metadata_path(paths) == written_path
    assert loaded == metadata
    assert raw["project_slug"] == "sync-demo"
    assert raw["trajectory_count"] == 2


def test_persist_sync_metadata_in_workspace_artifacts_validation_path(tmp_path: Path) -> None:
    paths = _state_paths(tmp_path)
    _ensure_state_dirs(paths)

    with pytest.raises(ValueError, match="Sync metadata requires non-empty string `endpoint`"):
        _write_sync_metadata(
            paths,
            {
                "endpoint": "",
                "project_slug": "sync-demo",
                "idempotency_key": "idem-123",
                "synced_at": "2026-03-18T12:00:00+00:00",
                "latest_report_path": ".trajectly/reports/latest.json",
                "latest_report_sha256": "report-sha",
                "processed_specs": 1,
                "report_count": 1,
                "trajectory_count": 1,
                "status": "accepted",
            },
        )

    bad_payload_path = _sync_metadata_path(paths)
    bad_payload_path.write_text(json.dumps(["not-an-object"]), encoding="utf-8")

    with pytest.raises(ValueError, match="Sync metadata payload must be an object"):
        _read_sync_metadata(paths)
