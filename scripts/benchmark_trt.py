#!/usr/bin/env python3
"""
TRT performance benchmark harness (QA-T007). CLI entrypoint.
Run: uv run python scripts/benchmark_trt.py [--iterations N] [--output out.json] [--md out.md]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __name__ == "__main__":
    _repo = Path(__file__).resolve().parent.parent
    _src = _repo / "src"
    if _src.exists() and str(_src) not in sys.path:
        sys.path.insert(0, str(_src))

from trajectly.benchmark import run_benchmark, to_md


def main() -> int:
    parser = argparse.ArgumentParser(description="TRT performance benchmark (QA-T007)")
    parser.add_argument("--iterations", type=int, default=5, help="Number of run_specs iterations")
    parser.add_argument("--output", type=Path, help="Write JSON to this file (default: stdout)")
    parser.add_argument("--md", type=Path, help="Write Markdown summary to this file")
    args = parser.parse_args()
    data = run_benchmark(iterations=args.iterations)
    json_str = json.dumps(data, indent=2)
    if args.output:
        args.output.write_text(json_str, encoding="utf-8")
    else:
        print(json_str)
    if args.md:
        args.md.write_text(to_md(data), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
