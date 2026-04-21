# ruff: noqa: I001
from __future__ import annotations

# pylint: disable=protected-access

import base64
import hashlib
import inspect
from datetime import timedelta
from typing import Any

from .base import BaseMiddleware


class EncryptionMiddleware(BaseMiddleware):
    """Encrypt cached values using Fernet symmetric encryption.

    Transparently encrypts on ``set`` and decrypts on ``get``. Uses Fernet
    from the ``cryptography`` library for authenticated encryption.

    Args:
        cache: The underlying cache to wrap.
        key: Encryption key (string). Converted to a Fernet-compatible key
            via SHA-256.
        key_id: Optional key identifier for key rotation (default: ``"v1"``).

    Examples:
        >>> from cachine import InMemoryCache
        >>> from cachine.middleware import EncryptionMiddleware
        >>> cache = EncryptionMiddleware(InMemoryCache(), key="my-secret-key", key_id="v1")
        >>> cache.set("key", "sensitive-data")
        >>> cache.get("key")
        'sensitive-data'
    """

    def __init__(self, cache: Any, *, key: str, key_id: str | None = None) -> None:
        super().__init__(cache)
        self.key = key
        self.key_id = key_id or "v1"
        self._fernet = self._create_fernet(key)

    def _create_fernet(self, key: str) -> Any:
        try:
            from cryptography.fernet import Fernet
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("cryptography package not installed; install with: `pip install cryptography`") from e
        key_bytes = key.encode("utf-8")
        fernet_key = base64.urlsafe_b64encode(hashlib.sha256(key_bytes).digest())
        return Fernet(fernet_key)

    def _encrypt(self, data: bytes) -> bytes:
        return self._fernet.encrypt(data)  # type: ignore[no-any-return]

    def _decrypt(self, data: bytes) -> bytes:
        return self._fernet.decrypt(data)  # type: ignore[no-any-return]

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
        """Store encrypted value."""
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

        if not isinstance(payload, bytes):
            payload = str(payload).encode("utf-8")

        encrypted = self._encrypt(payload)
        wrapped = {
            "__encrypted__": True,
            "key_id": self.key_id,
            "data": encrypted,
            "type": original_type,
        }
        self._cache.set(key, wrapped, ttl=ttl)

    async def aset(self, key: str, value: Any, *, ttl: int | timedelta | None = None) -> None:
        """Async version of :meth:`set`."""
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

        if not isinstance(payload, bytes):
            payload = str(payload).encode("utf-8")

        encrypted = self._encrypt(payload)
        wrapped = {
            "__encrypted__": True,
            "key_id": self.key_id,
            "data": encrypted,
            "type": original_type,
        }
        set_fn = self._cache.set
        if inspect.iscoroutinefunction(set_fn):
            await set_fn(key, wrapped, ttl=ttl)
        else:
            set_fn(key, wrapped, ttl=ttl)

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve and decrypt value."""
        value = self._cache.get(key, default=None)
        if value is None:
            return default

        if isinstance(value, dict) and value.get("__encrypted__"):
            decrypted = self._decrypt(value["data"])
            original_type = value.get("type", "bytes")
            ser = self._lookup_serializer()
            if ser is not None:
                return ser.loads(decrypted)
            if original_type == "str":
                return decrypted.decode("utf-8")
            return decrypted
        return value

    async def aget(self, key: str, default: Any = None) -> Any:
        """Async version of :meth:`get`."""
        get_fn = self._cache.get
        value = await get_fn(key, default=None) if inspect.iscoroutinefunction(get_fn) else get_fn(key, default=None)
        if value is None:
            return default

        if isinstance(value, dict) and value.get("__encrypted__"):
            decrypted = self._decrypt(value["data"])
            original_type = value.get("type", "bytes")
            ser = self._lookup_serializer()
            if ser is not None:
                return ser.loads(decrypted)
            if original_type == "str":
                return decrypted.decode("utf-8")
            return decrypted
        return value
