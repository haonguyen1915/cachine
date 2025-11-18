from __future__ import annotations

from cachine import InMemoryCache
from cachine.decorators import cached


def test_lazy_cache_factory_not_called_at_decoration_time() -> None:
    calls: list[str] = []

    def make_cache() -> InMemoryCache:
        calls.append("init")
        return InMemoryCache()

    @cached(cache=make_cache, ttl=10)
    def compute(x: int) -> int:
        return x + 1

    # Factory should not have been called during decoration
    assert calls == []

    # First invocation resolves the cache factory exactly once
    assert compute(1) == 2
    assert calls == ["init"]

    # Subsequent calls reuse the resolved cache; factory not called again
    assert compute(1) == 2
    assert calls == ["init"]


def test_lazy_cache_factory_returning_none_pass_through() -> None:
    calls: list[str] = []

    def make_cache_none():  # type: ignore[no-untyped-def]
        calls.append("init")
        return None

    n = {"calls": 0}

    @cached(cache=make_cache_none, ttl=10)
    def compute(x: int) -> int:
        n["calls"] += 1
        return x

    # Factory should not have been called during decoration
    assert calls == []

    # First invocation resolves to None -> pass-through (no caching)
    assert compute(7) == 7
    assert compute(7) == 7
    # Function executed twice because caching was bypassed
    assert n["calls"] == 2
    # Factory called once at first invocation
    assert calls == ["init"]

