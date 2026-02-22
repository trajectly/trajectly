from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from trajectly.plugins.interfaces import RunHookPlugin


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower())
    slug = slug.strip("-")
    return slug or "spec"


class CloudRunHookExporter(RunHookPlugin):
    """Reference run-hook exporter for Trajectly cloud ingestion API."""

    def __init__(
        self,
        api_base_url: str,
        api_key: str,
        timeout_seconds: float = 8.0,
        max_retries: int = 2,
    ) -> None:
        self._api_base_url = api_base_url.rstrip("/")
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries

    @classmethod
    def from_env(cls) -> CloudRunHookExporter | None:
        api_base_url = os.getenv("TRAJECTLY_CLOUD_API_BASE_URL", "").strip()
        api_key = os.getenv("TRAJECTLY_CLOUD_API_KEY", "").strip()
        if not api_base_url or not api_key:
            return None

        timeout_seconds_raw = os.getenv("TRAJECTLY_CLOUD_TIMEOUT_SECONDS", "8")
        max_retries_raw = os.getenv("TRAJECTLY_CLOUD_MAX_RETRIES", "2")
        try:
            timeout_seconds = float(timeout_seconds_raw)
        except ValueError:
            timeout_seconds = 8.0
        try:
            max_retries = int(max_retries_raw)
        except ValueError:
            max_retries = 2

        return cls(
            api_base_url=api_base_url,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )

    def on_run_finished(self, context: dict[str, Any], report_paths: dict[str, Path]) -> None:
        report_json_path = report_paths.get("json")
        report_markdown_path = report_paths.get("markdown")
        baseline_path = report_paths.get("baseline")
        current_path = report_paths.get("current")

        if report_json_path is None or report_markdown_path is None:
            raise ValueError("Cloud exporter requires json and markdown report paths")

        report_payload = json.loads(report_json_path.read_text(encoding="utf-8"))

        spec_name = str(context.get("spec", "spec"))
        slug = str(context.get("slug", _slugify(spec_name)))
        schema_version = str(context.get("schema_version", "v1"))
        run_id = str(context.get("run_id", f"{slug}-run"))
        is_regression = bool(context.get("regression", False))

        latest = {
            "schema_version": schema_version,
            "processed_specs": 1,
            "regressions": 1 if is_regression else 0,
            "errors": [],
            "reports": [
                {
                    "spec": spec_name,
                    "slug": slug,
                    "regression": is_regression,
                    "report_json": str(report_json_path),
                    "report_md": str(report_markdown_path),
                    "baseline": str(baseline_path) if baseline_path else "",
                    "current": str(current_path) if current_path else "",
                }
            ],
        }

        payload = {
            "schema_version": schema_version,
            "run_id": run_id,
            "latest": latest,
            "reports": {slug: report_payload},
        }

        request = urllib.request.Request(
            url=f"{self._api_base_url}/api/v1/runs/ingest",
            method="POST",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
                "X-Idempotency-Key": run_id,
            },
        )

        attempts = self._max_retries + 1
        for attempt in range(attempts):
            try:
                with urllib.request.urlopen(request, timeout=self._timeout_seconds):
                    return
            except urllib.error.HTTPError as exc:
                status = getattr(exc, "code", 0)
                if status < 500 or attempt >= attempts - 1:
                    raise
                time.sleep(0.1 * (attempt + 1))
            except urllib.error.URLError:
                if attempt >= attempts - 1:
                    raise
                time.sleep(0.1 * (attempt + 1))
