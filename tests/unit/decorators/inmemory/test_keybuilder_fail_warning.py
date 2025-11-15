from __future__ import annotations

import logging

from cachine import InMemoryCache, cached


def test_key_builder_failure_logs_warning_and_falls_back(caplog):
    cache = InMemoryCache()

    def bad_builder(*_a, **_k):  # always fail
        raise TypeError("boom")

    calls = {"n": 0}

    @cached(cache=cache, ttl=60, key_builder=bad_builder)
    def add(a: int, b: int) -> int:
        calls["n"] += 1
        return a + b

    caplog.set_level(logging.WARNING)

    assert add(2, 3) == 5
    # Second call should be a hit if fallback key worked
    assert add(2, 3) == 5
    assert calls["n"] == 1

    # Ensure at least one warning was logged about key_builder failure
    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert any("key_builder" in r.msg for r in warnings)
