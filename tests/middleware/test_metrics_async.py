from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any, Optional

import pytest

from cachine.core.types import HealthStatus
from cachine.middleware import AsyncMetricsMiddleware


class _DummyAsyncCache:
    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    # Basic ops
    async def get(self, key: str, default: Any = None, *, serializer: Any = None) -> Any:  # noqa: ARG002
        await asyncio.sleep(0)  # force scheduling for realism
        return self._store.get(key, default)

    async def set(self, key: str, value: Any, *, ttl: Optional[int | timedelta] = None, serializer: Any = None) -> None:  # noqa: ARG002
        await asyncio.sleep(0)
        self._store[key] = value

    async def delete(self, key: str) -> bool:
        await asyncio.sleep(0)
        return self._store.pop(key, None) is not None

    async def exists(self, key: str) -> bool:
        await asyncio.sleep(0)
        return key in self._store

    async def clear(self, *, dangerously_clear_all: bool = False) -> None:  # noqa: ARG002
        await asyncio.sleep(0)
        self._store.clear()

    # Enrichment
    async def get_or_set(
        self,
        key: str,
        factory: Any,
        *,
        ttl: Optional[int | timedelta] = None,  # noqa: ARG002
        jitter: Optional[int] = None,  # noqa: ARG002
    ) -> Any:
        await asyncio.sleep(0)
        if key in self._store:
            return self._store[key]
        value = await factory() if asyncio.iscoroutinefunction(factory) else factory()
        self._store[key] = value
        return value

    # TTL management
    async def expire(self, key: str, *, ttl: int | timedelta) -> bool:  # noqa: ARG002
        await asyncio.sleep(0)
        return key in self._store

    async def expire_at(self, key: str, when: datetime) -> bool:  # noqa: ARG002
        await asyncio.sleep(0)
        return key in self._store

    async def touch(self, key: str, *, ttl: Optional[int | timedelta] = None) -> bool:  # noqa: ARG002
        await asyncio.sleep(0)
        return key in self._store

    async def ttl(self, key: str) -> Optional[int]:  # noqa: ARG002
        await asyncio.sleep(0)
        return None

    async def persist(self, key: str) -> bool:  # noqa: ARG002
        await asyncio.sleep(0)
        return key in self._store

    # Counters
    async def incr(self, key: str, *, delta: int = 1, ttl_on_create: Optional[int | timedelta] = None) -> int:  # noqa: ARG002
        await asyncio.sleep(0)
        val = int(self._store.get(key, 0)) + delta
        self._store[key] = val
        return val

    async def decr(self, key: str, *, delta: int = 1) -> int:  # noqa: ARG002
        await asyncio.sleep(0)
        val = int(self._store.get(key, 0)) - delta
        self._store[key] = val
        return val

    # Tags
    async def invalidate_tags(self, tags: list[str]) -> int:  # noqa: ARG002
        await asyncio.sleep(0)
        return 0

    # Health / lifecycle
    async def ping(self) -> HealthStatus:
        await asyncio.sleep(0)
        return {"healthy": True, "latency_ms": 0.1, "backend": "dummy"}

    async def ping_ok(self) -> bool:
        await asyncio.sleep(0)
        return True

    async def close(self) -> None:
        await asyncio.sleep(0)

    # Async context manager
    async def __aenter__(self) -> "_DummyAsyncCache":
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:  # noqa: ARG002
        await self.close()


@pytest.mark.asyncio
async def test_metrics_async_hits_and_misses() -> None:
    base = _DummyAsyncCache()
    mw = AsyncMetricsMiddleware(base)

    # Miss path
    assert await mw.get("k1", default="d1") == "d1"

    # Hit path
    await mw.set("k1", "v1")
    assert await mw.get("k1") == "v1"

    stats = mw.get_stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert 0.0 <= stats["hit_rate"] <= 1.0
    assert stats["errors"] == 0
    assert stats["avg_latency_ms"] >= 0.0

