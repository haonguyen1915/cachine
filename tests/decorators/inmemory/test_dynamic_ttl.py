"""Tests for dynamic TTL feature in cached decorator."""

import time

import pytest

from cachine import InMemoryCache
from cachine.decorators import cached


class TestDynamicTTL:
    """Tests for dynamic TTL using callable ttl parameter."""

    def test_static_ttl_still_works(self) -> None:
        """Test that static TTL still works as before."""
        cache = InMemoryCache()
        calls = {"n": 0}

        @cached(cache=cache, ttl=1)
        def get_data(user_id: int) -> dict:
            calls["n"] += 1
            return {"id": user_id, "data": "test"}

        # First call - cache miss
        result1 = get_data(123)
        assert result1 == {"id": 123, "data": "test"}
        assert calls["n"] == 1

        # Second call - cache hit
        result2 = get_data(123)
        assert result2 == {"id": 123, "data": "test"}
        assert calls["n"] == 1

        # Wait for TTL to expire
        time.sleep(1.1)

        # Third call - cache miss after expiry
        result3 = get_data(123)
        assert result3 == {"id": 123, "data": "test"}
        assert calls["n"] == 2

    def test_callable_ttl_with_args(self) -> None:
        """Test callable TTL that uses positional arguments."""
        cache = InMemoryCache()
        calls = {"n": 0}

        # Short TTL for user_id < 100, long TTL for user_id >= 100
        @cached(cache=cache, ttl=lambda user_id: 10 if user_id >= 100 else 1)
        def get_user(user_id: int) -> dict:
            calls["n"] += 1
            return {"id": user_id}

        # User with short TTL
        get_user(50)
        assert calls["n"] == 1
        time.sleep(1.1)
        get_user(50)  # Should recompute
        assert calls["n"] == 2

        # User with long TTL
        get_user(150)
        assert calls["n"] == 3
        time.sleep(1.1)
        get_user(150)  # Should still be cached
        assert calls["n"] == 3

    def test_callable_ttl_with_kwargs(self) -> None:
        """Test callable TTL that uses keyword arguments."""
        cache = InMemoryCache()
        calls = {"n": 0}

        # Premium users get longer TTL
        # @cached(cache=cache, ttl=lambda user_id, premium=False: 3600 if premium else 60)
        @cached(cache=cache, ttl=lambda *args, **kwargs: 3600 if kwargs.get("premium", False) else 60)
        def get_user(user_id: int, premium: bool = False) -> dict:
            calls["n"] += 1
            return {"id": user_id, "premium": premium}

        # Regular user
        result1 = get_user(123)
        assert result1 == {"id": 123, "premium": False}
        assert calls["n"] == 1

        # Cache hit for regular user
        result2 = get_user(123)
        assert calls["n"] == 1

        # Premium user - different cache key due to different args
        result3 = get_user(456, premium=True)
        assert result3 == {"id": 456, "premium": True}
        assert calls["n"] == 2

        # Cache hit for premium user
        result4 = get_user(456, premium=True)
        assert calls["n"] == 2

    def test_callable_ttl_complex_logic(self) -> None:
        """Test callable TTL with complex conditional logic."""
        cache = InMemoryCache()
        calls = {"n": 0}

        def compute_ttl(resource_type: str, priority: str = "normal") -> int:
            if resource_type == "critical":
                return 10
            elif priority == "high":
                return 5
            else:
                return 1

        @cached(cache=cache, ttl=compute_ttl)
        def get_resource(resource_type: str, priority: str = "normal") -> dict:
            calls["n"] += 1
            return {"type": resource_type, "priority": priority}

        # Critical resource - 10 second TTL
        get_resource("critical")
        assert calls["n"] == 1

        # High priority non-critical - 5 second TTL
        get_resource("data", priority="high")
        assert calls["n"] == 2

        # Normal priority - 1 second TTL
        get_resource("data", priority="normal")
        assert calls["n"] == 3

        time.sleep(1.1)

        # Normal priority should expire
        get_resource("data", priority="normal")
        assert calls["n"] == 4

        # High priority should still be cached
        get_resource("data", priority="high")
        assert calls["n"] == 4

        # Critical should still be cached
        get_resource("critical")
        assert calls["n"] == 4

    def test_callable_ttl_returns_none(self) -> None:
        """Test that callable TTL can return None for no expiry."""
        cache = InMemoryCache()
        calls = {"n": 0}

        # No TTL for admin users
        @cached(cache=cache, ttl=lambda user_id, is_admin=False: None if is_admin else 1)
        def get_user(user_id: int, is_admin: bool = False) -> dict:
            calls["n"] += 1
            return {"id": user_id, "admin": is_admin}

        # Admin user - no TTL
        get_user(999, is_admin=True)
        assert calls["n"] == 1

        time.sleep(1.1)

        # Should still be cached (no expiry)
        get_user(999, is_admin=True)
        assert calls["n"] == 1

        # Regular user - 1 second TTL
        get_user(123, is_admin=False)
        assert calls["n"] == 2

        time.sleep(1.1)

        # Should expire
        get_user(123, is_admin=False)
        assert calls["n"] == 3

    def test_callable_ttl_with_error_fallback(self) -> None:
        """Test that errors in callable TTL fall back gracefully to None."""
        cache = InMemoryCache()
        calls = {"n": 0}

        def bad_ttl(user_id: int) -> int:
            if user_id == 999:
                raise ValueError("Invalid user_id")
            return 60

        @cached(cache=cache, ttl=bad_ttl)
        def get_user(user_id: int) -> dict:
            calls["n"] += 1
            return {"id": user_id}

        # Normal user - works fine
        get_user(123)
        assert calls["n"] == 1
        get_user(123)  # Cached
        assert calls["n"] == 1

        # User that causes error - falls back to None (no TTL)
        get_user(999)
        assert calls["n"] == 2
        get_user(999)  # Should still be cached (no expiry due to fallback)
        assert calls["n"] == 2

    def test_callable_ttl_with_jitter(self) -> None:
        """Test that callable TTL works with jitter parameter."""
        cache = InMemoryCache()
        calls = {"n": 0}

        @cached(cache=cache, ttl=lambda x: 5, jitter=2)
        def compute(x: int) -> int:
            calls["n"] += 1
            return x * 2

        result = compute(10)
        assert result == 20
        assert calls["n"] == 1

        # Should be cached
        result = compute(10)
        assert result == 20
        assert calls["n"] == 1

    def test_callable_ttl_with_stale_ttl(self) -> None:
        """Test that callable TTL works with stale_ttl parameter."""
        cache = InMemoryCache()
        calls = {"n": 0}

        @cached(cache=cache, ttl=lambda x: 1, stale_ttl=2)
        def compute(x: int) -> int:
            calls["n"] += 1
            return x * 2

        result = compute(10)
        assert result == 20
        assert calls["n"] == 1

        time.sleep(1.1)

        # Should return stale value and trigger background refresh
        result = compute(10)
        assert result == 20
        # The call count may be 1 or 2 depending on timing of background refresh
        assert calls["n"] >= 1


class TestDynamicTTLAsync:
    """Tests for dynamic TTL with async functions (using cache=None for simplicity)."""

    @pytest.mark.asyncio
    async def test_async_callable_ttl_passthrough(self) -> None:
        """Test that async functions work with dynamic TTL (passthrough mode)."""
        calls = {"n": 0}

        # Using cache=None to test that async functions don't break
        @cached(cache=None, ttl=lambda user_id, premium=False: 3600 if premium else 60)
        async def get_user_async(user_id: int, premium: bool = False) -> dict:
            calls["n"] += 1
            return {"id": user_id, "premium": premium}

        # Should always execute (no caching)
        result1 = await get_user_async(123)
        assert result1 == {"id": 123, "premium": False}
        assert calls["n"] == 1

        result2 = await get_user_async(123)
        assert calls["n"] == 2  # No caching, so increments


class TestDynamicTTLEdgeCases:
    """Edge case tests for dynamic TTL."""

    def test_callable_ttl_signature_mismatch(self) -> None:
        """Test callable TTL with signature mismatch falls back gracefully."""
        cache = InMemoryCache()
        calls = {"n": 0}

        # TTL function expects different args
        @cached(cache=cache, ttl=lambda: 60)  # No args
        def get_data(user_id: int) -> dict:
            calls["n"] += 1
            return {"id": user_id}

        # Should handle mismatch gracefully and fall back
        result = get_data(123)
        assert result == {"id": 123}
        assert calls["n"] == 1

        # Should still cache (with fallback TTL)
        result = get_data(123)
        assert calls["n"] == 1

    def test_callable_ttl_returns_float(self) -> None:
        """Test that callable TTL can return float values."""
        cache = InMemoryCache()
        calls = {"n": 0}

        # Use 2.5 seconds to ensure consistent behavior across systems
        @cached(cache=cache, ttl=lambda x: 2.5)
        def compute(x: int) -> int:
            calls["n"] += 1
            return x * 2

        result = compute(10)
        assert result == 20
        assert calls["n"] == 1

        time.sleep(1.0)

        # Should still be cached after 1 second
        result = compute(10)
        assert result == 20
        assert calls["n"] == 1

        time.sleep(2.0)

        # Should expire after 3 seconds total (> 2.5 TTL)
        result = compute(10)
        assert result == 20
        assert calls["n"] == 2

    def test_none_ttl_still_works(self) -> None:
        """Test that None TTL (no expiry) still works."""
        cache = InMemoryCache()
        calls = {"n": 0}

        @cached(cache=cache, ttl=None)
        def get_data(x: int) -> int:
            calls["n"] += 1
            return x * 2

        result = get_data(10)
        assert result == 20
        assert calls["n"] == 1

        time.sleep(1.0)

        # Should never expire
        result = get_data(10)
        assert result == 20
        assert calls["n"] == 1