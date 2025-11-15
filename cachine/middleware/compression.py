from __future__ import annotations

from typing import Any

from .base import BaseMiddleware


class CompressionMiddleware(BaseMiddleware):
    def __init__(self, cache: Any, *, algorithm: str = "gzip", min_size: int = 0) -> None:
        super().__init__(cache)
        self.algorithm = algorithm
        self.min_size = min_size
