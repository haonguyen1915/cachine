from cachine import cached


def test_instance_method_caching_redis(redis_sync_cache):
    cache = redis_sync_cache

    class Service:
        def __init__(self, tenant: str) -> None:
            self.tenant = tenant
            self.calls = 0

        @cached(cache, ttl=60, key_builder=lambda self, a, b: f"{self.tenant}:{a}:{b}")
        def add(self, a: int, b: int) -> int:
            self.calls += 1
            return a + b

    s = Service("t1")
    assert s.add(1, 2) == 3
    assert s.add(1, 2) == 3
    assert s.calls == 1


def test_staticmethod_caching_redis(redis_sync_cache):
    cache = redis_sync_cache

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


def test_classmethod_caching_redis(redis_sync_cache):
    cache = redis_sync_cache

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


def test_instance_method_default_keybuilder_redis(redis_sync_cache):
    cache = redis_sync_cache

    class Service:
        def __init__(self) -> None:
            self.calls = 0

        @cached(cache, ttl=60)
        def add(self, a: int, b: int) -> int:
            self.calls += 1
            return a + b

    s1 = Service()
    s2 = Service()

    assert s1.add(1, 2) == 3
    assert s1.add(1, 2) == 3
    assert s1.calls == 1

    assert s2.add(1, 2) == 3
    assert s2.add(1, 2) == 3
    assert s2.calls == 1
