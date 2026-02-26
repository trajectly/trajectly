"""Verify architectural boundaries: core must not depend on CLI frameworks."""
from __future__ import annotations

import ast
from pathlib import Path


def _collect_python_files(directory: Path) -> list[Path]:
    return sorted(directory.rglob("*.py"))


def _extract_imports(source: str) -> list[str]:
    tree = ast.parse(source)
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return modules


CORE_ROOT = Path(__file__).resolve().parents[2] / "src" / "trajectly" / "core"

FORBIDDEN_IN_CORE = {"typer", "rich", "click"}


def test_core_has_no_cli_framework_imports() -> None:
    violations: list[str] = []
    for py_file in _collect_python_files(CORE_ROOT):
        source = py_file.read_text(encoding="utf-8")
        for mod in _extract_imports(source):
            top_level = mod.split(".")[0]
            if top_level in FORBIDDEN_IN_CORE:
                rel = py_file.relative_to(CORE_ROOT)
                violations.append(f"{rel}: imports {mod}")

    assert not violations, (
        "Core package must not import CLI frameworks:\n" + "\n".join(violations)
    )


def test_sdk_has_no_cli_imports() -> None:
    sdk_root = CORE_ROOT.parent / "sdk"
    violations: list[str] = []
    for py_file in _collect_python_files(sdk_root):
        source = py_file.read_text(encoding="utf-8")
        for mod in _extract_imports(source):
            top_level = mod.split(".")[0]
            if top_level in FORBIDDEN_IN_CORE:
                rel = py_file.relative_to(sdk_root)
                violations.append(f"{rel}: imports {mod}")
            if mod.startswith("trajectly.cli"):
                rel = py_file.relative_to(sdk_root)
                violations.append(f"{rel}: imports {mod}")

    assert not violations, (
        "SDK must not import CLI frameworks or CLI layer:\n" + "\n".join(violations)
    )
