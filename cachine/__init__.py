"""Cachine public API exports.

This package exposes sync InMemoryCache, sync/async Redis caches,
the caching decorator, and the cache factory, along with subpackages
for serializers, middleware, and strategies as documented in INTERFACE.md.
"""

from .backends.inmemory.cache import InMemoryCache
from .backends.redis.sync import RedisCache
from .backends.redis.async_ import AsyncRedisCache
from .decorators.cached import cached
from .factory import create_cache

__all__ = [
    "InMemoryCache",
    "RedisCache",
    "AsyncRedisCache",
    "cached",
    "create_cache",
]

