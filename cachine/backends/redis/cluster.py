from __future__ import annotations

from typing import Any, Optional

from .sync import RedisCache


class RedisClusterCache(RedisCache):
    """Redis-backed cache configured for Redis Cluster.

    Wraps a ``redis.cluster.RedisCluster`` client and injects it into the base
    :class:`cachine.backends.redis.sync.RedisCache` with cluster-aware connectivity.

    Args:
        nodes (list[dict[str, Any]]): Startup node dicts with ``{"host": str, "port": int}``.
        username (str | None): Username for ACL-enabled Redis.
        password (str | None): Optional password used by the cluster.
        ssl (bool): Whether to use TLS.
        namespace (str | None): Optional key prefix (e.g., ``"myapp:"``).
        serializer (Any | None): Default serializer when per-call serializer is not provided.

    Notes:
        - Requires ``redis>=4`` with cluster support.
        - Only single-key operations are used to avoid cross-slot issues; tag indices
          are stored as per-tag sets under ``f"{namespace}tag::{tag}"``.
        - ``clear()`` iterates keys via SCAN and can be expensive on large keyspaces.
          ``dangerously_clear_all=True`` issues ``FLUSHDB``; use with care.

    Examples:
        >>> from cachine.backends.redis.cluster import RedisClusterCache
        >>> from cachine.serializers import JSONSerializer
        >>> cache = RedisClusterCache(
        ...     nodes=[{"host": "localhost", "port": 7000}, {"host": "localhost", "port": 7001}],
        ...     namespace="myapp",
        ...     serializer=JSONSerializer(),
        ... )
        >>> cache.set("k", {"v": 1}, ttl=60)
        >>> cache.get("k")
        {'v': 1}
    """

    def __init__(
        self,
        *,
        nodes: list[dict[str, Any]],
        username: Optional[str] = None,
        password: Optional[str] = None,
        ssl: bool = False,
        namespace: Optional[str] = None,
        serializer: Optional[Any] = None,
    ) -> None:
        try:
            from redis.cluster import RedisCluster
        except Exception as e:  # pragma: no cover
            raise RuntimeError("redis cluster client not available; install redis>=4 with cluster support") from e

        # Expect nodes as [{"host": ..., "port": ...}, ...]
        # redis-py API changed across versions; prefer ClusterNode if available (redis>=5),
        # otherwise pass startup_nodes (redis 4.x), and as a last resort connect to the first node.
        client = None
        try:
            try:
                from redis.cluster import ClusterNode as cluster_node_cls
            except Exception:
                cluster_node_cls = None  # type: ignore

            if cluster_node_cls is not None:
                cluster_nodes = [cluster_node_cls(n["host"], int(n.get("port", 6379))) for n in nodes]
                try:
                    client = RedisCluster(nodes=cluster_nodes, username=username, password=password, ssl=ssl)
                except TypeError:
                    # Some versions still expect startup_nodes as list of dicts
                    client = RedisCluster(
                        startup_nodes=[{"host": n["host"], "port": int(n.get("port", 6379))} for n in nodes],  # type: ignore[misc]
                        username=username,
                        password=password,
                        ssl=ssl,
                    )
            else:
                # Attempt redis 4.x style directly
                client = RedisCluster(  # type: ignore[unreachable]
                    startup_nodes=[{"host": n["host"], "port": int(n.get("port", 6379))} for n in nodes],
                    username=username,
                    password=password,
                    ssl=ssl,
                )
        except Exception:
            client = None

        if client is None:
            # Fallback: connect to first node; cluster should auto-discover
            first = nodes[0]
            client = RedisCluster(host=first["host"], port=int(first.get("port", 6379)), username=username, password=password, ssl=ssl)

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
