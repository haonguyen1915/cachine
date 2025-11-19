from __future__ import annotations

# pylint: disable=too-many-public-methods
import inspect
import json
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any, Optional, cast

from cachine.core.types import HealthStatus
from cachine.models.redis_config import RedisClusterConfig, RedisConfig, RedisSentinelConfig, RedisSingleConfig
from cachine.utils.helpers import to_seconds


class AsyncRedisCache:
    """Async Redis cache with TTL, counters, and tags.

    Mirrors :class:`cachine.backends.redis.sync.RedisCache` with ``async``/``await``
    operations using ``redis.asyncio``.

    Args:
        config (RedisConfig): Redis configuration object (RedisSingleConfig, RedisClusterConfig, or RedisSentinelConfig).
        namespace (str | None): Optional namespace prefix.
        serializer (Any | None): Default serializer for values.
        pubsub_channel (str | None): Pub/Sub channel for tag invalidation events. Defaults to "cachine:invalidate".
        auto_publish_invalidations (bool): Automatically publish tag invalidation events. Defaults to False.

    Examples:
        >>> from cachine.models.redis_config import RedisSingleConfig
        >>> config = RedisSingleConfig(host="localhost", port=6379, db=0)
        >>> cache = AsyncRedisCache(config, namespace="myapp")
        >>> await cache.set("key", "value", ttl=60)
        >>> await cache.get("key")
        'value'
    """

    def __init__(
        self,
        config: RedisConfig,
        *,
        namespace: Optional[str] = None,
        serializer: Optional[Any] = None,
        pubsub_channel: Optional[str] = "cachine:invalidate",
        auto_publish_invalidations: bool = False,
    ) -> None:
        # Client attribute (runtime async redis client)
        self._client: Any
        # Create appropriate client based on config type
        if isinstance(config, RedisSingleConfig):
            self._client = self._create_single_client(config)
        elif isinstance(config, RedisClusterConfig):
            self._client = self._create_cluster_client(config)
        elif isinstance(config, RedisSentinelConfig):
            self._client = self._create_sentinel_client(config)
        else:
            raise TypeError(f"Unsupported config type: {type(config)}")

        self._config = config
        self._ns = f"{namespace}:" if namespace else ""
        self._serializer = serializer
        self._pubsub_channel = pubsub_channel
        self._auto_publish_invalidations = auto_publish_invalidations

    # Basic ops
    async def get(self, key: str, default: Any = None, serializer: Any = None) -> Any:
        """Get a value by key.

        Args:
            key (str): Cache key.
            default (Any, optional): Value to return if key is missing.
            serializer (Any, optional): Serializer to decode bytes; defaults to instance serializer.

        Returns:
            Any: Decoded value or ``default``.
        """
        k = self._ns + key
        client = self._client
        raw = await client.get(k)
        if raw is None:
            return default
        ser = serializer or self._serializer
        if ser is not None:
            try:
                return ser.loads(raw)
            except Exception:
                return raw
        return raw

    async def set(self, key: str, value: Any, ttl: Optional[int | timedelta] = None, serializer: Any = None) -> None:
        """Set a value by key.

        Args:
            key (str): Cache key.
            value (Any): Value to store.
            ttl (int | timedelta | None): Optional time-to-live.
            serializer (Any, optional): Serializer to encode value; defaults to instance serializer.

        Returns:
            None
        """
        k = self._ns + key
        client = self._client
        ser = serializer or self._serializer
        payload = ser.dumps(value) if ser is not None else value
        seconds = int(ttl.total_seconds()) if isinstance(ttl, timedelta) else (int(ttl) if ttl is not None else None)
        if seconds is not None:
            await client.set(k, payload, ex=seconds)
        else:
            await client.set(k, payload)

    async def delete(self, key: str) -> bool:
        """Delete a key.

        Args:
            key (str): Cache key.

        Returns:
            bool: True if key existed.
        """
        k = self._ns + key
        client = self._client
        return bool(await client.delete(k))

    async def exists(self, key: str) -> bool:
        """Check key existence.

        Args:
            key (str): Cache key.

        Returns:
            bool: True if key exists.
        """
        k = self._ns + key
        client = self._client
        res = await client.exists(k)
        try:
            return bool(int(res))
        except Exception:
            return bool(res)

    async def clear(self, dangerously_clear_all: bool = False) -> None:
        """Clear keys in namespace or flush DB.

        Args:
            dangerously_clear_all (bool): When True, flushes the entire DB. When False,
                requires a namespace and removes only keys in that namespace.

        Returns:
            None
        """
        client = self._client
        if dangerously_clear_all:
            try:
                await client.flushdb()
            except Exception:
                pass
            return
        if not self._ns:
            raise RuntimeError("clear() requires a namespace or set dangerously_clear_all=True")
        pattern = f"{self._ns}*"
        keys = []
        try:
            async for k in client.scan_iter(match=pattern):
                if isinstance(k, bytes | bytearray):
                    k = k.decode("utf-8")
                keys.append(k)
        except Exception:
            keys = []
        if keys:
            try:
                del_many = getattr(client, "delete_many", None)
                if del_many is not None:
                    await del_many(*keys)
                else:
                    await client.delete(*keys)
            except Exception:
                for k in keys:
                    try:
                        await client.delete(k)
                    except Exception:
                        pass

    # Enrichment
    async def get_or_set(self, key: str, factory: Any, ttl: Optional[int | timedelta] = None, jitter: Optional[int] = None) -> Any:  # pylint: disable=unused-argument
        """Get or compute-and-set a value.

        Args:
            key (str): Cache key.
            factory (Any): Callable or value used to compute when missing.
            ttl (int | timedelta | None): Optional TTL for the stored value.
            jitter (int | None): Ignored by this implementation.

        Returns:
            Any: Existing value if present; otherwise the computed value.
        """
        sentinel = object()
        val = await self.get(key, default=sentinel)
        if val is not sentinel:
            return val
        computed = factory() if callable(factory) else factory
        if inspect.isawaitable(computed):
            computed = await computed
        await self.set(key, computed, ttl=ttl)
        return computed

    # TTL management
    async def expire(self, key: str, ttl: int | timedelta) -> bool:
        """Set a relative expiration.

        Args:
            key (str): Cache key.
            ttl (int | timedelta): Relative TTL; ``<= 0`` deletes the key.

        Returns:
            bool: True on success (including deletion when ttl <= 0).
        """
        k = self._ns + key
        client = self._client
        seconds = int(ttl.total_seconds()) if isinstance(ttl, timedelta) else int(ttl)
        if seconds <= 0:
            await client.delete(k)
            return True
        return bool(await client.expire(k, seconds))

    async def expire_at(self, key: str, when: datetime) -> bool:
        """Set an absolute expiration (UTC).

        Args:
            key (str): Cache key.
            when (datetime): Absolute UTC expiration time.

        Returns:
            bool: True if expiration was set.
        """
        k = self._ns + key
        client = self._client
        ts = int(when.timestamp())
        return bool(await client.expireat(k, ts))

    async def touch(self, key: str, ttl: Optional[int | timedelta] = None) -> bool:
        """Refresh presence or set a new TTL.

        Args:
            key (str): Cache key.
            ttl (int | timedelta | None): Optional TTL to set; when None, attempts
                a TOUCH operation or falls back to existence check.

        Returns:
            bool: True if key exists (and TTL was updated when provided).
        """
        k = self._ns + key
        client = self._client
        if ttl is None:
            try:
                return bool(await client.touch(k))
            except Exception:
                return await self.exists(key)
        seconds = int(ttl.total_seconds()) if isinstance(ttl, timedelta) else int(ttl)
        if seconds <= 0:
            await client.delete(k)
            return True
        return bool(await client.expire(k, seconds))

    async def ttl(self, key: str) -> Optional[int]:
        """Get remaining TTL.

        Args:
            key (str): Cache key.

        Returns:
            int | None: Remaining seconds; None if no TTL or missing.
        """
        k = self._ns + key
        client = self._client
        res = await client.ttl(k)
        try:
            val = int(res)
        except Exception:
            return None
        if val < 0:
            return None
        return val

    async def persist(self, key: str) -> bool:
        """Remove expiration from a key.

        Args:
            key (str): Cache key.

        Returns:
            bool: True if TTL existed and was removed.
        """
        k = self._ns + key
        client = self._client
        try:
            res = await client.persist(k)
            return bool(res)
        except Exception:
            ttl = await client.ttl(k)
            if ttl is None or (isinstance(ttl, int) and ttl < 0):
                return False
            try:
                await client.pexpire(k, 0)
            except Exception:
                pass
            return True

    # Counters
    async def incr(self, key: str, delta: int = 1, ttl_on_create: Optional[int | timedelta] = None) -> int:
        """Increment an integer value by ``delta``.

        Args:
            key (str): Cache key.
            delta (int): Increment amount.
            ttl_on_create (int | timedelta | None): TTL applied only on creation.

        Returns:
            int: The new integer value.
        """
        k = self._ns + key
        client = self._client
        if ttl_on_create is None:
            return int(await client.incrby(k, int(delta)))
        pexpire_ms = int(ttl_on_create.total_seconds() * 1000) if isinstance(ttl_on_create, timedelta) else int(ttl_on_create) * 1000
        script = (
            "local exists = redis.call('EXISTS', KEYS[1])\n"
            "local val = redis.call('INCRBY', KEYS[1], ARGV[1])\n"
            "if exists == 0 and tonumber(ARGV[2]) and tonumber(ARGV[2]) > 0 then\n"
            "  redis.call('PEXPIRE', KEYS[1], ARGV[2])\n"
            "end\n"
            "return val\n"
        )
        try:
            return int(await client.eval(script, 1, k, int(delta), pexpire_ms))
        except Exception:
            existed = bool(await client.exists(k))
            val = int(await client.incrby(k, int(delta)))
            if not existed and pexpire_ms > 0:
                try:
                    await client.pexpire(k, pexpire_ms)
                except Exception:
                    await client.expire(k, max(pexpire_ms // 1000, 1))
            return val

    async def decr(self, key: str, delta: int = 1) -> int:
        """Decrement an integer value.

        Args:
            key (str): Cache key.
            delta (int): Decrement amount.

        Returns:
            int: The new integer value.
        """
        return await self.incr(key, delta=-int(delta))

    # Tags
    async def invalidate_tags(self, tags: list[str], publish: Optional[bool] = None) -> int:
        """Invalidate keys by tags.

        Args:
            tags (list[str]): Tags to invalidate.
            publish (bool | None): Whether to publish invalidation event. If None, uses auto_publish_invalidations setting.

        Returns:
            int: Number of keys deleted across all tags.
        """
        client = self._client
        deleted = 0
        for tag in tags:
            tkey = f"{self._ns}tag::{tag}"
            try:
                members = await client.smembers(tkey)
            except Exception:
                members = set()
            for mk in list(members):
                key_name = mk.decode("utf-8") if isinstance(mk, bytes | bytearray) else mk
                try:
                    await client.delete(key_name)
                    deleted += 1
                except Exception:
                    pass
            try:
                await client.delete(tkey)
            except Exception:
                pass

        # Publish invalidation event if enabled
        should_publish = publish if publish is not None else self._auto_publish_invalidations
        if should_publish and self._pubsub_channel:
            await self.publish_invalidation(tags)

        return deleted

    async def add_tags(self, key: str, tags: list[str], ttl: Optional[int | timedelta] = None) -> None:
        """Associate tags with a key.

        Args:
            key (str): Stored cache key.
            tags (list[str]): Tags to associate.
            ttl (int | timedelta | None): Optional TTL for tag associations.
                If provided, tag sets will expire after this duration.

        Returns:
            None
        """
        client = self._client
        k = self._ns + key
        ttl_seconds = to_seconds(ttl) if ttl is not None else None

        for tag in tags:
            tkey = f"{self._ns}tag:{tag}"  # Consistent with sync version
            try:
                await client.sadd(tkey, k)
                # Set TTL on tag set if provided
                if ttl_seconds is not None and ttl_seconds > 0:
                    await client.expire(tkey, int(ttl_seconds))
            except Exception:
                pass

    # Pub/Sub
    async def publish_invalidation(self, tags: list[str]) -> None:
        """Publish a tag invalidation event to the Pub/Sub channel.

        Args:
            tags (list[str]): Tags to include in the invalidation event.

        Returns:
            None

        Examples:
            >>> await cache.publish_invalidation(["user:123", "product:456"])
        """
        if not self._pubsub_channel:
            return

        payload = {
            "type": "invalidate_tags",
            "namespace": self._ns.rstrip(":") if self._ns else None,
            "tags": list(tags),
        }
        try:
            data = json.dumps(payload)
            await self._client.publish(self._pubsub_channel, data)
        except Exception:
            pass

    async def subscribe_invalidations(
        self,
        handler: Callable[[dict[str, Any]], Any],
        *,
        channel: Optional[str] = None,
    ) -> None:
        """Subscribe to tag invalidation events and process them with a handler.

        This is a blocking operation that listens for invalidation events on the
        Pub/Sub channel and invokes the handler for each valid event.

        Args:
            handler (Callable[[dict[str, Any]], Any]): Function called with each event.
                Can be sync or async. Receives event dict with keys: type, namespace, tags.
            channel (str | None): Override the Pub/Sub channel. Uses instance channel if None.

        Returns:
            None

        Examples:
            >>> async def handle_event(event):
            ...     tags = event.get("tags", [])
            ...     print(f"Invalidating tags: {tags}")
            >>> await cache.subscribe_invalidations(handle_event)
        """
        target_channel = channel or self._pubsub_channel
        if not target_channel:
            return

        try:
            pubsub = self._client.pubsub()
            await pubsub.subscribe(target_channel)
            async for msg in pubsub.listen():
                if not msg or msg.get("type") != "message":
                    continue
                try:
                    event = json.loads(msg.get("data"))
                except Exception:
                    continue
                res = handler(event)
                if inspect.isawaitable(res):
                    await res
        except Exception:
            pass

    # Health / lifecycle
    async def ping(self) -> HealthStatus:
        """Check health.

        Returns:
            dict[str, Any]: Health payload with ``healthy``, ``latency_ms``, and ``backend``.
        """
        ok = False
        try:
            ok = await self._client.ping()
        except Exception:
            ok = False
        return {"healthy": bool(ok), "latency_ms": 0.0, "backend": "redis"}

    async def ping_ok(self) -> bool:
        """Return a boolean health indicator.

        Returns:
            bool: True if healthy.
        """
        s = await self.ping()
        return bool(s.get("healthy", False))

    async def close(self) -> None:
        """Close underlying client (async)."""
        try:
            # Try aclose() first (redis-py v5+), fall back to close() for older versions
            if hasattr(self._client, "aclose"):
                await self._client.aclose()
            else:
                await self._client.close()
        except Exception:
            pass

    def get_stats(self) -> Optional[dict[str, Any]]:
        """Get cache statistics.

        Returns:
            Optional[dict[str, Any]]: None for base cache (no stats collected).
                Middleware may override to return collected metrics.
        """
        return None

    # Async context manager
    async def __aenter__(self) -> AsyncRedisCache:
        """Enter async context manager.

        Returns:
            AsyncRedisCache: This cache instance.
        """
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        """Exit async context manager and close connections."""
        await self.close()

    @staticmethod
    def _create_single_client(config: RedisSingleConfig) -> Any:
        """Create client for single Redis instance.

        Args:
            config (RedisSingleConfig): Single instance configuration.

        Returns:
            Any: AsyncRedisClient wrapper instance.
        """
        try:
            from redis.asyncio import Redis
        except ImportError as e:
            raise RuntimeError("redis.asyncio.Redis not available; install with: `pip install redis`") from e
        kwargs: dict[str, Any] = {
            "host": config.host,
            "port": int(config.port),
            "db": int(config.db),
            "ssl": bool(config.ssl),
            "decode_responses": bool(config.decode_responses),
        }
        if config.username is not None:
            kwargs["username"] = config.username
        if config.password is not None:
            kwargs["password"] = config.password
        if config.socket_timeout is not None:
            kwargs["socket_timeout"] = float(config.socket_timeout)
        if config.socket_connect_timeout is not None:
            kwargs["socket_connect_timeout"] = float(config.socket_connect_timeout)
        if config.retry_on_timeout:
            kwargs["retry_on_timeout"] = True

        # Merge any additional parameters
        for k, v in config.extra.items():
            kwargs.setdefault(k, v)

        return Redis(**kwargs)

    @staticmethod
    def _create_cluster_client(config: RedisClusterConfig) -> Any:
        """Create client for Redis Cluster.

        Args:
            config (RedisClusterConfig): Cluster configuration.

        Returns:
            Any: RedisCluster client instance.

        Raises:
            RuntimeError: If redis cluster client is not available.
        """
        try:
            from redis.asyncio.cluster import ClusterNode, RedisCluster
        except Exception as e:  # pragma: no cover
            raise RuntimeError("redis.asyncio not available; install with: `pip install redis`") from e

        # Convert nodes to dict format for redis-py
        nodes = [{"host": node.host, "port": node.port} for node in config.nodes]

        # Try different redis-py API versions
        # Help type checker: ensure proper types for ClusterNode
        cluster_nodes = [ClusterNode(cast(str, n["host"]), int(cast(Any, n.get("port", 6379)))) for n in nodes]
        kwargs: dict[str, Any] = {
            "username": config.username,
            "password": config.password,
            "ssl": config.ssl,
        }
        if getattr(config, "decode_responses", False):
            kwargs["decode_responses"] = True
        if getattr(config, "socket_timeout", None) is not None:
            kwargs["socket_timeout"] = float(config.socket_timeout)  # type: ignore[arg-type]
        if getattr(config, "socket_connect_timeout", None) is not None:
            kwargs["socket_connect_timeout"] = float(config.socket_connect_timeout)  # type: ignore[arg-type]
        if getattr(config, "retry_on_timeout", False):
            kwargs["retry_on_timeout"] = True
        try:  # pragma: no cover
            import redis as _redis

            ver = getattr(_redis, "__version__", "")
            head = ver.split(".", maxsplit=1)[0] if ver else ""
            major = int(head) if head.isdigit() else None
            if major is not None and major >= 6:
                kwargs.pop("retry_on_timeout", None)
        except Exception:
            pass

        client = RedisCluster(startup_nodes=cluster_nodes, **kwargs)
        return client

    @staticmethod
    def _create_sentinel_client(config: RedisSentinelConfig) -> Any:
        """Create client for Redis Sentinel.

        Args:
            config (RedisSentinelConfig): Sentinel configuration.

        Returns:
            Any: Redis master client from Sentinel.

        Raises:
            RuntimeError: If redis.asyncio.sentinel is not available.
        """
        try:
            from redis.asyncio.sentinel import Sentinel
        except Exception as e:  # pragma: no cover
            raise RuntimeError("redis.asyncio not available; install with: `pip install redis`") from e

        st = 2 if config.socket_timeout is None else float(config.socket_timeout)
        sentinel = Sentinel(list(config.sentinels), socket_timeout=st, ssl=config.ssl)
        return sentinel.master_for(
            config.service_name,
            db=config.db,
            username=config.username,
            password=config.password,
            ssl=config.ssl,
        )
