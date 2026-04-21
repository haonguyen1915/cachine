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

    seconds: int | None = None
    delta: timedelta | None = None


T = TypeVar("T")


class HealthStatus(TypedDict):
    healthy: bool
    latency_ms: float
    backend: str


# ---------------------------------------------------------------------------
# Sync protocol hierarchy
# ---------------------------------------------------------------------------


@runtime_checkable
class MinimalCache(Protocol):
    """Minimum viable cache surface: basic get/set/delete/exists.

    Depend on this protocol when writing application-level code that only
    needs primitive cache operations. Advanced features (TTL management,
    counters, tags) remain available on concrete backends but are not
    required at type-check time.
    """

    def get(self, key: CacheKey, default: Any = None) -> Any: ...

    def set(self, key: CacheKey, value: Any, *, ttl: int | timedelta | None = None) -> None: ...

    def delete(self, key: CacheKey) -> bool: ...

    def exists(self, key: CacheKey) -> bool: ...

    def close(self) -> None: ...

    def __enter__(self) -> MinimalCache: ...

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None: ...


@runtime_checkable
class CounterCache(Protocol):
    """Mixin protocol for backends that support atomic counters."""

    def incr(self, key: CacheKey, *, delta: int = 1, ttl_if_new: int | timedelta | None = None) -> int: ...

    def decr(self, key: CacheKey, *, delta: int = 1) -> int: ...


@runtime_checkable
class TaggedCache(Protocol):
    """Mixin protocol for backends that support tag-based invalidation."""

    def add_tags(self, key: CacheKey, tags: list[str], *, ttl: int | timedelta | None = None) -> None: ...

    def invalidate_tags(self, tags: list[str]) -> int: ...


@runtime_checkable
class ObservableCache(Protocol):
    """Mixin protocol for health checks and stats."""

    def health(self) -> HealthStatus: ...

    def healthy(self) -> bool: ...

    def get_stats(self) -> dict[str, Any] | None: ...


@runtime_checkable
class Cache(Protocol):
    """Full sync cache protocol.

    Covers basic ops, TTL management, counters, tag invalidation, health
    checks, and context management. All keyword arguments (``ttl``,
    ``jitter``, ``delta``, ``ttl_if_new``) are keyword-only so sync and async
    call sites remain identical.
    """

    # Basic ops
    def get(self, key: CacheKey, default: Any = None) -> Any: ...

    def set(self, key: CacheKey, value: Any, *, ttl: int | timedelta | None = None) -> None: ...

    def delete(self, key: CacheKey) -> bool: ...

    def exists(self, key: CacheKey) -> bool: ...

    def clear(self, *, all: bool = False) -> None: ...

    # Enrichment
    def get_or_set(
        self,
        key: CacheKey,
        factory: Callable[[], T],
        *,
        ttl: int | timedelta | None = None,
        jitter: int | None = None,
    ) -> T: ...

    # TTL management
    def expire(self, key: CacheKey, *, ttl: int | timedelta) -> bool: ...

    def expire_at(self, key: CacheKey, when: datetime) -> bool: ...

    def touch(self, key: CacheKey, *, ttl: int | timedelta | None = None) -> bool: ...

    def ttl(self, key: CacheKey) -> int | None: ...

    def persist(self, key: CacheKey) -> bool: ...

    # Counters
    def incr(self, key: CacheKey, *, delta: int = 1, ttl_if_new: int | timedelta | None = None) -> int: ...

    def decr(self, key: CacheKey, *, delta: int = 1) -> int: ...

    # Tags
    def add_tags(self, key: CacheKey, tags: list[str], *, ttl: int | timedelta | None = None) -> None: ...

    def invalidate_tags(self, tags: list[str]) -> int: ...

    # Health / lifecycle
    def health(self) -> HealthStatus: ...

    def healthy(self) -> bool: ...

    def close(self) -> None: ...

    # Stats / observability
    def get_stats(self) -> dict[str, Any] | None: ...

    # Context manager
    def __enter__(self) -> Cache: ...

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None: ...


# ---------------------------------------------------------------------------
# Async protocol hierarchy (mirrors sync)
# ---------------------------------------------------------------------------


@runtime_checkable
class MinimalAsyncCache(Protocol):
    """Minimum viable async cache surface."""

    async def get(self, key: CacheKey, default: Any = None) -> Any: ...

    async def set(self, key: CacheKey, value: Any, *, ttl: int | timedelta | None = None) -> None: ...

    async def delete(self, key: CacheKey) -> bool: ...

    async def exists(self, key: CacheKey) -> bool: ...

    async def close(self) -> None: ...

    async def __aenter__(self) -> MinimalAsyncCache: ...

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None: ...


@runtime_checkable
class AsyncCounterCache(Protocol):
    """Async mixin protocol for atomic counters."""

    async def incr(self, key: CacheKey, *, delta: int = 1, ttl_if_new: int | timedelta | None = None) -> int: ...

    async def decr(self, key: CacheKey, *, delta: int = 1) -> int: ...


@runtime_checkable
class AsyncTaggedCache(Protocol):
    """Async mixin protocol for tag-based invalidation."""

    async def add_tags(self, key: CacheKey, tags: list[str], *, ttl: int | timedelta | None = None) -> None: ...

    async def invalidate_tags(self, tags: list[str]) -> int: ...


@runtime_checkable
class AsyncObservableCache(Protocol):
    """Async mixin protocol for health checks and stats."""

    async def health(self) -> HealthStatus: ...

    async def healthy(self) -> bool: ...

    def get_stats(self) -> dict[str, Any] | None: ...


@runtime_checkable
class AsyncCache(Protocol):
    """Full async cache protocol. Mirrors :class:`Cache`."""

    # Basic ops
    async def get(self, key: CacheKey, default: Any = None) -> Any: ...

    async def set(self, key: CacheKey, value: Any, *, ttl: int | timedelta | None = None) -> None: ...

    async def delete(self, key: CacheKey) -> bool: ...

    async def exists(self, key: CacheKey) -> bool: ...

    async def clear(self, *, all: bool = False) -> None: ...

    # Enrichment
    async def get_or_set(
        self,
        key: CacheKey,
        factory: Callable[[], Awaitable[T]] | Callable[[], T],
        *,
        ttl: int | timedelta | None = None,
        jitter: int | None = None,
    ) -> T: ...

    # TTL management
    async def expire(self, key: CacheKey, *, ttl: int | timedelta) -> bool: ...

    async def expire_at(self, key: CacheKey, when: datetime) -> bool: ...

    async def touch(self, key: CacheKey, *, ttl: int | timedelta | None = None) -> bool: ...

    async def ttl(self, key: CacheKey) -> int | None: ...

    async def persist(self, key: CacheKey) -> bool: ...

    # Counters
    async def incr(self, key: CacheKey, *, delta: int = 1, ttl_if_new: int | timedelta | None = None) -> int: ...

    async def decr(self, key: CacheKey, *, delta: int = 1) -> int: ...

    # Tags
    async def add_tags(self, key: CacheKey, tags: list[str], *, ttl: int | timedelta | None = None) -> None: ...

    async def invalidate_tags(self, tags: list[str]) -> int: ...

    # Health / lifecycle
    async def health(self) -> HealthStatus: ...

    async def healthy(self) -> bool: ...

    async def close(self) -> None: ...

    # Stats / observability
    def get_stats(self) -> dict[str, Any] | None: ...

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
    # Tiered protocols
    "MinimalCache",
    "MinimalAsyncCache",
    "CounterCache",
    "AsyncCounterCache",
    "TaggedCache",
    "AsyncTaggedCache",
    "ObservableCache",
    "AsyncObservableCache",
]
