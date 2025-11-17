from cachine import InMemoryCache, cached
from cachine.decorators.cached import KeyContext


def test_key_builder_receives_context_inmemory() -> None:
    cache = InMemoryCache()
    captured = {}

    def kb(ctx: KeyContext, a: int, b: int) -> str:  # ctx is KeyContext
        # Capture fields provided by the decorator
        captured["module"] = getattr(ctx, "module", None)
        captured["qualname"] = getattr(ctx, "qualname", None)
        captured["full_name"] = getattr(ctx, "full_name", None)
        captured["version"] = getattr(ctx, "version", None)
        return f"sum:{a}:{b}:{ctx.qualname}"

    calls = {"n": 0}

    @cached(cache, ttl=60, key_builder=kb, version="v9")
    def add(a: int, b: int) -> int:
        calls["n"] += 1
        return a + b

    assert add(1, 2) == 3
    assert add(1, 2) == 3
    assert calls["n"] == 1

    # Validate context fields were supplied
    assert captured["version"] == "v9"
    assert isinstance(captured["module"], str) and captured["module"]
    assert isinstance(captured["qualname"], str) and "add" in captured["qualname"]
    assert isinstance(captured["full_name"], str) and captured["module"] in captured["full_name"]
