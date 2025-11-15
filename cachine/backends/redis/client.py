from __future__ import annotations

# pylint: disable=too-many-public-methods
from typing import Any, Optional


class RedisClient:
    """Thin wrapper around redis-py client to centralize setup and API use.

    This wrapper exists to avoid hard dependencies at import time and to
    provide a consistent surface area for the higher-level RedisCache.
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
        return self._client.get(name)  # type: ignore[return-value]

    def set(self, name: str, value: Any, *, ex: Optional[int] = None, px: Optional[int] = None) -> bool:
        return bool(self._client.set(name, value, ex=ex, px=px))

    def delete(self, name: str) -> int:
        return int(self._client.delete(name))  # type: ignore[arg-type]

    def exists(self, name: str) -> int:
        return int(self._client.exists(name))  # type: ignore[arg-type]

    # TTL ops
    def ttl(self, name: str) -> int:
        return int(self._client.ttl(name))  # type: ignore[arg-type]

    def expire(self, name: str, seconds: int) -> int:
        return int(self._client.expire(name, seconds))  # type: ignore[arg-type]

    def expireat(self, name: str, timestamp: int) -> int:
        return int(self._client.expireat(name, timestamp))  # type: ignore[arg-type]

    def pexpire(self, name: str, ms: int) -> int:
        return int(self._client.pexpire(name, ms))  # type: ignore[arg-type]

    def persist(self, name: str) -> int:
        return int(self._client.persist(name))  # type: ignore[arg-type]

    # Counters
    def incrby(self, name: str, delta: int) -> int:
        return int(self._client.incrby(name, delta))  # type: ignore[arg-type]

    # Scripting
    def eval(self, script: str, numkeys: int, *keys_and_args: Any) -> Any:
        return self._client.eval(script, numkeys, *keys_and_args)

    # Touch/ping/close
    def touch(self, name: str) -> int:
        # touch returns 1 if the key exists, otherwise 0
        try:
            return int(self._client.touch(name))  # type: ignore[arg-type]
        except Exception:  # pragma: no cover - not all versions support touch
            return 1 if self.exists(name) else 0

    # Sets (for tag indexing)
    def sadd(self, name: str, *values: Any) -> int:
        return int(self._client.sadd(name, *values))  # type: ignore[arg-type]

    def smembers(self, name: str) -> set:  # type: ignore[valid-type]
        return set(self._client.smembers(name))  # type: ignore[arg-type]

    # Scanning and bulk ops
    def scan_iter(self, match: str, count: int | None = None) -> Any:
        if count is None:
            return self._client.scan_iter(match=match)
        return self._client.scan_iter(match=match, count=count)

    def delete_many(self, *names: str) -> int:
        if not names:
            return 0
        return int(self._client.delete(*names))  # type: ignore[arg-type]

    def flushdb(self) -> None:
        self._client.flushdb()

    # Pub/Sub
    def publish(self, channel: str, data: str) -> int:
        return int(self._client.publish(channel, data))  # type: ignore[arg-type]

    def pubsub(self) -> Any:  # pragma: no cover - requires live Redis
        return self._client.pubsub()

    def ping(self) -> bool:
        try:
            return bool(self._client.ping())
        except Exception:  # pragma: no cover
            return False

    def close(self) -> None:
        try:
            self._client.close()
        except Exception:  # pragma: no cover
            pass
