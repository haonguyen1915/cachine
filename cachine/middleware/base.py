from typing import Any


class BaseMiddleware:
    """Base middleware that forwards attribute access to the wrapped cache."""

    def __init__(self, cache: Any) -> None:
        self._cache = cache

    def __getattr__(self, item: str) -> Any:  # delegate to underlying cache
        return getattr(self._cache, item)
