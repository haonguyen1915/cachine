from __future__ import annotations

import pickle
from typing import Any

from ..exceptions import DeserializationError, SerializationError
from .base import Serializer


class PickleSerializer(Serializer):
    """Serialize values using Python pickle.

    Uses the highest available protocol.
    """

    def dumps(self, value: Any) -> bytes:
        """Serialize a Python object to pickle bytes.

        Args:
            value (Any): Python object.

        Returns:
            bytes: Pickled payload.

        Raises:
            SerializationError: If serialization fails.
        """
        try:
            return pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)
        except Exception as e:  # pragma: no cover
            raise SerializationError(str(e)) from e

    def loads(self, data: bytes) -> Any:
        """Deserialize pickle bytes to a Python object.

        Args:
            data (bytes): Pickled payload.

        Returns:
            Any: Decoded Python object.

        Raises:
            DeserializationError: If deserialization fails.
        """
        try:
            return pickle.loads(data)
        except Exception as e:  # pragma: no cover
            raise DeserializationError(str(e)) from e
