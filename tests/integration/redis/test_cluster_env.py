import os
import time
from typing import Any

import pytest

try:
    from cachine.backends.redis.cluster import RedisClusterCache
    from cachine.serializers import JSONSerializer
except Exception:  # pragma: no cover
    RedisClusterCache = None  # type: ignore[misc,assignment]


def _truthy(v: str | None) -> bool:
    return (v or "").lower() in {"1", "true", "yes", "on"}


def _parse_nodes(env: str | None) -> list[dict[str, Any]]:
    if not env:
        return []
    nodes: list[dict[str, Any]] = []
    for part in env.split(","):
        part = part.strip()
        if not part:
            continue
        host, _, port = part.partition(":")
        nodes.append({"host": host, "port": int(port or 6379)})
    return nodes


pytestmark = pytest.mark.skipif(
    not _truthy(os.getenv("RUN_REDIS_CLUSTER_TESTS")),
    reason="RUN_REDIS_CLUSTER_TESTS not enabled",
)


def test_redis_cluster_set_get_incr() -> None:
    if RedisClusterCache is None:
        pytest.skip("redis cluster client is not available")
    # Parse nodes from env: REDIS_CLUSTER_NODES="host1:7000,host2:7001,host3:7002"
    nodes = _parse_nodes(os.getenv("REDIS_CLUSTER_NODES"))
    if not nodes:
        pytest.skip("REDIS_CLUSTER_NODES is not set")

    username = os.getenv("REDIS_CLUSTER_USERNAME") or None
    password = os.getenv("REDIS_CLUSTER_PASSWORD") or None
    ssl = os.getenv("REDIS_SSL", "false").lower() in {"1", "true", "yes"}

    try:
        cache = RedisClusterCache(
            nodes=nodes,
            username=username,
            password=password,
            ssl=ssl,
            namespace=f"itest:{int(time.time())}",
            serializer=JSONSerializer(),
        )
    except RuntimeError as e:
        pytest.skip(str(e))

    # Basic set/get
    cache.set("k", {"a": 1}, ttl=10)
    assert cache.get("k") == {"a": 1}

    # Incr should work across slots
    assert cache.incr("cnt") == 1
    assert cache.incr("cnt", delta=4) == 5
