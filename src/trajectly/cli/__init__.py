"""Trajectly CLI — Typer commands and orchestration layer."""
from __future__ import annotations


def __getattr__(name: str) -> object:
    """Execute `__getattr__`."""
    if name == "app":
        from trajectly.cli.commands import app
        return app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["app"]
