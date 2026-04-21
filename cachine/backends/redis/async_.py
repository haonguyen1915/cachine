from __future__ import annotations

# pylint: disable=too-many-public-methods
import inspect
import json
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any, cast, overload

from cachine.core.types import HealthStatus
from cachine.exceptions import RedisURLParseError
from cachine.models.redis_config import (
    RedisClusterConfig,
    RedisConfig,
    RedisSentinelConfig,
    RedisSingleConfig,
)
from cachine.utils._deprecations import (
    MISSING,
    resolve_renamed_kwarg,
    warn_deprecated_kwarg,
    warn_deprecated_method,
)
from cachine.utils.helpers import to_seconds


class AsyncRedisCache:
    """Async Redis cache with TTL, counters, and tags.

    Mirrors :class:`cachine.backends.redis.sync.RedisCache` using
    ``redis.asyncio``. Supports kwargs shortcut for single-instance and a
    config object for Cluster/Sentinel topologies.
    """

    @overload
    def __init__(
        self,
        config: RedisConfig,
        *,
        namespace: str | None = None,
        serializer: Any | None = None,
        pubsub_channel: str | None = "cachine:invalidate",
        auto_publish_invalidations: bool = False,
    ) -> None: ...

    @overload
    def __init__(
        self,
        *,
        host: str,
        port: int = 6379,
        db: int = 0,
        password: str | None = None,
        username: str | None = None,
        ssl: bool = False,
        socket_timeout: float | None = None,
        socket_connect_timeout: float | None = None,
        retry_on_timeout: bool = False,
        decode_responses: bool = False,
        namespace: str | None = None,
        serializer: Any | None = None,
        pubsub_channel: str | None = "cachine:invalidate",
        auto_publish_invalidations: bool = False,
    ) -> None: ...

    def __init__(
        self,
        config: RedisConfig | None = None,
        *,
        host: str | None = None,
        port: int = 6379,
        db: int = 0,
        password: str | None = None,
        username: str | None = None,
        ssl: bool = False,
        socket_timeout: float | None = None,
        socket_connect_timeout: float | None = None,
        retry_on_timeout: bool = False,
        decode_responses: bool = False,
        namespace: str | None = None,
        serializer: Any | None = None,
        pubsub_channel: str | None = "cachine:invalidate",
        auto_publish_invalidations: bool = False,
    ) -> None:
        if config is not None and host is not None:
            raise TypeError("AsyncRedisCache: pass either `config` or `host=...` kwargs, not both")
        if config is None:
            if host is None:
                host = "localhost"
            config = RedisSingleConfig(
                host=host,
                port=port,
                db=db,
                password=password,
                username=username,
                ssl=ssl,
                socket_timeout=socket_timeout,
                socket_connect_timeout=socket_connect_timeout,
                retry_on_timeout=retry_on_timeout,
                decode_responses=decode_responses,
            )

        self._client: Any
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

    # ---- URL constructor ----
    @classmethod
    def from_url(
        cls,
        url: str,
        *,
        namespace: str | None = None,
        serializer: Any | None = None,
        pubsub_channel: str | None = "cachine:invalidate",
        auto_publish_invalidations: bool = False,
    ) -> AsyncRedisCache:
        """Construct an :class:`AsyncRedisCache` from a Redis connection URL."""
        from cachine.utils.redis_url import parse_redis_url

        scheme = url.split("://", 1)[0].lower() if "://" in url else ""
        if scheme and not scheme.startswith("redis"):
            raise RedisURLParseError(
                f"AsyncRedisCache.from_url received non-Redis URL ({scheme!r}); use AsyncSQLiteCache.from_url for sqlite:// URLs"
            )
        config = parse_redis_url(url)
        return cls(
            config,
            namespace=namespace,
            serializer=serializer,
            pubsub_channel=pubsub_channel,
            auto_publish_invalidations=auto_publish_invalidations,
        )

    # ---- Basic ops ----
    async def get(self, key: str, default: Any = None, *, serializer: Any = MISSING) -> Any:
        """Get a value by key."""
        if serializer is not MISSING:
            warn_deprecated_kwarg(
                name="serializer",
                owner="AsyncRedisCache.get",
                replacement="configure serializer on the cache constructor",
            )
        k = self._ns + key
        client = self._client
        raw = await client.get(k)
        if raw is None:
            return default
        ser = serializer if serializer is not MISSING and serializer is not None else self._serializer
        if ser is not None:
            try:
                return ser.loads(raw)
            except Exception:
                return raw
        return raw

    async def set(
        self,
        key: str,
        value: Any,
        *,
        ttl: int | timedelta | None = None,
        serializer: Any = MISSING,
    ) -> None:
        """Set a value by key."""
        if serializer is not MISSING:
            warn_deprecated_kwarg(
                name="serializer",
                owner="AsyncRedisCache.set",
                replacement="configure serializer on the cache constructor",
            )
        k = self._ns + key
        client = self._client
        ser = serializer if serializer is not MISSING and serializer is not None else self._serializer
        payload = ser.dumps(value) if ser is not None else value
        seconds = to_seconds(ttl)
        if seconds is not None:
            await client.set(k, payload, ex=int(seconds))
        else:
            await client.set(k, payload)

    async def delete(self, key: str) -> bool:
        """Delete a key."""
        k = self._ns + key
        client = self._client
        return bool(await client.delete(k))

    async def exists(self, key: str) -> bool:
        """Check key existence."""
        k = self._ns + key
        client = self._client
        res = await client.exists(k)
        try:
            return bool(int(res))
        except Exception:
            return bool(res)

    async def clear(self, *, all: bool = False, dangerously_clear_all: Any = MISSING) -> None:
        """Clear keys in the current namespace or flush the DB."""
        force = resolve_renamed_kwarg(
            old_name="dangerously_clear_all",
            new_name="all",
            old_value=dangerously_clear_all,
            new_value=all,
            owner="AsyncRedisCache.clear",
            new_default=False,
        )
        force = bool(force) if force is not None else False
        client = self._client
        if force:
            try:
                await client.flushdb()
            except Exception:
                pass
            return
        if not self._ns:
            raise RuntimeError("clear() requires a namespace or pass all=True")
        pattern = f"{self._ns}*"
        keys: list[str] = []
        try:
            async for k in client.scan_iter(match=pattern):
                keys.append(k.decode("utf-8") if isinstance(k, bytes | bytearray) else k)
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

    # ---- Enrichment ----
    async def get_or_set(  # pylint: disable=unused-argument
        self,
        key: str,
        factory: Any,
        *,
        ttl: int | timedelta | None = None,
        jitter: int | None = None,  # noqa: ARG002
    ) -> Any:
        """Get or compute-and-set a value."""
        sentinel = object()
        val = await self.get(key, default=sentinel)
        if val is not sentinel:
            return val
        computed = factory() if callable(factory) else factory
        if inspect.isawaitable(computed):
            computed = await computed
        await self.set(key, computed, ttl=ttl)
        return computed

    # ---- TTL management ----
    async def expire(self, key: str, *, ttl: int | timedelta) -> bool:
        """Set a relative expiration."""
        k = self._ns + key
        client = self._client
        seconds = int(ttl.total_seconds()) if isinstance(ttl, timedelta) else int(ttl)
        if seconds <= 0:
            await client.delete(k)
            return True
        return bool(await client.expire(k, seconds))

    async def expire_at(self, key: str, when: datetime) -> bool:
        """Set an absolute expiration."""
        k = self._ns + key
        client = self._client
        ts = int(when.timestamp())
        return bool(await client.expireat(k, ts))

    async def touch(self, key: str, *, ttl: int | timedelta | None = None) -> bool:
        """Refresh presence or set a new TTL."""
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

    async def ttl(self, key: str) -> int | None:
        """Get remaining TTL."""
        k = self._ns + key
        client = self._client
        res = await client.ttl(k)
        try:
            val = int(res)
        except Exception:
            return None
        return val if val >= 0 else None

    async def persist(self, key: str) -> bool:
        """Remove expiration from a key."""
        k = self._ns + key
        client = self._client
        try:
            return bool(await client.persist(k))
        except Exception:
            ttl = await client.ttl(k)
            if ttl is None or (isinstance(ttl, int) and ttl < 0):
                return False
            try:
                await client.pexpire(k, 0)
            except Exception:
                pass
            return True

    # ---- Counters ----
    async def incr(
        self,
        key: str,
        *,
        delta: int = 1,
        ttl_if_new: int | timedelta | None = None,
        ttl_on_create: Any = MISSING,
    ) -> int:
        """Increment an integer counter by ``delta``."""
        effective_ttl = resolve_renamed_kwarg(
            old_name="ttl_on_create",
            new_name="ttl_if_new",
            old_value=ttl_on_create,
            new_value=ttl_if_new,
            owner="AsyncRedisCache.incr",
        )
        k = self._ns + key
        client = self._client
        if effective_ttl is None:
            return int(await client.incrby(k, int(delta)))
        pexpire_ms = int(effective_ttl.total_seconds() * 1000) if isinstance(effective_ttl, timedelta) else int(effective_ttl) * 1000
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

    async def decr(self, key: str, *, delta: int = 1) -> int:
        """Decrement an integer counter."""
        return await self.incr(key, delta=-int(delta))

    # ---- Tags ----
    async def invalidate_tags(self, tags: list[str], publish: bool | None = None) -> int:
        """Invalidate keys by tags."""
        client = self._client
        deleted = 0
        for tag in tags:
            tkey = f"{self._ns}tag:{tag}"
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

        should_publish = publish if publish is not None else self._auto_publish_invalidations
        if should_publish and self._pubsub_channel:
            await self.publish_invalidation(tags)

        return deleted

    async def add_tags(self, key: str, tags: list[str], *, ttl: int | timedelta | None = None) -> None:
        """Associate ``tags`` with a key."""
        client = self._client
        k = self._ns + key
        ttl_seconds = to_seconds(ttl) if ttl is not None else None

        for tag in tags:
            tkey = f"{self._ns}tag:{tag}"
            try:
                await client.sadd(tkey, k)
                if ttl_seconds is not None and ttl_seconds > 0:
                    await client.expire(tkey, int(ttl_seconds))
            except Exception:
                pass

    # ---- Pub/Sub ----
    async def publish_invalidation(self, tags: list[str]) -> None:
        """Publish a tag invalidation event."""
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
        channel: str | None = None,
    ) -> None:
        """Subscribe to tag invalidation events (blocking)."""
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

    # ---- Health / lifecycle ----
    async def health(self) -> HealthStatus:
        """Return cache health status."""
        try:
            ok = bool(await self._client.ping())
        except Exception:
            ok = False
        return {"healthy": ok, "latency_ms": 0.0, "backend": "redis"}

    async def healthy(self) -> bool:
        """Return ``True`` if the cache is healthy."""
        s = await self.health()
        return bool(s.get("healthy", False))

    # Deprecated aliases
    async def ping(self) -> HealthStatus:
        """Deprecated alias for :meth:`health`."""
        warn_deprecated_method(name="ping", owner="AsyncRedisCache", replacement="health")
        return await self.health()

    async def ping_ok(self) -> bool:
        """Deprecated alias for :meth:`healthy`."""
        warn_deprecated_method(name="ping_ok", owner="AsyncRedisCache", replacement="healthy")
        return await self.healthy()

    async def close(self) -> None:
        """Close the underlying client."""
        try:
            if hasattr(self._client, "aclose"):
                await self._client.aclose()
            else:
                await self._client.close()
        except Exception:
            pass

    def get_stats(self) -> dict[str, Any] | None:
        """Return ``None``; middleware may override."""
        return None

    # ---- Async context manager ----
    async def __aenter__(self) -> AsyncRedisCache:
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self.close()

    @staticmethod
    def _create_single_client(config: RedisSingleConfig) -> Any:
        try:
            from redis.asyncio import Redis
        except ImportError as e:
            raise RuntimeError("redis.asyncio is not available; install with: `pip install redis`") from e
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

        for k, v in config.extra.items():
            kwargs.setdefault(k, v)

        return Redis(**kwargs)

    @staticmethod
    def _create_cluster_client(config: RedisClusterConfig) -> Any:
        try:
            from redis.asyncio.cluster import ClusterNode, RedisCluster
        except Exception as e:  # pragma: no cover
            raise RuntimeError("redis.asyncio cluster not available; install with: `pip install redis`") from e

        nodes = [{"host": node.host, "port": node.port} for node in config.nodes]
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

        return RedisCluster(startup_nodes=cluster_nodes, **kwargs)

    @staticmethod
    def _create_sentinel_client(config: RedisSentinelConfig) -> Any:
        try:
            from redis.asyncio.sentinel import Sentinel
        except Exception as e:  # pragma: no cover
            raise RuntimeError("redis.asyncio.sentinel not available; install with: `pip install redis`") from e

        st = 2 if config.socket_timeout is None else float(config.socket_timeout)
        sentinel = Sentinel(list(config.sentinels), socket_timeout=st, ssl=config.ssl)
        return sentinel.master_for(
            config.service_name,
            db=config.db,
            username=config.username,
            password=config.password,
            ssl=config.ssl,
        )
