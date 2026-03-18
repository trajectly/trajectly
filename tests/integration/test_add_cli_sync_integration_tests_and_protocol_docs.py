"""Integration coverage for sync retries and the protocol documentation."""

from __future__ import annotations

from pathlib import Path

from tests.integration.sync_support import PlannedSyncResponse, prepare_sync_workspace, runner, serve_sync_endpoint
from trajectly.cli import app


def test_add_cli_sync_integration_tests_and_protocol_docs_integration_happy_path(tmp_path: Path) -> None:
    prepare_sync_workspace(tmp_path)

    with serve_sync_endpoint(
        [
            PlannedSyncResponse(status=503, body={"message": "try-again"}),
            PlannedSyncResponse(status=202, body={"accepted": True, "sync_id": "sync-456"}),
        ]
    ) as server:
        result = runner.invoke(
            app,
            [
                "sync",
                "--project-root",
                str(tmp_path),
                "--endpoint",
                server.url,
                "--retries",
                "2",
            ],
        )

    assert result.exit_code == 0, result.output
    assert len(server.requests) == 2
    first_idempotency = server.requests[0].headers["Idempotency-Key"]
    second_idempotency = server.requests[1].headers["Idempotency-Key"]
    assert first_idempotency == second_idempotency

    docs_path = Path(__file__).resolve().parents[2] / "docs" / "platform_sync_protocol.md"
    docs_text = docs_path.read_text(encoding="utf-8")
    assert "POST /api/v1/sync" in docs_text
    assert "Idempotency-Key" in docs_text


def test_add_cli_sync_integration_tests_and_protocol_docs_integration_error_path(tmp_path: Path) -> None:
    prepare_sync_workspace(tmp_path)

    with serve_sync_endpoint(
        [PlannedSyncResponse(status=401, body={"message": "unauthorized"})]
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

    assert result.exit_code == 2
    assert "HTTP 401" in result.output
    assert len(server.requests) == 1
    assert not (tmp_path / ".trajectly" / "sync" / "latest.json").exists()
