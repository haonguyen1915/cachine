from typing import Any

from cachine import RedisCache
from cachine.decorators import cached


def test_args_only_redis(redis_cache: RedisCache) -> None:
    cache = redis_cache
    calls = {"n": 0}

    @cached(cache, ttl=60)
    def add(a: int, b: int) -> int:
        calls["n"] += 1
        return a + b

    assert add(1, 2) == 3
    assert add(1, 2) == 3
    assert calls["n"] == 1


def test_kwargs_only_redis(redis_cache: RedisCache) -> None:
    cache = redis_cache
    calls = {"n": 0}

    @cached(cache, ttl=60)
    def add(a: int, b: int) -> int:
        calls["n"] += 1
        return a + b

    assert add(a=1, b=2) == 3
    assert add(a=1, b=2) == 3
    assert calls["n"] == 1


def test_args_kwargs_equivalence_with_custom_keybuilder_redis(redis_cache: RedisCache) -> None:
    cache = redis_cache
    calls = {"n": 0}

    def kb(*args: Any, **kwargs: Any) -> str:
        if args and hasattr(args[0], "full_name"):
            args = args[1:]
        if len(args) >= 2:
            a, b = args[0], args[1]
        else:
            a = kwargs.get("a")
            b = kwargs.get("b")
        return f"sum:{a}:{b}"

    @cached(cache, ttl=60, key_builder=kb)
    def add(a: int, b: int) -> int:
        calls["n"] += 1
        return a + b

    assert add(1, 2) == 3
    assert add(a=1, b=2) == 3
    assert add(b=2, a=1) == 3
    assert calls["n"] == 1
