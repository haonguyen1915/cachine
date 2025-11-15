from cachine import cached


def test_key_builder_receives_context_redis(redis_sync_cache):
    cache = redis_sync_cache
    captured = {}

    def kb(ctx, a: int, b: int) -> str:  # ctx is KeyContext
        captured["module"] = getattr(ctx, "module", None)
        captured["qualname"] = getattr(ctx, "qualname", None)
        captured["full_name"] = getattr(ctx, "full_name", None)
        captured["version"] = getattr(ctx, "version", None)
        return f"sum:{a}:{b}:{ctx.qualname}"

    calls = {"n": 0}

    @cached(cache, ttl=60, key_builder=kb, version="rv1")
    def add(a: int, b: int) -> int:
        calls["n"] += 1
        return a + b

    assert add(1, 2) == 3
    assert add(1, 2) == 3
    assert calls["n"] == 1

    assert captured["version"] == "rv1"
    assert isinstance(captured["module"], str)
    assert isinstance(captured["qualname"], str) and "add" in captured["qualname"]
    assert isinstance(captured["full_name"], str) and captured["module"] in captured["full_name"]

