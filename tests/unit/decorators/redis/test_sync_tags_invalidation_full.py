from cachine import cached


def test_tags_full_invalidation_redis(redis_sync_cache):
    cache = redis_sync_cache
    calls = {"n": 0}

    @cached(
        cache,
        ttl=60,
        stale_ttl=30,
        tags=lambda uid: ["users", f"user:{uid}"],
        tags_from_result=lambda u: [f"role:{u['role']}"] if u else [],
    )
    def get_user(uid: int):
        calls["n"] += 1
        return {"id": uid, "role": "admin" if uid == 1 else "member"}

    # Populate two entries and confirm caching
    assert get_user(1) == {"id": 1, "role": "admin"}
    assert get_user(2) == {"id": 2, "role": "member"}
    assert get_user(1) == {"id": 1, "role": "admin"}
    assert get_user(2) == {"id": 2, "role": "member"}
    assert calls["n"] == 2

    # Invalidate by a specific role tag
    removed = cache.invalidate_tags(["role:admin"])  # type: ignore[attr-defined]
    assert removed >= 1
    # user 1 should recompute; user 2 remains cached
    assert get_user(1) == {"id": 1, "role": "admin"}
    assert get_user(2) == {"id": 2, "role": "member"}
    assert calls["n"] == 3

    # Invalidate by users namespace and specific user tag
    removed = cache.invalidate_tags(["users", "user:2"])  # type: ignore[attr-defined]
    assert removed >= 1
    assert get_user(1) == {"id": 1, "role": "admin"}
    assert get_user(2) == {"id": 2, "role": "member"}
    assert calls["n"] == 5
