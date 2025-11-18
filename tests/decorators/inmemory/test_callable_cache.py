"""Tests for callable cache support in the @cached decorator."""

from cachine import InMemoryCache
from cachine.decorators import cached


def test_callable_cache_basic() -> None:
    """Test that callable cache is resolved and works correctly."""
    cache = InMemoryCache()
    calls = {"n": 0}

    # Use a callable that returns the cache instance
    def get_cache():
        return cache

    @cached(get_cache, ttl=60)
    def add(a: int, b: int) -> int:
        calls["n"] += 1
        return a + b

    # First call should cache the result
    assert add(1, 2) == 3
    assert calls["n"] == 1

    # Second call should return cached result
    assert add(1, 2) == 3
    assert calls["n"] == 1

    # Different args should trigger new computation
    assert add(2, 3) == 5
    assert calls["n"] == 2


def test_callable_cache_deferred_creation() -> None:
    """Test that callable cache is resolved during decoration time."""
    cache_created = {"flag": False}
    cache_instance = None
    calls = {"n": 0}

    def create_cache():
        nonlocal cache_instance
        cache_created["flag"] = True
        cache_instance = InMemoryCache()
        return cache_instance

    # Cache should not be created yet
    assert cache_created["flag"] is False

    # Decorator application resolves the callable cache immediately
    @cached(create_cache, ttl=60)
    def multiply(a: int, b: int) -> int:
        calls["n"] += 1
        return a * b

    # Cache is created during decoration, not lazily
    assert cache_created["flag"] is True
    assert cache_instance is not None

    # Verify caching works
    result = multiply(3, 4)
    assert result == 12
    assert calls["n"] == 1

    # Second call uses cache
    assert multiply(3, 4) == 12
    assert calls["n"] == 1


def test_callable_cache_error_fallback() -> None:
    """Test that callable cache falls back to pass-through mode on error."""
    calls = {"n": 0}

    def failing_cache():
        raise RuntimeError("Cache creation failed")

    @cached(failing_cache, ttl=60)
    def subtract(a: int, b: int) -> int:
        calls["n"] += 1
        return a - b

    # Should work without caching (pass-through mode)
    assert subtract(10, 5) == 5
    assert calls["n"] == 1

    # Each call should execute the function (no caching)
    assert subtract(10, 5) == 5
    assert calls["n"] == 2


def test_callable_cache_with_features() -> None:
    """Test callable cache with various caching features."""
    cache = InMemoryCache()

    def get_cache():
        return cache

    calls = {"n": 0}

    @cached(
        get_cache,
        ttl=60,
        condition=lambda r: r > 0,
        tags=["math"],
        cache_none=False,
    )
    def divide(a: int, b: int) -> int:
        calls["n"] += 1
        if b == 0:
            return 0
        return a // b

    # Positive result should be cached
    assert divide(10, 2) == 5
    assert calls["n"] == 1
    assert divide(10, 2) == 5
    assert calls["n"] == 1

    # Zero result should not be cached (condition=False)
    assert divide(10, 0) == 0
    assert calls["n"] == 2
    assert divide(10, 0) == 0
    assert calls["n"] == 3

    # Invalidate by tag
    removed = cache.invalidate_tags(["math"])
    assert removed >= 1

    # Should recompute after invalidation
    assert divide(10, 2) == 5
    assert calls["n"] == 4


def test_callable_cache_multiple_decorators() -> None:
    """Test that multiple decorators can use different callable caches."""
    cache1 = InMemoryCache()
    cache2 = InMemoryCache()

    def get_cache1():
        return cache1

    def get_cache2():
        return cache2

    calls1 = {"n": 0}
    calls2 = {"n": 0}

    @cached(get_cache1, ttl=60)
    def func1(x: int) -> int:
        calls1["n"] += 1
        return x * 2

    @cached(get_cache2, ttl=60)
    def func2(x: int) -> int:
        calls2["n"] += 1
        return x * 3

    # Each function should use its own cache
    assert func1(5) == 10
    assert calls1["n"] == 1
    assert func1(5) == 10
    assert calls1["n"] == 1

    assert func2(5) == 15
    assert calls2["n"] == 1
    assert func2(5) == 15
    assert calls2["n"] == 1

    # Verify they use different caches
    cache1.clear()
    assert func1(5) == 10
    assert calls1["n"] == 2  # Recomputed after clear

    assert func2(5) == 15
    assert calls2["n"] == 1  # Still cached in cache2


def test_callable_cache_passthrough_on_none() -> None:
    """Test that callable returning None falls back to pass-through mode."""
    calls = {"n": 0}

    def get_none_cache():
        return None

    @cached(get_none_cache, ttl=60)
    def process(x: int) -> int:
        calls["n"] += 1
        return x * 3

    # Should work without caching (pass-through mode due to None cache)
    result = process(5)
    assert result == 15
    assert calls["n"] == 1

    # Each call should execute the function (no caching)
    result = process(5)
    assert result == 15
    assert calls["n"] == 2


def test_callable_cache_with_enabled_predicate() -> None:
    """Test callable cache with enabled predicate."""
    cache = InMemoryCache()
    calls = {"n": 0}

    def get_cache():
        return cache

    @cached(get_cache, ttl=60, enabled=lambda x: x > 5)
    def process(x: int) -> int:
        calls["n"] += 1
        return x * 2

    # x=3: enabled=False, should not cache
    assert process(3) == 6
    assert calls["n"] == 1
    assert process(3) == 6
    assert calls["n"] == 2  # Not cached

    # x=10: enabled=True, should cache
    assert process(10) == 20
    assert calls["n"] == 3
    assert process(10) == 20
    assert calls["n"] == 3  # Cached


def test_callable_cache_with_dynamic_ttl() -> None:
    """Test callable cache with dynamic TTL."""
    cache = InMemoryCache()
    calls = {"n": 0}

    def get_cache():
        return cache

    @cached(get_cache, ttl=lambda x: 60 if x > 5 else 10)
    def compute(x: int) -> int:
        calls["n"] += 1
        return x * x

    # Should cache with appropriate TTL
    assert compute(3) == 9
    assert calls["n"] == 1
    assert compute(3) == 9
    assert calls["n"] == 1

    assert compute(10) == 100
    assert calls["n"] == 2
    assert compute(10) == 100
    assert calls["n"] == 2
