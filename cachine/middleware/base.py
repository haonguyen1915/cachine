from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional

from cachine.core.types import AsyncCache, Cache, HealthStatus

from ..core.types import CacheLike


class BaseMiddleware:
    """Base middleware that forwards attribute access to the wrapped cache.

    Args:
        cache (Any): Wrapped cache instance.
    """

    def __init__(self, cache: CacheLike) -> None:
        self._cache = cache

    def __getattr__(self, item: str) -> Any:  # delegate to underlying cache
        """Delegate attribute access to the wrapped cache.

        Args:
            item (str): Attribute name.

        Returns:
            Any: Attribute from the underlying cache.
        """
        return getattr(self._cache, item)


class SyncCacheMiddleware(BaseMiddleware):
    """Typed delegating middleware for sync caches.

    Implements the Cache protocol by forwarding calls to the wrapped cache.
    Subclass this instead of BaseMiddleware when you want static type safety.
    """

    _cache: Cache

    # Basic ops
    def get(self, key: str, default: Any = None, *, serializer: Any = None) -> Any:
        return self._cache.get(key, default=default, serializer=serializer)

    def set(self, key: str, value: Any, *, ttl: Optional[int | timedelta] = None, serializer: Any = None) -> None:
        return self._cache.set(key, value, ttl=ttl, serializer=serializer)

    def delete(self, key: str) -> bool:
        return self._cache.delete(key)

    def exists(self, key: str) -> bool:
        return self._cache.exists(key)

    def clear(self, *, dangerously_clear_all: bool = False) -> None:
        return self._cache.clear(dangerously_clear_all=dangerously_clear_all)

    # Enrichment
    def get_or_set(self, key: str, factory: Any, *, ttl: Optional[int | timedelta] = None, jitter: Optional[int] = None) -> Any:
        return self._cache.get_or_set(key, factory, ttl=ttl, jitter=jitter)

    # TTL management
    def expire(self, key: str, *, ttl: int | timedelta) -> bool:
        return self._cache.expire(key, ttl=ttl)

    def expire_at(self, key: str, when: datetime) -> bool:
        return self._cache.expire_at(key, when)

    def touch(self, key: str, *, ttl: Optional[int | timedelta] = None) -> bool:
        return self._cache.touch(key, ttl=ttl)

    def ttl(self, key: str) -> Optional[int]:
        return self._cache.ttl(key)

    def persist(self, key: str) -> bool:
        return self._cache.persist(key)

    # Counters
    def incr(self, key: str, *, delta: int = 1, ttl_on_create: Optional[int | timedelta] = None) -> int:
        return self._cache.incr(key, delta=delta, ttl_on_create=ttl_on_create)

    def decr(self, key: str, *, delta: int = 1) -> int:
        return self._cache.decr(key, delta=delta)

    # Tags
    def add_tags(self, key: str, tags: list[str], ttl: Optional[int | timedelta] = None) -> None:
        add_tags_fn = getattr(self._cache, "add_tags", None)
        if add_tags_fn is not None:
            return add_tags_fn(key, tags, ttl=ttl)

    def invalidate_tags(self, tags: list[str]) -> int:
        inv = getattr(self._cache, "invalidate_tags", None)
        return int(inv(tags)) if inv is not None else 0

    # Health / lifecycle
    def ping(self) -> HealthStatus:
        return self._cache.ping()

    def ping_ok(self) -> bool:
        return self._cache.ping_ok()

    def close(self) -> None:
        return self._cache.close()

    # Stats / observability
    def get_stats(self) -> Optional[dict[str, Any]]:
        return self._cache.get_stats()

    # Context manager
    def __enter__(self) -> Cache:
        return self._cache.__enter__()

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return self._cache.__exit__(exc_type, exc, tb)


class AsyncCacheMiddleware(BaseMiddleware):
    """Typed delegating middleware for async caches.

    Implements the AsyncCache protocol by forwarding calls to the wrapped cache.
    Subclass this instead of BaseMiddleware when you want static type safety.
    """

    _cache: AsyncCache

    # Basic ops
    async def get(self, key: str, default: Any = None, *, serializer: Any = None) -> Any:
        return await self._cache.get(key, default=default, serializer=serializer)

    async def set(self, key: str, value: Any, *, ttl: Optional[int | timedelta] = None, serializer: Any = None) -> None:
        return await self._cache.set(key, value, ttl=ttl, serializer=serializer)

    async def delete(self, key: str) -> bool:
        return await self._cache.delete(key)

    async def exists(self, key: str) -> bool:
        return await self._cache.exists(key)

    async def clear(self, *, dangerously_clear_all: bool = False) -> None:
        return await self._cache.clear(dangerously_clear_all=dangerously_clear_all)

    # Enrichment
    async def get_or_set(
        self,
        key: str,
        factory: Any,
        *,
        ttl: Optional[int | timedelta] = None,
        jitter: Optional[int] = None,
    ) -> Any:
        return await self._cache.get_or_set(key, factory, ttl=ttl, jitter=jitter)

    # TTL management
    async def expire(self, key: str, *, ttl: int | timedelta) -> bool:
        return await self._cache.expire(key, ttl=ttl)

    async def expire_at(self, key: str, when: datetime) -> bool:
        return await self._cache.expire_at(key, when)

    async def touch(self, key: str, *, ttl: Optional[int | timedelta] = None) -> bool:
        return await self._cache.touch(key, ttl=ttl)

    async def ttl(self, key: str) -> Optional[int]:
        return await self._cache.ttl(key)

    async def persist(self, key: str) -> bool:
        return await self._cache.persist(key)

    # Counters
    async def incr(self, key: str, *, delta: int = 1, ttl_on_create: Optional[int | timedelta] = None) -> int:
        return await self._cache.incr(key, delta=delta, ttl_on_create=ttl_on_create)

    async def decr(self, key: str, *, delta: int = 1) -> int:
        return await self._cache.decr(key, delta=delta)

    # Tags
    async def add_tags(self, key: str, tags: list[str], ttl: Optional[int | timedelta] = None) -> None:
        import inspect

        add_tags_fn = getattr(self._cache, "add_tags", None)
        if add_tags_fn is not None:
            maybe = add_tags_fn(key, tags, ttl=ttl)
            if inspect.isawaitable(maybe):
                await maybe

    async def invalidate_tags(self, tags: list[str]) -> int:
        inv = getattr(self._cache, "invalidate_tags", None)
        if inv is None:
            return 0
        res = inv(tags)
        try:
            import inspect

            if inspect.isawaitable(res):
                return int(await res)
        except Exception:
            pass
        return int(res)

    # Health / lifecycle
    async def ping(self) -> HealthStatus:
        return await self._cache.ping()

    async def ping_ok(self) -> bool:
        return await self._cache.ping_ok()

    async def close(self) -> None:
        return await self._cache.close()

    # Stats / observability
    def get_stats(self) -> Optional[dict[str, Any]]:
        return self._cache.get_stats()

    # Async context manager
    async def __aenter__(self) -> AsyncCache:
        return await self._cache.__aenter__()

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return await self._cache.__aexit__(exc_type, exc, tb)
