import os
import uuid
from typing import Any

import pytest
import pytest_asyncio
from dotenv import load_dotenv

from cachine import logger_setup
from cachine.backends.redis.async_ import AsyncRedisCache
from cachine.backends.redis.sync import RedisCache
from cachine.models.redis_config import RedisClusterConfig, RedisSentinelConfig, RedisSingleConfig
from cachine.serializers import JSONSerializer
from cachine.utils import parse_redis_url

load_dotenv()
logger_setup(level="DEBUG")

REDIS_MODE = os.environ.get("REDIS_MODE", "single")

if REDIS_MODE == "single":
    REDIS_URL = os.environ.get("REDIS_SINGLE_URL")
    print(f"Testing Redis single at {REDIS_URL}")
elif REDIS_MODE == "cluster":
    REDIS_URL = os.environ.get("REDIS_CLUSTER_URL")
    print(f"Testing Redis cluster at {REDIS_URL}")
elif REDIS_MODE == "sentinel":
    REDIS_URL = os.environ.get("REDIS_SENTINEL_URL")
    print(f"Testing Redis sentinel at {REDIS_URL}")
else:
    raise ValueError(f"Invalid REDIS_MODE: {REDIS_MODE}")


@pytest.fixture
def inmemory_cache() -> Any:
    from cachine import InMemoryCache

    return InMemoryCache()


@pytest.fixture
def redis_single_config() -> RedisSingleConfig:
    """Provide RedisSingleConfig for tests."""
    if REDIS_MODE != "single":
        pytest.skip("redis_single_config fixture requires REDIS_MODE=single")
    return parse_redis_url(REDIS_URL)


@pytest.fixture
def redis_cache() -> RedisCache:
    """Real Redis sync cache configured via env.

    Enable by setting RUN_REDIS_TESTS to a truthy value.
    Uses REDIS_* (or CACHE_*) env vars for connection.
    """
    if REDIS_MODE == "single":
        cfg_obj: RedisSingleConfig = parse_redis_url(REDIS_URL)
    elif REDIS_MODE == "cluster":
        cfg_obj: RedisClusterConfig = parse_redis_url(REDIS_URL)
    elif REDIS_MODE == "sentinel":
        cfg_obj: RedisSentinelConfig = parse_redis_url(REDIS_URL)
    else:
        raise ValueError(f"Invalid REDIS_MODE: {REDIS_MODE}")
    ns = f"ut:{uuid.uuid4().hex}"
    cache = RedisCache(cfg_obj, namespace=ns, serializer=JSONSerializer())
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
    if REDIS_MODE == "single":
        cfg_obj: RedisSingleConfig = parse_redis_url(REDIS_URL)
    elif REDIS_MODE == "cluster":
        cfg_obj: RedisClusterConfig = parse_redis_url(REDIS_URL)
    elif REDIS_MODE == "sentinel":
        cfg_obj: RedisSentinelConfig = parse_redis_url(REDIS_URL)
    else:
        raise ValueError(f"Invalid REDIS_MODE: {REDIS_MODE}")

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
