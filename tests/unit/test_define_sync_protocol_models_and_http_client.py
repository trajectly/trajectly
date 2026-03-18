"""Unit coverage for sync protocol models and HTTP client behavior."""

from __future__ import annotations

import json
from typing import Any, cast

import pytest

from trajectly.core.events import make_event
from trajectly.core.sync import (
    SyncClient,
    SyncProject,
    SyncReportEnvelope,
    SyncRequest,
    SyncRunEnvelope,
    SyncTrajectoryEnvelope,
    trajectory_from_trace_events,
)


class _FakeResponse:
    def __init__(self, status: int, body: dict[str, Any]) -> None:
        self.status = status
        self._body = json.dumps(body).encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None


def test_define_sync_protocol_models_and_http_client_happy_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events = [
        make_event(
            event_type="tool_called",
            seq=1,
            run_id="sync-run-1",
            rel_ms=5,
            payload={"tool_name": "search", "input": {"args": ["status"]}},
        ),
        make_event(
            event_type="tool_returned",
            seq=2,
            run_id="sync-run-1",
            rel_ms=8,
            payload={"tool_name": "search", "output": {"value": "ok"}},
        ),
    ]
    trajectory = trajectory_from_trace_events(
        events,
        spec_name="sync-demo",
        mode="replay",
        metadata={"source_path": ".trajectly/current/sync-demo.run.jsonl"},
    )
    request = SyncRequest(
        project=SyncProject(
            slug="sync-demo",
            root_path="/tmp/sync-demo",
            git_sha="abc123",
            trajectly_version="0.4.2",
        ),
        run=SyncRunEnvelope(
            processed_specs=1,
            regressions=0,
            errors=[],
            latest_report_path=".trajectly/reports/latest.json",
            latest_report_sha256="report-sha",
        ),
        reports=[
            SyncReportEnvelope(
                spec="sync-demo",
                slug="sync-demo",
                regression=False,
                spec_path="sync.agent.yaml",
                report_json_path=".trajectly/reports/sync-demo.json",
                report_payload={"summary": {"regression": False}, "findings": []},
                run_id="sync-run-1",
                metadata={"baseline_version": "v1"},
            )
        ],
        trajectories=[
            SyncTrajectoryEnvelope(
                spec="sync-demo",
                slug="sync-demo",
                path=".trajectly/current/sync-demo.run.jsonl",
                run_id="sync-run-1",
                baseline_version="v1",
                trajectory=trajectory,
            )
        ],
    )

    captured: dict[str, Any] = {}

    def _fake_urlopen(http_request: Any, timeout: float) -> _FakeResponse:
        captured["url"] = http_request.full_url
        captured["timeout"] = timeout
        captured["headers"] = {key.lower(): value for key, value in http_request.header_items()}
        captured["body"] = json.loads(http_request.data.decode("utf-8"))
        return _FakeResponse(202, {"accepted": True, "sync_id": "sync-123", "message": "queued"})

    monkeypatch.setattr("trajectly.core.sync.urllib_request.urlopen", _fake_urlopen)

    response = SyncClient(
        endpoint="https://platform.example/api/v1/sync",
        api_key="secret-token",
        timeout_seconds=12.5,
        user_agent="trajectly/0.4.2",
    ).send(request, retries=0)

    assert response.accepted is True
    assert response.sync_id == "sync-123"
    assert response.message == "queued"
    assert response.idempotency_key == request.idempotency_key
    assert captured["url"] == "https://platform.example/api/v1/sync"
    assert captured["timeout"] == 12.5
    assert captured["headers"]["authorization"] == "Bearer secret-token"
    assert captured["headers"]["idempotency-key"] == request.idempotency_key
    assert captured["headers"]["x-trajectly-project-slug"] == "sync-demo"
    assert captured["body"]["reports"][0]["metadata"]["baseline_version"] == "v1"
    assert captured["body"]["trajectories"][0]["trajectory"]["events"][0]["kind"] == "TOOL_CALL"
    assert captured["body"]["trajectories"][0]["trajectory"]["events"][0]["payload"]["__trajectly__"]["seq"] == 1


def test_define_sync_protocol_models_and_http_client_validation_path() -> None:
    with pytest.raises(ValueError, match="endpoint must be an absolute http\\(s\\) URL"):
        SyncClient(endpoint="ftp://platform.example/sync")

    with pytest.raises(ValueError, match=r"project\.slug must be a non-empty string"):
        SyncProject(slug="   ", root_path="/tmp/project", git_sha="abc123", trajectly_version="0.4.2")

    with pytest.raises(ValueError, match=r"request\.reports must contain SyncReportEnvelope instances"):
        SyncRequest(
            project=SyncProject(
                slug="sync-demo",
                root_path="/tmp/sync-demo",
                git_sha="abc123",
                trajectly_version="0.4.2",
            ),
            run=SyncRunEnvelope(
                processed_specs=1,
                regressions=0,
                errors=[],
                latest_report_path=".trajectly/reports/latest.json",
                latest_report_sha256="report-sha",
            ),
            reports=[cast(Any, {"not": "a-report"})],
        )
