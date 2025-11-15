# ruff: noqa: I001
from __future__ import annotations

# pylint: disable=protected-access

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
        # Determine original type for restoration later
        original_type = type(value).__name__

        # Serialize first if serializer is provided
        if serializer is not None:
            payload = serializer.dumps(value)
        elif hasattr(self._cache, "_serializer") and self._cache._serializer is not None:
            payload = self._cache._serializer.dumps(value)
        else:
            # No serializer - convert to bytes for compression
            if isinstance(value, bytes):
                payload = value
                original_type = "bytes"
            elif isinstance(value, str):
                payload = value.encode("utf-8")
                original_type = "str"
            else:
                # Store as-is without compression
                self._cache.set(key, value, ttl=ttl)
                return

        # Compress if payload exceeds min_size
        if isinstance(payload, bytes) and len(payload) >= self.min_size:
            compressed = self._compress(payload)
            # Store with compression marker and type info
            wrapped_value = {"__compressed__": True, "data": compressed, "type": original_type}
            self._cache.set(key, wrapped_value, ttl=ttl)
        else:
            # Store as-is
            self._cache.set(key, value, ttl=ttl)

    async def aset(self, key: str, value: Any, *, ttl: Optional[int] = None, serializer: Any = None) -> None:
        """Store value with optional compression if size exceeds threshold (async)."""
        # Determine original type for restoration later
        original_type = type(value).__name__

        # Serialize first if serializer is provided
        if serializer is not None:
            payload = serializer.dumps(value)
        elif hasattr(self._cache, "_serializer") and self._cache._serializer is not None:
            payload = self._cache._serializer.dumps(value)
        else:
            if isinstance(value, bytes):
                payload = value
                original_type = "bytes"
            elif isinstance(value, str):
                payload = value.encode("utf-8")
                original_type = "str"
            else:
                # Store as-is when not serializable to bytes easily
                set_fn = self._cache.set
                if inspect.iscoroutinefunction(set_fn):
                    await set_fn(key, value, ttl=ttl)
                else:
                    set_fn(key, value, ttl=ttl)
                return

        # Compress if payload exceeds min_size
        if isinstance(payload, bytes) and len(payload) >= self.min_size:
            compressed = self._compress(payload)
            wrapped_value = {"__compressed__": True, "data": compressed, "type": original_type}
            set_fn = self._cache.set
            if inspect.iscoroutinefunction(set_fn):
                await set_fn(key, wrapped_value, ttl=ttl)
            else:
                set_fn(key, wrapped_value, ttl=ttl)
        else:
            set_fn = self._cache.set
            if inspect.iscoroutinefunction(set_fn):
                await set_fn(key, value, ttl=ttl, serializer=serializer)
            else:
                set_fn(key, value, ttl=ttl, serializer=serializer)

    def get(self, key: str, default: Any = None, *, serializer: Any = None) -> Any:
        """Retrieve value and decompress if necessary (sync)."""
        value = self._cache.get(key, default=None)
        if value is None:
            return default

        # Check if value is compressed
        if isinstance(value, dict) and value.get("__compressed__"):
            decompressed = self._decompress(value["data"])
            original_type = value.get("type", "bytes")

            # Deserialize if serializer is provided
            if serializer is not None:
                return serializer.loads(decompressed)
            if hasattr(self._cache, "_serializer") and self._cache._serializer is not None:
                return self._cache._serializer.loads(decompressed)

            # Restore original type
            if original_type == "str":
                return decompressed.decode("utf-8")
            return decompressed

        # Not compressed - return as-is
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
            original_type = value.get("type", "bytes")
            # Deserialize if serializer is provided
            if serializer is not None:
                return serializer.loads(decompressed)
            if hasattr(self._cache, "_serializer") and self._cache._serializer is not None:
                return self._cache._serializer.loads(decompressed)
            if original_type == "str":
                return decompressed.decode("utf-8")
            return decompressed

        return value
