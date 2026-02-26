from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from trajectly.core.specs import AgentSpec
from trajectly.core.trace.meta import default_trace_meta_path, default_trace_path


@dataclass(slots=True)
class ExecutionResult:
    returncode: int
    stdout: str
    stderr: str
    duration_ms: int
    raw_events: list[dict[str, object]]
    internal_error: str | None = None


def _repo_src_path() -> Path:
    # __file__ is src/trajectly/core/runtime.py → parents[2] is src/
    return Path(__file__).resolve().parents[2]


def _load_raw_events(events_path: Path) -> list[dict[str, object]]:
    if not events_path.exists():
        return []
    rows: list[dict[str, object]] = []
    with events_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            payload = json.loads(stripped)
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def execute_spec(
    spec: AgentSpec,
    mode: str,
    events_path: Path,
    fixtures_path: Path | None,
    strict: bool,
) -> ExecutionResult:
    events_path.parent.mkdir(parents=True, exist_ok=True)
    if events_path.exists():
        events_path.unlink()
    trace_path = default_trace_path(events_path)
    trace_meta_path = default_trace_meta_path(trace_path)
    if trace_path.exists():
        trace_path.unlink()
    if trace_meta_path.exists():
        trace_meta_path.unlink()

    env = dict(os.environ)
    env.update(spec.env)
    env.update(
        {
            "PYTHONHASHSEED": "0",
            "LC_ALL": "C.UTF-8",
            "LANG": "C.UTF-8",
            "TZ": "UTC",
            "TRAJECTLY_MODE": mode,
            "TRAJECTLY_EVENTS_FILE": str(events_path),
            "TRAJECTLY_TRACE_FILE": str(trace_path),
            "TRAJECTLY_TRACE_META_FILE": str(trace_meta_path),
            "TRAJECTLY_SPEC_NAME": spec.name,
            "TRAJECTLY_FIXTURE_POLICY": spec.fixture_policy,
            "TRAJECTLY_STRICT": "1" if strict else "0",
            "TRAJECTLY_CONTRACTS_JSON": json.dumps(
                asdict(spec.contracts), sort_keys=True, separators=(",", ":")
            ),
        }
    )

    if fixtures_path is not None:
        env["TRAJECTLY_FIXTURES_FILE"] = str(fixtures_path)

    if spec.contracts.network.allowlist:
        env["TRAJECTLY_NETWORK_ALLOWLIST"] = ",".join(spec.contracts.network.allowlist)

    src_path = str(_repo_src_path())
    prior = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{src_path}{os.pathsep}{prior}" if prior else src_path

    if mode == "replay":
        env["TRAJECTLY_REPLAY_GUARD"] = "1"

    start = time.monotonic()
    try:
        completed = subprocess.run(
            spec.command,
            shell=True,
            cwd=str(spec.resolved_workdir()),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        return ExecutionResult(
            returncode=1,
            stdout="",
            stderr="",
            duration_ms=duration_ms,
            raw_events=_load_raw_events(events_path),
            internal_error=str(exc),
        )

    duration_ms = int((time.monotonic() - start) * 1000)
    return ExecutionResult(
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        duration_ms=duration_ms,
        raw_events=_load_raw_events(events_path),
    )
