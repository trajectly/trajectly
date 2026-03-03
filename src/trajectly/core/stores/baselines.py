"""BaselineStore protocol and local filesystem implementation."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol, runtime_checkable

from trajectly.core.trace.io import write_trace_meta
from trajectly.core.trace.models import TraceMetaV03


@runtime_checkable
class BaselineStore(Protocol):
    """Abstraction for resolving, writing, and listing baselines."""

    def resolve(self, spec_id: str, baseline_id: str | None = None) -> BaselinePaths | None:
        """Resolve baseline file paths for a spec/baseline pair when present."""
        ...

    def write(
        self,
        spec_id: str,
        events: list[dict[str, object]],
        fixtures: dict[str, object] | None,
        meta: TraceMetaV03,
    ) -> BaselinePaths:
        """Persist baseline artifacts and return resolved output paths."""
        ...

    def list_baselines(self, spec_id: str) -> list[str]:
        """List known baseline ids for ``spec_id`` in storage order."""
        ...


class BaselinePaths:
    """Resolved file paths for a baseline."""
    __slots__ = ("fixture_path", "meta_path", "trace_path")

    def __init__(self, trace_path: Path, meta_path: Path, fixture_path: Path) -> None:
        """Execute `__init__`."""
        self.trace_path = trace_path
        self.meta_path = meta_path
        self.fixture_path = fixture_path


class LocalBaselineStore:
    """Wraps the existing .trajectly/baselines/ + fixtures/ layout."""

    def __init__(self, baselines_dir: Path, fixtures_dir: Path) -> None:
        """Execute `__init__`."""
        self._baselines_dir = baselines_dir
        self._fixtures_dir = fixtures_dir

    @property
    def baselines_dir(self) -> Path:
        """Execute `baselines_dir`."""
        return self._baselines_dir

    @property
    def fixtures_dir(self) -> Path:
        """Execute `fixtures_dir`."""
        return self._fixtures_dir

    def _meta_path(self, trace_path: Path) -> Path:
        """Execute `_meta_path`."""
        return trace_path.with_name(f"{trace_path.stem}.meta.json")

    def resolve(self, spec_id: str, baseline_id: str | None = None) -> BaselinePaths | None:
        """Execute `resolve`."""
        trace_path = self._baselines_dir / f"{spec_id}.jsonl"
        meta_path = self._meta_path(trace_path)
        fixture_path = self._fixtures_dir / f"{spec_id}.json"
        if not trace_path.exists():
            return None
        return BaselinePaths(
            trace_path=trace_path,
            meta_path=meta_path,
            fixture_path=fixture_path,
        )

    def write(
        self,
        spec_id: str,
        events: list[dict[str, object]],
        fixtures: dict[str, object] | None,
        meta: TraceMetaV03,
    ) -> BaselinePaths:
        """Execute `write`."""
        self._baselines_dir.mkdir(parents=True, exist_ok=True)
        self._fixtures_dir.mkdir(parents=True, exist_ok=True)

        trace_path = self._baselines_dir / f"{spec_id}.jsonl"
        meta_path = self._meta_path(trace_path)
        fixture_path = self._fixtures_dir / f"{spec_id}.json"

        with trace_path.open("w", encoding="utf-8") as fp:
            for event in events:
                fp.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")

        write_trace_meta(meta_path, meta)

        if fixtures is not None:
            fixture_path.write_text(
                json.dumps(fixtures, sort_keys=True, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

        return BaselinePaths(
            trace_path=trace_path,
            meta_path=meta_path,
            fixture_path=fixture_path,
        )

    def list_baselines(self, spec_id: str) -> list[str]:
        """Execute `list_baselines`."""
        pattern = f"{spec_id}.jsonl" if spec_id else "*.jsonl"
        return sorted(
            p.stem for p in self._baselines_dir.glob(pattern) if p.is_file()
        )


__all__ = ["BaselinePaths", "BaselineStore", "LocalBaselineStore"]
