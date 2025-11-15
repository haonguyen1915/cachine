from __future__ import annotations

import inspect
import time
from typing import Any

from cachine.middleware.base import BaseMiddleware

_SENTINEL = object()


class MetricsMiddleware(BaseMiddleware):
    """Collect basic hit/miss/error/latency metrics around cache operations.

    Notes:
    - Hits/misses are counted on `get` calls. Hits are when the underlying cache
      returns a non-sentinel value; misses when sentinel is returned. To avoid
      ambiguity with `default`, this middleware calls the wrapped cache with its
      own sentinel and then maps a miss back to the caller's provided `default`.
    - Latency is the average of measured `get` call durations in milliseconds.
    - Errors count any exceptions raised by wrapped methods; the exception is
      re-raised after incrementing the counter.
    """

    def __init__(self, cache: Any) -> None:
        super().__init__(cache)
        self._hits = 0
        self._misses = 0
        self._errors = 0
        self._latency_total_ms = 0.0
        self._latency_count = 0

    # ---- Instrumented methods ----
    def get(self, key: str, default: Any = None, *, serializer: Any = None) -> Any:  # sync path
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

    async def aget(self, key: str, default: Any = None, *, serializer: Any = None) -> Any:  # async convenience
        start = time.perf_counter()
        try:
            # If underlying cache has async get, await it; else fallback to sync
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
