"""End-to-end coverage for the `trajectly sync` workflow."""

from __future__ import annotations

import json
from pathlib import Path

from tests.integration.sync_support import PlannedSyncResponse, prepare_sync_workspace, runner, serve_sync_endpoint
from trajectly.cli import app


def test_cli_sync_pushes_latest_report_and_trajectory(tmp_path: Path) -> None:
    prepare_sync_workspace(tmp_path)

    with serve_sync_endpoint(
        [PlannedSyncResponse(status=202, body={"accepted": True, "sync_id": "sync-789"})]
    ) as server:
        result = runner.invoke(
            app,
            [
                "sync",
                "--project-root",
                str(tmp_path),
                "--endpoint",
                server.url,
            ],
        )

    assert result.exit_code == 0, result.output
    assert len(server.requests) == 1
    payload = server.requests[0].payload
    assert payload["run"]["processed_specs"] == 1
    assert payload["reports"][0]["report_payload"]["summary"]["regression"] is False
    assert payload["trajectories"][0]["trajectory"]["meta"]["spec_name"] == "sync-demo"


def test_cli_sync_dry_run_builds_payload_without_network_side_effects(tmp_path: Path) -> None:
    prepare_sync_workspace(tmp_path)

    result = runner.invoke(
        app,
        [
            "sync",
            "--project-root",
            str(tmp_path),
            "--endpoint",
            "https://platform.example/api/v1/sync",
            "--dry-run",
            "--project-slug",
            "demo-dry-run",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Prepared 1 report(s) and 1 trajectory bundle(s)" in result.output
    assert "Idempotency key:" in result.output
    assert not (tmp_path / ".trajectly" / "sync" / "latest.json").exists()


def test_cli_sync_uses_relative_workspace_paths_in_payload(tmp_path: Path) -> None:
    prepare_sync_workspace(tmp_path)

    with serve_sync_endpoint(
        [PlannedSyncResponse(status=202, body={"accepted": True, "sync_id": "sync-relative"})]
    ) as server:
        result = runner.invoke(
            app,
            [
                "sync",
                "--project-root",
                str(tmp_path),
                "--endpoint",
                server.url,
            ],
        )

    assert result.exit_code == 0, result.output
    payload = server.requests[0].payload
    assert payload["run"]["latest_report_path"] == ".trajectly/reports/latest.json"
    assert payload["reports"][0]["report_json_path"] == ".trajectly/reports/sync-demo.json"
    assert payload["trajectories"][0]["path"] == ".trajectly/current/sync-demo.run.jsonl"

    metadata = json.loads((tmp_path / ".trajectly" / "sync" / "latest.json").read_text(encoding="utf-8"))
    assert metadata["latest_report_path"] == ".trajectly/reports/latest.json"
