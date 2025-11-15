from __future__ import annotations

from typing import Any, Optional

from .sync import RedisCache


class RedisClusterCache(RedisCache):
    """RedisCache configured for Redis Cluster.

    Creates a redis.cluster.RedisCluster client and injects it into RedisCache.
    """

    def __init__(
        self,
        *,
        nodes: list[dict[str, Any]],
        password: Optional[str] = None,
        ssl: bool = False,
        namespace: Optional[str] = None,
        serializer: Optional[Any] = None,
    ) -> None:
        try:
            from redis.cluster import RedisCluster  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError("redis cluster client not available; install redis>=4 with cluster support") from e

        # Expect nodes as [{"host": ..., "port": ...}, ...]
        # RedisCluster accepts startup_nodes parameter in some versions; newer versions accept host/port directly.
        try:
            client = RedisCluster(startup_nodes=nodes, password=password, ssl=ssl)
        except TypeError:
            # Fallback: use first node (not ideal but avoids import-time errors)
            first = nodes[0]
            client = RedisCluster(host=first["host"], port=first["port"], password=password, ssl=ssl)

        super().__init__(
            host="",
            port=0,
            db=0,
            password=password,
            ssl=ssl,
            namespace=namespace,
            client=client,
            serializer=serializer,
        )

