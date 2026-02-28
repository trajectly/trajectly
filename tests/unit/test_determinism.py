from __future__ import annotations

import datetime as datetime_module
import json
import random
import time as time_module
import uuid as uuid_module
from pathlib import Path

import pytest

from trajectly.core import determinism
from trajectly.core.constants import (
    NONDETERMINISM_FILESYSTEM_DETECTED,
    NONDETERMINISM_UUID_DETECTED,
)


@pytest.fixture(autouse=True)
def _reset_determinism() -> None:
    determinism.reset_for_tests()
    yield
    determinism.reset_for_tests()


def _configure_env(
    monkeypatch: pytest.MonkeyPatch,
    *,
    project_root: Path,
    config: dict[str, object],
    mode: str = "replay",
    clock_seed: float | None = None,
    random_seed: int | None = None,
) -> None:
    monkeypatch.setenv("TRAJECTLY_DETERMINISM_JSON", json.dumps(config))
    monkeypatch.setenv("TRAJECTLY_MODE", mode)
    monkeypatch.setenv("TRAJECTLY_PROJECT_ROOT", str(project_root))
    if clock_seed is None:
        monkeypatch.delenv("TRAJECTLY_CLOCK_SEED", raising=False)
    else:
        monkeypatch.setenv("TRAJECTLY_CLOCK_SEED", str(clock_seed))
    if random_seed is None:
        monkeypatch.delenv("TRAJECTLY_RANDOM_SEED", raising=False)
    else:
        monkeypatch.setenv("TRAJECTLY_RANDOM_SEED", str(random_seed))


def test_clock_freeze_replay_returns_identical_timestamp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seed = 1_710_000_000.0
    _configure_env(
        monkeypatch,
        project_root=tmp_path,
        config={"clock": {"mode": "freeze_only"}},
        clock_seed=seed,
    )

    determinism.activate_from_env()

    first_now = datetime_module.datetime.now(datetime_module.UTC)
    second_now = datetime_module.datetime.now(datetime_module.UTC)

    assert first_now == second_now
    assert time_module.time() == seed
    assert time_module.monotonic() == seed


def test_clock_disabled_does_not_freeze_to_seed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seed = 1.0
    _configure_env(
        monkeypatch,
        project_root=tmp_path,
        config={"clock": {"mode": "disabled"}},
        clock_seed=seed,
    )

    determinism.activate_from_env()

    assert time_module.time() != seed


def test_random_seed_and_uuid_sequence_are_reproducible(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = {"random": {"mode": "deterministic_seed"}}
    _configure_env(monkeypatch, project_root=tmp_path, config=config, random_seed=4242)
    determinism.activate_from_env()

    first_random = [random.random() for _ in range(3)]
    first_uuid = [str(uuid_module.uuid4()) for _ in range(3)]

    determinism.reset_for_tests()
    _configure_env(monkeypatch, project_root=tmp_path, config=config, random_seed=4242)
    determinism.activate_from_env()

    second_random = [random.random() for _ in range(3)]
    second_uuid = [str(uuid_module.uuid4()) for _ in range(3)]

    assert first_random == second_random
    assert first_uuid == second_uuid


def test_random_strict_mode_blocks_uuid_usage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_env(
        monkeypatch,
        project_root=tmp_path,
        config={"random": {"mode": "strict"}},
        random_seed=7,
    )
    determinism.activate_from_env()

    with pytest.raises(determinism.DeterminismViolationError) as exc_info:
        _ = uuid_module.uuid4()

    assert exc_info.value.code == NONDETERMINISM_UUID_DETECTED
    assert "suggested_fix" in exc_info.value.details


def test_filesystem_strict_mode_blocks_unapproved_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "secret.txt"
    target.write_text("sensitive\n", encoding="utf-8")
    _configure_env(
        monkeypatch,
        project_root=tmp_path,
        config={
            "filesystem": {
                "mode": "strict",
                "allow_read_paths": [],
                "allow_write_paths": [],
            }
        },
    )
    determinism.activate_from_env()

    with pytest.raises(determinism.DeterminismViolationError) as exc_info:
        _ = target.read_text(encoding="utf-8")

    assert exc_info.value.code == NONDETERMINISM_FILESYSTEM_DETECTED
    assert exc_info.value.details.get("payload_diff") == {"missing_allow_read_path": str(target.resolve())}


def test_filesystem_strict_mode_allows_allowlisted_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    allowed_dir = tmp_path / "config"
    allowed_dir.mkdir(parents=True, exist_ok=True)
    target = allowed_dir / "safe.txt"
    target.write_text("ok\n", encoding="utf-8")
    _configure_env(
        monkeypatch,
        project_root=tmp_path,
        config={
            "filesystem": {
                "mode": "strict",
                "allow_read_paths": ["config"],
                "allow_write_paths": [],
            }
        },
    )
    determinism.activate_from_env()

    assert target.read_text(encoding="utf-8").strip() == "ok"
