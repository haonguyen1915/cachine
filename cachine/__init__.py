"""Cachine public API exports.

This package exposes sync InMemoryCache, sync/async Redis caches,
the caching decorator, and the cache factory, along with subpackages
for serializers, middleware, and strategies as documented in INTERFACE.md.
"""

from .backends.inmemory.cache import InMemoryCache
from .backends.redis.async_ import AsyncRedisCache
from .backends.redis.sync import RedisCache
from .core.types import AsyncCache as AsyncCacheType
from .core.types import Cache as CacheType
from .core.types import CacheLike
from .decorators.cached import cached
from .factory import create_cache
from .utils.logging_utils import logger_setup

__all__ = [
    "InMemoryCache",
    "RedisCache",
    "AsyncRedisCache",
    "cached",
    "CacheType",
    "AsyncCacheType",
    "CacheLike",
    "create_cache",
    "logger_setup",
]
