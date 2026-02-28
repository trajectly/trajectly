"""Tests for spec extends + deterministic deep-merge."""
from __future__ import annotations

from pathlib import Path

import pytest

from trajectly.core.specs import deep_merge, load_spec


class TestDeepMerge:
    def test_scalar_override(self) -> None:
        assert deep_merge({"a": 1}, {"a": 2}) == {"a": 2}

    def test_dict_recursive_merge(self) -> None:
        base = {"contracts": {"tools": {"deny": ["rm"]}, "network": {"enabled": True}}}
        overlay = {"contracts": {"tools": {"allow": ["ls"]}, "network": {"enabled": False}}}
        result = deep_merge(base, overlay)
        assert result == {
            "contracts": {
                "tools": {"deny": ["rm"], "allow": ["ls"]},
                "network": {"enabled": False},
            }
        }

    def test_list_override(self) -> None:
        assert deep_merge({"redact": ["a"]}, {"redact": ["b", "c"]}) == {"redact": ["b", "c"]}

    def test_new_keys_added(self) -> None:
        assert deep_merge({"a": 1}, {"b": 2}) == {"a": 1, "b": 2}

    def test_empty_overlay(self) -> None:
        assert deep_merge({"a": 1}, {}) == {"a": 1}

    def test_empty_base(self) -> None:
        assert deep_merge({}, {"a": 1}) == {"a": 1}

    def test_deterministic_key_order(self) -> None:
        r1 = deep_merge({"z": 1, "a": 2}, {"m": 3, "b": 4})
        r2 = deep_merge({"z": 1, "a": 2}, {"b": 4, "m": 3})
        assert list(r1.keys()) == list(r2.keys())


class TestSpecExtends:
    def test_single_extends(self, tmp_path: Path) -> None:
        base = tmp_path / "base.agent.yaml"
        base.write_text(
            "schema_version: '0.4'\n"
            "name: base-spec\n"
            "command: python agent.py\n"
            "strict: true\n"
            "budget_thresholds:\n"
            "  max_latency_ms: 5000\n"
            "  max_tool_calls: 10\n"
        )
        child = tmp_path / "child.agent.yaml"
        child.write_text(
            "extends: base.agent.yaml\n"
            "name: child-spec\n"
            "budget_thresholds:\n"
            "  max_tool_calls: 20\n"
        )
        spec = load_spec(child)
        assert spec.name == "child-spec"
        assert spec.strict is True
        assert spec.budget_thresholds.max_latency_ms == 5000
        assert spec.budget_thresholds.max_tool_calls == 20

    def test_chained_extends(self, tmp_path: Path) -> None:
        grandparent = tmp_path / "gp.agent.yaml"
        grandparent.write_text(
            "schema_version: '0.4'\n"
            "name: gp\n"
            "command: python agent.py\n"
            "strict: false\n"
        )
        parent = tmp_path / "parent.agent.yaml"
        parent.write_text(
            "extends: gp.agent.yaml\n"
            "strict: true\n"
        )
        child = tmp_path / "child.agent.yaml"
        child.write_text(
            "extends: parent.agent.yaml\n"
            "name: child\n"
        )
        spec = load_spec(child)
        assert spec.name == "child"
        assert spec.strict is True

    def test_missing_extends_target_raises(self, tmp_path: Path) -> None:
        child = tmp_path / "bad.agent.yaml"
        child.write_text("extends: nonexistent.yaml\nname: x\ncommand: echo hi\n")
        with pytest.raises(ValueError, match="extends target not found"):
            load_spec(child)

    def test_circular_extends_raises(self, tmp_path: Path) -> None:
        a = tmp_path / "a.agent.yaml"
        b = tmp_path / "b.agent.yaml"
        a.write_text("extends: b.agent.yaml\nname: a\ncommand: echo a\nschema_version: '0.4'\n")
        b.write_text("extends: a.agent.yaml\nname: b\ncommand: echo b\nschema_version: '0.4'\n")
        with pytest.raises(ValueError, match="extends depth exceeded"):
            load_spec(a)

    def test_no_extends_still_works(self, tmp_path: Path) -> None:
        spec_file = tmp_path / "solo.agent.yaml"
        spec_file.write_text(
            "schema_version: '0.4'\n"
            "name: solo\n"
            "command: python run.py\n"
        )
        spec = load_spec(spec_file)
        assert spec.name == "solo"
