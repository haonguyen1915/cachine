from __future__ import annotations

from .base import BaseMiddleware


class EncryptionMiddleware(BaseMiddleware):
    def __init__(self, cache, *, key: str, key_id: str | None = None):
        super().__init__(cache)
        self.key = key
        self.key_id = key_id or "v1"

