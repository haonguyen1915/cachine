from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional, Protocol, TypedDict, TypeVar, runtime_checkable

CacheKey = str
TTL = Optional["TTLValue"]


@dataclass(frozen=True)
class TTLValue:
    """Explicit TTL value wrapper for typing.

    Either ``seconds`` or ``delta`` may be provided to indicate a TTL.

    Args:
        seconds (int | None): TTL in seconds.
        delta (datetime.timedelta | None): TTL as a timedelta.
    """

    seconds: Optional[int] = None
    delta: Optional[timedelta] = None


T = TypeVar("T")


class HealthStatus(TypedDict):
    healthy: bool
    latency_ms: float
    backend: str


@runtime_checkable
class Cache(Protocol):
    # Basic ops
    def get(self, key: CacheKey, default: Any = None, serializer: Any = None) -> Any: ...

    def set(self, key: CacheKey, value: Any, ttl: Optional[int | timedelta] = None, serializer: Any = None) -> None: ...

    def delete(self, key: CacheKey) -> bool: ...

    def exists(self, key: CacheKey) -> bool: ...

    def clear(self, dangerously_clear_all: bool = False) -> None: ...

    # Enrichment
    def get_or_set(
        self, key: CacheKey, factory: Callable[[], T], ttl: Optional[int | timedelta] = None, jitter: Optional[int] = None
    ) -> T: ...

    # TTL management
    def expire(self, key: CacheKey, ttl: int | timedelta) -> bool: ...

    def expire_at(self, key: CacheKey, when: datetime) -> bool: ...

    def touch(self, key: CacheKey, ttl: Optional[int | timedelta] = None) -> bool: ...

    def ttl(self, key: CacheKey) -> Optional[int]: ...

    def persist(self, key: CacheKey) -> bool: ...

    # Counters
    def incr(self, key: CacheKey, delta: int = 1, ttl_on_create: Optional[int | timedelta] = None) -> int: ...

    def decr(self, key: CacheKey, delta: int = 1) -> int: ...

    # Tags
    def add_tags(self, key: CacheKey, tags: list[str], ttl: Optional[int | timedelta] = None) -> None: ...

    def invalidate_tags(self, tags: list[str]) -> int: ...

    # Health / lifecycle
    def ping(self) -> HealthStatus: ...

    def ping_ok(self) -> bool: ...

    def close(self) -> None: ...

    # Stats / observability
    def get_stats(self) -> Optional[dict[str, Any]]: ...

    # Context manager
    def __enter__(self) -> Cache: ...

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None: ...


@runtime_checkable
class AsyncCache(Protocol):
    # Basic ops
    async def get(self, key: CacheKey, default: Any = None, *, serializer: Any = None) -> Any: ...

    async def set(self, key: CacheKey, value: Any, *, ttl: Optional[int | timedelta] = None, serializer: Any = None) -> None: ...

    async def delete(self, key: CacheKey) -> bool: ...

    async def exists(self, key: CacheKey) -> bool: ...

    async def clear(self, *, dangerously_clear_all: bool = False) -> None: ...

    # Enrichment
    async def get_or_set(
        self,
        key: CacheKey,
        factory: Callable[[], Awaitable[T]] | Callable[[], T],
        *,
        ttl: Optional[int | timedelta] = None,
        jitter: Optional[int] = None,
    ) -> T: ...

    # TTL management
    async def expire(self, key: CacheKey, *, ttl: int | timedelta) -> bool: ...

    async def expire_at(self, key: CacheKey, when: datetime) -> bool: ...

    async def touch(self, key: CacheKey, *, ttl: Optional[int | timedelta] = None) -> bool: ...

    async def ttl(self, key: CacheKey) -> Optional[int]: ...

    async def persist(self, key: CacheKey) -> bool: ...

    # Counters
    async def incr(self, key: CacheKey, *, delta: int = 1, ttl_on_create: Optional[int | timedelta] = None) -> int: ...

    async def decr(self, key: CacheKey, *, delta: int = 1) -> int: ...

    # Tags
    async def add_tags(self, key: CacheKey, tags: list[str], ttl: Optional[int | timedelta] = None) -> None: ...

    async def invalidate_tags(self, tags: list[str]) -> int: ...

    # Health / lifecycle
    async def ping(self) -> HealthStatus: ...

    async def ping_ok(self) -> bool: ...

    async def close(self) -> None: ...

    # Stats / observability
    def get_stats(self) -> Optional[dict[str, Any]]: ...

    # Async context manager
    async def __aenter__(self) -> AsyncCache: ...

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None: ...


# Helpful alias for code that accepts either sync or async cache types
CacheLike = Cache | AsyncCache

__all__ = [
    "Cache",
    "AsyncCache",
    "CacheLike",
    "CacheKey",
    "TTL",
    "TTLValue",
    "HealthStatus",
]
