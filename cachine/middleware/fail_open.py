from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional

from ..core.types import AsyncCache, HealthStatus
from ..core.types import Cache as SyncCache
from .base import BaseMiddleware


class FailOpenMiddleware(BaseMiddleware):
    """Fail-open wrapper for sync caches.

    Swallows backend connection errors so application logic continues without
    cache. Read operations return misses; write operations become no-ops.

    Notes:
        - ``get`` returns the provided ``default`` if the underlying cache fails.
        - ``set`` ignores errors.
        - Mutators return a safe fallback value on failure (e.g., ``False`` or ``0``).
        - ``incr``/``decr`` maintain an in-process ephemeral counter as a best-effort
          fallback so code relying on counters can continue operating.
    """

    def __init__(self, cache: SyncCache) -> None:
        super().__init__(cache)
        self._local_counters: dict[str, int] = {}

    # ---- Basic ops ----
    def get(self, key: str, default: Any = None, *, serializer: Any = None) -> Any:  # noqa: D401
        try:
            return self._cache.get(key, default=default, serializer=serializer)
        except Exception:
            return default

    def set(self, key: str, value: Any, *, ttl: Optional[int | timedelta] = None, serializer: Any = None) -> None:  # noqa: D401
        try:
            self._cache.set(key, value, ttl=ttl, serializer=serializer)
        except Exception:
            return None

    def delete(self, key: str) -> bool:
        try:
            return bool(self._cache.delete(key))
        except Exception:
            return False

    def exists(self, key: str) -> bool:
        try:
            return bool(self._cache.exists(key))
        except Exception:
            return False

    # ---- TTL management ----
    def expire(self, key: str, *, ttl: int | timedelta) -> bool:
        try:
            return bool(self._cache.expire(key, ttl=ttl))
        except Exception:
            return False

    def expire_at(self, key: str, when: datetime) -> bool:
        try:
            return bool(self._cache.expire_at(key, when))
        except Exception:
            return False

    def touch(self, key: str, *, ttl: Optional[int | timedelta] = None) -> bool:
        try:
            return bool(self._cache.touch(key, ttl=ttl))
        except Exception:
            return False

    def ttl(self, key: str) -> Optional[int]:
        try:
            return self._cache.ttl(key)
        except Exception:
            return None

    def persist(self, key: str) -> bool:
        try:
            return bool(self._cache.persist(key))
        except Exception:
            return False

    # ---- Counters ----
    def incr(self, key: str, *, delta: int = 1, ttl_on_create: Optional[int | timedelta] = None) -> int:  # noqa: ARG002
        try:
            return int(self._cache.incr(key, delta=delta, ttl_on_create=ttl_on_create))
        except Exception:
            # Fallback to in-process counter
            ns_key = key
            self._local_counters[ns_key] = int(self._local_counters.get(ns_key, 0)) + int(delta)
            return self._local_counters[ns_key]

    def decr(self, key: str, *, delta: int = 1) -> int:
        try:
            return int(self._cache.decr(key, delta=delta))
        except Exception:
            ns_key = key
            self._local_counters[ns_key] = int(self._local_counters.get(ns_key, 0)) - int(delta)
            return self._local_counters[ns_key]

    # ---- Tags / maintenance ----
    def add_tags(self, key: str, tags: list[str]) -> None:
        try:
            self._cache.add_tags(key, tags)
        except Exception:
            return None

    def invalidate_tags(self, tags: list[str]) -> int:
        try:
            return int(self._cache.invalidate_tags(tags))
        except Exception:
            return 0

    def clear(self, *, dangerously_clear_all: bool = False) -> None:
        try:
            self._cache.clear(dangerously_clear_all=dangerously_clear_all)
        except Exception:
            return None

    # ---- Health ----
    def ping(self) -> HealthStatus:  # type: ignore[override]
        try:
            return self._cache.ping()
        except Exception:
            return {"healthy": False, "latency_ms": 0.0, "backend": "fail-open"}

    def ping_ok(self) -> bool:  # type: ignore[override]
        try:
            return bool(self._cache.ping_ok())
        except Exception:
            return False


class AsyncFailOpenMiddleware(BaseMiddleware):
    """Fail-open wrapper for async caches.

    Mirrors ``FailOpenMiddleware`` but with async methods.
    """

    def __init__(self, cache: AsyncCache) -> None:
        super().__init__(cache)
        self._local_counters: dict[str, int] = {}

    # ---- Basic ops ----
    async def get(self, key: str, default: Any = None, *, serializer: Any = None) -> Any:  # noqa: D401
        try:
            return await self._cache.get(key, default=default, serializer=serializer)
        except Exception:
            return default

    async def set(self, key: str, value: Any, *, ttl: Optional[int | timedelta] = None, serializer: Any = None) -> None:  # noqa: D401
        try:
            await self._cache.set(key, value, ttl=ttl, serializer=serializer)
        except Exception:
            return None

    async def delete(self, key: str) -> bool:
        try:
            return bool(await self._cache.delete(key))
        except Exception:
            return False

    async def exists(self, key: str) -> bool:
        try:
            return bool(await self._cache.exists(key))
        except Exception:
            return False

    # ---- TTL management ----
    async def expire(self, key: str, *, ttl: int | timedelta) -> bool:
        try:
            return bool(await self._cache.expire(key, ttl=ttl))
        except Exception:
            return False

    async def expire_at(self, key: str, when: datetime) -> bool:
        try:
            return bool(await self._cache.expire_at(key, when))
        except Exception:
            return False

    async def touch(self, key: str, *, ttl: Optional[int | timedelta] = None) -> bool:
        try:
            return bool(await self._cache.touch(key, ttl=ttl))
        except Exception:
            return False

    async def ttl(self, key: str) -> Optional[int]:
        try:
            return await self._cache.ttl(key)
        except Exception:
            return None

    async def persist(self, key: str) -> bool:
        try:
            return bool(await self._cache.persist(key))
        except Exception:
            return False

    # ---- Counters ----
    async def incr(self, key: str, *, delta: int = 1, ttl_on_create: Optional[int | timedelta] = None) -> int:  # noqa: ARG002
        try:
            return int(await self._cache.incr(key, delta=delta, ttl_on_create=ttl_on_create))
        except Exception:
            ns_key = key
            self._local_counters[ns_key] = int(self._local_counters.get(ns_key, 0)) + int(delta)
            return self._local_counters[ns_key]

    async def decr(self, key: str, *, delta: int = 1) -> int:
        try:
            return int(await self._cache.decr(key, delta=delta))
        except Exception:
            ns_key = key
            self._local_counters[ns_key] = int(self._local_counters.get(ns_key, 0)) - int(delta)
            return self._local_counters[ns_key]

    # ---- Tags / maintenance ----
    async def add_tags(self, key: str, tags: list[str]) -> None:
        try:
            await self._cache.add_tags(key, tags)
        except Exception:
            return None

    async def invalidate_tags(self, tags: list[str]) -> int:
        try:
            return int(await self._cache.invalidate_tags(tags))
        except Exception:
            return 0

    async def clear(self, *, dangerously_clear_all: bool = False) -> None:
        try:
            await self._cache.clear(dangerously_clear_all=dangerously_clear_all)
        except Exception:
            return None

    # ---- Health ----
    async def ping(self) -> HealthStatus:  # type: ignore[override]
        try:
            return await self._cache.ping()
        except Exception:
            return {"healthy": False, "latency_ms": 0.0, "backend": "fail-open"}

    async def ping_ok(self) -> bool:  # type: ignore[override]
        try:
            return bool(await self._cache.ping_ok())
        except Exception:
            return False
