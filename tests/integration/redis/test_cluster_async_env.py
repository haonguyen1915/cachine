import os
import time

import pytest


def _truthy(v: str | None) -> bool:
    return (v or "").lower() in {"1", "true", "yes", "on"}


def _parse_nodes(env: str | None) -> list:  # type: ignore[type-arg]
    if not env:
        return []
    try:
        from cachine.models.redis_config import RedisNodeConfig

        nodes: list[RedisNodeConfig] = []
        for part in env.split(","):
            part = part.strip()
            if not part:
                continue
            host, _, port = part.partition(":")
            nodes.append(RedisNodeConfig(host=host, port=int(port or 6379)))
        return nodes
    except Exception:  # pragma: no cover
        return []


pytestmark = pytest.mark.skipif(
    not _truthy(os.getenv("RUN_REDIS_CLUSTER_TESTS")),
    reason="RUN_REDIS_CLUSTER_TESTS not enabled",
)


@pytest.mark.asyncio
async def test_async_redis_cluster_set_get_incr() -> None:
    try:
        from cachine.backends.redis.async_ import AsyncRedisCache
        from cachine.models.redis_config import RedisClusterConfig
        from cachine.serializers import JSONSerializer
    except Exception as e:  # pragma: no cover
        pytest.skip(f"async redis cluster client not available: {e}")

    nodes = _parse_nodes(os.getenv("REDIS_CLUSTER_NODES"))
    if not nodes:
        pytest.skip("REDIS_CLUSTER_NODES is not set")

    username = os.getenv("REDIS_CLUSTER_USERNAME") or None
    password = os.getenv("REDIS_CLUSTER_PASSWORD") or None
    ssl = os.getenv("REDIS_SSL", "false").lower() in {"1", "true", "yes"}

    try:
        config = RedisClusterConfig(
            nodes=nodes,
            username=username,
            password=password,
            ssl=ssl,
        )
        cache = AsyncRedisCache(
            config,
            namespace=f"itest:{int(time.time())}",
            serializer=JSONSerializer(),
        )
    except RuntimeError as e:
        pytest.skip(str(e))

    # Basic set/get
    await cache.set("k", {"a": 1}, ttl=10)
    assert await cache.get("k") == {"a": 1}

    # Incr/decr
    assert await cache.incr("cnt") == 1
    assert await cache.incr("cnt", delta=4) == 5
    assert await cache.decr("cnt", delta=2) == 3

    # Cleanup
    await cache.clear()
    await cache.close()
