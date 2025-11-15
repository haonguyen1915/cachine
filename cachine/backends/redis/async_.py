from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional


class AsyncRedisCache:
    """Async Redis cache scaffold.

    This is a placeholder; wire to an async Redis client in implementation.
    """

    def __init__(
        self,
        *,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        ssl: bool = False,
        namespace: Optional[str] = None,
    ) -> None:
        self._ns = f"{namespace}:" if namespace else ""
        self._cfg = {"host": host, "port": port, "db": db, "ssl": ssl}
        self._password = password

    # Basic ops (stubs)
    async def get(self, key: str, default: Any = None, *, serializer: Any = None) -> Any:
        raise NotImplementedError

    async def set(self, key: str, value: Any, *, ttl: Optional[int | timedelta] = None, serializer: Any = None) -> None:
        raise NotImplementedError

    async def delete(self, key: str) -> bool:
        raise NotImplementedError

    async def exists(self, key: str) -> bool:
        raise NotImplementedError

    async def clear(self, *, dangerously_clear_all: bool = False) -> None:
        raise NotImplementedError

    # Enrichment
    async def get_or_set(self, key: str, factory, *, ttl: Optional[int | timedelta] = None, jitter: Optional[int] = None):
        raise NotImplementedError

    # TTL management
    async def expire(self, key: str, *, ttl: int | timedelta) -> bool:
        raise NotImplementedError

    async def expire_at(self, key: str, when: datetime) -> bool:
        raise NotImplementedError

    async def touch(self, key: str, *, ttl: Optional[int | timedelta] = None) -> bool:
        raise NotImplementedError

    async def ttl(self, key: str) -> Optional[int]:
        raise NotImplementedError

    async def persist(self, key: str) -> bool:
        raise NotImplementedError

    # Counters
    async def incr(self, key: str, *, delta: int = 1, ttl_on_create: Optional[int | timedelta] = None) -> int:
        raise NotImplementedError

    async def decr(self, key: str, *, delta: int = 1) -> int:
        return await self.incr(key, delta=-int(delta))

    # Tags
    async def invalidate_tags(self, tags: list[str]) -> int:
        raise NotImplementedError

    # Health / lifecycle
    async def ping(self) -> dict:
        return {"healthy": True, "latency_ms": 0.0, "backend": "redis"}

    async def ping_ok(self) -> bool:
        s = await self.ping()
        return bool(s.get("healthy", False))

    async def close(self) -> None:
        return None

    # Async context manager
    async def __aenter__(self) -> "AsyncRedisCache":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

