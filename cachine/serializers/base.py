from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Serializer(ABC):
    """Abstract serializer interface for cache values.

    Implementations convert Python objects to bytes and back. Used by Redis caches.
    """

    @abstractmethod
    def dumps(self, value: Any) -> bytes:  # pragma: no cover - abstract
        """Serialize a value to bytes.

        Args:
            value (Any): Python object to serialize.

        Returns:
            bytes: Serialized byte payload.
        """

    @abstractmethod
    def loads(self, data: bytes) -> Any:  # pragma: no cover - abstract
        """Deserialize bytes into a Python object.

        Args:
            data (bytes): Serialized payload.

        Returns:
            Any: Deserialized Python object.
        """
