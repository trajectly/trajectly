"""
TRT performance benchmark harness (QA-T007).

Runs TRT run_specs in a minimal workspace repeatedly and reports wall-clock times.
Deterministic and offline-safe (replay-only; no network).
"""

from __future__ import annotations

import tempfile
import time
from pathlib import Path
from typing import Any

from trajectly.constants import EXIT_SUCCESS
from trajectly.engine import initialize_workspace, record_specs, run_specs


def _write(path: Path, body: str) -> None:
    path.write_text(body.strip() + "\n", encoding="utf-8")


def _setup_workspace(root: Path) -> Path:
    """Create minimal TRT workspace with one spec and agent; record baseline. Returns spec path."""
    initialize_workspace(root)
    agent = root / "agent.py"
    _write(agent, "print('ok')")
    spec = root / "bench.agent.yaml"
    _write(
        spec,
        """
schema_version: "0.3"
name: bench
command: python agent.py
workdir: .
strict: true
""",
    )
    outcome = record_specs(targets=[str(spec)], project_root=root)
    if outcome.exit_code != EXIT_SUCCESS:
        raise RuntimeError(f"record_specs failed: {outcome.errors}")
    return spec


def run_benchmark(iterations: int = 5) -> dict[str, Any]:
    """Run TRT run_specs `iterations` times in a fresh workspace; return timings and summary."""
    times_s: list[float] = []
    with tempfile.TemporaryDirectory(prefix="trajectly_bench_") as tmp:
        root = Path(tmp)
        spec = _setup_workspace(root)
        for _ in range(iterations):
            t0 = time.perf_counter()
            outcome = run_specs(targets=[str(spec)], project_root=root)
            t1 = time.perf_counter()
            if outcome.exit_code != EXIT_SUCCESS:
                raise RuntimeError(f"run_specs failed: {outcome.errors}")
            times_s.append(t1 - t0)
    n = len(times_s)
    return {
        "runs": [{"wall_s": round(t, 6)} for t in times_s],
        "summary": {
            "n": n,
            "mean_s": round(sum(times_s) / n, 6),
            "min_s": round(min(times_s), 6),
            "max_s": round(max(times_s), 6),
        },
    }


def to_md(data: dict[str, Any]) -> str:
    """Short Markdown summary of benchmark result."""
    s = data["summary"]
    return (
        "## TRT benchmark summary\n\n"
        f"- **Runs:** {s['n']}\n"
        f"- **Mean:** {s['mean_s']} s\n"
        f"- **Min / Max:** {s['min_s']} s / {s['max_s']} s\n"
    )
