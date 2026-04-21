"""Advanced Redis construction using a config dataclass.

Use ``RedisSingleConfig``/``RedisClusterConfig``/``RedisSentinelConfig`` when
you need SSL, tuned timeouts, or cluster/sentinel topology. For simple cases
(single host) prefer the ``RedisCache(host=..., namespace=...)`` kwargs form.
"""

from __future__ import annotations

from cachine import RedisCache
from cachine.models import RedisSingleConfig


def main() -> None:
    config = RedisSingleConfig(
        host="localhost",
        port=6379,
        db=0,
        ssl=False,
        socket_timeout=5.0,
        socket_connect_timeout=2.0,
    )

    with RedisCache(config, namespace="myapp") as cache:
        cache.set("config", {"debug": True}, ttl=3600)
        print(cache.get("config"))


if __name__ == "__main__":
    main()
