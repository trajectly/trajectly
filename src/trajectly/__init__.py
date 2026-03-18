"""Trajectly module: trajectly/__init__.py."""

from __future__ import annotations

from trajectly.core import Trajectory, Verdict, Violation, evaluate
from trajectly.sdk.graph import App

__all__ = [
    "App",
    "Trajectory",
    "Verdict",
    "Violation",
    "__version__",
    "evaluate",
]

__version__ = "0.4.2"
