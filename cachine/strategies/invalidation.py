from __future__ import annotations

from typing import Any, Optional


class TagBasedInvalidation:
    """Optional wrapper for tag-based invalidation.

    In practice, prefer calling `cache.invalidate_tags(tags)` directly when available.
    This strategy is provided for compatibility with the documented interface.
    """

    def __init__(self, cache: Any) -> None:
        self._cache = cache

    async def set(self, key: str, value: Any, *, ttl: Optional[int] = None, tags: Optional[list[str]] = None) -> None:
        # Set the value and attach tags if the backend supports it.
        if hasattr(self._cache, "set"):
            res = self._cache.set(key, value, ttl=ttl)  # type: ignore[misc]
            if hasattr(res, "__await__"):
                await res
        if tags and hasattr(self._cache, "add_tags"):
            attach = getattr(self._cache, "add_tags")
            out = attach(key, tags)
            if hasattr(out, "__await__"):
                await out

    async def invalidate_tag(self, tag: str) -> int:
        if hasattr(self._cache, "invalidate_tags"):
            res = self._cache.invalidate_tags([tag])  # type: ignore[misc]
            if hasattr(res, "__await__"):
                return await res
            return int(res) if res is not None else 0
        return 0
