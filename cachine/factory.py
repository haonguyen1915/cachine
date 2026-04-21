"""Deprecated cache factory functions.

These helpers route URLs to the appropriate backend. They have been
superseded by ``<Backend>.from_url(url)`` classmethods on each backend
(``RedisCache.from_url``, ``SQLiteCache.from_url``, and their async
counterparts). Scheduled for removal in v0.3.
"""

from __future__ import annotations

import warnings
from typing import Any

from cachine.serializers import Serializer

from .core.types import AsyncCache, Cache
from .exceptions import RedisURLParseError


def _warn(old: str, replacement: str) -> None:
    warnings.warn(
        f"{old} is deprecated since v0.2 and will be removed in v0.3; use {replacement} instead.",
        DeprecationWarning,
        stacklevel=3,
    )


def cache_from_url(
    url: str,
    namespace: str | None = None,
    serializer: Serializer | None = None,
    **kwargs: Any,
) -> Cache:
    """Deprecated: prefer ``RedisCache.from_url`` or ``SQLiteCache.from_url``."""
    _warn("cache_from_url", "RedisCache.from_url / SQLiteCache.from_url")
    if not url:
        raise RedisURLParseError("URL cannot be empty")
    scheme = url.split("://", 1)[0].lower() if "://" in url else ""

    if kwargs:
        warnings.warn(f"Unknown arguments ignored: {list(kwargs.keys())}", stacklevel=2)

    if scheme in ("redis", "rediss", "redis+sentinel", "rediss+sentinel"):
        from .backends.redis.sync import RedisCache

        return RedisCache.from_url(url, namespace=namespace, serializer=serializer)

    if scheme == "sqlite":
        from .backends.sqlite.sync import SQLiteCache

        return SQLiteCache.from_url(url, namespace=namespace, serializer=serializer)

    raise RedisURLParseError(
        f"Unsupported cache URL scheme: {scheme}. Supported schemes: redis://, rediss://, redis+sentinel://, rediss+sentinel://, sqlite://"
    )


def async_cache_from_url(
    url: str,
    namespace: str | None = None,
    serializer: Serializer | None = None,
    **kwargs: Any,
) -> AsyncCache:
    """Deprecated: prefer ``AsyncRedisCache.from_url`` or ``AsyncSQLiteCache.from_url``."""
    _warn("async_cache_from_url", "AsyncRedisCache.from_url / AsyncSQLiteCache.from_url")
    if not url:
        raise RedisURLParseError("URL cannot be empty")
    scheme = url.split("://", 1)[0].lower() if "://" in url else ""

    if kwargs:
        warnings.warn(f"Unknown arguments ignored: {list(kwargs.keys())}", stacklevel=2)

    if scheme in ("redis", "rediss", "redis+sentinel", "rediss+sentinel"):
        from .backends.redis.async_ import AsyncRedisCache

        return AsyncRedisCache.from_url(url, namespace=namespace, serializer=serializer)

    if scheme == "sqlite":
        from .backends.sqlite.async_ import AsyncSQLiteCache

        return AsyncSQLiteCache.from_url(url, namespace=namespace, serializer=serializer)

    raise RedisURLParseError(
        f"Unsupported cache URL scheme: {scheme}. Supported schemes: redis://, rediss://, redis+sentinel://, rediss+sentinel://, sqlite://"
    )


__all__ = [
    "cache_from_url",
    "async_cache_from_url",
]
