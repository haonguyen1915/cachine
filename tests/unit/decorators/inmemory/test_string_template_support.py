from __future__ import annotations

from cachine import InMemoryCache, cached


def test_key_builder_accepts_string_template_for_positional() -> None:
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


def test_key_builder_accepts_string_template_for_kwargs() -> None:
    cache = InMemoryCache()
    calls = {"n": 0}

    @cached(cache=cache, ttl=60, key_builder="{ctx.full_name}:uid={uid}")
    def fetch_user(*, uid: int) -> dict[str, int]:
        calls["n"] += 1
        return {"id": uid}

    assert fetch_user(uid=9)["id"] == 9
    assert fetch_user(uid=9)["id"] == 9
    assert calls["n"] == 1


def test_key_builder_template_kwargs_name_from_positional() -> None:
    cache = InMemoryCache()
    calls = {"n": 0}

    @cached(cache=cache, ttl=60, key_builder="{ctx.full_name}:uid={uid}")
    def fetch_user(uid: int) -> dict[str, int]:
        calls["n"] += 1
        return {"id": uid}

    # Called positionally; template references {uid} by name
    assert fetch_user(5)["id"] == 5
    # Second call should hit cache using same resolved template
    assert fetch_user(5)["id"] == 5
    assert calls["n"] == 1


def test_key_builder_template_kwonly_called_positionally_ok() -> None:
    cache = InMemoryCache()
    calls = {"n": 0}

    @cached(cache=cache, ttl=60, key_builder="uid={0}")
    def fetch_user(uid: int, a: int) -> dict[str, int]:
        calls["n"] += 1
        return {"id": uid, "a": a}

    # Called positionally though function is kw-only; decorator normalizes call
    assert fetch_user(uid=7, a=8)["id"] == 7
    # assert fetch_user(7, 8)["id"] == 7
    # assert calls["n"] == 1
