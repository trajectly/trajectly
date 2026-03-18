"""Shared helpers for CLI sync integration coverage."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from textwrap import dedent
from typing import Any

from typer.testing import CliRunner

from trajectly.cli import app

runner = CliRunner()


def _write(path: Path, content: str) -> None:
    path.write_text(dedent(content).strip() + "\n", encoding="utf-8")


def prepare_sync_workspace(tmp_path: Path) -> Path:
    """Create a recorded-and-run workspace with one passing spec ready for sync."""

    agent = tmp_path / "agent.py"
    _write(
        agent,
        """
        from trajectly.sdk import agent_step, tool

        @tool("echo")
        def echo(text):
            return text

        agent_step("start")
        echo("sync-ready")
        agent_step("done")
        """,
    )

    spec = tmp_path / "sync.agent.yaml"
    _write(
        spec,
        """
        schema_version: "0.4"
        name: sync-demo
        command: python agent.py
        workdir: .
        strict: true
        """,
    )

    init_result = runner.invoke(app, ["init", str(tmp_path)])
    assert init_result.exit_code == 0, init_result.output

    record_result = runner.invoke(app, ["record", str(spec), "--project-root", str(tmp_path)])
    assert record_result.exit_code == 0, record_result.output

    run_result = runner.invoke(app, ["run", str(spec), "--project-root", str(tmp_path)])
    assert run_result.exit_code == 0, run_result.output

    return spec


@dataclass(slots=True)
class RecordedSyncRequest:
    """Captured request metadata from the local test sync server."""

    path: str
    headers: dict[str, str]
    payload: dict[str, Any]


@dataclass(slots=True)
class PlannedSyncResponse:
    """One queued HTTP response for the local test sync server."""

    status: int
    body: dict[str, Any] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class SyncServerHandle:
    """Mutable handle returned to integration tests for assertions."""

    url: str
    requests: list[RecordedSyncRequest]


@contextmanager
def serve_sync_endpoint(responses: list[PlannedSyncResponse] | None = None) -> Iterator[SyncServerHandle]:
    """Serve queued JSON responses and capture incoming sync requests."""

    recorded_requests: list[RecordedSyncRequest] = []
    queued_responses = list(responses or [PlannedSyncResponse(status=200, body={"accepted": True})])

    class SyncHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            content_length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_length)
            payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
            recorded_requests.append(
                RecordedSyncRequest(
                    path=self.path,
                    headers={key: value for key, value in self.headers.items()},
                    payload=payload,
                )
            )

            planned = queued_responses.pop(0) if queued_responses else PlannedSyncResponse(status=200, body={})
            body = json.dumps(planned.body).encode("utf-8")

            self.send_response(planned.status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            for key, value in planned.headers.items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = HTTPServer(("127.0.0.1", 0), SyncHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = int(server.server_address[1])
        yield SyncServerHandle(url=f"http://127.0.0.1:{port}/sync", requests=recorded_requests)
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
