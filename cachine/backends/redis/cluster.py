from __future__ import annotations

from typing import Any, Optional

from .sync import RedisCache


class RedisClusterCache(RedisCache):
    """Redis-backed cache configured for Redis Cluster.

    This class wraps a ``redis.cluster.RedisCluster`` client and injects it into
    the base :class:`~cachine.backends.redis.sync.RedisCache`, providing the same
    caching API (``get``, ``set``, ``ttl``, ``persist``, ``incr``/``decr``,
    tag invalidation, etc.) with cluster-aware connectivity.

    Parameters
    - nodes: list of startup node dictionaries, each with ``{"host": str, "port": int}``.
      Example: ``[{"host": "localhost", "port": 7000}, {"host": "localhost", "port": 7001}]``.
    - password: optional password used by the cluster.
    - ssl: whether to use TLS.
    - namespace: optional key prefix applied to all keys (e.g., ``"myapp:"``).
    - serializer: default serializer to use when calls do not provide a per-call serializer
      (e.g., :class:`~cachine.serializers.JSONSerializer`, :class:`~cachine.serializers.MsgPackSerializer`).

    Notes
    - Requires ``redis>=4`` with cluster support enabled.
    - Keys are automatically distributed across hash slots by Redis. The cache uses
      single-key operations and avoids multi-key commands that would violate hash-slot
      constraints. Tag indices are stored as per-tag sets under
      ``f"{namespace}tag::${tag}"``; invalidation iterates and deletes member keys individually.
    - ``clear()`` with a namespace performs a SCAN across cluster nodes via the client’s
      iterator and deletes matching keys. This can be expensive on large keyspaces—use with care.
      ``dangerously_clear_all=True`` will issue a ``FLUSHDB`` on the selected database for each node;
      do not use in production unless you understand the impact.

    Example
    >>> from cachine.backends.redis.cluster import RedisClusterCache
    >>> from cachine.serializers import JSONSerializer
    >>> cache = RedisClusterCache(
    ...     nodes=[{"host": "localhost", "port": 7000}, {"host": "localhost", "port": 7001}, {"host": "localhost", "port": 7002}],
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
