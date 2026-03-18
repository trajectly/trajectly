"""Acceptance tests for the documented platform API surface."""

from __future__ import annotations

from pathlib import Path

import pytest


def _platform_docs_path() -> Path:
    return Path(__file__).resolve().parents[2] / "docs" / "platform_api_surface.md"


def _readme_path() -> Path:
    return Path(__file__).resolve().parents[2] / "README.md"


def _validate_platform_api_docs(text: str) -> None:
    required_snippets = [
        "from trajectly.core import Trajectory, Verdict, Violation, evaluate",
        "from trajectly import Trajectory, Verdict, Violation, evaluate",
        "from trajectly.core.trace import (",
        "TrajectoryV03",
        "read_trajectory_json",
        "write_trajectory_json",
        "python -m trajectly sync",
        "0.4.x",
        "Breaking changes to this contract must ship in the next minor release",
        "Explicitly Not Part Of The Stable Import Contract",
        "trajectly.core.sync",
        "trajectly.cli.*",
    ]
    missing = [snippet for snippet in required_snippets if snippet not in text]
    if missing:
        raise ValueError("Platform API docs are missing required snippets: " + ", ".join(missing))


def test_write_public_api_surface_documentation_happy_path() -> None:
    docs_text = _platform_docs_path().read_text(encoding="utf-8")

    _validate_platform_api_docs(docs_text)

    assert "Stable Object Shapes" in docs_text
    assert "`Trajectory`" in docs_text
    assert "`Verdict`" in docs_text
    assert "`Violation`" in docs_text


def test_write_public_api_surface_documentation_validation_path() -> None:
    docs_text = _platform_docs_path().read_text(encoding="utf-8")
    readme_text = _readme_path().read_text(encoding="utf-8")

    _validate_platform_api_docs(docs_text)
    assert "docs/platform_api_surface.md" in readme_text

    with pytest.raises(ValueError, match="Platform API docs are missing required snippets"):
        _validate_platform_api_docs("from trajectly.core import evaluate")
