from __future__ import annotations

import json
from pathlib import Path

import pytest

from trajectly.constants import EXIT_INTERNAL_ERROR
from trajectly.engine import (
    SUPPORTED_ENABLE_TEMPLATES,
    apply_enable_template,
    build_repro_command,
    discover_spec_files,
    enable_workspace,
    initialize_workspace,
    latest_report_path,
    read_latest_report,
    record_specs,
    resolve_repro_spec,
    run_specs,
)
from trajectly.schema import SchemaValidationError
from trajectly.trace.io import read_trace_meta


def _write(path: Path, body: str) -> None:
    path.write_text(body.strip() + "\n", encoding="utf-8")


def test_initialize_workspace_creates_expected_files(tmp_path: Path) -> None:
    initialize_workspace(tmp_path)

    assert (tmp_path / ".trajectly" / "config.yaml").exists()
    assert (tmp_path / "tests" / "sample.agent.yaml").exists()


def test_enable_workspace_returns_discovered_specs(tmp_path: Path) -> None:
    discovered = enable_workspace(tmp_path)

    assert (tmp_path / ".trajectly" / "config.yaml").exists()
    assert (tmp_path / "tests" / "sample.agent.yaml").resolve() in discovered


def test_apply_enable_template_creates_expected_files(tmp_path: Path) -> None:
    created = apply_enable_template(tmp_path, "openai")
    created_set = {path.resolve() for path in created}

    assert (tmp_path / "openai.agent.yaml").resolve() in created_set
    assert (tmp_path / "templates" / "openai_agent.py").resolve() in created_set

    second_pass = apply_enable_template(tmp_path, "openai")
    assert second_pass == []


def test_apply_enable_template_rejects_unknown_template(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unsupported template"):
        apply_enable_template(tmp_path, "unknown")
    assert {"openai", "langchain", "autogen"} == SUPPORTED_ENABLE_TEMPLATES


def test_discover_spec_files_excludes_runtime_and_hidden_dirs(tmp_path: Path) -> None:
    (tmp_path / "specs").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".trajectly").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".venv").mkdir(parents=True, exist_ok=True)
    (tmp_path / "node_modules").mkdir(parents=True, exist_ok=True)
    (tmp_path / "specs" / "a.agent.yaml").write_text("command: python a.py\n", encoding="utf-8")
    (tmp_path / "z.agent.yaml").write_text("command: python z.py\n", encoding="utf-8")
    (tmp_path / ".trajectly" / "hidden.agent.yaml").write_text("command: python x.py\n", encoding="utf-8")
    (tmp_path / ".venv" / "venv.agent.yaml").write_text("command: python x.py\n", encoding="utf-8")
    (tmp_path / "node_modules" / "npm.agent.yaml").write_text("command: python x.py\n", encoding="utf-8")

    discovered = discover_spec_files(tmp_path)

    assert discovered == [
        (tmp_path / "specs" / "a.agent.yaml").resolve(),
        (tmp_path / "z.agent.yaml").resolve(),
    ]


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


def test_record_specs_blocks_ci_baseline_writes_without_override(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initialize_workspace(tmp_path)
    agent = tmp_path / "agent.py"
    _write(agent, "print('ok')")
    spec = tmp_path / "record.agent.yaml"
    _write(
        spec,
        """
name: record
command: python agent.py
workdir: .
strict: true
""",
    )
    monkeypatch.setenv("TRAJECTLY_CI", "1")

    blocked = record_specs(targets=[str(spec)], project_root=tmp_path)
    assert blocked.exit_code == EXIT_INTERNAL_ERROR
    assert any("Baseline writes are blocked when TRAJECTLY_CI=1" in error for error in blocked.errors)

    allowed = record_specs(targets=[str(spec)], project_root=tmp_path, allow_ci_write=True)
    assert allowed.exit_code == 0


def test_run_specs_fails_fast_on_normalizer_version_mismatch(tmp_path: Path) -> None:
    initialize_workspace(tmp_path)
    agent = tmp_path / "agent.py"
    _write(agent, "print('ok')")
    spec = tmp_path / "trt.agent.yaml"
    _write(
        spec,
        """
schema_version: "0.3"
name: trt-demo
command: python agent.py
workdir: .
strict: true
""",
    )

    recorded = record_specs(targets=[str(spec)], project_root=tmp_path)
    assert recorded.exit_code == 0

    baseline_meta = tmp_path / ".trajectly" / "baselines" / "trt-demo.meta.json"
    assert baseline_meta.exists()
    assert read_trace_meta(baseline_meta).normalizer_version == "1"

    payload = json.loads(baseline_meta.read_text(encoding="utf-8"))
    payload["normalizer_version"] = "999"
    baseline_meta.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    run_outcome = run_specs(targets=[str(spec)], project_root=tmp_path)
    assert run_outcome.exit_code == EXIT_INTERNAL_ERROR
    assert any("NORMALIZER_VERSION_MISMATCH" in error for error in run_outcome.errors)


def test_read_latest_report_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Latest report not found"):
        read_latest_report(tmp_path, as_json=True)

    assert latest_report_path(tmp_path, as_json=False).name == "latest.md"


def test_read_latest_report_rejects_unsupported_schema_version(tmp_path: Path) -> None:
    reports_dir = tmp_path / ".trajectly" / "reports"
    reports_dir.mkdir(parents=True)
    (reports_dir / "latest.json").write_text(
        json.dumps(
            {
                "schema_version": "v999",
                "processed_specs": 0,
                "regressions": 0,
                "errors": [],
                "reports": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(SchemaValidationError, match="Unsupported report schema_version"):
        read_latest_report(tmp_path, as_json=True)


def test_resolve_repro_spec_prefers_latest_regression(tmp_path: Path) -> None:
    spec_a = tmp_path / "a.agent.yaml"
    spec_b = tmp_path / "b.agent.yaml"
    _write(spec_a, "command: python a.py")
    _write(spec_b, "command: python b.py")

    reports_dir = tmp_path / ".trajectly" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "latest.json").write_text(
        json.dumps(
            {
                "schema_version": "v1",
                "processed_specs": 2,
                "regressions": 1,
                "errors": [],
                "reports": [
                    {"spec": "a", "slug": "a", "regression": False, "spec_path": str(spec_a.resolve())},
                    {"spec": "b", "slug": "b", "regression": True, "spec_path": str(spec_b.resolve())},
                ],
            }
        ),
        encoding="utf-8",
    )

    spec_name, spec_path = resolve_repro_spec(tmp_path)
    assert spec_name == "b"
    assert spec_path == spec_b.resolve()

    command = build_repro_command(spec_path=spec_path, project_root=tmp_path.resolve())
    assert "trajectly run" in command
    assert str(spec_b.resolve()) in command
