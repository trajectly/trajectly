"""Portable workspace sync protocol and HTTP client for platform ingestion."""

from __future__ import annotations

import json
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request

from trajectly.core.canonical import canonical_dumps, sha256_of_data
from trajectly.core.events import TraceEvent, compute_event_id
from trajectly.core.trace.models import EventKindV03, TraceEventV03, TraceMetaV03, TrajectoryV03

SYNC_PROTOCOL_VERSION = "v1"
RETRYABLE_STATUS_CODES = frozenset({408, 409, 425, 429, 500, 502, 503, 504})

_EVENT_KIND_BY_EVENT_TYPE: dict[str, EventKindV03] = {
    "tool_called": "TOOL_CALL",
    "tool_returned": "TOOL_RESULT",
    "llm_called": "LLM_REQUEST",
    "llm_returned": "LLM_RESPONSE",
    "agent_step": "MESSAGE",
    "run_started": "OBSERVATION",
    "run_finished": "OBSERVATION",
}


class SyncError(RuntimeError):
    """Base exception for sync protocol and transport failures."""


class SyncTransportError(SyncError):
    """Represent a transport-level failure while uploading a sync request."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        body: str | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body
        self.retryable = retryable


def _require_non_empty_string(value: str, *, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must be a non-empty string")
    return normalized


def _validate_string_or_none(value: str | None, *, field_name: str) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must be a non-empty string when provided")
    return normalized


def _validate_endpoint(endpoint: str) -> str:
    normalized = _require_non_empty_string(endpoint, field_name="endpoint")
    parsed = urllib_parse.urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("endpoint must be an absolute http(s) URL")
    return normalized


def _coerce_json_object(value: Any, *, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a JSON object")
    return dict(value)


@dataclass(slots=True)
class SyncProject:
    """Project-level metadata attached to each sync request."""

    slug: str
    root_path: str
    git_sha: str
    trajectly_version: str

    def __post_init__(self) -> None:
        self.slug = _require_non_empty_string(self.slug, field_name="project.slug")
        self.root_path = _require_non_empty_string(self.root_path, field_name="project.root_path")
        self.git_sha = _require_non_empty_string(self.git_sha, field_name="project.git_sha")
        self.trajectly_version = _require_non_empty_string(
            self.trajectly_version,
            field_name="project.trajectly_version",
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize this project envelope."""

        return {
            "slug": self.slug,
            "root_path": self.root_path,
            "git_sha": self.git_sha,
            "trajectly_version": self.trajectly_version,
        }


@dataclass(slots=True)
class SyncRunEnvelope:
    """Top-level latest-run summary attached to a sync request."""

    processed_specs: int
    regressions: int
    errors: list[str]
    latest_report_path: str
    latest_report_sha256: str
    trt_mode: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.processed_specs, int) or self.processed_specs < 0:
            raise ValueError("run.processed_specs must be a non-negative integer")
        if not isinstance(self.regressions, int) or self.regressions < 0:
            raise ValueError("run.regressions must be a non-negative integer")
        if not isinstance(self.errors, list) or any(not isinstance(item, str) for item in self.errors):
            raise ValueError("run.errors must be a list of strings")
        self.errors = [item for item in self.errors]
        self.latest_report_path = _require_non_empty_string(
            self.latest_report_path,
            field_name="run.latest_report_path",
        )
        self.latest_report_sha256 = _require_non_empty_string(
            self.latest_report_sha256,
            field_name="run.latest_report_sha256",
        )
        if not isinstance(self.trt_mode, bool):
            raise ValueError("run.trt_mode must be a boolean")

    def to_dict(self) -> dict[str, Any]:
        """Serialize this run envelope."""

        return {
            "processed_specs": self.processed_specs,
            "regressions": self.regressions,
            "errors": list(self.errors),
            "latest_report_path": self.latest_report_path,
            "latest_report_sha256": self.latest_report_sha256,
            "trt_mode": self.trt_mode,
        }


@dataclass(slots=True)
class SyncReportEnvelope:
    """Per-spec report payload included in a sync request."""

    spec: str
    slug: str
    regression: bool
    spec_path: str
    report_json_path: str
    report_payload: dict[str, Any]
    run_id: str | None = None
    report_md_path: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.spec = _require_non_empty_string(self.spec, field_name="report.spec")
        self.slug = _require_non_empty_string(self.slug, field_name="report.slug")
        if not isinstance(self.regression, bool):
            raise ValueError("report.regression must be a boolean")
        self.spec_path = _require_non_empty_string(self.spec_path, field_name="report.spec_path")
        self.report_json_path = _require_non_empty_string(
            self.report_json_path,
            field_name="report.report_json_path",
        )
        self.report_payload = _coerce_json_object(self.report_payload, field_name="report.report_payload")
        self.run_id = _validate_string_or_none(self.run_id, field_name="report.run_id")
        self.report_md_path = _validate_string_or_none(self.report_md_path, field_name="report.report_md_path")
        self.metadata = _coerce_json_object(self.metadata, field_name="report.metadata")

    def to_dict(self) -> dict[str, Any]:
        """Serialize this per-spec report envelope."""

        payload: dict[str, Any] = {
            "spec": self.spec,
            "slug": self.slug,
            "regression": self.regression,
            "spec_path": self.spec_path,
            "report_json_path": self.report_json_path,
            "report_payload": self.report_payload,
            "metadata": self.metadata,
        }
        if self.run_id is not None:
            payload["run_id"] = self.run_id
        if self.report_md_path is not None:
            payload["report_md_path"] = self.report_md_path
        return payload


@dataclass(slots=True)
class SyncTrajectoryEnvelope:
    """Portable trajectory bundle included in a sync request."""

    spec: str
    slug: str
    path: str
    trajectory: TrajectoryV03
    kind: Literal["current", "baseline"] = "current"
    run_id: str | None = None
    baseline_version: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.spec = _require_non_empty_string(self.spec, field_name="trajectory.spec")
        self.slug = _require_non_empty_string(self.slug, field_name="trajectory.slug")
        self.path = _require_non_empty_string(self.path, field_name="trajectory.path")
        if self.kind not in {"current", "baseline"}:
            raise ValueError("trajectory.kind must be one of: current, baseline")
        if not isinstance(self.trajectory, TrajectoryV03):
            raise ValueError("trajectory.trajectory must be a TrajectoryV03 instance")
        self.run_id = _validate_string_or_none(self.run_id, field_name="trajectory.run_id")
        self.baseline_version = _validate_string_or_none(
            self.baseline_version,
            field_name="trajectory.baseline_version",
        )
        self.metadata = _coerce_json_object(self.metadata, field_name="trajectory.metadata")

    def to_dict(self) -> dict[str, Any]:
        """Serialize this trajectory envelope."""

        payload: dict[str, Any] = {
            "spec": self.spec,
            "slug": self.slug,
            "kind": self.kind,
            "path": self.path,
            "trajectory": self.trajectory.to_dict(),
            "metadata": self.metadata,
        }
        if self.run_id is not None:
            payload["run_id"] = self.run_id
        if self.baseline_version is not None:
            payload["baseline_version"] = self.baseline_version
        return payload


@dataclass(slots=True)
class SyncRequest:
    """Deterministic payload uploaded by `trajectly sync`."""

    project: SyncProject
    run: SyncRunEnvelope
    reports: list[SyncReportEnvelope] = field(default_factory=list)
    trajectories: list[SyncTrajectoryEnvelope] = field(default_factory=list)
    generated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    schema_version: str = SYNC_PROTOCOL_VERSION
    protocol_version: str = SYNC_PROTOCOL_VERSION
    idempotency_key: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.project, SyncProject):
            raise ValueError("request.project must be a SyncProject instance")
        if not isinstance(self.run, SyncRunEnvelope):
            raise ValueError("request.run must be a SyncRunEnvelope instance")
        self.reports = [self._coerce_report(item) for item in self.reports]
        self.trajectories = [self._coerce_trajectory(item) for item in self.trajectories]
        self.generated_at = _require_non_empty_string(self.generated_at, field_name="request.generated_at")
        if self.schema_version != SYNC_PROTOCOL_VERSION:
            raise ValueError(
                f"request.schema_version must be `{SYNC_PROTOCOL_VERSION}`, got {self.schema_version!r}"
            )
        if self.protocol_version != SYNC_PROTOCOL_VERSION:
            raise ValueError(
                f"request.protocol_version must be `{SYNC_PROTOCOL_VERSION}`, got {self.protocol_version!r}"
            )
        if self.idempotency_key:
            self.idempotency_key = _require_non_empty_string(
                self.idempotency_key,
                field_name="request.idempotency_key",
            )
        else:
            self.idempotency_key = sha256_of_data(self._payload_without_idempotency())

    @staticmethod
    def _coerce_report(value: SyncReportEnvelope) -> SyncReportEnvelope:
        if not isinstance(value, SyncReportEnvelope):
            raise ValueError("request.reports must contain SyncReportEnvelope instances")
        return value

    @staticmethod
    def _coerce_trajectory(value: SyncTrajectoryEnvelope) -> SyncTrajectoryEnvelope:
        if not isinstance(value, SyncTrajectoryEnvelope):
            raise ValueError("request.trajectories must contain SyncTrajectoryEnvelope instances")
        return value

    def _payload_without_idempotency(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "schema_version": self.schema_version,
            "protocol_version": self.protocol_version,
            "project": self.project.to_dict(),
            "run": self.run.to_dict(),
            "reports": [report.to_dict() for report in self.reports],
            "trajectories": [trajectory.to_dict() for trajectory in self.trajectories],
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize this sync request."""

        payload = self._payload_without_idempotency()
        payload["idempotency_key"] = self.idempotency_key
        return payload

    def to_json(self) -> str:
        """Serialize this sync request to canonical JSON."""

        return canonical_dumps(self.to_dict())


@dataclass(slots=True)
class SyncResponse:
    """Structured response returned by the sync HTTP client."""

    accepted: bool
    endpoint: str
    status_code: int
    idempotency_key: str
    attempts: int
    dry_run: bool = False
    sync_id: str | None = None
    message: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.accepted, bool):
            raise ValueError("response.accepted must be a boolean")
        self.endpoint = _validate_endpoint(self.endpoint)
        if not isinstance(self.status_code, int) or self.status_code < 0:
            raise ValueError("response.status_code must be a non-negative integer")
        self.idempotency_key = _require_non_empty_string(
            self.idempotency_key,
            field_name="response.idempotency_key",
        )
        if not isinstance(self.attempts, int) or self.attempts <= 0:
            raise ValueError("response.attempts must be a positive integer")
        if not isinstance(self.dry_run, bool):
            raise ValueError("response.dry_run must be a boolean")
        self.sync_id = _validate_string_or_none(self.sync_id, field_name="response.sync_id")
        self.message = _validate_string_or_none(self.message, field_name="response.message")
        self.details = _coerce_json_object(self.details, field_name="response.details")

    def to_dict(self) -> dict[str, Any]:
        """Serialize this sync response."""

        payload: dict[str, Any] = {
            "accepted": self.accepted,
            "endpoint": self.endpoint,
            "status_code": self.status_code,
            "idempotency_key": self.idempotency_key,
            "attempts": self.attempts,
            "dry_run": self.dry_run,
            "details": self.details,
        }
        if self.sync_id is not None:
            payload["sync_id"] = self.sync_id
        if self.message is not None:
            payload["message"] = self.message
        return payload


def trace_event_to_v03(event: TraceEvent, *, event_index: int) -> TraceEventV03:
    """Project a legacy runtime trace event onto the portable Phase 1 trace schema."""

    kind = _EVENT_KIND_BY_EVENT_TYPE.get(event.event_type, "ERROR")
    payload = dict(event.payload)
    payload["__trajectly__"] = {
        "event_type": event.event_type,
        "seq": event.seq,
        "run_id": event.run_id,
        "rel_ms": event.rel_ms,
        "schema_version": event.schema_version,
        "meta": dict(event.meta),
    }
    return TraceEventV03(
        event_index=event_index,
        kind=kind,
        payload=payload,
        stable_hash=event.event_id or compute_event_id(event),
    )


def trajectory_from_trace_events(
    events: Sequence[TraceEvent],
    *,
    spec_name: str,
    mode: str,
    run_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> TrajectoryV03:
    """Build a portable trajectory bundle from the existing runtime event model."""

    normalized_spec_name = _require_non_empty_string(spec_name, field_name="trajectory.spec_name")
    normalized_mode = _require_non_empty_string(mode, field_name="trajectory.mode")
    normalized_events = list(events)
    for index, event in enumerate(normalized_events):
        if not isinstance(event, TraceEvent):
            raise ValueError(
                f"trajectory.events[{index}] must be a trajectly.events.TraceEvent, got {type(event).__name__}"
            )
    resolved_run_id = run_id or (normalized_events[0].run_id if normalized_events else None)
    return TrajectoryV03(
        meta=TraceMetaV03(
            spec_name=normalized_spec_name,
            run_id=resolved_run_id,
            mode=normalized_mode,
            metadata=dict(metadata or {}),
        ),
        events=[
            trace_event_to_v03(event, event_index=index)
            for index, event in enumerate(normalized_events)
        ],
    )


@dataclass(slots=True)
class SyncClient:
    """Minimal HTTP client for deterministic sync uploads."""

    endpoint: str
    api_key: str | None = None
    timeout_seconds: float = 15.0
    user_agent: str = "trajectly-sync-client"

    def __post_init__(self) -> None:
        self.endpoint = _validate_endpoint(self.endpoint)
        self.api_key = _validate_string_or_none(self.api_key, field_name="client.api_key")
        if not isinstance(self.timeout_seconds, (int, float)) or self.timeout_seconds <= 0:
            raise ValueError("client.timeout_seconds must be a positive number")
        self.timeout_seconds = float(self.timeout_seconds)
        self.user_agent = _require_non_empty_string(self.user_agent, field_name="client.user_agent")

    def send(
        self,
        request: SyncRequest,
        *,
        retries: int = 2,
        retry_backoff_seconds: float = 0.25,
    ) -> SyncResponse:
        """Upload a sync request with retry-safe idempotency headers."""

        if not isinstance(request, SyncRequest):
            raise ValueError("request must be a SyncRequest instance")
        if not isinstance(retries, int) or retries < 0:
            raise ValueError("retries must be a non-negative integer")
        if not isinstance(retry_backoff_seconds, (int, float)) or retry_backoff_seconds < 0:
            raise ValueError("retry_backoff_seconds must be a non-negative number")

        attempt = 0
        while True:
            attempt += 1
            try:
                return self._send_once(request, attempt=attempt)
            except SyncTransportError as exc:
                if not exc.retryable or attempt > retries:
                    raise
                time.sleep(float(retry_backoff_seconds) * attempt)

    def _send_once(self, request: SyncRequest, *, attempt: int) -> SyncResponse:
        payload = request.to_json().encode("utf-8")
        http_request = urllib_request.Request(
            self.endpoint,
            data=payload,
            method="POST",
            headers=self._build_headers(request),
        )

        try:
            with urllib_request.urlopen(http_request, timeout=self.timeout_seconds) as handle:
                status_code = int(getattr(handle, "status", 200))
                raw_body = handle.read().decode("utf-8", errors="replace")
        except urllib_error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise SyncTransportError(
                self._format_http_error_message(status_code=exc.code, body=body),
                status_code=exc.code,
                body=body,
                retryable=exc.code in RETRYABLE_STATUS_CODES,
            ) from exc
        except urllib_error.URLError as exc:
            reason = str(getattr(exc, "reason", exc))
            raise SyncTransportError(
                f"Sync request failed for {self.endpoint}: {reason}",
                body=reason,
                retryable=True,
            ) from exc

        details = self._parse_response_body(raw_body)
        accepted = bool(details.get("accepted", True))
        message = details.get("message")
        sync_id = details.get("sync_id")
        return SyncResponse(
            accepted=accepted,
            endpoint=self.endpoint,
            status_code=status_code,
            idempotency_key=request.idempotency_key,
            attempts=attempt,
            sync_id=sync_id if isinstance(sync_id, str) else None,
            message=message if isinstance(message, str) else None,
            details=details,
        )

    def _build_headers(self, request: SyncRequest) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Idempotency-Key": request.idempotency_key,
            "User-Agent": self.user_agent,
            "X-Trajectly-Project-Slug": request.project.slug,
            "X-Trajectly-Protocol-Version": request.protocol_version,
        }
        if self.api_key is not None:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    @staticmethod
    def _format_http_error_message(*, status_code: int, body: str) -> str:
        snippet = body.strip()
        if snippet:
            return f"Sync request failed with HTTP {status_code}: {snippet}"
        return f"Sync request failed with HTTP {status_code}"

    @staticmethod
    def _parse_response_body(raw_body: str) -> dict[str, Any]:
        text = raw_body.strip()
        if not text:
            return {}
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return {"message": text}
        if isinstance(parsed, dict):
            return parsed
        return {"message": text}


__all__ = [
    "SYNC_PROTOCOL_VERSION",
    "SyncClient",
    "SyncError",
    "SyncProject",
    "SyncReportEnvelope",
    "SyncRequest",
    "SyncResponse",
    "SyncRunEnvelope",
    "SyncTrajectoryEnvelope",
    "SyncTransportError",
    "trace_event_to_v03",
    "trajectory_from_trace_events",
]
