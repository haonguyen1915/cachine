from __future__ import annotations

from typing import Any

from .base import BaseMiddleware


class EncryptionMiddleware(BaseMiddleware):
    def __init__(self, cache: Any, *, key: str, key_id: str | None = None) -> None:
        super().__init__(cache)
        self.key = key
        self.key_id = key_id or "v1"
