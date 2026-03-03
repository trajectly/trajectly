"""Core implementation module: trajectly/core/diff/__init__.py."""

from trajectly.core.diff.engine import compare_traces
from trajectly.core.diff.models import DiffResult, Finding

__all__ = ["DiffResult", "Finding", "compare_traces"]
