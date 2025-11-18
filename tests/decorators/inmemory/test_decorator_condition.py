from __future__ import annotations

from cachine import InMemoryCache
from cachine.decorators import cached


def test_decorator_condition_prevents_store() -> None:
    cache = InMemoryCache()
    calls = {"n": 0}

    @cached(cache=cache, ttl=60, condition=lambda res: res > 0)
    def compute(x: int) -> int:
        calls["n"] += 1
        return x

    # First call with negative result -> condition False -> no store
    assert compute(-1) == -1
    # Second call with same args recomputes (not stored)
    assert compute(-1) == -1
    assert calls["n"] == 2

    # Positive result -> condition True -> store
    assert compute(5) == 5
    # Cached hit, no recompute
    assert compute(5) == 5
    assert calls["n"] == 3


def test_decorator_enabled_predicate_from_input() -> None:
    cache = InMemoryCache()
    calls = {"n": 0}

    # Disable caching when input starts with "no:" (lambda form)
    enabled = lambda ctx, args, kwargs: not (  # noqa: E731
        bool(args) and isinstance(args[0], str) and args[0].startswith("no:")
    )

    @cached(cache=cache, ttl=60, enabled=enabled)
    def f(k: str) -> str:
        calls["n"] += 1
        return k

    # disabled case: recompute
    assert f("no:1") == "no:1"
    assert f("no:1") == "no:1"
    # enabled case: store and hit
    assert f("ok:1") == "ok:1"
    assert f("ok:1") == "ok:1"
    # Two for disabled path + 1 for first ok + no increment on second ok
    assert calls["n"] == 3
