from __future__ import annotations

from .base import BaseMiddleware


class CompressionMiddleware(BaseMiddleware):
    def __init__(self, cache, *, algorithm: str = "gzip", min_size: int = 0):
        super().__init__(cache)
        self.algorithm = algorithm
        self.min_size = min_size

