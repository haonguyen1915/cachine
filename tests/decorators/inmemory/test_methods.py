from cachine import InMemoryCache
from cachine.decorators import cached
from cachine.decorators.cached import KeyContext


def test_instance_method_caching_inmemory() -> None:
    cache = InMemoryCache()

    class Service:
        def __init__(self, tenant: str) -> None:
            self.tenant = tenant
            self.calls = 0

        @cached(cache, ttl=60, key_builder=lambda ctx, self, a, b: f"{self.tenant}:{a}:{b}")
        def add(self, a: int, b: int) -> int:
            self.calls += 1
            return a + b

    s = Service("t1")
    assert s.add(1, 2) == 3
    assert s.add(1, 2) == 3
    assert s.calls == 1


def test_staticmethod_caching_inmemory() -> None:
    cache = InMemoryCache()

    class Util:
        calls = 0

        @staticmethod
        @cached(cache, ttl=60)
        def mul(a: int, b: int) -> int:
            Util.calls += 1
            return a * b

    assert Util.mul(2, 3) == 6
    assert Util.mul(2, 3) == 6
    assert Util.calls == 1


def test_classmethod_caching_inmemory() -> None:
    cache = InMemoryCache()

    class Counter:
        calls = 0

        @classmethod
        @cached(cache, ttl=60)
        def inc(cls, x: int) -> int:
            cls.calls += 1
            return x + 1

    assert Counter.inc(5) == 6
    assert Counter.inc(5) == 6
    assert Counter.calls == 1


def test_instance_method_default_keybuilder_inmemory() -> None:
    cache = InMemoryCache()

    class Service:
        def __init__(self) -> None:
            self.calls = 0

        # No key_builder provided: default key uses module.qualname + args (including self)
        @cached(cache, ttl=60)
        def add(self, a: int, b: int) -> int:
            self.calls += 1
            return a + b

    s1 = Service()
    s2 = Service()

    # Same instance should cache
    assert s1.add(1, 2) == 3
    assert s1.add(1, 2) == 3
    assert s1.calls == 1

    # Different instance (different self) should not hit s1's cache
    assert s2.add(1, 2) == 3
    assert s2.add(1, 2) == 3
    assert s2.calls == 1


def test_instance_method_keybuilder_with_context_inmemory() -> None:
    cache = InMemoryCache()
    captured = {}

    def kb(ctx: KeyContext, _self: "Service", a: int, b: int) -> str:
        # capture qualname/full_name and include tenant in key
        captured["qualname"] = getattr(ctx, "qualname", None)
        captured["full_name"] = getattr(ctx, "full_name", None)
        return f"{ctx.full_name}:{a}:{b}"

    class Service:
        def __init__(self, tenant: str) -> None:
            self.tenant = tenant
            self.calls = 0

        @cached(cache, ttl=60, key_builder=kb, version="v_ctx")
        def add(self, a: int, b: int) -> int:
            self.calls += 1
            return a + b

    s = Service("acme")
    assert s.add(1, 2) == 3
    assert s.add(1, 2) == 3
    assert s.calls == 1
    assert isinstance(captured.get("qualname"), str) and "add" in captured["qualname"]  # type: ignore[operator]
    assert isinstance(captured.get("full_name"), str)


def test_staticmethod_with_keybuilder_inmemory() -> None:
    cache = InMemoryCache()
    captured = {}

    def kb(ctx: KeyContext, a: int, b: int) -> str:
        # Static methods don't have self/cls, so just args
        captured["qualname"] = getattr(ctx, "qualname", None)
        captured["full_name"] = getattr(ctx, "full_name", None)
        return f"static:{ctx.qualname}:{a}*{b}"

    class Util:
        calls = 0

        @staticmethod
        @cached(cache, ttl=60, key_builder=kb)
        def mul(a: int, b: int) -> int:
            Util.calls += 1
            return a * b

    assert Util.mul(2, 3) == 6
    assert Util.mul(2, 3) == 6  # Should hit cache
    assert Util.calls == 1
    assert "mul" in captured.get("qualname", "")  # type: ignore[operator]
    assert isinstance(captured.get("full_name"), str)


def test_classmethod_with_keybuilder_inmemory() -> None:
    cache = InMemoryCache()
    captured = {}

    def kb(ctx: KeyContext, _cls: type, x: int) -> str:
        # Class methods receive the class as first argument
        captured["qualname"] = getattr(ctx, "qualname", None)
        captured["full_name"] = getattr(ctx, "full_name", None)
        captured["cls_name"] = _cls.__name__
        return f"cls:{ctx.qualname}:{_cls.__name__}:{x}"

    class Counter:
        calls = 0

        @classmethod
        @cached(cache, ttl=60, key_builder=kb)
        def inc(cls, x: int) -> int:
            cls.calls += 1
            return x + 1

    assert Counter.inc(5) == 6
    assert Counter.inc(5) == 6  # Should hit cache
    assert Counter.calls == 1
    assert "inc" in captured.get("qualname", "")  # type: ignore[operator]
    assert captured.get("cls_name") == "Counter"
