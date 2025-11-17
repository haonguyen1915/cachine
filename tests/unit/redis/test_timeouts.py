from __future__ import annotations

from typing import Any

import pytest


def test_sync_redis_timeouts_plumbed_to_client(monkeypatch: pytest.MonkeyPatch) -> None:
    from cachine.backends.redis import sync as sync_mod
    from cachine.backends.redis.sync import RedisCache

    captured: dict[str, object] = {}

    class CaptureClient:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

        # minimal surface for the call we do below
        def exists(self, name: str) -> int:  # noqa: ARG002
            return 0

    monkeypatch.setattr(sync_mod, "RedisClient", CaptureClient)

    cache = RedisCache(
        host="localhost",
        port=6379,
        namespace="ut",
        socket_timeout=1.25,
        socket_connect_timeout=0.5,
        retry_on_timeout=True,
    )

    # trigger client creation
    assert cache.exists("k") is False

    assert captured.get("socket_timeout") == 1.25
    assert captured.get("socket_connect_timeout") == 0.5
    assert captured.get("retry_on_timeout") is True


try:  # pragma: no cover - optional dependency gate
    import pytest_asyncio as _pytest_asyncio  # noqa: F401
    HAS_ASYNC = True
except Exception:  # pragma: no cover
    HAS_ASYNC = False


@pytest.mark.skipif(not HAS_ASYNC, reason="pytest-asyncio not installed")
@pytest.mark.asyncio
async def test_async_redis_timeouts_plumbed_to_client(monkeypatch: pytest.MonkeyPatch) -> None:
    from cachine.backends.redis import async_ as async_mod
    from cachine.backends.redis.async_ import AsyncRedisCache

    captured: dict[str, object] = {}

    class CaptureAsyncClient:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

        async def exists(self, name: str) -> int:  # noqa: ARG002
            return 0

    monkeypatch.setattr(async_mod, "AsyncRedisClient", CaptureAsyncClient)

    cache = AsyncRedisCache(
        host="localhost",
        port=6379,
        namespace="ut",
        socket_timeout=2.5,
        socket_connect_timeout=1.0,
        retry_on_timeout=True,
    )

    # trigger client creation
    assert await cache.exists("k") is False

    assert captured.get("socket_timeout") == 2.5
    assert captured.get("socket_connect_timeout") == 1.0
    assert captured.get("retry_on_timeout") is True
