from __future__ import annotations

import json
from pathlib import Path

from trajectly.constants import SCHEMA_VERSION
from trajectly.diff.models import DiffResult
from trajectly.schema import validate_diff_report_dict


def render_markdown(spec_name: str, result: DiffResult) -> str:
    lines: list[str] = []
    lines.append(f"## Trajectly Report: {spec_name}")
    lines.append("")
    summary = result.summary
    status = "Regression detected" if summary.get("regression") else "No regression"
    lines.append(f"- Status: **{status}**")
    lines.append(f"- Findings: **{summary.get('finding_count', 0)}**")
    first_divergence = summary.get("first_divergence")
    if isinstance(first_divergence, dict):
        lines.append(
            "- First divergence: "
            f"**{first_divergence.get('kind', 'unknown')}** at index "
            f"**{first_divergence.get('index', '?')}**"
        )

    baseline = summary.get("baseline", {})
    current = summary.get("current", {})
    lines.append("")
    lines.append("### Budgets")
    lines.append("")
    lines.append("| Metric | Baseline | Current |")
    lines.append("|---|---:|---:|")
    lines.append(
        f"| Duration (ms) | {baseline.get('duration_ms', 0)} | {current.get('duration_ms', 0)} |"
    )
    lines.append(f"| Tool Calls | {baseline.get('tool_calls', 0)} | {current.get('tool_calls', 0)} |")
    lines.append(f"| Tokens | {baseline.get('tokens', 0)} | {current.get('tokens', 0)} |")

    lines.append("")
    lines.append("### Findings")
    lines.append("")
    if not result.findings:
        lines.append("No findings.")
    else:
        for finding in result.findings:
            location = f" at `{finding.path}`" if finding.path else ""
            lines.append(f"- `{finding.classification}`{location}: {finding.message}")

    lines.append("")
    return "\n".join(lines)


def write_reports(spec_name: str, result: DiffResult, json_path: Path, md_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    report_payload = {"schema_version": SCHEMA_VERSION, **result.to_dict()}
    validated_payload = validate_diff_report_dict(report_payload)
    json_path.write_text(json.dumps(validated_payload, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_markdown(spec_name=spec_name, result=result), encoding="utf-8")
