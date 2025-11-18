from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from ..core.types import AsyncCache, HealthStatus
from ..core.types import Cache as SyncCache
from .base import BaseMiddleware

logger = logging.getLogger(__name__)


class FailOpenMiddleware(BaseMiddleware):
    """Fail-open wrapper for sync caches.

    Swallows backend connection errors so application logic continues without
    cache. Read operations return misses; write operations become no-ops.

    Args:
        cache (SyncCache): The underlying cache to wrap.
        log_errors (bool): Whether to log cache errors. Defaults to True.
        log_tracebacks (bool): Whether to include full tracebacks in error logs. Defaults to False.

    Notes:
        - ``get`` returns the provided ``default`` if the underlying cache fails.
        - ``set`` ignores errors.
        - Mutators return a safe fallback value on failure (e.g., ``False`` or ``0``).
        - ``incr``/``decr`` maintain an in-process ephemeral counter as a best-effort
          fallback so code relying on counters can continue operating.
    """

    def __init__(self, cache: SyncCache, *, log_errors: bool = True, log_tracebacks: bool = False) -> None:
        super().__init__(cache)
        self._cache: SyncCache = cache  # narrow type
        self._local_counters: dict[str, int] = {}
        self._log_errors = log_errors
        self._log_tracebacks = log_tracebacks

    def _log_error(self, message: str, *args: Any) -> None:
        """Log an error if logging is enabled."""
        if self._log_errors:
            logger.warning(message, *args, exc_info=self._log_tracebacks)

    # ---- Basic ops ----
    def get(self, key: str, default: Any = None, *, serializer: Any = None) -> Any:  # noqa: D401
        try:
            return self._cache.get(key, default=default, serializer=serializer)
        except Exception as e:
            self._log_error("Cache get failed for key '%s': %s: %s", key, type(e).__name__, str(e))
            return default

    def set(self, key: str, value: Any, *, ttl: Optional[int | timedelta] = None, serializer: Any = None) -> None:  # noqa: D401
        try:
            self._cache.set(key, value, ttl=ttl, serializer=serializer)
        except Exception as e:
            self._log_error("Cache set failed for key '%s': %s: %s", key, type(e).__name__, str(e))

    def delete(self, key: str) -> bool:
        try:
            return bool(self._cache.delete(key))
        except Exception as e:
            self._log_error("Cache delete failed for key '%s': %s: %s", key, type(e).__name__, str(e))
            return False

    def exists(self, key: str) -> bool:
        try:
            return bool(self._cache.exists(key))
        except Exception as e:
            self._log_error("Cache exists check failed for key '%s': %s: %s", key, type(e).__name__, str(e))
            return False

    # ---- TTL management ----
    def expire(self, key: str, *, ttl: int | timedelta) -> bool:
        try:
            return bool(self._cache.expire(key, ttl=ttl))
        except Exception as e:
            self._log_error("Cache expire failed for key '%s': %s: %s", key, type(e).__name__, str(e))
            return False

    def expire_at(self, key: str, when: datetime) -> bool:
        try:
            return bool(self._cache.expire_at(key, when))
        except Exception as e:
            self._log_error("Cache expire_at failed for key '%s': %s: %s", key, type(e).__name__, str(e))
            return False

    def touch(self, key: str, *, ttl: Optional[int | timedelta] = None) -> bool:
        try:
            return bool(self._cache.touch(key, ttl=ttl))
        except Exception as e:
            self._log_error("Cache touch failed for key '%s': %s: %s", key, type(e).__name__, str(e))
            return False

    def ttl(self, key: str) -> Optional[int]:
        try:
            return self._cache.ttl(key)
        except Exception as e:
            self._log_error("Cache ttl check failed for key '%s': %s: %s", key, type(e).__name__, str(e))
            return None

    def persist(self, key: str) -> bool:
        try:
            return bool(self._cache.persist(key))
        except Exception as e:
            self._log_error("Cache persist failed for key '%s': %s: %s", key, type(e).__name__, str(e))
            return False

    # ---- Counters ----
    def incr(self, key: str, *, delta: int = 1, ttl_on_create: Optional[int | timedelta] = None) -> int:  # noqa: ARG002
        try:
            return int(self._cache.incr(key, delta=delta, ttl_on_create=ttl_on_create))
        except Exception as e:
            self._log_error("Cache incr failed for key '%s', using local counter fallback: %s: %s", key, type(e).__name__, str(e))
            # Fallback to in-process counter
            ns_key = key
            self._local_counters[ns_key] = int(self._local_counters.get(ns_key, 0)) + int(delta)
            return self._local_counters[ns_key]

    def decr(self, key: str, *, delta: int = 1) -> int:
        try:
            return int(self._cache.decr(key, delta=delta))
        except Exception as e:
            self._log_error("Cache decr failed for key '%s', using local counter fallback: %s: %s", key, type(e).__name__, str(e))
            ns_key = key
            self._local_counters[ns_key] = int(self._local_counters.get(ns_key, 0)) - int(delta)
            return self._local_counters[ns_key]

    # ---- Tags / maintenance ----
    def add_tags(self, key: str, tags: list[str]) -> None:
        try:
            add_fn = getattr(self._cache, "add_tags", None)
            if add_fn is not None:
                add_fn(key, tags)
        except Exception as e:
            self._log_error("Cache add_tags failed for key '%s': %s: %s", key, type(e).__name__, str(e))

    def invalidate_tags(self, tags: list[str]) -> int:
        try:
            return int(self._cache.invalidate_tags(tags))
        except Exception as e:
            self._log_error("Cache invalidate_tags failed for tags %s: %s: %s", tags, type(e).__name__, str(e))
            return 0

    def clear(self, *, dangerously_clear_all: bool = False) -> None:
        try:
            self._cache.clear(dangerously_clear_all=dangerously_clear_all)
        except Exception as e:
            self._log_error("Cache clear failed: %s: %s", type(e).__name__, str(e))

    # ---- Health ----
    def ping(self) -> HealthStatus:
        try:
            return self._cache.ping()
        except Exception as e:
            self._log_error("Cache ping failed: %s: %s", type(e).__name__, str(e))
            return {"healthy": False, "latency_ms": 0.0, "backend": "fail-open"}

    def ping_ok(self) -> bool:
        try:
            return bool(self._cache.ping_ok())
        except Exception as e:
            self._log_error("Cache ping_ok failed: %s: %s", type(e).__name__, str(e))
            return False


class AsyncFailOpenMiddleware(BaseMiddleware):
    """Fail-open wrapper for async caches.

    Mirrors ``FailOpenMiddleware`` but with async methods.

    Args:
        cache (AsyncCache): The underlying async cache to wrap.
        log_errors (bool): Whether to log cache errors. Defaults to True.
        log_tracebacks (bool): Whether to include full tracebacks in error logs. Defaults to False.
    """

    def __init__(self, cache: AsyncCache, *, log_errors: bool = True, log_tracebacks: bool = False) -> None:
        super().__init__(cache)
        self._cache: AsyncCache = cache  # narrow type
        self._local_counters: dict[str, int] = {}
        self._log_errors = log_errors
        self._log_tracebacks = log_tracebacks

    def _log_error(self, message: str, *args: Any) -> None:
        """Log an error if logging is enabled."""
        if self._log_errors:
            logger.warning(message, *args, exc_info=self._log_tracebacks)

    # ---- Basic ops ----
    async def get(self, key: str, default: Any = None, *, serializer: Any = None) -> Any:  # noqa: D401
        try:
            return await self._cache.get(key, default=default, serializer=serializer)
        except Exception as e:
            self._log_error("Async cache get failed for key '%s': %s: %s", key, type(e).__name__, str(e))
            return default

    async def set(self, key: str, value: Any, *, ttl: Optional[int | timedelta] = None, serializer: Any = None) -> None:  # noqa: D401
        try:
            await self._cache.set(key, value, ttl=ttl, serializer=serializer)
        except Exception as e:
            self._log_error("Async cache set failed for key '%s': %s: %s", key, type(e).__name__, str(e))

    async def delete(self, key: str) -> bool:
        try:
            return bool(await self._cache.delete(key))
        except Exception as e:
            self._log_error("Async cache delete failed for key '%s': %s: %s", key, type(e).__name__, str(e))
            return False

    async def exists(self, key: str) -> bool:
        try:
            return bool(await self._cache.exists(key))
        except Exception as e:
            self._log_error("Async cache exists check failed for key '%s': %s: %s", key, type(e).__name__, str(e))
            return False

    # ---- TTL management ----
    async def expire(self, key: str, *, ttl: int | timedelta) -> bool:
        try:
            return bool(await self._cache.expire(key, ttl=ttl))
        except Exception as e:
            self._log_error("Async cache expire failed for key '%s': %s: %s", key, type(e).__name__, str(e))
            return False

    async def expire_at(self, key: str, when: datetime) -> bool:
        try:
            return bool(await self._cache.expire_at(key, when))
        except Exception as e:
            self._log_error("Async cache expire_at failed for key '%s': %s: %s", key, type(e).__name__, str(e))
            return False

    async def touch(self, key: str, *, ttl: Optional[int | timedelta] = None) -> bool:
        try:
            return bool(await self._cache.touch(key, ttl=ttl))
        except Exception as e:
            self._log_error("Async cache touch failed for key '%s': %s: %s", key, type(e).__name__, str(e))
            return False

    async def ttl(self, key: str) -> Optional[int]:
        try:
            return await self._cache.ttl(key)
        except Exception as e:
            self._log_error("Async cache ttl check failed for key '%s': %s: %s", key, type(e).__name__, str(e))
            return None

    async def persist(self, key: str) -> bool:
        try:
            return bool(await self._cache.persist(key))
        except Exception as e:
            self._log_error("Async cache persist failed for key '%s': %s: %s", key, type(e).__name__, str(e))
            return False

    # ---- Counters ----
    async def incr(self, key: str, *, delta: int = 1, ttl_on_create: Optional[int | timedelta] = None) -> int:  # noqa: ARG002
        try:
            return int(await self._cache.incr(key, delta=delta, ttl_on_create=ttl_on_create))
        except Exception as e:
            self._log_error("Async cache incr failed for key '%s', using local counter fallback: %s: %s", key, type(e).__name__, str(e))
            ns_key = key
            self._local_counters[ns_key] = int(self._local_counters.get(ns_key, 0)) + int(delta)
            return self._local_counters[ns_key]

    async def decr(self, key: str, *, delta: int = 1) -> int:
        try:
            return int(await self._cache.decr(key, delta=delta))
        except Exception as e:
            self._log_error("Async cache decr failed for key '%s', using local counter fallback: %s: %s", key, type(e).__name__, str(e))
            ns_key = key
            self._local_counters[ns_key] = int(self._local_counters.get(ns_key, 0)) - int(delta)
            return self._local_counters[ns_key]

    # ---- Tags / maintenance ----
    async def add_tags(self, key: str, tags: list[str]) -> None:
        try:
            add_fn = getattr(self._cache, "add_tags", None)
            if add_fn is not None:
                res = add_fn(key, tags)
                try:
                    import inspect as _inspect

                    if _inspect.isawaitable(res):
                        await res
                except Exception:
                    pass
        except Exception as e:
            self._log_error("Async cache add_tags failed for key '%s': %s: %s", key, type(e).__name__, str(e))

    async def invalidate_tags(self, tags: list[str]) -> int:
        try:
            return int(await self._cache.invalidate_tags(tags))
        except Exception as e:
            self._log_error("Async cache invalidate_tags failed for tags %s: %s: %s", tags, type(e).__name__, str(e))
            return 0

    async def clear(self, *, dangerously_clear_all: bool = False) -> None:
        try:
            await self._cache.clear(dangerously_clear_all=dangerously_clear_all)
        except Exception as e:
            self._log_error("Async cache clear failed: %s: %s", type(e).__name__, str(e))

    # ---- Health ----
    async def ping(self) -> HealthStatus:
        try:
            return await self._cache.ping()
        except Exception as e:
            self._log_error("Async cache ping failed: %s: %s", type(e).__name__, str(e))
            return {"healthy": False, "latency_ms": 0.0, "backend": "fail-open"}

    async def ping_ok(self) -> bool:
        try:
            return bool(await self._cache.ping_ok())
        except Exception as e:
            self._log_error("Async cache ping_ok failed: %s: %s", type(e).__name__, str(e))
            return False
