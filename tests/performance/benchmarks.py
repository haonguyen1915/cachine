"""Performance benchmarks and helpers.

These tests are informational and skipped unless RUN_PERF_TESTS is truthy.
Use PERF_N to control the number of iterations (defaults chosen conservatively
for CI stability). Tests print throughput metrics but only assert correctness,
not absolute speed thresholds, to avoid flakiness across environments.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable

import pytest


def _truthy(val: str | None) -> bool:
    return (val or "").lower() in {"1", "true", "yes", "on"}


perf_enabled = pytest.mark.skipif(not _truthy(os.getenv("RUN_PERF_TESTS")), reason="RUN_PERF_TESTS not enabled")


def measure_throughput(fn: Callable[[], None], *, iterations: int) -> float:
    """Measure simple throughput for a no-arg callable.

    Args:
        fn: Callable to execute in a tight loop.
        iterations: Number of invocations.

    Returns:
        float: Operations per second.
    """
    start = time.perf_counter()
    for _ in range(iterations):
        fn()
    elapsed = time.perf_counter() - start
    return iterations / elapsed if elapsed > 0 else float("inf")


@perf_enabled
def test_perf_placeholder_smoke():
    # Simple micro benchmark to ensure harness works
    N = int(os.getenv("PERF_N", "10000"))
    counter = {"x": 0}

    def inc() -> None:
        counter["x"] += 1

    ops = measure_throughput(inc, iterations=N)
    assert counter["x"] == N
    # Print for human inspection
    print(f"placeholder throughput: {ops:,.0f} ops/s over {N} iterations")
