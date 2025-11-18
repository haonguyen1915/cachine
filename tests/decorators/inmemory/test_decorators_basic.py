import hashlib

from cachine import InMemoryCache
from cachine.decorators import cached


def test_cached_decorator_full_config_inmemory() -> None:
    cache = InMemoryCache()
    calls = {"n": 0}

    def kb(a: int, b: int) -> str:
        # stable, non-PII key
        return f"sum:{hashlib.sha256(f'{a}:{b}'.encode()).hexdigest()}"

    @cached(
        cache,
        ttl=2,
        jitter=1,
        key_builder=kb,
        condition=lambda r: r is not None,
        version="v1",
        cache_none=False,
        stale_ttl=2,
        singleflight=True,
        tags=["math", "sum"],
        tags_from_result=lambda r: [f"sum:{r}"] if r is not None else [],
    )
    def add(a: int, b: int) -> int:
        calls["n"] += 1
        return a + b

    # Caches result with full options
    assert add(1, 2) == 3
    assert add(1, 2) == 3
    assert calls["n"] == 1

    # Invalidate by tag and recompute
    removed = cache.invalidate_tags(["math"])
    assert removed >= 1
    assert add(1, 2) == 3
    assert calls["n"] == 2
