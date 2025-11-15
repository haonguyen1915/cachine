from __future__ import annotations

import os
from typing import Any, Literal

from .backends.inmemory.cache import InMemoryCache
from .backends.redis.async_ import AsyncRedisCache
from .backends.redis.sync import RedisCache


class _CacheFactory:
    """Factory for constructing caches from dict or environment configuration."""

    def __call__(self, config: dict[str, Any], mode: Literal["async", "sync"] = "async") -> Any:
        """Create a cache from a configuration mapping.

        Args:
            config (dict[str, Any]): Configuration mapping. Supported keys for Redis
                include ``host``, ``port``, ``db``, ``password``, ``ssl``, ``namespace``.
            mode (Literal["async", "sync"]): Redis mode to use. In-memory is always sync.

        Returns:
            Any: Cache instance.
        """
        backend = (config.get("backend") or "inmemory").lower()
        if backend == "inmemory":
            return InMemoryCache(
                max_size=config.get("max_size"),
                eviction_policy=config.get("eviction_policy"),
                namespace=config.get("namespace"),
            )
        if backend == "redis":
            common = {
                "host": config.get("host", "localhost"),
                "port": config.get("port", 6379),
                "db": config.get("db", 0),
                "password": config.get("password"),
                "ssl": config.get("ssl", False),
                "namespace": config.get("namespace"),
            }
            if mode == "async":
                return AsyncRedisCache(**common)
            return RedisCache(**common)
        raise ValueError(f"Unknown backend: {backend}")

    def from_env(self, mode: Literal["async", "sync"] = "sync") -> Any:
        """Create a cache from environment variables.

        Reads variables prefixed with ``CACHE_`` such as ``CACHE_BACKEND``, ``CACHE_HOST``.

        Args:
            mode (Literal["async", "sync"]): Redis mode to use when backend is "redis".

        Returns:
            Any: Cache instance.
        """
        backend = os.getenv("CACHE_BACKEND", "inmemory").lower()
        if backend == "inmemory":
            return InMemoryCache(namespace=os.getenv("CACHE_NAMESPACE"))
        if backend == "redis":
            cfg = {
                "host": os.getenv("CACHE_HOST", "localhost"),
                "port": int(os.getenv("CACHE_PORT", "6379")),
                "db": int(os.getenv("CACHE_DB", "0")),
                "password": os.getenv("CACHE_PASSWORD") or None,
                "ssl": os.getenv("CACHE_SSL", "false").lower() in {"1", "true", "yes"},
                "namespace": os.getenv("CACHE_NAMESPACE"),
            }
            if mode == "async":
                return AsyncRedisCache(**cfg)  # type: ignore[arg-type]
            return RedisCache(**cfg)  # type: ignore[arg-type]
        raise ValueError(f"Unknown backend from env: {backend}")


create_cache = _CacheFactory()

__all__ = ["create_cache"]
