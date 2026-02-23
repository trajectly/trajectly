"""Smoke test for TRT benchmark harness (QA-T007)."""

from __future__ import annotations

from trajectly.benchmark import run_benchmark, to_md


def test_benchmark_smoke() -> None:
    """Run benchmark with 2 iterations; assert shape and positive timings."""
    data = run_benchmark(iterations=2)
    assert "runs" in data
    assert "summary" in data
    assert len(data["runs"]) == 2
    for r in data["runs"]:
        assert "wall_s" in r
        assert r["wall_s"] >= 0
    s = data["summary"]
    assert s["n"] == 2
    assert s["mean_s"] >= 0
    assert s["min_s"] >= 0
    assert s["max_s"] >= 0


def test_benchmark_to_md() -> None:
    """to_md produces summary section with runs and mean."""
    data = run_benchmark(iterations=1)
    md = to_md(data)
    assert "## TRT benchmark summary" in md
    assert "Runs:" in md
    assert "Mean:" in md
