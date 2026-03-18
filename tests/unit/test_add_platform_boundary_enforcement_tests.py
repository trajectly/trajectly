"""Acceptance tests for the platform API contract boundary suite."""

from __future__ import annotations

from pathlib import Path

import pytest


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _validate_boundary_suite(contract_text: str, boundary_text: str) -> None:
    required_contract_snippets = [
        "test_platform_core_public_surface_matches_documented_contract",
        "test_platform_value_objects_keep_documented_fields_and_helpers",
        "test_platform_trace_surface_matches_documented_contract",
    ]
    required_boundary_snippets = [
        "FORBIDDEN_CORE_PREFIXES",
        "trajectly.cli",
        "trajectly.engine_common",
        "test_platform_contract_doc_lists_non_api_modules_that_remain_internal",
    ]
    missing = [
        snippet
        for snippet in required_contract_snippets
        if snippet not in contract_text
    ] + [
        snippet
        for snippet in required_boundary_snippets
        if snippet not in boundary_text
    ]
    if missing:
        raise ValueError("Platform boundary suite is missing required coverage: " + ", ".join(missing))


def test_add_platform_boundary_enforcement_tests_happy_path() -> None:
    contract_text = (_repo_root() / "tests" / "unit" / "test_platform_api_contract.py").read_text(encoding="utf-8")
    boundary_text = (_repo_root() / "tests" / "unit" / "test_boundary_enforcement.py").read_text(encoding="utf-8")

    _validate_boundary_suite(contract_text, boundary_text)


def test_add_platform_boundary_enforcement_tests_validation_path() -> None:
    contract_text = (_repo_root() / "tests" / "unit" / "test_platform_api_contract.py").read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="Platform boundary suite is missing required coverage"):
        _validate_boundary_suite(contract_text, "def test_core_has_no_cli_framework_imports():\n    pass\n")
