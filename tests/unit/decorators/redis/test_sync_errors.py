import time

import pytest

from cachine import cached


def test_exception_not_cached_and_propagates_redis(redis_sync_cache):
    cache = redis_sync_cache
    state = {"fail": True, "calls": 0}

    @cached(cache, ttl=60)
    def compute(x: int) -> int:
        state["calls"] += 1
        if state["fail"]:
            raise ValueError("boom")
        return x * 2

    with pytest.raises(ValueError):
        compute(2)
    assert state["calls"] == 1

    state["fail"] = False
    assert compute(2) == 4
    assert compute(2) == 4
    assert state["calls"] == 2


def test_stale_ttl_refresh_error_redis(redis_sync_cache):
    cache = redis_sync_cache
    state = {"fail": False, "n": 0}

    @cached(cache, ttl=1, stale_ttl=3, singleflight=True)
    def expensive() -> int:
        state["n"] += 1
        if state["fail"]:
            raise RuntimeError("refresh failed")
        return state["n"]

    assert expensive() == 1
    time.sleep(1.2)
    state["fail"] = True
    assert expensive() == 1  # stale
    state["fail"] = False
    _ = expensive()  # stale, triggers refresh
    time.sleep(0.2)
    # Failed refresh increments before raising; next success stores 3
    assert expensive() == 3
