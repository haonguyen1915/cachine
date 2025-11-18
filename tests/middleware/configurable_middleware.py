"""Example configurable middleware for testing builder pattern with configuration."""

from __future__ import annotations

from typing import Any

from cachine.core.types import AsyncCache, Cache
from cachine.middleware.base import AsyncCacheMiddleware, SyncCacheMiddleware


class ConfigurableMetricsMiddleware(SyncCacheMiddleware):
    """Example middleware that accepts configuration parameters.

    Supports factory pattern for use with builders:
        .add_middleware(ConfigurableMetricsMiddleware.create(namespace="app"))
    """

    def __init__(self, cache: Cache, namespace: str = "default", enabled: bool = True):
        super().__init__(cache)
        self.namespace = namespace
        self.enabled = enabled
        self._hits = 0
        self._misses = 0

    @classmethod
    def create(cls, namespace: str = "default", enabled: bool = True):
        """Factory method for configuring middleware before providing cache.

        Returns a callable that accepts a cache and returns configured middleware.
        """
        return lambda cache: cls(cache, namespace=namespace, enabled=enabled)

    def get(self, key: str, default: Any = None, **kwargs: Any) -> Any:
        result = self._cache.get(key, default=default, **kwargs)
        if self.enabled:
            if result is default:
                self._misses += 1
            else:
                self._hits += 1
        return result

    def get_stats(self) -> dict[str, Any]:
        return {
            "namespace": self.namespace,
            "enabled": self.enabled,
            "hits": self._hits,
            "misses": self._misses,
        }


class AsyncConfigurableMetricsMiddleware(AsyncCacheMiddleware):
    """Async version of ConfigurableMetricsMiddleware."""

    def __init__(self, cache: AsyncCache, namespace: str = "default", enabled: bool = True):
        super().__init__(cache)
        self.namespace = namespace
        self.enabled = enabled
        self._hits = 0
        self._misses = 0

    @classmethod
    def create(cls, namespace: str = "default", enabled: bool = True):
        """Factory method for configuring middleware before providing cache."""
        return lambda cache: cls(cache, namespace=namespace, enabled=enabled)

    async def get(self, key: str, default: Any = None, **kwargs: Any) -> Any:
        result = await self._cache.get(key, default=default, **kwargs)
        if self.enabled:
            if result is default:
                self._misses += 1
            else:
                self._hits += 1
        return result

    def get_stats(self) -> dict[str, Any]:
        return {
            "namespace": self.namespace,
            "enabled": self.enabled,
            "hits": self._hits,
            "misses": self._misses,
        }
