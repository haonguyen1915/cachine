from __future__ import annotations

# pylint: disable=too-many-public-methods
import inspect
from datetime import datetime, timedelta
from typing import Any, Optional


class AsyncRedisClient:
    def __init__(
        self,
        *,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        ssl: bool = False,
        decode_responses: bool = False,
    ) -> None:
        try:
            from redis.asyncio import Redis
        except Exception as e:  # pragma: no cover
            raise RuntimeError("redis.asyncio not available; install redis>=4") from e
        self._client = Redis(host=host, port=port, db=db, password=password, ssl=ssl, decode_responses=decode_responses)

    # Basic ops
    async def get(self, name: str) -> Any:
        return await self._client.get(name)

    async def set(self, name: str, value: Any, *, ex: Optional[int] = None, px: Optional[int] = None) -> bool:
        return bool(await self._client.set(name, value, ex=ex, px=px))

    async def delete(self, name: str) -> int:
        return int(await self._client.delete(name))

    async def exists(self, name: str) -> int:
        return int(await self._client.exists(name))

    async def ttl(self, name: str) -> int:
        return int(await self._client.ttl(name))

    async def expire(self, name: str, seconds: int) -> int:
        return int(await self._client.expire(name, seconds))

    async def expireat(self, name: str, timestamp: int) -> int:
        return int(await self._client.expireat(name, timestamp))

    async def pexpire(self, name: str, ms: int) -> int:
        return int(await self._client.pexpire(name, ms))

    async def persist(self, name: str) -> int:
        return int(await self._client.persist(name))

    async def incrby(self, name: str, delta: int) -> int:
        return int(await self._client.incrby(name, delta))

    async def eval(self, script: str, numkeys: int, *keys_and_args: Any) -> Any:
        return await self._client.eval(script, numkeys, *keys_and_args)  # type: ignore[misc]

    async def touch(self, name: str) -> int:
        try:
            return int(await self._client.touch(name))
        except Exception:
            return 1 if await self._client.exists(name) else 0

    async def smembers(self, name: str) -> set:  # type: ignore[valid-type]
        return set(await self._client.smembers(name))  # type: ignore[misc]

    async def sadd(self, name: str, *values: Any) -> int:
        return int(await self._client.sadd(name, *values))  # type: ignore[misc]

    async def scan_iter(self, match: str) -> Any:
        async for key in self._client.scan_iter(match=match):
            yield key

    async def delete_many(self, *names: str) -> int:
        if not names:
            return 0
        return int(await self._client.delete(*names))

    async def flushdb(self) -> None:
        await self._client.flushdb()

    async def publish(self, channel: str, data: str) -> int:
        return int(await self._client.publish(channel, data))

    def pubsub(self) -> Any:  # pragma: no cover
        return self._client.pubsub()

    async def ping(self) -> bool:
        try:
            return bool(await self._client.ping())  # type: ignore[misc]
        except Exception:
            return False

    async def close(self) -> None:
        try:
            await self._client.close()
        except Exception:
            pass


class AsyncRedisCache:
    def __init__(
        self,
        *,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        ssl: bool = False,
        namespace: Optional[str] = None,
        client: Optional[Any] = None,
        serializer: Optional[Any] = None,
    ) -> None:
        self._ns = f"{namespace}:" if namespace else ""
        self._cfg = {"host": host, "port": port, "db": db, "ssl": ssl}
        self._password = password
        self._client = client
        self._serializer = serializer

    # Basic ops
    async def get(self, key: str, default: Any = None, *, serializer: Any = None) -> Any:
        k = self._ns + key
        client = await self._require_client()
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

    async def set(self, key: str, value: Any, *, ttl: Optional[int | timedelta] = None, serializer: Any = None) -> None:
        k = self._ns + key
        client = await self._require_client()
        ser = serializer or self._serializer
        payload = ser.dumps(value) if ser is not None else value
        seconds = int(ttl.total_seconds()) if isinstance(ttl, timedelta) else (int(ttl) if ttl is not None else None)
        if seconds is not None:
            await client.set(k, payload, ex=seconds)
        else:
            await client.set(k, payload)

    async def delete(self, key: str) -> bool:
        k = self._ns + key
        client = await self._require_client()
        return bool(await client.delete(k))

    async def exists(self, key: str) -> bool:
        k = self._ns + key
        client = await self._require_client()
        res = await client.exists(k)
        try:
            return bool(int(res))
        except Exception:
            return bool(res)

    async def clear(self, *, dangerously_clear_all: bool = False) -> None:
        client = await self._require_client()
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
                await client.delete_many(*keys)
            except Exception:
                for k in keys:
                    try:
                        await client.delete(k)
                    except Exception:
                        pass

    # Enrichment
    async def get_or_set(self, key: str, factory: Any, *, ttl: Optional[int | timedelta] = None, jitter: Optional[int] = None) -> Any:  # pylint: disable=unused-argument
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
    async def expire(self, key: str, *, ttl: int | timedelta) -> bool:
        k = self._ns + key
        client = await self._require_client()
        seconds = int(ttl.total_seconds()) if isinstance(ttl, timedelta) else int(ttl)
        if seconds <= 0:
            await client.delete(k)
            return True
        return bool(await client.expire(k, seconds))

    async def expire_at(self, key: str, when: datetime) -> bool:
        k = self._ns + key
        client = await self._require_client()
        ts = int(when.timestamp())
        return bool(await client.expireat(k, ts))

    async def touch(self, key: str, *, ttl: Optional[int | timedelta] = None) -> bool:
        k = self._ns + key
        client = await self._require_client()
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
        k = self._ns + key
        client = await self._require_client()
        res = await client.ttl(k)
        try:
            val = int(res)
        except Exception:
            return None
        if val < 0:
            return None
        return val

    async def persist(self, key: str) -> bool:
        k = self._ns + key
        client = await self._require_client()
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
    async def incr(self, key: str, *, delta: int = 1, ttl_on_create: Optional[int | timedelta] = None) -> int:
        k = self._ns + key
        client = await self._require_client()
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

    async def decr(self, key: str, *, delta: int = 1) -> int:
        return await self.incr(key, delta=-int(delta))

    # Tags
    async def invalidate_tags(self, tags: list[str]) -> int:
        client = await self._require_client()
        deleted = 0
        for tag in tags:
            tkey = f"{self._ns}tag::{tag}"
            try:
                members = await client.smembers(tkey)
            except Exception:
                members = set()
            for mk in members:
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
        return deleted

    async def add_tags(self, key: str, tags: list[str]) -> None:
        client = await self._require_client()
        k = self._ns + key
        for tag in tags:
            tkey = f"{self._ns}tag::{tag}"
            try:
                await client.sadd(tkey, k)
            except Exception:
                pass

    # Health / lifecycle
    async def ping(self) -> dict[str, Any]:
        ok = False
        try:
            ok = await (await self._require_client()).ping()
        except Exception:
            ok = False
        return {"healthy": bool(ok), "latency_ms": 0.0, "backend": "redis"}

    async def ping_ok(self) -> bool:
        s = await self.ping()
        return bool(s.get("healthy", False))

    async def close(self) -> None:
        try:
            await (await self._require_client()).close()
        except Exception:
            pass

    # Async context manager
    async def __aenter__(self) -> AsyncRedisCache:
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self.close()

    async def _require_client(self) -> Any:
        if self._client is not None:
            return self._client
        self._client = AsyncRedisClient(
            host=str(self._cfg["host"]),
            port=int(self._cfg["port"]),
            db=int(self._cfg["db"]),
            password=self._password,
            ssl=bool(self._cfg["ssl"]),
            decode_responses=False,
        )
        return self._client


class AsyncRedisSentinelCache(AsyncRedisCache):
    """Async Redis cache configured via Redis Sentinel (redis.asyncio).

    Creates a sentinel connection and injects a master client into AsyncRedisCache.
    """

    def __init__(
        self,
        *,
        sentinels: list[tuple[str, int]],
        service_name: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        db: int = 0,
        ssl: bool = False,
        namespace: Optional[str] = None,
        serializer: Optional[Any] = None,
    ) -> None:
        try:
            from redis.asyncio.sentinel import Sentinel
        except Exception as e:  # pragma: no cover
            raise RuntimeError("redis.asyncio.sentinel is not available; install redis>=4") from e

        sentinel = Sentinel(sentinels, socket_timeout=2, ssl=ssl)
        client = sentinel.master_for(service_name, db=db, username=username, password=password, ssl=ssl)
        # Inject client
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


class AsyncRedisClusterCache(AsyncRedisCache):
    """Async Redis cache configured for Redis Cluster (redis.asyncio)."""

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
            from redis.asyncio.cluster import RedisCluster
        except Exception as e:  # pragma: no cover
            raise RuntimeError("redis.asyncio.cluster not available; install redis>=5") from e

        # Prefer ClusterNode if available
        client = None
        try:
            try:
                from redis.asyncio.cluster import ClusterNode as cluster_node_cls
            except Exception:
                cluster_node_cls = None  # type: ignore

            if cluster_node_cls is not None:
                cluster_nodes = [cluster_node_cls(n["host"], int(n.get("port", 6379))) for n in nodes]
                try:
                    client = RedisCluster(nodes=cluster_nodes, username=username, password=password, ssl=ssl)  # type: ignore[call-arg]
                except TypeError:
                    client = RedisCluster(
                        startup_nodes=[{"host": n["host"], "port": int(n.get("port", 6379))} for n in nodes],  # type: ignore[misc]
                        username=username,
                        password=password,
                        ssl=ssl,
                    )
            else:
                client = RedisCluster(  # type: ignore[unreachable]
                    startup_nodes=[{"host": n["host"], "port": int(n.get("port", 6379))} for n in nodes],
                    username=username,
                    password=password,
                    ssl=ssl,
                )
        except Exception:
            client = None

        if client is None:
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
