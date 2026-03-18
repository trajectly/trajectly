"""Acceptance tests for the dedicated platform API CI gate."""

from __future__ import annotations

from pathlib import Path

import pytest


def _ci_path() -> Path:
    return Path(__file__).resolve().parents[2] / ".github" / "workflows" / "ci.yml"


def _validate_ci_gate(text: str) -> None:
    required_snippets = [
        "- name: Platform API Compatibility",
        "- name: Test",
        "tests/unit/test_platform_api_contract.py",
        "tests/unit/test_boundary_enforcement.py",
        "tests/integration/test_platform_api_smoke.py",
        "tests/integration/test_platform_evaluate_import.py",
    ]
    missing = [snippet for snippet in required_snippets if snippet not in text]
    if missing:
        raise ValueError("CI compatibility gate is missing required snippets: " + ", ".join(missing))

    compatibility_index = text.index("- name: Platform API Compatibility")
    full_test_index = text.index("- name: Test")
    if compatibility_index > full_test_index:
        raise ValueError("CI compatibility gate must run before the full test suite")


def test_add_ci_compatibility_gate_for_platform_facing_api_integration_happy_path() -> None:
    ci_text = _ci_path().read_text(encoding="utf-8")

    _validate_ci_gate(ci_text)

    assert "pytest -q \\" in ci_text


def test_add_ci_compatibility_gate_for_platform_facing_api_integration_error_path() -> None:
    with pytest.raises(ValueError, match="CI compatibility gate is missing required snippets"):
        _validate_ci_gate(
            """
name: ci
jobs:
  test:
    steps:
      - name: Test
        run: pytest -q
"""
        )

    with pytest.raises(ValueError, match="CI compatibility gate must run before the full test suite"):
        _validate_ci_gate(
            """
name: ci
jobs:
  test:
    steps:
      - name: Test
        run: pytest -q
      - name: Platform API Compatibility
        run: pytest -q tests/integration/test_platform_evaluate_import.py
      - name: Another step
        run: echo done
      - name: paths
        run: |
          pytest -q \
            tests/unit/test_platform_api_contract.py \
            tests/unit/test_boundary_enforcement.py \
            tests/integration/test_platform_api_smoke.py \
            tests/integration/test_platform_evaluate_import.py
"""
        )
