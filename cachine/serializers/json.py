from __future__ import annotations

import json
from typing import Any

from ..exceptions import DeserializationError, SerializationError
from .base import Serializer


class JSONSerializer(Serializer):
    def dumps(self, value: Any) -> bytes:
        try:
            return json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        except Exception as e:  # pragma: no cover - simple passthrough
            raise SerializationError(str(e)) from e

    def loads(self, data: bytes) -> Any:
        try:
            return json.loads(data.decode("utf-8"))
        except Exception as e:  # pragma: no cover - simple passthrough
            raise DeserializationError(str(e)) from e

