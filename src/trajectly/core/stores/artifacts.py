"""ArtifactStore protocol and local filesystem implementation."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class ArtifactStore(Protocol):
    """Abstraction for reading/writing artifacts (reports, repros, etc.)."""

    def put_bytes(self, key: str, data: bytes) -> None: ...
    def put_file(self, key: str, path: Path) -> None: ...
    def get_bytes(self, key: str) -> bytes: ...
    def list_keys(self, prefix: str) -> list[str]: ...


class LocalArtifactStore:
    """Wraps the existing .trajectly/{reports,repros}/ filesystem layout."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def root(self) -> Path:
        return self._root

    def put_bytes(self, key: str, data: bytes) -> None:
        dest = self._root / key
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)

    def put_file(self, key: str, path: Path) -> None:
        dest = self._root / key
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(path), str(dest))

    def get_bytes(self, key: str) -> bytes:
        target = self._root / key
        if not target.exists():
            raise FileNotFoundError(f"Artifact not found: {key}")
        return target.read_bytes()

    def list_keys(self, prefix: str) -> list[str]:
        base = self._root / prefix if prefix else self._root
        if not base.exists():
            return []
        results: list[str] = []
        for path in sorted(base.rglob("*")):
            if path.is_file():
                results.append(str(path.relative_to(self._root)))
        return results


__all__ = ["ArtifactStore", "LocalArtifactStore"]
