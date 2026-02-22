from __future__ import annotations

from pathlib import Path
from typing import Any

from trajectly.diff.models import Finding
from trajectly.plugins import loader


class _FakeEntryPoint:
    def __init__(self, obj: Any) -> None:
        self._obj = obj

    def load(self) -> Any:
        return self._obj


class _FakeEntryPoints:
    def __init__(self, groups: dict[str, list[_FakeEntryPoint]]) -> None:
        self._groups = groups

    def select(self, *, group: str) -> list[_FakeEntryPoint]:
        return self._groups.get(group, [])


class _SemanticPlugin:
    def compare(self, baseline_trace: list[Any], current_trace: list[Any]) -> list[Finding]:
        assert isinstance(baseline_trace, list)
        assert isinstance(current_trace, list)
        return [Finding(classification="semantic", message="semantic mismatch")]


class _RunHookPlugin:
    called: bool = False

    def on_run_finished(self, context: dict[str, Any], report_paths: dict[str, Path]) -> None:
        _ = context
        _ = report_paths
        self.called = True


def test_run_semantic_plugins(monkeypatch) -> None:
    fake = _FakeEntryPoints(
        {
            "trajectly.semantic_diff_plugins": [_FakeEntryPoint(_SemanticPlugin)],
        }
    )
    monkeypatch.setattr(loader, "entry_points", lambda: fake)

    findings = loader.run_semantic_plugins(baseline=[], current=[])

    assert len(findings) == 1
    assert findings[0].classification == "semantic"


def test_run_run_hooks(monkeypatch) -> None:
    plugin = _RunHookPlugin()
    fake = _FakeEntryPoints(
        {
            "trajectly.run_hook_plugins": [_FakeEntryPoint(plugin)],
        }
    )
    monkeypatch.setattr(loader, "entry_points", lambda: fake)

    loader.run_run_hooks(context={"spec": "x"}, report_paths={"json": Path("out.json")})

    assert plugin.called is True
