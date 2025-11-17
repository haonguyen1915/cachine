import os
import uuid
from typing import Any

import pytest
import pytest_asyncio
from dotenv import load_dotenv

from cachine import logger_setup
from cachine.backends.redis.async_ import AsyncRedisCache
from cachine.backends.redis.sync import RedisCache
from cachine.models.redis_config import RedisClusterConfig, RedisSingleConfig
from cachine.serializers import JSONSerializer
from cachine.utils import parse_redis_url

load_dotenv()
logger_setup(level="DEBUG")


@pytest.fixture
def inmemory_cache() -> Any:
    from cachine import InMemoryCache

    return InMemoryCache()


@pytest.fixture
def redis_cache() -> RedisCache:
    """Real Redis sync cache configured via env.

    Enable by setting RUN_REDIS_TESTS to a truthy value.
    Uses REDIS_* (or CACHE_*) env vars for connection.
    """

    redis_config: RedisSingleConfig = parse_redis_url(os.getenv("REDIS_SINGLE_URL"))
    ns = f"ut:{uuid.uuid4().hex}"
    cache = RedisCache(redis_config, namespace=ns, serializer=JSONSerializer())
    try:
        yield cache
    finally:
        try:
            # Clear keys for this namespace then close
            cache.clear()
            cache.close()
        except Exception as e:
            pass


@pytest.fixture
def redis_cluster_cache() -> Any:
    """Real Redis sync cache configured via env.

    Enable by setting RUN_REDIS_TESTS to a truthy value.
    Uses REDIS_* (or CACHE_*) env vars for connection.
    """

    redis_config: RedisClusterConfig = parse_redis_url(os.getenv("REDIS_CLUSTER_URL"))
    ns = f"ut:{uuid.uuid4().hex}"
    cache = RedisCache(redis_config, namespace=ns, serializer=JSONSerializer())
    try:
        yield cache
    finally:
        try:
            # Clear keys for this namespace then close
            cache.clear()
            cache.close()
        except Exception as e:
            pass


@pytest_asyncio.fixture
async def a_redis_cache() -> AsyncRedisCache:
    cfg_obj: RedisSingleConfig = parse_redis_url(os.getenv("REDIS_SINGLE_URL"))
    ns = f"ut:{uuid.uuid4().hex}"
    cache = AsyncRedisCache(cfg_obj, namespace=ns, serializer=JSONSerializer())
    try:
        yield cache
    finally:
        try:
            await cache.clear()
            await cache.close()
        except Exception:
            pass


@pytest_asyncio.fixture
async def a_redis_cluster_cache() -> Any:
    cfg_obj: RedisClusterConfig = parse_redis_url(os.getenv("REDIS_SINGLE_URL"))
    ns = f"ut:{uuid.uuid4().hex}"
    cache = AsyncRedisCache(cfg_obj, namespace=ns, serializer=JSONSerializer())
    try:
        yield cache
    finally:
        try:
            await cache.clear()
            await cache.close()
        except Exception:
            pass
