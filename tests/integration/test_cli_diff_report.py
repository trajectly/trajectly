from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from trajectly.cli import app
from trajectly.events import make_event, write_events_jsonl

runner = CliRunner()


def _trace(path: Path, output_value: int) -> None:
    events = [
        make_event(
            event_type="tool_returned",
            seq=1,
            run_id="run-1",
            rel_ms=1,
            payload={"tool_name": "add", "output": output_value, "error": None},
        ),
        make_event(
            event_type="run_finished",
            seq=2,
            run_id="run-1",
            rel_ms=2,
            payload={"duration_ms": 2, "returncode": 0},
        ),
    ]
    write_events_jsonl(path, events)


def test_cli_diff_writes_report_files_and_returns_regression(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.jsonl"
    current = tmp_path / "current.jsonl"
    out_json = tmp_path / "out.json"
    out_md = tmp_path / "out.md"

    _trace(baseline, 3)
    _trace(current, 9)

    result = runner.invoke(
        app,
        [
            "diff",
            "--baseline",
            str(baseline),
            "--current",
            str(current),
            "--json-output",
            str(out_json),
            "--markdown-output",
            str(out_md),
            "--spec-name",
            "demo",
        ],
    )

    assert result.exit_code == 1
    assert out_json.exists()
    assert out_md.exists()
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["regression"] is True


def test_cli_report_prints_json_and_source(tmp_path: Path) -> None:
    reports_dir = tmp_path / ".trajectly" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_json = reports_dir / "latest.json"
    report_json.write_text(
        json.dumps(
            {
                "schema_version": "v1",
                "processed_specs": 1,
                "regressions": 0,
                "errors": [],
                "reports": [],
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["report", "--project-root", str(tmp_path), "--json"])

    assert result.exit_code == 0
    assert '"processed_specs": 1' in result.stdout
    assert "Source:" in result.stdout


def test_cli_report_missing_latest_file_returns_error(tmp_path: Path) -> None:
    result = runner.invoke(app, ["report", "--project-root", str(tmp_path), "--json"])

    assert result.exit_code == 2
    assert "Latest report not found" in result.stdout
