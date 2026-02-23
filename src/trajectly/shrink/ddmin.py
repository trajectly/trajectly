from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from math import ceil
from time import monotonic

from trajectly.events import TraceEvent


@dataclass(slots=True)
class ShrinkResult:
    original_len: int
    reduced_len: int
    iterations: int
    seconds: float
    reduced_events: list[TraceEvent]

    @property
    def reduced(self) -> bool:
        return self.reduced_len < self.original_len


def ddmin_shrink(
    *,
    events: list[TraceEvent],
    failure_predicate: Callable[[list[TraceEvent]], bool],
    max_seconds: float,
    max_iterations: int,
) -> ShrinkResult:
    if max_seconds <= 0:
        raise ValueError("max_seconds must be > 0")
    if max_iterations <= 0:
        raise ValueError("max_iterations must be > 0")
    if not events:
        raise ValueError("events must not be empty")
    if not failure_predicate(events):
        raise ValueError("failure_predicate must hold for original events")

    started = monotonic()
    current = list(events)
    granularity = 2
    iterations = 0

    while len(current) >= 2:
        elapsed = monotonic() - started
        if elapsed >= max_seconds or iterations >= max_iterations:
            break

        chunk_size = max(1, ceil(len(current) / granularity))
        reduced_this_round = False

        for start in range(0, len(current), chunk_size):
            elapsed = monotonic() - started
            if elapsed >= max_seconds or iterations >= max_iterations:
                break

            end = min(len(current), start + chunk_size)
            candidate = [*current[:start], *current[end:]]
            if not candidate:
                continue

            iterations += 1
            if failure_predicate(candidate):
                current = candidate
                granularity = max(2, granularity - 1)
                reduced_this_round = True
                break

        if not reduced_this_round:
            if granularity >= len(current):
                break
            granularity = min(len(current), granularity * 2)

    seconds = monotonic() - started
    return ShrinkResult(
        original_len=len(events),
        reduced_len=len(current),
        iterations=iterations,
        seconds=round(seconds, 6),
        reduced_events=current,
    )


__all__ = ["ShrinkResult", "ddmin_shrink"]
