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
contracts:
  version: v1
  tools:
    allow: [add, search]
    deny: [delete]
    max_calls_total: 5
    max_calls_per_tool:
      add: 2
    schema:
      add:
        type: object
  sequence:
    require: [tool:add]
    forbid: [tool:delete]
    require_before:
      - before: tool:add
        after: step:done
    eventually: [tool:add]
    never: [tool:delete]
    at_most_once: [step:done]
  side_effects:
    deny_write_tools: true
  network:
    default: deny
    allowlist: [api.example.com]
    allow_domains: [example.com]
  data_leak:
    deny_pii_outbound: true
    outbound_kinds: [TOOL_CALL]
    secret_patterns: ["sk_live_[A-Za-z0-9]+"]
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
    assert spec.contracts.tools.allow == ["add", "search"]
    assert spec.contracts.tools.deny == ["delete"]
    assert spec.contracts.tools.max_calls_total == 5
    assert spec.contracts.tools.max_calls_per_tool == {"add": 2}
    assert spec.contracts.sequence.require == ["tool:add"]
    assert spec.contracts.sequence.forbid == ["tool:delete"]
    assert spec.contracts.sequence.require_before == [("tool:add", "step:done")]
    assert spec.contracts.sequence.eventually == ["tool:add"]
    assert spec.contracts.sequence.never == ["tool:delete"]
    assert spec.contracts.sequence.at_most_once == ["step:done"]
    assert spec.contracts.side_effects.deny_write_tools is True
    assert spec.contracts.network.allowlist == ["api.example.com"]
    assert spec.contracts.network.default == "deny"
    assert spec.contracts.network.allow_domains == ["example.com"]
    assert spec.contracts.data_leak.deny_pii_outbound is True
    assert spec.contracts.data_leak.outbound_kinds == ["TOOL_CALL"]
    assert spec.contracts.data_leak.secret_patterns == ["sk_live_[A-Za-z0-9]+"]
    assert spec.contracts.version == "v1"
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
    assert spec.contracts.tools.allow == []
    assert spec.contracts.tools.deny == []
    assert spec.contracts.tools.max_calls_total is None
    assert spec.contracts.sequence.require == []
    assert spec.contracts.sequence.forbid == []
    assert spec.contracts.sequence.require_before == []
    assert spec.contracts.sequence.eventually == []
    assert spec.contracts.sequence.never == []
    assert spec.contracts.sequence.at_most_once == []
    assert spec.contracts.side_effects.deny_write_tools is False
    assert spec.contracts.network.allowlist == []
    assert spec.contracts.network.default == "deny"
    assert spec.contracts.network.allow_domains == []
    assert spec.contracts.data_leak.deny_pii_outbound is False
    assert spec.contracts.data_leak.outbound_kinds == []
    assert spec.contracts.data_leak.secret_patterns == []
    assert spec.contracts.version == "v1"
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
        (
            "command: python a.py\ncontracts: nope",
            "contracts must be a mapping",
        ),
        (
            "command: python a.py\ncontracts:\n  version: 1",
            "contracts.version must be a string",
        ),
        (
            "command: python a.py\ncontracts:\n  version: v2",
            "Unsupported contracts.version: v2. Supported: v1",
        ),
        (
            "command: python a.py\ncontracts:\n  tools: nope",
            "contracts.tools must be a mapping",
        ),
        (
            "command: python a.py\ncontracts:\n  tools:\n    allow: nope",
            "contracts.tools.allow must be a list",
        ),
        (
            "command: python a.py\ncontracts:\n  tools:\n    deny: nope",
            "contracts.tools.deny must be a list",
        ),
        (
            "command: python a.py\ncontracts:\n  tools:\n    allow: [add]\n    deny: [add]",
            "contracts.tools allow/deny overlap",
        ),
        (
            "command: python a.py\ncontracts:\n  tools:\n    max_calls_total: -1",
            "contracts.tools.max_calls_total must be >= 0",
        ),
        (
            "command: python a.py\ncontracts:\n  tools:\n    max_calls_per_tool: nope",
            "contracts.tools.max_calls_per_tool must be a mapping",
        ),
        (
            "command: python a.py\ncontracts:\n  tools:\n    max_calls_per_tool:\n      add: -1",
            "contracts.tools.max_calls_per_tool values must be >= 0",
        ),
        (
            "command: python a.py\ncontracts:\n  tools:\n    schema: nope",
            "contracts.tools.schema must be a mapping",
        ),
        (
            "command: python a.py\ncontracts:\n  args: nope",
            "contracts.args must be a mapping",
        ),
        (
            "command: python a.py\ncontracts:\n  args:\n    checkout: nope",
            "contracts.args entries must be mappings",
        ),
        (
            "command: python a.py\ncontracts:\n  sequence: nope",
            "contracts.sequence must be a mapping",
        ),
        (
            "command: python a.py\ncontracts:\n  sequence:\n    require: nope",
            "contracts.sequence.require must be a list",
        ),
        (
            "command: python a.py\ncontracts:\n  sequence:\n    require_before: nope",
            "contracts.sequence.require_before must be a list",
        ),
        (
            "command: python a.py\ncontracts:\n  sequence:\n    require_before:\n      - before: tool:add",
            "contracts.sequence.require_before entries need string before/after",
        ),
        (
            "command: python a.py\ncontracts:\n  side_effects: nope",
            "contracts.side_effects must be a mapping",
        ),
        (
            "command: python a.py\ncontracts:\n  side_effects:\n    deny_write_tools: nope",
            "contracts.side_effects.deny_write_tools must be a boolean",
        ),
        (
            "command: python a.py\ncontracts:\n  network: nope",
            "contracts.network must be a mapping",
        ),
        (
            "command: python a.py\ncontracts:\n  network:\n    default: nope",
            "contracts.network.default must be deny|allow",
        ),
        (
            "command: python a.py\ncontracts:\n  network:\n    allowlist: nope",
            "contracts.network.allowlist must be a list",
        ),
        (
            "command: python a.py\ncontracts:\n  network:\n    allow_domains: nope",
            "contracts.network.allow_domains must be a list",
        ),
        (
            "command: python a.py\ncontracts:\n  data_leak: nope",
            "contracts.data_leak must be a mapping",
        ),
        (
            "command: python a.py\ncontracts:\n  data_leak:\n    deny_pii_outbound: nope",
            "contracts.data_leak.deny_pii_outbound must be a boolean",
        ),
        (
            "command: python a.py\ncontracts:\n  data_leak:\n    secret_patterns: nope",
            "contracts.data_leak.secret_patterns must be a list",
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


def test_load_spec_v03_with_contracts_config_and_refinement(tmp_path: Path) -> None:
    contracts_path = tmp_path / "phi.yaml"
    _write(
        contracts_path,
        """
version: v1
tools:
  allow: [search, checkout]
  deny: [delete_account]
sequence:
  require: [tool:search, tool:checkout]
""",
    )

    spec_path = tmp_path / "v03.agent.yaml"
    _write(
        spec_path,
        f"""
schema_version: "0.3"
name: support-triage
command: python agent.py
workdir: .
mode_profile: ci_safe
baseline:
  trace: .trajectly/baselines/support-triage.trace.jsonl
abstraction:
  config: trajectly/abstraction/default.yaml
contracts:
  config: {contracts_path.name}
replay:
  mode: offline
  strict_sequence: false
  llm_match_mode: signature_match
  tool_match_mode: args_signature_match
refinement:
  mode: skeleton
  allow_extra_llm_steps: true
  allow_extra_tools: [log_event]
  ignore_call_tools: [log_event]
artifacts:
  dir: trajectly/artifacts
""",
    )

    spec = load_spec(spec_path)
    assert spec.schema_version == "0.3"
    assert spec.legacy_compat is False
    assert spec.contracts.tools.allow == ["search", "checkout"]
    assert spec.contracts.tools.deny == ["delete_account"]
    assert spec.contracts_config is not None
    assert spec.replay.mode == "offline"
    assert spec.replay.tool_match_mode == "args_signature_match"
    assert spec.refinement.mode == "skeleton"
    assert spec.refinement.ignore_call_tools == ["log_event"]


def test_load_spec_v03_rejects_refinement_in_contracts_file(tmp_path: Path) -> None:
    contracts_path = tmp_path / "phi.yaml"
    _write(
        contracts_path,
        """
version: v1
refinement:
  mode: skeleton
""",
    )
    spec_path = tmp_path / "bad-v03.agent.yaml"
    _write(
        spec_path,
        f"""
schema_version: "0.3"
name: demo
command: python agent.py
contracts:
  config: {contracts_path.name}
""",
    )

    with pytest.raises(ValueError, match=r"refinement must be defined in \.agent\.yaml"):
        load_spec(spec_path)


def test_load_spec_v03_rejects_missing_name(tmp_path: Path) -> None:
    spec_path = tmp_path / "missing-name.agent.yaml"
    _write(
        spec_path,
        """
schema_version: "0.3"
command: python agent.py
""",
    )
    with pytest.raises(ValueError, match="requires non-empty `name`"):
        load_spec(spec_path)
