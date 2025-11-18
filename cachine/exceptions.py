class CacheError(Exception):
    """Base class for cache-related errors."""


class ConnectionError(CacheError):
    """Raised when the cache backend is unavailable or connection fails."""


class SerializationError(CacheError):
    """Raised when serialization of a value fails."""


class DeserializationError(CacheError):
    """Raised when deserialization of stored bytes fails."""


class EvictionError(CacheError):
    """Raised for eviction-related errors in in-memory cache backends."""


class RedisURLParseError(CacheError):
    """Raised when a Redis URL cannot be parsed."""
