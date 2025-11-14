from __future__ import annotations

import pickle
from typing import Any

from ..exceptions import DeserializationError, SerializationError
from .base import Serializer


class PickleSerializer(Serializer):
    def dumps(self, value: Any) -> bytes:
        try:
            return pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)
        except Exception as e:  # pragma: no cover
            raise SerializationError(str(e)) from e

    def loads(self, data: bytes) -> Any:
        try:
            return pickle.loads(data)
        except Exception as e:  # pragma: no cover
            raise DeserializationError(str(e)) from e

