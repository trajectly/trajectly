from __future__ import annotations

import json
from pathlib import Path

from trajectly.diff.models import DiffResult, Finding
from trajectly.report.renderers import render_markdown, write_reports


def _result_with_finding() -> DiffResult:
    return DiffResult(
        summary={
            "regression": True,
            "finding_count": 1,
            "baseline": {"duration_ms": 10, "tool_calls": 1, "tokens": 2},
            "current": {"duration_ms": 20, "tool_calls": 3, "tokens": 5},
        },
        findings=[
            Finding(
                classification="structural_mismatch",
                message="Payload mismatch at $.payload.output",
                path="$.payload.output",
            )
        ],
    )


def test_render_markdown_contains_sections() -> None:
    markdown = render_markdown("demo", _result_with_finding())

    assert "## Trajectly Report: demo" in markdown
    assert "Regression detected" in markdown
    assert "$.payload.output" in markdown


def test_write_reports_outputs_json_and_markdown(tmp_path: Path) -> None:
    json_path = tmp_path / "out" / "report.json"
    md_path = tmp_path / "out" / "report.md"
    write_reports("demo", _result_with_finding(), json_path, md_path)

    assert json_path.exists()
    assert md_path.exists()
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["summary"]["regression"] is True
    assert "Trajectly Report" in md_path.read_text(encoding="utf-8")
