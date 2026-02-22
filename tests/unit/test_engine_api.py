from __future__ import annotations

from pathlib import Path

import pytest

from trajectly.constants import EXIT_INTERNAL_ERROR
from trajectly.engine import (
    diff_traces,
    initialize_workspace,
    latest_report_path,
    read_latest_report,
    run_specs,
    write_diff_report,
)
from trajectly.events import make_event, write_events_jsonl


def _write(path: Path, body: str) -> None:
    path.write_text(body.strip() + "\n", encoding="utf-8")


def test_initialize_workspace_creates_expected_files(tmp_path: Path) -> None:
    initialize_workspace(tmp_path)

    assert (tmp_path / ".trajectly" / "config.yaml").exists()
    assert (tmp_path / "tests" / "sample.agent.yaml").exists()


def test_run_specs_reports_missing_baseline(tmp_path: Path) -> None:
    initialize_workspace(tmp_path)
    agent = tmp_path / "agent.py"
    _write(agent, "print('ok')")
    spec = tmp_path / "demo.agent.yaml"
    _write(
        spec,
        """
name: demo
command: python agent.py
workdir: .
strict: true
""",
    )

    outcome = run_specs(targets=[str(spec)], project_root=tmp_path)

    assert outcome.exit_code == EXIT_INTERNAL_ERROR
    assert any("missing baseline trace" in err for err in outcome.errors)
    assert outcome.latest_report_json is not None
    assert outcome.latest_report_json.exists()


def test_diff_traces_and_write_diff_report(tmp_path: Path) -> None:
    baseline_path = tmp_path / "baseline.jsonl"
    current_path = tmp_path / "current.jsonl"

    baseline = [
        make_event(
            event_type="tool_returned",
            seq=1,
            run_id="r",
            rel_ms=1,
            payload={"tool_name": "add", "output": 3, "error": None},
        ),
        make_event(
            event_type="run_finished",
            seq=2,
            run_id="r",
            rel_ms=2,
            payload={"duration_ms": 2, "returncode": 0},
        ),
    ]
    current = [
        make_event(
            event_type="tool_returned",
            seq=1,
            run_id="r",
            rel_ms=1,
            payload={"tool_name": "add", "output": 4, "error": None},
        ),
        make_event(
            event_type="run_finished",
            seq=2,
            run_id="r",
            rel_ms=3,
            payload={"duration_ms": 3, "returncode": 0},
        ),
    ]

    write_events_jsonl(baseline_path, baseline)
    write_events_jsonl(current_path, current)

    result = diff_traces(baseline_path=baseline_path, current_path=current_path)
    assert result.summary["regression"] is True

    out_json = tmp_path / "reports" / "diff.json"
    out_md = tmp_path / "reports" / "diff.md"
    write_diff_report("demo", result, out_json, out_md)

    assert out_json.exists()
    assert out_md.exists()


def test_read_latest_report_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Latest report not found"):
        read_latest_report(tmp_path, as_json=True)

    assert latest_report_path(tmp_path, as_json=False).name == "latest.md"
