from __future__ import annotations

from typing import Any

from cachine import InMemoryCache, cached
from cachine.utils.key_builder import template_key_builder


def test_template_key_builder_positional_and_ctx() -> None:
    cache = InMemoryCache()
    kb = template_key_builder("{ctx.full_name}:{0}:{1}")
    recorded: list[str] = []

    def rkb(ctx: Any, *args: Any, **kwargs: Any) -> str:
        s = kb(ctx, *args, **kwargs)
        recorded.append(s)
        return s

    @cached(cache=cache, ttl=60, key_builder=rkb, version="v1")
    def add(a: int, b: int) -> int:
        return a + b

    # call and ensure value is cached under expected key
    assert add(2, 3) == 5
    expected_key = f"{recorded[0]}|v:v1"
    assert cache.exists(expected_key)
    assert cache.get(expected_key) == 5 or cache.get(expected_key).get("v") == 5  # handle SWR envelope if present later


def test_template_key_builder_kwargs_only() -> None:
    cache = InMemoryCache()
    kb = template_key_builder("{ctx.full_name}:uid={uid}")
    recorded: list[str] = []

    def rkb(ctx: Any, *args: Any, **kwargs: Any) -> str:
        s = kb(ctx, *args, **kwargs)
        recorded.append(s)
        return s

    @cached(cache=cache, ttl=60, key_builder=rkb)
    def fetch_user(*, uid: int) -> dict[str, int]:
        return {"id": uid}

    out = fetch_user(uid=7)
    assert out["id"] == 7
    expected_key = recorded[0]
    assert cache.exists(expected_key)


def test_template_key_builder_instance_method_with_attr() -> None:
    cache = InMemoryCache()
    kb = template_key_builder("{ctx.full_name}:{0.tenant}:{1}")
    recorded: list[str] = []

    def rkb(ctx: Any, *args: Any, **kwargs: Any) -> str:
        s = kb(ctx, *args, **kwargs)
        recorded.append(s)
        return s

    class Svc:
        def __init__(self, tenant: str) -> None:
            self.tenant = tenant

        @cached(cache=cache, ttl=60, key_builder=rkb)
        def compute(self, x: int) -> int:  # pylint: disable=unused-argument
            return x * 2

    svc = Svc("t1")
    assert svc.compute(9) == 18
    expected_key = recorded[0]
    assert cache.exists(expected_key)
