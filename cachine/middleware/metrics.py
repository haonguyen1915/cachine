from __future__ import annotations

import time
from typing import Any

from cachine.core.types import CacheLike
from cachine.middleware.base import AsyncCacheMiddleware, SyncCacheMiddleware

_SENTINEL = object()


class MetricsMiddleware(SyncCacheMiddleware):
    """Collect basic hit/miss/error/latency metrics around cache operations.

    Hits and misses are counted on ``get`` calls. A private sentinel is used
    when delegating so a caller-provided ``default`` is never confused with a
    cache hit.
    """

    def __init__(self, cache: CacheLike) -> None:
        super().__init__(cache)
        self._hits = 0
        self._misses = 0
        self._errors = 0
        self._latency_total_ms = 0.0
        self._latency_count = 0

    def get(self, key: str, default: Any = None) -> Any:
        start = time.perf_counter()
        try:
            value = self._cache.get(key, default=_SENTINEL)
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


class AsyncMetricsMiddleware(AsyncCacheMiddleware):
    """Async mirror of :class:`MetricsMiddleware`."""

    def __init__(self, cache: CacheLike) -> None:
        super().__init__(cache)
        self._hits = 0
        self._misses = 0
        self._errors = 0
        self._latency_total_ms = 0.0
        self._latency_count = 0

    async def get(self, key: str, default: Any = None) -> Any:
        start = time.perf_counter()
        try:
            value = await self._cache.get(key, default=_SENTINEL)
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
