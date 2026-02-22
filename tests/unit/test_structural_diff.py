from __future__ import annotations

from trajectly.diff.structural import structural_diff


def test_structural_diff_reports_paths() -> None:
    baseline = {"a": {"b": [1, {"c": "x"}]}}
    current = {"a": {"b": [1, {"c": "y"}]}}
    changes = structural_diff(baseline, current)
    assert len(changes) == 1
    assert changes[0].path == "$.a.b[1].c"
    assert changes[0].baseline == "x"
    assert changes[0].current == "y"
