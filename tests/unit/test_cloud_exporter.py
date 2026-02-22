from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from trajectly.plugins.cloud_exporter import CloudRunHookExporter


class _ResponseContext:
    def __enter__(self) -> _ResponseContext:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        _ = exc_type
        _ = exc
        _ = tb


def _write_report(path: Path) -> None:
    payload = {
        "schema_version": "v1",
        "summary": {
            "regression": True,
            "finding_count": 1,
            "classifications": {"runtime_error": 1},
            "baseline": {"duration_ms": 1, "tool_calls": 1, "tokens": 0},
            "current": {"duration_ms": 2, "tool_calls": 1, "tokens": 0},
        },
        "findings": [{"classification": "runtime_error", "message": "boom", "path": None}],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_from_env_missing(monkeypatch) -> None:
    monkeypatch.delenv("TRAJECTLY_CLOUD_API_BASE_URL", raising=False)
    monkeypatch.delenv("TRAJECTLY_CLOUD_API_KEY", raising=False)

    assert CloudRunHookExporter.from_env() is None


def test_on_run_finished_posts_payload(monkeypatch, tmp_path: Path) -> None:
    report_json = tmp_path / "spec.json"
    report_md = tmp_path / "spec.md"
    baseline = tmp_path / "base.jsonl"
    current = tmp_path / "current.jsonl"
    _write_report(report_json)
    report_md.write_text("# md", encoding="utf-8")
    baseline.write_text("[]", encoding="utf-8")
    current.write_text("[]", encoding="utf-8")

    captured: dict[str, Any] = {}

    def _fake_urlopen(request: urllib.request.Request, timeout: float):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["auth"] = request.headers.get("Authorization")
        captured["idem"] = request.headers.get("X-idempotency-key")
        body = request.data.decode("utf-8") if isinstance(request.data, bytes) else ""
        captured["payload"] = json.loads(body)
        return _ResponseContext()

    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)

    exporter = CloudRunHookExporter(api_base_url="https://cloud.trajectly.dev", api_key="secret", max_retries=1)
    exporter.on_run_finished(
        context={
            "schema_version": "v1",
            "spec": "example-regression",
            "slug": "example-regression",
            "run_id": "run-123",
            "regression": True,
        },
        report_paths={"json": report_json, "markdown": report_md, "baseline": baseline, "current": current},
    )

    assert captured["url"] == "https://cloud.trajectly.dev/api/v1/runs/ingest"
    assert captured["auth"] == "Bearer secret"
    assert captured["idem"] == "run-123"
    assert captured["payload"]["run_id"] == "run-123"
    assert captured["payload"]["reports"]["example-regression"]["schema_version"] == "v1"


def test_on_run_finished_retries_on_url_error(monkeypatch, tmp_path: Path) -> None:
    report_json = tmp_path / "spec.json"
    report_md = tmp_path / "spec.md"
    _write_report(report_json)
    report_md.write_text("# md", encoding="utf-8")

    attempts = {"count": 0}

    def _flaky_urlopen(request: urllib.request.Request, timeout: float):
        _ = request
        _ = timeout
        attempts["count"] += 1
        if attempts["count"] < 2:
            raise urllib.error.URLError("temporary")
        return _ResponseContext()

    monkeypatch.setattr(urllib.request, "urlopen", _flaky_urlopen)

    exporter = CloudRunHookExporter(api_base_url="https://cloud.trajectly.dev", api_key="secret", max_retries=2)
    exporter.on_run_finished(
        context={"schema_version": "v1", "spec": "example-regression", "run_id": "run-123", "regression": True},
        report_paths={"json": report_json, "markdown": report_md},
    )

    assert attempts["count"] == 2
