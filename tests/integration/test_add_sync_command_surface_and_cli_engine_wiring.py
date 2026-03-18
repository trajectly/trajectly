"""Integration coverage for the `trajectly sync` command surface."""

from __future__ import annotations

import json
from pathlib import Path

from tests.integration.sync_support import PlannedSyncResponse, prepare_sync_workspace, runner, serve_sync_endpoint
from trajectly.cli import app


def test_add_sync_command_surface_and_cli_engine_wiring_integration_happy_path(tmp_path: Path) -> None:
    prepare_sync_workspace(tmp_path)

    with serve_sync_endpoint(
        [PlannedSyncResponse(status=202, body={"accepted": True, "sync_id": "sync-123", "message": "queued"})]
    ) as server:
        result = runner.invoke(
            app,
            [
                "sync",
                "--project-root",
                str(tmp_path),
                "--endpoint",
                server.url,
                "--api-key",
                "secret-token",
                "--project-slug",
                "demo-sync",
            ],
        )

    assert result.exit_code == 0, result.output
    assert "Synced 1 report(s) and 1 trajectory bundle(s)" in result.output
    assert "Server message: queued" in result.output
    assert len(server.requests) == 1
    request = server.requests[0]
    assert request.headers["Authorization"] == "Bearer secret-token"
    assert request.headers["Idempotency-Key"]
    assert request.payload["project"]["slug"] == "demo-sync"
    assert request.payload["run"]["processed_specs"] == 1
    assert request.payload["reports"][0]["spec"] == "sync-demo"
    assert request.payload["trajectories"][0]["path"] == ".trajectly/current/sync-demo.run.jsonl"

    metadata_path = tmp_path / ".trajectly" / "sync" / "latest.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["project_slug"] == "demo-sync"
    assert metadata["sync_id"] == "sync-123"


def test_add_sync_command_surface_and_cli_engine_wiring_integration_error_path(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "sync",
            "--project-root",
            str(tmp_path),
            "--endpoint",
            "https://platform.example/api/v1/sync",
        ],
    )

    assert result.exit_code == 2
    assert "Latest report not found" in result.output
