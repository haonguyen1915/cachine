import os

import pytest
from dotenv import load_dotenv

from cachine import logger_setup

load_dotenv()
logger_setup(level="DEBUG")


@pytest.fixture
def inmemory_cache():
    from cachine import InMemoryCache

    return InMemoryCache()


# Removed FakeRedis and redis_cache fixture in favor of real Redis fixture below.


def _truthy(v: str | None) -> bool:
    return (v or "").lower() in {"1", "true", "yes", "on"}


def _redis_cfg_from_env():
    host = os.getenv("REDIS_HOST", os.getenv("CACHE_HOST", "localhost"))
    port = int(os.getenv("REDIS_PORT", os.getenv("CACHE_PORT", "6379")))
    db = int(os.getenv("REDIS_DB", os.getenv("CACHE_DB", "0")))
    password = os.getenv("REDIS_PASSWORD", os.getenv("CACHE_PASSWORD", None)) or None
    ssl = (os.getenv("REDIS_SSL", os.getenv("CACHE_SSL", "false")).lower() in {"1", "true", "yes"})
    return dict(host=host, port=port, db=db, password=password, ssl=ssl)


@pytest.fixture
def redis_sync_cache():
    """Real Redis sync cache configured via env.

    Enable by setting RUN_REDIS_TESTS to a truthy value.
    Uses REDIS_* (or CACHE_*) env vars for connection.
    """
    if not _truthy(os.getenv("RUN_REDIS_TESTS")):
        pytest.skip("RUN_REDIS_TESTS not enabled")
    try:
        import redis
    except Exception:
        pytest.skip("redis package is not installed")

    from cachine.backends.redis.sync import RedisCache
    from cachine.serializers import JSONSerializer

    cfg = _redis_cfg_from_env()
    import uuid
    ns = f"ut:{uuid.uuid4().hex}"
    cache = RedisCache(namespace=ns, serializer=JSONSerializer(), **cfg)
    try:
        yield cache
    finally:
        try:
            # Clear keys for this namespace then close
            cache.clear()
            cache.close()
        except Exception:
            pass
