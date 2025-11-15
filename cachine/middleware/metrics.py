from __future__ import annotations

from .base import BaseMiddleware


class MetricsMiddleware(BaseMiddleware):
    def __init__(self, cache):
        super().__init__(cache)
        self._hits = 0
        self._misses = 0
        self._errors = 0

    def get_stats(self) -> dict:
        total = self._hits + self._misses
        hit_rate = (self._hits / total) if total else 0.0
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
            "errors": self._errors,
            "avg_latency_ms": 0.0,  # placeholder
        }

