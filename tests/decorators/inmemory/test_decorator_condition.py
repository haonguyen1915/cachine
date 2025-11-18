"""Tests for condition and enabled parameters in cached decorator."""

from __future__ import annotations

from cachine import InMemoryCache
from cachine.decorators import cached


class TestConditionParameter:
    """Tests for the condition parameter."""

    def test_condition_prevents_store(self) -> None:
        """Test that condition prevents caching when False."""
        cache = InMemoryCache()
        calls = {"n": 0}

        @cached(cache=cache, ttl=60, condition=lambda res: res > 0)
        def compute(x: int) -> int:
            calls["n"] += 1
            return x

        # First call with negative result -> condition False -> no store
        assert compute(-1) == -1
        # Second call with same args recomputes (not stored)
        assert compute(-1) == -1
        assert calls["n"] == 2

        # Positive result -> condition True -> store
        assert compute(5) == 5
        # Cached hit, no recompute
        assert compute(5) == 5
        assert calls["n"] == 3

    def test_condition_with_complex_result(self) -> None:
        """Test condition with complex result types."""
        cache = InMemoryCache()
        calls = {"n": 0}

        # Only cache successful responses
        @cached(cache=cache, ttl=60, condition=lambda res: res.get("success", False))
        def api_call(user_id: int) -> dict:
            calls["n"] += 1
            if user_id < 0:
                return {"success": False, "error": "Invalid user_id"}
            return {"success": True, "user_id": user_id}

        # Failed result - not cached
        result1 = api_call(-1)
        assert result1["success"] is False
        _ = api_call(-1)
        assert calls["n"] == 2

        # Successful result - cached
        result3 = api_call(123)
        assert result3["success"] is True
        _ = api_call(123)
        assert calls["n"] == 3  # No new call for cached result


class TestEnabledParameter:
    """Tests for the enabled parameter."""

    def test_enabled_static_true(self) -> None:
        """Test that enabled=True allows caching."""
        cache = InMemoryCache()
        calls = {"n": 0}

        @cached(cache=cache, ttl=60, enabled=True)
        def compute(x: int) -> int:
            calls["n"] += 1
            return x * 2

        assert compute(5) == 10
        assert compute(5) == 10  # Cached
        assert calls["n"] == 1

    def test_enabled_static_false(self) -> None:
        """Test that enabled=False bypasses caching."""
        cache = InMemoryCache()
        calls = {"n": 0}

        @cached(cache=cache, ttl=60, enabled=False)
        def compute(x: int) -> int:
            calls["n"] += 1
            return x * 2

        assert compute(5) == 10
        assert compute(5) == 10  # Not cached, recomputed
        assert calls["n"] == 2

    def test_enabled_dynamic_from_args(self) -> None:
        """Test dynamic enabled based on function arguments."""
        cache = InMemoryCache()
        calls = {"n": 0}

        # Only cache when use_cache=True
        @cached(cache=cache, ttl=60, enabled=lambda k, use_cache=True: use_cache)
        def fetch_data(k: str, use_cache: bool = True) -> str:
            calls["n"] += 1
            return f"data_{k}"

        # Caching disabled
        assert fetch_data("a", use_cache=False) == "data_a"
        assert fetch_data("a", use_cache=False) == "data_a"
        assert calls["n"] == 2  # Recomputed both times

        # Caching enabled
        assert fetch_data("b", use_cache=True) == "data_b"
        assert fetch_data("b", use_cache=True) == "data_b"
        assert calls["n"] == 3  # Only computed once

        # Default is True (caching enabled)
        assert fetch_data("c") == "data_c"
        assert fetch_data("c") == "data_c"
        assert calls["n"] == 4  # Only computed once

    def test_enabled_based_on_user_type(self) -> None:
        """Test enabled based on user type (admin vs regular)."""
        cache = InMemoryCache()
        calls = {"n": 0}

        # Only cache for admin users
        @cached(cache=cache, ttl=60, enabled=lambda user_id, is_admin=False: is_admin)
        def get_sensitive_data(user_id: int, is_admin: bool = False) -> dict:
            calls["n"] += 1
            return {"user_id": user_id, "data": "sensitive"}

        # Regular user - no caching
        get_sensitive_data(123, is_admin=False)
        get_sensitive_data(123, is_admin=False)
        assert calls["n"] == 2

        # Admin user - cached
        get_sensitive_data(456, is_admin=True)
        get_sensitive_data(456, is_admin=True)
        assert calls["n"] == 3

    def test_enabled_with_conditional_logic(self) -> None:
        """Test enabled with complex conditional logic."""
        cache = InMemoryCache()
        calls = {"n": 0}

        def should_cache(operation: str, user_tier: str = "free") -> bool:
            # Premium users always get caching
            if user_tier == "premium":
                return True
            # Free users only get caching for read operations
            return operation == "read"

        @cached(cache=cache, ttl=60, enabled=should_cache)
        def perform_operation(operation: str, user_tier: str = "free") -> str:
            calls["n"] += 1
            return f"{operation}_result"

        # Free user, read operation - cached
        perform_operation("read", "free")
        perform_operation("read", "free")
        assert calls["n"] == 1

        # Free user, write operation - not cached
        perform_operation("write", "free")
        perform_operation("write", "free")
        assert calls["n"] == 3

        # Premium user, write operation - cached
        perform_operation("write", "premium")
        perform_operation("write", "premium")
        assert calls["n"] == 4

    def test_enabled_with_error_fallback(self) -> None:
        """Test that errors in enabled callable fall back to True (enabled)."""
        cache = InMemoryCache()
        calls = {"n": 0}

        def buggy_enabled(x: int) -> bool:
            if x == 999:
                raise ValueError("Oops!")
            return x > 10

        @cached(cache=cache, ttl=60, enabled=buggy_enabled)
        def compute(x: int) -> int:
            calls["n"] += 1
            return x * 2

        # Normal case: x > 10 -> enabled
        compute(20)
        compute(20)
        assert calls["n"] == 1

        # Normal case: x <= 10 -> disabled
        compute(5)
        compute(5)
        assert calls["n"] == 3

        # Error case: falls back to enabled=True
        compute(999)
        compute(999)
        assert calls["n"] == 4  # Cached due to fallback


class TestConditionAndEnabledTogether:
    """Tests for using condition and enabled together."""

    def test_condition_and_enabled_together(self) -> None:
        """Test that both condition and enabled work together correctly."""
        cache = InMemoryCache()
        calls = {"n": 0}

        @cached(
            cache=cache,
            ttl=60,
            enabled=lambda x, use_cache=True: use_cache,
            condition=lambda res: res > 0,
        )
        def compute(x: int, use_cache: bool = True) -> int:
            calls["n"] += 1
            return x

        # Enabled=False -> no caching regardless of condition
        compute(10, use_cache=False)
        compute(10, use_cache=False)
        assert calls["n"] == 2

        # Enabled=True, condition=False (negative result) -> no caching
        compute(-5, use_cache=True)
        compute(-5, use_cache=True)
        assert calls["n"] == 4

        # Enabled=True, condition=True (positive result) -> cached
        compute(10, use_cache=True)
        compute(10, use_cache=True)
        assert calls["n"] == 5
