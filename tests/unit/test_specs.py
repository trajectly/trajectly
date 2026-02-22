from __future__ import annotations

from pathlib import Path

import pytest

from trajectly.specs import AgentSpec, load_spec, load_specs


def _write(path: Path, body: str) -> None:
    path.write_text(body.strip() + "\n", encoding="utf-8")


def test_load_spec_parses_all_fields(tmp_path: Path) -> None:
    spec_path = tmp_path / "full.agent.yaml"
    _write(
        spec_path,
        """
name: full
command: python agent.py
workdir: .
env:
  API_KEY: abc123
fixture_policy: by_hash
strict: true
redact:
  - secret_[0-9]+
budget_thresholds:
  max_latency_ms: 500
  max_tool_calls: 3
  max_tokens: 42
""",
    )

    spec = load_spec(spec_path)

    assert isinstance(spec, AgentSpec)
    assert spec.name == "full"
    assert spec.command == "python agent.py"
    assert spec.fixture_policy == "by_hash"
    assert spec.strict is True
    assert spec.env == {"API_KEY": "abc123"}
    assert spec.redact == ["secret_[0-9]+"]
    assert spec.budget_thresholds.max_latency_ms == 500
    assert spec.budget_thresholds.max_tool_calls == 3
    assert spec.budget_thresholds.max_tokens == 42
    assert spec.resolved_workdir() == spec_path.parent.resolve()


def test_load_spec_defaults_name_and_workdir(tmp_path: Path) -> None:
    spec_path = tmp_path / "demo.agent.yaml"
    _write(
        spec_path,
        """
command: python script.py
""",
    )

    spec = load_spec(spec_path)

    assert spec.name == "demo.agent"
    assert spec.fixture_policy == "by_index"
    assert spec.strict is False
    assert spec.env == {}
    assert spec.redact == []
    assert spec.resolved_workdir() == tmp_path.resolve()


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("name: x", "missing required non-empty field: command"),
        ("command: ''", "missing required non-empty field: command"),
        (
            "command: python a.py\nfixture_policy: random",
            "invalid fixture_policy",
        ),
        (
            "command: python a.py\nenv: [1,2]",
            "field env must be a mapping",
        ),
        (
            "command: python a.py\nredact: nope",
            "field redact must be a list",
        ),
        (
            "command: python a.py\nbudget_thresholds: nope",
            "budget_thresholds must be a mapping",
        ),
    ],
)
def test_load_spec_validation_errors(tmp_path: Path, body: str, message: str) -> None:
    spec_path = tmp_path / "bad.agent.yaml"
    _write(spec_path, body)

    with pytest.raises(ValueError, match=message):
        load_spec(spec_path)


def test_load_specs_resolves_glob_and_deduplicates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    spec_a = tmp_path / "a.agent.yaml"
    spec_b = tmp_path / "b.agent.yaml"
    _write(spec_a, "command: python a.py")
    _write(spec_b, "command: python b.py")

    monkeypatch.chdir(tmp_path)
    loaded = load_specs(["*.agent.yaml", str(spec_a.resolve())], cwd=tmp_path)

    assert [spec.name for spec in loaded] == ["a.agent", "b.agent"]


def test_load_specs_raises_when_no_matches(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="No spec files matched targets"):
        load_specs([str(tmp_path / "*.agent.yaml")], cwd=tmp_path)
