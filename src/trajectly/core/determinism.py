from __future__ import annotations

import builtins
import datetime as datetime_module
import hashlib
import io
import json
import os
import random
import shlex
import subprocess
import time as time_module
import uuid as uuid_module
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from trajectly.core.constants import (
    NONDETERMINISM_CLOCK_DETECTED,
    NONDETERMINISM_FILESYSTEM_DETECTED,
    NONDETERMINISM_RANDOM_DETECTED,
    NONDETERMINISM_UUID_DETECTED,
)

_ORIGINAL_DATETIME_CLASS = datetime_module.datetime
_ORIGINAL_TIME = time_module.time
_ORIGINAL_MONOTONIC = time_module.monotonic
_ORIGINAL_OPEN = builtins.open
_ORIGINAL_IO_OPEN = io.open
_ORIGINAL_PATH_OPEN = Path.open
_ORIGINAL_UUID4 = uuid_module.uuid4
_ORIGINAL_URANDOM = os.urandom
_ORIGINAL_SUBPROCESS_RUN = subprocess.run
_ORIGINAL_SUBPROCESS_POPEN = subprocess.Popen

_ACTIVE = False


@dataclass(slots=True)
class DeterminismViolationError(RuntimeError):
    code: str
    message: str
    details: dict[str, Any]

    def __str__(self) -> str:
        return f"{self.code}: {self.message} :: {json.dumps(self.details, sort_keys=True)}"


@dataclass(slots=True)
class ClockConfig:
    mode: str = "disabled"


@dataclass(slots=True)
class RandomConfig:
    mode: str = "disabled"


@dataclass(slots=True)
class FilesystemConfig:
    mode: str = "permissive"
    allow_read_paths: list[str] = field(default_factory=list)
    allow_write_paths: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SubprocessConfig:
    mode: str = "disabled"
    allow_commands: list[str] = field(default_factory=list)


@dataclass(slots=True)
class DeterminismConfig:
    clock: ClockConfig = field(default_factory=ClockConfig)
    random: RandomConfig = field(default_factory=RandomConfig)
    filesystem: FilesystemConfig = field(default_factory=FilesystemConfig)
    subprocess: SubprocessConfig = field(default_factory=SubprocessConfig)


@dataclass(slots=True)
class RuntimeState:
    mode: str
    project_root: Path
    config: DeterminismConfig
    clock_seed: float | None
    random_seed: int | None

    allow_read_paths: list[Path] = field(default_factory=list)
    allow_write_paths: list[Path] = field(default_factory=list)
    allow_commands: set[str] = field(default_factory=set)

    deterministic_rng: random.Random | None = None
    frozen_timestamp: float | None = None


def _sha(value: Any) -> str:
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    except TypeError:
        raw = repr(value)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _raise_violation(
    *,
    code: str,
    message: str,
    expected: Any,
    actual: Any,
    suggested_fix: str,
    payload_diff: dict[str, Any] | None = None,
) -> None:
    details: dict[str, Any] = {
        "expected": expected,
        "actual": actual,
        "expected_hash": _sha(expected),
        "actual_hash": _sha(actual),
        "suggested_fix": suggested_fix,
    }
    if payload_diff is not None:
        details["payload_diff"] = payload_diff
    raise DeterminismViolationError(code=code, message=message, details=details)


def _parse_config(raw: str | None) -> DeterminismConfig:
    if not raw:
        return DeterminismConfig()
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        return DeterminismConfig()

    clock_raw = payload.get("clock")
    random_raw = payload.get("random")
    fs_raw = payload.get("filesystem")
    sp_raw = payload.get("subprocess")

    clock = ClockConfig(mode=str((clock_raw or {}).get("mode", "disabled")))
    random_cfg = RandomConfig(mode=str((random_raw or {}).get("mode", "disabled")))
    filesystem = FilesystemConfig(
        mode=str((fs_raw or {}).get("mode", "permissive")),
        allow_read_paths=[str(item) for item in (fs_raw or {}).get("allow_read_paths", []) if isinstance(item, str)],
        allow_write_paths=[
            str(item) for item in (fs_raw or {}).get("allow_write_paths", []) if isinstance(item, str)
        ],
    )
    subprocess_cfg = SubprocessConfig(
        mode=str((sp_raw or {}).get("mode", "disabled")),
        allow_commands=[str(item).strip().lower() for item in (sp_raw or {}).get("allow_commands", [])],
    )
    return DeterminismConfig(clock=clock, random=random_cfg, filesystem=filesystem, subprocess=subprocess_cfg)


def _resolve_path(project_root: Path, raw: str) -> Path:
    candidate = Path(raw)
    if candidate.is_absolute():
        return candidate.resolve()
    return (project_root / candidate).resolve()


def _build_state_from_env() -> RuntimeState | None:
    config = _parse_config(os.getenv("TRAJECTLY_DETERMINISM_JSON"))
    if (
        config.clock.mode == "disabled"
        and config.random.mode == "disabled"
        and config.filesystem.mode == "permissive"
        and config.subprocess.mode == "disabled"
    ):
        return None

    mode = os.getenv("TRAJECTLY_MODE", "record").strip().lower()
    project_root = Path(os.getenv("TRAJECTLY_PROJECT_ROOT", ".")).resolve()

    clock_seed: float | None = None
    random_seed: int | None = None
    clock_seed_raw = os.getenv("TRAJECTLY_CLOCK_SEED")
    random_seed_raw = os.getenv("TRAJECTLY_RANDOM_SEED")
    if clock_seed_raw:
        clock_seed = float(clock_seed_raw)
    if random_seed_raw:
        random_seed = int(random_seed_raw)

    state = RuntimeState(
        mode=mode,
        project_root=project_root,
        config=config,
        clock_seed=clock_seed,
        random_seed=random_seed,
    )

    for raw in config.filesystem.allow_read_paths:
        state.allow_read_paths.append(_resolve_path(project_root, raw))
    for raw in config.filesystem.allow_write_paths:
        state.allow_write_paths.append(_resolve_path(project_root, raw))
    for raw in config.subprocess.allow_commands:
        if raw:
            state.allow_commands.add(raw)

    # Internal Trajectly artifacts must remain writable/readable when strict FS mode is enabled.
    for env_name in (
        "TRAJECTLY_EVENTS_FILE",
        "TRAJECTLY_TRACE_FILE",
        "TRAJECTLY_TRACE_META_FILE",
        "TRAJECTLY_FIXTURES_FILE",
    ):
        path_raw = os.getenv(env_name)
        if not path_raw:
            continue
        path_value = Path(path_raw).resolve()
        state.allow_read_paths.append(path_value)
        state.allow_write_paths.append(path_value)
        state.allow_read_paths.append(path_value.parent)
        state.allow_write_paths.append(path_value.parent)

    return state


def _is_within(parent: Path, child: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _allowed_path(path: Path, allowlist: list[Path]) -> bool:
    return any(_is_within(candidate, path) for candidate in allowlist)


def _parse_access_mode(mode: str) -> tuple[bool, bool]:
    normalized = mode or "r"
    is_read = "r" in normalized or "+" in normalized
    is_write = any(flag in normalized for flag in ("w", "a", "x", "+"))
    return is_read, is_write


def _guard_path_access(state: RuntimeState, file: str | os.PathLike[str], mode: str) -> None:
    if state.config.filesystem.mode != "strict":
        return
    candidate = Path(file).resolve()

    # Only enforce for project-local paths to avoid breaking interpreter/module internals.
    if not _is_within(state.project_root, candidate):
        return

    is_read, is_write = _parse_access_mode(mode)
    if is_read and not _allowed_path(candidate, state.allow_read_paths):
        _raise_violation(
            code=NONDETERMINISM_FILESYSTEM_DETECTED,
            message=f"Unapproved file read during deterministic replay: {candidate}",
            expected={"allow_read_paths": [str(item) for item in state.allow_read_paths]},
            actual={"path": str(candidate), "mode": mode},
            suggested_fix=(
                "Add the path under determinism.filesystem.allow_read_paths in your spec, "
                "or route file access through an explicit deterministic @tool."
            ),
            payload_diff={"missing_allow_read_path": str(candidate)},
        )
    if is_write and not _allowed_path(candidate, state.allow_write_paths):
        _raise_violation(
            code=NONDETERMINISM_FILESYSTEM_DETECTED,
            message=f"Unapproved file write during deterministic replay: {candidate}",
            expected={"allow_write_paths": [str(item) for item in state.allow_write_paths]},
            actual={"path": str(candidate), "mode": mode},
            suggested_fix=(
                "Add the path under determinism.filesystem.allow_write_paths in your spec, "
                "or disable strict filesystem determinism for this spec."
            ),
            payload_diff={"missing_allow_write_path": str(candidate)},
        )


def _install_clock_hooks(state: RuntimeState) -> None:
    clock_mode = state.config.clock.mode
    if clock_mode == "disabled":
        return

    should_freeze = clock_mode == "record_and_freeze" or (clock_mode == "freeze_only" and state.mode == "replay")
    if not should_freeze:
        return

    if state.clock_seed is None:
        _raise_violation(
            code=NONDETERMINISM_CLOCK_DETECTED,
            message="Clock freeze requested but no clock seed was provided",
            expected={"clock_seed": "float timestamp"},
            actual={"clock_seed": None},
            suggested_fix="Re-record baseline with determinism.clock.mode=record_and_freeze to capture clock_seed.",
        )
    assert state.clock_seed is not None
    state.frozen_timestamp = state.clock_seed
    frozen_dt = _ORIGINAL_DATETIME_CLASS.fromtimestamp(state.clock_seed, tz=datetime_module.UTC)

    class FrozenDateTime(_ORIGINAL_DATETIME_CLASS):
        @classmethod
        def now(cls, tz: datetime_module.tzinfo | None = None) -> FrozenDateTime:
            if tz is None:
                return cast(FrozenDateTime, frozen_dt.replace(tzinfo=None))
            return cast(FrozenDateTime, frozen_dt.astimezone(tz))

        @classmethod
        def utcnow(cls) -> FrozenDateTime:
            return cast(FrozenDateTime, frozen_dt.replace(tzinfo=None))

    cast(Any, datetime_module).datetime = FrozenDateTime
    time_module.time = lambda: float(state.frozen_timestamp or state.clock_seed or 0.0)
    time_module.monotonic = lambda: float(state.frozen_timestamp or state.clock_seed or 0.0)


def _install_random_hooks(state: RuntimeState) -> None:
    random_mode = state.config.random.mode
    if random_mode == "disabled":
        return

    if state.random_seed is None:
        _raise_violation(
            code=NONDETERMINISM_RANDOM_DETECTED,
            message="Random determinism enabled but no random_seed was provided",
            expected={"random_seed": "int"},
            actual={"random_seed": None},
            suggested_fix="Re-record baseline with deterministic randomness enabled to capture random_seed.",
        )
    assert state.random_seed is not None

    random.seed(state.random_seed)
    state.deterministic_rng = random.Random(state.random_seed)

    if random_mode in {"deterministic_seed", "strict"}:
        def deterministic_uuid4() -> uuid_module.UUID:
            assert state.deterministic_rng is not None
            if random_mode == "strict":
                _raise_violation(
                    code=NONDETERMINISM_UUID_DETECTED,
                    message="uuid.uuid4() is blocked in strict deterministic mode",
                    expected={"uuid_source": "explicit deterministic @tool or seeded generator"},
                    actual={"call": "uuid.uuid4"},
                    suggested_fix="Wrap UUID generation in an explicit @tool and record its output.",
                )
            bits = state.deterministic_rng.getrandbits(128)
            bits = (bits & ~(0xF << 76)) | (4 << 76)
            bits = (bits & ~(0x3 << 62)) | (0x2 << 62)
            return uuid_module.UUID(int=bits)

        uuid_module.uuid4 = deterministic_uuid4

        def deterministic_urandom(size: int) -> bytes:
            assert state.deterministic_rng is not None
            if random_mode == "strict":
                _raise_violation(
                    code=NONDETERMINISM_RANDOM_DETECTED,
                    message="os.urandom() is blocked in strict deterministic mode",
                    expected={"random_source": "deterministic_seed"},
                    actual={"call": "os.urandom", "size": size},
                    suggested_fix="Use seeded `random` usage through explicit @tool wrappers instead of os.urandom.",
                )
            return bytes(state.deterministic_rng.getrandbits(8) for _ in range(size))

        os.urandom = deterministic_urandom


def _extract_command_name(command: Any) -> str:
    if isinstance(command, str):
        tokens = shlex.split(command)
        return tokens[0].strip().lower() if tokens else ""
    if isinstance(command, (list, tuple)) and command:
        return str(command[0]).strip().lower()
    return ""


def _install_filesystem_hooks(state: RuntimeState) -> None:
    if state.config.filesystem.mode != "strict":
        return

    def guarded_open(
        file: str | os.PathLike[str],
        mode: str = "r",
        buffering: int = -1,
        encoding: str | None = None,
        errors: str | None = None,
        newline: str | None = None,
        closefd: bool = True,
        opener: Callable[[str, int], int] | None = None,
    ) -> Any:
        _guard_path_access(state, file, mode)
        return _ORIGINAL_OPEN(file, mode, buffering, encoding, errors, newline, closefd, opener)

    def guarded_io_open(
        file: str | os.PathLike[str],
        mode: str = "r",
        buffering: int = -1,
        encoding: str | None = None,
        errors: str | None = None,
        newline: str | None = None,
        closefd: bool = True,
        opener: Callable[[str, int], int] | None = None,
    ) -> Any:
        _guard_path_access(state, file, mode)
        return _ORIGINAL_IO_OPEN(file, mode, buffering, encoding, errors, newline, closefd, opener)

    def guarded_path_open(
        self: Path,
        mode: str = "r",
        buffering: int = -1,
        encoding: str | None = None,
        errors: str | None = None,
        newline: str | None = None,
    ) -> Any:
        _guard_path_access(state, str(self), mode)
        return _ORIGINAL_PATH_OPEN(self, mode, buffering, encoding, errors, newline)

    cast(Any, builtins).open = guarded_open
    cast(Any, io).open = guarded_io_open
    cast(Any, Path).open = guarded_path_open


def _install_subprocess_hooks(state: RuntimeState) -> None:
    if state.config.subprocess.mode != "strict":
        return

    def guard_command(command: Any) -> None:
        name = _extract_command_name(command)
        if not name:
            return
        if name in state.allow_commands:
            return
        _raise_violation(
            code=NONDETERMINISM_FILESYSTEM_DETECTED,
            message=f"Subprocess command blocked in strict deterministic mode: {name}",
            expected={"allow_commands": sorted(state.allow_commands)},
            actual={"command": str(command)},
            suggested_fix="Add the command name under determinism.subprocess.allow_commands or disable strict mode.",
            payload_diff={"blocked_command": name},
        )

    def guarded_run(*args: Any, **kwargs: Any) -> Any:
        command = args[0] if args else kwargs.get("args")
        guard_command(command)
        return _ORIGINAL_SUBPROCESS_RUN(*args, **kwargs)

    def guarded_popen(*args: Any, **kwargs: Any) -> Any:
        command = args[0] if args else kwargs.get("args")
        guard_command(command)
        return _ORIGINAL_SUBPROCESS_POPEN(*args, **kwargs)

    cast(Any, subprocess).run = guarded_run
    cast(Any, subprocess).Popen = guarded_popen


def activate_from_env() -> None:
    global _ACTIVE
    if _ACTIVE:
        return
    state = _build_state_from_env()
    if state is None:
        return
    _install_clock_hooks(state)
    _install_random_hooks(state)
    _install_filesystem_hooks(state)
    _install_subprocess_hooks(state)
    _ACTIVE = True


def reset_for_tests() -> None:
    global _ACTIVE
    cast(Any, datetime_module).datetime = _ORIGINAL_DATETIME_CLASS
    time_module.time = _ORIGINAL_TIME
    time_module.monotonic = _ORIGINAL_MONOTONIC
    cast(Any, builtins).open = _ORIGINAL_OPEN
    cast(Any, io).open = _ORIGINAL_IO_OPEN
    cast(Any, Path).open = _ORIGINAL_PATH_OPEN
    uuid_module.uuid4 = _ORIGINAL_UUID4
    os.urandom = _ORIGINAL_URANDOM
    cast(Any, subprocess).run = _ORIGINAL_SUBPROCESS_RUN
    cast(Any, subprocess).Popen = _ORIGINAL_SUBPROCESS_POPEN
    _ACTIVE = False


__all__ = [
    "DeterminismViolationError",
    "activate_from_env",
    "reset_for_tests",
]
