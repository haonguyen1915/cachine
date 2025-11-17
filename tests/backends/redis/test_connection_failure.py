# from __future__ import annotations
#
# import pytest
#
#
# class FlakyClient:
#     """Minimal sync Redis client stub that can fail after being toggled.
#
#     When ``fail`` is True, all operations raise ``RuntimeError`` to simulate a
#     dropped/failed Redis connection.
#     """
#
#     def __init__(self) -> None:
#         self.store: dict[str, object] = {}
#         self.fail = False
#
#     # ---- Basic ops ----
#     def set(self, name: str, value: object, *, ex: int | None = None, px: int | None = None) -> bool:  # noqa: ARG002
#         if self.fail:
#             raise RuntimeError("connection lost")
#         self.store[name] = value
#         return True
#
#     def get(self, name: str) -> object | None:
#         if self.fail:
#             raise RuntimeError("connection lost")
#         return self.store.get(name)
#
#     def delete(self, name: str) -> int:
#         if self.fail:
#             raise RuntimeError("connection lost")
#         return 1 if self.store.pop(name, None) is not None else 0
#
#     def exists(self, name: str) -> int:
#         if self.fail:
#             raise RuntimeError("connection lost")
#         return 1 if name in self.store else 0
#
#     # ---- TTL / counters (minimal stubs) ----
#     def ttl(self, name: str) -> int:  # noqa: ARG002
#         if self.fail:
#             raise RuntimeError("connection lost")
#         return -1
#
#     def expire(self, name: str, seconds: int) -> int:  # noqa: ARG002
#         if self.fail:
#             raise RuntimeError("connection lost")
#         return 1
#
#     def expireat(self, name: str, timestamp: int) -> int:  # noqa: ARG002
#         if self.fail:
#             raise RuntimeError("connection lost")
#         return 1
#
#     def pexpire(self, name: str, ms: int) -> int:  # noqa: ARG002
#         if self.fail:
#             raise RuntimeError("connection lost")
#         return 1
#
#     def persist(self, name: str) -> int:  # noqa: ARG002
#         if self.fail:
#             raise RuntimeError("connection lost")
#         return 1
#
#     def incrby(self, name: str, delta: int) -> int:  # noqa: ARG002
#         if self.fail:
#             raise RuntimeError("connection lost")
#         current: int = int(self.store.get(name, 0))
#         val: int = current + delta
#         self.store[name] = val
#         return val
#
#     # ---- Scanning / bulk ----
#     def scan_iter(self, match: str, count: int | None = None) -> object:  # noqa: ARG002
#         if self.fail:
#             raise RuntimeError("connection lost")
#         return iter([])
#
#     def delete_many(self, *names: str) -> int:
#         if self.fail:
#             raise RuntimeError("connection lost")
#         removed = 0
#         for n in names:
#             removed += 1 if self.store.pop(n, None) is not None else 0
#         return removed
#
#     def flushdb(self) -> None:
#         if self.fail:
#             raise RuntimeError("connection lost")
#         self.store.clear()
#
#     # ---- Pub/Sub / misc ----
#     def publish(self, channel: str, data: str) -> int:  # noqa: ARG002
#         if self.fail:
#             raise RuntimeError("connection lost")
#         return 0
#
#     def pubsub(self) -> object:  # pragma: no cover - unused in these tests
#         if self.fail:
#             raise RuntimeError("connection lost")
#         return object()
#
#     def touch(self, name: str) -> int:  # noqa: ARG002
#         if self.fail:
#             raise RuntimeError("connection lost")
#         return 1
#
#     def sadd(self, name: str, *values: object) -> int:  # noqa: ARG002
#         if self.fail:
#             raise RuntimeError("connection lost")
#         return len(values)
#
#     def smembers(self, name: str) -> set:  # type: ignore[valid-type]
#         if self.fail:
#             raise RuntimeError("connection lost")
#         return set()
#
#     def ping(self) -> bool:
#         return not self.fail
#
#     def close(self) -> None:  # pragma: no cover - nothing to close in stub
#         return None
#
#
# def test_sync_redis_connection_loss_raises_on_ops_and_clear_is_safe() -> None:
#     """Simulate a sudden connection loss in RedisCache via a flaky client.
#
#     - First, operations succeed.
#     - Then, after toggling failure, data operations raise.
#     - Maintenance operations like clear(dangerously_clear_all=True) do not raise
#       because the implementation swallows backend errors.
#     """
#     from cachine.backends.redis.sync import RedisCache
#
#     client = FlakyClient()
#     cache = RedisCache(namespace="ut", client=client)
#
#     # Before failure: works
#     cache.set("k", b"v")
#     assert cache.get("k") == b"v"
#
#     # Simulate sudden outage
#     client.fail = True
#
#     with pytest.raises(RuntimeError):
#         cache.get("k")
#
#     # clear(dangerously_clear_all=True) swallows backend errors; should not raise
#     cache.clear(dangerously_clear_all=True)
#
#
# # ----- Async variant (skipped if pytest-asyncio is unavailable) -----
# try:  # pragma: no cover - import guard for optional dependency
#     import pytest_asyncio as _pytest_asyncio  # noqa: F401
#     HAS_ASYNC_TESTS = True
# except Exception:  # pragma: no cover - optional
#     HAS_ASYNC_TESTS = False
#
#
# class AsyncFlakyClient:
#     """Minimal async Redis client stub that can fail after being toggled."""
#
#     def __init__(self) -> None:
#         self.store: dict[str, object] = {}
#         self.fail = False
#
#     # ---- Basic ops ----
#     async def set(self, name: str, value: object, *, ex: int | None = None, px: int | None = None) -> bool:  # noqa: ARG002
#         if self.fail:
#             raise RuntimeError("connection lost")
#         self.store[name] = value
#         return True
#
#     async def get(self, name: str) -> object | None:
#         if self.fail:
#             raise RuntimeError("connection lost")
#         return self.store.get(name)
#
#     async def delete(self, name: str) -> int:
#         if self.fail:
#             raise RuntimeError("connection lost")
#         return 1 if self.store.pop(name, None) is not None else 0
#
#     async def exists(self, name: str) -> int:
#         if self.fail:
#             raise RuntimeError("connection lost")
#         return 1 if name in self.store else 0
#
#     # ---- TTL / counters (minimal stubs) ----
#     async def ttl(self, name: str) -> int:  # noqa: ARG002
#         if self.fail:
#             raise RuntimeError("connection lost")
#         return -1
#
#     async def expire(self, name: str, seconds: int) -> int:  # noqa: ARG002
#         if self.fail:
#             raise RuntimeError("connection lost")
#         return 1
#
#     async def expireat(self, name: str, timestamp: int) -> int:  # noqa: ARG002
#         if self.fail:
#             raise RuntimeError("connection lost")
#         return 1
#
#     async def pexpire(self, name: str, ms: int) -> int:  # noqa: ARG002
#         if self.fail:
#             raise RuntimeError("connection lost")
#         return 1
#
#     async def persist(self, name: str) -> int:  # noqa: ARG002
#         if self.fail:
#             raise RuntimeError("connection lost")
#         return 1
#
#     async def incrby(self, name: str, delta: int) -> int:  # noqa: ARG002
#         if self.fail:
#             raise RuntimeError("connection lost")
#         current: int = int(self.store.get(name, 0))
#         val: int = current + delta
#         self.store[name] = val
#         return val
#
#     async def eval(self, script: str, numkeys: int, *keys_and_args: object) -> None:  # noqa: ARG002
#         if self.fail:
#             raise RuntimeError("connection lost")
#         return None
#
#     # ---- Scanning / bulk ----
#     async def scan_iter(self, match: str) -> object:  # noqa: ARG002
#         if self.fail:
#             raise RuntimeError("connection lost")
#
#         async def _gen() -> object:  # pragma: no cover - not used in this test
#             for k in list(self.store.keys()):
#                 yield k
#         return _gen()
#
#     async def delete_many(self, *names: str) -> int:
#         if self.fail:
#             raise RuntimeError("connection lost")
#         removed = 0
#         for n in names:
#             removed += 1 if self.store.pop(n, None) is not None else 0
#         return removed
#
#     async def flushdb(self) -> None:
#         if self.fail:
#             raise RuntimeError("connection lost")
#         self.store.clear()
#
#     # ---- Pub/Sub / misc ----
#     async def publish(self, channel: str, data: str) -> int:  # noqa: ARG002
#         if self.fail:
#             raise RuntimeError("connection lost")
#         return 0
#
#     def pubsub(self) -> object:  # pragma: no cover - unused in these tests
#         if self.fail:
#             raise RuntimeError("connection lost")
#         return object()
#
#     async def touch(self, name: str) -> int:  # noqa: ARG002
#         if self.fail:
#             raise RuntimeError("connection lost")
#         return 1
#
#     async def sadd(self, name: str, *values: object) -> int:  # noqa: ARG002
#         if self.fail:
#             raise RuntimeError("connection lost")
#         return len(values)
#
#     async def smembers(self, name: str) -> set:  # type: ignore[valid-type]
#         if self.fail:
#             raise RuntimeError("connection lost")
#         return set()
#
#     async def ping(self) -> bool:
#         return not self.fail
#
#     async def close(self) -> None:  # pragma: no cover - nothing to close in stub
#         return None
#
#
# @pytest.mark.skipif(not HAS_ASYNC_TESTS, reason="pytest-asyncio not installed")
# @pytest.mark.asyncio
# async def test_async_redis_connection_loss_raises_on_ops_and_ping_reports_unhealthy() -> None:
#     from cachine.backends.redis.async_ import AsyncRedisCache
#
#     client = AsyncFlakyClient()
#     cache = AsyncRedisCache(namespace="ut", client=client)
#
#     # Before failure: works
#     await cache.set("k", b"v")
#     assert await cache.get("k") == b"v"
#
#     # Simulate sudden outage
#     client.fail = True
#
#     with pytest.raises(RuntimeError):
#         await cache.get("k")
#
#     # Async ping() actually checks connectivity and should report unhealthy
#     health = await cache.ping()
#     assert health.get("healthy") is False
#
#     # clear(dangerously_clear_all=True) should not raise despite backend failure
#     await cache.clear(dangerously_clear_all=True)
#
#
# def test_sync_fail_open_allows_function_to_run_without_cache() -> None:
#     """Verify fail-open middleware makes decorator and cache calls resilient.
#
#     When the backend fails, cached function still executes and returns a value,
#     and subsequent calls work once the backend is healthy again.
#     """
#     from cachine.backends.redis.sync import RedisCache
#     from cachine.decorators.cached import cached
#     from cachine.middleware.fail_open import FailOpenMiddleware
#
#     client = FlakyClient()
#     base = RedisCache(namespace="ut", client=client)
#     cache = FailOpenMiddleware(base)
#
#     calls = {"n": 0}
#
#     @cached(cache=cache, ttl=60)
#     def compute(x: int) -> int:
#         calls["n"] += 1
#         return x * 2
#
#     # Simulate outage: get/set would raise without middleware
#     client.fail = True
#     assert compute(3) == 6  # executes function
#     assert calls["n"] == 1
#
#     # Still failing -> no cache, function runs again
#     assert compute(3) == 6
#     assert calls["n"] == 2
#
#     # Recovery: cache becomes effective again
#     client.fail = False
#     assert compute(3) == 6  # miss -> store
#     assert calls["n"] == 3
#     assert compute(3) == 6  # hit
#     assert calls["n"] == 3
#
#
# @pytest.mark.skipif(not HAS_ASYNC_TESTS, reason="pytest-asyncio not installed")
# @pytest.mark.asyncio
# async def test_async_fail_open_allows_function_to_run_without_cache() -> None:
#     from cachine.backends.redis.async_ import AsyncRedisCache
#     from cachine.decorators.cached import cached
#     from cachine.middleware.fail_open import AsyncFailOpenMiddleware
#
#     client = AsyncFlakyClient()
#     base = AsyncRedisCache(namespace="ut", client=client)
#     cache = AsyncFailOpenMiddleware(base)
#
#     calls = {"n": 0}
#
#     @cached(cache=cache, ttl=60)
#     async def compute(x: int) -> int:
#         calls["n"] += 1
#         return x * 2
#
#     # Simulate outage
#     client.fail = True
#     assert await compute(3) == 6
#     assert calls["n"] == 1
#
#     # Still failing -> recompute
#     assert await compute(3) == 6
#     assert calls["n"] == 2
#
#     # Recovery
#     client.fail = False
#     assert await compute(3) == 6  # miss -> store
#     assert calls["n"] == 3
#     assert await compute(3) == 6  # hit
#     assert calls["n"] == 3
