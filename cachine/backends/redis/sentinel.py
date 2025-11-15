from __future__ import annotations

from typing import Any, Optional

from .sync import RedisCache


class RedisSentinelCache(RedisCache):
    """Redis cache configured via Redis Sentinel.

    Uses ``redis.sentinel.Sentinel`` to obtain a master client and injects it
    into the base :class:`cachine.backends.redis.sync.RedisCache`.

    Args:
        sentinels (list[tuple[str, int]]): Sentinel host/port tuples.
        service_name (str): Sentinel service name (master alias).
        password (str | None): Password for Redis.
        db (int): Database index.
        ssl (bool): Whether to use TLS.
        namespace (str | None): Optional namespace prefix.
        serializer (Any | None): Default serializer for values.
    """

    def __init__(
        self,
        *,
        sentinels: list[tuple[str, int]],
        service_name: str,
        password: Optional[str] = None,
        db: int = 0,
        ssl: bool = False,
        namespace: Optional[str] = None,
        serializer: Optional[Any] = None,
    ) -> None:
        try:
            from redis.sentinel import Sentinel
        except Exception as e:  # pragma: no cover
            raise RuntimeError("redis.sentinel is not available; install redis>=4") from e

        sentinel = Sentinel(sentinels, socket_timeout=2, ssl=ssl)
        client = sentinel.master_for(service_name, db=db, password=password, ssl=ssl)
        super().__init__(
            host="",
            port=0,
            db=db,
            password=password,
            ssl=ssl,
            namespace=namespace,
            client=client,
            serializer=serializer,
        )
