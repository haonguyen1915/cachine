# ruff: noqa: I001
from __future__ import annotations

# pylint: disable=protected-access

import gzip
import inspect
import zlib
from datetime import timedelta
from typing import Any

from .base import BaseMiddleware


class CompressionMiddleware(BaseMiddleware):
    """Compress cached values when they exceed a minimum size threshold.

    Transparently compresses data on ``set`` and decompresses on ``get`` when
    the payload size exceeds ``min_size`` bytes. Supports gzip and zlib.

    Args:
        cache: The underlying cache to wrap.
        algorithm: Compression algorithm to use (``"gzip"`` or ``"zlib"``).
        min_size: Minimum payload size in bytes to trigger compression
            (default: ``0`` — always compress).

    Examples:
        >>> from cachine import InMemoryCache
        >>> from cachine.middleware import CompressionMiddleware
        >>> cache = CompressionMiddleware(InMemoryCache(), algorithm="gzip", min_size=100)
        >>> cache.set("key", "a" * 1000)
        >>> cache.get("key")
        'aaa...'
    """

    def __init__(self, cache: Any, *, algorithm: str = "gzip", min_size: int = 0) -> None:
        super().__init__(cache)
        self.algorithm = algorithm
        self.min_size = min_size

    def _compress(self, data: bytes) -> bytes:
        if self.algorithm == "gzip":
            return gzip.compress(data)
        if self.algorithm == "zlib":
            return zlib.compress(data)
        raise ValueError(f"Unsupported compression algorithm: {self.algorithm}")

    def _decompress(self, data: bytes) -> bytes:
        if self.algorithm == "gzip":
            return gzip.decompress(data)
        if self.algorithm == "zlib":
            return zlib.decompress(data)
        raise ValueError(f"Unsupported compression algorithm: {self.algorithm}")

    def _lookup_serializer(self) -> Any:
        """Walk the middleware chain to find the backend's configured serializer."""
        cur: Any = self._cache
        while cur is not None:
            ser = vars(cur).get("_serializer") if hasattr(cur, "__dict__") else None
            if ser is not None:
                return ser
            cur = getattr(cur, "_cache", None)
        return None

    def set(self, key: str, value: Any, *, ttl: int | timedelta | None = None) -> None:
        """Store value with optional compression if size exceeds threshold."""
        # Pass-through for already-wrapped envelopes from upstream middleware
        # (e.g. encryption). We don't try to re-serialize those.
        if isinstance(value, dict) and (value.get("__encrypted__") or value.get("__compressed__")):
            self._cache.set(key, value, ttl=ttl)
            return

        original_type = type(value).__name__
        ser = self._lookup_serializer()

        if ser is not None:
            payload = ser.dumps(value)
        elif isinstance(value, bytes):
            payload = value
            original_type = "bytes"
        elif isinstance(value, str):
            payload = value.encode("utf-8")
            original_type = "str"
        else:
            self._cache.set(key, value, ttl=ttl)
            return

        if isinstance(payload, bytes) and len(payload) >= self.min_size:
            compressed = self._compress(payload)
            wrapped = {"__compressed__": True, "data": compressed, "type": original_type}
            self._cache.set(key, wrapped, ttl=ttl)
        else:
            self._cache.set(key, value, ttl=ttl)

    async def aset(self, key: str, value: Any, *, ttl: int | timedelta | None = None) -> None:
        """Async version of :meth:`set`."""
        if isinstance(value, dict) and (value.get("__encrypted__") or value.get("__compressed__")):
            set_fn = self._cache.set
            if inspect.iscoroutinefunction(set_fn):
                await set_fn(key, value, ttl=ttl)
            else:
                set_fn(key, value, ttl=ttl)
            return

        original_type = type(value).__name__
        ser = self._lookup_serializer()

        if ser is not None:
            payload = ser.dumps(value)
        elif isinstance(value, bytes):
            payload = value
            original_type = "bytes"
        elif isinstance(value, str):
            payload = value.encode("utf-8")
            original_type = "str"
        else:
            set_fn = self._cache.set
            if inspect.iscoroutinefunction(set_fn):
                await set_fn(key, value, ttl=ttl)
            else:
                set_fn(key, value, ttl=ttl)
            return

        if isinstance(payload, bytes) and len(payload) >= self.min_size:
            compressed = self._compress(payload)
            wrapped = {"__compressed__": True, "data": compressed, "type": original_type}
            set_fn = self._cache.set
            if inspect.iscoroutinefunction(set_fn):
                await set_fn(key, wrapped, ttl=ttl)
            else:
                set_fn(key, wrapped, ttl=ttl)
        else:
            set_fn = self._cache.set
            if inspect.iscoroutinefunction(set_fn):
                await set_fn(key, value, ttl=ttl)
            else:
                set_fn(key, value, ttl=ttl)

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve and decompress value."""
        value = self._cache.get(key, default=None)
        if value is None:
            return default

        if isinstance(value, dict) and value.get("__compressed__"):
            decompressed = self._decompress(value["data"])
            original_type = value.get("type", "bytes")
            ser = self._lookup_serializer()
            if ser is not None:
                return ser.loads(decompressed)
            if original_type == "str":
                return decompressed.decode("utf-8")
            return decompressed
        return value

    async def aget(self, key: str, default: Any = None) -> Any:
        """Async version of :meth:`get`."""
        get_fn = self._cache.get
        value = await get_fn(key, default=None) if inspect.iscoroutinefunction(get_fn) else get_fn(key, default=None)
        if value is None:
            return default

        if isinstance(value, dict) and value.get("__compressed__"):
            decompressed = self._decompress(value["data"])
            original_type = value.get("type", "bytes")
            ser = self._lookup_serializer()
            if ser is not None:
                return ser.loads(decompressed)
            if original_type == "str":
                return decompressed.decode("utf-8")
            return decompressed
        return value
