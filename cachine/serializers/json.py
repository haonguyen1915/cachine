from __future__ import annotations

import json
from typing import Any

from ..exceptions import DeserializationError, SerializationError
from .base import Serializer


class JSONSerializer(Serializer):
    """Serialize values using JSON.

    Uses compact separators and UTF-8 encoding.
    """

    def dumps(self, value: Any) -> bytes:
        """Serialize a Python object to JSON bytes.

        Args:
            value (Any): JSON-serializable object.

        Returns:
            bytes: UTF-8 encoded JSON.

        Raises:
            SerializationError: If serialization fails.
        """
        try:
            return json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        except Exception as e:  # pragma: no cover - simple passthrough
            raise SerializationError(str(e)) from e

    def loads(self, data: bytes) -> Any:
        """Deserialize JSON bytes to a Python object.

        Args:
            data (bytes): UTF-8 encoded JSON.

        Returns:
            Any: Decoded Python object.

        Raises:
            DeserializationError: If deserialization fails.
        """
        try:
            return json.loads(data.decode("utf-8"))
        except Exception as e:  # pragma: no cover - simple passthrough
            raise DeserializationError(str(e)) from e
