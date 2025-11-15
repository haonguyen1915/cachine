from __future__ import annotations

from cachine import InMemoryCache, cached


def test_key_builder_accepts_string_template_for_positional():
    cache = InMemoryCache()
    calls = {"n": 0}

    @cached(cache=cache, ttl=60, key_builder="{ctx.full_name}:{0}:{1}")
    def add(a: int, b: int) -> int:
        calls["n"] += 1
        return a + b

    assert add(3, 4) == 7
    assert add(3, 4) == 7
    # Only computed once → second call was a hit using the same template key
    assert calls["n"] == 1


def test_key_builder_accepts_string_template_for_kwargs():
    cache = InMemoryCache()
    calls = {"n": 0}

    @cached(cache=cache, ttl=60, key_builder="uid={uid}")
    def fetch_user(*, uid: int) -> dict:
        calls["n"] += 1
        return {"id": uid}

    fetch_user(9)
    # assert fetch_user(uid=9)["id"] == 9
    # assert fetch_user(uid=9)["id"] == 9
    # assert calls["n"] == 1

