"""Core implementation module: trajectly/core/trt/__init__.py."""

from trajectly.core.trt.types import TRTViolation
from trajectly.core.trt.witness import WitnessResolution, resolve_witness

__all__ = [
    "TRTViolation",
    "WitnessResolution",
    "resolve_witness",
]
