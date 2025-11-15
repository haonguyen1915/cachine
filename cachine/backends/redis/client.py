from __future__ import annotations

# pylint: disable=too-many-public-methods
from typing import Any, Optional


class RedisClient:
    """Thin wrapper around redis-py client to centralize setup and API use.

    This wrapper exists to avoid hard dependencies at import time and to
    provide a consistent surface area for the higher-level RedisCache.

    Args:
        host (str): Redis host.
        port (int): Redis port.
        db (int): Database index.
        password (str | None): Optional password.
        ssl (bool): Whether to use TLS.
        decode_responses (bool): If True, decode responses to strings.
    """

    def __init__(
        self,
        *,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        ssl: bool = False,
        decode_responses: bool = False,
    ) -> None:
        try:
            import redis
        except Exception as e:  # pragma: no cover
            raise RuntimeError("redis package not installed. Please install redis (pip install redis).") from e

        self._client = redis.Redis(
            host=host,
            port=port,
            db=db,
            password=password,
            ssl=ssl,
            decode_responses=decode_responses,
        )

    # Basic ops
    def get(self, name: str) -> Optional[bytes]:
        """Return raw value for ``name`` (bytes) or None if missing."""
        return self._client.get(name)  # type: ignore[return-value]

    def set(self, name: str, value: Any, *, ex: Optional[int] = None, px: Optional[int] = None) -> bool:
        """Set value with optional expire in seconds (ex) or milliseconds (px)."""
        return bool(self._client.set(name, value, ex=ex, px=px))

    def delete(self, name: str) -> int:
        """Delete key; return number of removed keys (0 or 1)."""
        return int(self._client.delete(name))  # type: ignore[arg-type]

    def exists(self, name: str) -> int:
        """Return 1 if key exists, else 0."""
        return int(self._client.exists(name))  # type: ignore[arg-type]

    # TTL ops
    def ttl(self, name: str) -> int:
        """Return TTL in seconds, -1 if no expire, -2 if missing."""
        return int(self._client.ttl(name))  # type: ignore[arg-type]

    def expire(self, name: str, seconds: int) -> int:
        """Set expiration in seconds; return 1 on success."""
        return int(self._client.expire(name, seconds))  # type: ignore[arg-type]

    def expireat(self, name: str, timestamp: int) -> int:
        """Set absolute expiration at unix ``timestamp`` seconds; return 1 on success."""
        return int(self._client.expireat(name, timestamp))  # type: ignore[arg-type]

    def pexpire(self, name: str, ms: int) -> int:
        """Set expiration in milliseconds; return 1 on success."""
        return int(self._client.pexpire(name, ms))  # type: ignore[arg-type]

    def persist(self, name: str) -> int:
        """Remove expiration from key; return 1 if TTL was removed."""
        return int(self._client.persist(name))  # type: ignore[arg-type]

    # Counters
    def incrby(self, name: str, delta: int) -> int:
        """Increment key by ``delta`` and return the new value."""
        return int(self._client.incrby(name, delta))  # type: ignore[arg-type]

    # Scripting
    def eval(self, script: str, numkeys: int, *keys_and_args: Any) -> Any:
        """Evaluate a Lua ``script`` with ``numkeys`` and arguments."""
        return self._client.eval(script, numkeys, *keys_and_args)

    # Touch/ping/close
    def touch(self, name: str) -> int:
        """Return 1 if key exists (and updates last access time when supported)."""
        # touch returns 1 if the key exists, otherwise 0
        try:
            return int(self._client.touch(name))  # type: ignore[arg-type]
        except Exception:  # pragma: no cover - not all versions support touch
            return 1 if self.exists(name) else 0

    # Sets (for tag indexing)
    def sadd(self, name: str, *values: Any) -> int:
        """Add ``values`` to set ``name``; returns number of added elements."""
        return int(self._client.sadd(name, *values))  # type: ignore[arg-type]

    def smembers(self, name: str) -> set:  # type: ignore[valid-type]
        """Return a Python set of members in Redis set ``name``."""
        return set(self._client.smembers(name))  # type: ignore[arg-type]

    # Scanning and bulk ops
    def scan_iter(self, match: str, count: int | None = None) -> Any:
        """Return an iterator over keys matching ``match`` (optionally batch size)."""
        if count is None:
            return self._client.scan_iter(match=match)
        return self._client.scan_iter(match=match, count=count)

    def delete_many(self, *names: str) -> int:
        """Delete many keys; returns number of removed keys."""
        if not names:
            return 0
        return int(self._client.delete(*names))  # type: ignore[arg-type]

    def flushdb(self) -> None:
        """Flush the current database (dangerous)."""
        self._client.flushdb()

    # Pub/Sub
    def publish(self, channel: str, data: str) -> int:
        """Publish a message.

        Args:
            channel (str): Channel name.
            data (str): String payload.

        Returns:
            int: Number of clients that received the message.
        """
        return int(self._client.publish(channel, data))  # type: ignore[arg-type]

    def pubsub(self) -> Any:  # pragma: no cover - requires live Redis
        """Create a Pub/Sub object.

        Returns:
            Any: Pub/Sub object for subscribing/listening.
        """
        return self._client.pubsub()

    def ping(self) -> bool:
        """Return True if PING succeeds against Redis."""
        try:
            return bool(self._client.ping())
        except Exception:  # pragma: no cover
            return False

    def close(self) -> None:
        """Close the client connection if possible."""
        try:
            self._client.close()
        except Exception:  # pragma: no cover
            pass
