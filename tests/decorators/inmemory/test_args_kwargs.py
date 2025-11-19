from typing import Any

from cachine import InMemoryCache
from cachine.decorators import cached
from cachine.models import KeyContext


def test_args_only_inmemory() -> None:
    cache = InMemoryCache()
    calls = {"n": 0}

    @cached(cache, ttl=60)
    def add(a: int, b: int) -> int:
        calls["n"] += 1
        return a + b

    assert add(1, 2) == 3
    assert add(1, 2) == 3
    assert calls["n"] == 1


def test_kwargs_only_inmemory() -> None:
    cache = InMemoryCache()
    calls = {"n": 0}

    @cached(cache, ttl=60)
    def add(a: int, b: int) -> int:
        calls["n"] += 1
        return a + b

    assert add(a=1, b=2) == 3
    assert add(a=1, b=2) == 3
    assert calls["n"] == 1


def test_args_kwargs_equivalence_with_custom_keybuilder_inmemory() -> None:
    cache = InMemoryCache()
    calls = {"n": 0}

    def kb(_ctx: KeyContext, *args: Any, **kwargs: Any) -> str:
        # Normalize to (a, b) regardless of how they were passed; ignore KeyContext if present
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
