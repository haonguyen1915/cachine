from __future__ import annotations

import inspect
import time
from typing import Any

from cachine.core.types import CacheLike
from cachine.middleware.base import AsyncCacheMiddleware, SyncCacheMiddleware

_SENTINEL = object()


class MetricsMiddleware(SyncCacheMiddleware):
    """Collect basic hit/miss/error/latency metrics around cache operations.

    Hits/misses are counted on ``get`` calls. To avoid ambiguity with a caller
    provided ``default``, the middleware uses its own sentinel when delegating to
    the underlying cache and then maps misses to the caller's default.

    Args:
        cache (Any): Wrapped cache instance.
    """

    def __init__(self, cache: CacheLike) -> None:
        super().__init__(cache)
        self._hits = 0
        self._misses = 0
        self._errors = 0
        self._latency_total_ms = 0.0
        self._latency_count = 0

    # ---- Instrumented methods ----
    def get(self, key: str, default: Any = None, *, serializer: Any = None) -> Any:  # sync path
        """Get a value while recording hit/miss and latency metrics.

        Args:
            key (str): Cache key.
            default (Any, optional): Value to return on miss.
            serializer (Any, optional): Optional serializer forwarded to the cache.

        Returns:
            Any: Cached value or ``default``.
        """
        start = time.perf_counter()
        try:
            value = self._cache.get(key, default=_SENTINEL, serializer=serializer)
        except Exception:  # pragma: no cover - error path
            self._errors += 1
            raise
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            self._latency_total_ms += elapsed_ms
            self._latency_count += 1

        if value is _SENTINEL:
            self._misses += 1
            return default
        self._hits += 1
        return value

    async def aget(self, key: str, default: Any = None, *, serializer: Any = None) -> Any:  # async compatibility helper
        """Deprecated: prefer AsyncMetricsMiddleware. Async-friendly get() for mixed stacks.

        If the underlying cache's get is async, await it; otherwise call sync get.
        Still records hits/misses and latency like sync get.
        """
        start = time.perf_counter()
        try:
            get_fn = self._cache.get
            value = (
                await get_fn(key, default=_SENTINEL, serializer=serializer)
                if inspect.iscoroutinefunction(get_fn)
                else get_fn(key, default=_SENTINEL, serializer=serializer)
            )
        except Exception:  # pragma: no cover - error path
            self._errors += 1
            raise
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            self._latency_total_ms += elapsed_ms
            self._latency_count += 1

        if value is _SENTINEL:
            self._misses += 1
            return default
        self._hits += 1
        return value

    # ---- Stats ----
    def get_stats(self) -> dict[str, Any]:
        """Return collected metrics.

        Returns:
            dict[str, Any]: ``{"hits": int, "misses": int, "hit_rate": float, "errors": int, "avg_latency_ms": float}``.
        """
        total = self._hits + self._misses
        hit_rate = (self._hits / total) if total else 0.0
        avg_latency = (self._latency_total_ms / self._latency_count) if self._latency_count else 0.0
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
            "errors": self._errors,
            "avg_latency_ms": avg_latency,
        }


class AsyncMetricsMiddleware(AsyncCacheMiddleware):
    """Async metrics middleware mirroring MetricsMiddleware for async caches.

    Instruments async ``get`` to record hit/miss, errors, and latency.
    """

    def __init__(self, cache: CacheLike) -> None:
        super().__init__(cache)
        self._hits = 0
        self._misses = 0
        self._errors = 0
        self._latency_total_ms = 0.0
        self._latency_count = 0

    async def get(self, key: str, default: Any = None, *, serializer: Any = None) -> Any:
        start = time.perf_counter()
        try:
            value = await self._cache.get(key, default=_SENTINEL, serializer=serializer)
        except Exception:  # pragma: no cover - error path
            self._errors += 1
            raise
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            self._latency_total_ms += elapsed_ms
            self._latency_count += 1

        if value is _SENTINEL:
            self._misses += 1
            return default
        self._hits += 1
        return value

    def get_stats(self) -> dict[str, Any]:
        total = self._hits + self._misses
        hit_rate = (self._hits / total) if total else 0.0
        avg_latency = (self._latency_total_ms / self._latency_count) if self._latency_count else 0.0
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
            "errors": self._errors,
            "avg_latency_ms": avg_latency,
        }
