from __future__ import annotations

import gzip
import inspect
import zlib
from typing import Any, Optional

from .base import BaseMiddleware


class CompressionMiddleware(BaseMiddleware):
    """Compress cached values when they exceed a minimum size threshold.

    This middleware transparently compresses data on ``set`` and decompresses on ``get``
    when the payload size exceeds ``min_size`` bytes. Supports both gzip and zlib algorithms.

    Args:
        cache: The underlying cache to wrap
        algorithm: Compression algorithm to use ("gzip" or "zlib")
        min_size: Minimum payload size in bytes to trigger compression (default: 0 = always compress)

    Examples:
        >>> from cachine import InMemoryCache
        >>> from cachine.middleware import CompressionMiddleware
        >>> cache = CompressionMiddleware(InMemoryCache(), algorithm="gzip", min_size=100)
        >>> cache.set("key", "a" * 1000)  # Will be compressed
        >>> cache.get("key")  # Automatically decompressed
        'aaa...'
    """

    def __init__(self, cache: Any, *, algorithm: str = "gzip", min_size: int = 0) -> None:
        super().__init__(cache)
        self.algorithm = algorithm
        self.min_size = min_size

    def _compress(self, data: bytes) -> bytes:
        """Compress data using the configured algorithm."""
        if self.algorithm == "gzip":
            return gzip.compress(data)
        if self.algorithm == "zlib":
            return zlib.compress(data)
        raise ValueError(f"Unsupported compression algorithm: {self.algorithm}")

    def _decompress(self, data: bytes) -> bytes:
        """Decompress data using the configured algorithm."""
        if self.algorithm == "gzip":
            return gzip.decompress(data)
        if self.algorithm == "zlib":
            return zlib.decompress(data)
        raise ValueError(f"Unsupported compression algorithm: {self.algorithm}")

    def set(self, key: str, value: Any, *, ttl: Optional[int] = None, serializer: Any = None) -> None:
        """Store value with optional compression if size exceeds threshold (sync)."""
        # Serialize first if serializer is provided
        if serializer is not None:
            payload = serializer.dumps(value)
        elif hasattr(self._cache, "_serializer") and self._cache._serializer is not None:
            payload = self._cache._serializer.dumps(value)
        else:
            # No serializer - assume value is already bytes or will be handled by underlying cache
            payload = value if isinstance(value, bytes) else str(value).encode("utf-8")

        # Compress if payload exceeds min_size
        if isinstance(payload, bytes) and len(payload) >= self.min_size:
            compressed = self._compress(payload)
            # Store with compression marker
            wrapped_value = {"__compressed__": True, "data": compressed}
            self._cache.set(key, wrapped_value, ttl=ttl, serializer=None)
        else:
            # Store as-is
            self._cache.set(key, value, ttl=ttl, serializer=serializer)

    async def aset(self, key: str, value: Any, *, ttl: Optional[int] = None, serializer: Any = None) -> None:
        """Store value with optional compression if size exceeds threshold (async)."""
        # Serialize first if serializer is provided
        if serializer is not None:
            payload = serializer.dumps(value)
        elif hasattr(self._cache, "_serializer") and self._cache._serializer is not None:
            payload = self._cache._serializer.dumps(value)
        else:
            payload = value if isinstance(value, bytes) else str(value).encode("utf-8")

        # Compress if payload exceeds min_size
        if isinstance(payload, bytes) and len(payload) >= self.min_size:
            compressed = self._compress(payload)
            wrapped_value = {"__compressed__": True, "data": compressed}
            set_fn = self._cache.set
            if inspect.iscoroutinefunction(set_fn):
                await set_fn(key, wrapped_value, ttl=ttl, serializer=None)
            else:
                set_fn(key, wrapped_value, ttl=ttl, serializer=None)
        else:
            set_fn = self._cache.set
            if inspect.iscoroutinefunction(set_fn):
                await set_fn(key, value, ttl=ttl, serializer=serializer)
            else:
                set_fn(key, value, ttl=ttl, serializer=serializer)

    def get(self, key: str, default: Any = None, *, serializer: Any = None) -> Any:
        """Retrieve value and decompress if necessary (sync)."""
        value = self._cache.get(key, default=None, serializer=None)
        if value is None:
            return default

        # Check if value is compressed
        if isinstance(value, dict) and value.get("__compressed__"):
            decompressed = self._decompress(value["data"])
            # Deserialize if serializer is provided
            if serializer is not None:
                return serializer.loads(decompressed)
            if hasattr(self._cache, "_serializer") and self._cache._serializer is not None:
                return self._cache._serializer.loads(decompressed)
            return decompressed

        # Not compressed - return as-is (may need deserialization by underlying cache)
        if serializer is not None:
            # Value was not compressed, but might need deserialization
            return value
        return value

    async def aget(self, key: str, default: Any = None, *, serializer: Any = None) -> Any:
        """Retrieve value and decompress if necessary (async)."""
        get_fn = self._cache.get
        if inspect.iscoroutinefunction(get_fn):
            value = await get_fn(key, default=None, serializer=None)
        else:
            value = get_fn(key, default=None, serializer=None)

        if value is None:
            return default

        # Check if value is compressed
        if isinstance(value, dict) and value.get("__compressed__"):
            decompressed = self._decompress(value["data"])
            # Deserialize if serializer is provided
            if serializer is not None:
                return serializer.loads(decompressed)
            if hasattr(self._cache, "_serializer") and self._cache._serializer is not None:
                return self._cache._serializer.loads(decompressed)
            return decompressed

        return value
