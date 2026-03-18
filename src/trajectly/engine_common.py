"""Compatibility shim: real code lives in trajectly.cli.engine_common."""
from trajectly.cli.engine_common import (
    CommandOutcome,
    SyncMetadata,
    _baseline_meta_path,
    _ensure_state_dirs,
    _read_sync_metadata,
    _slugify,
    _state_paths,
    _StatePaths,
    _sync_metadata_path,
    _write_sync_metadata,
)

__all__ = [
    "CommandOutcome",
    "SyncMetadata",
    "_StatePaths",
    "_baseline_meta_path",
    "_ensure_state_dirs",
    "_read_sync_metadata",
    "_slugify",
    "_state_paths",
    "_sync_metadata_path",
    "_write_sync_metadata",
]
