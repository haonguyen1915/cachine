# ruff: noqa: I001
from __future__ import annotations

# pylint: disable=protected-access

import base64
import hashlib
import inspect
from typing import Any, Optional

from .base import BaseMiddleware


class EncryptionMiddleware(BaseMiddleware):
    """Encrypt cached values using Fernet symmetric encryption.

    This middleware transparently encrypts data on ``set`` and decrypts on ``get``.
    Uses Fernet from the cryptography library for authenticated encryption.

    Args:
        cache: The underlying cache to wrap
        key: Encryption key (string). Will be converted to Fernet-compatible key via SHA-256
        key_id: Optional key identifier for key rotation support (default: "v1")

    Notes:
        - The key is automatically converted to a valid Fernet key using SHA-256
        - Encrypted values are stored with metadata including key_id for rotation support
        - Requires the ``cryptography`` package to be installed

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
        """Create a Fernet cipher from a string key."""
        try:
            from cryptography.fernet import Fernet
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("cryptography package not installed. Please install it: pip install cryptography") from e

        # Convert string key to Fernet-compatible key using SHA-256
        key_bytes = key.encode("utf-8")
        fernet_key = base64.urlsafe_b64encode(hashlib.sha256(key_bytes).digest())
        return Fernet(fernet_key)

    def _encrypt(self, data: bytes) -> bytes:
        """Encrypt data using Fernet."""
        return self._fernet.encrypt(data)  # type: ignore[no-any-return]

    def _decrypt(self, data: bytes) -> bytes:
        """Decrypt data using Fernet."""
        return self._fernet.decrypt(data)  # type: ignore[no-any-return]

    def set(self, key: str, value: Any, *, ttl: Optional[int] = None, serializer: Any = None) -> None:
        """Store encrypted value (sync)."""
        # Determine original type for restoration later
        original_type = type(value).__name__

        # Serialize first if serializer is provided
        if serializer is not None:
            payload = serializer.dumps(value)
        elif hasattr(self._cache, "_serializer") and self._cache._serializer is not None:
            payload = self._cache._serializer.dumps(value)
        else:
            # No serializer - convert to bytes for encryption
            if isinstance(value, bytes):
                payload = value
                original_type = "bytes"
            elif isinstance(value, str):
                payload = value.encode("utf-8")
                original_type = "str"
            else:
                # For non-serializable types, store as-is
                self._cache.set(key, value, ttl=ttl)
                return

        # Encrypt the payload
        if not isinstance(payload, bytes):
            payload = str(payload).encode("utf-8")

        encrypted = self._encrypt(payload)

        # Store with encryption metadata
        wrapped_value = {
            "__encrypted__": True,
            "key_id": self.key_id,
            "data": encrypted,
            "type": original_type,
        }
        self._cache.set(key, wrapped_value, ttl=ttl)

    async def aset(self, key: str, value: Any, *, ttl: Optional[int] = None, serializer: Any = None) -> None:
        """Store encrypted value (async)."""
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
                set_fn = self._cache.set
                if inspect.iscoroutinefunction(set_fn):
                    await set_fn(key, value, ttl=ttl)
                else:
                    set_fn(key, value, ttl=ttl)
                return

        # Encrypt the payload
        if not isinstance(payload, bytes):
            payload = str(payload).encode("utf-8")

        encrypted = self._encrypt(payload)

        # Store with encryption metadata
        wrapped_value = {
            "__encrypted__": True,
            "key_id": self.key_id,
            "data": encrypted,
            "type": original_type,
        }
        set_fn = self._cache.set
        if inspect.iscoroutinefunction(set_fn):
            await set_fn(key, wrapped_value, ttl=ttl)
        else:
            set_fn(key, wrapped_value, ttl=ttl)

    def get(self, key: str, default: Any = None, *, serializer: Any = None) -> Any:
        """Retrieve and decrypt value (sync)."""
        value = self._cache.get(key, default=None)
        if value is None:
            return default

        # Check if value is encrypted
        if isinstance(value, dict) and value.get("__encrypted__"):
            # TODO: Support key rotation by checking key_id and using appropriate key
            decrypted = self._decrypt(value["data"])
            original_type = value.get("type", "bytes")

            # Deserialize if serializer is provided
            if serializer is not None:
                return serializer.loads(decrypted)
            if hasattr(self._cache, "_serializer") and self._cache._serializer is not None:
                return self._cache._serializer.loads(decrypted)

            # Restore original type
            if original_type == "str":
                return decrypted.decode("utf-8")
            return decrypted

        # Not encrypted - return as-is
        return value

    async def aget(self, key: str, default: Any = None, *, serializer: Any = None) -> Any:
        """Retrieve and decrypt value (async)."""
        get_fn = self._cache.get
        if inspect.iscoroutinefunction(get_fn):
            value = await get_fn(key, default=None, serializer=None)
        else:
            value = get_fn(key, default=None, serializer=None)

        if value is None:
            return default

        # Check if value is encrypted
        if isinstance(value, dict) and value.get("__encrypted__"):
            decrypted = self._decrypt(value["data"])
            original_type = value.get("type", "bytes")

            # Deserialize if serializer is provided
            if serializer is not None:
                return serializer.loads(decrypted)
            if hasattr(self._cache, "_serializer") and self._cache._serializer is not None:
                return self._cache._serializer.loads(decrypted)
            if original_type == "str":
                return decrypted.decode("utf-8")
            return decrypted

        return value
